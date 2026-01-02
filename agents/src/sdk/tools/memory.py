"""Memory search tool (migrated from src/tools/memory_search.py)."""

from claude_agents import tool
from typing import List, Dict
import structlog

logger = structlog.get_logger()


@tool
async def search_memory(
    user_id: int,
    query: str,
    limit: int = 5,
) -> List[Dict]:
    """Search user's memory/PKM for relevant information.

    Args:
        user_id: User's Telegram ID
        query: Semantic search query
        limit: Max results (default: 5)

    Returns:
        Matching memories with content and metadata
    """
    from src.services.qdrant import get_text_embedding, search_pkm_items

    # Get embedding for query
    embedding = await get_text_embedding(query, for_query=True)
    if not embedding:
        logger.warning("embedding_failed", query=query[:30])
        return []

    # Search PKM items
    results = await search_pkm_items(
        user_id=user_id,
        embedding=embedding,
        limit=limit,
        status_filter="active"
    )

    return [
        {
            "content": r.get("content_preview", ""),
            "type": r.get("type", ""),
            "tags": r.get("tags", []),
            "score": r.get("score", 0.0)
        }
        for r in results
    ]
