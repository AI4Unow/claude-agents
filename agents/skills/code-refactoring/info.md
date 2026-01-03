---
name: code-refactoring
description: Guidelines and patterns for refactoring Procaffe Python scripts, based on the Dec 2025 codebase revi
category: development
deployment: local
---

# Code Refactoring Skill

Guidelines and patterns for refactoring Procaffe Python scripts, based on the Dec 2025 codebase review.

## When to Use

- Consolidating duplicated code across scripts
- Extracting shared utility modules
- Improving code maintainability
- Reviewing scripts for DRY violations
- Moving hardcoded secrets to environment variables

---

## Shared Utility Modules

### utils.py

Core utilities used across all scripts:

```python
from utils import (
    load_env_file,      # Load .env before config import
    load_json,          # Safe JSON loading with default
    save_json,          # Atomic JSON write
    random_delay,       # Human-like gaussian delay
    setup_logger,       # Logging with file + console
)
```

**Functions:**

```python
def load_env_file(env_path: Path = None) -> None:
    """Load .env file. Call BEFORE importing config."""

def load_json(path: Path, default=None) -> dict:
    """Load JSON safely, return default if missing/invalid."""

def save_json(path: Path, data: dict, indent: int = 2) -> None:
    """Save JSON with parent directory creation."""

def random_delay(min_sec: float, max_sec: float) -> float:
    """Gaussian random delay between min and max."""

def setup_logger(name: str, log_file: str = None) -> logging.Logger:
    """Configure logger with file and console output."""
```

---

### firebase_utils.py

Singleton Firebase initialization and CRUD operations:

```python
from firebase_utils import (
    init_firebase,        # Singleton Firestore client
    get_collection_docs,  # Get all docs from collection
    upsert_document,      # Create/update document
    delete_document,      # Delete document
)
```

**Functions:**

```python
def init_firebase() -> Optional[firestore.Client]:
    """Initialize Firebase once, return cached client."""

def get_collection_docs(collection_name: str, limit: int = None) -> list:
    """Get [(doc_id, doc_dict), ...] from collection."""

def upsert_document(collection_name: str, doc_id: str, data: dict) -> bool:
    """Create or merge document. Returns success."""

def delete_document(collection_name: str, doc_id: str) -> bool:
    """Delete document. Returns success."""
```

**Why Singleton:**
- Prevents multiple Firebase initializations
- Safe to call `init_firebase()` from anywhere
- No global state management needed

---

### automation_utils.py

Chrome CDP connection and browser automation:

```python
from automation_utils import (
    connect_to_chrome,       # CDP connection with retry
    get_active_page,         # Get first page from browser
    dismiss_tiktok_modal,    # TikTok modal removal
    dismiss_linkedin_modal,  # LinkedIn modal dismissal
    scroll_modal,            # Scroll modal for lazy loading
    with_retry,              # Exponential backoff retry
)
```

**CDP Ports:**
- TikTok: 9222
- LinkedIn: 9223
- Facebook: 9224

**Functions:**

```python
async def connect_to_chrome(port: int, logger, max_retries=3):
    """Connect to Chrome via CDP with retry. Returns (playwright, browser)."""

async def dismiss_tiktok_modal(page, logger) -> bool:
    """Remove TikTok modal overlays via JavaScript."""

async def with_retry(func, max_retries=3, base_delay=2.0, logger=None):
    """Execute async function with exponential backoff."""
```

---

## Refactoring Patterns

### 1. Environment Variables

**Before (BAD):**
```python
# config.py
PINECONE_API_KEY = "pcsk_4mNEmD_..."  # Hardcoded secret!
```

**After (GOOD):**
```python
# config.py
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")

# .env
PINECONE_API_KEY=your-key-here
```

**Script Pattern:**
```python
# At TOP of script, before other imports
from utils import load_env_file
load_env_file()

# Now import config (env vars are loaded)
from config import PINECONE_API_KEY
```

---

### 2. Logging

**Before (BAD):**
```python
def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    logger = logging.getLogger("my-script")
    logger.setLevel(logging.INFO)
    # ... 20 more lines duplicated everywhere
```

**After (GOOD):**
```python
from utils import setup_logger
logger = setup_logger("my-script", "my-script/2024-12-31.log")
```

---

### 3. Firebase Initialization

**Before (BAD):**
```python
def init_firebase():
    try:
        from firebase_admin import credentials, firestore
        import firebase_admin
        # ... 20 lines duplicated in every script
```

**After (GOOD):**
```python
from firebase_utils import init_firebase
db = init_firebase()  # Singleton, safe to call multiple times
```

---

### 4. Chrome CDP Connection

**Before (BAD):**
```python
async def connect_to_chrome(logger):
    cdp_url = f"http://127.0.0.1:{TIKTOK_CDP_PORT}"
    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.connect_over_cdp(cdp_url)
        return playwright, browser
    except Exception as e:
        logger.error(f"Failed: {e}")
        await playwright.stop()
        raise
```

**After (GOOD):**
```python
from automation_utils import connect_to_chrome
from config import TIKTOK_CDP_PORT

playwright, browser = await connect_to_chrome(TIKTOK_CDP_PORT, logger)
```

---

### 5. Random Delays

**Before (BAD):**
```python
def random_delay():
    mean = (DELAY_MIN + DELAY_MAX) / 2
    std = (DELAY_MAX - DELAY_MIN) / 4
    delay = random.gauss(mean, std)
    return max(DELAY_MIN, min(DELAY_MAX, delay))
```

**After (GOOD):**
```python
from utils import random_delay
delay = random_delay(30, 90)  # Gaussian distribution
```

---

## Codebase Review Checklist

When reviewing scripts, check for:

1. **Security**
   - [ ] No hardcoded API keys in code
   - [ ] Secrets in `.env` file
   - [ ] `.env` in `.gitignore`

2. **DRY Violations**
   - [ ] `setup_logging()` duplicated? → Use `setup_logger()`
   - [ ] `init_firebase()` duplicated? → Use `firebase_utils.init_firebase()`
   - [ ] `connect_to_chrome()` duplicated? → Use `automation_utils.connect_to_chrome()`
   - [ ] `random_delay()` duplicated? → Use `utils.random_delay()`
   - [ ] JSON load/save duplicated? → Use `utils.load_json()/save_json()`

3. **Error Handling**
   - [ ] Network operations have retry logic?
   - [ ] Graceful error messages?
   - [ ] `--dry-run` mode available?

4. **Rate Limiting**
   - [ ] Delays between API calls?
   - [ ] Daily/hourly caps?
   - [ ] Human-like timing?

---

## Refactoring Plan Template

When refactoring a codebase:

```
plans/YYMMDD-codebase-refactor/
├── plan.md              # Overview and phases
├── phase-01-*.md        # Security fixes
├── phase-02-*.md        # Shared utilities
├── phase-03-*.md        # Script consolidation
└── ...
```

**Phase Order:**
1. **Security** (CRITICAL) - Move secrets to .env
2. **Shared Utils** (HIGH) - Extract common functions
3. **Script Consolidation** (MEDIUM) - Merge similar scripts
4. **Error Handling** (MEDIUM) - Add retry logic

---

## LOC Reduction Metrics

Track refactoring progress:

| Metric | Before | After | Reduction |
|--------|--------|-------|-----------|
| Duplicated LOC | ~1800 | ~200 | -89% |
| Total Scripts | 55 | 45 | -18% |
| Firebase patterns | 5 | 1 | -80% |

---

## References

- `plans/251231-1055-codebase-refactor/` - Full refactoring plan
- `scripts/utils.py` - Core utilities
- `scripts/firebase_utils.py` - Firebase utilities
- `scripts/automation_utils.py` - Chrome CDP utilities
