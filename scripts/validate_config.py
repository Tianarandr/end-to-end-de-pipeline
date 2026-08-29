#!/usr/bin/env python3
"""Configuration validation: the CI step for "did someone forget an env var
or write invalid YAML," run without any live credentials. See
.github/workflows/ci.yml.

Checks:
1. Every required field on IngestionSettings/AISettings has a matching key
   (case-insensitive) in .env.example, so a new required setting can't ship
   without also documenting it there.
2. Every docs/data_contracts/*.yml file is valid YAML with the required
   top-level keys.
3. ai/text_to_sql/schema_registry.yml is valid YAML and every metric in
   dbt/delivery_pipeline/metrics/metrics.yml that names a semantic_view points
   at a view actually present in the registry (also covered by
   tests/python/test_schema_registry.py, repeated here so `make` /CI's
   config-validation step doesn't silently depend on the test suite for it).
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent

REQUIRED_CONTRACT_KEYS = {"dataset", "owner", "description", "grain", "primary_key"}


def check_env_example_covers_settings() -> list[str]:
    sys.path.insert(0, str(ROOT))
    from ai.common.config import AISettings
    from ingestion.config import IngestionSettings

    env_example = (ROOT / ".env.example").read_text().upper()
    errors = []

    for settings_cls in (IngestionSettings, AISettings):
        for name, field in settings_cls.model_fields.items():
            if field.is_required():
                env_key = name.upper()
                if env_key not in env_example:
                    errors.append(f"{settings_cls.__name__}.{name} is required but '{env_key}' is not documented in .env.example")
    return errors


def check_data_contracts() -> list[str]:
    errors = []
    contracts_dir = ROOT / "docs" / "data_contracts"
    contract_files = list(contracts_dir.glob("*.yml"))
    if not contract_files:
        errors.append(f"No data contracts found in {contracts_dir}")

    for path in contract_files:
        try:
            doc = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            errors.append(f"{path}: invalid YAML ({exc})")
            continue
        missing = REQUIRED_CONTRACT_KEYS - set(doc or {})
        if missing:
            errors.append(f"{path}: missing required key(s) {sorted(missing)}")
    return errors


def check_schema_registry_metrics_consistency() -> list[str]:
    errors = []
    registry_path = ROOT / "ai" / "text_to_sql" / "schema_registry.yml"
    metrics_path = ROOT / "dbt" / "delivery_pipeline" / "metrics" / "metrics.yml"

    try:
        registry = yaml.safe_load(registry_path.read_text())
        metrics_doc = yaml.safe_load(metrics_path.read_text())
    except yaml.YAMLError as exc:
        return [f"invalid YAML in schema_registry.yml or metrics.yml ({exc})"]

    allowed = {f"{registry['schema']}.{v}" for v in registry["views"]}
    for metric in metrics_doc["metrics"]:
        view = metric.get("semantic_view")
        if view and view not in allowed:
            errors.append(f"metric '{metric['name']}' references semantic_view '{view}' not present in schema_registry.yml")
    return errors


def main() -> int:
    all_errors = [
        *check_env_example_covers_settings(),
        *check_data_contracts(),
        *check_schema_registry_metrics_consistency(),
    ]

    if all_errors:
        print("Configuration validation FAILED:")
        for e in all_errors:
            print(f"  - {e}")
        return 1

    print("Configuration validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
