"""Task pipeline orchestrator with state-machine and audit integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.automation.executor import StepExecutor, StepResult
from app.automation.screenshot import ScreenshotService
from app.core.logger import get_logger
from app.db.database import session_scope
from app.db.models import FailureKind, LogEntry, StepLog, Task, TaskStatus, _utcnow
from app.schemas.task import StepConfig
from app.services.state_machine import state_machine

logger = get_logger(__name__)


@dataclass(frozen=True)
class RunContext:
    """Immutable execution context loaded at task start."""

    task_id: str
    execution_id: str
    resume_from_step: int
    steps: Sequence[StepConfig]


class TaskRunner:
    """Drives a saved ``Task`` through its configured steps."""

    def __init__(
        self,
        executor: StepExecutor | None = None,
        screenshots: ScreenshotService | None = None,
    ) -> None:
        self._executor = executor or StepExecutor()
        self._screenshots = screenshots or ScreenshotService()

    def run(self, task_id: str) -> TaskStatus:
        """Run the pipeline for ``task_id`` and return the final task status."""
        context = self._begin_task(task_id)
        final_status = TaskStatus.SUCCESS
        final_error: str | None = None

        for index, step in enumerate(context.steps):
            if index < context.resume_from_step:
                continue

            self._mark_current_step(context.task_id, index)
            log_row_id = self._open_step_log(context=context, index=index, step=step)
            result = self._executor.execute(
                step_type=step.type,
                params=step.params,
                retries=step.retries,
                retry_delay=step.retry_delay,
                timeout_seconds=step.timeout_seconds,
                backoff_multiplier=step.backoff_multiplier if step.retry_strategy == "exponential" else 1.0,
            )
            if result.attempts > 1:
                self._record_retry_cycle(context.task_id, f"step {index} retried {result.attempts} times")

            screenshot_path = None
            if not result.success:
                screenshot_path = self._capture_failure(task_id=context.task_id, step_index=index)

            self._close_step_log(
                log_row_id=log_row_id,
                result=result,
                screenshot_path=screenshot_path,
            )
            self._emit_step_log(context=context, index=index, step=step, result=result)

            if not result.success:
                logger.error(
                    "task %s step %d (%s) failed after %d attempts: %s",
                    context.task_id,
                    index,
                    step.type,
                    result.attempts,
                    result.error,
                )
                if step.on_failure == "abort":
                    final_status = TaskStatus.FAILED
                    final_error = f"step {index} ({step.type}): {result.error}"
                    break
                final_status = TaskStatus.FAILED
                final_error = final_error or f"step {index} ({step.type}): {result.error}"

        self._finish_task(task_id=context.task_id, status=final_status, error=final_error)
        return final_status

    def _begin_task(self, task_id: str) -> RunContext:
        """Transition a PENDING task to RUNNING and return parsed steps."""
        with session_scope() as session:
            task = session.get(Task, task_id)
            if task is None:
                raise LookupError(f"task '{task_id}' not found")
            if task.status != TaskStatus.PENDING:
                return RunContext(task.id, task.execution_id, task.resume_from_step, [])
            state_machine.transition(session, task, TaskStatus.RUNNING, reason="worker picked task")
            pipeline = task.pipeline
            execution_id = task.execution_id
            resume_from_step = task.resume_from_step
            session.add(
                LogEntry(
                    task_id=task.id,
                    execution_id=execution_id,
                    level="INFO",
                    event="task.started",
                    message="task execution started",
                    payload={"resume_from_step": resume_from_step},
                )
            )
        return RunContext(
            task_id=task_id,
            execution_id=execution_id,
            resume_from_step=resume_from_step,
            steps=[StepConfig.model_validate(s) for s in pipeline["steps"]],
        )

    def _finish_task(self, *, task_id: str, status: TaskStatus, error: str | None) -> None:
        with session_scope() as session:
            task = session.get(Task, task_id)
            if task is None or task.status in {TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED}:
                return
            state_machine.transition(session, task, status, reason=error or "task completed")
            task.error = error
            session.add(
                LogEntry(
                    task_id=task.id,
                    execution_id=task.execution_id,
                    level="INFO" if status == TaskStatus.SUCCESS else "ERROR",
                    event="task.finished",
                    message=f"task finished as {status.value}",
                    payload={"error": error},
                )
            )

    def _mark_current_step(self, task_id: str, step_index: int) -> None:
        with session_scope() as session:
            task = session.get(Task, task_id)
            if task is not None:
                task.current_step_index = step_index

    def _record_retry_cycle(self, task_id: str, reason: str) -> None:
        with session_scope() as session:
            task = session.get(Task, task_id)
            if task is None or task.status != TaskStatus.RUNNING:
                return
            state_machine.transition(session, task, TaskStatus.RETRYING, reason=reason)
            state_machine.transition(session, task, TaskStatus.RUNNING, reason="retry cycle finished")

    def _open_step_log(self, *, context: RunContext, index: int, step: StepConfig) -> int:
        with session_scope() as session:
            row = StepLog(
                task_id=context.task_id,
                execution_id=context.execution_id,
                step_index=index,
                step_type=step.type,
                params=step.params,
                started_at=_utcnow(),
            )
            session.add(row)
            session.flush()
            return row.id

    def _close_step_log(
        self,
        *,
        log_row_id: int,
        result: StepResult,
        screenshot_path: str | None,
    ) -> None:
        with session_scope() as session:
            row = session.get(StepLog, log_row_id)
            if row is None:
                return
            row.success = result.success
            row.attempts = result.attempts
            row.failure_kind = FailureKind(result.failure_kind) if result.failure_kind else None
            row.error = result.error
            row.screenshot_path = screenshot_path or result.result.get("path")
            row.latency_ms = result.latency_ms
            row.finished_at = _utcnow()

    def _emit_step_log(
        self,
        *,
        context: RunContext,
        index: int,
        step: StepConfig,
        result: StepResult,
    ) -> None:
        with session_scope() as session:
            session.add(
                LogEntry(
                    task_id=context.task_id,
                    execution_id=context.execution_id,
                    step_index=index,
                    level="INFO" if result.success else "ERROR",
                    event="step.finished",
                    message=f"step {step.type} {'succeeded' if result.success else 'failed'}",
                    payload={
                        "step_type": step.type,
                        "attempts": result.attempts,
                        "latency_ms": result.latency_ms,
                        "failure_kind": result.failure_kind,
                        "error": result.error,
                    },
                )
            )

    def _capture_failure(self, *, task_id: str, step_index: int) -> str | None:
        try:
            path = self._screenshots.capture(label=f"fail_{task_id}_{step_index}")
            return str(path)
        except Exception:  # pragma: no cover - environment-specific
            logger.exception("could not capture failure screenshot")
            return None
