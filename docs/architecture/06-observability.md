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

## What this doesn't include

No external observability platform (Datadog/Monte Carlo/Grafana) is wired
up. At this scale, three control tables plus Airflow's own UI and structured
logs answer every question above; a dashboard on top of `PIPELINE_RUNS` is a
half-day follow-up whenever the team is large enough to need one, not a
day-one requirement. See the "what would change at larger scale" section of
the top-level README.
