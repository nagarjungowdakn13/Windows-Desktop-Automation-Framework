"""Task lifecycle transition enforcement."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import InvalidTransitionError
from app.db.models import Task, TaskStateTransition, TaskStatus, _utcnow


VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.RUNNING: {TaskStatus.RETRYING, TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.RETRYING: {TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.SUCCESS: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELLED: set(),
}


class TaskStateMachine:
    """Applies valid task transitions and records every state change."""

    def transition(
        self,
        session: Session,
        task: Task,
        target: TaskStatus,
        *,
        reason: str | None = None,
    ) -> None:
        """Move ``task`` to ``target`` or raise if the transition is invalid."""
        source = task.status
        if source == target:
            return
        if target not in VALID_TRANSITIONS[source]:
            raise InvalidTransitionError(f"invalid task transition {source.value} -> {target.value}")

        now = _utcnow()
        task.status = target
        if target == TaskStatus.PENDING:
            task.pending_at = now
        elif target == TaskStatus.RUNNING:
            task.started_at = task.started_at or now
        elif target == TaskStatus.RETRYING:
            task.retrying_at = now
            task.retry_count += 1
        elif target in {TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED}:
            task.finished_at = now

        session.add(
            TaskStateTransition(
                task_id=task.id,
                execution_id=task.execution_id,
                from_status=source,
                to_status=target,
                reason=reason,
                created_at=now,
            )
        )


state_machine = TaskStateMachine()
