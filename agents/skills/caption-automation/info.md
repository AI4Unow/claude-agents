---
name: caption-automation
description: Generate AI-powered TikTok captions using Vertex AI Gemini for video content.
category: automation
deployment: local
---

# Caption Automation Skill

Generate AI-powered TikTok captions using Vertex AI Gemini for video content.

## When to Use

Activate when user mentions:
- "generate captions"
- "create TikTok captions"
- "add captions to videos"
- "generate hashtags"
- "create video hooks"
- "batch caption generation"

## Core Capabilities

1. **Single Video Caption Generation**: Analyze video, generate bilingual (Vietnamese/English) captions with optimal hashtags
2. **Batch Processing**: Process multiple videos (processed or AI-generated) in one run
3. **Smart Hashtag Selection**: Uses competitor analysis data to select proven hashtags
4. **Context-Aware**: For AI-generated videos, uses generation prompt as context
5. **Hook Optimization**: Generates scroll-stopping hooks following TikTok 2025 best practices

## Script Location

**Main Script**: `/Users/nad/Library/CloudStorage/OneDrive-Personal/Procaffe/scripts/caption-generator.py`
**Prompt Library**: `/Users/nad/Library/CloudStorage/OneDrive-Personal/Procaffe/scripts/prompts.py`

## Prerequisites

```bash
# Check Gemini client installed
/opt/homebrew/bin/python3 -c "from google import genai"

# Verify GCP auth
gcloud auth application-default login

# Verify environment
export GCP_PROJECT="procaffe-d3230"
export GCP_LOCATION="us-central1"
```

## Usage Examples

### Single Video Caption

```bash
/opt/homebrew/bin/python3 /Users/nad/Library/CloudStorage/OneDrive-Personal/Procaffe/scripts/caption-generator.py \
  /Users/nad/Library/CloudStorage/OneDrive-Personal/Procaffe/exports/processed/20241220-143522/video-tiktok.mp4
```

### Batch Process All Videos

```bash
# All processed videos
/opt/homebrew/bin/python3 /Users/nad/Library/CloudStorage/OneDrive-Personal/Procaffe/scripts/caption-generator.py --batch

# AI-generated videos only
/opt/homebrew/bin/python3 /Users/nad/Library/CloudStorage/OneDrive-Personal/Procaffe/scripts/caption-generator.py --ai-videos

# Both sources
/opt/homebrew/bin/python3 /Users/nad/Library/CloudStorage/OneDrive-Personal/Procaffe/scripts/caption-generator.py --all-sources
```

### Batch with Limit

```bash
# Process first 5 videos
/opt/homebrew/bin/python3 /Users/nad/Library/CloudStorage/OneDrive-Personal/Procaffe/scripts/caption-generator.py --batch --limit 5
```

### Force Regenerate

```bash
# Overwrite existing captions
/opt/homebrew/bin/python3 /Users/nad/Library/CloudStorage/OneDrive-Personal/Procaffe/scripts/caption-generator.py --batch --force
```

## CLI Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `video` | positional | Path to single video file |
| `--batch` | flag | Process all processed videos in exports/processed/ |
| `--ai-videos` | flag | Process AI-generated videos only |
| `--all-sources` | flag | Process both processed and AI-generated videos |
| `--limit N` | integer | Limit number of videos to process |
| `--force` | flag | Overwrite existing caption.txt files |

## Output Format

Caption saved to `caption.txt` in video directory:

```
Bí mật pha cà phê hoàn hảo với máy chuyên nghiệp ☕

The secret to perfect coffee with professional machines

#procaffe #xuhuongtiktok #mayphacaphe #caphe #coffee
```

Structure:
- Line 1: Vietnamese caption (hook + message, max 100 chars)
- Line 2: Empty
- Line 3: English caption (max 80 chars)
- Line 4: Empty
- Line 5: Hashtags (5-6 tags from optimal list)

## How It Works

1. **Video Analysis**: Extracts keyframes and uploads video to Gemini
2. **Context Loading**: For AI videos, reads metadata.json for generation prompt
3. **Hashtag Selection**: Loads competitor data from `data/competitor-tiktok-data.json`
4. **Caption Generation**: Uses Vertex AI Gemini 2.5 Flash with optimized prompt
5. **Fallback Strategy**: If video upload fails, uses keyframe images
6. **Save Output**: Writes caption.txt to video directory

## Hashtag Strategy

**Data Source**: `data/competitor-tiktok-data.json`
**Selection Logic**:
- Trending tags: High usage across competitors (fyp, xuhuongtiktok)
- Niche tags: High view score, coffee-related (mayphacaphe, caphe)
- Brand tag: Always includes #procaffe

**Output**: 5-6 hashtags total (1-2 trending + 3-4 niche + brand)

## Error Handling

- Missing dependencies → Install instructions
- GCP auth failure → Prompt for `gcloud auth`
- Video processing error → Fallback to keyframes
- Empty response → Report failure, skip to next video

## Performance Notes

- **Model**: gemini-2.5-flash (fast, cost-effective)
- **Video size**: Handles up to 1GB videos
- **Batch speed**: ~10-15 seconds per video
- **Rate limits**: Vertex AI default quotas apply

## Related Files

- `scripts/config.py` - Project paths and configuration
- `scripts/utils.py` - Video discovery utilities
- `data/competitor-tiktok-data.json` - Hashtag analysis data

## Reference Documentation

See `references/` for:
- `gemini-config.md` - Vertex AI configuration details
- `batch-processing.md` - Batch workflow and optimization
