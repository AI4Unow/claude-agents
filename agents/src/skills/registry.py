"""Skill Registry with Progressive Disclosure.

II Framework SkillRegistry:
- Lazy loading: Only name/description loaded initially
- Full content loaded on activation (get_full)
- Firebase sync for stats and memory backup
- Qdrant integration for semantic routing
"""
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import re

import yaml

from src.utils.logging import get_logger

logger = get_logger()


@dataclass
class SkillSummary:
    """Minimal skill info for progressive disclosure (Layer 1)."""
    name: str
    description: str
    category: Optional[str] = None
    deployment: str = "remote"  # "local" | "remote" | "both"
    path: Optional[Path] = None


@dataclass
class SkillStats:
    """Skill execution statistics."""
    run_count: int = 0
    success_rate: float = 0.0
    last_run: Optional[datetime] = None
    avg_duration_ms: float = 0.0


@dataclass
class Skill:
    """Full skill content (loaded on activation)."""
    name: str
    description: str
    body: str
    frontmatter: Dict[str, Any]
    memory: str = ""
    error_history: str = ""
    stats: SkillStats = field(default_factory=SkillStats)
    path: Optional[Path] = None

    def get_system_prompt(self) -> str:
        """Get full system prompt for LLM."""
        return f"""{self.body}

## Memory

{self.memory}

## Error History

{self.error_history}
""".strip()


class SkillRegistry:
    """Registry for skill discovery and loading with progressive disclosure.

    Progressive Disclosure Pattern:
    1. discover() - Returns only name/description for all skills (fast)
    2. get_full() - Loads complete skill on activation (lazy)

    Memory Hierarchy:
    - info.md (Modal Volume) - Primary, fast local read
    - Firebase (Cloud) - Backup, cross-session persistence
    """

    def __init__(self, skills_path: Path = Path("/skills")):
        """Initialize registry.

        Args:
            skills_path: Path to skills directory (Modal Volume mount)
        """
        self.skills_path = skills_path
        self.logger = logger.bind(component="SkillRegistry")
        self._summaries_cache: Dict[str, SkillSummary] = {}
        self._full_cache: Dict[str, Skill] = {}

    def discover(self, force_refresh: bool = False) -> List[SkillSummary]:
        """Discover all skills, returning only summaries (progressive disclosure).

        This is the first layer of progressive disclosure:
        - Only reads frontmatter (name, description)
        - Fast for large skill collections
        - Cached for subsequent calls

        Returns:
            List of SkillSummary objects
        """
        if self._summaries_cache and not force_refresh:
            return list(self._summaries_cache.values())

        self._summaries_cache.clear()
        summaries = []

        if not self.skills_path.exists():
            self.logger.warning("skills_path_not_found", path=str(self.skills_path))
            return summaries

        for skill_dir in sorted(self.skills_path.iterdir()):
            if not skill_dir.is_dir():
                continue
            if skill_dir.name.startswith('.'):
                continue

            summary = self._extract_summary(skill_dir)
            if summary:
                summaries.append(summary)
                self._summaries_cache[summary.name] = summary

        self.logger.info("skills_discovered", count=len(summaries))
        return summaries

    def _extract_summary(self, skill_dir: Path) -> Optional[SkillSummary]:
        """Extract summary from skill's info.md frontmatter."""
        info_file = skill_dir / "info.md"
        if not info_file.exists():
            return None

        content = info_file.read_text()
        frontmatter = self._parse_frontmatter(content)

        if not frontmatter:
            # Fallback: use directory name
            return SkillSummary(
                name=skill_dir.name,
                description="",
                path=skill_dir
            )

        return SkillSummary(
            name=frontmatter.get('name', skill_dir.name),
            description=frontmatter.get('description', ''),
            category=frontmatter.get('category'),
            deployment=frontmatter.get('deployment', 'remote'),
            path=skill_dir
        )

    def _parse_frontmatter(self, content: str) -> Dict[str, Any]:
        """Parse YAML frontmatter from markdown."""
        if not content.startswith('---'):
            return {}

        end_match = re.search(r'\n---\n', content[3:])
        if not end_match:
            return {}

        frontmatter_str = content[3:end_match.start() + 3]

        try:
            return yaml.safe_load(frontmatter_str) or {}
        except yaml.YAMLError:
            return {}

    def get_full(self, name: str, use_cache: bool = True) -> Optional[Skill]:
        """Load full skill content (Layer 2 - on activation).

        This is the second layer of progressive disclosure:
        - Loads complete body, memory, error history
        - Called when skill is actually needed
        - Cached for active session

        Args:
            name: Skill name
            use_cache: Whether to use cached version if available

        Returns:
            Full Skill object or None if not found
        """
        if use_cache and name in self._full_cache:
            return self._full_cache[name]

        # Find skill path
        skill_path = None
        if name in self._summaries_cache:
            skill_path = self._summaries_cache[name].path
        else:
            skill_path = self.skills_path / name

        if not skill_path or not skill_path.exists():
            self.logger.warning("skill_not_found", name=name)
            return None

        skill = self._load_full_skill(skill_path)
        if skill:
            self._full_cache[name] = skill
            self.logger.info("skill_loaded", name=name)

        return skill

    def _load_full_skill(self, skill_path: Path) -> Optional[Skill]:
        """Load complete skill from info.md."""
        info_file = skill_path / "info.md"
        if not info_file.exists():
            return None

        content = info_file.read_text()
        frontmatter = self._parse_frontmatter(content)

        # Extract body (after frontmatter)
        body = content
        if content.startswith('---'):
            end_match = re.search(r'\n---\n', content[3:])
            if end_match:
                body = content[end_match.start() + 7:]  # Skip ---\n---\n

        # Extract memory section
        memory = self._extract_section(body, "Memory")
        error_history = self._extract_section(body, "Error History")

        # Remove memory/error sections from body for clean prompt
        body_clean = self._remove_section(body, "Memory")
        body_clean = self._remove_section(body_clean, "Error History")

        return Skill(
            name=frontmatter.get('name', skill_path.name),
            description=frontmatter.get('description', ''),
            body=body_clean.strip(),
            frontmatter=frontmatter,
            memory=memory,
            error_history=error_history,
            path=skill_path
        )

    def _extract_section(self, content: str, section_name: str) -> str:
        """Extract content of a markdown section."""
        pattern = rf"## {section_name}\n([\s\S]*?)(?=\n## |\Z)"
        match = re.search(pattern, content)
        if match:
            return match.group(1).strip()
        return ""

    def _remove_section(self, content: str, section_name: str) -> str:
        """Remove a markdown section from content."""
        pattern = rf"\n## {section_name}\n[\s\S]*?(?=\n## |\Z)"
        return re.sub(pattern, "", content)

    def update_memory(self, name: str, memory_content: str) -> bool:
        """Update skill's memory section.

        Args:
            name: Skill name
            memory_content: New memory content

        Returns:
            True if update successful
        """
        skill = self.get_full(name, use_cache=False)
        if not skill or not skill.path:
            return False

        info_file = skill.path / "info.md"
        content = info_file.read_text()

        # Replace memory section
        new_memory = f"## Memory\n\n{memory_content}"
        if "## Memory" in content:
            content = re.sub(
                r"## Memory\n[\s\S]*?(?=\n## |\Z)",
                new_memory,
                content
            )
        else:
            content += f"\n\n{new_memory}"

        info_file.write_text(content)

        # Update cache
        if name in self._full_cache:
            self._full_cache[name].memory = memory_content

        self.logger.info("memory_updated", name=name)
        return True

    def add_error(self, name: str, error: str, fix: str) -> bool:
        """Add error entry to skill's error history.

        Args:
            name: Skill name
            error: Error description
            fix: Fix applied

        Returns:
            True if update successful
        """
        skill = self.get_full(name, use_cache=False)
        if not skill or not skill.path:
            return False

        date = datetime.now().strftime('%Y-%m-%d')
        entry = f"- {date}: {error} - {fix}"

        new_history = f"{skill.error_history}\n{entry}".strip()

        info_file = skill.path / "info.md"
        content = info_file.read_text()

        # Replace error history section
        new_section = f"## Error History\n\n{new_history}"
        if "## Error History" in content:
            content = re.sub(
                r"## Error History\n[\s\S]*?(?=\n## |\Z)",
                new_section,
                content
            )
        else:
            content += f"\n\n{new_section}"

        info_file.write_text(content)

        # Update cache
        if name in self._full_cache:
            self._full_cache[name].error_history = new_history

        self.logger.info("error_added", name=name, error=error[:50])
        return True

    def get_names(self) -> List[str]:
        """Get list of all skill names."""
        if not self._summaries_cache:
            self.discover()
        return list(self._summaries_cache.keys())

    def clear_cache(self):
        """Clear all caches."""
        self._summaries_cache.clear()
        self._full_cache.clear()


# Singleton instance
_registry: Optional[SkillRegistry] = None


def get_registry(skills_path: Path = Path("/skills")) -> SkillRegistry:
    """Get or create singleton SkillRegistry instance."""
    global _registry
    if _registry is None:
        _registry = SkillRegistry(skills_path)
    return _registry
