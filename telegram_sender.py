from __future__ import annotations

from typing import Iterable

import requests

from .config import Config


class TelegramConfigError(RuntimeError):
    pass


class TelegramSendError(RuntimeError):
    pass


TELEGRAM_MAX_MESSAGE_LENGTH = 4096


def validate_telegram_config(config: Config) -> None:
    missing = []
    if not config.telegram_token:
        missing.append("TELEGRAM_TOKEN")
    if not config.telegram_chat_id:
        missing.append("TELEGRAM_CHAT_ID")
    if missing:
        raise TelegramConfigError(f"Faltan variables de Telegram obligatorias: {', '.join(missing)}")


def _split_message(text: str, max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> Iterable[str]:
    """Split long Telegram messages without cutting words/lines when possible."""
    if len(text) <= max_length:
        yield text
        return

    current = ""
    for line in text.splitlines(keepends=True):
        if len(line) > max_length:
            if current:
                yield current.rstrip()
                current = ""
            for index in range(0, len(line), max_length):
                yield line[index : index + max_length].rstrip()
            continue

        if len(current) + len(line) > max_length:
            yield current.rstrip()
            current = line
        else:
            current += line

    if current:
        yield current.rstrip()


def send_telegram_message(config: Config, text: str) -> None:
    validate_telegram_config(config)

    url = f"https://api.telegram.org/bot{config.telegram_token}/sendMessage"

    for chunk in _split_message(text):
        try:
            response = requests.post(
                url,
                json={
                    "chat_id": config.telegram_chat_id,
                    "text": chunk,
                    "disable_web_page_preview": True,
                },
                timeout=20,
            )
        except requests.RequestException as exc:
            raise TelegramSendError(f"No se pudo enviar el mensaje por Telegram: {exc}") from exc

        if not response.ok:
            raise TelegramSendError(
                f"Telegram respondió HTTP {response.status_code}: {response.text[:300]}"
            )
