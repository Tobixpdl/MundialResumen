from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .date_utils import format_ddmmyyyy


DAY_NAMES_ES = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


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


def _format_telegram_time(time_value: str | None) -> str:
    if not time_value:
        return "Horario a confirmar"

    clean_time = str(time_value).strip()[:5]
    if ":" not in clean_time:
        return clean_time

    hour_text, minute_text = clean_time.split(":", maxsplit=1)
    try:
        hour = int(hour_text)
    except ValueError:
        return clean_time

    if minute_text == "00":
        return f"{hour}hs"
    return f"{hour}:{minute_text}"


def _format_telegram_date(date_value: str | None) -> str:
    if not date_value:
        return "Fecha a confirmar"

    try:
        parsed_date = datetime.fromisoformat(str(date_value)).date()
    except ValueError:
        return str(date_value)

    day_name = DAY_NAMES_ES[parsed_date.weekday()]
    return f"{day_name} {parsed_date.strftime('%d/%m')}"


def _format_telegram_match_line(match: dict[str, Any], include_date: bool = False) -> str:
    time_label = _format_telegram_time(match.get("time_argentina"))
    score = format_score(match)

    if include_date:
        date_label = _format_telegram_date(match.get("date"))
        return f"• {date_label} · {time_label} — {score}"

    return f"• {time_label} — {score}"


def _format_telegram_match_section(title: str, matches: list[dict[str, Any]], include_date: bool = False) -> str:
    if not matches:
        return f"{title}\nSin partidos."

    lines = [title]
    for match in matches:
        lines.append(_format_telegram_match_line(match, include_date=include_date))

        if match.get("status") == "finalizado":
            goals = format_goals(match)
            if goals and goals != "Detalle de goles no disponible todavía.":
                lines.append(f"  ⚽ Goles: {goals}")

            cards = format_cards(match)
            if cards and cards != "Tarjetas importantes no disponibles todavía.":
                lines.append(f"  🟨 Tarjetas: {cards}")

    return "\n".join(lines)


def render_daily_telegram(context: dict[str, Any]) -> str:
    parts = [
        "🏆 Mundial 2026",
        "",
        _format_telegram_match_section("📌 Ayer", context.get("yesterday_matches", [])),
        "",
        _format_telegram_match_section("🔥 Hoy", context.get("today_matches", [])),
        "",
        _format_telegram_match_section("📅 Próximos partidos", context.get("upcoming_matches", []), include_date=True),
    ]

    return "\n".join(parts).strip()
