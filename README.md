# Modal.com Self-Improving Agents

Multi-agent system using the **II Framework (Information & Implementation)** deployed on Modal.com. Agents read instructions from Modal Volume, execute tasks, and can self-improve by rewriting their instructions based on experience.

## Status

**Phase:** Production MVP
**Deploy URL:** https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run
**Last Updated:** Dec 30, 2025

### Key Features
- 7 circuit breakers (claude, exa, tavily, firebase, qdrant, telegram, gemini)
- Execution tracing with tool-level timing
- Self-improvement loop with Telegram admin approval
- 53 skills (8 local, 43 remote, 2 hybrid deployment)
- Gemini API integration (deep research, grounding, vision, thinking)
- Smart FAQ system with hybrid keyword+semantic matching
- User personalization (profiles, context, macros, activity learning)
- Gemini embeddings (gemini-embedding-001, 3072 dimensions)
- Firebase Storage for research reports + content downloads (24h links)
- User tier system (guest, user, developer, admin)
- Command Router pattern (decorator-based registration)
- PKM Second Brain (capture, organize, semantic search)
- WhatsApp Evolution API integration
- Stress test framework (Locust + chaos engineering)

## Agents

| Agent | Purpose | Trigger |
|-------|---------|---------|
| **Telegram Chat** | Primary user interface via Telegram | Webhook (always-on) |
| **GitHub** | Repository automation | Cron (hourly) + webhook |
| **Data** | Data processing & analytics | Scheduled (daily) |
| **Content** | Content generation & transformation | On-demand |

## Technology Stack

- **Runtime:** Modal.com (Python 3.11, serverless)
- **Web Framework:** FastAPI
- **AI:** Anthropic Claude API, Google Gemini (Vertex AI)
- **Embeddings:** Gemini gemini-embedding-001 (3072 dim)
- **Vector Memory:** Qdrant Cloud
- **State Store:** Firebase Firestore + Storage
- **Chat Platform:** Telegram Bot
- **Web Search:** Exa (primary) + Tavily (fallback)

## Quick Start

```bash
# Install Modal CLI
pip install modal
modal setup

# Deploy
cd agents
modal deploy main.py

# View logs
modal app logs claude-agents
```

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check with circuit status |
| `/webhook/telegram` | POST | Telegram bot webhook |
| `/webhook/whatsapp` | POST | WhatsApp Evolution API webhook |
| `/webhook/github` | POST | GitHub webhook |
| `/api/skill` | POST | Execute skill (simple/routed/orchestrated) |
| `/api/skills` | GET | List available skills |
| `/api/task/{id}` | GET | Get local task status |
| `/api/reports` | GET | List user research reports |
| `/api/reports/{id}` | GET | Get report download URL |
| `/api/reports/{id}/content` | GET | Get report content |
| `/api/traces` | GET | Execution traces (developer+) |
| `/api/circuits` | GET | Circuit breaker status |

## Telegram Commands

| Command | Tier | Description |
|---------|------|-------------|
| `/start` | All | Welcome message |
| `/help` | All | Show available commands |
| `/status` | All | Check status and tier |
| `/skills` | All | Browse skills (menu) |
| `/skill <name> <task>` | All | Execute skill |
| `/mode <simple\|routed\|auto>` | All | Set execution mode |
| `/task <id>` | User+ | Check task status |
| `/traces` | Developer+ | Recent execution traces |
| `/circuits` | Developer+ | Circuit breaker status |
| `/grant <id> <tier>` | Admin | Grant user tier |
| `/revoke <id>` | Admin | Revoke user access |

## Skill Architecture

53 skills with deployment types:
- **Local** (8): canvas-design, docx, xlsx, pptx, pdf, media-processing, image-enhancer, video-downloader
- **Remote** (43): planning, debugging, research, code-review, gemini-*, backend-dev, frontend-dev, mobile-dev, ui-ux-pro-max, ai-multimodal, automation skills
- **Hybrid** (2): repomix, sequential-thinking

### Gemini Skills (New)
| Skill | Description |
|-------|-------------|
| `gemini-deep-research` | Multi-step agentic research with citations |
| `gemini-grounding` | Real-time factual queries via Google Search |
| `gemini-thinking` | Configurable reasoning depth |
| `gemini-vision` | Image and document analysis |

## Project Structure

```
agents/
├── main.py                    # Modal app entry point (~2,000 lines)
├── api/                       # FastAPI routes (modular)
│   ├── routes/                # Route handlers
│   │   ├── health.py          # Health check
│   │   ├── telegram.py        # Telegram webhook
│   │   ├── whatsapp.py        # WhatsApp webhook
│   │   └── skills.py          # Skill execution
├── commands/                  # Command Router pattern
│   ├── base.py                # Router decorators
│   └── *.py                   # Command handlers
├── src/
│   ├── agents/                # Agent implementations (4)
│   ├── services/              # External integrations
│   │   ├── firebase/          # Modular Firebase (12 modules)
│   │   ├── gemini.py          # Gemini API client
│   │   ├── llm.py             # Claude API
│   │   └── evolution.py       # WhatsApp Evolution API
│   ├── tools/                 # Tool system (8 tools)
│   │   ├── gemini_tools.py    # Gemini skill handlers
│   │   ├── web_search.py      # Exa/Tavily
│   │   └── ...
│   └── core/                  # II Framework (12 modules)
│       ├── state.py           # L1 cache + L2 Firebase
│       ├── faq.py             # Smart FAQ
│       ├── resilience.py      # 7 circuit breakers
│       ├── orchestrator.py    # Multi-skill execution
│       └── improvement.py     # Self-improvement
├── skills/                    # 53 skill info.md files
├── scripts/                   # Utility scripts
└── tests/                     # 37 test files (unit + stress)
docs/
├── project-overview-pdr.md
├── system-architecture.md
├── codebase-summary.md        # Comprehensive overview
├── code-standards.md
├── project-roadmap.md
└── deployment-guide.md
```

## Secrets Required

```bash
modal secret create anthropic-credentials ANTHROPIC_API_KEY=...
modal secret create telegram-credentials TELEGRAM_BOT_TOKEN=...
modal secret create firebase-credentials FIREBASE_PROJECT_ID=... FIREBASE_CREDENTIALS_JSON=...
modal secret create qdrant-credentials QDRANT_URL=... QDRANT_API_KEY=...
modal secret create exa-credentials EXA_API_KEY=...
modal secret create tavily-credentials TAVILY_API_KEY=...
modal secret create admin-credentials ADMIN_TELEGRAM_ID=... ADMIN_API_TOKEN=...
modal secret create gcp-credentials GCP_PROJECT_ID=... GOOGLE_APPLICATION_CREDENTIALS_JSON=...
```

## Documentation

- [Project Overview & PDR](docs/project-overview-pdr.md)
- [System Architecture](docs/system-architecture.md)
- [Code Standards](docs/code-standards.md)
- [Codebase Summary](docs/codebase-summary.md)
- [Project Roadmap](docs/project-roadmap.md)
- [Deployment Guide](docs/deployment-guide.md)

## License

Private repository.
