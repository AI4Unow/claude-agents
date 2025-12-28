---
title: "Skills Categorization & Auto-Sync System"
description: "Categorize skills by deployment target (local/modal), add deployment metadata, implement auto-sync from skills folder"
status: draft
priority: P1
effort: 6h
branch: main
tags: [agentex, skills, modal, deployment]
created: 2025-12-28
---

# Skills Categorization & Auto-Sync System

## Context

**User Request**: Process and categorize all skills into:
1. **Local** - Browser-based, requires consumer IP (e.g., video-downloader, media-processing)
2. **Modal** - Cloud-deployed via Modal.com (e.g., planning, backend-development)

Additionally: Frequently update skills from the skills folder.

**Current State**:
- 25+ skills in `agents/skills/` directory
- Skills loaded via `SkillRegistry` from Modal Volume `/skills/`
- No deployment target metadata in skill frontmatter
- Manual sync via `sync_skills_from_github()` function exists but not automated
- Local/Modal distinction not enforced

## Problem Analysis

### Why Categorization Matters

| Skill Type | Characteristics | Example Skills |
|------------|-----------------|----------------|
| **Local** | Needs browser, file system, consumer IP, CLI tools | video-downloader, media-processing, pdf, docx, pptx, xlsx, image-enhancer |
| **Modal** | Stateless, API-based, LLM-only, cloud-friendly | planning, research, backend-development, code-review, ai-artist |

**Local skills cannot run on Modal.com because**:
- Need ffmpeg/imagemagick/yt-dlp installed locally
- Access local file system for input/output
- Some require consumer IP (geo-restricted content)
- Browser automation needs headless Chrome locally

**Modal skills benefit from**:
- Always-on availability via webhooks
- Shared memory via Volume
- Horizontal scaling
- Lower latency for API-based work

## Implementation Phases

| Phase | Description | Status | Effort |
|-------|-------------|--------|--------|
| [Phase 01](./phase-01-skill-metadata.md) | Add `deployment` field to skill frontmatter | pending | 1h |
| [Phase 02](./phase-02-categorize-skills.md) | Audit all 25+ skills, assign deployment targets | pending | 2h |
| [Phase 03](./phase-03-registry-filtering.md) | Update SkillRegistry to filter by deployment | pending | 1.5h |
| [Phase 04](./phase-04-auto-sync.md) | Scheduled skill sync from local folder to Volume | pending | 1.5h |

## Success Criteria

- [ ] All skills have `deployment: local|modal` in frontmatter
- [ ] SkillRegistry exposes `discover(deployment="modal")` filter
- [ ] Modal endpoints only load modal-compatible skills
- [ ] Skills auto-sync to Volume on schedule (hourly or on deploy)
- [ ] Documentation updated with categorization guide

## Files to Modify

| File | Changes |
|------|---------|
| `skills/*/info.md` | Add `deployment:` and `requires:` frontmatter |
| `src/skills/registry.py` | Add deployment filter to discover() |
| `main.py` | Add scheduled sync function |
| `docs/system-architecture.md` | Document skill categorization |

## Skill Categorization (Draft)

### Local Skills (Browser/CLI required)
- `video-downloader` - yt-dlp CLI, local files
- `media-processing` - ffmpeg, imagemagick
- `pdf` - pypdf, pdfplumber, local files
- `docx` - python-docx, local files
- `pptx` - python-pptx, local files
- `xlsx` - openpyxl, local files
- `image-enhancer` - imagemagick, rmbg
- `ui-styling` - shadcn CLI, local project

### Modal Skills (Cloud-friendly)
- `planning` - LLM-only
- `research` - LLM + web search
- `backend-development` - LLM-only guidance
- `frontend-development` - LLM-only guidance
- `mobile-development` - LLM-only guidance
- `code-review` - LLM-only
- `debugging` - LLM-only
- `ai-artist` - LLM prompt engineering
- `ai-multimodal` - LLM + Gemini API
- `canvas-design` - LLM design guidance
- `ui-ux-pro-max` - LLM design guidance
- `content` - LLM content generation
- `data` - LLM data analysis
- `github` - GitHub API (cloud-friendly)
- `telegram-chat` - Telegram API (cloud-friendly)

## Dependencies

- No new external dependencies
- Uses existing Modal Volume and sync mechanisms

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Mis-categorized skill | LOW | Add `requires:` field for explicit deps |
| Sync overwrites user changes | MEDIUM | Only sync info.md, preserve Memory section |
| Volume sync latency | LOW | Use commit() after writes |
