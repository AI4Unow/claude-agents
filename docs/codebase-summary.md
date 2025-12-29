# Codebase Summary

## Current Status

**Phase:** Production MVP
**Deploy URL:** https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run
**Last Updated:** Dec 29, 2025

Fully deployed II Framework agents on Modal.com with:
- 7 circuit breakers (exa, tavily, firebase, qdrant, claude, telegram, gemini)
- Execution tracing with tool-level timing
- Self-improvement loop with Telegram admin approval
- 55 skills (local, remote, hybrid deployment)
- State management with L1/L2 caching
- Gemini API integration for research, grounding, vision, thinking
- Firebase Storage for research reports
- User tier system (guest, user, developer, admin)

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
│   ├── codebase-summary.md
│   ├── project-roadmap.md
│   └── deployment-guide.md
├── plans/                         # Implementation plans
└── agents/                        # Main codebase
    ├── main.py                    # Modal app entry point (~2500 lines)
    ├── modal.toml                 # Modal configuration
    ├── requirements.txt           # Python dependencies
    ├── src/
    │   ├── agents/                # Agent implementations
    │   ├── services/              # External service integrations
    │   ├── tools/                 # Tool system
    │   ├── core/                  # II Framework core components
    │   ├── skills/                # Skill registry
    │   └── utils/                 # Utilities (logging)
    ├── skills/                    # 55 skill info.md files
    ├── scripts/                   # Utility scripts
    └── tests/                     # Test files
```

## Key Components

### Entry Point (main.py)

The main Modal app defining:
- FastAPI web application with webhook handlers
- TelegramChatAgent class with @enter hook for cache warming
- 4 specialized agents (Telegram, GitHub, Data, Content)
- Skill API with execution modes (simple, routed, orchestrated)
- User tier system with permission-based commands
- Reports API for Firebase Storage access
- Cron jobs for scheduled tasks

### Agents (src/agents/)

| File | Purpose | Trigger |
|------|---------|---------|
| `base.py` | Base agent class | - |
| `content_generator.py` | Content generation/transformation | HTTP API + commands |
| `data_processor.py` | Data processing & analytics | Cron (daily) |
| `github_automation.py` | GitHub repo automation | Cron (hourly) + webhook |

### Services (src/services/)

| File | Lines | Purpose |
|------|-------|---------|
| `firebase.py` | ~1200 | Firestore + Storage (state, tiers, tasks, reports, reminders) |
| `gemini.py` | 441 | GeminiClient with Vertex AI SDK (chat, research, grounding, vision) |
| `llm.py` | 200 | Claude API client (Anthropic via ai4u.now proxy) |
| `agentic.py` | 260 | Agentic loop with tool execution + conversation persistence |
| `qdrant.py` | 617 | Qdrant vector database client |
| `telegram.py` | 400 | Telegram message utilities + formatters |
| `embeddings.py` | 80 | Embedding generation |
| `media.py` | 127 | Media processing utilities |

### Tools (src/tools/)

| File | Tool | Purpose |
|------|------|---------|
| `gemini_tools.py` | Gemini skills | Deep research, grounding, thinking, vision handlers |
| `web_search.py` | `web_search` | Web search via Exa + Tavily fallback |
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

#### Key Components

**Resilience (resilience.py)**
- CircuitBreaker class with states: CLOSED, OPEN, HALF_OPEN
- Pre-configured circuits: exa, tavily, firebase, qdrant, claude, telegram, gemini
- with_retry decorator for exponential backoff
- get_circuit_stats() for monitoring

**Tracing (trace.py)**
- TraceContext: Async context manager for execution spans
- ToolTrace: Individual tool call with timing/error status
- ExecutionTrace: Complete execution with all tool traces
- Firebase persistence for trace history

**Self-Improvement (improvement.py)**
- ImprovementProposal dataclass
- ImprovementService with rate limiting (3/hour/skill)
- Deduplication (24h window)
- LLM-based error reflection
- Telegram notifications with approve/reject buttons

**State Manager (state.py)**
- User tier caching with TTL
- Rate limiting per tier
- Session management
- Pending skill tracking
- User mode preferences (simple, routed, auto)

### Skills (agents/skills/)

55 skills organized by category with deployment type:

**Local Only (8):** Require local execution
- `canvas-design/`, `docx/`, `xlsx/`, `pptx/`, `pdf/`
- `image-enhancer/`, `media-processing/`, `video-downloader/`

**Remote (40+):** Deployed to Modal
- Agent: `telegram-chat/`, `github/`, `data/`, `content/`
- Development: `planning/`, `debugging/`, `code-review/`, `research/`
- Backend: `backend-development/`, `databases/`, `devops/`
- Frontend: `frontend-development/`, `frontend-design/`, `frontend-design-pro/`
- Mobile: `mobile-development/`
- Design: `ui-ux-pro-max/`, `ui-styling/`
- AI: `ai-multimodal/`, `ai-artist/`
- Gemini: `gemini-deep-research/`, `gemini-grounding/`, `gemini-thinking/`, `gemini-vision/`

**Hybrid (7):** Both local and remote
- `better-auth/`, `chrome-devtools/`, `mcp-builder/`, `repomix/`
- `sequential-thinking/`, `web-frameworks/`, `webapp-testing/`

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check with circuit breaker status |
| `/webhook/telegram` | POST | Telegram bot webhook |
| `/webhook/github` | POST | GitHub event webhook |
| `/api/skill` | POST | Execute skill (simple/routed/orchestrated) |
| `/api/skills` | GET | List available skills |
| `/api/task/{id}` | GET | Get local task status |
| `/api/reports` | GET | List user research reports |
| `/api/reports/{id}` | GET | Get report download URL |
| `/api/reports/{id}/content` | GET | Get report content |
| `/api/content` | POST | Content generation |
| `/api/traces` | GET | List execution traces (developer+) |
| `/api/traces/{id}` | GET | Get single trace (developer+) |
| `/api/circuits` | GET | Get circuit breaker status (developer+) |
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
| `/traces [limit]` | Developer+ | Recent execution traces |
| `/trace <id>` | Developer+ | Trace details |
| `/circuits` | Developer+ | Circuit breaker status |
| `/grant <id> <tier>` | Admin | Grant user tier |
| `/revoke <id>` | Admin | Revoke user access |
| `/admin reset <circuit>` | Admin | Reset circuit breaker |
| `/remind <time> <msg>` | Admin | Set reminder |
| `/reminders` | Admin | List reminders |

## Technology Stack

| Layer | Technology | Version |
|-------|------------|---------|
| Runtime | Modal.com (Python 3.11) | modal>=0.60.0 |
| Web Framework | FastAPI | >=0.109.0 |
| AI | Anthropic Claude | anthropic>=0.40.0 |
| AI | Google Gemini | google-genai>=1.0.0 |
| Vector DB | Qdrant Cloud | qdrant-client>=1.7.0 |
| State Store | Firebase Firestore + Storage | firebase-admin>=6.4.0 |
| Chat Platform | Telegram | python-telegram-bot>=21.0 |
| GitHub | PyGithub | >=2.1.0 |
| Web Search | Exa + Tavily | exa-py>=1.0.0, tavily-python>=0.3.0 |
| Document Processing | python-docx, openpyxl, python-pptx, pypdf | Various |
| Logging | structlog | >=24.1.0 |

## Related Documents

- [Project Overview](./project-overview-pdr.md)
- [System Architecture](./system-architecture.md)
- [Code Standards](./code-standards.md)
- [Project Roadmap](./project-roadmap.md)
- [Deployment Guide](./deployment-guide.md)
