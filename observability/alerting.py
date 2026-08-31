"""Alert dispatch on top of the control tables (06-observability.md). The
control tables already answer "what happened"; this module is the piece
that used to be missing: getting a human's attention when a run fails,
instead of that only being visible if someone happens to query
PIPELINE_RUNS or check the Airflow UI.

Two channels, both optional and independently configured via env vars
(.env.example): a Slack incoming webhook and SMTP email. Neither adds a new
service to operate: a Slack webhook URL and an existing mail relay are
both things a small team already has, not new infrastructure. Configuring
neither is a valid, supported state (dev/CI): send_alert then just logs the
alert and returns, so nothing here can make a pipeline run fail because
alerting itself failed.

Deliberately stdlib-only (urllib, smtplib): alerting is a side channel that
fires exactly when something has already gone wrong, which is the worst
moment to also depend on a third-party HTTP client behaving correctly.
"""
from __future__ import annotations

import json
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage

from observability.config import AlertingSettings
from observability.logging_utils import get_logger, log_event

logger = get_logger(__name__)


def send_alert(*, subject: str, message: str, severity: str = "critical", context: dict | None = None) -> None:
    """Best-effort: every failure here is caught and logged, never raised.
    Called from places that are already handling a failure (DAG
    on_failure_callback, an AI quality-check breach); an alerting outage
    must never turn into a second, unrelated pipeline failure."""
    settings = AlertingSettings()
    context = context or {}
    log_event(logger, "alert_dispatched", severity=severity, subject=subject, **context)

    if not settings.configured:
        log_event(logger, "alert_skipped_not_configured", subject=subject)
        return

    if settings.alert_slack_webhook_url:
        _send_slack(settings.alert_slack_webhook_url, subject, message, severity, context)

    if settings.alert_email_to and settings.alert_smtp_host:
        _send_email(settings, subject, message, context)


def _send_slack(webhook_url: str, subject: str, message: str, severity: str, context: dict) -> None:
    detail = "\n".join(f"- *{key}*: {value}" for key, value in context.items())
    text = f"*[{severity.upper()}] {subject}*\n{message}" + (f"\n{detail}" if detail else "")
    payload = json.dumps({"text": text}).encode("utf-8")
    request = urllib.request.Request(
        webhook_url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=10):  # noqa: S310 - webhook_url is operator-configured, not user input
            pass
    except (urllib.error.URLError, OSError) as exc:
        log_event(logger, "alert_slack_send_failed", level=30, error=str(exc))


def _send_email(settings: AlertingSettings, subject: str, message: str, context: dict) -> None:
    detail = "\n".join(f"{key}: {value}" for key, value in context.items())
    body = f"{message}\n\n{detail}" if detail else message

    email = EmailMessage()
    email["Subject"] = f"[delivery-pipeline] {subject}"
    email["From"] = settings.alert_email_from or "delivery-pipeline@localhost"
    email["To"] = settings.alert_email_to
    email.set_content(body)

    try:
        with smtplib.SMTP(settings.alert_smtp_host, settings.alert_smtp_port, timeout=10) as smtp:
            if settings.alert_smtp_user and settings.alert_smtp_password:
                smtp.starttls()
                smtp.login(settings.alert_smtp_user, settings.alert_smtp_password)
            smtp.send_message(email)
    except (OSError, smtplib.SMTPException) as exc:
        log_event(logger, "alert_email_send_failed", level=30, error=str(exc))


__all__ = ["send_alert"]
