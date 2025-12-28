# Phase 03: Registry Deployment Filtering

## Objective

Update SkillRegistry to filter skills by deployment target.

## Changes

### 1. Update discover() Method

**File**: `src/skills/registry.py`

```python
def discover(
    self,
    force_refresh: bool = False,
    deployment: Optional[str] = None  # NEW: filter by deployment
) -> List[SkillSummary]:
    """Discover skills, optionally filtered by deployment target.

    Args:
        force_refresh: Force re-read from disk
        deployment: Filter by deployment type ("modal", "local", or None for all)

    Returns:
        List of SkillSummary objects
    """
    if self._summaries_cache and not force_refresh:
        summaries = list(self._summaries_cache.values())
    else:
        # ... existing discovery logic ...
        summaries = list(self._summaries_cache.values())

    # Apply deployment filter
    if deployment:
        summaries = [s for s in summaries if s.deployment == deployment]

    return summaries
```

### 2. Add Deployment Filter to API

**File**: `main.py`

Update `/api/skills` endpoint:

```python
@web_app.get("/api/skills")
async def list_skills(deployment: Optional[str] = None):
    """List available skills, optionally filtered by deployment target."""
    from src.skills.registry import get_registry

    registry = get_registry()
    summaries = registry.discover(deployment=deployment)

    return {
        "ok": True,
        "skills": [
            {
                "name": s.name,
                "description": s.description,
                "deployment": s.deployment,
                "requires": s.requires
            }
            for s in summaries
        ],
        "count": len(summaries)
    }
```

### 3. Filter Modal Skills for Telegram Bot

Update `build_skills_keyboard()` to only show modal-compatible skills:

```python
def build_skills_keyboard(category: str = None) -> list:
    from src.skills.registry import get_registry

    registry = get_registry()
    # Only show modal-compatible skills in Telegram
    summaries = registry.discover(deployment="modal")
    # ... rest of function ...
```

### 4. Add Helper Methods

```python
def get_modal_skills(self) -> List[str]:
    """Get names of all modal-compatible skills."""
    return [s.name for s in self.discover(deployment="modal")]

def get_local_skills(self) -> List[str]:
    """Get names of all local-only skills."""
    return [s.name for s in self.discover(deployment="local")]

def can_run_on_modal(self, skill_name: str) -> bool:
    """Check if skill can run on Modal.com."""
    if skill_name not in self._summaries_cache:
        self.discover()
    summary = self._summaries_cache.get(skill_name)
    return summary.deployment == "modal" if summary else False
```

## Validation

- [ ] `discover(deployment="modal")` returns only modal skills
- [ ] `discover(deployment="local")` returns only local skills
- [ ] `discover()` returns all skills (backward compatible)
- [ ] Telegram bot only shows modal skills
- [ ] `/api/skills?deployment=modal` works correctly

## Effort

1.5 hours
