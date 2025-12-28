# Phase 4: Main Security Fixes

## Files
- `agents/main.py`

## Issues

### 1. Missing Rate Limiting (CRITICAL)
**Fix:** Add slowapi middleware

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

def create_web_app():
    web_app = FastAPI()
    web_app.state.limiter = limiter
    web_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @web_app.post("/webhook/telegram")
    @limiter.limit("30/minute")  # 30 requests per minute per IP
    async def telegram_webhook(request: Request):
        ...
```

### 2. Missing Webhook Signature Verification (CRITICAL)
**Fix:** Verify Telegram secret token

```python
import hmac
import hashlib

async def verify_telegram_webhook(request: Request) -> bool:
    """Verify Telegram webhook using secret token."""
    secret_token = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    if not secret_token:
        return True  # No verification configured

    header_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    return hmac.compare_digest(secret_token, header_token)

@web_app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    if not await verify_telegram_webhook(request):
        raise HTTPException(status_code=401, detail="Invalid webhook token")
    ...
```

### 3. Blocking I/O in Async (HIGH)
**Fix:** Use aiofiles for file operations

```python
import aiofiles

async def process_message(text: str, user: dict, chat_id: int) -> str:
    info_path = Path("/skills/telegram-chat/info.md")
    system_prompt = "You are a helpful AI assistant..."

    if info_path.exists():
        async with aiofiles.open(info_path, 'r') as f:
            system_prompt = await f.read()
```

### 4. Extract Telegram Helpers (DRY)
**Fix:** Create telegram.py service with shared client

```python
# In src/services/telegram.py
class TelegramClient:
    def __init__(self):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._client = None

    async def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML"):
        ...

    async def send_keyboard(self, chat_id: int, text: str, keyboard: list):
        ...
```

## Success Criteria
- [x] Rate limiting active (30 req/min)
- [x] Webhook signature verified
- [x] No blocking file I/O
- [x] Telegram helpers extracted
