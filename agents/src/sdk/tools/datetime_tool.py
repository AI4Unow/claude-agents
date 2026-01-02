"""Datetime utility tool (migrated from src/tools/datetime_tool.py)."""

from claude_agents import tool
from datetime import datetime
from typing import Dict
import pytz


@tool
async def get_datetime(
    timezone_name: str = "UTC",
) -> Dict:
    """Get current date and time in specified timezone.

    Args:
        timezone_name: Timezone name (default: UTC)

    Returns:
        Current datetime info with date, time, day_of_week, timezone
    """
    try:
        tz = pytz.timezone(timezone_name)
        now = datetime.now(tz)

        return {
            "datetime": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "day_of_week": now.strftime("%A"),
            "timezone": timezone_name,
        }
    except Exception as e:
        # Fallback to UTC
        now = datetime.now(pytz.UTC)
        return {
            "datetime": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "day_of_week": now.strftime("%A"),
            "timezone": "UTC",
            "error": f"Invalid timezone '{timezone_name}', using UTC"
        }
