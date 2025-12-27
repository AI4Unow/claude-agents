# Phase 3: Qdrant Cloud Vector Memory

## Context

- Plan: [plan.md](./plan.md)
- Previous: [Phase 2 - Firebase Integration](./phase-02-firebase-integration.md)

## Overview

**Priority:** P1 - Core Infrastructure
**Status:** Pending
**Effort:** 2h

Connect to Qdrant Cloud (Asia region) for semantic memory. Agents store/retrieve conversation history and knowledge via vector embeddings.

## Requirements

### Functional
- Qdrant Cloud cluster in Asia region
- Collections for: conversations, knowledge, tasks
- Embedding generation (Vertex AI)
- Semantic search with filtering
- Memory persistence (managed by Qdrant Cloud)

### Non-Functional
- Sub-100ms search latency
- 1GB+ vector storage
- Managed backups (Qdrant Cloud handles this)

## Architecture

```
┌─────────────────────────────────────────┐
│              AGENTS (Modal)             │
│   ┌─────────┐ ┌─────┐ ┌─────┐ ┌─────┐      │
│   │Telegram │ │GitHub│ │Data │ │Content│    │
│   └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘      │
│      └───────┴───────┴───────┘          │
│                  │                       │
└──────────────────┼───────────────────────┘
                   │ HTTPS
           ┌───────▼───────┐
           │ QDRANT CLOUD  │
           │ (Asia region) │
           │   Managed     │
           └───────────────┘
```

## Qdrant Cloud Setup

### 1. Create Qdrant Cloud Account

1. Go to https://cloud.qdrant.io/
2. Sign up / Login
3. Create new cluster:
   - **Region:** Asia (Singapore or Tokyo)
   - **Plan:** Free tier (1GB) or Starter
   - **Name:** `claude-agents`

### 2. Get Connection Details

After cluster creation:
- **URL:** `https://xxxxx.asia.qdrant.io`
- **API Key:** Generated in dashboard

### 3. Configure Modal Secret

```bash
modal secret create qdrant-credentials \
  QDRANT_URL=https://xxxxx.asia.qdrant.io \
  QDRANT_API_KEY=your-api-key
```

## Qdrant Collections

| Collection | Purpose | Payload Schema |
|------------|---------|----------------|
| `conversations` | Chat history | `{user_id, agent, role, content, timestamp}` |
| `knowledge` | Domain knowledge | `{source, topic, content, created_at}` |
| `tasks` | Task context | `{task_id, type, summary, result}` |

Vector dimension: 768 (Vertex AI text-embedding-004)

## Implementation Steps

### 4. Create src/services/qdrant.py

```python
from typing import List, Dict, Optional, Any
import os
from qdrant_client import QdrantClient
from qdrant_client.http import models
from datetime import datetime

# Qdrant Cloud client
_client: Optional[QdrantClient] = None

VECTOR_DIM = 768  # Vertex AI text-embedding-004

def get_client() -> QdrantClient:
    """Get Qdrant Cloud client."""
    global _client
    if _client is None:
        # Connect to Qdrant Cloud
        _client = QdrantClient(
            url=os.environ["QDRANT_URL"],
            api_key=os.environ["QDRANT_API_KEY"],
        )
    return _client

def init_collections():
    """Initialize all collections if they don't exist."""
    client = get_client()

    collections = ["conversations", "knowledge", "tasks"]

    for name in collections:
        try:
            client.get_collection(name)
        except:
            client.create_collection(
                collection_name=name,
                vectors_config=models.VectorParams(
                    size=VECTOR_DIM,
                    distance=models.Distance.COSINE
                )
            )

# ==================== Conversations ====================

async def store_conversation(
    user_id: str,
    agent: str,
    role: str,  # "user" or "assistant"
    content: str,
    embedding: List[float]
) -> str:
    """Store a conversation message with embedding."""
    client = get_client()

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
) -> str:
    """Store knowledge with embedding."""
    client = get_client()

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

# ==================== Structured Memory (Context Engineering) ====================

async def store_structured_memory(
    user_id: str,
    session_summary: Dict
) -> str:
    """
    Store structured session summary for better retrieval.

    Prevents "lost in the middle" problem by storing explicit sections.

    Args:
        session_summary: {
            "intent": str,          # What user wanted
            "entities": List[str],  # Users, repos, projects mentioned
            "actions": List[str],   # What agents did
            "decisions": List[str], # Choices made
            "artifacts": List[str], # Files, URLs created
            "next_steps": List[str] # Suggested follow-ups
        }
    """
    import json

    # Convert to embedding-friendly text
    text = f"""
    Intent: {session_summary.get('intent', '')}
    Entities: {', '.join(session_summary.get('entities', []))}
    Actions: {', '.join(session_summary.get('actions', []))}
    Decisions: {', '.join(session_summary.get('decisions', []))}
    """

    embedding = get_embedding(text)

    return await store_conversation(
        user_id=user_id,
        agent="system",
        role="summary",
        content=json.dumps(session_summary),
        embedding=embedding
    )
```

### 4. Create src/services/embeddings.py

```python
import os
from typing import List
from google.cloud import aiplatform
from vertexai.language_models import TextEmbeddingModel

# Initialize Vertex AI
aiplatform.init(
    project=os.environ["GCP_PROJECT_ID"],
    location=os.environ.get("GCP_LOCATION", "us-central1")
)

# Load embedding model
_model = None

def _get_model() -> TextEmbeddingModel:
    """Get or initialize the embedding model."""
    global _model
    if _model is None:
        _model = TextEmbeddingModel.from_pretrained("text-embedding-004")
    return _model

def get_embedding(text: str) -> List[float]:
    """Generate embedding using Vertex AI text-embedding-004."""
    model = _get_model()
    embeddings = model.get_embeddings([text])
    return embeddings[0].values

def get_embedding_for_query(text: str) -> List[float]:
    """Generate embedding optimized for search queries."""
    model = _get_model()
    embeddings = model.get_embeddings(
        [text],
        task_type="RETRIEVAL_QUERY"
    )
    return embeddings[0].values

def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple texts (max 250 per batch)."""
    model = _get_model()
    # Vertex AI supports up to 250 texts per batch
    embeddings = model.get_embeddings(texts[:250])
    return [e.values for e in embeddings]
```

### 5. Add Vertex AI to requirements.txt

```
google-cloud-aiplatform>=1.40.0
```

### 6. Test Qdrant Connection

```python
# tests/test_qdrant.py
import pytest
from src.services.qdrant import get_client, init_collections

def test_qdrant_connection():
    client = get_client()
    assert client.get_collections() is not None

def test_init_collections():
    init_collections()
    client = get_client()
    collections = [c.name for c in client.get_collections().collections]
    assert "conversations" in collections
    assert "knowledge" in collections
    assert "tasks" in collections
```

## Files to Create

| Path | Action | Description |
|------|--------|-------------|
| `agents/src/services/qdrant.py` | Create | Qdrant client and operations |
| `agents/src/services/embeddings.py` | Create | Embedding generation |
| `agents/tests/test_qdrant.py` | Create | Qdrant tests |

## Todo List

- [ ] Create qdrant-data volume
- [ ] Add QdrantService to main.py
- [ ] Create qdrant.py service
- [ ] Create embeddings.py service
- [ ] Deploy and verify Qdrant starts
- [ ] Initialize collections
- [ ] Test store/search operations
- [ ] Verify data persists across restarts

## Success Criteria

- [ ] Qdrant container runs on Modal
- [ ] All 3 collections created
- [ ] Store and search operations work
- [ ] Data persists in volume
- [ ] Search latency <100ms

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Qdrant OOM | Memory crash | Monitor, scale memory |
| Volume data loss | Lost memory | Regular snapshots |
| Slow embeddings | High latency | Batch embeddings, cache |

## Cost Considerations

| Option | Quality | Cost |
|--------|---------|------|
| Vertex AI text-embedding-004 | High | ~$0.0001/1K chars |

Vertex AI embeddings are very cheap (~$0.10 per million characters). For typical usage, expect <$2/mo.

## Security Considerations

- Qdrant not exposed publicly (Modal internal)
- No auth needed for internal access
- Volume encrypted at rest

## Next Steps

After completing this phase:
1. Proceed to Phase 4: Vercel Edge Webhooks
2. Integrate memory into agents
