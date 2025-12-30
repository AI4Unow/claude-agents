"""Global command router instance."""
from commands.base import CommandRouter

# Global command router instance
# Commands are registered by importing command modules
command_router = CommandRouter()
