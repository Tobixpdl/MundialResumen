from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def now_in_timezone(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def get_date_window(tz_name: str, upcoming_days: int = 3, now: datetime | None = None) -> dict[str, object]:
    local_now = now.astimezone(ZoneInfo(tz_name)) if now else now_in_timezone(tz_name)
    today = local_now.date()
    return {
        "yesterday": today - timedelta(days=1),
        "today": today,
        "upcoming": [today + timedelta(days=i) for i in range(1, upcoming_days + 1)],
    }


def iso_date(value: date) -> str:
    return value.isoformat()


def parse_api_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def utc_to_timezone(value: str, tz_name: str) -> datetime:
    return parse_api_datetime(value).astimezone(ZoneInfo(tz_name))


def format_argentina_time(value: str, tz_name: str = "America/Argentina/Buenos_Aires") -> str:
    return utc_to_timezone(value, tz_name).strftime("%H:%M")


def parse_openfootball_datetime(date_value: str, time_value: str, target_tz: str) -> datetime:
    """Parse OpenFootball times like '13:00 UTC-6' and convert to target timezone."""
    if not time_value:
        return datetime.fromisoformat(date_value).replace(tzinfo=timezone.utc).astimezone(ZoneInfo(target_tz))

    match = re.search(r"(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*UTC(?P<offset>[+-]\d{1,2})", time_value)
    if not match:
        return datetime.fromisoformat(f"{date_value}T00:00:00+00:00").astimezone(ZoneInfo(target_tz))

    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    offset_hours = int(match.group("offset"))
    source_tz = timezone(timedelta(hours=offset_hours))
    local_dt = datetime.fromisoformat(date_value).replace(hour=hour, minute=minute, tzinfo=source_tz)
    return local_dt.astimezone(ZoneInfo(target_tz))


def format_ddmmyyyy(value: date) -> str:
    return value.strftime("%d/%m/%Y")
