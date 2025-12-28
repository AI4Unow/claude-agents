---
phase: 4
title: "Media & Procaffe Scripts"
status: pending
effort: 2h
priority: P2
dependencies: [phase-03]
---

# Phase 4: Media & Procaffe Scripts

## Context

- Parent: [Unified II Framework](./plan.md)
- Depends on: [Phase 3 - Document Skills](./phase-03-document-skills.md)

## Overview

Migrate media processing skills and integrate Procaffe automation scripts.

## Media Skills (5 skills)

| Skill | Purpose | Dependencies |
|-------|---------|--------------|
| ai-multimodal | Multi-modal AI tasks | Anthropic vision |
| media-processing | FFmpeg/ImageMagick | ffmpeg, imagemagick |
| ai-artist | Image generation | Gemini/DALL-E |
| image-enhancer | Image quality | PIL, OpenCV |
| video-downloader | yt-dlp downloads | yt-dlp |

## Procaffe Scripts (~20 convertible)

| Category | Scripts | Priority |
|----------|---------|----------|
| TikTok | auto-liker, auto-follower, firebase-sync | High |
| LinkedIn | auto-connector, content-poster, engager | High |
| Content | caption-generator, publer-upload | Medium |
| Firebase | admin, kb-sync | Medium |

## Key Insights

- Media skills need FFmpeg in container
- Procaffe scripts use Selenium/Playwright (browser)
- Some scripts have LaunchAgents (local only)
- Focus on API-based scripts for Modal

## Requirements

1. Convert 5 media SKILL.md → info.md
2. Wrap convertible Procaffe scripts as skills
3. Skip browser-automation scripts (local only)
4. Add FFmpeg to Modal image

## Architecture

### Procaffe → Modal Conversion

```
Procaffe Script                Modal Skill
┌────────────────────┐        ┌────────────────────┐
│ caption-generator  │        │ content-caption/   │
│ .py                │  ───►  │ ├── info.md        │
│                    │        │ └── scripts/       │
│ - API-based ✓      │        │     └── generate.py│
└────────────────────┘        └────────────────────┘

┌────────────────────┐
│ tiktok-auto-liker  │        ❌ Local only
│ .py                │        (needs browser)
│ - Selenium/Chrome  │
└────────────────────┘
```

### Convertible Procaffe Scripts

| Script | Deploy | Environment |
|--------|--------|-------------|
| caption-generator.py | Modal | API-based (Gemini) |
| publer-upload.py | Modal | API-based |
| kb-pinecone-sync.py | Modal | API-based |
| firebase-admin.py | Modal | API-based |
| fb-firebase-import.py | Modal | API-based |
| tiktok-firebase-sync.py | Modal | API-based |
| tiktok-auto-liker.py | Local | Browser (Selenium) |
| tiktok-auto-follower.py | Local | Browser (Selenium) |
| linkedin-auto-connector.py | Local | Browser (Selenium) |
| linkedin-auto-engager.py | Local | Browser (Selenium) |
| linkedin-content-poster.py | Local | Browser (Selenium) |

**Decision:** All scripts included. Browser-based run locally with LaunchAgent triggers.

## Related Code Files

| File | Purpose |
|------|---------|
| `~/.claude/skills/media-processing/SKILL.md` | Media skill |
| `/Procaffe/scripts/caption-generator.py` | Caption gen |
| `/Procaffe/scripts/publer-upload.py` | Publer API |
| `/Procaffe/scripts/config.py` | Shared config |

## Implementation Steps

- [ ] Convert 5 media skills
- [ ] Add FFmpeg/ImageMagick to Modal image
- [ ] Create content-caption skill from caption-generator.py
- [ ] Create social-publish skill from publer-upload.py
- [ ] Create kb-sync skill from kb-pinecone-sync.py
- [ ] Create firebase-admin skill
- [ ] Test media processing on Modal
- [ ] Test Procaffe-derived skills

## Todo List

- [ ] Convert ai-multimodal skill
- [ ] Convert media-processing skill
- [ ] Convert ai-artist skill
- [ ] Convert image-enhancer skill
- [ ] Convert video-downloader skill
- [ ] Create 6 Procaffe-derived skills
- [ ] Add media dependencies to image
- [ ] Integration tests

## Success Criteria

1. 5 media skills deployed
2. 6 Procaffe scripts converted to skills
3. FFmpeg/ImageMagick working on Modal
4. API-based automation functional

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| FFmpeg size | High | Use slim FFmpeg build |
| API rate limits | Medium | Add throttling |
| Procaffe deps | Medium | Document requirements |

## Next Steps

→ Phase 5: Claude Code integration
