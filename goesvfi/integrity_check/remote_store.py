"""Remote store for fetching satellite imagery files.

This module defines interfaces and implementations for accessing remote
satellite imagery repositories, downloading missing files, and reporting progress.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from goesvfi.utils import log

from .time_index import SatellitePattern, generate_expected_filename

LOGGER = log.get_logger(__name__)

# Type alias for progress callbacks
ProgressCallback = Callable[[int, int, float], None]
CancelCallback = Callable[[], bool]


class RemoteStore(ABC):
    """Abstract base class for remote file stores.

    This is a minimal stub implementation to allow the app to start.
    """

    @abstractmethod
    def construct_url(self, timestamp: datetime, satellite: SatellitePattern) -> str:
        """Construct URL for a specific timestamp and satellite."""
        pass

    @abstractmethod
    def download_file(
        self,
        url: str,
        local_path: Path,
        progress_callback: Optional[ProgressCallback] = None,
        should_cancel: Optional[CancelCallback] = None,
    ) -> bool:
        """Download a file from the remote store."""
        pass

    @abstractmethod
    def check_exists(self, url: str) -> bool:
        """Check if a file exists at the given URL."""
        pass


class HTTPRemoteStore(RemoteStore):
    """HTTP-based remote store implementation.

    This is a minimal stub implementation.
    """

    def __init__(self, base_url: str, timeout: int = 30, verify_ssl: bool = True) -> None:
        """Initialize the HTTP remote store."""
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        LOGGER.warning("HTTPRemoteStore using minimal stub implementation")

    def construct_url(self, timestamp: datetime, satellite: SatellitePattern) -> str:
        """Construct URL for a specific timestamp and satellite."""
        filename = generate_expected_filename(timestamp, satellite)
        return f"{self.base_url}/{filename}"

    def download_file(
        self,
        url: str,
        local_path: Path,
        progress_callback: Optional[ProgressCallback] = None,
        should_cancel: Optional[CancelCallback] = None,
    ) -> bool:
        """Download a file from the remote store.

        This is a stub implementation that returns False.
        """
        LOGGER.debug("Stub download_file called for %s", url)
        return False

    def check_exists(self, url: str) -> bool:
        """Check if a file exists at the given URL.

        This is a stub implementation that returns False.
        """
        LOGGER.debug("Stub check_exists called for %s", url)
        return False


def create_remote_store(url: str, **kwargs: Any) -> RemoteStore:
    """Factory function to create the appropriate remote store.

    Args:
        url: Base URL for the remote store
        **kwargs: Additional arguments to pass to the store constructor

    Returns:
        RemoteStore instance
    """
    parsed = urlparse(url)

    if parsed.scheme in ("http", "https"):
        return HTTPRemoteStore(url, **kwargs)
    else:
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")
