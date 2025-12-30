"""PKM service - orchestrates Firebase + Qdrant + AI.

High-level service layer for Personal Knowledge Management that:
- Classifies content using LLM
- Stores in Firebase (source of truth)
- Generates embeddings and stores in Qdrant (search index)
- Provides semantic search and organization suggestions
"""
import json
from typing import Dict, List, Optional

from src.utils.logging import get_logger
from src.services.firebase.pkm import (
    PKMItem, create_item, get_item, update_item,
    list_items, get_inbox, get_tasks
)
from src.services.qdrant import store_pkm_item, search_pkm_items
from src.services.embeddings import get_embedding, get_query_embedding
from src.services.llm import get_llm_client

logger = get_logger()

CLASSIFICATION_PROMPT = """Analyze this item and classify it.

Item: {content}

Return JSON:
{{
  "type": "note|task|idea|link|quote",
  "tags": ["tag1", "tag2"],
  "priority": "low|medium|high" or null,
  "has_deadline": boolean
}}

Rules:
- "task" if action-oriented (do, fix, call, buy, etc.)
- "link" if contains URL
- "quote" if starts with quote marks or attribution
- "idea" if speculative/future-oriented
- "note" for everything else"""


async def classify_item(content: str) -> Dict:
    """Use LLM to classify content.

    Args:
        content: Item content to classify

    Returns:
        Dict with type, tags, priority, has_deadline
    """
    try:
        llm = get_llm_client()
        prompt = CLASSIFICATION_PROMPT.format(content=content)

        response = llm.chat(
            messages=[{"role": "user", "content": prompt}],
            system="You are a content classifier. Only output valid JSON, no explanation.",
            max_tokens=512,
            temperature=0.3,
        )

        # Parse JSON from response
        response_text = response.strip()
        if response_text.startswith("```"):
            # Remove markdown code block
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])

        result = json.loads(response_text)
        logger.info("content_classified", type=result.get("type"), tags=result.get("tags", []))
        return result

    except Exception as e:
        logger.error("classify_item_error", error=str(e)[:100])
        # Graceful fallback
        return {
            "type": "note",
            "tags": [],
            "priority": None,
            "has_deadline": False
        }


async def save_item(user_id: int, content: str, source: str = "telegram") -> PKMItem:
    """Save item with AI classification.

    Orchestrates:
    1. Classify content (type, tags, priority)
    2. Create item in Firebase
    3. Generate embedding
    4. Store in Qdrant

    Args:
        user_id: User ID
        content: Item content
        source: Source system (default: telegram)

    Returns:
        Created PKMItem
    """
    try:
        # Step 1: Classify content
        classification = await classify_item(content)

        # Step 2: Create in Firebase
        item = await create_item(
            user_id=user_id,
            content=content,
            item_type=classification.get("type", "note"),
            tags=classification.get("tags", []),
            priority=classification.get("priority"),
            source=source,
        )

        # Step 3: Generate embedding
        embedding = get_embedding(content)
        if not embedding:
            logger.warning("embedding_failed", user_id=user_id, item_id=item.id)
            return item

        # Step 4: Store in Qdrant
        stored = await store_pkm_item(
            user_id=user_id,
            item_id=item.id,
            content=content,
            embedding=embedding,
            item_type=item.type,
            status=item.status,
            tags=item.tags
        )

        if stored:
            logger.info("pkm_item_saved", user_id=user_id, item_id=item.id, type=item.type)
        else:
            logger.warning("qdrant_store_failed", user_id=user_id, item_id=item.id)

        return item

    except Exception as e:
        logger.error("save_item_error", error=str(e)[:100], user_id=user_id)
        raise


async def find_items(user_id: int, query: str, limit: int = 5) -> List[PKMItem]:
    """Find items by semantic search.

    Args:
        user_id: User ID
        query: Search query
        limit: Max results (default: 5)

    Returns:
        List of matching PKMItem instances
    """
    try:
        # Generate query embedding
        embedding = get_query_embedding(query)
        if not embedding:
            logger.warning("query_embedding_failed", user_id=user_id)
            # Fallback to recent inbox items
            return await get_inbox(user_id, limit=limit)

        # Search Qdrant
        results = await search_pkm_items(
            user_id=user_id,
            embedding=embedding,
            limit=limit
        )

        if not results:
            logger.info("no_search_results", user_id=user_id, query=query[:30])
            return []

        # Fetch full items from Firebase
        items = []
        for r in results:
            item_id = r.get("item_id")
            if item_id:
                item = await get_item(user_id, item_id)
                if item:
                    items.append(item)

        logger.info("items_found", user_id=user_id, count=len(items))
        return items

    except Exception as e:
        logger.error("find_items_error", error=str(e)[:100], user_id=user_id)
        return []


async def get_related_items(user_id: int, item_id: str, limit: int = 3) -> List[PKMItem]:
    """Find related items via semantic similarity.

    Args:
        user_id: User ID
        item_id: Source item ID
        limit: Max results (default: 3)

    Returns:
        List of related PKMItem instances
    """
    try:
        # Get source item
        item = await get_item(user_id, item_id)
        if not item:
            logger.warning("item_not_found", user_id=user_id, item_id=item_id)
            return []

        # Generate embedding for item content
        embedding = get_embedding(item.content)
        if not embedding:
            logger.warning("embedding_failed_for_related", user_id=user_id, item_id=item_id)
            return []

        # Search for similar items
        results = await search_pkm_items(
            user_id=user_id,
            embedding=embedding,
            limit=limit + 1  # +1 to exclude self
        )

        # Fetch full items, excluding the source item
        related = []
        for r in results:
            rid = r.get("item_id")
            if rid and rid != item_id:
                related_item = await get_item(user_id, rid)
                if related_item:
                    related.append(related_item)

        logger.info("related_items_found", user_id=user_id, item_id=item_id, count=len(related))
        return related[:limit]

    except Exception as e:
        logger.error("get_related_items_error", error=str(e)[:100], user_id=user_id)
        return []


async def suggest_organization(user_id: int, item: PKMItem) -> Dict:
    """Suggest project/tags based on similar items.

    Args:
        user_id: User ID
        item: PKMItem to organize

    Returns:
        Dict with suggested_project and suggested_tags
    """
    try:
        # Find related items
        related = await get_related_items(user_id, item.id, limit=5)

        if not related:
            return {
                "suggested_project": None,
                "suggested_tags": []
            }

        # Aggregate projects and tags from related items
        projects = {}
        tags_count = {}

        for r in related:
            if r.project:
                projects[r.project] = projects.get(r.project, 0) + 1
            for tag in r.tags:
                tags_count[tag] = tags_count.get(tag, 0) + 1

        # Pick most common project
        suggested_project = None
        if projects:
            suggested_project = max(projects, key=projects.get)

        # Pick top 3 most common tags
        suggested_tags = sorted(tags_count.keys(), key=lambda t: tags_count[t], reverse=True)[:3]

        logger.info("organization_suggested",
                   user_id=user_id,
                   item_id=item.id,
                   project=suggested_project,
                   tags=suggested_tags)

        return {
            "suggested_project": suggested_project,
            "suggested_tags": suggested_tags
        }

    except Exception as e:
        logger.error("suggest_organization_error", error=str(e)[:100], user_id=user_id)
        return {
            "suggested_project": None,
            "suggested_tags": []
        }
