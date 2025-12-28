# Project Overview - Product Development Requirements

## Vision

Deploy self-improving AI agents on Modal.com using the **II Framework (Information & Implementation)**. Agents collaborate 24/7 for chat automation, GitHub workflows, data processing, and content generation.

## Status

**Phase:** Production MVP
**Deploy URL:** https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run
**Last Updated:** Dec 28, 2025

## Goals

1. **Self-Improving Agents** - Agents read/write their own instructions, learning from errors
2. **Cost-Effective** - $40-60/month budget target
3. **Low Latency** - <2s response for Telegram chat
4. **Scalable** - Pay-per-use serverless architecture
5. **Tool-Enabled** - Agents can use web search, code execution, memory search

## User Stories

| As a | I want to | So that | Status |
|------|-----------|---------|--------|
| User | Chat via Telegram | Get AI assistance on mobile | Done |
| Developer | Automate GitHub tasks | Reduce manual repo management | Done |
| Content Creator | Generate reports/content | Save time on writing | Done |
| Data Analyst | Schedule data processing | Automate recurring analysis | Done |
| Developer | Execute skills via API | Integrate with other systems | Done |

## Success Criteria

- [x] Skills deploy with one command (`modal deploy`)
- [x] Agents read/write info.md from Volume
- [x] Self-improvement loop architecture in place
- [x] Telegram webhook responds within timeout
- [x] Agents communicate via Firebase
- [x] Vector memory setup in Qdrant
- [x] Tool system with web search, code exec, etc.
- [x] Skill API with multiple execution modes
- [x] Circuit breakers for 6 external services
- [x] Execution tracing with tool-level timing
- [x] Self-improvement with Telegram admin approval
- [ ] Monthly cost <$60 (monitoring)

## Implemented Features

### Agents
- **Telegram Chat Agent** - Always-on (min_containers=1), handles user messages with tool access
- **GitHub Agent** - Hourly cron + webhook for repo automation
- **Data Agent** - Scheduled daily summary generation
- **Content Agent** - On-demand content generation/transformation

### State Management
- **StateManager** - Unified L1 TTL cache + L2 Firebase persistence
- **Thread-safe** - Double-check locking for singleton and cache operations
- **Conversation persistence** - Last 20 messages per user (24hr TTL)
- **Cache warming** - @enter hook preloads skills and sessions on container start

### Reliability & Observability
- **Circuit Breakers** - 6 circuits (Exa, Tavily, Firebase, Qdrant, Claude, Telegram)
- **Execution Tracing** - TraceContext with tool-level timing and error tracking
- **Self-Improvement** - LLM-based error reflection with Telegram admin approval
- **Retry Logic** - Exponential backoff with configurable thresholds

### Tools
- `web_search` - Exa (primary) + Tavily (fallback)
- `get_datetime` - Timezone-aware date/time
- `run_python` - Python code execution
- `read_webpage` - URL content fetching
- `search_memory` - Qdrant vector search

### Skill Execution Modes
- **Simple** - Direct skill execution
- **Routed** - Semantic routing to best skill
- **Orchestrated** - Multi-skill complex tasks
- **Chained** - Sequential skill pipeline
- **Evaluated** - Quality assessment included

### API Endpoints
- `/health` - Health check with circuit status
- `/webhook/telegram` - Telegram bot webhook
- `/webhook/github` - GitHub webhook
- `/api/skill` - Skill execution API
- `/api/skills` - List available skills
- `/api/content` - Content generation API
- `/api/traces` - Execution traces (admin)
- `/api/circuits` - Circuit breaker status (admin)

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

## Completed Implementation Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Modal Setup & II Framework | Done |
| 2 | Firebase Integration | Done |
| 3 | Qdrant Cloud Setup | Done |
| 4 | Webhook Handlers | Done |
| 5 | Telegram Chat Agent | Done |
| 6 | GitHub Agent | Done |
| 7 | Data & Content Agents | Done |
| 8 | Tool System | Done |
| 9 | Skill Routing & API | Done |
| 10 | State Management (L1/L2 caching) | Done |
| 11 | Reliability & Tracing | Done |
| 12 | Self-Improvement Loop | Done |

## Dependencies

- Modal.com account (deployed)
- Firebase project (free tier)
- Qdrant Cloud (configured)
- Telegram Bot (configured)
- Anthropic API key (configured)
- Exa API key (configured)
- Tavily API key (configured)
- GitHub token (configured)

## Related Documents

- [System Architecture](./system-architecture.md)
- [Code Standards](./code-standards.md)
- [Codebase Summary](./codebase-summary.md)
- [Project Roadmap](./project-roadmap.md)
- [Deployment Guide](./deployment-guide.md)
