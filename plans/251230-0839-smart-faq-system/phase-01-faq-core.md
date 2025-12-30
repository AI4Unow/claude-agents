# Phase 1: FAQ Core

## Context
- Parent: [plan.md](./plan.md)
- Brainstorm: [brainstorm-251230-0839-smart-faq-system.md](../reports/brainstorm-251230-0839-smart-faq-system.md)

## Overview
- **Date:** 2025-12-30
- **Description:** Create Firebase schema and FAQMatcher class
- **Priority:** P1
- **Implementation Status:** pending
- **Review Status:** pending

## Key Insights
- Keyword matching should be O(1) via dict lookup
- L1 cache prevents Firebase calls on every message
- Normalize input: lowercase, strip punctuation, collapse whitespace

## Requirements
1. Firebase `faq_entries` collection with schema
2. FAQMatcher class with keyword matching
3. L1 cache with 5min TTL

## Architecture

```python
# src/core/faq.py
class FAQMatcher:
    def __init__(self):
        self._cache: Dict[str, FAQEntry] = {}
        self._cache_expiry: float = 0
        self._keyword_index: Dict[str, str] = {}  # pattern -> faq_id

    def match_keyword(self, message: str) -> Optional[str]:
        """Fast O(1) keyword lookup."""
        normalized = self._normalize(message)
        faq_id = self._keyword_index.get(normalized)
        return self._cache[faq_id].answer if faq_id else None

    def _normalize(self, text: str) -> str:
        """Lowercase, strip punctuation, collapse whitespace."""
        return re.sub(r'[^\w\s]', '', text.lower()).strip()

    async def _refresh_cache(self):
        """Load FAQ entries from Firebase."""
        entries = await get_faq_entries()
        self._cache = {e.id: e for e in entries}
        self._keyword_index = {}
        for e in entries:
            for pattern in e.patterns:
                self._keyword_index[self._normalize(pattern)] = e.id
        self._cache_expiry = time.time() + 300  # 5 min
```

## Related Code Files
- `src/services/firebase.py` - Add FAQ CRUD functions
- `src/core/faq.py` - NEW: FAQMatcher class

## Implementation Steps

### 1. Firebase Schema (firebase.py)
```python
# Add to firebase.py

@dataclass
class FAQEntry:
    id: str
    patterns: List[str]
    answer: str
    category: str
    enabled: bool
    embedding: Optional[List[float]] = None
    updated_at: Optional[datetime] = None

async def get_faq_entries(enabled_only: bool = True) -> List[FAQEntry]:
    """Get all FAQ entries from Firestore."""
    ...

async def create_faq_entry(entry: FAQEntry) -> bool:
    """Create new FAQ entry."""
    ...

async def update_faq_entry(faq_id: str, updates: dict) -> bool:
    """Update FAQ entry fields."""
    ...

async def delete_faq_entry(faq_id: str) -> bool:
    """Soft delete (set enabled=False)."""
    ...
```

### 2. FAQMatcher Class (faq.py)
```python
# src/core/faq.py
"""Smart FAQ system with hybrid keyword+semantic matching."""

import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from src.utils.logging import get_logger

logger = get_logger()

class FAQMatcher:
    """Hybrid FAQ matcher: keyword first, semantic fallback."""

    CACHE_TTL = 300  # 5 minutes

    def __init__(self):
        self._cache: Dict[str, 'FAQEntry'] = {}
        self._cache_expiry: float = 0
        self._keyword_index: Dict[str, str] = {}

    def _normalize(self, text: str) -> str:
        """Normalize text for matching."""
        return re.sub(r'[^\w\s]', '', text.lower()).strip()

    async def match_keyword(self, message: str) -> Optional[str]:
        """Fast keyword lookup, returns answer or None."""
        await self._ensure_cache()
        normalized = self._normalize(message)
        faq_id = self._keyword_index.get(normalized)
        if faq_id and faq_id in self._cache:
            entry = self._cache[faq_id]
            if entry.enabled:
                logger.info("faq_keyword_hit", faq_id=faq_id)
                return entry.answer
        return None

    async def match(self, message: str) -> Optional[str]:
        """Hybrid match: keyword first, then semantic."""
        # Keyword match (fast path)
        answer = await self.match_keyword(message)
        if answer:
            return answer
        # Semantic match (Phase 2)
        return await self.match_semantic(message)

    async def match_semantic(self, message: str, threshold: float = 0.9) -> Optional[str]:
        """Semantic search via Qdrant. Implemented in Phase 2."""
        return None  # Placeholder

    async def _ensure_cache(self):
        """Refresh cache if expired."""
        if time.time() > self._cache_expiry:
            await self._refresh_cache()

    async def _refresh_cache(self):
        """Load FAQ entries from Firebase."""
        from src.services.firebase import get_faq_entries
        entries = await get_faq_entries()
        self._cache = {e.id: e for e in entries}
        self._keyword_index = {}
        for e in entries:
            for pattern in e.patterns:
                self._keyword_index[self._normalize(pattern)] = e.id
        self._cache_expiry = time.time() + self.CACHE_TTL
        logger.info("faq_cache_refreshed", count=len(entries))

# Singleton
_matcher: Optional[FAQMatcher] = None

def get_faq_matcher() -> FAQMatcher:
    global _matcher
    if _matcher is None:
        _matcher = FAQMatcher()
    return _matcher
```

## Todo List
- [ ] Add FAQEntry dataclass to firebase.py
- [ ] Add get_faq_entries() function
- [ ] Add create_faq_entry() function
- [ ] Add update_faq_entry() function
- [ ] Add delete_faq_entry() function
- [ ] Create src/core/faq.py with FAQMatcher
- [ ] Test keyword matching locally

## Success Criteria
- FAQMatcher can load entries from Firebase
- Keyword matching returns answer in <5ms
- Cache refreshes every 5 minutes

## Risk Assessment
- **Firebase quota:** Low risk, only fetches on cache miss
- **Empty cache:** Graceful fallback to LLM

## Security Considerations
- FAQ answers are public, no auth needed for read
- Write operations (add/edit/delete) require admin tier

## Next Steps
→ [Phase 2: Qdrant Collection](./phase-02-qdrant-collection.md)
