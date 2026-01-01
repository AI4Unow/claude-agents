# agents/tests/e2e/skills/test_local_skills.py
"""E2E tests for local skills (queued for local executor)."""
import pytest
from ..conftest import execute_skill, upload_file

LOCAL_SKILLS = [
    ("pdf", "Analyze this document"),
    ("docx", "Summarize this document"),
    ("xlsx", "Analyze this spreadsheet"),
    ("pptx", "Summarize this presentation"),
    ("video-downloader", "Download this video"),
    ("image-enhancer", "Enhance this image"),
    ("media-processing", "Process this media"),
    ("canvas-design", "Create a simple design"),
]


class TestLocalSkills:
    """Tests for locally executed skills (verify queue behavior)."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.parametrize("skill_name,prompt", LOCAL_SKILLS)
    async def test_local_skill_queued(self, telegram_client, bot_username, skill_name, prompt):
        """Test local skill gets queued notification."""
        result = await execute_skill(
            telegram_client,
            bot_username,
            skill_name,
            prompt,
            timeout=30
        )

        assert result.success, f"Local skill '{skill_name}' failed to respond"
        text_lower = result.text.lower()

        # Should indicate task was queued for local execution
        assert any(word in text_lower for word in ["queue", "local", "task", "pending", "wait"]), \
            f"Expected queue notification for '{skill_name}', got: {result.text[:200]}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.media
    async def test_pdf_with_file(self, telegram_client, bot_username, fixtures_dir):
        """Test PDF skill with actual file upload."""
        pdf_path = fixtures_dir / "sample-document.pdf"
        if not pdf_path.exists():
            pytest.skip("PDF fixture not available")

        response = await upload_file(
            telegram_client,
            bot_username,
            pdf_path,
            caption="Analyze this PDF"
        )

        assert response is not None, "No response to PDF upload"
        text_lower = (response.text or "").lower()

        # Should queue for local processing
        assert any(word in text_lower for word in ["queue", "processing", "document", "analyze"]), \
            f"Unexpected PDF response: {response.text[:200] if response.text else '(no text)'}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.media
    async def test_docx_with_file(self, telegram_client, bot_username, fixtures_dir):
        """Test DOCX skill with actual file upload."""
        docx_path = fixtures_dir / "sample-word.docx"
        if not docx_path.exists():
            pytest.skip("DOCX fixture not available")

        response = await upload_file(
            telegram_client,
            bot_username,
            docx_path,
            caption="Summarize this document"
        )

        assert response is not None, "No response to DOCX upload"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.media
    async def test_xlsx_with_file(self, telegram_client, bot_username, fixtures_dir):
        """Test XLSX skill with actual file upload."""
        xlsx_path = fixtures_dir / "sample-spreadsheet.xlsx"
        if not xlsx_path.exists():
            pytest.skip("XLSX fixture not available")

        response = await upload_file(
            telegram_client,
            bot_username,
            xlsx_path,
            caption="Analyze this data"
        )

        assert response is not None, "No response to XLSX upload"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_video_downloader_with_url(self, telegram_client, bot_username):
        """Test video downloader with YouTube URL."""
        from ..conftest import send_and_wait

        # Use a known short public video
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "Download this video: https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            timeout=30
        )

        assert response is not None, "No response to video URL"
        text_lower = (response.text or "").lower()

        # Should recognize video URL and queue or offer download
        assert any(word in text_lower for word in ["video", "download", "queue", "youtube"]), \
            f"Unexpected video response: {response.text[:200] if response.text else '(no text)'}"
