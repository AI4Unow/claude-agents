"""Debug script to test webhook processing logic."""
import asyncio
import os
import sys

# Simulate Modal environment
os.environ.setdefault("ANTHROPIC_API_KEY", "dummy-key")
os.environ.setdefault("ANTHROPIC_BASE_URL", "https://api.ai4u.now")
# Use centralized config default (set via ANTHROPIC_MODEL env var if needed)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dummy-token")

sys.path.insert(0, "/Users/nad/Library/CloudStorage/OneDrive-Personal/Agents/agents")

async def test_process_message():
    """Test the message processing flow."""
    print("=" * 60)
    print("Testing message processing flow...")
    print("=" * 60)

    try:
        # Import after env vars are set
        from src.services.llm import get_llm_client

        print("\n1. Testing LLM client initialization...")
        client = get_llm_client()
        print(f"   ✓ Client created: {client}")
        print(f"   - API Key: {client.api_key[:10]}...")
        print(f"   - Base URL: {client.base_url}")
        print(f"   - Model: {client.model}")

        print("\n2. Testing LLM chat call...")
        try:
            response = client.chat(
                messages=[{"role": "user", "content": "Say hello"}],
                system="You are a helpful assistant.",
                max_tokens=50,
            )
            print(f"   ✓ LLM response: {response[:100]}...")
        except Exception as e:
            print(f"   ✗ LLM call failed: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

        print("\n3. Testing Telegram send message...")
        try:
            import httpx
            token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
            url = f"https://api.telegram.org/bot{token}/sendMessage"

            async with httpx.AsyncClient() as http_client:
                result = await http_client.post(url, json={
                    "chat_id": 123456,
                    "text": "Test message",
                    "parse_mode": "Markdown",
                })
                print(f"   Status: {result.status_code}")
                print(f"   Response: {result.text[:200]}")
        except Exception as e:
            print(f"   ✗ Telegram send failed: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"\n✗ FATAL ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

if __name__ == "__main__":
    asyncio.run(test_process_message())
