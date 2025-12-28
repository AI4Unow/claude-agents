# Phase 4: Skill System Architecture

## Context

Document the II Framework skill system: progressive disclosure, routing, execution modes, and self-improvement loop. Consolidates existing implementation with enhancement plan.

## Overview

Skills = Information (.md) + Implementation (.py). Info.md lives on Modal Volume (mutable); Python code on Modal Server (immutable). Progressive disclosure loads summaries at startup, full content on-demand.

## Key Insights

- Two-layer loading reduces memory and startup time
- Semantic routing via Qdrant, keyword fallback
- Five execution modes for different use cases
- Self-improvement requires human approval

## Progressive Disclosure Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│                  PROGRESSIVE DISCLOSURE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  LAYER 1: DISCOVERY (Startup)                                   │
│  ─────────────────────────────                                  │
│  Load SkillSummary for all 25+ skills                           │
│                                                                  │
│  @dataclass                                                      │
│  class SkillSummary:                                             │
│      name: str              # "planning"                         │
│      description: str       # "Create implementation plans"      │
│      category: str          # "development"                      │
│      deployment: str        # "remote" | "local" | "both"        │
│                                                                  │
│  → Loaded from info.md frontmatter                               │
│  → Cached in memory                                              │
│  → Used for routing decisions                                    │
│                                                                  │
│                                                                  │
│  LAYER 2: ACTIVATION (On-demand)                                │
│  ────────────────────────────────                               │
│  Load full Skill when invoked                                   │
│                                                                  │
│  @dataclass                                                      │
│  class Skill:                                                    │
│      name: str                                                   │
│      description: str                                            │
│      body: str              # Full markdown content              │
│      memory: List[str]      # Accumulated learnings             │
│      error_history: List    # Past issues                       │
│      deployment: str                                             │
│                                                                  │
│  → Loaded from Modal Volume                                      │
│  → Body used as system prompt for LLM                           │
│  → Memory updated after execution                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Skill Routing Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SKILL ROUTING                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Request: "Create auth system plan"                             │
│       │                                                          │
│       ▼                                                          │
│  ┌──────────────────────┐                                        │
│  │ SkillRouter.route()  │                                        │
│  └──────────┬───────────┘                                        │
│             │                                                    │
│  ┌──────────▼───────────┐                                        │
│  │ 1. SEMANTIC SEARCH   │                                        │
│  │    (Primary)         │                                        │
│  │                      │                                        │
│  │    Embed request     │                                        │
│  │    → Qdrant search   │                                        │
│  │    → skills collection│                                       │
│  └──────────┬───────────┘                                        │
│             │                                                    │
│             ├── Success: [{skill: "planning", score: 0.92}]     │
│             │                                                    │
│             └── Failure (Qdrant down):                          │
│                        │                                         │
│  ┌──────────────────────▼───────────┐                            │
│  │ 2. KEYWORD MATCH (Fallback)     │                            │
│  │                                  │                            │
│  │    Match keywords in:           │                            │
│  │    • skill names                │                            │
│  │    • descriptions               │                            │
│  │    "plan" → "planning"          │                            │
│  └──────────────────────────────────┘                            │
│             │                                                    │
│             ▼                                                    │
│  ┌──────────────────────┐                                        │
│  │ Load Full Skill      │ ← Progressive disclosure Layer 2      │
│  │ (registry.get_full)  │                                        │
│  └──────────┬───────────┘                                        │
│             │                                                    │
│             ▼                                                    │
│  Execute with skill.body as system prompt                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Execution Modes

```
┌─────────────────────────────────────────────────────────────────┐
│                    5 EXECUTION MODES                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. SIMPLE                                                       │
│     ────────                                                     │
│     Direct skill execution, no routing                          │
│     POST /api/skill {"skill": "planning", "task": "...",        │
│                       "mode": "simple"}                         │
│                                                                  │
│  2. ROUTED                                                       │
│     ────────                                                     │
│     Auto-select best skill via semantic search                  │
│     POST /api/skill {"task": "...", "mode": "routed"}           │
│                                                                  │
│  3. ORCHESTRATED                                                 │
│     ─────────────                                                │
│     Multi-skill complex task coordination                       │
│     Orchestrator decomposes task, assigns sub-tasks             │
│     POST /api/skill {"task": "...", "mode": "orchestrated"}     │
│                                                                  │
│  4. CHAINED                                                      │
│     ─────────                                                    │
│     Sequential skill pipeline                                   │
│     Output of skill N → input of skill N+1                      │
│     POST /api/skill {"skills": ["research", "planning"],        │
│                       "task": "...", "mode": "chained"}         │
│                                                                  │
│  5. EVALUATED                                                    │
│     ──────────                                                   │
│     Execute + quality assessment                                │
│     Returns result + evaluation score                           │
│     POST /api/skill {"skill": "planning", "task": "...",        │
│                       "mode": "evaluated"}                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Self-Improvement Loop

From `plans/251228-0736-agents-enhancement/plan.md`:

```
┌─────────────────────────────────────────────────────────────────┐
│                  SELF-IMPROVEMENT LOOP                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. ERROR DETECTION                                              │
│     ─────────────────                                            │
│     agentic.py catches execution errors                         │
│     {skill, error, context, timestamp}                          │
│                                                                  │
│  2. LLM REFLECTION                                               │
│     ───────────────                                              │
│     "Given this error, how should the skill be improved?"       │
│     → ImprovementProposal {section, old_text, new_text}         │
│                                                                  │
│  3. STORE PROPOSAL                                               │
│     ───────────────                                              │
│     Firebase: skill_improvements/{proposal_id}                  │
│     {skill, proposal, status: "pending", created_at}            │
│                                                                  │
│  4. ADMIN NOTIFICATION                                           │
│     ───────────────────                                          │
│     Telegram message to ADMIN_TELEGRAM_ID                       │
│     Shows full diff inline + [Approve] [Reject] buttons         │
│                                                                  │
│  5. HUMAN DECISION                                               │
│     ───────────────                                              │
│     [Approve] → Write to info.md → Volume commit                │
│     [Reject] → Mark rejected, log reason                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Skill Sync Flow

```
CC (Source of Truth) → GitHub → Modal Volume

┌─────────────────────────────────────────────────────────────────┐
│                    SKILL SYNC FLOW                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  LOCAL (Claude Code)                                            │
│  ───────────────────                                            │
│  agents/skills/                                                  │
│  ├── planning/info.md          ◄── Edit here                   │
│  ├── research/info.md                                           │
│  └── ...                                                         │
│           │                                                      │
│           │ git commit && git push                              │
│           ▼                                                      │
│  GITHUB REPO                                                     │
│  ───────────                                                     │
│  origin/main:agents/skills/                                     │
│           │                                                      │
│           │ modal deploy (mounts skills/)                       │
│           ▼                                                      │
│  MODAL VOLUME (/skills/)                                        │
│  ───────────────────────                                        │
│  planning/info.md              ◄── Agents read/write here      │
│  research/info.md                                               │
│                                                                  │
│  IMPORTANT: Improvements written to Volume stay there           │
│  until manually synced back to CC/GitHub                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Skill Categorization (Deployment Field)

```yaml
# agents/skills/planning/info.md
---
name: planning
description: Create implementation plans
deployment: remote     # Deployed to Modal
category: development
---

# agents/skills/tiktok/info.md
---
name: tiktok
description: Post to TikTok
deployment: local      # NOT deployed to Modal
requires:
  - chrome-dev skill
  - consumer IP
---
```

**Sync Filter Logic:**

```python
def should_deploy_skill(skill_path: Path) -> bool:
    """Check if skill should be deployed to Modal."""
    info_md = skill_path / "info.md"
    metadata = parse_frontmatter(info_md.read_text())
    deployment = metadata.get("deployment", "remote")  # default: remote
    return deployment in ("remote", "both")
```

## Implementation Steps

1. [ ] Add `deployment` field to all skill info.md
2. [ ] Update SkillSummary dataclass with deployment
3. [ ] Implement sync filter in deploy script
4. [ ] Create ImprovementService in src/services/
5. [ ] Add Telegram callbacks for approve/reject
6. [ ] Test self-improvement loop end-to-end

## Todo List

- [ ] Audit all 25+ skills for deployment field
- [ ] Document which skills are local-only
- [ ] Create skill template with all fields
- [ ] Add skill versioning (optional)

## Success Criteria

- [ ] All skills have deployment field
- [ ] Local-only skills NOT in Modal Volume
- [ ] Self-improvement proposals sent to admin
- [ ] Approve/reject buttons functional
- [ ] Approved changes persist to Volume
