# Research: Telethon for Telegram Bot E2E Testing

**Date:** 2026-01-01
**Status:** Completed
**Scope:** Telethon vs Pyrogram, Auth, Best Practices, Waiting Logic, Pitfalls

## 1. Telethon vs. Pyrogram for E2E Testing

| Feature | **Telethon** | **Pyrogram** |
| :--- | :--- | :--- |
| **Philosophy** | Low-level, closer to MTProto. Stable. | High-level, OOP, elegant. |
| **E2E Utility** | **Superior** via `conversation` helper. | Requires manual event handling for flows. |
| **Stability** | Mature, battle-tested for 7+ years. | Modern, but faster breaking changes. |
| **Testing Fit** | Best for linear scripts and protocol tests. | Best for building custom clients/UIs. |

**Verdict:** **Telethon** is preferred for E2E bot testing because its `conversation` utility allows writing linear test scripts (Send -> Wait -> Assert) without complex event loops.

## 2. Authentication & Session Management

### Credentials
- **API ID/Hash:** Required from [my.telegram.org](https://my.telegram.org).
- **Test Numbers:** Use Telegram Test DC numbers (`99966XYYYY`) to avoid bans.

### Session Management (CI/CD)
- **Problem:** Standard `.session` files (SQLite) lock when accessed by multiple processes or in ephemeral CI.
- **Solution:** Use **StringSession**.
  1. Generate locally: `print(client.session.save())`
  2. Store in env: `TELEGRAM_SESSION_STRING`.
  3. Initialize: `TelegramClient(StringSession(env_str), api_id, api_hash)`.

## 3. Best Practices for Automated Testing

1. **Session-Scoped Fixtures:** Use a single client per test session to reduce login overhead.
2. **Test Environment:** Always use `test_mode=True` or Telegram's Test DCs to avoid production rate limits.
3. **Dedicated Test User:** Never test with a production or personal account.
4. **Resilience Markers:** Mark E2E tests with `@pytest.mark.e2e` to separate them from fast unit tests.
5. **Circuit Breakers:** Integrate with project's existing resilience patterns (e.g., wrap client in retries).

## 4. Reliably Waiting for Responses

Avoid `time.sleep()`. Use these Telethon-native methods:

### Method A: Conversations (Recommended)
```python
async with client.conversation(bot_username) as conv:
    await conv.send_message("/start")
    response = await conv.get_response() # Blocks until reply
    assert "Welcome" in response.text
```

### Method B: Event-Driven (Complex Flows)
Use `NewMessage` events with a `future` to catch specific responses from the bot.

### Method C: Polling (Fallback)
```python
for _ in range(10):
    msgs = await client.get_messages(bot_username, limit=1)
    if msgs and msgs[0].id > last_cmd_id:
        return msgs[0]
    await asyncio.sleep(1)
```

## 5. Common Pitfalls & Solutions

| Pitfall | Solution |
| :--- | :--- |
| **FloodWaitError** | User API is strict. Add `asyncio.sleep(1)` between commands. Catch and wait if hit. |
| **Database Locked** | Use `StringSession` or ensure `client.disconnect()` in teardown. |
| **Interactive Buttons** | Use `message.click()` to simulate clicking InlineButtons. |
| **CI Login** | You cannot enter codes in CI. Must use pre-authorized `StringSession`. |
| **Account Bans** | Use Test DCs and avoid rapid fire of same message content. |

## Unresolved Questions
1. Should we set up a permanent Telegram Test DC account or use a rotating pool?
2. How to handle multi-step interactions (e.g., keyboard menus) in a scalable helper function?
