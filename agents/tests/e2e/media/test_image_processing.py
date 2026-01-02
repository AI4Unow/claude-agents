# agents/tests/e2e/media/test_image_processing.py
"""E2E tests for image processing capabilities."""
import pytest
from pathlib import Path
from ..conftest import upload_file, execute_skill

pytestmark = [
    pytest.mark.requires_claude,  # Vision analysis requires LLM
    pytest.mark.requires_gemini   # Uses Gemini Vision
]


class TestImageProcessing:
    """Tests for image upload and analysis."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.media
    async def test_image_upload_triggers_vision(
        self, telegram_client, bot_username, fixtures_dir
    ):
        """Uploading image triggers vision analysis."""
        image_path = fixtures_dir / "sample-image.jpg"
        if not image_path.exists():
            pytest.skip("Sample image fixture not available")

        response = await upload_file(
            telegram_client,
            bot_username,
            image_path,
            timeout=60
        )

        assert response is not None, "No response to image upload"
        # Bot should acknowledge image
        has_content = (
            len(response.text or "") > 10 or
            response.media is not None
        )
        assert has_content, "No meaningful response to image"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.media
    async def test_image_with_caption_directive(
        self, telegram_client, bot_username, fixtures_dir
    ):
        """Image with caption directs analysis."""
        image_path = fixtures_dir / "sample-image.jpg"
        if not image_path.exists():
            pytest.skip("Sample image fixture not available")

        response = await upload_file(
            telegram_client,
            bot_username,
            image_path,
            caption="Describe the colors in this image",
            timeout=60
        )

        assert response is not None, "No response to captioned image"
        text_lower = (response.text or "").lower()

        # Should mention colors or visual elements
        visual_words = ["color", "image", "see", "show", "visual", "photo"]
        has_visual = any(word in text_lower for word in visual_words)
        assert has_visual or response.media, \
            f"Caption not followed: {response.text[:200] if response.text else 'no text'}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.media
    async def test_ocr_text_extraction(
        self, telegram_client, bot_username, fixtures_dir
    ):
        """Screenshot with text triggers OCR."""
        screenshot_path = fixtures_dir / "sample-screenshot.png"
        if not screenshot_path.exists():
            pytest.skip("Sample screenshot fixture not available")

        response = await upload_file(
            telegram_client,
            bot_username,
            screenshot_path,
            caption="Extract the text from this image",
            timeout=60
        )

        assert response is not None, "No response to screenshot"
        # Should contain extracted text or OCR mention
        text_lower = (response.text or "").lower()
        ocr_indicators = ["text", "read", "extract", "content", "says"]
        has_ocr = any(word in text_lower for word in ocr_indicators)
        assert has_ocr, f"No OCR performed: {response.text[:200] if response.text else 'no text'}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.media
    @pytest.mark.local
    async def test_image_enhancer_skill(
        self, telegram_client, bot_username, fixtures_dir
    ):
        """Image enhancer skill queued for local execution."""
        image_path = fixtures_dir / "sample-image.jpg"
        if not image_path.exists():
            pytest.skip("Sample image fixture not available")

        response = await upload_file(
            telegram_client,
            bot_username,
            image_path,
            caption="/skill image-enhancer Enhance this image",
            timeout=45
        )

        assert response is not None, "No response to enhancer skill"
        text_lower = (response.text or "").lower()

        # Should queue for local or process
        queue_words = ["queue", "task", "local", "enhance", "process"]
        assert any(word in text_lower for word in queue_words), \
            f"Enhancer not triggered: {response.text[:200] if response.text else 'no text'}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.media
    async def test_multiple_images_handling(
        self, telegram_client, bot_username, fixtures_dir
    ):
        """Multiple images in album handled."""
        image_path = fixtures_dir / "sample-image.jpg"
        if not image_path.exists():
            pytest.skip("Sample image fixture not available")

        # Send same image twice as album (Telethon supports this)
        await telegram_client.send_file(
            bot_username,
            [image_path, image_path],
            caption="Compare these images"
        )

        import asyncio
        await asyncio.sleep(10)

        messages = await telegram_client.get_messages(bot_username, limit=5)
        bot_responses = [m for m in messages if not m.out]

        assert len(bot_responses) >= 1, "No response to album"
