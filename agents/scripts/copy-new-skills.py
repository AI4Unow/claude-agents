#!/usr/bin/env python3
"""Copy new skills from ~/.claude/skills/ to agents/skills/ with deployment metadata.

- Copies SKILL.md as info.md with YAML frontmatter
- Copies scripts/ directory if present
- Assigns deployment based on skill type
"""

import os
import re
import shutil
from pathlib import Path

# Directories to exclude (not skills)
EXCLUDE = {'.venv', 'common', 'core', 'examples', 'reference', 'references', 'scripts', 'templates', 'themes'}

# LOCAL skills: Browser automation, consumer IP required
LOCAL_SKILLS = {
    "artifacts-builder",       # Browser-based
    "caption-automation",      # Browser automation
    "code-refactoring",        # Local file access
    "email-marketing",         # Potentially browser-based
    "file-organizer",          # Local file access
    "google-adk-python",       # Local development
    "invoice-organizer",       # Local file processing
    "markdown-novel-viewer",   # Local file viewing
    "marketing-dashboard",     # Browser dashboard
    "masterplan-builder",      # Local planning
    "mermaidjs-v11",           # Local rendering
    "threejs",                 # Browser 3D
}

# BOTH skills: Work in both contexts
BOTH_SKILLS = {
    "kit-builder",             # Can build kits locally or remotely
    "plans-kanban",            # Works both ways
    "seo-optimization",        # API + browser analysis
    "slack-gif-creator",       # Can work both ways
    "test-orchestrator",       # Both contexts
}

# All others are REMOTE (API-based, LLM, no browser)

# Category mapping based on skill name patterns
CATEGORY_PATTERNS = {
    "development": ["code", "dev", "backend", "frontend", "mobile", "framework"],
    "design": ["design", "ui", "ux", "theme", "canvas", "mermaid", "threejs"],
    "marketing": ["ads", "campaign", "seo", "social", "marketing", "email", "referral", "affiliate", "lead", "competitive"],
    "content": ["content", "copywriting", "creativity", "brainstorm", "writing", "novel"],
    "document": ["document", "docs", "pdf", "invoice", "file", "assets", "storage"],
    "automation": ["automation", "organizer", "builder", "generator", "extractor"],
    "analytics": ["analytics", "data", "growth", "insights", "meeting"],
    "agent": ["agent", "telegram", "github", "slack"],
    "media": ["video", "image", "youtube", "gif"],
}


def get_category(skill_name: str) -> str:
    """Determine category based on skill name."""
    for category, patterns in CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if pattern in skill_name.lower():
                return category
    return "general"


def get_deployment(skill_name: str) -> str:
    """Determine deployment type for a skill."""
    if skill_name in LOCAL_SKILLS:
        return "local"
    elif skill_name in BOTH_SKILLS:
        return "both"
    else:
        return "remote"


def extract_description(content: str) -> str:
    """Extract description from SKILL.md content."""
    # Try to find first paragraph after title
    lines = content.split('\n')
    in_content = False
    for line in lines:
        if line.startswith('#'):
            in_content = True
            continue
        if in_content and line.strip() and not line.startswith('#'):
            # Clean up markdown
            desc = line.strip()
            desc = re.sub(r'\[.*?\]\(.*?\)', '', desc)  # Remove links
            desc = re.sub(r'[*_`]', '', desc)  # Remove formatting
            desc = desc[:100]  # Limit length
            if desc:
                return desc
    return "Skill for specialized tasks"


def copy_skill(skill_name: str, src_dir: Path, dest_dir: Path) -> bool:
    """Copy a skill from ~/.claude/skills/ to agents/skills/."""
    skill_src = src_dir / skill_name
    skill_dest = dest_dir / skill_name
    skill_md = skill_src / "SKILL.md"

    if not skill_md.exists():
        print(f"  [SKIP] {skill_name} - no SKILL.md")
        return False

    # Create destination directory
    skill_dest.mkdir(exist_ok=True)

    # Read SKILL.md
    content = skill_md.read_text()

    # Extract description
    description = extract_description(content)

    # Determine category and deployment
    category = get_category(skill_name)
    deployment = get_deployment(skill_name)

    # Create info.md with YAML frontmatter
    frontmatter = f"""---
name: {skill_name}
description: {description}
category: {category}
deployment: {deployment}
---

"""

    # Write info.md
    info_md = skill_dest / "info.md"
    info_md.write_text(frontmatter + content)

    # Copy scripts directory if present
    scripts_src = skill_src / "scripts"
    if scripts_src.exists() and scripts_src.is_dir():
        scripts_dest = skill_dest / "scripts"
        if scripts_dest.exists():
            shutil.rmtree(scripts_dest)
        shutil.copytree(scripts_src, scripts_dest)
        print(f"  [OK] {skill_name} → {deployment} (with scripts)")
    else:
        print(f"  [OK] {skill_name} → {deployment}")

    return True


def main():
    src_dir = Path.home() / ".claude" / "skills"
    dest_dir = Path(__file__).parent.parent / "skills"

    # Get existing skills
    existing = set()
    for skill in dest_dir.iterdir():
        if skill.is_dir():
            existing.add(skill.name)

    # Get new skills
    new_skills = []
    for skill in src_dir.iterdir():
        if skill.is_dir() and skill.name not in EXCLUDE and skill.name not in existing:
            if (skill / "SKILL.md").exists():
                new_skills.append(skill.name)

    print(f"Found {len(new_skills)} new skills to copy\n")

    copied = 0
    skipped = 0
    errors = 0

    local_count = 0
    remote_count = 0
    both_count = 0

    for skill_name in sorted(new_skills):
        try:
            if copy_skill(skill_name, src_dir, dest_dir):
                copied += 1
                dep = get_deployment(skill_name)
                if dep == "local":
                    local_count += 1
                elif dep == "remote":
                    remote_count += 1
                else:
                    both_count += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  [ERR] {skill_name}: {e}")
            errors += 1

    print(f"\n=== Summary ===")
    print(f"Copied: {copied}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {errors}")
    print(f"\nDeployment distribution:")
    print(f"  Local: {local_count}")
    print(f"  Remote: {remote_count}")
    print(f"  Both: {both_count}")

    # Final count
    total = len(list(dest_dir.iterdir()))
    print(f"\nTotal skills in agents/skills/: {total}")


if __name__ == "__main__":
    main()
