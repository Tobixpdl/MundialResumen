from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    api_football_key: str | None
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    email_from: str
    email_to: str
    telegram_token: str
    telegram_chat_id: str
    timezone: str
    upcoming_days: int
    report_start_hour: int
    dry_run: bool
    use_openfootball_fallback: bool
    use_elnine_fallback: bool
    project_root: Path


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "si", "sí", "on"}


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def _as_hour(value: str | None, default: int = 10) -> int:
    hour = _as_int(value, default)
    if hour < 0:
        return 0
    if hour > 23:
        return 23
    return hour


def load_config(project_root: Path | None = None) -> Config:
    root = project_root or Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")

    return Config(
        api_football_key=os.getenv("API_FOOTBALL_KEY") or None,
        smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=_as_int(os.getenv("SMTP_PORT"), 587),
        smtp_user=os.getenv("SMTP_USER", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        email_from=os.getenv("EMAIL_FROM", ""),
        email_to=os.getenv("EMAIL_TO", ""),
        telegram_token=os.getenv("TELEGRAM_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        timezone=os.getenv("TIMEZONE", "America/Argentina/Buenos_Aires"),
        upcoming_days=max(1, _as_int(os.getenv("UPCOMING_DAYS"), 3)),
        report_start_hour=_as_hour(os.getenv("REPORT_START_HOUR"), 10),
        dry_run=_as_bool(os.getenv("DRY_RUN"), False),
        use_openfootball_fallback=_as_bool(os.getenv("USE_OPENFOOTBALL_FALLBACK"), True),
        use_elnine_fallback=_as_bool(os.getenv("USE_ELNINE_FALLBACK"), True),
        project_root=root,
    )
