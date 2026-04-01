"""ツール実行ループとオーケストレーション。

LLMツール呼び出しの管理と並列実行を行います。
"""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator

from backend.domain.models.llm import StreamChunk
from backend.infrastructure.llm import LLMClient, Message, ToolCall
from backend.usecases.tools import Tool, ToolRegistry

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """ツール実行エラーの基底クラス。"""

    pass


class MaxIterationsExceeded(ToolExecutionError):
    """最大イテレーション到達時の例外。"""

    pass


class ToolExecutionResult:
    """ツール実行ループの結果。"""

    def __init__(
        self,
        final_message: Message,
        response_id: str,
        usage: dict | None,
        iterations: int,
    ):
        """ToolExecutionResultを初期化します。

        Args:
            final_message: 最終的なLLMメッセージ
            response_id: レスポンスID
            usage: トークン使用量情報
            iterations: 実行イテレーション回数
        """
        self.final_message = final_message
        self.response_id = response_id
        self.usage = usage
        self.iterations = iterations


class ToolExecutor:
    """LLMツール実行ループを管理するクラス。

    LLMとツール実行の繰り返しを管理し、最大イテレーション数とタイムアウトを制御します。
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
        max_iterations: int = 5,
    ):
        """ToolExecutorを初期化します。

        Args:
            llm_client: LLMクライアント
            tool_registry: ツールレジストリ
            max_iterations: 最大イテレーション回数（デフォルト: 5）
        """
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.max_iterations = max_iterations

    async def execute_loop(
        self,
        conversation_history: list[Message],
        tools: list[Tool] | None,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> ToolExecutionResult:
        """ツール実行ループを実行します。

        LLMがツール呼び出しを返す限り、ツールを実行して結果をLLMに返すループを実行します。
        最大イテレーション回数またはタイムアウトに達した場合は例外を発生させます。

        Args:
            conversation_history: チャットメッセージ履歴
            tools: 利用可能なツールのスキーマ
            temperature: 生成の多様性
            max_tokens: 最大トークン数
            timeout: 全体のタイムアウト秒数

        Returns:
            ToolExecutionResult: 実行結果

        Raises:
            MaxIterationsExceeded: 最大イテレーション数に到達した場合
            asyncio.TimeoutError: タイムアウトした場合
        """
        iteration = 0
        loop = asyncio.get_running_loop()
        start_time = loop.time()

        while iteration < self.max_iterations:
            iteration += 1

            # 残り時間計算
            elapsed = loop.time() - start_time
            remaining_timeout = timeout - elapsed

            if remaining_timeout <= 0:
                logger.error("Total timeout exceeded after %s seconds", timeout)
                raise asyncio.TimeoutError(f"Request timed out after {timeout} seconds")

            # LLMリクエスト送信
            try:
                response = await asyncio.wait_for(
                    self.llm_client.chat(
                        messages=conversation_history,
                        tools=tools,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    ),
                    timeout=remaining_timeout,
                )
            except asyncio.TimeoutError:
                logger.error("LLM request timed out")
                raise

            # ツール呼び出しがなければ終了
            if not response.tool_calls:
                logger.info("Chat completed after %s iteration(s)", iteration)
                return ToolExecutionResult(
                    final_message=response.message,
                    response_id=response.id,
                    usage=response.usage,
                    iterations=iteration,
                )

            # assistant メッセージを履歴に追加
            conversation_history.append(response.message)
            logger.debug(
                "Iteration %s: LLM requested %s tool call(s)",
                iteration,
                len(response.tool_calls),
            )

            # 残り時間を再計算（ツール実行にもタイムアウトを適用）
            elapsed = loop.time() - start_time
            remaining_timeout = timeout - elapsed

            if remaining_timeout <= 0:
                logger.error("Total timeout exceeded before tool execution")
                raise asyncio.TimeoutError(f"Request timed out after {timeout} seconds")

            # ツールを並列実行（タイムアウト付き）
            try:
                tool_results = await asyncio.wait_for(
                    self._execute_tools_parallel(response.tool_calls),
                    timeout=remaining_timeout,
                )
            except asyncio.TimeoutError:
                logger.error("Tool execution timed out")
                raise

            # ツール結果を履歴に追加
            # 長さの不一致を検出するために strict=True を使用（Python 3.10+）
            for tool_call, result in zip(
                response.tool_calls, tool_results, strict=True
            ):
                tool_message = self._create_tool_result_message(tool_call, result)
                conversation_history.append(tool_message)

        # 最大イテレーション到達
        logger.error("Reached maximum iterations: %s", self.max_iterations)
        raise MaxIterationsExceeded(
            f"Reached maximum iterations ({self.max_iterations}) without final answer"
        )

    async def execute_loop_stream(
        self,
        conversation_history: list[Message],
        tools: list[Tool] | None,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> AsyncGenerator[StreamChunk, None]:
        """ツール実行ループをストリーミングで実行します。

        LLMがツール呼び出しを返す限り、ツールを実行して結果をLLMに返すループを実行します。
        最終的なテキスト応答はストリーミングで yield されます。
        ツール呼び出し自体は非ストリーミングで実行されます。

        Args:
            conversation_history: チャットメッセージ履歴
            tools: 利用可能なツールのスキーマ
            temperature: 生成の多様性
            max_tokens: 最大トークン数
            timeout: 全体のタイムアウト秒数

        Yields:
            StreamChunk: 各ストリーミングチャンク

        Raises:
            MaxIterationsExceeded: 最大イテレーション数に到達した場合
            asyncio.TimeoutError: タイムアウトした場合
        """
        iteration = 0
        loop = asyncio.get_running_loop()
        start_time = loop.time()

        while iteration < self.max_iterations:
            iteration += 1

            # 残り時間計算
            elapsed = loop.time() - start_time
            remaining_timeout = timeout - elapsed

            if remaining_timeout <= 0:
                logger.error("Total timeout exceeded after %s seconds", timeout)
                raise asyncio.TimeoutError(f"Request timed out after {timeout} seconds")

            # LLMストリーミングリクエスト
            try:
                # ツール呼び出しの完全な情報を収集するためのフラグ
                has_tool_calls = False
                final_tool_calls: list[ToolCall] = []
                last_done_chunk: StreamChunk | None = None

                # ストリーミングリクエストを実行（タイムアウト付き）
                async with asyncio.timeout(remaining_timeout):
                    async for chunk in self.llm_client.chat_stream(
                        messages=conversation_history,
                        tools=tools,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    ):
                        if chunk.type == "error":
                            # エラーが発生した場合はエラーチャンクをyieldして終了
                            logger.error("LLM streaming error: %s", chunk.error)
                            yield chunk
                            return
                        elif chunk.type == "delta":
                            # テキストデルタを yield
                            yield chunk
                        elif chunk.type == "tool_call" and chunk.tool_calls:
                            # ツール呼び出しを蓄積
                            has_tool_calls = True
                            final_tool_calls.extend(chunk.tool_calls)
                        elif chunk.type == "done":
                            # doneチャンクを保存（usage/finish_reason保持）
                            last_done_chunk = chunk

            except asyncio.TimeoutError:
                logger.error("LLM request timed out")
                # クライアントにエラーを通知
                yield StreamChunk(type="error", error="Request timed out")
                raise

            # ツール呼び出しなければ終了
            if not has_tool_calls:
                logger.info("Stream completed after %s iteration(s)", iteration)
                # LLMからのdoneチャンクを優先、なければ新規作成
                if last_done_chunk:
                    yield last_done_chunk
                else:
                    yield StreamChunk(type="done")
                return

            # assistant メッセージを履歴に追加
            # ストリーミングでは完全なメッセージが取得できないため、
            # ツール呼び出しだけを含むメッセージを作成
            assistant_message = Message(
                role="assistant",
                content=None,
                tool_calls=final_tool_calls,
            )
            conversation_history.append(assistant_message)
            logger.debug(
                "Iteration %s: LLM requested %s tool call(s)",
                iteration,
                len(final_tool_calls),
            )

            # 残り時間を再計算（ツール実行にもタイムアウトを適用）
            elapsed = loop.time() - start_time
            remaining_timeout = timeout - elapsed

            if remaining_timeout <= 0:
                logger.error("Total timeout exceeded before tool execution")
                raise asyncio.TimeoutError(f"Request timed out after {timeout} seconds")

            # ツールを並列実行（タイムアウト付き）
            try:
                tool_results = await asyncio.wait_for(
                    self._execute_tools_parallel(final_tool_calls),
                    timeout=remaining_timeout,
                )
            except asyncio.TimeoutError:
                logger.error("Tool execution timed out")
                raise

            # ツール結果を yield（オプション：デバッグ用）
            for tool_call, result in zip(final_tool_calls, tool_results, strict=True):
                yield StreamChunk(
                    type="tool_result",
                    tool_name=tool_call.name,
                    tool_result=result,
                )

            # ツール結果を履歴に追加
            # 長さの不一致を検出するために strict=True を使用（Python 3.10+）
            for tool_call, result in zip(final_tool_calls, tool_results, strict=True):
                tool_message = self._create_tool_result_message(tool_call, result)
                conversation_history.append(tool_message)

        # 最大イテレーション到達
        logger.error("Reached maximum iterations: %s", self.max_iterations)
        raise MaxIterationsExceeded(
            f"Reached maximum iterations ({self.max_iterations}) without final answer"
        )

    async def _execute_tools_parallel(
        self, tool_calls: list[ToolCall]
    ) -> list[dict[str, Any]]:
        """複数ツールを並列実行する。

        Args:
            tool_calls: ツール呼び出しリスト

        Returns:
            実行結果のリスト。成功時は {"success": True, "result": ...}、
            失敗時は {"success": False, "error": ..., "error_type": ...} を含む。
        """
        loop = asyncio.get_running_loop()

        async def execute_single_tool(tool_call: ToolCall) -> dict[str, Any]:
            """単一ツールを実行する。

            Args:
                tool_call: ツール呼び出し

            Returns:
                実行結果の辞書
            """
            try:
                # ToolRegistry.execute は同期関数なので run_in_executor を使用
                result = await loop.run_in_executor(
                    None,
                    lambda: self.tool_registry.execute(
                        tool_call.name, **tool_call.parameters
                    ),
                )
                return {"success": True, "result": result}
            except (KeyError, ValueError) as e:
                # 想定内のエラー: LLMに詳細を返す
                logger.error(
                    "Expected error in tool %s (%s): %s",
                    tool_call.name,
                    type(e).__name__,
                    str(e),
                )
                return {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            except Exception as e:
                # 予期しないエラー: ログに記録し、汎用メッセージを返す
                # （機密情報漏洩を防ぐ）
                logger.exception(
                    "Unexpected error in tool %s: %s", tool_call.name, type(e).__name__
                )
                return {
                    "success": False,
                    "error": (
                        "Internal tool execution error. Check server logs for details."
                    ),
                    "error_type": "InternalError",
                }

        # 並列実行
        results = await asyncio.gather(*[execute_single_tool(tc) for tc in tool_calls])
        return results

    def _create_tool_result_message(
        self, tool_call: ToolCall, result: dict[str, Any]
    ) -> Message:
        """ツール実行結果からメッセージを生成する。

        Args:
            tool_call: ツール呼び出し
            result: 実行結果（success, result/error を含む辞書）

        Returns:
            tool role のメッセージ
        """
        if result["success"]:
            # 成功時: result を JSON シリアライズ
            content = json.dumps(result["result"], ensure_ascii=False)
        else:
            # 失敗時: error と error_type を JSON シリアライズ
            content = json.dumps(
                {
                    "error": result["error"],
                    "error_type": result["error_type"],
                },
                ensure_ascii=False,
            )

        return Message(
            role="tool",
            content=content,
            tool_call_id=tool_call.id,
            name=tool_call.name,
        )
