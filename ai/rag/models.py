"""Shared types across the RAG pipeline stages."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    doc_id: str          # review_id
    text: str             # comment
    metadata: dict          # city, rating, review_date: whatever generate.py needs for grounding/citation


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    metadata: dict


@dataclass(frozen=True)
class EmbeddedChunk:
    chunk: Chunk
    vector: list[float]


@dataclass(frozen=True)
class ScoredChunk:
    chunk: Chunk
    score: float


@dataclass(frozen=True)
class Answer:
    text: str
    sources: list[ScoredChunk]
