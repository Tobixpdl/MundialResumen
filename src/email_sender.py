from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import Config


class EmailConfigError(RuntimeError):
    pass


def validate_email_config(config: Config) -> None:
    missing = []
    for field in ["smtp_host", "smtp_user", "smtp_password", "email_from", "email_to"]:
        if not getattr(config, field):
            missing.append(field.upper())
    if missing:
        raise EmailConfigError(f"Faltan variables SMTP obligatorias: {', '.join(missing)}")


def send_email(config: Config, subject: str, html_body: str) -> None:
    validate_email_config(config)

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.email_from
    message["To"] = config.email_to
    message.set_content("Tu cliente de email no muestra HTML. Abrí este mensaje en Gmail o un cliente compatible.")
    message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(config.smtp_host, config.smtp_port) as smtp:
        smtp.starttls()
        smtp.login(config.smtp_user, config.smtp_password)
        smtp.send_message(message)
