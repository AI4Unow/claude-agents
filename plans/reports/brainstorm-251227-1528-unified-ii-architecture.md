# II Framework Architecture Brainstorm

## Problem Statement

Build a unified "Information + Implementation" (II) architecture that:
1. Shares ~59 Claude Code skills between local and Modal.com environments
2. Enables per-skill memory with cross-skill knowledge sharing
3. Converts SKILL.md (immutable) to info.md (mutable) at build-time
4. Syncs scripts from Git at runtime

## Current State Analysis

### Local Skills Inventory (59 skills)

| Category | Skills | Modal Potential |
|----------|--------|-----------------|
| **Development** | planning, debugging, code-review, research, backend-development, frontend-development, mobile-development | High |
| **Documents** | pdf, docx, pptx, xlsx | Medium (requires LibreOffice) |
| **Design** | ui-ux-pro-max, canvas-design, frontend-design, frontend-design-pro, ui-styling | High |
| **Media** | ai-multimodal, media-processing, ai-artist, image-enhancer, video-downloader | High |
| **Content** | content-research-writer, internal-comms, brand-guidelines | High |
| **Infrastructure** | devops, databases, mcp-management, mcp-builder, shopify | Medium |
| **Automation** | worktree-manager, file-organizer, invoice-organizer, fb-to-tiktok | Medium |
| **Other** | sequential-thinking, problem-solving, skill-creator, repomix, etc. | Varies |

### Existing Modal Architecture

```
agents/
├── main.py                    # Modal app entry point
├── src/
│   ├── agents/               # Agent implementations
│   │   ├── base.py           # II Framework BaseAgent
│   │   ├── github_automation.py
│   │   ├── data_processor.py
│   │   └── content_generator.py
│   ├── services/             # Shared services
│   │   ├── llm.py, firebase.py, qdrant.py, embeddings.py
│   └── tools/                # Anthropic tool_use tools
│       ├── web_search.py, datetime_tool.py, code_exec.py, etc.
└── skills/                   # Modal Volume skills (info.md)
    ├── telegram-chat/info.md
    ├── github/info.md
    ├── data/info.md
    └── content/info.md
```

## Proposed Unified II Architecture

### Layer 1: Skill Format Adapter

```
SKILL.md (Claude Code)          info.md (Modal)
┌──────────────────────┐       ┌──────────────────────┐
│ ---                  │       │ # {name}             │
│ name: skill-name     │  ──►  │                      │
│ description: ...     │       │ ## Instructions      │
│ ---                  │       │ {markdown body}      │
│ # Markdown body      │       │                      │
│ ...                  │       │ ## Memory            │
└──────────────────────┘       │ [mutable section]    │
                               │                      │
                               │ ## Error History     │
                               │ [self-improvement]   │
                               └──────────────────────┘
```

**Build-time converter:** `skill-to-modal.py`
- Parse SKILL.md YAML frontmatter
- Extract description → ## Instructions header
- Copy markdown body
- Append mutable sections (## Memory, ## Error History)
- Output info.md + copy scripts to staging

### Layer 2: Hybrid Memory System

```
┌─────────────────────────────────────────────────────────┐
│                    Memory Architecture                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Per-Skill Memory (info.md)    Cross-Skill KB (Qdrant)  │
│  ┌──────────────────────┐     ┌──────────────────────┐  │
│  │ ## Memory            │     │ Collection: knowledge │  │
│  │ - User prefers...    │     │ - Shared learnings    │  │
│  │ - Last used: ...     │ ◄─► │ - Cross-skill refs    │  │
│  │ ## Error History     │     │ - Semantic search     │  │
│  │ - 2025-12-27: Fixed..│     │                      │  │
│  └──────────────────────┘     └──────────────────────┘  │
│                                                         │
│  Sync: After each task, extract insights → Qdrant      │
│  Recall: Before task, query Qdrant for relevant context │
└─────────────────────────────────────────────────────────┘
```

### Layer 3: Git-Sync Scripts

```
GitHub Repo                          Modal Volume
┌────────────────────┐              ┌────────────────────┐
│ skills/            │              │ /skills/           │
│ ├── pdf/           │   git sync   │ ├── pdf/           │
│ │   ├── SKILL.md   │ ──────────► │ │   ├── info.md    │
│ │   └── scripts/   │  (cron/     │ │   └── scripts/   │
│ ├── docx/          │   webhook)  │ ├── docx/          │
│ └── ...            │              │ └── ...            │
└────────────────────┘              └────────────────────┘
```

### Layer 4: Unified Skill Registry

```python
# skills/registry.py
class SkillRegistry:
    """Unified registry for Claude Code and Modal skills."""

    def __init__(self, skills_path: Path):
        self.skills_path = skills_path
        self._skills = {}

    def discover(self) -> List[Skill]:
        """Discover skills from both SKILL.md and info.md formats."""
        for skill_dir in self.skills_path.iterdir():
            skill_md = skill_dir / "SKILL.md"
            info_md = skill_dir / "info.md"

            if skill_md.exists():
                self._skills[skill_dir.name] = self._parse_skill_md(skill_md)
            elif info_md.exists():
                self._skills[skill_dir.name] = self._parse_info_md(info_md)

        return list(self._skills.values())

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)
```

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)
- [ ] Create `skill-to-modal.py` converter
- [ ] Extend `sync_skills_from_github()` to run converter
- [ ] Add Qdrant knowledge collection for cross-skill memory
- [ ] Create SkillRegistry class

### Phase 2: Priority Skills Migration (Week 2)
- [ ] Migrate Development skills: planning, debugging, code-review, research
- [ ] Migrate Design skills: ui-ux-pro-max, canvas-design
- [ ] Test hybrid memory with 2-3 skills

### Phase 3: Document Skills (Week 3)
- [ ] Add LibreOffice to Modal image (for xlsx recalc)
- [ ] Migrate: pdf, docx, pptx, xlsx
- [ ] Test document processing on Modal

### Phase 4: Media & Remaining Skills (Week 4)
- [ ] Migrate: ai-multimodal, media-processing, ai-artist
- [ ] Migrate remaining ~40 skills
- [ ] Full integration testing

### Phase 5: Claude Code Integration (Week 5)
- [ ] Create Claude Code skill that loads Modal skills
- [ ] Bidirectional memory sync
- [ ] End-to-end testing

## Technical Decisions

### Decision 1: Build-time Conversion
**Rationale:** SKILL.md is read-only, but Modal needs mutable info.md for self-improvement. Converting at build time:
- Preserves original SKILL.md in Git
- Adds mutable sections (Memory, Error History)
- Scripts copied to Volume with executable permissions

### Decision 2: Hybrid Memory
**Rationale:** Per-skill memory is fast and contextual, but cross-skill knowledge enables emergent learning:
- Per-skill: User preferences, recent errors, task patterns
- Cross-skill: Domain knowledge, best practices, shared learnings
- Sync happens after task completion (async, non-blocking)

### Decision 3: Git-Sync Scripts
**Rationale:** Scripts change more frequently than agent code:
- Hot-reload without redeploying Modal functions
- Single source of truth in Git
- Webhook trigger on push for instant updates

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Script dependencies | High | Bundle common deps in Modal image, validate at sync |
| Memory drift | Medium | Periodic reconciliation between info.md and Qdrant |
| LibreOffice size | Medium | Separate Modal function with larger container |
| Skill conflicts | Low | Namespace skills by category |

## Success Metrics

1. **Skill Availability:** 59/59 skills accessible on Modal
2. **Memory Persistence:** Self-improvements survive restarts
3. **Cross-skill Learning:** Insights from one skill improve others
4. **Sync Latency:** < 60s from Git push to Modal update
5. **Claude Code Parity:** Same skill behavior local and cloud

## Next Steps

1. Create detailed implementation plan
2. Build skill-to-modal.py converter (PoC with 3 skills)
3. Test hybrid memory with telegram-chat skill
4. Iterate based on learnings

## Unresolved Questions

1. Should Modal skills call Claude Code skills (reverse proxy)?
2. How to handle skills with heavy dependencies (e.g., LibreOffice, FFmpeg)?
3. Rate limiting for cross-skill Qdrant queries?
4. Versioning strategy for skill info.md changes?
