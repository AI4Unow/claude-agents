# Brainstorm Report: Modal.com + Claude Code Skills Agent System

**Date:** 2025-12-26
**Status:** Architecture Approved, Ready for Implementation Plan

---

## Problem Statement

Deploy Claude Code skills on Modal.com to create a team of collaborating agents running 24/7, supporting:
- GitHub automation
- Chat/messaging bots (Zalo OA)
- Data processing
- Content generation

---

## Requirements

| Requirement | Details |
|-------------|---------|
| **Budget** | $30-50/mo target (actual: $35-45/mo) |
| **Chat Platform** | Zalo Official Account |
| **Memory** | Persistent across sessions |
| **Storage** | Firebase Firestore + Qdrant (vectors) |
| **Skills** | Hot-reload via Modal Volume |
| **Agents** | Collaborative, not fully independent |

---

## Evaluated Approaches

### 1. Fully Serverless (Modal Only)
- **Pros:** Simple, cheap, no external deps
- **Cons:** Limited persistent storage, cold starts
- **Verdict:** ❌ Insufficient for persistent memory needs

### 2. Modal + External DB (Supabase/Neon)
- **Pros:** SQL power, generous free tiers
- **Cons:** No vector search without pgvector setup
- **Verdict:** ⚠️ Viable but more SQL overhead

### 3. Modal + Firebase + Qdrant (Selected)
- **Pros:** Best of both - structured state + semantic memory
- **Cons:** Slightly over budget, multiple services
- **Verdict:** ✅ Optimal for use case

---

## Final Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MODAL.COM                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                    ZALO CHAT AGENT (Primary Gateway)                    ││
│  │              Modal Web Endpoint + min_containers=1                      ││
│  │                      FastAPI + python-zalo-bot                          ││
│  └────────────────────────────────┬────────────────────────────────────────┘│
│                                   │                                          │
│              ┌────────────────────┼────────────────────┐                    │
│              ▼                    ▼                    ▼                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │  GITHUB AGENT   │  │   DATA AGENT    │  │ CONTENT AGENT   │             │
│  │  (Cron + Hook)  │  │  (Scheduled)    │  │  (On-demand)    │             │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘             │
│           │                    │                    │                       │
│           └────────────────────┼────────────────────┘                       │
│                                ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                      SKILLS VOLUME (Hot-reload)                         ││
│  │                   Claude Code Skills + CLAUDE.md                        ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                    QDRANT CONTAINER (Vector Memory)                     ││
│  │                       Self-hosted on Modal                              ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└──────────────────────────────────┬───────────────────────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
   │    FIREBASE     │  │    ZALO OA      │  │   ANTHROPIC     │
   │  (State/Config) │  │   (Webhooks)    │  │   (Claude API)  │
   └─────────────────┘  └─────────────────┘  └─────────────────┘
```

---

## Component Specifications

### Modal Components

| Component | Modal Feature | Config | Est. Cost |
|-----------|---------------|--------|-----------|
| Zalo Chat Agent | Web Endpoint | `min_containers=1`, FastAPI | ~$15/mo |
| GitHub Agent | Cron + Webhook | Hourly schedule | ~$3/mo |
| Data Agent | Scheduled Function | Daily/hourly | ~$2/mo |
| Content Agent | Function | On-demand spawn | Pay-per-use |
| Skills Volume | Volume | 10GB | Free |
| Qdrant | Container | 1GB memory | ~$5/mo |

### External Services

| Service | Purpose | Tier | Est. Cost |
|---------|---------|------|-----------|
| Firebase Firestore | State, config, tokens | Free tier | $0 |
| Anthropic Claude API | Agent intelligence | Pay-per-use | ~$10-20/mo |
| Zalo OA | Chat interface | Free | $0 |
| GitHub | Automation target | Free | $0 |

---

## Firebase Schema

```
firestore/
├── users/{userId}
│   ├── zaloId: string
│   ├── preferences: map
│   ├── tier: string
│   └── createdAt: timestamp
├── agents/{agentId}
│   ├── status: "running" | "idle" | "error"
│   ├── lastRun: timestamp
│   └── config: map
├── tasks/{taskId}
│   ├── type: "github" | "data" | "content"
│   ├── status: "pending" | "processing" | "done"
│   ├── payload: map
│   └── result: map
├── tokens/{service}
│   ├── accessToken: string
│   ├── refreshToken: string
│   └── expiresAt: timestamp
└── logs/{timestamp}
    ├── agent: string
    ├── action: string
    └── details: map
```

---

## Qdrant Collections

| Collection | Vector Dim | Purpose |
|------------|------------|---------|
| `conversations` | 768 (Gemini) | Chat history embeddings |
| `knowledge` | 768 | Domain knowledge base |
| `tasks` | 768 | Task context for retrieval |

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Runtime | Modal.com (Python 3.11) |
| Web Framework | FastAPI |
| Zalo Integration | python-zalo-bot, zalo-oa-api-wrapper |
| GitHub | PyGithub |
| AI | Claude Agent SDK, Anthropic API |
| Vector DB | Qdrant (self-hosted) |
| State Store | Firebase Firestore |
| Embeddings | Vertex AI text-embedding-004 |

---

## Inter-Agent Communication

### Pattern: Task Queue via Firebase

```python
# Agent A dispatches task
db.collection("tasks").add({
    "type": "content",
    "status": "pending",
    "payload": {"topic": "weekly report"},
    "createdAt": firestore.SERVER_TIMESTAMP
})

# Agent B picks up task (Cloud Function trigger or polling)
tasks = db.collection("tasks")\
    .where("type", "==", "content")\
    .where("status", "==", "pending")\
    .limit(1).get()
```

### Pattern: Direct Invocation via Modal

```python
# Zalo Agent calls Content Agent directly
from agents.content import generate_report

@app.function()
async def handle_message(user_msg):
    if "report" in user_msg:
        result = await generate_report.remote(user_msg)
        return result
```

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Zalo 2s timeout | Messages fail | Async processing, immediate ACK |
| Modal cold start | Slow first response | `min_containers=1` for chat agent |
| Token expiry | Auth failures | Firebase token refresh cron |
| Qdrant memory | OOM crashes | Monitor, scale container |
| Over budget | Cost overrun | Usage alerts, optimize agents |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Zalo response time | <2 seconds |
| Agent uptime | >99% |
| Monthly cost | <$50 |
| Task success rate | >95% |

---

## Next Steps

1. Create detailed implementation plan
2. Setup Modal project structure
3. Implement Zalo Chat Agent first
4. Add Firebase integration
5. Deploy Qdrant container
6. Implement remaining agents
7. Test inter-agent communication
8. Deploy to production

---

## Unresolved Questions

1. **Zalo OA approval:** Do you have Zalo OA already created and verified?
2. **GitHub scope:** Which repos/orgs should GitHub Agent monitor?
