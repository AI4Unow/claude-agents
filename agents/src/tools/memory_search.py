"""Memory search tool - Query Qdrant vector memory."""
from typing import Any, Dict
from src.tools.base import BaseTool, ToolResult
from src.core.resilience import qdrant_circuit, CircuitOpenError

from src.utils.logging import get_logger

logger = get_logger()


class MemorySearchTool(BaseTool):
    """Search vector memory for relevant context."""

    def __init__(self):
        self._qdrant = None

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

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        query = params.get("query", "")
        limit = min(params.get("limit", 3), 10)

        if not query:
            return ToolResult.fail("No query provided")

        if not self.qdrant_client:
            return ToolResult.fail("Memory search not available (Qdrant not configured)")

        try:
            result = await qdrant_circuit.call(
                self._search,
                query,
                limit,
                timeout=15.0
            )
            return result
        except CircuitOpenError as e:
            return ToolResult.fail(f"Memory search unavailable ({e.cooldown_remaining}s)")
        except Exception as e:
            logger.error("memory_search_error", error=str(e))
            return ToolResult.fail(f"Memory search error: {str(e)[:100]}")

    async def _search(self, query: str, limit: int) -> ToolResult:
        """Internal search implementation."""
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
            return ToolResult.ok("No relevant memories found.")

        # Format results
        formatted = []
        for i, r in enumerate(results, 1):
            payload = r.payload or {}
            text = payload.get("content", payload.get("text", ""))[:500]
            score = r.score
            formatted.append(f"{i}. (relevance: {score:.2f})\n{text}")

        logger.info("memory_search_success", query=query[:30], results=len(results))
        return ToolResult.ok("Found memories:\n\n" + "\n\n".join(formatted))
