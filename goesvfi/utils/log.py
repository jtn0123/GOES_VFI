# TODO: colorlog wrapper
from __future__ import annotations
"""goesvfi.utils.log – colourised logger helper"""

import logging
import sys
from typing import Optional

try:
    import colorlog
except ImportError:  # graceful degradation
    colorlog = None

_LEVEL = logging.DEBUG

_handler: Optional[logging.Handler] = None

def _build_handler() -> logging.Handler:
    if colorlog:
        handler = colorlog.StreamHandler()
        handler.setFormatter(colorlog.ColoredFormatter(
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
    logger.propagate = False
    return logger
