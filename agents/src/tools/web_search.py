"""Web search tool using Exa (primary) with Gemini and Tavily fallbacks.

Fallback chain: Exa → Gemini → Tavily
Includes circuit breakers for resilience.
"""
import os
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from collections import OrderedDict
from src.tools.base import BaseTool, ToolResult
from src.core.resilience import exa_circuit, tavily_circuit, gemini_circuit, CircuitOpenError
from src.services.gemini import get_gemini_client

from src.utils.logging import get_logger

logger = get_logger()

# LRU cache with bounded size
CACHE_TTL = timedelta(minutes=15)

class LRUCache:
    """LRU cache with TTL and bounded size."""
    def __init__(self, maxsize: int = 100):
        self._cache = OrderedDict()
        self._maxsize = maxsize

    def get(self, key: str) -> Optional[tuple]:
        """Get cached value if valid."""
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def set(self, key: str, value: tuple):
        """Set cache value, evicting LRU if at capacity."""
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self._maxsize:
                self._cache.popitem(last=False)
        self._cache[key] = value

_cache = LRUCache(maxsize=100)


class WebSearchTool(BaseTool):
    """Web search using Exa (primary) with Gemini and Tavily fallbacks."""

    def __init__(self):
        self._exa_client = None
        self._tavily_client = None
        self._gemini_client = None

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
        """Lazy-load Tavily client (3rd fallback)."""
        if self._tavily_client is None:
            api_key = os.environ.get("TAVILY_API_KEY", "")
            if api_key:
                from tavily import TavilyClient
                self._tavily_client = TavilyClient(api_key=api_key)
        return self._tavily_client

    @property
    def gemini_client(self):
        """Lazy-load Gemini client (2nd fallback)."""
        if self._gemini_client is None:
            self._gemini_client = get_gemini_client()
        return self._gemini_client

    def _get_cached(self, query: str) -> Optional[str]:
        """Get cached result if valid."""
        key = query.lower().strip()
        cached = _cache.get(key)
        if cached:
            result, timestamp = cached
            if datetime.now() - timestamp < CACHE_TTL:
                logger.info("cache_hit", query=query[:30])
                return result
        return None

    def _set_cache(self, query: str, result: str):
        """Cache result with timestamp."""
        key = query.lower().strip()
        _cache.set(key, (result, datetime.now()))

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        query = params.get("query", "")

        if not query:
            return ToolResult.fail("No query provided")

        # Check cache first
        cached = self._get_cached(query)
        if cached:
            return ToolResult.ok(cached)

        # Try Exa first with circuit breaker
        exa_result: Optional[ToolResult] = None
        try:
            exa_result = await exa_circuit.call(self._search_exa, query)
        except CircuitOpenError as e:
            logger.warning("exa_circuit_open", cooldown=e.cooldown_remaining)
            exa_result = ToolResult.fail(f"Exa circuit open ({e.cooldown_remaining}s)")

        # If Exa succeeded, cache and return
        if exa_result and exa_result.success:
            self._set_cache(query, exa_result.data)
            return exa_result

        # Fallback 1: Try Gemini grounding
        if self.gemini_client:
            logger.info("fallback_to_gemini", query=query[:30])
            try:
                gemini_result = await gemini_circuit.call(self._search_gemini, query)
                if gemini_result.success:
                    self._set_cache(query, gemini_result.data)
                    return gemini_result
            except CircuitOpenError as e:
                logger.warning("gemini_circuit_open", cooldown=e.cooldown_remaining)

        # Fallback 2: Try Tavily (last resort)
        if self.tavily_client:
            logger.info("fallback_to_tavily", query=query[:30])
            try:
                tavily_result = await tavily_circuit.call(self._search_tavily, query)
                if tavily_result.success:
                    self._set_cache(query, tavily_result.data)
                return tavily_result
            except CircuitOpenError as e:
                logger.warning("tavily_circuit_open", cooldown=e.cooldown_remaining)
                return ToolResult.fail("All search circuits open")

        # Return Exa error if no Tavily fallback
        return exa_result or ToolResult.fail("No search providers available")

    async def _search_exa(self, query: str) -> ToolResult:
        """Search using Exa API."""
        if not self.exa_client:
            return ToolResult.fail("Exa not configured")

        try:
            result = self.exa_client.search_and_contents(
                query=query,
                num_results=5,
                text={"max_characters": 500},
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
            return ToolResult.ok(output or "No results found.")

        except Exception as e:
            logger.error("exa_search_error", error=str(e))
            return ToolResult.fail(f"Exa search failed: {str(e)[:50]}")

    async def _search_gemini(self, query: str) -> ToolResult:
        """Fallback search using Gemini grounding (Google Search)."""
        if not self.gemini_client:
            return ToolResult.fail("Gemini not configured")

        try:
            response = await self.gemini_client.grounded_query(
                query=query,
                grounding_sources=["google_search"],
                model="gemini-2.0-flash-001",
            )

            # Format: Text + Citations
            formatted = []

            # Add main text as first result
            if response.text:
                formatted.append(f"**Summary**\n{response.text[:400]}")

            # Add citations as additional results
            for citation in response.citations[:2]:
                title = citation.get("title", "")
                url = citation.get("url", "")
                snippet = citation.get("snippet", "")[:300]
                if title and url:
                    formatted.append(f"**{title}**\n{snippet}\nSource: {url}")

            output = "\n\n".join(formatted)
            if len(output) > 2000:
                output = output[:1997] + "..."

            logger.info("gemini_search_success", query=query[:30])
            return ToolResult.ok(output or "No results found.")

        except Exception as e:
            logger.error("gemini_search_error", error=str(e))
            return ToolResult.fail(f"Gemini search failed: {str(e)[:50]}")

    async def _search_tavily(self, query: str) -> ToolResult:
        """Fallback search using Tavily API."""
        if not self.tavily_client:
            return ToolResult.fail("No search providers available")

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
            return ToolResult.ok(output or "No results found.")

        except Exception as e:
            logger.error("tavily_search_error", error=str(e))
            return ToolResult.fail(f"Tavily search failed: {str(e)[:50]}")
