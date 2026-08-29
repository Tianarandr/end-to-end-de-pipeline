"""SnowflakeLoader is the one place that knows how to get a file from a
Source into RAW with technical metadata attached, regardless of source type.

Idempotency works on two layers (see ADR-004):
1. Application-level: `is_file_already_loaded` skips any file with a prior
   SUCCEEDED row in INGESTION_RUNS for the same source, which is what makes
   a re-triggered DAG run a safe no-op.
2. Warehouse-level: Snowflake's own COPY INTO load history also refuses to
   reload a file it's already loaded into the same table (tracked for 64
   days), independent of our control table.
"""
from __future__ import annotations

import uuid

from ingestion.config import SOURCE_COLUMNS
from ingestion.control_table import is_file_already_loaded, record_result
from ingestion.logging_utils import get_logger, log_event
from ingestion.models import FileLoadResult, FileRef, LoadStatus
from ingestion.sources.base import Source
from snowflake.connector import SnowflakeConnection

logger = get_logger(__name__)


def new_run_id() -> str:
    return str(uuid.uuid4())


class SnowflakeLoader:
    def __init__(self, connection: SnowflakeConnection, database: str) -> None:
        self.connection = connection
        self.database = database

    def load_source(self, source: Source, run_id: str) -> list[FileLoadResult]:
        cursor = self.connection.cursor()
        results: list[FileLoadResult] = []

        try:
            files = source.list_new_files()
        except Exception as exc:  # network/S3 failure: treat the whole source as failed, log it as one row
            log_event(logger, "ingestion_list_files_failed", source=source.name, error=str(exc))
            failure = FileLoadResult(
                source=source.name,
                file_ref=FileRef(key="<list_files>", relative_path=""),
                run_id=run_id,
                row_count=0,
                status=LoadStatus.FAILED,
                error_message=str(exc),
            )
            record_result(cursor, failure)
            self.connection.commit()
            return [failure]

        log_event(logger, "ingestion_source_discovered", source=source.name, file_count=len(files))

        for file_ref in files:
            if is_file_already_loaded(cursor, source.name, file_ref.key):
                result = FileLoadResult(source.name, file_ref, run_id, 0, LoadStatus.SKIPPED_ALREADY_LOADED)
                log_event(logger, "ingestion_file_skipped", source=source.name, file=file_ref.key)
            else:
                result = self._load_file(cursor, source, file_ref, run_id)

            record_result(cursor, result)
            self.connection.commit()  # commit per file so a mid-batch crash still leaves earlier files recorded correctly
            results.append(result)

        cursor.close()
        return results

    def _load_file(self, cursor, source: Source, file_ref: FileRef, run_id: str) -> FileLoadResult:
        columns = SOURCE_COLUMNS[source.name]
        select_positions = ", ".join(f"${i + 1}" for i in range(len(columns)))
        row_hash_expr = f"MD5(CONCAT_WS('|', {select_positions}))"
        column_list = ", ".join(columns)

        copy_sql = f"""
            COPY INTO RAW.{source.name}
                ({column_list}, _ingested_at, _source_file, _batch_id, _record_hash)
            FROM (
                SELECT {select_positions},
                       CURRENT_TIMESTAMP(),
                       METADATA$FILENAME,
                       '{run_id}',
                       {row_hash_expr}
                FROM {source.stage_ref(self.database)}
            )
            FILES = ('{file_ref.relative_path}')
            FILE_FORMAT = (FORMAT_NAME = RAW.CSV_FMT)
            ON_ERROR = 'ABORT_STATEMENT'
        """

        try:
            cursor.execute(copy_sql)
            copy_rows = cursor.fetchall()
            # COPY INTO returns one row per file, rows_loaded sits at position 3
            # (file, status, rows_parsed, rows_loaded, ...) in the connector's result shape.
            row_count = sum(row[3] for row in copy_rows) if copy_rows else 0
            log_event(logger, "ingestion_file_loaded", source=source.name, file=file_ref.key, rows=row_count)
            return FileLoadResult(source.name, file_ref, run_id, row_count, LoadStatus.SUCCEEDED)
        except Exception as exc:
            log_event(logger, "ingestion_file_failed", source=source.name, file=file_ref.key, error=str(exc))
            return FileLoadResult(source.name, file_ref, run_id, 0, LoadStatus.FAILED, error_message=str(exc))
