"""Unit tests for the ingestion idempotency/duplicate-protection mechanism.
See docs/architecture/02-data-flow.md#ingestion--bronze-the-part-most-portfolio-pipelines-skip.
No live Snowflake connection: the cursor is mocked."""
from __future__ import annotations

from unittest.mock import MagicMock

from ingestion.control_table import is_file_already_loaded, record_result
from ingestion.loader import SnowflakeLoader
from ingestion.models import FileLoadResult, FileRef, LoadStatus
from ingestion.sources.base import Source


def test_is_file_already_loaded_true_when_prior_success_exists():
    cursor = MagicMock()
    cursor.fetchone.return_value = (1,)

    assert is_file_already_loaded(cursor, "orders", "raw/orders/2026-01-01.csv") is True
    cursor.execute.assert_called_once()
    args, kwargs = cursor.execute.call_args
    assert args[1]["status"] == "SUCCEEDED"


def test_is_file_already_loaded_false_when_no_prior_success():
    cursor = MagicMock()
    cursor.fetchone.return_value = None

    assert is_file_already_loaded(cursor, "orders", "raw/orders/2026-01-01.csv") is False


def test_record_result_uses_merge_to_stay_idempotent():
    cursor = MagicMock()
    result = FileLoadResult(
        source="orders",
        file_ref=FileRef(key="raw/orders/f.csv", relative_path="f.csv"),
        run_id="run-1",
        row_count=10,
        status=LoadStatus.SUCCEEDED,
    )
    record_result(cursor, result)

    sql = cursor.execute.call_args[0][0]
    assert "MERGE INTO" in sql
    assert "INGESTION_RUNS" in sql


class _FakeSource(Source):
    """A Source stub that exercises SnowflakeLoader without needing S3 or a
    real Snowflake connection, which is the whole point of the Source
    abstraction (ADR-004)."""

    def __init__(self, name: str, files: list[FileRef]) -> None:
        self.name = name
        self._files = files

    def list_new_files(self) -> list[FileRef]:
        return self._files

    def stage_ref(self, database: str) -> str:
        return f"@{database}.RAW.LANDING_STAGE/{self.name}/"


def test_loader_skips_already_loaded_files_without_running_copy_into(mocker):
    connection = MagicMock()
    cursor = MagicMock()
    connection.cursor.return_value = cursor

    # Every file looks already-loaded.
    mocker.patch("ingestion.loader.is_file_already_loaded", return_value=True)
    record_result_mock = mocker.patch("ingestion.loader.record_result")

    source = _FakeSource("orders", [FileRef(key="raw/orders/a.csv", relative_path="a.csv")])
    loader = SnowflakeLoader(connection, database="DELIVERY_DEV")

    results = loader.load_source(source, run_id="run-1")

    assert len(results) == 1
    assert results[0].status == LoadStatus.SKIPPED_ALREADY_LOADED
    cursor.execute.assert_not_called()  # no COPY INTO issued for an already-loaded file
    record_result_mock.assert_called_once()


def test_loader_runs_copy_into_for_new_files_and_records_success(mocker):
    connection = MagicMock()
    cursor = MagicMock()
    connection.cursor.return_value = cursor
    cursor.fetchall.return_value = [("a.csv", "LOADED", 100, 100, 0, 0, None, None, None, None)]

    mocker.patch("ingestion.loader.is_file_already_loaded", return_value=False)
    record_result_mock = mocker.patch("ingestion.loader.record_result")

    source = _FakeSource("orders", [FileRef(key="raw/orders/a.csv", relative_path="a.csv")])
    loader = SnowflakeLoader(connection, database="DELIVERY_DEV")

    results = loader.load_source(source, run_id="run-1")

    assert results[0].status == LoadStatus.SUCCEEDED
    assert results[0].row_count == 100
    copy_sql = cursor.execute.call_args_list[0][0][0]
    assert "COPY INTO RAW.orders" in copy_sql
    assert "_batch_id" in copy_sql
    assert "_record_hash" in copy_sql
    record_result_mock.assert_called_once()


def test_loader_records_failure_on_copy_into_error_without_raising(mocker):
    connection = MagicMock()
    cursor = MagicMock()
    connection.cursor.return_value = cursor
    cursor.execute.side_effect = Exception("boom")  # simulate COPY INTO failing

    mocker.patch("ingestion.loader.is_file_already_loaded", return_value=False)
    record_result_mock = mocker.patch("ingestion.loader.record_result")

    source = _FakeSource("orders", [FileRef(key="raw/orders/a.csv", relative_path="a.csv")])
    loader = SnowflakeLoader(connection, database="DELIVERY_DEV")

    results = loader.load_source(source, run_id="run-1")

    assert results[0].status == LoadStatus.FAILED
    assert "boom" in results[0].error_message
    record_result_mock.assert_called_once()  # failure is logged, never silently dropped
