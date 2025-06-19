"""Base classes for remote store implementations.

This module provides the base classes and exceptions for remote store
implementations used in the integrity check system.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

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
        technical_details: Optional[str] = None,
        original_exception: Optional[Exception] = None,
        troubleshooting_tips: Optional[str] = None,
        error_code: Optional[str] = None,
    ):
        """Initialize the error."""
        super().__init__(message)
        self.message = message
        self.technical_details = technical_details
        self.original_exception = original_exception
        self.troubleshooting_tips = troubleshooting_tips
        self.error_code = error_code


class ConnectionError(RemoteStoreError):
    """Error connecting to remote store."""

    pass


class NetworkError(RemoteStoreError):
    """General network-related error."""

    pass


class TemporaryError(RemoteStoreError):
    """Temporary error that may succeed on retry."""

    pass


class AuthenticationError(RemoteStoreError):
    """Authentication or authorization error."""

    pass


class ResourceNotFoundError(RemoteStoreError):
    """Requested resource not found."""

    pass


class TimeoutError(RemoteStoreError):
    """Operation timed out."""

    pass


class RateLimitError(RemoteStoreError):
    """Rate limit exceeded."""

    pass


class ServerError(RemoteStoreError):
    """Server-side error."""

    pass


class RemoteStore(ABC):
    """Abstract base class for remote file stores.

    This is a minimal stub implementation to allow the app to start.
    """

    @abstractmethod
    async def check_file_exists(self, timestamp: datetime, satellite: Any) -> bool:
        """Check if a file exists for the given timestamp and satellite."""
        pass

    @abstractmethod
    async def download_file(
        self,
        timestamp: datetime,
        satellite: Any,
        destination: Path,
        progress_callback: Optional[ProgressCallback] = None,
        cancel_check: Optional[CancelCallback] = None,
    ) -> Path:
        """Download a file for the given timestamp and satellite."""
        pass

    @abstractmethod
    async def get_file_url(self, timestamp: datetime, satellite: Any) -> str:
        """Get the URL for a file."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close any resources used by the store."""
        pass

    def diagnose_connection(self) -> Dict[str, Any]:
        """Diagnose connection issues.

        This is a stub implementation that returns minimal diagnostics.
        """
        LOGGER.warning("Using stub diagnose_connection implementation")
        return {
            "status": "unknown",
            "message": "Diagnostic not implemented in stub",
        }
