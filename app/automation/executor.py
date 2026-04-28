"""Single-step executor with retry policy and per-attempt timeout.

Separated from :class:`TaskRunner` so it can be unit-tested without a database
or a real desktop session — pass in a fake handler registry and you're done.

Timeouts are enforced by running each attempt on a worker thread and waiting
on a ``concurrent.futures.Future``. If the deadline passes, the executor
*reports* the timeout, but the worker thread cannot be killed forcibly in
Python — it will continue until the underlying call returns. Step handlers
that interact with pyautogui are short-running by design, so this is fine in
practice.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from app.core.config import settings
from app.core.exceptions import StepExecutionError, UnknownStepTypeError
from app.core.logger import get_logger
from app.automation.steps import STEP_HANDLERS, StepHandler

logger = get_logger(__name__)


@dataclass(slots=True)
class StepResult:
    """Outcome of executing a single step."""

    success: bool
    attempts: int
    result: Dict[str, Any]
    error: Optional[str] = None
    timed_out: bool = False


class StepExecutor:
    """Executes a single configured step with retry, backoff, and timeout."""

    def __init__(self, handlers: Mapping[str, StepHandler] | None = None) -> None:
        self._handlers: Mapping[str, StepHandler] = handlers or STEP_HANDLERS
        # One reusable thread per executor instance is enough — the runner
        # serialises calls anyway.
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="wda-step")

    def execute(
        self,
        step_type: str,
        params: Mapping[str, Any],
        *,
        retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
        timeout_seconds: Optional[float] = None,
    ) -> StepResult:
        """Run one step. Returns a :class:`StepResult`; never raises for step errors.

        Unknown step types are still raised (config bug, not a runtime failure).
        """
        handler = self._handlers.get(step_type)
        if handler is None:
            raise UnknownStepTypeError(f"no handler registered for step type '{step_type}'")

        max_retries = retries if retries is not None else settings.default_step_retries
        delay = retry_delay if retry_delay is not None else settings.default_retry_delay_sec
        attempts = 0
        last_error: Optional[Exception] = None
        timed_out = False

        while attempts <= max_retries:
            attempts += 1
            try:
                logger.info(
                    "executing step '%s' attempt %d/%d (timeout=%s)",
                    step_type, attempts, max_retries + 1, timeout_seconds,
                )
                result = self._invoke(handler, params, timeout_seconds)
                return StepResult(success=True, attempts=attempts, result=result)
            except FuturesTimeoutError as exc:
                timed_out = True
                last_error = StepExecutionError(
                    step_type, f"timed out after {timeout_seconds}s", original=exc
                )
                logger.warning("step '%s' timed out (attempt %d)", step_type, attempts)
            except StepExecutionError as exc:
                last_error = exc
                logger.warning("step '%s' failed (attempt %d): %s", step_type, attempts, exc)
            except Exception as exc:  # noqa: BLE001 — coerce to StepExecutionError below
                last_error = StepExecutionError(step_type, str(exc), original=exc)
                logger.warning(
                    "step '%s' raised %s (attempt %d): %s",
                    step_type, type(exc).__name__, attempts, exc,
                )
            if attempts <= max_retries:
                time.sleep(delay)

        assert last_error is not None
        return StepResult(
            success=False,
            attempts=attempts,
            result={},
            error=str(last_error),
            timed_out=timed_out,
        )

    # ----------------------------------------------------------------- helpers

    def _invoke(
        self,
        handler: StepHandler,
        params: Mapping[str, Any],
        timeout_seconds: Optional[float],
    ) -> Dict[str, Any]:
        if timeout_seconds is None or timeout_seconds <= 0:
            return handler.execute(params)
        future = self._pool.submit(handler.execute, params)
        return future.result(timeout=timeout_seconds)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
