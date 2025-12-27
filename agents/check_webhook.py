"""Check Telegram webhook status."""
import modal
import os

app = modal.App("webhook-check")

image = modal.Image.debian_slim(python_version="3.11").pip_install("httpx")

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("telegram-credentials")],
)
async def check_webhook():
    """Check webhook configuration."""
    import httpx
    
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            data = response.json()
            return data
    except Exception as e:
        return {"error": str(e)}

@app.local_entrypoint()
def main():
    result = check_webhook.remote()
    print("\nWebhook Info:")
    import json
    print(json.dumps(result, indent=2))
