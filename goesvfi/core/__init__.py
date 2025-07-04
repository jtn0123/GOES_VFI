"""Core functionality for GOES-VFI application.

This package contains core utilities and base classes used throughout
the GOES-VFI application including async I/O, configuration management,
error handling, and resource management.
"""

from .configuration import ConfigurationManager
from .error_decorators import (
    async_safe,
    deprecated,
    robust_operation,
    with_error_handling,
    with_logging,
    with_retry,
    with_timeout,
    with_validation,
)

__all__ = [
    "ConfigurationManager",
    "async_safe",
    "deprecated",
    "robust_operation",
    "with_error_handling",
    "with_logging",
    "with_retry",
    "with_timeout",
    "with_validation",
]
