# 06: Observability

## What "observable" means here

For every pipeline run, without opening Airflow's task logs, you can answer:

- What started, and when?
- What succeeded, what failed?
- How many rows moved through ingestion, staging, and gold?
- How long did each stage take?
- Which source file / batch was processed?
- Did data quality pass, and was any failure blocking or just a warning?
- Did AI enrichment succeed? How many records failed, and why?

This is answered from **three control tables**, not from log-scraping:

| Table | Written by | Answers |
|---|---|---|
| `INGESTION_RUNS` | `ingestion/` | Per-source ingestion outcome: `run_id`, `source`, `file_name`, `ingestion_timestamp`, `row_count`, `status`, `error_message`. |
| `AI.ENRICHMENT_LOG` | `ai/enrichment/` | Per-review-attempt outcome: `batch_id`, `status`, `attempt_number`, `error_message`, `processed_at`. |
| `PIPELINE_RUNS` | Airflow's `publish` task | One row per DAG run: `run_id`, `dag_run_id`, `started_at`, `finished_at`, `status`, `rows_ingested`, `dq_status` (`passed`/`warned`/`failed`), `ai_success_count`, `ai_fail_count`. |

`docs/data_contracts/pipeline_runs.yml` and the DDL in
[snowflake/03_control_tables.sql](../../snowflake/03_control_tables.sql)
define the exact schema.

## Airflow-level observability

- The DAG (`airflow/dags/delivery_pipeline_dag.py`) is organized into
  `TaskGroup`s that mirror the logical pipeline stages (see
  [16-AIRFLOW in the README] / the DAG file itself), so the Airflow UI's
  graph view *is* the architecture diagram: a failed task tells you exactly
  which stage broke.
- Every custom Python task logs structured, greppable lines
  (`ingestion/logging_utils.py`, `ai/common/logging_utils.py`), like
  `event=ingestion_run_complete run_id=... source=... rows=... status=...`,
  instead of free-text prints, so logs can be parsed by a future log-based
  alert without changing the code.
- `run_id` (the ingestion batch) and the Airflow `dag_run.run_id` are both
  logged on every task, so an Airflow run can always be traced forward to
  the exact `INGESTION_RUNS` / `PIPELINE_RUNS` rows it produced.
- Task-level retries (`retries=2`, exponential backoff) are set on network-
  bound tasks (ingestion, AI enrichment); dbt/data-quality tasks are not
  auto-retried. A failing test is a real failure to look at, not a flake.

## Alerting

`observability/alerting.py`'s `send_alert()` is called from the two places
a run failing is actually decided: the DAG's `on_failure_callback`
(`record_failure_from_context`, any task) and the AI quality-check breach
(`ai/enrichment/quality_check.py`, a failure rate over threshold). Two
channels, both optional and independently configured (`.env.example`): a
Slack incoming webhook, and SMTP email. Neither is configured by default
(dev/CI): with nothing set, `send_alert()` logs and returns, so a run still
gets its `PIPELINE_RUNS`/`ENRICHMENT_LOG` row either way, it just doesn't
also page anyone. An alert send failure (webhook down, SMTP unreachable) is
caught and logged, never raised: alerting is a side channel on top of an
already-failing run, not something that can turn into a second, unrelated
failure.

## Lineage

dbt's own model graph (`ref()`/`source()`) is the lineage mechanism for
everything from `STAGING` through `SEMANTIC`/`AI` (see
[ADR-002](../decisions/ADR-002-dbt.md)); `dbt docs generate` renders it as
an interactive DAG. The one hop that graph doesn't cover is what happens
*before* dbt ever runs: which S3 file produced which `RAW` load. When
`OPENLINEAGE_URL` is set, `airflow/dags/delivery_pipeline_dag.py` runs dbt
through the `dbt-ol` wrapper (`openlineage-dbt`) instead of `dbt` directly,
which emits column-level lineage for every dbt-built table with no code
change here, and `observability/lineage.py` emits one OpenLineage run event
per ingestion source, closing the S3-to-`RAW` gap. Both are no-ops if
`OPENLINEAGE_URL` isn't set (the CI/local default): no lineage backend
(e.g. [Marquez](https://marquezproject.ai/)) is stood up by this repo, this
just means the pipeline emits standard OpenLineage events the moment one
exists to receive them.

## What this doesn't include

No external observability platform (Datadog/Monte Carlo/Grafana) is wired
up, and no lineage backend is deployed as part of this repo. At this scale,
three control tables plus Airflow's own UI and structured logs answer every
question above; a dashboard on top of `PIPELINE_RUNS`, or standing up
Marquez to receive the OpenLineage events already being emitted, is a
follow-up whenever the team is large enough to need one, not a day-one
requirement. See the "what would change at larger scale" section of the
top-level README.
