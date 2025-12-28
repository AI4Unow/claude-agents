---
name: worktree-manager
description: Create, manage, and cleanup git worktrees with Claude Code agents across all projects. USE THIS SKILL when user says "create worktree", "spin up worktrees", "new worktree for X", "worktree status", "cleanup worktrees", or wants parallel development branches. Handles worktree creation, dependency installation, validation, agent launching in Ghostty, and global registry management.
---

# Global Worktree Manager

Manage parallel development across ALL projects using git worktrees with Claude Code agents. Each worktree is an isolated copy of the repo on a different branch, stored centrally at `~/tmp/worktrees/`.

**IMPORTANT**: You (Claude) can perform ALL operations manually using standard tools (jq, git, bash). Scripts are helpers, not requirements. If a script fails, fall back to manual operations described in this document.

## When This Skill Activates

**Trigger phrases:**
- "spin up worktrees for X, Y, Z"
- "create 3 worktrees for features A, B, C"
- "new worktree for feature/auth"
- "what's the status of my worktrees?"
- "show all worktrees" / "show worktrees for this project"
- "clean up merged worktrees"
- "clean up the auth worktree"
- "launch agent in worktree X"

---

## File Locations

| File | Purpose |
|------|---------|
| `~/.claude/worktree-registry.json` | **Global registry** - tracks all worktrees across all projects |
| `~/.claude/skills/worktree-manager/config.json` | **Skill config** - terminal, shell, port range settings |
| `~/.claude/skills/worktree-manager/scripts/` | **Helper scripts** - optional, can do everything manually |
| `~/tmp/worktrees/` | **Worktree storage** - all worktrees live here |
| `.claude/worktree.json` (per-project) | **Project config** - optional custom settings |

---

## Core Concepts

### Centralized Worktree Storage
All worktrees live in `~/tmp/worktrees/<project-name>/<branch-slug>/`

```
~/tmp/worktrees/
├── obsidian-ai-agent/
│   ├── feature-auth/           # branch: feature/auth
│   ├── feature-payments/       # branch: feature/payments
│   └── fix-login-bug/          # branch: fix/login-bug
└── another-project/
    └── feature-dark-mode/
```

### Branch Slug Convention
Branch names are slugified for filesystem safety by replacing `/` with `-`:
- `feature/auth` → `feature-auth`
- `fix/login-bug` → `fix-login-bug`
- `feat/user-profile` → `feat-user-profile`

**Slugify manually:** `echo "feature/auth" | tr '/' '-'` → `feature-auth`

### Port Allocation Rules
- **Global pool**: 8100-8199 (100 ports total)
- **Per worktree**: 2 ports allocated (for API + frontend patterns)
- **Globally unique**: Ports are tracked globally to avoid conflicts across projects
- **Check before use**: Always verify port isn't in use by system: `lsof -i :<port>`

---

## Global Registry

### Location
`~/.claude/worktree-registry.json`

### Schema
```json
{
  "worktrees": [
    {
      "id": "unique-uuid",
      "project": "obsidian-ai-agent",
      "repoPath": "/Users/rasmus/Projects/obsidian-ai-agent",
      "branch": "feature/auth",
      "branchSlug": "feature-auth",
      "worktreePath": "/Users/rasmus/tmp/worktrees/obsidian-ai-agent/feature-auth",
      "ports": [8100, 8101],
      "createdAt": "2025-12-04T10:00:00Z",
      "validatedAt": "2025-12-04T10:02:00Z",
      "agentLaunchedAt": "2025-12-04T10:03:00Z",
      "task": "Implement OAuth login",
      "prNumber": null,
      "status": "active"
    }
  ],
  "portPool": {
    "start": 8100,
    "end": 8199,
    "allocated": [8100, 8101]
  }
}
```

### Manual Registry Operations

**Initialize empty registry (if missing):**
```bash
mkdir -p ~/.claude
cat > ~/.claude/worktree-registry.json << 'EOF'
{
  "worktrees": [],
  "portPool": {
    "start": 8100,
    "end": 8199,
    "allocated": []
  }
}
EOF
```

**List all worktrees:**
```bash
cat ~/.claude/worktree-registry.json | jq '.worktrees[]'
```

**List worktrees for specific project:**
```bash
cat ~/.claude/worktree-registry.json | jq '.worktrees[] | select(.project == "my-project")'
```

---

## Workflows

### 1. Create Multiple Worktrees with Agents

**User says:** "Spin up 3 worktrees for feature/auth, feature/payments, and fix/login-bug"

**You do (can parallelize with subagents):**

```
For EACH branch (can run in parallel):

1. SETUP
   a. Get project name:
      PROJECT=$(basename $(git remote get-url origin 2>/dev/null | sed 's/\.git$//') 2>/dev/null || basename $(pwd))
   b. Get repo root:
      REPO_ROOT=$(git rev-parse --show-toplevel)
   c. Slugify branch:
      BRANCH_SLUG=$(echo "feature/auth" | tr '/' '-')
   d. Determine worktree path:
      WORKTREE_PATH=~/tmp/worktrees/$PROJECT/$BRANCH_SLUG

2. ALLOCATE PORTS
   Option A (script): ~/.claude/skills/worktree-manager/scripts/allocate-ports.sh 2
   Option B (manual): Find 2 unused ports from 8100-8199, add to registry

3. CREATE WORKTREE
   mkdir -p ~/tmp/worktrees/$PROJECT
   git worktree add $WORKTREE_PATH -b $BRANCH
   # If branch exists already, omit -b flag

4. COPY UNCOMMITTED RESOURCES
   cp -r .agents $WORKTREE_PATH/ 2>/dev/null || true
   cp .env.example $WORKTREE_PATH/.env 2>/dev/null || true

5. INSTALL DEPENDENCIES
   cd $WORKTREE_PATH
   # Detect and run: npm install / uv sync / etc.

6. VALIDATE (start server, health check, stop)
   a. Start server with allocated port
   b. Wait and health check: curl -sf http://localhost:$PORT/health
   c. Stop server
   d. If FAILS: report error but continue with other worktrees

7. REGISTER IN GLOBAL REGISTRY
   Option A (script): ~/.claude/skills/worktree-manager/scripts/register.sh ...
   Option B (manual): Update ~/.claude/worktree-registry.json with jq

8. LAUNCH AGENT
   Option A (script): ~/.claude/skills/worktree-manager/scripts/launch-agent.sh $WORKTREE_PATH "task"
   Option B (manual): Open terminal manually, cd to path, run claude
```

### 2. Check Status

**With script:**
```bash
~/.claude/skills/worktree-manager/scripts/status.sh
~/.claude/skills/worktree-manager/scripts/status.sh --project my-project
```

**Manual:**
```bash
cat ~/.claude/worktree-registry.json | jq -r '.worktrees[] | "\(.project)\t\(.branch)\t\(.ports | join(","))\t\(.status)\t\(.task // "-")"'
```

### 3. Cleanup Worktree

**With script:**
```bash
~/.claude/skills/worktree-manager/scripts/cleanup.sh my-project feature/auth --delete-branch
```

**Manual cleanup:**
```bash
# 1. Get worktree info from registry
ENTRY=$(cat ~/.claude/worktree-registry.json | jq '.worktrees[] | select(.project == "my-project" and .branch == "feature/auth")')
WORKTREE_PATH=$(echo "$ENTRY" | jq -r '.worktreePath')
PORTS=$(echo "$ENTRY" | jq -r '.ports[]')
REPO_PATH=$(echo "$ENTRY" | jq -r '.repoPath')

# 2. Kill processes on ports
for PORT in $PORTS; do
  lsof -ti:"$PORT" | xargs kill -9 2>/dev/null || true
done

# 3. Remove worktree
cd "$REPO_PATH"
git worktree remove "$WORKTREE_PATH" --force 2>/dev/null || rm -rf "$WORKTREE_PATH"
git worktree prune

# 4. Remove from registry
TMP=$(mktemp)
jq 'del(.worktrees[] | select(.project == "my-project" and .branch == "feature/auth"))' \
  ~/.claude/worktree-registry.json > "$TMP" && mv "$TMP" ~/.claude/worktree-registry.json

# 5. Release ports
TMP=$(mktemp)
for PORT in $PORTS; do
  jq ".portPool.allocated = (.portPool.allocated | map(select(. != $PORT)))" \
    ~/.claude/worktree-registry.json > "$TMP" && mv "$TMP" ~/.claude/worktree-registry.json
done
```

---

## Package Manager Detection

Detect by checking for lockfiles in priority order:

| File | Package Manager | Install Command |
|------|-----------------|-----------------|
| `bun.lockb` | bun | `bun install` |
| `pnpm-lock.yaml` | pnpm | `pnpm install` |
| `yarn.lock` | yarn | `yarn install` |
| `package-lock.json` | npm | `npm install` |
| `uv.lock` | uv | `uv sync` |
| `pyproject.toml` (no uv.lock) | uv | `uv sync` |
| `requirements.txt` | pip | `pip install -r requirements.txt` |
| `go.mod` | go | `go mod download` |
| `Cargo.toml` | cargo | `cargo build` |

---

## Script Reference

Scripts are in `~/.claude/skills/worktree-manager/scripts/`

### allocate-ports.sh
```bash
~/.claude/skills/worktree-manager/scripts/allocate-ports.sh <count>
# Returns: space-separated port numbers (e.g., "8100 8101")
```

### register.sh
```bash
~/.claude/skills/worktree-manager/scripts/register.sh \
  <project> <branch> <branch-slug> <worktree-path> <repo-path> <ports> [task]
```

### launch-agent.sh
```bash
~/.claude/skills/worktree-manager/scripts/launch-agent.sh <worktree-path> [task]
# Opens new terminal window (Ghostty by default) with Claude Code
```

### status.sh
```bash
~/.claude/skills/worktree-manager/scripts/status.sh [--project <name>]
```

### cleanup.sh
```bash
~/.claude/skills/worktree-manager/scripts/cleanup.sh <project> <branch> [--delete-branch]
```

### release-ports.sh
```bash
~/.claude/skills/worktree-manager/scripts/release-ports.sh <port1> [port2] ...
```

---

## Skill Config

Location: `~/.claude/skills/worktree-manager/config.json`

```json
{
  "terminal": "ghostty",
  "shell": "bash",
  "claudeCommand": "claude --dangerously-skip-permissions",
  "portPool": { "start": 8100, "end": 8199 },
  "portsPerWorktree": 2,
  "worktreeBase": "~/tmp/worktrees"
}
```

**Options:**
- **terminal**: `ghostty`, `iterm2`, `tmux`, `wezterm`, `kitty`, `alacritty`
- **shell**: `bash`, `zsh`, `fish`
- **claudeCommand**: Command to launch Claude Code

---

## Common Issues

### "Worktree already exists"
```bash
git worktree list
git worktree remove <path> --force
git worktree prune
```

### "Branch already exists"
```bash
# Use existing branch (omit -b flag)
git worktree add <path> <branch>
```

### "Port already in use"
```bash
lsof -i :<port>
# Kill if stale, or pick different port
```
