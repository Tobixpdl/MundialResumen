from pathlib import Path

from src.formatter import format_score, render_daily_email

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"


def base_context(**overrides):
    context = {
        "report_date": "08/06/2026",
        "today_iso": "2026-06-08",
        "source_label": "test",
        "fallback_reason": "",
        "yesterday_matches": [],
        "today_matches": [],
        "upcoming_matches": [],
    }
    context.update(overrides)
    return context


def test_format_score_with_score():
    match = {"home_team": "Argentina", "away_team": "Francia", "home_score": 2, "away_score": 1}

    assert format_score(match) == "Argentina 2 - 1 Francia"


def test_format_score_without_score():
    match = {"home_team": "Argentina", "away_team": "México", "home_score": None, "away_score": None}

    assert format_score(match) == "Argentina vs México"


def test_render_when_no_matches():
    html = render_daily_email(base_context(), TEMPLATE_DIR)

    assert "No hay partidos registrados para ayer" in html
    assert "No hay partidos programados para hoy" in html
    assert "No hay próximos partidos" in html


def test_render_when_matches_exist():
    html = render_daily_email(
        base_context(
            today_matches=[
                {
                    "home_team": "Argentina",
                    "away_team": "México",
                    "home_score": None,
                    "away_score": None,
                    "date": "2026-06-08",
                    "time_argentina": "16:00",
                    "venue": "MetLife Stadium",
                    "city": "East Rutherford",
                    "round": "Group Stage",
                    "group": "Group A",
                    "status": "programado",
                }
            ]
        ),
        TEMPLATE_DIR,
    )

    assert "Argentina vs México" in html
    assert "MetLife Stadium" in html
    assert "Estado: Programado" in html
