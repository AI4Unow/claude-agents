# Modal.com Self-Improving Agents

Multi-agent system using the **II Framework (Information & Implementation)** deployed on Modal.com. Agents are self-improving: they read instructions from Modal Volume, execute tasks, and rewrite their own instructions based on experience.

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
| **Zalo Chat** | Primary user interface via Zalo OA | Webhook (always-on) |
| **GitHub** | Repository automation | Cron + webhook |
| **Data** | Data processing & analytics | Scheduled |
| **Content** | Content generation | On-demand |

## Architecture

```
LOCAL                                MODAL CLOUD
─────                                ───────────
skills/                              ┌─────────────────────┐
├── zalo-chat/     modal deploy      │  MODAL SERVER       │
│   ├── info.md   ──────────────►    │  • agent code       │
│   └── agent.py                     │  • cron schedules   │
└── github/                          └─────────────────────┘
                                              │
                    ┌─────────────────────────┼─────────────────┐
                    ▼                         ▼                 ▼
          ┌─────────────────┐       ┌─────────────┐   ┌─────────────┐
          │  VERCEL EDGE    │       │   FIREBASE  │   │QDRANT CLOUD │
          │  (Webhooks)     │       │  (State)    │   │  (Memory)   │
          └─────────────────┘       └─────────────┘   └─────────────┘
```

## Technology Stack

- **Runtime:** Modal.com (Python 3.11, serverless)
- **Web Framework:** FastAPI
- **AI:** Anthropic Claude API
- **Vector Memory:** Qdrant Cloud (Asia region)
- **State Store:** Firebase Firestore
- **Embeddings:** Vertex AI
- **Chat Platform:** Zalo Official Account

## Project Structure

```
./
├── docs/                          # Documentation
│   ├── project-overview-pdr.md    # Product requirements
│   ├── system-architecture.md     # Architecture diagrams
│   ├── code-standards.md          # Coding conventions
│   └── codebase-summary.md        # Current status
├── plans/                         # Implementation plans
│   └── 251226-1500-modal-claude-agents/
│       ├── plan.md                # Master plan
│       └── phase-*.md             # Phase details
└── README.md
```

## Quick Start (Planned)

```bash
# Install Modal CLI
pip install modal
modal setup

# Clone and deploy
git clone <repo>
cd agents
modal deploy main.py

# View logs
modal app logs claude-agents
```

## Self-Improvement Loop

1. **Wake Up** - Cron or webhook trigger
2. **Read** - Load `info.md` from Modal Volume
3. **Execute** - Run task with LLM
4. **Evaluate** - Check results
5. **Improve** - On error, LLM rewrites `info.md`
6. **Sleep** - Wait for next trigger

## Cost Estimate

| Component | Monthly |
|-----------|---------|
| Modal compute | ~$15-20 |
| Qdrant Cloud | ~$25 |
| LLM API | ~$10-20 |
| Firebase | $0 |
| Vercel | $0 |
| **Total** | **~$40-60** |

## Documentation

- [Project Overview & PDR](docs/project-overview-pdr.md)
- [System Architecture](docs/system-architecture.md)
- [Code Standards](docs/code-standards.md)
- [Codebase Summary](docs/codebase-summary.md)

## Status

**Phase:** Planning - No code implemented yet

See `plans/` directory for detailed implementation plans.

## License

Private repository.
