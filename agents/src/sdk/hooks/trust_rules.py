"""Trust rules as PreToolUse hook."""

from claude_agents import Hook, PreToolUseResult, PostToolUseResult
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional
import structlog

logger = structlog.get_logger()


class TrustLevel(Enum):
    AUTO_SILENT = "auto_silent"
    AUTO_NOTIFY = "auto_notify"
    CONFIRM = "confirm"


@dataclass
class ActionRule:
    trust: TrustLevel
    template: Optional[str] = None


DEFAULT_RULES = {
    "task_create": ActionRule(TrustLevel.AUTO_NOTIFY, "Created: {content}"),
    "task_update": ActionRule(TrustLevel.AUTO_NOTIFY, "Updated: {task_id}"),
    "task_delete": ActionRule(TrustLevel.CONFIRM),
    "calendar_write": ActionRule(TrustLevel.CONFIRM),
    "web_search": ActionRule(TrustLevel.AUTO_SILENT),
    "search_memory": ActionRule(TrustLevel.AUTO_SILENT),
}


class TrustRulesHook(Hook):
    """Enforce trust rules before tool execution."""

    def __init__(self, user_id: int, rules: Dict[str, ActionRule] = None):
        self.user_id = user_id
        self.rules = rules or DEFAULT_RULES

    async def pre_tool_use(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
    ) -> PreToolUseResult:
        rule = self.rules.get(tool_name, ActionRule(TrustLevel.CONFIRM))

        if rule.trust == TrustLevel.CONFIRM:
            return PreToolUseResult(
                allow=False,
                message=f"Confirm {tool_name}? Reply 'yes' to proceed.",
            )

        return PreToolUseResult(allow=True)

    async def post_tool_use(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Any,
    ) -> PostToolUseResult:
        rule = self.rules.get(tool_name)
        if rule and rule.trust == TrustLevel.AUTO_NOTIFY and rule.template:
            msg = rule.template.format(**tool_input)
            await self._notify(msg)
        return PostToolUseResult()

    async def _notify(self, message: str):
        from src.services.telegram import send_message
        await send_message(self.user_id, f"[ai4u.now] {message}")
