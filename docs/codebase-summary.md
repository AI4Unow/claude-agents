# Codebase Summary

## Current Status

**Phase:** Planning (no code implemented yet)

The project is in the planning phase with detailed implementation plans completed. No source code has been written.

## Repository Structure

```
./
├── CLAUDE.md              # Claude Code project instructions
├── docs/                  # Documentation (this folder)
│   ├── project-overview-pdr.md
│   ├── system-architecture.md
│   ├── code-standards.md
│   └── codebase-summary.md
├── plans/                 # Implementation plans
│   ├── 251226-1500-modal-claude-agents/
│   │   ├── plan.md                              # Master plan
│   │   ├── phase-01-project-setup-modal-config.md
│   │   ├── phase-02-firebase-integration.md
│   │   ├── phase-03-qdrant-vector-memory.md
│   │   ├── phase-04-vercel-edge-webhooks.md
│   │   ├── phase-05-zalo-chat-agent.md
│   │   ├── phase-06-github-agent.md
│   │   ├── phase-07-data-content-agents.md
│   │   └── phase-08-testing-deployment.md
│   └── reports/
│       └── brainstorm-251226-1500-modal-claude-agents-architecture.md
└── README.md
```

## Planned Project Structure

After implementation, the repository will have:

```
agents/
├── modal.toml
├── requirements.txt
├── main.py
├── src/
│   ├── config.py
│   ├── agents/
│   │   ├── base.py
│   │   ├── zalo_chat.py
│   │   ├── github_automation.py
│   │   ├── data_processor.py
│   │   └── content_generator.py
│   ├── services/
│   │   ├── firebase.py
│   │   ├── qdrant.py
│   │   ├── anthropic.py
│   │   └── embeddings.py
│   └── utils/
│       └── logging.py
├── skills/
│   └── (hot-reload skills)
└── tests/
```

## Key Components (Planned)

### Agents

| Agent | File | Purpose | Trigger |
|-------|------|---------|---------|
| Zalo Chat | `zalo_chat.py` | Primary interface | Webhook (always-on) |
| GitHub | `github_automation.py` | Repo automation | Cron + webhook |
| Data | `data_processor.py` | Data processing | Scheduled |
| Content | `content_generator.py` | Content generation | On-demand |

### Services

| Service | File | Purpose |
|---------|------|---------|
| Firebase | `firebase.py` | State, task queue |
| Qdrant | `qdrant.py` | Vector memory |
| Anthropic | `anthropic.py` | Claude API |
| Embeddings | `embeddings.py` | Vertex AI embeddings |

## Technology Stack

| Layer | Technology |
|-------|------------|
| Runtime | Modal.com (Python 3.11) |
| Web Framework | FastAPI |
| AI | Anthropic Claude API |
| Vector DB | Qdrant Cloud |
| State Store | Firebase Firestore |
| Embeddings | Vertex AI text-embedding-004 |
| Chat | python-zalo-bot |
| GitHub | PyGithub |

## Development Workflow

1. **Local Development**
   - Edit skills in `skills/` directory
   - Test with `modal serve main.py`

2. **Deployment**
   - `modal deploy main.py`
   - Skills sync to Modal Volume

3. **Monitoring**
   - `modal app logs claude-agents`
   - Firebase console for state
   - Qdrant dashboard for vectors

## Next Steps

1. Complete Phase 1: Modal project setup
2. Configure secrets and volume
3. Implement base agent class
4. Add Firebase and Qdrant integrations
5. Build Zalo Chat Agent first

## Related Documents

- [Project Overview](./project-overview-pdr.md)
- [System Architecture](./system-architecture.md)
- [Code Standards](./code-standards.md)
