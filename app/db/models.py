"""ORM models for tasks, step attempts, transitions, and structured logs."""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, List, Optional


def _utcnow() -> datetime:
    """Tz-naive UTC, kept compatible with SQLite DateTime column."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class TaskStatus(str, enum.Enum):
    """Formal task lifecycle states.

    A task may only move through the transition graph enforced by
    :mod:`app.services.state_machine`.
    """

    PENDING = "pending"
    RUNNING = "running"
    RETRYING = "retrying"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FailureKind(str, enum.Enum):
    """Normalized failure classes used by retry policy and observability."""

    TRANSIENT = "transient"
    PERMANENT = "permanent"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class Task(Base):
    """A submitted automation pipeline."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    execution_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    task_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, native_enum=False, length=20),
        default=TaskStatus.PENDING,
        nullable=False,
        index=True,
    )
    pipeline: Mapped[dict] = mapped_column(JSON, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_step_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resume_from_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
    pending_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    retrying_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    step_logs: Mapped[List["TaskStep"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskStep.id",
    )
    transitions: Mapped[List["TaskStateTransition"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskStateTransition.id",
    )
    logs: Mapped[List["LogEntry"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="LogEntry.id",
    )


class TaskStep(Base):
    """Per-step audit row written by the runner."""

    __tablename__ = "task_steps"
    __table_args__ = (
        Index("ix_task_steps_task_step", "task_id", "step_index"),
        Index("ix_task_steps_execution_step", "execution_id", "step_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    execution_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(50), nullable=False)
    params: Mapped[dict] = mapped_column(JSON, nullable=False)
    success: Mapped[bool] = mapped_column(default=False, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    failure_kind: Mapped[Optional[FailureKind]] = mapped_column(
        Enum(FailureKind, native_enum=False, length=20), nullable=True
    )
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    screenshot_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    task: Mapped[Task] = relationship(back_populates="step_logs")


# Backwards-compatible Python name used throughout older code and tests.
StepLog = TaskStep


class TaskStateTransition(Base):
    """Immutable state-machine transition history."""

    __tablename__ = "task_state_transitions"
    __table_args__ = (Index("ix_task_state_transitions_task_at", "task_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    execution_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    from_status: Mapped[Optional[TaskStatus]] = mapped_column(
        Enum(TaskStatus, native_enum=False, length=20), nullable=True
    )
    to_status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, native_enum=False, length=20), nullable=False
    )
    reason: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    task: Mapped[Task] = relationship(back_populates="transitions")


class LogEntry(Base):
    """Structured JSON log event persisted for observability."""

    __tablename__ = "logs"
    __table_args__ = (Index("ix_logs_task_created", "task_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True, index=True
    )
    execution_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    step_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    event: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    task: Mapped[Optional[Task]] = relationship(back_populates="logs")
