"""Database-facing business logic for task lifecycle and audit data."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import selectinload

from app.core.exceptions import IdempotencyConflictError, TaskNotFoundError
from app.db.database import session_scope
from app.db.models import LogEntry, Task, TaskStatus, _utcnow
from app.schemas.task import (
    StatsResponse,
    TaskRequest,
    TaskStatusResponse,
    TaskSummary,
)
from app.services.state_machine import state_machine


_TERMINAL = {TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED}


@dataclass(frozen=True)
class CreatedTask:
    """Identifiers returned when a task is persisted."""

    task_id: str
    execution_id: str
    status: TaskStatus
    existing: bool = False


class TaskService:
    """Domain service over task persistence, idempotency, and status queries."""

    def create(self, request: TaskRequest, *, idempotency_key: str | None = None) -> str:
        """Persist a new task and return its id.

        Kept for compatibility with existing tests and CLI code. New API code
        should call :meth:`create_task` to also receive the execution id.
        """
        return self.create_task(request, idempotency_key=idempotency_key).task_id

    def create_task(
        self,
        request: TaskRequest,
        *,
        idempotency_key: str | None = None,
        resume_from_step: int = 0,
    ) -> CreatedTask:
        """Persist a PENDING task with a unique execution id.

        If ``idempotency_key`` is reused with the same payload, the existing
        non-terminal task is returned instead of creating a duplicate. Reusing
        a key with a different payload raises an idempotency conflict.
        """
        payload = request.model_dump(mode="json")
        task_hash = _hash_payload(payload)
        with session_scope() as session:
            if idempotency_key:
                existing = session.execute(
                    select(Task).where(Task.idempotency_key == idempotency_key)
                ).scalar_one_or_none()
                if existing is not None:
                    if existing.task_hash != task_hash:
                        raise IdempotencyConflictError("idempotency key was used with a different task")
                    return CreatedTask(
                        task_id=existing.id,
                        execution_id=existing.execution_id,
                        status=existing.status,
                        existing=True,
                    )

            now = _utcnow()
            task = Task(
                id=str(uuid.uuid4()),
                execution_id=str(uuid.uuid4()),
                idempotency_key=idempotency_key,
                task_hash=task_hash,
                name=request.name,
                status=TaskStatus.PENDING,
                pipeline=payload,
                retry_count=0,
                resume_from_step=resume_from_step,
                pending_at=now,
                created_at=now,
            )
            session.add(task)
            session.flush()
            session.add(
                LogEntry(
                    event="task.created",
                    message="task created",
                    task_id=task.id,
                    execution_id=task.execution_id,
                    level="INFO",
                    payload={"name": task.name, "steps": len(request.steps)},
                )
            )
            return CreatedTask(task_id=task.id, execution_id=task.execution_id, status=task.status)

    def rerun(self, task_id: str, *, resume_from_failed_step: bool = False) -> CreatedTask:
        """Create a new execution from an existing task's pipeline."""
        with session_scope() as session:
            original = (
                session.execute(
                    select(Task).options(selectinload(Task.step_logs)).where(Task.id == task_id)
                ).scalar_one_or_none()
            )
            if original is None:
                raise TaskNotFoundError(task_id)
            resume_from_step = 0
            if resume_from_failed_step:
                failed_steps = [s.step_index for s in original.step_logs if not s.success]
                resume_from_step = min(failed_steps) if failed_steps else 0
            request = TaskRequest.model_validate(original.pipeline)
        return self.create_task(request, resume_from_step=resume_from_step)

    def get_status(self, task_id: str) -> TaskStatusResponse:
        """Return current task status, steps, and transition history."""
        with session_scope() as session:
            stmt = (
                select(Task)
                .options(selectinload(Task.step_logs), selectinload(Task.transitions))
                .where(Task.id == task_id)
            )
            task = session.execute(stmt).scalar_one_or_none()
            if task is None:
                raise TaskNotFoundError(task_id)
            return TaskStatusResponse.model_validate(
                {
                    "id": task.id,
                    "execution_id": task.execution_id,
                    "name": task.name,
                    "status": task.status.value,
                    "error": task.error,
                    "created_at": task.created_at,
                    "started_at": task.started_at,
                    "finished_at": task.finished_at,
                    "steps": [
                        {
                            "step_index": s.step_index,
                            "step_type": s.step_type,
                            "params": s.params,
                            "success": s.success,
                            "attempts": s.attempts,
                            "failure_kind": s.failure_kind.value if s.failure_kind else None,
                            "latency_ms": s.latency_ms,
                            "error": s.error,
                            "screenshot_path": s.screenshot_path,
                            "started_at": s.started_at,
                            "finished_at": s.finished_at,
                        }
                        for s in task.step_logs
                    ],
                    "transitions": [
                        {
                            "from_status": t.from_status.value if t.from_status else None,
                            "to_status": t.to_status.value,
                            "reason": t.reason,
                            "created_at": t.created_at,
                        }
                        for t in task.transitions
                    ],
                }
            )

    def list_tasks(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        query: Optional[str] = None,
    ) -> List[TaskSummary]:
        """Filterable, paginated task listing."""
        with session_scope() as session:
            stmt = select(Task)
            if status:
                normalized = "pending" if status == "queued" else status
                try:
                    stmt = stmt.where(Task.status == TaskStatus(normalized))
                except ValueError as exc:
                    raise ValueError(f"unknown status filter '{status}'") from exc
            if query:
                like = f"%{query.lower()}%"
                stmt = stmt.where(
                    or_(
                        func.lower(Task.name).like(like),
                        func.lower(Task.id).like(like),
                        func.lower(Task.execution_id).like(like),
                    )
                )
            stmt = stmt.order_by(desc(Task.created_at)).limit(limit).offset(offset)
            rows = session.execute(stmt).scalars().all()
            return [
                TaskSummary.model_validate(
                    {
                        "id": r.id,
                        "execution_id": r.execution_id,
                        "name": r.name,
                        "status": r.status.value,
                        "created_at": r.created_at,
                        "started_at": r.started_at,
                        "finished_at": r.finished_at,
                    }
                )
                for r in rows
            ]

    def stats(self, *, queue_depth: int, running_task_id: Optional[str]) -> StatsResponse:
        """Return aggregate task and queue metrics."""
        with session_scope() as session:
            total = session.execute(select(func.count(Task.id))).scalar_one()
            by_status: Dict[TaskStatus, int] = dict(
                session.execute(select(Task.status, func.count(Task.id)).group_by(Task.status)).all()
            )
            counts = {s.value: int(by_status.get(s, 0)) for s in TaskStatus}
            counts["queued"] = counts.get(TaskStatus.PENDING.value, 0)
            success = counts.get(TaskStatus.SUCCESS.value, 0)
            failed = counts.get(TaskStatus.FAILED.value, 0)
            denom = success + failed
            success_rate = (success / denom) if denom else 0.0

            avg_seconds = session.execute(
                select(
                    func.avg(
                        (func.julianday(Task.finished_at) - func.julianday(Task.started_at)) * 86400.0
                    )
                ).where(Task.finished_at.is_not(None), Task.started_at.is_not(None))
            ).scalar()
            avg_duration = float(avg_seconds) if avg_seconds is not None else 0.0
            last_task_at = session.execute(select(func.max(Task.created_at))).scalar()

        return StatsResponse(
            total=int(total or 0),
            by_status=counts,
            success_rate=round(success_rate, 4),
            avg_duration_seconds=round(avg_duration, 3),
            queue_depth=queue_depth,
            running_task_id=running_task_id,
            last_task_at=last_task_at,
        )

    def cancel(self, task_id: str) -> tuple[bool, TaskStatus, str]:
        """Cancel a pending task. Running tasks cannot be interrupted mid-step."""
        with session_scope() as session:
            task = session.get(Task, task_id)
            if task is None:
                raise TaskNotFoundError(task_id)
            if task.status == TaskStatus.PENDING:
                state_machine.transition(session, task, TaskStatus.CANCELLED, reason="cancelled before execution")
                task.error = "cancelled before execution"
                return True, TaskStatus.CANCELLED, "cancelled while pending"
            if task.status in _TERMINAL:
                return False, task.status, f"task already {task.status.value}"
            return False, task.status, "running tasks cannot be cancelled mid-flight"

    def exists(self, task_id: str) -> bool:
        """Return true when a task id exists."""
        with session_scope() as session:
            return session.execute(select(func.count(Task.id)).where(Task.id == task_id)).scalar_one() > 0


def _hash_payload(payload: dict) -> str:
    """Stable hash used for idempotency conflict detection."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
