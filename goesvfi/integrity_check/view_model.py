"""View model for integrity check functionality.

This module provides the IntegrityCheckViewModel class, which serves as the
intermediary between the UI (View) and the reconciliation logic (Model).
"""

from datetime import datetime, timedelta
from enum import Enum, auto
import os
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

from goesvfi.utils import log

from .reconciler import Reconciler
from .remote_store import RemoteStore, create_remote_store
from .time_index import SatellitePattern

LOGGER = log.get_logger(__name__)


class MissingItemsTreeModel:
    """Stub class for MissingItemsTreeModel.

    This class is referenced by enhanced_gui_tab.py but was not found in the original file.
    This is a placeholder to allow the app to start.
    """

    def __init__(self) -> None:
        pass


class ScanStatus(Enum):
    """Enumeration of scan operation statuses."""

    READY = auto()
    SCANNING = auto()
    DOWNLOADING = auto()
    COMPLETED = auto()
    ERROR = auto()
    CANCELLED = auto()


class MissingTimestamp:
    """Class representing a missing timestamp with additional metadata."""

    def __init__(self, timestamp: datetime, expected_filename: str) -> None:
        self.timestamp = timestamp
        self.expected_filename = expected_filename
        self.is_downloading = False
        self.is_downloaded = False
        self.download_error = ""
        self.remote_url = ""
        self.local_path = ""
        self.satellite = ""  # Satellite identifier (G16, G17, G18, etc.)
        self.source = ""  # Source of the data (AWS S3, NOAA CDN, etc.)

        # Try to extract satellite from filename
        if "G16" in expected_filename:
            self.satellite = "GOES-16"
        elif "G17" in expected_filename:
            self.satellite = "GOES-17"
        elif "G18" in expected_filename:
            self.satellite = "GOES-18"
        else:
            self.satellite = "Unknown"

        # Determine source based on self.remote_url if available
        if self.remote_url and "s3://" in self.remote_url:
            self.source = "AWS S3"
        elif self.remote_url and "cdn.star.nesdis.noaa.gov" in self.remote_url:
            self.source = "NOAA CDN"
        else:
            self.source = "Unknown"

    def as_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "timestamp": self.timestamp,
            "expected_filename": self.expected_filename,
            "is_downloading": self.is_downloading,
            "is_downloaded": self.is_downloaded,
            "download_error": self.download_error,
            "remote_url": self.remote_url,
            "local_path": self.local_path,
            "satellite": self.satellite,
            "source": self.source,
        }


class IntegrityCheckViewModel(QObject):
    """ViewModel for the Integrity Check tab.

    This class manages the state and presentation logic for the Integrity Check feature,
    coordinating between the UI and the underlying business logic in the Reconciler.
    """

    # Signals for view binding
    status_updated = pyqtSignal(str)  # General status updates
    status_type_changed = pyqtSignal(ScanStatus)  # Status type changes
    progress_updated = pyqtSignal(int, int, float)  # current, total, eta_seconds
    missing_items_updated = pyqtSignal(list)  # List of missing timestamps
    scan_completed = pyqtSignal(bool, str)  # success/failure, message
    download_progress_updated = pyqtSignal(int, int)  # current, total
    download_item_updated = pyqtSignal(int, MissingTimestamp)  # index, updated item

    def __init__(self, reconciler: Reconciler | None = None) -> None:
        """Initialize the IntegrityCheckViewModel.

        Args:
            reconciler: Optional Reconciler instance, will create one if not provided
        """
        super().__init__()

        # Initialize state properties
        self._status_message = "Ready to scan"
        self._status = ScanStatus.READY  # pylint: disable=attribute-defined-outside-init
        self._progress_current = 0  # pylint: disable=attribute-defined-outside-init
        self._progress_total = 100  # pylint: disable=attribute-defined-outside-init
        self._progress_eta = 0.0  # pylint: disable=attribute-defined-outside-init

        # Scan parameters
        self._start_date = datetime.now().replace(  # pylint: disable=attribute-defined-outside-init
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=1)
        self._end_date = datetime.now().replace(  # pylint: disable=attribute-defined-outside-init
            hour=23, minute=59, second=59, microsecond=0
        ) - timedelta(days=1)
        self._selected_pattern = SatellitePattern.GENERIC  # pylint: disable=attribute-defined-outside-init
        self._interval_minutes = 0  # 0 = auto detect  # pylint: disable=attribute-defined-outside-init
        self._base_directory = Path(os.path.expanduser("~"))  # pylint: disable=attribute-defined-outside-init
        self._force_rescan = False  # pylint: disable=attribute-defined-outside-init
        self._auto_download = False  # pylint: disable=attribute-defined-outside-init

        # Result data
        self._missing_timestamps: list[MissingTimestamp] = []
        self._last_scan_time: datetime | None = None
        self._total_expected = 0  # pylint: disable=attribute-defined-outside-init
        self._total_found = 0  # pylint: disable=attribute-defined-outside-init
        self._detected_interval = 0  # pylint: disable=attribute-defined-outside-init

        # Remote download settings
        self._remote_base_url = "https://example.com/satellite-images"  # pylint: disable=attribute-defined-outside-init

        # Initialize reconciler
        self._reconciler = reconciler or Reconciler()  # pylint: disable=attribute-defined-outside-init

        # Threading state
        self._cancel_requested = False  # pylint: disable=attribute-defined-outside-init
        self._thread_pool = QThreadPool.globalInstance()  # pylint: disable=attribute-defined-outside-init

    # --- Property accessors ---

    @property
    def status_message(self) -> str:
        """Get the current status message."""
        return self._status_message

    @status_message.setter
    def status_message(self, value: str) -> None:
        """Set the status message and emit signal."""
        if self._status_message != value:
            self._status_message = value  # pylint: disable=attribute-defined-outside-init
            self.status_updated.emit(value)

    @property
    def status(self) -> ScanStatus:
        """Get the current status type."""
        return self._status

    @status.setter
    def status(self, value: ScanStatus) -> None:
        """Set the status type and emit signal."""
        if self._status != value:
            self._status = value  # pylint: disable=attribute-defined-outside-init
            self.status_type_changed.emit(value)

    @property
    def start_date(self) -> datetime:
        """Get the start date for the scan range."""
        return self._start_date

    @start_date.setter
    def start_date(self, value: datetime) -> None:
        """Set the start date."""
        self._start_date = value  # pylint: disable=attribute-defined-outside-init

    @property
    def end_date(self) -> datetime:
        """Get the end date for the scan range."""
        return self._end_date

    @end_date.setter
    def end_date(self, value: datetime) -> None:
        """Set the end date."""
        self._end_date = value  # pylint: disable=attribute-defined-outside-init

    @property
    def selected_pattern(self) -> SatellitePattern:
        """Get the selected satellite pattern."""
        return self._selected_pattern

    @selected_pattern.setter
    def selected_pattern(self, value: SatellitePattern) -> None:
        """Set the selected satellite pattern."""
        self._selected_pattern = value  # pylint: disable=attribute-defined-outside-init

    @property
    def interval_minutes(self) -> int:
        """Get the interval in minutes."""
        return self._interval_minutes

    @interval_minutes.setter
    def interval_minutes(self, value: int) -> None:
        """Set the interval in minutes."""
        self._interval_minutes = value  # pylint: disable=attribute-defined-outside-init

    @property
    def base_directory(self) -> Path:
        """Get the base directory to scan."""
        return self._base_directory

    @base_directory.setter
    def base_directory(self, value: str) -> None:
        """Set the base directory from string path."""
        self._base_directory = Path(value)  # pylint: disable=attribute-defined-outside-init

    @property
    def force_rescan(self) -> bool:
        """Get the force rescan flag."""
        return self._force_rescan

    @force_rescan.setter
    def force_rescan(self, value: bool) -> None:
        """Set the force rescan flag."""
        self._force_rescan = value  # pylint: disable=attribute-defined-outside-init

    @property
    def auto_download(self) -> bool:
        """Get the auto download flag."""
        return self._auto_download

    @auto_download.setter
    def auto_download(self, value: bool) -> None:
        """Set the auto download flag."""
        self._auto_download = value  # pylint: disable=attribute-defined-outside-init

    @property
    def remote_base_url(self) -> str:
        """Get the remote base URL."""
        return self._remote_base_url

    @remote_base_url.setter
    def remote_base_url(self, value: str) -> None:
        """Set the remote base URL."""
        self._remote_base_url = value  # pylint: disable=attribute-defined-outside-init

    @property
    def is_scanning(self) -> bool:
        """Check if a scan is in progress."""
        return self._status == ScanStatus.SCANNING

    @property
    def is_downloading(self) -> bool:
        """Check if downloads are in progress."""
        return self._status == ScanStatus.DOWNLOADING

    @property
    def can_start_scan(self) -> bool:
        """Check if a scan can be started."""
        return (
            self._status not in {ScanStatus.SCANNING, ScanStatus.DOWNLOADING}
            and self._base_directory.exists()
            and self._base_directory.is_dir()
        )

    @property
    def missing_items(self) -> list[MissingTimestamp]:
        """Get the list of missing timestamps."""
        return self._missing_timestamps

    @property
    def has_missing_items(self) -> bool:
        """Check if there are missing timestamps."""
        return len(self._missing_timestamps) > 0

    @property
    def missing_count(self) -> int:
        """Get the count of missing timestamps."""
        return len(self._missing_timestamps)

    @property
    def total_expected(self) -> int:
        """Get the total expected timestamps."""
        return self._total_expected

    @property
    def total_found(self) -> int:
        """Get the total found timestamps."""
        return self._total_found

    @property
    def last_scan_time(self) -> datetime | None:
        """Get the time of the last scan."""
        return self._last_scan_time

    # --- Command methods ---

    def start_scan(self) -> None:
        """Start the scan operation."""
        if not self.can_start_scan:
            LOGGER.warning("Cannot start scan: Operation in progress or directory invalid")
            return

        # Update state
        self.status = ScanStatus.SCANNING
        self.status_message = "Starting scan..."
        self._cancel_requested = False  # pylint: disable=attribute-defined-outside-init
        self._missing_timestamps = []  # pylint: disable=attribute-defined-outside-init
        self.missing_items_updated.emit([])

        # Create a runnable for the scan operation
        scan_task = ScanTask(
            self._reconciler,
            self._start_date,
            self._end_date,
            self._selected_pattern,
            self._base_directory,
            self._interval_minutes,
            self._force_rescan,
        )

        # Connect signals
        scan_task.signals.progress.connect(self._update_scan_progress)
        scan_task.signals.finished.connect(self._handle_scan_completed)
        scan_task.signals.error.connect(self._handle_scan_error)

        # Start the task
        if self._thread_pool is not None:
            self._thread_pool.start(scan_task)
            LOGGER.info("Scan task started")
        else:
            LOGGER.error("Thread pool is None, cannot start scan task")

    def cancel_scan(self) -> None:
        """Cancel the ongoing scan operation."""
        if self._status == ScanStatus.SCANNING:
            self.status_message = "Cancelling scan..."
            self._cancel_requested = True  # pylint: disable=attribute-defined-outside-init
            LOGGER.info("Scan cancellation requested")

    def start_downloads(self, items: list[MissingTimestamp] | None = None) -> None:
        """Start downloading missing files.

        Args:
            items: Optional list of items to download. If ``None`` all missing
                items will be downloaded.
        """
        if self._status == ScanStatus.DOWNLOADING:
            LOGGER.warning("Download already in progress")
            return

        target_items = items or self._missing_timestamps

        if not target_items:
            LOGGER.warning("No missing items to download")
            return

        # Update state
        self.status = ScanStatus.DOWNLOADING
        self.status_message = "Starting downloads..."
        self._cancel_requested = False  # pylint: disable=attribute-defined-outside-init

        try:
            # Create remote store
            remote_store = create_remote_store(self._remote_base_url)

            # Create a download task for each item
            for index, item in enumerate(target_items):
                # Skip already downloaded items
                if item.is_downloaded:
                    continue

                # Create download task
                download_task = DownloadTask(remote_store, item, index, self._base_directory)

                # Connect signals
                download_task.signals.progress.connect(lambda c, t, i=index: self._update_download_progress(i, c, t))
                download_task.signals.finished.connect(
                    lambda success, msg, i=index, item=item: self._handle_download_completed(i, item, success, msg)
                )

                # Start the task
                if self._thread_pool is not None:
                    self._thread_pool.start(download_task)
                else:
                    LOGGER.error("Thread pool is None, cannot start download task")

                # Update item state
                item.is_downloading = True
                self.download_item_updated.emit(index, item)

            LOGGER.info("Started downloads for %s items", len(target_items))

        except Exception as e:
            LOGGER.exception("Error starting downloads: %s", e)
            self.status = ScanStatus.ERROR
            self.status_message = f"Error starting downloads: {e}"

    def cancel_downloads(self) -> None:
        """Cancel ongoing downloads."""
        if self._status == ScanStatus.DOWNLOADING:
            self.status_message = "Cancelling downloads..."
            self._cancel_requested = True  # pylint: disable=attribute-defined-outside-init
            LOGGER.info("Download cancellation requested")

    def clear_cache(self) -> None:
        """Clear the scan result cache."""
        try:
            success = self._reconciler.cache.clear_cache()
            if success:
                self.status_message = "Cache cleared successfully"
            else:
                self.status_message = "Error clearing cache"
        except Exception as e:
            LOGGER.exception("Error clearing cache: %s", e)
            self.status_message = f"Error clearing cache: {e}"

    def get_cache_stats(self) -> dict[str, Any]:
        """Get statistics about the cache."""
        try:
            return self._reconciler.cache.get_cache_stats()
        except Exception as e:
            LOGGER.exception("Error getting cache stats: %s", e)
            return {"error": str(e)}

    # --- Callback handlers ---

    def _update_scan_progress(self, current: int, total: int, eta: float) -> None:
        """Update progress during scan operation."""
        self._progress_current = current  # pylint: disable=attribute-defined-outside-init
        self._progress_total = total  # pylint: disable=attribute-defined-outside-init
        self._progress_eta = eta  # pylint: disable=attribute-defined-outside-init

        # Update UI
        self.status_message = f"Scanning: {current}/{total} complete"
        self.progress_updated.emit(current, total, eta)

    def _handle_scan_completed(self, result: dict[str, Any]) -> None:
        """Handle scan completion."""
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
        self._last_scan_time = datetime.now()  # pylint: disable=attribute-defined-outside-init
        self._total_expected = result.get("total_expected", 0)  # pylint: disable=attribute-defined-outside-init
        self._total_found = result.get("total_found", 0)  # pylint: disable=attribute-defined-outside-init
        self._detected_interval = result.get("interval", 0)  # pylint: disable=attribute-defined-outside-init

        # Convert missing timestamps to objects
        missing_datetimes = result.get("missing", [])
        timestamp_details = result.get("timestamp_details", [])

        self._missing_timestamps = []  # pylint: disable=attribute-defined-outside-init

        # If we have details, use them; otherwise, create from basic timestamps
        if timestamp_details:
            for detail in timestamp_details:
                item = MissingTimestamp(detail["timestamp"], detail.get("expected_filename", "unknown.png"))
                self._missing_timestamps.append(item)
        else:
            for dt in missing_datetimes:
                item = MissingTimestamp(dt, f"{dt.strftime('%Y%m%dT%H%M%S')}.png")
                self._missing_timestamps.append(item)

        # Update UI
        missing_count = len(self._missing_timestamps)
        if missing_count > 0:
            self.status_message = f"Scan complete: {missing_count} missing items found"
            self.missing_items_updated.emit(self._missing_timestamps)

            # Auto-download if enabled
            if self._auto_download and missing_count > 0:
                self.start_downloads()
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

    def _handle_scan_error(self, error_message: str) -> None:
        """Handle scan error."""
        self.status = ScanStatus.ERROR
        self.status_message = f"Scan error: {error_message}"
        self.scan_completed.emit(False, error_message)

    def _update_download_progress(self, item_index: int, _current: int, _total: int) -> None:
        """Update progress during file download."""
        # Update overall progress
        total_items = len(self._missing_timestamps)
        current_item = item_index + 1
        self.download_progress_updated.emit(current_item, total_items)

        # Update status message with overall progress
        self.status_message = f"Downloading: {current_item}/{total_items} files"

    def _handle_download_completed(self, item_index: int, item: MissingTimestamp, success: bool, message: str) -> None:
        """Handle completion of a file download."""
        # Update item state
        item.is_downloading = False

        if success:
            item.is_downloaded = True
            item.download_error = ""
        else:
            item.download_error = message

        # Emit signal for UI update
        self.download_item_updated.emit(item_index, item)

        # Check if all downloads are complete
        all_complete = True
        for item in self._missing_timestamps:
            if item.is_downloading:
                all_complete = False
                break

        if all_complete:
            # Count successful downloads
            success_count = sum(1 for item in self._missing_timestamps if item.is_downloaded)

            self.status = ScanStatus.COMPLETED
            self.status_message = f"Downloads complete: {success_count}/{len(self._missing_timestamps)} successful"  # pylint: disable=attribute-defined-outside-init

            # Clear cancel flag
            self._cancel_requested = False  # pylint: disable=attribute-defined-outside-init


class TaskSignals(QObject):
    """Signals for worker threads."""

    progress = pyqtSignal(int, int, float)  # current, total, eta_seconds
    error = pyqtSignal(str)
    finished = pyqtSignal(dict)  # Result dictionary


class ScanTask(QRunnable):
    """Background task for directory scanning."""

    def __init__(
        self,
        reconciler: Reconciler,
        start_date: datetime,
        end_date: datetime,
        satellite_pattern: SatellitePattern,
        base_directory: Path,
        interval_minutes: int = 0,
        force_rescan: bool = False,
    ) -> None:
        """Initialize the scan task.

        Args:
            reconciler: Reconciler instance to use
            start_date: Start date for the scan
            end_date: End date for the scan
            satellite_pattern: Satellite pattern to match
            base_directory: Directory to scan
            interval_minutes: Time interval in minutes (0 = auto-detect)
            force_rescan: Whether to force a rescan
        """
        super().__init__()

        self.reconciler = reconciler
        self.start_date = start_date
        self.end_date = end_date
        self.satellite_pattern = satellite_pattern
        self.base_directory = base_directory
        self.interval_minutes = interval_minutes
        self.force_rescan = force_rescan

        self.signals = TaskSignals()
        self._cancel_requested = False  # pylint: disable=attribute-defined-outside-init

    def run(self) -> None:
        """Execute the scan task."""
        try:
            # Run the scan
            result = self.reconciler.scan_date_range(
                self.start_date,
                self.end_date,
                self.satellite_pattern,
                self.base_directory,
                self.interval_minutes,
                progress_callback=self._progress_callback,
                should_cancel=self._should_cancel,
                force_rescan=self.force_rescan,
            )

            # Emit result
            self.signals.finished.emit(result)

        except Exception as e:
            LOGGER.error("Error in scan task: %s", e, exc_info=True)
            self.signals.error.emit(str(e))

    def _progress_callback(self, current: int, total: int, eta: float = 0.0) -> None:
        """Forward progress updates to signals."""
        self.signals.progress.emit(current, total, eta)

    def _should_cancel(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancel_requested

    def cancel(self) -> None:
        """Request cancellation of the task."""
        self._cancel_requested = True  # pylint: disable=attribute-defined-outside-init


class DownloadSignals(QObject):
    """Signals for download worker threads."""

    progress = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal(bool, str)  # success, message


class DownloadTask(QRunnable):
    """Background task for downloading a missing file."""

    def __init__(
        self,
        remote_store: RemoteStore,
        item: MissingTimestamp,
        item_index: int,
        destination_dir: Path,
    ) -> None:
        """Initialize the download task.

        Args:
            remote_store: RemoteStore instance to use
            item: MissingTimestamp to download
            item_index: Index of the item in the list
            destination_dir: Base directory to download to
        """
        super().__init__()

        self.remote_store = remote_store
        self.item = item
        self.item_index = item_index
        self.destination_dir = destination_dir

        self.signals = DownloadSignals()
        self._cancel_requested = False  # pylint: disable=attribute-defined-outside-init

    def run(self) -> None:
        """Execute the download task."""
        try:
            # Construct URL
            url = self.remote_store.construct_url(self.item.timestamp, SatellitePattern.GENERIC)
            self.item.remote_url = url

            # Construct local path
            timestamp_dir = self.destination_dir / "downloads"
            os.makedirs(timestamp_dir, exist_ok=True)
            local_path = timestamp_dir / self.item.expected_filename
            self.item.local_path = str(local_path)

            # Check if file exists remotely
            if not self.remote_store.check_exists(url):
                self.signals.finished.emit(False, f"File not found at {url}")
                return

            # Download the file
            success = self.remote_store.download_file(
                url,
                local_path,
                progress_callback=self._progress_callback,
                should_cancel=self._should_cancel,
            )

            if success:
                self.signals.finished.emit(True, f"Downloaded to {local_path}")
            else:
                self.signals.finished.emit(False, "Download failed")

        except Exception as e:
            LOGGER.error("Error in download task: %s", e, exc_info=True)
            self.signals.finished.emit(False, str(e))

    def _progress_callback(self, current: int, total: int, _eta: float = 0.0) -> None:
        """Forward progress updates to signals."""
        self.signals.progress.emit(current, total)

    def _should_cancel(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancel_requested

    def cancel(self) -> None:
        """Request cancellation of the task."""
        self._cancel_requested = True  # pylint: disable=attribute-defined-outside-init
