"""Media handling service for Telegram (download, transcribe, encode)."""
import os
import base64
import httpx
import tempfile
from typing import Optional


async def download_telegram_file(file_id: str) -> bytes:
    """Download file from Telegram servers.

    Args:
        file_id: Telegram file_id from message

    Returns:
        File content as bytes
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Get file path from Telegram
        resp = await client.get(
            f"https://api.telegram.org/bot{token}/getFile",
            params={"file_id": file_id}
        )
        data = resp.json()

        if not data.get("ok"):
            raise ValueError(f"Failed to get file: {data}")

        file_path = data["result"]["file_path"]

        # Download file content
        file_resp = await client.get(
            f"https://api.telegram.org/file/bot{token}/{file_path}"
        )
        return file_resp.content


async def transcribe_audio_groq(audio_bytes: bytes, duration: int = 0) -> str:
    """Transcribe audio using Groq Whisper API.

    Args:
        audio_bytes: OGG audio bytes from Telegram
        duration: Audio duration in seconds

    Returns:
        Transcribed text
    """
    # Enforce 60 second limit
    if duration > 60:
        raise ValueError("Voice message too long. Max 60 seconds.")

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not configured")

    # Save to temp file (Groq API needs file upload)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(audio_bytes)
        temp_path = f.name

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            with open(temp_path, "rb") as audio_file:
                response = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={"file": ("audio.ogg", audio_file, "audio/ogg")},
                    data={"model": "whisper-large-v3-turbo", "language": "en"}
                )

            if response.status_code != 200:
                raise ValueError(f"Groq API error: {response.text}")

            result = response.json()
            return result.get("text", "")

    finally:
        os.unlink(temp_path)


def encode_image_base64(image_bytes: bytes) -> str:
    """Encode image bytes to base64 for Claude Vision."""
    return base64.standard_b64encode(image_bytes).decode("utf-8")


def get_media_type(file_path: str) -> str:
    """Determine media type from file extension."""
    ext = file_path.lower().split(".")[-1]
    types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp"
    }
    return types.get(ext, "image/jpeg")


async def extract_pdf_text(pdf_bytes: bytes, max_chars: int = 10000) -> str:
    """Extract text from PDF bytes.

    Args:
        pdf_bytes: PDF file content
        max_chars: Maximum characters to extract

    Returns:
        Extracted text (truncated if needed)
    """
    from pypdf import PdfReader
    import io

    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages_text = []

    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages_text.append(text)

    full_text = "\n".join(pages_text)

    if len(full_text) > max_chars:
        return full_text[:max_chars] + "\n\n[Truncated...]"

    return full_text
