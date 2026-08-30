"""Unit tests for observability/lineage.py. openlineage-client is imported
lazily inside emit_source_load (see its docstring), so these tests fake the
module in sys.modules rather than requiring the real package to be
installed, matching how CI's fast unit-test job doesn't install it. See
docs/architecture/06-observability.md#lineage."""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

from observability.lineage import emit_source_load


def test_no_op_when_openlineage_url_not_set(monkeypatch):
    monkeypatch.delenv("OPENLINEAGE_URL", raising=False)
    # No openlineage.client import should even be attempted; if it were,
    # and the package isn't installed, this would raise ImportError instead
    # of silently returning.
    emit_source_load(run_id="r1", source="orders", s3_keys=["orders/2026-01-01.csv"], raw_table="RAW.ORDERS", state="COMPLETE")


def _install_fake_openlineage_module():
    client_module = types.ModuleType("openlineage.client")
    run_module = types.ModuleType("openlineage.client.run")

    mock_client_cls = MagicMock()
    mock_instance = mock_client_cls.return_value
    client_module.OpenLineageClient = mock_client_cls

    run_module.Dataset = lambda namespace, name: {"namespace": namespace, "name": name}
    run_module.Job = lambda namespace, name: {"namespace": namespace, "name": name}
    run_module.Run = lambda runId: {"runId": runId}
    run_module.RunEvent = MagicMock(side_effect=lambda **kwargs: kwargs)
    run_module.RunState = {"START": "START", "COMPLETE": "COMPLETE", "FAIL": "FAIL"}

    openlineage_pkg = types.ModuleType("openlineage")
    sys.modules["openlineage"] = openlineage_pkg
    sys.modules["openlineage.client"] = client_module
    sys.modules["openlineage.client.run"] = run_module
    return mock_client_cls, mock_instance


def test_emits_complete_event_when_configured(monkeypatch):
    monkeypatch.setenv("OPENLINEAGE_URL", "http://marquez.local:5000")
    mock_client_cls, mock_instance = _install_fake_openlineage_module()
    try:
        emit_source_load(
            run_id="r1", source="orders", s3_keys=["orders/2026-01-01.csv"], raw_table="RAW.ORDERS",
            state="COMPLETE", row_count=42,
        )
        mock_client_cls.assert_called_once_with(url="http://marquez.local:5000")
        mock_instance.emit.assert_called_once()
    finally:
        for mod in ("openlineage", "openlineage.client", "openlineage.client.run"):
            sys.modules.pop(mod, None)


def test_emit_failure_is_caught_not_raised(monkeypatch):
    monkeypatch.setenv("OPENLINEAGE_URL", "http://marquez.local:5000")
    mock_client_cls, mock_instance = _install_fake_openlineage_module()
    mock_instance.emit.side_effect = RuntimeError("backend unreachable")
    try:
        emit_source_load(
            run_id="r1", source="orders", s3_keys=["orders/2026-01-01.csv"], raw_table="RAW.ORDERS", state="COMPLETE",
        )  # must not raise
    finally:
        for mod in ("openlineage", "openlineage.client", "openlineage.client.run"):
            sys.modules.pop(mod, None)
