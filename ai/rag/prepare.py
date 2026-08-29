"""Stage 1: document preparation. Pulls reviews from SEMANTIC.SEM_REVIEWS
only (never STAGING or RAW), via AI_READONLY_ROLE. See ADR-006."""
from __future__ import annotations

from ai.common.config import AISettings
from ai.common.snowflake_client import get_ai_readonly_connection
from ai.rag.models import Document


def load_documents(settings: AISettings, sample_size: int) -> list[Document]:
    connection = get_ai_readonly_connection(settings)
    query = f"""
        SELECT review_id, city, rating, comment, review_date
        FROM SEMANTIC.SEM_REVIEWS
        SAMPLE ({int(sample_size)} ROWS)
    """
    df = connection.cursor().execute(query).fetch_pandas_all()
    connection.close()
    df.columns = [c.lower() for c in df.columns]

    return [
        Document(
            doc_id=str(row.review_id),
            text=row.comment,
            metadata={"city": row.city, "rating": row.rating, "review_date": str(row.review_date)},
        )
        for row in df.itertuples()
    ]
