"""Pydantic schemas for HTTP request and response payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class StepConfig(BaseModel):
    """Single step in a pipeline as supplied by the client."""

    type: str = Field(..., description="Step type, e.g. 'click', 'launch_app'.")
    params: Dict[str, Any] = Field(default_factory=dict)
    retries: Optional[int] = Field(
        default=None, ge=0, description="Override default retry count for this step."
    )
    retry_delay: Optional[float] = Field(
        default=None, ge=0, description="Seconds between retries."
    )
    timeout_seconds: Optional[float] = Field(
        default=None, gt=0, description="Per-attempt timeout. The step is aborted if exceeded."
    )
    on_failure: Literal["abort", "continue"] = Field(default="abort")


class TaskRequest(BaseModel):
    """Body of POST /run-task."""

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=500)
    tags: List[str] = Field(default_factory=list)
    steps: List[StepConfig] = Field(..., min_length=1)


class TaskSubmittedResponse(BaseModel):
    """Returned immediately after enqueueing."""

    task_id: str
    status: str
    message: str = "Task accepted and queued."


class StepLogResponse(BaseModel):
    """Public view of a StepLog row."""

    model_config = ConfigDict(from_attributes=True)

    step_index: int
    step_type: str
    params: Dict[str, Any]
    success: bool
    attempts: int
    error: Optional[str]
    screenshot_path: Optional[str]
    started_at: datetime
    finished_at: Optional[datetime]


class TaskStatusResponse(BaseModel):
    """Returned by GET /status/{task_id}."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: str
    error: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    steps: List[StepLogResponse] = Field(default_factory=list)


class TaskSummary(BaseModel):
    """Compact row for the list endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: str
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]


class StatsResponse(BaseModel):
    """Aggregate stats served to the dashboard."""

    total: int
    by_status: Dict[str, int]
    success_rate: float = Field(description="0..1, success / (success + failed). 0 if no terminal tasks.")
    avg_duration_seconds: float = Field(description="Mean duration of finished tasks.")
    queue_depth: int
    running_task_id: Optional[str]
    last_task_at: Optional[datetime]


class HealthResponse(BaseModel):
    """Returned by /health."""

    status: Literal["ok", "degraded"]
    version: str
    database: Literal["ok", "down"]
    worker: Literal["running", "stopped"]
    queue_depth: int


class CancelResponse(BaseModel):
    """Returned by /cancel/{task_id}."""

    task_id: str
    status: str
    cancelled: bool
    message: str
