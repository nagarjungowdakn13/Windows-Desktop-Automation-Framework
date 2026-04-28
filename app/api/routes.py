"""HTTP routes."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import text

from app import __version__
from app.core.config import settings
from app.core.exceptions import IdempotencyConflictError, TaskNotFoundError
from app.core.logger import get_logger
from app.db.database import engine
from app.schemas.task import (
    CancelResponse,
    HealthResponse,
    StatsResponse,
    TaskRequest,
    TaskStatusResponse,
    TaskSubmittedResponse,
    TaskSummary,
)
from app.services.task_service import TaskService
from app.ui.dashboard import DASHBOARD_HTML

logger = get_logger(__name__)
router = APIRouter()
_service = TaskService()


# ---------------------------------------------------------------------------
# Task lifecycle
# ---------------------------------------------------------------------------


@router.post("/run-task", response_model=TaskSubmittedResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_task(payload: TaskRequest, request: Request) -> TaskSubmittedResponse:
    """Persist the task and enqueue it for execution."""
    idempotency_key = request.headers.get("Idempotency-Key")
    try:
        created = _service.create_task(payload, idempotency_key=idempotency_key)
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    worker = request.app.state.worker
    try:
        if not created.existing:
            await worker.submit(created.task_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("failed to enqueue task %s", created.task_id)
        raise HTTPException(status_code=503, detail=f"worker unavailable: {exc}") from exc
    return TaskSubmittedResponse(task_id=created.task_id, execution_id=created.execution_id, status=created.status.value)


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_status(task_id: str) -> TaskStatusResponse:
    try:
        return _service.get_status(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"task '{task_id}' not found") from exc


@router.get("/tasks", response_model=List[TaskSummary])
async def list_tasks(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by status: pending | running | retrying | success | failed | cancelled.",
    ),
    q: Optional[str] = Query(None, description="Case-insensitive substring match on name or id."),
) -> List[TaskSummary]:
    try:
        return _service.list_tasks(limit=limit, offset=offset, status=status_filter, query=q)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/logs/{task_id}", response_model=TaskStatusResponse)
async def get_logs(task_id: str) -> TaskStatusResponse:
    """Alias of /status/{task_id} that emphasises the step-level audit trail."""
    try:
        return _service.get_status(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"task '{task_id}' not found") from exc


@router.post("/rerun/{task_id}", response_model=TaskSubmittedResponse, status_code=status.HTTP_202_ACCEPTED)
async def rerun(
    task_id: str,
    request: Request,
    resume_from_failed_step: bool = Query(False),
) -> TaskSubmittedResponse:
    """Create a new execution from an existing task, optionally resuming at its first failed step."""
    try:
        created = _service.rerun(task_id, resume_from_failed_step=resume_from_failed_step)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"task '{task_id}' not found") from exc
    await request.app.state.worker.submit(created.task_id)
    return TaskSubmittedResponse(
        task_id=created.task_id,
        execution_id=created.execution_id,
        status=created.status.value,
        message="Task re-run accepted and queued.",
    )


@router.post("/cancel/{task_id}", response_model=CancelResponse)
async def cancel(task_id: str) -> CancelResponse:
    """Cancel a pending task. Running tasks cannot be interrupted mid-step."""
    try:
        cancelled, current_status, message = _service.cancel(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"task '{task_id}' not found") from exc
    return CancelResponse(
        task_id=task_id,
        status=current_status.value,
        cancelled=cancelled,
        message=message,
    )


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=StatsResponse)
async def stats(request: Request) -> StatsResponse:
    worker = request.app.state.worker
    return _service.stats(
        queue_depth=worker.queue_depth,
        running_task_id=worker.running_task_id,
    )


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    worker = request.app.state.worker
    db_state: str = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_state = "down"
    worker_state = "running" if worker.is_running else "stopped"
    overall = "ok" if db_state == "ok" and worker_state == "running" else "degraded"
    return HealthResponse(
        status=overall,
        version=__version__,
        database=db_state,
        worker=worker_state,
        queue_depth=worker.queue_depth,
    )


# ---------------------------------------------------------------------------
# Dashboard + assets
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    return HTMLResponse(DASHBOARD_HTML)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    return HTMLResponse(DASHBOARD_HTML)


@router.get("/screenshots/{filename}")
async def get_screenshot(filename: str) -> FileResponse:
    screenshot_dir = settings.screenshot_dir.resolve()
    path = (screenshot_dir / Path(filename).name).resolve()
    if screenshot_dir not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="screenshot not found")
    return FileResponse(path)
