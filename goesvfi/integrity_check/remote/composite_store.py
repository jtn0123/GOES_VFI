"""
Composite Store with fallback mechanisms for accessing GOES imagery.

This module provides a RemoteStore implementation that tries multiple
data sources in order, falling back to the next source if one fails.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from goesvfi.integrity_check.remote.base import (
    AuthenticationError,
    RemoteStore,
    RemoteStoreError,
    ResourceNotFoundError,
)
from goesvfi.integrity_check.remote.cdn_store import CDNStore
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.time_index import SatellitePattern
from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)


class DataSourceResult:
    """Result from attempting to access a data source."""

    def __init__(
        self,
        source_name: str,
        success: bool,
        result_path: Optional[Path] = None,
        error: Optional[RemoteStoreError] = None,
        elapsed_time: float = 0.0,
    ):
        """Initialize a data source result.

        Args:
            source_name: Name of the data source
            success: Whether the operation succeeded
            result_path: Path to downloaded file if successful
            error: Error if operation failed
            elapsed_time: Time taken for the operation
        """
        self.source_name = source_name
        self.success = success
        self.result_path = result_path
        self.error = error
        self.elapsed_time = elapsed_time


class CompositeStore(RemoteStore):
    """Store implementation with automatic fallback between multiple sources.

    This store tries data sources in the following order:
    1. Primary: NOAA S3 bucket (fastest when available)
    2. Secondary: NOAA CDN (more reliable but potentially slower)
    3. Tertiary: Local cache (if configured)

    The store tracks performance metrics to optimize source selection over time.
    """

    def __init__(
        self,
        enable_s3: bool = True,
        enable_cdn: bool = True,
        enable_cache: bool = True,
        cache_dir: Optional[Path] = None,
        timeout: int = 60,
        prefer_recent_success: bool = True,
    ):
        """Initialize the composite store.

        Args:
            enable_s3: Whether to use S3 as a data source
            enable_cdn: Whether to use CDN as a data source
            enable_cache: Whether to use local cache as a data source
            cache_dir: Directory for local cache (required if enable_cache=True)
            timeout: Timeout for each source in seconds
            prefer_recent_success: Prioritize recently successful sources
        """
        self.timeout = timeout
        self.prefer_recent_success = prefer_recent_success

        # Initialize data sources
        self.sources: List[Tuple[str, RemoteStore]] = []

        if enable_s3:
            self.sources.append(("S3", S3Store(timeout=timeout)))

        if enable_cdn:
            self.sources.append(("CDN", CDNStore(timeout=timeout)))

        if enable_cache and cache_dir:
            # Local cache is not yet implemented
            LOGGER.warning("Local cache store not yet implemented")

        if not self.sources:
            raise ValueError("At least one data source must be enabled")

        # Track source performance
        self.source_stats: Dict[str, Dict[str, Any]] = {
            name: {
                "attempts": 0,
                "successes": 0,
                "failures": 0,
                "total_time": 0.0,
                "last_success": None,
                "last_failure": None,
                "consecutive_failures": 0,
            }
            for name, _ in self.sources
        }

        LOGGER.info(
            f"Initialized CompositeStore with sources: {[name for name, _ in self.sources]}"
        )

    def _get_ordered_sources(self) -> List[Tuple[str, RemoteStore]]:
        """Get sources ordered by priority based on recent performance.

        Returns:
            List of (name, store) tuples ordered by priority
        """
        if not self.prefer_recent_success:
            return self.sources

        # Sort sources by recent success and performance
        def source_priority(source_tuple: Tuple[str, RemoteStore]) -> Tuple[int, float]:
            name, _ = source_tuple
            stats = self.source_stats[name]

            # Penalize sources with recent consecutive failures
            if stats["consecutive_failures"] >= 3:
                return (1000 + stats["consecutive_failures"], 0.0)

            # Prioritize by success rate
            attempts = stats["attempts"]
            if attempts == 0:
                return (0, 0.0)  # Untried sources first

            success_rate = stats["successes"] / attempts
            avg_time = stats["total_time"] / attempts if attempts > 0 else float("inf")

            # Lower score is better
            # Combine success rate (inverted) and average time
            score = (1.0 - success_rate) * 100 + avg_time

            return (stats["consecutive_failures"], score)

        sorted_sources = sorted(self.sources, key=source_priority)

        # Log if order changed from default
        if [name for name, _ in sorted_sources] != [name for name, _ in self.sources]:
            LOGGER.debug(
                f"Source priority reordered: {[name for name, _ in sorted_sources]}"
            )

        return sorted_sources

    def _update_stats(
        self,
        source_name: str,
        success: bool,
        elapsed_time: float,
        error: Optional[RemoteStoreError] = None,
    ) -> None:
        """Update performance statistics for a source.

        Args:
            source_name: Name of the data source
            success: Whether the operation succeeded
            elapsed_time: Time taken for the operation
            error: Error if operation failed
        """
        stats = self.source_stats[source_name]
        stats["attempts"] += 1
        stats["total_time"] += elapsed_time

        if success:
            stats["successes"] += 1
            stats["last_success"] = datetime.now()
            stats["consecutive_failures"] = 0
        else:
            stats["failures"] += 1
            stats["last_failure"] = datetime.now()
            stats["consecutive_failures"] += 1

            # Log failure details
            if error:
                LOGGER.warning("%s failed: %s", source_name, error.get_user_message())

    async def download(
        self,
        ts: datetime,
        satellite: SatellitePattern,
        dest_path: Path,
        product_type: str = "RadC",
        band: int = 13,
    ) -> Path:
        """Download a file using fallback mechanism across multiple sources.

        Args:
            ts: Timestamp to download
            satellite: Satellite pattern enum
            dest_path: Destination path to save the file
            product_type: Product type ("RadF", "RadC", "RadM")
            band: Band number (1-16)

        Returns:
            Path to the downloaded file

        Raises:
            RemoteStoreError: If all sources fail
        """
        results: List[DataSourceResult] = []

        # Try each source in priority order
        for source_name, store in self._get_ordered_sources():
            LOGGER.info("Attempting download from %s...", source_name)

            start_time = asyncio.get_event_loop().time()

            try:
                # Attempt download
                # The stores have download_file method, not download
                # We need to use the appropriate method based on store type
                if hasattr(store, "download"):
                    result_path = await store.download(
                        ts=ts,
                        satellite=satellite,
                        dest_path=dest_path,
                        product_type=product_type,
                        band=band,
                    )
                else:
                    # Fallback to download_file for basic RemoteStore interface
                    result_path = await store.download_file(
                        timestamp=ts, satellite=satellite, destination=dest_path
                    )

                elapsed_time = asyncio.get_event_loop().time() - start_time

                # Update statistics
                self._update_stats(source_name, True, elapsed_time)

                # Success!
                LOGGER.info(
                    f"Successfully downloaded from {source_name} in {elapsed_time:.2f}s"
                )

                results.append(
                    DataSourceResult(
                        source_name=source_name,
                        success=True,
                        result_path=result_path,
                        elapsed_time=elapsed_time,
                    )
                )

                return result_path

            except (RemoteStoreError, Exception) as e:
                elapsed_time = asyncio.get_event_loop().time() - start_time

                # Convert to RemoteStoreError if needed
                if isinstance(e, RemoteStoreError):
                    error = e
                else:
                    error = RemoteStoreError(
                        message=f"Error downloading from {source_name}",
                        technical_details=str(e),
                        original_exception=e,
                    )

                # Update statistics
                self._update_stats(source_name, False, elapsed_time, error)

                results.append(
                    DataSourceResult(
                        source_name=source_name,
                        success=False,
                        error=error,
                        elapsed_time=elapsed_time,
                    )
                )

                # Log but continue to next source
                LOGGER.warning(
                    f"{source_name} failed after {elapsed_time:.2f}s: {error.message}"
                )

                # For auth errors, skip other sources as they'll likely fail too
                if isinstance(error, AuthenticationError):
                    LOGGER.error("Authentication error - skipping remaining sources")
                    break

        # All sources failed - create comprehensive error
        self._create_fallback_error(results, ts, satellite)
        # This line is unreachable as _create_fallback_error always raises,
        # but mypy needs it for type checking
        raise RemoteStoreError("All sources failed")

    def _create_fallback_error(
        self,
        results: List[DataSourceResult],
        ts: datetime,
        satellite: SatellitePattern,
    ) -> None:
        """Create and raise a comprehensive error when all sources fail.

        Args:
            results: List of results from each source attempt
            ts: Timestamp that was requested
            satellite: Satellite that was requested

        Raises:
            RemoteStoreError: Always raises with details of all failures
        """
        # Build error message
        error_lines = [
            f"All data sources failed for {satellite.name} at {ts.isoformat()}",
            "",
            "Attempted sources:",
        ]

        for result in results:
            status = "✓" if result.success else "✗"
            time_str = f"{result.elapsed_time:.1f}s"

            if result.error:
                error_summary = result.error.message
                if len(error_summary) > 60:
                    error_summary = error_summary[:57] + "..."
                error_lines.append(
                    f"  {status} {result.source_name} ({time_str}): {error_summary}"
                )
            else:
                error_lines.append(f"  {status} {result.source_name} ({time_str})")

        # Add troubleshooting tips
        error_lines.extend(
            [
                "",
                "Troubleshooting tips:",
                "• Check your internet connection",
                "• Verify the timestamp is not too recent (15+ minute delay for GOES data)",
                "• Try a different timestamp or date range",
                "• Check if the satellite was operational at this time",
            ]
        )

        # Add alternative sources
        error_lines.extend(
            [
                "",
                "Alternative data sources:",
                "• NOAA CLASS archive: https://www.avl.class.noaa.gov/",
                "• Google Cloud GOES-16: https://console.cloud.google.com/storage/browser/gcp-public-data-goes-16",
            ]
        )

        # Determine primary error type from results
        primary_error = None
        for result in results:
            if result.error:
                if isinstance(result.error, ResourceNotFoundError):
                    primary_error = result.error
                    break
                elif primary_error is None:
                    primary_error = result.error

        # Find where troubleshooting tips start
        tips_index = error_lines.index("Troubleshooting tips:")

        # Create comprehensive error
        if isinstance(primary_error, ResourceNotFoundError):
            raise ResourceNotFoundError(
                message="\n".join(
                    error_lines[: tips_index - 1]
                ),  # Include all source attempts
                technical_details="\n".join(error_lines),
                original_exception=(
                    primary_error.original_exception if primary_error else None
                ),
                troubleshooting_tips="\n".join(error_lines[tips_index:]),
            )
        else:
            raise RemoteStoreError(
                message="\n".join(
                    error_lines[: tips_index - 1]
                ),  # Include all source attempts
                technical_details="\n".join(error_lines),
                original_exception=(
                    primary_error.original_exception if primary_error else None
                ),
                troubleshooting_tips="\n".join(error_lines[tips_index:]),
            )

    async def exists(
        self,
        ts: datetime,
        satellite: SatellitePattern,
        product_type: str = "RadC",
        band: int = 13,
    ) -> bool:
        """Check if a file exists in any data source.

        Args:
            ts: Timestamp to check
            satellite: Satellite pattern enum
            product_type: Product type
            band: Band number

        Returns:
            True if file exists in any source, False otherwise
        """
        # Check sources in priority order
        for source_name, store in self._get_ordered_sources():
            try:
                # Check if store has exists method, otherwise use check_file_exists
                if hasattr(store, "exists"):
                    exists = await store.exists(
                        ts=ts,
                        satellite=satellite,
                        product_type=product_type,
                        band=band,
                    )
                else:
                    # Fallback to check_file_exists for basic RemoteStore interface
                    exists = await store.check_file_exists(
                        timestamp=ts, satellite=satellite
                    )

                if exists:
                    LOGGER.debug("File exists in %s", source_name)
                    return True

            except RemoteStoreError as e:
                # Log but continue checking other sources
                LOGGER.debug("Error checking %s: %s", source_name, e.message)
                continue

        return False

    async def check_file_exists(self, timestamp: datetime, satellite: Any) -> bool:
        """Check if a file exists for the given timestamp and satellite.

        This wraps the exists method to match the RemoteStore interface.
        """
        return await self.exists(timestamp, satellite)

    async def download_file(
        self,
        timestamp: datetime,
        satellite: Any,
        destination: Path,
        progress_callback: Optional[Any] = None,
        cancel_check: Optional[Any] = None,
    ) -> Path:
        """Download a file for the given timestamp and satellite.

        This wraps the download method to match the RemoteStore interface.
        """
        return await self.download(
            ts=timestamp,
            satellite=satellite,
            dest_path=destination,
        )

    async def get_file_url(self, timestamp: datetime, satellite: Any) -> str:
        """Get the URL for a file.

        Returns the URL from the first available source.
        """
        for source_name, store in self._get_ordered_sources():
            try:
                url = await store.get_file_url(timestamp, satellite)
                return url
            except Exception as e:
                LOGGER.debug("Error getting URL from %s: %s", source_name, e)
                continue

        raise RemoteStoreError(
            message=f"Could not get URL for {satellite} at {timestamp}",
            troubleshooting_tips="All sources failed to provide a URL",
        )

    async def close(self) -> None:
        """Close all data source connections."""
        for name, store in self.sources:
            try:
                await store.close()
            except Exception as e:
                LOGGER.error("Error closing %s: %s", name, e)

    def get_statistics(self) -> Dict[str, Any]:
        """Get performance statistics for all sources.

        Returns:
            Dictionary of statistics per source
        """
        stats = {}

        for source_name, source_stats in self.source_stats.items():
            attempts = source_stats["attempts"]
            if attempts > 0:
                success_rate = source_stats["successes"] / attempts * 100
                avg_time = source_stats["total_time"] / attempts
            else:
                success_rate = 0.0
                avg_time = 0.0

            stats[source_name] = {
                "attempts": attempts,
                "success_rate": f"{success_rate:.1f}%",
                "average_time": f"{avg_time:.2f}s",
                "consecutive_failures": source_stats["consecutive_failures"],
                "last_success": (
                    source_stats["last_success"].isoformat()
                    if source_stats["last_success"]
                    else "Never"
                ),
                "last_failure": (
                    source_stats["last_failure"].isoformat()
                    if source_stats["last_failure"]
                    else "Never"
                ),
            }

        return stats

    def reset_statistics(self) -> None:
        """Reset performance statistics for all sources."""
        for stats in self.source_stats.values():
            stats["attempts"] = 0
            stats["successes"] = 0
            stats["failures"] = 0
            stats["total_time"] = 0.0
            stats["last_success"] = None
            stats["last_failure"] = None
            stats["consecutive_failures"] = 0

        LOGGER.info("Reset performance statistics for all sources")
