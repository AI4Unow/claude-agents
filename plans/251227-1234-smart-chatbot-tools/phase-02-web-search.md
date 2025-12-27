# Phase 2: Web Search Integration

## Context

- [Plan Overview](./plan.md)
- [Web Search APIs Research](./research/researcher-02-web-search-apis.md)
- [Phase 1: Tool System](./phase-01-tool-system.md)

## Overview

Implement web search tool using Exa API (neural/semantic search) with Tavily fallback. Tool enables chatbot to fetch current information from the web.

## Requirements

1. Use Exa API for neural/meaning-based search (primary)
2. Tavily API as fallback for reliability
3. Return structured, concise results (max 2000 chars)
4. Cache results for 15 minutes to reduce API costs
5. Brief error messages to users

## Architecture

```
WebSearchTool
    ├── ExaClient (primary - neural search)
    └── TavilyClient (fallback - LLM-optimized)
```

## Implementation Steps

### 2.1 Add Dependencies

**File:** `agents/requirements.txt`

```
exa-py>=1.0.0
tavily-python>=0.3.0
```

### 2.2 Create WebSearchTool

**File:** `agents/src/tools/web_search.py`

```python
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
            from exa_py import Exa
            api_key = os.environ.get("EXA_API_KEY", "")
            if api_key:
                self._exa_client = Exa(api_key=api_key)
        return self._exa_client

    @property
    def tavily_client(self):
        """Lazy-load Tavily client (fallback)."""
        if self._tavily_client is None:
            from tavily import TavilyClient
            api_key = os.environ.get("TAVILY_API_KEY", "")
            if api_key:
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
```

### 2.3 Register Tool at Startup

**File:** `agents/src/tools/__init__.py` (update)

```python
from src.tools.registry import ToolRegistry, get_registry
from src.tools.base import BaseTool
from src.tools.web_search import WebSearchTool

def init_default_tools():
    """Register default tools."""
    registry = get_registry()
    registry.register(WebSearchTool())

__all__ = ["ToolRegistry", "get_registry", "BaseTool", "init_default_tools"]
```

### 2.4 Add Modal Secrets

Create secrets for both providers:

```bash
modal secret create exa-credentials EXA_API_KEY=xxx
modal secret create tavily-credentials TAVILY_API_KEY=tvly-xxx
```

Update `agents/main.py`:

```python
secrets = [
    modal.Secret.from_name("anthropic-credentials"),
    modal.Secret.from_name("exa-credentials"),      # Primary
    modal.Secret.from_name("tavily-credentials"),   # Fallback
    ...
]
```

## Todo

- [ ] Add `exa-py` and `tavily-python` to requirements.txt
- [ ] Create `web_search.py` with WebSearchTool
- [ ] Update `__init__.py` with init_default_tools
- [ ] Create `exa-credentials` Modal secret
- [ ] Create `tavily-credentials` Modal secret
- [ ] Add secrets to main.py secrets list
- [ ] Test Exa search in isolation
- [ ] Test fallback to Tavily
- [ ] Verify cache works (15min TTL)

## Success Criteria

1. `WebSearchTool().execute({"query": "weather hanoi"})` returns results
2. Exa is used as primary search provider
3. Tavily fallback triggers when Exa fails
4. Results cached for 15 minutes
5. Results formatted and truncated to 2000 chars
6. Errors return brief message (not full stack trace)
