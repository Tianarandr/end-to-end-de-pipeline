"""INGESTION_RUNS control table access, the duplicate-protection and
observability mechanism described in docs/architecture/02-data-flow.md and
docs/architecture/06-observability.md.

Plain functions rather than a class, so tests can patch a cursor without
standing up a real connection (see tests/python/test_ingestion_idempotency.py).
"""
from __future__ import annotations

from datetime import UTC, datetime

from ingestion.models import FileLoadResult, LoadStatus


def is_file_already_loaded(cursor, source: str, file_name: str) -> bool:
    """A file only counts as loaded if a *previous* attempt SUCCEEDED. A prior
    FAILED attempt for the same file gets retried rather than skipped, which
    is what lets ingestion pick back up cleanly after a transient failure."""
    cursor.execute(
        """
        SELECT 1 FROM PUBLIC.INGESTION_RUNS
        WHERE source = %(source)s AND file_name = %(file_name)s AND status = %(status)s
        LIMIT 1
        """,
        {"source": source, "file_name": file_name, "status": LoadStatus.SUCCEEDED.value},
    )
    return cursor.fetchone() is not None


def record_result(cursor, result: FileLoadResult) -> None:
    cursor.execute(
        """
        MERGE INTO PUBLIC.INGESTION_RUNS AS target
        USING (SELECT %(run_id)s AS run_id, %(source)s AS source, %(file_name)s AS file_name) AS src
        ON target.run_id = src.run_id AND target.source = src.source AND target.file_name = src.file_name
        WHEN MATCHED THEN UPDATE SET
            ingestion_timestamp = %(ingestion_timestamp)s,
            row_count = %(row_count)s,
            status = %(status)s,
            error_message = %(error_message)s
        WHEN NOT MATCHED THEN INSERT (run_id, source, file_name, ingestion_timestamp, row_count, status, error_message)
        VALUES (%(run_id)s, %(source)s, %(file_name)s, %(ingestion_timestamp)s, %(row_count)s, %(status)s, %(error_message)s)
        """,
        {
            "run_id": result.run_id,
            "source": result.source,
            "file_name": result.file_ref.key,
            "ingestion_timestamp": datetime.now(UTC),
            "row_count": result.row_count,
            "status": result.status.value,
            "error_message": result.error_message,
        },
    )
