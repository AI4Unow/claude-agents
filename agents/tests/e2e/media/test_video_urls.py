# agents/tests/e2e/media/test_video_urls.py
"""E2E tests for video URL handling."""
import pytest
from ..conftest import send_and_wait


class TestVideoUrls:
    """Tests for video download flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_youtube_url_detected(self, telegram_client, bot_username):
        """YouTube URL triggers download offer."""
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            timeout=30
        )

        assert response is not None, "No response to YouTube URL"
        text_lower = (response.text or "").lower()

        # Should recognize video URL
        video_words = ["video", "youtube", "download", "url"]
        assert any(word in text_lower for word in video_words), \
            f"YouTube not recognized: {response.text[:200] if response.text else 'no text'}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_video_download_with_skill(self, telegram_client, bot_username):
        """Explicit video-downloader skill queued."""
        from ..conftest import execute_skill

        result = await execute_skill(
            telegram_client,
            bot_username,
            "video-downloader",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            timeout=30
        )

        assert result.success, "Video downloader skill failed"
        text_lower = (result.text or "").lower()

        # Should queue for local execution
        queue_words = ["queue", "task", "local", "download", "video"]
        assert any(word in text_lower for word in queue_words), \
            f"Video not queued: {result.text[:200] if result.text else 'no text'}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_invalid_video_url(self, telegram_client, bot_username):
        """Invalid video URL handled gracefully."""
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "Download this video: https://not-a-real-video-site.xyz/video123",
            timeout=30
        )

        assert response is not None, "No response to invalid URL"
        # Should explain issue or ask for valid URL
        text_lower = (response.text or "").lower()
        assert not ("traceback" in text_lower or "exception" in text_lower), \
            "Raw error exposed"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_short_form_video_url(self, telegram_client, bot_username):
        """Short-form video URLs (youtu.be) handled."""
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "https://youtu.be/dQw4w9WgXcQ",
            timeout=30
        )

        assert response is not None, "No response to short URL"
        text_lower = (response.text or "").lower()

        # Should recognize as video
        video_words = ["video", "youtube", "download"]
        assert any(word in text_lower for word in video_words), \
            f"Short URL not recognized: {response.text[:200] if response.text else 'no text'}"
