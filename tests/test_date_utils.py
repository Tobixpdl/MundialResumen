from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.date_utils import get_date_window, parse_openfootball_datetime, utc_to_timezone


def test_get_date_window_uses_configured_timezone():
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    window = get_date_window("America/Argentina/Buenos_Aires", upcoming_days=3, now=now)

    assert window["yesterday"].isoformat() == "2026-06-07"
    assert window["today"].isoformat() == "2026-06-08"
    assert [d.isoformat() for d in window["upcoming"]] == ["2026-06-09", "2026-06-10", "2026-06-11"]


def test_utc_to_argentina_time():
    local_dt = utc_to_timezone("2026-06-11T19:00:00+00:00", "America/Argentina/Buenos_Aires")

    assert local_dt.strftime("%Y-%m-%d %H:%M") == "2026-06-11 16:00"
    assert local_dt.tzinfo == ZoneInfo("America/Argentina/Buenos_Aires")


def test_parse_openfootball_datetime_with_utc_offset():
    local_dt = parse_openfootball_datetime("2026-06-11", "13:00 UTC-6", "America/Argentina/Buenos_Aires")

    assert local_dt.strftime("%Y-%m-%d %H:%M") == "2026-06-11 16:00"
