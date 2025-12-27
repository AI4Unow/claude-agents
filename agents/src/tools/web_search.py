"""Web search tool using Exa (primary) with Tavily fallback."""
import os
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from src.tools.base import BaseTool
import structlog

logger = structlog.get_logger()

# Simple cache with 15min TTL
_cache: Dict[str, tuple] = {}
CACHE_TTL = timedelta(minutes=15)


class WebSearchTool(BaseTool):
    """Web search using Exa (primary) with Tavily fallback."""

    def __init__(self):
        self._exa_client = None
        self._tavily_client = None

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the web for current information. Use for: "
            "news, weather, prices, recent events, factual queries. "
            "Returns summarized results from multiple sources."
        )

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                }
            },
            "required": ["query"]
        }

    @property
    def exa_client(self):
        """Lazy-load Exa client."""
        if self._exa_client is None:
            api_key = os.environ.get("EXA_API_KEY", "")
            if api_key:
                from exa_py import Exa
                self._exa_client = Exa(api_key=api_key)
        return self._exa_client

    @property
    def tavily_client(self):
        """Lazy-load Tavily client (fallback)."""
        if self._tavily_client is None:
            api_key = os.environ.get("TAVILY_API_KEY", "")
            if api_key:
                from tavily import TavilyClient
                self._tavily_client = TavilyClient(api_key=api_key)
        return self._tavily_client

    def _get_cached(self, query: str) -> Optional[str]:
        """Get cached result if valid."""
        key = query.lower().strip()
        if key in _cache:
            result, timestamp = _cache[key]
            if datetime.now() - timestamp < CACHE_TTL:
                logger.info("cache_hit", query=query[:30])
                return result
        return None

    def _set_cache(self, query: str, result: str):
        """Cache result with timestamp."""
        key = query.lower().strip()
        _cache[key] = (result, datetime.now())

    async def execute(self, params: Dict[str, Any]) -> str:
        query = params.get("query", "")

        if not query:
            return "Search failed: No query provided"

        # Check cache first
        cached = self._get_cached(query)
        if cached:
            return cached

        # Try Exa first (neural search)
        result = await self._search_exa(query)

        # Fallback to Tavily if Exa fails
        if result.startswith("Search failed") and self.tavily_client:
            logger.info("fallback_to_tavily", query=query[:30])
            result = await self._search_tavily(query)

        # Cache successful results
        if not result.startswith("Search failed"):
            self._set_cache(query, result)

        return result

    async def _search_exa(self, query: str) -> str:
        """Search using Exa API."""
        if not self.exa_client:
            return "Search failed: Exa not configured"

        try:
            result = self.exa_client.search_and_contents(
                query=query,
                num_results=5,
                text={"max_characters": 500},
                use_autoprompt=True
            )

            formatted = []
            for r in result.results[:3]:
                title = r.title or "Untitled"
                content = (r.text or "")[:400]
                url = r.url or ""
                formatted.append(f"**{title}**\n{content}\nSource: {url}")

            output = "\n\n".join(formatted)
            if len(output) > 2000:
                output = output[:1997] + "..."

            logger.info("exa_search_success", query=query[:30])
            return output or "No results found."

        except Exception as e:
            logger.error("exa_search_error", error=str(e))
            return f"Search failed: {str(e)[:50]}"

    async def _search_tavily(self, query: str) -> str:
        """Fallback search using Tavily API."""
        if not self.tavily_client:
            return "Search failed: No search providers available"

        try:
            result = self.tavily_client.search(
                query=query,
                search_depth="basic",
                max_results=5
            )

            formatted = []
            for r in result.get("results", [])[:3]:
                title = r.get("title", "")
                content = r.get("content", "")[:400]
                url = r.get("url", "")
                formatted.append(f"**{title}**\n{content}\nSource: {url}")

            output = "\n\n".join(formatted)
            if len(output) > 2000:
                output = output[:1997] + "..."

            logger.info("tavily_search_success", query=query[:30])
            return output or "No results found."

        except Exception as e:
            logger.error("tavily_search_error", error=str(e))
            return f"Search failed: {str(e)[:50]}"
