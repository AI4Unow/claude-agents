"""Command router with decorator-based registration and permission checking."""
from dataclasses import dataclass
from typing import Callable, Awaitable, Dict, List
import structlog

logger = structlog.get_logger()

CommandHandler = Callable[[str, dict, int], Awaitable[str]]


@dataclass
class CommandDefinition:
    """Definition of a registered command."""
    handler: CommandHandler
    name: str
    description: str
    usage: str
    permission_level: str  # guest, user, developer, admin
    category: str


class CommandRouter:
    """Route commands to handlers with permission checking."""

    def __init__(self):
        self._commands: Dict[str, CommandDefinition] = {}
        self._categories: Dict[str, List[str]] = {}

    def command(
        self,
        name: str,
        description: str = "",
        usage: str = "",
        permission: str = "guest",
        category: str = "general"
    ):
        """Decorator to register command handler.

        Args:
            name: Command name (with or without leading /)
            description: Brief description for help text
            usage: Usage example
            permission: Required permission level (guest|user|developer|admin)
            category: Command category for help grouping
        """
        def decorator(func: CommandHandler):
            cmd_name = name if name.startswith("/") else f"/{name}"
            self._commands[cmd_name] = CommandDefinition(
                handler=func,
                name=cmd_name,
                description=description or func.__doc__ or "",
                usage=usage or cmd_name,
                permission_level=permission,
                category=category
            )
            # Track by category
            if category not in self._categories:
                self._categories[category] = []
            self._categories[category].append(cmd_name)
            logger.info("command_registered", command=cmd_name, category=category, permission=permission)
            return func
        return decorator

    async def handle(self, command: str, user: dict, chat_id: int) -> str:
        """Route command to handler with permission check.

        Args:
            command: Full command string including args
            user: User dict with 'id' and other fields
            chat_id: Telegram chat ID

        Returns:
            Response message string
        """
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        cmd_def = self._commands.get(cmd)
        if not cmd_def:
            return self._unknown_command(cmd)

        # Permission check
        if not await self._check_permission(user.get("id"), cmd_def.permission_level):
            return f"⛔ Access denied. Requires {cmd_def.permission_level} tier."

        try:
            result = await cmd_def.handler(args, user, chat_id)
            logger.info("command_executed", command=cmd, user_id=user.get("id"))
            return result
        except Exception as e:
            logger.error("command_error", command=cmd, error=str(e), exc_info=True)
            return f"❌ Error: {str(e)[:100]}"

    async def _check_permission(self, user_id: int, required: str) -> bool:
        """Check if user has required permission level.

        Permission hierarchy: guest < user < developer < admin
        """
        # Lazy import to avoid circular dependencies
        from src.core.state import get_state_manager

        if required == "guest":
            return True

        # Admin check using environment variable
        if required == "admin":
            import os
            admin_id = os.environ.get("ADMIN_TELEGRAM_ID")
            return str(user_id) == str(admin_id)

        # For user/developer tiers, check Firebase
        state = get_state_manager()
        tier = await state.get_user_tier_cached(user_id)

        tier_levels = {"guest": 0, "user": 1, "developer": 2, "admin": 3}
        return tier_levels.get(tier, 0) >= tier_levels.get(required, 0)

    def _unknown_command(self, cmd: str) -> str:
        """Return helpful message for unknown command."""
        # Find similar commands (same prefix)
        similar = [c for c in self._commands.keys() if cmd[:3] in c]
        if similar:
            return f"❓ Unknown command: {cmd}\nDid you mean: {', '.join(similar[:3])}?"
        return f"❓ Unknown command: {cmd}\nUse /help to see available commands."

    def get_help_text(self, tier: str = "guest") -> str:
        """Generate help text based on user tier.

        Args:
            tier: User's permission tier

        Returns:
            Formatted help text with commands available to this tier
        """
        lines = ["<b>Available Commands:</b>\n"]
        tier_levels = {"guest": 0, "user": 1, "developer": 2, "admin": 3}
        user_level = tier_levels.get(tier, 0)

        for category, commands in sorted(self._categories.items()):
            category_cmds = []
            for cmd_name in sorted(commands):
                cmd_def = self._commands[cmd_name]
                if tier_levels.get(cmd_def.permission_level, 0) <= user_level:
                    category_cmds.append(f"{cmd_name} - {cmd_def.description}")

            if category_cmds:
                lines.append(f"\n<b>{category.title()}</b>")
                lines.extend(category_cmds)

        return "\n".join(lines)

    def list_commands(self) -> List[CommandDefinition]:
        """List all registered commands."""
        return list(self._commands.values())

    def get_command(self, name: str) -> CommandDefinition:
        """Get command definition by name."""
        return self._commands.get(name)
