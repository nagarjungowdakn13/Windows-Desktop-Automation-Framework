"""Custom exception hierarchy for the automation framework."""

from __future__ import annotations


class AutomationError(Exception):
    """Base class for every framework-raised error."""


# ---------------------------------------------------------------------------
# Step execution errors
# ---------------------------------------------------------------------------


class StepExecutionError(AutomationError):
    """Raised when a single pipeline step fails after exhausting retries.

    Subclasses signal *why* the step failed so the executor can pick a
    sensible retry policy:

    * :class:`TransientStepError`  — recoverable; retry with backoff.
    * :class:`PermanentStepError`  — non-recoverable; fail immediately.

    Step handlers SHOULD raise one of those two subclasses. A bare
    :class:`StepExecutionError` is treated as transient by default for
    backwards compatibility.
    """

    #: One of "transient" | "permanent" | "timeout".
    kind: str = "transient"

    def __init__(self, step_type: str, message: str, *, original: Exception | None = None) -> None:
        super().__init__(f"[{step_type}] {message}")
        self.step_type = step_type
        self.original = original


class TransientStepError(StepExecutionError):
    """Recoverable failure (network blip, app not focused yet, etc.)."""

    kind = "transient"


class PermanentStepError(StepExecutionError):
    """Non-recoverable failure (config bug, missing param, app missing)."""

    kind = "permanent"


# ---------------------------------------------------------------------------
# Domain-level
# ---------------------------------------------------------------------------


class UnknownStepTypeError(AutomationError):
    """Raised when a JSON pipeline references a step type that has no handler."""


class TaskNotFoundError(AutomationError):
    """Raised when a task_id has no row in the database."""


class InvalidTaskDefinitionError(AutomationError):
    """Raised when the submitted task config is structurally invalid."""


class InvalidTransitionError(AutomationError):
    """Raised when the state machine refuses a target transition."""


class IdempotencyConflictError(AutomationError):
    """Raised when an Idempotency-Key collides with a different task body."""
