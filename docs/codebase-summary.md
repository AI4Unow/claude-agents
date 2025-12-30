# Codebase Summary

## Current Status

**Phase:** Production MVP
**Deploy URL:** https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run
**Last Updated:** Dec 30, 2025

**Statistics:**
- **55 skills** in agents/skills/ directory
- **50+ Python files** in agents/src/
- **22 test files** (unit + stress tests with Locust framework)
- **~3,200 lines** in main.py
- **7 circuit breakers** (exa, tavily, firebase, qdrant, claude, telegram, gemini)
- **14 API endpoints** (health, webhooks, skill execution, reports, traces, circuits)
- **4 agents** (Telegram, GitHub, Data, Content)

**Key Features:**
- Execution tracing with tool-level timing
- Self-improvement loop with Telegram admin approval
- State management with L1/L2 caching
- Gemini API integration for research, grounding, vision, thinking
- Firebase Storage for research reports
- User tier system (guest, user, developer, admin)
- Hybrid skill architecture (local, remote, both)
- **Personalization system** (profiles, context, macros, activity learning)
- **Smart FAQ system** (hybrid keyword + semantic matching)

## Repository Structure

```
./
├── CLAUDE.md                      # Claude Code project instructions
├── README.md                      # Project readme
├── firebase.json                  # Firebase hosting config
├── firestore.indexes.json         # Firestore composite indexes
├── docs/                          # Documentation
│   ├── project-overview-pdr.md
│   ├── system-architecture.md
│   ├── code-standards.md
│   ├── codebase-summary.md        # This file
│   ├── project-roadmap.md
│   └── deployment-guide.md
├── plans/                         # Implementation plans
│   ├── 251229-1515-telegram-stress-test/
│   ├── 251228-0903-skills-categorization/
│   └── reports/                   # Planning reports
├── agents/                        # Main codebase
    ├── main.py                    # Modal app entry point (~3,200 lines)
    ├── modal.toml                 # Modal configuration
    ├── requirements.txt           # Python dependencies
    ├── src/
    │   ├── agents/                # Agent implementations
    │   ├── services/              # External service integrations
    │   ├── tools/                 # Tool system
    │   ├── core/                  # II Framework core components
    │   ├── skills/                # Skill registry
    │   ├── models/                # Data models (personalization)
    │   └── utils/                 # Utilities (logging)
    ├── skills/                    # 55 skill info.md files
    ├── scripts/                   # Utility scripts
    └── tests/                     # 22 test files
```

## Entry Point (main.py - ~3,200 lines)

The main Modal app defining:
- **FastAPI web application** with 14 endpoints
- **TelegramChatAgent class** with @enter hook for cache warming
- **4 specialized agents** (Telegram, GitHub, Data, Content)
- **Skill API** with execution modes (simple, routed, auto, orchestrated, chained, evaluated)
- **User tier system** with permission-based commands
- **Reports API** for Firebase Storage access
- **Cron jobs** for scheduled tasks
- **Test functions** for service verification

### Key Decorators
```python
@app.cls(min_containers=1)  # Telegram chat agent (always-on)
@app.function(schedule=modal.Cron("0 * * * *"))  # GitHub monitor (hourly)
@app.function(schedule=modal.Cron("0 1 * * *"))  # Daily summary
@app.function(timeout=120)  # Content agent
```

## Core Components

### Agents (src/agents/)

| File | Lines | Purpose | Trigger |
|------|-------|---------|---------|
| `base.py` | 150 | Base agent class | - |
| `content_generator.py` | 250 | Content generation/transformation | HTTP API + commands |
| `data_processor.py` | 200 | Data processing & analytics | Cron (daily) |
| `github_automation.py` | 300 | GitHub repo automation | Cron (hourly) + webhook |

### Services (src/services/)

| File | Lines | Purpose |
|------|-------|---------|
| `firebase.py` | ~1,200 | Firestore + Storage (state, tiers, tasks, reports, reminders) |
| `gemini.py` | 441 | GeminiClient with Vertex AI SDK (chat, research, grounding, vision) |
| `llm.py` | 200 | Claude API client (Anthropic via ai4u.now proxy) |
| `agentic.py` | 260 | Agentic loop with tool execution + conversation persistence |
| `qdrant.py` | 617 | Qdrant vector database client |
| `telegram.py` | 400 | Telegram message utilities + formatters (markdown-to-HTML) |
| `embeddings.py` | 200 | Embedding generation with caching |
| `media.py` | 127 | Media processing utilities |
| `user_profile.py` | 200 | User profile CRUD + onboarding |
| `user_context.py` | 150 | Work context management |
| `user_macros.py` | 260 | Personal macros with NLU detection |
| `activity.py` | 250 | Activity logging + pattern analysis |
| `data_deletion.py` | 160 | GDPR-compliant data deletion |
| `personalization.py` | 100 | Personalization loader with L1/L2 cache |

### Tools (src/tools/)

| File | Tool | Purpose |
|------|------|---------|
| `gemini_tools.py` | Gemini skills | Deep research, grounding, thinking, vision handlers |
| `web_search.py` | `web_search` | Web search via Exa (primary) + Tavily (fallback) |
| `datetime_tool.py` | `get_datetime` | Timezone-aware date/time |
| `code_exec.py` | `run_python` | Python code execution |
| `web_reader.py` | `read_webpage` | URL content fetching |
| `memory_search.py` | `search_memory` | Qdrant vector search |
| `registry.py` | - | Tool registry with Anthropic-compatible definitions |
| `base.py` | - | Base tool interface |

### Core II Framework (src/core/)

| File | Lines | Purpose |
|------|-------|---------|
| `state.py` | 500+ | StateManager with L1 TTL cache + L2 Firebase, user tiers |
| `resilience.py` | 350 | Circuit breakers (7 services) + retry decorator |
| `trace.py` | 200 | Execution tracing with TraceContext, ToolTrace |
| `improvement.py` | 500 | Self-improvement service with Telegram approval |
| `orchestrator.py` | 500 | Multi-skill task orchestration with progress |
| `complexity.py` | 130 | Task complexity classification |
| `evaluator.py` | 287 | Quality evaluation and optimization |
| `context_optimization.py` | 283 | Context compaction and optimization |
| `chain.py` | 243 | Sequential skill pipeline execution |
| `router.py` | 160 | Semantic skill routing via Qdrant |
| `faq.py` | 350 | Smart FAQ with hybrid keyword + semantic matching |
| `suggestions.py` | 200 | Proactive suggestion engine |
| `macro_executor.py` | 170 | Macro execution with rate limiting |

### Models (src/models/)

| File | Purpose |
|------|---------|
| `personalization.py` | Data models (UserProfile, WorkContext, Macro, PersonalContext) |

#### Circuit Breakers (resilience.py)

7 pre-configured circuits with states: CLOSED, OPEN, HALF_OPEN
```python
exa_circuit = CircuitBreaker("exa_api", threshold=3, cooldown=30)
tavily_circuit = CircuitBreaker("tavily_api", threshold=3, cooldown=30)
firebase_circuit = CircuitBreaker("firebase", threshold=5, cooldown=60)
qdrant_circuit = CircuitBreaker("qdrant", threshold=5, cooldown=60)
claude_circuit = CircuitBreaker("claude_api", threshold=3, cooldown=60)
telegram_circuit = CircuitBreaker("telegram_api", threshold=5, cooldown=30)
gemini_circuit = CircuitBreaker("gemini_api", threshold=3, cooldown=60)
```

Features:
- Exponential backoff with `with_retry` decorator
- `get_circuit_stats()` for monitoring
- `/api/circuits` endpoint for status
- `/api/circuits/reset` for admin reset

#### Tracing (trace.py)

Components:
- **TraceContext**: Async context manager for execution spans
- **ToolTrace**: Individual tool call with timing/error status
- **ExecutionTrace**: Complete execution with all tool traces
- Firebase persistence for trace history
- `/api/traces` endpoints (developer+ tier)

#### Self-Improvement (improvement.py)

Flow:
1. Error detection → `ImprovementService.analyze_error()`
2. Rate limiting (3/hour/skill) + deduplication (24h window)
3. LLM reflection → Generate proposal → Firebase (status: pending)
4. Telegram notification with approve/reject buttons
5. Local application via `scripts/pull-improvements.py`
6. Sync to Modal Volume on deploy

Status transitions: `pending → approved → applied` or `pending → rejected`

#### State Manager (state.py)

Features:
- **L1 Cache**: In-memory with TTL (sessions: 1h, conversations: 24h, generic: 5min)
- **L2 Store**: Firebase Firestore for persistence
- **Thread-safe**: Double-check locking for singleton + cache operations
- **Cache warming**: @enter hook preloads skills + last 50 active sessions
- **User tiers**: guest, user, developer, admin with rate limits
- **User modes**: simple, routed, auto
- **Conversation persistence**: Last 20 messages per user

## Skills (agents/skills/ - 55 total)

Organized by deployment type:

### Local Only (8)
Require local execution (browser automation, consumer IP):
- `canvas-design/`, `docx/`, `xlsx/`, `pptx/`, `pdf/`
- `image-enhancer/`, `media-processing/`, `video-downloader/`

### Remote (40+)
Deployed to Modal.com:

**Agent Skills:**
- `telegram-chat/`, `github/`, `data/`, `content/`

**Development:**
- `planning/`, `debugging/`, `code-review/`, `research/`
- `skill-creator/`, `problem-solving/`, `internal-comms/`

**Backend:**
- `backend-development/`, `databases/`, `devops/`
- `web-frameworks/`, `shopify/`

**Frontend:**
- `frontend-development/`, `frontend-design/`, `frontend-design-pro/`
- `ui-ux-pro-max/`, `ui-styling/`

**Mobile:**
- `mobile-development/`

**AI:**
- `ai-multimodal/`, `ai-artist/`, `content-research-writer/`

**Gemini:**
- `gemini-deep-research/`, `gemini-grounding/`, `gemini-thinking/`, `gemini-vision/`

**Automation:**
- `tiktok-automation/`, `linkedin-automation/`, `fb-to-tiktok/`

**Utilities:**
- `raffle-winner-picker/`, `domain-name-brainstormer/`, `theme-factory/`

### Hybrid (7)
Both local and remote execution:
- `better-auth/`, `chrome-devtools/`, `mcp-builder/`, `mcp-management/`
- `repomix/`, `sequential-thinking/`, `webapp-testing/`

### Skill Structure

Each skill follows II Framework pattern:
```
skills/skill-name/
├── info.md              # Information: instructions, memory, plans (mutable)
└── scripts/             # Optional: utility scripts
    ├── tool.py
    └── tests/
        └── test_tool.py
```

YAML frontmatter:
```yaml
---
name: skill-name
description: Brief description for routing
category: development|design|media|document
deployment: local|remote|both    # Determines execution environment
---
```

## API Endpoints (14 total)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check with circuit breaker status |
| `/webhook/telegram` | POST | Telegram bot webhook |
| `/webhook/github` | POST | GitHub event webhook |
| `/api/skill` | POST | Execute skill (6 modes) |
| `/api/skills` | GET | List available skills with deployment info |
| `/api/task/{id}` | GET | Get local task status/result |
| `/api/reports` | GET | List user research reports (Firebase Storage) |
| `/api/reports/{id}` | GET | Get report download URL (signed) |
| `/api/reports/{id}/content` | GET | Get report content |
| `/api/content` | POST | Content generation API |
| `/api/traces` | GET | List execution traces (developer+) |
| `/api/traces/{id}` | GET | Get single trace (developer+) |
| `/api/circuits` | GET | Circuit breaker status (developer+) |
| `/api/circuits/reset` | POST | Reset all circuits (admin) |

## Telegram Bot Commands

| Command | Tier | Description |
|---------|------|-------------|
| `/start` | All | Welcome message |
| `/help` | All | Show commands (tier-aware) |
| `/status` | All | Agent and tier status |
| `/tier` | All | Check tier and rate limit |
| `/clear` | All | Clear conversation history |
| `/skills` | All | Browse skills (inline menu) |
| `/skill <name> <task>` | All | Execute skill |
| `/mode <simple\|routed\|auto>` | All | Set execution mode |
| `/translate <text>` | All | Translate to English |
| `/summarize <text>` | All | Summarize text |
| `/rewrite <text>` | All | Improve text |
| `/task <id>` | User+ | Check local task status |
| `/cancel` | User+ | Cancel pending task |
| `/traces [limit]` | Developer+ | Recent execution traces |
| `/trace <id>` | Developer+ | Trace details |
| `/circuits` | Developer+ | Circuit breaker status |
| `/grant <id> <tier>` | Admin | Grant user tier |
| `/revoke <id>` | Admin | Revoke user access |
| `/admin reset <circuit>` | Admin | Reset circuit breaker |
| `/remind <time> <msg>` | Admin | Set reminder |
| `/reminders` | Admin | List reminders |
| `/profile [set]` | All | View/edit user profile |
| `/context [set/clear]` | All | Manage work context |
| `/macro [add/list/del]` | All | Personal macro management |
| `/activity [stats]` | All | View activity history |
| `/suggest` | All | Get proactive suggestions |
| `/forget` | All | Delete all personal data (GDPR) |

## Technology Stack

| Layer | Technology | Version |
|-------|------------|---------|
| Runtime | Modal.com (Python 3.11) | modal>=0.60.0 |
| Web Framework | FastAPI | >=0.109.0 |
| AI - Primary | Anthropic Claude | anthropic>=0.40.0 |
| AI - Secondary | Google Gemini | google-genai>=1.0.0 |
| Vector DB | Qdrant Cloud | qdrant-client>=1.7.0 |
| State Store | Firebase Firestore + Storage | firebase-admin>=6.4.0 |
| Chat Platform | Telegram | python-telegram-bot>=21.0 |
| GitHub | PyGithub | >=2.1.0 |
| Web Search | Exa + Tavily | exa-py>=1.0.0, tavily-python>=0.3.0 |
| Document Processing | python-docx, openpyxl, python-pptx, pypdf | Various |
| Logging | structlog | >=24.1.0 |

## Tests (22 files)

### Unit Tests
Located in skill scripts:
- `agents/skills/*/scripts/tests/test_*.py`
- Coverage for individual skill utilities

### Stress Tests
Located in `agents/tests/stress/`:
- **Locust framework** for load testing
- **Chaos engineering** scenarios
- **Metrics collection** and reporting
- Test scenarios: concurrent users, skill routing, API endpoints

Framework files:
- `locustfile.py` - Main Locust configuration
- `chaos.py` - Chaos engineering (circuit failures, delays)
- `metrics.py` - Metrics collection and analysis

## Scripts (agents/scripts/)

| Script | Purpose |
|--------|---------|
| `local-executor.py` | Poll Firebase for local tasks, execute via Claude Code |
| `pull-improvements.py` | Fetch approved improvements from Firebase, apply to local skills |
| `skill-to-modal.py` | Helper for skill deployment |
| `skill-sync-watcher.py` | Auto-sync skills on file change (launchd) |
| `seed-faq.py` | Seed FAQ entries to Qdrant |
| `sync-skills.sh` | Shell script for skill synchronization |
| `verify_phase_2a.py` | Verification script |

## Data Flow

### Message Flow (Telegram)
```
User (Telegram) → Telegram Server → Modal Webhook → Extract Message
                                            ↓
                    ┌───────────────────────┼───────────────────┐
                    ↓                       ↓                   ↓
              Command Handler       Agentic Loop          Error Handler
                    ↓                       ↓
              Execute Command       Tool Execution
                    └───────────────┬───────┘
                                    ↓
                            Send Response → Telegram API
```

### Skill Execution Flow
```
Request → Mode Detection → is_local_skill()?
                                ├─ Yes → Queue to Firebase (pending)
                                │        └─ local-executor.py polls (30s)
                                │           └─ Execute via Claude Code
                                │              └─ Update Firebase (done/error)
                                │                 └─ Notify user
                                │
                                └─ No → Execute on Modal
                                       ├─ Simple: Direct execution
                                       ├─ Routed: Semantic routing
                                       ├─ Auto: Complexity detection
                                       ├─ Orchestrated: Multi-skill
                                       ├─ Chained: Sequential pipeline
                                       └─ Evaluated: Quality assessment
```

### State Flow
```
Request → L1 Cache (check) → Hit? → Return
                ↓
             Miss
                ↓
        L2 Firebase (fetch) → Cache in L1 → Return
```

## Firestore Schema

Collections:
```javascript
users/{userId}
  ├── telegramId: string
  ├── tier: "guest" | "user" | "developer" | "admin"
  ├── preferences: { mode: string }
  ├── rateLimit: { count: number, resetAt: timestamp }
  └── createdAt: timestamp

agents/{agentId}
  ├── status: "running" | "idle" | "error"
  ├── lastRun: timestamp
  └── config: map

tasks/{taskId}
  ├── userId: string
  ├── skill: string
  ├── task: string
  ├── status: "pending" | "processing" | "done" | "error"
  ├── result: string
  ├── createdAt: timestamp
  └── updatedAt: timestamp

execution_traces/{traceId}
  ├── userId: string
  ├── skill: string
  ├── status: "success" | "error"
  ├── iterations: number
  ├── toolTraces: array
  └── timestamp: timestamp

improvement_proposals/{proposalId}
  ├── skillName: string
  ├── errorContext: string
  ├── proposedFix: string
  ├── status: "pending" | "approved" | "rejected" | "applied"
  └── createdAt: timestamp

user_sessions/{sessionId}
  ├── userId: string
  ├── messages: array (last 20)
  └── updatedAt: timestamp

user_profiles/{userId}
  ├── name: string
  ├── tone: string ("concise" | "detailed" | "casual")
  ├── domain: array (expertise areas)
  ├── tech_stack: array (technologies)
  ├── communication_prefs: map
  ├── onboarded: boolean
  └── updatedAt: timestamp

user_contexts/{userId}
  ├── current_project: string
  ├── current_task: string
  ├── blockers: array
  ├── goals: array
  └── updatedAt: timestamp

user_macros/{userId}/macros/{macroId}
  ├── trigger_phrases: array
  ├── action_type: "command" | "skill" | "sequence"
  ├── action: string
  ├── description: string
  ├── use_count: number
  └── createdAt: timestamp

user_activities/{userId}/logs/{activityId}
  ├── action_type: string
  ├── skill: string
  ├── summary: string
  ├── duration_ms: number
  └── timestamp: timestamp

reminders/{reminderId}
  ├── userId: string
  ├── message: string
  ├── scheduledAt: timestamp
  └── status: "pending" | "sent"
```

Firebase Storage:
```
research-reports/{userId}/{reportId}.md
```

## Qdrant Collections

| Collection | Vector Dim | Purpose |
|------------|------------|---------|
| `skills` | 768/1536 | Skill embeddings for semantic routing |
| `knowledge` | 768/1536 | Cross-skill insights |
| `conversations` | 768/1536 | Chat history (future) |
| `errors` | 768/1536 | Error pattern matching (future) |
| `faq` | 768/1536 | FAQ entries for smart FAQ system |
| `user_activities` | 768/1536 | User activity embeddings for pattern analysis |

## Key Design Patterns

### II Framework
- **Information** (.md) = Mutable instructions/memory → Modal Volume
- **Implementation** (.py) = Immutable code → Modal Server

### Progressive Disclosure
- **Layer 1**: SkillSummary (name, description, category) - fast discovery
- **Layer 2**: Full Skill (body, memory, error_history) - on activation

### Resilience
- Circuit breakers with exponential backoff
- Graceful degradation (Exa → Tavily fallback)
- Health check with circuit status

### Observability
- Structured logging (structlog)
- Execution tracing with tool timing
- Metrics exposed via endpoints

### State Management
- L1 in-memory cache (TTL-based)
- L2 Firebase persistence
- Thread-safe operations
- Cache warming on container start

## Recent Changes (Dec 30, 2025)

1. **Personalization System** - Complete user personalization layer:
   - User profiles (tone, domain, tech stack preferences)
   - Work context (current project, task, blockers, goals)
   - Personal macros with NLU detection (exact + semantic matching)
   - Activity logging + pattern analysis
   - Proactive suggestions engine
   - GDPR-compliant data deletion (/forget command)
   - Rate limiting (5s per-macro cooldown)
   - Dangerous command blocking

2. **Smart FAQ System** - Hybrid keyword + semantic FAQ matching:
   - `src/core/faq.py` - FAQ engine with Qdrant vector search
   - `scripts/seed-faq.py` - FAQ seeding script
   - Keywords + embeddings for dual-phase matching

3. **New Commands** - 6 personalization commands:
   - `/profile`, `/context`, `/macro`, `/activity`, `/suggest`, `/forget`

4. **Model names corrected** - Using kiro-claude-* from ai4u.now API
5. **Skill auto-sync watcher** - `scripts/skill-sync-watcher.py` with launchd
6. **55 skills** - With local/remote/both categorization

## LLM Models (via ai4u.now API)

| Purpose | Model | File |
|---------|-------|------|
| All calls | `kiro-claude-opus-4-5-agentic` | `llm.py`, `main.py`, `complexity.py`, `intent.py` |

Note: Haiku model not available via Anthropic SDK on ai4u.now proxy.

Available models on API (OpenAI SDK only):
- **Claude**: `kiro-claude-opus-4-5`, `kiro-claude-sonnet-4-5`, `kiro-claude-sonnet-4`, `kiro-claude-haiku-4-5`
- **Claude Agentic**: `kiro-claude-opus-4-5-agentic`, `kiro-claude-sonnet-4-5-agentic`, `kiro-claude-sonnet-4-agentic`
- **Gemini**: `gemini-3-flash-preview`, `gemini-3-pro-preview`, `gemini-2.5-pro`, `gemini-2.5-flash`

## Related Documents

- [Project Overview](./project-overview-pdr.md)
- [System Architecture](./system-architecture.md)
- [Code Standards](./code-standards.md)
- [Project Roadmap](./project-roadmap.md)
- [Deployment Guide](./deployment-guide.md)
