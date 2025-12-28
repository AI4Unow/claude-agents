# Phase 04: Cache Warming on Startup

## Objective

Preload hot data into L1 cache when Modal container starts to reduce cold-start latency.

## Current State

- SkillRegistry cache empty on container start
- First request pays full Firebase latency
- No @enter hook for pre-warming

## Target State

- Container @enter hook warms skill cache
- First request hits L1 cache immediately
- Optional: preload active user sessions

## Changes to `src/core/state.py`

Add warming methods:

```python
async def warm_skills(self):
    """Preload skill summaries into L1 cache."""
    from src.skills.registry import get_registry

    registry = get_registry()
    summaries = registry.discover()

    self.logger.info("cache_warming_skills", count=len(summaries))

    # Cache skill metadata from Firebase
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

        # Get recent sessions ordered by updated_at
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
```

## Changes to `main.py`

Add container lifecycle hook:

```python
# Define a class with @enter hook for cache warming
@app.cls(
    image=image,
    secrets=secrets,
    volumes={"/skills": skills_volume},
    min_containers=1,
    timeout=60,
)
@modal.concurrent(max_inputs=100)
class TelegramChatAgentCls:
    """Telegram Chat Agent with cache warming."""

    @modal.enter()
    async def warm_caches(self):
        """Warm caches when container starts."""
        import structlog
        logger = structlog.get_logger()

        try:
            from src.core.state import get_state_manager
            state = get_state_manager()
            await state.warm()
            logger.info("cache_warming_done")
        except Exception as e:
            logger.warning("cache_warming_failed", error=str(e))

    @modal.asgi_app()
    def app(self):
        return create_web_app()


# Keep the function version for backwards compatibility during transition
@app.function(
    image=image,
    secrets=secrets,
    volumes={"/skills": skills_volume},
    min_containers=1,
    timeout=60,
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def telegram_chat_agent():
    """Telegram Chat Agent - Primary interface (legacy)."""
    return create_web_app()
```

**Note**: Modal @enter hooks require `@app.cls` decorator. Alternative approach using function:

```python
# Alternative: Warm in first request (lazy warm)
_warmed = False

async def ensure_warm():
    global _warmed
    if not _warmed:
        from src.core.state import get_state_manager
        state = get_state_manager()
        await state.warm()
        _warmed = True

# In create_web_app(), add middleware or call in health check
@web_app.on_event("startup")
async def startup_event():
    await ensure_warm()
```

## Changes to `src/skills/registry.py`

Integrate with StateManager for skill stats:

```python
# In SkillRegistry.__init__(), add:
self._state = None

@property
def state(self):
    if self._state is None:
        from src.core.state import get_state_manager
        self._state = get_state_manager()
    return self._state

# In get_full(), after loading skill, fetch stats:
async def get_full_with_stats(self, name: str, use_cache: bool = True) -> Optional[Skill]:
    """Load full skill with Firebase stats."""
    skill = self.get_full(name, use_cache)
    if not skill:
        return None

    # Try to get stats from StateManager cache
    stats_data = await self.state.get("skills", name, ttl_seconds=300)
    if stats_data and "stats" in stats_data:
        skill.stats = SkillStats(
            run_count=stats_data["stats"].get("runCount", 0),
            success_rate=stats_data["stats"].get("successRate", 0.0),
            avg_duration_ms=stats_data["stats"].get("avgDurationMs", 0.0)
        )

    return skill
```

## Verification

```bash
# Deploy
modal deploy main.py

# Check logs for warming
modal app logs claude-agents | grep "cache_warming"

# Expected:
# cache_warming_skills count=15
# sessions_warmed count=10
# cache_warming_done

# Verify first request is fast
time curl -X GET https://...modal.run/health
```

## Acceptance Criteria

- [ ] Cache warms on container start (or first request)
- [ ] Skills loaded into L1 cache
- [ ] Recent sessions preloaded
- [ ] First real request hits warm cache
- [ ] Warming failures don't crash container
