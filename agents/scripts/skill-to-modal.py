#!/usr/bin/env python3
"""Convert SKILL.md files to Modal-compatible info.md format.

II Framework Converter:
- Parses YAML frontmatter from SKILL.md (immutable source)
- Creates info.md with mutable sections (## Memory, ## Error History)
- Supports progressive disclosure via SkillSummary extraction
"""
import argparse
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import yaml


@dataclass
class SkillSummary:
    """Minimal skill info for progressive disclosure."""
    name: str
    description: str
    category: Optional[str] = None
    license: Optional[str] = None


@dataclass
class SkillContent:
    """Full skill content for activation."""
    name: str
    description: str
    body: str
    frontmatter: dict
    references: list[str]


def parse_frontmatter(content: str) -> Tuple[dict, str]:
    """Parse YAML frontmatter from markdown content.

    Returns:
        Tuple of (frontmatter_dict, markdown_body)
    """
    if not content.startswith('---'):
        return {}, content

    # Find end of frontmatter
    end_match = re.search(r'\n---\n', content[3:])
    if not end_match:
        return {}, content

    end_pos = end_match.start() + 3
    frontmatter_str = content[3:end_pos]
    body = content[end_pos + 4:]  # Skip closing ---\n

    try:
        frontmatter = yaml.safe_load(frontmatter_str)
        return frontmatter if frontmatter else {}, body
    except yaml.YAMLError as e:
        print(f"Warning: YAML parse error: {e}")
        return {}, content


def extract_references(body: str) -> list[str]:
    """Extract reference file paths from skill body.

    Looks for patterns like: Load: `references/file.md`
    """
    pattern = r"Load:\s*`([^`]+)`"
    return re.findall(pattern, body)


def extract_summary(skill_path: Path) -> Optional[SkillSummary]:
    """Extract minimal skill summary for progressive disclosure.

    Only reads frontmatter, not full body.
    """
    skill_file = skill_path / "SKILL.md"
    if not skill_file.exists():
        return None

    content = skill_file.read_text()
    frontmatter, _ = parse_frontmatter(content)

    if not frontmatter:
        return None

    return SkillSummary(
        name=frontmatter.get('name', skill_path.name),
        description=frontmatter.get('description', ''),
        category=frontmatter.get('category'),
        license=frontmatter.get('license'),
    )


def parse_skill(skill_path: Path) -> Optional[SkillContent]:
    """Parse full skill content from SKILL.md."""
    skill_file = skill_path / "SKILL.md"
    if not skill_file.exists():
        return None

    content = skill_file.read_text()
    frontmatter, body = parse_frontmatter(content)

    references = extract_references(body)

    return SkillContent(
        name=frontmatter.get('name', skill_path.name),
        description=frontmatter.get('description', ''),
        body=body,
        frontmatter=frontmatter,
        references=references,
    )


def resolve_references(skill: SkillContent, skill_path: Path) -> str:
    """Resolve and inline reference files into skill body."""
    body = skill.body

    for ref in skill.references:
        ref_path = skill_path / ref
        if ref_path.exists():
            ref_content = ref_path.read_text()
            # Replace Load: `ref` with actual content
            pattern = rf"Load:\s*`{re.escape(ref)}`"
            body = re.sub(pattern, ref_content, body)

    return body


def create_info_md(skill: SkillContent, skill_path: Path, include_refs: bool = True) -> str:
    """Create info.md content from skill.

    Adds mutable sections:
    - ## Memory: Per-skill learning storage
    - ## Error History: Past errors and fixes
    """
    # Resolve references if requested
    body = resolve_references(skill, skill_path) if include_refs else skill.body

    # Build info.md content
    info_content = f"""---
name: {skill.name}
description: {skill.description}
source: SKILL.md
converted: {datetime.now().strftime('%Y-%m-%d')}
---

{body.strip()}

## Memory

<!-- Per-skill memory: patterns, preferences, learnings -->
<!-- Updated automatically after each task -->

## Error History

<!-- Past errors and fixes -->
<!-- Format: YYYY-MM-DD: error description - fix applied -->
"""

    return info_content


def convert_skill(
    skill_path: Path,
    output_dir: Path,
    include_refs: bool = True,
    dry_run: bool = False
) -> bool:
    """Convert a single skill from SKILL.md to info.md.

    Args:
        skill_path: Path to skill directory containing SKILL.md
        output_dir: Output directory for converted skills
        include_refs: Whether to inline reference files
        dry_run: Print output without writing

    Returns:
        True if conversion successful
    """
    skill = parse_skill(skill_path)
    if not skill:
        print(f"Skipping {skill_path.name}: No SKILL.md found")
        return False

    info_content = create_info_md(skill, skill_path, include_refs)

    if dry_run:
        print(f"=== {skill.name} ===")
        print(info_content[:500])
        print("...")
        return True

    # Create output directory
    out_skill_dir = output_dir / skill_path.name
    out_skill_dir.mkdir(parents=True, exist_ok=True)

    # Write info.md
    info_file = out_skill_dir / "info.md"
    info_file.write_text(info_content)

    # Copy scripts directory if exists
    scripts_dir = skill_path / "scripts"
    if scripts_dir.exists():
        import shutil
        out_scripts = out_skill_dir / "scripts"
        if out_scripts.exists():
            shutil.rmtree(out_scripts)
        shutil.copytree(scripts_dir, out_scripts)

    print(f"Converted: {skill.name} -> {info_file}")
    return True


def convert_all_skills(
    skills_dir: Path,
    output_dir: Path,
    include_refs: bool = True,
    dry_run: bool = False
) -> dict:
    """Convert all skills in a directory.

    Returns:
        Summary dict with counts
    """
    results = {"converted": 0, "skipped": 0, "errors": 0}

    for skill_path in skills_dir.iterdir():
        if not skill_path.is_dir():
            continue
        if skill_path.name.startswith('.'):
            continue

        try:
            if convert_skill(skill_path, output_dir, include_refs, dry_run):
                results["converted"] += 1
            else:
                results["skipped"] += 1
        except Exception as e:
            print(f"Error converting {skill_path.name}: {e}")
            results["errors"] += 1

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Convert SKILL.md files to Modal-compatible info.md"
    )
    parser.add_argument(
        "skills_dir",
        type=Path,
        help="Directory containing skill subdirectories with SKILL.md files"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("/skills"),
        help="Output directory for converted skills (default: /skills)"
    )
    parser.add_argument(
        "--no-refs",
        action="store_true",
        help="Don't inline reference files"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print output without writing files"
    )
    parser.add_argument(
        "--single",
        type=str,
        help="Convert only a single skill by name"
    )

    args = parser.parse_args()

    if not args.skills_dir.exists():
        print(f"Error: Skills directory not found: {args.skills_dir}")
        sys.exit(1)

    if args.single:
        skill_path = args.skills_dir / args.single
        if not skill_path.exists():
            print(f"Error: Skill not found: {args.single}")
            sys.exit(1)
        success = convert_skill(
            skill_path,
            args.output,
            not args.no_refs,
            args.dry_run
        )
        sys.exit(0 if success else 1)

    results = convert_all_skills(
        args.skills_dir,
        args.output,
        not args.no_refs,
        args.dry_run
    )

    print(f"\nConversion complete:")
    print(f"  Converted: {results['converted']}")
    print(f"  Skipped: {results['skipped']}")
    print(f"  Errors: {results['errors']}")


if __name__ == "__main__":
    main()
