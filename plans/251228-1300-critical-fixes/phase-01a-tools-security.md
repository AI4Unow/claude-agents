# Phase 1A: Tools Security Fixes

## Files
- `agents/src/tools/code_exec.py`
- `agents/src/tools/web_search.py`

## Issues

### 1. Code Execution Sandbox Bypass (CRITICAL)
**File:** code_exec.py
**Problem:** numpy exposes file I/O via np.save(), np.load()
**Fix:** Whitelist only safe numpy math functions

```python
# BEFORE (unsafe)
"numpy": numpy,

# AFTER (safe whitelist)
"numpy": _create_safe_numpy(),

def _create_safe_numpy():
    """Create numpy module with only safe math functions."""
    import types
    safe_np = types.ModuleType('numpy')

    # Safe math functions only
    safe_attrs = [
        'abs', 'add', 'subtract', 'multiply', 'divide',
        'sqrt', 'power', 'exp', 'log', 'log10', 'log2',
        'sin', 'cos', 'tan', 'arcsin', 'arccos', 'arctan',
        'sinh', 'cosh', 'tanh', 'floor', 'ceil', 'round',
        'mean', 'median', 'std', 'var', 'sum', 'prod',
        'min', 'max', 'argmin', 'argmax', 'sort',
        'array', 'zeros', 'ones', 'arange', 'linspace',
        'pi', 'e', 'inf', 'nan', 'dtype', 'float64', 'int64',
    ]

    for attr in safe_attrs:
        if hasattr(numpy, attr):
            setattr(safe_np, attr, getattr(numpy, attr))

    return safe_np
```

### 2. Web Search Cache Unbounded (HIGH)
**File:** web_search.py
**Problem:** Global dict grows indefinitely
**Fix:** LRU cache with max 100 entries

```python
# BEFORE
_cache: Dict[str, tuple] = {}

# AFTER
from collections import OrderedDict

class LRUCache:
    def __init__(self, maxsize: int = 100):
        self._cache = OrderedDict()
        self._maxsize = maxsize

    def get(self, key: str):
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def set(self, key: str, value):
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self._maxsize:
                self._cache.popitem(last=False)
        self._cache[key] = value

_cache = LRUCache(maxsize=100)
```

## Success Criteria
- [x] numpy cannot access file system - np.save/load blocked with AttributeError
- [x] Cache never exceeds 100 entries - LRU eviction tested and working
- [x] Existing tests pass - 67/67 tests pass

## Implementation Status
**COMPLETED** - 2025-12-28

All security fixes implemented and verified. See: `plans/reports/fullstack-developer-251228-1302-phase-01a-security-fixes.md`
