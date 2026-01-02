"""Gemini AI tools (vision, grounding, thinking)."""

from claude_agents import tool
from typing import Dict
import structlog

logger = structlog.get_logger()


@tool
async def gemini_vision(
    image_url: str,
    prompt: str,
) -> Dict:
    """Analyze image with Gemini Vision.

    Args:
        image_url: URL of image to analyze
        prompt: Analysis prompt

    Returns:
        Vision analysis result
    """
    from src.services.gemini import get_gemini_client
    import base64
    import httpx

    try:
        client = get_gemini_client()

        # Download image
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(image_url, timeout=30.0)
            image_bytes = response.content

        # Convert to base64
        image_base64 = base64.b64encode(image_bytes).decode()

        # Analyze with Gemini
        analysis = await client.analyze_image(
            image_base64=image_base64,
            prompt=prompt,
            media_type=response.headers.get("content-type", "image/jpeg")
        )

        return {"analysis": analysis}

    except Exception as e:
        logger.error("gemini_vision_error", error=str(e)[:100])
        return {"error": f"Vision analysis failed: {str(e)[:100]}"}


@tool
async def gemini_grounding(
    query: str,
) -> Dict:
    """Get web-grounded response from Gemini with sources.

    Args:
        query: Query requiring current information

    Returns:
        Grounded response with sources
    """
    from src.services.gemini import get_gemini_client

    try:
        client = get_gemini_client()
        result = await client.grounded_query(
            query=query,
            grounding_sources=["google_search"]
        )

        return {
            "response": result.text,
            "sources": [
                {"title": c.get("title", ""), "url": c.get("url", "")}
                for c in result.citations
            ]
        }

    except Exception as e:
        logger.error("gemini_grounding_error", error=str(e)[:100])
        return {"error": f"Grounding failed: {str(e)[:100]}"}


@tool
async def gemini_thinking(
    problem: str,
    thinking_budget: int = 10000,
) -> Dict:
    """Deep thinking with Gemini for complex problems.

    Args:
        problem: Complex problem to analyze
        thinking_budget: Token budget for thinking (default: 10000)

    Returns:
        Analysis with reasoning
    """
    from src.services.gemini import get_gemini_client

    try:
        client = get_gemini_client()

        # Use chat with thinking for 2.5+ models (fallback to regular for 2.0)
        response = await client.chat(
            messages=[{"role": "user", "content": problem}],
            model="gemini-2.0-flash-001",  # 2.0 doesn't support thinking
            max_tokens=thinking_budget
        )

        return {
            "analysis": response,
            "thinking": "Thinking mode not available for Gemini 2.0"
        }

    except Exception as e:
        logger.error("gemini_thinking_error", error=str(e)[:100])
        return {"error": f"Thinking failed: {str(e)[:100]}"}
