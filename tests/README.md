# Tests

`tests/python/` holds unit tests for the parts of this repo that are pure
logic and worth protecting with fast, no-warehouse-needed tests: ingestion
idempotency (`ingestion/loader.py`, `ingestion/control_table.py`), the
text-to-SQL AST guardrails (`ai/text_to_sql/guardrails.py`), AI enrichment's
structured-output validation and attempt logging, and the schema-registry /
metrics-dictionary consistency check.

Everything here mocks the Snowflake connection/cursor: no live warehouse,
no credentials, matching `.github/workflows/ci.yml`'s "no production
credentials in CI" rule (see docs/architecture/05-security.md).

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/python -v
# or: make test
```

dbt's own tests (schema tests, freshness, singular tests) aren't
duplicated here; they're dbt's job, validated by `dbt parse`/`dbt build`
(see `dbt/delivery_pipeline/README.md` and
[docs/architecture/07-data-quality.md](../docs/architecture/07-data-quality.md)).
