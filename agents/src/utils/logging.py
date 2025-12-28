"""Structured logging configuration with fallback."""
import logging
from functools import wraps
from contextlib import contextmanager
import time

# Try structlog, fallback to stdlib logging
try:
    import structlog
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False


class FallbackLogger:
    """Simple fallback logger when structlog unavailable."""

    def __init__(self, name: str = "agents"):
        self._logger = logging.getLogger(name)
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)
        self._context = {}

    def bind(self, **kwargs):
        """Add context to logger."""
        new_logger = FallbackLogger(self._logger.name)
        new_logger._context = {**self._context, **kwargs}
        return new_logger

    def _format(self, msg, **kwargs):
        ctx = {**self._context, **kwargs}
        if ctx:
            return f"{msg} | {ctx}"
        return msg

    def info(self, msg, **kwargs):
        self._logger.info(self._format(msg, **kwargs))

    def debug(self, msg, **kwargs):
        self._logger.debug(self._format(msg, **kwargs))

    def warning(self, msg, **kwargs):
        self._logger.warning(self._format(msg, **kwargs))

    def error(self, msg, **kwargs):
        self._logger.error(self._format(msg, **kwargs))

    def exception(self, msg, **kwargs):
        self._logger.exception(self._format(msg, **kwargs))


def setup_logging():
    """Configure logging for production."""
    if HAS_STRUCTLOG:
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
    else:
        logging.basicConfig(level=logging.INFO)


def get_logger(agent_id: str = None):
    """Get logger with optional agent context."""
    if HAS_STRUCTLOG:
        logger = structlog.get_logger()
        if agent_id:
            logger = logger.bind(agent=agent_id)
        return logger
    else:
        logger = FallbackLogger("agents")
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
            logger = get_logger()
            with log_duration(logger, action):
                return await func(*args, **kwargs)
        return wrapper
    return decorator
