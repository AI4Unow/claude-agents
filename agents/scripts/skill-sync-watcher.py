#!/usr/bin/env python3
"""Watch skills directory for changes and auto-sync to GitHub + Modal.

Monitors agents/skills/ for file changes and:
1. Categorizes skills by deployment type (local/remote/both)
2. Commits and pushes to GitHub
3. Deploys to Modal only if remote/both skills changed

Usage:
    python3 skill-sync-watcher.py                    # Run watcher
    python3 skill-sync-watcher.py --interval 30     # Check every 30 seconds
    python3 skill-sync-watcher.py --once            # Run once and exit
"""
import argparse
import hashlib
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


# Configuration
REPO_ROOT = Path(__file__).parent.parent.parent  # /Agents/
AGENTS_DIR = REPO_ROOT / "agents"
SKILLS_DIR = AGENTS_DIR / "skills"
STATE_FILE = REPO_ROOT / ".skill-sync-state"


@dataclass
class SkillInfo:
    """Skill metadata for categorization."""
    name: str
    deployment: str  # local, remote, both

    @property
    def needs_modal(self) -> bool:
        """Check if skill needs Modal deployment."""
        return self.deployment in ("remote", "both")


def get_skill_deployment(skill_dir: Path) -> str:
    """Parse deployment field from skill's info.md frontmatter."""
    info_file = skill_dir / "info.md"
    if not info_file.exists():
        return "remote"  # Default to remote

    content = info_file.read_text()

    # Parse YAML frontmatter
    if not content.startswith("---"):
        return "remote"

    end_match = re.search(r'\n---\n', content[3:])
    if not end_match:
        return "remote"

    frontmatter = content[3:end_match.start() + 3]

    # Extract deployment field
    match = re.search(r'^deployment:\s*(\w+)', frontmatter, re.MULTILINE)
    if match:
        return match.group(1).lower()

    return "remote"


def categorize_skills(skill_names: list[str]) -> dict[str, list[SkillInfo]]:
    """Categorize skills by deployment type.

    Returns dict with keys: local, remote, both
    """
    categories = {"local": [], "remote": [], "both": []}

    for name in skill_names:
        skill_dir = SKILLS_DIR / name
        deployment = get_skill_deployment(skill_dir)
        info = SkillInfo(name=name, deployment=deployment)
        categories[deployment].append(info)

    return categories


def get_skills_hash() -> str:
    """Calculate hash of all skill files for change detection."""
    hasher = hashlib.md5()

    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith('.'):
            continue

        info_file = skill_dir / "info.md"
        if info_file.exists():
            content = info_file.read_bytes()
            hasher.update(skill_dir.name.encode())
            hasher.update(content)

    return hasher.hexdigest()


def load_last_hash() -> str:
    """Load the last synced hash from state file."""
    if STATE_FILE.exists():
        return STATE_FILE.read_text().strip()
    return ""


def save_hash(hash_value: str) -> None:
    """Save current hash to state file."""
    STATE_FILE.write_text(hash_value)


def run_command(cmd: list[str], cwd: Path = None) -> tuple[bool, str]:
    """Run a shell command and return (success, output)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def get_changed_skills() -> list[str]:
    """Get list of skills with uncommitted changes."""
    success, output = run_command(["git", "status", "--porcelain", "agents/skills/"])
    if not success:
        return []

    skills = set()
    for line in output.strip().split('\n'):
        if not line:
            continue
        # Extract skill name from path like "agents/skills/skill-name/info.md"
        parts = line.split()
        if len(parts) >= 2:
            path = parts[-1]
            if "agents/skills/" in path:
                skill_path = path.split("agents/skills/")[1]
                skill_name = skill_path.split("/")[0]
                skills.add(skill_name)

    return sorted(skills)


def sync_to_github(skills: list[str]) -> bool:
    """Commit and push skill changes to GitHub."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    skill_list = ", ".join(skills[:5])  # Show first 5
    if len(skills) > 5:
        skill_list += f" +{len(skills) - 5} more"

    commit_msg = f"chore: auto-sync skills ({skill_list})\n\n[skill-sync-watcher] {timestamp}"

    # Stage skill changes
    success, output = run_command(["git", "add", "agents/skills/"])
    if not success:
        print(f"❌ Failed to stage: {output}")
        return False

    # Check if there are staged changes
    success, output = run_command(["git", "diff", "--cached", "--quiet"])
    if success:
        print("ℹ️  No changes to commit")
        return True

    # Commit
    success, output = run_command(["git", "commit", "-m", commit_msg])
    if not success:
        print(f"❌ Failed to commit: {output}")
        return False

    print(f"✅ Committed: {skill_list}")

    # Push
    success, output = run_command(["git", "push"])
    if not success:
        print(f"❌ Failed to push: {output}")
        return False

    print("✅ Pushed to GitHub")
    return True


def deploy_to_modal() -> bool:
    """Deploy to Modal."""
    print("🚀 Deploying to Modal...")

    success, output = run_command(
        ["modal", "deploy", "main.py"],
        cwd=AGENTS_DIR
    )

    if not success:
        print(f"❌ Modal deploy failed: {output}")
        return False

    if "App deployed" in output:
        print("✅ Deployed to Modal")
        return True
    else:
        print(f"⚠️  Unexpected output: {output[:200]}")
        return False


def sync_if_changed(force: bool = False) -> bool:
    """Check for changes and sync if needed."""
    current_hash = get_skills_hash()
    last_hash = load_last_hash()

    if not force and current_hash == last_hash:
        return False

    changed_skills = get_changed_skills()
    if not changed_skills and not force:
        # Hash changed but no git changes - probably just read state
        save_hash(current_hash)
        return False

    # Categorize changed skills
    categories = categorize_skills(changed_skills)
    local_skills = [s.name for s in categories["local"]]
    remote_skills = [s.name for s in categories["remote"]]
    both_skills = [s.name for s in categories["both"]]

    # Check if any skills need Modal deployment
    needs_modal = bool(remote_skills or both_skills)

    print(f"\n{'='*60}")
    print(f"🔄 Skill changes detected at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   📍 Local only: {', '.join(local_skills) if local_skills else 'none'}")
    print(f"   ☁️  Remote:     {', '.join(remote_skills) if remote_skills else 'none'}")
    print(f"   🔄 Both:       {', '.join(both_skills) if both_skills else 'none'}")
    print('='*60)

    # Sync to GitHub (always)
    github_ok = sync_to_github(changed_skills)

    # Deploy to Modal only if remote/both skills changed
    modal_ok = True
    if needs_modal:
        modal_ok = deploy_to_modal()
    else:
        print("⏭️  Skipping Modal deploy (only local skills changed)")

    if github_ok and modal_ok:
        save_hash(current_hash)
        print("✅ Sync complete\n")
        return True
    else:
        print("⚠️  Sync completed with errors\n")
        return False


def watch(interval: int = 60) -> None:
    """Watch for changes and sync periodically."""
    print(f"👀 Watching {SKILLS_DIR} for changes (every {interval}s)")
    print("   Press Ctrl+C to stop\n")

    try:
        while True:
            try:
                sync_if_changed()
            except Exception as e:
                print(f"❌ Error during sync: {e}")

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n👋 Watcher stopped")


def main():
    parser = argparse.ArgumentParser(
        description="Watch skills and auto-sync to GitHub + Modal"
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=60,
        help="Check interval in seconds (default: 60)"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force sync even if no changes detected"
    )

    args = parser.parse_args()

    if args.once:
        sync_if_changed(force=args.force)
    else:
        watch(interval=args.interval)


if __name__ == "__main__":
    main()
