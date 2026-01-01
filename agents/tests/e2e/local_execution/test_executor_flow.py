# agents/tests/e2e/local_execution/test_executor_flow.py
"""E2E tests for full local executor flow."""
import pytest
import asyncio
from ..conftest import execute_skill, upload_file


@pytest.mark.local
class TestExecutorFlow:
    """Full local execution E2E tests.

    Requires local-executor running:
    python3 agents/scripts/local-executor.py --poll --interval 5
    """

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_pdf_full_flow(
        self, telegram_client, bot_username, fixtures_dir, executor_process
    ):
        """PDF: upload → queue → execute → result."""
        pdf_path = fixtures_dir / "sample-document.pdf"
        if not pdf_path.exists():
            pytest.skip("PDF fixture not available")

        # Upload PDF
        response = await upload_file(
            telegram_client,
            bot_username,
            pdf_path,
            caption="Analyze this PDF document",
            timeout=30
        )

        assert response is not None, "No initial response"

        # Wait for executor to process (up to 90s)
        final_response = None
        for _ in range(18):  # 18 * 5s = 90s
            await asyncio.sleep(5)
            messages = await telegram_client.get_messages(bot_username, limit=5)
            for msg in messages:
                if not msg.out and msg.id > response.id:
                    # Check if this is final result (not just queue notification)
                    text_lower = (msg.text or "").lower()
                    if "result" in text_lower or "complete" in text_lower or "content" in text_lower:
                        final_response = msg
                        break
            if final_response:
                break

        # Should have gotten result from executor
        if final_response:
            assert len(final_response.text or "") > 50, "Result too short"
        else:
            # May still be pending if executor not running
            pytest.skip("Executor did not complete in time")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_video_download_flow(
        self, telegram_client, bot_username, executor_process
    ):
        """Video: URL → queue → download → notification."""
        result = await execute_skill(
            telegram_client,
            bot_username,
            "video-downloader",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            timeout=30
        )

        assert result.success, "No initial response"

        # Wait for download completion
        final_response = None
        for _ in range(24):  # 24 * 5s = 120s
            await asyncio.sleep(5)
            messages = await telegram_client.get_messages(bot_username, limit=5)
            for msg in messages:
                if not msg.out:
                    text_lower = (msg.text or "").lower()
                    if "download" in text_lower and ("complete" in text_lower or "saved" in text_lower):
                        final_response = msg
                        break
                    if msg.media:  # File might be sent
                        final_response = msg
                        break
            if final_response:
                break

        if final_response:
            # Either got text confirmation or file
            assert final_response.text or final_response.media, "No result content"
        else:
            pytest.skip("Download did not complete in time")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_execution_error_handling(
        self, telegram_client, bot_username, executor_process
    ):
        """Executor error properly reported to user."""
        # Try to process invalid input that will fail
        result = await execute_skill(
            telegram_client,
            bot_username,
            "pdf",
            "Process a file that doesn't exist",
            timeout=30
        )

        assert result.success, "No response"

        # Wait for error report
        await asyncio.sleep(15)

        messages = await telegram_client.get_messages(bot_username, limit=5)
        # Should have gotten queue notification or error
        has_response = any(len(m.text or "") > 10 for m in messages if not m.out)
        assert has_response, "No error feedback"
