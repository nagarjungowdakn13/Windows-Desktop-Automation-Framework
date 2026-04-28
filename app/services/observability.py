"""SQLite-backed structured log writer."""

from __future__ import annotations

from typing import Any

from app.db.database import session_scope
from app.db.models import LogEntry


class ObservabilityService:
    """Persists structured events that complement the text log file."""

    def emit(
        self,
        *,
        event: str,
        message: str,
        level: str = "INFO",
        task_id: str | None = None,
        execution_id: str | None = None,
        step_index: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Write one structured log row to SQLite."""
        with session_scope() as session:
            session.add(
                LogEntry(
                    task_id=task_id,
                    execution_id=execution_id,
                    step_index=step_index,
                    level=level.upper(),
                    event=event,
                    message=message,
                    payload=payload or {},
                )
            )


observability = ObservabilityService()
