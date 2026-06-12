from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests

from .cache import JsonCache


class ElNineError(RuntimeError):
    pass


@dataclass(frozen=True)
class AnchorItem:
    href: str
    text: str


class _AnchorCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[AnchorItem] = []
        self._href_stack: list[str | None] = []
        self._current_href: str | None = None
        self._current_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = None
        for key, value in attrs:
            if key.lower() == "href" and value:
                href = value
                break
        self._href_stack.append(self._current_href)
        self._current_href = href
        self._current_chunks = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._current_href is None:
            return
        text = _normalize_space(" ".join(self._current_chunks))
        self.anchors.append(AnchorItem(href=self._current_href, text=text))
        self._current_href = self._href_stack.pop() if self._href_stack else None
        self._current_chunks = []


def _normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", unescape(str(value or ""))).strip()


def _looks_like_worldcup_header(text: str) -> bool:
    normalized = _normalize_space(text).lower()
    if "ver" not in normalized:
        return False
    return "fifa mundial" in normalized or "copa mundial" in normalized


def _looks_like_competition_header(text: str) -> bool:
    normalized = _normalize_space(text)
    return bool(re.search(r"\bVer\s+\d+\b", normalized, flags=re.IGNORECASE))


class ElNineClient:
    BASE_URL = "https://elnine.com.ar/"

    def __init__(self, cache_dir: Path | str = ".cache", timeout_seconds: int = 20) -> None:
        self.cache = JsonCache(cache_dir)
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

    def _url_for_date(self, target_date: date) -> str:
        return f"{self.BASE_URL}?d={target_date.isoformat()}"

    def _ttl_for_date(self, target_date: date) -> int:
        today = datetime.now().date()
        if target_date == today:
            return 5 * 60
        if target_date < today:
            return 24 * 60 * 60
        return 30 * 60

    def _get_html(self, target_date: date) -> str:
        url = self._url_for_date(target_date)
        cache_key = f"elnine:matches-html:{target_date.isoformat()}"
        cached = self.cache.get(cache_key, self._ttl_for_date(target_date))
        if cached is not None:
            return str(cached)

        try:
            response = self.session.get(url, timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            stale = self.cache.get_stale(cache_key)
            if stale is not None:
                return str(stale)
            raise ElNineError(f"No se pudo consultar ELNINE para {target_date.isoformat()}: {exc}") from exc

        if not response.ok:
            stale = self.cache.get_stale(cache_key)
            if stale is not None:
                return str(stale)
            raise ElNineError(f"ELNINE respondió HTTP {response.status_code}: {response.text[:300]}")

        html = response.text
        self.cache.set(cache_key, html)
        return html

    def _collect_anchors(self, html: str) -> list[AnchorItem]:
        parser = _AnchorCollector()
        parser.feed(html)
        return [AnchorItem(href=urljoin(self.BASE_URL, item.href), text=item.text) for item in parser.anchors]

    def _extract_worldcup_match_anchors(self, html: str, target_date: date) -> list[AnchorItem]:
        anchors = self._collect_anchors(html)
        header_indexes = [index for index, item in enumerate(anchors) if _looks_like_worldcup_header(item.text)]

        for header_index in reversed(header_indexes):
            selected: list[AnchorItem] = []
            for item in anchors[header_index + 1 :]:
                if "/partido/" in item.href:
                    selected.append(item)
                    continue
                if selected and _looks_like_competition_header(item.text):
                    break
            if selected:
                return selected

        # Fallback defensivo: si cambia el header, al menos tomamos los partidos de esa fecha.
        date_text = target_date.isoformat()
        return [item for item in anchors if "/partido/" in item.href and date_text in item.href]

    def get_matches_by_date(self, target_date: date) -> list[dict[str, Any]]:
        html = self._get_html(target_date)
        anchors = self._extract_worldcup_match_anchors(html, target_date)

        raw_matches: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in anchors:
            text = _normalize_space(item.text)
            if not text or item.href in seen:
                continue
            seen.add(item.href)
            raw_matches.append(
                {
                    "source": "elnine",
                    "date": target_date.isoformat(),
                    "text": text,
                    "url": item.href,
                }
            )

        return raw_matches
