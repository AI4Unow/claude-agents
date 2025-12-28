# Phase 04: Admin Authentication

## Context

- **Parent Plan:** [plan.md](./plan.md)
- **Issue:** Code review #11 - /api/circuits endpoints lack authentication
- **Related:** `main.py:91-102`

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-28 |
| Priority | MEDIUM |
| Effort | 1h |
| Implementation | pending |
| Review | pending |

## Problem

Admin endpoints exposed without authentication:
- `GET /api/circuits` - Exposes internal state
- `POST /api/circuits/reset` - Can DOS by repeated resets
- `GET /api/traces` - Exposes execution data

## Solution

Add simple token-based authentication:

```python
async def verify_admin_token(x_admin_token: str = Header(None)):
    expected = os.environ.get("ADMIN_API_TOKEN")
    if not expected or x_admin_token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
```

## Related Files

| File | Lines | Action |
|------|-------|--------|
| `main.py` | 91-102 | Add authentication dependency |

## Implementation Steps

1. Create Modal secret `admin-credentials` with `ADMIN_API_TOKEN`
2. Add `verify_admin_token` dependency function
3. Apply to `/api/circuits`, `/api/circuits/reset`, `/api/traces` endpoints
4. Keep `/health` public (needed for monitoring)

## Code Changes

### Modal Secret

```bash
modal secret create admin-credentials ADMIN_API_TOKEN=$(openssl rand -hex 32)
```

### main.py

```python
# Add imports at top of create_web_app()
from fastapi import Header, HTTPException, Depends

# Add dependency function
async def verify_admin_token(x_admin_token: str = Header(None)):
    """Verify admin authorization."""
    expected = os.environ.get("ADMIN_API_TOKEN")
    if not expected or x_admin_token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

# Update endpoints
@web_app.get("/api/traces")
async def list_traces_endpoint(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 20,
    _: None = Depends(verify_admin_token)  # NEW
):
    ...

@web_app.get("/api/traces/{trace_id}")
async def get_trace_endpoint(
    trace_id: str,
    _: None = Depends(verify_admin_token)  # NEW
):
    ...

@web_app.get("/api/circuits")
async def get_circuits_endpoint(
    _: None = Depends(verify_admin_token)  # NEW
):
    ...

@web_app.post("/api/circuits/reset")
async def reset_circuits_endpoint(
    _: None = Depends(verify_admin_token)  # NEW
):
    ...
```

### Update secrets list in app definition

```python
secrets = [
    modal.Secret.from_name("anthropic-credentials"),
    modal.Secret.from_name("firebase-credentials"),
    modal.Secret.from_name("telegram-credentials"),
    modal.Secret.from_name("qdrant-credentials"),
    modal.Secret.from_name("exa-credentials"),
    modal.Secret.from_name("tavily-credentials"),
    modal.Secret.from_name("admin-credentials"),  # NEW
]
```

## Usage

```bash
# Get circuits status
curl -H "X-Admin-Token: your-token-here" \
  https://duc-a-nguyen--claude-agents-telegram-chat-agent.modal.run/api/circuits

# Reset circuits
curl -X POST -H "X-Admin-Token: your-token-here" \
  https://duc-a-nguyen--claude-agents-telegram-chat-agent.modal.run/api/circuits/reset
```

## Todo List

- [ ] Create Modal secret `admin-credentials`
- [ ] Add `verify_admin_token` function to main.py
- [ ] Update `/api/traces` endpoints
- [ ] Update `/api/circuits` endpoints
- [ ] Add secret to TelegramChatAgent secrets list
- [ ] Test unauthorized access returns 401

## Success Criteria

- [ ] All admin endpoints require X-Admin-Token header
- [ ] Invalid/missing token returns 401 Unauthorized
- [ ] /health remains public (no auth required)
- [ ] Token stored securely in Modal Secrets

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Token leaked in logs | HIGH | Never log token value |
| Forgot to protect endpoint | MEDIUM | Review all new endpoints |
| Token rotation | LOW | Update Modal secret and redeploy |

## Security Considerations

- Use cryptographically random token (32+ bytes)
- Store in Modal Secrets, not env files
- Rotate token periodically
- Consider rate limiting on auth failures (future)

## Next Steps

After this phase, proceed to [Phase 05](./phase-05-unit-tests.md).
