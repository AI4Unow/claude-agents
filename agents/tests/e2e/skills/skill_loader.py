# agents/tests/e2e/skills/skill_loader.py
"""Dynamic skill discovery for E2E tests.

Integrates with SkillRegistry for test parametrization.
Replaces hardcoded SKILL_PROMPTS/LOCAL_SKILLS/SLOW_SKILLS.
"""
import sys
from pathlib import Path
from functools import lru_cache
from typing import List, Optional, Set

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.skills.registry import SkillSummary, SkillRegistry


# Skills path: use local agents/skills for tests
SKILLS_PATH = PROJECT_ROOT / "skills"


@lru_cache(maxsize=1)
def get_registry() -> SkillRegistry:
    """Get SkillRegistry instance for testing."""
    return SkillRegistry(SKILLS_PATH)


@lru_cache(maxsize=1)
def get_testable_skills() -> List[SkillSummary]:
    """Load all skills from registry for test parametrization.

    Returns:
        List of SkillSummary objects (cached per session)
    """
    registry = get_registry()
    summaries = registry.discover(force_refresh=True)
    return summaries


def get_skill_names(deployment: Optional[str] = None) -> List[str]:
    """Get skill names for pytest.mark.parametrize.

    Args:
        deployment: Filter by deployment type (local/remote/both)

    Returns:
        List of skill names matching filter
    """
    summaries = get_testable_skills()

    if deployment:
        # Filter by deployment type
        # "both" skills match both local and remote filters
        if deployment == "local":
            summaries = [s for s in summaries if s.deployment in ("local", "both")]
        elif deployment == "remote":
            summaries = [s for s in summaries if s.deployment in ("remote", "both")]
        else:
            summaries = [s for s in summaries if s.deployment == deployment]

    return [s.name for s in summaries]


def get_skill_names_by_marker(marker: str) -> List[str]:
    """Get skill names by test marker (slow, local, etc).

    Args:
        marker: Marker name to filter by

    Returns:
        List of skill names with that marker
    """
    summaries = get_testable_skills()

    if marker == "slow":
        # Use YAML timeout as source of truth for slow skills
        from .test_data_loader import get_test_data_loader
        loader = get_test_data_loader()
        slow_skills = []
        for s in summaries:
            test_data = loader.get(s.name)
            # Mark as slow if timeout > 60 or has 'slow' marker in YAML
            if test_data:
                if test_data.timeout > 60 or "slow" in test_data.markers:
                    slow_skills.append(s.name)
            else:
                # Fallback: certain categories are slow
                if s.category in {"research", "content", "design"}:
                    slow_skills.append(s.name)
        return slow_skills

    if marker == "local":
        return [
            s.name for s in summaries
            if s.deployment in ("local", "both")
        ]

    if marker == "remote":
        return [
            s.name for s in summaries
            if s.deployment in ("remote", "both")
        ]

    return []


def get_skill_summary(name: str) -> Optional[SkillSummary]:
    """Get skill summary by name.

    Args:
        name: Skill name

    Returns:
        SkillSummary or None
    """
    for s in get_testable_skills():
        if s.name == name:
            return s
    return None


def is_local_skill(name: str) -> bool:
    """Check if skill is local (queued to Firebase)."""
    summary = get_skill_summary(name)
    return summary is not None and summary.deployment in ("local", "both")


def is_slow_skill(name: str) -> bool:
    """Check if skill requires extended timeout."""
    return name in get_skill_names_by_marker("slow")


def get_skill_timeout(name: str, default: int = 45) -> int:
    """Get recommended timeout for skill.

    Args:
        name: Skill name
        default: Default timeout in seconds

    Returns:
        Timeout in seconds (90 for slow skills, default otherwise)
    """
    if is_slow_skill(name):
        return 90
    return default


# Pre-compute skill sets for fast lookup
@lru_cache(maxsize=1)
def get_local_skill_set() -> Set[str]:
    """Get set of local skill names for O(1) lookup."""
    return set(get_skill_names("local"))


@lru_cache(maxsize=1)
def get_slow_skill_set() -> Set[str]:
    """Get set of slow skill names for O(1) lookup."""
    return set(get_skill_names_by_marker("slow"))
