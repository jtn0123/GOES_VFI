"""Refactored S3 Store implementation for accessing GOES imagery.

This is a refactored version of s3_store.py that uses modular components
for better maintainability and testability.
"""

import asyncio
import re
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, Tuple, Type, TypeVar

import aioboto3  # type: ignore
import botocore.exceptions

from goesvfi.integrity_check.remote.base import (
    AuthenticationError,
)
from goesvfi.integrity_check.remote.base import ConnectionError as RemoteConnectionError
from goesvfi.integrity_check.remote.base import (
    RemoteStore,
    RemoteStoreError,
    ResourceNotFoundError,
)
from goesvfi.integrity_check.remote.s3_utils import (
    DownloadStatsTracker,
    NetworkDiagnostics,
    S3ClientConfig,
    S3ErrorConverter,
    create_s3_config,
)
from goesvfi.integrity_check.time_index import (
    S3_BUCKETS,
    SATELLITE_CODES,
    SatellitePattern,
    TimeIndex,
)
from goesvfi.utils.log import get_logger

# Type variables
ExcType = TypeVar("ExcType", bound=BaseException)
S3ClientType = Any  # aioboto3 doesn't expose concrete types

LOGGER = get_logger(__name__)


class S3Store(RemoteStore):
    """Refactored S3 store implementation with modular design.

    This implementation uses separate modules for:
    - Download statistics tracking
    - Client configuration
    - Error conversion
    - Network diagnostics
    """

    def __init__(
        self,
        aws_profile: Optional[str] = None,
        aws_region: str = "us-east-1",
        timeout: int = 60,
    ) -> None:
        """Initialize S3Store with configuration.

        Args:
            aws_profile: AWS profile name (optional, not required for NOAA buckets)
            aws_region: AWS region name (defaults to us-east-1)
            timeout: Operation timeout in seconds
        """
        # Initialize configuration
        self._config = S3ClientConfig(
            aws_profile=aws_profile,
            aws_region=aws_region,
            timeout=timeout,
        )

        # Initialize components
        self._stats_tracker = DownloadStatsTracker()
        self._network_diagnostics = NetworkDiagnostics()
        self._error_converter = S3ErrorConverter()

        # Client state
        self._session: Optional[Any] = None
        self._s3_client: Optional[S3ClientType] = None

        # Setup and initial diagnostics
        self._initialize()

    def _initialize(self) -> None:
        """Perform initialization tasks."""
        LOGGER.info(
            "Initializing S3Store: region=%s, timeout=%ss",
            self._config.aws_region,
            self._config.timeout,
        )

        # Setup debug logging if needed
        self._config.setup_debug_logging()

        # Collect initial diagnostics
        try:
            LOGGER.info("Collecting system and network diagnostics during S3Store initialization")
            self._network_diagnostics.log_system_info()
        except Exception as e:
            LOGGER.error("Error collecting system diagnostics: %s", e)

        # Test connectivity
        self._network_diagnostics.log_connectivity_test()

    async def _get_s3_client(self) -> S3ClientType:
        """Get or create an S3 client with retry logic.

        Returns:
            S3 client instance

        Raises:
            Various RemoteStoreError subclasses
        """
        if self._s3_client is not None:
            return self._s3_client

        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                # Calculate exponential backoff delay
                delay = 0
                if retry_count > 0:
                    jitter = 0.75 + (0.5 * asyncio.get_event_loop().time())
                    delay = (2**retry_count) * jitter
                    LOGGER.info(
                        "Applying exponential backoff delay of %.2fs before retry %d",
                        delay,
                        retry_count + 1,
                    )
                    await asyncio.sleep(delay)

                LOGGER.debug(
                    "Creating new S3 client (attempt %d/%d)",
                    retry_count + 1,
                    max_retries,
                )

                # Create configuration
                s3_config = create_s3_config(
                    timeout=self._config.timeout,
                    connect_timeout=self._config.connect_timeout,
                    max_retries=self._config.max_retries,
                    use_unsigned=True,
                )

                # Create session and client
                session = aioboto3.Session(**self._config.get_session_kwargs())
                client_context = session.client("s3", config=s3_config)

                # Create client with timeout
                client_timeout = 15 * (1 + retry_count * 0.5)  # 15s, 22.5s, 30s
                self._s3_client = await asyncio.wait_for(
                    client_context.__aenter__(),
                    timeout=client_timeout,
                )

                LOGGER.debug("Successfully created S3 client")
                return self._s3_client

            except asyncio.TimeoutError:
                retry_count += 1
                self._stats_tracker.increment_retry()

                if retry_count >= max_retries:
                    error_details = self._network_diagnostics.create_network_error_details(
                        asyncio.TimeoutError("Client creation timeout"),
                        "Creating S3 client",
                        {"attempts": retry_count, "timeouts": [15, 22.5, 30]},
                    )
                    raise RemoteConnectionError(
                        message="Connection to AWS S3 timed out",
                        technical_details=error_details,
                        error_code="CONN-TIMEOUT",
                    )

            except Exception as e:
                LOGGER.error("Error creating S3 client: %s", e)

                # Convert to appropriate error type
                if retry_count < max_retries - 1:
                    retry_count += 1
                    self._stats_tracker.increment_retry()
                    continue

                # Final attempt failed, raise error
                error = self._error_converter.from_generic_error(
                    e,
                    "creating S3 client",
                    SatellitePattern.GOES_16,  # Default for client creation
                    datetime.now(),
                    {"region": self._config.aws_region},
                )
                raise error

    async def close(self) -> None:
        """Close the S3 client and log final statistics."""
        if self._s3_client is not None:
            await self._s3_client.__aexit__(None, None, None)
            self._s3_client = None

        # Log final statistics if any downloads occurred
        stats = self._stats_tracker.get_stats()
        if stats.total_attempts > 0:
            self._stats_tracker.log_statistics()

    async def __aenter__(self) -> "S3Store":
        """Context manager entry."""
        await self._get_s3_client()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[ExcType]],
        exc_val: Optional[ExcType],
        exc_tb: Optional[Any],
    ) -> None:
        """Context manager exit."""
        await self.close()

    def _get_bucket_and_key(
        self,
        ts: datetime,
        satellite: SatellitePattern,
        product_type: str = "RadC",
        band: int = 13,
        exact_match: bool = False,
    ) -> Tuple[str, str]:
        """Get S3 bucket and key for the given parameters.

        Args:
            ts: Timestamp
            satellite: Satellite pattern
            product_type: Product type
            band: Band number
            exact_match: Whether to use exact match

        Returns:
            Tuple of (bucket_name, object_key)
        """
        bucket = S3_BUCKETS[satellite]
        key = TimeIndex.to_s3_key(
            ts,
            satellite,
            product_type=product_type,
            band=band,
            exact_match=exact_match,
        )
        return bucket, key

    async def exists(
        self,
        ts: datetime,
        satellite: SatellitePattern,
        product_type: str = "RadC",
        band: int = 13,
    ) -> bool:
        """Check if a file exists in S3.

        Args:
            ts: Timestamp
            satellite: Satellite pattern
            product_type: Product type
            band: Band number

        Returns:
            True if file exists, False otherwise
        """
        bucket, key = self._get_bucket_and_key(ts, satellite, product_type=product_type, band=band, exact_match=True)
        s3 = await self._get_s3_client()

        try:
            await s3.head_object(Bucket=bucket, Key=key)
            return True
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404":
                LOGGER.debug("S3 object not found: s3://%s/%s", bucket, key)
                return False

            # Convert and handle other errors
            error = self._error_converter.from_client_error(
                e, "checking existence", satellite, ts, {"bucket": bucket, "key": key}
            )

            # Log error details
            LOGGER.error("S3 error: %s", error.get_user_message())
            if hasattr(error, "technical_details"):
                LOGGER.debug("Technical details: %s", error.technical_details)

            # Re-raise authentication/connection errors
            if isinstance(error, (AuthenticationError, RemoteConnectionError)):
                raise error

            # For other errors, return False
            return False

    async def download(
        self,
        ts: datetime,
        satellite: SatellitePattern,
        dest_path: Path,
        product_type: str = "RadC",
        band: int = 13,
    ) -> Path:
        """Download a file from S3.

        Args:
            ts: Timestamp
            satellite: Satellite pattern
            dest_path: Destination path
            product_type: Product type
            band: Band number

        Returns:
            Path to downloaded file

        Raises:
            Various RemoteStoreError subclasses
        """
        bucket, key = self._get_bucket_and_key(ts, satellite, product_type=product_type, band=band, exact_match=True)
        s3 = await self._get_s3_client()

        LOGGER.info(
            "Attempting to download S3 file for %s at %s",
            satellite.name,
            ts.isoformat(),
        )
        LOGGER.info("Target S3 path: s3://%s/%s", bucket, key)
        LOGGER.info("Local destination: %s", dest_path)

        # Check if exact file exists first
        try:
            has_exact_match = await self._check_exact_file(s3, bucket, key)

            if has_exact_match:
                return await self._download_file(s3, bucket, key, dest_path, ts, satellite)
            else:
                # Try wildcard match
                bucket, wildcard_key = self._get_bucket_and_key(
                    ts,
                    satellite,
                    exact_match=False,
                    product_type=product_type,
                    band=band,
                )

                best_match_key = await self._find_best_match(s3, bucket, wildcard_key, ts, satellite)

                return await self._download_file(s3, bucket, best_match_key, dest_path, ts, satellite)

        except Exception as e:
            # Handle all errors consistently
            if isinstance(e, (RemoteStoreError, ResourceNotFoundError)):
                raise

            # Convert other errors
            error = self._error_converter.from_generic_error(
                e,
                "downloading",
                satellite,
                ts,
                {"bucket": bucket, "key": key, "path": str(dest_path)},
            )
            raise error

    async def _check_exact_file(self, s3: S3ClientType, bucket: str, key: str) -> bool:
        """Check if exact file exists in S3.

        Args:
            s3: S3 client
            bucket: Bucket name
            key: Object key

        Returns:
            True if exists, False otherwise
        """
        try:
            LOGGER.debug("Checking exact file: s3://%s/%s", bucket, key)
            await s3.head_object(Bucket=bucket, Key=key)
            LOGGER.info("Found exact match: s3://%s/%s", bucket, key)
            return True
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404":
                LOGGER.info("Exact file not found, will try wildcard")
                return False
            raise

    async def _find_best_match(
        self,
        s3: S3ClientType,
        bucket: str,
        wildcard_key: str,
        ts: datetime,
        satellite: SatellitePattern,
    ) -> str:
        """Find best matching object using wildcard search.

        Args:
            s3: S3 client
            bucket: Bucket name
            wildcard_key: Key pattern with wildcards
            ts: Timestamp for matching
            satellite: Satellite pattern

        Returns:
            Best matching key

        Raises:
            ResourceNotFoundError if no matches found
        """
        LOGGER.info("Searching with wildcard: s3://%s/%s", bucket, wildcard_key)

        # Extract prefix and create regex pattern
        prefix = wildcard_key.split("*")[0] if "*" in wildcard_key else wildcard_key
        base_path = "/".join(wildcard_key.split("/")[:-1]) + "/"

        # Create search parameters
        sat_code = f"_{SATELLITE_CODES.get(satellite)}_"
        timestamp_part = f"s{ts.year}{ts.strftime('%j')}{ts.strftime('%H')}{ts.strftime('%M')}"

        # Create regex pattern
        filename_pattern = wildcard_key.split("/")[-1]
        regex_pattern = filename_pattern.replace("*", ".*")
        compiled_pattern = re.compile(regex_pattern)

        # Search for matching objects
        matching_objects = []
        paginator = s3.get_paginator("list_objects_v2")

        async for page in paginator.paginate(Bucket=bucket, Prefix=base_path):
            if "Contents" not in page:
                continue

            for obj in page["Contents"]:
                key = obj["Key"]
                if sat_code in key and timestamp_part in key:
                    if compiled_pattern.search(key):
                        matching_objects.append(key)

        if not matching_objects:
            raise ResourceNotFoundError(
                message=f"No files found for {satellite.name} at {ts.isoformat()}",
                technical_details=(
                    f"No files found matching: s3://{bucket}/{wildcard_key}\n"
                    f"Search parameters: prefix={base_path}, "
                    f"satellite={sat_code}, timestamp={timestamp_part}"
                ),
                original_exception=FileNotFoundError("No matching files in S3"),
            )

        # Return the most recent match
        matching_objects.sort()
        best_match: str = matching_objects[-1]
        LOGGER.info("Selected best match: s3://%s/%s", bucket, best_match)
        return best_match

    async def _download_file(
        self,
        s3: S3ClientType,
        bucket: str,
        key: str,
        dest_path: Path,
        ts: datetime,
        satellite: SatellitePattern,
    ) -> Path:
        """Download a file from S3.

        Args:
            s3: S3 client
            bucket: Bucket name
            key: Object key
            dest_path: Destination path
            ts: Timestamp
            satellite: Satellite pattern

        Returns:
            Path to downloaded file
        """
        # Create parent directory
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        LOGGER.info("Downloading s3://%s/%s to %s", bucket, key, dest_path)
        download_start = time.time()

        try:
            # Download file
            await s3.download_file(Bucket=bucket, Key=key, Filename=str(dest_path))
            download_time = time.time() - download_start

            # Verify and get file size
            if not dest_path.exists():
                raise RemoteStoreError(
                    message="Download completed but file not found",
                    technical_details=f"File missing at {dest_path}",
                )

            file_size = dest_path.stat().st_size

            # Update statistics
            self._stats_tracker.update_attempt(
                success=True,
                download_time=download_time,
                file_size=file_size,
                satellite=satellite.name,
                bucket=bucket,
                key=key,
            )

            # Log if milestone
            if self._stats_tracker.should_log_stats():
                self._stats_tracker.log_statistics()

            LOGGER.info(
                "Download complete: %s (%.2f seconds, %d bytes)",
                dest_path,
                download_time,
                file_size,
            )

            return dest_path

        except Exception as e:
            download_time = time.time() - download_start

            # Determine error type
            error_type = self._error_converter.get_error_type(e)

            # Update statistics
            self._stats_tracker.update_attempt(
                success=False,
                download_time=download_time,
                error_type=error_type,
                error_message=str(e),
                satellite=satellite.name,
                bucket=bucket,
                key=key,
            )

            # Collect diagnostics if needed
            if self._stats_tracker.should_collect_diagnostics():
                self._network_diagnostics.log_system_info()

            # Convert and raise error
            if isinstance(e, botocore.exceptions.ClientError):
                error = self._error_converter.from_client_error(
                    e,
                    "downloading",
                    satellite,
                    ts,
                    {
                        "bucket": bucket,
                        "key": key,
                        "path": str(dest_path),
                        "download_time": download_time,
                    },
                )
            else:
                error = self._error_converter.from_generic_error(
                    e,
                    "downloading",
                    satellite,
                    ts,
                    {
                        "bucket": bucket,
                        "key": key,
                        "path": str(dest_path),
                        "download_time": download_time,
                    },
                )

            LOGGER.error("Download error: %s", error.get_user_message())
            LOGGER.error("Traceback: %s", traceback.format_exc())

            raise error

    # Implement abstract methods from RemoteStore

    async def check_file_exists(self, timestamp: datetime, satellite: SatellitePattern) -> bool:
        """Check if a file exists for the given timestamp and satellite."""
        return await self.exists(timestamp, satellite)

    async def download_file(
        self,
        timestamp: datetime,
        satellite: SatellitePattern,
        destination: Path,
        progress_callback: Optional[Callable] = None,
        cancel_check: Optional[Callable] = None,
    ) -> Path:
        """Download a file for the given timestamp and satellite."""
        return await self.download(timestamp, satellite, destination)

    async def get_file_url(self, timestamp: datetime, satellite: SatellitePattern) -> str:
        """Get the URL for a file."""
        bucket, key = self._get_bucket_and_key(timestamp, satellite)
        return f"s3://{bucket}/{key}"
