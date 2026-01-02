"""SDK tools package - all tools for agent."""

from typing import List, Callable

from .web_search import web_search
from .memory import search_memory
from .code_exec import run_python
from .datetime_tool import get_datetime
from .gemini import gemini_vision, gemini_grounding, gemini_thinking
from .tasks import task_create, task_list, task_complete


def get_all_tools() -> List[Callable]:
    """Get all SDK tools for agent.

    Returns:
        List of @tool decorated functions
    """
    return [
        web_search,
        search_memory,
        run_python,
        get_datetime,
        gemini_vision,
        gemini_grounding,
        gemini_thinking,
        task_create,
        task_list,
        task_complete,
    ]


__all__ = [
    "get_all_tools",
    "web_search",
    "search_memory",
    "run_python",
    "get_datetime",
    "gemini_vision",
    "gemini_grounding",
    "gemini_thinking",
    "task_create",
    "task_list",
    "task_complete",
]
