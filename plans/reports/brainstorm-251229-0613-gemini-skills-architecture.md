# Brainstorm: Gemini API Skills Architecture

**Date:** 2024-12-29
**Status:** Agreed
**Scope:** 4 modular Gemini skills for Modal agents

---

## Problem Statement

Current Modal agents use Claude exclusively. Need to leverage Gemini API capabilities:
- Deep Research (agentic multi-step)
- Thinking Modes (adjustable reasoning depth)
- Grounding (real-time Google Search/Maps)
- Vision (multi-modal analysis)

**Goal:** Complement Claude with Gemini for specialized tasks.

---

## Requirements

| Requirement | Decision |
|-------------|----------|
| Deployment | Hybrid (Telegram remote + Claude Code local) |
| API Provider | Vertex AI |
| Async Model | Streaming + Firebase queue |
| Skill Count | 4 modular skills |
| Integration | Gemini complements Claude (not replaces) |

---

## Proposed Skills

### 1. `gemini-deep-research` (Priority: 1st)

**Purpose:** Multi-step agentic research with citations

| Field | Value |
|-------|-------|
| Deployment | `remote` |
| Trigger | "research X", "deep dive into Y", "analyze market for Z" |
| Duration | 5-30 min (async) |
| Output | Professional report + sources |

**Workflow:**
```
User Request
    │
    ▼
Task Decomposition (break into sub-queries)
    │
    ▼
┌───────────────────────────────────┐
│ Iterative Research Loop           │
│ ┌─────────────────────────────┐   │
│ │ 1. Execute sub-query        │   │
│ │ 2. Ground with Search       │   │──→ Stream progress to Telegram
│ │ 3. Validate findings        │   │
│ │ 4. Identify gaps → refine   │   │
│ └─────────────────────────────┘   │
└───────────────────────────────────┘
    │
    ▼
Synthesize Report + Citations
    │
    ▼
Save to Firebase + Notify User
```

**Key Features:**
- Task decomposition using `gemini-3-pro` thinking
- Dynamic `google_search` tool grounding
- Streaming progress updates via Telegram `edit_message`
- Firebase persistence for resume on failure
- Memory: stores successful research patterns

---

### 2. `gemini-grounding` (Priority: 2nd)

**Purpose:** Real-time factual answers with source attribution

| Field | Value |
|-------|-------|
| Deployment | `both` |
| Trigger | "what's current...", "find nearby...", "latest news on..." |
| Duration | 5-30 sec (sync) |
| Output | Grounded answer + inline citations |

**Features:**
- Google Search grounding for factual queries
- Google Maps grounding for location queries
- Dynamic retrieval (model auto-decides when to search)
- Cost-optimized (only searches when needed)
- Combine with JSON structured output for data extraction

**Example:**
```
User: "What's the current price of NVDA stock?"
↓
Gemini + Search Grounding
↓
"NVIDIA (NVDA) is trading at $XXX.XX as of [time]. [Source: Yahoo Finance]"
```

---

### 3. `gemini-thinking` (Priority: 3rd)

**Purpose:** Configurable reasoning depth for complex problems

| Field | Value |
|-------|-------|
| Deployment | `remote` |
| Trigger | "think deeply about...", "analyze step by step...", "reason through..." |
| Duration | 30s - 5 min |
| Levels | `minimal`, `low`, `medium`, `high`, `deep_think` |

**Features:**
- Auto-select thinking level based on query complexity
- Expose `thinking_level` parameter to users
- Thought signature preservation for multi-turn
- Deep Think mode for math/coding problems
- Cost optimization (lower = cheaper, faster)

**Thinking Levels:**
| Level | Use Case | Latency | Cost |
|-------|----------|---------|------|
| minimal | Simple tasks | <2s | $ |
| low | Instruction following | 2-5s | $$ |
| medium | General reasoning | 5-15s | $$$ |
| high | Complex analysis | 15-60s | $$$$ |
| deep_think | Math/code/proofs | 1-5min | $$$$$ |

---

### 4. `gemini-vision` (Priority: 4th)

**Purpose:** Advanced multi-modal analysis

| Field | Value |
|-------|-------|
| Deployment | `both` |
| Trigger | Image upload, video URL, document |
| Duration | 10-60 sec |
| Models | `gemini-3-flash` (fast), `gemini-3-pro` (quality) |

**Features:**
- Image understanding + Q&A
- Video frame-by-frame analysis
- PDF/document understanding
- Diagram/chart interpretation
- Bounding box extraction
- Compare multiple images

**Use Cases:**
- Screenshot analysis → code generation
- Invoice/receipt parsing
- Technical diagram explanation
- Video summarization

---

## Technical Architecture

### New Components

```
agents/src/
├── services/
│   ├── llm.py              # Existing Claude client
│   └── gemini.py           # NEW: Vertex AI Gemini client
│
├── core/
│   └── resilience.py       # Add gemini_circuit breaker
│
├── tools/
│   └── gemini_tools.py     # NEW: Research manager, streaming
│
└── skills/
    └── registry.py         # No changes (existing works)

agents/skills/
├── gemini-deep-research/
│   └── info.md
├── gemini-grounding/
│   └── info.md
├── gemini-thinking/
│   └── info.md
└── gemini-vision/
    └── info.md
```

### GeminiClient Design (gemini.py)

```python
class GeminiClient:
    """Vertex AI Gemini client with circuit breaker."""

    def __init__(self):
        self.project_id = os.environ["GCP_PROJECT_ID"]
        self.location = os.environ.get("GCP_LOCATION", "us-central1")
        self._client = None

    def chat(
        self,
        messages: List[Dict],
        model: str = "gemini-3-flash",
        thinking_level: str = "medium",
        tools: List[str] = None,  # ["google_search", "code_execution"]
        stream: bool = False,
    ) -> Union[str, Generator]:
        """Standard chat with optional thinking and tools."""
        pass

    async def deep_research(
        self,
        query: str,
        on_progress: Callable[[str], None],
        max_iterations: int = 10,
    ) -> ResearchReport:
        """Agentic research with streaming progress."""
        pass

    def grounded_query(
        self,
        query: str,
        grounding_sources: List[str] = ["google_search"],
    ) -> GroundedResponse:
        """Quick grounded answer with citations."""
        pass

    def analyze_image(
        self,
        image_base64: str,
        prompt: str,
    ) -> str:
        """Vision analysis."""
        pass
```

### Async Research Flow

```
┌───────────────────────────────────────────────────────────────┐
│                    Deep Research Flow                          │
├───────────────────────────────────────────────────────────────┤
│                                                                │
│  1. User: "Research AI agent frameworks 2025"                 │
│     │                                                          │
│     ▼                                                          │
│  2. Create Firebase task: {status: "running", progress: []}    │
│     │                                                          │
│     ▼                                                          │
│  3. Task Decomposition (Gemini thinking=high):                │
│     • "What are the top AI agent frameworks in 2025?"         │
│     • "Compare LangChain vs CrewAI vs AutoGPT"               │
│     • "What are production deployment patterns?"              │
│     │                                                          │
│     ▼                                                          │
│  4. For each sub-query:                                        │
│     a. Execute with google_search grounding                    │
│     b. Stream progress: "Researching frameworks..." → Telegram │
│     c. Validate: Are findings sufficient?                      │
│     d. If gaps → generate follow-up queries                    │
│     │                                                          │
│     ▼                                                          │
│  5. Synthesize findings into structured report                 │
│     │                                                          │
│     ▼                                                          │
│  6. Save report to Firebase, update task: {status: "complete"} │
│     │                                                          │
│     ▼                                                          │
│  7. Send final report to user via Telegram                     │
│                                                                │
└───────────────────────────────────────────────────────────────┘
```

---

## Secrets Required

```bash
# Add to Modal secrets
modal secret create gcp-credentials \
  GCP_PROJECT_ID=your-project \
  GCP_LOCATION=us-central1 \
  GOOGLE_APPLICATION_CREDENTIALS_JSON='...'
```

---

## Implementation Order

| Phase | Skill | Estimated Effort |
|-------|-------|------------------|
| 1 | `gemini-deep-research` | Core client + research manager + streaming |
| 2 | `gemini-grounding` | Add grounding modes to client |
| 3 | `gemini-thinking` | Add thinking level config |
| 4 | `gemini-vision` | Add vision methods |

---

## Trade-offs Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Single unified skill | Simple routing | Complex skill file | ❌ Rejected |
| 4 modular skills | Clean separation, easier testing | More files | ✅ Selected |
| Claude orchestrating Gemini | Leverage Claude's reasoning | Extra latency, cost | ❌ Rejected |
| Gemini standalone | Direct, efficient | Separate workflow | ✅ Selected |

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Vertex AI costs (Deep Research) | High bills | Per-user daily limits, auto-downgrade thinking level |
| Research timeout (30+ min) | User frustration | Firebase checkpoints + resume, interim updates |
| Gemini API instability | Skill failures | Circuit breaker + fallback to Claude |
| Streaming to Telegram rate limits | Blocked updates | Batch updates (every 10s instead of realtime) |
| Thought signatures across sessions | Broken context | Store in Firebase, restore on resume |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Research report quality | >80% user satisfaction |
| Grounding latency | <5s for factual queries |
| Skill adoption | >30% of queries use Gemini skills |
| Error rate | <5% failures |

---

## Next Steps

1. Create `/plan` for implementation
2. Start with `gemini.py` service + circuit breaker
3. Build `gemini-deep-research` skill
4. Add Telegram streaming integration
5. Deploy and test on Modal

---

## Unresolved Questions

- Q1: Should deep research have hard time limit (30 min) or let it run indefinitely?
- Q2: How to handle Gemini rate limits in Vertex AI (quotas)?
- Q3: Store research reports in Qdrant for semantic search later?
