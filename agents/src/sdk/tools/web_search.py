"""Web search tool (migrated from src/tools/web_search.py)."""

from claude_agents import tool
from typing import List, Dict
import structlog

logger = structlog.get_logger()


@tool
async def web_search(
    query: str,
    max_results: int = 5,
) -> List[Dict]:
    """Search the web for current information.

    Args:
        query: Search query
        max_results: Maximum results to return (default: 5)

    Returns:
        List of search results with title, url, snippet
    """
    from src.tools.web_search import WebSearchTool

    # Use existing implementation
    search_tool = WebSearchTool()
    result = await search_tool.execute({"query": query})

    if result.success:
        # Parse results from existing format
        return [{"content": result.data}]
    else:
        logger.warning("web_search_failed", error=result.error)
        return [{"error": result.error or "Search failed"}]
