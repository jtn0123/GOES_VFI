"""Background task workers for integrity check operations.

This module provides QRunnable implementations for running integrity check
operations in background threads, ensuring the UI remains responsive.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Set

from PyQt6.QtCore import QObject, pyqtSignal, QRunnable

from goesvfi.utils import log
from .reconciler import Reconciler
from .time_index import SatellitePattern
from .remote_store import RemoteStore

LOGGER = log.get_logger(__name__)

# Type hint for callbacks
ProgressCallback = Callable[[int, int, float], None]
CancelCallback = Callable[[], bool]


class TaskSignals(QObject):
    """Common signals for worker tasks."""
    
    progress = pyqtSignal(int, int, float)  # current, total, eta
    error = pyqtSignal(str)
    finished = pyqtSignal(dict)  # Result dictionary


class ScanTask(QRunnable):
    """Background task for directory scanning."""
    
    def __init__(self, 
                reconciler: Reconciler,
                start_date: datetime,
                end_date: datetime,
                satellite_pattern: SatellitePattern,
                base_directory: Path,
                interval_minutes: int = 0,
                force_rescan: bool = False):
        """
        Initialize the scan task.
        
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
        self._cancel_requested = False
    
    def run(self):
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
                force_rescan=self.force_rescan
            )
            
            # Emit result
            self.signals.finished.emit(result)
            
        except Exception as e:
            LOGGER.error(f"Error in scan task: {e}", exc_info=True)
            self.signals.error.emit(str(e))
    
    def _progress_callback(self, current: int, total: int, eta: float = 0.0) -> None:
        """Forward progress updates to signals."""
        self.signals.progress.emit(current, total, eta)
    
    def _should_cancel(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancel_requested
    
    def cancel(self) -> None:
        """Request cancellation of the task."""
        self._cancel_requested = True


class DownloadSignals(QObject):
    """Signals for download worker threads."""
    
    progress = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal(bool, str)  # success, message


class DownloadTask(QRunnable):
    """Background task for downloading a missing file."""
    
    def __init__(self,
                remote_store: RemoteStore,
                timestamp: datetime,
                expected_filename: str,
                destination_dir: Path,
                satellite_pattern: SatellitePattern = SatellitePattern.GENERIC):
        """
        Initialize the download task.
        
        Args:
            remote_store: RemoteStore instance to use
            timestamp: Datetime to download
            expected_filename: Expected filename for the download
            destination_dir: Directory to download to
            satellite_pattern: Satellite pattern to use for URL construction
        """
        super().__init__()
        
        self.remote_store = remote_store
        self.timestamp = timestamp
        self.expected_filename = expected_filename
        self.destination_dir = destination_dir
        self.satellite_pattern = satellite_pattern
        
        self.signals = DownloadSignals()
        self._cancel_requested = False
    
    def run(self):
        """Execute the download task."""
        try:
            # Construct URL
            url = self.remote_store.construct_url(self.timestamp, self.satellite_pattern)
            
            # Construct local path
            timestamp_str = self.timestamp.strftime("%Y%m%d")
            timestamp_dir = self.destination_dir / "downloads" / timestamp_str
            timestamp_dir.mkdir(parents=True, exist_ok=True)
            local_path = timestamp_dir / self.expected_filename
            
            # Check if file exists locally
            if local_path.exists():
                LOGGER.info(f"File already exists locally: {local_path}")
                self.signals.finished.emit(True, f"File already exists: {local_path}")
                return
            
            # Check if file exists remotely
            if not self.remote_store.check_file_exists(url):
                LOGGER.warning(f"File not found at remote URL: {url}")
                self.signals.finished.emit(False, f"File not found at {url}")
                return
            
            # Download the file
            success = self.remote_store.download_file(
                url,
                local_path,
                progress_callback=self._progress_callback,
                should_cancel=self._should_cancel
            )
            
            if success:
                LOGGER.info(f"Successfully downloaded {url} to {local_path}")
                self.signals.finished.emit(True, f"Downloaded to {local_path}")
            else:
                LOGGER.error(f"Failed to download {url}")
                self.signals.finished.emit(False, "Download failed")
            
        except Exception as e:
            LOGGER.error(f"Error in download task: {e}", exc_info=True)
            self.signals.finished.emit(False, str(e))
    
    def _progress_callback(self, current: int, total: int, eta: float = 0.0) -> None:
        """Forward progress updates to signals."""
        self.signals.progress.emit(current, total)
    
    def _should_cancel(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancel_requested
    
    def cancel(self) -> None:
        """Request cancellation of the task."""
        self._cancel_requested = True


class BatchDownloadSignals(QObject):
    """Signals for batch download tasks."""
    
    item_progress = pyqtSignal(int, int, int)  # item_index, current, total
    item_finished = pyqtSignal(int, bool, str)  # item_index, success, message
    all_finished = pyqtSignal(int, int)  # success_count, total_count


class BatchDownloadTask(QRunnable):
    """Background task for downloading multiple missing files."""
    
    def __init__(self,
                remote_store: RemoteStore,
                items: List[Dict[str, Any]],
                destination_dir: Path,
                max_concurrent: int = 3):
        """
        Initialize the batch download task.
        
        Args:
            remote_store: RemoteStore instance to use
            items: List of item dictionaries (timestamp, expected_filename)
            destination_dir: Directory to download to
            max_concurrent: Maximum number of concurrent downloads
        """
        super().__init__()
        
        self.remote_store = remote_store
        self.items = items
        self.destination_dir = destination_dir
        self.max_concurrent = max_concurrent
        
        self.signals = BatchDownloadSignals()
        self._cancel_requested = False
    
    def run(self):
        """Execute the batch download task."""
        try:
            success_count = 0
            total_count = len(self.items)
            
            # Process items in batches of max_concurrent
            for i in range(0, total_count, self.max_concurrent):
                batch = self.items[i:i + self.max_concurrent]
                threads = []
                
                # Start downloads for this batch
                for j, item in enumerate(batch):
                    item_index = i + j
                    
                    # Check for cancellation
                    if self._cancel_requested:
                        LOGGER.info("Batch download cancelled")
                        break
                    
                    timestamp = item['timestamp']
                    expected_filename = item['expected_filename']
                    satellite_pattern = item.get('satellite_pattern', SatellitePattern.GENERIC)
                    
                    # Construct URL
                    url = self.remote_store.construct_url(timestamp, satellite_pattern)
                    
                    # Construct local path
                    timestamp_str = timestamp.strftime("%Y%m%d")
                    timestamp_dir = self.destination_dir / "downloads" / timestamp_str
                    timestamp_dir.mkdir(parents=True, exist_ok=True)
                    local_path = timestamp_dir / expected_filename
                    
                    # Check if file exists locally
                    if local_path.exists():
                        LOGGER.info(f"File already exists locally: {local_path}")
                        self.signals.item_finished.emit(
                            item_index, True, f"File already exists: {local_path}"
                        )
                        success_count += 1
                        continue
                    
                    # Check if file exists remotely
                    if not self.remote_store.check_file_exists(url):
                        LOGGER.warning(f"File not found at remote URL: {url}")
                        self.signals.item_finished.emit(
                            item_index, False, f"File not found at {url}"
                        )
                        continue
                    
                    # Download the file
                    def progress_callback(current, total, item_idx=item_index):
                        self.signals.item_progress.emit(item_idx, current, total)
                    
                    success = self.remote_store.download_file(
                        url,
                        local_path,
                        progress_callback=progress_callback,
                        should_cancel=self._should_cancel
                    )
                    
                    if success:
                        LOGGER.info(f"Successfully downloaded {url} to {local_path}")
                        self.signals.item_finished.emit(
                            item_index, True, f"Downloaded to {local_path}"
                        )
                        success_count += 1
                    else:
                        LOGGER.error(f"Failed to download {url}")
                        self.signals.item_finished.emit(
                            item_index, False, "Download failed"
                        )
                
                # Check for cancellation after each batch
                if self._cancel_requested:
                    break
            
            # Emit final completion signal
            self.signals.all_finished.emit(success_count, total_count)
            
        except Exception as e:
            LOGGER.error(f"Error in batch download task: {e}", exc_info=True)
            self.signals.all_finished.emit(success_count, total_count)
    
    def _should_cancel(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancel_requested
    
    def cancel(self) -> None:
        """Request cancellation of the task."""
        self._cancel_requested = True