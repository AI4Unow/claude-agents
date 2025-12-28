# Phase 1: System Overview

## Context

Create master architecture diagrams showing complete hybrid system. Consolidates current Modal-only architecture with planned local agent capabilities.

## Overview

Three-layer architecture: Local Execution, Modal Cloud, External Services. II Framework unifies skill management across both execution environments.

## Key Insights

- Local agents handle browser automation (TikTok, FB, YT, LinkedIn) requiring consumer IP
- Modal agents handle API-based tasks (planning, research, chat)
- Firebase acts as coordination layer between local and remote
- Qdrant provides shared memory across all agents

## Master Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              HYBRID AGENT ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  LOCAL EXECUTION (Claude Code)           MODAL CLOUD (Serverless)                   │
│  ────────────────────────────           ───────────────────────                     │
│  ┌───────────────────────────┐         ┌────────────────────────────────────┐       │
│  │ Claude Code CLI           │         │ Modal App (claude-agents)          │       │
│  │ ├── chrome-dev skill      │         │ ├── TelegramChatAgent (always-on)  │       │
│  │ ├── chrome skill          │         │ ├── GitHubAgent (cron + webhook)   │       │
│  │ └── MCP servers           │         │ ├── DataAgent (daily cron)         │       │
│  │                           │         │ └── ContentAgent (on-demand)       │       │
│  │ Local-Only Skills:        │         │                                    │       │
│  │ • tiktok, facebook        │  Queue  │ Remote Skills (25+):               │       │
│  │ • youtube, linkedin       │◄───────►│ • planning, research               │       │
│  │ • instagram               │         │ • backend-development              │       │
│  │ (Consumer IP required)    │         │ • ui-ux-pro-max, etc.              │       │
│  └───────────────────────────┘         └────────────────────────────────────┘       │
│           │                                         │                               │
│           │                                         │                               │
│           └─────────────────┬───────────────────────┘                               │
│                             │                                                       │
│                             ▼                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                           PERSISTENCE LAYER                                  │   │
│  ├───────────────────────────┬─────────────────────┬───────────────────────────┤   │
│  │ Firebase Firestore        │ Modal Volume        │ Qdrant Cloud              │   │
│  │ ├── telegram_sessions     │ └── /skills/        │ ├── skills (routing)      │   │
│  │ ├── conversations         │     ├── info.md     │ ├── knowledge (insights)  │   │
│  │ ├── tasks (queue)         │     └── (mutable)   │ ├── conversations         │   │
│  │ ├── skill_improvements    │                     │ └── errors (patterns)     │   │
│  │ └── logs                  │                     │                           │   │
│  └───────────────────────────┴─────────────────────┴───────────────────────────┘   │
│                             │                                                       │
│                             ▼                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                           EXTERNAL SERVICES                                  │   │
│  ├───────────────────┬───────────────────┬─────────────────┬───────────────────┤   │
│  │ Anthropic Claude  │ Telegram Bot API  │ GitHub API      │ Exa/Tavily        │   │
│  │ (via ai4u.now)    │ (webhooks)        │ (webhooks)      │ (web search)      │   │
│  └───────────────────┴───────────────────┴─────────────────┴───────────────────┘   │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA FLOW                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  USER INPUT                                                                  │
│  ─────────                                                                   │
│  Telegram ───► Modal Webhook ───► TelegramChatAgent                         │
│                                           │                                  │
│                                           ▼                                  │
│                                   ┌───────────────┐                          │
│                                   │ Skill Router  │                          │
│                                   └───────┬───────┘                          │
│                           ┌───────────────┼───────────────┐                  │
│                           ▼               ▼               ▼                  │
│                     ┌──────────┐   ┌──────────┐   ┌──────────┐               │
│                     │ Simple   │   │ Routed   │   │Orchestr- │               │
│                     │ (direct) │   │ (Qdrant) │   │ated      │               │
│                     └────┬─────┘   └────┬─────┘   └────┬─────┘               │
│                          └──────────────┼──────────────┘                     │
│                                         ▼                                    │
│                                 ┌───────────────┐                            │
│                                 │ Agentic Loop  │                            │
│                                 │ (max 5 iter)  │                            │
│                                 └───────┬───────┘                            │
│                           ┌─────────────┼─────────────┐                      │
│                           ▼             ▼             ▼                      │
│                     ┌──────────┐ ┌──────────┐ ┌──────────┐                   │
│                     │web_search│ │run_python│ │ search   │                   │
│                     │          │ │          │ │ _memory  │                   │
│                     └──────────┘ └──────────┘ └──────────┘                   │
│                                         │                                    │
│                                         ▼                                    │
│                                 ┌───────────────┐                            │
│                                 │ Response      │                            │
│                                 │ + State Save  │                            │
│                                 └───────────────┘                            │
│                                         │                                    │
│                                         ▼                                    │
│                              Telegram API (send_message)                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Inventory

### Modal Components

| Component | Type | Config | Purpose | Lines |
|-----------|------|--------|---------|-------|
| TelegramChatAgent | Web Endpoint | min_containers=1 | Primary chat | 782 |
| GitHubAgent | Cron + Webhook | hourly | Repo automation | ~200 |
| DataAgent | Cron | daily 1AM UTC | Data processing | ~150 |
| ContentAgent | Function | on-demand | Content gen | ~150 |
| Skills Volume | Modal Volume | 10GB | Mutable info.md | - |

### Services

| Service | File | Lines | Purpose |
|---------|------|-------|---------|
| agentic.py | src/services/ | ~400 | Agentic loop, conversation persist |
| llm.py | src/services/ | ~200 | Claude API client |
| firebase.py | src/services/ | 507 | Firestore operations |
| qdrant.py | src/services/ | 617 | Vector DB client |
| embeddings.py | src/services/ | ~100 | Embedding generation |
| telegram.py | src/services/ | ~50 | Message utilities |

### Core II Framework

| Module | Lines | Purpose |
|--------|-------|---------|
| state.py | 372 | L1 TTL cache + L2 Firebase |
| orchestrator.py | 300 | Multi-skill coordination |
| evaluator.py | 287 | Quality assessment |
| context_optimization.py | 283 | Context compaction |
| chain.py | 243 | Sequential pipelines |
| router.py | 160 | Semantic skill routing |
| resilience.py | 264 | Circuit breakers, retries |
| trace.py | ~200 | Execution tracing |

### Tools

| Tool | File | Purpose |
|------|------|---------|
| web_search | web_search.py | Exa primary + Tavily fallback |
| get_datetime | datetime_tool.py | Timezone-aware date/time |
| run_python | code_exec.py | Python execution |
| read_webpage | web_reader.py | URL content fetch |
| search_memory | memory_search.py | Qdrant vector search |

## Implementation Steps

1. [ ] Validate current architecture matches diagram
2. [ ] Identify gaps in local agent coordination
3. [ ] Document skill deployment categorization
4. [ ] Create component dependency graph
5. [ ] Update system-architecture.md

## Todo List

- [ ] Review main.py for accuracy (1107 lines)
- [ ] Confirm all services listed correctly
- [ ] Verify Modal Volume structure
- [ ] Check Firebase collections schema

## Success Criteria

- [ ] Master diagram reflects reality
- [ ] All components inventoried
- [ ] Data flow complete and accurate
- [ ] Gaps between current and target identified
