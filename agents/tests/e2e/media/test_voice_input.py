# agents/tests/e2e/media/test_voice_input.py
"""E2E tests for voice message handling."""
import pytest
from ..conftest import upload_file


class TestVoiceInput:
    """Tests for voice message transcription."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.media
    async def test_voice_transcription(
        self, telegram_client, bot_username, fixtures_dir
    ):
        """Voice message transcribed and processed."""
        voice_path = fixtures_dir / "sample-voice.ogg"
        if not voice_path.exists():
            pytest.skip("Sample voice fixture not available")

        # Send as voice message
        await telegram_client.send_file(
            bot_username,
            voice_path,
            voice_note=True  # Telethon flag for voice
        )

        import asyncio
        await asyncio.sleep(10)

        messages = await telegram_client.get_messages(bot_username, limit=5)
        bot_response = None
        for msg in messages:
            if not msg.out and len(msg.text or "") > 10:
                bot_response = msg
                break

        assert bot_response is not None, "No response to voice message"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.media
    async def test_voice_with_skill_trigger(
        self, telegram_client, bot_username, fixtures_dir
    ):
        """Voice containing skill trigger word routed correctly."""
        # This test assumes voice contains "skill planning" or similar
        # Requires specific voice fixture
        voice_path = fixtures_dir / "sample-voice-command.ogg"
        if not voice_path.exists():
            pytest.skip("Command voice fixture not available")

        await telegram_client.send_file(
            bot_username,
            voice_path,
            voice_note=True
        )

        import asyncio
        await asyncio.sleep(15)

        messages = await telegram_client.get_messages(bot_username, limit=5)
        bot_response = None
        for msg in messages:
            if not msg.out:
                bot_response = msg
                break

        # Should route to skill or ask for clarification
        assert bot_response is not None, "No response to voice command"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.media
    @pytest.mark.slow
    async def test_long_voice_message(
        self, telegram_client, bot_username, fixtures_dir
    ):
        """Long voice message (>1 min) handled."""
        voice_path = fixtures_dir / "sample-voice-long.ogg"
        if not voice_path.exists():
            pytest.skip("Long voice fixture not available")

        await telegram_client.send_file(
            bot_username,
            voice_path,
            voice_note=True
        )

        import asyncio
        await asyncio.sleep(30)  # Longer wait for transcription

        messages = await telegram_client.get_messages(bot_username, limit=5)
        bot_response = None
        for msg in messages:
            if not msg.out:
                bot_response = msg
                break

        assert bot_response is not None, "No response to long voice"
