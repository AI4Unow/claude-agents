"""Agentic loop service for tool execution."""
from typing import List, Dict, Optional
from src.services.llm import get_llm_client
from src.tools import get_registry, init_default_tools
import structlog

logger = structlog.get_logger()

MAX_ITERATIONS = 5


async def run_agentic_loop(
    user_message: str,
    system: Optional[str] = None,
    context: Optional[List[Dict]] = None,
) -> str:
    """Run agentic loop with tool execution.

    Args:
        user_message: User's input
        system: System prompt
        context: Previous conversation messages

    Returns:
        Final text response
    """
    # Initialize tools
    init_default_tools()
    registry = get_registry()
    tools = registry.get_definitions()

    # Build initial messages
    messages = []
    if context:
        messages.extend(context[-5:])  # Last 5 for context
    messages.append({"role": "user", "content": user_message})

    llm = get_llm_client()
    iterations = 0
    accumulated_text = []

    while iterations < MAX_ITERATIONS:
        iterations += 1
        logger.info("agentic_iteration", iteration=iterations)

        # Call LLM with tools
        response = llm.chat(
            messages=messages,
            system=system,
            max_tokens=4096,
            tools=tools if tools else None,
        )

        # Collect text content
        for block in response.content:
            if block.type == "text":
                accumulated_text.append(block.text)

        # Check if done
        if response.stop_reason == "end_turn":
            logger.info("agentic_complete", iterations=iterations)
            break

        # Process tool calls
        if response.stop_reason == "tool_use":
            # Append assistant response to history
            messages.append({
                "role": "assistant",
                "content": response.content
            })

            # Execute tools and collect results
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    logger.info("tool_call", name=block.name, input=str(block.input)[:50])
                    result = await registry.execute(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                        "is_error": result.startswith("Search failed") or result.startswith("Error") or result.startswith("Tool error")
                    })

            # Append tool results as user message
            messages.append({
                "role": "user",
                "content": tool_results
            })

    if iterations >= MAX_ITERATIONS:
        logger.warning("agentic_max_iterations", max=MAX_ITERATIONS)
        accumulated_text.append("\n\n[Note: Reached maximum iterations limit]")

    return "\n".join(accumulated_text)
