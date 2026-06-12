from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any
from urllib.parse import unquote, urlparse
from zoneinfo import ZoneInfo

from .date_utils import parse_openfootball_datetime, utc_to_timezone

FINISHED_STATUSES = {"FT", "AET", "PEN"}
LIVE_STATUSES = {"1H", "HT", "2H", "ET", "P", "BT", "LIVE", "INT"}
POSTPONED_STATUSES = {"PST", "SUSP"}
CANCELLED_STATUSES = {"CANC", "ABD", "AWD", "WO"}

STAT_LABELS = {
    "ball possession": "Posesión",
    "total shots": "Tiros",
    "shots on goal": "Tiros al arco",
    "shots on target": "Tiros al arco",
    "corner kicks": "Corners",
    "corners": "Corners",
    "fouls": "Faltas",
    "offsides": "Offsides",
    "yellow cards": "Tarjetas amarillas",
    "red cards": "Tarjetas rojas",
    "expected goals": "xG",
    "expected_goals": "xG",
    "xg": "xG",
}

STAT_ORDER = [
    "Posesión",
    "Tiros",
    "Tiros al arco",
    "Corners",
    "Faltas",
    "Offsides",
    "Tarjetas amarillas",
    "Tarjetas rojas",
    "xG",
]


def empty_match() -> dict[str, Any]:
    return {
        "source": "",
        "fixture_id": None,
        "kickoff_at": "",
        "date": "",
        "time_argentina": "",
        "home_team": "",
        "away_team": "",
        "home_score": None,
        "away_score": None,
        "status": "programado",
        "status_raw": "",
        "round": "",
        "group": "",
        "venue": "",
        "city": "",
        "goals": [],
        "cards": [],
        "statistics": {},
        "statistics_pairs": [],
        "has_statistics": False,
        "has_events": False,
        "lineups": [],
        "has_lineups": False,
    }


def map_status(short_status: str | None, long_status: str | None = None) -> str:
    short = (short_status or "").upper()
    if short in FINISHED_STATUSES:
        return "finalizado"
    if short in LIVE_STATUSES:
        return "en vivo"
    if short in POSTPONED_STATUSES:
        return "postergado"
    if short in CANCELLED_STATUSES:
        return "cancelado"
    if short in {"NS", "TBD"}:
        return "programado"

    text = (long_status or "").lower()
    if "finished" in text:
        return "finalizado"
    if "postponed" in text:
        return "postergado"
    if "cancel" in text:
        return "cancelado"
    return "programado"


def is_finished(match: dict[str, Any]) -> bool:
    return str(match.get("status_raw", "")).upper() in FINISHED_STATUSES or match.get("status") == "finalizado"


def _safe_get(container: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = container
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return current if current is not None else default


def normalize_api_football_fixture(raw: dict[str, Any], timezone_name: str) -> dict[str, Any]:
    fixture = raw.get("fixture", {}) or {}
    league = raw.get("league", {}) or {}
    teams = raw.get("teams", {}) or {}
    goals = raw.get("goals", {}) or {}
    venue = fixture.get("venue", {}) or {}
    status = fixture.get("status", {}) or {}

    fixture_date = fixture.get("date")
    local_dt = utc_to_timezone(fixture_date, timezone_name) if fixture_date else None

    match = empty_match()
    match.update(
        {
            "source": "api-football",
            "fixture_id": fixture.get("id"),
            "kickoff_at": local_dt.isoformat() if local_dt else "",
            "date": local_dt.date().isoformat() if local_dt else "",
            "time_argentina": local_dt.strftime("%H:%M") if local_dt else "",
            "home_team": _safe_get(teams, "home", "name", default="Equipo local"),
            "away_team": _safe_get(teams, "away", "name", default="Equipo visitante"),
            "home_score": goals.get("home"),
            "away_score": goals.get("away"),
            "status": map_status(status.get("short"), status.get("long")),
            "status_raw": status.get("short", ""),
            "round": league.get("round") or "",
            "group": league.get("group") or "",
            "venue": venue.get("name") or "",
            "city": venue.get("city") or "",
        }
    )
    return match


def normalize_api_football_fixtures(raw_fixtures: list[dict[str, Any]], timezone_name: str) -> list[dict[str, Any]]:
    return [normalize_api_football_fixture(item, timezone_name) for item in raw_fixtures]


def normalize_api_football_events(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    goals: list[dict[str, Any]] = []
    cards: list[dict[str, Any]] = []

    for event in events or []:
        event_type = event.get("type")
        detail = event.get("detail") or ""
        elapsed = _safe_get(event, "time", "elapsed")
        extra = _safe_get(event, "time", "extra")
        minute = f"{elapsed}+{extra}" if extra else str(elapsed) if elapsed is not None else ""
        player_name = _safe_get(event, "player", "name", default="")
        team_name = _safe_get(event, "team", "name", default="")

        if event_type == "Goal" and "Missed Penalty" not in detail:
            goals.append(
                {
                    "team": team_name,
                    "player": player_name or "Gol",
                    "minute": minute,
                    "detail": detail,
                }
            )
        elif event_type == "Card":
            cards.append(
                {
                    "team": team_name,
                    "player": player_name or "Jugador",
                    "minute": minute,
                    "detail": detail or "Tarjeta",
                }
            )

    return goals, cards


def _normalize_stat_label(raw_label: str) -> str | None:
    key = raw_label.strip().lower()
    return STAT_LABELS.get(key)


def normalize_api_football_statistics(stats: list[dict[str, Any]], home_team: str, away_team: str) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    if not stats:
        return {}, []

    by_team: dict[str, dict[str, Any]] = {}
    for team_stats in stats:
        team_name = _safe_get(team_stats, "team", "name", default="")
        if not team_name:
            continue
        normalized_stats: dict[str, Any] = {}
        for stat in team_stats.get("statistics", []) or []:
            label = _normalize_stat_label(str(stat.get("type", "")))
            if not label:
                continue
            value = stat.get("value")
            if value is not None:
                normalized_stats[label] = value
        by_team[team_name] = normalized_stats

    pairs: list[dict[str, Any]] = []
    home_stats = by_team.get(home_team, {})
    away_stats = by_team.get(away_team, {})
    for label in STAT_ORDER:
        if label in home_stats or label in away_stats:
            pairs.append({"label": label, "home": home_stats.get(label, "-"), "away": away_stats.get(label, "-")})

    return by_team, pairs


def enrich_api_football_match(
    match: dict[str, Any],
    events: list[dict[str, Any]] | None = None,
    statistics: list[dict[str, Any]] | None = None,
    lineups: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if events:
        goals, cards = normalize_api_football_events(events)
        match["goals"] = goals
        match["cards"] = cards
        match["has_events"] = bool(goals or cards)

    if statistics:
        normalized_stats, pairs = normalize_api_football_statistics(statistics, match["home_team"], match["away_team"])
        match["statistics"] = normalized_stats
        match["statistics_pairs"] = pairs
        match["has_statistics"] = bool(pairs)

    if lineups:
        match["lineups"] = lineups
        match["has_lineups"] = True

    return match


ELNINE_TEAM_NAME_FIXES = {
    "argentina": "Argentina",
    "australia": "Australia",
    "belgica": "Bélgica",
    "bosnia-herzegovina": "Bosnia-Herzegovina",
    "brasil": "Brasil",
    "canada": "Canadá",
    "corea-del-sur": "Corea del Sur",
    "costa-de-marfil": "Costa de Marfil",
    "croacia": "Croacia",
    "dinamarca": "Dinamarca",
    "ecuador": "Ecuador",
    "egipto": "Egipto",
    "escocia": "Escocia",
    "espana": "España",
    "estados-unidos": "Estados Unidos",
    "francia": "Francia",
    "haiti": "Haití",
    "inglaterra": "Inglaterra",
    "japon": "Japón",
    "marruecos": "Marruecos",
    "mexico": "México",
    "nueva-zelanda": "Nueva Zelanda",
    "paises-bajos": "Países Bajos",
    "paraguay": "Paraguay",
    "qatar": "Qatar",
    "republica-checa": "República Checa",
    "sudafrica": "Sudáfrica",
    "suiza": "Suiza",
    "uruguay": "Uruguay",
}


def _normalize_elnine_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("–", "—")).strip()


def _collapse_repeated_team_name(value: str) -> str:
    text = _normalize_elnine_text(value)
    if not text:
        return ""

    tokens = text.split()
    if len(tokens) >= 2 and len(tokens) % 2 == 0:
        half = len(tokens) // 2
        if tokens[:half] == tokens[half:]:
            return " ".join(tokens[:half])

    return text


def _humanize_elnine_slug(value: str) -> str:
    slug = unquote(value or "").strip("-/").lower()
    fixed = ELNINE_TEAM_NAME_FIXES.get(slug)
    if fixed:
        return fixed
    return " ".join(word.capitalize() for word in slug.replace("-", " ").split())


def _fallback_elnine_teams_from_url(url: str) -> tuple[str, str]:
    path = urlparse(str(url or "")).path
    match = re.search(r"/partido/(?P<teams>.+?)-\d{4}-\d{2}-\d{2}(?:-|$)", path)
    if not match:
        return "Equipo local", "Equipo visitante"

    teams_slug = match.group("teams")
    if "-vs-" not in teams_slug:
        return "Equipo local", "Equipo visitante"

    home_slug, away_slug = teams_slug.split("-vs-", maxsplit=1)
    return _humanize_elnine_slug(home_slug), _humanize_elnine_slug(away_slug)


def _parse_elnine_int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _strip_elnine_events_tail(value: str) -> str:
    # En el listado de ELNINE, después del visitante pueden venir goleadores: "9 ' J. Quiñones".
    return re.split(r"\s+\d{1,3}(?:\+\d+)?\s*['’]", value, maxsplit=1)[0].strip()


def _parse_elnine_match_text(raw_text: str, fallback_home: str, fallback_away: str) -> dict[str, Any]:
    text = _normalize_elnine_text(raw_text)
    body = text
    status = "programado"
    status_raw = "NS"
    time_value = ""

    status_match = re.match(r"^(FIN|FINAL|SUSP|POST|PST|CANC|CAN|ABD|VIVO|LIVE|1T|2T|ET|MT|DESC)\b\s*", body, flags=re.IGNORECASE)
    if status_match:
        prefix = status_match.group(1).upper()
        body = body[status_match.end() :].strip()
        if prefix in {"FIN", "FINAL"}:
            status = "finalizado"
            status_raw = "FT"
        elif prefix in {"SUSP", "POST", "PST"}:
            status = "postergado"
            status_raw = "PST"
        elif prefix in {"CANC", "CAN", "ABD"}:
            status = "cancelado"
            status_raw = "CANC"
        else:
            status = "en vivo"
            status_raw = "LIVE"

    time_match = re.match(r"^(?P<time>\d{1,2}:\d{2})\b\s*", body)
    if time_match:
        time_value = time_match.group("time")
        if len(time_value) == 4:
            time_value = f"0{time_value}"
        body = body[time_match.end() :].strip()

    home_score: int | None = None
    away_score: int | None = None
    home_team = fallback_home
    away_team = fallback_away

    score_match = re.search(r"\s(?P<home_score>\d+)\s*[—-]\s*(?P<away_score>\d+)\s", f" {body} ")
    if score_match:
        # Ajustamos por el espacio agregado al principio.
        start = max(score_match.start() - 1, 0)
        end = max(score_match.end() - 1, 0)
        home_raw = body[:start].strip()
        away_raw = body[end:].strip()
        home_team = _collapse_repeated_team_name(home_raw) or fallback_home
        away_team = _collapse_repeated_team_name(_strip_elnine_events_tail(away_raw)) or fallback_away
        home_score = _parse_elnine_int(score_match.group("home_score"))
        away_score = _parse_elnine_int(score_match.group("away_score"))
        if status == "programado":
            status = "finalizado"
            status_raw = "FT"
    else:
        teams = re.split(r"\s+[—-]\s+", body, maxsplit=1)
        if len(teams) == 2:
            home_team = _collapse_repeated_team_name(teams[0]) or fallback_home
            away_team = _collapse_repeated_team_name(teams[1]) or fallback_away

    return {
        "time_argentina": time_value,
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score,
        "away_score": away_score,
        "status": status,
        "status_raw": status_raw,
    }


def normalize_elnine_match(raw: dict[str, Any], timezone_name: str, index: int = 0) -> dict[str, Any]:
    date_value = str(raw.get("date") or "")
    fallback_home, fallback_away = _fallback_elnine_teams_from_url(str(raw.get("url") or ""))
    parsed = _parse_elnine_match_text(str(raw.get("text") or ""), fallback_home, fallback_away)

    time_value = parsed.get("time_argentina") or "00:00"
    try:
        local_dt = datetime.fromisoformat(f"{date_value}T{time_value}:00").replace(tzinfo=ZoneInfo(timezone_name))
    except ValueError:
        local_dt = None

    match = empty_match()
    match.update(
        {
            "source": "elnine",
            "fixture_id": f"elnine-{index + 1}-{date_value}",
            "kickoff_at": local_dt.isoformat() if local_dt else "",
            "date": date_value,
            "time_argentina": parsed.get("time_argentina") or "",
            "home_team": parsed.get("home_team") or fallback_home,
            "away_team": parsed.get("away_team") or fallback_away,
            "home_score": parsed.get("home_score"),
            "away_score": parsed.get("away_score"),
            "status": parsed.get("status") or "programado",
            "status_raw": parsed.get("status_raw") or "NS",
            "round": "",
            "group": "",
            "venue": "",
            "city": "",
        }
    )
    return match


def normalize_elnine_matches(raw_matches: list[dict[str, Any]], timezone_name: str) -> list[dict[str, Any]]:
    return [normalize_elnine_match(item, timezone_name, index=i) for i, item in enumerate(raw_matches)]


def _score_from_openfootball(raw: dict[str, Any]) -> tuple[int | None, int | None]:
    for left_key, right_key in [("score1", "score2"), ("goals1", "goals2")]:
        if left_key in raw and right_key in raw:
            return raw.get(left_key), raw.get(right_key)

    score = raw.get("score") or raw.get("result")
    if isinstance(score, list) and len(score) >= 2:
        return score[0], score[1]
    if isinstance(score, dict):
        return score.get("team1"), score.get("team2")
    return None, None


def normalize_openfootball_match(raw: dict[str, Any], timezone_name: str, index: int = 0) -> dict[str, Any]:
    local_dt = parse_openfootball_datetime(str(raw.get("date", "")), str(raw.get("time", "")), timezone_name)
    home_score, away_score = _score_from_openfootball(raw)

    match = empty_match()
    match.update(
        {
            "source": "openfootball",
            "fixture_id": f"openfootball-{raw.get('num', index)}",
            "kickoff_at": local_dt.isoformat(),
            "date": local_dt.date().isoformat(),
            "time_argentina": local_dt.strftime("%H:%M"),
            "home_team": raw.get("team1") or raw.get("home_team") or "Equipo local",
            "away_team": raw.get("team2") or raw.get("away_team") or "Equipo visitante",
            "home_score": home_score,
            "away_score": away_score,
            "status": "finalizado" if home_score is not None and away_score is not None else "programado",
            "status_raw": "FT" if home_score is not None and away_score is not None else "NS",
            "round": raw.get("round") or "",
            "group": raw.get("group") or "",
            "venue": raw.get("stadium") or raw.get("ground") or "",
            "city": raw.get("city") or raw.get("ground") or "",
        }
    )
    return match


def normalize_openfootball_matches(raw_matches: list[dict[str, Any]], timezone_name: str) -> list[dict[str, Any]]:
    return [normalize_openfootball_match(item, timezone_name, index=i + 1) for i, item in enumerate(raw_matches)]


def _match_kickoff(match: dict[str, Any], fallback_tzinfo: Any = None) -> datetime | None:
    kickoff_at = match.get("kickoff_at")
    if kickoff_at:
        try:
            parsed = datetime.fromisoformat(str(kickoff_at))
            if parsed.tzinfo is None and fallback_tzinfo is not None:
                parsed = parsed.replace(tzinfo=fallback_tzinfo)
            return parsed
        except ValueError:
            return None

    date_value = match.get("date")
    time_value = match.get("time_argentina")
    if not date_value or not time_value:
        return None

    try:
        parsed = datetime.fromisoformat(f"{date_value}T{time_value}:00")
        if fallback_tzinfo is not None:
            parsed = parsed.replace(tzinfo=fallback_tzinfo)
        return parsed
    except ValueError:
        return None


def filter_matches_by_window(matches: list[dict[str, Any]], start: datetime, end: datetime) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for match in matches:
        kickoff = _match_kickoff(match, fallback_tzinfo=start.tzinfo)
        if kickoff is None:
            continue
        if start <= kickoff < end:
            filtered.append(match)
    return filtered


def filter_matches_by_date(matches: list[dict[str, Any]], target_date: date) -> list[dict[str, Any]]:
    return [match for match in matches if match.get("date") == target_date.isoformat()]
