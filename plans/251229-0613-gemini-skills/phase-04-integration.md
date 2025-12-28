# Phase 4: Integration & Telegram Streaming

**Status:** Pending
**Depends on:** Phase 3
**Files:** `main.py`, `src/services/telegram.py`

---

## Tasks

### 4.1 Add Telegram Progress Updates

**File:** `agents/src/services/telegram.py`

Add function at end of file:

```python
async def update_progress_message(
    chat_id: int,
    message_id: int,
    text: str,
    bot_token: str = None,
) -> bool:
    """Update existing message with progress (for streaming).

    Uses edit_message_text to update in-place.
    Rate limited by Telegram to ~30 edits/minute.

    Args:
        chat_id: Telegram chat ID
        message_id: Message ID to update
        text: New message text
        bot_token: Optional bot token override

    Returns:
        True if update successful
    """
    import httpx
    import os

    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/editMessageText"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "HTML",
            })
            return response.status_code == 200
    except Exception:
        return False


async def send_with_progress(
    chat_id: int,
    initial_text: str,
    bot_token: str = None,
) -> int:
    """Send initial message and return message_id for progress updates.

    Args:
        chat_id: Telegram chat ID
        initial_text: Initial message text
        bot_token: Optional bot token override

    Returns:
        message_id for subsequent updates
    """
    import httpx
    import os

    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={
                "chat_id": chat_id,
                "text": initial_text,
                "parse_mode": "HTML",
            })
            if response.status_code == 200:
                return response.json()["result"]["message_id"]
            return 0
    except Exception:
        return 0
```

---

### 4.2 Integrate Progress with Deep Research

**File:** `agents/main.py`

In the Telegram webhook handler, when invoking deep research:

```python
async def handle_gemini_research(text: str, chat_id: int, user: dict):
    """Handle deep research with progress streaming."""
    from src.services.telegram import send_with_progress, update_progress_message
    from src.tools.gemini_tools import execute_deep_research

    # Send initial message
    message_id = await send_with_progress(
        chat_id=chat_id,
        initial_text="🔍 Starting deep research..."
    )

    # Progress callback
    async def on_progress(status: str):
        await update_progress_message(
            chat_id=chat_id,
            message_id=message_id,
            text=f"🔍 {status}"
        )

    # Execute research
    result = await execute_deep_research(
        query=text,
        user_id=user.get("id", 0),
        chat_id=chat_id,
        progress_callback=on_progress,
    )

    # Send final result
    if result["success"]:
        await update_progress_message(
            chat_id=chat_id,
            message_id=message_id,
            text=f"✅ Research complete!\n\n{result['summary'][:1000]}"
        )
    else:
        await update_progress_message(
            chat_id=chat_id,
            message_id=message_id,
            text=f"❌ Research failed: {result.get('error', 'Unknown')}"
        )

    return result
```

---

### 4.3 Add Test Functions to main.py

**File:** `agents/main.py`

Add at end of file:

```python
@app.local_entrypoint()
def test_gemini():
    """Test Gemini client initialization."""
    import asyncio
    from src.services.gemini import get_gemini_client

    async def run():
        client = get_gemini_client()
        print(f"Project: {client.project_id}")
        print(f"Location: {client.location}")

        result = await client.chat(
            messages=[{"role": "user", "content": "Hello, test message"}],
            thinking_level="minimal"
        )
        print(f"Response: {result[:200]}")

    asyncio.run(run())


@app.local_entrypoint()
def test_grounding():
    """Test grounded query."""
    import asyncio
    from src.services.gemini import get_gemini_client

    async def run():
        client = get_gemini_client()
        result = await client.grounded_query(
            query="What's the current price of Bitcoin?"
        )
        print(f"Answer: {result.text[:200]}")
        print(f"Citations: {len(result.citations)}")

    asyncio.run(run())


@app.local_entrypoint()
def test_deep_research():
    """Test deep research skill."""
    import asyncio
    from src.tools.gemini_tools import execute_deep_research

    async def run():
        def progress(s):
            print(f"Progress: {s}")

        result = await execute_deep_research(
            query="Current state of AI agents in 2025",
            progress_callback=progress,
            max_iterations=2
        )
        print(f"Success: {result['success']}")
        if result['success']:
            print(f"Summary: {result['summary'][:300]}")
            print(f"Queries: {result['query_count']}")
            print(f"Duration: {result['duration_seconds']:.1f}s")

    asyncio.run(run())
```

---

### 4.4 Verify Skills in Registry

After deployment, check skills are visible:

```bash
curl https://your-modal-url/api/skills | jq '.[] | select(.name | startswith("gemini"))'
```

Expected output:
```json
{"name": "gemini-deep-research", "category": "research", "deployment": "remote"}
{"name": "gemini-grounding", "category": "research", "deployment": "both"}
{"name": "gemini-thinking", "category": "reasoning", "deployment": "remote"}
{"name": "gemini-vision", "category": "vision", "deployment": "both"}
```

---

## Completion Criteria

- [ ] `update_progress_message()` function works
- [ ] `send_with_progress()` returns message_id
- [ ] Deep research streams progress to Telegram
- [ ] Test functions run successfully via `modal run`
- [ ] All 4 Gemini skills visible in `/api/skills`
