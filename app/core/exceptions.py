"""Custom exception hierarchy for the automation framework."""

from __future__ import annotations


class AutomationError(Exception):
    """Base class for every framework-raised error."""


class StepExecutionError(AutomationError):
    """Raised when a single pipeline step fails after exhausting retries."""

    def __init__(self, step_type: str, message: str, *, original: Exception | None = None) -> None:
        super().__init__(f"[{step_type}] {message}")
        self.step_type = step_type
        self.original = original


class UnknownStepTypeError(AutomationError):
    """Raised when a JSON pipeline references a step type that has no handler."""


class TaskNotFoundError(AutomationError):
    """Raised when a task_id has no row in the database."""


class InvalidTaskDefinitionError(AutomationError):
    """Raised when the submitted task config is structurally invalid."""
