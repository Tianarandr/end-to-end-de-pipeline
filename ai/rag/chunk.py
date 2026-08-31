"""Stage 2: chunking. Reviews are short (a sentence or two) so this is
just a pass-through today, one chunk per document. Kept as its own stage,
independent of prepare.py and embed.py, so a future document type that
needs real splitting (e.g. long-form restaurant policy docs) is a new
chunking strategy here, not a rewrite of the pipeline around it."""
from __future__ import annotations

from ai.rag.models import Chunk, Document


def chunk_documents(documents: list[Document]) -> list[Chunk]:
    return [
        Chunk(chunk_id=doc.doc_id, doc_id=doc.doc_id, text=doc.text, metadata=doc.metadata)
        for doc in documents
    ]
