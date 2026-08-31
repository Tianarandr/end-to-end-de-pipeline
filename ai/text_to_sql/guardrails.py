"""Static SQL validation, run before anything ever reaches Snowflake. See
docs/architecture/04-ai-architecture.md#c-natural-language-analytics--text-to-sql-aitext_to_sql
and docs/architecture/05-security.md#why-a-read-only-role-matters-more-than-the-sql-blocklist.

This is defense layer one (fast, clear error messages). Defense layer two,
the real enforcement, is that the query executes under AI_READONLY_ROLE,
which has no grant outside SEMANTIC and no write privilege anywhere
(ADR-006). A bug here can't escalate into data loss or a cross-schema read;
at worst it produces a confusing error instead of a clear one.

Uses sqlglot for real parsing rather than a keyword blocklist. The
original repo's `id_safe()` checked `"drop" not in sql.lower()`, which a
column named `dropoff_time` or a quoted string literal would already defeat.
"""
from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp

DISALLOWED_NODE_TYPES = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create,
    exp.Merge, exp.Command, exp.Grant, exp.Copy,
)


class GuardrailViolation(Exception):
    """Raised with a human-readable reason, shown to the user rather than
    swallowed. See docs/architecture/04-ai-architecture.md point 5."""


@dataclass(frozen=True)
class ValidatedQuery:
    sql: str            # the exact string that will be executed, LIMIT enforced
    original_sql: str    # what the LLM actually generated, for display/audit


def validate_and_prepare(candidate_sql: str, allowed_tables: set[str], default_schema: str, row_limit: int) -> ValidatedQuery:
    try:
        statements = sqlglot.parse(candidate_sql, read="snowflake")
    except Exception as exc:
        raise GuardrailViolation(f"Could not parse the generated SQL: {exc}") from exc

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise GuardrailViolation(f"Expected exactly one SQL statement, found {len(statements)}.")

    root = statements[0]
    inner = root.this if isinstance(root, exp.With) else root

    if not isinstance(inner, exp.Select | exp.Union):
        raise GuardrailViolation(f"Only SELECT/WITH statements are allowed; got {type(root).__name__}.")

    disallowed = list(root.find_all(*DISALLOWED_NODE_TYPES))
    if disallowed:
        kinds = sorted({type(n).__name__ for n in disallowed})
        raise GuardrailViolation(f"Disallowed operation(s) found: {', '.join(kinds)}.")

    _check_table_allowlist(root, allowed_tables, default_schema)
    _enforce_row_limit(inner, row_limit)

    return ValidatedQuery(sql=root.sql(dialect="snowflake"), original_sql=candidate_sql)


def _check_table_allowlist(root: exp.Expression, allowed_tables: set[str], default_schema: str) -> None:
    cte_names = {cte.alias_or_name.upper() for cte in root.find_all(exp.CTE)}
    default_schema = default_schema.upper()

    for table in root.find_all(exp.Table):
        name = table.name.upper()
        db = (table.db or "").upper()

        if not db and name in cte_names:
            continue  # a reference to a WITH-defined CTE, not a real table

        if db and db != default_schema:
            raise GuardrailViolation(f"Schema '{db}' is not allowed; only {default_schema} may be queried.")

        qualified = f"{db or default_schema}.{name}"
        if qualified not in allowed_tables:
            raise GuardrailViolation(f"Table '{qualified}' is not on the allowlist. Allowed: {sorted(allowed_tables)}.")


def _enforce_row_limit(query_node: exp.Expression, row_limit: int) -> None:
    existing = query_node.args.get("limit")
    if existing is None:
        query_node.set("limit", exp.Limit(expression=exp.Literal.number(row_limit)))
        return

    try:
        current_value = int(existing.expression.this)
    except (AttributeError, ValueError, TypeError):
        # Non-literal LIMIT (e.g. a bind variable): replace outright rather than trust it.
        existing.set("expression", exp.Literal.number(row_limit))
        return

    if current_value > row_limit:
        existing.set("expression", exp.Literal.number(row_limit))
