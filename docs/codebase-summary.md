# Codebase Summary

## Current Status

**Phase:** Production MVP
**Deploy URL:** https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run
**Last Updated:** Dec 28, 2025

Fully deployed II Framework agents on Modal.com with:
- 6 circuit breakers (exa, tavily, firebase, qdrant, claude, telegram)
- Execution tracing with tool-level timing
- Self-improvement loop with Telegram admin approval
- Skill categorization (local vs remote deployment)
- State management with L1/L2 caching

## Repository Structure

```
./
├── CLAUDE.md                      # Claude Code project instructions
├── README.md                      # Project readme
├── firebase.json                  # Firebase hosting config
├── docs/                          # Documentation
│   ├── project-overview-pdr.md
│   ├── system-architecture.md
│   ├── code-standards.md
│   ├── codebase-summary.md
│   ├── project-roadmap.md
│   └── deployment-guide.md
├── plans/                         # Implementation plans
│   ├── 251226-1500-modal-claude-agents/
│   ├── 251227-0629-agent-reliability-improvements/
│   ├── 251227-1234-smart-chatbot-tools/
│   ├── 251227-1308-additional-bot-tools/
│   ├── 251227-1355-skills-deployment-audit/
│   ├── 251227-1528-unified-ii-framework/
│   └── reports/
└── agents/                        # Main codebase
    ├── main.py                    # Modal app entry point (782 lines)
    ├── modal.toml                 # Modal configuration
    ├── requirements.txt           # Python dependencies
    ├── src/
    │   ├── config.py              # Environment configuration
    │   ├── agents/                # Agent implementations
    │   ├── services/              # External service integrations
    │   ├── tools/                 # Tool system
    │   ├── core/                  # II Framework core components
    │   ├── skills/                # Skill registry
    │   └── utils/                 # Utilities (logging)
    ├── skills/                    # 25+ skill info.md files
    ├── scripts/                   # Utility scripts
    └── tests/                     # Test files
```

## Key Components

### Entry Point (main.py - 1107 lines)

The main Modal app defining:
- FastAPI web application with webhook handlers
- TelegramChatAgent class with @enter hook for cache warming
- 4 specialized agents (Telegram, GitHub, Data, Content)
- Skill API with 5 execution modes
- Skill terminal commands (/skill, /run, /mode)
- Cron jobs for scheduled tasks

### Agents (src/agents/)

| File | Purpose | Trigger |
|------|---------|---------|
| `base.py` | Base agent class | - |
| `content_generator.py` | Content generation/transformation | HTTP API + commands |
| `data_processor.py` | Data processing & analytics | Cron (daily) |
| `github_automation.py` | GitHub repo automation | Cron (hourly) + webhook |

### Services (src/services/)

| File | Purpose |
|------|---------|
| `agentic.py` | Agentic loop with tool execution + conversation persistence |
| `llm.py` | Claude API client (Anthropic via ai4u.now proxy) |
| `firebase.py` | Firebase Firestore client (507 lines) |
| `qdrant.py` | Qdrant vector database client (617 lines) |
| `embeddings.py` | Embedding generation |
| `telegram.py` | Telegram message utilities |

### Tools (src/tools/)

| File | Tool | Purpose |
|------|------|---------|
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
| `state.py` | 372 | Unified StateManager with L1 TTL cache + L2 Firebase |
| `resilience.py` | 270 | Circuit breakers (6 services) + retry decorator |
| `trace.py` | 200 | Execution tracing with TraceContext, ToolTrace |
| `improvement.py` | 380 | Self-improvement service with Telegram approval |
| `orchestrator.py` | 300 | Multi-skill task orchestration |
| `evaluator.py` | 287 | Quality evaluation and optimization |
| `context_optimization.py` | 283 | Context compaction and optimization |
| `chain.py` | 243 | Sequential skill pipeline execution |
| `router.py` | 160 | Semantic skill routing via Qdrant |

#### New Components

**Resilience (resilience.py)**
- CircuitBreaker class with states: CLOSED, OPEN, HALF_OPEN
- Pre-configured circuits: exa, tavily, firebase, qdrant, claude, telegram
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

### Skill Registry (src/skills/)

| File | Purpose |
|------|---------|
| `registry.py` | Progressive disclosure skill loading |

Key classes:
- `SkillSummary` - Minimal skill info (Layer 1)
- `Skill` - Full skill content (Layer 2)
- `SkillRegistry` - Discovery, loading, memory update

### Skills (agents/skills/)

24 skills organized by category with deployment type:

**Local Only (8):** Require local execution
- `canvas-design/` - Canvas design
- `docx/` - Word documents (with scripts/)
- `image-enhancer/` - Image enhancement
- `media-processing/` - Media conversion (with scripts/)
- `pdf/` - PDF processing (with scripts/)
- `pptx/` - PowerPoint (with scripts/)
- `video-downloader/` - Video downloading
- `xlsx/` - Excel spreadsheets

**Remote (16):** Deployed to Modal
- Agent: `telegram-chat/`, `github/`, `data/`, `content/`
- Development: `planning/`, `debugging/`, `code-review/`, `research/`, `backend-development/`, `frontend-development/`, `mobile-development/`
- Design: `ui-ux-pro-max/` (with scripts/), `ui-styling/` (with scripts/)
- AI: `ai-multimodal/` (with scripts/), `ai-artist/`

## Technology Stack

| Layer | Technology | Version |
|-------|------------|---------|
| Runtime | Modal.com (Python 3.11) | modal>=0.60.0 |
| Web Framework | FastAPI | >=0.109.0 |
| AI | Anthropic Claude | anthropic>=0.40.0 |
| Vector DB | Qdrant Cloud | qdrant-client>=1.7.0 |
| State Store | Firebase Firestore | firebase-admin>=6.4.0 |
| Chat Platform | Telegram | python-telegram-bot>=21.0 |
| GitHub | PyGithub | >=2.1.0 |
| Web Search | Exa + Tavily | exa-py>=1.0.0, tavily-python>=0.3.0 |
| Document Processing | python-docx, openpyxl, python-pptx, pypdf | Various |
| Logging | structlog | >=24.1.0 |

## Development Workflow

1. **Local Development**
   - Edit code in `agents/` directory
   - Test with `modal serve agents/main.py`

2. **Deployment**
   - `modal deploy agents/main.py`
   - Skills sync to Modal Volume

3. **Monitoring**
   - `modal app logs claude-agents`
   - Firebase console for state
   - Qdrant dashboard for vectors

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check with circuit breaker status |
| `/webhook/telegram` | POST | Telegram bot webhook |
| `/webhook/github` | POST | GitHub event webhook |
| `/api/skill` | POST | Execute skill (5 modes) |
| `/api/skills` | GET | List available skills |
| `/api/content` | POST | Content generation |
| `/api/traces` | GET | List execution traces (admin) |
| `/api/traces/{id}` | GET | Get single trace (admin) |
| `/api/circuits` | GET | Get circuit breaker status (admin) |
| `/api/circuits/reset` | POST | Reset all circuits (admin) |

## Telegram Bot Commands

- `/start` - Welcome message
- `/help` - Show commands
- `/status` - Agent status
- `/clear` - Clear conversation history
- `/skill <name>` - Execute skill
- `/run <name>` - Run skill directly
- `/mode <simple|agentic>` - Switch execution mode
- `/translate <text>` - Translate to English
- `/summarize <text>` - Summarize text
- `/rewrite <text>` - Improve text

## Related Documents

- [Project Overview](./project-overview-pdr.md)
- [System Architecture](./system-architecture.md)
- [Code Standards](./code-standards.md)
- [Project Roadmap](./project-roadmap.md)
- [Deployment Guide](./deployment-guide.md)
