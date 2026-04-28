"""Plugin-style registry for automation actions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from app.core.exceptions import UnknownStepTypeError


class ActionHandler(Protocol):
    """Protocol implemented by every concrete automation action."""

    type_name: str

    def execute(self, params: Mapping[str, object]) -> dict[str, object]:
        """Execute the action and return a small result payload."""


class ActionRegistry:
    """Runtime registry that decouples the executor from concrete actions."""

    def __init__(self) -> None:
        self._handlers: dict[str, ActionHandler] = {}

    def register(self, handler: ActionHandler, *aliases: str) -> ActionHandler:
        """Register ``handler`` under its type name and optional aliases."""
        names = {handler.type_name, *aliases}
        for name in names:
            if not name:
                continue
            self._handlers[name] = handler
        return handler

    def get(self, action_type: str) -> ActionHandler:
        """Return a registered action or raise a domain error."""
        try:
            return self._handlers[action_type]
        except KeyError as exc:
            raise UnknownStepTypeError(f"no handler registered for step type '{action_type}'") from exc

    def as_mapping(self) -> Mapping[str, ActionHandler]:
        """Read-only mapping view used by tests and the executor."""
        return self._handlers

    def names(self) -> list[str]:
        """Return registered action names for diagnostics and validation."""
        return sorted(self._handlers)


ACTION_REGISTRY = ActionRegistry()
