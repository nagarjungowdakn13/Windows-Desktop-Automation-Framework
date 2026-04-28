"""Single-step executor with classified retries and per-attempt timeout."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from app.automation import steps as _builtin_steps  # noqa: F401 - registers built-in actions
from app.automation.registry import ACTION_REGISTRY, ActionHandler
from app.core.config import settings
from app.core.exceptions import PermanentStepError, StepExecutionError, UnknownStepTypeError
from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class StepResult:
    """Outcome of executing a single step."""

    success: bool
    attempts: int
    result: Dict[str, Any]
    error: Optional[str] = None
    timed_out: bool = False
    failure_kind: Optional[str] = None
    latency_ms: float = 0.0


class StepExecutor:
    """Executes one configured step with retry, exponential backoff, and timeout."""

    def __init__(self, handlers: Mapping[str, ActionHandler] | None = None) -> None:
        self._handlers: Mapping[str, ActionHandler] = handlers or ACTION_REGISTRY.as_mapping()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="wda-step")

    def execute(
        self,
        step_type: str,
        params: Mapping[str, Any],
        *,
        retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
        timeout_seconds: Optional[float] = None,
        backoff_multiplier: Optional[float] = None,
    ) -> StepResult:
        """Run one step and return a result object.

        Permanent failures stop immediately. Transient and timeout failures are
        retried with exponential backoff until attempts are exhausted.
        """
        handler = self._handlers.get(step_type)
        if handler is None:
            raise UnknownStepTypeError(f"no handler registered for step type '{step_type}'")

        max_retries = retries if retries is not None else settings.default_step_retries
        delay = retry_delay if retry_delay is not None else settings.default_retry_delay_sec
        multiplier = backoff_multiplier if backoff_multiplier is not None else 2.0
        attempts = 0
        last_error: Optional[Exception] = None
        timed_out = False
        failure_kind: Optional[str] = None
        started = time.perf_counter()

        while attempts <= max_retries:
            attempts += 1
            try:
                logger.info(
                    "executing step '%s' attempt %d/%d (timeout=%s)",
                    step_type,
                    attempts,
                    max_retries + 1,
                    timeout_seconds,
                )
                result = self._invoke(handler, params, timeout_seconds)
                return StepResult(
                    success=True,
                    attempts=attempts,
                    result=result,
                    latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
                )
            except FuturesTimeoutError as exc:
                timed_out = True
                last_error = StepExecutionError(
                    step_type, f"timed out after {timeout_seconds}s", original=exc
                )
                failure_kind = "timeout"
                logger.warning("step '%s' timed out (attempt %d)", step_type, attempts)
            except StepExecutionError as exc:
                last_error = exc
                failure_kind = exc.kind
                logger.warning("step '%s' failed (attempt %d): %s", step_type, attempts, exc)
            except Exception as exc:  # noqa: BLE001 - normalize unexpected handler errors.
                last_error = StepExecutionError(step_type, str(exc), original=exc)
                failure_kind = last_error.kind
                logger.warning(
                    "step '%s' raised %s (attempt %d): %s",
                    step_type,
                    type(exc).__name__,
                    attempts,
                    exc,
                )

            if isinstance(last_error, PermanentStepError):
                logger.info("step '%s' failed permanently; skipping retries", step_type)
                break
            if attempts <= max_retries:
                time.sleep(delay * (multiplier ** (attempts - 1)))

        assert last_error is not None
        return StepResult(
            success=False,
            attempts=attempts,
            result={},
            error=str(last_error),
            timed_out=timed_out,
            failure_kind=failure_kind or "unknown",
            latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
        )

    def _invoke(
        self,
        handler: ActionHandler,
        params: Mapping[str, Any],
        timeout_seconds: Optional[float],
    ) -> Dict[str, Any]:
        """Run the handler directly or through a timeout-aware future."""
        if timeout_seconds is None or timeout_seconds <= 0:
            return dict(handler.execute(params))
        future = self._pool.submit(handler.execute, params)
        return dict(future.result(timeout=timeout_seconds))

    def shutdown(self) -> None:
        """Stop the timeout worker thread."""
        self._pool.shutdown(wait=False, cancel_futures=True)
