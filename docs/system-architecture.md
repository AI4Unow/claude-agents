# System Architecture

## High-Level Overview

```
LOCAL DEVELOPMENT                         MODAL CLOUD
─────────────────                         ───────────

┌─────────────────┐                      ┌─────────────────────────────────────┐
│ Your Computer   │                      │            MODAL SERVER             │
│                 │                      │                                     │
│ skills/         │    modal deploy      │  ┌─────────────────────────────────┐│
│ ├── zalo-chat/  │ ──────────────────► │  │  zalo_chat.py                   ││
│ │   ├── info.md │                      │  │  github_agent.py                ││
│ │   └── agent.py│                      │  │  data_agent.py                  ││
│ ├── github/     │                      │  │  content_agent.py               ││
│ │   ├── info.md │                      │  │                                 ││
│ │   └── agent.py│                      │  │  Runs on cron schedule          ││
│ └── ...         │                      │  │  Up to 60 min per execution     ││
│                 │                      │  └─────────────────────────────────┘│
│ .env (secrets)  │    modal secrets     │                                     │
│                 │ ──────────────────► │  ┌─────────────────────────────────┐│
└─────────────────┘                      │  │  MODAL VOLUME (/skills/)        ││
                                         │  │                                 ││
                                         │  │  zalo-chat/info.md  (mutable)   ││
                                         │  │  github/info.md     (mutable)   ││
                                         │  │  data/info.md       (mutable)   ││
                                         │  │  content/info.md    (mutable)   ││
                                         │  │                                 ││
                                         │  │  Agents READ and WRITE here     ││
                                         │  │  Self-improvement persists      ││
                                         │  └─────────────────────────────────┘│
                                         └─────────────────────────────────────┘
                                                          │
                    ┌─────────────────────────────────────┼─────────────────┐
                    ▼                                     ▼                 ▼
          ┌─────────────────┐                   ┌─────────────┐   ┌─────────────┐
          │  VERCEL EDGE    │                   │   FIREBASE  │   │QDRANT CLOUD │
          │  (Webhooks)     │                   │  (State)    │   │  (Memory)   │
          └─────────────────┘                   └─────────────┘   └─────────────┘
```

## Component Descriptions

### Modal Components

| Component | Type | Config | Purpose |
|-----------|------|--------|---------|
| Zalo Chat Agent | Web Endpoint | `min_containers=1` | Primary user interface |
| GitHub Agent | Cron + Webhook | Hourly | Repo automation |
| Data Agent | Scheduled | Daily/hourly | Data processing |
| Content Agent | Function | On-demand | Content generation |
| Skills Volume | Volume | 10GB | Mutable info.md storage |

### External Services

| Service | Purpose | Region |
|---------|---------|--------|
| Firebase Firestore | State, task queue, tokens | Default |
| Qdrant Cloud | Vector memory | Asia (Singapore/Tokyo) |
| Vercel Edge | Webhook relay | Global edge |
| Anthropic API | Claude LLM | Default |
| Vertex AI | Text embeddings | us-central1 |

## Self-Improvement Loop

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENT EXECUTION CYCLE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. WAKE UP (Cron or webhook trigger)                                       │
│     │                                                                        │
│  2. READ info.md from Modal Volume                                          │
│     │  - Current instructions                                               │
│     │  - Memory of past runs                                                │
│     │  - Learned improvements                                               │
│     │                                                                        │
│  3. EXECUTE task using agent.py + LLM API                                   │
│     │                                                                        │
│  4. EVALUATE results                                                        │
│     │                                                                        │
│     ├── Success → Append to memory section in info.md                       │
│     │                                                                        │
│     └── Error → SELF-IMPROVE                                                │
│           │                                                                  │
│           ├── LLM analyzes what went wrong                                  │
│           ├── LLM rewrites info.md with fix                                 │
│           ├── Commit changes to Modal Volume                                │
│           └── Retry (recursive until success or timeout)                    │
│                                                                              │
│  5. COMPLETE - Sleep until next trigger                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Message Flow (Zalo Chat)

```
User (Zalo) ──► Zalo Server ──► Modal Webhook
                                     │
                                     ▼
                              ┌─────────────────┐
                              │ Verify Signature │
                              └────────┬────────┘
                                       │
                              ┌────────▼────────┐
                              │ Get User Context │◄── Qdrant
                              └────────┬────────┘
                                       │
                              ┌────────▼────────┐
                              │ Process w/ Claude│◄── Anthropic
                              └────────┬────────┘
                                       │
                         ┌─────────────┼─────────────┐
                         ▼             ▼             ▼
                   ┌──────────┐ ┌──────────┐ ┌──────────┐
                   │ Dispatch │ │ Store    │ │ Respond  │
                   │ Task     │ │ Memory   │ │ to User  │
                   └──────────┘ └──────────┘ └──────────┘
                        │             │             │
                   Firebase       Qdrant         Zalo API
```

### Inter-Agent Communication

Pattern: Task Queue via Firebase

```python
# Agent A dispatches task
db.collection("tasks").add({
    "type": "content",
    "status": "pending",
    "payload": {"topic": "weekly report"}
})

# Agent B picks up task
tasks = db.collection("tasks")
    .where("type", "==", "content")
    .where("status", "==", "pending")
    .limit(1).get()
```

## Firebase Schema

```
firestore/
├── users/{userId}
│   ├── zaloId: string
│   ├── preferences: map
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
└── tokens/{service}
    ├── accessToken: string
    └── expiresAt: timestamp
```

## Qdrant Collections

| Collection | Vector Dim | Purpose |
|------------|------------|---------|
| `conversations` | 768 | Chat history embeddings |
| `knowledge` | 768 | Domain knowledge base |
| `tasks` | 768 | Task context for retrieval |

## Cost Estimate

| Component | Monthly Cost |
|-----------|-------------|
| Modal compute | ~$15-20 |
| Qdrant Cloud | ~$25 |
| LLM API calls | ~$10-20 |
| Firebase | $0 (free tier) |
| Vercel Edge | $0 (free tier) |
| **Total** | **~$40-60** |
