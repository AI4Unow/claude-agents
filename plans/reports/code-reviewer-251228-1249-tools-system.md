# Code Review: Tools System

**Reviewer:** code-reviewer
**Date:** 2025-12-28
**Scope:** `/agents/src/tools/` directory

---

## Scope

**Files Reviewed:**
- `__init__.py` - Tool initialization (25 lines)
- `registry.py` - Tool registry (47 lines)
- `base.py` - Base tool interface (67 lines)
- `web_search.py` - Web search with Exa/Tavily (186 lines)
- `code_exec.py` - Python code execution (94 lines)
- `web_reader.py` - URL content fetching (86 lines)
- `memory_search.py` - Qdrant search (93 lines)
- `datetime_tool.py` - Datetime utility (49 lines)
- `src/core/resilience.py` - Circuit breaker implementation (270 lines)

**Lines of Code:** ~917 lines
**Review Focus:** Security, error handling, circuit breakers, timeout handling, cache management

---

## Overall Assessment

**Good:** Strong circuit breaker implementation, proper async/await patterns, structured error handling via `ToolResult`, lazy client initialization.

**Concerns:** Critical security vulnerability in code execution, unbounded cache growth, missing timeout configuration, no circuit breaker on some external calls, missing comprehensive tests.

---

## Critical Issues

### 1. **Code Execution Sandbox Bypass Risk** ⚠️ CRITICAL
**File:** `code_exec.py` lines 11-43

**Issue:** Sandbox allows `numpy` with full API access including file I/O capabilities.

```python
# Current code
import numpy as np
SAFE_BUILTINS['np'] = np  # UNSAFE: numpy has file I/O methods
SAFE_BUILTINS['numpy'] = np
```

**Risk:** User can execute:
```python
# Bypass sandbox via numpy
np.save('/tmp/malicious.npy', data)  # File write
np.load('/etc/passwd')  # File read
np.loadtxt('sensitive.csv')  # Data exfiltration
```

**Impact:** Complete sandbox escape, file system access, potential data exfiltration.

**Recommendation:**
```python
# Whitelist safe numpy functions only
SAFE_NUMPY = {
    'array': np.array,
    'arange': np.arange,
    'linspace': np.linspace,
    'zeros': np.zeros,
    'ones': np.ones,
    'mean': np.mean,
    'std': np.std,
    'median': np.median,
    'sum': np.sum,
    'min': np.min,
    'max': np.max,
    # Add other safe math functions, NOT file I/O
}
SAFE_BUILTINS.update(SAFE_NUMPY)
# Remove: SAFE_BUILTINS['np'] = np
```

### 2. **Unbounded Cache Growth** 🔴 HIGH
**File:** `web_search.py` lines 15-17, 82-85

**Issue:** Global cache dict grows indefinitely, no max size, no LRU eviction.

```python
_cache: Dict[str, tuple] = {}  # Unbounded growth

def _set_cache(self, query: str, result: str):
    key = query.lower().strip()
    _cache[key] = (result, datetime.now())  # Never evicts
```

**Impact:** Memory leak in long-running Modal deployment, potential OOM crash.

**Recommendation:**
```python
from collections import OrderedDict
from threading import Lock

MAX_CACHE_SIZE = 100
_cache: OrderedDict[str, tuple] = OrderedDict()
_cache_lock = Lock()

def _set_cache(self, query: str, result: str):
    key = query.lower().strip()
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
        _cache[key] = (result, datetime.now())
        if len(_cache) > MAX_CACHE_SIZE:
            _cache.popitem(last=False)  # LRU eviction
```

### 3. **Missing Timeout on Memory Search** 🔴 HIGH
**File:** `memory_search.py` lines 63-74

**Issue:** No timeout protection on Qdrant API calls, embedding generation.

```python
# No timeout protection
embedding = get_embedding(query)  # Can hang indefinitely
results = self.qdrant_client.search(...)  # No timeout
```

**Impact:** Telegram bot can hang indefinitely waiting for Qdrant, blocking user requests.

**Recommendation:**
```python
from src.core.resilience import qdrant_circuit

async def execute(self, params: Dict[str, Any]) -> ToolResult:
    # ... validation ...
    try:
        # Wrap in circuit breaker with timeout
        async def _search():
            embedding = get_embedding(query)
            return self.qdrant_client.search(
                collection_name="conversations",
                query_vector=embedding,
                limit=limit,
                timeout=10  # Add Qdrant timeout
            )

        results = await qdrant_circuit.call(_search, timeout=15.0)
        # ... format results ...
```

---

## High Priority Findings

### 4. **Web Reader Missing Response Size Validation** 🟠 HIGH
**File:** `web_reader.py` lines 49-56

**Issue:** Only limits content AFTER downloading entire response.

```python
response = await client.get(url, ...)  # Downloads full response
content = response.text[:MAX_CONTENT_LENGTH]  # Truncates after
```

**Impact:** DoS via large file download (e.g., 5GB video), memory exhaustion.

**Recommendation:**
```python
async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
    async with client.stream('GET', url, headers={...}) as response:
        response.raise_for_status()

        # Check content length header
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > MAX_CONTENT_LENGTH:
            return ToolResult.fail(f"Content too large: {content_length} bytes")

        # Stream and limit
        chunks = []
        total = 0
        async for chunk in response.aiter_bytes():
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_CONTENT_LENGTH:
                break

        content = b''.join(chunks).decode('utf-8', errors='ignore')
```

### 5. **Circuit Breaker Not Used Consistently** 🟠 HIGH
**File:** `web_reader.py`, `memory_search.py`

**Issue:** Web reader and memory search don't use circuit breakers.

**Files affected:**
- `web_reader.py` lines 49-71: Direct httpx calls, no circuit breaker
- `memory_search.py` lines 63-88: Direct Qdrant calls, no circuit breaker

**Impact:** No protection against cascading failures when services are down.

**Recommendation:**
```python
# web_reader.py
from src.core.resilience import CircuitBreaker
httpx_circuit = CircuitBreaker("httpx", threshold=3, cooldown=30)

async def execute(self, params: Dict[str, Any]) -> ToolResult:
    # ... validation ...
    try:
        result = await httpx_circuit.call(self._fetch_url, url, timeout=15.0)
        return result
    except CircuitOpenError as e:
        return ToolResult.fail(f"Web reader circuit open ({e.cooldown_remaining}s)")
```

### 6. **Error Messages Expose Internal State** 🟠 MEDIUM
**File:** `registry.py` line 34

**Issue:** Error truncation to 100 chars may expose partial API keys or sensitive data.

```python
return ToolResult.fail(f"Tool error: {str(e)[:100]}")
```

**Impact:** Logs may leak partial credentials if exception contains API keys.

**Recommendation:**
```python
# Sanitize error messages
def _sanitize_error(error: str) -> str:
    """Remove potential secrets from error messages."""
    import re
    # Remove API key patterns
    error = re.sub(r'(api[_-]?key["\s:=]+)[^\s"]+', r'\1***', error, flags=re.IGNORECASE)
    error = re.sub(r'(token["\s:=]+)[^\s"]+', r'\1***', error, flags=re.IGNORECASE)
    return error[:100]

return ToolResult.fail(f"Tool error: {_sanitize_error(str(e))}")
```

### 7. **No Rate Limiting on Tools** 🟠 MEDIUM
**Files:** All tool files

**Issue:** No rate limiting on tool execution, vulnerable to abuse.

**Impact:** Malicious user can spam web searches, burn API credits, DoS external services.

**Recommendation:**
```python
# registry.py
from collections import defaultdict
from datetime import datetime, timedelta

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._rate_limits: Dict[str, list] = defaultdict(list)  # tool_name -> timestamps
        self._rate_limit_window = timedelta(minutes=1)
        self._rate_limit_max = 10  # 10 calls per minute per tool

    async def execute(self, name: str, params: dict, user_id: str = None) -> ToolResult:
        # Check rate limit
        if user_id and not self._check_rate_limit(name, user_id):
            return ToolResult.fail(f"Rate limit exceeded for {name}")

        # ... existing execution logic ...
```

---

## Medium Priority Improvements

### 8. **Cache Thread Safety Issues** 🟡 MEDIUM
**File:** `web_search.py` lines 72-85

**Issue:** Cache operations not thread-safe, race conditions in concurrent access.

```python
def _get_cached(self, query: str) -> Optional[str]:
    key = query.lower().strip()
    if key in _cache:  # RACE: Check-then-act
        result, timestamp = _cache[key]
```

**Fix:** Use `threading.Lock()` for cache operations (shown in Issue #2).

### 9. **Missing Input Validation** 🟡 MEDIUM
**File:** `web_reader.py` lines 42-47

**Issue:** URL validation is superficial, doesn't prevent SSRF.

```python
if not url.startswith(("http://", "https://")):
    return ToolResult.fail("URL must start with http:// or https://")
# Missing: localhost, private IP, file:// checks
```

**Risk:** SSRF attacks to internal services.

**Recommendation:**
```python
from urllib.parse import urlparse
import ipaddress

def _validate_url(self, url: str) -> bool:
    """Validate URL is external and safe."""
    try:
        parsed = urlparse(url)

        # Check scheme
        if parsed.scheme not in ('http', 'https'):
            return False

        # Block localhost
        if parsed.hostname in ('localhost', '127.0.0.1', '::1'):
            return False

        # Block private IPs
        try:
            ip = ipaddress.ip_address(parsed.hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except ValueError:
            pass  # Not an IP, likely domain name

        return True
    except:
        return False
```

### 10. **HTML Parsing Vulnerable to XSS** 🟡 MEDIUM
**File:** `web_reader.py` lines 73-85

**Issue:** Regex-based HTML parsing misses edge cases, incomplete entity decoding.

**Recommendation:** Use proper HTML parser:
```python
from html.parser import HTMLParser
from html import unescape

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []

    def handle_data(self, data):
        self.text.append(data.strip())

    def get_text(self):
        return ' '.join(self.text)

def _html_to_text(self, html: str) -> str:
    extractor = TextExtractor()
    extractor.feed(html)
    return unescape(extractor.get_text())
```

### 11. **No Logging for Cache Performance** 🟡 LOW
**File:** `web_search.py` lines 72-85

**Issue:** Cache hit logged but no cache metrics (hit rate, size, evictions).

**Recommendation:**
```python
def get_cache_stats(self) -> dict:
    return {
        'size': len(_cache),
        'oldest_entry': min([ts for _, ts in _cache.values()], default=None),
        'newest_entry': max([ts for _, ts in _cache.values()], default=None),
    }
```

---

## Low Priority Suggestions

### 12. **Missing Type Hints** 🟢 LOW
**Files:** Multiple

Some functions lack complete type hints:
- `web_search.py` line 72: `_get_cached` return type should be `Optional[str]`
- `registry.py` line 41: `get_registry` should specify singleton return

### 13. **Magic Numbers** 🟢 LOW
**Files:** Multiple

Extract constants:
```python
# web_search.py
MAX_SEARCH_RESULTS = 5
MAX_RESULT_PREVIEW = 400
MAX_OUTPUT_LENGTH = 2000

# web_reader.py
MAX_CONTENT_LENGTH = 50000
MAX_TEXT_OUTPUT = 3000
REQUEST_TIMEOUT = 15.0
```

### 14. **No Tool Execution Metrics** 🟢 LOW

Add metrics collection for monitoring:
```python
# registry.py
async def execute(self, name: str, params: dict) -> ToolResult:
    start = time.monotonic()
    result = await tool.execute(params)
    duration_ms = int((time.monotonic() - start) * 1000)

    logger.info("tool_executed",
                tool=name,
                success=result.success,
                duration_ms=duration_ms)
    return result
```

---

## Positive Observations

✅ **Excellent circuit breaker implementation** - `resilience.py` is production-ready with proper state machine, timeouts, cooldown.

✅ **Structured error handling** - `ToolResult` pattern eliminates string-based error detection.

✅ **Lazy client initialization** - Clients only created when needed, reduces startup overhead.

✅ **Proper async/await** - All I/O operations use async patterns correctly.

✅ **Fallback mechanism** - Web search gracefully falls back from Exa to Tavily.

✅ **Clean abstractions** - `BaseTool` provides consistent interface for all tools.

---

## Recommended Actions

**Priority 1 (MUST FIX):**
1. ✅ Fix code execution sandbox - whitelist safe numpy functions only
2. ✅ Add bounded cache with LRU eviction (max 100 entries)
3. ✅ Add circuit breaker + timeout to memory search tool

**Priority 2 (SHOULD FIX):**
4. ✅ Implement streaming for web reader to prevent large downloads
5. ✅ Add circuit breakers to web reader and memory search
6. ✅ Sanitize error messages to prevent credential leaks
7. ✅ Add rate limiting per tool per user

**Priority 3 (NICE TO HAVE):**
8. ✅ Add thread-safe cache implementation
9. ✅ Implement SSRF protection in URL validation
10. ✅ Replace regex HTML parsing with proper parser
11. ✅ Add cache performance metrics
12. ✅ Write comprehensive tests for all tools

**Priority 4 (POLISH):**
13. Add complete type hints
14. Extract magic numbers to constants
15. Add tool execution metrics/monitoring

---

## Metrics

**Type Coverage:** Not measured (mypy not installed)
**Test Coverage:** 0% (no tool tests exist)
**Linting Issues:** Not measured (pylint not installed)
**Security Issues:** 1 Critical, 3 High, 4 Medium

---

## Code Examples

### Recommended Secure Code Execution

```python
# code_exec.py - SECURE VERSION
SAFE_MATH = {
    'sqrt': math.sqrt, 'sin': math.sin, 'cos': math.cos,
    'log': math.log, 'exp': math.exp, 'pi': math.pi,
}

# Whitelist ONLY safe numpy functions
SAFE_NUMPY = {
    'array': np.array,
    'arange': np.arange,
    'linspace': np.linspace,
    'zeros': np.zeros,
    'ones': np.ones,
    'mean': np.mean,
    'std': np.std,
    'median': np.median,
    'sum': np.sum,
    'min': np.min,
    'max': np.max,
    'dot': np.dot,
    'transpose': np.transpose,
    'reshape': lambda arr, shape: arr.reshape(shape) if hasattr(arr, 'reshape') else None,
}

SAFE_BUILTINS = {
    **SAFE_BASIC_BUILTINS,
    **SAFE_MATH,
    **SAFE_NUMPY,
}

# DO NOT expose np module directly
```

### Recommended Cache Implementation

```python
# web_search.py - SECURE CACHE
from collections import OrderedDict
from threading import Lock

MAX_CACHE_SIZE = 100
CACHE_TTL = timedelta(minutes=15)

class WebSearchTool(BaseTool):
    def __init__(self):
        self._cache = OrderedDict()
        self._cache_lock = Lock()

    def _get_cached(self, query: str) -> Optional[str]:
        key = query.lower().strip()
        with self._cache_lock:
            if key in self._cache:
                result, timestamp = self._cache[key]
                if datetime.now() - timestamp < CACHE_TTL:
                    self._cache.move_to_end(key)  # LRU
                    return result
                else:
                    del self._cache[key]  # Expired
        return None

    def _set_cache(self, query: str, result: str):
        key = query.lower().strip()
        with self._cache_lock:
            self._cache[key] = (result, datetime.now())
            self._cache.move_to_end(key)
            while len(self._cache) > MAX_CACHE_SIZE:
                self._cache.popitem(last=False)
```

---

## Unresolved Questions

1. **Code Execution Scope:** Should numpy be allowed at all? Consider removing entirely if not critical for use cases.

2. **Cache Strategy:** Should cache be per-tool instance or global? Current global cache shared across all WebSearchTool instances may cause issues.

3. **Rate Limiting Strategy:** Should rate limits be per-user, per-tool, or per-user-per-tool? Where should user_id come from in tool context?

4. **Test Strategy:** No tests exist. Should we add unit tests, integration tests, or both? Modal environment makes integration testing complex.

5. **Memory Search Embedding:** `get_embedding()` function not reviewed - does it have timeout protection? Where is it defined?

6. **Production Deployment:** Are these tools running in Modal sandboxed functions or shared server? Sandboxing requirements differ.

7. **Tool Discovery:** How do users know which tools are available? Should we add a `list_tools` endpoint or help tool?
