# Phase 02: Categorize All Skills

## Objective

Audit all 25+ skills and add appropriate `deployment` and `requires` metadata.

## Categorization Rules

| Criterion | Deployment |
|-----------|------------|
| Requires CLI tools (ffmpeg, imagemagick, yt-dlp) | local |
| Needs local file system access | local |
| Requires consumer IP (geo-restricted) | local |
| Needs browser automation | local |
| LLM-only (Claude/GPT calls) | modal |
| External API calls (GitHub, Telegram) | modal |
| Web search only | modal |

## Skills Audit

### Local Skills (8)

| Skill | Deployment | Requires |
|-------|------------|----------|
| `video-downloader` | local | `[yt-dlp, local-files]` |
| `media-processing` | local | `[ffmpeg, imagemagick, local-files]` |
| `pdf` | local | `[local-files]` |
| `docx` | local | `[local-files]` |
| `pptx` | local | `[local-files]` |
| `xlsx` | local | `[local-files]` |
| `image-enhancer` | local | `[imagemagick, rmbg, local-files]` |
| `ui-styling` | local | `[npm, local-files]` |

### Modal Skills (16)

| Skill | Deployment | Requires |
|-------|------------|----------|
| `planning` | modal | `[]` |
| `research` | modal | `[]` |
| `backend-development` | modal | `[]` |
| `frontend-development` | modal | `[]` |
| `mobile-development` | modal | `[]` |
| `code-review` | modal | `[]` |
| `debugging` | modal | `[]` |
| `ai-artist` | modal | `[]` |
| `ai-multimodal` | modal | `[]` |
| `canvas-design` | modal | `[]` |
| `ui-ux-pro-max` | modal | `[]` |
| `content` | modal | `[]` |
| `data` | modal | `[]` |
| `github` | modal | `[]` |
| `telegram-chat` | modal | `[]` |
| `shopify` | modal | `[]` |

## Implementation

For each skill, update `info.md` frontmatter:

```yaml
---
name: video-downloader
description: Downloads videos from YouTube...
deployment: local
requires:
  - yt-dlp
  - local-files
source: SKILL.md
converted: 2025-12-27
---
```

## Validation

- [ ] All 25+ skills have `deployment` field
- [ ] Local skills have non-empty `requires` list
- [ ] Modal skills have empty or no `requires` list
- [ ] YAML frontmatter is valid (test with yaml.safe_load)

## Effort

2 hours (manual audit and update)
