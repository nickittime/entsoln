"""Production Structured Logging Configuration.

Configures structlog for JSON formatting, contextual enrichment,
and sensitive field redaction.
"""

import logging
import sys
from typing import Any, Dict
import structlog
from src.common.config.settings import get_settings


def redact_sensitive_data(
    logger: logging.Logger, log_method: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Scrub sensitive credentials, passwords, and tokens from log events."""
    sensitive_keys = {
        "password", "secret", "token", "authorization",
        "access_key", "secret_key", "pan", "aadhaar"
    }
    for key in list(event_dict.keys()):
        if any(sens in key.lower() for sens in sensitive_keys):
            event_dict[key] = "[REDACTED]"
    return event_dict


def setup_logging() -> None:
    """Initialize structured JSON logging for the application runtime."""
    settings = get_settings()
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        redact_sensitive_data,
    ]

    if settings.DEBUG:
        processors = shared_processors + [structlog.dev.ConsoleRenderer()]
    else:
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Retrieve a bound structured logger by namespace."""
    return structlog.get_logger(name)
