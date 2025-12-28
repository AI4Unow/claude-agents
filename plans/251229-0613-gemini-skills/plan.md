# Implementation Plan: Gemini API Skills

**Date:** 2024-12-29
**Status:** Ready for Implementation
**Brainstorm:** `plans/reports/brainstorm-251229-0613-gemini-skills-architecture.md`

---

## Overview

Implement 4 modular Gemini skills using Vertex AI SDK to complement Claude-based agents:
1. `gemini-deep-research` - Multi-step agentic research (Priority 1)
2. `gemini-grounding` - Real-time factual queries (Priority 2)
3. `gemini-thinking` - Configurable reasoning depth (Priority 3)
4. `gemini-vision` - Multi-modal analysis (Priority 4)

---

## Prerequisites

```bash
# GCP Secrets for Modal
modal secret create gcp-credentials \
  GCP_PROJECT_ID=your-project \
  GCP_LOCATION=us-central1 \
  GOOGLE_APPLICATION_CREDENTIALS_JSON='...'
```

---

## Phase 1: Core Infrastructure

**Files:** `agents/src/services/gemini.py`, `agents/src/core/resilience.py`

### 1.1 Add Gemini Circuit Breaker

**File:** `agents/src/core/resilience.py`

Add after line 224:
```python
gemini_circuit = CircuitBreaker("gemini_api", threshold=3, cooldown=60)
```

Update `get_circuit_stats()` and `reset_all_circuits()` to include gemini_circuit.

### 1.2 Create GeminiClient

**File:** `agents/src/services/gemini.py` (NEW)

```python
"""Gemini client using google-genai SDK with Vertex AI."""
import os
import asyncio
from typing import List, Dict, Optional, Generator, Callable, Any
from dataclasses import dataclass

from src.utils.logging import get_logger
from src.core.resilience import gemini_circuit, CircuitOpenError, CircuitState

logger = get_logger()


@dataclass
class GroundedResponse:
    """Response with grounding citations."""
    text: str
    citations: List[Dict[str, str]]  # [{title, url, snippet}]
    grounding_metadata: Optional[Dict] = None


@dataclass
class ResearchReport:
    """Deep research output."""
    title: str
    summary: str
    sections: List[Dict[str, str]]  # [{heading, content}]
    citations: List[Dict[str, str]]
    thinking_trace: List[str]  # reasoning steps
    query_count: int
    duration_seconds: float


class GeminiClient:
    """Vertex AI Gemini client with circuit breaker."""

    def __init__(self):
        self.project_id = os.environ.get("GCP_PROJECT_ID", "")
        self.location = os.environ.get("GCP_LOCATION", "us-central1")
        self._client = None

    @property
    def client(self):
        """Lazy-load genai client."""
        if self._client is None:
            from google import genai
            self._client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=self.location
            )
        return self._client

    async def chat(
        self,
        messages: List[Dict],
        model: str = "gemini-2.0-flash-001",
        thinking_level: str = "medium",
        tools: List[str] = None,
        max_tokens: int = 8192,
        stream: bool = False,
    ):
        """Standard chat with optional thinking and tools.

        Args:
            messages: [{"role": "user", "content": "..."}]
            model: gemini-2.0-flash-001, gemini-3-pro-preview
            thinking_level: minimal, low, medium, high
            tools: ["google_search", "code_execution"]
            stream: Return generator if True

        Returns:
            Text string or async generator
        """
        if gemini_circuit.state == CircuitState.OPEN:
            raise CircuitOpenError("gemini_api", gemini_circuit._cooldown_remaining())

        from google.genai import types

        # Build tools
        tool_configs = []
        if tools and "google_search" in tools:
            tool_configs.append(types.Tool(google_search=types.GoogleSearch()))
        if tools and "code_execution" in tools:
            tool_configs.append(types.Tool(code_execution=types.ToolCodeExecution()))

        # Build thinking config
        thinking_config = types.ThinkingConfig(
            include_thoughts=False,
            thinking_level=thinking_level
        ) if thinking_level else None

        config = types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            tools=tool_configs if tool_configs else None,
            thinking_config=thinking_config,
        )

        # Convert messages to content
        contents = self._messages_to_contents(messages)

        try:
            if stream:
                return self._stream_response(model, contents, config)

            response = await self.client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
            gemini_circuit._record_success()
            return response.text

        except Exception as e:
            gemini_circuit._record_failure(e)
            logger.error("gemini_chat_error", error=str(e)[:100])
            raise

    async def _stream_response(self, model, contents, config):
        """Async generator for streaming responses."""
        async for chunk in self.client.aio.models.generate_content_stream(
            model=model,
            contents=contents,
            config=config,
        ):
            if chunk.text:
                yield chunk.text
        gemini_circuit._record_success()

    def _messages_to_contents(self, messages: List[Dict]) -> List:
        """Convert chat messages to Gemini contents format."""
        from google.genai import types
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(types.Content(
                role=role,
                parts=[types.Part(text=msg["content"])]
            ))
        return contents

    async def grounded_query(
        self,
        query: str,
        grounding_sources: List[str] = None,
        model: str = "gemini-2.0-flash-001",
    ) -> GroundedResponse:
        """Quick grounded answer with citations.

        Args:
            query: User query
            grounding_sources: ["google_search", "google_maps"]
            model: Model to use

        Returns:
            GroundedResponse with text and citations
        """
        if gemini_circuit.state == CircuitState.OPEN:
            raise CircuitOpenError("gemini_api", gemini_circuit._cooldown_remaining())

        from google.genai import types

        sources = grounding_sources or ["google_search"]
        tools = []
        if "google_search" in sources:
            tools.append(types.Tool(google_search=types.GoogleSearch()))

        config = types.GenerateContentConfig(
            tools=tools,
        )

        try:
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=query,
                config=config,
            )
            gemini_circuit._record_success()

            # Extract citations from grounding metadata
            citations = []
            if hasattr(response, 'grounding_metadata') and response.grounding_metadata:
                for source in response.grounding_metadata.get('groundingSupports', []):
                    citations.append({
                        "title": source.get("segment", {}).get("text", ""),
                        "url": source.get("segment", {}).get("uri", ""),
                        "snippet": source.get("text", "")
                    })

            return GroundedResponse(
                text=response.text,
                citations=citations,
                grounding_metadata=getattr(response, 'grounding_metadata', None)
            )

        except Exception as e:
            gemini_circuit._record_failure(e)
            logger.error("gemini_grounded_error", error=str(e)[:100])
            raise

    async def deep_research(
        self,
        query: str,
        on_progress: Callable[[str], None] = None,
        max_iterations: int = 10,
        model: str = "gemini-2.0-flash-001",
    ) -> ResearchReport:
        """Agentic multi-step research with streaming progress.

        Args:
            query: Research topic
            on_progress: Callback for progress updates
            max_iterations: Max research iterations
            model: Model to use

        Returns:
            ResearchReport with sections and citations
        """
        import time
        start_time = time.time()

        if gemini_circuit.state == CircuitState.OPEN:
            raise CircuitOpenError("gemini_api", gemini_circuit._cooldown_remaining())

        from google.genai import types

        thinking_trace = []
        all_citations = []
        query_count = 0

        # Step 1: Decompose query into sub-queries
        if on_progress:
            on_progress("Analyzing research topic...")

        decompose_prompt = f"""You are a research planner. Break down this research topic into 3-5 specific sub-queries that can be searched:

Topic: {query}

Output as JSON array of strings, each a searchable query. Only output the JSON array, no explanation."""

        decompose_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="high"),
        )

        try:
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=decompose_prompt,
                config=decompose_config,
            )
            gemini_circuit._record_success()

            import json
            sub_queries = json.loads(response.text.strip())
            thinking_trace.append(f"Decomposed into {len(sub_queries)} sub-queries")

            if on_progress:
                on_progress(f"Planning {len(sub_queries)} research steps...")

        except Exception as e:
            gemini_circuit._record_failure(e)
            logger.error("decompose_error", error=str(e)[:100])
            sub_queries = [query]  # Fallback to single query

        # Step 2: Research each sub-query with grounding
        findings = []
        search_tool = types.Tool(google_search=types.GoogleSearch())

        for i, sq in enumerate(sub_queries[:max_iterations]):
            if on_progress:
                on_progress(f"Researching ({i+1}/{len(sub_queries)}): {sq[:50]}...")

            try:
                response = await self.client.aio.models.generate_content(
                    model=model,
                    contents=f"Research and provide detailed findings on: {sq}",
                    config=types.GenerateContentConfig(tools=[search_tool]),
                )
                gemini_circuit._record_success()
                query_count += 1

                findings.append({
                    "query": sq,
                    "content": response.text
                })

                # Extract citations
                if hasattr(response, 'grounding_metadata') and response.grounding_metadata:
                    for source in response.grounding_metadata.get('groundingSupports', []):
                        all_citations.append({
                            "title": source.get("segment", {}).get("text", ""),
                            "url": source.get("segment", {}).get("uri", ""),
                        })

                thinking_trace.append(f"Completed: {sq[:40]}")

            except Exception as e:
                logger.warning("subquery_error", query=sq[:40], error=str(e)[:50])
                thinking_trace.append(f"Failed: {sq[:40]} - {str(e)[:30]}")

        # Step 3: Synthesize findings into report
        if on_progress:
            on_progress("Synthesizing research report...")

        findings_text = "\n\n".join([
            f"### {f['query']}\n{f['content']}" for f in findings
        ])

        synthesize_prompt = f"""You are a research analyst. Synthesize these findings into a professional research report.

RESEARCH TOPIC: {query}

FINDINGS:
{findings_text}

Create a structured report with:
1. Executive Summary (2-3 paragraphs)
2. Key Findings (3-5 main points)
3. Detailed Analysis (expand on each finding)
4. Recommendations
5. Conclusion

Output as professional markdown."""

        try:
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=synthesize_prompt,
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_level="high"),
                ),
            )
            gemini_circuit._record_success()

            report_text = response.text

        except Exception as e:
            gemini_circuit._record_failure(e)
            logger.error("synthesize_error", error=str(e)[:100])
            report_text = findings_text  # Fallback to raw findings

        duration = time.time() - start_time

        if on_progress:
            on_progress(f"Research complete in {duration:.0f}s")

        return ResearchReport(
            title=query,
            summary=report_text[:500] + "...",
            sections=[{"heading": "Full Report", "content": report_text}],
            citations=all_citations,
            thinking_trace=thinking_trace,
            query_count=query_count,
            duration_seconds=duration
        )

    async def analyze_image(
        self,
        image_base64: str,
        prompt: str,
        media_type: str = "image/jpeg",
        model: str = "gemini-2.0-flash-001",
    ) -> str:
        """Vision analysis of image.

        Args:
            image_base64: Base64 encoded image
            prompt: Analysis prompt
            media_type: MIME type
            model: Model to use

        Returns:
            Analysis text
        """
        if gemini_circuit.state == CircuitState.OPEN:
            raise CircuitOpenError("gemini_api", gemini_circuit._cooldown_remaining())

        from google.genai import types
        import base64

        try:
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(
                        data=base64.b64decode(image_base64),
                        mime_type=media_type
                    ),
                    prompt
                ],
            )
            gemini_circuit._record_success()
            return response.text

        except Exception as e:
            gemini_circuit._record_failure(e)
            logger.error("gemini_vision_error", error=str(e)[:100])
            raise


# Singleton
_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """Get or create GeminiClient singleton."""
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client
```

---

## Phase 2: Deep Research Skill

**Files:** `agents/skills/gemini-deep-research/info.md`, update `main.py`

### 2.1 Create Skill Info

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
| thinking_level | high | Reasoning depth |

## Output

Returns structured research report with:
- Executive summary
- Key findings with analysis
- Recommendations
- Citations with URLs

## Async Behavior

Long-running researches (>30s) are queued to Firebase and user is notified when complete.
```

### 2.2 Add Research Skill Handler

**File:** `agents/src/tools/gemini_tools.py` (NEW)

```python
"""Gemini skill tools for Modal agents."""
import asyncio
from typing import Dict, Optional, Callable

from src.services.gemini import get_gemini_client, ResearchReport
from src.services.firebase import (
    create_local_task,
    complete_local_task,
    update_task_progress
)
from src.utils.logging import get_logger

logger = get_logger()


async def execute_deep_research(
    query: str,
    user_id: int = 0,
    chat_id: int = 0,
    progress_callback: Callable[[str], None] = None,
    max_iterations: int = 10,
) -> Dict:
    """Execute deep research skill.

    Args:
        query: Research topic
        user_id: Telegram user ID for notifications
        chat_id: Telegram chat ID for progress updates
        progress_callback: Optional callback for progress
        max_iterations: Max research iterations

    Returns:
        Dict with report and metadata
    """
    client = get_gemini_client()

    try:
        report = await client.deep_research(
            query=query,
            on_progress=progress_callback,
            max_iterations=max_iterations,
        )

        # Format citations
        citations_md = "\n".join([
            f"- [{c['title'][:50]}]({c['url']})"
            for c in report.citations[:10]
        ])

        return {
            "success": True,
            "report": report.sections[0]["content"],
            "summary": report.summary,
            "citations": citations_md,
            "query_count": report.query_count,
            "duration_seconds": report.duration_seconds,
            "thinking_trace": report.thinking_trace,
        }

    except Exception as e:
        logger.error("deep_research_error", error=str(e)[:100])
        return {
            "success": False,
            "error": str(e),
        }


async def execute_grounded_query(
    query: str,
    sources: list = None,
) -> Dict:
    """Execute grounded query skill.

    Args:
        query: Factual query
        sources: ["google_search", "google_maps"]

    Returns:
        Dict with answer and citations
    """
    client = get_gemini_client()

    try:
        response = await client.grounded_query(
            query=query,
            grounding_sources=sources or ["google_search"],
        )

        citations_md = "\n".join([
            f"- [{c['title'][:50]}]({c['url']})"
            for c in response.citations[:5]
        ])

        return {
            "success": True,
            "answer": response.text,
            "citations": citations_md,
        }

    except Exception as e:
        logger.error("grounded_query_error", error=str(e)[:100])
        return {
            "success": False,
            "error": str(e),
        }


async def execute_thinking(
    prompt: str,
    thinking_level: str = "high",
) -> Dict:
    """Execute thinking skill with configurable depth.

    Args:
        prompt: Problem to analyze
        thinking_level: minimal, low, medium, high

    Returns:
        Dict with analysis
    """
    client = get_gemini_client()

    try:
        result = await client.chat(
            messages=[{"role": "user", "content": prompt}],
            thinking_level=thinking_level,
            model="gemini-2.0-flash-001",
        )

        return {
            "success": True,
            "analysis": result,
            "thinking_level": thinking_level,
        }

    except Exception as e:
        logger.error("thinking_error", error=str(e)[:100])
        return {
            "success": False,
            "error": str(e),
        }


async def execute_vision(
    image_base64: str,
    prompt: str,
    media_type: str = "image/jpeg",
) -> Dict:
    """Execute vision analysis skill.

    Args:
        image_base64: Base64 encoded image
        prompt: Analysis prompt
        media_type: Image MIME type

    Returns:
        Dict with analysis
    """
    client = get_gemini_client()

    try:
        result = await client.analyze_image(
            image_base64=image_base64,
            prompt=prompt,
            media_type=media_type,
        )

        return {
            "success": True,
            "analysis": result,
        }

    except Exception as e:
        logger.error("vision_error", error=str(e)[:100])
        return {
            "success": False,
            "error": str(e),
        }
```

---

## Phase 3: Remaining Skills

### 3.1 Grounding Skill

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

## Usage

```
/skill gemini-grounding "What's the current price of Bitcoin?"
```

## Features

- Google Search grounding for facts
- Google Maps grounding for locations
- Dynamic retrieval (only searches when needed)
- Inline citations with URLs
```

### 3.2 Thinking Skill

**File:** `agents/skills/gemini-thinking/info.md` (NEW)

```markdown
---
name: gemini-thinking
description: Configurable reasoning depth for complex analysis. Adjust thinking level from minimal (fast) to deep (thorough).
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

| Level | Use Case | Speed |
|-------|----------|-------|
| minimal | Simple facts | <2s |
| low | Basic reasoning | 2-5s |
| medium | General analysis | 5-15s |
| high | Complex problems | 15-60s |

## Usage

```
/skill gemini-thinking "Analyze the trade-offs of microservices vs monolith" --level high
```
```

### 3.3 Vision Skill

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
- Video frame analysis

## Usage

Send an image with prompt, or:
```
/skill gemini-vision [image_url] "Extract the text from this screenshot"
```
```

---

## Phase 4: Integration

### 4.1 Update main.py Skill Router

**File:** `agents/main.py`

Add to skill routing (around line 360):

```python
# Gemini skill routing
GEMINI_SKILLS = {
    "gemini-deep-research": "execute_deep_research",
    "gemini-grounding": "execute_grounded_query",
    "gemini-thinking": "execute_thinking",
    "gemini-vision": "execute_vision",
}

# In skill_api handler, add:
if skill_name in GEMINI_SKILLS:
    from src.tools.gemini_tools import (
        execute_deep_research,
        execute_grounded_query,
        execute_thinking,
        execute_vision,
    )

    handlers = {
        "gemini-deep-research": lambda: execute_deep_research(task, user_id),
        "gemini-grounding": lambda: execute_grounded_query(task),
        "gemini-thinking": lambda: execute_thinking(task),
        "gemini-vision": lambda: execute_vision(
            context.get("image_base64", ""),
            task
        ),
    }

    result = await handlers[skill_name]()
    return {"ok": True, "result": result}
```

### 4.2 Add Telegram Streaming Support

**File:** `agents/src/services/telegram.py`

Add function:

```python
async def update_progress_message(
    chat_id: int,
    message_id: int,
    text: str,
    bot_token: str = None,
) -> bool:
    """Update existing message with progress (for streaming).

    Uses edit_message_text to update in-place.
    Rate limited to 1 update per 3 seconds.
    """
    import httpx
    import os

    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/editMessageText"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "HTML",
            })
            return response.status_code == 200
    except Exception:
        return False
```

### 4.3 Update Modal Secrets

**File:** `agents/main.py`

Add to app definition:

```python
app = modal.App(
    "claude-agents",
    secrets=[
        modal.Secret.from_name("anthropic-credentials"),
        modal.Secret.from_name("telegram-credentials"),
        modal.Secret.from_name("firebase-credentials"),
        modal.Secret.from_name("qdrant-credentials"),
        modal.Secret.from_name("exa-credentials"),
        modal.Secret.from_name("tavily-credentials"),
        modal.Secret.from_name("admin-credentials"),
        modal.Secret.from_name("gcp-credentials"),  # NEW
    ],
)
```

---

## Phase 5: Testing & Deployment

### 5.1 Test Commands

```bash
# Test Gemini client
modal run agents/main.py::test_gemini

# Test deep research
modal run agents/main.py::test_deep_research

# Test grounding
modal run agents/main.py::test_grounding
```

### 5.2 Add Test Functions

**File:** `agents/main.py`

```python
@app.local_entrypoint()
def test_gemini():
    """Test Gemini client initialization."""
    import asyncio
    from src.services.gemini import get_gemini_client

    async def run():
        client = get_gemini_client()
        result = await client.chat(
            messages=[{"role": "user", "content": "Hello, test message"}],
            thinking_level="minimal"
        )
        print(f"Response: {result[:100]}")

    asyncio.run(run())


@app.local_entrypoint()
def test_deep_research():
    """Test deep research skill."""
    import asyncio
    from src.tools.gemini_tools import execute_deep_research

    async def run():
        result = await execute_deep_research(
            query="Current state of AI agents in 2025",
            max_iterations=3
        )
        print(f"Success: {result['success']}")
        if result['success']:
            print(f"Report preview: {result['summary'][:200]}")
            print(f"Query count: {result['query_count']}")

    asyncio.run(run())
```

### 5.3 Deploy

```bash
# Deploy to Modal
modal deploy agents/main.py

# Verify skills visible
curl https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run/api/skills
```

---

## File Checklist

| Phase | File | Action |
|-------|------|--------|
| 1 | `src/core/resilience.py` | Add gemini_circuit |
| 1 | `src/services/gemini.py` | NEW - GeminiClient |
| 2 | `skills/gemini-deep-research/info.md` | NEW - Skill info |
| 2 | `src/tools/gemini_tools.py` | NEW - Skill handlers |
| 3 | `skills/gemini-grounding/info.md` | NEW |
| 3 | `skills/gemini-thinking/info.md` | NEW |
| 3 | `skills/gemini-vision/info.md` | NEW |
| 4 | `main.py` | Add routing + secrets |
| 4 | `src/services/telegram.py` | Add progress updates |
| 5 | `main.py` | Add test functions |

---

## Dependencies

Add to Modal image:

```python
image = modal.Image.debian_slim().pip_install(
    "anthropic",
    "google-genai",  # NEW
    "httpx",
    "structlog",
    # ... existing deps
)
```

---

## Unresolved Questions

1. **Q1:** Hard time limit for research? → Suggest 30 min max with Firebase checkpointing
2. **Q2:** Vertex AI quotas? → Use dynamic retrieval + rate limiting
3. **Q3:** Store in Qdrant? → Phase 2 feature, not MVP

---

## Success Criteria

- [ ] `gemini-deep-research` returns report with citations
- [ ] `gemini-grounding` answers factual queries in <5s
- [ ] `gemini-thinking` supports all 4 thinking levels
- [ ] `gemini-vision` analyzes uploaded images
- [ ] Circuit breaker protects against API failures
- [ ] Telegram progress updates work for long research
