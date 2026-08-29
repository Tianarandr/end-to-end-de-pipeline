# 04: AI Architecture

## Principle: AI sits *above* governed data, never beside it

Every AI capability in this repo reads from `SEMANTIC` (or, for the writer
path, from `STAGING`), never from `RAW`, and never with a role that can
write outside the `AI` schema. See
[ADR-006](../decisions/ADR-006-ai-above-governed-data.md) for why, and
[05-security.md](05-security.md) for the role grants that enforce it.

The AI layer is split into four clearly separated concerns, matching
`ai/`'s subpackages:

```
ai/
├── common/           # shared LLM client, Snowflake role-scoped connections, config
├── enrichment/        # A. Batch AI enrichment (writer)
├── rag/                # B. Retrieval / RAG (reader)
├── text_to_sql/         # C. Natural-language analytics (reader)
└── apps/                 # Streamlit UIs composing B and C
```

*(D. Future AI agents: see [Future agents](#d-future-ai-agents-not-built) below.)*

## A. Batch AI enrichment (`ai/enrichment/`)

Classifies review sentiment/topic/key-issue with an LLM. Redesigned from a
15-line script into a pipeline with:

- **Idempotent, resumable batches.** Selects reviews with no `SUCCEEDED` row
  in `AI.ENRICHMENT_LOG`, in batches of `AI_ENRICHMENT_BATCH_SIZE`. Re-running
  never re-classifies an already-succeeded review, and *can* reprocess a
  previously failed one on request (`--reprocess-failed`).
- **Structured output**, validated against a Pydantic schema before it's
  ever written to Snowflake (`schema.py`). A malformed LLM response fails
  loudly instead of writing garbage into `sentiment_score`.
- **Retries with backoff** (`tenacity`) on transient API errors; a review
  that still fails after `AI_ENRICHMENT_MAX_RETRIES` is logged with
  `status='FAILED'` and its `error_message`, never silently dropped.
- **Full traceability**: `model_name`, `model_version`, `prompt_version`
  (`prompts/review_classification_v1.py`), `processed_at`, and `batch_id`
  are stored on every row, in both the success table (`REVIEW_ENRICHED`)
  and the attempt log (`ENRICHMENT_LOG`). Bumping the prompt is a new
  `prompt_version`, not a silent behavior change.

## B. Retrieval / RAG (`ai/rag/`)

The original `rag_chat.py` did document loading, chunking (implicitly,
whole reviews), embedding, storage, retrieval, and generation all inline in
one Streamlit file. Split into single-purpose, independently-testable
modules with explicit interfaces so any one of them can be swapped later:

| Module | Responsibility | Interface |
|---|---|---|
| `prepare.py` | Pull reviews from `SEMANTIC.SEM_REVIEWS` (not `RAW`) | `load_documents() -> list[Document]` |
| `chunk.py` | Split documents into retrieval units | `chunk(documents) -> list[Chunk]` (pass-through for review-length text; ready for longer documents later) |
| `embed.py` | Turn chunks into vectors, with a content-hash cache | `embed(chunks) -> list[EmbeddedChunk]` |
| `store.py` | `VectorStore` protocol + `ParquetVectorStore` implementation | `upsert()`, `search(query_vector, k)` |
| `retrieve.py` | Embed the question, call the store, return top-k with scores | `retrieve(question, k) -> list[ScoredChunk]` |
| `generate.py` | Answer strictly grounded in retrieved context | `generate(question, chunks) -> Answer` |

**No vector database was introduced.** At this data volume (thousands to low
millions of reviews), a Parquet-cached embedding matrix with cosine
similarity is fewer moving parts, zero extra infrastructure cost, and fast
enough. `store.py` defines `VectorStore` as a `Protocol`; swapping in
pgvector/Pinecone/OpenSearch later is a new class behind the same interface,
not a rewrite. See
[ADR-007](../decisions/ADR-007-no-kafka-spark-k8s.md#no-dedicated-vector-database).

## C. Natural-language analytics / Text-to-SQL (`ai/text_to_sql/`)

The highest-risk AI capability in the repo: an LLM writing SQL that
actually executes, and the one with the most guardrails. See
[13-DATA-QUALITY / guardrail table below] and
[05-security.md](05-security.md#text-to-sql-guardrails) for the full list:

1. **Schema-aware, semantic-aware prompting.** The prompt is generated from
   `schema_registry.yml`, the same file the semantic layer's `metrics.yml`
   feeds, so the model is told about `SEM_REVENUE_DAILY.gross_merchandise_value`
   by its governed name and definition instead of inventing "GMV" itself.
2. **Schema/table allowlist.** Only views under `SEMANTIC` are ever named in
   the prompt or accepted in the generated SQL.
3. **Static validation before execution** (`guardrails.py`, via `sqlglot`):
   single statement, `SELECT`/`WITH` only, every referenced table is on the
   allowlist, no disallowed constructs (DDL/DML/`COPY`/`CALL`/UDF calls/
   multi-statement `;`-chaining), and a `LIMIT` is enforced/injected.
4. **Execution guardrails**: runs under `AI_READONLY_ROLE`
   (`SELECT`-only grant on `SEMANTIC`), with a session
   `STATEMENT_TIMEOUT_IN_SECONDS` and a hard row cap.
5. **Clear failure modes**: a query that fails validation is never sent to
   Snowflake at all, and the user sees *why* (which rule it broke).

## D. Future AI agents (not built)

Out of scope for this repo for now (see the "no over-engineering" principle
in the top-level README), but the architecture is ready for it: an agent
would be composed from the same building blocks: `ai/text_to_sql` and
`ai/rag` as callable tools, `SEMANTIC` as its only data surface, and
`ai/common` for the shared LLM client/guardrail patterns. No new
data-access pattern would be needed.
