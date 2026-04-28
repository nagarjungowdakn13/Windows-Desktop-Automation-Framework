"""Unit tests for the StepExecutor (no real desktop required)."""

from __future__ import annotations

import time
from typing import Any, Dict, Mapping

import pytest

from app.automation.executor import StepExecutor
from app.automation.steps import StepHandler
from app.core.exceptions import StepExecutionError, UnknownStepTypeError


class _AlwaysOkHandler(StepHandler):
    type_name = "ok"

    def execute(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        return {"echoed": dict(params)}


class _FlakyHandler(StepHandler):
    """Fails the first ``fail_times`` calls, then succeeds."""

    type_name = "flaky"

    def __init__(self, fail_times: int) -> None:
        self.calls = 0
        self.fail_times = fail_times

    def execute(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise StepExecutionError(self.type_name, f"transient #{self.calls}")
        return {"calls": self.calls}


class _AlwaysFailHandler(StepHandler):
    type_name = "boom"

    def execute(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        raise StepExecutionError(self.type_name, "permanent")


class _SlowHandler(StepHandler):
    """Sleeps long enough to exceed any reasonable timeout."""

    type_name = "slow"

    def execute(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        time.sleep(float(params.get("sleep", 1.0)))
        return {"ok": True}


def _executor(*handlers: StepHandler) -> StepExecutor:
    return StepExecutor(handlers={h.type_name: h for h in handlers})


def test_success_first_try() -> None:
    result = _executor(_AlwaysOkHandler()).execute("ok", {"a": 1}, retries=0, retry_delay=0)
    assert result.success is True
    assert result.attempts == 1
    assert result.result == {"echoed": {"a": 1}}
    assert result.timed_out is False


def test_retry_then_success() -> None:
    flaky = _FlakyHandler(fail_times=2)
    result = _executor(flaky).execute("flaky", {}, retries=3, retry_delay=0)
    assert result.success is True
    assert result.attempts == 3
    assert flaky.calls == 3


def test_retry_exhausted_returns_failure_not_raise() -> None:
    result = _executor(_AlwaysFailHandler()).execute("boom", {}, retries=2, retry_delay=0)
    assert result.success is False
    assert result.attempts == 3
    assert "permanent" in (result.error or "")


def test_unknown_step_raises() -> None:
    with pytest.raises(UnknownStepTypeError):
        _executor(_AlwaysOkHandler()).execute("nope", {}, retries=0, retry_delay=0)


def test_timeout_marks_step_failed_and_timed_out() -> None:
    ex = _executor(_SlowHandler())
    result = ex.execute("slow", {"sleep": 1.0}, retries=0, retry_delay=0, timeout_seconds=0.05)
    assert result.success is False
    assert result.timed_out is True
    assert "timed out" in (result.error or "").lower()
    ex.shutdown()


def test_no_timeout_when_unspecified() -> None:
    ex = _executor(_SlowHandler())
    result = ex.execute("slow", {"sleep": 0.05}, retries=0, retry_delay=0)
    assert result.success is True
    assert result.timed_out is False
    ex.shutdown()
