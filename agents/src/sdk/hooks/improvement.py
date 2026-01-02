"""Self-improvement trigger as PostToolUse hook."""

from claude_agents import Hook, PostToolUseResult
from typing import Dict, Any
import structlog

from src.core.improvement import get_improvement_service

logger = structlog.get_logger()


class ImprovementHook(Hook):
    """Trigger self-improvement on tool errors."""

    def __init__(self, skill_name: str = None):
        self.skill_name = skill_name

    async def post_tool_use(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Any,
    ) -> PostToolUseResult:
        if isinstance(tool_output, Exception):
            improvement_service = get_improvement_service()
            proposal = await improvement_service.analyze_error(
                skill_name=self.skill_name or tool_name,
                error=str(tool_output),
                context={"tool": tool_name, "input": tool_input},
            )
            if proposal:
                await improvement_service.store_proposal(proposal)
                logger.info("improvement_triggered", tool=tool_name, proposal_id=proposal.id)

        return PostToolUseResult()
