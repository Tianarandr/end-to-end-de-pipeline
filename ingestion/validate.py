"""What Airflow's `bronze_validation` task calls. Confirms the ingestion
stage that just ran actually succeeded for every source before dbt reads
RAW. See docs/architecture/07-data-quality.md.

Kept small and specific to this one check. It reuses
ingestion.snowflake_client (LOADER_ROLE has SELECT on PUBLIC.INGESTION_RUNS)
instead of adding a second connection-config path.
"""
from __future__ import annotations

from ingestion.config import load_settings
from ingestion.snowflake_client import get_loader_connection


class BronzeValidationFailed(Exception):
    pass


def assert_bronze_load_succeeded(run_id: str) -> dict:
    settings = load_settings()
    connection = get_loader_connection(settings)
    cursor = connection.cursor()
    cursor.execute(
        "SELECT source, status, row_count FROM PUBLIC.INGESTION_RUNS WHERE run_id = %(run_id)s",
        {"run_id": run_id},
    )
    rows = cursor.fetchall()
    connection.close()

    if not rows:
        raise BronzeValidationFailed(f"No INGESTION_RUNS rows found for run_id={run_id}; ingestion may not have run.")

    failed_sources = sorted({source for source, status, _ in rows if status == "FAILED"})
    if failed_sources:
        raise BronzeValidationFailed(f"Ingestion failed for source(s): {failed_sources}. See PUBLIC.INGESTION_RUNS for error_message detail.")

    total_rows = sum(row_count or 0 for _, _, row_count in rows)
    return {"sources_loaded": len({source for source, _, _ in rows}), "total_rows": total_rows}
