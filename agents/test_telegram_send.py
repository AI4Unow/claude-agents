"""Test if Telegram send works in Modal environment."""
import modal
import os

app = modal.App("telegram-send-test")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("httpx")
)

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("telegram-credentials")],
)
async def test_send_message():
    """Test sending a Telegram message."""
    import httpx
    
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    print(f"Token found: {bool(token)}")
    print(f"Token length: {len(token)}")
    print(f"Token prefix: {token[:10] if token else 'N/A'}...")
    
    if not token:
        return {"status": "error", "error": "No TELEGRAM_BOT_TOKEN"}
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            result = await client.post(url, json={
                "chat_id": 999999,  # This will fail but shows if API works
                "text": "Test message from Modal",
                "parse_mode": "Markdown",
            })
            return {
                "status": "sent",
                "status_code": result.status_code,
                "response": result.text[:500],
            }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "type": type(e).__name__,
        }

@app.local_entrypoint()
def main():
    result = test_send_message.remote()
    print("\nResult:", result)
