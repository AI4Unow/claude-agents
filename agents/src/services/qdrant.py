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

VECTOR_DIM = 1024  # Z.AI embedding-3 default dimension

# Collection names
COLLECTIONS = {
    "skills": "Semantic skill matching for routing",
    "knowledge": "Cross-skill insights and learnings",
    "conversations": "Chat history for context",
    "errors": "Error pattern matching",
    "tasks": "Task context for similar task lookup",
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

    collections = ["conversations", "knowledge", "tasks"]
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
