from src.normalizer import enrich_api_football_match, normalize_api_football_fixture, normalize_openfootball_match


def test_normalize_api_football_fixture():
    raw = {
        "fixture": {
            "id": 123,
            "date": "2026-06-11T19:00:00+00:00",
            "venue": {"name": "Estadio Azteca", "city": "Mexico City"},
            "status": {"short": "NS", "long": "Not Started"},
        },
        "league": {"round": "Group Stage - 1"},
        "teams": {"home": {"name": "Mexico"}, "away": {"name": "South Africa"}},
        "goals": {"home": None, "away": None},
    }

    match = normalize_api_football_fixture(raw, "America/Argentina/Buenos_Aires")

    assert match["source"] == "api-football"
    assert match["fixture_id"] == 123
    assert match["date"] == "2026-06-11"
    assert match["time_argentina"] == "16:00"
    assert match["home_team"] == "Mexico"
    assert match["away_team"] == "South Africa"
    assert match["status"] == "programado"


def test_enrich_api_football_match_with_events_and_statistics():
    match = {
        "home_team": "Argentina",
        "away_team": "Francia",
        "goals": [],
        "cards": [],
        "has_events": False,
        "statistics": {},
        "statistics_pairs": [],
        "has_statistics": False,
    }
    events = [
        {
            "time": {"elapsed": 23, "extra": None},
            "team": {"name": "Argentina"},
            "player": {"name": "Messi"},
            "type": "Goal",
            "detail": "Normal Goal",
        }
    ]
    statistics = [
        {"team": {"name": "Argentina"}, "statistics": [{"type": "Ball Possession", "value": "54%"}]},
        {"team": {"name": "Francia"}, "statistics": [{"type": "Ball Possession", "value": "46%"}]},
    ]

    enriched = enrich_api_football_match(match, events=events, statistics=statistics)

    assert enriched["has_events"] is True
    assert enriched["goals"][0]["player"] == "Messi"
    assert enriched["has_statistics"] is True
    assert enriched["statistics_pairs"][0] == {"label": "Posesión", "home": "54%", "away": "46%"}


def test_normalize_openfootball_match():
    raw = {
        "round": "Matchday 1",
        "date": "2026-06-11",
        "time": "13:00 UTC-6",
        "team1": "Mexico",
        "team2": "South Africa",
        "group": "Group A",
        "ground": "Mexico City",
    }

    match = normalize_openfootball_match(raw, "America/Argentina/Buenos_Aires", index=1)

    assert match["source"] == "openfootball"
    assert match["date"] == "2026-06-11"
    assert match["time_argentina"] == "16:00"
    assert match["home_team"] == "Mexico"
    assert match["away_team"] == "South Africa"
    assert match["has_statistics"] is False
