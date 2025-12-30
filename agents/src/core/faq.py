"""Smart FAQ system with hybrid keyword+semantic matching.

Handles common questions (identity, capabilities, commands) without LLM calls.
Flow: Keyword check (~5ms) → Semantic search (~50ms) → LLM fallback
"""

import re
import time
from typing import Dict, Optional

from src.utils.logging import get_logger

logger = get_logger()


class FAQMatcher:
    """Hybrid FAQ matcher: keyword first, semantic fallback."""

    CACHE_TTL = 300  # 5 minutes

    def __init__(self):
        self._cache: Dict[str, 'FAQEntry'] = {}
        self._cache_expiry: float = 0
        self._keyword_index: Dict[str, str] = {}  # normalized pattern -> faq_id

    def _normalize(self, text: str) -> str:
        """Normalize text for matching: lowercase, strip punctuation, collapse whitespace."""
        normalized = re.sub(r'[^\w\s]', '', text.lower())
        return ' '.join(normalized.split())

    async def match(self, message: str) -> Optional[str]:
        """Hybrid match: keyword first, then semantic fallback."""
        start = time.time()

        # Fast path: keyword match
        answer = await self.match_keyword(message)
        if answer:
            duration_ms = int((time.time() - start) * 1000)
            logger.info("faq_hit", match_type="keyword", duration_ms=duration_ms)
            return answer

        # Slow path: semantic match
        answer = await self.match_semantic(message)
        if answer:
            duration_ms = int((time.time() - start) * 1000)
            logger.info("faq_hit", match_type="semantic", duration_ms=duration_ms)
            return answer

        return None

    async def match_keyword(self, message: str) -> Optional[str]:
        """Fast O(1) keyword lookup, returns answer or None."""
        await self._ensure_cache()

        normalized = self._normalize(message)
        faq_id = self._keyword_index.get(normalized)

        if faq_id and faq_id in self._cache:
            entry = self._cache[faq_id]
            if entry.enabled:
                logger.debug("faq_keyword_match", faq_id=faq_id)
                return entry.answer

        return None

    async def match_semantic(self, message: str, threshold: float = 0.9) -> Optional[str]:
        """Semantic search via Qdrant. Returns answer if similarity > threshold."""
        try:
            from src.services.qdrant import search_faq_embedding, get_text_embedding

            # Generate embedding for query (use query task type)
            embedding = await get_text_embedding(message, for_query=True)
            if not embedding:
                return None

            # Search Qdrant
            result = await search_faq_embedding(embedding, threshold)
            if result:
                logger.debug("faq_semantic_match", faq_id=result.get("faq_id"))
                return result.get("answer")

            return None

        except Exception as e:
            logger.error("faq_semantic_error", error=str(e)[:100])
            return None

    async def _ensure_cache(self):
        """Refresh cache if expired."""
        if time.time() > self._cache_expiry:
            await self._refresh_cache()

    async def _refresh_cache(self):
        """Load FAQ entries from Firebase."""
        from src.services.firebase import get_faq_entries

        try:
            entries = await get_faq_entries()
            self._cache = {e.id: e for e in entries}
            self._keyword_index = {}

            for e in entries:
                for pattern in e.patterns:
                    self._keyword_index[self._normalize(pattern)] = e.id

            self._cache_expiry = time.time() + self.CACHE_TTL
            logger.info("faq_cache_refreshed", count=len(entries))

        except Exception as e:
            logger.error("faq_cache_refresh_error", error=str(e)[:100])
            # Keep old cache on error
            self._cache_expiry = time.time() + 60  # Retry in 1 min

    def invalidate_cache(self):
        """Force cache refresh on next access."""
        self._cache_expiry = 0


# Singleton instance
_matcher: Optional[FAQMatcher] = None


def get_faq_matcher() -> FAQMatcher:
    """Get or create FAQ matcher singleton."""
    global _matcher
    if _matcher is None:
        _matcher = FAQMatcher()
    return _matcher
