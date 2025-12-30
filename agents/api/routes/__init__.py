"""API routes module.

Exports all route routers for inclusion in main FastAPI app.
"""
from . import health
from . import telegram
from . import skills
from . import reports
from . import admin


__all__ = [
    "health",
    "telegram",
    "skills",
    "reports",
    "admin"
]
