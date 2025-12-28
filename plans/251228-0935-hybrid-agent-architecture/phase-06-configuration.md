# Phase 6: Configuration & Environment

## Context

Complete catalog of environment variables, Modal secrets, Firebase collections, and Qdrant collections. Single reference for all configuration.

## Overview

Configuration lives in three layers:
1. **Modal Secrets** - Sensitive credentials (API keys, tokens)
2. **Environment Variables** - Runtime config injected from secrets
3. **Firebase/Qdrant Schemas** - Data structure definitions

## Modal Secrets

Secrets created via `modal secret create`:

| Secret Name | Variables Inside | Purpose |
|-------------|------------------|---------|
| anthropic-credentials | ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL | Claude API |
| firebase-credentials | FIREBASE_CREDENTIALS | Firestore JSON |
| telegram-credentials | TELEGRAM_BOT_TOKEN | Telegram Bot |
| qdrant-credentials | QDRANT_URL, QDRANT_API_KEY | Vector DB |
| exa-credentials | EXA_API_KEY | Web search (primary) |
| tavily-credentials | TAVILY_API_KEY | Web search (fallback) |
| github-credentials | GITHUB_TOKEN | GitHub API |
| admin-credentials | ADMIN_TOKEN, ADMIN_TELEGRAM_ID | Admin access |

**Creation commands:**

```bash
# Anthropic
modal secret create anthropic-credentials \
  ANTHROPIC_API_KEY=sk-ant-... \
  ANTHROPIC_BASE_URL=https://ai4u.now/anthropic

# Firebase (JSON string)
modal secret create firebase-credentials \
  FIREBASE_CREDENTIALS='{"type":"service_account",...}'

# Telegram
modal secret create telegram-credentials \
  TELEGRAM_BOT_TOKEN=123456:ABC...

# Qdrant
modal secret create qdrant-credentials \
  QDRANT_URL=https://xxx.qdrant.cloud \
  QDRANT_API_KEY=...

# Search APIs
modal secret create exa-credentials EXA_API_KEY=...
modal secret create tavily-credentials TAVILY_API_KEY=...

# GitHub
modal secret create github-credentials GITHUB_TOKEN=ghp_...

# Admin
modal secret create admin-credentials \
  ADMIN_TOKEN=random_secure_token \
  ADMIN_TELEGRAM_ID=12345678
```

## Environment Variables Catalog

### API Credentials

| Variable | Source Secret | Required | Default |
|----------|---------------|----------|---------|
| ANTHROPIC_API_KEY | anthropic-credentials | Yes | - |
| ANTHROPIC_BASE_URL | anthropic-credentials | No | https://api.anthropic.com |
| TELEGRAM_BOT_TOKEN | telegram-credentials | Yes | - |
| QDRANT_URL | qdrant-credentials | Yes | - |
| QDRANT_API_KEY | qdrant-credentials | Yes | - |
| EXA_API_KEY | exa-credentials | Yes | - |
| TAVILY_API_KEY | tavily-credentials | Yes | - |
| GITHUB_TOKEN | github-credentials | For GitHub agent | - |

### Firebase Configuration

| Variable | Source Secret | Required | Notes |
|----------|---------------|----------|-------|
| FIREBASE_CREDENTIALS | firebase-credentials | Yes | JSON string |

### Admin Configuration

| Variable | Source Secret | Required | Notes |
|----------|---------------|----------|-------|
| ADMIN_TOKEN | admin-credentials | Yes | For /api endpoints auth |
| ADMIN_TELEGRAM_ID | admin-credentials | Yes | For improvement notifications |

### Runtime Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| MODEL_NAME | claude-sonnet-4-20250514 | LLM model |
| MAX_AGENTIC_ITERATIONS | 5 | Agentic loop limit |
| CONVERSATION_MAX_MESSAGES | 20 | History limit |
| L1_CACHE_TTL_SECONDS | 300 | Default cache TTL |

## Firebase Collections Schema

```javascript
firestore/
├── telegram_sessions/{platform}:{user_id}
│   {
│     user_id: string,           // "telegram:12345"
│     username: string,
│     first_name: string,
│     mode: "agentic" | "simple",
│     created_at: timestamp,
│     updated_at: timestamp,
│     preferences: {
│       language: string,
│       timezone: string
│     }
│   }
│
├── conversations/{platform}:{user_id}
│   {
│     user_id: string,
│     messages: [                // Last 20 messages
│       {
│         role: "user" | "assistant",
│         content: string,
│         timestamp: timestamp
│       }
│     ],
│     updated_at: timestamp
│   }
│
├── agents/{agent_id}
│   {
│     agent_id: string,          // "telegram_chat", "github", etc.
│     status: "running" | "idle" | "error",
│     last_run: timestamp,
│     config: map,
│     health: {
│       last_check: timestamp,
│       status: string
│     }
│   }
│
├── tasks/{task_id}
│   {
│     id: string,
│     type: "local_skill" | "remote_skill",
│     skill: string,             // "tiktok", "youtube", etc.
│     payload: map,
│     status: "pending" | "processing" | "done" | "failed",
│     created_at: timestamp,
│     assigned_to: string | null,
│     claimed_at: timestamp | null,
│     completed_at: timestamp | null,
│     result: map | null,
│     error: string | null
│   }
│
├── skill_improvements/{proposal_id}
│   {
│     id: string,
│     skill: string,
│     error_context: string,
│     proposal: {
│       section: string,
│       old_text: string,
│       new_text: string,
│       rationale: string
│     },
│     status: "pending" | "approved" | "rejected",
│     created_at: timestamp,
│     reviewed_at: timestamp | null,
│     reviewed_by: string | null,
│     rejection_reason: string | null
│   }
│
└── logs/{log_id}
    {
      skill_id: string,
      action: string,
      result: "success" | "error",
      duration_ms: number,
      error_message: string | null,
      timestamp: timestamp,
      trace_id: string | null
    }
```

## Qdrant Collections Schema

| Collection | Vector Dim | Distance | Purpose |
|------------|------------|----------|---------|
| skills | 768 or 1536 | Cosine | Skill embeddings for routing |
| knowledge | 768 or 1536 | Cosine | Cross-skill insights |
| conversations | 768 or 1536 | Cosine | Chat history (optional) |
| errors | 768 or 1536 | Cosine | Error pattern matching |

**Payload Schema:**

```javascript
// skills collection
{
  "name": "planning",
  "description": "Create implementation plans",
  "category": "development",
  "deployment": "remote"
}

// knowledge collection
{
  "source_skill": "planning",
  "insight": "Always include success criteria",
  "learned_at": "2025-12-28T00:00:00Z"
}

// errors collection
{
  "skill": "web_search",
  "error_type": "timeout",
  "pattern": "Exa API timeout after 30s",
  "resolution": "Fallback to Tavily"
}
```

**Index Creation:**

```python
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# Create skills collection
client.create_collection(
    collection_name="skills",
    vectors_config=VectorParams(
        size=768,  # or 1536 for larger models
        distance=Distance.COSINE
    )
)
```

## Modal Configuration (modal.toml)

```toml
[app]
name = "claude-agents"

[build]
python_packages = ["modal>=0.60.0"]

[environments.main]
secrets = [
    "anthropic-credentials",
    "firebase-credentials",
    "telegram-credentials",
    "qdrant-credentials",
    "exa-credentials",
    "tavily-credentials",
    "admin-credentials"
]
```

## Local Development (.env)

For local testing (NOT committed):

```bash
# .env (gitignored)
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_BASE_URL=https://ai4u.now/anthropic
TELEGRAM_BOT_TOKEN=123456:ABC...
QDRANT_URL=https://xxx.qdrant.cloud
QDRANT_API_KEY=...
EXA_API_KEY=...
TAVILY_API_KEY=...
FIREBASE_CREDENTIALS='{...}'
ADMIN_TOKEN=local_dev_token
ADMIN_TELEGRAM_ID=12345678
```

## Configuration Loader

```python
# src/config.py

import os
import json
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Application configuration."""

    # LLM
    anthropic_api_key: str
    anthropic_base_url: str
    model_name: str

    # Telegram
    telegram_bot_token: str

    # Qdrant
    qdrant_url: str
    qdrant_api_key: str

    # Search
    exa_api_key: str
    tavily_api_key: str

    # Firebase
    firebase_credentials: dict

    # Admin
    admin_token: str
    admin_telegram_id: str

    # Runtime
    max_iterations: int
    max_messages: int


def load_config() -> Config:
    """Load configuration from environment."""
    return Config(
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        anthropic_base_url=os.environ.get(
            "ANTHROPIC_BASE_URL",
            "https://api.anthropic.com"
        ),
        model_name=os.environ.get(
            "MODEL_NAME",
            "claude-sonnet-4-20250514"
        ),
        telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        qdrant_url=os.environ["QDRANT_URL"],
        qdrant_api_key=os.environ["QDRANT_API_KEY"],
        exa_api_key=os.environ["EXA_API_KEY"],
        tavily_api_key=os.environ["TAVILY_API_KEY"],
        firebase_credentials=json.loads(
            os.environ["FIREBASE_CREDENTIALS"]
        ),
        admin_token=os.environ["ADMIN_TOKEN"],
        admin_telegram_id=os.environ["ADMIN_TELEGRAM_ID"],
        max_iterations=int(os.environ.get("MAX_AGENTIC_ITERATIONS", "5")),
        max_messages=int(os.environ.get("CONVERSATION_MAX_MESSAGES", "20"))
    )
```

## Implementation Steps

1. [ ] Verify all Modal secrets exist
2. [ ] Create Firebase indexes for queries
3. [ ] Initialize Qdrant collections
4. [ ] Update config.py with all variables
5. [ ] Document secret rotation procedure

## Todo List

- [ ] Add secret rotation script
- [ ] Create Firestore security rules
- [ ] Add Qdrant backup procedure
- [ ] Document disaster recovery

## Success Criteria

- [ ] All secrets documented
- [ ] All env vars catalogued
- [ ] Firebase schema complete
- [ ] Qdrant schema complete
- [ ] Config loader validates required vars
