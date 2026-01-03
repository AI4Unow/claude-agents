#!/usr/bin/env python3
"""Add deployment metadata to skills missing the field.

Categories:
- LOCAL: Browser automation, consumer IP required, desktop file access
- REMOTE: API-based, always available, no browser needed
- BOTH: Works in both contexts
"""

import os
import re
from pathlib import Path

# Skill categorization based on plan validation
LOCAL_SKILLS = {
    "fb-automation",      # Facebook browser automation
    "fb-to-tiktok",       # Facebook to TikTok conversion
    "linkedin-automation", # LinkedIn browser automation
    "tiktok-automation",  # TikTok browser automation
}

BOTH_SKILLS = {
    "better-auth",        # Auth works locally and remotely
    "chrome-devtools",    # Browser tools, can run both
    "claude-code",        # Claude Code guidance, both contexts
    "mcp-builder",        # MCP works both locally and remotely
    "mcp-management",     # MCP management, both contexts
    "repomix",            # Repository analysis, both contexts
    "sequential-thinking", # Thinking patterns, both contexts
    "webapp-testing",     # Web testing, both contexts
}

# All other skills are REMOTE (API-based, LLM, no browser)
REMOTE_SKILLS = {
    "ai-artist",
    "ai-multimodal",
    "backend-development",
    "code-review",
    "content",
    "content-research-writer",
    "data",
    "databases",
    "debugging",
    "devops",
    "firebase-automation",
    "frontend-design",
    "frontend-design-pro",
    "frontend-development",
    "github",
    "internal-comms",
    "mobile-development",
    "payment-integration",
    "planning",
    "problem-solving",
    "publer-automation",
    "research",
    "shopify",
    "skill-creator",
    "telegram-chat",
    "ui-styling",
    "ui-ux-pro-max",
    "web-frameworks",
    "worktree-manager",
}


def get_deployment(skill_name: str) -> str:
    """Determine deployment type for a skill."""
    if skill_name in LOCAL_SKILLS:
        return "local"
    elif skill_name in BOTH_SKILLS:
        return "both"
    elif skill_name in REMOTE_SKILLS:
        return "remote"
    else:
        # Default to remote for unknown skills
        print(f"  [WARN] Unknown skill '{skill_name}', defaulting to remote")
        return "remote"


def update_info_md(skill_path: Path, deployment: str) -> bool:
    """Add deployment field to info.md after description."""
    info_path = skill_path / "info.md"
    if not info_path.exists():
        return False

    content = info_path.read_text()

    # Check if already has deployment
    if re.search(r"^deployment:", content, re.MULTILINE):
        print(f"  [SKIP] {skill_path.name} - already has deployment")
        return False

    # Find the end of frontmatter (second ---)
    # Insert deployment after description line
    lines = content.split("\n")
    new_lines = []
    in_frontmatter = False
    added = False

    for i, line in enumerate(lines):
        new_lines.append(line)

        if line.strip() == "---":
            if not in_frontmatter:
                in_frontmatter = True
            else:
                # End of frontmatter, add before if not added
                if not added:
                    # Insert deployment before closing ---
                    new_lines.insert(-1, f"deployment: {deployment}")
                    added = True
                in_frontmatter = False
        elif in_frontmatter and line.startswith("description:"):
            # Add deployment after description
            new_lines.append(f"deployment: {deployment}")
            added = True

    if added:
        info_path.write_text("\n".join(new_lines))
        return True
    return False


def main():
    skills_dir = Path(__file__).parent.parent / "skills"

    updated = 0
    skipped = 0
    errors = 0

    for skill_path in sorted(skills_dir.iterdir()):
        if not skill_path.is_dir():
            continue

        info_path = skill_path / "info.md"
        if not info_path.exists():
            continue

        # Check if missing deployment
        content = info_path.read_text()
        if re.search(r"^deployment:", content, re.MULTILINE):
            skipped += 1
            continue

        deployment = get_deployment(skill_path.name)

        try:
            if update_info_md(skill_path, deployment):
                print(f"  [OK] {skill_path.name} → {deployment}")
                updated += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  [ERR] {skill_path.name}: {e}")
            errors += 1

    print(f"\n=== Summary ===")
    print(f"Updated: {updated}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {errors}")

    # Verification
    missing = 0
    for skill_path in skills_dir.iterdir():
        if skill_path.is_dir():
            info_path = skill_path / "info.md"
            if info_path.exists():
                content = info_path.read_text()
                if not re.search(r"^deployment:", content, re.MULTILINE):
                    missing += 1
                    print(f"  [MISSING] {skill_path.name}")

    print(f"Still missing: {missing}")


if __name__ == "__main__":
    main()
