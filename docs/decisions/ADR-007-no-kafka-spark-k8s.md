# ADR-007: Do not introduce Kafka, Spark, Kubernetes, Databricks, or a dedicated vector database

## Status
Accepted

## Context
It's tempting to make a portfolio/reference architecture "look more
enterprise" by adding well-known big-data tools. Each of the tools below was
considered and turned down, not out of unfamiliarity but because none of
them solves a problem this platform actually has at its actual scale
(tens of millions of rows, daily-batch freshness, a small team).

## Decision and reasoning, per tool

### Kafka / a streaming platform
**Problem it solves:** sub-minute-latency event delivery, high-throughput
pub/sub decoupling between many producers and consumers.
**Problem this project has:** daily-batch source extracts. Nothing in the
business requirements (revenue reporting, review enrichment, delivery SLA)
needs sub-minute freshness. Introducing Kafka would mean operating a
distributed log, consumer group management, and schema registry for a
throughput this project will not reach.
**Revisit when:** a real requirement for near-real-time freshness appears
(e.g. live order tracking), and even then, evaluate managed
Kinesis/MSK/Confluent Cloud before self-hosting.

### Spark
**Problem it solves:** distributed transformation over datasets too large
for a single warehouse query or that need custom distributed compute logic.
**Problem this project has:** every transformation here is expressible as
SQL over a dataset Snowflake's own compute handles natively (and scales
by warehouse size, not cluster management). Spark would duplicate
Snowflake's job while adding a cluster to operate.
**Revisit when:** transformation logic that genuinely can't be SQL (complex
ML feature engineering at scale, non-tabular processing) appears.

### Kubernetes
**Problem it solves:** orchestrating many independently-scaled
containerized services.
**Problem this project has:** a handful of services (Airflow, Postgres,
Streamlit apps) that run comfortably on Docker Compose on a single host.
Kubernetes would add cluster provisioning, networking, and manifests to
maintain for services that don't need independent horizontal scaling.
**Revisit when:** the number of independently-deployed services grows
enough that Compose's single-host model is the actual bottleneck, likely
alongside a move to managed Airflow anyway.

### Databricks
**Problem it solves:** a unified Spark + lakehouse + ML platform.
**Problem this project has:** SQL transformation (solved by
Snowflake+dbt) and light LLM API calls (solved by direct OpenAI SDK calls).
Neither needs a lakehouse compute platform. Running both Databricks and
Snowflake would be two warehouses to pay for and reconcile.

### A dedicated vector database (pgvector/Pinecone/Weaviate/OpenSearch)
**Problem it solves:** low-latency approximate nearest-neighbor search over
millions-billions of vectors, with metadata filtering, at query volumes a
flat scan can't serve.
**Problem this project has:** retrieval over thousands to low millions of
review embeddings for a handful of interactive Streamlit users. A
content-hash-cached embedding matrix with cosine similarity
(`ai/rag/store.py`'s `ParquetVectorStore`) answers a query in milliseconds
at this scale, with zero extra infrastructure. `VectorStore` is defined as
a `Protocol` so this is a same-interface swap, not a rewrite, when/if scale
demands it. See
[04-ai-architecture.md](../architecture/04-ai-architecture.md#b-retrieval--rag-airag).
**Revisit when:** embedding volume or query concurrency actually makes a
flat scan too slow (a measurable trigger, not a guess).

## Consequences
Every one of these is a legitimate, well-built tool, just for a different
scale of problem. Adopting any of them here would trade real operational
complexity (clusters, schema registries, cross-system reconciliation) for
no measurable benefit, which is precisely the "impressive but unjustified"
failure mode this ADR exists to avoid. The trade-off table in the top-level
README's "what would change at larger scale" section names the concrete
trigger for reconsidering each one.
