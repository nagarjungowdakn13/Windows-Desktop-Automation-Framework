"""Application configuration loaded from environment / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Strongly-typed runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_prefix="WDA_",
        extra="ignore",
    )

    # --- Server -------------------------------------------------------------
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000)
    api_base_url: str = Field(default="http://127.0.0.1:8000")

    # --- Storage paths ------------------------------------------------------
    data_dir: Path = Field(default=PROJECT_ROOT / "data")
    log_dir: Path = Field(default=PROJECT_ROOT / "logs")
    screenshot_dir: Path = Field(default=PROJECT_ROOT / "screenshots")

    # --- Database -----------------------------------------------------------
    database_url: str = Field(
        default=f"sqlite:///{(PROJECT_ROOT / 'data' / 'automation.db').as_posix()}"
    )

    # --- Automation defaults -----------------------------------------------
    default_step_retries: int = Field(default=2)
    default_retry_delay_sec: float = Field(default=1.0)
    pyautogui_pause_sec: float = Field(default=0.1)
    pyautogui_failsafe: bool = Field(default=True)

    # --- Worker -------------------------------------------------------------
    worker_queue_size: int = Field(default=128)

    def ensure_dirs(self) -> None:
        """Create runtime directories if missing."""
        for path in (self.data_dir, self.log_dir, self.screenshot_dir):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
