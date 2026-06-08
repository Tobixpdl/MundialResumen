from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .date_utils import format_ddmmyyyy


def format_score(match: dict[str, Any]) -> str:
    home = match.get("home_team") or "Equipo local"
    away = match.get("away_team") or "Equipo visitante"
    home_score = match.get("home_score")
    away_score = match.get("away_score")
    if home_score is None or away_score is None:
        return f"{home} vs {away}"
    return f"{home} {home_score} - {away_score} {away}"


def format_match_datetime_label(match: dict[str, Any], today_iso: str | None = None) -> str:
    date_value = match.get("date", "")
    time_value = match.get("time_argentina", "")
    if today_iso and date_value == today_iso:
        return f"Hoy, {time_value} ARG" if time_value else "Hoy"
    if not date_value:
        return f"{time_value} ARG" if time_value else "Horario no disponible"
    return f"{date_value} - {time_value} ARG" if time_value else date_value


def format_goals(match: dict[str, Any]) -> str:
    goals = match.get("goals") or []
    if not goals:
        return "Detalle de goles no disponible todavía."

    home_team = match.get("home_team")
    home_goals = []
    away_goals = []
    for goal in goals:
        text = goal.get("player") or "Gol"
        minute = goal.get("minute")
        if minute:
            text = f"{text} {minute}’"
        detail = goal.get("detail")
        if detail and detail not in {"Normal Goal"}:
            text = f"{text} ({detail})"
        if goal.get("team") == home_team:
            home_goals.append(text)
        else:
            away_goals.append(text)

    left = ", ".join(home_goals) if home_goals else "-"
    right = ", ".join(away_goals) if away_goals else "-"
    return f"{left} / {right}"


def format_cards(match: dict[str, Any]) -> str:
    cards = match.get("cards") or []
    if not cards:
        return "Tarjetas importantes no disponibles todavía."
    formatted = []
    for card in cards:
        player = card.get("player") or "Jugador"
        detail = card.get("detail") or "Tarjeta"
        minute = f" {card.get('minute')}’" if card.get("minute") else ""
        team = f" - {card.get('team')}" if card.get("team") else ""
        formatted.append(f"{player}{minute} ({detail}{team})")
    return ", ".join(formatted)


def render_daily_email(context: dict[str, Any], template_dir: Path | str) -> str:
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["score"] = format_score
    env.filters["goals"] = format_goals
    env.filters["cards"] = format_cards
    env.filters["date_label"] = format_match_datetime_label
    env.filters["ddmmyyyy"] = format_ddmmyyyy

    template = env.get_template("daily_email.html")
    return template.render(**context)


def build_console_summary(context: dict[str, Any]) -> str:
    yesterday = len(context.get("yesterday_matches", []))
    today = len(context.get("today_matches", []))
    upcoming = len(context.get("upcoming_matches", []))
    source = context.get("source_label", "desconocida")
    return f"Fuente: {source} | Ayer: {yesterday} | Hoy: {today} | Próximos: {upcoming}"
