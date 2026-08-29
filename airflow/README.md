# Airflow

`dags/delivery_pipeline_dag.py` is the daily DAG: nine `TaskGroup`s matching
the pipeline's logical stages. See
[docs/architecture/06-observability.md](../docs/architecture/06-observability.md)
and [ADR-003](../docs/decisions/ADR-003-airflow.md).

The Docker image/compose setup lives in [docker/airflow/](../docker/airflow/),
not here; this directory holds only the DAG definition. Its thin Python
callables live in [ingestion/validate.py](../ingestion/validate.py) and
[observability/pipeline_runs.py](../observability/pipeline_runs.py), kept
out of a package literally named `airflow.*` so they don't collide with the
installed `apache-airflow` package's own `airflow` namespace.

```bash
cp .env.example .env                       # fill in real values
cp dbt/delivery_pipeline/profiles/profiles.yml.example dbt/delivery_pipeline/profiles/profiles.yml
cd docker/airflow && docker compose up -d --build
# UI: http://localhost:8080 (admin/admin)
```

Or via the repo-root `Makefile`: `make airflow-up` / `make airflow-down`.
