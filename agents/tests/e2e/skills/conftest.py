# agents/tests/e2e/skills/conftest.py
"""Skill test fixtures using dynamic discovery.

Replaces hardcoded skill lists with SkillRegistry integration.
"""
import os
import pytest
from typing import Dict, List, Optional

from .skill_loader import (
    get_testable_skills,
    get_skill_names,
    get_skill_names_by_marker,
    get_skill_summary,
    is_local_skill,
    is_slow_skill,
    get_skill_timeout,
)
from .assertions import SkillAssertionChecker
from .test_data_loader import TestDataLoader


# === Session-Scoped Fixtures ===

@pytest.fixture(scope="session")
def all_skill_summaries():
    """All discovered skills from registry."""
    return get_testable_skills()


@pytest.fixture(scope="session")
def remote_skill_names():
    """Names of remote skills."""
    return get_skill_names(deployment="remote")


@pytest.fixture(scope="session")
def local_skill_names():
    """Names of local skills."""
    return get_skill_names(deployment="local")


@pytest.fixture(scope="session")
def slow_skill_names():
    """Names of slow skills (>30s timeout)."""
    return get_skill_names_by_marker("slow")


@pytest.fixture(scope="session")
def assertion_checker():
    """Shared assertion checker for skill response validation.

    LLM-as-Judge is controlled by E2E_USE_LLM_ASSERTIONS env var.
    """
    use_llm = os.environ.get("E2E_USE_LLM_ASSERTIONS", "false").lower() == "true"
    return SkillAssertionChecker(use_llm=use_llm)


@pytest.fixture(scope="session")
def test_data_loader():
    """Shared test data loader for YAML-based test configs."""
    return TestDataLoader()


# === Function-Scoped Fixtures ===

@pytest.fixture
def skill_summary(request):
    """Get skill summary for current parametrized test.

    Usage:
        @pytest.mark.parametrize("skill_name", get_skill_names())
        def test_skill(skill_name, skill_summary):
            assert skill_summary.name == skill_name
    """
    skill_name = getattr(request, 'param', None)
    if not skill_name:
        # Try to get from test function params
        if hasattr(request, 'node') and hasattr(request.node, 'callspec'):
            skill_name = request.node.callspec.params.get('skill_name')
    return get_skill_summary(skill_name) if skill_name else None


@pytest.fixture
def skill_timeout(request) -> int:
    """Get timeout for current parametrized skill test.

    Returns 90s for slow skills, 45s otherwise.
    """
    skill_name = None
    if hasattr(request, 'node') and hasattr(request.node, 'callspec'):
        skill_name = request.node.callspec.params.get('skill_name')

    if skill_name:
        return get_skill_timeout(skill_name)
    return 45


# === Backward Compatibility ===
# These lists are deprecated but kept for gradual migration

REMOTE_SKILLS = get_skill_names("remote")
LOCAL_SKILLS = get_skill_names("local")
SLOW_SKILLS = get_skill_names_by_marker("slow")


@pytest.fixture(params=get_skill_names("remote")[:10])  # Limit for smoke tests
def remote_skill(request):
    """Parametrize over remote skills (smoke test subset)."""
    return request.param


@pytest.fixture(params=get_skill_names("local"))
def local_skill(request):
    """Parametrize over local skills."""
    return request.param


@pytest.fixture(params=get_skill_names_by_marker("slow"))
def slow_skill(request):
    """Parametrize over slow skills."""
    return request.param


# === Skill Test Helpers ===

def get_skill_test_markers(skill_name: str) -> List[str]:
    """Get pytest markers for a skill.

    Returns:
        List of marker names (e.g., ['e2e', 'slow', 'requires_claude'])
    """
    markers = ['e2e']

    if is_slow_skill(skill_name):
        markers.append('slow')

    if is_local_skill(skill_name):
        markers.append('local')
    else:
        markers.append('requires_claude')

    return markers


def should_skip_skill(skill_name: str) -> Optional[str]:
    """Check if skill should be skipped.

    Returns:
        Skip reason string, or None if should run
    """
    summary = get_skill_summary(skill_name)
    if not summary:
        return f"Skill '{skill_name}' not found in registry"

    # Check if local-executor environment
    if summary.deployment == "local":
        if not os.environ.get("LOCAL_EXECUTOR_AVAILABLE"):
            return f"Skill '{skill_name}' requires local-executor"

    return None
