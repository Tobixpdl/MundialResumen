from __future__ import annotations

import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests

from .cache import JsonCache
from .date_utils import iso_date


class APIFootballError(RuntimeError):
    pass


class APIFootballClient:
    BASE_URL = "https://v3.football.api-sports.io"
    WORLD_CUP_LEAGUE_ID = 1
    WORLD_CUP_SEASON = 2026

    def __init__(
        self,
        api_key: str,
        cache_dir: Path | str = ".cache",
        timeout_seconds: int = 20,
        min_request_interval_seconds: float = 0.25,
    ) -> None:
        if not api_key:
            raise APIFootballError("API_FOOTBALL_KEY no está configurada.")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.min_request_interval_seconds = min_request_interval_seconds
        self.cache = JsonCache(cache_dir)
        self._last_request_at = 0.0

    @property
    def headers(self) -> dict[str, str]:
        return {"x-apisports-key": self.api_key}

    def _cache_key(self, endpoint: str, params: dict[str, Any]) -> str:
        clean_params = "&".join(f"{key}={params[key]}" for key in sorted(params))
        return f"api-football:{endpoint}?{clean_params}"

    def _respect_rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_at
        remaining = self.min_request_interval_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _get(self, endpoint: str, params: dict[str, Any], ttl_seconds: int) -> list[dict[str, Any]]:
        key = self._cache_key(endpoint, params)
        cached = self.cache.get(key, ttl_seconds)
        if cached is not None:
            return cached

        self._respect_rate_limit()
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=self.timeout_seconds)
            self._last_request_at = time.time()
        except requests.RequestException as exc:
            stale = self.cache.get_stale(key)
            if stale is not None:
                return stale
            raise APIFootballError(f"No se pudo consultar API-FOOTBALL: {exc}") from exc

        if response.status_code == 429:
            stale = self.cache.get_stale(key)
            if stale is not None:
                return stale
            raise APIFootballError("Se superó el límite diario o de rate limit de API-FOOTBALL.")

        if response.status_code in {401, 403}:
            raise APIFootballError("Token inválido o sin permisos en API-FOOTBALL.")

        if not response.ok:
            stale = self.cache.get_stale(key)
            if stale is not None:
                return stale
            raise APIFootballError(f"API-FOOTBALL respondió HTTP {response.status_code}: {response.text[:300]}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise APIFootballError("API-FOOTBALL devolvió una respuesta que no es JSON válido.") from exc

        errors = payload.get("errors")
        if errors:
            stale = self.cache.get_stale(key)
            if stale is not None:
                return stale
            raise APIFootballError(f"API-FOOTBALL devolvió errores: {errors}")

        data = payload.get("response", [])
        self.cache.set(key, data)
        return data

    def _fixture_ttl_for_date(self, target_date: date) -> int:
        today = datetime.now().date()
        if target_date == today:
            return 15 * 60
        if target_date < today:
            return 24 * 60 * 60
        return 6 * 60 * 60

    def get_worldcup_fixtures(self) -> list[dict[str, Any]]:
        return self._get(
            "fixtures",
            {"league": self.WORLD_CUP_LEAGUE_ID, "season": self.WORLD_CUP_SEASON},
            ttl_seconds=6 * 60 * 60,
        )

    def get_fixtures_by_date(self, target_date: date, timezone_name: str = "America/Argentina/Buenos_Aires") -> list[dict[str, Any]]:
        return self._get(
            "fixtures",
            {
                "league": self.WORLD_CUP_LEAGUE_ID,
                "season": self.WORLD_CUP_SEASON,
                "date": iso_date(target_date),
                "timezone": timezone_name,
            },
            ttl_seconds=self._fixture_ttl_for_date(target_date),
        )

    def get_fixture_by_id(self, fixture_id: int | str) -> list[dict[str, Any]]:
        return self._get("fixtures", {"id": fixture_id}, ttl_seconds=15 * 60)

    def get_fixture_events(self, fixture_id: int | str) -> list[dict[str, Any]]:
        return self._get("fixtures/events", {"fixture": fixture_id}, ttl_seconds=24 * 60 * 60)

    def get_fixture_statistics(self, fixture_id: int | str) -> list[dict[str, Any]]:
        return self._get("fixtures/statistics", {"fixture": fixture_id}, ttl_seconds=24 * 60 * 60)

    def get_fixture_lineups(self, fixture_id: int | str) -> list[dict[str, Any]]:
        return self._get("fixtures/lineups", {"fixture": fixture_id}, ttl_seconds=24 * 60 * 60)

    def get_standings(self) -> list[dict[str, Any]]:
        return self._get(
            "standings",
            {"league": self.WORLD_CUP_LEAGUE_ID, "season": self.WORLD_CUP_SEASON},
            ttl_seconds=6 * 60 * 60,
        )

    def get_top_scorers(self) -> list[dict[str, Any]]:
        return self._get(
            "players/topscorers",
            {"league": self.WORLD_CUP_LEAGUE_ID, "season": self.WORLD_CUP_SEASON},
            ttl_seconds=6 * 60 * 60,
        )
