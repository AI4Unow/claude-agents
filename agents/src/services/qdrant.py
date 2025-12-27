"""Qdrant Cloud vector memory service."""
from typing import List, Dict, Optional, Any
import os
from datetime import datetime
import structlog

logger = structlog.get_logger()

# Qdrant Cloud client
_client = None
_enabled = False

VECTOR_DIM = 1024  # Z.AI embedding-3 default dimension


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
