# Phase 04: Automated Skill Sync

## Objective

Implement scheduled skill synchronization from local skills folder to Modal Volume.

## Current State

- `sync_skills_from_github()` exists but requires GitHub repo configuration
- No automatic sync on deploy
- Skills manually deployed via `init_skills()` for base agents only

## Changes

### 1. Add Deploy-Time Sync

**File**: `main.py`

Add skills folder to container image:

```python
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "curl")
    .pip_install_from_requirements("requirements.txt")
    .add_local_dir("src", remote_path="/root/src")
    .add_local_dir("skills", remote_path="/root/skills_source")  # NEW
)
```

### 2. Create Sync Function

```python
@app.function(
    image=image,
    volumes={"/skills": skills_volume},
    timeout=120,
)
def sync_skills_from_local():
    """Sync skills from container's skills_source to Modal Volume.

    Called on deploy to ensure Volume has latest skill definitions.
    Preserves Memory and Error History sections.
    """
    import shutil
    from pathlib import Path

    source_dir = Path("/root/skills_source")
    target_dir = Path("/skills")

    if not source_dir.exists():
        return {"status": "skipped", "reason": "No skills_source directory"}

    synced = []
    for skill_dir in source_dir.iterdir():
        if not skill_dir.is_dir() or skill_dir.name.startswith('.'):
            continue

        target_skill = target_dir / skill_dir.name
        target_skill.mkdir(parents=True, exist_ok=True)

        # Sync info.md (preserve Memory section)
        source_info = skill_dir / "info.md"
        target_info = target_skill / "info.md"

        if source_info.exists():
            if target_info.exists():
                # Preserve existing Memory and Error History
                memory = _extract_section(target_info.read_text(), "Memory")
                errors = _extract_section(target_info.read_text(), "Error History")

                new_content = source_info.read_text()
                if memory:
                    new_content = _update_section(new_content, "Memory", memory)
                if errors:
                    new_content = _update_section(new_content, "Error History", errors)

                target_info.write_text(new_content)
            else:
                shutil.copy2(source_info, target_info)

            synced.append(skill_dir.name)

        # Sync references directory
        source_refs = skill_dir / "references"
        if source_refs.exists():
            target_refs = target_skill / "references"
            if target_refs.exists():
                shutil.rmtree(target_refs)
            shutil.copytree(source_refs, target_refs)

    skills_volume.commit()
    return {"status": "synced", "skills": synced, "count": len(synced)}


def _extract_section(content: str, section_name: str) -> str:
    """Extract content of a markdown section."""
    import re
    pattern = rf"## {section_name}\n([\s\S]*?)(?=\n## |\Z)"
    match = re.search(pattern, content)
    return match.group(1).strip() if match else ""


def _update_section(content: str, section_name: str, new_content: str) -> str:
    """Update or append a markdown section."""
    import re
    pattern = rf"(## {section_name}\n)[\s\S]*?(?=\n## |\Z)"
    replacement = f"## {section_name}\n\n{new_content}\n\n"
    if re.search(pattern, content):
        return re.sub(pattern, replacement, content)
    return content + f"\n{replacement}"
```

### 3. Add Scheduled Sync (Optional)

```python
@app.function(
    image=image,
    volumes={"/skills": skills_volume},
    schedule=modal.Cron("0 */6 * * *"),  # Every 6 hours
    timeout=120,
)
def scheduled_skill_sync():
    """Scheduled sync from GitHub (if configured) or local."""
    import os

    if os.environ.get("SKILLS_REPO"):
        return sync_skills_from_github()
    return {"status": "skipped", "reason": "No SKILLS_REPO configured"}
```

### 4. Add Deploy Hook

Call sync on deploy via local entrypoint:

```python
@app.local_entrypoint()
def main(sync: bool = False):
    """Local entrypoint with optional skill sync."""
    if sync:
        print("Syncing skills to Volume...")
        result = sync_skills_from_local.remote()
        print(f"Sync result: {result}")

    print("Testing LLM...")
    result = test_llm.remote()
    print(f"LLM test result: {result}")
```

Usage:
```bash
modal run main.py --sync  # Sync skills before test
modal deploy main.py      # Skills synced via image layer
```

## Validation

- [ ] `sync_skills_from_local()` copies skills to Volume
- [ ] Memory and Error History sections preserved
- [ ] References directory synced
- [ ] `modal deploy` includes skills in container
- [ ] Volume commit() called after sync

## Effort

1.5 hours
