# Phase 3: Remaining Skills

**Status:** Pending
**Depends on:** Phase 2
**Files:** `skills/gemini-grounding/`, `skills/gemini-thinking/`, `skills/gemini-vision/`

---

## Tasks

### 3.1 Create Skill Directories

```bash
mkdir -p agents/skills/gemini-grounding
mkdir -p agents/skills/gemini-thinking
mkdir -p agents/skills/gemini-vision
```

---

### 3.2 Grounding Skill

**File:** `agents/skills/gemini-grounding/info.md` (NEW)

```markdown
---
name: gemini-grounding
description: Real-time factual queries with Google Search/Maps grounding. Returns cited answers for current events, prices, locations.
category: research
deployment: both
triggers:
  - "what's the current"
  - "latest news on"
  - "find nearby"
  - "price of"
  - "today's"
---

# Gemini Grounding

Quick factual answers with real-time web data and citations.

## Features

- Google Search grounding for facts
- Google Maps grounding for locations
- Dynamic retrieval (only searches when needed)
- Inline citations with URLs

## Usage

```
/skill gemini-grounding "What's the current price of Bitcoin?"
```

## Response Time

Typically 2-5 seconds for factual queries.

## Examples

- "What's the current price of NVDA stock?"
- "Latest news on AI regulations"
- "Find cafes near Times Square"
- "Today's weather in Tokyo"
```

---

### 3.3 Thinking Skill

**File:** `agents/skills/gemini-thinking/info.md` (NEW)

```markdown
---
name: gemini-thinking
description: Configurable reasoning depth for complex analysis. Adjust thinking level from minimal (fast) to high (thorough).
category: reasoning
deployment: remote
triggers:
  - "think deeply about"
  - "analyze step by step"
  - "reason through"
  - "solve this problem"
---

# Gemini Thinking

Adjustable reasoning depth for different complexity levels.

## Thinking Levels

| Level | Use Case | Speed | Cost |
|-------|----------|-------|------|
| minimal | Simple facts | <2s | $ |
| low | Basic reasoning | 2-5s | $$ |
| medium | General analysis | 5-15s | $$$ |
| high | Complex problems | 15-60s | $$$$ |

## Usage

```
/skill gemini-thinking "Analyze trade-offs of microservices vs monolith"
```

With explicit level:
```json
{
  "skill": "gemini-thinking",
  "task": "Prove the Pythagorean theorem",
  "context": {"thinking_level": "high"}
}
```

## Best For

- Mathematical proofs
- Code debugging
- Architecture decisions
- Complex problem solving
- Multi-step reasoning
```

---

### 3.4 Vision Skill

**File:** `agents/skills/gemini-vision/info.md` (NEW)

```markdown
---
name: gemini-vision
description: Multi-modal image and document analysis. Screenshots, diagrams, PDFs, video frames.
category: vision
deployment: both
triggers:
  - "[image attached]"
  - "analyze this image"
  - "what's in this"
  - "read this document"
---

# Gemini Vision

Advanced image and document understanding.

## Capabilities

- Image understanding + Q&A
- Screenshot → code generation
- Diagram/chart interpretation
- Document/PDF parsing
- Receipt/invoice extraction
- Handwriting recognition

## Usage

Via Telegram: Send image with caption like "Analyze this"

Via API:
```json
{
  "skill": "gemini-vision",
  "task": "Extract the text from this screenshot",
  "context": {
    "image_base64": "...",
    "media_type": "image/png"
  }
}
```

## Supported Formats

- Images: JPEG, PNG, GIF, WebP
- Documents: PDF (first pages)
- Media types: image/jpeg, image/png, application/pdf

## Examples

- "What code is in this screenshot?"
- "Explain this architecture diagram"
- "Extract text from this receipt"
- "What's wrong with this UI design?"
```

---

## Validation

```bash
# Test grounding
curl -X POST https://your-modal-url/api/skill \
  -H "Content-Type: application/json" \
  -d '{"skill": "gemini-grounding", "task": "Current Bitcoin price"}'

# Test thinking
curl -X POST https://your-modal-url/api/skill \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "gemini-thinking",
    "task": "Explain P vs NP problem",
    "context": {"thinking_level": "high"}
  }'

# Test vision (with base64 image)
curl -X POST https://your-modal-url/api/skill \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "gemini-vision",
    "task": "What text is in this image?",
    "context": {"image_base64": "/9j/4AAQ..."}
  }'
```

---

## Completion Criteria

- [ ] All 3 skill info.md files created
- [ ] Grounding returns answers in <5s
- [ ] Thinking supports all 4 levels
- [ ] Vision processes base64 images
- [ ] All skills visible in `/api/skills`
