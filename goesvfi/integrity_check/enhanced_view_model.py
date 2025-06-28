"""Enhanced ViewModel for the Integrity Check tab with CDN/S3 hybrid fetching.

This module provides the EnhancedIntegrityCheckViewModel class, which extends
the base IntegrityCheckViewModel with support for hybrid CDN/S3 fetching of
GOES-16 and GOES-18 Band 13 imagery.
"""

import asyncio
from datetime import datetime, timedelta
from enum import Enum
import os
from pathlib import Path
import time
import traceback
from typing import Any, cast

from PyQt6.QtCore import QObject, QRunnable, QThread, QThreadPool, pyqtSignal

from goesvfi.utils import log

from .cache_db import CacheDB
from .reconcile_manager import ReconcileManager
from .reconciler import Reconciler
from .remote.base import (
    AuthenticationError,
    ConnectionError,
    RemoteStoreError,
    ResourceNotFoundError,
)
from .remote.cdn_store import CDNStore
from .remote.s3_store import S3Store
from .thread_cache_db import ThreadLocalCacheDB
from .time_index import SatellitePattern, TimeIndex
from .view_model import IntegrityCheckViewModel, MissingTimestamp, ScanStatus


# Define fetch source enum
class FetchSource(Enum):
    AUTO = "auto"
    S3 = "s3"
    CDN = "cdn"
    LOCAL = "local"  # Local files only


LOGGER = log.get_logger(__name__)


class EnhancedMissingTimestamp(MissingTimestamp):
    """Enhanced missing timestamp class with satellite and source information."""

    def __init__(self, timestamp: datetime, expected_filename: str) -> None:
        super().__init__(timestamp, expected_filename)
        self.satellite: str = ""  # Override parent's satellite property
        self.source = ""  # "cdn" or "s3"
        self.progress = 0  # Download progress (0-100)

    def as_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        result = super().as_dict()
        result.update({
            "satellite": self.satellite,
            "source": self.source,
            "progress": self.progress,
        })
        return result


# FetchSource enum is already defined above (line 21) with all options


class EnhancedIntegrityCheckViewModel(IntegrityCheckViewModel):
    """Enhanced ViewModel for the Integrity Check tab with support for hybrid CDN/S3 fetching.

    This class extends the base IntegrityCheckViewModel to provide support for:
    1. GOES-16 and GOES-18 satellites
    2. Hybrid CDN/S3 fetching based on timestamp recency
    3. NetCDF to PNG rendering for S3 data
    4. Enhanced progress reporting
    """

    # Additional signals for enhanced functionality
    fetch_source_changed = pyqtSignal(FetchSource)
    satellite_changed = pyqtSignal(SatellitePattern)
    download_item_progress = pyqtSignal(int, int)  # index, progress percentage
    disk_space_updated = pyqtSignal(float, float)  # used_gb, total_gb

    def __init__(
        self,
        base_reconciler: Reconciler | None = None,
        cache_db: CacheDB | None = None,
        cdn_store: CDNStore | None = None,
        s3_store: S3Store | None = None,
    ) -> None:
        """Initialize the EnhancedIntegrityCheckViewModel.

        Args:
            base_reconciler: Optional Reconciler instance for backward compatibility
            cache_db: Optional CacheDB instance, will create one if not provided
            cdn_store: Optional CDNStore instance, will create one if not provided
            s3_store: Optional S3Store instance, will create one if not provided
        """
        # Initialize the base class
        super().__init__(base_reconciler)

        # Initialize enhanced state properties
        self._satellite = SatellitePattern.GOES_18  # Default to GOES-18
        self._fetch_source = FetchSource.AUTO  # Default to auto (hybrid)
        self.preferred_source = self._fetch_source  # For backward compatibility
        self._max_concurrent_downloads = 5
        self._cdn_resolution = TimeIndex.CDN_RES  # Default resolution
        self._aws_profile: str | None = None
        self._s3_region = "us-east-1"

        # Initialize thread-local CacheDB and stores for thread safety
        # Check if passed cache_db is already thread-local
        if cache_db is not None and not isinstance(cache_db, ThreadLocalCacheDB):
            LOGGER.info("Converting regular CacheDB to thread-local CacheDB for thread safety")
            self._cache_db = ThreadLocalCacheDB(db_path=cache_db.db_path)
            # Close the original connection since we won't use it
            cache_db.close()
        else:
            self._cache_db = cache_db or ThreadLocalCacheDB()

        # Log the type of cache DB being used
        LOGGER.debug(
            "Enhanced view model using cache DB of type: %s",
            type(self._cache_db).__name__,
        )

        self._cdn_store = cdn_store or CDNStore(resolution=self._cdn_resolution)
        self._s3_store = s3_store or S3Store(aws_profile=self._aws_profile, aws_region=self._s3_region)

        # Create the ReconcileManager with thread-local cache
        self._reconcile_manager = ReconcileManager(
            cache_db=self._cache_db,
            base_dir=self._base_directory,
            cdn_store=self._cdn_store,
            s3_store=self._s3_store,
            cdn_resolution=self._cdn_resolution,
            max_concurrency=self._max_concurrent_downloads,
        )

        # Result data for enhanced functionality
        self._missing_timestamps = []  # Override with EnhancedMissingTimestamp objects
        self._downloaded_count = 0
        self._failed_count = 0

        # Initialize async state
        self._async_task = None
        self._scan_task_future = None
        self._download_task_future = None

        # Initialize thread pool with min lifetime to keep tasks alive
        self._thread_pool = QThreadPool.globalInstance()
        if self._thread_pool is not None:
            self._thread_pool.setExpiryTimeout(30000)  # Keep threads alive for 30 seconds

        # Keep references to active tasks to prevent premature cleanup
        self._active_tasks: list[QRunnable] = []

        # Download tracking properties
        self._downloaded_success_count = 0
        self._downloaded_failed_count = 0
        self._download_start_time = 0.0
        self._last_download_rate = 0.0
        self._currently_downloading_items: list[datetime] = []

        # Setup disk space check timer - disabled for now due to blocking issues
        self._disk_space_timer = QThread()
        self._disk_space_timer.setObjectName("DiskSpaceCheckerThread")
        # self._disk_space_timer.started.connect(self._check_disk_space_loop)
        # self._disk_space_timer.start()
        # Instead, just emit a single disk space update
        try:
            used_gb, total_gb = self.get_disk_space_info()
            self.disk_space_updated.emit(used_gb, total_gb)
        except Exception:
            LOGGER.exception("Error in initial disk space check")

    # --- Additional property accessors ---

    @property
    def satellite(self) -> SatellitePattern:
        """Get the selected satellite."""
        return self._satellite

    @satellite.setter
    def satellite(self, value: SatellitePattern) -> None:
        """Set the selected satellite and emit signal."""
        if self._satellite != value:
            self._satellite = value
            self.satellite_changed.emit(value)

    @property
    def fetch_source(self) -> FetchSource:
        """Get the fetch source."""
        return self._fetch_source

    @fetch_source.setter
    def fetch_source(self, value: FetchSource) -> None:
        """Set the fetch source and emit signal."""
        if self._fetch_source != value:
            self._fetch_source = value
            self.fetch_source_changed.emit(value)

    @property
    def cdn_resolution(self) -> str:
        """Get the CDN resolution."""
        return self._cdn_resolution

    @cdn_resolution.setter
    def cdn_resolution(self, value: str) -> None:
        """Set the CDN resolution."""
        self._cdn_resolution = value

    @property
    def downloaded_success_count(self) -> int:
        """Get the number of successfully downloaded files in the current session."""
        return self._downloaded_success_count

    @property
    def downloaded_failed_count(self) -> int:
        """Get the number of failed downloads in the current session."""
        return self._downloaded_failed_count

    @property
    def currently_downloading_items(self) -> list[datetime]:
        """Get the list of timestamps currently being downloaded."""
        return self._currently_downloading_items

    def is_item_downloading(self, timestamp: datetime) -> bool:
        """Check if a specific timestamp is currently being downloaded.

        Args:
            timestamp: The timestamp to check

        Returns:
            True if the timestamp is in the downloading list, False otherwise
        """
        return timestamp in self._currently_downloading_items

    def get_downloading_item_by_timestamp(self, timestamp: datetime) -> MissingTimestamp | None:
        """Get a downloading item by its timestamp.

        Args:
            timestamp: The timestamp to look for

        Returns:
            The MissingTimestamp object if found, None otherwise
        """
        for item in self._missing_timestamps:
            if item.timestamp == timestamp and item.is_downloading:
                return item
        return None

    def cancel_item_download(self, timestamp: datetime) -> bool:
        """Cancel the download of a specific item.

        Args:
            timestamp: The timestamp of the item to cancel

        Returns:
            True if the item was found and canceled, False otherwise
        """
        # First check if the item is in the download list
        if timestamp not in self._currently_downloading_items:
            return False

        # Remove from the currently downloading list
        self._currently_downloading_items.remove(timestamp)

        # Find the corresponding item and update its state
        for i, item in enumerate(self._missing_timestamps):
            if item.timestamp == timestamp:
                item.is_downloading = False
                item.download_error = "Download canceled by user"
                # Update the UI
                self.download_item_updated.emit(i, item)
                return True

        return False

    # Define a separate method instead of property setter to avoid conflicts
    def update_cdn_resolution(self, value: str) -> None:
        """Set the CDN resolution."""
        self._cdn_resolution = value

        # Update the CDN store
        if self._cdn_store:
            self._cdn_store = CDNStore(resolution=value)

        # Update the ReconcileManager
        if self._reconcile_manager:
            self._reconcile_manager = ReconcileManager(
                cache_db=self._cache_db,
                base_dir=self._base_directory,
                cdn_store=self._cdn_store,
                s3_store=self._s3_store,
                cdn_resolution=self._cdn_resolution,
                max_concurrency=self._max_concurrent_downloads,
            )

    @property
    def aws_profile(self) -> str | None:
        """Get the AWS profile name."""
        return self._aws_profile

    @aws_profile.setter
    def aws_profile(self, value: str | None) -> None:
        """Set the AWS profile name."""
        self.set_aws_profile(value)

    # Use regular method instead of property setter to avoid type issues
    def set_aws_profile(self, value: str | None) -> None:
        """Set the AWS profile name."""
        self._aws_profile = value

        # Update the S3 store
        if self._s3_store:
            self._s3_store = S3Store(aws_profile=value, aws_region=self._s3_region)

        # Update the ReconcileManager
        if self._reconcile_manager:
            self._reconcile_manager = ReconcileManager(
                cache_db=self._cache_db,
                base_dir=self._base_directory,
                cdn_store=self._cdn_store,
                s3_store=self._s3_store,
                cdn_resolution=self._cdn_resolution,
                max_concurrency=self._max_concurrent_downloads,
            )

    @property
    def max_concurrent_downloads(self) -> int:
        """Get the maximum concurrent downloads."""
        return self._max_concurrent_downloads

    @max_concurrent_downloads.setter
    def max_concurrent_downloads(self, value: int) -> None:
        """Set the maximum concurrent downloads."""
        self._max_concurrent_downloads = value

        # Update the ReconcileManager
        if self._reconcile_manager:
            self._reconcile_manager = ReconcileManager(
                cache_db=self._cache_db,
                base_dir=self._base_directory,
                cdn_store=self._cdn_store,
                s3_store=self._s3_store,
                cdn_resolution=self._cdn_resolution,
                max_concurrency=value,
            )

    # --- Enhanced command methods ---

    def start_enhanced_scan(self) -> None:
        """Start the enhanced scan operation with async support."""
        if not self.can_start_scan:
            LOGGER.warning("Cannot start scan: Operation in progress or directory invalid")
            return

        # Log scan parameters for debugging
        LOGGER.debug("Starting enhanced scan with parameters:")
        LOGGER.debug("  Base directory: %s", self._base_directory)
        LOGGER.debug("  Satellite: %s", self._satellite)
        LOGGER.debug("  Date range: %s to %s", self._start_date, self._end_date)
        LOGGER.debug("  Interval minutes: %s", self._interval_minutes)

        # Update state
        self.status = ScanStatus.SCANNING
        self.status_message = "Starting scan..."
        self._cancel_requested = False
        self._missing_timestamps = []
        self.missing_items_updated.emit([])

        # Create AsyncScanTask
        LOGGER.debug("Creating AsyncScanTask instance")
        scan_task = AsyncScanTask(self)

        # Keep a reference to prevent garbage collection
        if not hasattr(self, "_active_tasks"):
            self._active_tasks = []
        self._active_tasks.append(scan_task)

        # Configure the task to be auto-deleting only AFTER all processing is done
        scan_task.setAutoDelete(False)

        # Start the task
        LOGGER.debug("Starting AsyncScanTask in thread pool")
        if self._thread_pool is not None:
            self._thread_pool.start(scan_task)
        LOGGER.info("Enhanced scan task started - waiting for progress updates")

    def start_enhanced_downloads(self) -> None:
        """Start downloading missing files with enhanced CDN/S3 support."""
        if self._status == ScanStatus.DOWNLOADING:
            LOGGER.warning("Download already in progress")
            return

        if not self.has_missing_items:
            LOGGER.warning("No missing items to download")
            return

        # Update state
        self.status = ScanStatus.DOWNLOADING
        self.status_message = "Starting downloads..."
        self._cancel_requested = False
        self._downloaded_count = 0
        self._failed_count = 0

        # Reset download tracking metrics for this session
        self._downloaded_success_count = 0
        self._downloaded_failed_count = 0
        self._download_start_time = time.time()
        self._last_download_rate = 0.0

        # Clear previous download list and add all timestamps that need to be downloaded
        self._currently_downloading_items = []
        for item in self._missing_timestamps:
            if not item.is_downloaded and not item.download_error:
                self._currently_downloading_items.append(item.timestamp)
                item.is_downloading = True

        # Create AsyncDownloadTask
        download_task = AsyncDownloadTask(self)

        # Start the task
        if self._thread_pool is not None:
            self._thread_pool.start(download_task)
        LOGGER.info("Enhanced download task started for %s items", len(self._missing_timestamps))

    def get_disk_space_info(self) -> tuple[float, float]:
        """Get disk space information for the base directory.

        Returns:
            Tuple of (used_gb, total_gb)
        """
        try:
            if not self._base_directory.exists():
                return 0.0, 0.0

            # Get disk usage statistics
            usage = os.statvfs(self._base_directory)
            total = usage.f_blocks * usage.f_frsize
            free = usage.f_bavail * usage.f_frsize
            used = total - free

            # Convert to GB
            total_gb = total / (1024**3)
            used_gb = used / (1024**3)

            return used_gb, total_gb
        except Exception:
            LOGGER.exception("Error getting disk space info")
            return 0.0, 0.0

    def reset_database(self) -> None:
        """Reset the database and clear all cached data."""
        try:
            if hasattr(self._cache_db, "reset_database"):
                self._cache_db.reset_database()
                self.status_message = "Database reset successfully"
            else:
                self.status_message = "Database reset not supported by current cache implementation"
        except Exception as e:
            LOGGER.exception("Error resetting database")
            self.status_message = f"Error resetting database: {e}"

    # --- Callback handlers and utility methods ---

    def _check_disk_space_loop(self) -> None:
        """Background loop to check disk space periodically."""
        # Using a flag to allow safer shutdown
        self._stop_disk_space_check = False
        check_count = 0

        while not self._stop_disk_space_check and check_count < 100:  # Limit to 100 checks
            try:
                used_gb, total_gb = self.get_disk_space_info()
                self.disk_space_updated.emit(used_gb, total_gb)
            except Exception:
                LOGGER.exception("Error in disk space check")

            # Sleep for 5 seconds
            time.sleep(5)
            check_count += 1

        LOGGER.info("Disk space check loop completed")

    def _handle_enhanced_scan_progress(self, current: int, total: int, message: str) -> None:
        """Handle progress updates from the enhanced scan operation."""
        self._progress_current = current
        self._progress_total = total

        # Update UI
        self.status_message = message
        self.progress_updated.emit(current, total, 0.0)  # No ETA calculation

    def _handle_enhanced_scan_completed(self, result: dict[str, Any]) -> None:
        """Handle completion of the enhanced scan operation."""
        if result.get("status") == "cancelled":
            self.status = ScanStatus.CANCELLED
            self.status_message = "Scan cancelled"
            self.scan_completed.emit(False, "Scan was cancelled")
            return

        if result.get("status") == "error":
            self.status = ScanStatus.ERROR
            error_msg = result.get("error", "Unknown error")
            self.status_message = f"Scan error: {error_msg}"
            self.scan_completed.emit(False, error_msg)
            return

        # Process successful result
        self._last_scan_time = datetime.now()

        # Extract scan results
        existing_timestamps = result.get("existing", set())
        missing_timestamps = result.get("missing", set())

        self._total_expected = len(existing_timestamps) + len(missing_timestamps)
        self._total_found = len(existing_timestamps)

        # Convert missing timestamps to enhanced objects
        self._missing_timestamps = []

        for ts in sorted(missing_timestamps):
            # Generate filename based on satellite
            expected_filename = f"{self._satellite.name.lower()}_{ts.strftime('%Y%m%d_%H%M%S')}_band13.png"

            item = EnhancedMissingTimestamp(ts, expected_filename)
            item.satellite = cast("Any", self._satellite)

            # Determine source based on recency
            cutoff = datetime.utcnow() - timedelta(days=TimeIndex.RECENT_WINDOW_DAYS)
            if ts >= cutoff:
                item.source = "cdn"
            else:
                item.source = "s3"

            self._missing_timestamps.append(item)

        # Update UI
        missing_count = len(self._missing_timestamps)
        if missing_count > 0:
            self.status_message = f"Scan complete: {missing_count} missing items found"
            self.missing_items_updated.emit(self._missing_timestamps)

            # Auto-download if enabled
            if self._auto_download and missing_count > 0:
                self.start_enhanced_downloads()
            else:
                self.status = ScanStatus.COMPLETED
        else:
            self.status_message = "Scan complete: No missing items found"
            self.status = ScanStatus.COMPLETED
            self.missing_items_updated.emit([])

        # Emit completion signal
        self.scan_completed.emit(
            True,
            f"Found {missing_count} missing out of {self._total_expected} expected timestamps",
        )

    def download_missing_items(self, items: list[MissingTimestamp]) -> None:
        """Download specific missing items.

        Args:
            items: List of MissingTimestamp objects to download
        """
        if not items:
            LOGGER.warning("No items to download")
            return

        if self._status == ScanStatus.DOWNLOADING:
            LOGGER.warning("Download already in progress")
            return

        # Update state
        self.status = ScanStatus.DOWNLOADING
        self.status_message = f"Starting downloads for {len(items)} items..."
        self._cancel_requested = False
        self._downloaded_count = 0
        self._failed_count = 0

        # Reset download tracking metrics for this session
        self._downloaded_success_count = 0
        self._downloaded_failed_count = 0
        self._download_start_time = time.time()
        self._last_download_rate = 0.0

        # Clear previous download list and add all timestamps that need to be downloaded
        self._currently_downloading_items = []
        for item in items:
            if not item.is_downloaded and not item.download_error:
                if hasattr(item, "timestamp"):
                    self._currently_downloading_items.append(item.timestamp)
                item.is_downloading = True

        # Create AsyncDownloadTask
        download_task = AsyncDownloadTask(self)

        # Start the task
        if self._thread_pool is not None:
            self._thread_pool.start(download_task)
        LOGGER.info("Enhanced download task started for %s items", len(items))

    def retry_failed_downloads(self, items: list[MissingTimestamp]) -> None:
        """Retry failed downloads.

        Args:
            items: List of MissingTimestamp objects with failed downloads to retry
        """
        retry_items = [item for item in items if not item.is_downloaded and item.download_error]

        if not retry_items:
            LOGGER.warning("No failed items to retry")
            return

        # Reset error status for these items
        for item in retry_items:
            item.download_error = ""

        # Start download for these items
        self.download_missing_items(retry_items)

    def _handle_enhanced_download_progress(self, current: int, total: int, message: str) -> None:
        """Handle progress updates from the enhanced download operation."""
        self._progress_current = current
        self._progress_total = total

        # Update UI
        self.status_message = message
        self.download_progress_updated.emit(current, total)

    def _handle_download_item_progress(self, index: int, progress: int) -> None:
        """Handle progress updates for a specific download item."""
        if 0 <= index < len(self._missing_timestamps):
            item = self._missing_timestamps[index]
            if hasattr(item, "progress"):
                item.progress = progress
            # Make sure this item is marked as downloading and is in the currently_downloading_items list
            if progress > 0 and progress < 100:
                if not item.is_downloading:
                    item.is_downloading = True
                if item.timestamp not in self._currently_downloading_items:
                    self._currently_downloading_items.append(item.timestamp)
            # If download is complete, update tracking
            elif progress >= 100:
                if item.timestamp in self._currently_downloading_items:
                    self._currently_downloading_items.remove(item.timestamp)
            self.download_item_progress.emit(index, progress)

    def _handle_enhanced_download_completed(self, results: dict[datetime, Path | Exception]) -> None:
        """Handle completion of the enhanced download operation."""
        # Update item states based on results
        for i, item in enumerate(self._missing_timestamps):
            if item.timestamp in results:
                result = results[item.timestamp]

                # Update item state
                item.is_downloading = False

                # Remove from currently downloading items list if it's there
                if item.timestamp in self._currently_downloading_items:
                    self._currently_downloading_items.remove(item.timestamp)

                if isinstance(result, Path):
                    item.is_downloaded = True
                    item.download_error = ""
                    item.local_path = str(result)
                    self._downloaded_count += 1
                    self._downloaded_success_count += 1
                else:
                    # Enhanced error handling with detailed message and special cases
                    error_message = ""

                    # Handle SQLite thread errors specially with a user-friendly message
                    if "SQLite objects created in a thread" in str(result):
                        error_message = "Database thread conflict: SQLite database accessed from multiple threads."
                        # Add a more detailed explanation and workaround
                        if hasattr(result, "technical_details"):
                            result.technical_details += (
                                "\n\nThis is a known limitation with SQLite. "
                                "The application needs to be restarted to fix this issue."
                            )
                    # Use the custom error message if available
                    elif hasattr(result, "get_user_message"):
                        error_message = result.get_user_message()
                    else:
                        error_message = str(result)

                    item.download_error = error_message

                    # Add contextual information about day of year for easier debugging
                    doy = item.timestamp.strftime("%j")  # Day of year as string

                    # Log detailed error information
                    if hasattr(result, "technical_details"):
                        LOGGER.error(
                            "Download error for %s (DOY=%s): %s",
                            item.timestamp,
                            doy,
                            error_message,
                        )
                        LOGGER.debug("Technical details: %s", result.technical_details)
                    else:
                        LOGGER.error(
                            "Download error for %s (DOY=%s): %s",
                            item.timestamp,
                            doy,
                            error_message,
                        )

                    # For "File not found" errors, add helpful debugging notes about GOES data intervals
                    if "not found" in error_message.lower() or "no such key" in error_message.lower():
                        LOGGER.debug(
                            "Note: NOAA GOES imagery may not be available at exactly %s minutes",
                            item.timestamp.minute,
                        )
                        LOGGER.debug(
                            "Available timestamps are usually at intervals like 00, 10, 20, 30, 40, 50 minutes"
                        )
                        LOGGER.debug(
                            "Check actual timestamps available in the S3 bucket for year=%s, doy=%s",
                            item.timestamp.year,
                            doy,
                        )

                        # Just use the error message as-is to match test expectations
                        item.download_error = error_message

                    self._failed_count += 1
                    self._downloaded_failed_count += 1

                # Emit signal for UI update
                self.download_item_updated.emit(i, item)

        # Ensure currently_downloading_items is empty at the end of all downloads
        self._currently_downloading_items = cast("list[datetime]", [])

        # Update status
        self.status = ScanStatus.COMPLETED

        # Calculate download rate if we have a start time
        if self._download_start_time > 0:
            total_time = time.time() - self._download_start_time
            if total_time > 0 and (self._downloaded_success_count + self._downloaded_failed_count) > 0:
                (self._downloaded_success_count + self._downloaded_failed_count) / total_time
            self._download_start_time = 0.0  # Reset timer

        # Enhanced status message with more details
        if self._failed_count > 0:
            self.status_message = (
                f"Downloads complete: {self._downloaded_count} successful, {self._failed_count} failed"
            )
            self.status_type_changed.emit(ScanStatus.ERROR)
        else:
            self.status_message = f"Downloads complete: {self._downloaded_count} successful"

        # Clear cancel flag
        self._cancel_requested = False

    def _handle_scan_error(self, error_msg: str) -> None:
        """Handle errors during scanning with enhanced error reporting.

        Args:
            error_msg: The error message
        """
        LOGGER.error("Scan error: %s", error_msg)

        # Update status
        self.status = ScanStatus.ERROR
        self.status_message = f"Error: {error_msg}"
        self.status_type_changed.emit(self.status)

        # Emit scan completion signal with failure
        self.scan_completed.emit(False, error_msg)

        # Clear cancel flag
        self._cancel_requested = False

    def _handle_download_error(self, error_msg: str) -> None:
        """Handle errors during download with enhanced error reporting.

        Args:
            error_msg: The error message
        """
        LOGGER.error("Download error: %s", error_msg)

        # Update status
        self.status = ScanStatus.ERROR
        self.status_message = f"Download error: {error_msg}"
        self.status_type_changed.emit(self.status)

        # Clear cancel flag
        self._cancel_requested = False

    # --- Cleanup ---

    def cleanup(self) -> None:
        """Clean up resources."""
        # Check if any operations are in progress
        if hasattr(self, "_active_tasks") and self._active_tasks:
            LOGGER.warning(
                "Cleanup called with %s active tasks - will wait for completion",
                len(self._active_tasks),
            )

            # Wait for a while to let tasks complete
            for task in self._active_tasks:
                if hasattr(task, "is_running") and task.is_running:
                    LOGGER.debug("Task %s is still running during cleanup", task)

            # Don't terminate active tasks, just log a warning
            # We'll leave the tasks running to complete properly

        # Set stop flag for disk space check
        if hasattr(self, "_stop_disk_space_check"):
            self._stop_disk_space_check = True

        # Stop disk space check thread
        if hasattr(self, "_disk_space_timer"):
            try:
                if self._disk_space_timer.isRunning():
                    LOGGER.debug("Stopping disk space timer thread")
                    self._disk_space_timer.terminate()
                    timeout_ms = 1000  # 1 second timeout
                    if not self._disk_space_timer.wait(timeout_ms):
                        LOGGER.warning("Disk space timer thread did not stop in time")
            except Exception:
                LOGGER.exception("Error stopping disk space timer")

        # Close database connection
        if hasattr(self, "_cache_db"):
            try:
                LOGGER.debug("Closing cache database (type: %s)", type(self._cache_db).__name__)
                if isinstance(self._cache_db, ThreadLocalCacheDB):
                    # For thread-local DB, close all thread connections
                    LOGGER.debug("Performing thread-local database cleanup")
                self._cache_db.close()
            except Exception:
                LOGGER.exception("Error closing cache database")

        # Close base reconciler's cache
        if hasattr(self, "_reconciler") and hasattr(self._reconciler, "cache"):
            try:
                LOGGER.debug("Closing reconciler cache")
                self._reconciler.cache.close()
            except Exception:
                LOGGER.exception("Error closing reconciler cache")

        # Store active tasks list locally before removing reference
        active_tasks: list[QRunnable] = []
        if hasattr(self, "_active_tasks"):
            active_tasks = self._active_tasks.copy()

        LOGGER.info("Cleanup completed (with %s active tasks still running)", len(active_tasks))


class AsyncTaskSignals(QObject):
    """Signals for async worker threads."""

    progress = pyqtSignal(int, int, str)  # current, total, message
    error = pyqtSignal(str)
    scan_finished = pyqtSignal(object)  # Scan result dictionary
    download_finished = pyqtSignal(object)  # Download results dictionary


class AsyncScanTask(QRunnable):
    """Async task for enhanced directory scanning."""

    def __init__(self, view_model: EnhancedIntegrityCheckViewModel) -> None:
        """Initialize the scan task.

        Args:
            view_model: EnhancedIntegrityCheckViewModel instance
        """
        super().__init__()

        self.view_model = view_model
        self.signals = AsyncTaskSignals()
        self.is_running = False
        self.is_complete = False

        # Connect signals to view model
        self.signals.progress.connect(view_model._handle_enhanced_scan_progress)
        self.signals.scan_finished.connect(self._handle_scan_finished)
        self.signals.error.connect(self._handle_error)

    def _handle_scan_finished(self, result: dict[str, Any]) -> None:
        """Handle scan finished signal and cleanly remove the task."""
        self.view_model._handle_enhanced_scan_completed(result)
        self.is_complete = True
        self.is_running = False

        # Safe removal from active tasks list
        if hasattr(self.view_model, "_active_tasks") and self in self.view_model._active_tasks:
            LOGGER.debug("Removing completed task from active tasks list")
            self.view_model._active_tasks.remove(self)

    def _handle_error(self, error_msg: str) -> None:
        """Handle error signal and cleanly remove the task."""
        self.view_model._handle_scan_error(error_msg)
        self.is_complete = True
        self.is_running = False

        # Safe removal from active tasks list
        if hasattr(self.view_model, "_active_tasks") and self in self.view_model._active_tasks:
            LOGGER.debug("Removing failed task from active tasks list")
            self.view_model._active_tasks.remove(self)

    def run(self) -> None:
        """Execute the scan task."""
        self.is_running = True
        try:
            # Setup async event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Run the scan
            result = loop.run_until_complete(self._run_scan())

            # Emit result
            self.signals.scan_finished.emit(result)

            # Clean up
            loop.close()

        except (
            RemoteStoreError,
            AuthenticationError,
            ConnectionError,
            ResourceNotFoundError,
        ) as e:
            # Use our custom error types for better error messages
            LOGGER.exception("Remote store error in scan task: %s", e.get_user_message())
            if hasattr(e, "technical_details") and e.technical_details:
                LOGGER.debug("Technical details: %s", e.technical_details)
            # Emit a user-friendly error message
            self.signals.error.emit(e.get_user_message())
        except Exception as e:
            LOGGER.exception("Error in async scan task")
            LOGGER.exception(traceback.format_exc())
            self.signals.error.emit(f"Unexpected error: {e!s}")

    async def _run_scan(self) -> dict[str, Any]:
        """Run the scan operation asynchronously.

        Returns:
            Dict with scan results
        """
        try:
            # Progress callback that emits signals
            def progress_callback(current: int, total: int, message: str) -> None:
                LOGGER.debug("Progress callback: %s/%s - %s", current, total, message)
                self.signals.progress.emit(current, total, message)

            # Run the scan with enhanced progress reporting
            # Progress callback that formats step data nicely
            def enhanced_progress_callback(current_step: int, total_steps: int, message: str) -> None:
                # Log the raw progress data for debugging
                LOGGER.debug(
                    "Enhanced progress callback: step %s/%s - %s",
                    current_step,
                    total_steps,
                    message,
                )

                # Format the message with step information and pass it to the original callback
                progress_message = f"{message}"
                # Pass both the numeric progress and the formatted message
                progress_callback(current_step, total_steps, progress_message)

            LOGGER.debug(
                "Starting scan operation with params: dir=%s, sat=%s, start=%s, end=%s",
                self.view_model._base_directory,
                self.view_model._satellite.name,
                self.view_model._start_date,
                self.view_model._end_date,
            )

            existing, missing = await self.view_model._reconcile_manager.scan_directory(
                directory=self.view_model._base_directory,
                satellite=self.view_model._satellite,
                start_time=self.view_model._start_date,
                end_time=self.view_model._end_date,
                interval_minutes=self.view_model._interval_minutes,
                progress_callback=enhanced_progress_callback,
            )

            LOGGER.debug(
                "Scan completed with %s existing files and %s missing files",
                len(existing),
                len(missing),
            )

            return {
                "status": "completed",
                "existing": existing,
                "missing": missing,
                "total": len(existing) + len(missing),
            }

        except asyncio.CancelledError:
            return {"status": "cancelled"}
        except Exception as e:
            LOGGER.exception("Error in scan operation")
            return {"status": "error", "error": str(e)}


class AsyncDownloadTask(QRunnable):
    """Async task for enhanced file downloading."""

    def __init__(self, view_model: EnhancedIntegrityCheckViewModel) -> None:
        """Initialize the download task.

        Args:
            view_model: EnhancedIntegrityCheckViewModel instance
        """
        super().__init__()

        self.view_model = view_model
        self.signals = AsyncTaskSignals()

        # Connect signals to view model
        self.signals.progress.connect(view_model._handle_enhanced_download_progress)
        self.signals.download_finished.connect(view_model._handle_enhanced_download_completed)
        self.signals.error.connect(view_model._handle_download_error)  # Use dedicated download error handler

        # Keep track of running state
        self.is_running = False
        self.is_complete = False

    def run(self) -> None:
        """Execute the download task."""
        self.is_running = True
        try:
            # Setup async event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Run the downloads
            results = loop.run_until_complete(self._run_downloads())

            # Emit result
            self.signals.download_finished.emit(results)

            # Clean up
            loop.close()

            # Update task state
            self.is_complete = True
            self.is_running = False

            # Safe removal from active tasks list
            if hasattr(self.view_model, "_active_tasks") and self in self.view_model._active_tasks:
                LOGGER.debug("Removing completed download task from active tasks list")
                self.view_model._active_tasks.remove(self)

        except (
            RemoteStoreError,
            AuthenticationError,
            ConnectionError,
            ResourceNotFoundError,
        ) as e:
            # Enhanced error handling for our custom error types
            error_code = getattr(e, "error_code", "UNK-001")
            LOGGER.exception(
                "[Error %s] Remote store error in download task: %s",
                error_code,
                e.get_user_message(),
            )

            # Log troubleshooting tips if available
            if hasattr(e, "troubleshooting_tips") and e.troubleshooting_tips:
                LOGGER.info("Troubleshooting tips: %s", e.troubleshooting_tips)

            # Log technical details if available
            if hasattr(e, "technical_details") and e.technical_details:
                LOGGER.debug("Technical details: %s", e.technical_details)

            # Create a detailed error message with the error code
            if error_code:
                error_message = f"[Error {error_code}] {e.get_user_message()}"
                if hasattr(e, "technical_details") and e.technical_details:
                    error_message += f"\n\nTechnical details: {e.technical_details}"
            else:
                error_message = e.get_user_message()

            # Emit error with detailed message
            self.signals.error.emit(error_message)

            # Update task state
            self.is_complete = True
            self.is_running = False

            # Safe removal from active tasks list
            if hasattr(self.view_model, "_active_tasks") and self in self.view_model._active_tasks:
                LOGGER.debug("Removing failed download task from active tasks list")
                self.view_model._active_tasks.remove(self)

        except Exception as e:
            # Enhanced error handling for generic exceptions
            LOGGER.exception("Error in async download task")
            LOGGER.exception(traceback.format_exc())

            # Create a detailed error message with stack trace
            error_message = f"Unexpected error: {e!s}"

            # Emit error with detailed message
            self.signals.error.emit(error_message)

            # Update task state
            self.is_complete = True
            self.is_running = False

            # Safe removal from active tasks list
            if hasattr(self.view_model, "_active_tasks") and self in self.view_model._active_tasks:
                LOGGER.debug("Removing failed download task from active tasks list")
                self.view_model._active_tasks.remove(self)

    async def _run_downloads(self) -> dict[datetime, Path | Exception]:
        """Run the download operation asynchronously.

        Returns:
            Dict mapping timestamps to download results
        """
        try:
            # Extract missing timestamps for download
            missing_timestamps = {item.timestamp for item in self.view_model._missing_timestamps}

            # Progress callback that emits signals and handles tracking files in progress
            def progress_callback(current: int, total: int, message: str) -> None:
                # Check if this is a message about starting to download a specific file
                if message.startswith(("Downloading file:", "Processing file:")):
                    try:
                        # Extract timestamp from message if possible
                        timestamp_str = None
                        if "timestamp:" in message:
                            # Try to parse date from the message
                            timestamp_str = message.split("timestamp:")[1].strip().split()[0]
                            dt_format = "%Y-%m-%d_%H:%M:%S"
                            if "_" not in timestamp_str and " " in timestamp_str:
                                dt_format = "%Y-%m-%d %H:%M:%S"
                            timestamp = datetime.strptime(timestamp_str, dt_format)

                            # Add to currently downloading items if not already there
                            if timestamp not in self.view_model._currently_downloading_items:
                                self.view_model._currently_downloading_items.append(timestamp)
                                LOGGER.debug(
                                    "Added timestamp %s to currently downloading items",
                                    timestamp,
                                )
                    except Exception as e:
                        LOGGER.debug(
                            "Failed to parse timestamp from message: %s, error: %s",
                            message,
                            e,
                        )

                # Emit the progress signal
                self.signals.progress.emit(current, total, message)

            # File callback for updating individual items
            def file_callback(path: Path, success: bool) -> None:
                # Find the matching timestamp for this path
                for i, item in enumerate(self.view_model._missing_timestamps):
                    if item.expected_filename in {path.name, path.stem}:
                        if success:
                            item.local_path = str(path)
                            self.view_model._downloaded_success_count += 1
                        else:
                            self.view_model._downloaded_failed_count += 1

                        # Remove timestamp from currently downloading list when file is processed
                        if item.timestamp in self.view_model._currently_downloading_items:
                            self.view_model._currently_downloading_items.remove(item.timestamp)
                            LOGGER.debug(
                                "Removed timestamp %s from currently downloading items",
                                item.timestamp,
                            )

                        self.view_model.download_item_updated.emit(i, item)
                        break

            # Reset currently downloading items before starting
            self.view_model._currently_downloading_items = cast("list[datetime]", [])

            # Run the downloads
            results = await self.view_model._reconcile_manager.fetch_missing_files(
                missing_timestamps=list(missing_timestamps),  # Convert set to list
                satellite=self.view_model._satellite,
                destination_dir=self.view_model.base_directory,
                progress_callback=progress_callback,
                _item_progress_callback=file_callback,
            )

            # Calculate and store download rate for display
            if self.view_model._download_start_time > 0:
                total_time = time.time() - self.view_model._download_start_time
                if total_time > 0 and len(results) > 0:
                    self.view_model._last_download_rate = len(results) / total_time
                    LOGGER.info(
                        "Download rate: %.2f files/sec",
                        self.view_model._last_download_rate,
                    )

            return results

        except asyncio.CancelledError:
            return {}
        except Exception:
            LOGGER.exception("Error in download operation")
            return {}
