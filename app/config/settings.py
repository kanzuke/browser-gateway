"""Configuration via Pydantic Settings — toutes les constantes en dur sont interdites."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration du service, chargée depuis .env ou variables d'environnement."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Browser ---
    browser_headless: bool = True
    browser_profile_dir: Path = Path("/data/browser-profile")
    browser_executable_path: str = ""
    browser_launch_args: str = (
        "--disable-blink-features=AutomationControlled "
        "--no-sandbox "
        "--disable-dev-shm-usage "
        "--disable-features=IsolateOrigins,site-per-process "
        "--disable-infobars "
        "--window-size=1920,1080 "
        "--start-maximized"
    )
    browser_viewport_width: int = 1920
    browser_viewport_height: int = 1080
    browser_user_agent: str = ""

    # --- Identity ---
    identity_rotation_days: int = 30
    identity_score_initial: int = 100
    identity_score_ready: int = 80
    identity_score_degraded: int = 50
    identity_score_blocked: int = 20

    # --- Penalties ---
    penalty_datadome: int = 15
    penalty_cloudflare: int = 10
    penalty_captcha: int = 20
    penalty_http_403: int = 10
    penalty_http_429: int = 10
    penalty_nav_fail: int = 5

    # --- Bonus ---
    bonus_nav_success: int = 1

    # --- Behavior ---
    behavior_random_scroll: bool = True
    behavior_warmup_wait_min: int = 3
    behavior_warmup_wait_max: int = 8
    behavior_nav_timeout_ms: int = 30000

    # --- History ---
    history_max_records: int = 500

    # --- Monitoring ---
    monitoring_max_memory_mb: int = 512

    # --- Logging ---
    log_level: str = "INFO"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000

    @property
    def launch_args_list(self) -> list[str]:
        """Retourne les args de launch séparés en liste."""
        return self.browser_launch_args.split()

    @property
    def warmup_wait_range(self) -> tuple[int, int]:
        """Tuple (min, max) pour le warmup."""
        return self.behavior_warmup_wait_min, self.behavior_warmup_wait_max


def get_settings() -> Settings:
    """Factory — instancie Settings à chaque appel (test-friendly)."""
    return Settings()
