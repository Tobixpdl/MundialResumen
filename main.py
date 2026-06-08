from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from src.api_football_client import APIFootballClient, APIFootballError
from src.config import Config, load_config
from src.date_utils import format_ddmmyyyy, get_date_window
from src.email_sender import send_email
from src.formatter import build_console_summary, render_daily_email
from src.logger import get_logger
from src.normalizer import (
    enrich_api_football_match,
    filter_matches_by_date,
    is_finished,
    normalize_api_football_fixtures,
    normalize_openfootball_matches,
)
from src.openfootball_client import OpenFootballClient, OpenFootballError

logger = get_logger()


def _sort_matches(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(matches, key=lambda item: (item.get("date", ""), item.get("time_argentina", ""), item.get("home_team", "")))


def _fetch_from_api_football(config: Config, yesterday: date, today: date, upcoming: list[date]) -> dict[str, list[dict[str, Any]]]:
    if not config.api_football_key:
        raise APIFootballError("API_FOOTBALL_KEY no está configurada.")

    client = APIFootballClient(config.api_football_key, cache_dir=config.project_root / ".cache")
    logger.info("Consultando API-FOOTBALL...")

    raw_yesterday = client.get_fixtures_by_date(yesterday, config.timezone)
    raw_today = client.get_fixtures_by_date(today, config.timezone)

    raw_upcoming: list[dict[str, Any]] = []
    for target_date in upcoming:
        raw_upcoming.extend(client.get_fixtures_by_date(target_date, config.timezone))

    yesterday_matches = normalize_api_football_fixtures(raw_yesterday, config.timezone)
    today_matches = normalize_api_football_fixtures(raw_today, config.timezone)
    upcoming_matches = normalize_api_football_fixtures(raw_upcoming, config.timezone)

    for match in yesterday_matches:
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

    return {
        "yesterday_matches": _sort_matches(yesterday_matches),
        "today_matches": _sort_matches(today_matches),
        "upcoming_matches": _sort_matches(upcoming_matches),
    }


def _fetch_from_openfootball(config: Config, yesterday: date, today: date, upcoming: list[date]) -> dict[str, list[dict[str, Any]]]:
    logger.info("Usando OpenFootball como fallback...")
    client = OpenFootballClient(cache_dir=config.project_root / ".cache")
    raw_matches = client.get_matches()
    normalized = normalize_openfootball_matches(raw_matches, config.timezone)

    upcoming_matches: list[dict[str, Any]] = []
    for target_date in upcoming:
        upcoming_matches.extend(filter_matches_by_date(normalized, target_date))

    return {
        "yesterday_matches": _sort_matches(filter_matches_by_date(normalized, yesterday)),
        "today_matches": _sort_matches(filter_matches_by_date(normalized, today)),
        "upcoming_matches": _sort_matches(upcoming_matches),
    }


def build_email_context(config: Config) -> dict[str, Any]:
    window = get_date_window(config.timezone, config.upcoming_days)
    yesterday = window["yesterday"]
    today = window["today"]
    upcoming = window["upcoming"]
    assert isinstance(yesterday, date)
    assert isinstance(today, date)
    assert isinstance(upcoming, list)

    fallback_reason = ""
    source_label = "API-FOOTBALL"

    try:
        if config.dry_run:
            raise APIFootballError("DRY_RUN=true: se usa fallback para no gastar requests de API-FOOTBALL.")
        matches = _fetch_from_api_football(config, yesterday, today, upcoming)
    except (APIFootballError, OpenFootballError) as exc:
        fallback_reason = str(exc)
        if not config.use_openfootball_fallback:
            raise
        source_label = "OpenFootball fallback"
        try:
            matches = _fetch_from_openfootball(config, yesterday, today, upcoming)
        except OpenFootballError as fallback_exc:
            if not config.dry_run:
                raise
            source_label = "modo demo sin datos"
            fallback_reason = f"{fallback_reason} | OpenFootball tampoco respondió: {fallback_exc}"
            logger.warning("OpenFootball no respondió en DRY_RUN. Se genera una preview vacía.")
            matches = {"yesterday_matches": [], "today_matches": [], "upcoming_matches": []}

    return {
        "report_date": format_ddmmyyyy(today),
        "today_iso": today.isoformat(),
        "source_label": source_label,
        "fallback_reason": fallback_reason,
        "yesterday_date": yesterday,
        "today_date": today,
        "upcoming_dates": upcoming,
        **matches,
    }


def save_preview(project_root: Path, html: str) -> Path:
    output_dir = project_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    preview_path = output_dir / "daily_email_preview.html"
    preview_path.write_text(html, encoding="utf-8")
    return preview_path


def main() -> None:
    config = load_config()
    context = build_email_context(config)
    html = render_daily_email(context, template_dir=config.project_root / "templates")

    subject = f"Resumen Mundialista - {context['report_date']}"

    logger.info(build_console_summary(context))
    logger.info("Fuente usada: %s", context["source_label"])

    if config.dry_run:
        preview_path = save_preview(config.project_root, html)
        logger.info("DRY_RUN=true: no se envió email. Preview guardada en %s", preview_path)
        return

    send_email(config, subject=subject, html_body=html)
    logger.info("Email enviado correctamente a %s", config.email_to)


if __name__ == "__main__":
    main()
