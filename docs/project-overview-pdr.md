# Project Overview - Product Development Requirements

## Vision

Deploy self-improving AI agents on Modal.com using the **II Framework (Information & Implementation)**. Agents collaborate 24/7 for chat automation, GitHub workflows, data processing, and content generation.

## Status

**Phase:** Production MVP
**Deploy URL:** https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run
**Last Updated:** Dec 29, 2025

## Goals

1. **Self-Improving Agents** - Agents read/write their own instructions, learning from errors
2. **Cost-Effective** - $40-60/month budget target
3. **Low Latency** - <2s response for Telegram chat
4. **Scalable** - Pay-per-use serverless architecture
5. **Tool-Enabled** - Agents can use web search, code execution, memory search
6. **Multi-Model** - Claude + Gemini API integration

## User Stories

| As a | I want to | So that | Status |
|------|-----------|---------|--------|
| User | Chat via Telegram | Get AI assistance on mobile | Done |
| Developer | Automate GitHub tasks | Reduce manual repo management | Done |
| Content Creator | Generate reports/content | Save time on writing | Done |
| Data Analyst | Schedule data processing | Automate recurring analysis | Done |
| Developer | Execute skills via API | Integrate with other systems | Done |
| Researcher | Run deep research | Get comprehensive reports with citations | Done |
| Admin | Manage user tiers | Control access to features | Done |

## Success Criteria

- [x] Skills deploy with one command (`modal deploy`)
- [x] Agents read/write info.md from Volume
- [x] Self-improvement loop architecture in place
- [x] Telegram webhook responds within timeout
- [x] Agents communicate via Firebase
- [x] Vector memory setup in Qdrant
- [x] Tool system with web search, code exec, etc.
- [x] Skill API with multiple execution modes
- [x] Circuit breakers for 7 external services
- [x] Execution tracing with tool-level timing
- [x] Self-improvement with Telegram admin approval
- [x] Gemini API integration (research, grounding, vision, thinking)
- [x] Firebase Storage for research reports
- [x] User tier system (guest, user, developer, admin)
- [x] Stress test framework (Locust + chaos engineering)
- [x] 53 skills deployed (8 local, 40+ remote, 7 hybrid)
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
- **User tiers** - guest, user, developer, admin with rate limits

### Reliability & Observability
- **Circuit Breakers** - 7 circuits (Exa, Tavily, Firebase, Qdrant, Claude, Telegram, Gemini)
- **Execution Tracing** - TraceContext with tool-level timing and error tracking
- **Self-Improvement** - LLM-based error reflection with Telegram admin approval
- **Retry Logic** - Exponential backoff with configurable thresholds

### Tools
- `web_search` - Exa (primary) + Tavily (fallback)
- `get_datetime` - Timezone-aware date/time
- `run_python` - Python code execution
- `read_webpage` - URL content fetching
- `search_memory` - Qdrant vector search

### Gemini Skills
- `gemini-deep-research` - Multi-step agentic research with citations
- `gemini-grounding` - Real-time factual queries via Google Search
- `gemini-thinking` - Configurable reasoning depth (minimal/low/medium/high)
- `gemini-vision` - Image and document analysis

### Skill Execution Modes
- **Simple** - Direct skill execution
- **Routed** - Semantic routing to best skill
- **Auto** - Smart detection (simple vs complex)
- **Orchestrated** - Multi-skill complex tasks

### API Endpoints
- `/health` - Health check with circuit status
- `/webhook/telegram` - Telegram bot webhook
- `/webhook/github` - GitHub webhook
- `/api/skill` - Skill execution API
- `/api/skills` - List available skills
- `/api/task/{id}` - Local task status
- `/api/reports` - List user reports
- `/api/reports/{id}` - Report download URL
- `/api/reports/{id}/content` - Report content
- `/api/content` - Content generation API
- `/api/traces` - Execution traces (developer+)
- `/api/circuits` - Circuit breaker status (developer+)

### Telegram Commands
- Basic: /start, /help, /status, /tier, /clear
- Skills: /skills, /skill, /mode, /task, /cancel
- Quick: /translate, /summarize, /rewrite
- Developer: /traces, /trace, /circuits
- Admin: /grant, /revoke, /admin, /remind, /reminders

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
| 13 | Gemini Integration & Reports | Done |
| 14 | User Tier System | Done |

## Dependencies

- Modal.com account (deployed)
- Firebase project (Firestore + Storage)
- Qdrant Cloud (configured)
- Telegram Bot (configured)
- Anthropic API key (configured)
- Google Cloud Platform (Vertex AI)
- Exa API key (configured)
- Tavily API key (configured)
- GitHub token (configured)

## Related Documents

- [System Architecture](./system-architecture.md)
- [Code Standards](./code-standards.md)
- [Codebase Summary](./codebase-summary.md)
- [Project Roadmap](./project-roadmap.md)
- [Deployment Guide](./deployment-guide.md)
