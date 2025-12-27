"""DateTime tool - Get current date/time in any timezone."""
from datetime import datetime
from typing import Any, Dict
from zoneinfo import ZoneInfo
from src.tools.base import BaseTool


class DateTimeTool(BaseTool):
    """Get current date/time in any timezone."""

    @property
    def name(self) -> str:
        return "get_datetime"

    @property
    def description(self) -> str:
        return (
            "Get current date and time. Use for: time in different cities, "
            "today's date, day of week, countdown calculations."
        )

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "IANA timezone (e.g., 'Asia/Tokyo', 'America/New_York', 'UTC'). Default: UTC"
                }
            },
            "required": []
        }

    async def execute(self, params: Dict[str, Any]) -> str:
        tz_name = params.get("timezone", "UTC")
        try:
            tz = ZoneInfo(tz_name)
            now = datetime.now(tz)
            return (
                f"Current time in {tz_name}:\n"
                f"Date: {now.strftime('%Y-%m-%d')}\n"
                f"Time: {now.strftime('%H:%M:%S')}\n"
                f"Day: {now.strftime('%A')}"
            )
        except Exception:
            return f"Error: Invalid timezone '{tz_name}'. Use IANA format like 'Asia/Ho_Chi_Minh'"
