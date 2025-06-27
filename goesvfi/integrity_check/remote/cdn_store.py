"""CDN Store implementation for accessing GOES imagery via NOAA STAR CDN.

This module provides a RemoteStore implementation that fetches GOES Band 13
imagery from the NOAA STAR CDN using asynchronous HTTP requests.
"""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import aiohttp
from aiohttp.client_exceptions import ClientError, ClientResponseError

from goesvfi.integrity_check.remote.base import RemoteStore
from goesvfi.integrity_check.time_index import SatellitePattern, TimeIndex
from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)


class CDNStore(RemoteStore):
    """Store implementation for the NOAA STAR CDN."""

    def __init__(self, resolution: str | None = None, timeout: int = 30) -> None:
        """Initialize with optional resolution and timeout parameters.

        Args:
            resolution: Image resolution to fetch (default: TimeIndex.CDN_RES)
            timeout: HTTP timeout in seconds (default: 30)
        """
        self.resolution = resolution or TimeIndex.CDN_RES
        self.timeout = timeout
        self._session: aiohttp.ClientSession | None = None

    @property
    async def session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp ClientSession."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={"User-Agent": "GOES-VFI/1.0"},
            )
        # The session has been created above if it was None
        assert self._session is not None, "Session is unexpectedly None"
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "CDNStore":
        """Context manager entry."""
        await self.session
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Context manager exit."""
        _ = exc_val  # Unused but required by protocol
        _ = exc_tb  # Unused but required by protocol
        await self.close()

    async def exists(self, ts: datetime, satellite: SatellitePattern) -> bool:
        """Check if a file exists in the CDN for the timestamp and satellite.

        Args:
            ts: Timestamp to check
            satellite: Satellite pattern enum

        Returns:
            True if the file exists, False otherwise
        """
        url = TimeIndex.to_cdn_url(ts, satellite, self.resolution)
        session = await self.session

        try:
            async with session.head(url, allow_redirects=True) as response:
                return bool(response.status == 200)
        except ClientError as e:
            LOGGER.debug("CDN check failed for %s: %s", url, e)
            return False

    async def download(self, ts: datetime, satellite: SatellitePattern, dest_path: Path) -> Path:
        """Download a file from the CDN.

        Args:
            ts: Timestamp to download
            satellite: Satellite pattern enum
            dest_path: Destination path to save the file

        Returns:
            Path to the downloaded file

        Raises:
            FileNotFoundError: If the file doesn't exist
            IOError: If there's an error during download
        """
        url = TimeIndex.to_cdn_url(ts, satellite, self.resolution)
        session = await self.session

        try:
            # First check if the file exists
            async with session.head(url, allow_redirects=True) as response:
                if response.status != 200:
                    msg = f"File not found at {url} (status: {response.status})"
                    raise FileNotFoundError(msg)

            # Create parent directory if it doesn't exist
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Download the file with progress tracking
            LOGGER.debug("Downloading %s to %s", url, dest_path)
            async with session.get(url, allow_redirects=True) as response:
                if response.status != 200:
                    msg = f"File not found at {url} (status: {response.status})"
                    raise FileNotFoundError(msg)

                content_length = response.headers.get("Content-Length", "0")
                total_size = int(content_length) if content_length.isdigit() else 0
                LOGGER.debug("Total size: %s bytes", total_size)

                with open(dest_path, "wb") as f:
                    downloaded = 0
                    async for chunk in response.content.iter_chunked(8192):
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Log progress every ~10% only if we have a valid size
                        if total_size > 0 and downloaded % max(1, (total_size // 10)) < 8192:
                            progress = (downloaded / total_size) * 100.0
                            LOGGER.debug("Download progress: %.1f%%", progress)

            LOGGER.debug("Download complete: %s", dest_path)
            return dest_path

        except ClientResponseError as e:
            if e.status == 404:
                msg = f"File not found at {url}"
                raise FileNotFoundError(msg) from e
            msg = f"Failed to download {url}: {e}"
            raise OSError(msg) from e
        except ClientError as e:
            msg = f"Failed to download {url}: {e}"
            raise OSError(msg) from e
        except Exception as e:
            msg = f"Unexpected error downloading {url}: {e}"
            raise OSError(msg) from e

    async def check_file_exists(self, timestamp: datetime, satellite: SatellitePattern) -> bool:
        """Check if a file exists for the given timestamp and satellite.

        This method implements the abstract method from RemoteStore.
        """
        return await self.exists(timestamp, satellite)

    async def download_file(
        self,
        timestamp: datetime,
        satellite: SatellitePattern,
        destination: Path,
        progress_callback: Callable[..., None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> Path:
        """Download a file for the given timestamp and satellite.

        This method implements the abstract method from RemoteStore.
        Note: progress_callback and cancel_check are not implemented in this stub.
        """
        return await self.download(timestamp, satellite, destination)

    async def get_file_url(self, timestamp: datetime, satellite: SatellitePattern) -> str:
        """Get the URL for a file.

        This method implements the abstract method from RemoteStore.
        """
        return TimeIndex.to_cdn_url(timestamp, satellite, self.resolution)
