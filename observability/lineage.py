"""Best-effort OpenLineage emission for the one hop dbt's own lineage
doesn't cover: ingestion (S3 -> RAW). Lineage from STAGING through
SEMANTIC/AI comes for free by running dbt through the `dbt-ol` wrapper
(`openlineage-dbt`) instead of plain `dbt` when `OPENLINEAGE_URL` is set,
see airflow/dags/delivery_pipeline_dag.py. This module closes the gap
dbt-ol can't see: what fed RAW before dbt ever ran. See
docs/architecture/06-observability.md#lineage.

No-op if OPENLINEAGE_URL isn't set (the CI/local default): ingestion has
zero dependency on a lineage backend actually running, and any emission
failure (backend down, network error, an unexpected client-library shape)
is caught and logged, never raised. Lineage is an observability side
channel; it must never be able to fail an ingestion run.
"""
from __future__ import annotations

import os
from datetime import UTC, datetime

from observability.logging_utils import get_logger, log_event

logger = get_logger(__name__)

NAMESPACE = "delivery-pipeline"
PRODUCER = "https://github.com/Tianarandr/end-to-end-de-pipeline/tree/master/ingestion"


def emit_source_load(
    *,
    run_id: str,
    source: str,
    s3_keys: list[str],
    raw_table: str,
    state: str,
    row_count: int = 0,
    error_message: str | None = None,
) -> None:
    """One event per (run, source): `state` is 'START', 'COMPLETE', or
    'FAIL'. `s3_keys` are the files ingestion/loader.py just loaded (or
    attempted to); `raw_table` is the RAW table they landed in, e.g.
    'RAW.ORDERS'."""
    if not os.environ.get("OPENLINEAGE_URL"):
        return

    try:
        from openlineage.client import OpenLineageClient
        from openlineage.client.run import Dataset, Job, Run, RunEvent, RunState

        client = OpenLineageClient(url=os.environ["OPENLINEAGE_URL"])
        job = Job(namespace=NAMESPACE, name=f"ingestion.{source}")
        run = Run(runId=run_id)
        inputs = [Dataset(namespace="s3", name=key) for key in s3_keys]
        outputs = [Dataset(namespace=NAMESPACE, name=raw_table)] if state != "START" else []

        event = RunEvent(
            eventType=RunState[state],
            eventTime=datetime.now(UTC).isoformat(),
            run=run,
            job=job,
            producer=PRODUCER,
            inputs=inputs,
            outputs=outputs,
        )
        client.emit(event)
        log_event(logger, "lineage_event_emitted", source=source, run_id=run_id, state=state, row_count=row_count)
    except Exception as exc:  # noqa: BLE001 - lineage emission must never fail the ingestion run
        log_event(logger, "lineage_emit_failed", level=30, source=source, run_id=run_id, error=str(exc))


__all__ = ["emit_source_load"]
