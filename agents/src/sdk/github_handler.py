"""GitHub webhook handler using SDK agent."""

from typing import Dict, Any
import structlog

from src.sdk import create_agent, run_agent
from src.sdk.config import AgentConfig

logger = structlog.get_logger()


async def run_github_agent(event_type: str, payload: Dict[str, Any]) -> str:
    """Run GitHub agent for webhook events.

    Args:
        event_type: GitHub event type (push, pull_request, issue, etc.)
        payload: GitHub webhook payload

    Returns:
        Agent response
    """
    try:
        # GitHub agent uses admin tier (no limits)
        agent = create_agent(
            user_id=0,  # System user
            tier="admin",
            config=AgentConfig(model="claude-sonnet-4-20250514"),
        )

        # Format prompt with event details
        prompt = f"""GitHub {event_type} event:

Repository: {payload.get('repository', {}).get('full_name', 'unknown')}
Sender: {payload.get('sender', {}).get('login', 'unknown')}

Event Data:
{str(payload)[:1000]}

Analyze this event and determine appropriate actions."""

        response = await run_agent(agent, prompt)

        logger.info("github_agent_success", event_type=event_type)
        return response

    except Exception as e:
        logger.error("github_agent_failed", error=str(e)[:100], event_type=event_type)
        raise
