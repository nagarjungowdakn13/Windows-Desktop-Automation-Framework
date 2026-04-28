"""SQLAlchemy engine, session factory, and table bootstrap."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


# ``check_same_thread=False`` is safe because we serialise writes through the
# single-consumer worker; the FastAPI side only does short reads.
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create all tables. Called once at app startup."""
    # Import models so they register with Base.metadata.
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _upgrade_sqlite_schema()


def _upgrade_sqlite_schema() -> None:
    """Apply additive SQLite upgrades for existing local databases.

    This project intentionally avoids a migration framework to keep the desktop
    install small. The upgrades here are additive only: new installs are handled
    by ``create_all`` and older installs get missing columns/indexes.
    """
    if not engine.url.get_backend_name().startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "tasks" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("tasks")}
    task_columns = {
        "execution_id": "VARCHAR(36)",
        "idempotency_key": "VARCHAR(200)",
        "task_hash": "VARCHAR(64)",
        "retry_count": "INTEGER DEFAULT 0 NOT NULL",
        "current_step_index": "INTEGER DEFAULT 0 NOT NULL",
        "resume_from_step": "INTEGER DEFAULT 0 NOT NULL",
        "pending_at": "DATETIME",
        "retrying_at": "DATETIME",
    }
    with engine.begin() as conn:
        for name, ddl in task_columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE tasks ADD COLUMN {name} {ddl}"))
        conn.execute(text("UPDATE tasks SET execution_id = id WHERE execution_id IS NULL"))
        conn.execute(text("UPDATE tasks SET task_hash = '' WHERE task_hash IS NULL"))
        conn.execute(text("UPDATE tasks SET retry_count = 0 WHERE retry_count IS NULL"))
        conn.execute(text("UPDATE tasks SET current_step_index = 0 WHERE current_step_index IS NULL"))
        conn.execute(text("UPDATE tasks SET resume_from_step = 0 WHERE resume_from_step IS NULL"))
        conn.execute(text("UPDATE tasks SET pending_at = created_at WHERE pending_at IS NULL"))
        conn.execute(text("UPDATE tasks SET status = 'PENDING' WHERE status IN ('QUEUED', 'queued', 'pending')"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tasks_status ON tasks(status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tasks_execution_id ON tasks(execution_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tasks_idempotency_key ON tasks(idempotency_key)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tasks_task_hash ON tasks(task_hash)"))

        if "step_logs" in inspector.get_table_names() and "task_steps" in inspector.get_table_names():
            conn.execute(
                text(
                    """
                    INSERT INTO task_steps (
                        task_id, execution_id, step_index, step_type, params, success,
                        attempts, error, screenshot_path, started_at, finished_at
                    )
                    SELECT
                        s.task_id, COALESCE(t.execution_id, s.task_id), s.step_index,
                        s.step_type, s.params, s.success, s.attempts, s.error,
                        s.screenshot_path, s.started_at, s.finished_at
                    FROM step_logs s
                    LEFT JOIN tasks t ON t.id = s.task_id
                    WHERE NOT EXISTS (
                        SELECT 1 FROM task_steps ts
                        WHERE ts.task_id = s.task_id AND ts.step_index = s.step_index
                    )
                    """
                )
            )


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
