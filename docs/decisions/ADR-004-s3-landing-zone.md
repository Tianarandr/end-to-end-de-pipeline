# ADR-004: Use S3 as an immutable landing zone

## Status
Accepted

## Context
Source data (CSV extracts today; API pulls or DB/CDC extracts plausible
later) needs a durable, replayable landing point before it's loaded into
the warehouse, decoupled from both the source system and Snowflake.

## Decision
Land all source data in S3, unmodified, before any Snowflake load. `RAW` in
Snowflake is always populated *from* S3, never written to directly by a
source system.

## Why
- **Immutability and replay.** If a bug is found in staging logic three
  weeks later, the exact bytes that produced a bad Bronze load are still in
  S3 (versioned bucket). Bronze can be rebuilt without going back to the
  source system, which may not even have the data anymore.
- **Decouples ingestion cadence from source availability.** A source API
  being down doesn't block a warehouse reload; a Snowflake maintenance
  window doesn't block landing new files.
- **One ingestion pattern for every future source shape.** `ingestion/sources/base.py`
  defines a `Source` that yields `(file_ref, row_count)`; a CSV drop, an API
  pull serialized to JSON/Parquet, or a CDC extract all land in S3 the same
  way and are loaded the same way. See
  [02-data-flow.md](../architecture/02-data-flow.md#ingestion--bronze-the-part-most-portfolio-pipelines-skip).
  Adding a new source is a new `Source` implementation, not a new pipeline.
- **Cheap, durable, and the natural place for IAM-scoped least-privilege
  access** (`infrastructure/terraform/aws.tf`) between "whatever produces the
  data" and "whatever loads it."

## Alternatives considered

| Option | Why not |
|---|---|
| Load sources directly into Snowflake (skip a landing zone) | No replay capability, no clean boundary for IAM/least-privilege, and API/CDC sources have nowhere to land before a transform decision is made. The landing zone exists to support that without a rewrite. |
| A message queue (Kafka/Kinesis) as the landing point | Solves a streaming problem this project doesn't have. See [ADR-007](ADR-007-no-kafka-spark-k8s.md). Batch files landing in S3 on a schedule is sufficient for daily-batch freshness requirements. |

## Consequences
- Adds one hop (S3) between source and warehouse versus loading directly.
  Worth it for the replayability and decoupling it buys, at negligible S3
  storage cost with a lifecycle policy to Glacier for anything older than
  the active retention window.
