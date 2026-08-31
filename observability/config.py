"""Alerting configuration. A separate settings class (not folded into
ingestion.config.IngestionSettings or ai.common.config.AISettings) since
alerting is called from both sides (an ingestion/DAG-level failure and an
AI quality-check breach) and neither of those settings classes should
depend on the other. See observability/alerting.py."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class AlertingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    alert_slack_webhook_url: str = ""

    alert_email_to: str = ""
    alert_email_from: str = ""
    alert_smtp_host: str = ""
    alert_smtp_port: int = 587
    alert_smtp_user: str = ""
    alert_smtp_password: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.alert_slack_webhook_url or (self.alert_email_to and self.alert_smtp_host))
