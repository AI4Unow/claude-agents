# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Modal.com Self-Improving Agents** using the **II Framework (Information & Implementation)**. Multi-agent system where agents read instructions from Modal Volume, execute tasks, and rewrite their own instructions based on experience.

See [docs/project-overview-pdr.md](docs/project-overview-pdr.md) for full requirements.

## Status

**Phase:** Production MVP
**Deploy URL:** https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run
**Last Updated:** Dec 28, 2025

## Build & Development Commands

```bash
# Install Modal CLI
pip install modal
modal setup

# Deploy to Modal
modal deploy agents/main.py

# Local development
modal serve agents/main.py

# View logs
modal app logs claude-agents

# Test services
modal run agents/main.py::test_llm
modal run agents/main.py::test_firebase
modal run agents/main.py::test_qdrant
```

## Architecture

See [docs/system-architecture.md](docs/system-architecture.md) for full architecture.

```
┌───────────────────────────────────────────────────────────────────────────┐
│                          MODAL CLOUD                                       │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│  │ FastAPI Server  │───►│     Agents      │───►│  Core Framework │        │
│  │                 │    │                 │    │                 │        │
│  │ • /webhook/*    │    │ • Telegram      │    │ • StateManager  │        │
│  │ • /api/skill    │    │ • GitHub        │    │ • Circuits (6)  │        │
│  │ • /api/traces   │    │ • Data          │    │ • TraceContext  │        │
│  │ • /api/circuits │    │ • Content       │    │ • SkillRouter   │        │
│  └─────────────────┘    └─────────────────┘    └────────┬────────┘        │
│                                                         │                  │
│                              ┌──────────────────────────┼──────┐          │
│                              ▼                          ▼      ▼          │
│                    ┌─────────────────┐    ┌──────────┐  ┌──────────┐     │
│                    │  Modal Volume   │    │ Firebase │  │  Qdrant  │     │
│                    │  (24 skills)    │    │(L2 State)│  │ (Memory) │     │
│                    └─────────────────┘    └──────────┘  └──────────┘     │
│                                                                            │
└───────────────────────────────────────────────────────────────────────────┘
                                    │
           ┌────────────────────────┼────────────────────────┐
           ▼                        ▼                        ▼
    ┌─────────────┐          ┌─────────────┐          ┌─────────────┐
    │  Claude API │          │  Exa/Tavily │          │  Telegram   │
    │ (Anthropic) │          │ (Web Search)│          │   Bot API   │
    └─────────────┘          └─────────────┘          └─────────────┘
```

**II Framework Pattern:** Each skill = `.md` (Information) + `.py` (Implementation)
- `.md` → Modal Volume (mutable, self-improving)
- `.py` → Modal Server (immutable after deploy)

**Reliability Patterns:**
- 6 circuit breakers (exa, tavily, firebase, qdrant, claude, telegram)
- L1 TTL cache + L2 Firebase for state persistence
- Execution tracing with tool-level timing
- Self-improvement loop with admin approval

**Data Flow:**
```
Request → Webhook → Agentic Loop → Tool Execution → Response
                         │               │
                         ▼               ▼
                    L1 Cache ←→     Circuit Breakers
                         │
                    L2 Firebase
```

## Project Structure

```
./
├── agents/                        # Main codebase
│   ├── main.py                    # Modal app entry point
│   ├── src/
│   │   ├── agents/                # Agent implementations
│   │   ├── services/              # External integrations (llm, firebase, qdrant)
│   │   ├── tools/                 # Tool system (web_search, code_exec, etc.)
│   │   ├── core/                  # II Framework (state, resilience, trace, improvement)
│   │   └── skills/                # Skill registry
│   └── skills/                    # 24 skill info.md files
├── docs/                          # Documentation
│   ├── project-overview-pdr.md
│   ├── system-architecture.md
│   ├── code-standards.md
│   ├── codebase-summary.md
│   ├── project-roadmap.md
│   └── deployment-guide.md
├── plans/                         # Implementation plans
└── README.md
```

## Code Standards

See [docs/code-standards.md](docs/code-standards.md) for conventions.

**Key patterns:**
- Use `structlog` for logging
- Circuit breakers for external services
- TraceContext for execution tracing
- Progressive disclosure for skill loading
- L1 TTL cache + L2 Firebase for state

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/health` | Health check with circuit status |
| `/webhook/telegram` | Telegram bot webhook |
| `/webhook/github` | GitHub webhook |
| `/api/skill` | Execute skill (5 modes) |
| `/api/traces` | Execution traces (admin) |
| `/api/circuits` | Circuit breaker status |

## Secrets Required

```bash
modal secret create anthropic-credentials ANTHROPIC_API_KEY=...
modal secret create telegram-credentials TELEGRAM_BOT_TOKEN=...
modal secret create firebase-credentials FIREBASE_PROJECT_ID=... FIREBASE_CREDENTIALS_JSON=...
modal secret create qdrant-credentials QDRANT_URL=... QDRANT_API_KEY=...
modal secret create exa-credentials EXA_API_KEY=...
modal secret create tavily-credentials TAVILY_API_KEY=...
modal secret create admin-credentials ADMIN_TELEGRAM_ID=... ADMIN_API_TOKEN=...
```
