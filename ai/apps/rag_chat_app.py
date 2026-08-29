"""Streamlit RAG chat over customer reviews. Thin composition of
ai/rag/*.py's stages: no pipeline logic lives here, just UI wiring. Run
with `make rag` or `streamlit run ai/apps/rag_chat_app.py`."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from ai.common.config import load_settings
from ai.common.llm_client import get_client
from ai.rag.chunk import chunk_documents
from ai.rag.embed import embed_chunks
from ai.rag.generate import generate
from ai.rag.prepare import load_documents
from ai.rag.retrieve import retrieve
from ai.rag.store import ParquetVectorStore

SAMPLE_SIZE = 500
TOP_K = 5
CACHE_PATH = Path(__file__).parent.parent / "rag" / ".cache" / "review_embeddings.parquet"

st.title("Chat with your Customer Reviews")
st.caption(f"Retrieval-augmented over a sample of {SAMPLE_SIZE} reviews from SEMANTIC.SEM_REVIEWS")


@st.cache_resource
def get_store() -> ParquetVectorStore:
    settings = load_settings()
    client = get_client(settings)
    store = ParquetVectorStore(CACHE_PATH)

    if not CACHE_PATH.exists():
        documents = load_documents(settings, SAMPLE_SIZE)
        chunks = chunk_documents(documents)
        embedded = embed_chunks(client, settings.ai_embedding_model, chunks, cache={})
        store.upsert(embedded)

    return store


settings = load_settings()
client = get_client(settings)
store = get_store()

question = st.text_input(
    "Ask a question about your reviews:",
    placeholder="What are the most common complaints about pricing?",
)

if question:
    scored_chunks = retrieve(client, settings.ai_embedding_model, question, store, TOP_K)
    answer = generate(client, settings.ai_chat_model, question, scored_chunks)

    st.markdown("**Answer:**")
    st.write(answer.text)

    with st.expander("Reviews used to build this answer"):
        for sc in answer.sources:
            st.markdown(f"- ({sc.chunk.metadata.get('city')}, {sc.chunk.metadata.get('rating')}★, score={sc.score:.3f}) {sc.chunk.text}")
