"""Base agent class implementing II Framework.

II Framework = Information (.md) + Implementation (.py)
- info.md: Mutable instructions stored in Modal Volume
- agent.py: Immutable code deployed to Modal Server
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Optional, List
from pathlib import Path

from src.utils.logging import get_logger
from src.services.llm import get_llm_client

logger = get_logger()


class BaseAgent(ABC):
    """Base class for all agents using II Framework.

    Each agent reads instructions from /skills/{agent_id}/info.md
    and can self-improve by rewriting that file.
    """

    def __init__(self, agent_id: str):
        """Initialize agent.

        Args:
            agent_id: Unique identifier for this agent (e.g., 'telegram-chat')
        """
        self.agent_id = agent_id
        self.logger = logger.bind(agent_id=agent_id)
        self.skills_path = Path("/skills")
        self.info_path = self.skills_path / agent_id / "info.md"
        self.llm = get_llm_client()

    @abstractmethod
    async def process(self, task: dict) -> dict:
        """Process a task and return result. Must be implemented by subclasses."""
        pass

    def read_instructions(self) -> str:
        """Read current instructions from info.md (Information layer)."""
        if self.info_path.exists():
            return self.info_path.read_text()
        return ""

    def write_instructions(self, content: str) -> None:
        """Write updated instructions to info.md (Self-improvement).

        Note: Must call volume.commit() after this in the Modal function.
        """
        self.info_path.parent.mkdir(parents=True, exist_ok=True)
        self.info_path.write_text(content)

    def execute_with_llm(
        self,
        user_message: str,
        context: Optional[List[Dict]] = None,
    ) -> str:
        """Execute task using LLM with info.md as system instructions.

        Args:
            user_message: User's request
            context: Previous conversation context

        Returns:
            LLM response text
        """
        # Read current instructions (self-improving, may have changed)
        instructions = self.read_instructions()

        # Build messages with context
        messages = []
        if context:
            for c in context[-5:]:  # Last 5 messages
                messages.append({
                    "role": c.get("role", "user"),
                    "content": c.get("content", "")
                })

        messages.append({"role": "user", "content": user_message})

        try:
            response = self.llm.chat(
                messages=messages,
                system=instructions,
                max_tokens=2048,
            )
            return response

        except Exception as e:
            self.logger.error("llm_error", error=str(e))
            raise

    async def self_improve(self, error: str, context: str = "") -> str:
        """Self-improvement loop: LLM analyzes error and rewrites info.md.

        Args:
            error: Error message or issue description
            context: Additional context about what went wrong

        Returns:
            Improved instructions
        """
        current_instructions = self.read_instructions()

        improvement_prompt = f"""You are improving your own instructions based on an error.

CURRENT INSTRUCTIONS:
{current_instructions}

ERROR ENCOUNTERED:
{error}

CONTEXT:
{context}

Analyze what went wrong and rewrite the instructions to prevent this error.
Return the complete updated instructions in markdown format.
Add this fix to the "## Error History" section with today's date ({datetime.now().strftime('%Y-%m-%d')}).
Update "## Memory" section with what you learned."""

        improved = self.llm.chat(
            messages=[{"role": "user", "content": improvement_prompt}],
            max_tokens=4096,
        )

        self.write_instructions(improved)

        self.logger.info("self_improved",
            agent=self.agent_id,
            error_summary=error[:100]
        )

        return improved

    async def log_activity(self, action: str, details: dict, level: str = "info"):
        """Log agent activity to Firebase (implemented in firebase service)."""
        # Will be implemented in Phase 2
        self.logger.log(level, action, **details)
