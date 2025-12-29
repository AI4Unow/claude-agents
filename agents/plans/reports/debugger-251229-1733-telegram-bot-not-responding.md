# Telegram Bot Non-Responsiveness Investigation

**Date:** 2025-12-29 17:33 UTC
**Investigator:** Debugger Agent
**Status:** Root cause identified

## Executive Summary

Telegram bot completely non-responsive to messages. Root cause: webhook verification requires `TELEGRAM_WEBHOOK_SECRET` env var but it's not configured in Modal secrets, causing all webhook requests to fail with 500 error.

**Impact:** All Telegram messages rejected since security fix deployment (commit a7cfd84, Dec 28).

**Fix:** Add `TELEGRAM_WEBHOOK_SECRET` to `telegram-credentials` Modal secret.

## Evidence

### 1. Health Check - PASS
```bash
curl https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run/health
```
**Result:** Healthy, circuits closed, app deployed and running.

### 2. Webhook Test - FAIL
```bash
curl -X POST /webhook/telegram -d '{"update_id":1,"message":{...}}'
```
**Response:**
```json
{"detail":"Webhook verification not configured"}
```
**HTTP Status:** 500

### 3. Code Analysis
**File:** `agents/main.py:117-135`

```python
async def verify_telegram_webhook(request: Request) -> bool:
    """Verify Telegram webhook using secret token (timing-safe comparison).

    SECURITY: Fail-closed - requires secret to be configured in production.
    Set TELEGRAM_WEBHOOK_SECRET="" explicitly to disable (not recommended).
    """
    secret_token = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
    if secret_token is None:  # ← FAILS HERE
        import structlog
        structlog.get_logger().warning("telegram_webhook_secret_not_configured")
        raise HTTPException(status_code=500, detail="Webhook verification not configured")
```

**Issue:** `TELEGRAM_WEBHOOK_SECRET` not in environment → raises 500 → webhook never processes.

### 4. Git History
**Commit:** a7cfd84 (Dec 28, 2025)
**Title:** "fix: critical security + reliability fixes (14 issues)"
**Change:** Added fail-closed webhook verification for security hardening.

**Breaking change:** Introduced new required env var without updating secrets.

## Root Cause

Security fix (a7cfd84) added mandatory `TELEGRAM_WEBHOOK_SECRET` validation. Modal secret `telegram-credentials` lacks this key. All webhook requests fail verification before reaching message handler.

**Flow:**
```
Telegram → POST /webhook/telegram → verify_telegram_webhook()
  → os.environ.get("TELEGRAM_WEBHOOK_SECRET") = None
  → HTTPException(500)
  → User never gets response
```

## Recommended Fix

### Immediate (5 min)
```bash
# Option 1: Add secret token
modal secret update telegram-credentials \
  TELEGRAM_BOT_TOKEN=<existing> \
  TELEGRAM_WEBHOOK_SECRET=<random_token>

# Then configure Telegram webhook:
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run/webhook/telegram",
    "secret_token": "<same_random_token>"
  }'

# Option 2: Explicitly disable (not recommended)
modal secret update telegram-credentials \
  TELEGRAM_BOT_TOKEN=<existing> \
  TELEGRAM_WEBHOOK_SECRET=""
```

### Long-term
1. Document required secrets in `docs/deployment-guide.md`
2. Add env var validation at startup with clear error messages
3. Add deployment checklist to prevent similar issues

## Verification Steps

After fix:
1. `curl /webhook/telegram` should return `{"ok": true}` not 500
2. Send test message to bot → should respond
3. Check Modal logs: should see `telegram_update` not `telegram_webhook_secret_not_configured`

## Timeline

- **Dec 27, 07:55 UTC** - App deployed (last successful)
- **Dec 28, 13:32 UTC** - Security fix committed (a7cfd84)
- **Dec 28-29** - Bot non-responsive period
- **Dec 29, 17:33 UTC** - Root cause identified

## Unresolved Questions

1. Was webhook secret configured in Telegram's setWebhook call previously?
2. Are there automated health checks for webhook functionality?
3. Should deployment block if required secrets missing?
