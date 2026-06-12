from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
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


def _window_label(start: datetime, end: datetime) -> str:
    return f"{start.strftime('%d/%m %H:%M')} a {end.strftime('%d/%m %H:%M')} ARG"


def _dates_covered_by_window(start: datetime, end: datetime) -> list[date]:
    dates: list[date] = []
    current = start.date()
    last = end.date()
    while current <= last:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def get_report_windows(
    tz_name: str,
    upcoming_days: int = 3,
    start_hour: int = 10,
    now: datetime | None = None,
) -> dict[str, object]:
    """
    Build report windows anchored to the local calendar date.

    Example with start_hour=10 and local date 05/06:
    - Ayer: 04/06 10:00 <= match < 05/06 10:00
    - Hoy: 05/06 10:00 <= match < 06/06 10:00
    - Próximos: following windows of 24 hours, also starting at 10:00
    """
    tz = ZoneInfo(tz_name)
    local_now = now.astimezone(tz) if now else now_in_timezone(tz_name)
    report_date = local_now.date()

    start_hour = max(0, min(23, start_hour))

    def start_for(day: date) -> datetime:
        return datetime.combine(day, time(hour=start_hour), tzinfo=tz)

    today_start = start_for(report_date)
    today_end = today_start + timedelta(days=1)
    yesterday_start = today_start - timedelta(days=1)
    yesterday_end = today_start

    upcoming_windows: list[dict[str, object]] = []
    for index in range(1, upcoming_days + 1):
        start = today_start + timedelta(days=index)
        end = start + timedelta(days=1)
        upcoming_windows.append(
            {
                "date": start.date(),
                "start": start,
                "end": end,
                "label": _window_label(start, end),
            }
        )

    fetch_dates: set[date] = set()
    for start, end in [(yesterday_start, yesterday_end), (today_start, today_end)]:
        fetch_dates.update(_dates_covered_by_window(start, end))
    for window in upcoming_windows:
        fetch_dates.update(_dates_covered_by_window(window["start"], window["end"]))

    return {
        "report_date": report_date,
        "yesterday": {
            "date": yesterday_start.date(),
            "start": yesterday_start,
            "end": yesterday_end,
            "label": _window_label(yesterday_start, yesterday_end),
        },
        "today": {
            "date": today_start.date(),
            "start": today_start,
            "end": today_end,
            "label": _window_label(today_start, today_end),
        },
        "upcoming": upcoming_windows,
        "fetch_dates": sorted(fetch_dates),
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
