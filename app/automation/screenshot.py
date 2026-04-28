"""Screenshot capture used both as a step and on failure."""

from __future__ import annotations

from pathlib import Path

import pyautogui

from app.core.config import settings
from app.core.logger import get_logger
from app.db.models import _utcnow

logger = get_logger(__name__)


class ScreenshotService:
    """Thin wrapper around ``pyautogui.screenshot`` with deterministic naming."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or settings.screenshot_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def capture(self, label: str) -> Path:
        """Capture the full desktop and return the saved file path.

        ``label`` is sanitised into the filename so it is safe to pass any string.
        """
        safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)
        timestamp = _utcnow().strftime("%Y%m%dT%H%M%S%f")
        path = self._output_dir / f"{timestamp}_{safe_label}.png"
        try:
            image = pyautogui.screenshot()
            image.save(path)
            logger.info("screenshot saved: %s", path)
            return path
        except Exception:  # pragma: no cover - environment-specific
            logger.exception("failed to capture screenshot")
            raise
