"""Unit tests for the text-to-SQL AST-based guardrails. See
docs/architecture/04-ai-architecture.md#c-natural-language-analytics--text-to-sql-aitext_to_sql
and ADR-006. These are the guardrails.py-level checks (defense layer one);
the real enforcement is the AI_READONLY_ROLE grant (defense layer two,
snowflake/01_roles_and_grants.sql, not something a unit test can exercise
without a live warehouse)."""
from __future__ import annotations

import pytest

from ai.text_to_sql.guardrails import GuardrailViolation, validate_and_prepare

ALLOWED = {"SEMANTIC.SEM_REVENUE_DAILY", "SEMANTIC.SEM_ORDERS"}


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT city, SUM(gross_merchandise_value) FROM sem_revenue_daily GROUP BY city",
        "SELECT * FROM sem_revenue_daily LIMIT 5",
        "SELECT * FROM semantic.sem_orders",
        "WITH x AS (SELECT * FROM sem_orders) SELECT * FROM x",
        "select 1 as n union select 2",
    ],
)
def test_valid_queries_pass(sql):
    result = validate_and_prepare(sql, ALLOWED, "SEMANTIC", row_limit=200)
    assert "LIMIT" in result.sql.upper()


@pytest.mark.parametrize(
    "sql,expected_reason_fragment",
    [
        ("SELECT * FROM sem_revenue_daily; DROP TABLE sem_revenue_daily;", "exactly one SQL statement"),
        ("SELECT * FROM raw.orders", "not allowed"),
        ("DELETE FROM sem_orders", "Only SELECT/WITH statements"),
        ("UPDATE sem_orders SET sales_amount = 0", "Only SELECT/WITH statements"),
        ("DROP TABLE sem_orders", "Only SELECT/WITH statements"),
        ("SELECT * FROM sem_restaurant_performance", "not on the allowlist"),  # not in ALLOWED for this test
    ],
)
def test_invalid_queries_rejected_with_clear_reason(sql, expected_reason_fragment):
    with pytest.raises(GuardrailViolation) as exc_info:
        validate_and_prepare(sql, ALLOWED, "SEMANTIC", row_limit=200)
    assert expected_reason_fragment.lower() in str(exc_info.value).lower()


def test_row_limit_is_injected_when_missing():
    result = validate_and_prepare("SELECT * FROM sem_orders", ALLOWED, "SEMANTIC", row_limit=50)
    assert "LIMIT 50" in result.sql.upper()


def test_row_limit_is_clamped_when_too_high():
    result = validate_and_prepare("SELECT * FROM sem_orders LIMIT 999999", ALLOWED, "SEMANTIC", row_limit=50)
    assert "LIMIT 50" in result.sql.upper()
    assert "999999" not in result.sql


def test_row_limit_below_cap_is_preserved():
    result = validate_and_prepare("SELECT * FROM sem_orders LIMIT 10", ALLOWED, "SEMANTIC", row_limit=200)
    assert "LIMIT 10" in result.sql.upper()


def test_cte_alias_is_not_mistaken_for_a_real_table():
    # `x` here is a CTE alias, not a table, and must not be checked against the allowlist.
    result = validate_and_prepare(
        "WITH x AS (SELECT * FROM sem_orders) SELECT * FROM x", ALLOWED, "SEMANTIC", row_limit=200
    )
    assert result.sql  # did not raise


def test_unparseable_sql_is_rejected_not_silently_passed():
    with pytest.raises(GuardrailViolation):
        validate_and_prepare("this is not sql at all $$$ ---", ALLOWED, "SEMANTIC", row_limit=200)
