# TODO: colorlog wrapper
from __future__ import annotations
"""goesvfi.utils.log – colourised logger helper"""

import logging
import sys
from typing import Optional, cast
from types import ModuleType

try:
    import colorlog
except ImportError:  # graceful degradation
    colorlog_module: Optional[ModuleType] = None
else:
    colorlog_module = colorlog

_LEVEL = logging.INFO # Default to INFO

_handler: Optional[logging.Handler] = None

def _build_handler() -> logging.Handler:
    handler: logging.Handler
    if colorlog_module:
        handler = cast(logging.Handler, colorlog_module.StreamHandler())
        handler.setFormatter(colorlog_module.ColoredFormatter(
            fmt="%(log_color)s[%(levelname).1s] %(name)s: %(message)s",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "white",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bold",
            },
        ))
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("[%(levelname).1s] %(name)s: %(message)s"))
    return handler


def get_logger(name: str | None = None) -> logging.Logger:
    global _handler
    if _handler is None:
        _handler = _build_handler()
    logger = logging.getLogger(name)
    logger.setLevel(_LEVEL)
    if not any(isinstance(h, type(_handler)) for h in logger.handlers):
        logger.addHandler(_handler)
    return logger

def set_level(debug_mode: bool) -> None:
    """Set the global logging level and update the handler."""
    global _LEVEL, _handler
    _LEVEL = logging.DEBUG if debug_mode else logging.INFO
    # Update existing handler level if it was already created
    if _handler:
        _handler.setLevel(_LEVEL)
    # Ensure root logger level is also appropriate if needed
    # logging.getLogger().setLevel(_LEVEL) # Optional: Update root logger level too
