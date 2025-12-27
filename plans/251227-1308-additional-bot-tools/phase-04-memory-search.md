# Phase 4: Memory/RAG Search Tool

## Context
- [Plan Overview](./plan.md)
- Uses existing Qdrant service

## Overview
Query vector memory for conversation context and knowledge retrieval.

## Implementation

**File:** `agents/src/tools/memory_search.py`

```python
import os
from typing import Any, Dict
from src.tools.base import BaseTool
import structlog

logger = structlog.get_logger()


class MemorySearchTool(BaseTool):
    """Search vector memory for relevant context."""

    def __init__(self):
        self._qdrant = None
        self._embeddings = None

    @property
    def name(self) -> str:
        return "search_memory"

    @property
    def description(self) -> str:
        return (
            "Search memory for relevant past conversations and knowledge. "
            "Use for: recalling previous context, finding related info."
        )

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for memory"
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default: 3)"
                }
            },
            "required": ["query"]
        }

    @property
    def qdrant_client(self):
        """Lazy-load Qdrant client."""
        if self._qdrant is None:
            from src.services.qdrant import get_client, is_enabled
            if is_enabled():
                self._qdrant = get_client()
        return self._qdrant

    async def execute(self, params: Dict[str, Any]) -> str:
        query = params.get("query", "")
        limit = min(params.get("limit", 3), 10)

        if not query:
            return "Error: No query provided"

        if not self.qdrant_client:
            return "Memory search not available (Qdrant not configured)"

        try:
            from src.services.embeddings import get_embedding

            # Get embedding for query
            embedding = get_embedding(query)

            # Search Qdrant
            results = self.qdrant_client.search(
                collection_name="conversations",
                query_vector=embedding,
                limit=limit
            )

            if not results:
                return "No relevant memories found."

            # Format results
            formatted = []
            for i, r in enumerate(results, 1):
                payload = r.payload or {}
                text = payload.get("text", "")[:500]
                score = r.score
                formatted.append(f"{i}. (relevance: {score:.2f})\n{text}")

            logger.info("memory_search_success", query=query[:30], results=len(results))
            return "Found memories:\n\n" + "\n\n".join(formatted)

        except Exception as e:
            logger.error("memory_search_error", error=str(e))
            return f"Memory search error: {str(e)[:100]}"
```

## Todo
- [ ] Create `memory_search.py`
- [ ] Register in `__init__.py`
- [ ] Ensure Qdrant collections exist
- [ ] Test with context query

## Success Criteria
1. Queries Qdrant with embedding
2. Returns relevant memories
3. Graceful fallback if Qdrant unavailable
