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


def _format_match_line(match: dict[str, Any], today_iso: str | None = None) -> str:
    label = format_match_datetime_label(match, today_iso=today_iso)
    score = format_score(match)
    status = match.get("status") or "programado"
    venue = match.get("venue") or ""
    city = match.get("city") or ""
    place = ""
    if venue and city:
        place = f" — {venue}, {city}"
    elif venue:
        place = f" — {venue}"
    elif city:
        place = f" — {city}"
    return f"• {label}: {score} ({status}){place}"


def _format_match_section(
    title: str,
    matches: list[dict[str, Any]],
    today_iso: str | None = None,
    window_label: str | None = None,
) -> str:
    heading = f"{title} ({window_label})" if window_label else title
    if not matches:
        return f"{heading}\nSin partidos para mostrar."

    lines = [heading]
    for match in matches:
        lines.append(_format_match_line(match, today_iso=today_iso))

        if match.get("status") == "finalizado":
            goals = format_goals(match)
            if goals and goals != "Detalle de goles no disponible todavía.":
                lines.append(f"  Goles: {goals}")

            cards = format_cards(match)
            if cards and cards != "Tarjetas importantes no disponibles todavía.":
                lines.append(f"  Tarjetas: {cards}")

        stats = match.get("statistics_pairs") or []
        if stats:
            compact_stats = []
            for stat in stats[:4]:
                compact_stats.append(f"{stat['label']} {stat['home']}/{stat['away']}")
            lines.append(f"  Stats: {' | '.join(compact_stats)}")

    return "\n".join(lines)


def render_daily_telegram(context: dict[str, Any]) -> str:
    report_date = context.get("report_date", "")
    today_iso = context.get("today_iso")
    source = context.get("source_label", "desconocida")
    fallback_reason = context.get("fallback_reason", "")
    today_window_label = context.get("today_window_label", "")

    parts = [
        f"Resumen Mundialista - {report_date}",
        f"Fuente: {source}",
    ]

    if today_window_label:
        parts.append(f"Ventana de hoy: {today_window_label}")

    if fallback_reason:
        parts.append(f"Aviso: {fallback_reason}")

    parts.extend(
        [
            "",
            _format_match_section(
                "Ayer",
                context.get("yesterday_matches", []),
                today_iso=today_iso,
                window_label=context.get("yesterday_window_label"),
            ),
            "",
            _format_match_section(
                "Hoy",
                context.get("today_matches", []),
                today_iso=today_iso,
                window_label=today_window_label,
            ),
            "",
            _format_match_section(
                "Próximos partidos",
                context.get("upcoming_matches", []),
                today_iso=today_iso,
                window_label=context.get("upcoming_window_label"),
            ),
        ]
    )

    return "\n".join(parts).strip()
