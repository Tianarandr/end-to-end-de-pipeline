# dbt project: delivery_pipeline

Silver to Gold to Semantic transformation. See
[docs/architecture/03-data-model.md](../../docs/architecture/03-data-model.md)
for the full schema, and [ADR-002](../../docs/decisions/ADR-002-dbt.md) for
why we picked dbt.

```
models/
├── staging/    # Silver: cast, dedupe, standardize. One stg_* view per RAW source.
├── marts/      # Gold: star schema (dim_*/fact_*) plus business marts.
└── semantic/   # Semantic layer: curated views AI/BI actually read (ADR-005).
metrics/
└── metrics.yml # Metric dictionary, loaded directly by ai/text_to_sql/schema_registry.py.
macros/
└── metrics.sql # The SQL each metric above resolves to. One definition, reused everywhere.
```

## Running it

```bash
cp profiles/profiles.yml.example profiles/profiles.yml   # fill in real values, gitignored
dbt deps    --project-dir . --profiles-dir profiles
dbt build   --project-dir . --profiles-dir profiles --exclude tag:ai   # staging + gold + semantic
# ... ai/enrichment runs here in the real pipeline ...
dbt build   --project-dir . --profiles-dir profiles --select tag:ai    # mart_review_insights
```

`make dbt-build` / `make dbt-test` (repo root `Makefile`) wrap the same
commands. See [docs/architecture/07-data-quality.md](../../docs/architecture/07-data-quality.md)
for which tests block the build and which just warn.
