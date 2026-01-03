# agents/tests/e2e/skills/test_data_loader.py
"""YAML-based test data loader for skill tests.

Supports inheritance from defaults and category defaults.
Replaces hardcoded SKILL_PROMPTS/SKILL_ASSERTIONS dicts.
"""
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from functools import lru_cache


@dataclass
class SkillTestData:
    """Test configuration for a skill."""
    skill_name: str
    prompt: str
    timeout: int
    markers: List[str]
    assertions: Dict[str, Any]
    is_local: bool = False
    category: Optional[str] = None

    @property
    def has_patterns(self) -> bool:
        return bool(self.assertions.get("patterns"))


class SkillTestDataLoader:
    """Load and merge test data from YAML files."""

    def __init__(self, data_dir: Path = None):
        """Initialize loader with optional data directory.

        Args:
            data_dir: Path to test data directory (defaults to tests/e2e/data)
        """
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "data"
        self.data_dir = data_dir
        self._cache: Dict[str, SkillTestData] = {}
        self._defaults: Dict[str, Any] = {}
        self._category_defaults: Dict[str, Dict[str, Any]] = {}
        self._loaded = False

    def _load(self) -> None:
        """Load test data from YAML files."""
        if self._loaded:
            return

        main_file = self.data_dir / "skill-tests.yaml"
        if not main_file.exists():
            self._loaded = True
            return

        with open(main_file) as f:
            data = yaml.safe_load(f) or {}

        # Store defaults
        self._defaults = data.get("defaults", {})
        self._category_defaults = data.get("category_defaults", {})

        # Build skill test data
        for skill_name, config in data.get("skills", {}).items():
            self._cache[skill_name] = self._build_test_data(skill_name, config)

        self._loaded = True

    def _build_test_data(self, name: str, config: Dict[str, Any]) -> SkillTestData:
        """Build test data with inheritance from defaults."""
        # Start with global defaults
        merged = self._deep_merge({}, self._defaults)

        # Apply category defaults if specified
        category = config.get("category")
        if category and category in self._category_defaults:
            merged = self._deep_merge(merged, self._category_defaults[category])

        # Apply skill-specific config (highest priority)
        merged = self._deep_merge(merged, config)

        return SkillTestData(
            skill_name=name,
            prompt=merged.get("prompt", "Hello"),
            timeout=merged.get("timeout", 45),
            markers=merged.get("markers", ["e2e"]),
            assertions=merged.get("assertions", {}),
            is_local=merged.get("is_local", False),
            category=category,
        )

    def _deep_merge(self, base: Dict, overlay: Dict) -> Dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        for key, value in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def get(self, skill_name: str, category: str = None) -> Optional[SkillTestData]:
        """Get test data for a skill.

        Args:
            skill_name: Name of the skill
            category: Optional category to use for defaults

        Returns:
            SkillTestData or None if not found
        """
        self._load()

        if skill_name in self._cache:
            return self._cache[skill_name]

        # Generate default for unknown skills
        return self._build_test_data(skill_name, {"category": category})

    def get_all(self) -> Dict[str, SkillTestData]:
        """Get all loaded test data."""
        self._load()
        return self._cache.copy()

    def get_by_category(self, category: str) -> List[SkillTestData]:
        """Get all test data for a category."""
        self._load()
        return [
            data for data in self._cache.values()
            if data.category == category
        ]

    def get_local_skills(self) -> List[str]:
        """Get names of local skills."""
        self._load()
        return [
            name for name, data in self._cache.items()
            if data.is_local
        ]

    def get_slow_skills(self) -> List[str]:
        """Get names of slow skills (timeout > 60)."""
        self._load()
        return [
            name for name, data in self._cache.items()
            if data.timeout > 60 or "slow" in data.markers
        ]


# Singleton instance for convenience
@lru_cache(maxsize=1)
def get_test_data_loader() -> SkillTestDataLoader:
    """Get singleton SkillTestDataLoader instance."""
    return SkillTestDataLoader()


def get_skill_test_data(skill_name: str) -> Optional[SkillTestData]:
    """Convenience function to get test data for a skill."""
    return get_test_data_loader().get(skill_name)


# Alias for backward compatibility
TestDataLoader = SkillTestDataLoader
