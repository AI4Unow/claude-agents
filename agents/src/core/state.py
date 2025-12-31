"""Unified state management with L1 cache + L2 Firebase persistence.

TTL Defaults:
- Sessions: 1 hour
- Conversations: 24 hours
- User Tiers: 1 hour
- Generic cache: 5 minutes

Thread Safety:
- Singleton protected by _singleton_lock
- L1 cache protected by _cache_lock
"""
import asyncio
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from src.utils.logging import get_logger

logger = get_logger()

# Module-level locks for thread safety
_singleton_lock = threading.Lock()
_cache_lock = threading.Lock()
_rate_limit_lock = threading.Lock()

# Cache size limit
MAX_CACHE_SIZE = 1000


@dataclass
class CacheEntry:
    """Cache entry with expiration."""
    value: Any
    expires_at: datetime

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at


class StateManager:
    """Unified state manager with L1 cache + L2 Firebase.

    Usage:
        state = get_state_manager()
        await state.set("collection", "doc_id", value, ttl_seconds=300)
        value = await state.get("collection", "doc_id")
    """

    # TTL defaults (seconds)
    TTL_SESSION = 3600        # 1 hour
    TTL_CONVERSATION = 86400  # 24 hours
    TTL_CACHE = 300           # 5 minutes
    TTL_USER_TIER = 3600      # 1 hour

    # Collection names
    COLLECTION_SESSIONS = "telegram_sessions"
    COLLECTION_CONVERSATIONS = "conversations"
    MAX_CONVERSATION_MESSAGES = 20

    def __init__(self):
        self._l1_cache: Dict[str, CacheEntry] = {}
        self._db = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._rate_counters: Dict[int, List[float]] = defaultdict(list)  # user_id -> timestamps
        self.logger = logger.bind(component="StateManager")

    def _get_db(self):
        """Get Firestore client (lazy init)."""
        if self._db is None:
            from src.services.firebase import get_db
            self._db = get_db()
        return self._db

    # ==================== Async Firebase Wrappers ====================

    async def _firebase_get(self, collection: str, doc_id: str) -> Optional[Dict]:
        """Async wrapper for Firebase get."""
        try:
            db = self._get_db()
            doc = await asyncio.to_thread(
                lambda: db.collection(collection).document(doc_id).get()
            )
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            self.logger.error("firebase_get_failed", collection=collection, doc_id=doc_id, error=str(e))
            return None

    async def _firebase_set(self, collection: str, doc_id: str, data: Dict, merge: bool = True):
        """Async wrapper for Firebase set."""
        try:
            db = self._get_db()
            await asyncio.to_thread(
                lambda: db.collection(collection).document(doc_id).set(data, merge=merge)
            )
        except Exception as e:
            self.logger.error("firebase_set_failed", collection=collection, doc_id=doc_id, error=str(e))

    async def _firebase_update(self, collection: str, doc_id: str, data: Dict):
        """Async wrapper for Firebase update."""
        try:
            db = self._get_db()
            await asyncio.to_thread(
                lambda: db.collection(collection).document(doc_id).update(data)
            )
        except Exception as e:
            self.logger.error("firebase_update_failed", collection=collection, doc_id=doc_id, error=str(e))

    # ==================== Generic Cache ====================

    def _cache_key(self, collection: str, doc_id: str) -> str:
        """Generate cache key."""
        return f"{collection}:{doc_id}"

    def _get_from_l1(self, key: str) -> Optional[Any]:
        """Get from L1 cache if not expired (thread-safe)."""
        with _cache_lock:
            entry = self._l1_cache.get(key)
            if entry and not entry.is_expired:
                return entry.value
            if entry:
                del self._l1_cache[key]  # Cleanup expired
            return None

    def _set_to_l1(self, key: str, value: Any, ttl_seconds: int):
        """Set to L1 cache with TTL and LRU eviction (thread-safe)."""
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

        with _cache_lock:
            # Evict oldest if at capacity
            if len(self._l1_cache) >= MAX_CACHE_SIZE and key not in self._l1_cache:
                # Find oldest entry
                oldest_key = min(
                    self._l1_cache.keys(),
                    key=lambda k: self._l1_cache[k].expires_at
                )
                del self._l1_cache[oldest_key]

            self._l1_cache[key] = CacheEntry(
                value=value,
                expires_at=expires_at
            )

    async def get(self, collection: str, doc_id: str, ttl_seconds: int = TTL_CACHE) -> Optional[Dict]:
        """Get from L1 cache, fallback to L2 Firebase.

        Args:
            collection: Firestore collection name
            doc_id: Document ID
            ttl_seconds: TTL for L1 cache on miss

        Returns:
            Document dict or None
        """
        key = self._cache_key(collection, doc_id)

        # L1 hit
        cached = self._get_from_l1(key)
        if cached is not None:
            self.logger.debug("l1_hit", key=key)
            return cached

        # L2 fallback
        data = await self._firebase_get(collection, doc_id)
        if data:
            self._set_to_l1(key, data, ttl_seconds)
            self.logger.debug("l2_hit", key=key)

        return data

    async def set(
        self,
        collection: str,
        doc_id: str,
        data: Dict,
        ttl_seconds: int = TTL_CACHE,
        persist: bool = True
    ):
        """Set to L1 cache and optionally L2 Firebase.

        Args:
            collection: Firestore collection name
            doc_id: Document ID
            data: Data to store
            ttl_seconds: TTL for L1 cache
            persist: Whether to write to Firebase
        """
        key = self._cache_key(collection, doc_id)
        self._set_to_l1(key, data, ttl_seconds)

        if persist:
            await self._firebase_set(collection, doc_id, data)
            self.logger.debug("persisted", key=key)

    async def invalidate(self, collection: str, doc_id: str):
        """Remove from L1 cache (thread-safe)."""
        key = self._cache_key(collection, doc_id)
        with _cache_lock:
            self._l1_cache.pop(key, None)

    def cleanup_expired(self) -> int:
        """Remove all expired L1 entries (thread-safe). Returns count removed."""
        now = datetime.now(timezone.utc)
        with _cache_lock:
            expired = [k for k, v in self._l1_cache.items() if v.expires_at < now]
            for k in expired:
                del self._l1_cache[k]
        return len(expired)

    # ==================== Session Methods ====================

    async def get_session(self, user_id: int) -> Optional[Dict]:
        """Get Telegram session with caching."""
        if not user_id:
            return None
        return await self.get(
            self.COLLECTION_SESSIONS,
            str(user_id),
            ttl_seconds=self.TTL_SESSION
        )

    async def set_session(self, user_id: int, data: Dict):
        """Update Telegram session atomically (Firebase merge + write-through cache).

        Uses Firebase merge=True for atomic update without race conditions.
        Updates cache atomically after Firebase write to prevent stale window.
        """
        if not user_id:
            return

        # Prepare update with timestamp (outside lock)
        update_data = {**data, "updated_at": datetime.now(timezone.utc).isoformat()}

        # Write to Firebase first
        await self._firebase_set(
            self.COLLECTION_SESSIONS,
            str(user_id),
            update_data,
            merge=True
        )

        # Update L1 cache with merged data (write-through, not invalidate)
        key = self._cache_key(self.COLLECTION_SESSIONS, str(user_id))
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.TTL_SESSION)

        with _cache_lock:
            existing = self._l1_cache.get(key)
            if existing and not existing.is_expired:
                # Merge with existing cached data
                merged = {**existing.value, **update_data}
                self._l1_cache[key] = CacheEntry(
                    value=merged,
                    expires_at=expires_at
                )
            else:
                # No existing cache, set directly
                self._l1_cache[key] = CacheEntry(
                    value=update_data,
                    expires_at=expires_at
                )

    async def get_pending_skill(self, user_id: int) -> Optional[str]:
        """Get pending skill from session."""
        session = await self.get_session(user_id)
        return session.get("pending_skill") if session else None

    async def clear_pending_skill(self, user_id: int):
        """Clear pending skill."""
        await self.set_session(user_id, {"pending_skill": None})

    async def get_user_mode(self, user_id: int) -> str:
        """Get user's execution mode."""
        session = await self.get_session(user_id)
        return session.get("mode", "simple") if session else "simple"

    async def set_user_mode(self, user_id: int, mode: str):
        """Set user's execution mode."""
        await self.set_session(user_id, {"mode": mode})

    # ==================== Profile & Context Methods ====================

    TTL_PROFILE = 300   # 5 minutes
    TTL_CONTEXT = 60    # 1 minute

    async def get_user_profile(self, user_id: int) -> Optional[Dict]:
        """Get user profile with caching."""
        if not user_id:
            return None
        return await self.get(
            "user_profiles",
            str(user_id),
            ttl_seconds=self.TTL_PROFILE
        )

    async def set_user_profile(self, user_id: int, data: Dict):
        """Update user profile."""
        if not user_id:
            return
        await self.set(
            "user_profiles",
            str(user_id),
            data,
            ttl_seconds=self.TTL_PROFILE
        )

    async def get_work_context(self, user_id: int) -> Optional[Dict]:
        """Get work context with short TTL caching."""
        if not user_id:
            return None
        return await self.get(
            "user_contexts",
            str(user_id),
            ttl_seconds=self.TTL_CONTEXT
        )

    async def set_work_context(self, user_id: int, data: Dict):
        """Update work context."""
        if not user_id:
            return
        await self.set(
            "user_contexts",
            str(user_id),
            data,
            ttl_seconds=self.TTL_CONTEXT
        )

    # ==================== Conversation Methods ====================

    async def get_conversation(self, user_id: int) -> List[Dict]:
        """Get conversation history."""
        if not user_id:
            return []

        data = await self.get(
            self.COLLECTION_CONVERSATIONS,
            str(user_id),
            ttl_seconds=self.TTL_CONVERSATION
        )

        if not data:
            return []

        return data.get("messages", [])[-self.MAX_CONVERSATION_MESSAGES:]

    async def save_conversation(self, user_id: int, messages: List[Dict]):
        """Save conversation history (last N messages)."""
        if not user_id:
            return

        # Keep only serializable messages
        clean_messages = []
        for msg in messages[-self.MAX_CONVERSATION_MESSAGES:]:
            clean_msg = {"role": msg.get("role", "user")}

            content = msg.get("content")
            if isinstance(content, str):
                clean_msg["content"] = content
            elif isinstance(content, list):
                # Tool results - serialize to string summary
                clean_msg["content"] = "[tool results]"
            else:
                clean_msg["content"] = str(content) if content else ""

            clean_messages.append(clean_msg)

        await self.set(
            self.COLLECTION_CONVERSATIONS,
            str(user_id),
            {"messages": clean_messages, "updated_at": datetime.now(timezone.utc).isoformat()},
            ttl_seconds=self.TTL_CONVERSATION
        )

    async def clear_conversation(self, user_id: int):
        """Clear conversation history."""
        if not user_id:
            return

        await self.invalidate(self.COLLECTION_CONVERSATIONS, str(user_id))
        await self._firebase_set(
            self.COLLECTION_CONVERSATIONS,
            str(user_id),
            {"messages": [], "cleared_at": datetime.now(timezone.utc).isoformat()}
        )

    # ==================== Wizard State Methods ====================

    COLLECTION_WIZARD = "wizard_state"
    TTL_WIZARD = 300  # 5 minutes

    async def get_wizard_state(self, user_id: int) -> Optional[Dict]:
        """Get current wizard state for user."""
        if not user_id:
            return None
        return await self.get(self.COLLECTION_WIZARD, str(user_id), ttl_seconds=self.TTL_WIZARD)

    async def set_wizard_state(self, user_id: int, wizard_type: str, step: str, data: Dict = None):
        """Set wizard state for multi-step flows."""
        if not user_id:
            return
        await self.set(
            self.COLLECTION_WIZARD,
            str(user_id),
            {
                "wizard": wizard_type,
                "step": step,
                "data": data or {},
                "updated_at": time.time()
            },
            ttl_seconds=self.TTL_WIZARD
        )

    async def clear_wizard_state(self, user_id: int):
        """Clear wizard state."""
        if not user_id:
            return
        await self.invalidate(self.COLLECTION_WIZARD, str(user_id))

    # ==================== User Tier Methods ====================

    async def get_user_tier_cached(self, user_id: int) -> str:
        """Get user tier with L1 cache.

        Checks ADMIN_TELEGRAM_ID env var first for admin auto-assignment.
        """
        import os

        if not user_id:
            return "guest"

        # Check admin env var first
        admin_id = os.environ.get("ADMIN_TELEGRAM_ID")
        if str(user_id) == str(admin_id):
            return "admin"

        key = self._cache_key("user_tiers", str(user_id))

        # L1 hit
        cached = self._get_from_l1(key)
        if cached is not None:
            return cached.get("tier", "guest")

        # L2 fallback
        from src.services.firebase import get_user_tier
        tier = await get_user_tier(user_id)

        # Cache the result
        self._set_to_l1(key, {"tier": tier}, self.TTL_USER_TIER)
        return tier

    def check_rate_limit(self, user_id: int, tier: str) -> tuple:
        """Check if user is within rate limit.

        Thread Safety:
            Protected by _rate_limit_lock to prevent race conditions

        Returns:
            (is_allowed: bool, seconds_until_reset: int)
        """
        from src.services.firebase import get_rate_limit

        limit = get_rate_limit(tier)
        now = time.time()
        window_start = now - 60  # 1 minute window

        with _rate_limit_lock:
            # Clean old entries
            self._rate_counters[user_id] = [
                ts for ts in self._rate_counters[user_id]
                if ts > window_start
            ]

            current_count = len(self._rate_counters[user_id])

            if current_count >= limit:
                oldest = min(self._rate_counters[user_id]) if self._rate_counters[user_id] else now
                reset_in = int(oldest + 60 - now)
                return False, max(1, reset_in)

            # Record this request
            self._rate_counters[user_id].append(now)
            return True, 0

    async def invalidate_user_tier(self, user_id: int):
        """Invalidate cached tier after grant/revoke."""
        key = self._cache_key("user_tiers", str(user_id))
        with _cache_lock:
            if key in self._l1_cache:
                del self._l1_cache[key]

    # ==================== Cache Warming ====================

    async def _periodic_cleanup(self):
        """Background task to cleanup expired L1 cache entries."""
        while True:
            await asyncio.sleep(300)  # 5 minutes
            try:
                count = self.cleanup_expired()
                if count > 0:
                    self.logger.info("cache_cleanup", expired_count=count)
            except Exception as e:
                self.logger.error("cleanup_failed", error=str(e))

    async def warm_skills(self):
        """Preload skill summaries into L1 cache."""
        from src.skills.registry import get_registry

        registry = get_registry()
        summaries = registry.discover()

        self.logger.info("cache_warming_skills", count=len(summaries))

        for summary in summaries:
            try:
                skill_data = await self._firebase_get("skills", summary.name)
                if skill_data:
                    self._set_to_l1(
                        self._cache_key("skills", summary.name),
                        skill_data,
                        ttl_seconds=self.TTL_CACHE
                    )
            except Exception as e:
                self.logger.warning("skill_warm_failed", skill=summary.name, error=str(e))

        self.logger.info("cache_warming_complete", cached=len(summaries))

    async def warm_recent_sessions(self, limit: int = 50):
        """Preload recently active user sessions."""
        try:
            db = self._get_db()

            docs = await asyncio.to_thread(
                lambda: db.collection(self.COLLECTION_SESSIONS)
                    .order_by("updated_at", direction="DESCENDING")
                    .limit(limit)
                    .get()
            )

            for doc in docs:
                data = doc.to_dict()
                self._set_to_l1(
                    self._cache_key(self.COLLECTION_SESSIONS, doc.id),
                    data,
                    ttl_seconds=self.TTL_SESSION
                )

            self.logger.info("sessions_warmed", count=len(docs))

        except Exception as e:
            self.logger.warning("session_warm_failed", error=str(e))

    async def warm(self):
        """Full cache warming (call from @enter hook)."""
        await self.warm_skills()
        await self.warm_recent_sessions()

        # Start periodic cleanup if not already running
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
            self.logger.info("cleanup_task_started")


# Singleton
_state_manager: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    """Get or create singleton StateManager (thread-safe)."""
    global _state_manager
    if _state_manager is None:
        with _singleton_lock:
            # Double-check locking pattern
            if _state_manager is None:
                _state_manager = StateManager()
    return _state_manager
