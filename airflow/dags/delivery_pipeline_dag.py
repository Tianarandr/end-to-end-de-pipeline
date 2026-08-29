"""Daily delivery_pipeline DAG, nine logical stages, each its own TaskGroup,
so the Airflow graph view *is* the architecture diagram (see
docs/architecture/06-observability.md). This file is orchestration only:
every task calls into ingestion/, dbt, ai/, or observability/, and no
transformation or AI logic lives here. See ADR-003.

    ingestion -> bronze_validation -> dbt_staging -> data_quality
              -> gold_models -> semantic_validation
              -> ai_enrichment -> ai_quality_checks -> publish

A single Airflow run_id ({{ run_id }}) is threaded through every stage as
the ingestion batch_id / AI batch_id / PIPELINE_RUNS run_id. See
docs/architecture/02-data-flow.md#run-identity-and-traceability.

A blocking failure anywhere before `publish` (ingestion failure, a
severity=error dbt test, an AI failure-rate breach) stops the DAG there;
downstream tasks are never reached. See docs/architecture/07-data-quality.md.
"""
from __future__ import annotations

from datetime import datetime

from ai.enrichment.quality_check import check_batch_quality
from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup
from ingestion.validate import assert_bronze_load_succeeded
from observability.pipeline_runs import record_failure_from_context, record_pipeline_run

PROJECT_ROOT = "/opt/airflow/project"
# The dbt venv is built into the image at /opt/airflow/.dbt_venv (docker/airflow/Dockerfile),
# kept OUTSIDE the bind-mounted project directory: anything built under
# PROJECT_ROOT at image-build time would get shadowed the moment the host repo
# is mounted over it at container start.
DBT = "/opt/airflow/.dbt_venv/bin/dbt"
DBT_PROJECT_DIR = f"{PROJECT_ROOT}/dbt/delivery_pipeline"
DBT_PROFILES_DIR = f"{PROJECT_ROOT}/dbt/delivery_pipeline/profiles"
DBT_FLAGS = f"--project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROFILES_DIR}"

RUN_ID = "{{ run_id }}"


def _record_success(**context) -> None:
    dag_run = context["dag_run"]
    ti = context["task_instance"]

    bronze = ti.xcom_pull(task_ids="bronze_validation.validate_bronze_load") or {}
    ai_quality = ti.xcom_pull(task_ids="ai_quality_checks.check_ai_batch_quality") or {}

    record_pipeline_run(
        run_id=dag_run.run_id,
        dag_run_id=dag_run.run_id,
        started_at=dag_run.start_date,
        status="SUCCESS",
        rows_ingested=bronze.get("total_rows", 0),
        dq_status="passed",  # getting to this task means every blocking gate upstream already passed
        ai_success_count=ai_quality.get("succeeded", 0),
        ai_fail_count=ai_quality.get("failed", 0),
    )


with DAG(
    dag_id="delivery_pipeline",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["delivery", "dbt", "snowflake", "ai"],
    on_failure_callback=record_failure_from_context,
    doc_md=__doc__,
) as dag:

    with TaskGroup(group_id="ingestion") as ingestion:
        run_ingestion = BashOperator(
            task_id="run_ingestion",
            bash_command=f"cd {PROJECT_ROOT} && python -m ingestion.run --source all --run-id '{RUN_ID}'",
            retries=2,
        )

    with TaskGroup(group_id="bronze_validation") as bronze_validation:
        validate_bronze_load = PythonOperator(
            task_id="validate_bronze_load",
            python_callable=assert_bronze_load_succeeded,
            op_kwargs={"run_id": RUN_ID},
        )

    with TaskGroup(group_id="dbt_staging") as dbt_staging:
        run_staging = BashOperator(
            task_id="run_staging",
            bash_command=f"{DBT} run --select staging {DBT_FLAGS}",
        )

    with TaskGroup(group_id="data_quality") as data_quality:
        # Source freshness + staging tests. If a severity=error test fails
        # here (see docs/architecture/07-data-quality.md), this task fails
        # and the DAG doesn't proceed to gold_models.
        check_source_freshness = BashOperator(
            task_id="check_source_freshness",
            bash_command=f"{DBT} source freshness {DBT_FLAGS}",
        )
        test_staging = BashOperator(
            task_id="test_staging",
            bash_command=f"{DBT} test --select staging {DBT_FLAGS}",
        )
        check_source_freshness >> test_staging

    with TaskGroup(group_id="gold_models") as gold_models:
        build_marts = BashOperator(
            task_id="build_marts",
            bash_command=f"{DBT} build --select marts --exclude tag:ai {DBT_FLAGS}",
        )

    with TaskGroup(group_id="semantic_validation") as semantic_validation:
        build_semantic = BashOperator(
            task_id="build_semantic",
            bash_command=f"{DBT} build --select semantic {DBT_FLAGS}",
        )

    with TaskGroup(group_id="ai_enrichment") as ai_enrichment:
        run_enrichment = BashOperator(
            task_id="run_enrichment",
            bash_command=f"cd {PROJECT_ROOT} && python -m ai.enrichment.run --batch-id '{RUN_ID}'",
            retries=1,
        )

    with TaskGroup(group_id="ai_quality_checks") as ai_quality_checks:
        check_ai_batch_quality = PythonOperator(
            task_id="check_ai_batch_quality",
            python_callable=check_batch_quality,
            op_kwargs={"batch_id": RUN_ID},
        )

    with TaskGroup(group_id="publish") as publish:
        build_ai_models = BashOperator(
            task_id="build_ai_models",
            bash_command=f"{DBT} build --select tag:ai {DBT_FLAGS}",
        )
        record_run = PythonOperator(
            task_id="record_run",
            python_callable=_record_success,
        )
        build_ai_models >> record_run

    (
        ingestion
        >> bronze_validation
        >> dbt_staging
        >> data_quality
        >> gold_models
        >> semantic_validation
        >> ai_enrichment
        >> ai_quality_checks
        >> publish
    )
