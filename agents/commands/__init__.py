"""Commands package - modular command handlers with permission checking.

Import all command modules to register them with the global router.
"""
from commands.router import command_router

# Import all command modules to trigger registration
# Modules use @command_router.command() decorator to self-register
from commands import user
from commands import skills
from commands import admin
from commands import personalization
from commands import developer
from commands import reminders
from commands import pkm

__all__ = ["command_router"]
