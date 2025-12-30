# Phase 03: Conversation FSM

**Priority:** P1 (Intelligence Layer)
**Effort:** Medium
**Impact:** High - Foundation for intelligent routing

---

## Objective

Implement conversation state machine to track user context, handle multi-step flows, and enable smarter responses.

## Current State

- No conversation state tracking
- Each message processed independently
- Pending skill state exists but limited

## Target State

```
User states:
├── onboarding    → First-time user, guided intro
├── idle          → Ready for new request
├── processing    → Skill/LLM running
├── awaiting_input → Bot asked question, waiting reply
└── in_flow       → Multi-step workflow active (research → report → share)
```

## Implementation

### Task 1: Create FSM module

**File:** `agents/src/core/conversation_fsm.py` (NEW)

```python
"""Conversation Finite State Machine.

Tracks conversation state per user for intelligent routing.
States: onboarding, idle, processing, awaiting_input, in_flow
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Literal, Optional

from src.utils.logging import get_logger

logger = get_logger()


ConversationState = Literal[
    "onboarding",     # First-time user, guided intro
    "idle",           # Ready for new request
    "processing",     # Skill/LLM running
    "awaiting_input", # Bot asked question, waiting reply
    "in_flow",        # Multi-step workflow active
]


@dataclass
class FlowContext:
    """Context for multi-step flows."""
    flow_type: str = ""         # "research", "document", etc.
    current_step: int = 0
    total_steps: int = 0
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FSMState:
    """Complete FSM state for a user."""
    state: ConversationState = "idle"
    pending_action: Optional[str] = None      # Action waiting for input
    pending_skill: Optional[str] = None       # Skill waiting for task
    flow: Optional[FlowContext] = None        # Multi-step flow context
    last_updated: str = ""                    # ISO timestamp

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "pending_action": self.pending_action,
            "pending_skill": self.pending_skill,
            "flow": {
                "flow_type": self.flow.flow_type,
                "current_step": self.flow.current_step,
                "total_steps": self.flow.total_steps,
                "data": self.flow.data,
            } if self.flow else None,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FSMState":
        flow_data = data.get("flow")
        flow = None
        if flow_data:
            flow = FlowContext(
                flow_type=flow_data.get("flow_type", ""),
                current_step=flow_data.get("current_step", 0),
                total_steps=flow_data.get("total_steps", 0),
                data=flow_data.get("data", {}),
            )
        return cls(
            state=data.get("state", "idle"),
            pending_action=data.get("pending_action"),
            pending_skill=data.get("pending_skill"),
            flow=flow,
            last_updated=data.get("last_updated", ""),
        )


# Valid state transitions
TRANSITIONS = {
    # (current_state, event) -> new_state
    ("onboarding", "complete"): "idle",
    ("onboarding", "skip"): "idle",

    ("idle", "start_processing"): "processing",
    ("idle", "ask_user"): "awaiting_input",
    ("idle", "start_flow"): "in_flow",

    ("processing", "complete"): "idle",
    ("processing", "need_input"): "awaiting_input",
    ("processing", "error"): "idle",

    ("awaiting_input", "user_replied"): "processing",
    ("awaiting_input", "cancel"): "idle",
    ("awaiting_input", "timeout"): "idle",

    ("in_flow", "step_complete"): "in_flow",
    ("in_flow", "flow_complete"): "idle",
    ("in_flow", "cancel"): "idle",
}


class ConversationFSM:
    """Manages conversation state for a single user.

    Usage:
        fsm = await get_fsm(user_id)
        new_state = await fsm.transition("start_processing")
        await fsm.save()
    """

    COLLECTION = "conversation_fsm"
    TTL = 3600 * 24  # 24 hours

    def __init__(self, user_id: int, state: FSMState = None):
        self.user_id = user_id
        self._state = state or FSMState()
        self._dirty = False

    @property
    def state(self) -> ConversationState:
        return self._state.state

    @property
    def pending_action(self) -> Optional[str]:
        return self._state.pending_action

    @property
    def pending_skill(self) -> Optional[str]:
        return self._state.pending_skill

    @property
    def flow(self) -> Optional[FlowContext]:
        return self._state.flow

    async def transition(self, event: str) -> ConversationState:
        """Attempt state transition based on event.

        Args:
            event: Event name (e.g., "start_processing", "complete")

        Returns:
            New state after transition (may be unchanged if invalid)
        """
        key = (self._state.state, event)
        new_state = TRANSITIONS.get(key)

        if new_state:
            old = self._state.state
            self._state.state = new_state
            self._state.last_updated = datetime.now(timezone.utc).isoformat()
            self._dirty = True
            logger.debug(
                "fsm_transition",
                user_id=self.user_id,
                old=old,
                event=event,
                new=new_state
            )
        else:
            logger.debug(
                "fsm_invalid_transition",
                user_id=self.user_id,
                state=self._state.state,
                event=event
            )

        return self._state.state

    def set_pending_action(self, action: str):
        """Set pending action (waiting for user input)."""
        self._state.pending_action = action
        self._dirty = True

    def clear_pending_action(self):
        """Clear pending action."""
        self._state.pending_action = None
        self._dirty = True

    def set_pending_skill(self, skill: str):
        """Set pending skill (waiting for task)."""
        self._state.pending_skill = skill
        self._dirty = True

    def clear_pending_skill(self):
        """Clear pending skill."""
        self._state.pending_skill = None
        self._dirty = True

    def start_flow(self, flow_type: str, total_steps: int, initial_data: dict = None):
        """Start a multi-step flow."""
        self._state.flow = FlowContext(
            flow_type=flow_type,
            current_step=1,
            total_steps=total_steps,
            data=initial_data or {}
        )
        self._state.state = "in_flow"
        self._dirty = True

    def advance_flow(self, data: dict = None):
        """Advance to next step in flow."""
        if self._state.flow:
            self._state.flow.current_step += 1
            if data:
                self._state.flow.data.update(data)
            self._dirty = True

    def end_flow(self):
        """End current flow."""
        self._state.flow = None
        self._state.state = "idle"
        self._dirty = True

    async def save(self):
        """Persist state to L1 cache + L2 Firebase."""
        if not self._dirty:
            return

        from src.core.state import get_state_manager
        state_mgr = get_state_manager()

        self._state.last_updated = datetime.now(timezone.utc).isoformat()
        await state_mgr.set(
            self.COLLECTION,
            str(self.user_id),
            self._state.to_dict(),
            ttl_seconds=self.TTL
        )
        self._dirty = False

    def reset(self):
        """Reset to idle state."""
        self._state = FSMState()
        self._dirty = True


async def get_fsm(user_id: int) -> ConversationFSM:
    """Get or create FSM for user.

    Args:
        user_id: Telegram user ID

    Returns:
        ConversationFSM instance with loaded state
    """
    from src.core.state import get_state_manager
    state_mgr = get_state_manager()

    data = await state_mgr.get(
        ConversationFSM.COLLECTION,
        str(user_id),
        ttl_seconds=ConversationFSM.TTL
    )

    if data:
        fsm_state = FSMState.from_dict(data)
        return ConversationFSM(user_id, fsm_state)

    return ConversationFSM(user_id)


def is_interruptible(state: ConversationState) -> bool:
    """Check if state can be interrupted by new request."""
    return state in ("idle", "awaiting_input")


def requires_input_handling(state: ConversationState) -> bool:
    """Check if state requires special input handling."""
    return state in ("awaiting_input", "in_flow")
```

### Task 2: Integrate FSM in webhook

**File:** `agents/api/routes/telegram.py`

Add FSM check before processing:

```python
# After extracting user_data and chat_id (around line 70)
from src.core.conversation_fsm import get_fsm, requires_input_handling

# Get user FSM state
user_id = user_data.get("id")
fsm = await get_fsm(user_id)

# Check if in awaiting_input state
if requires_input_handling(fsm.state):
    # Handle as reply to pending action/skill
    if fsm.pending_skill:
        # User is providing task for selected skill
        response = await execute_skill_with_fsm(fsm, text, user_data, chat_id)
        await fsm.save()
        if response:
            await send_telegram_message(chat_id, response)
        return {"ok": True}

    elif fsm.pending_action:
        # User is replying to a question
        response = await handle_pending_action(fsm, text, user_data, chat_id)
        await fsm.save()
        if response:
            await send_telegram_message(chat_id, response)
        return {"ok": True}

# Normal processing path...
```

### Task 3: Update process_message to use FSM

**File:** `agents/main.py`

```python
async def process_message(
    text: str,
    user: dict,
    chat_id: int,
    message_id: int = None
) -> str:
    """Process message with FSM state tracking."""
    from src.core.conversation_fsm import get_fsm

    user_id = user.get("id")
    fsm = await get_fsm(user_id)

    # Transition to processing
    await fsm.transition("start_processing")
    await fsm.save()

    try:
        # ... existing processing logic ...

        # On success
        await fsm.transition("complete")
        await fsm.save()
        return result

    except Exception as e:
        await fsm.transition("error")
        await fsm.save()
        raise
```

### Task 4: Add FSM-aware skill execution

**File:** `agents/main.py`

```python
async def execute_skill_with_fsm(
    fsm: "ConversationFSM",
    task: str,
    user: dict,
    chat_id: int
) -> str:
    """Execute skill using FSM pending skill."""
    skill_name = fsm.pending_skill
    fsm.clear_pending_skill()

    # Transition to processing
    await fsm.transition("user_replied")

    # Execute skill
    result = await execute_skill_simple(skill_name, task, {"user": user})

    # Complete
    await fsm.transition("complete")

    return result
```

## Testing

```python
# tests/test_conversation_fsm.py
import pytest
from src.core.conversation_fsm import (
    ConversationFSM,
    FSMState,
    get_fsm,
    TRANSITIONS,
)

def test_valid_transitions():
    fsm = ConversationFSM(123)
    assert fsm.state == "idle"

    # idle -> processing
    new_state = await fsm.transition("start_processing")
    assert new_state == "processing"

    # processing -> idle
    new_state = await fsm.transition("complete")
    assert new_state == "idle"

def test_invalid_transition():
    fsm = ConversationFSM(123)
    # Can't go from idle to in_flow via complete
    new_state = await fsm.transition("complete")
    assert new_state == "idle"  # Unchanged

def test_flow_management():
    fsm = ConversationFSM(123)
    fsm.start_flow("research", total_steps=3)

    assert fsm.state == "in_flow"
    assert fsm.flow.current_step == 1

    fsm.advance_flow({"topic": "AI"})
    assert fsm.flow.current_step == 2
    assert fsm.flow.data["topic"] == "AI"

def test_serialization():
    fsm = ConversationFSM(123)
    fsm.start_flow("test", 2)
    fsm.set_pending_action("confirm")

    data = fsm._state.to_dict()
    restored = FSMState.from_dict(data)

    assert restored.state == "in_flow"
    assert restored.pending_action == "confirm"
    assert restored.flow.flow_type == "test"
```

## Acceptance Criteria

- [ ] FSM state persists across messages
- [ ] State transitions follow defined rules
- [ ] Invalid transitions are rejected gracefully
- [ ] Pending skill/action handled correctly
- [ ] Multi-step flows work (start, advance, complete)
- [ ] FSM state survives container restarts (L2 Firebase)

## Rollback

1. Remove FSM checks from telegram.py webhook
2. Remove FSM updates from process_message
3. Keep conversation_fsm.py (no harm if unused)
