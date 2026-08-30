"""Unit tests for ai/metrics_api/app.py. Snowflake is mocked throughout;
these test the API's own logic (metric lookup, allowlist check, row
shaping), not connectivity. See docs/architecture/04-ai-architecture.md#e-metrics-api-aimetrics_api."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from ai.metrics_api.app import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_metrics_includes_known_metric():
    response = client.get("/metrics")
    assert response.status_code == 200
    names = {m["name"] for m in response.json()}
    assert "gross_merchandise_value" in names


def test_unknown_metric_returns_404():
    response = client.get("/metrics/not_a_real_metric")
    assert response.status_code == 404


def _set_ai_settings_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "test-account")
    monkeypatch.setenv("SNOWFLAKE_DATABASE", "DELIVERY_TEST")


def test_get_metric_returns_rows_from_its_semantic_view(monkeypatch):
    _set_ai_settings_env(monkeypatch)
    mock_connection = MagicMock()
    mock_cursor = mock_connection.cursor.return_value
    mock_cursor.description = [("ORDER_DATE",), ("CITY",), ("GROSS_MERCHANDISE_VALUE",)]
    mock_cursor.fetchall.return_value = [("2026-01-01", "Auckland", 1234.5)]

    with patch("ai.metrics_api.app.get_ai_readonly_connection", return_value=mock_connection):
        response = client.get("/metrics/gross_merchandise_value")

    assert response.status_code == 200
    body = response.json()
    assert body["semantic_view"] == "SEMANTIC.SEM_REVENUE_DAILY"
    assert body["rows"] == [{"order_date": "2026-01-01", "city": "Auckland", "gross_merchandise_value": 1234.5}]

    executed_sql = mock_cursor.execute.call_args[0][0]
    assert "SEMANTIC.SEM_REVENUE_DAILY" in executed_sql
    mock_connection.close.assert_called_once()


def test_get_metric_by_alias(monkeypatch):
    _set_ai_settings_env(monkeypatch)
    mock_connection = MagicMock()
    mock_cursor = mock_connection.cursor.return_value
    mock_cursor.description = [("ORDER_DATE",)]
    mock_cursor.fetchall.return_value = []

    with patch("ai.metrics_api.app.get_ai_readonly_connection", return_value=mock_connection):
        response = client.get("/metrics/gmv")

    assert response.status_code == 200
    assert response.json()["metric"] == "gross_merchandise_value"


def test_limit_is_clamped_to_configured_row_limit(monkeypatch):
    _set_ai_settings_env(monkeypatch)
    mock_connection = MagicMock()
    mock_cursor = mock_connection.cursor.return_value
    mock_cursor.description = [("ORDER_DATE",)]
    mock_cursor.fetchall.return_value = []

    with patch("ai.metrics_api.app.get_ai_readonly_connection", return_value=mock_connection):
        response = client.get("/metrics/gross_merchandise_value?limit=999999")

    assert response.status_code == 200
    executed_sql = mock_cursor.execute.call_args[0][0]
    assert "LIMIT 200" in executed_sql  # default text_to_sql_row_limit
