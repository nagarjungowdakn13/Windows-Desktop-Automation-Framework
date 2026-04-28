"""Concrete step handlers.

Each handler implements the :class:`StepHandler` ABC and is registered in
``STEP_HANDLERS``. Adding a new step type means writing a new subclass and
adding one line to the registry.
"""

from __future__ import annotations

import shlex
import subprocess
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Mapping

import pyautogui

from app.core.config import settings
from app.automation.registry import ACTION_REGISTRY
from app.core.exceptions import PermanentStepError, StepExecutionError, TransientStepError, UnknownStepTypeError
from app.core.logger import get_logger

logger = get_logger(__name__)

# Apply pyautogui-wide knobs once at import time.
pyautogui.FAILSAFE = settings.pyautogui_failsafe
pyautogui.PAUSE = settings.pyautogui_pause_sec


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class StepHandler(ABC):
    """Base class for all pipeline step handlers."""

    #: Human-readable identifier used in JSON ``type`` field.
    type_name: str = ""

    @abstractmethod
    def execute(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        """Run the step. Must raise on failure. Returns a small result dict."""

    @staticmethod
    def _required(params: Mapping[str, Any], key: str) -> Any:
        if key not in params:
            raise PermanentStepError(
                step_type=params.get("__type__", "?"),
                message=f"missing required parameter '{key}'",
            )
        return params[key]


# ---------------------------------------------------------------------------
# Process control
# ---------------------------------------------------------------------------


class LaunchAppHandler(StepHandler):
    """Start a process via ``subprocess.Popen``.

    Params:
        path: executable name or absolute path (e.g. ``notepad.exe``).
        args: optional list of arguments OR a single shell-style string.
        wait_seconds: optional sleep after launch to let the window appear.
    """

    type_name = "launch_app"

    def execute(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        path = self._required(params, "path")
        raw_args = params.get("args", [])
        if isinstance(raw_args, str):
            raw_args = shlex.split(raw_args)
        cmd = [path, *raw_args]
        logger.info("launching: %s", cmd)
        try:
            proc = subprocess.Popen(cmd, shell=False)
        except (FileNotFoundError, OSError) as exc:
            raise PermanentStepError(self.type_name, f"failed to launch {path}: {exc}", original=exc)

        wait = float(params.get("wait_seconds", 1.0))
        if wait > 0:
            time.sleep(wait)
        return {"pid": proc.pid}


class CloseAppHandler(StepHandler):
    """Close a process by image name using ``taskkill``.

    Params:
        image_name: e.g. ``notepad.exe``.
        force: bool, sends /F when true.
    """

    type_name = "close_app"

    def execute(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        image_name = self._required(params, "image_name")
        force = bool(params.get("force", True))
        cmd = ["taskkill", "/IM", image_name]
        if force:
            cmd.append("/F")
        logger.info("close_app: %s", cmd)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip()
            if result.returncode == 128 and "not found" in message.lower():
                logger.info("close_app: process already absent: %s", image_name)
                return {"stdout": result.stdout.strip(), "already_absent": True}
            raise TransientStepError(
                self.type_name,
                f"taskkill exit={result.returncode}: {message}",
            )
        return {"stdout": result.stdout.strip()}


# ---------------------------------------------------------------------------
# UI automation
# ---------------------------------------------------------------------------


class ClickHandler(StepHandler):
    """Click at coordinates or on an image template.

    Params (one of):
        x, y: integer screen coordinates.
        image: path to a PNG to locate on screen (uses ``locateCenterOnScreen``).
        button: 'left' | 'right' | 'middle' (default 'left').
        clicks: number of clicks (default 1).
        confidence: 0..1 for image match (only when ``image`` is provided).
    """

    type_name = "click"

    def execute(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        button = params.get("button", "left")
        clicks = int(params.get("clicks", 1))
        if "image" in params:
            confidence = float(params.get("confidence", 0.9))
            location = pyautogui.locateCenterOnScreen(params["image"], confidence=confidence)
            if location is None:
                raise TransientStepError(
                    self.type_name, f"image not found on screen: {params['image']}"
                )
            x, y = int(location.x), int(location.y)
        else:
            x = int(self._required(params, "x"))
            y = int(self._required(params, "y"))
        logger.info("click(%s,%s) button=%s clicks=%s", x, y, button, clicks)
        pyautogui.click(x=x, y=y, clicks=clicks, button=button)
        return {"x": x, "y": y}


class MoveMouseHandler(StepHandler):
    """Move the cursor to absolute coordinates.

    Params: x, y, duration (seconds, default 0.0).
    """

    type_name = "move_mouse"

    def execute(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        x = int(self._required(params, "x"))
        y = int(self._required(params, "y"))
        duration = float(params.get("duration", 0.0))
        pyautogui.moveTo(x, y, duration=duration)
        return {"x": x, "y": y}


class TypeTextHandler(StepHandler):
    """Type text into the focused window.

    Params:
        text: the string to type.
        interval: per-character delay (seconds).
    """

    type_name = "type_text"

    def execute(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        text = str(self._required(params, "text"))
        interval = float(params.get("interval", 0.02))
        logger.info("type_text len=%d interval=%s", len(text), interval)
        pyautogui.typewrite(text, interval=interval)
        return {"chars": len(text)}


class HotkeyHandler(StepHandler):
    """Press a keyboard shortcut.

    Params:
        keys: list of key names, e.g. ``["ctrl", "s"]``.
    """

    type_name = "hotkey"

    def execute(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        keys = self._required(params, "keys")
        if not isinstance(keys, (list, tuple)) or not keys:
            raise PermanentStepError(self.type_name, "'keys' must be a non-empty list")
        logger.info("hotkey: %s", "+".join(str(k) for k in keys))
        pyautogui.hotkey(*[str(k) for k in keys])
        return {"keys": list(keys)}


class WaitHandler(StepHandler):
    """Sleep for a configurable number of seconds.

    Params: seconds (float, default 1.0).
    """

    type_name = "wait"

    def execute(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        seconds = float(params.get("seconds", 1.0))
        time.sleep(seconds)
        return {"seconds": seconds}


class ScreenshotHandler(StepHandler):
    """Capture the screen as part of the pipeline (not the on-failure capture).

    Params:
        label: optional filename suffix.
    """

    type_name = "screenshot"

    def __init__(self) -> None:
        # Lazy import avoids a circular reference at module load time.
        from app.automation.screenshot import ScreenshotService

        self._service = ScreenshotService()

    def execute(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        label = str(params.get("label", "step"))
        path = self._service.capture(label=label)
        return {"path": str(path)}


class ScrollHandler(StepHandler):
    """Scroll the mouse wheel.

    Params:
        clicks: positive = up, negative = down.
        x, y: optional anchor coordinates (defaults to current position).
    """

    type_name = "scroll"

    def execute(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        clicks = int(self._required(params, "clicks"))
        x = params.get("x")
        y = params.get("y")
        if x is not None and y is not None:
            pyautogui.scroll(clicks, x=int(x), y=int(y))
        else:
            pyautogui.scroll(clicks)
        return {"clicks": clicks}


class DragHandler(StepHandler):
    """Click and drag from one point to another.

    Params:
        from_x, from_y: starting coordinates.
        to_x, to_y: ending coordinates.
        duration: seconds (default 0.4).
        button: 'left' | 'right' | 'middle' (default 'left').
    """

    type_name = "drag"

    def execute(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        fx = int(self._required(params, "from_x"))
        fy = int(self._required(params, "from_y"))
        tx = int(self._required(params, "to_x"))
        ty = int(self._required(params, "to_y"))
        duration = float(params.get("duration", 0.4))
        button = params.get("button", "left")
        logger.info("drag (%s,%s) -> (%s,%s) button=%s", fx, fy, tx, ty, button)
        pyautogui.moveTo(fx, fy)
        pyautogui.dragTo(tx, ty, duration=duration, button=button)
        return {"from": [fx, fy], "to": [tx, ty]}


class KeyPressHandler(StepHandler):
    """Press a single key (or a list of keys, sequentially).

    Params:
        key: e.g. "enter", or list ["tab","tab","enter"].
        presses: number of presses for a single key (default 1).
        interval: per-press delay (seconds, default 0.05).
    """

    type_name = "key_press"

    def execute(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        key = self._required(params, "key")
        presses = int(params.get("presses", 1))
        interval = float(params.get("interval", 0.05))
        if isinstance(key, list):
            for k in key:
                pyautogui.press(str(k), interval=interval)
            return {"keys": list(key)}
        pyautogui.press(str(key), presses=presses, interval=interval)
        return {"key": str(key), "presses": presses}


class WriteClipboardHandler(StepHandler):
    """Place text on the Windows clipboard via clip.exe.

    Params:
        text: the string to copy.
    """

    type_name = "write_clipboard"

    def execute(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        text = str(self._required(params, "text"))
        try:
            proc = subprocess.run(
                ["clip"],
                input=text,
                text=True,
                capture_output=True,
                shell=False,
            )
        except OSError as exc:
            raise StepExecutionError(self.type_name, f"clip.exe unavailable: {exc}", original=exc)
        if proc.returncode != 0:
            raise StepExecutionError(
                self.type_name,
                f"clip exit={proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}",
            )
        return {"chars": len(text)}


class ReadClipboardHandler(StepHandler):
    """Read the Windows clipboard via PowerShell Get-Clipboard.

    Returns: ``{"text": <clipboard contents>}``.
    """

    type_name = "read_clipboard"

    def execute(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                capture_output=True,
                text=True,
                shell=False,
            )
        except OSError as exc:
            raise StepExecutionError(self.type_name, f"powershell unavailable: {exc}", original=exc)
        if proc.returncode != 0:
            raise StepExecutionError(
                self.type_name,
                f"Get-Clipboard exit={proc.returncode}: {proc.stderr.strip()}",
            )
        # PowerShell appends a trailing newline; strip exactly one if present.
        text_value = proc.stdout
        if text_value.endswith("\r\n"):
            text_value = text_value[:-2]
        elif text_value.endswith("\n"):
            text_value = text_value[:-1]
        return {"text": text_value}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def _build_registry() -> Dict[str, StepHandler]:
    handlers: list[StepHandler] = [
        LaunchAppHandler(),
        CloseAppHandler(),
        ClickHandler(),
        MoveMouseHandler(),
        TypeTextHandler(),
        HotkeyHandler(),
        WaitHandler(),
        ScreenshotHandler(),
        ScrollHandler(),
        DragHandler(),
        KeyPressHandler(),
        WriteClipboardHandler(),
        ReadClipboardHandler(),
    ]
    return {h.type_name: h for h in handlers}


STEP_HANDLERS: Dict[str, StepHandler] = _build_registry()
for _handler in STEP_HANDLERS.values():
    ACTION_REGISTRY.register(_handler)
ACTION_REGISTRY.register(STEP_HANDLERS["launch_app"], "open_app")
ACTION_REGISTRY.register(STEP_HANDLERS["type_text"], "type")


def get_handler(step_type: str) -> StepHandler:
    """Return the registered handler for ``step_type`` or raise."""
    handler = STEP_HANDLERS.get(step_type)
    if handler is None:
        raise UnknownStepTypeError(f"no handler registered for step type '{step_type}'")
    return handler
