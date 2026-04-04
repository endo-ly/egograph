"""In-process step execution."""

from __future__ import annotations

import importlib
import inspect
import io
from contextlib import redirect_stderr, redirect_stdout
from multiprocessing import get_context
from queue import Empty
from typing import Any, Callable

from pipelines.domain.workflow import (
    StepDefinition,
    StepExecutionResult,
    StepRunStatus,
    WorkflowRun,
)
from pipelines.infrastructure.execution.log_store import LocalLogStore


class InProcessStepExecutor:
    """StepDefinition.callable_ref を Python 関数として実行する。"""

    def __init__(self, log_store: LocalLogStore) -> None:
        self._log_store = log_store

    def execute(
        self,
        *,
        workflow_id: str,
        run: WorkflowRun,
        step: StepDefinition,
        attempt_no: int,
    ) -> StepExecutionResult:
        """callable_ref を import して実行する。"""
        context = get_context("spawn")
        queue = context.Queue(maxsize=1)
        process = context.Process(
            target=_execute_callable_in_child,
            args=(step.callable_ref, run, queue),
        )
        process.start()
        process.join(timeout=step.timeout_seconds)

        if process.is_alive():
            process.terminate()
            process.join(timeout=1)
            stdout_text = ""
            stderr_text = f"TimeoutError: step timed out after {step.timeout_seconds}s"
            log_path = self._log_store.write_step_log(
                workflow_id=workflow_id,
                run_id=run.run_id,
                step_id=step.step_id,
                attempt_no=attempt_no,
                stdout_text=stdout_text,
                stderr_text=stderr_text,
            )
            return StepExecutionResult(
                status=StepRunStatus.FAILED,
                exit_code=None,
                stdout_tail=self._log_store.tail(stdout_text),
                stderr_tail=self._log_store.tail(stderr_text),
                log_path=log_path,
                result_summary=None,
                error_message=f"step timed out after {step.timeout_seconds}s",
            )

        payload = _read_child_payload(queue)
        status = StepRunStatus.SUCCEEDED if payload["ok"] else StepRunStatus.FAILED
        exit_code = 0 if payload["ok"] else 1
        stdout_text = str(payload["stdout"])
        stderr_text = str(payload["stderr"])
        log_path = self._log_store.write_step_log(
            workflow_id=workflow_id,
            run_id=run.run_id,
            step_id=step.step_id,
            attempt_no=attempt_no,
            stdout_text=stdout_text,
            stderr_text=stderr_text,
        )
        return StepExecutionResult(
            status=status,
            exit_code=exit_code,
            stdout_tail=self._log_store.tail(stdout_text),
            stderr_tail=self._log_store.tail(stderr_text),
            log_path=log_path,
            result_summary=payload["result_summary"],
            error_message=payload["error_message"],
        )

    @staticmethod
    def _load_callable(callable_ref: str | None) -> Callable[[], Any]:
        if not callable_ref:
            raise ValueError("callable_ref is required for in-process step")
        module_name, function_name = callable_ref.split(":", maxsplit=1)
        module = importlib.import_module(module_name)
        target = getattr(module, function_name)
        if not callable(target):
            raise TypeError(f"step target is not callable: {callable_ref}")
        return target

    @staticmethod
    def _invoke(target: Callable[..., Any], run: WorkflowRun) -> Any:
        signature = inspect.signature(target)
        if len(signature.parameters) == 0:
            return target()
        return target(run)


def _execute_callable_in_child(
    callable_ref: str | None,
    run: WorkflowRun,
    queue,
) -> None:
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    try:
        target = InProcessStepExecutor._load_callable(callable_ref)
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            result = InProcessStepExecutor._invoke(target, run)
        queue.put(
            {
                "ok": True,
                "stdout": stdout_buffer.getvalue(),
                "stderr": stderr_buffer.getvalue(),
                "result_summary": result if isinstance(result, dict) else None,
                "error_message": None,
            }
        )
    except Exception as exc:
        queue.put(
            {
                "ok": False,
                "stdout": stdout_buffer.getvalue(),
                "stderr": stderr_buffer.getvalue()
                + f"\n{type(exc).__name__}: {exc}",
                "result_summary": None,
                "error_message": str(exc),
            }
        )


def _read_child_payload(queue) -> dict[str, Any]:
    try:
        return queue.get_nowait()
    except Empty:
        return {
            "ok": False,
            "stdout": "",
            "stderr": "RuntimeError: step process exited without result",
            "result_summary": None,
            "error_message": "step process exited without result",
        }
