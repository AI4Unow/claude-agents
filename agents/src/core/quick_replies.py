"""Quick reply buttons for contextual follow-up actions.

Provides inline keyboard buttons based on response context.
"""
from typing import Dict, List, Optional

from src.utils.logging import get_logger

logger = get_logger()


# Quick reply configurations per skill
QUICK_REPLIES = {
    # Research skills
    "gemini-deep-research": [
        {"text": "📥 Download PDF", "action": "download_report"},
        {"text": "🔄 Dig Deeper", "action": "research_more"},
        {"text": "📤 Share", "action": "share_report"},
    ],
    "gemini-grounding": [
        {"text": "🔍 More Details", "action": "expand"},
        {"text": "📚 Sources", "action": "show_sources"},
    ],

    # Code skills
    "code-review": [
        {"text": "🔧 Apply Fixes", "action": "apply_fixes"},
        {"text": "📝 Explain", "action": "explain_code"},
    ],
    "debugging": [
        {"text": "🔧 Fix It", "action": "fix_issue"},
        {"text": "🔍 Root Cause", "action": "root_cause"},
    ],

    # Design skills
    "canvas-design": [
        {"text": "🎨 Variations", "action": "design_variations"},
        {"text": "📐 Resize", "action": "resize"},
    ],
    "ui-ux-pro-max": [
        {"text": "💻 Code It", "action": "generate_code"},
        {"text": "🎨 More Options", "action": "more_designs"},
    ],

    # Document skills
    "pdf": [
        {"text": "📄 Summary", "action": "summarize"},
        {"text": "🔍 Find Text", "action": "search_doc"},
    ],

    # Default for any skill
    "_default": [
        {"text": "🔍 More Info", "action": "expand"},
        {"text": "🔄 Try Again", "action": "retry"},
    ],

    # Chat responses (no skill)
    "_chat": [
        {"text": "🔍 Search Web", "action": "web_search"},
        {"text": "📚 Learn More", "action": "learn_more"},
    ],
}


def build_quick_replies(context: Dict, max_buttons: int = 3) -> List[List[Dict]]:
    """Build inline keyboard for quick replies.

    Args:
        context: Response context with skill, type, etc.
        max_buttons: Maximum buttons to show

    Returns:
        Inline keyboard rows for Telegram
    """
    skill = context.get("skill")
    response_type = context.get("type", "chat")

    # Get reply config
    if skill and skill in QUICK_REPLIES:
        replies = QUICK_REPLIES[skill]
    elif skill:
        replies = QUICK_REPLIES["_default"]
    elif response_type == "chat":
        replies = QUICK_REPLIES["_chat"]
    else:
        return []

    # Build keyboard (limit to max_buttons)
    buttons = []
    for reply in replies[:max_buttons]:
        callback_data = f"qr:{reply['action']}"
        # Include skill for action context
        if skill:
            callback_data += f":{skill}"

        buttons.append({
            "text": reply["text"],
            "callback_data": callback_data
        })

    # Single row or split into 2-button rows
    if len(buttons) <= 2:
        return [buttons]
    else:
        rows = []
        for i in range(0, len(buttons), 2):
            rows.append(buttons[i:i+2])
        return rows


def get_action_prompt(action: str, original_context: Dict) -> Optional[str]:
    """Get prompt for quick reply action.

    Args:
        action: Action identifier
        original_context: Context from original request

    Returns:
        Prompt to execute for the action, or None for special actions
    """
    original_query = original_context.get("query", "")

    ACTION_PROMPTS = {
        # Research actions
        "download_report": None,  # Special: trigger download
        "research_more": f"Provide more in-depth research on: {original_query}",
        "share_report": None,  # Special: trigger share
        "expand": f"Expand on this with more details: {original_query}",
        "show_sources": "List all sources used in the previous response",

        # Code actions
        "apply_fixes": "Apply the suggested fixes to the code",
        "explain_code": "Explain the code in more detail, step by step",
        "fix_issue": "Fix the identified issue",
        "root_cause": "Explain the root cause of this issue",

        # Design actions
        "design_variations": "Create 3 variations of this design",
        "resize": None,  # Special: ask for size
        "generate_code": "Generate the code for this design",
        "more_designs": "Show 3 alternative design options",

        # Document actions
        "summarize": "Provide a brief summary of this document",
        "search_doc": None,  # Special: ask what to find

        # General actions
        "web_search": f"Search the web for: {original_query}",
        "learn_more": f"Tell me more about: {original_query}",
        "retry": f"Try again: {original_query}",
    }

    return ACTION_PROMPTS.get(action)


def is_special_action(action: str) -> bool:
    """Check if action requires special handling."""
    return action in ("download_report", "share_report", "resize", "search_doc")
