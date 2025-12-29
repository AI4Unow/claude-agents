# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Modal.com Self-Improving Agents** using the **II Framework (Information & Implementation)**. Multi-agent system where agents read instructions from Modal Volume, execute tasks, and rewrite their own instructions based on experience.

See [docs/project-overview-pdr.md](docs/project-overview-pdr.md) for full requirements.

## Status

**Phase:** Production MVP
**Deploy URL:** https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run
**Last Updated:** Dec 29, 2025

### Key Features
- 7 circuit breakers (claude, exa, tavily, firebase, qdrant, telegram, gemini)
- 55 skills (local, remote, hybrid deployment)
- Gemini API integration (deep research, grounding, vision, thinking)
- Firebase Storage for research reports
- User tier system (guest, user, developer, admin)

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
modal run agents/main.py::test_gemini
modal run agents/main.py::test_grounding
modal run agents/main.py::test_deep_research
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
│  │ • /api/skill    │    │ • GitHub        │    │ • Circuits (7)  │        │
│  │ • /api/traces   │    │ • Data          │    │ • TraceContext  │        │
│  │ • /api/circuits │    │ • Content       │    │ • SkillRouter   │        │
│  │ • /api/reports  │    │                 │    │ • GeminiClient  │        │
│  └─────────────────┘    └─────────────────┘    └────────┬────────┘        │
│                                                         │                  │
│                              ┌──────────────────────────┼──────┐          │
│                              ▼                          ▼      ▼          │
│                    ┌─────────────────┐    ┌──────────┐  ┌──────────┐     │
│                    │  Modal Volume   │    │ Firebase │  │  Qdrant  │     │
│                    │  (55 skills)    │    │(L2+Store)│  │ (Memory) │     │
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
           │
           ▼
    ┌─────────────┐
    │  Gemini API │
    │ (Vertex AI) │
    └─────────────┘
```

**II Framework Pattern:** Each skill = `.md` (Information) + `.py` (Implementation)
- `.md` → Local source of truth, synced to Modal Volume on deploy
- `.py` → Modal Server (immutable after deploy)

**Reliability Patterns:**
- 7 circuit breakers (exa, tavily, firebase, qdrant, claude, telegram, gemini)
- L1 TTL cache + L2 Firebase for state persistence
- Execution tracing with tool-level timing
- Self-improvement loop with admin approval (local-first)
- User tier system (guest, user, developer, admin)

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
│   │   ├── services/              # External integrations (llm, firebase, qdrant, gemini)
│   │   ├── tools/                 # Tool system (web_search, code_exec, gemini_tools)
│   │   ├── core/                  # II Framework (state, resilience, trace, improvement)
│   │   └── skills/                # Skill registry
│   └── skills/                    # 55 skill info.md files
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

## Hybrid Skill Architecture

Skills use `deployment` field in YAML frontmatter to determine execution environment:

```
LOCAL SKILLS (8)                    REMOTE SKILLS (40+)
────────────────                    ──────────────────
Run via Claude Code                 Run on Modal.com
• canvas-design                     • telegram-chat, github, data, content
• docx, xlsx, pptx, pdf             • planning, debugging, code-review, research
• media-processing                  • backend-dev, frontend-dev, mobile-dev
• image-enhancer                    • ui-ux-pro-max, ui-styling, ai-multimodal
• video-downloader                  • gemini-deep-research, gemini-grounding
                                    • gemini-thinking, gemini-vision

HYBRID SKILLS (7)
─────────────────
Both local and remote
• better-auth, chrome-devtools, mcp-builder, repomix
• sequential-thinking, web-frameworks, webapp-testing

Why local?                          Why remote?
• Browser automation needed         • API-based, no browser needed
• Consumer IP required              • Always available 24/7
• TikTok, Facebook, YouTube, etc.   • Scalable serverless
```

**Skill frontmatter:**
```yaml
---
name: skill-name
description: Brief description
category: development|design|media|document
deployment: local|remote|both    # ← Determines execution environment
---
```

**Sync flow:** Claude Code → GitHub → Modal Volume (one-way)

## Skill Invocation Flow

### Remote Skills (Modal.com)
Direct execution on Modal serverless:
```
User Request → /api/skill → is_local_skill()=False → execute_skill_simple() → Response
```

### Local Skills (Firebase Task Queue)
Queued for local Claude Code execution:
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

**Key files:**
- `main.py:40-54` - `is_local_skill()` detection
- `main.py:272-291` - Queue to Firebase if local
- `src/services/firebase.py:563-827` - Task queue CRUD
- `scripts/local-executor.py` - Polling executor

**Run local executor:**
```bash
python3 agents/scripts/local-executor.py --poll --interval 30
```

## Self-Improvement Workflow (Local-First)

Skills self-improve through error analysis. Improvements flow: Local → GitHub → Modal.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. ERROR → Firebase    2. APPROVE → Firebase   3. APPLY → Local → Deploy  │
│                                                                              │
│  Modal/Local Error  →   Admin via Telegram  →   pull-improvements.py  →    │
│  status: pending        status: approved        Apply to agents/skills/     │
│                                                 git commit && git push      │
│                                                 modal deploy main.py        │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key scripts:**
```bash
# Pull and apply approved improvements from Firebase
python3 agents/scripts/pull-improvements.py           # Apply all
python3 agents/scripts/pull-improvements.py --dry-run # Preview
python3 agents/scripts/pull-improvements.py --list    # List pending

# Sync skills to Modal Volume
modal run agents/main.py --sync
```

**Key files:**
- `src/core/improvement.py` - Proposal generation & Firebase storage
- `scripts/pull-improvements.py` - Local application script
- `main.py:sync_skills_from_local()` - Deploy-time sync

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/health` | Health check with circuit status |
| `/webhook/telegram` | Telegram bot webhook |
| `/webhook/github` | GitHub webhook |
| `/api/skill` | Execute skill (simple/routed/orchestrated) |
| `/api/skills` | List skills with deployment info |
| `/api/task/{id}` | Get local task status/result |
| `/api/reports` | List user research reports |
| `/api/reports/{id}` | Get report download URL |
| `/api/reports/{id}/content` | Get report content |
| `/api/traces` | Execution traces (developer+) |
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
modal secret create gcp-credentials GCP_PROJECT_ID=... GCP_LOCATION=us-central1 GOOGLE_APPLICATION_CREDENTIALS_JSON=...
```
