"""Enhanced ViewModel for the Integrity Check tab with CDN/S3 hybrid fetching.

This module provides the EnhancedIntegrityCheckViewModel class, which extends
the base IntegrityCheckViewModel with support for hybrid CDN/S3 fetching of
GOES-16 and GOES-18 Band 13 imagery.
"""

import asyncio
import os
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Set, Any, Callable, cast, Union, Tuple
from enum import Enum, auto
import traceback

from PyQt6.QtCore import QObject, pyqtSignal, QThread, QThreadPool, QRunnable, QMetaObject, Qt

from goesvfi.utils import log
from goesvfi.utils import config
from .reconciler import Reconciler
from .time_index import TimeIndex, SatellitePattern
from .cache_db import CacheDB
from .reconcile_manager import ReconcileManager
from .remote.cdn_store import CDNStore
from .remote.s3_store import S3Store
from .view_model import IntegrityCheckViewModel, ScanStatus, MissingTimestamp

LOGGER = log.get_logger(__name__)


class EnhancedMissingTimestamp(MissingTimestamp):
    """Enhanced missing timestamp class with satellite and source information."""
    
    def __init__(self, timestamp: datetime, expected_filename: str):
        super().__init__(timestamp, expected_filename)
        self.satellite = None
        self.source = ""  # "cdn" or "s3"
        self.progress = 0  # Download progress (0-100)
    
    def as_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = super().as_dict()
        result.update({
            'satellite': self.satellite,
            'source': self.source,
            'progress': self.progress,
        })
        return result


class FetchSource(Enum):
    """Enumeration of data source types."""
    AUTO = auto()    # Automatic selection based on date
    CDN = auto()     # Force CDN
    S3 = auto()      # Force S3
    LOCAL = auto()   # Local files only


class EnhancedIntegrityCheckViewModel(IntegrityCheckViewModel):
    """
    Enhanced ViewModel for the Integrity Check tab with support for hybrid CDN/S3 fetching.
    
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
        base_reconciler: Optional[Reconciler] = None,
        cache_db: Optional[CacheDB] = None,
        cdn_store: Optional[CDNStore] = None,
        s3_store: Optional[S3Store] = None,
    ):
        """
        Initialize the EnhancedIntegrityCheckViewModel.
        
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
        self._max_concurrent_downloads = 5
        self._cdn_resolution = TimeIndex.CDN_RES  # Default resolution
        self._aws_profile = None  # Use default credentials
        self._s3_region = "us-east-1"
        
        # Initialize CacheDB and stores
        self._cache_db = cache_db or CacheDB()
        self._cdn_store = cdn_store or CDNStore(resolution=self._cdn_resolution)
        self._s3_store = s3_store or S3Store(aws_profile=self._aws_profile, aws_region=self._s3_region)
        
        # Create the ReconcileManager
        self._reconcile_manager = ReconcileManager(
            cache_db=self._cache_db,
            base_dir=self._base_directory,
            cdn_store=self._cdn_store,
            s3_store=self._s3_store,
            cdn_resolution=self._cdn_resolution,
            max_concurrency=self._max_concurrent_downloads
        )
        
        # Result data for enhanced functionality
        self._missing_timestamps = []  # Override with EnhancedMissingTimestamp objects
        self._downloaded_count = 0
        self._failed_count = 0
        
        # Initialize async state
        self._async_task = None
        self._scan_task_future = None
        self._download_task_future = None
        
        # Setup disk space check timer - disabled for now due to blocking issues
        self._disk_space_timer = QThread()
        self._disk_space_timer.setObjectName("DiskSpaceCheckerThread")
        # self._disk_space_timer.started.connect(self._check_disk_space_loop)
        # self._disk_space_timer.start()
        # Instead, just emit a single disk space update
        try:
            used_gb, total_gb = self.get_disk_space_info()
            self.disk_space_updated.emit(used_gb, total_gb)
        except Exception as e:
            LOGGER.error(f"Error in initial disk space check: {e}")
    
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
                max_concurrency=self._max_concurrent_downloads
            )
    
    @property
    def aws_profile(self) -> Optional[str]:
        """Get the AWS profile name."""
        return self._aws_profile
    
    @aws_profile.setter
    def aws_profile(self, value: Optional[str]) -> None:
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
                max_concurrency=self._max_concurrent_downloads
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
                max_concurrency=value
            )
    
    # --- Enhanced command methods ---
    
    def start_enhanced_scan(self) -> None:
        """Start the enhanced scan operation with async support."""
        if not self.can_start_scan:
            LOGGER.warning("Cannot start scan: Operation in progress or directory invalid")
            return
        
        # Update state
        self.status = ScanStatus.SCANNING
        self.status_message = "Starting scan..."
        self._cancel_requested = False
        self._missing_timestamps = []
        self.missing_items_updated.emit([])
        
        # Create AsyncScanTask
        scan_task = AsyncScanTask(self)
        
        # Start the task
        self._thread_pool.start(scan_task)
        LOGGER.info("Enhanced scan task started")
    
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
        
        # Create AsyncDownloadTask
        download_task = AsyncDownloadTask(self)
        
        # Start the task
        self._thread_pool.start(download_task)
        LOGGER.info(f"Enhanced download task started for {len(self._missing_timestamps)} items")
    
    def get_disk_space_info(self) -> Tuple[float, float]:
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
            total_gb = total / (1024 ** 3)
            used_gb = used / (1024 ** 3)
            
            return used_gb, total_gb
        except Exception as e:
            LOGGER.error(f"Error getting disk space info: {e}")
            return 0.0, 0.0
    
    def reset_database(self) -> None:
        """Reset the database and clear all cached data."""
        try:
            self._cache_db.reset_database()
            self.status_message = "Database reset successfully"
        except Exception as e:
            LOGGER.error(f"Error resetting database: {e}")
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
            except Exception as e:
                LOGGER.error(f"Error in disk space check: {e}")
            
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
    
    def _handle_enhanced_scan_completed(self, result: Dict[str, Any]) -> None:
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
            item.satellite = self._satellite
            
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
            f"Found {missing_count} missing out of {self._total_expected} expected timestamps"
        )
    
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
            item.progress = progress
            self.download_item_progress.emit(index, progress)
    
    def _handle_enhanced_download_completed(self, results: Dict[datetime, Union[Path, Exception]]) -> None:
        """Handle completion of the enhanced download operation."""
        # Update item states based on results
        for i, item in enumerate(self._missing_timestamps):
            if item.timestamp in results:
                result = results[item.timestamp]
                
                # Update item state
                item.is_downloading = False
                
                if isinstance(result, Path):
                    item.is_downloaded = True
                    item.download_error = ""
                    item.local_path = str(result)
                    self._downloaded_count += 1
                else:
                    item.download_error = str(result)
                    self._failed_count += 1
                
                # Emit signal for UI update
                self.download_item_updated.emit(i, item)
        
        # Update status
        self.status = ScanStatus.COMPLETED
        self.status_message = (
            f"Downloads complete: {self._downloaded_count} successful, "
            f"{self._failed_count} failed"
        )
        
        # Clear cancel flag
        self._cancel_requested = False
    
    # --- Cleanup ---
    
    def cleanup(self) -> None:
        """Clean up resources."""
        # Set stop flag for disk space check
        if hasattr(self, '_stop_disk_space_check'):
            self._stop_disk_space_check = True
            
        # Stop disk space check thread
        if hasattr(self, '_disk_space_timer'):
            try:
                if self._disk_space_timer.isRunning():
                    LOGGER.debug("Stopping disk space timer thread")
                    self._disk_space_timer.terminate()
                    timeout_ms = 1000  # 1 second timeout
                    if not self._disk_space_timer.wait(timeout_ms):
                        LOGGER.warning("Disk space timer thread did not stop in time")
            except Exception as e:
                LOGGER.error(f"Error stopping disk space timer: {e}")
        
        # Close database connection
        if hasattr(self, '_cache_db'):
            try:
                LOGGER.debug("Closing cache database")
                self._cache_db.close()
            except Exception as e:
                LOGGER.error(f"Error closing cache database: {e}")
        
        # Close base reconciler
        if hasattr(self, '_reconciler'):
            try:
                LOGGER.debug("Closing reconciler")
                self._reconciler.close()
            except Exception as e:
                LOGGER.error(f"Error closing reconciler: {e}")
                
        LOGGER.info("Cleanup completed")


class AsyncTaskSignals(QObject):
    """Signals for async worker threads."""
    progress = pyqtSignal(int, int, str)  # current, total, message
    error = pyqtSignal(str)
    scan_finished = pyqtSignal(dict)  # Scan result dictionary
    download_finished = pyqtSignal(dict)  # Download results dictionary


class AsyncScanTask(QRunnable):
    """Async task for enhanced directory scanning."""
    
    def __init__(self, view_model: EnhancedIntegrityCheckViewModel):
        """
        Initialize the scan task.
        
        Args:
            view_model: EnhancedIntegrityCheckViewModel instance
        """
        super().__init__()
        
        self.view_model = view_model
        self.signals = AsyncTaskSignals()
        
        # Connect signals to view model
        self.signals.progress.connect(view_model._handle_enhanced_scan_progress)
        self.signals.scan_finished.connect(view_model._handle_enhanced_scan_completed)
        self.signals.error.connect(view_model._handle_scan_error)
    
    def run(self):
        """Execute the scan task."""
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
            
        except Exception as e:
            LOGGER.error(f"Error in async scan task: {e}")
            LOGGER.error(traceback.format_exc())
            self.signals.error.emit(str(e))
    
    async def _run_scan(self) -> Dict[str, Any]:
        """
        Run the scan operation asynchronously.
        
        Returns:
            Dict with scan results
        """
        try:
            # Progress callback that emits signals
            def progress_callback(current, total, message):
                self.signals.progress.emit(current, total, message)
            
            # Run the scan
            existing, missing = await self.view_model._reconcile_manager.scan_directory(
                directory=self.view_model._base_directory,
                satellite=self.view_model._satellite,
                start_time=self.view_model._start_date,
                end_time=self.view_model._end_date,
                interval_minutes=self.view_model._interval_minutes,
                progress_callback=progress_callback
            )
            
            return {
                "status": "completed",
                "existing": existing,
                "missing": missing,
                "total": len(existing) + len(missing)
            }
            
        except asyncio.CancelledError:
            return {
                "status": "cancelled"
            }
        except Exception as e:
            LOGGER.error(f"Error in scan operation: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


class AsyncDownloadTask(QRunnable):
    """Async task for enhanced file downloading."""
    
    def __init__(self, view_model: EnhancedIntegrityCheckViewModel):
        """
        Initialize the download task.
        
        Args:
            view_model: EnhancedIntegrityCheckViewModel instance
        """
        super().__init__()
        
        self.view_model = view_model
        self.signals = AsyncTaskSignals()
        
        # Connect signals to view model
        self.signals.progress.connect(view_model._handle_enhanced_download_progress)
        self.signals.download_finished.connect(view_model._handle_enhanced_download_completed)
        self.signals.error.connect(view_model._handle_scan_error)
    
    def run(self):
        """Execute the download task."""
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
            
        except Exception as e:
            LOGGER.error(f"Error in async download task: {e}")
            LOGGER.error(traceback.format_exc())
            self.signals.error.emit(str(e))
    
    async def _run_downloads(self) -> Dict[datetime, Union[Path, Exception]]:
        """
        Run the download operation asynchronously.
        
        Returns:
            Dict mapping timestamps to download results
        """
        try:
            # Extract missing timestamps for download
            missing_timestamps = {item.timestamp for item in self.view_model._missing_timestamps}
            
            # Progress callback that emits signals
            def progress_callback(current, total, message):
                self.signals.progress.emit(current, total, message)
            
            # File callback for updating individual items
            def file_callback(path, success):
                # Find the matching timestamp for this path
                for i, item in enumerate(self.view_model._missing_timestamps):
                    if path.name == item.expected_filename or path.stem == item.expected_filename:
                        if success:
                            item.local_path = str(path)
                        self.view_model.download_item_updated.emit(i, item)
                        break
            
            # Item progress callback for updating download progress
            def item_progress_callback(index, progress):
                self.view_model._handle_download_item_progress(index, progress)
            
            # Run the downloads
            results = await self.view_model._reconcile_manager.fetch_missing_files(
                missing_timestamps=missing_timestamps,
                satellite=self.view_model._satellite,
                progress_callback=progress_callback,
                file_callback=file_callback,
                error_callback=lambda path, error: None  # Handled via results
            )
            
            return results
            
        except asyncio.CancelledError:
            return {}
        except Exception as e:
            LOGGER.error(f"Error in download operation: {e}")
            return {}