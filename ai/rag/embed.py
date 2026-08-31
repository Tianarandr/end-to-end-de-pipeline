"""Stage 3: embedding generation, with a content-hash cache so re-running
the pipeline never re-embeds a chunk whose text hasn't changed. Same
idempotency principle as ingestion and enrichment, just applied to embeddings."""
from __future__ import annotations

import hashlib

from openai import OpenAI

from ai.rag.models import Chunk, EmbeddedChunk


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def embed_chunks(client: OpenAI, model: str, chunks: list[Chunk], cache: dict[str, list[float]]) -> list[EmbeddedChunk]:
    to_embed = [c for c in chunks if content_hash(c.text) not in cache]

    if to_embed:
        response = client.embeddings.create(input=[c.text for c in to_embed], model=model)
        for chunk, item in zip(to_embed, response.data, strict=False):
            cache[content_hash(chunk.text)] = item.embedding

    return [EmbeddedChunk(chunk=c, vector=cache[content_hash(c.text)]) for c in chunks]
