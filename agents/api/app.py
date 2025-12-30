"""FastAPI application factory.

Creates FastAPI app with middleware and configuration.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


def create_app() -> FastAPI:
    """Create FastAPI application with middleware.

    Returns:
        Configured FastAPI app instance
    """
    web_app = FastAPI(
        title="AI4U.now Agents API",
        description="Modal.com Self-Improving Agents",
        version="1.0.0"
    )

    # CORS middleware
    web_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting
    limiter = Limiter(key_func=get_remote_address)
    web_app.state.limiter = limiter
    web_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    return web_app


# Singleton for imports
web_app = create_app()
