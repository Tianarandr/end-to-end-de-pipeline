"""Idempotent, source-agnostic ingestion into the Bronze (RAW) layer.

See docs/architecture/02-data-flow.md and ADR-004 for the design this
package implements: sources (ingestion/sources/) yield file references,
SnowflakeLoader (loader.py) stamps technical metadata and logs every
attempt to the INGESTION_RUNS control table, regardless of source shape.
"""
