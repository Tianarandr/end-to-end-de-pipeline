"""Unit tests for observability/alerting.py. See
docs/architecture/06-observability.md#alerting."""
from __future__ import annotations

from unittest.mock import patch

from observability.alerting import send_alert
from observability.config import AlertingSettings


def _clear_env(monkeypatch):
    for var in (
        "ALERT_SLACK_WEBHOOK_URL", "ALERT_EMAIL_TO", "ALERT_EMAIL_FROM",
        "ALERT_SMTP_HOST", "ALERT_SMTP_PORT", "ALERT_SMTP_USER", "ALERT_SMTP_PASSWORD",
    ):
        monkeypatch.delenv(var, raising=False)


def test_not_configured_is_a_no_op(monkeypatch):
    _clear_env(monkeypatch)
    with patch("urllib.request.urlopen") as mock_urlopen, patch("smtplib.SMTP") as mock_smtp:
        send_alert(subject="run failed", message="detail")
    mock_urlopen.assert_not_called()
    mock_smtp.assert_not_called()


def test_configured_state_reflects_either_channel(monkeypatch):
    _clear_env(monkeypatch)
    assert AlertingSettings().configured is False

    monkeypatch.setenv("ALERT_SLACK_WEBHOOK_URL", "https://hooks.slack.example/T000/B000/xxx")
    assert AlertingSettings().configured is True


def test_slack_webhook_called_when_configured(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("ALERT_SLACK_WEBHOOK_URL", "https://hooks.slack.example/T000/B000/xxx")

    with patch("urllib.request.urlopen") as mock_urlopen:
        send_alert(subject="run failed", message="detail", context={"dag_run_id": "abc123"})

    assert mock_urlopen.called
    request = mock_urlopen.call_args[0][0]
    assert request.full_url == "https://hooks.slack.example/T000/B000/xxx"
    assert b"run failed" in request.data


def test_slack_send_failure_does_not_raise(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("ALERT_SLACK_WEBHOOK_URL", "https://hooks.slack.example/T000/B000/xxx")

    with patch("urllib.request.urlopen", side_effect=OSError("network down")):
        send_alert(subject="run failed", message="detail")  # must not raise


def test_email_sent_when_configured(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("ALERT_EMAIL_TO", "oncall@example.com")
    monkeypatch.setenv("ALERT_SMTP_HOST", "smtp.example.com")

    with patch("smtplib.SMTP") as mock_smtp:
        send_alert(subject="run failed", message="detail")

    mock_smtp.assert_called_once()
    instance = mock_smtp.return_value.__enter__.return_value
    instance.send_message.assert_called_once()
