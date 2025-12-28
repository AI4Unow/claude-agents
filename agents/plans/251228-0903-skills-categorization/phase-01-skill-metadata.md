# Phase 01: Add Skill Metadata Schema

## Objective

Define and document the skill metadata schema with deployment categorization fields.

## Changes

### 1. Update Skill Frontmatter Schema

Add new fields to skill `info.md` frontmatter:

```yaml
---
name: skill-name
description: Brief description
deployment: modal  # NEW: modal | local | both
requires:          # NEW: List of requirements
  - ffmpeg         # CLI tool
  - local-files    # File system access
  - consumer-ip    # Consumer IP for geo-restricted content
  - browser        # Browser automation
category: development  # Optional: for UI grouping
source: SKILL.md
converted: 2025-12-27
---
```

### 2. Update SkillSummary Dataclass

**File**: `src/skills/registry.py`

```python
@dataclass
class SkillSummary:
    """Minimal skill info for progressive disclosure (Layer 1)."""
    name: str
    description: str
    category: Optional[str] = None
    deployment: str = "modal"  # NEW: default to modal
    requires: List[str] = field(default_factory=list)  # NEW
    path: Optional[Path] = None
```

### 3. Update _extract_summary Method

Parse new fields from frontmatter:

```python
def _extract_summary(self, skill_dir: Path) -> Optional[SkillSummary]:
    # ... existing code ...
    return SkillSummary(
        name=frontmatter.get('name', skill_dir.name),
        description=frontmatter.get('description', ''),
        category=frontmatter.get('category'),
        deployment=frontmatter.get('deployment', 'modal'),  # NEW
        requires=frontmatter.get('requires', []),  # NEW
        path=skill_dir
    )
```

## Validation

- [ ] SkillSummary has deployment and requires fields
- [ ] Skills without deployment field default to "modal"
- [ ] discover() returns summaries with new fields

## Effort

1 hour
