from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import requests

from .cache import JsonCache
from .date_utils import parse_openfootball_datetime


class OpenFootballError(RuntimeError):
    pass


class OpenFootballClient:
    DEFAULT_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"

    def __init__(self, cache_dir: Path | str = ".cache", timeout_seconds: int = 20, source_url: str | None = None) -> None:
        self.cache = JsonCache(cache_dir)
        self.timeout_seconds = timeout_seconds
        self.source_url = source_url or self.DEFAULT_URL

    def get_worldcup_data(self) -> dict[str, Any]:
        cache_key = "openfootball:worldcup-2026-json"
        cached = self.cache.get(cache_key, max_age_seconds=6 * 60 * 60)
        if cached is not None:
            return cached

        try:
            response = requests.get(self.source_url, timeout=self.timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            stale = self.cache.get_stale(cache_key)
            if stale is not None:
                return stale
            raise OpenFootballError(f"No se pudo descargar OpenFootball: {exc}") from exc
        except ValueError as exc:
            raise OpenFootballError("OpenFootball devolvió JSON inválido.") from exc

        self.cache.set(cache_key, payload)
        return payload

    def get_matches(self) -> list[dict[str, Any]]:
        payload = self.get_worldcup_data()
        matches = payload.get("matches", [])
        if not isinstance(matches, list):
            raise OpenFootballError("El JSON de OpenFootball no tiene una lista válida en 'matches'.")
        return matches

    def get_matches_by_argentina_date(self, target_date: date, timezone_name: str) -> list[dict[str, Any]]:
        filtered: list[dict[str, Any]] = []
        for match in self.get_matches():
            local_dt = parse_openfootball_datetime(str(match.get("date", "")), str(match.get("time", "")), timezone_name)
            if local_dt.date() == target_date:
                filtered.append(match)
        return filtered
