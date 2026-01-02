"""Content agent handler using SDK agent."""

from typing import Dict, Any
import structlog

from src.sdk import create_agent, run_agent

logger = structlog.get_logger()


async def run_content_agent(
    user_id: int,
    skill_name: str,
    params: Dict[str, Any]
) -> str:
    """Run content agent for skill execution.

    Args:
        user_id: User's Telegram ID
        skill_name: Name of skill to execute
        params: Skill parameters

    Returns:
        Agent response
    """
    try:
        # Get user tier from Firebase
        from src.services.firebase.users import get_user_tier
        tier = await get_user_tier(user_id)

        # Create agent with user's tier
        agent = create_agent(user_id=user_id, tier=tier)

        # Format prompt for skill execution
        prompt = f"""Execute the '{skill_name}' skill with these parameters:

Parameters:
{str(params)[:500]}

Complete the requested operation and report results."""

        response = await run_agent(agent, prompt, context={"skill": skill_name})

        logger.info("content_agent_success", user_id=user_id, skill=skill_name)
        return response

    except Exception as e:
        logger.error("content_agent_failed", error=str(e)[:100], user_id=user_id, skill=skill_name)
        raise
