"""E2E tests for media handling (voice, images)."""
import pytest
import base64
from .conftest import wait_for_response


# Minimal valid PNG (1x1 transparent pixel)
TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_image_upload(telegram_client, bot_username):
    """Test image upload and analysis."""
    import io

    # Create minimal image
    image_data = base64.b64decode(TINY_PNG_B64)

    # Send image with caption
    await telegram_client.send_file(
        bot_username,
        io.BytesIO(image_data),
        caption="What is in this image?",
        file_name="test.png"
    )

    # Wait for response
    response = await wait_for_response(telegram_client, bot_username, timeout=30)

    # Bot should respond (may be vision analysis or acknowledgment)
    assert response is not None, "No response to image"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_document_upload(telegram_client, bot_username):
    """Test document upload handling."""
    import io

    # Create simple text file
    text_content = b"This is a test document for the bot."

    await telegram_client.send_file(
        bot_username,
        io.BytesIO(text_content),
        caption="Summarize this document",
        file_name="test.txt"
    )

    response = await wait_for_response(telegram_client, bot_username, timeout=30)

    # Should acknowledge or process
    assert response is not None, "No response to document"


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skip(reason="Voice requires audio file - skip for now")
async def test_voice_message(telegram_client, bot_username):
    """Test voice message handling."""
    # Would need actual audio file
    pass
