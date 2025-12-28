# Phase 1B: Tools Stability Fixes

## Files
- `agents/src/tools/web_reader.py`
- `agents/src/tools/memory_search.py`

## Issues

### 1. Web Reader DoS Vulnerability (HIGH)
**File:** web_reader.py
**Problem:** Downloads entire response before size check
**Fix:** Stream with early termination

```python
# BEFORE
response = await client.get(url)
content = response.text
if len(content) > MAX_SIZE:
    content = content[:MAX_SIZE]

# AFTER
async with client.stream("GET", url) as response:
    chunks = []
    total = 0
    async for chunk in response.aiter_bytes(chunk_size=8192):
        total += len(chunk)
        if total > MAX_SIZE:
            break
        chunks.append(chunk)
    content = b"".join(chunks).decode('utf-8', errors='ignore')
```

### 2. Missing Timeout on Memory Search (HIGH)
**File:** memory_search.py
**Problem:** No timeout on Qdrant/embedding calls
**Fix:** Add circuit breaker with timeout

```python
from src.core.resilience import qdrant_circuit

async def execute(self, params: Dict[str, Any]) -> ToolResult:
    query = params.get("query", "")

    try:
        result = await qdrant_circuit.call(
            self._search,
            query,
            timeout=15.0
        )
        return result
    except CircuitOpenError as e:
        return ToolResult.fail(f"Memory search unavailable ({e.cooldown_remaining}s)")
```

## Success Criteria
- [x] Large URLs don't cause memory exhaustion
- [x] Memory search has 15s timeout
- [x] Circuit breaker protects Qdrant calls

## Implementation Status
**COMPLETED** - 2025-12-28

### Changes Applied
1. web_reader.py: Streaming with early termination (lines 41-80)
2. memory_search.py: Circuit breaker with 15s timeout (lines 1-8, 54-104)

### Verification
- Syntax check: PASS (both modules import successfully)
- Files modified: 2
- Report: plans/reports/fullstack-developer-251228-1302-phase-01b-tools-stability.md
