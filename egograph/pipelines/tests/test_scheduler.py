from datetime import UTC, datetime

from pipelines.domain.schedule import TriggerSpec, TriggerSpecType
from pipelines.domain.workflow import (
    StepDefinition,
    StepExecutorType,
    WorkflowDefinition,
)
from pipelines.infrastructure.db.connection import connect
from pipelines.infrastructure.db.repositories import WorkflowStateRepository
from pipelines.infrastructure.db.schema import initialize_schema
from pipelines.infrastructure.scheduling.apscheduler_app import ScheduleTriggerApp


def test_enqueue_schedule_run_ignores_disabled_workflow(tmp_path):
    """別プロセスで disable された workflow は schedule 発火時に no-op にする。"""
    # Arrange
    conn = connect(tmp_path / "state.sqlite3")
    initialize_schema(conn)
    repository = WorkflowStateRepository(conn)
    workflows = {
        "probe_workflow": WorkflowDefinition(
            workflow_id="probe_workflow",
            name="Probe workflow",
            description="Probe workflow",
            steps=(
                StepDefinition(
                    step_id="probe_step",
                    step_name="Probe step",
                    executor_type=StepExecutorType.INPROCESS,
                    callable_ref="pipelines.tests.support.dummy_steps:succeed",
                ),
            ),
            triggers=(TriggerSpec(TriggerSpecType.INTERVAL, "1s"),),
        )
    }
    scheduler = ScheduleTriggerApp(
        repository=repository,
        workflows=workflows,
        timezone="UTC",
    )
    scheduler.sync_jobs()
    repository.set_workflow_enabled("probe_workflow", False)

    # Act
    scheduler._enqueue_schedule_run("probe_workflow:0", "probe_workflow")

    # Assert
    workflow = repository.get_workflow("probe_workflow")
    assert repository.list_runs(workflow_id="probe_workflow") == []
    assert workflow["enabled"] is False
    assert workflow["schedules"][0]["next_run_at"] is None
    assert datetime.fromisoformat(
        workflow["schedules"][0]["last_scheduled_at"]
    ).tzinfo == UTC
