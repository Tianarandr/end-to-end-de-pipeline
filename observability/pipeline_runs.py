"""What Airflow's `publish` task calls last. Writes the one row per DAG run
that docs/architecture/06-observability.md describes as the top-level
observability record. Pulls its numbers from XCom (earlier tasks' return
values) rather than re-querying every upstream system, since each stage has
already reported what it did."""
from __future__ import annotations

from datetime import UTC, datetime

from ingestion.config import load_settings
from ingestion.snowflake_client import get_loader_connection


def record_pipeline_run(
    *,
    run_id: str,
    dag_run_id: str,
    started_at: datetime,
    status: str,
    rows_ingested: int,
    dq_status: str,
    ai_success_count: int,
    ai_fail_count: int,
) -> None:
    settings = load_settings()
    connection = get_loader_connection(settings)
    cursor = connection.cursor()
    cursor.execute(
        """
        MERGE INTO PUBLIC.PIPELINE_RUNS AS target
        USING (SELECT %(run_id)s AS run_id) AS src
        ON target.run_id = src.run_id
        WHEN MATCHED THEN UPDATE SET
            finished_at = %(finished_at)s, status = %(status)s, rows_ingested = %(rows_ingested)s,
            dq_status = %(dq_status)s, ai_success_count = %(ai_success_count)s, ai_fail_count = %(ai_fail_count)s
        WHEN NOT MATCHED THEN INSERT
            (run_id, dag_run_id, started_at, finished_at, status, rows_ingested, dq_status, ai_success_count, ai_fail_count)
        VALUES
            (%(run_id)s, %(dag_run_id)s, %(started_at)s, %(finished_at)s, %(status)s, %(rows_ingested)s,
             %(dq_status)s, %(ai_success_count)s, %(ai_fail_count)s)
        """,
        {
            "run_id": run_id,
            "dag_run_id": dag_run_id,
            "started_at": started_at,
            "finished_at": datetime.now(UTC),
            "status": status,
            "rows_ingested": rows_ingested,
            "dq_status": dq_status,
            "ai_success_count": ai_success_count,
            "ai_fail_count": ai_fail_count,
        },
    )
    connection.commit()
    connection.close()


def record_failure_from_context(context: dict) -> None:
    """DAG-level `on_failure_callback`. Makes sure a run that never reaches
    `publish` (a blocking data-quality gate failed, ingestion failed, etc.)
    still gets a PIPELINE_RUNS row instead of leaving no record at all.
    It's best-effort: XComs from tasks that never ran simply aren't there,
    so rows_ingested/ai counts fall back to 0 rather than failing the
    callback itself. The callback just needs to make the failure visible,
    not compute a perfect summary of a run that didn't finish.
    """
    dag_run = context["dag_run"]
    ti = context["task_instance"]

    rows_ingested = ti.xcom_pull(task_ids="bronze_validation.validate_bronze_load", key="return_value") or {}

    record_pipeline_run(
        run_id=dag_run.run_id,
        dag_run_id=dag_run.run_id,
        started_at=dag_run.start_date or datetime.now(UTC),
        status="FAILED",
        rows_ingested=rows_ingested.get("total_rows", 0) if isinstance(rows_ingested, dict) else 0,
        dq_status="failed",
        ai_success_count=0,
        ai_fail_count=0,
    )
