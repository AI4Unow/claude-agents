"""Status message utilities for Telegram.

Provides contextual status updates during processing.
Centralizes status text and update logic.
"""
from enum import Enum
from typing import Callable, Awaitable, Optional, List


class ProcessingStatus(Enum):
    """Standard processing status messages."""
    PROCESSING = "🔄 Processing..."
    DETECTING_INTENT = "🧠 Understanding..."
    ROUTING_SKILL = "🔍 Finding skill..."
    RUNNING_SKILL = "⚡ Running {skill_name}..."
    SEARCHING = "🔎 Searching..."
    THINKING = "💭 Thinking..."
    GENERATING = "📝 Generating..."
    COMPLETE = "✅ Complete"
    ERROR = "❌ Error"


# Status templates by intent type
STATUS_TEMPLATES = {
    "chat": ["💭 Thinking...", "📝 Responding..."],
    "skill": ["🔍 Finding skill...", "⚡ Running {skill}...", "📝 Finalizing..."],
    "orchestrate": ["🧠 Planning...", "🔧 Executing...", "📝 Compiling..."],
    "research": ["🔍 Searching...", "📚 Analyzing...", "📝 Writing..."],
}


class StatusUpdater:
    """Manages status message updates for a processing session.

    Usage:
        updater = StatusUpdater(chat_id, msg_id, edit_fn)
        await updater.update("Processing...")
        await updater.skill("gemini-research")
        await updater.complete()
    """

    def __init__(
        self,
        chat_id: int,
        message_id: int,
        edit_fn: Callable[[int, int, str], Awaitable[None]]
    ):
        self.chat_id = chat_id
        self.message_id = message_id
        self.edit_fn = edit_fn
        self.current_status: Optional[str] = None

    async def update(self, status: str, **kwargs) -> None:
        """Update status message.

        Args:
            status: Status text (may contain {placeholders})
            **kwargs: Values for placeholders
        """
        formatted = status.format(**kwargs) if kwargs else status
        # Skip if same status
        if formatted == self.current_status:
            return
        self.current_status = formatted
        await self.edit_fn(self.chat_id, self.message_id, f"<i>{formatted}</i>")

    async def intent(self) -> None:
        """Show intent detection status."""
        await self.update(ProcessingStatus.DETECTING_INTENT.value)

    async def routing(self) -> None:
        """Show skill routing status."""
        await self.update(ProcessingStatus.ROUTING_SKILL.value)

    async def skill(self, skill_name: str) -> None:
        """Show skill execution status."""
        await self.update(f"⚡ Running {skill_name}...")

    async def orchestrate(self) -> None:
        """Show orchestration status."""
        await self.update("🧠 Planning approach...")

    async def thinking(self) -> None:
        """Show thinking status for chat."""
        await self.update(ProcessingStatus.THINKING.value)

    async def complete(self) -> None:
        """Mark processing complete."""
        await self.update(ProcessingStatus.COMPLETE.value)

    async def error(self, msg: str = None) -> None:
        """Mark processing failed."""
        status = f"❌ {msg[:100]}" if msg else ProcessingStatus.ERROR.value
        await self.update(status)


def get_skill_status_sequence(skill_name: str) -> List[str]:
    """Get status messages for skill execution.

    Args:
        skill_name: Name of skill being executed

    Returns:
        List of status messages to show during execution
    """
    base = [f"⚡ Running {skill_name}..."]

    # Skill-specific additions
    if "research" in skill_name.lower():
        base.extend(["📚 Analyzing sources...", "📝 Writing report..."])
    elif "code" in skill_name.lower():
        base.extend(["💻 Reviewing code...", "📝 Formatting..."])
    elif "design" in skill_name.lower():
        base.extend(["🎨 Creating design...", "📝 Finalizing..."])
    else:
        base.append("📝 Generating response...")

    return base
