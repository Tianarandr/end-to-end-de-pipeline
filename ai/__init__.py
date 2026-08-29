"""The AI layer, split into four pieces (see docs/architecture/04-ai-architecture.md):

  ai/enrichment/   batch AI enrichment (writer, reads STAGING, writes AI schema)
  ai/rag/          retrieval-augmented generation over reviews (reader, SEMANTIC only)
  ai/text_to_sql/  natural-language analytics with guardrails (reader, SEMANTIC only)
  ai/apps/         Streamlit UIs composing rag/ and text_to_sql/
  ai/common/       shared LLM client, role-scoped Snowflake connections, config

Every reader here is granted SELECT on SEMANTIC only, never RAW/STAGING/MARTS.
See ADR-006 and docs/architecture/05-security.md.
"""
