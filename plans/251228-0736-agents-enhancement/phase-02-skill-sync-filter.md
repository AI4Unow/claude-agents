# Phase 2: Skill Sync Filter

## Context

- Plan: `./plan.md`
- Depends on: Phase 1 (Skill Categorization Schema)

## Overview

- **Priority:** P1
- **Status:** Pending
- **Effort:** 2h

Update sync_skills_from_github() to filter out local-only skills before copying to Modal Volume.

## Key Insights

- Existing function: `sync_skills_from_github()` in `main.py:811-838`
- Currently copies all skills from GitHub repo to Modal Volume
- Need to read frontmatter and skip `deployment: local` skills
- Should log which skills were skipped

## Requirements

### Functional
- Parse YAML frontmatter from each skill's info.md
- Skip skills with `deployment: local`
- Sync skills with `deployment: remote` or `deployment: both` or no field
- Log skipped skills for visibility

### Non-Functional
- Minimal performance impact (frontmatter parsing is fast)
- Clear logging for debugging

## Architecture

```python
def should_sync_to_modal(skill_path: Path) -> bool:
    """Check if skill should be synced to Modal."""
    info_file = skill_path / "info.md"
    if not info_file.exists():
        return True  # Default to sync if no info.md

    content = info_file.read_text()
    frontmatter = parse_frontmatter(content)

    deployment = frontmatter.get('deployment', 'remote')
    return deployment in ['remote', 'both']
```

## Related Code Files

### Modify
- `agents/main.py:811-838` - Add filtering logic to sync_skills_from_github()

### Create
- `agents/src/utils/frontmatter.py` - Reusable YAML frontmatter parser (optional, can inline)

## Implementation Steps

1. Add frontmatter parsing utility (or inline in function)
2. Modify sync_skills_from_github():
   - After cloning/pulling repo
   - Iterate through skills in source directory
   - Check should_sync_to_modal() for each
   - Only copy skills that pass filter
3. Add logging for skipped skills
4. Test with a local-only skill to verify filtering

## Code Changes

```python
# In main.py, modify sync_skills_from_github()

import re
import yaml

def parse_skill_frontmatter(skill_path: Path) -> dict:
    """Parse YAML frontmatter from skill info.md."""
    info_file = skill_path / "info.md"
    if not info_file.exists():
        return {}

    content = info_file.read_text()
    if not content.startswith('---'):
        return {}

    end_match = re.search(r'\n---\n', content[3:])
    if not end_match:
        return {}

    try:
        return yaml.safe_load(content[3:end_match.start() + 3]) or {}
    except yaml.YAMLError:
        return {}


def sync_skills_from_github():
    """Sync skills from GitHub repo to Modal Volume (with filtering)."""
    # ... existing clone/pull logic ...

    src_skills = os.path.join(repo_dir, skills_path_in_repo)
    if os.path.exists(src_skills):
        synced = []
        skipped = []

        for skill_dir in Path(src_skills).iterdir():
            if not skill_dir.is_dir() or skill_dir.name.startswith('.'):
                continue

            frontmatter = parse_skill_frontmatter(skill_dir)
            deployment = frontmatter.get('deployment', 'remote')

            if deployment in ['remote', 'both']:
                # Copy skill to volume
                dest = Path(f"/skills/{skill_dir.name}")
                dest.mkdir(parents=True, exist_ok=True)
                subprocess.run(["cp", "-r", f"{skill_dir}/.", str(dest)], check=True)
                synced.append(skill_dir.name)
            else:
                skipped.append(skill_dir.name)

        skills_volume.commit()

        return {
            "status": "synced",
            "synced": synced,
            "synced_count": len(synced),
            "skipped": skipped,
            "skipped_count": len(skipped),
        }

    return {"status": "skipped", "reason": "skills path not found"}
```

## Todo List

- [ ] Add parse_skill_frontmatter() function
- [ ] Modify sync_skills_from_github() with filtering logic
- [ ] Add structured logging for synced/skipped skills
- [ ] Test with local-only skill (video-downloader)
- [ ] Test with remote skill (planning)
- [ ] Deploy and verify filtering works

## Success Criteria

- Local-only skills NOT copied to Modal Volume
- Remote skills synced normally
- Logs show which skills were skipped and why
- No errors during sync process

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Frontmatter parsing fails | Medium | Fallback to 'remote' (sync anyway) |
| Wrong skills filtered | High | Test thoroughly before deploy |
| Breaking existing sync | High | Keep existing logic as fallback |

## Next Steps

After this phase, proceed to Phase 3: ImprovementService Core
