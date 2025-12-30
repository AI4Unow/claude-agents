"""Conversation Finite State Machine.

Tracks conversation state per user for intelligent routing.
States: onboarding, idle, processing, awaiting_input, in_flow
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    flow_type: str = ""
    current_step: int = 0
    total_steps: int = 0
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FSMState:
    """Complete FSM state for a user."""
    state: ConversationState = "idle"
    pending_action: Optional[str] = None
    pending_skill: Optional[str] = None
    flow: Optional[FlowContext] = None
    last_updated: str = ""

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


# Valid state transitions: (current, event) -> new_state
TRANSITIONS = {
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
            logger.debug("fsm_transition", user_id=self.user_id, old=old, event=event, new=new_state)
        else:
            logger.debug("fsm_invalid_transition", user_id=self.user_id, state=self._state.state, event=event)

        return self._state.state

    def set_pending_action(self, action: str) -> None:
        """Set pending action (waiting for user input)."""
        self._state.pending_action = action
        self._dirty = True

    def clear_pending_action(self) -> None:
        """Clear pending action."""
        self._state.pending_action = None
        self._dirty = True

    def set_pending_skill(self, skill: str) -> None:
        """Set pending skill (waiting for task)."""
        self._state.pending_skill = skill
        self._dirty = True

    def clear_pending_skill(self) -> None:
        """Clear pending skill."""
        self._state.pending_skill = None
        self._dirty = True

    def start_flow(self, flow_type: str, total_steps: int, initial_data: dict = None) -> None:
        """Start a multi-step flow."""
        self._state.flow = FlowContext(
            flow_type=flow_type,
            current_step=1,
            total_steps=total_steps,
            data=initial_data or {}
        )
        self._state.state = "in_flow"
        self._dirty = True

    def advance_flow(self, data: dict = None) -> None:
        """Advance to next step in flow."""
        if self._state.flow:
            self._state.flow.current_step += 1
            if data:
                self._state.flow.data.update(data)
            self._dirty = True

    def end_flow(self) -> None:
        """End current flow."""
        self._state.flow = None
        self._state.state = "idle"
        self._dirty = True

    async def save(self) -> None:
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

    def reset(self) -> None:
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
