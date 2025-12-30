# Phase 6: Testing & Deployment

**Status:** Ready
**Dependencies:** All previous phases
**Output:** Production-ready WhatsApp integration

## Overview

Final integration, testing, and production deployment. Includes circuit breaker, tracing, and webhook configuration.

## Tasks

### 6.1 Add WhatsApp Circuit Breaker to Registry

**Update `src/core/resilience.py`:**

```python
# Add to existing circuit breakers dictionary
CIRCUITS = {
    "claude": CircuitBreaker("claude", threshold=3, cooldown=30),
    "exa": CircuitBreaker("exa", threshold=3, cooldown=30),
    "tavily": CircuitBreaker("tavily", threshold=3, cooldown=30),
    "firebase": CircuitBreaker("firebase", threshold=5, cooldown=60),
    "qdrant": CircuitBreaker("qdrant", threshold=3, cooldown=30),
    "telegram": CircuitBreaker("telegram", threshold=5, cooldown=30),
    "gemini": CircuitBreaker("gemini", threshold=3, cooldown=30),
    "whatsapp": CircuitBreaker("whatsapp", threshold=3, cooldown=30),  # NEW
}
```

### 6.2 Update Secrets List in main.py

```python
secrets = [
    modal.Secret.from_name("anthropic-credentials"),
    modal.Secret.from_name("firebase-credentials"),
    modal.Secret.from_name("telegram-credentials"),
    modal.Secret.from_name("qdrant-credentials"),
    modal.Secret.from_name("exa-credentials"),
    modal.Secret.from_name("tavily-credentials"),
    modal.Secret.from_name("admin-credentials"),
    modal.Secret.from_name("groq-credentials"),
    modal.Secret.from_name("gcp-credentials"),
    modal.Secret.from_name("whatsapp-credentials"),  # NEW
]
```

### 6.3 Add Trace Logging for WhatsApp

**In webhook handler:**

```python
@web_app.api_route("/webhook/whatsapp", methods=["GET", "POST"])
async def whatsapp_webhook(request: Request):
    from src.core.trace import create_trace, end_trace

    # ... verification ...

    try:
        data = await request.json()
        msg = parse_webhook(Platform.WHATSAPP, data)
        if not msg:
            return {"status": "ok"}

        # Create trace for this interaction
        trace = await create_trace(
            user_id=msg.user.user_id,
            skill=None,  # Determined later
            input_text=msg.text or "[media]",
            platform="whatsapp"
        )

        try:
            response = await process_normalized_message(msg)

            if response:
                await send_message(msg.chat_id, response)

            await end_trace(trace.trace_id, status="success", output=response[:500] if response else None)

        except Exception as e:
            await end_trace(trace.trace_id, status="error", error=str(e))
            raise

        return {"status": "ok"}

    except Exception as e:
        logger.error("whatsapp_webhook_error", error=str(e))
        return {"status": "error"}
```

### 6.4 Update Health Endpoint

```python
@web_app.get("/health")
async def health():
    """Health check endpoint with circuit status."""
    from src.core.resilience import get_circuit_stats

    circuits = get_circuit_stats()
    any_open = any(c["state"] == "open" for c in circuits.values())

    return {
        "status": "degraded" if any_open else "healthy",
        "agent": "claude-agents",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.1.0",  # Version bump
        "circuits": circuits,
        "platforms": ["telegram", "whatsapp"]  # NEW
    }
```

### 6.5 Testing with Test Number

**Test sequence:**

1. **Deploy to Modal:**
   ```bash
   modal deploy agents/main.py
   ```

2. **Configure webhook in Meta Dashboard:**
   - Go to App Dashboard → WhatsApp → Configuration
   - Webhook URL: `https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run/webhook/whatsapp`
   - Verify Token: (from WHATSAPP_VERIFY_TOKEN secret)
   - Subscribe to: `messages`

3. **Test verification:**
   ```bash
   curl "https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=test123"
   # Should return: test123
   ```

4. **Send test messages from WhatsApp:**
   - Text: "Hello" → Should respond
   - Command: "/help" → Should show help
   - Voice: Send voice note → Should transcribe
   - Image: Send photo → Should analyze
   - Document: Send PDF → Should summarize

5. **Monitor logs:**
   ```bash
   modal app logs claude-agents
   ```

### 6.6 Production Checklist

**Before going live:**

- [ ] Business verification complete (if needed)
- [ ] Production phone number configured
- [ ] Permanent access token generated
- [ ] All secrets updated in Modal
- [ ] Webhook URL verified working
- [ ] Test all message types
- [ ] Circuit breaker tested (force failure)
- [ ] Traces appearing in Firebase
- [ ] Rate limiting working

### 6.7 Update Documentation

**Update `CLAUDE.md`:**

```markdown
### Platforms
- **Telegram:** Primary chat interface
- **WhatsApp:** Secondary chat interface (Cloud API)

### Secrets Required
...
modal secret create whatsapp-credentials \
  WHATSAPP_TOKEN=... \
  WHATSAPP_PHONE_ID=... \
  WHATSAPP_BUSINESS_ID=... \
  WHATSAPP_APP_SECRET=... \
  WHATSAPP_VERIFY_TOKEN=...
```

**Update `docs/system-architecture.md`:**

Add WhatsApp to architecture diagram and webhook endpoints list.

### 6.8 Error Handling for 24h Window

WhatsApp's 24-hour messaging window requires special handling:

```python
async def send_message_with_fallback(phone: str, text: str) -> bool:
    """Send message, handling 24h window expiry."""
    from src.services.whatsapp import send_message

    success, msg_id = await send_message(phone, text)

    if not success:
        # Check if it's a window expiry error
        # If so, could send template message instead
        logger.warning("whatsapp_send_failed", phone=phone[:6] + "...")
        # For now, just log - template implementation is separate
        return False

    return True
```

### 6.9 Personalization Integration

Ensure personalization works with WhatsApp users:

```python
# In process_normalized_message or wherever personalization is loaded

# WhatsApp uses phone as user_id
user_id_for_personalization = msg.user.user_id

# Load personalization context
from src.services.personalization import load_personal_context
context = await load_personal_context(user_id_for_personalization)
```

**Note:** WhatsApp user IDs are phone numbers (strings), while Telegram uses integers. The personalization system uses string keys in Firebase, so this should work without modification.

## Deployment Commands

```bash
# Deploy
modal deploy agents/main.py

# Check logs
modal app logs claude-agents

# Test health
curl https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run/health

# Check circuits
curl -H "X-Admin-Token: $ADMIN_TOKEN" \
  https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run/api/circuits
```

## Rollback Plan

If issues arise:

1. **Remove webhook from Meta Dashboard** (stops new messages)
2. **Redeploy previous version:**
   ```bash
   git checkout HEAD~1 agents/main.py
   modal deploy agents/main.py
   ```
3. **Investigate logs**
4. **Fix and redeploy**

## Success Criteria

- [ ] WhatsApp messages processed end-to-end
- [ ] Text, voice, image, document messages work
- [ ] Commands work identically to Telegram
- [ ] Circuit breaker protects API
- [ ] Traces logged for debugging
- [ ] Personalization loads for WhatsApp users
- [ ] Health endpoint shows WhatsApp circuit status
- [ ] Error handling graceful (24h window, rate limits)

## Post-Deployment Monitoring

First 24 hours:
- Monitor error rates in logs
- Check circuit breaker state
- Verify traces in Firebase
- Test edge cases (long messages, special characters)

First week:
- Monitor rate limit usage
- Track message volumes
- Review any improvement proposals
- Gather user feedback
