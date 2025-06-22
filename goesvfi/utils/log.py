from __future__ import annotations

# TODO: colorlog wrapper

"""goesvfi.utils.log – colourised logger helper"""

import logging
import sys
from types import ModuleType
from typing import Optional, cast

from goesvfi.utils import config  # Import config module

try:
    import colorlog
except ImportError:  # graceful degradation
    colorlog_module: Optional[ModuleType] = None
else:
    colorlog_module = colorlog

# Map level names to logging constants
LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _get_level_from_config() -> int:
    """Gets the logging level from config, defaulting to INFO."""
    level_name = config.get_logging_level().upper()
    return LOG_LEVEL_MAP.get(level_name, logging.INFO)


_LEVEL = _get_level_from_config()  # Get level from config

_handler: Optional[logging.Handler] = None


def _build_handler() -> logging.Handler:
    handler: logging.Handler
    if colorlog_module:
        handler = cast(logging.Handler, colorlog_module.StreamHandler())
        handler.setFormatter(
            colorlog_module.ColoredFormatter(
                fmt="%(log_color)s[%(levelname).1s] %(name)s: %(message)s",
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "white",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red,bold",
                },
            )
        )
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("[%(levelname).1s] %(name)s: %(message)s")
        )
    return handler


def get_logger(name: str | None = None) -> logging.Logger:
    """Gets a logger instance. Configuration is handled by the root logger."""
    global _handler

    logger = logging.getLogger(name)
    logger.setLevel(_LEVEL)

    # Build handler if it doesn't exist
    if _handler is None:
        _handler = _build_handler()
        _handler.setLevel(_LEVEL)

    # Add handler to logger if not already present
    handler_types = [type(h) for h in logger.handlers]
    if type(_handler) not in handler_types:
        logger.addHandler(_handler)

    return logger


def set_global_log_level(level: int) -> None:
    """
    Configure the root logger with a single handler and set its level.
    This relies on propagation for named loggers.
    """
    root_logger = logging.getLogger()

    # Remove any existing handlers from the root logger
    for handler in root_logger.handlers[:]:  # Iterate over a copy
        root_logger.removeHandler(handler)

    # Build and add the single desired handler
    handler = _build_handler()
    root_logger.addHandler(handler)

    # Set the root logger's level
    root_logger.setLevel(level)

    # Log the change using the root logger itself
    # Use root_logger.info to ensure it uses the configured handler
    root_logger.info("Log level set to %s", logging._levelToName.get(level, level))

    # No need to update existing named loggers directly, propagation handles it.
    # No need for the global _LEVEL variable anymore.


# set_level function added for backward compatibility
def set_level(debug_mode: bool) -> None:
    """Set the global logging level based on debug mode."""
    global _LEVEL
    _LEVEL = logging.DEBUG if debug_mode else logging.INFO

    # Update the handler level if it exists
    if _handler:
        _handler.setLevel(_LEVEL)

    # Update all existing loggers
    for name in logging.Logger.manager.loggerDict:
        logger = logging.getLogger(name)
        logger.setLevel(_LEVEL)
