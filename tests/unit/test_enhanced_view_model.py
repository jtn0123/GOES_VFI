"""Unit tests for the integrity_check enhanced view model functionality."""

import unittest
import tempfile
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock, call

from PyQt6.QtCore import QObject, pyqtSignal, QThreadPool

from goesvfi.integrity_check.time_index import SatellitePattern, TimeIndex
from goesvfi.integrity_check.cache_db import CacheDB
from goesvfi.integrity_check.remote.cdn_store import CDNStore
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.view_model import ScanStatus, MissingTimestamp
from goesvfi.integrity_check.enhanced_view_model import (
    EnhancedIntegrityCheckViewModel, EnhancedMissingTimestamp, FetchSource,
    AsyncTaskSignals, AsyncScanTask, AsyncDownloadTask
)


class TestEnhancedIntegrityCheckViewModel(unittest.TestCase):
    """Test cases for the EnhancedIntegrityCheckViewModel class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        
        # Mock dependencies
        self.mock_cache_db = MagicMock(spec=CacheDB)
        self.mock_cdn_store = MagicMock(spec=CDNStore)
        self.mock_s3_store = MagicMock(spec=S3Store)
        self.mock_reconcile_manager = MagicMock()
        
        # Create test view model
        self.view_model = EnhancedIntegrityCheckViewModel(
            cache_db=self.mock_cache_db,
            cdn_store=self.mock_cdn_store,
            s3_store=self.mock_s3_store,
        )
        
        # Replace ReconcileManager with mock
        self.view_model._reconcile_manager = self.mock_reconcile_manager
        
        # Mock thread pool
        self.mock_thread_pool = MagicMock(spec=QThreadPool)
        self.view_model._thread_pool = self.mock_thread_pool
        
        # Mock disk space timer
        self.mock_timer = MagicMock()
        self.view_model._disk_space_timer = self.mock_timer
        
        # Dates for testing
        self.start_date = datetime(2023, 6, 15, 0, 0, 0)
        self.end_date = datetime(2023, 6, 15, 1, 0, 0)

    def tearDown(self):
        """Tear down test fixtures."""
        # Clean up temporary directory
        self.temp_dir.cleanup()

    def test_init_default_values(self):
        """Test initialization with default values."""
        # Create a fresh view model with default values
        vm = EnhancedIntegrityCheckViewModel()
        
        # Verify default values
        self.assertEqual(vm._satellite, SatellitePattern.GOES_18)
        self.assertEqual(vm._fetch_source, FetchSource.AUTO)
        self.assertEqual(vm._max_concurrent_downloads, 5)
        self.assertEqual(vm._cdn_resolution, TimeIndex.CDN_RES)
        self.assertIsNone(vm._aws_profile)
        self.assertEqual(vm._s3_region, "us-east-1")
        self.assertEqual(vm._missing_timestamps, [])
        self.assertEqual(vm._downloaded_count, 0)
        self.assertEqual(vm._failed_count, 0)

    def test_property_getters_and_setters(self):
        """Test property getters and setters."""
        # Test satellite property
        self.assertEqual(self.view_model.satellite, SatellitePattern.GOES_18)  # Default
        
        # Mock signal
        self.view_model.satellite_changed = MagicMock()
        
        # Set satellite
        self.view_model.satellite = SatellitePattern.GOES_16
        self.assertEqual(self.view_model.satellite, SatellitePattern.GOES_16)
        self.view_model.satellite_changed.emit.assert_called_once_with(SatellitePattern.GOES_16)
        
        # Setting same value should not emit signal
        self.view_model.satellite_changed.reset_mock()
        self.view_model.satellite = SatellitePattern.GOES_16
        self.view_model.satellite_changed.emit.assert_not_called()
        
        # Test fetch_source property
        self.assertEqual(self.view_model.fetch_source, FetchSource.AUTO)  # Default
        
        # Mock signal
        self.view_model.fetch_source_changed = MagicMock()
        
        # Set fetch_source
        self.view_model.fetch_source = FetchSource.CDN
        self.assertEqual(self.view_model.fetch_source, FetchSource.CDN)
        self.view_model.fetch_source_changed.emit.assert_called_once_with(FetchSource.CDN)
        
        # Setting same value should not emit signal
        self.view_model.fetch_source_changed.reset_mock()
        self.view_model.fetch_source = FetchSource.CDN
        self.view_model.fetch_source_changed.emit.assert_not_called()
        
        # Test cdn_resolution property
        self.assertEqual(self.view_model.cdn_resolution, TimeIndex.CDN_RES)  # Default
        
        # Set cdn_resolution
        self.view_model.cdn_resolution = "250m"
        self.assertEqual(self.view_model.cdn_resolution, "250m")
        
        # Test aws_profile property
        self.assertIsNone(self.view_model.aws_profile)  # Default
        
        # Set aws_profile
        self.view_model.aws_profile = "test-profile"
        self.assertEqual(self.view_model.aws_profile, "test-profile")
        
        # Test max_concurrent_downloads property
        self.assertEqual(self.view_model.max_concurrent_downloads, 5)  # Default
        
        # Set max_concurrent_downloads
        self.view_model.max_concurrent_downloads = 10
        self.assertEqual(self.view_model.max_concurrent_downloads, 10)

    def test_get_disk_space_info(self):
        """Test getting disk space information."""
        # Mock os.statvfs
        mock_statvfs = MagicMock()
        mock_statvfs.f_blocks = 1000000
        mock_statvfs.f_frsize = 4096
        mock_statvfs.f_bavail = 500000
        
        with patch('os.statvfs', return_value=mock_statvfs):
            used_gb, total_gb = self.view_model.get_disk_space_info()
            
            # Calculate expected values
            total = 1000000 * 4096
            free = 500000 * 4096
            used = total - free
            expected_total_gb = total / (1024 ** 3)
            expected_used_gb = used / (1024 ** 3)
            
            self.assertAlmostEqual(used_gb, expected_used_gb, places=2)
            self.assertAlmostEqual(total_gb, expected_total_gb, places=2)
        
        # Test with non-existent directory
        with patch('os.statvfs', side_effect=FileNotFoundError):
            used_gb, total_gb = self.view_model.get_disk_space_info()
            self.assertEqual(used_gb, 0.0)
            self.assertEqual(total_gb, 0.0)

    def test_reset_database(self):
        """Test resetting the database."""
        self.view_model.reset_database()
        self.mock_cache_db.reset_database.assert_called_once()
        
        # Test with error
        self.mock_cache_db.reset_database.side_effect = Exception("Test error")
        self.view_model.status_message = "Previous status"
        self.view_model.reset_database()
        self.assertTrue(self.view_model.status_message.startswith("Error resetting database"))

    def test_handle_enhanced_scan_progress(self):
        """Test handling enhanced scan progress updates."""
        # Mock signals
        self.view_model.status_updated = MagicMock()
        self.view_model.progress_updated = MagicMock()
        
        # Test progress update
        self.view_model._handle_enhanced_scan_progress(50, 100, "Testing progress")
        
        # Verify
        self.assertEqual(self.view_model._progress_current, 50)
        self.assertEqual(self.view_model._progress_total, 100)
        self.view_model.status_updated.emit.assert_called_once_with("Testing progress")
        self.view_model.progress_updated.emit.assert_called_once_with(50, 100, 0.0)

    def test_handle_enhanced_scan_completed(self):
        """Test handling enhanced scan completion."""
        # Mock signals
        self.view_model.status_updated = MagicMock()
        self.view_model.status_type_changed = MagicMock()
        self.view_model.missing_items_updated = MagicMock()
        self.view_model.scan_completed = MagicMock()
        
        # Test cancelled
        self.view_model._handle_enhanced_scan_completed({"status": "cancelled"})
        self.assertEqual(self.view_model.status, ScanStatus.CANCELLED)
        self.view_model.scan_completed.emit.assert_called_once_with(False, "Scan was cancelled")
        
        # Reset mocks
        self.view_model.status_updated.reset_mock()
        self.view_model.status_type_changed.reset_mock()
        self.view_model.missing_items_updated.reset_mock()
        self.view_model.scan_completed.reset_mock()
        
        # Test error
        self.view_model._handle_enhanced_scan_completed({"status": "error", "error": "Test error"})
        self.assertEqual(self.view_model.status, ScanStatus.ERROR)
        self.view_model.scan_completed.emit.assert_called_once_with(False, "Test error")
        
        # Reset mocks
        self.view_model.status_updated.reset_mock()
        self.view_model.status_type_changed.reset_mock()
        self.view_model.missing_items_updated.reset_mock()
        self.view_model.scan_completed.reset_mock()
        
        # Test success with missing items
        now = datetime.now()
        existing = {now - timedelta(minutes=1), now - timedelta(minutes=3)}
        missing = {now - timedelta(minutes=2), now - timedelta(minutes=4)}
        
        self.view_model._handle_enhanced_scan_completed({
            "status": "completed",
            "existing": existing,
            "missing": missing
        })
        
        # Verify
        self.assertEqual(self.view_model._last_scan_time.date(), datetime.now().date())
        self.assertEqual(self.view_model._total_expected, 4)  # 2 existing + 2 missing
        self.assertEqual(self.view_model._total_found, 2)
        self.assertEqual(len(self.view_model._missing_timestamps), 2)
        self.view_model.missing_items_updated.emit.assert_called_once()
        self.assertEqual(self.view_model.status, ScanStatus.COMPLETED)
        self.view_model.scan_completed.emit.assert_called_once()
        
        # Test success with no missing items
        # Reset mocks
        self.view_model.status_updated.reset_mock()
        self.view_model.status_type_changed.reset_mock()
        self.view_model.missing_items_updated.reset_mock()
        self.view_model.scan_completed.reset_mock()
        
        self.view_model._handle_enhanced_scan_completed({
            "status": "completed",
            "existing": existing,
            "missing": set()  # No missing items
        })
        
        # Verify
        self.assertEqual(len(self.view_model._missing_timestamps), 0)
        self.view_model.missing_items_updated.emit.assert_called_once_with([])
        self.assertEqual(self.view_model.status, ScanStatus.COMPLETED)
        self.view_model.scan_completed.emit.assert_called_once()

    def test_handle_enhanced_download_progress(self):
        """Test handling enhanced download progress updates."""
        # Mock signals
        self.view_model.status_updated = MagicMock()
        self.view_model.download_progress_updated = MagicMock()
        
        # Test progress update
        self.view_model._handle_enhanced_download_progress(3, 10, "Downloading: 3/10 files")
        
        # Verify
        self.assertEqual(self.view_model._progress_current, 3)
        self.assertEqual(self.view_model._progress_total, 10)
        self.view_model.status_updated.emit.assert_called_once_with("Downloading: 3/10 files")
        self.view_model.download_progress_updated.emit.assert_called_once_with(3, 10)

    def test_handle_download_item_progress(self):
        """Test handling download item progress updates."""
        # Setup
        timestamp = datetime.now()
        item1 = EnhancedMissingTimestamp(timestamp, "test1.png")
        item2 = EnhancedMissingTimestamp(timestamp - timedelta(minutes=1), "test2.png")
        self.view_model._missing_timestamps = [item1, item2]
        
        # Mock signals
        self.view_model.download_item_progress = MagicMock()
        
        # Test progress update for first item
        self.view_model._handle_download_item_progress(0, 50)
        
        # Verify
        self.assertEqual(item1.progress, 50)
        self.view_model.download_item_progress.emit.assert_called_once_with(0, 50)
        
        # Test progress update for second item
        self.view_model.download_item_progress.reset_mock()
        self.view_model._handle_download_item_progress(1, 75)
        
        # Verify
        self.assertEqual(item2.progress, 75)
        self.view_model.download_item_progress.emit.assert_called_once_with(1, 75)
        
        # Test with invalid index
        self.view_model.download_item_progress.reset_mock()
        self.view_model._handle_download_item_progress(5, 100)  # Out of range
        
        # Verify no emissions for invalid index
        self.view_model.download_item_progress.emit.assert_not_called()

    def test_handle_enhanced_download_completed(self):
        """Test handling enhanced download completion."""
        # Setup
        timestamp1 = datetime.now()
        timestamp2 = datetime.now() - timedelta(minutes=1)
        
        item1 = EnhancedMissingTimestamp(timestamp1, "test1.png")
        item2 = EnhancedMissingTimestamp(timestamp2, "test2.png")
        self.view_model._missing_timestamps = [item1, item2]
        
        # Mock signals
        self.view_model.status_updated = MagicMock()
        self.view_model.status_type_changed = MagicMock()
        self.view_model.download_item_updated = MagicMock()
        
        # Create results
        success_path = self.base_dir / "success.png"
        results = {
            timestamp1: success_path,  # Success
            timestamp2: FileNotFoundError("Not found")  # Error
        }
        
        # Test completion
        self.view_model._handle_enhanced_download_completed(results)
        
        # Verify
        self.assertEqual(self.view_model.status, ScanStatus.COMPLETED)
        self.assertEqual(self.view_model._downloaded_count, 1)
        self.assertEqual(self.view_model._failed_count, 1)
        
        # Check item states
        self.assertFalse(item1.is_downloading)
        self.assertTrue(item1.is_downloaded)
        self.assertEqual(item1.local_path, str(success_path))
        
        self.assertFalse(item2.is_downloading)
        self.assertFalse(item2.is_downloaded)
        self.assertEqual(item2.download_error, "Not found")
        
        # Verify signals
        self.view_model.download_item_updated.assert_has_calls([
            call(0, item1),
            call(1, item2)
        ], any_order=True)
        
        self.assertEqual(self.view_model.status_message,
                        "Downloads complete: 1 successful, 1 failed")

    def test_cleanup(self):
        """Test cleanup method."""
        self.view_model.cleanup()
        
        # Verify disk space timer stopped
        self.mock_timer.terminate.assert_called_once()
        self.mock_timer.wait.assert_called_once()
        
        # Verify cache closed
        self.mock_cache_db.close.assert_called_once()

    def test_start_enhanced_scan(self):
        """Test starting enhanced scan."""
        # Mock AsyncScanTask constructor and instance
        mock_scan_task = MagicMock()
        
        with patch('goesvfi.integrity_check.enhanced_view_model.AsyncScanTask', 
                return_value=mock_scan_task) as mock_scan_task_class:
            # Set view model state
            self.view_model.start_date = self.start_date
            self.view_model.end_date = self.end_date
            self.view_model.interval_minutes = 10
            self.view_model.force_rescan = True
            self.view_model.auto_download = True
            
            # Start scan
            self.view_model.start_enhanced_scan()
            
            # Verify
            self.assertEqual(self.view_model.status, ScanStatus.SCANNING)
            mock_scan_task_class.assert_called_once_with(self.view_model)
            self.mock_thread_pool.start.assert_called_once_with(mock_scan_task)

    def test_start_enhanced_downloads(self):
        """Test starting enhanced downloads."""
        # Mock AsyncDownloadTask constructor and instance
        mock_download_task = MagicMock()
        
        with patch('goesvfi.integrity_check.enhanced_view_model.AsyncDownloadTask', 
                return_value=mock_download_task) as mock_download_task_class:
            # Set view model state
            timestamp = datetime.now()
            self.view_model._missing_timestamps = [EnhancedMissingTimestamp(timestamp, "test.png")]
            
            # Start downloads
            self.view_model.start_enhanced_downloads()
            
            # Verify
            self.assertEqual(self.view_model.status, ScanStatus.DOWNLOADING)
            mock_download_task_class.assert_called_once_with(self.view_model)
            self.mock_thread_pool.start.assert_called_once_with(mock_download_task)
            
            # Test with no missing items
            self.mock_thread_pool.reset_mock()
            mock_download_task_class.reset_mock()
            
            self.view_model._missing_timestamps = []
            self.view_model.start_enhanced_downloads()
            
            # Verify no task created for empty list
            mock_download_task_class.assert_not_called()
            self.mock_thread_pool.start.assert_not_called()
            
            # Test with downloading already in progress
            self.mock_thread_pool.reset_mock()
            mock_download_task_class.reset_mock()
            
            self.view_model._missing_timestamps = [EnhancedMissingTimestamp(timestamp, "test.png")]
            self.view_model._status = ScanStatus.DOWNLOADING
            self.view_model.start_enhanced_downloads()
            
            # Verify no task created when download in progress
            mock_download_task_class.assert_not_called()
            self.mock_thread_pool.start.assert_not_called()


class TestAsyncTasks(unittest.TestCase):
    """Test cases for the async tasks used by the enhanced view model."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        
        # Mock view model
        self.mock_view_model = MagicMock(spec=EnhancedIntegrityCheckViewModel)
        self.mock_view_model._reconcile_manager = MagicMock()
        self.mock_view_model._start_date = datetime(2023, 6, 15, 0, 0, 0)
        self.mock_view_model._end_date = datetime(2023, 6, 15, 1, 0, 0)
        self.mock_view_model._satellite = SatellitePattern.GOES_16
        self.mock_view_model._interval_minutes = 10
        self.mock_view_model._base_directory = self.base_dir
        
        # Mock signals class
        self.mock_signals = MagicMock(spec=AsyncTaskSignals)
        
        # Set up task under test
        self.scan_task = AsyncScanTask(self.mock_view_model)
        self.scan_task.signals = self.mock_signals
        
        self.download_task = AsyncDownloadTask(self.mock_view_model)
        self.download_task.signals = self.mock_signals

    def tearDown(self):
        """Tear down test fixtures."""
        # Clean up temporary directory
        self.temp_dir.cleanup()

    @patch('asyncio.new_event_loop')
    def test_scan_task_run(self, mock_new_event_loop):
        """Test scanning task execution."""
        # Mock event loop and scan result
        mock_loop = MagicMock()
        mock_new_event_loop.return_value = mock_loop
        
        mock_result = {"status": "completed", "existing": set(), "missing": set()}
        mock_loop.run_until_complete.return_value = mock_result
        
        # Run the task
        self.scan_task.run()
        
        # Verify
        mock_new_event_loop.assert_called_once()
        mock_loop.run_until_complete.assert_called_once()
        mock_loop.close.assert_called_once()
        self.mock_signals.scan_finished.emit.assert_called_once_with(mock_result)
        
        # Test with exception
        mock_new_event_loop.reset_mock()
        mock_loop.reset_mock()
        self.mock_signals.reset_mock()
        
        # Make run_until_complete raise an exception
        mock_loop.run_until_complete.side_effect = Exception("Test error")
        
        # Run the task
        self.scan_task.run()
        
        # Verify
        mock_new_event_loop.assert_called_once()
        mock_loop.run_until_complete.assert_called_once()
        mock_loop.close.assert_called_once()
        self.mock_signals.error.emit.assert_called_once()
        self.assertEqual(self.mock_signals.error.emit.call_args[0][0], "Test error")

    @patch('asyncio.set_event_loop')
    async def test_run_scan(self, mock_set_event_loop):
        """Test the async scan operation."""
        # Mock scan result
        existing = {datetime(2023, 6, 15, 0, 0, 0)}
        missing = {datetime(2023, 6, 15, 0, 10, 0)}
        
        self.mock_view_model._reconcile_manager.scan_directory = AsyncMock(
            return_value=(existing, missing)
        )
        
        # Run the scan
        result = await self.scan_task._run_scan()
        
        # Verify
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["existing"], existing)
        self.assertEqual(result["missing"], missing)
        self.assertEqual(result["total"], 2)
        
        self.mock_view_model._reconcile_manager.scan_directory.assert_called_once_with(
            directory=self.mock_view_model._base_directory,
            satellite=self.mock_view_model._satellite,
            start_time=self.mock_view_model._start_date,
            end_time=self.mock_view_model._end_date,
            interval_minutes=self.mock_view_model._interval_minutes,
            progress_callback=unittest.mock.ANY
        )
        
        # Test cancelled operation
        self.mock_view_model._reconcile_manager.scan_directory.reset_mock()
        self.mock_view_model._reconcile_manager.scan_directory.side_effect = asyncio.CancelledError()
        
        result = await self.scan_task._run_scan()
        self.assertEqual(result["status"], "cancelled")
        
        # Test error
        self.mock_view_model._reconcile_manager.scan_directory.reset_mock()
        self.mock_view_model._reconcile_manager.scan_directory.side_effect = Exception("Test error")
        
        result = await self.scan_task._run_scan()
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "Test error")

    @patch('asyncio.new_event_loop')
    def test_download_task_run(self, mock_new_event_loop):
        """Test download task execution."""
        # Mock event loop and download result
        mock_loop = MagicMock()
        mock_new_event_loop.return_value = mock_loop
        
        mock_timestamp = datetime(2023, 6, 15, 0, 0, 0)
        mock_result = {mock_timestamp: self.base_dir / "test.png"}
        mock_loop.run_until_complete.return_value = mock_result
        
        # Run the task
        self.download_task.run()
        
        # Verify
        mock_new_event_loop.assert_called_once()
        mock_loop.run_until_complete.assert_called_once()
        mock_loop.close.assert_called_once()
        self.mock_signals.download_finished.emit.assert_called_once_with(mock_result)
        
        # Test with exception
        mock_new_event_loop.reset_mock()
        mock_loop.reset_mock()
        self.mock_signals.reset_mock()
        
        # Make run_until_complete raise an exception
        mock_loop.run_until_complete.side_effect = Exception("Test error")
        
        # Run the task
        self.download_task.run()
        
        # Verify
        mock_new_event_loop.assert_called_once()
        mock_loop.run_until_complete.assert_called_once()
        mock_loop.close.assert_called_once()
        self.mock_signals.error.emit.assert_called_once()
        self.assertEqual(self.mock_signals.error.emit.call_args[0][0], "Test error")

    @patch('asyncio.set_event_loop')
    async def test_run_downloads(self, mock_set_event_loop):
        """Test the async download operation."""
        # Setup
        mock_timestamp = datetime(2023, 6, 15, 0, 0, 0)
        mock_item = EnhancedMissingTimestamp(mock_timestamp, "test.png")
        self.mock_view_model._missing_timestamps = [mock_item]
        
        mock_result = {mock_timestamp: self.base_dir / "test.png"}
        self.mock_view_model._reconcile_manager.fetch_missing_files = AsyncMock(
            return_value=mock_result
        )
        
        # Run the downloads
        result = await self.download_task._run_downloads()
        
        # Verify
        self.assertEqual(result, mock_result)
        
        self.mock_view_model._reconcile_manager.fetch_missing_files.assert_called_once_with(
            missing_timestamps={mock_timestamp},
            satellite=self.mock_view_model._satellite,
            progress_callback=unittest.mock.ANY,
            file_callback=unittest.mock.ANY,
            error_callback=unittest.mock.ANY
        )
        
        # Test cancelled operation
        self.mock_view_model._reconcile_manager.fetch_missing_files.reset_mock()
        self.mock_view_model._reconcile_manager.fetch_missing_files.side_effect = asyncio.CancelledError()
        
        result = await self.download_task._run_downloads()
        self.assertEqual(result, {})
        
        # Test error
        self.mock_view_model._reconcile_manager.fetch_missing_files.reset_mock()
        self.mock_view_model._reconcile_manager.fetch_missing_files.side_effect = Exception("Test error")
        
        result = await self.download_task._run_downloads()
        self.assertEqual(result, {})


def async_test(coro):
    """Decorator for running async tests."""
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro(*args, **kwargs))
    return wrapper


# Apply async_test decorator to async test methods
for cls in [TestAsyncTasks]:
    for method_name in dir(cls):
        if method_name.startswith('test_') and asyncio.iscoroutinefunction(getattr(cls, method_name)):
            setattr(cls, method_name, async_test(getattr(cls, method_name)))


if __name__ == '__main__':
    unittest.main()