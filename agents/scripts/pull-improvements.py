#!/usr/bin/env python3
"""Pull approved skill improvements from Firebase and apply locally.

Local-First Self-Improvement Flow:
1. Error on Modal/Local → ImprovementService → Firebase (status: pending)
2. Admin approves via Telegram → Firebase (status: approved)
3. This script: Fetch approved → Apply to local info.md → Mark applied
4. User: git commit && git push
5. modal deploy → Skills synced to Modal Volume

Usage:
    python3 agents/scripts/pull-improvements.py           # Apply all approved
    python3 agents/scripts/pull-improvements.py --dry-run # Preview changes
    python3 agents/scripts/pull-improvements.py --list    # List approved
"""
import argparse
import asyncio
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.firebase import init_firebase
from src.core.improvement import get_improvement_service, ImprovementProposal
from src.utils.logging import get_logger

logger = get_logger()

# Local skills directory
SKILLS_DIR = Path(__file__).parent.parent / "skills"


def extract_section(content: str, section_name: str) -> str:
    """Extract content of a markdown section."""
    pattern = rf"## {section_name}\n([\s\S]*?)(?=\n## |\Z)"
    match = re.search(pattern, content)
    return match.group(1).strip() if match else ""


def update_section(content: str, section_name: str, new_content: str) -> str:
    """Update or append a markdown section."""
    pattern = rf"(## {section_name}\n)[\s\S]*?(?=\n## |\Z)"
    replacement = f"## {section_name}\n\n{new_content}\n\n"
    if re.search(pattern, content):
        return re.sub(pattern, replacement, content)
    return content.rstrip() + f"\n\n{replacement}"


def apply_improvement_to_skill(
    skill_name: str,
    memory_addition: str,
    error_entry: str,
    dry_run: bool = False
) -> bool:
    """Apply improvement to local skill info.md file."""
    skill_dir = SKILLS_DIR / skill_name
    info_file = skill_dir / "info.md"

    if not info_file.exists():
        print(f"  ⚠ Skill not found locally: {skill_name}")
        return False

    content = info_file.read_text()

    # Get current sections
    current_memory = extract_section(content, "Memory")
    current_errors = extract_section(content, "Error History")

    # Build new content
    new_memory = current_memory
    if memory_addition:
        if new_memory and not new_memory.endswith("\n"):
            new_memory += "\n"
        new_memory += f"- {memory_addition}"

    new_errors = current_errors
    if error_entry:
        if new_errors and not new_errors.endswith("\n"):
            new_errors += "\n"
        new_errors += f"- {error_entry}"

    # Apply updates
    new_content = content
    if memory_addition:
        new_content = update_section(new_content, "Memory", new_memory)
    if error_entry:
        new_content = update_section(new_content, "Error History", new_errors)

    if dry_run:
        print(f"  Would update {info_file}")
        if memory_addition:
            print(f"    Memory: +\"{memory_addition[:60]}...\"")
        if error_entry:
            print(f"    Error History: +\"{error_entry[:60]}...\"")
        return True

    # Write updated content
    info_file.write_text(new_content)
    print(f"  ✓ Updated {skill_name}/info.md")
    return True


async def list_approved():
    """List all approved improvements waiting to be applied."""
    service = get_improvement_service()
    proposals = await service.get_approved_proposals(limit=50)

    if not proposals:
        print("No approved improvements waiting to be applied.")
        return

    print(f"\n{'='*60}")
    print(f"APPROVED IMPROVEMENTS ({len(proposals)} pending)")
    print(f"{'='*60}\n")

    for p in proposals:
        print(f"ID: {p.id}")
        print(f"Skill: {p.skill_name}")
        print(f"Error: {p.error_summary[:80]}...")
        print(f"Memory: {p.proposed_memory_addition[:80]}...")
        print(f"Approved: {p.created_at}")
        print("-" * 40)


async def apply_all(dry_run: bool = False):
    """Apply all approved improvements to local skills."""
    service = get_improvement_service()
    proposals = await service.get_approved_proposals(limit=50)

    if not proposals:
        print("No approved improvements to apply.")
        return 0

    print(f"\n{'='*60}")
    print(f"APPLYING {len(proposals)} IMPROVEMENTS {'(DRY RUN)' if dry_run else ''}")
    print(f"{'='*60}\n")

    applied = 0
    for p in proposals:
        print(f"\n[{p.id}] {p.skill_name}")

        success = apply_improvement_to_skill(
            skill_name=p.skill_name,
            memory_addition=p.proposed_memory_addition,
            error_entry=p.proposed_error_entry,
            dry_run=dry_run
        )

        if success and not dry_run:
            # Mark as applied in Firebase
            await service.mark_applied(p.id)
            applied += 1

    print(f"\n{'='*60}")
    if dry_run:
        print(f"DRY RUN: Would apply {len(proposals)} improvements")
    else:
        print(f"APPLIED: {applied}/{len(proposals)} improvements")
        if applied > 0:
            print("\nNext steps:")
            print("  1. Review changes: git diff agents/skills/")
            print("  2. Commit: git add agents/skills/ && git commit -m 'chore: apply skill improvements'")
            print("  3. Push: git push")
            print("  4. Deploy: modal deploy agents/main.py")
    print(f"{'='*60}\n")

    return applied


def validate_env():
    """Validate required environment variables."""
    if not os.environ.get("FIREBASE_CREDENTIALS") and not os.environ.get("FIREBASE_CREDENTIALS_JSON"):
        print("Missing FIREBASE_CREDENTIALS or FIREBASE_CREDENTIALS_JSON env var")
        print("\nSet one of:")
        print("  export FIREBASE_CREDENTIALS=/path/to/service-account.json")
        print("  export FIREBASE_CREDENTIALS_JSON='{...}'")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Pull and apply skill improvements")
    parser.add_argument("--list", action="store_true", help="List approved improvements")
    parser.add_argument("--dry-run", action="store_true", help="Preview without applying")
    parser.add_argument("--skip-validation", action="store_true", help="Skip env validation")
    args = parser.parse_args()

    if not args.skip_validation:
        validate_env()

    # Initialize Firebase
    init_firebase()

    if args.list:
        asyncio.run(list_approved())
    else:
        asyncio.run(apply_all(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
