"""Small, source-agnostic data structures shared across ingestion/."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LoadStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED_ALREADY_LOADED = "SKIPPED_ALREADY_LOADED"


@dataclass(frozen=True)
class FileRef:
    """A single loadable unit from a Source: a CSV file today, maybe a
    paginated API response or a CDC extract batch down the line. `key` is
    the source's own identifier for it (S3 key, API cursor, extract id);
    `relative_path` is what the loader passes to Snowflake's
    COPY INTO ... FILES = (...)."""

    key: str
    relative_path: str
    size_bytes: int | None = None


@dataclass(frozen=True)
class FileLoadResult:
    source: str
    file_ref: FileRef
    run_id: str
    row_count: int
    status: LoadStatus
    error_message: str | None = None
