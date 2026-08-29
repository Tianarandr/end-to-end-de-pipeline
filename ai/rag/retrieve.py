"""Stage 5: retrieval. Embeds the question, asks the VectorStore for the
top-k, hands back scored chunks. Nothing here knows or cares whether the
store is the Parquet implementation or something else."""
from __future__ import annotations

from openai import OpenAI

from ai.rag.models import ScoredChunk
from ai.rag.store import VectorStore


def retrieve(client: OpenAI, model: str, question: str, store: VectorStore, k: int) -> list[ScoredChunk]:
    query_vector = client.embeddings.create(input=[question], model=model).data[0].embedding
    return store.search(query_vector, k)
