# ADR-003: Use Apache Airflow for orchestration

## Status
Accepted

## Context
The pipeline has an ordered set of dependent stages (ingestion, dbt builds,
data-quality gates, AI enrichment) that must run on a schedule, retry
transient failures, and make failure visible per stage.

## Decision
Use Apache Airflow (LocalExecutor, Docker Compose) as the orchestrator, with
the DAG expressed as `TaskGroup`s per logical stage
(`ingestion → bronze_validation → dbt_staging → data_quality → gold_models →
semantic_validation → ai_enrichment → ai_quality_checks → publish`).

## Why
- **Airflow orchestrates; it does not contain business logic.** Every task
  in `airflow/dags/delivery_pipeline_dag.py` is a thin call into `ingestion/`,
  `dbt`, or `ai/`: the DAG file itself is a dependency graph, not a place
  where transformation or AI logic lives. This makes each piece unit-testable
  independent of Airflow.
- **`TaskGroup`s make the DAG graph *be* the architecture diagram.** A
  glance at the Airflow UI shows exactly which of the nine logical stages
  failed; that's the redesign's answer to the original DAG being one flat
  4-task chain with no visible quality gate.
- Mature retry/backoff, SLA, and connection-management primitives, and the
  de facto standard a hiring data engineer will already know.
- The team already standardized on it; no reason to introduce a second
  orchestrator's operational surface (deployment, auth, alerting) for a
  same-class capability.

## Alternatives considered

| Option | Why not |
|---|---|
| Dagster / Prefect | Comparable capability class with stronger native data-asset lineage; a legitimate alternative, but not a strict improvement large enough to justify a rewrite here. Airflow's TaskGroup model already gives adequate stage-level visibility at this pipeline's complexity. |
| Cron + shell scripts | No retries, no dependency graph, no UI, no per-task observability, a step backward from what the original repo already had. |
| No orchestrator (trigger dbt Cloud jobs directly) | Loses the ability to gate AI enrichment on data-quality results and to run the Python ingestion/AI steps in the same dependency graph as the SQL steps. |

## Consequences
- Running Airflow means running Postgres (metadata DB) and the Airflow
  webserver/scheduler/dag-processor: real, if modest, operational surface
  for a small team. `docker/airflow/docker-compose.yaml` keeps this to a
  single-host footprint appropriate for the project's scale; a managed
  Airflow (MWAA/Composer/Astronomer) is the natural next step, not day-one
  infrastructure. See the README's "at larger scale" section.
