"""Qdrant Cloud vector memory service.

II Framework Integration:
- Derived index (rebuildable from Firebase)
- Semantic skill routing
- Cross-skill knowledge search
- Fallback to Firebase keyword search
"""
from typing import List, Dict, Optional, Any
import os
from datetime import datetime

from src.utils.logging import get_logger
from src.core.resilience import qdrant_circuit, CircuitOpenError

logger = get_logger()

# Qdrant Cloud client
_client = None
_enabled = False

VECTOR_DIM = 3072  # Gemini gemini-embedding-001 dimension

# Collection names
COLLECTIONS = {
    "skills": "Semantic skill matching for routing",
    "knowledge": "Cross-skill insights and learnings",
    "conversations": "Chat history for context",
    "errors": "Error pattern matching",
    "tasks": "Task context for similar task lookup",
    "user_activities": "User activity patterns for learning",
    "pkm_items": "Personal Knowledge Management items",
}


def is_enabled() -> bool:
    """Check if Qdrant is configured."""
    return bool(os.environ.get("QDRANT_URL") and os.environ.get("QDRANT_API_KEY"))


def get_client():
    """Get Qdrant Cloud client."""
    global _client, _enabled

    if not is_enabled():
        logger.warning("qdrant_not_configured")
        return None

    if _client is None:
        from qdrant_client import QdrantClient
        _client = QdrantClient(
            url=os.environ["QDRANT_URL"],
            api_key=os.environ["QDRANT_API_KEY"],
        )
        _enabled = True
        logger.info("qdrant_connected", url=os.environ["QDRANT_URL"][:30] + "...")

    return _client


def init_collections():
    """Initialize all collections if they don't exist."""
    client = get_client()
    if not client:
        return {"status": "skipped", "reason": "Qdrant not configured"}

    from qdrant_client.http import models

    collections = ["conversations", "knowledge", "tasks", "user_activities", "pkm_items"]
    created = []

    for name in collections:
        try:
            client.get_collection(name)
        except Exception:
            client.create_collection(
                collection_name=name,
                vectors_config=models.VectorParams(
                    size=VECTOR_DIM,
                    distance=models.Distance.COSINE
                )
            )
            created.append(name)

    return {"status": "initialized", "created": created}


# ==================== Conversations ====================

async def store_conversation(
    user_id: str,
    agent: str,
    role: str,
    content: str,
    embedding: List[float]
) -> Optional[str]:
    """Store a conversation message with embedding."""
    client = get_client()
    if not client:
        return None

    from qdrant_client.http import models

    point_id = f"{user_id}_{datetime.utcnow().timestamp()}"

    client.upsert(
        collection_name="conversations",
        points=[
            models.PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "user_id": user_id,
                    "agent": agent,
                    "role": role,
                    "content": content,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        ]
    )

    return point_id


async def search_conversations(
    embedding: List[float],
    user_id: Optional[str] = None,
    limit: int = 5
) -> List[Dict]:
    """Search similar conversations."""
    client = get_client()
    if not client:
        return []

    async def _search_internal():
        from qdrant_client.http import models

        filter_conditions = None
        if user_id:
            filter_conditions = models.Filter(
                must=[
                    models.FieldCondition(
                        key="user_id",
                        match=models.MatchValue(value=user_id)
                    )
                ]
            )

        results = client.search(
            collection_name="conversations",
            query_vector=embedding,
            query_filter=filter_conditions,
            limit=limit
        )

        return [
            {
                "id": r.id,
                "score": r.score,
                **r.payload
            }
            for r in results
        ]

    try:
        return await qdrant_circuit.call(_search_internal, timeout=15.0)
    except CircuitOpenError:
        logger.warning("qdrant_circuit_open", operation="search_conversations")
        return []
    except Exception as e:
        logger.error("qdrant_search_error", error=str(e)[:50])
        return []


# ==================== Knowledge ====================

async def store_knowledge(
    source: str,
    topic: str,
    content: str,
    embedding: List[float]
) -> Optional[str]:
    """Store knowledge with embedding."""
    client = get_client()
    if not client:
        return None

    from qdrant_client.http import models

    point_id = f"kb_{datetime.utcnow().timestamp()}"

    client.upsert(
        collection_name="knowledge",
        points=[
            models.PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "source": source,
                    "topic": topic,
                    "content": content,
                    "created_at": datetime.utcnow().isoformat()
                }
            )
        ]
    )

    return point_id


async def search_knowledge(
    embedding: List[float],
    topic: Optional[str] = None,
    limit: int = 5
) -> List[Dict]:
    """Search knowledge base."""
    client = get_client()
    if not client:
        return []

    async def _search_internal():
        from qdrant_client.http import models

        filter_conditions = None
        if topic:
            filter_conditions = models.Filter(
                must=[
                    models.FieldCondition(
                        key="topic",
                        match=models.MatchValue(value=topic)
                    )
                ]
            )

        results = client.search(
            collection_name="knowledge",
            query_vector=embedding,
            query_filter=filter_conditions,
            limit=limit
        )

        return [
            {
                "id": r.id,
                "score": r.score,
                **r.payload
            }
            for r in results
        ]

    try:
        return await qdrant_circuit.call(_search_internal, timeout=15.0)
    except CircuitOpenError:
        logger.warning("qdrant_circuit_open", operation="search_knowledge")
        return []
    except Exception as e:
        logger.error("qdrant_search_knowledge_error", error=str(e)[:50])
        return []


# ==================== Tasks ====================

async def store_task_context(
    task_id: str,
    task_type: str,
    summary: str,
    result: Dict,
    embedding: List[float]
) -> None:
    """Store task result for future reference."""
    client = get_client()
    if not client:
        return

    from qdrant_client.http import models

    client.upsert(
        collection_name="tasks",
        points=[
            models.PointStruct(
                id=task_id,
                vector=embedding,
                payload={
                    "task_id": task_id,
                    "type": task_type,
                    "summary": summary,
                    "result": result,
                    "created_at": datetime.utcnow().isoformat()
                }
            )
        ]
    )


async def search_similar_tasks(
    embedding: List[float],
    task_type: Optional[str] = None,
    limit: int = 3
) -> List[Dict]:
    """Find similar past tasks."""
    client = get_client()
    if not client:
        return []

    from qdrant_client.http import models

    filter_conditions = None
    if task_type:
        filter_conditions = models.Filter(
            must=[
                models.FieldCondition(
                    key="type",
                    match=models.MatchValue(value=task_type)
                )
            ]
        )

    results = client.search(
        collection_name="tasks",
        query_vector=embedding,
        query_filter=filter_conditions,
        limit=limit
    )

    return [
        {
            "id": r.id,
            "score": r.score,
            **r.payload
        }
        for r in results
    ]


# ==================== Skills Collection (for Routing) ====================

async def store_skill(
    skill_id: str,
    name: str,
    description: str,
    embedding: List[float],
    category: Optional[str] = None
) -> None:
    """Store skill for semantic routing."""
    client = get_client()
    if not client:
        return

    from qdrant_client.http import models

    client.upsert(
        collection_name="skills",
        points=[
            models.PointStruct(
                id=skill_id,
                vector=embedding,
                payload={
                    "name": name,
                    "description": description,
                    "category": category,
                    "firebase_ref": f"skills/{skill_id}",
                    "updated_at": datetime.utcnow().isoformat()
                }
            )
        ]
    )


async def search_skills(
    embedding: List[float],
    limit: int = 3,
    category: Optional[str] = None
) -> List[Dict]:
    """Find matching skills for routing."""
    client = get_client()
    if not client:
        return []

    from qdrant_client.http import models

    filter_conditions = None
    if category:
        filter_conditions = models.Filter(
            must=[
                models.FieldCondition(
                    key="category",
                    match=models.MatchValue(value=category)
                )
            ]
        )

    results = client.search(
        collection_name="skills",
        query_vector=embedding,
        query_filter=filter_conditions,
        limit=limit
    )

    return [
        {
            "id": r.id,
            "score": r.score,
            **r.payload
        }
        for r in results
    ]


# ==================== Errors Collection ====================

async def store_error_pattern(
    error_id: str,
    error_description: str,
    solution: str,
    embedding: List[float],
    source_skill: str
) -> None:
    """Store error pattern for matching."""
    client = get_client()
    if not client:
        return

    from qdrant_client.http import models

    client.upsert(
        collection_name="errors",
        points=[
            models.PointStruct(
                id=error_id,
                vector=embedding,
                payload={
                    "description": error_description,
                    "solution": solution,
                    "source_skill": source_skill,
                    "firebase_ref": f"errors/{error_id}",
                    "created_at": datetime.utcnow().isoformat()
                }
            )
        ]
    )


async def search_error_patterns(
    embedding: List[float],
    limit: int = 3
) -> List[Dict]:
    """Find similar error patterns."""
    client = get_client()
    if not client:
        return []

    results = client.search(
        collection_name="errors",
        query_vector=embedding,
        limit=limit
    )

    return [
        {
            "id": r.id,
            "score": r.score,
            **r.payload
        }
        for r in results
    ]


# ==================== Rebuild from Firebase ====================

async def rebuild_from_firebase() -> Dict[str, int]:
    """Rebuild all Qdrant collections from Firebase.

    This is the disaster recovery function - Qdrant is derived,
    Firebase is the source of truth.

    Returns:
        Dict with counts per collection rebuilt
    """
    from src.services.firebase import get_db
    from src.services.embeddings import get_embedding

    client = get_client()
    if not client:
        return {"status": "skipped", "reason": "Qdrant not configured"}

    from qdrant_client.http import models

    counts = {"skills": 0, "knowledge": 0, "errors": 0}
    db = get_db()

    # Rebuild skills collection
    try:
        skills = db.collection("skills").get()
        for skill in skills:
            data = skill.to_dict()
            desc = data.get("description", data.get("name", ""))
            if desc:
                embedding = get_embedding(desc)
                client.upsert(
                    collection_name="skills",
                    points=[
                        models.PointStruct(
                            id=skill.id,
                            vector=embedding,
                            payload={
                                "name": data.get("name", skill.id),
                                "description": desc,
                                "firebase_ref": f"skills/{skill.id}"
                            }
                        )
                    ]
                )
                counts["skills"] += 1
    except Exception as e:
        logger.error("rebuild_skills_error", error=str(e))

    # Rebuild knowledge from decisions
    try:
        decisions = db.collection("decisions") \
            .where("valid_until", "==", None) \
            .get()

        for dec in decisions:
            data = dec.to_dict()
            text = f"{data.get('condition', '')} {data.get('action', '')}"
            if text.strip():
                embedding = get_embedding(text)
                client.upsert(
                    collection_name="knowledge",
                    points=[
                        models.PointStruct(
                            id=dec.id,
                            vector=embedding,
                            payload={
                                "type": "decision",
                                "condition": data.get("condition"),
                                "action": data.get("action"),
                                "confidence": data.get("confidence"),
                                "firebase_ref": f"decisions/{dec.id}"
                            }
                        )
                    ]
                )
                counts["knowledge"] += 1
    except Exception as e:
        logger.error("rebuild_knowledge_error", error=str(e))

    logger.info("qdrant_rebuilt", counts=counts)
    return counts


# ==================== Search with Firebase Fallback ====================

async def search_with_fallback(
    collection: str,
    embedding: List[float],
    query_text: str,
    limit: int = 5
) -> List[Dict]:
    """Search Qdrant with Firebase keyword fallback.

    Args:
        collection: Qdrant collection name
        embedding: Query embedding
        query_text: Original query text (for fallback)
        limit: Max results

    Returns:
        Search results from Qdrant or Firebase fallback
    """
    client = get_client()

    # Try Qdrant first
    if client:
        try:
            results = client.search(
                collection_name=collection,
                query_vector=embedding,
                limit=limit
            )

            if results:
                return [
                    {
                        "id": r.id,
                        "score": r.score,
                        "source": "qdrant",
                        **r.payload
                    }
                    for r in results
                ]
        except Exception as e:
            logger.warning("qdrant_search_failed", error=str(e))

    # Fallback to Firebase keyword search
    logger.info("using_firebase_fallback", collection=collection)

    from src.services.firebase import keyword_search

    # Map collection to Firebase collection
    firebase_collection = {
        "knowledge": "decisions",
        "skills": "skills",
        "errors": "logs",
    }.get(collection, collection)

    keywords = query_text.lower().split()
    results = await keyword_search(firebase_collection, keywords, limit)

    return [
        {**r, "source": "firebase_fallback"}
        for r in results
    ]


# ==================== Health Check ====================

def health_check() -> Dict[str, Any]:
    """Check Qdrant availability and collection status."""
    client = get_client()
    if not client:
        return {"status": "disabled", "reason": "Not configured"}

    try:
        collections = client.get_collections()
        collection_names = [c.name for c in collections.collections]

        missing = [
            name for name in COLLECTIONS.keys()
            if name not in collection_names
        ]

        return {
            "status": "healthy" if not missing else "degraded",
            "collections": collection_names,
            "missing": missing
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ==================== User Activities ====================

async def store_user_activity(
    user_id: int,
    action_type: str,
    summary: str,
    embedding: List[float],
    skill: Optional[str] = None,
    duration_ms: int = 0
) -> Optional[str]:
    """Store user activity for pattern learning."""
    client = get_client()
    if not client:
        return None

    from qdrant_client.http import models

    point_id = f"{user_id}_{datetime.utcnow().timestamp()}"

    try:
        client.upsert(
            collection_name="user_activities",
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "user_id": user_id,
                        "action_type": action_type,
                        "skill": skill,
                        "summary": summary,
                        "timestamp": datetime.utcnow().isoformat(),
                        "hour_of_day": datetime.utcnow().hour,
                        "day_of_week": datetime.utcnow().weekday(),
                        "duration_ms": duration_ms
                    }
                )
            ]
        )
        return point_id
    except Exception as e:
        logger.error("store_user_activity_error", error=str(e)[:50])
        return None


async def search_user_activities(
    user_id: int,
    embedding: List[float],
    limit: int = 5
) -> List[Dict]:
    """Search user's past activities."""
    client = get_client()
    if not client:
        return []

    from qdrant_client.http import models

    try:
        filter_conditions = models.Filter(
            must=[
                models.FieldCondition(
                    key="user_id",
                    match=models.MatchValue(value=user_id)
                )
            ]
        )

        results = client.search(
            collection_name="user_activities",
            query_vector=embedding,
            query_filter=filter_conditions,
            limit=limit
        )

        return [
            {
                "id": r.id,
                "score": r.score,
                **r.payload
            }
            for r in results
        ]
    except Exception as e:
        logger.error("search_user_activities_error", error=str(e)[:50])
        return []


# ==================== FAQ Semantic Search ====================

FAQ_COLLECTION = "faq_embeddings"


def ensure_faq_collection():
    """Create FAQ collection if not exists."""
    client = get_client()
    if not client:
        return False

    from qdrant_client.http import models

    try:
        client.get_collection(FAQ_COLLECTION)
        return True
    except Exception:
        try:
            client.create_collection(
                collection_name=FAQ_COLLECTION,
                vectors_config=models.VectorParams(
                    size=VECTOR_DIM,
                    distance=models.Distance.COSINE
                )
            )
            logger.info("faq_collection_created")
            return True
        except Exception as e:
            logger.error("faq_collection_error", error=str(e)[:50])
            return False


async def upsert_faq_embedding(faq_id: str, embedding: List[float], answer: str) -> bool:
    """Upsert FAQ entry embedding to Qdrant."""
    client = get_client()
    if not client:
        return False

    ensure_faq_collection()

    from qdrant_client.http import models

    try:
        # Use stable int ID from faq_id hash
        point_id = abs(hash(faq_id)) % (2**63)

        client.upsert(
            collection_name=FAQ_COLLECTION,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "faq_id": faq_id,
                        "answer": answer
                    }
                )
            ]
        )
        logger.debug("faq_embedding_upserted", faq_id=faq_id)
        return True
    except Exception as e:
        logger.error("upsert_faq_embedding_error", error=str(e)[:50])
        return False


async def search_faq_embedding(embedding: List[float], threshold: float = 0.9) -> Optional[Dict]:
    """Search FAQ by embedding, return match if above threshold."""
    client = get_client()
    if not client:
        return None

    ensure_faq_collection()

    try:
        results = client.search(
            collection_name=FAQ_COLLECTION,
            query_vector=embedding,
            limit=1,
            score_threshold=threshold
        )

        if results:
            return {
                "faq_id": results[0].payload.get("faq_id"),
                "answer": results[0].payload.get("answer"),
                "score": results[0].score
            }
        return None
    except Exception as e:
        logger.error("search_faq_embedding_error", error=str(e)[:50])
        return None


async def delete_faq_embedding(faq_id: str) -> bool:
    """Delete FAQ embedding by ID."""
    client = get_client()
    if not client:
        return False

    from qdrant_client.http import models

    try:
        point_id = abs(hash(faq_id)) % (2**63)
        client.delete(
            collection_name=FAQ_COLLECTION,
            points_selector=models.PointIdsList(points=[point_id])
        )
        logger.debug("faq_embedding_deleted", faq_id=faq_id)
        return True
    except Exception as e:
        logger.error("delete_faq_embedding_error", error=str(e)[:50])
        return False


async def get_text_embedding(text: str, for_query: bool = False) -> Optional[List[float]]:
    """Get embedding for text using Gemini embedding service.

    Args:
        text: Text to embed
        for_query: If True, uses RETRIEVAL_QUERY task type (for searches).
                   If False, uses RETRIEVAL_DOCUMENT task type (for storage).
    """
    try:
        if for_query:
            from src.services.embeddings import get_query_embedding
            return get_query_embedding(text)
        else:
            from src.services.embeddings import get_embedding
            return get_embedding(text)
    except Exception as e:
        logger.error("get_text_embedding_error", error=str(e)[:50])
        return None


# ==================== PKM Collection ====================

PKM_COLLECTION = "pkm_items"


def ensure_pkm_collection():
    """Create PKM collection if not exists.

    Vector size: 3072 (Gemini embedding dimension)
    """
    client = get_client()
    if not client:
        return False

    from qdrant_client.http import models

    try:
        client.get_collection(PKM_COLLECTION)
        return True
    except Exception:
        try:
            client.create_collection(
                collection_name=PKM_COLLECTION,
                vectors_config=models.VectorParams(
                    size=VECTOR_DIM,
                    distance=models.Distance.COSINE
                )
            )
            logger.info("pkm_collection_created")
            return True
        except Exception as e:
            logger.error("pkm_collection_error", error=str(e)[:50])
            return False


async def store_pkm_item(
    user_id: int,
    item_id: str,
    content: str,
    embedding: List[float],
    item_type: str,
    status: str,
    tags: List[str]
) -> bool:
    """Store PKM item embedding in Qdrant.

    ID format: pkm_{user_id}_{item_id}
    Payload: user_id, item_id, type, status, tags, content_preview (200 chars)

    Args:
        user_id: User ID
        item_id: Unique item ID from Firebase
        content: Full item content
        embedding: Gemini embedding vector (3072 dims)
        item_type: Item type (note, task, idea, learning)
        status: Status (active, archived, deleted)
        tags: List of tags

    Returns:
        True if successful, False otherwise
    """
    client = get_client()
    if not client:
        return False

    ensure_pkm_collection()

    from qdrant_client.http import models

    try:
        # Stable point ID from user_id + item_id
        point_key = f"pkm_{user_id}_{item_id}"
        point_id = abs(hash(point_key)) % (2**63)

        # Content preview (first 200 chars)
        content_preview = content[:200] if len(content) > 200 else content

        client.upsert(
            collection_name=PKM_COLLECTION,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "user_id": user_id,
                        "item_id": item_id,
                        "type": item_type,
                        "status": status,
                        "tags": tags,
                        "content_preview": content_preview,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                )
            ]
        )
        logger.debug("pkm_item_stored", user_id=user_id, item_id=item_id)
        return True
    except Exception as e:
        logger.error("store_pkm_item_error", error=str(e)[:50], user_id=user_id)
        return False


async def search_pkm_items(
    user_id: int,
    embedding: List[float],
    limit: int = 5,
    status_filter: Optional[str] = None,
    type_filter: Optional[str] = None
) -> List[Dict]:
    """Search user's PKM items by embedding.

    Filter by user_id (required), optionally by status/type.

    Args:
        user_id: User ID (required filter)
        embedding: Query embedding vector
        limit: Max results to return
        status_filter: Optional status filter (active, archived, deleted)
        type_filter: Optional type filter (note, task, idea, learning)

    Returns:
        List of {item_id, score, type, status, tags, content_preview}
    """
    client = get_client()
    if not client:
        return []

    ensure_pkm_collection()

    from qdrant_client.http import models

    async def _search_internal():
        # Build filter conditions
        filter_must = [
            models.FieldCondition(
                key="user_id",
                match=models.MatchValue(value=user_id)
            )
        ]

        if status_filter:
            filter_must.append(
                models.FieldCondition(
                    key="status",
                    match=models.MatchValue(value=status_filter)
                )
            )

        if type_filter:
            filter_must.append(
                models.FieldCondition(
                    key="type",
                    match=models.MatchValue(value=type_filter)
                )
            )

        filter_conditions = models.Filter(must=filter_must)

        results = client.search(
            collection_name=PKM_COLLECTION,
            query_vector=embedding,
            query_filter=filter_conditions,
            limit=limit
        )

        return [
            {
                "item_id": r.payload.get("item_id"),
                "score": r.score,
                "type": r.payload.get("type"),
                "status": r.payload.get("status"),
                "tags": r.payload.get("tags", []),
                "content_preview": r.payload.get("content_preview")
            }
            for r in results
        ]

    try:
        return await qdrant_circuit.call(_search_internal, timeout=15.0)
    except CircuitOpenError:
        logger.warning("qdrant_circuit_open", operation="search_pkm_items")
        return []
    except Exception as e:
        logger.error("search_pkm_items_error", error=str(e)[:50], user_id=user_id)
        return []


async def delete_pkm_item(user_id: int, item_id: str) -> bool:
    """Delete PKM item from Qdrant.

    Args:
        user_id: User ID
        item_id: Item ID to delete

    Returns:
        True if successful, False otherwise
    """
    client = get_client()
    if not client:
        return False

    from qdrant_client.http import models

    try:
        point_key = f"pkm_{user_id}_{item_id}"
        point_id = abs(hash(point_key)) % (2**63)

        client.delete(
            collection_name=PKM_COLLECTION,
            points_selector=models.PointIdsList(points=[point_id])
        )
        logger.debug("pkm_item_deleted", user_id=user_id, item_id=item_id)
        return True
    except Exception as e:
        logger.error("delete_pkm_item_error", error=str(e)[:50], user_id=user_id)
        return False


async def update_pkm_item_status(user_id: int, item_id: str, new_status: str) -> bool:
    """Update item status in Qdrant payload.

    Uses set_payload to update only the status field without re-embedding.

    Args:
        user_id: User ID
        item_id: Item ID
        new_status: New status value (active, archived, deleted)

    Returns:
        True if successful, False otherwise
    """
    client = get_client()
    if not client:
        return False

    from qdrant_client.http import models

    try:
        point_key = f"pkm_{user_id}_{item_id}"
        point_id = abs(hash(point_key)) % (2**63)

        client.set_payload(
            collection_name=PKM_COLLECTION,
            payload={
                "status": new_status,
                "updated_at": datetime.utcnow().isoformat()
            },
            points=[point_id]
        )
        logger.debug("pkm_item_status_updated", user_id=user_id, item_id=item_id, status=new_status)
        return True
    except Exception as e:
        logger.error("update_pkm_item_status_error", error=str(e)[:50], user_id=user_id)
        return False
