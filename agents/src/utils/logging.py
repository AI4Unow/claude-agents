"""Structured logging configuration."""
import logging
import structlog
from functools import wraps
from contextlib import contextmanager
import time


def setup_logging():
    """Configure structlog for production."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def get_logger(agent_id: str = None):
    """Get logger with optional agent context."""
    logger = structlog.get_logger()
    if agent_id:
        logger = logger.bind(agent=agent_id)
    return logger


@contextmanager
def log_duration(logger, action: str, **extra):
    """Context manager to log action duration."""
    start = time.perf_counter()
    try:
        yield
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(f"{action}_completed", duration_ms=round(duration_ms, 2), **extra)
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.error(f"{action}_failed", duration_ms=round(duration_ms, 2), error=str(e), **extra)
        raise


def log_execution(action: str):
    """Decorator to log function execution."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            logger = structlog.get_logger()
            with log_duration(logger, action):
                return await func(*args, **kwargs)
        return wrapper
    return decorator
