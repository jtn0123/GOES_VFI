"""Base classes for remote store implementations.

This module provides the base classes and exceptions for remote store
implementations used in the integrity check system.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)

# Type aliases
ProgressCallback = Callable[[int, int, float], None]
CancelCallback = Callable[[], bool]


class RemoteStoreError(Exception):
    """Base exception for remote store errors."""

    def __init__(
        self,
        message: str,
        technical_details: str | None = None,
        original_exception: Exception | None = None,
        troubleshooting_tips: str | None = None,
        error_code: str | None = None,
    ) -> None:
        """Initialize the error."""
        super().__init__(message)
        self.message = message
        self.technical_details = technical_details
        self.original_exception = original_exception
        self.troubleshooting_tips = troubleshooting_tips
        self.error_code = error_code

    def get_user_message(self) -> str:
        """Get a user-friendly error message."""
        return self.message


class ConnectionError(RemoteStoreError):
    """Error connecting to remote store."""


class NetworkError(RemoteStoreError):
    """General network-related error."""


class TemporaryError(RemoteStoreError):
    """Temporary error that may succeed on retry."""


class AuthenticationError(RemoteStoreError):
    """Authentication or authorization error."""


class ResourceNotFoundError(RemoteStoreError):
    """Requested resource not found."""


class TimeoutError(RemoteStoreError):
    """Operation timed out."""


class RateLimitError(RemoteStoreError):
    """Rate limit exceeded."""


class ServerError(RemoteStoreError):
    """Server-side error."""


class RemoteStore(ABC):
    """Abstract base class for remote file stores.

    This is a minimal stub implementation to allow the app to start.
    """

    @abstractmethod
    async def check_file_exists(self, timestamp: datetime, satellite: Any) -> bool:
        """Check if a file exists for the given timestamp and satellite."""

    @abstractmethod
    async def download_file(
        self,
        timestamp: datetime,
        satellite: Any,
        destination: Path,
        progress_callback: ProgressCallback | None = None,
        cancel_check: CancelCallback | None = None,
    ) -> Path:
        """Download a file for the given timestamp and satellite."""

    @abstractmethod
    async def get_file_url(self, timestamp: datetime, satellite: Any) -> str:
        """Get the URL for a file."""

    @abstractmethod
    async def close(self) -> None:
        """Close any resources used by the store."""

    def diagnose_connection(self) -> dict[str, Any]:
        """Diagnose connection issues.

        This is a stub implementation that returns minimal diagnostics.
        """
        LOGGER.warning("Using stub diagnose_connection implementation")
        return {
            "status": "unknown",
            "message": "Diagnostic not implemented in stub",
        }
