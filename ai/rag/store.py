"""Stage 4: vector storage. `VectorStore` is a Protocol so a different
backend (pgvector, OpenSearch, a managed vector DB) can swap in later
behind the same interface instead of triggering a rewrite. See ADR-007's
"no dedicated vector database (yet)" reasoning. `ParquetVectorStore` is
what this project actually runs: a content-hash-cached embedding matrix on
local/mounted disk, searched by cosine similarity. That's fine at
review-corpus scale (thousands to low millions of rows, a handful of
interactive users), well short of approximate-nearest-neighbor-over-billions
scale, and that gap is a known trade-off, not an oversight.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd

from ai.rag.models import Chunk, EmbeddedChunk, ScoredChunk


class VectorStore(Protocol):
    def upsert(self, embedded_chunks: list[EmbeddedChunk]) -> None: ...
    def search(self, query_vector: list[float], k: int) -> list[ScoredChunk]: ...


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom else 0.0


class ParquetVectorStore:
    def __init__(self, cache_path: Path) -> None:
        self.cache_path = cache_path
        self._df: pd.DataFrame | None = None

    def _load(self) -> pd.DataFrame:
        if self._df is None:
            if self.cache_path.exists():
                self._df = pd.read_parquet(self.cache_path)
            else:
                self._df = pd.DataFrame(columns=["chunk_id", "doc_id", "text", "metadata", "vector"])
        return self._df

    def upsert(self, embedded_chunks: list[EmbeddedChunk]) -> None:
        df = self._load()
        rows = [
            {
                "chunk_id": ec.chunk.chunk_id,
                "doc_id": ec.chunk.doc_id,
                "text": ec.chunk.text,
                "metadata": ec.chunk.metadata,
                "vector": ec.vector,
            }
            for ec in embedded_chunks
        ]
        new_df = pd.DataFrame(rows)
        merged = pd.concat([df, new_df]).drop_duplicates(subset="chunk_id", keep="last")
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        merged.to_parquet(self.cache_path)
        self._df = merged

    def search(self, query_vector: list[float], k: int) -> list[ScoredChunk]:
        df = self._load()
        if df.empty:
            return []
        q = np.array(query_vector)
        scored = [
            ScoredChunk(
                chunk=Chunk(chunk_id=row.chunk_id, doc_id=row.doc_id, text=row.text, metadata=row.metadata),
                score=_cosine_similarity(q, np.array(row.vector)),
            )
            for row in df.itertuples()
        ]
        return sorted(scored, key=lambda s: s.score, reverse=True)[:k]
