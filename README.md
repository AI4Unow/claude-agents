# Modal.com Self-Improving Agents

Multi-agent system using the **II Framework (Information & Implementation)** deployed on Modal.com. Agents read instructions from Modal Volume, execute tasks, and can self-improve by rewriting their instructions based on experience.

## Status

**Phase:** Production MVP
**Deploy URL:** https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run
**Last Updated:** Dec 29, 2025

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
| `/api/skills` | GET | List available skills with deployment info |
| `/api/task/{id}` | GET | Get local task status and result |
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

## Hybrid Skill Architecture

Skills are categorized by deployment type using the `deployment` field in YAML frontmatter:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      HYBRID LOCAL + MODAL DEPLOYMENT                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  LOCAL (Claude Code)                    REMOTE (Modal.com)                   │
│  ───────────────────                    ──────────────────                   │
│  • Runs on your machine                 • Runs on Modal serverless           │
│  • Browser automation                   • API-based operations               │
│  • Consumer IP required                 • Always available                   │
│  • Desktop apps access                  • Scalable & cost-effective          │
│                                                                              │
│  ┌─────────────────────┐               ┌─────────────────────┐              │
│  │ 8 LOCAL SKILLS      │               │ 16 REMOTE SKILLS    │              │
│  ├─────────────────────┤               ├─────────────────────┤              │
│  │ • canvas-design     │               │ • telegram-chat     │              │
│  │ • docx              │               │ • github            │              │
│  │ • image-enhancer    │               │ • planning          │              │
│  │ • media-processing  │               │ • debugging         │              │
│  │ • pdf               │               │ • code-review       │              │
│  │ • pptx              │               │ • research          │              │
│  │ • video-downloader  │               │ • backend-dev       │              │
│  │ • xlsx              │               │ • frontend-dev      │              │
│  └─────────────────────┘               │ • mobile-dev        │              │
│                                        │ • ui-ux-pro-max     │              │
│  Why Local?                            │ • ui-styling        │              │
│  • TikTok, Facebook, YouTube           │ • ai-multimodal     │              │
│  • LinkedIn automation                 │ • ai-artist         │              │
│  • Desktop app control                 │ • data, content     │              │
│  • Browser with consumer IP            └─────────────────────┘              │
│                                                                              │
│  SYNC: Claude Code → GitHub → Modal Volume (one-way)                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Skill YAML Frontmatter

```yaml
---
name: skill-name
description: Brief description for routing
category: development|design|media|document
deployment: local|remote|both    # ← Determines where skill runs
---
```

## Skill Invocation Flow

### Remote Skills (Modal.com)
Remote skills execute directly on Modal serverless:

```
User Request → /api/skill → is_local_skill()=False → execute_skill_simple() → Response
```

**Example:**
```bash
curl -X POST https://<modal-url>/api/skill \
  -H "Content-Type: application/json" \
  -d '{"skill": "planning", "task": "Create auth plan", "mode": "simple"}'
```

### Local Skills (Firebase Task Queue)
Local skills are queued to Firebase and executed by Claude Code locally:

```
┌──────────────┐     ┌──────────────────┐     ┌────────────────────┐
│ User Request │────►│ Modal.com        │────►│ Firebase           │
│ (Telegram)   │     │ is_local_skill() │     │ task_queue         │
└──────────────┘     │ = True           │     │ status: pending    │
                     └──────────────────┘     └─────────┬──────────┘
                              │                         │
                     Notify: "Task queued"              │ Poll (30s)
                              │                         ▼
                     ┌────────▼─────────┐     ┌────────────────────┐
                     │ User notified    │◄────│ Claude Code        │
                     │ with result      │     │ local-executor.py  │
                     └──────────────────┘     └────────────────────┘
```

**Running Local Executor:**
```bash
# One-time execution
python3 agents/scripts/local-executor.py

# Continuous polling (30s interval)
python3 agents/scripts/local-executor.py --poll

# Custom interval
python3 agents/scripts/local-executor.py --poll --interval 60

# Execute specific task
python3 agents/scripts/local-executor.py --task <task_id>
```

**Task Queue API:**
```bash
# Check task status
curl https://<modal-url>/api/task/<task_id>
```

## Self-Improvement Loop (Local-First)

Skills self-improve through error analysis with admin approval. **Source of truth:** Local `agents/skills/` (Git-tracked).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   LOCAL-FIRST SELF-IMPROVEMENT FLOW                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. ERROR DETECTION        2. ADMIN APPROVAL      3. LOCAL APPLICATION      │
│  ──────────────────        ─────────────────      ────────────────────      │
│  Modal/Local Error    →    Telegram buttons   →   pull-improvements.py      │
│  ↓                         [Approve] [Reject]     ↓                         │
│  ImprovementService        ↓                      Apply to agents/skills/   │
│  ↓                         Firebase               ↓                         │
│  Firebase                  status: approved       Mark "applied"            │
│  status: pending                                                             │
│                                                                              │
│  4. SYNC TO MODAL                                                            │
│  ───────────────                                                             │
│  git commit && git push → modal deploy → sync_skills_from_local()           │
│  Skills bundled in image, synced to Modal Volume                            │
│  (Runtime Memory/Error History preserved)                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Improvement Commands

```bash
# Pull and apply approved improvements from Firebase
python3 agents/scripts/pull-improvements.py           # Apply all
python3 agents/scripts/pull-improvements.py --dry-run # Preview changes
python3 agents/scripts/pull-improvements.py --list    # List pending

# After applying improvements
git add agents/skills/ && git commit -m "chore: apply skill improvements"
git push
modal deploy agents/main.py

# Manual sync to Modal Volume
modal run agents/main.py --sync
```

### Key Files

| File | Purpose |
|------|---------|
| `src/core/improvement.py` | Proposal generation & Firebase storage |
| `scripts/pull-improvements.py` | Local application script |
| `main.py:sync_skills_from_local()` | Deploy-time sync to Volume |

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
