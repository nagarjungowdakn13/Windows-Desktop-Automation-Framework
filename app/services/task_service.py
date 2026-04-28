"""Database-facing business logic for tasks.

The service is the only layer that mutates ORM rows on behalf of the API.
Routes call the service; the service uses ``session_scope``.
"""

from __future__ import annotations

import uuid
from typing import Dict, List, Optional

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import selectinload

from app.core.exceptions import TaskNotFoundError
from app.db.database import session_scope
from app.db.models import Task, TaskStatus, _utcnow
from app.schemas.task import (
    StatsResponse,
    TaskRequest,
    TaskStatusResponse,
    TaskSummary,
)


_TERMINAL = {TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED}


class TaskService:
    """Thin domain service over the SQLAlchemy session."""

    # --------------------------------------------------------------- create

    def create(self, request: TaskRequest) -> str:
        """Persist a new task in QUEUED state and return its id."""
        task_id = str(uuid.uuid4())
        with session_scope() as session:
            task = Task(
                id=task_id,
                name=request.name,
                status=TaskStatus.QUEUED,
                pipeline=request.model_dump(mode="json"),
            )
            session.add(task)
        return task_id

    # ------------------------------------------------------------- read one

    def get_status(self, task_id: str) -> TaskStatusResponse:
        with session_scope() as session:
            stmt = (
                select(Task)
                .options(selectinload(Task.step_logs))
                .where(Task.id == task_id)
            )
            task = session.execute(stmt).scalar_one_or_none()
            if task is None:
                raise TaskNotFoundError(task_id)
            return TaskStatusResponse.model_validate(
                {
                    "id": task.id,
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
                            "error": s.error,
                            "screenshot_path": s.screenshot_path,
                            "started_at": s.started_at,
                            "finished_at": s.finished_at,
                        }
                        for s in task.step_logs
                    ],
                }
            )

    # ------------------------------------------------------------- read list

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
                try:
                    stmt = stmt.where(Task.status == TaskStatus(status))
                except ValueError as exc:
                    raise ValueError(f"unknown status filter '{status}'") from exc
            if query:
                like = f"%{query.lower()}%"
                stmt = stmt.where(
                    or_(
                        func.lower(Task.name).like(like),
                        func.lower(Task.id).like(like),
                    )
                )
            stmt = stmt.order_by(desc(Task.created_at)).limit(limit).offset(offset)
            rows = session.execute(stmt).scalars().all()
            return [
                TaskSummary.model_validate(
                    {
                        "id": r.id,
                        "name": r.name,
                        "status": r.status.value,
                        "created_at": r.created_at,
                        "started_at": r.started_at,
                        "finished_at": r.finished_at,
                    }
                )
                for r in rows
            ]

    # ------------------------------------------------------------------ stats

    def stats(self, *, queue_depth: int, running_task_id: Optional[str]) -> StatsResponse:
        with session_scope() as session:
            total = session.execute(select(func.count(Task.id))).scalar_one()
            by_status: Dict[str, int] = dict(
                session.execute(
                    select(Task.status, func.count(Task.id)).group_by(Task.status)
                ).all()
            )
            counts = {s.value: int(by_status.get(s, 0)) for s in TaskStatus}
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

            last_task_at = session.execute(
                select(func.max(Task.created_at))
            ).scalar()

        return StatsResponse(
            total=int(total or 0),
            by_status=counts,
            success_rate=round(success_rate, 4),
            avg_duration_seconds=round(avg_duration, 3),
            queue_depth=queue_depth,
            running_task_id=running_task_id,
            last_task_at=last_task_at,
        )

    # ----------------------------------------------------------------- cancel

    def cancel(self, task_id: str) -> tuple[bool, TaskStatus, str]:
        """Cancel a queued task. Returns (cancelled, current_status, message)."""
        with session_scope() as session:
            task = session.get(Task, task_id)
            if task is None:
                raise TaskNotFoundError(task_id)
            if task.status == TaskStatus.QUEUED:
                task.status = TaskStatus.CANCELLED
                task.finished_at = _utcnow()
                task.error = "cancelled before execution"
                return True, TaskStatus.CANCELLED, "cancelled while queued"
            if task.status in _TERMINAL:
                return False, task.status, f"task already {task.status.value}"
            return False, task.status, "running tasks cannot be cancelled mid-flight"

    # ------------------------------------------------------------- existence

    def exists(self, task_id: str) -> bool:
        with session_scope() as session:
            return session.execute(
                select(func.count(Task.id)).where(Task.id == task_id)
            ).scalar_one() > 0
