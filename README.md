# Modal.com Self-Improving Agents

Multi-agent system using the **II Framework (Information & Implementation)** deployed on Modal.com. Agents read instructions from Modal Volume, execute tasks, and can self-improve by rewriting their instructions based on experience.

## Status

**Phase:** Production MVP
**Deploy URL:** https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run
**Last Updated:** Dec 28, 2025

### Key Features
- 6 circuit breakers for external service resilience
- Execution tracing with tool-level timing
- Self-improvement loop with Telegram admin approval
- 24 skills (8 local, 16 remote)
- State management with L1/L2 caching

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SKILL = Information (.md) + Implementation (.py)          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INFORMATION (.md)              IMPLEMENTATION (.py)                         │
│  • Instructions                 • Python execution code                      │
│  • Memory of past runs          • Tool functions                             │
│  • Learned improvements         • LLM API calls                              │
│  • Error history                • External integrations                      │
│                                                                              │
│  MUTABLE at runtime             IMMUTABLE after deploy                       │
│  → Modal Volume                 → Modal Server                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Agents

| Agent | Purpose | Trigger |
|-------|---------|---------|
| **Telegram Chat** | Primary user interface via Telegram | Webhook (always-on) |
| **GitHub** | Repository automation | Cron (hourly) + webhook |
| **Data** | Data processing & analytics | Scheduled (daily) |
| **Content** | Content generation & transformation | On-demand |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              SYSTEM ARCHITECTURE                                     │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  USERS                           MODAL CLOUD                      EXTERNAL SERVICES │
│  ─────                           ───────────                      ───────────────── │
│                                                                                      │
│  ┌──────────┐                   ┌─────────────────────────────┐                     │
│  │ Telegram │◄──────────────────│     MODAL SERVER            │                     │
│  │   Bot    │   webhook         │                             │                     │
│  └──────────┘                   │  ┌───────────────────────┐  │   ┌─────────────┐  │
│                                 │  │   FastAPI Web App     │  │   │  Claude API │  │
│  ┌──────────┐                   │  │   ────────────────    │  │◄─►│  (Anthropic)│  │
│  │  GitHub  │◄──────────────────│  │   /webhook/telegram   │  │   └─────────────┘  │
│  │  Repos   │   webhook         │  │   /webhook/github     │  │                     │
│  └──────────┘                   │  │   /api/skill          │  │   ┌─────────────┐  │
│                                 │  │   /api/traces         │  │◄─►│  Exa/Tavily │  │
│  ┌──────────┐                   │  │   /api/circuits       │  │   │ (Web Search)│  │
│  │   API    │◄──────────────────│  └───────────────────────┘  │   └─────────────┘  │
│  │ Clients  │   REST            │                             │                     │
│  └──────────┘                   │  ┌───────────────────────┐  │                     │
│                                 │  │   AGENTS              │  │                     │
│                                 │  │   ──────              │  │                     │
│                                 │  │   • TelegramChat      │  │                     │
│                                 │  │   • GitHub            │  │                     │
│                                 │  │   • Data              │  │                     │
│                                 │  │   • Content           │  │                     │
│                                 │  └───────────────────────┘  │                     │
│                                 │              │              │                     │
│                                 │  ┌───────────▼───────────┐  │                     │
│                                 │  │   CORE FRAMEWORK      │  │                     │
│                                 │  │   ──────────────      │  │                     │
│                                 │  │   • StateManager      │◄─┼──► Firebase        │
│                                 │  │   • CircuitBreakers   │  │    (L2 State)      │
│                                 │  │   • TraceContext      │  │                     │
│                                 │  │   • SkillRouter       │◄─┼──► Qdrant Cloud    │
│                                 │  │   • ImprovementSvc    │  │    (Vector Memory) │
│                                 │  └───────────────────────┘  │                     │
│                                 │              │              │                     │
│                                 │  ┌───────────▼───────────┐  │                     │
│                                 │  │   MODAL VOLUME        │  │                     │
│                                 │  │   ────────────        │  │                     │
│                                 │  │   24 skills (info.md) │  │                     │
│                                 │  │   Self-improving      │  │                     │
│                                 │  └───────────────────────┘  │                     │
│                                 └─────────────────────────────┘                     │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘

DATA FLOW
─────────
┌────────┐    ┌─────────┐    ┌──────────┐    ┌───────────┐    ┌──────────┐
│ Request│───►│ Webhook │───►│ Agentic  │───►│ Tool Exec │───►│ Response │
└────────┘    │ Handler │    │   Loop   │    │ (traced)  │    └──────────┘
              └─────────┘    └──────────┘    └───────────┘
                                  │               │
                                  ▼               ▼
                            ┌──────────┐    ┌──────────┐
                            │ L1 Cache │    │ Circuit  │
                            │ (Memory) │    │ Breakers │
                            └────┬─────┘    └──────────┘
                                 │ miss
                                 ▼
                            ┌──────────┐
                            │ Firebase │
                            │(L2 Store)│
                            └──────────┘
```

## Technology Stack

- **Runtime:** Modal.com (Python 3.11, serverless)
- **Web Framework:** FastAPI
- **AI:** Anthropic Claude API
- **Vector Memory:** Qdrant Cloud
- **State Store:** Firebase Firestore
- **Chat Platform:** Telegram Bot
- **Web Search:** Exa (primary) + Tavily (fallback)

## Project Structure

```
./
├── agents/                        # Main codebase
│   ├── main.py                    # Modal app entry point
│   ├── modal.toml                 # Modal config
│   ├── requirements.txt           # Python dependencies
│   ├── src/
│   │   ├── agents/                # Agent implementations
│   │   │   ├── base.py
│   │   │   ├── content_generator.py
│   │   │   ├── data_processor.py
│   │   │   └── github_automation.py
│   │   ├── services/              # External integrations
│   │   │   ├── agentic.py         # Agentic loop with conversation persistence
│   │   │   ├── llm.py             # Claude API client
│   │   │   ├── firebase.py
│   │   │   ├── qdrant.py
│   │   │   └── embeddings.py
│   │   ├── tools/                 # Tool system
│   │   │   ├── registry.py
│   │   │   ├── web_search.py
│   │   │   ├── web_reader.py
│   │   │   ├── code_exec.py
│   │   │   ├── datetime_tool.py
│   │   │   └── memory_search.py
│   │   ├── core/                  # II Framework core
│   │   │   ├── state.py           # StateManager (L1 cache + L2 Firebase)
│   │   │   ├── router.py          # Semantic skill routing
│   │   │   ├── orchestrator.py
│   │   │   ├── chain.py
│   │   │   └── evaluator.py
│   │   └── skills/
│   │       └── registry.py        # Progressive disclosure
│   ├── skills/                    # 24 skill info.md files
│   └── tests/
├── docs/                          # Documentation
│   ├── project-overview-pdr.md
│   ├── system-architecture.md
│   ├── code-standards.md
│   ├── codebase-summary.md
│   ├── project-roadmap.md
│   └── deployment-guide.md
└── plans/                         # Implementation plans
```

## Quick Start

```bash
# Install Modal CLI
pip install modal
modal setup

# Clone and deploy
git clone <repo>
cd agents

# Set up secrets
modal secret create anthropic-credentials ANTHROPIC_API_KEY=sk-ant-...
modal secret create telegram-credentials TELEGRAM_BOT_TOKEN=...
modal secret create firebase-credentials FIREBASE_PROJECT_ID=... FIREBASE_CREDENTIALS_JSON=...
modal secret create qdrant-credentials QDRANT_URL=... QDRANT_API_KEY=...
modal secret create exa-credentials EXA_API_KEY=...
modal secret create tavily-credentials TAVILY_API_KEY=...

# Deploy
modal deploy agents/main.py

# View logs
modal app logs claude-agents
```

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check with circuit status |
| `/webhook/telegram` | POST | Telegram bot webhook |
| `/webhook/github` | POST | GitHub webhook |
| `/api/skill` | POST | Execute skill (simple/routed/orchestrated/chained/evaluated) |
| `/api/skills` | GET | List available skills |
| `/api/content` | POST | Content generation API |
| `/api/traces` | GET | Execution traces (admin) |
| `/api/circuits` | GET | Circuit breaker status |

## Skill API Usage

```bash
# Simple skill execution
curl -X POST https://<modal-url>/api/skill \
  -H "Content-Type: application/json" \
  -d '{"skill": "planning", "task": "Create auth plan", "mode": "simple"}'

# Routed execution (auto-selects best skill)
curl -X POST https://<modal-url>/api/skill \
  -d '{"task": "Debug this error", "mode": "routed"}'
```

## Self-Improvement Loop

1. **Wake Up** - Cron or webhook trigger
2. **Read** - Load `info.md` from Modal Volume
3. **Execute** - Run task with LLM + tools
4. **Evaluate** - Check results
5. **Improve** - On error, LLM can rewrite `info.md`
6. **Sleep** - Wait for next trigger

## Available Tools

| Tool | Purpose |
|------|---------|
| `web_search` | Search web via Exa/Tavily |
| `get_datetime` | Get current date/time (timezone aware) |
| `run_python` | Execute Python code |
| `read_webpage` | Fetch and parse URL content |
| `search_memory` | Query Qdrant vector store |

## Cost Estimate

| Component | Monthly |
|-----------|---------|
| Modal compute | ~$15-20 |
| Qdrant Cloud | ~$25 |
| LLM API | ~$10-20 |
| Firebase | $0 (free tier) |
| **Total** | **~$40-60** |

## Documentation

- [Project Overview & PDR](docs/project-overview-pdr.md)
- [System Architecture](docs/system-architecture.md)
- [Code Standards](docs/code-standards.md)
- [Codebase Summary](docs/codebase-summary.md)
- [Project Roadmap](docs/project-roadmap.md)
- [Deployment Guide](docs/deployment-guide.md)

## License

Private repository.
