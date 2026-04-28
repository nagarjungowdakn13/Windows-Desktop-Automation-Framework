"""Task pipeline orchestrator.

The runner walks the pipeline, asks the executor to run each step, persists
``StepLog`` rows, and updates the parent ``Task`` row. On failure, a desktop
screenshot is captured and its path is written into the failing step's row.
"""

from __future__ import annotations

from typing import Sequence

from app.automation.executor import StepExecutor, StepResult
from app.automation.screenshot import ScreenshotService
from app.core.logger import get_logger
from app.db.database import session_scope
from app.db.models import StepLog, Task, TaskStatus, _utcnow
from app.schemas.task import StepConfig

logger = get_logger(__name__)


class TaskRunner:
    """Drives a saved ``Task`` through its configured steps."""

    def __init__(
        self,
        executor: StepExecutor | None = None,
        screenshots: ScreenshotService | None = None,
    ) -> None:
        self._executor = executor or StepExecutor()
        self._screenshots = screenshots or ScreenshotService()

    # ------------------------------------------------------------------ public

    def run(self, task_id: str) -> TaskStatus:
        """Run the pipeline for ``task_id``. Returns the final task status."""
        steps = self._begin_task(task_id)
        final_status = TaskStatus.SUCCESS
        final_error: str | None = None

        for index, step in enumerate(steps):
            log_row_id = self._open_step_log(task_id=task_id, index=index, step=step)
            result = self._executor.execute(
                step_type=step.type,
                params=step.params,
                retries=step.retries,
                retry_delay=step.retry_delay,
                timeout_seconds=step.timeout_seconds,
            )
            screenshot_path = None
            if not result.success:
                screenshot_path = self._capture_failure(task_id=task_id, step_index=index)

            self._close_step_log(
                log_row_id=log_row_id,
                result=result,
                screenshot_path=screenshot_path,
            )

            if not result.success:
                logger.error(
                    "task %s step %d (%s) failed after %d attempts: %s",
                    task_id, index, step.type, result.attempts, result.error,
                )
                if step.on_failure == "abort":
                    final_status = TaskStatus.FAILED
                    final_error = f"step {index} ({step.type}): {result.error}"
                    break
                # on_failure == "continue" — keep going but mark task degraded.
                final_status = TaskStatus.FAILED
                final_error = final_error or f"step {index} ({step.type}): {result.error}"

        self._finish_task(task_id=task_id, status=final_status, error=final_error)
        return final_status

    # ---------------------------------------------------------------- internals

    def _begin_task(self, task_id: str) -> Sequence[StepConfig]:
        """Mark task running and return its parsed steps."""
        with session_scope() as session:
            task = session.get(Task, task_id)
            if task is None:
                raise LookupError(f"task '{task_id}' not found")
            task.status = TaskStatus.RUNNING
            task.started_at = _utcnow()
            pipeline = task.pipeline
        return [StepConfig.model_validate(s) for s in pipeline["steps"]]

    def _finish_task(self, *, task_id: str, status: TaskStatus, error: str | None) -> None:
        with session_scope() as session:
            task = session.get(Task, task_id)
            if task is None:
                return
            task.status = status
            task.error = error
            task.finished_at = _utcnow()

    def _open_step_log(self, *, task_id: str, index: int, step: StepConfig) -> int:
        with session_scope() as session:
            row = StepLog(
                task_id=task_id,
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
            row.error = result.error
            row.screenshot_path = screenshot_path or result.result.get("path")
            row.finished_at = _utcnow()

    def _capture_failure(self, *, task_id: str, step_index: int) -> str | None:
        try:
            path = self._screenshots.capture(label=f"fail_{task_id}_{step_index}")
            return str(path)
        except Exception:  # pragma: no cover — environment-specific
            logger.exception("could not capture failure screenshot")
            return None
