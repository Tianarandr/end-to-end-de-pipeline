"""Stage 6: generation. Answers stay grounded in the retrieved chunks; the
model is told to say so rather than guess when the context doesn't cover
the question."""
from __future__ import annotations

from openai import OpenAI

from ai.rag.models import Answer, ScoredChunk

SYSTEM_PROMPT = (
    "Answer ONLY using the customer reviews provided. "
    "Be concise. If the reviews don't cover it, say so."
)


def generate(client: OpenAI, model: str, question: str, chunks: list[ScoredChunk]) -> Answer:
    context = "\n".join(
        f" ({c.chunk.metadata.get('city')}, {c.chunk.metadata.get('rating')} stars) {c.chunk.text}"
        for c in chunks
    )
    user_prompt = f"Question: {question}\n\nReviews:\n{context}"

    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    return Answer(text=response.choices[0].message.content, sources=chunks)
