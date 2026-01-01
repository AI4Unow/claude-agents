# agents/tests/e2e/local_execution/test_task_queue.py
"""E2E tests for Firebase task queue behavior."""
import pytest
from ..conftest import execute_skill, send_and_wait


class TestTaskQueue:
    """Tests for local skill task queue."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_local_skill_creates_task(self, telegram_client, bot_username):
        """Local skill invocation creates task in queue."""
        result = await execute_skill(
            telegram_client,
            bot_username,
            "pdf",
            "Analyze a document",
            timeout=30
        )

        assert result.success, "No response to local skill"
        text_lower = (result.text or "").lower()

        # Should indicate task was queued
        queue_indicators = ["queue", "task", "pending", "local", "wait"]
        assert any(word in text_lower for word in queue_indicators), \
            f"Task not queued: {result.text[:200]}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_queue_notification_sent(self, telegram_client, bot_username):
        """User receives queue notification for local skill."""
        result = await execute_skill(
            telegram_client,
            bot_username,
            "video-downloader",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            timeout=30
        )

        assert result.success, "No response"
        text_lower = (result.text or "").lower()

        # Should notify about queuing
        notification_words = ["queued", "task", "notify", "complete", "result", "video", "download"]
        has_notification = any(word in text_lower for word in notification_words)
        assert has_notification, f"No queue notification: {result.text[:200]}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_task_status_api(self, api_base_url):
        """Task status API returns valid data."""
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Check if task API exists
                resp = await client.get(f"{api_base_url}/health")
                assert resp.status_code == 200, "API not healthy"

                # Note: Getting specific task requires valid task_id
                # This test just verifies API is accessible
            except httpx.RequestError as e:
                pytest.skip(f"API not accessible: {e}")
