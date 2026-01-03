"""Gemini skill tools for Modal agents."""
import uuid
from typing import Dict, Optional, Callable

from src.services.gemini import get_gemini_client, ResearchReport
from src.utils.logging import get_logger

logger = get_logger()


async def execute_deep_research(
    query: str,
    user_id: int = 0,
    chat_id: int = 0,
    progress_callback: Callable[[str], None] = None,
    max_iterations: int = 10,
    save_report: bool = True,
) -> Dict:
    """Execute deep research skill.

    Args:
        query: Research topic
        user_id: Telegram user ID for notifications
        chat_id: Telegram chat ID for progress updates
        progress_callback: Optional callback for progress
        max_iterations: Max research iterations
        save_report: Whether to save report to Firebase Storage

    Returns:
        Dict with report and metadata
    """
    client = get_gemini_client()

    try:
        report = await client.deep_research(
            query=query,
            on_progress=progress_callback,
            max_iterations=max_iterations,
        )

        # Format citations
        citations_md = "\n".join([
            f"- [{c['title'][:50]}]({c['url']})"
            for c in report.citations[:10]
            if c.get('url')
        ])

        # Guard against empty sections - fallback to summary
        report_content = (
            report.sections[0]["content"]
            if report.sections and report.sections[0].get("content")
            else report.summary or "No content available"
        )

        result = {
            "success": True,
            "report": report_content,
            "summary": report.summary,
            "citations": citations_md,
            "query_count": report.query_count,
            "duration_seconds": report.duration_seconds,
            "thinking_trace": report.thinking_trace,
        }

        # Save report to Firebase Storage if user_id provided
        if save_report and user_id:
            try:
                from src.services.firebase import save_report as fb_save_report
                report_id = f"research-{uuid.uuid4().hex[:8]}"
                url = await fb_save_report(
                    user_id=user_id,
                    report_id=report_id,
                    content=report_content,
                    metadata={
                        "title": f"Research: {query[:50]}",
                        "query": query,
                        "duration_seconds": str(report.duration_seconds),
                        "query_count": str(report.query_count),
                    }
                )
                result["report_id"] = report_id
                result["download_url"] = url
                logger.info("report_saved_to_storage", report_id=report_id, user_id=user_id)
            except Exception as e:
                logger.warning("report_save_failed", error=str(e)[:50])
                # Continue without saving - don't fail the whole operation

        return result

    except Exception as e:
        logger.error("deep_research_error", error=str(e)[:100])
        return {
            "success": False,
            "error": str(e),
        }


async def execute_grounded_query(
    query: str,
    sources: list = None,
) -> Dict:
    """Execute grounded query skill.

    Args:
        query: Factual query
        sources: ["google_search", "google_maps"]

    Returns:
        Dict with answer and citations
    """
    client = get_gemini_client()

    try:
        response = await client.grounded_query(
            query=query,
            grounding_sources=sources or ["google_search"],
        )

        citations_md = "\n".join([
            f"- [{c['title'][:50]}]({c['url']})"
            for c in response.citations[:5]
            if c.get('url')
        ])

        return {
            "success": True,
            "answer": response.text,
            "citations": citations_md,
        }

    except Exception as e:
        logger.error("grounded_query_error", error=str(e)[:100])
        return {
            "success": False,
            "error": str(e),
        }


async def execute_thinking(
    prompt: str,
    thinking_level: str = "high",
    user_id: int = 0,
) -> Dict:
    """Execute thinking skill with configurable depth.

    Args:
        prompt: Problem to analyze
        thinking_level: minimal, low, medium, high
        user_id: User ID for saving result to storage

    Returns:
        Dict with analysis and optional download_url
    """
    client = get_gemini_client()

    try:
        result = await client.chat(
            messages=[{"role": "user", "content": prompt}],
            thinking_level=thinking_level,
            model="gemini-2.0-flash-001",
        )

        response = {
            "success": True,
            "analysis": result,
            "thinking_level": thinking_level,
        }

        # Save analysis to storage if user_id provided
        if user_id:
            try:
                from src.services.firebase import save_file
                file_id = f"thinking-{uuid.uuid4().hex[:8]}"
                url = await save_file(
                    user_id=user_id,
                    file_id=file_id,
                    content=result,
                    content_type="text/markdown",
                    metadata={"title": f"Analysis ({thinking_level})", "skill": "gemini-thinking"}
                )
                response["file_id"] = file_id
                response["download_url"] = url
            except Exception as e:
                logger.warning("thinking_save_failed", error=str(e)[:50])

        return response

    except Exception as e:
        logger.error("thinking_error", error=str(e)[:100])
        return {
            "success": False,
            "error": str(e),
        }


async def execute_vision(
    image_base64: str,
    prompt: str,
    media_type: str = "image/jpeg",
    user_id: int = 0,
) -> Dict:
    """Execute vision analysis skill.

    Args:
        image_base64: Base64 encoded image
        prompt: Analysis prompt
        media_type: Image MIME type
        user_id: User ID for saving result to storage

    Returns:
        Dict with analysis and optional download_url
    """
    client = get_gemini_client()

    try:
        result = await client.analyze_image(
            image_base64=image_base64,
            prompt=prompt,
            media_type=media_type,
        )

        response = {
            "success": True,
            "analysis": result,
        }

        # Save analysis to storage if user_id provided
        if user_id:
            try:
                from src.services.firebase import save_file
                file_id = f"vision-{uuid.uuid4().hex[:8]}"
                url = await save_file(
                    user_id=user_id,
                    file_id=file_id,
                    content=result,
                    content_type="text/markdown",
                    metadata={"title": "Vision Analysis", "skill": "gemini-vision"}
                )
                response["file_id"] = file_id
                response["download_url"] = url
            except Exception as e:
                logger.warning("vision_save_failed", error=str(e)[:50])

        return response

    except Exception as e:
        logger.error("vision_error", error=str(e)[:100])
        return {
            "success": False,
            "error": str(e),
        }
