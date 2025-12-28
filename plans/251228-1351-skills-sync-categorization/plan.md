# Skills Sync & Modal Deployment Plan

**Date:** 2025-12-28
**Status:** READY FOR REVIEW
**Goal:** Sync local skills to GitHub, categorize for Modal deployment

## Summary

Sync 76 local skills from `~/.claude/skills/` to `agents/skills/`, commit to GitHub, and configure Modal deployment for compute-intensive skills.

## Execution Strategy

```
Phase 1: Skill Sync (Local → GitHub)
         │
         ▼
Phase 2: Modal Volume Setup
         │
         ▼
Phase 3: Skill Registration
         │
         ▼
Phase 4: Deploy & Verify
```

## Phase 1: Skill Sync to GitHub

**Duration:** Single execution
**Files:** agents/skills/*, sync script

### Tasks

1. **Create sync script**
   - Copy SKILL.md → info.md for each skill
   - Preserve scripts/ directories for executable skills
   - Skip irrelevant directories (references/, themes/, templates/)

2. **Selective sync** (Priority skills only)
   - Tier 1 (P0): ai-multimodal, media-processing, video-downloader, image-enhancer
   - Tier 2 (P1): debugging, ui-styling, docx, pdf, pptx, xlsx, canvas-design
   - Tier 3: All remaining Claude Code extension skills

3. **Git operations**
   ```bash
   git add agents/skills/
   git commit -m "feat: sync skills from local to agents project"
   git push origin main
   ```

### File Changes

```
agents/skills/
├── ai-multimodal/
│   ├── info.md          # From SKILL.md
│   └── scripts/         # Python scripts
├── media-processing/
│   ├── info.md
│   └── scripts/
├── video-downloader/
│   └── info.md
├── image-enhancer/
│   └── info.md
├── debugging/
│   ├── info.md
│   └── scripts/
└── ... (23+ more)
```

## Phase 2: Modal Volume Configuration

**Files:** agents/main.py, agents/src/skills/

### Tasks

1. **Update Volume structure**
   ```python
   skills_volume = modal.Volume.from_name("skills-volume", create_if_missing=True)

   # Mount path: /skills/{skill-name}/info.md
   ```

2. **Create skill loader**
   ```python
   def load_skill_info(skill_name: str) -> str:
       """Load info.md from Modal Volume."""
       path = f"/skills/{skill_name}/info.md"
       if os.path.exists(path):
           return Path(path).read_text()
       return ""
   ```

3. **Sync script for Volume**
   ```bash
   # One-time sync from repo to Volume
   modal volume put skills-volume agents/skills/ /skills/
   ```

## Phase 3: Skill Registration

**Files:** agents/src/skills/registry.py

### Tasks

1. **Create SkillRegistry class**
   ```python
   @dataclass
   class SkillMeta:
       name: str
       description: str
       category: str  # "compute", "llm", "hybrid"
       requires_scripts: bool
       modal_function: Optional[str] = None

   class SkillRegistry:
       def list_skills() -> List[SkillMeta]
       def get_skill(name: str) -> SkillMeta
       def load_skill_content(name: str) -> str
   ```

2. **Categorize skills**
   ```python
   SKILL_CATEGORIES = {
       "compute": ["ai-multimodal", "media-processing", "video-downloader"],
       "llm": ["planning", "research", "code-review"],
       "hybrid": ["debugging", "ui-styling", "docx", "pdf"],
   }
   ```

## Phase 4: Deployment

**Commands:**

```bash
# 1. Deploy updated code
modal deploy agents/main.py

# 2. Sync skills to Volume
modal volume put skills-volume ./agents/skills/ /skills/ --force

# 3. Verify
curl https://your-app.modal.run/api/skills
```

### Verification Checklist

- [ ] All skills listed at /api/skills endpoint
- [ ] Skill info.md accessible from Volume
- [ ] Scripts executable for compute skills
- [ ] II Framework integration working

## Categorization Summary

| Category | Count | Modal Deployment |
|----------|-------|------------------|
| Compute (P0) | 4 | Full execution on Modal |
| Hybrid (P1) | 8 | Optional Modal, works local |
| LLM-only | 11 | Info.md only, no execution |
| **Total for sync** | 23 | |

## Dependencies

- Modal CLI installed and configured
- GitHub credentials (for push)
- Modal secrets configured

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Large Volume size | Sync only essential skills |
| Script compatibility | Test scripts locally first |
| Breaking existing skills | Incremental rollout |

## Reports

- [skill-analysis.md](./skill-analysis.md) - Detailed categorization

## Next Steps After Approval

1. Execute Phase 1 (sync script)
2. Commit to GitHub
3. Execute Phase 2-4 (Modal deployment)
