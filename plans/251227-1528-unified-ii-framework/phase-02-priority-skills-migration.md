---
phase: 2
title: "Priority Skills Migration"
status: pending
effort: 3h
priority: P1
dependencies: [phase-01]
---

# Phase 2: Priority Skills Migration

## Context

- Parent: [Unified II Framework](./plan.md)
- Depends on: [Phase 1 - Core Infrastructure](./phase-01-core-infrastructure.md)

## Overview

Migrate high-value Development and Design skills first. Test hybrid memory with 2-3 skills.

## Priority Skills (10 skills)

### Development (7 skills)

| Skill | Purpose | Modal Fit |
|-------|---------|-----------|
| planning | Implementation planning | High |
| debugging | Issue investigation | High |
| code-review | Quality assessment | High |
| research | Technical research | High |
| backend-development | API/DB development | High |
| frontend-development | React/TypeScript | High |
| mobile-development | React Native/Flutter | High |

### Design (3 skills)

| Skill | Purpose | Modal Fit |
|-------|---------|-----------|
| ui-ux-pro-max | UI/UX design | High |
| canvas-design | Visual art creation | High |
| ui-styling | shadcn/Tailwind | High |

## Key Insights

- Development skills are text-heavy, low dependencies
- Design skills may need canvas/image libraries
- Hybrid memory: per-skill context + shared learnings

## Requirements

1. Convert 10 SKILL.md → info.md
2. Verify scripts executable on Modal
3. Test hybrid memory with planning skill
4. Validate cross-skill knowledge extraction

## Architecture

### Hybrid Memory Flow

```
Skill Execution
      │
      ▼
┌─────────────────┐
│ Read info.md    │ ◄── Per-skill context
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Query Qdrant    │ ◄── Cross-skill insights
│ "knowledge" KB  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Execute Task    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Update info.md  │ ──► Per-skill memory
│ Memory section  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Extract insight │ ──► Qdrant knowledge
│ (if significant)│
└─────────────────┘
```

## Related Code Files

| File | Purpose |
|------|---------|
| `~/.claude/skills/planning/SKILL.md` | Planning skill source |
| `~/.claude/skills/debugging/SKILL.md` | Debugging skill source |
| `agents/src/services/qdrant.py` | Qdrant integration |
| `agents/scripts/skill-to-modal.py` | Converter (Phase 1) |

## Implementation Steps

- [ ] Run converter on 10 priority skills
- [ ] Deploy converted skills to Modal Volume
- [ ] Update base.py to query Qdrant knowledge collection
- [ ] Add knowledge extraction after task completion
- [ ] Test planning skill end-to-end
- [ ] Test cross-skill memory (planning → debugging insight)
- [ ] Document hybrid memory patterns

## Todo List

- [ ] Convert planning skill
- [ ] Convert debugging skill
- [ ] Convert code-review skill
- [ ] Convert research skill
- [ ] Convert backend-development skill
- [ ] Convert frontend-development skill
- [ ] Convert mobile-development skill
- [ ] Convert ui-ux-pro-max skill
- [ ] Convert canvas-design skill
- [ ] Convert ui-styling skill
- [ ] Test hybrid memory

## Success Criteria

1. All 10 skills deployed on Modal
2. Skills read info.md correctly
3. Memory section persists after execution
4. Cross-skill KB receives insights

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Script dependencies | High | Check imports before deploy |
| Memory sync conflicts | Medium | Lock during write |
| Qdrant rate limits | Low | Batch insert insights |

## Next Steps

→ Phase 3: Document skills (pdf, docx, pptx, xlsx)
