from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.api_football_client import APIFootballClient, APIFootballError
from src.config import Config, load_config
<<<<<<< Updated upstream
from src.date_utils import format_ddmmyyyy, get_date_window
=======
from src.date_utils import format_ddmmyyyy, get_report_windows
>>>>>>> Stashed changes
from src.telegram_sender import send_telegram_message
from src.formatter import build_console_summary, render_daily_telegram
from src.logger import get_logger
from src.normalizer import (
    enrich_api_football_match,
    filter_matches_by_window,
    is_finished,
    normalize_api_football_fixtures,
    normalize_openfootball_matches,
)
from src.openfootball_client import OpenFootballClient, OpenFootballError

logger = get_logger()


def _sort_matches(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(matches, key=lambda item: (item.get("kickoff_at", ""), item.get("home_team", "")))


def _dedupe_raw_fixtures(raw_fixtures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in raw_fixtures:
        fixture_id = (((item.get("fixture") or {}).get("id")))
        key = str(fixture_id) if fixture_id is not None else repr(item)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _enrich_finished_matches(client: APIFootballClient, matches: list[dict[str, Any]]) -> None:
    for match in matches:
        if not is_finished(match) or not match.get("fixture_id"):
            continue
        fixture_id = match["fixture_id"]
        try:
            events = client.get_fixture_events(fixture_id)
        except APIFootballError as exc:
            logger.warning("No se pudieron obtener eventos para fixture %s: %s", fixture_id, exc)
            events = []
        try:
            statistics = client.get_fixture_statistics(fixture_id)
        except APIFootballError as exc:
            logger.warning("No se pudieron obtener estadísticas para fixture %s: %s", fixture_id, exc)
            statistics = []
        try:
            lineups = client.get_fixture_lineups(fixture_id)
        except APIFootballError as exc:
            logger.warning("No se pudieron obtener lineups para fixture %s: %s", fixture_id, exc)
            lineups = []

        enrich_api_football_match(match, events=events, statistics=statistics, lineups=lineups)


def _window_dates(windows: dict[str, Any]) -> list[date]:
    dates = windows.get("fetch_dates", [])
    return [item for item in dates if isinstance(item, date)]


def _filter_context_matches(all_matches: list[dict[str, Any]], windows: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    yesterday_window = windows["yesterday"]
    today_window = windows["today"]
    upcoming_windows = windows["upcoming"]

    assert isinstance(yesterday_window["start"], datetime)
    assert isinstance(yesterday_window["end"], datetime)
    assert isinstance(today_window["start"], datetime)
    assert isinstance(today_window["end"], datetime)
    assert isinstance(upcoming_windows, list)

    upcoming_matches: list[dict[str, Any]] = []
    for window in upcoming_windows:
        assert isinstance(window["start"], datetime)
        assert isinstance(window["end"], datetime)
        upcoming_matches.extend(filter_matches_by_window(all_matches, window["start"], window["end"]))

    return {
        "yesterday_matches": _sort_matches(filter_matches_by_window(all_matches, yesterday_window["start"], yesterday_window["end"])),
        "today_matches": _sort_matches(filter_matches_by_window(all_matches, today_window["start"], today_window["end"])),
        "upcoming_matches": _sort_matches(upcoming_matches),
    }


def _fetch_from_api_football(config: Config, windows: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    if not config.api_football_key:
        raise APIFootballError("API_FOOTBALL_KEY no está configurada.")

    client = APIFootballClient(config.api_football_key, cache_dir=config.project_root / ".cache")
    logger.info("Consultando API-FOOTBALL...")

    raw_fixtures: list[dict[str, Any]] = []
    for target_date in _window_dates(windows):
        raw_fixtures.extend(client.get_fixtures_by_date(target_date, config.timezone))

    all_matches = normalize_api_football_fixtures(_dedupe_raw_fixtures(raw_fixtures), config.timezone)
    _enrich_finished_matches(client, all_matches)
    return _filter_context_matches(all_matches, windows)


def _fetch_from_openfootball(config: Config, windows: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    logger.info("Usando OpenFootball como fallback...")
    client = OpenFootballClient(cache_dir=config.project_root / ".cache")
    raw_matches = client.get_matches()
    normalized = normalize_openfootball_matches(raw_matches, config.timezone)
    return _filter_context_matches(normalized, windows)


def build_report_context(config: Config) -> dict[str, Any]:
<<<<<<< Updated upstream
    window = get_date_window(config.timezone, config.upcoming_days)
    yesterday = window["yesterday"]
    today = window["today"]
    upcoming = window["upcoming"]
    assert isinstance(yesterday, date)
    assert isinstance(today, date)
    assert isinstance(upcoming, list)
=======
    windows = get_report_windows(config.timezone, config.upcoming_days, config.report_start_hour)
    report_date = windows["report_date"]
    yesterday_window = windows["yesterday"]
    today_window = windows["today"]
    upcoming_windows = windows["upcoming"]

    assert isinstance(report_date, date)
    assert isinstance(yesterday_window, dict)
    assert isinstance(today_window, dict)
    assert isinstance(upcoming_windows, list)
    assert isinstance(yesterday_window["date"], date)
    assert isinstance(today_window["date"], date)
>>>>>>> Stashed changes

    fallback_reason = ""
    source_label = "API-FOOTBALL"

    try:
        if config.dry_run:
            raise APIFootballError("DRY_RUN=true: se usa fallback para no gastar requests de API-FOOTBALL.")
        matches = _fetch_from_api_football(config, windows)
    except (APIFootballError, OpenFootballError) as exc:
        fallback_reason = str(exc)
        if not config.use_openfootball_fallback:
            raise
        source_label = "OpenFootball fallback"
        try:
            matches = _fetch_from_openfootball(config, windows)
        except OpenFootballError as fallback_exc:
            if not config.dry_run:
                raise
            source_label = "modo demo sin datos"
            fallback_reason = f"{fallback_reason} | OpenFootball tampoco respondió: {fallback_exc}"
            logger.warning("OpenFootball no respondió en DRY_RUN. Se genera una preview vacía.")
            matches = {"yesterday_matches": [], "today_matches": [], "upcoming_matches": []}

    return {
        "report_date": format_ddmmyyyy(report_date),
        "today_iso": today_window["date"].isoformat(),
        "source_label": source_label,
        "fallback_reason": fallback_reason,
        "yesterday_date": yesterday_window["date"],
        "today_date": today_window["date"],
        "upcoming_dates": [window["date"] for window in upcoming_windows],
        "yesterday_window_label": yesterday_window["label"],
        "today_window_label": today_window["label"],
        "upcoming_window_label": f"desde {upcoming_windows[0]['label'].split(' a ')[0]}" if upcoming_windows else "",
        **matches,
    }


def save_preview(project_root: Path, text: str) -> Path:
    output_dir = project_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    preview_path = output_dir / "daily_telegram_preview.txt"
    preview_path.write_text(text, encoding="utf-8")
    return preview_path


def main() -> None:
    config = load_config()
    context = build_report_context(config)
    telegram_text = render_daily_telegram(context)

    logger.info(build_console_summary(context))
    logger.info("Fuente usada: %s", context["source_label"])
    logger.info("Ventana de hoy: %s", context.get("today_window_label", ""))

    if config.dry_run:
        preview_path = save_preview(config.project_root, telegram_text)
        logger.info("DRY_RUN=true: no se envió Telegram. Preview guardada en %s", preview_path)
        return

    send_telegram_message(config, telegram_text)
    logger.info("Mensaje enviado correctamente por Telegram al chat %s", config.telegram_chat_id)


if __name__ == "__main__":
    main()
