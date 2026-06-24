from __future__ import annotations

import os
import smtplib
import ssl
import sys
from email.message import EmailMessage

import httpx

from .. import config
from ..models import Event, severity_at_least


def _post(url: str, payload: dict) -> None:
    httpx.post(url, json=payload, timeout=config.HTTP_TIMEOUT_S).raise_for_status()


def _send_webhook(event: Event, title: str, body: str) -> None:
    url = os.environ.get("FANOUT_WEBHOOK_URL")
    if url:
        _post(
            url,
            {
                "type": event.type,
                "severity": event.severity,
                "key": event.key,
                "title": title,
                "body": body,
            },
        )


def _send_slack(event: Event, title: str, body: str) -> None:
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if url:
        _post(url, {"text": f"`[{event.severity}]` *{title}*\n{body}"})


def _send_discord(event: Event, title: str, body: str) -> None:
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if url:
        _post(url, {"content": f"**[{event.severity}] {title}**\n{body}"[:1900]})


def _send_email(event: Event, title: str, body: str) -> None:
    host = os.environ.get("SMTP_HOST")
    recipient = os.environ.get("SMTP_TO")
    if not host or not recipient:
        return
    message = EmailMessage()
    message["Subject"] = f"[{event.severity}] {title}"
    message["From"] = os.environ.get("SMTP_FROM", "nasa-defense@localhost")
    message["To"] = recipient
    message.set_content(body)
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587"))) as server:
        server.starttls(context=ssl.create_default_context())
        if user and password:
            server.login(user, password)
        server.send_message(message)


_CHANNELS = (_send_webhook, _send_slack, _send_discord, _send_email)


def fan_out(event: Event, title: str, body: str) -> None:
    """Best-effort outbound notification to every configured channel. Each channel
    is a no-op unless its secret is set; failures are logged, never raised — Issues
    remain the at-least-once system of record."""
    if not severity_at_least(event.severity, config.FANOUT_MIN_SEVERITY):
        return
    for channel in _CHANNELS:
        try:
            channel(event, title, body)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"fan-out {channel.__name__} failed: {exc}", file=sys.stderr)
