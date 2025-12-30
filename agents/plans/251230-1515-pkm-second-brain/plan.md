---
title: "PKM Second Brain System"
description: "Personal knowledge management via Telegram - capture, organize, retrieve"
status: completed
priority: P1
effort: 16h
branch: main
tags: [pkm, telegram, firebase, qdrant, ai]
created: 2025-12-30
completed: 2025-12-30
review_status: completed
review_report: plans/reports/code-reviewer-251230-1538-pkm-review.md
review_grade: A-
---

# PKM Second Brain System

## Overview

Build personal knowledge management (PKM) system into Telegram bot. Users capture thoughts, ideas, tasks, and notes via quick commands. AI organizes and retrieves items via semantic search.

**Core Value:** Frictionless capture + AI organization + smart retrieval

## Architecture

```
User Message                  Commands
     │                            │
     ▼                            ▼
┌─────────────────────────────────────────────────┐
│              Telegram Webhook                    │
│   • Quick capture via reply/forward             │
│   • Commands: /save, /inbox, /tasks, /find      │
└───────────────────────┬─────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────┐
│              PKM Service Layer                   │
│   • src/services/pkm.py                         │
│   • Item CRUD, AI classification, suggestions   │
└───────────────────────┬─────────────────────────┘
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
┌─────────────────────┐    ┌─────────────────────┐
│     Firebase        │    │      Qdrant         │
│ pkm_items/{user_id} │    │   pkm_items         │
│   /items/{item_id}  │    │ (semantic search)   │
│                     │    │                     │
│ • Source of truth   │    │ • Derived index     │
│ • Metadata, status  │    │ • Embeddings        │
└─────────────────────┘    └─────────────────────┘
```

## Data Model

### Firebase: `pkm_items/{user_id}/items/{item_id}`

```python
{
    "id": "uuid",
    "user_id": int,
    "content": str,            # Original text
    "type": "note|task|idea|link|quote",
    "status": "inbox|active|done|archived",
    "tags": ["tag1", "tag2"],
    "project": str | None,     # Optional project grouping
    "priority": "low|medium|high" | None,
    "due_date": datetime | None,
    "outcome": str | None,     # For review: what came of this?
    "source": "telegram|voice|image",
    "created_at": datetime,
    "updated_at": datetime,
    "completed_at": datetime | None,
}
```

### Qdrant: `pkm_items` collection

```python
{
    "id": "pkm_{user_id}_{item_id}",
    "vector": [3072 dims],  # Gemini embedding
    "payload": {
        "user_id": int,
        "item_id": str,
        "type": str,
        "status": str,
        "tags": list,
        "content_preview": str[:200]
    }
}
```

---

## Phase 1: Core Capture & Storage (4h)

**Goal:** Basic CRUD with Firebase + Qdrant storage

### Phase 1A: Firebase PKM Module (2h)

**Files:**
- `src/services/firebase/pkm.py` (NEW)
- `src/services/firebase/__init__.py` (MODIFY - exports)

**Implementation:**

```python
# src/services/firebase/pkm.py
"""PKM item CRUD operations."""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Literal

ItemType = Literal["note", "task", "idea", "link", "quote"]
ItemStatus = Literal["inbox", "active", "done", "archived"]

@dataclass
class PKMItem:
    id: str
    user_id: int
    content: str
    type: ItemType
    status: ItemStatus
    tags: List[str]
    project: Optional[str]
    priority: Optional[str]
    due_date: Optional[datetime]
    outcome: Optional[str]
    source: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

async def create_item(user_id: int, content: str, item_type: ItemType = "note", **kwargs) -> PKMItem:
    """Create new PKM item."""

async def get_item(user_id: int, item_id: str) -> Optional[PKMItem]:
    """Get item by ID."""

async def update_item(user_id: int, item_id: str, **updates) -> Optional[PKMItem]:
    """Update item fields."""

async def delete_item(user_id: int, item_id: str) -> bool:
    """Delete item."""

async def list_items(
    user_id: int,
    status: Optional[ItemStatus] = None,
    item_type: Optional[ItemType] = None,
    limit: int = 20
) -> List[PKMItem]:
    """List items with optional filters."""

async def get_inbox(user_id: int, limit: int = 10) -> List[PKMItem]:
    """Get inbox items (status=inbox)."""

async def get_tasks(user_id: int, include_done: bool = False) -> List[PKMItem]:
    """Get task items."""
```

### Phase 1B: Qdrant PKM Collection (2h)

**Files:**
- `src/services/qdrant.py` (MODIFY - add pkm functions)

**Implementation:**

```python
# Add to src/services/qdrant.py

PKM_COLLECTION = "pkm_items"

def ensure_pkm_collection():
    """Create PKM collection if not exists."""

async def store_pkm_item(
    user_id: int,
    item_id: str,
    content: str,
    embedding: List[float],
    item_type: str,
    status: str,
    tags: List[str]
) -> bool:
    """Store PKM item embedding."""

async def search_pkm_items(
    user_id: int,
    embedding: List[float],
    limit: int = 5,
    status_filter: Optional[str] = None,
    type_filter: Optional[str] = None
) -> List[Dict]:
    """Search user's PKM items by embedding."""

async def delete_pkm_item(user_id: int, item_id: str) -> bool:
    """Delete PKM item from Qdrant."""

async def update_pkm_item_status(user_id: int, item_id: str, new_status: str) -> bool:
    """Update item status in Qdrant payload."""
```

### Success Criteria Phase 1

- [x] Firebase CRUD operations work ✓
- [x] Qdrant storage/search work ✓
- [x] Unit tests pass: `pytest tests/test_pkm.py` ✓ (20/20 passing)

---

## Phase 2: AI Organization (4h)

**Goal:** Auto-classify items, extract tags, suggest organization

### Phase 2A: PKM Service Layer (2h)

**Files:**
- `src/services/pkm.py` (NEW)

**Implementation:**

```python
# src/services/pkm.py
"""PKM service - orchestrates Firebase + Qdrant + AI."""

from src.services.firebase.pkm import PKMItem, create_item, update_item
from src.services.qdrant import store_pkm_item, search_pkm_items
from src.services.embeddings import get_embedding
from src.services.llm import get_llm_client

async def save_item(
    user_id: int,
    content: str,
    source: str = "telegram"
) -> PKMItem:
    """Save and classify new item.

    1. Classify type (note/task/idea/link/quote)
    2. Extract tags
    3. Store in Firebase
    4. Store embedding in Qdrant
    """

async def classify_item(content: str) -> Dict:
    """Use LLM to classify item type and extract tags.

    Returns: {"type": str, "tags": list, "priority": str|None}
    """

async def find_items(
    user_id: int,
    query: str,
    limit: int = 5
) -> List[PKMItem]:
    """Semantic search across user's items."""

async def get_related_items(
    user_id: int,
    item_id: str,
    limit: int = 3
) -> List[PKMItem]:
    """Find items related to given item."""

async def suggest_organization(
    user_id: int,
    item: PKMItem
) -> Dict:
    """Suggest project, tags, or related items."""
```

### Phase 2B: Classification Prompts (1h)

**Files:**
- `src/services/pkm.py` (classification logic)

**Classification Prompt:**

```
Analyze this item and classify it.

Item: {content}

Return JSON:
{
  "type": "note|task|idea|link|quote",
  "tags": ["tag1", "tag2"],  // 0-3 tags, lowercase
  "priority": "low|medium|high" | null,
  "has_deadline": boolean
}

Rules:
- "task" if action-oriented (do, fix, call, buy, etc.)
- "link" if contains URL
- "quote" if starts with quote marks or attribution
- "idea" if speculative/future-oriented
- "note" for everything else
```

### Phase 2C: Integration Tests (1h)

**Files:**
- `tests/test_pkm.py` (NEW)

**Test Cases:**
- Create item -> verify Firebase + Qdrant
- Classify task -> type="task"
- Classify URL -> type="link"
- Search items -> finds relevant
- Delete item -> removes from both stores

### Success Criteria Phase 2

- [x] Auto-classification works ✓
- [x] Tag extraction works ✓
- [x] Semantic search returns relevant items ✓
- [x] Integration tests pass ✓

---

## Phase 3: Commands & Outcomes (4h)

**Goal:** Full command set for PKM workflow

### Phase 3A: PKM Commands (2h)

**Files:**
- `commands/pkm.py` (NEW)
- `api/routes/telegram.py` (MODIFY - import new commands)

**Commands:**

```python
# commands/pkm.py

@command_router.command(
    name="/save",
    description="Quick capture - save anything",
    usage="/save <content> or reply to message",
    permission="user",
    category="pkm"
)
async def save_command(args: str, user: dict, chat_id: int) -> str:
    """Quick capture any content."""
    # Reply to message -> save that message's content
    # Args -> save args as content

@command_router.command(
    name="/inbox",
    description="View inbox items needing processing",
    usage="/inbox [limit]",
    permission="user",
    category="pkm"
)
async def inbox_command(args: str, user: dict, chat_id: int) -> str:
    """Show inbox items with action buttons."""
    # Returns inline keyboard for each item

@command_router.command(
    name="/tasks",
    description="View your tasks",
    usage="/tasks [all|done]",
    permission="user",
    category="pkm"
)
async def tasks_command(args: str, user: dict, chat_id: int) -> str:
    """Show active tasks."""

@command_router.command(
    name="/find",
    description="Search your notes",
    usage="/find <query>",
    permission="user",
    category="pkm"
)
async def find_command(args: str, user: dict, chat_id: int) -> str:
    """Semantic search across all items."""

@command_router.command(
    name="/outcome",
    description="Record outcome for an item",
    usage="/outcome <item_id> <outcome_text>",
    permission="user",
    category="pkm"
)
async def outcome_command(args: str, user: dict, chat_id: int) -> str:
    """Record what came of an idea/task."""

@command_router.command(
    name="/review",
    description="Weekly review of items",
    usage="/review",
    permission="user",
    category="pkm"
)
async def review_command(args: str, user: dict, chat_id: int) -> str:
    """Generate weekly review summary."""
```

### Phase 3B: Callback Handlers (1h)

**Files:**
- `main.py` (MODIFY - handle_callback for PKM actions)

**Callbacks:**

```python
# Add to handle_callback function

PKM_CALLBACKS = {
    "pkm_done": mark_item_done,      # Complete task/idea
    "pkm_archive": archive_item,      # Archive item
    "pkm_delete": delete_item,        # Delete item
    "pkm_edit": start_edit_mode,      # Enter edit mode
    "pkm_tag": add_tag_prompt,        # Add tag
    "pkm_project": assign_project,    # Assign to project
}
```

### Phase 3C: Weekly Digest (1h)

**Files:**
- `src/services/pkm.py` (add digest function)

**Implementation:**

```python
async def generate_weekly_digest(user_id: int) -> str:
    """Generate weekly review.

    Includes:
    - Items captured this week
    - Tasks completed
    - Items still in inbox
    - Outcomes recorded
    - Suggestions for stale items
    """
```

### Success Criteria Phase 3

- [x] All commands work: /save, /inbox, /tasks, /find, /outcome, /review ✓
- [ ] Inline keyboard actions work (not implemented)
- [x] Weekly digest generates useful summary ✓

---

## Phase 4: Proactive Features (3h) [Post-MVP]

**Goal:** Automated suggestions and reminders

### Phase 4A: Stale Item Detection

**Files:**
- `src/services/pkm.py` (add stale detection)

**Logic:**
- Items in inbox > 7 days -> suggest process or archive
- Tasks with past due_date -> remind
- Ideas with no outcome after 30 days -> prompt for follow-up

### Phase 4B: Daily Digest (Optional)

**Files:**
- `scripts/pkm-digest.py` (NEW - scheduled job)

**Scheduled via Modal cron:**
- Morning: Show today's tasks
- Evening: Prompt for capture
- Weekly: Full review digest

---

## Phase 5: Advanced Capture (2h) [Post-MVP]

**Goal:** Voice and image capture

### Phase 5A: Voice Notes

**Integration:**
- Extend `handle_voice_message()` in main.py
- Transcribe -> auto-save as PKM item
- Classify transcription

### Phase 5B: Image/Screenshot Capture

**Integration:**
- Extend `handle_image_message()` in main.py
- Extract text via Gemini vision
- Auto-save as PKM item with type="note"

---

## File Ownership Matrix

| File | Phase | Owner | Depends On |
|------|-------|-------|------------|
| `src/services/firebase/pkm.py` | 1A | Dev A | - |
| `src/services/qdrant.py` | 1B | Dev B | - |
| `src/services/pkm.py` | 2A | Dev A | 1A, 1B |
| `commands/pkm.py` | 3A | Dev B | 2A |
| `main.py` (callbacks) | 3B | Dev A | 3A |
| `tests/test_pkm.py` | 2C | Dev B | 2A |

**Parallel Execution:**
- Phase 1A || Phase 1B (no deps)
- Phase 2A after 1A+1B complete
- Phase 3A || Phase 3B (both depend on 2A)

---

## Dependency Graph

```
Phase 1A (Firebase)    Phase 1B (Qdrant)
        │                    │
        └────────┬───────────┘
                 │
                 ▼
           Phase 2A (PKM Service)
                 │
                 ├────────┬──────────┐
                 │        │          │
                 ▼        ▼          ▼
           Phase 2B   Phase 2C   Phase 3A
           (Prompts)  (Tests)   (Commands)
                                     │
                                     ▼
                               Phase 3B
                              (Callbacks)
                                     │
                                     ▼
                               Phase 3C
                               (Digest)
```

---

## Testing Strategy

### Unit Tests (Phase 2C)

```python
# tests/test_pkm.py

class TestPKMFirebase:
    async def test_create_item(self):
        """Create item, verify fields."""

    async def test_update_item(self):
        """Update item, verify changes."""

    async def test_list_items_filter(self):
        """List with status/type filter."""

class TestPKMQdrant:
    async def test_store_and_search(self):
        """Store item, search returns it."""

    async def test_user_isolation(self):
        """User A can't find User B's items."""

class TestPKMClassification:
    async def test_classify_task(self):
        """'Buy groceries' -> type=task"""

    async def test_classify_link(self):
        """'https://...' -> type=link"""

    async def test_classify_note(self):
        """'Meeting notes: ...' -> type=note"""
```

### Integration Tests

```python
class TestPKMIntegration:
    async def test_save_and_find(self):
        """Full flow: save -> classify -> find."""

    async def test_inbox_workflow(self):
        """Save -> inbox -> process -> done."""
```

---

## Rollout Plan

1. **Phase 1-2:** Backend ready, no user-facing changes
2. **Phase 3:** Enable commands for admin only (testing)
3. **Phase 3:** Enable for `developer` tier (beta)
4. **Phase 3:** Enable for all `user` tier (GA)

---

---

## Code Review Summary (2025-12-30)

**Report:** [code-reviewer-251230-1538-pkm-review.md](../reports/code-reviewer-251230-1538-pkm-review.md)
**Grade:** A- (High quality with minor improvements needed)
**Test Status:** 20/20 passing ✓

### Critical Issues: None ✓

### High Priority Fixes Recommended:
1. **[H2]** Add user_id validation (prevent None/string IDs)
2. **[H3]** Change create_item circuit to non-blocking (improve availability)
3. **[H4]** Optimize get_related_items (N+1 query → batch fetch)

### Implementation Status:
- **Phase 1 (Core Capture):** ✓ Complete
- **Phase 2 (AI Organization):** ✓ Complete
- **Phase 3 (Commands):** ✓ Complete (except inline keyboard)
- **Phase 4 (Proactive):** Pending
- **Phase 5 (Advanced Capture):** Pending

### Production Readiness:
✓ Can deploy with current state (no blocking issues)
⚠️ Priority fixes before scale (H2, H3, H4)

---

## Unresolved Questions

1. **Item Limits:** Max items per user? Suggest 1000 for free tier
2. **Retention:** Auto-archive items older than X days?
3. **Export:** Should users be able to export all items? Format?
4. **Sharing:** Future feature for shared items/projects?
5. **Natural Language Capture:** Should forwarded messages auto-save without /save?
6. **Web UI plans?** If yes, input sanitization becomes CRITICAL (see review H1)
7. **Expected user scale?** If 1000+ concurrent users, N+1 fix (H4) needs immediate attention
