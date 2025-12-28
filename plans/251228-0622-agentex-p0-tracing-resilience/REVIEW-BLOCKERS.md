# Code Review Blockers - AgentEx P0

**Review Date:** 2025-12-28
**Reviewer:** code-reviewer
**Full Report:** plans/reports/code-reviewer-251228-1311-critical-fixes.md

## P0 Blockers (Must Fix Before Production)

### 🔴 CRITICAL-01: Code Execution Sandbox Escape

**File:** `src/tools/code_exec.py:117-121`

**Issue:** Missing `__import__` restriction allows potential sandbox escape.

**Fix:**
```python
restricted_globals = {
    "__builtins__": SAFE_BUILTINS,
    "__name__": "__main__",
    "__doc__": None,
    "__import__": lambda *args, **kwargs: None,  # Block all imports
}
```

**Status:** ❌ NOT FIXED

---

### 🔴 CRITICAL-02: Webhook Verification Fail-Open

**File:** `main.py:66-73`

**Issue:** Webhook accepts all requests if `TELEGRAM_WEBHOOK_SECRET` unset.

**Fix:**
```python
async def verify_telegram_webhook(request: Request) -> bool:
    secret_token = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
    if not secret_token:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    header_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(secret_token, header_token):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    return True
```

**Status:** ❌ NOT FIXED

---

## P1 Performance Issues (Fix This Week)

### 🟡 HIGH-01: StateManager Cache Eviction O(n)

**File:** `src/core/state.py:128-140`

**Issue:** Using `min()` for LRU eviction holds lock during O(n) scan.

**Fix:** Use OrderedDict with `popitem(last=False)` for O(1) eviction.

**Status:** ❌ NOT FIXED

---

### 🟡 HIGH-03: Web Search Cache Memory Leak

**File:** `src/tools/web_search.py:96-105`

**Issue:** Expired entries never removed from cache.

**Fix:** Add eviction in `_get_cached()` when entry expired.

**Status:** ❌ NOT FIXED

---

## Test Coverage Gaps

**Current Coverage:**
- ✅ Circuit breakers: ~90%
- ✅ Execution tracing: ~95%
- ❌ Tools: 0%
- ❌ State management: 0%
- ❌ Orchestrator: 0%
- ❌ Services: 0%

**Required:**
- Add tests for web_search, code_exec, memory_search
- Add tests for state.py cache operations
- Add tests for orchestrator DAG validation

---

## Approval Gate

**Current Status:** ⚠️ BLOCKED - 2 critical security issues

**Approval Criteria:**
1. [x] Code compiles without errors
2. [x] Circuit breakers implemented
3. [ ] **CRITICAL-01 fixed** (sandbox escape)
4. [ ] **CRITICAL-02 fixed** (webhook security)
5. [ ] HIGH-01 fixed OR accepted as tech debt
6. [ ] HIGH-03 fixed OR accepted as tech debt

**Next Steps:**
1. Apply security fixes (1-2 hours)
2. Apply performance fixes (2-3 hours)
3. Add critical path tests (3-4 hours)
4. Re-review for approval

---

**Estimated Time to Unblock:** 6-9 hours
