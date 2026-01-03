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
│                 │                      │  │  MODAL VOLUME (/skills/)        ││
│                 │                      │  │                                 ││
│                 │                      │  │  telegram-chat/info.md          ││
│                 │                      │  │  github/info.md                 ││
│                 │                      │  │  planning/info.md               ││
│                 │                      │  │  ... (53 skills)                ││
│                 │                      │  │                                 ││
│                 │                      │  │  Agents READ and WRITE here     ││
│                 │                      │  │  Self-improvement persists      ││
│                 │                      │  └─────────────────────────────────┘│
│                 │                      └─────────────────────────────────────┘
└─────────────────┘                                          │
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
| Claude Agents SDK | Framework | - | Hook-based agent management |

### External Services

| Service | Purpose | Details |
|---------|---------|---------|
| Telegram Bot API | Chat interface | User messaging |
| WhatsApp Evolution API | Alternative chat | User messaging via WhatsApp |
| Firebase Firestore | State, task queue | 14 modules, free tier |
| Firebase Storage | Reports, content files | 24h signed URLs, 7-day retention |
| Qdrant Cloud | Vector memory | 7 collections, semantic search |
| Anthropic API | Claude LLM | Via ai4u.now proxy |
| Google Vertex AI | Gemini LLM | Deep research, vision, grounding |
| Exa API | Web search | Primary search |
| Tavily API | Web search | Fallback search |
| GitHub API | Repo automation | Via PyGithub |
| Google Calendar/Tasks | Personal info | OAuth2 bidirectional sync |
| Apple CalDAV/iCloud | Personal info | CalDAV sync |

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
→ Loaded for all 102 skills at startup
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
│  Evolution API  │ evolution_api   │ 5 fails   │ 30s                         │
│  Gemini API     │ gemini_api      │ 3 fails   │ 60s                         │
│  Google Calendar│ google_calendar │ 3 fails   │ 60s                         │
│  Google Tasks   │ google_tasks    │ 3 fails   │ 60s                         │
│  Apple CalDAV   │ apple_caldav    │ 3 fails   │ 60s                         │
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

## Smart Task Management Architecture (src/core/task_extractor.py)

```
┌─────────────────────────────────────────────────────────────┐
│ Input (Telegram/WhatsApp) ──► NLP Parser (Date/Task)        │
│                                     │                       │
│                                     ▼                       │
│                              Task Extractor                 │
│                                     │                       │
│               ┌─────────────────────┼────────────────────┐  │
│               ▼                     ▼                    ▼  │
│        Firebase (Store)      Qdrant (Vector)      Calendar Sync│
│        (Persistence)         (Search)             (Google/Apple)│
└─────────────────────────────────────────────────────────────┘
```

## PKM System Architecture (src/services/pkm.py)

```
┌─────────────────────────────────────────────────────────────┐
│ Input (Telegram) ──► PKM Service ──► Classification (LLM)   │
│                        │              │                     │
│                        ▼              ▼                     │
│                 Qdrant (Vector)   Firebase (Store)          │
│                 (Semantic Search) (Persistence)             │
└─────────────────────────────────────────────────────────────┘
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

## Module Structure (Post-Refactor)

```
agents/
├── main.py                          # Modal app entry, route includes
├── api/                             # FastAPI layer
│   └── routes/
│       ├── health.py                # /health endpoint
│       ├── telegram.py              # /webhook/telegram
│       ├── whatsapp.py              # /webhook/whatsapp
│       └── ...
├── commands/                        # Command handling layer
│   ├── base.py                      # CommandRouter with decorator
│   ├── pkm.py                       # PKM commands
│   └── ...
├── src/
│   ├── sdk/                         # Claude Agents SDK
│   │   ├── agent.py                 # Agent factory
│   │   └── hooks/                   # Resilience hooks
│   ├── core/                        # Core framework (15+ modules)
│   │   ├── state.py                 # StateManager
│   │   ├── resilience.py            # Circuit breakers
│   │   ├── calendar_sync.py         # Bidirectional sync
│   │   ├── smart_timing.py          # behavior-based scheduling
│   │   ├── nlp_parser.py            # Temporal extraction
│   │   └── ...
│   ├── services/
│   │   ├── firebase/                # Modular Firebase (14 modules)
│   │   ├── google_calendar.py       # Google Calendar API
│   │   ├── google_tasks.py          # Google Tasks API
│   │   ├── apple_caldav.py          # iCloud CalDAV API
│   │   └── ...
│   └── tools/                       # Tool implementations
└── skills/                          # 102 skill info.md files
```
