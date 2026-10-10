"""EmailSender interface. Nothing is sent from an agent tool; only the owner send path uses this."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger("inventory.email")

CONSOLE_BANNER = "Console email mode is on. Drafts are logged and are never delivered."


class EmailSendError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class EmailSender(Protocol):
    mode: str

    def send(self, *, to_email: str, subject: str, body: str) -> None:
        ...


class ConsoleEmailSender:
    mode = "console"

    def send(self, *, to_email: str, subject: str, body: str) -> None:
        logger.info(
            "CONSOLE EMAIL (not delivered) to=%s subject=%s\n%s",
            to_email,
            subject,
            body,
        )


class SmtpEmailSender:
    mode = "smtp"

    def send(self, *, to_email: str, subject: str, body: str) -> None:
        if not settings.email_from or not settings.email_smtp_host:
            raise EmailSendError("SMTP is not configured.")
        message = EmailMessage()
        message["From"] = settings.email_from
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)
        try:
            with smtplib.SMTP(settings.email_smtp_host, settings.email_smtp_port, timeout=20) as client:
                if settings.email_smtp_tls:
                    client.starttls()
                if settings.email_smtp_user:
                    client.login(settings.email_smtp_user, settings.email_smtp_password or "")
                client.send_message(message)
        except OSError as exc:
            raise EmailSendError(f"SMTP send failed: {exc}") from exc


def get_email_sender() -> EmailSender:
    if settings.email_sender == "smtp":
        return SmtpEmailSender()
    return ConsoleEmailSender()


def sender_status() -> dict[str, object]:
    mode = "smtp" if settings.email_sender == "smtp" else "console"
    return {
        "mode": mode,
        "console_mode": mode == "console",
        "banner": CONSOLE_BANNER if mode == "console" else None,
    }
