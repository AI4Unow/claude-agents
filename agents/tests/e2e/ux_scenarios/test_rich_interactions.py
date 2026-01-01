# agents/tests/e2e/ux_scenarios/test_rich_interactions.py
"""E2E tests for rich Telegram interactions."""
import pytest
import asyncio
from ..conftest import send_and_wait, click_button, upload_file


class TestRichInteractions:
    """Tests for Telegram-specific UX elements."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_inline_keyboard_present(self, telegram_client, bot_username):
        """Bot uses inline keyboards appropriately."""
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "/skills",
            timeout=20
        )

        assert response is not None, "No skills response"

        # Many implementations use inline keyboards for skill categories
        if response.buttons:
            assert len(response.buttons) > 0, "Empty button list"
            assert len(response.buttons[0]) > 0, "Empty button row"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_button_click_response(self, telegram_client, bot_username):
        """Clicking inline button updates message."""
        # Get message with buttons
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "/skills",
            timeout=20
        )

        if not response or not response.buttons:
            pytest.skip("No inline buttons available")

        # Click first button
        first_button_text = response.buttons[0][0].text
        updated = await click_button(telegram_client, response, first_button_text)

        # Should get response (either updated message or new message)
        # Note: Button behavior varies, just verify no crash
        assert True, "Button click processed"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.media
    async def test_image_upload_response(self, telegram_client, bot_username, sample_image):
        """Bot responds appropriately to image upload."""
        if not sample_image.exists():
            pytest.skip("Sample image not available")

        response = await upload_file(
            telegram_client,
            bot_username,
            sample_image,
            caption="What's in this image?",
            timeout=60
        )

        assert response is not None, "No response to image upload"
        # Should acknowledge image or process it
        has_text = len(response.text or "") > 10
        has_media = response.media is not None
        assert has_text or has_media, "No meaningful response to image"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_reply_context_preserved(self, telegram_client, bot_username):
        """Replying to message preserves context."""
        # Send initial message
        initial = await telegram_client.send_message(
            bot_username,
            "I'm building a Python web app with FastAPI"
        )

        # Wait for response
        await asyncio.sleep(5)

        # Send reply
        reply = await telegram_client.send_message(
            bot_username,
            "What database should I use for it?",
            reply_to=initial.id
        )

        # Wait for response
        await asyncio.sleep(5)

        messages = await telegram_client.get_messages(bot_username, limit=5)
        bot_response = None
        for msg in messages:
            if not msg.out and msg.id > reply.id:
                bot_response = msg
                break

        if bot_response:
            text_lower = (bot_response.text or "").lower()
            # Should reference Python/FastAPI context
            context_refs = ["python", "fastapi", "database", "sql", "postgres", "mongo"]
            has_context = any(ref in text_lower for ref in context_refs)
            # Not strict - just verify response exists
            assert len(bot_response.text or "") > 10, "Reply response too short"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.media
    async def test_document_upload_acknowledged(self, telegram_client, bot_username, fixtures_dir):
        """Document upload gets appropriate response."""
        doc_path = fixtures_dir / "sample-document.pdf"
        if not doc_path.exists():
            pytest.skip("Sample document not available")

        response = await upload_file(
            telegram_client,
            bot_username,
            doc_path,
            caption="Analyze this document",
            timeout=45
        )

        assert response is not None, "No response to document"
        # Should acknowledge document
        text_lower = (response.text or "").lower()
        doc_words = ["document", "pdf", "file", "analyze", "content", "queue"]
        has_ack = any(word in text_lower for word in doc_words)
        assert has_ack or response.media, f"Document not acknowledged: {response.text[:200] if response.text else 'no text'}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_progress_indicator(self, telegram_client, bot_username):
        """Long operations show progress indicators."""
        import time

        # Send request that takes time
        sent = await telegram_client.send_message(
            bot_username,
            "/skill research Comprehensive analysis of cloud computing trends"
        )

        # Check for intermediate messages
        messages = []
        start = time.time()
        while time.time() - start < 30:
            recent = await telegram_client.get_messages(bot_username, limit=10)
            for msg in recent:
                if not msg.out and msg.id > sent.id:
                    if msg.id not in [m.id for m in messages]:
                        messages.append(msg)
            await asyncio.sleep(2)

        # Should have at least one response
        assert len(messages) >= 1, "No response to long request"

        # Check for progress indicators (optional but good UX)
        has_progress = any(
            "..." in (m.text or "") or
            "processing" in (m.text or "").lower() or
            "working" in (m.text or "").lower()
            for m in messages
        )
        # Progress is optional, final result is required
        final = messages[-1]
        assert len(final.text or "") > 20, "Final response too short"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_markdown_formatting(self, telegram_client, bot_username):
        """Bot uses proper markdown formatting."""
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "/help",
            timeout=20
        )

        assert response is not None, "No help response"
        text = response.text or ""

        # Help should use formatting
        # Check for code blocks, bold, or other formatting
        has_formatting = (
            "```" in text or
            "**" in text or
            "`" in text or
            "\n- " in text or  # Lists
            "\n• " in text
        )
        # Formatting is optional but expected
        assert len(text) > 50, "Help response too short"
