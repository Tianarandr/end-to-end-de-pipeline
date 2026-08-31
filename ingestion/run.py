"""CLI entrypoint for the ingestion stage, what Airflow's `ingestion`
TaskGroup actually calls (`python -m ingestion.run`). Stays thin on purpose:
it wires config to sources to loader and reports a summary. The real logic
lives in loader.py, control_table.py, and sources/, so it can be unit
tested without Airflow in the picture.

Exit code is non-zero if any source FAILED, so Airflow's task (and with it
the whole `ingestion` TaskGroup) fails and the DAG doesn't proceed to
bronze_validation. See docs/architecture/07-data-quality.md.
"""
from __future__ import annotations

import argparse
import sys

from ingestion.config import SOURCE_COLUMNS, load_settings
from ingestion.loader import SnowflakeLoader, new_run_id
from ingestion.logging_utils import get_logger, log_event
from ingestion.models import LoadStatus
from ingestion.snowflake_client import get_loader_connection
from ingestion.sources.s3_csv import S3CsvSource
from observability.lineage import emit_source_load

logger = get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run ingestion for one or all sources.")
    parser.add_argument("--source", default="all", help="Source name, or 'all' (default).")
    parser.add_argument("--run-id", default=None, help="Override run_id (defaults to a fresh UUID). Airflow passes its dag_run.run_id here for cross-referencing PIPELINE_RUNS.")
    args = parser.parse_args(argv)

    settings = load_settings()
    run_id = args.run_id or new_run_id()
    source_names = list(SOURCE_COLUMNS) if args.source == "all" else [args.source]

    log_event(logger, "ingestion_run_started", run_id=run_id, sources=",".join(source_names))

    connection = get_loader_connection(settings)
    loader = SnowflakeLoader(connection, settings.snowflake_database)

    any_failed = False
    total_rows = 0
    for name in source_names:
        source = S3CsvSource(name=name, bucket=settings.s3_landing_bucket, region=settings.aws_region)
        results = loader.load_source(source, run_id)
        source_rows = 0
        source_failed = False
        for r in results:
            total_rows += r.row_count
            source_rows += r.row_count
            if r.status == LoadStatus.FAILED:
                any_failed = True
                source_failed = True

        emit_source_load(
            run_id=run_id,
            source=name,
            s3_keys=[r.file_ref.key for r in results],
            raw_table=f"RAW.{name}",
            state="FAIL" if source_failed else "COMPLETE",
            row_count=source_rows,
        )

    connection.close()
    log_event(
        logger,
        "ingestion_run_finished",
        run_id=run_id,
        total_rows=total_rows,
        status="FAILED" if any_failed else "SUCCEEDED",
    )
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
