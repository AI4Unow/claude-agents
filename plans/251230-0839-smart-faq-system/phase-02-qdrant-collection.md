# Phase 2: Qdrant FAQ Collection

## Context
- Parent: [plan.md](./plan.md)
- Depends on: [Phase 1](./phase-01-faq-core.md)

## Overview
- **Date:** 2025-12-30
- **Description:** Create Qdrant collection for semantic FAQ search
- **Priority:** P1
- **Implementation Status:** pending
- **Review Status:** pending

## Key Insights
- Reuse existing embedding model from SkillRouter
- Collection name: `faq_embeddings`
- Store faq_id as payload for answer lookup
- Threshold 0.9 to avoid false positives

## Requirements
1. Create Qdrant collection `faq_embeddings`
2. Sync FAQ embeddings when entries change
3. Implement match_semantic() in FAQMatcher

## Architecture

```
FAQ Entry Created/Updated
    ↓
Generate embedding (same model as skills)
    ↓
Upsert to Qdrant faq_embeddings
    ↓
Available for semantic search
```

## Related Code Files
- `src/services/qdrant.py` - Add FAQ collection functions
- `src/core/faq.py` - Complete match_semantic()

## Implementation Steps

### 1. Qdrant FAQ Functions (qdrant.py)
```python
# Add to qdrant.py

FAQ_COLLECTION = "faq_embeddings"

async def ensure_faq_collection():
    """Create FAQ collection if not exists."""
    try:
        client = get_qdrant_client()
        collections = client.get_collections()
        if FAQ_COLLECTION not in [c.name for c in collections.collections]:
            client.create_collection(
                collection_name=FAQ_COLLECTION,
                vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
            )
            logger.info("faq_collection_created")
    except Exception as e:
        logger.error("faq_collection_error", error=str(e))

async def upsert_faq_embedding(faq_id: str, embedding: List[float], answer: str):
    """Upsert FAQ entry embedding."""
    client = get_qdrant_client()
    client.upsert(
        collection_name=FAQ_COLLECTION,
        points=[
            PointStruct(
                id=hash(faq_id) % (2**63),  # Stable int ID
                vector=embedding,
                payload={"faq_id": faq_id, "answer": answer}
            )
        ]
    )

async def search_faq(query_embedding: List[float], threshold: float = 0.9) -> Optional[str]:
    """Search FAQ by embedding, return answer if above threshold."""
    client = get_qdrant_client()
    results = client.search(
        collection_name=FAQ_COLLECTION,
        query_vector=query_embedding,
        limit=1,
        score_threshold=threshold
    )
    if results:
        return results[0].payload.get("answer")
    return None

async def delete_faq_embedding(faq_id: str):
    """Delete FAQ embedding by ID."""
    client = get_qdrant_client()
    client.delete(
        collection_name=FAQ_COLLECTION,
        points_selector=PointIdsList(
            points=[hash(faq_id) % (2**63)]
        )
    )
```

### 2. Complete match_semantic() (faq.py)
```python
async def match_semantic(self, message: str, threshold: float = 0.9) -> Optional[str]:
    """Semantic search via Qdrant."""
    from src.services.qdrant import search_faq, get_embedding

    try:
        # Generate embedding for query
        embedding = await get_embedding(message)
        if not embedding:
            return None

        # Search Qdrant
        answer = await search_faq(embedding, threshold)
        if answer:
            logger.info("faq_semantic_hit", threshold=threshold)
        return answer
    except Exception as e:
        logger.error("faq_semantic_error", error=str(e)[:100])
        return None
```

### 3. Sync Embeddings on FAQ Update
```python
# Add to firebase.py create/update functions

async def create_faq_entry(entry: FAQEntry) -> bool:
    """Create FAQ entry and sync embedding."""
    success = await _save_faq_to_firestore(entry)
    if success and entry.embedding:
        await upsert_faq_embedding(entry.id, entry.embedding, entry.answer)
    return success
```

## Todo List
- [ ] Add ensure_faq_collection() to qdrant.py
- [ ] Add upsert_faq_embedding() function
- [ ] Add search_faq() function
- [ ] Add delete_faq_embedding() function
- [ ] Complete match_semantic() in faq.py
- [ ] Add embedding sync to firebase create/update
- [ ] Test semantic matching

## Success Criteria
- Qdrant collection created on first use
- Semantic search returns answer for similar questions
- <100ms for semantic matches
- 0.9 threshold prevents false positives

## Risk Assessment
- **Qdrant unavailable:** Graceful fallback, keyword still works
- **Embedding mismatch:** Use same model as skills

## Security Considerations
- No auth needed for read
- Collection auto-created, no manual setup

## Next Steps
→ [Phase 3: Integration](./phase-03-integration.md)
