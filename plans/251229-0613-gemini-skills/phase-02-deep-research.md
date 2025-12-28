# Phase 2: Deep Research Skill

**Status:** Pending
**Depends on:** Phase 1
**Files:** `skills/gemini-deep-research/info.md`, `src/tools/gemini_tools.py`

---

## Tasks

### 2.1 Create Skill Directory

```bash
mkdir -p agents/skills/gemini-deep-research
```

### 2.2 Create Skill Info

**File:** `agents/skills/gemini-deep-research/info.md` (NEW)

```markdown
---
name: gemini-deep-research
description: Multi-step agentic research with web grounding, citations, and professional reports. Use for complex topics requiring comprehensive analysis.
category: research
deployment: remote
triggers:
  - "research"
  - "deep dive"
  - "analyze market"
  - "investigate"
  - "comprehensive report on"
---

# Gemini Deep Research

Autonomous research agent powered by Gemini with Google Search grounding.

## Capabilities

- **Task Decomposition:** Breaks complex queries into searchable sub-queries
- **Web Grounding:** Uses Google Search for real-time, factual data
- **Iterative Refinement:** Identifies gaps and generates follow-up queries
- **Citation Extraction:** Provides sources for all claims
- **Report Synthesis:** Creates professional markdown reports

## Usage

```
/skill gemini-deep-research "Research AI agent frameworks in 2025"
```

## Parameters

| Param | Default | Description |
|-------|---------|-------------|
| max_iterations | 10 | Max sub-queries to research |
| model | gemini-2.0-flash-001 | Gemini model |

## Output

Returns structured research report with:
- Executive summary
- Key findings with analysis
- Recommendations
- Citations with URLs

## Async Behavior

Long-running researches (>30s) stream progress updates to Telegram.
```

---

### 2.3 Create Gemini Tools Module

**File:** `agents/src/tools/gemini_tools.py` (NEW)

See `plan.md` Phase 2.2 for full implementation.

**Functions:**
- `execute_deep_research(query, user_id, chat_id, progress_callback, max_iterations)`
- `execute_grounded_query(query, sources)`
- `execute_thinking(prompt, thinking_level)`
- `execute_vision(image_base64, prompt, media_type)`

---

### 2.4 Add Skill Routing

**File:** `agents/main.py`

Find `/api/skill` endpoint and add Gemini skill routing:

```python
# After line ~360, add:
GEMINI_SKILLS = {
    "gemini-deep-research",
    "gemini-grounding",
    "gemini-thinking",
    "gemini-vision",
}

# In the handler, add before existing skill logic:
if skill_name in GEMINI_SKILLS:
    from src.tools.gemini_tools import (
        execute_deep_research,
        execute_grounded_query,
        execute_thinking,
        execute_vision,
    )

    if skill_name == "gemini-deep-research":
        result = await execute_deep_research(
            query=task,
            user_id=user_id,
            max_iterations=context.get("max_iterations", 10)
        )
    elif skill_name == "gemini-grounding":
        result = await execute_grounded_query(query=task)
    elif skill_name == "gemini-thinking":
        result = await execute_thinking(
            prompt=task,
            thinking_level=context.get("thinking_level", "high")
        )
    elif skill_name == "gemini-vision":
        result = await execute_vision(
            image_base64=context.get("image_base64", ""),
            prompt=task
        )

    return {"ok": True, "result": result}
```

---

## Validation

```bash
# Test deep research locally
python3 -c "
import asyncio
from agents.src.tools.gemini_tools import execute_deep_research

async def test():
    result = await execute_deep_research(
        query='Current state of AI agents 2025',
        max_iterations=2
    )
    print(f'Success: {result[\"success\"]}')
    if result['success']:
        print(f'Summary: {result[\"summary\"][:200]}')
        print(f'Queries: {result[\"query_count\"]}')

asyncio.run(test())
"

# Test via API after deploy
curl -X POST https://your-modal-url/api/skill \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "gemini-deep-research",
    "task": "Research serverless AI frameworks",
    "context": {"max_iterations": 3}
  }'
```

---

## Completion Criteria

- [ ] `gemini-deep-research/info.md` created
- [ ] `gemini_tools.py` with all skill handlers
- [ ] Skill routing added to main.py
- [ ] Deep research returns report with citations
- [ ] Progress callback works for streaming
