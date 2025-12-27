# Project Overview - Product Development Requirements

## Vision

Deploy self-improving AI agents on Modal.com using the **II Framework (Information & Implementation)**. Agents collaborate 24/7 for chat automation, GitHub workflows, data processing, and content generation.

## Goals

1. **Self-Improving Agents** - Agents read/write their own instructions, learning from errors
2. **Cost-Effective** - $40-60/month budget target
3. **Low Latency** - <2s response for Zalo chat (platform requirement)
4. **Scalable** - Pay-per-use serverless architecture

## User Stories

| As a | I want to | So that |
|------|-----------|---------|
| User | Chat via Zalo OA | Get AI assistance on mobile |
| Developer | Automate GitHub tasks | Reduce manual repo management |
| Content Creator | Generate reports/content | Save time on writing |
| Data Analyst | Schedule data processing | Automate recurring analysis |

## Success Criteria

- [ ] Skills deploy with one command (`modal deploy`)
- [ ] Agents read/write info.md from Volume
- [ ] Self-improvement loop works
- [ ] Zalo webhook responds <2 seconds
- [ ] Agents communicate via Firebase
- [ ] Vector memory persists in Qdrant
- [ ] Monthly cost <$60

## Phase Overview

| Phase | Description | Effort |
|-------|-------------|--------|
| 1 | Modal Setup & II Framework | 3h |
| 2 | Firebase Integration | 2h |
| 3 | Qdrant Cloud Setup | 2h |
| 4 | Vercel Edge Webhooks | 2h |
| 5 | Zalo Chat Agent | 3h |
| 6 | GitHub Agent | 3h |
| 7 | Data & Content Agents | 3h |
| 8 | Testing & Deployment | 2h |

**Total Estimated Effort:** 20h

## The II Framework

Each skill = Information (.md) + Implementation (.py)

```
INFORMATION (.md)              IMPLEMENTATION (.py)
─────────────────              ──────────────────
• Instructions                 • Python code
• Memory of past runs          • Tool functions
• Learned improvements         • LLM API calls
• Error history                • Integrations

MUTABLE at runtime             IMMUTABLE after deploy
→ Modal Volume                 → Modal Server
```

## Dependencies

- Modal.com account
- Vercel account (free tier)
- Firebase project (free tier)
- Qdrant Cloud (Asia region, ~$25/mo)
- Zalo Official Account
- Anthropic API key

## Related Documents

- [System Architecture](./system-architecture.md)
- [Code Standards](./code-standards.md)
- [Codebase Summary](./codebase-summary.md)
- Implementation Plans: `plans/251226-1500-modal-claude-agents/`
