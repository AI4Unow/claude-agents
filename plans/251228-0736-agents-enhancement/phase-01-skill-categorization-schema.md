# Phase 1: Skill Categorization Schema

## Context

- Plan: `./plan.md`
- Brainstorm: `plans/reports/brainstorm-251228-0736-agents-enhancement-integration.md`

## Overview

- **Priority:** P1
- **Status:** Pending
- **Effort:** 2h

Add `deployment` field to skill YAML frontmatter to categorize skills as local-only, remote-only, or both.

## Key Insights

- Browser automation skills (TikTok, Facebook, YouTube, LinkedIn) need consumer IP to avoid bot detection
- API-based skills safe for cloud deployment
- Current frontmatter has: name, description, category, source, converted
- Need to add: deployment, requires_browser

## Requirements

### Functional
- Add `deployment` field with values: `local`, `remote`, `both`
- Add `requires_browser` boolean field (optional)
- Default to `remote` if field missing (backward compatible)
- Update existing 25+ skills with appropriate values

### Non-Functional
- No breaking changes to SkillRegistry
- Maintain backward compatibility with existing skills

## Architecture

```yaml
# Updated skill frontmatter schema
---
name: video-downloader
description: Download videos from YouTube
category: media
deployment: local       # NEW: local | remote | both (default: remote)
requires_browser: true  # NEW: uses chrome-dev/chrome skill for browser automation
source: SKILL.md
converted: 2025-12-27
---
```

## Related Code Files

### Modify
- `agents/skills/*/info.md` - Add deployment field to all skills

### No Changes Required
- `agents/src/skills/registry.py` - SkillRegistry ignores unknown frontmatter fields

## Implementation Steps

1. Define skill categorization rules
2. Update local-only skills:
   - `video-downloader/info.md` - deployment: local
   - `fb-to-tiktok/info.md` (if exists) - deployment: local
   - Social media skills - deployment: local
3. Update remote skills (explicit or leave default):
   - `planning/info.md` - deployment: remote
   - `research/info.md` - deployment: remote
   - `backend-development/info.md` - deployment: remote
   - All API-based skills
4. Document categorization rules in CLAUDE.md

## Todo List

- [ ] Identify all local-only skills in codebase
- [ ] Add `deployment: local` to video-downloader
- [ ] Add `deployment: local` to all browser automation skills
- [ ] Add `deployment: remote` to API-based skills (or leave default)
- [ ] Update `agents/skills/CLAUDE.md` with schema docs
- [ ] Test SkillRegistry still parses updated frontmatter

## Success Criteria

- All 25+ skills have explicit or implicit deployment categorization
- SkillRegistry.discover() works with updated frontmatter
- No runtime errors when loading skills

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking frontmatter parsing | High | Test registry before deploy |
| Missing skills categorization | Low | Default to 'remote' is safe |

## Next Steps

After this phase, proceed to Phase 2: Skill Sync Filter
