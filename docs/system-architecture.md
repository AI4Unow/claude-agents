# System Architecture

## High-Level Overview

```
LOCAL DEVELOPMENT                         MODAL CLOUD
─────────────────                         ───────────

┌─────────────────┐                      ┌─────────────────────────────────────┐
│ Your Computer   │                      │            MODAL SERVER             │
│                 │                      │                                     │
│ agents/         │    modal deploy      │  ┌─────────────────────────────────┐│
│ ├── main.py     │ ──────────────────► │  │  FastAPI Web App                ││
│ ├── api/        │                      │  │  ├── /webhook/telegram          ││
│ ├── commands/   │                      │  │  ├── /webhook/whatsapp          ││
│ ├── src/        │                      │  │  ├── /webhook/github            ││
│ │   ├── agents/ │                      │  │  ├── /api/skill                 ││
│ │   ├── services│                      │  │  ├── /api/skills                ││
│ │   ├── tools/  │                      │  │  └── /api/reports               ││
│ │   └── core/   │                      │  │                                 ││
│ └── skills/     │                      │  │  Cron Jobs:                     ││
│                 │                      │  │  ├── github_monitor (hourly)    ││
│                 │                      │  │  ├── daily_summary (1 AM UTC)   ││
│                 │                      │  │  └── cleanup_content (3 AM UTC) ││
│                 │                      │  └─────────────────────────────────┘│
│                 │    modal secrets     │                                     │
│                 │ ──────────────────► │  ┌─────────────────────────────────┐│
└─────────────────┘                      │  │  MODAL VOLUME (/skills/)        ││
                                         │  │                                 ││
                                         │  │  telegram-chat/info.md          ││
                                         │  │  github/info.md                 ││
                                         │  │  planning/info.md               ││
                                         │  │  ... (53 skills)                ││
                                         │  │                                 ││
                                         │  │  Agents READ and WRITE here     ││
                                         │  │  Self-improvement persists      ││
                                         │  └─────────────────────────────────┘│
                                         └─────────────────────────────────────┘
                                                          │
                    ┌─────────────────────────────────────┼─────────────────┐
                    ▼                                     ▼                 ▼
          ┌─────────────────┐                   ┌─────────────┐   ┌─────────────┐
          │  TELEGRAM API   │                   │   FIREBASE  │   │QDRANT CLOUD │
          │  (Chat)         │                   │  (State)    │   │  (Memory)   │
          └─────────────────┘                   └─────────────┘   └─────────────┘
                    │
          ┌─────────────────┐
          │  WHATSAPP API   │
          │  (Evolution)    │
          └─────────────────┘
```

## Component Descriptions

### Modal Components

| Component | Type | Config | Purpose |
|-----------|------|--------|---------|
| Telegram Chat Agent | Web Endpoint | `min_containers=1` | Primary user interface |
| GitHub Agent | Cron + Webhook | Hourly | Repo automation |
| Data Agent | Scheduled | Daily | Data processing |
| Content Agent | Function | On-demand | Content generation |
| Skills Volume | Volume | 10GB | Mutable info.md storage |

### External Services

| Service | Purpose | Details |
|---------|---------|---------|
| Telegram Bot API | Chat interface | User messaging |
| WhatsApp Evolution API | Alternative chat | User messaging via WhatsApp |
| Firebase Firestore | State, task queue | Free tier |
| Firebase Storage | Reports, content files | 24h signed URLs, 7-day retention |
| Qdrant Cloud | Vector memory | Semantic search |
| Anthropic API | Claude LLM | Via ai4u.now proxy |
| Exa API | Web search | Primary search |
| Tavily API | Web search | Fallback search |
| GitHub API | Repo automation | Via PyGithub |

## II Framework Architecture

### Skill = Information + Implementation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         II FRAMEWORK PATTERN                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INFORMATION (.md)                    IMPLEMENTATION (.py)                   │
│  ─────────────────                    ──────────────────                     │
│  • Instructions for LLM               • Python execution code                │
│  • Memory of past runs                • Tool functions                       │
│  • Learned improvements               • LLM API calls                        │
│  • Error history                      • External integrations                │
│                                                                              │
│  MUTABLE at runtime                   IMMUTABLE after deploy                 │
│  → Modal Volume (/skills/)            → Modal Server (src/)                  │
│                                                                              │
│  Self-Improvement Flow:                                                      │
│  1. Read info.md from Volume                                                 │
│  2. Execute task with LLM + tools                                            │
│  3. Evaluate results                                                         │
│  4. Update info.md if needed                                                 │
│  5. Commit changes to Volume                                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Progressive Disclosure Pattern

```
Layer 1: DISCOVERY (Fast)
────────────────────────
SkillSummary {
  name: "planning"
  description: "Create implementation plans"
  category: "development"
}
→ Loaded for all 25+ skills at startup
→ Used for routing decisions

Layer 2: ACTIVATION (On-demand)
───────────────────────────────
Skill {
  name, description
  body: full markdown content
  memory: accumulated learnings
  error_history: past issues
}
→ Loaded when skill is invoked
→ Used as system prompt for LLM
```

## State Management Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STATE MANAGER (src/core/state.py)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  L1 CACHE (In-Memory)              L2 STORE (Firebase Firestore)            │
│  ─────────────────────             ─────────────────────────────            │
│  • TTL-based expiration            • Persistent storage                     │
│  • Thread-safe (lock)              • Async via asyncio.to_thread()          │
│  • Hot data access                 • Cold data fallback                     │
│                                                                              │
│  TTL Defaults:                                                               │
│  ├── Sessions: 1 hour                                                        │
│  ├── Conversations: 24 hours (last 20 messages)                              │
│  └── Generic cache: 5 minutes                                                │
│                                                                              │
│  Cache Flow:                                                                 │
│  ┌─────────┐    miss    ┌─────────┐    cache     ┌─────────┐                │
│  │ Request │ ─────────► │ L1 Cache│ ───────────► │ L2 Store│                │
│  └─────────┘            └─────────┘              └─────────┘                │
│       ▲                      │                        │                      │
│       │                      │ hit                    │ found                │
│       └──────────────────────┴────────────────────────┘                      │
│                                                                              │
│  Thread Safety:                                                              │
│  • _singleton_lock: Double-check locking for StateManager                   │
│  • _cache_lock: Protects L1 cache dict operations                           │
│  • Atomic session updates via Firebase merge                                │
│                                                                              │
│  Cache Warming (@enter hook):                                                │
│  • Preload skill metadata from Firebase                                      │
│  • Preload last 50 active user sessions                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Resilience Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CIRCUIT BREAKERS (src/core/resilience.py)           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Service        │ Circuit Name    │ Threshold │ Cooldown                    │
│  ────────────── │ ─────────────── │ ───────── │ ────────                    │
│  Exa Search     │ exa_api         │ 3 fails   │ 30s                         │
│  Tavily Search  │ tavily_api      │ 3 fails   │ 30s                         │
│  Firebase       │ firebase        │ 5 fails   │ 60s                         │
│  Qdrant         │ qdrant          │ 5 fails   │ 60s                         │
│  Claude API     │ claude_api      │ 3 fails   │ 60s                         │
│  Telegram API   │ telegram_api    │ 5 fails   │ 30s                         │
│  Gemini API     │ gemini_api      │ 3 fails   │ 60s                         │
│                                                                              │
│  PKM System Architecture (src/services/pkm.py)                               │
│  ┌─────────────────────────────────────────────────────────────┐             │
│  │ Input (Telegram) ──► PKM Service ──► Classification (LLM)   │             │
│  │                        │              │                     │             │
│  │                        ▼              ▼                     │             │
│  │                 Qdrant (Vector)   Firebase (Store)          │             │
│  │                 (Semantic Search) (Persistence)             │             │
│  └─────────────────────────────────────────────────────────────┘             │
│                                                                              │
│  States:                                                                     │
│  ├── CLOSED: Normal operation, requests pass through                        │
│  ├── OPEN: Service failing, reject immediately                              │
│  └── HALF_OPEN: Testing if service recovered                                │
│                                                                              │
│  Endpoints:                                                                  │
│  ├── GET /health - Includes circuit status                                  │
│  ├── GET /api/circuits - Detailed circuit stats                             │
│  └── POST /api/circuits/reset - Reset all circuits                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Execution Tracing

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TRACING (src/core/trace.py)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  TraceContext (async context manager)                                        │
│  ├── trace_id: Unique execution ID                                          │
│  ├── user_id: Telegram user ID                                              │
│  ├── skill: Skill name for metadata                                         │
│  ├── iterations: Agentic loop count                                         │
│  └── tool_traces: List[ToolTrace]                                           │
│                                                                              │
│  ToolTrace (per tool call)                                                   │
│  ├── name: Tool name                                                         │
│  ├── input_params: Tool input                                                │
│  ├── output: Tool result                                                     │
│  ├── duration_ms: Execution time                                             │
│  ├── is_error: Success/failure                                               │
│  └── timestamp: Call time                                                    │
│                                                                              │
│  Storage: Firebase (execution_traces collection)                             │
│  Retention: Configurable                                                     │
│                                                                              │
│  Endpoints:                                                                  │
│  ├── GET /api/traces?user_id=X&status=Y&limit=N                             │
│  └── GET /api/traces/{trace_id}                                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Self-Improvement Loop (Local-First)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              SELF-IMPROVEMENT (Local-First Architecture)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 1: ERROR DETECTION (Modal or Local)                                  │
│  ─────────────────────────────────────────                                  │
│  Error detected → ImprovementService.analyze_error()                        │
│       │                                                                      │
│       ├── Rate limit check (3/hour/skill)                                   │
│       ├── Deduplication check (24h window)                                  │
│       ▼                                                                      │
│  LLM Reflection → Generate proposal → Firebase (status: pending)            │
│                                                                              │
│  PHASE 2: ADMIN APPROVAL (Telegram)                                         │
│  ──────────────────────────────────                                         │
│  Telegram notification → [Approve] [Reject]                                 │
│       │                                                                      │
│       ├── Approve → Firebase (status: approved)                             │
│       └── Reject → Firebase (status: rejected)                              │
│                                                                              │
│  PHASE 3: LOCAL APPLICATION (Claude Code)                                   │
│  ─────────────────────────────────────────                                  │
│  python3 agents/scripts/pull-improvements.py                                │
│       │                                                                      │
│       ├── Fetch approved proposals from Firebase                            │
│       ├── Apply to local agents/skills/*/info.md                            │
│       └── Mark as "applied" in Firebase                                     │
│                                                                              │
│  PHASE 4: SYNC TO MODAL (Deploy)                                            │
│  ───────────────────────────────                                            │
│  git commit && git push                                                     │
│  modal deploy agents/main.py                                                │
│       │                                                                      │
│       └── sync_skills_from_local() → Modal Volume                           │
│           (preserves runtime Memory/Error History)                          │
│                                                                              │
│  KEY FILES:                                                                  │
│  • src/core/improvement.py - Proposal generation & Firebase storage         │
│  • scripts/pull-improvements.py - Local application script                  │
│  • main.py:sync_skills_from_local() - Deploy-time sync to Volume           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Improvement Status Flow:**
```
pending → approved → applied
    └──→ rejected
```

**Source of Truth:** Local `agents/skills/` directory (Git-tracked)

## Tool System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TOOL SYSTEM                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ToolRegistry                                                                │
│  ├── get_definitions() → List[dict]   # Anthropic-compatible schemas        │
│  ├── execute(name, input) → str       # Run tool and return result          │
│  └── register(tool)                   # Add new tool                         │
│                                                                              │
│  Built-in Tools:                                                             │
│  ┌──────────────┬─────────────────────────────────────────────────────────┐ │
│  │ web_search   │ Search web via Exa (primary) + Tavily (fallback)        │ │
│  ├──────────────┼─────────────────────────────────────────────────────────┤ │
│  │ get_datetime │ Current date/time with timezone support                 │ │
│  ├──────────────┼─────────────────────────────────────────────────────────┤ │
│  │ run_python   │ Execute Python code in sandboxed environment            │ │
│  ├──────────────┼─────────────────────────────────────────────────────────┤ │
│  │ read_webpage │ Fetch and parse URL content                             │ │
│  ├──────────────┼─────────────────────────────────────────────────────────┤ │
│  │ search_memory│ Semantic search in Qdrant vector store                  │ │
│  └──────────────┴─────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Agentic Loop Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENTIC LOOP (max 5 iterations)                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  User Message                                                                │
│       │                                                                      │
│       ▼                                                                      │
│  ┌──────────────────────┐                                                    │
│  │ Build Messages       │ ← Context (last 5 messages)                        │
│  │ + System Prompt      │ ← From info.md                                     │
│  │ + Tools              │ ← From registry                                    │
│  └──────────┬───────────┘                                                    │
│             │                                                                │
│             ▼                                                                │
│  ┌──────────────────────┐                                                    │
│  │ Call Claude API      │                                                    │
│  │ with tools           │                                                    │
│  └──────────┬───────────┘                                                    │
│             │                                                                │
│             ├─── stop_reason: "end_turn" ──► Return text response            │
│             │                                                                │
│             └─── stop_reason: "tool_use" ──┐                                 │
│                                            │                                 │
│                  ┌─────────────────────────▼─────┐                           │
│                  │ Execute tool(s)               │                           │
│                  │ Append results to messages    │                           │
│                  └─────────────────────────┬─────┘                           │
│                                            │                                 │
│                                            └──► Loop (next iteration)        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Skill Routing Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SKILL ROUTING                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Request: "Create a plan for authentication"                                 │
│       │                                                                      │
│       ▼                                                                      │
│  ┌──────────────────────┐                                                    │
│  │ SkillRouter.route()  │                                                    │
│  └──────────┬───────────┘                                                    │
│             │                                                                │
│             ├─── Try: Semantic Search (Qdrant)                               │
│             │         Embed request → Search skills collection               │
│             │         Return: [{skill: "planning", score: 0.92}]             │
│             │                                                                │
│             └─── Fallback: Keyword Match                                     │
│                   If Qdrant fails, match keywords                            │
│                   in skill names/descriptions                                │
│                                                                              │
│       ▼                                                                      │
│  ┌──────────────────────┐                                                    │
│  │ Load Full Skill      │ ← Progressive disclosure Layer 2                   │
│  │ (registry.get_full)  │                                                    │
│  └──────────┬───────────┘                                                    │
│             │                                                                │
│             ▼                                                                │
│  ┌──────────────────────┐                                                    │
│  │ Execute with LLM     │ ← Skill body as system prompt                      │
│  └──────────────────────┘                                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Skill Execution Modes

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXECUTION MODES                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SIMPLE                    ROUTED                     ORCHESTRATED           │
│  ──────                    ──────                     ────────────           │
│  Direct skill execution    Auto-select best skill    Multi-skill complex     │
│                                                       task coordination      │
│  POST /api/skill           POST /api/skill           POST /api/skill         │
│  {                         {                         {                       │
│    "skill": "planning",      "task": "...",            "task": "...",        │
│    "task": "...",            "mode": "routed"          "mode": "orchestrated"│
│    "mode": "simple"        }                         }                       │
│  }                                                                           │
│                                                                              │
│  CHAINED                   EVALUATED                                         │
│  ───────                   ─────────                                         │
│  Sequential skill          Execute with quality                              │
│  pipeline                  assessment                                        │
│                                                                              │
│  POST /api/skill           POST /api/skill                                   │
│  {                         {                                                 │
│    "skills": ["research",    "skill": "planning",                            │
│               "planning"],   "task": "...",                                  │
│    "task": "...",            "mode": "evaluated"                             │
│    "mode": "chained"       }                                                 │
│  }                                                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Message Flow (Telegram Chat)

```
User (Telegram) ──► Telegram Server ──► Modal Webhook
                                             │
                                             ▼
                                      ┌─────────────────┐
                                      │ Extract Message │
                                      └────────┬────────┘
                                               │
                         ┌─────────────────────┼─────────────────────┐
                         │                     │                     │
                         ▼                     ▼                     ▼
                   ┌──────────┐         ┌──────────┐          ┌──────────┐
                   │ Command? │         │ Regular  │          │ Error    │
                   │ /help    │         │ Message  │          │ Handler  │
                   └────┬─────┘         └────┬─────┘          └──────────┘
                        │                    │
                        ▼                    ▼
                   ┌──────────┐         ┌──────────────────┐
                   │ Handle   │         │ Agentic Loop     │
                   │ Command  │         │ with Tools       │
                   └────┬─────┘         └────────┬─────────┘
                        │                        │
                        └────────────┬───────────┘
                                     ▼
                              ┌─────────────────┐
                              │ Send Response   │──► Telegram API
                              └─────────────────┘
```

## Firebase Schema

```javascript
firestore/
├── users/{userId}
│   ├── telegramId: string
│   ├── preferences: map
│   └── createdAt: timestamp
├── agents/{agentId}
│   ├── status: "running" | "idle" | "error"
│   ├── lastRun: timestamp
│   └── config: map
├── tasks/{taskId}
│   ├── type: "github" | "data" | "content"
│   ├── status: "pending" | "processing" | "done"
│   ├── payload: map
│   └── result: map
└── logs/{logId}
    ├── skill_id: string
    ├── action: string
    ├── result: string
    ├── duration_ms: number
    └── timestamp: timestamp
```

## Qdrant Collections

| Collection | Vector Dim | Purpose |
|------------|------------|---------|
| `skills` | 3072 | Skill embeddings for routing (gemini-embedding-001) |
| `faq_embeddings` | 3072 | FAQ semantic search (20 entries) |
| `knowledge` | 3072 | Cross-skill insights |
| `conversations` | 3072 | Chat history |
| `errors` | 3072 | Error pattern matching |

## Module Structure (Post-Refactor)

```
agents/
├── main.py                          # Modal app entry, route includes (~2,000 lines)
├── api/                             # FastAPI layer
│   ├── __init__.py
│   ├── app.py                       # App factory, middleware
│   ├── dependencies.py              # Auth, rate limiting, webhook verification
│   └── routes/
│       ├── health.py                # /health endpoint
│       ├── telegram.py              # /webhook/telegram
│       ├── whatsapp.py              # /webhook/whatsapp (Evolution API)
│       ├── github.py                # /webhook/github
│       ├── skills.py                # /api/skill, /api/skills
│       └── reports.py               # /api/reports
├── commands/                        # Command handling layer
│   ├── base.py                      # CommandRouter with decorator pattern
│   ├── router.py                    # Global command_router instance
│   ├── user.py                      # /start, /help, /status, /tier, /clear, /cancel
│   ├── skills.py                    # /skills, /skill, /mode, /suggest, /task
│   ├── admin.py                     # /grant, /revoke, /faq, /admin
│   ├── personalization.py           # /profile, /context, /macro, /macros, /activity
│   ├── developer.py                 # /traces, /trace, /circuits, /improve
│   ├── pkm.py                       # /capture, /inbox, /notes, /tasks (PKM)
│   └── reminders.py                 # /remind, /reminders
├── validators/                      # Input validation
│   └── input.py                     # InputValidator: skill names, text, FAQ patterns
├── config/                          # Configuration
│   └── env.py                       # Admin validation, env helpers
├── src/
│   ├── core/                        # Core framework (12 modules)
│   │   ├── state.py                 # StateManager (L1 cache + L2 Firebase)
│   │   ├── resilience.py            # Circuit breakers (7)
│   │   ├── trace.py                 # TraceContext
│   │   ├── improvement.py           # Self-improvement proposals
│   │   ├── faq.py                   # Smart FAQ (keyword + semantic)
│   │   └── suggestions.py           # Proactive suggestions
│   ├── services/
│   │   ├── firebase/                # Firebase domain services (12 modules)
│   │   │   ├── _client.py           # Thread-safe Firebase init (lru_cache)
│   │   │   ├── _circuit.py          # @with_firebase_circuit decorator
│   │   │   ├── users.py             # User CRUD
│   │   │   ├── tasks.py             # Task queue
│   │   │   ├── tiers.py             # User tier system
│   │   │   ├── faq.py               # FAQ management
│   │   │   ├── reports.py           # Firebase Storage reports + content files
│   │   │   ├── reminders.py         # Reminder scheduling
│   │   │   ├── local_tasks.py       # Local skill task queue
│   │   │   ├── pkm.py               # PKM data persistence
│   │   │   ├── ii_framework.py      # Temporal entities, decisions
│   │   │   ├── tokens.py            # OAuth tokens
│   │   │   └── __init__.py          # Backward compatibility re-exports
│   │   ├── llm.py                   # Claude API client
│   │   ├── telegram.py              # Telegram Bot API
│   │   ├── evolution.py             # WhatsApp Evolution API
│   │   ├── gemini.py                # Gemini API (vision, grounding, thinking)
│   │   └── pkm.py                   # PKM logic, classification, semantic search
│   ├── skills/                      # Skill system
│   │   └── registry.py              # SkillRegistry with progressive disclosure
│   └── tools/                       # Tool implementations
│       ├── gemini_tools.py          # Gemini skill handlers (with download links)
│       ├── web_search.py            # Exa + Tavily search
│       └── code_exec.py             # Python execution
└── skills/                          # 53 skill info.md files
```

### Layer Responsibilities

| Layer | Responsibility |
|-------|----------------|
| `api/` | HTTP routing, middleware, request/response |
| `commands/` | Telegram command handling, permission checks |
| `validators/` | Input sanitization, security constraints |
| `src/core/` | Framework: state, circuits, tracing |
| `src/services/` | External integrations: Firebase, LLM, APIs |
| `src/skills/` | Skill loading and routing |
| `src/tools/` | Tool implementations for agentic loop |

### Command Router Pattern

Commands use a decorator-based registration pattern:

```python
from commands.router import command_router

@command_router.command(
    name="/mycommand",
    description="What it does",
    permission="user",  # guest|user|developer|admin
    category="general"
)
async def my_command(args: str, user: dict, chat_id: int) -> str:
    return "Response"
```

### Circuit Breaker Decorator

Firebase operations use a reusable decorator:

```python
from src.services.firebase._circuit import with_firebase_circuit

@with_firebase_circuit(open_return=None)
async def get_user(user_id: int):
    db = get_db()
    doc = db.collection("users").document(str(user_id)).get()
    return doc.to_dict() if doc.exists else None

@with_firebase_circuit(raise_on_open=True)
async def create_user(user_id: int, data: dict):
    db = get_db()
    db.collection("users").document(str(user_id)).set(data)
```

## Cost Estimate

| Component | Monthly Cost |
|-----------|-------------|
| Modal compute | ~$15-20 |
| Qdrant Cloud | ~$25 |
| LLM API calls | ~$10-20 |
| Firebase | $0 (free tier) |
| **Total** | **~$40-60** |
