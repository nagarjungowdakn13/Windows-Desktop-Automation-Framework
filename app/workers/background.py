"""Single-consumer asyncio background worker.

Why one consumer: ``pyautogui`` drives a single physical mouse and keyboard.
Running pipelines concurrently would interleave inputs and corrupt every
running task. The API still accepts unlimited submissions — they queue.

The worker also exposes inspectable state (`running_task_id`, `queue_depth`)
so the API can surface live progress on the dashboard.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from app.automation.runner import TaskRunner
from app.core.config import settings
from app.core.logger import get_logger
from app.db.database import session_scope
from app.db.models import Task, TaskStatus

logger = get_logger(__name__)

_STOP_SENTINEL = "__stop__"


class BackgroundWorker:
    """Drains a queue of task ids and runs each pipeline serially."""

    def __init__(self, runner: TaskRunner | None = None) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=settings.worker_queue_size)
        self._runner = runner or TaskRunner()
        self._task: Optional[asyncio.Task[None]] = None
        self._stopping = asyncio.Event()
        self._running_task_id: Optional[str] = None

    # -------------------------------------------------------------- lifecycle

    async def start(self) -> None:
        if self._task is not None:
            return
        logger.info("background worker starting")
        self._stopping.clear()
        self._task = asyncio.create_task(self._loop(), name="wda-worker")

    async def stop(self) -> None:
        if self._task is None:
            return
        logger.info("background worker stopping")
        self._stopping.set()
        await self._queue.put(_STOP_SENTINEL)
        await self._task
        self._task = None

    # ------------------------------------------------------------- inspection

    @property
    def running_task_id(self) -> Optional[str]:
        return self._running_task_id

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    # ---------------------------------------------------------------- enqueue

    async def submit(self, task_id: str) -> None:
        """Enqueue a task id. Raises ``asyncio.QueueFull`` if the queue is full."""
        await self._queue.put(task_id)
        logger.info("queued task %s (depth=%d)", task_id, self._queue.qsize())

    # ----------------------------------------------------------------- worker

    async def _loop(self) -> None:
        while not self._stopping.is_set():
            task_id = await self._queue.get()
            if task_id == _STOP_SENTINEL:
                break
            try:
                if self._was_cancelled(task_id):
                    logger.info("skipping cancelled task %s", task_id)
                    continue
                self._running_task_id = task_id
                await asyncio.to_thread(self._runner.run, task_id)
            except Exception:  # noqa: BLE001
                logger.exception("worker crashed while running task %s", task_id)
            finally:
                self._running_task_id = None
                self._queue.task_done()

    @staticmethod
    def _was_cancelled(task_id: str) -> bool:
        with session_scope() as session:
            row = session.get(Task, task_id)
            return row is not None and row.status == TaskStatus.CANCELLED
