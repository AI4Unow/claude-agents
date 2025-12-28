"""Web reader tool - Fetch and extract text from URLs."""
from typing import Any, Dict
import re
import httpx
from src.tools.base import BaseTool, ToolResult

from src.utils.logging import get_logger

logger = get_logger()

MAX_CONTENT_LENGTH = 50000  # ~50KB max


class WebReaderTool(BaseTool):
    """Read and extract content from web pages."""

    @property
    def name(self) -> str:
        return "read_webpage"

    @property
    def description(self) -> str:
        return (
            "Read content from a URL. Use for: summarizing articles, "
            "extracting info from web pages, reading documentation."
        )

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to read (must start with http:// or https://)"
                }
            },
            "required": ["url"]
        }

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        url = params.get("url", "")
        if not url:
            return ToolResult.fail("No URL provided")

        if not url.startswith(("http://", "https://")):
            return ToolResult.fail("URL must start with http:// or https://")

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                # Stream with early termination to prevent DoS
                async with client.stream("GET", url, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; ClaudeBot/1.0)"
                }) as response:
                    response.raise_for_status()

                    chunks = []
                    total = 0
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        total += len(chunk)
                        if total > MAX_CONTENT_LENGTH:
                            break
                        chunks.append(chunk)

                    content = b"".join(chunks).decode('utf-8', errors='ignore')

                # Simple HTML to text conversion
                text = self._html_to_text(content)

                if len(text) > 3000:
                    text = text[:2997] + "..."

                logger.info("web_reader_success", url=url[:50])
                return ToolResult.ok(f"Content from {url}:\n\n{text}")

        except httpx.HTTPStatusError as e:
            return ToolResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.error("web_reader_error", error=str(e))
            return ToolResult.fail(f"Error reading URL: {str(e)[:100]}")

    def _html_to_text(self, html: str) -> str:
        """Simple HTML to text conversion."""
        # Remove script and style
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        # Remove tags
        text = re.sub(r'<[^>]+>', ' ', text)
        # Clean whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Decode entities
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        text = text.replace('&lt;', '<').replace('&gt;', '>')
        return text
