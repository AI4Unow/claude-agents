# Phase 2: Firebase Integration

## Context

- Plan: [plan.md](./plan.md)
- Previous: [Phase 1 - Project Setup](./phase-01-project-setup-modal-config.md)

## Overview

**Priority:** P1 - Core Infrastructure
**Status:** Pending
**Effort:** 3h

Integrate Firebase Firestore for state management, task queues, token storage, and activity logging.

## Requirements

### Functional
- Firebase Admin SDK initialized in Modal container
- CRUD operations for all collections (users, agents, tasks, tokens, logs)
- Token refresh mechanism for external OAuth services
- Task queue with status transitions
- Real-time agent status tracking

### Non-Functional
- Connection pooling for performance
- Error handling with retries
- Firestore security rules

## Firebase Schema

```
firestore/
├── users/{telegramUserId}
│   ├── displayName: string
│   ├── preferences: map
│   ├── tier: "free" | "pro"
│   └── createdAt: timestamp
│
├── agents/{agentId}
│   ├── type: "telegram" | "github" | "data" | "content"
│   ├── status: "idle" | "running" | "error"
│   ├── lastRun: timestamp
│   ├── config: map
│   └── stats: { tasksCompleted: number, errors: number }
│
├── tasks/{taskId}
│   ├── type: "github" | "data" | "content"
│   ├── status: "pending" | "processing" | "done" | "failed"
│   ├── priority: number (1-10)
│   ├── createdBy: string (agentId)
│   ├── assignedTo: string | null
│   ├── payload: map
│   ├── result: map | null
│   ├── error: string | null
│   ├── createdAt: timestamp
│   └── updatedAt: timestamp
│
├── tokens/{service}  # e.g., "github"
│   ├── accessToken: string
│   ├── refreshToken: string
│   ├── expiresAt: timestamp
│   └── updatedAt: timestamp
│
└── logs/{auto-id}
    ├── agent: string
    ├── action: string
    ├── level: "info" | "warn" | "error"
    ├── details: map
    └── timestamp: timestamp
```

## Implementation Steps

### 1. Create Firebase Project

1. Go to https://console.firebase.google.com
2. Create new project: `claude-agents-prod`
3. Enable Firestore Database (production mode)
4. Generate service account key:
   - Project Settings → Service Accounts → Generate New Private Key
   - Save JSON securely

### 2. Create src/services/firebase.py

```python
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import FieldFilter

# Initialize Firebase
_app = None
_db = None

def init_firebase():
    """Initialize Firebase with credentials from Modal secret."""
    global _app, _db

    if _app is not None:
        return _db

    cred_json = os.environ.get("FIREBASE_CREDENTIALS")
    if not cred_json:
        raise ValueError("FIREBASE_CREDENTIALS not set")

    cred_dict = json.loads(cred_json)
    cred = credentials.Certificate(cred_dict)
    _app = firebase_admin.initialize_app(cred)
    _db = firestore.client()
    return _db

def get_db():
    """Get Firestore client, initializing if needed."""
    global _db
    if _db is None:
        init_firebase()
    return _db

# ==================== Users ====================

async def get_user(user_id: str) -> Optional[Dict]:
    """Get user by Telegram user ID."""
    db = get_db()
    doc = db.collection("users").document(user_id).get()
    return doc.to_dict() if doc.exists else None

async def create_or_update_user(user_id: str, data: Dict) -> None:
    """Create or update user."""
    db = get_db()
    db.collection("users").document(user_id).set({
        **data,
        "updatedAt": firestore.SERVER_TIMESTAMP
    }, merge=True)

# ==================== Agents ====================

async def update_agent_status(agent_id: str, status: str) -> None:
    """Update agent status."""
    db = get_db()
    db.collection("agents").document(agent_id).set({
        "status": status,
        "lastRun": firestore.SERVER_TIMESTAMP
    }, merge=True)

async def get_agent(agent_id: str) -> Optional[Dict]:
    """Get agent by ID."""
    db = get_db()
    doc = db.collection("agents").document(agent_id).get()
    return doc.to_dict() if doc.exists else None

# ==================== Tasks ====================

async def create_task(
    task_type: str,
    payload: Dict,
    created_by: str,
    priority: int = 5
) -> str:
    """Create a new task and return task ID."""
    db = get_db()
    doc_ref = db.collection("tasks").add({
        "type": task_type,
        "status": "pending",
        "priority": priority,
        "createdBy": created_by,
        "assignedTo": None,
        "payload": payload,
        "result": None,
        "error": None,
        "createdAt": firestore.SERVER_TIMESTAMP,
        "updatedAt": firestore.SERVER_TIMESTAMP
    })
    return doc_ref[1].id

async def claim_task(task_type: str, agent_id: str) -> Optional[Dict]:
    """Claim a pending task for processing."""
    db = get_db()
    tasks = db.collection("tasks")\
        .where(filter=FieldFilter("type", "==", task_type))\
        .where(filter=FieldFilter("status", "==", "pending"))\
        .order_by("priority", direction=firestore.Query.DESCENDING)\
        .order_by("createdAt")\
        .limit(1)\
        .get()

    if not tasks:
        return None

    task_doc = tasks[0]
    task_ref = db.collection("tasks").document(task_doc.id)

    # Atomic claim with transaction
    @firestore.transactional
    def claim_in_transaction(transaction, task_ref):
        snapshot = task_ref.get(transaction=transaction)
        if snapshot.get("status") != "pending":
            return None
        transaction.update(task_ref, {
            "status": "processing",
            "assignedTo": agent_id,
            "updatedAt": firestore.SERVER_TIMESTAMP
        })
        return {**snapshot.to_dict(), "id": snapshot.id}

    transaction = db.transaction()
    return claim_in_transaction(transaction, task_ref)

async def complete_task(task_id: str, result: Dict) -> None:
    """Mark task as completed with result."""
    db = get_db()
    db.collection("tasks").document(task_id).update({
        "status": "done",
        "result": result,
        "updatedAt": firestore.SERVER_TIMESTAMP
    })

async def fail_task(task_id: str, error: str) -> None:
    """Mark task as failed with error."""
    db = get_db()
    db.collection("tasks").document(task_id).update({
        "status": "failed",
        "error": error,
        "updatedAt": firestore.SERVER_TIMESTAMP
    })

# ==================== Tokens ====================

async def get_token(service: str) -> Optional[Dict]:
    """Get OAuth token for service."""
    db = get_db()
    doc = db.collection("tokens").document(service).get()
    return doc.to_dict() if doc.exists else None

async def save_token(
    service: str,
    access_token: str,
    refresh_token: str,
    expires_at: datetime
) -> None:
    """Save OAuth token."""
    db = get_db()
    db.collection("tokens").document(service).set({
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "expiresAt": expires_at,
        "updatedAt": firestore.SERVER_TIMESTAMP
    })

# ==================== Logs ====================

async def log_activity(
    agent: str,
    action: str,
    details: Dict,
    level: str = "info"
) -> None:
    """Log agent activity."""
    db = get_db()
    db.collection("logs").add({
        "agent": agent,
        "action": action,
        "level": level,
        "details": details,
        "timestamp": firestore.SERVER_TIMESTAMP
    })
```

### 3. Create Firestore Security Rules

In Firebase Console → Firestore → Rules:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Only allow server-side access (Admin SDK bypasses rules)
    // These rules are for client access if ever needed

    match /users/{userId} {
      allow read, write: if false;  // Server-only
    }

    match /agents/{agentId} {
      allow read, write: if false;  // Server-only
    }

    match /tasks/{taskId} {
      allow read, write: if false;  // Server-only
    }

    match /tokens/{service} {
      allow read, write: if false;  // Server-only (sensitive!)
    }

    match /logs/{logId} {
      allow read, write: if false;  // Server-only
    }
  }
}
```

### 4. Create Token Refresh Service

```python
# src/services/token_refresh.py
import httpx
from datetime import datetime, timedelta
from src.services.firebase import get_token, save_token
from src.config import settings

async def refresh_github_token() -> str:
    """Refresh GitHub access token if expired (for GitHub Apps)."""
    token_data = await get_token("github")

    if token_data and token_data["expiresAt"] > datetime.utcnow():
        return token_data["accessToken"]

    # For GitHub Apps, tokens are refreshed via installation token API
    # For personal access tokens, no refresh needed (they don't expire)
    # This is a placeholder for GitHub App token refresh logic
    return settings.github_token
```

### 5. Add Firebase Init to main.py

```python
# Add to main.py

@app.function(
    image=image,
    secrets=secrets,
)
def init_services():
    """Initialize all services on container start."""
    from src.services.firebase import init_firebase
    init_firebase()
    print("Firebase initialized")
```

## Files to Create

| Path | Action | Description |
|------|--------|-------------|
| `agents/src/services/firebase.py` | Create | Firebase client with all CRUD ops |
| `agents/src/services/token_refresh.py` | Create | OAuth token refresh logic |

## Todo List

- [ ] Create Firebase project in console
- [ ] Enable Firestore database
- [ ] Generate service account key
- [ ] Add credentials to Modal secret
- [ ] Create firebase.py service
- [ ] Create token_refresh.py
- [ ] Deploy and test Firebase connection
- [ ] Set up Firestore security rules

## Success Criteria

- [ ] Firebase initializes in Modal container
- [ ] All CRUD operations work (users, tasks, tokens)
- [ ] Task claim uses atomic transactions
- [ ] Token management works for GitHub

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Credentials leak | Critical | Use Modal Secrets only |
| Firestore quotas | Service degradation | Monitor usage, batch writes |
| Transaction conflicts | Task duplicates | Use proper transactions |

## Security Considerations

- Service account has minimal permissions
- Credentials never logged
- Security rules block client access
- Tokens encrypted at rest (Firestore default)

## Next Steps

After completing this phase:
1. Proceed to Phase 3: Qdrant Vector Memory
2. Test task queue flow between agents
