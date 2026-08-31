"""The Source interface every ingestion source implements.

The point of this abstraction (see ADR-004 and
docs/architecture/02-data-flow.md#ingestion--bronze) is that the loader
never needs to know whether it's loading a CSV drop, an API pull, or a
database/CDC extract. It only needs `list_new_files()` to return `FileRef`s
it can hand to Snowflake's COPY INTO. A new source type means implementing
this interface, not touching loader.py.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ingestion.models import FileRef


class Source(ABC):
    """A landing-zone source: something that has already deposited files in
    S3 under a known prefix, in a shape the loader's COPY INTO can read."""

    name: str

    @abstractmethod
    def list_new_files(self) -> list[FileRef]:
        """Return every file currently in this source's landing prefix.

        Idempotency is *not* this method's job, it always returns everything
        present. The loader (loader.py) decides, via the INGESTION_RUNS
        control table, which of these are actually new. That keeps Source
        implementations simple and keeps "have we loaded this before" in one
        shared place.
        """

    @abstractmethod
    def stage_ref(self, database: str) -> str:
        """The Snowflake stage location this source's files are readable
        from, e.g. `@DATABASE.RAW.LANDING_STAGE/restaurants/`."""
