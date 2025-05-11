"""
ReconcileManager refactored module.
Contains the refactored version of the ReconcileManager class with reduced complexity.
"""
import asyncio
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

from ..utils.log import get_logger
from .remote.base import (
    AuthenticationError,
    ConnectionError,
    RemoteStore,
    RemoteStoreError,
    ResourceNotFoundError,
)
from .render.netcdf import render_png
from .time_index import SatellitePattern, TimeIndex

LOGGER = get_logger(__name__)

# Type aliases for callbacks
ProgressCallback = callable[[int, int, str], None]
FileCallback = callable[[Path, bool], None]
ErrorCallback = callable[[str, Exception], None]


class ReconcileManager:
    """
    Manager for reconciling files between local and remote storage.

    This class is responsible for scanning directories to find missing files,
    fetching them from appropriate remote sources, and maintaining a local cache.
    """

    def __init__(self, cache_db, cdn_store, s3_store, max_concurrency=10):
        """Initialize the ReconcileManager."""
        self.cache_db = cache_db
        self.cdn_store = cdn_store
        self.s3_store = s3_store
        self.max_concurrency = max_concurrency

    async def _is_recent(self, ts: datetime) -> bool:
        """
        Check if a timestamp is recent for determining the appropriate store.

        Args:
            ts: The timestamp to check

        Returns:
            True if the timestamp is considered recent, False otherwise
        """
        # Implementation would be here
        pass

    def _get_local_path(self, ts: datetime, satellite: SatellitePattern) -> Path:
        """
        Get the local path for storing a file based on its timestamp.

        Args:
            ts: The timestamp for the file
            satellite: The satellite pattern

        Returns:
            A Path object for the local file
        """
        # Implementation would be here
        pass

    async def _group_timestamps_by_recency(
        self, missing_timestamps: Set[datetime]
    ) -> Tuple[Set[datetime], Set[datetime]]:
        """
        Group timestamps by recency for efficient store handling.

        Args:
            missing_timestamps: Set of missing timestamps to group

        Returns:
            Tuple of (recent_timestamps, old_timestamps)
        """
        recent_timestamps = set()
        old_timestamps = set()

        for ts in missing_timestamps:
            if await self._is_recent(ts):
                recent_timestamps.add(ts)
            else:
                old_timestamps.add(ts)

        return recent_timestamps, old_timestamps

    def _update_progress(
        self,
        progress_callback: Optional[ProgressCallback],
        step: int,
        total_steps: int,
        message: str,
    ) -> None:
        """
        Update progress using the progress callback if provided.

        Args:
            progress_callback: Optional callback for progress updates
            step: Current step
            total_steps: Total number of steps
            message: Progress message
        """
        if progress_callback:
            progress_callback(step, total_steps, message)

    def _log_file_not_found_details(self, ts: datetime) -> None:
        """
        Log detailed information about a file not found error.

        Args:
            ts: The timestamp that was not found
        """
        # Calculate day of year for clearer debugging
        doy = ts.strftime("%j")

        # Find nearest standard GOES imagery intervals for better error messaging
        nearest_intervals = TimeIndex.find_nearest_intervals(ts)
        nearest_intervals_str = ", ".join(
            [dt.strftime("%Y-%m-%d %H:%M") for dt in nearest_intervals]
        )

        # Log detailed debugging information
        LOGGER.warning(f"File not found remotely for {ts.isoformat()} (DOY={doy})")
        LOGGER.debug(f"Note: NOAA GOES imagery is available at specific time intervals")
        LOGGER.debug(
            f"Input timestamp: year={ts.year}, doy={doy}, hour={ts.hour}, minute={ts.minute}"
        )
        LOGGER.debug(
            f"Standard GOES intervals: {TimeIndex.STANDARD_INTERVALS} minutes past the hour"
        )
        LOGGER.debug(f"Nearest standard timestamps: {nearest_intervals_str}")

    async def _process_netcdf_file(
        self,
        downloaded_path: Path,
        ts: datetime,
        progress_callback: Optional[ProgressCallback] = None,
        idx: int = 0,
        source_total: int = 0,
    ) -> Path:
        """
        Process a downloaded NetCDF file (render to PNG).

        Args:
            downloaded_path: Path to the downloaded NetCDF file
            ts: Timestamp for progress reporting
            progress_callback: Optional callback for progress updates
            idx: Current file index
            source_total: Total number of files

        Returns:
            Path to the rendered PNG file
        """
        if progress_callback:
            render_message = f"Rendering NetCDF to PNG: {ts.isoformat()}"
            progress_callback(
                3, 4, f"Step 4/4: {render_message} ({idx+1}/{source_total})"
            )

        # Render NetCDF to PNG
        png_path = render_png(
            netcdf_path=downloaded_path,
            output_path=downloaded_path.with_suffix(".png"),
        )

        return png_path

    async def _handle_successful_download(
        self,
        ts: datetime,
        satellite: SatellitePattern,
        downloaded_path: Path,
        file_callback: Optional[FileCallback] = None,
    ) -> Path:
        """
        Handle a successful file download (update cache and call callbacks).

        Args:
            ts: Timestamp of the downloaded file
            satellite: Satellite pattern
            downloaded_path: Path to the downloaded file
            file_callback: Optional callback for file download completion

        Returns:
            Path to the downloaded file
        """
        # Update cache
        await self.cache_db.add_timestamp(
            timestamp=ts,
            satellite=satellite,
            file_path=str(downloaded_path),
            found=True,
        )

        # Notify via callback if provided
        if file_callback:
            file_callback(downloaded_path, True)

        return downloaded_path

    def _handle_file_not_found(
        self,
        ts: datetime,
        satellite: SatellitePattern,
        local_path: Path,
        file_callback: Optional[FileCallback] = None,
        error_callback: Optional[ErrorCallback] = None,
    ) -> Exception:
        """
        Handle a file not found error.

        Args:
            ts: Timestamp of the file
            satellite: Satellite pattern
            local_path: Local path where the file would be saved
            file_callback: Optional callback for file download completion
            error_callback: Optional callback for errors

        Returns:
            FileNotFoundError exception
        """
        # Log detailed information
        self._log_file_not_found_details(ts)

        # Add DOY info to error message for clearer debugging
        doy = ts.strftime("%j")  # Day of year as string

        # Notify via callback if provided
        if file_callback:
            file_callback(local_path, False)

        # Create enhanced error message with suggestions
        msg = f"File not found remotely for {ts.isoformat()} (DOY={doy})"
        msg = f"{msg} - Try timestamps at {TimeIndex.STANDARD_INTERVALS} minutes past the hour instead"

        error = FileNotFoundError(msg)

        # Call error callback if provided
        if error_callback:
            error_callback(str(local_path), error)

        return error

    def _handle_known_error(
        self,
        e: Exception,
        ts: datetime,
        source_name: str,
        satellite: SatellitePattern,
        store: RemoteStore,
        local_path: Path,
        error_callback: Optional[ErrorCallback] = None,
    ) -> Exception:
        """
        Handle known error types (ResourceNotFoundError, AuthenticationError, etc.).

        Args:
            e: The exception that was raised
            ts: Timestamp of the file
            source_name: Name of the source store (CDN, S3)
            satellite: Satellite pattern
            store: The RemoteStore instance
            local_path: Local path where the file would be saved
            error_callback: Optional callback for errors

        Returns:
            The original exception
        """
        # Enhanced error logging
        LOGGER.error(
            f"Error fetching {ts.isoformat()} from {source_name}: {e.get_user_message()}"
        )

        # Log additional details if available
        if hasattr(e, "technical_details") and e.technical_details:
            LOGGER.debug(
                f"Technical details for {ts.isoformat()}: {e.technical_details}"
            )

        # Log extra debug info
        LOGGER.debug(
            f"Download error context - Satellite: {satellite}, "
            f"Store: {store.__class__.__name__}, Remote exists check failed"
        )

        # Call error callback if provided
        if error_callback:
            error_callback(str(local_path), e)

        return e

    def _handle_unexpected_error(
        self,
        e: Exception,
        ts: datetime,
        source_name: str,
        satellite: SatellitePattern,
        store: RemoteStore,
        local_path: Path,
        error_callback: Optional[ErrorCallback] = None,
    ) -> RemoteStoreError:
        """
        Handle unexpected errors by wrapping them in a RemoteStoreError.

        Args:
            e: The exception that was raised
            ts: Timestamp of the file
            source_name: Name of the source store (CDN, S3)
            satellite: Satellite pattern
            store: The RemoteStore instance
            local_path: Local path where the file would be saved
            error_callback: Optional callback for errors

        Returns:
            Wrapped RemoteStoreError exception
        """
        # Enhanced error logging
        LOGGER.error(
            f"CRITICAL ERROR fetching {ts.isoformat()} from {source_name}: {str(e)}"
        )
        LOGGER.error(f"Stacktrace for {ts.isoformat()}: {traceback.format_exc()}")

        # Log as much context as possible
        LOGGER.debug(
            f"Download context - Satellite: {satellite}, Store type: {store.__class__.__name__}"
        )
        LOGGER.debug(
            f"Download context - Local path: {local_path}, TS: {ts.isoformat()}"
        )

        # Try to get more information about the store
        try:
            store_info = "Unknown"
            if hasattr(store, "base_url"):
                store_info = f"base_url={store.base_url}"
            elif hasattr(store, "bucket_name"):
                store_info = f"bucket={store.bucket_name}"
            LOGGER.debug(f"Store details: {store_info}")
        except Exception as store_err:
            LOGGER.debug(f"Unable to get store details: {store_err}")

        # Create wrapped error
        wrapped_error = RemoteStoreError(
            message=f"Unexpected error downloading {satellite.name} data",
            technical_details=f"Error during download for {ts.isoformat()}: {str(e)}",
            original_exception=e,
        )

        # Call error callback if provided
        if error_callback:
            error_callback(str(local_path), wrapped_error)

        return wrapped_error

    async def _fetch_single_file(
        self,
        ts: datetime,
        satellite: SatellitePattern,
        store: RemoteStore,
        is_recent: bool,
        source_name: str,
        idx: int,
        source_total: int,
        progress_callback: Optional[ProgressCallback] = None,
        file_callback: Optional[FileCallback] = None,
        error_callback: Optional[ErrorCallback] = None,
        semaphore: asyncio.Semaphore = None,
    ) -> Tuple[datetime, Union[Path, Exception]]:
        """
        Fetch a single file from a remote store with comprehensive error handling.

        Args:
            ts: Timestamp to fetch
            satellite: Satellite pattern
            store: Remote store to use
            is_recent: Whether this is a recent timestamp (affects messaging)
            source_name: Name of the source (for logging)
            idx: Index in the batch
            source_total: Total number of files in the batch
            progress_callback: Optional callback for progress updates
            file_callback: Optional callback for file completion
            error_callback: Optional callback for errors
            semaphore: Optional semaphore for concurrency control

        Returns:
            Tuple of (timestamp, result) where result is either a Path or Exception
        """
        async with semaphore:
            # Update progress
            step = 2 if is_recent else 3
            if progress_callback:
                if is_recent:
                    step_message = f"Step 3/4: Downloading from CDN ({idx+1}/{source_total}): {ts.isoformat()}"
                else:
                    step_message = f"Step 4/4: Downloading from S3 ({idx+1}/{source_total}): {ts.isoformat()}"
                progress_callback(step, 4, step_message)

            # Get local path for the file
            local_path = self._get_local_path(ts, satellite)

            try:
                # Check if file exists remotely
                exists_message = f"Checking {source_name} for {ts.isoformat()}"
                if progress_callback:
                    progress_callback(
                        step,
                        4,
                        f"Step {step+1}/4: {exists_message} ({idx+1}/{source_total})",
                    )

                if await store.exists(ts, satellite):
                    # File exists, download it
                    download_message = (
                        f"Downloading from {source_name}: {ts.isoformat()}"
                    )
                    if progress_callback:
                        progress_callback(
                            step,
                            4,
                            f"Step {step+1}/4: {download_message} ({idx+1}/{source_total})",
                        )

                    # Download the file
                    downloaded_path = await store.download(ts, satellite, local_path)

                    # For S3 NetCDF files, render to PNG
                    if not is_recent and downloaded_path.suffix.lower() == ".nc":
                        downloaded_path = await self._process_netcdf_file(
                            downloaded_path, ts, progress_callback, idx, source_total
                        )

                    # Handle successful download
                    await self._handle_successful_download(
                        ts, satellite, downloaded_path, file_callback
                    )

                    return ts, downloaded_path
                else:
                    # File not found remotely
                    not_found_message = (
                        f"File not found on {source_name}: {ts.isoformat()}"
                    )
                    if progress_callback:
                        progress_callback(
                            step,
                            4,
                            f"Step {step+1}/4: {not_found_message} ({idx+1}/{source_total})",
                        )

                    # Update cache to mark as not found
                    await self.cache_db.add_timestamp(
                        timestamp=ts, satellite=satellite, file_path="", found=False
                    )

                    # Handle file not found error
                    error = self._handle_file_not_found(
                        ts, satellite, local_path, file_callback, error_callback
                    )

                    return ts, error

            except (
                ResourceNotFoundError,
                AuthenticationError,
                ConnectionError,
                RemoteStoreError,
            ) as e:
                # Handle known errors
                error_message = f"Error fetching from {source_name}: {ts.isoformat()}"
                if progress_callback:
                    progress_callback(
                        step,
                        4,
                        f"Step {step+1}/4: {error_message} ({idx+1}/{source_total})",
                    )

                # Handle known error
                error = self._handle_known_error(
                    e, ts, source_name, satellite, store, local_path, error_callback
                )

                return ts, error

            except Exception as e:
                # Handle unexpected errors
                error_message = f"Unexpected error from {source_name}: {ts.isoformat()}"
                if progress_callback:
                    progress_callback(
                        step,
                        4,
                        f"Step {step+1}/4: {error_message} ({idx+1}/{source_total})",
                    )

                # Handle unexpected error
                error = self._handle_unexpected_error(
                    e, ts, source_name, satellite, store, local_path, error_callback
                )

                return ts, error

    async def _process_recent_files(
        self,
        recent_timestamps: Set[datetime],
        satellite: SatellitePattern,
        progress_callback: Optional[ProgressCallback] = None,
        file_callback: Optional[FileCallback] = None,
        error_callback: Optional[ErrorCallback] = None,
        semaphore: asyncio.Semaphore = None,
    ) -> Dict[datetime, Union[Path, Exception]]:
        """
        Process recent files using the CDN store.

        Args:
            recent_timestamps: Set of recent timestamps to fetch
            satellite: Satellite pattern
            progress_callback: Optional callback for progress updates
            file_callback: Optional callback for file completion
            error_callback: Optional callback for errors
            semaphore: Semaphore for concurrency control

        Returns:
            Dictionary mapping timestamps to downloaded paths or exceptions
        """
        results = {}

        # Update progress
        if progress_callback and recent_timestamps:
            progress_callback(
                2,
                4,
                f"Step 3/4: Downloading {len(recent_timestamps)} recent files from CDN...",
            )

        # Generate tasks for fetching from CDN
        cdn_tasks = []
        async with self.cdn_store:
            for i, ts in enumerate(sorted(recent_timestamps)):
                cdn_tasks.append(
                    self._fetch_single_file(
                        ts=ts,
                        satellite=satellite,
                        store=self.cdn_store,
                        is_recent=True,
                        source_name="CDN",
                        idx=i,
                        source_total=len(recent_timestamps),
                        progress_callback=progress_callback,
                        file_callback=file_callback,
                        error_callback=error_callback,
                        semaphore=semaphore,
                    )
                )

            if cdn_tasks:
                # Wait for all tasks to complete
                fetch_results = await asyncio.gather(*cdn_tasks)

                # Add results to the dictionary
                for ts, result in fetch_results:
                    results[ts] = result

        return results

    async def _process_old_files(
        self,
        old_timestamps: Set[datetime],
        satellite: SatellitePattern,
        progress_callback: Optional[ProgressCallback] = None,
        file_callback: Optional[FileCallback] = None,
        error_callback: Optional[ErrorCallback] = None,
        semaphore: asyncio.Semaphore = None,
    ) -> Dict[datetime, Union[Path, Exception]]:
        """
        Process older files using the S3 store.

        Args:
            old_timestamps: Set of older timestamps to fetch
            satellite: Satellite pattern
            progress_callback: Optional callback for progress updates
            file_callback: Optional callback for file completion
            error_callback: Optional callback for errors
            semaphore: Semaphore for concurrency control

        Returns:
            Dictionary mapping timestamps to downloaded paths or exceptions
        """
        results = {}

        # Update progress
        if progress_callback and old_timestamps:
            progress_callback(
                3,
                4,
                f"Step 4/4: Downloading {len(old_timestamps)} older files from S3...",
            )

        # Generate tasks for fetching from S3
        s3_tasks = []
        async with self.s3_store:
            for i, ts in enumerate(sorted(old_timestamps)):
                s3_tasks.append(
                    self._fetch_single_file(
                        ts=ts,
                        satellite=satellite,
                        store=self.s3_store,
                        is_recent=False,
                        source_name="S3",
                        idx=i,
                        source_total=len(old_timestamps),
                        progress_callback=progress_callback,
                        file_callback=file_callback,
                        error_callback=error_callback,
                        semaphore=semaphore,
                    )
                )

            if s3_tasks:
                # Wait for all tasks to complete
                fetch_results = await asyncio.gather(*s3_tasks)

                # Add results to the dictionary
                for ts, result in fetch_results:
                    results[ts] = result

        return results

    async def fetch_missing_files(
        self,
        missing_timestamps: Set[datetime],
        satellite: SatellitePattern,
        progress_callback: Optional[ProgressCallback] = None,
        file_callback: Optional[FileCallback] = None,
        error_callback: Optional[ErrorCallback] = None,
    ) -> Dict[datetime, Union[Path, Exception]]:
        """Fetch missing files from remote sources.

        Args:
            missing_timestamps: Set of missing timestamps to fetch
            satellite: Satellite pattern enum
            progress_callback: Callback for progress updates
            file_callback: Callback when a file is processed
            error_callback: Callback when an error occurs

        Returns:
            Dictionary mapping timestamps to downloaded paths or exceptions
        """
        results = {}
        total = len(missing_timestamps)

        # Early exit if no missing files
        if not missing_timestamps:
            self._update_progress(progress_callback, 0, 1, "No missing files to fetch")
            LOGGER.info("No missing files to fetch")
            return results

        # Step 1: Analyze and group timestamps
        self._update_progress(
            progress_callback, 0, 4, "Step 1/4: Analyzing missing files..."
        )
        LOGGER.info(f"Fetching {total} missing files")

        # Group timestamps by recency for efficient store handling
        recent_timestamps, old_timestamps = await self._group_timestamps_by_recency(
            missing_timestamps
        )

        # Step 2: Preparing download strategy
        self._update_progress(
            progress_callback,
            1,
            4,
            f"Step 2/4: Preparing download strategy ({len(recent_timestamps)} CDN, "
            f"{len(old_timestamps)} S3)...",
        )

        LOGGER.debug(
            f"Fetching strategy: {len(recent_timestamps)} recent files from CDN, "
            f"{len(old_timestamps)} older files from S3"
        )

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.max_concurrency)

        # Step 3: Download recent files from CDN
        cdn_results = await self._process_recent_files(
            recent_timestamps,
            satellite,
            progress_callback,
            file_callback,
            error_callback,
            semaphore,
        )
        results.update(cdn_results)

        # Step 4: Download older files from S3
        s3_results = await self._process_old_files(
            old_timestamps,
            satellite,
            progress_callback,
            file_callback,
            error_callback,
            semaphore,
        )
        results.update(s3_results)

        # Final summary
        success_count = sum(1 for v in results.values() if isinstance(v, Path))
        success_message = (
            f"Download complete: {success_count}/{total} files downloaded successfully"
        )

        LOGGER.info(success_message)
        self._update_progress(progress_callback, 4, 4, success_message)

        return results
