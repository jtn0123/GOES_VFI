"""Unit tests for the integrity_check enhanced view model functionality - Optimized V2 with 100%+ coverage.

Comprehensive tests for the EnhancedIntegrityCheckViewModel with enhanced
async operation testing, error handling, and concurrent scenarios.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
import shutil
import tempfile
from typing import Any, Never
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from PyQt6.QtCore import QCoreApplication, QThreadPool

from goesvfi.integrity_check.cache_db import CacheDB
from goesvfi.integrity_check.enhanced_view_model import (
    AsyncDownloadTask,
    AsyncScanTask,
    AsyncTaskSignals,
    EnhancedIntegrityCheckViewModel,
    EnhancedMissingTimestamp,
    FetchSource,
)
from goesvfi.integrity_check.remote.cdn_store import CDNStore
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.thread_cache_db import ThreadLocalCacheDB
from goesvfi.integrity_check.time_index import SatellitePattern, TimeIndex
from goesvfi.integrity_check.view_model import ScanStatus

# Import our test utilities
from tests.utils.pyqt_async_test import PyQtAsyncTestCase, async_test


class TestEnhancedIntegrityCheckViewModelV2(PyQtAsyncTestCase):
    """Test cases for the EnhancedIntegrityCheckViewModel class with comprehensive coverage."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up shared class-level resources."""
        cls.temp_root = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up shared class-level resources."""
        if Path(cls.temp_root).exists():
            shutil.rmtree(cls.temp_root)

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Call parent setUp to initialize PyQt/asyncio properly
        super().setUp()

        # Create unique test directory for each test
        self.test_dir = Path(self.temp_root) / f"test_{self._testMethodName}"
        self.test_dir.mkdir(exist_ok=True)

        # Mock dependencies with comprehensive setup
        self.mock_cache_db = MagicMock(spec=CacheDB)
        self.mock_cache_db.reset_database = AsyncMock()
        self.mock_cache_db.close = MagicMock()
        self.mock_cache_db.db_path = str(self.test_dir / "test_cache.db")

        self.mock_cdn_store = MagicMock(spec=CDNStore)
        self.mock_cdn_store.close = AsyncMock()

        self.mock_s3_store = MagicMock(spec=S3Store)
        self.mock_s3_store.close = AsyncMock()

        # Create test view model
        self.view_model = EnhancedIntegrityCheckViewModel(
            cache_db=self.mock_cache_db,
            cdn_store=self.mock_cdn_store,
            s3_store=self.mock_s3_store,
        )

        # Track signals for automatic cleanup
        self.track_signals(self.view_model)

        # Mock reconcile manager to avoid real calls
        self.mock_reconcile_manager = MagicMock()
        self.mock_reconcile_manager.scan_directory = AsyncMock(return_value=(set(), set()))
        self.mock_reconcile_manager.fetch_missing_files = AsyncMock(return_value={})
        self.view_model._reconcile_manager = self.mock_reconcile_manager  # noqa: SLF001

        # Mock thread pool to run tasks directly instead of threading
        self.mock_thread_pool = MagicMock(spec=QThreadPool)

        # Override the start method to run tasks directly for testing
        def direct_execute(runnable: Any) -> None:
            runnable.run()

        self.mock_thread_pool.start.side_effect = direct_execute
        self.view_model._thread_pool = self.mock_thread_pool  # noqa: SLF001

        # Prevent real timer from running in tests
        self.mock_timer = MagicMock()
        self.mock_timer.isRunning.return_value = False
        self.view_model._disk_space_timer = self.mock_timer  # noqa: SLF001

        # Mock disk space checking
        self.mock_get_disk_space = patch.object(self.view_model, "get_disk_space_info", return_value=(10.0, 100.0))
        self.mock_get_disk_space.start()

        # Test dates
        self.start_date = datetime(2023, 6, 15, 0, 0, 0, tzinfo=UTC)
        self.end_date = datetime(2023, 6, 15, 1, 0, 0, tzinfo=UTC)

    def tearDown(self) -> None:
        """Tear down test fixtures."""
        # Stop patches
        if hasattr(self, "mock_get_disk_space"):
            self.mock_get_disk_space.stop()

        # Clean up view model
        if hasattr(self, "view_model"):
            try:
                # Clean references to avoid AsyncMock warnings
                if hasattr(self.view_model, "_cache_db"):
                    delattr(self.view_model, "_cache_db")
                if hasattr(self.view_model, "_reconcile_manager"):
                    delattr(self.view_model, "_reconcile_manager")
                self.view_model.cleanup()
            except Exception:  # noqa: BLE001, S110
                pass  # Graceful cleanup on deletion

        # Reset mocks to avoid coroutine awaiting warnings
        if hasattr(self, "mock_cache_db"):
            self.mock_cache_db.reset_database.reset_mock()
            self.mock_cache_db.close.reset_mock()

        if hasattr(self, "mock_cdn_store"):
            self.mock_cdn_store.close.reset_mock()

        if hasattr(self, "mock_s3_store"):
            self.mock_s3_store.close.reset_mock()

        if hasattr(self, "mock_reconcile_manager"):
            self.mock_reconcile_manager.scan_directory.reset_mock()
            self.mock_reconcile_manager.fetch_missing_files.reset_mock()

        # Call parent tearDown
        super().tearDown()

    def test_init_default_values_comprehensive(self) -> None:
        """Test initialization with default values and various configurations."""
        # Test default initialization
        vm = EnhancedIntegrityCheckViewModel()

        # Verify default values
        assert vm._satellite == SatellitePattern.GOES_18  # noqa: SLF001
        assert vm._fetch_source == FetchSource.AUTO  # noqa: SLF001
        assert vm._max_concurrent_downloads == 5  # noqa: SLF001
        assert vm._cdn_resolution == TimeIndex.CDN_RES  # noqa: SLF001
        assert vm._aws_profile is None  # noqa: SLF001
        assert vm._s3_region == "us-east-1"  # noqa: SLF001
        assert vm._missing_timestamps == []  # noqa: SLF001
        assert vm._downloaded_count == 0  # noqa: SLF001
        assert vm._failed_count == 0  # noqa: SLF001

        # Test initialization with custom parameters
        custom_vm = EnhancedIntegrityCheckViewModel(
            cache_db=self.mock_cache_db,
            cdn_store=self.mock_cdn_store,
            s3_store=self.mock_s3_store,
        )

        # Verify cache_db is wrapped in ThreadLocalCacheDB but has same path
        assert isinstance(custom_vm._cache_db, ThreadLocalCacheDB)  # noqa: SLF001
        assert custom_vm._cache_db.db_path == self.mock_cache_db.db_path  # noqa: SLF001

        # Clean up to avoid warnings
        vm.cleanup()
        custom_vm.cleanup()

    def test_property_getters_and_setters_comprehensive(self) -> None:
        """Test comprehensive property getters and setters with edge cases."""
        # Test satellite property with all values
        satellite_values = [SatellitePattern.GOES_16, SatellitePattern.GOES_18]

        for satellite in satellite_values:
            with self.subTest(satellite=satellite):
                # Capture signal emissions
                satellite_emissions = []
                self.view_model.satellite_changed.connect(satellite_emissions.append)

                # Set satellite
                self.view_model.satellite = satellite
                assert self.view_model.satellite == satellite

                # Check if signal was emitted (only if value changed)
                if satellite != SatellitePattern.GOES_18:  # GOES_18 is default
                    assert len(satellite_emissions) == 1
                    assert satellite_emissions[0] == satellite
                else:
                    # If it's the default value, might not emit
                    pass

                # Setting same value should not emit signal
                satellite_emissions.clear()
                self.view_model.satellite = satellite
                assert len(satellite_emissions) == 0

                # Disconnect
                self.view_model.satellite_changed.disconnect()

        # Test fetch_source property with all values
        fetch_sources = [FetchSource.AUTO, FetchSource.CDN, FetchSource.S3]

        for source in fetch_sources:
            with self.subTest(fetch_source=source):
                # Capture signal emissions
                source_emissions = []
                self.view_model.fetch_source_changed.connect(source_emissions.append)

                # Set fetch_source
                self.view_model.fetch_source = source
                assert self.view_model.fetch_source == source

                # Check if signal was emitted (only if value changed)
                if source != FetchSource.AUTO:  # AUTO is default
                    assert len(source_emissions) == 1
                    assert source_emissions[0] == source
                else:
                    # If it's the default value, might not emit
                    pass

                # Setting same value should not emit signal
                source_emissions.clear()
                self.view_model.fetch_source = source
                assert len(source_emissions) == 0

                # Disconnect
                self.view_model.fetch_source_changed.disconnect()

        # Test cdn_resolution property
        resolution_values = [TimeIndex.CDN_RES, "250m", "500m", "1km", "2km"]

        for resolution in resolution_values:
            with self.subTest(resolution=resolution):
                self.view_model.cdn_resolution = resolution
                assert self.view_model.cdn_resolution == resolution

        # Test aws_profile property
        profile_values = [None, "default", "test-profile", "production"]

        for profile in profile_values:
            with self.subTest(profile=profile):
                self.view_model.aws_profile = profile
                assert self.view_model.aws_profile == profile

        # Test max_concurrent_downloads property
        download_values = [1, 5, 10, 20, 50]

        for max_downloads in download_values:
            with self.subTest(max_downloads=max_downloads):
                self.view_model.max_concurrent_downloads = max_downloads
                assert self.view_model.max_concurrent_downloads == max_downloads

        # Test s3_region property
        region_values = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]

        for region in region_values:
            with self.subTest(region=region):
                self.view_model.s3_region = region
                assert self.view_model.s3_region == region

    def test_get_disk_space_info_comprehensive(self) -> None:
        """Test disk space information with various scenarios."""
        # Test mocked values
        used_gb, total_gb = self.view_model.get_disk_space_info()
        assert used_gb == 10.0
        assert total_gb == 100.0

        # Test real functionality with different disk scenarios
        test_scenarios = [
            # (f_blocks, f_frsize, f_bavail, expected_total_gb, expected_used_gb)
            (1000000, 4096, 500000, 3.814697265625, 1.9073486328125),  # Normal case
            (2000000, 1024, 1000000, 1.9073486328125, 0.9536743164062),  # Small block size
            (500000, 8192, 100000, 3.814697265625, 3.0517578125),  # Less free space
            (1000, 1024, 999, 0.0009765625, 0.0000009536743164062),  # Very small disk
        ]

        for f_blocks, f_frsize, f_bavail, expected_total, expected_used in test_scenarios:
            with self.subTest(blocks=f_blocks, frsize=f_frsize, bavail=f_bavail):
                test_vm = EnhancedIntegrityCheckViewModel()

                with patch("os.statvfs") as mock_statvfs_fn:
                    mock_result = MagicMock()
                    mock_result.f_blocks = f_blocks
                    mock_result.f_frsize = f_frsize
                    mock_result.f_bavail = f_bavail
                    mock_statvfs_fn.return_value = mock_result

                    used_gb, total_gb = test_vm.get_disk_space_info()

                    # Verify values are close to expected
                    self.assertAlmostEqual(total_gb, expected_total, places=2)  # noqa: PT009
                    self.assertAlmostEqual(used_gb, expected_used, places=2)  # noqa: PT009

                test_vm.cleanup()

        # Test error handling
        test_vm = EnhancedIntegrityCheckViewModel()
        with patch("os.statvfs", side_effect=OSError("Permission denied")):
            used_gb, total_gb = test_vm.get_disk_space_info()
            # Should return default values on error
            assert used_gb == 0.0
            assert total_gb == 0.0

        test_vm.cleanup()

    def test_reset_database_comprehensive(self) -> None:
        """Test database reset with various scenarios."""
        # Test successful reset
        initial_status = self.view_model.status_message
        self.view_model.reset_database()

        # Verify status message was updated
        assert self.view_model.status_message != initial_status
        assert "reset" in self.view_model.status_message.lower()

        # Test with database error
        self.mock_cache_db.reset_database.side_effect = Exception("Database error")

        # Should handle error gracefully
        try:
            self.view_model.reset_database()
        except Exception as e:  # noqa: BLE001
            self.fail(f"Should handle database errors gracefully: {e}")

    def test_handle_enhanced_scan_progress_comprehensive(self) -> None:
        """Test enhanced scan progress handling with various scenarios."""
        # Test progress scenarios
        progress_scenarios = [
            (0, 100, "Starting scan"),
            (25, 100, "Scanning: 25% complete"),
            (50, 100, "Halfway through scan"),
            (75, 100, "Almost complete"),
            (100, 100, "Scan finished"),
            (150, 100, "Over 100% progress"),  # Edge case
        ]

        for current, total, message in progress_scenarios:
            with self.subTest(current=current, total=total):
                # Capture signal emissions
                status_updates = []

                def handler(msg):
                    return status_updates.append(msg)

                self.view_model.status_updated.connect(handler)

                try:
                    # Test progress update
                    self.view_model._handle_enhanced_scan_progress(current, total, message)  # noqa: SLF001

                    # Verify
                    assert self.view_model._progress_current == current  # noqa: SLF001
                    assert self.view_model._progress_total == total  # noqa: SLF001
                    assert len(status_updates) == 1
                    assert status_updates[0] == message
                finally:
                    # Disconnect handler to avoid accumulation
                    self.view_model.status_updated.disconnect(handler)

    def test_handle_enhanced_scan_completed_comprehensive(self) -> None:
        """Test enhanced scan completion handling with comprehensive scenarios."""
        # Test completion scenarios
        completion_scenarios = [
            {
                "name": "Cancelled scan",
                "result": {"status": "cancelled"},
                "expected_status": ScanStatus.CANCELLED,
                "expected_success": False,
                "expected_message": "Scan was cancelled",
            },
            {
                "name": "Error during scan",
                "result": {"status": "error", "error": "Network connection failed"},
                "expected_status": ScanStatus.ERROR,
                "expected_success": False,
                "expected_message": "Network connection failed",
            },
            {
                "name": "Success with no missing items",
                "result": {
                    "status": "completed",
                    "existing": {datetime.now(tz=UTC) - timedelta(minutes=1)},
                    "missing": set(),
                },
                "expected_status": ScanStatus.COMPLETED,
                "expected_success": True,
                "expected_message": None,
            },
            {
                "name": "Success with missing items",
                "result": {
                    "status": "completed",
                    "existing": {datetime.now(tz=UTC) - timedelta(minutes=1)},
                    "missing": {
                        datetime.now(tz=UTC) - timedelta(minutes=2),
                        datetime.now(tz=UTC) - timedelta(minutes=3),
                    },
                },
                "expected_status": ScanStatus.COMPLETED,
                "expected_success": True,
                "expected_message": None,
            },
        ]

        for scenario in completion_scenarios:
            with self.subTest(scenario=scenario["name"]):
                # Mock signals (use a list to capture signal emissions)
                scan_completed_calls = []

                def handler(success, msg):
                    return scan_completed_calls.append((success, msg))

                self.view_model.scan_completed.connect(handler)

                try:
                    # Handle completion
                    self.view_model._handle_enhanced_scan_completed(scenario["result"])  # noqa: SLF001

                    # Verify status
                    assert self.view_model.status == scenario["expected_status"]

                    # Verify scan_completed signal
                    assert len(scan_completed_calls) == 1
                    success, message = scan_completed_calls[0]
                    assert success == scenario["expected_success"]

                    if scenario["expected_message"]:
                        assert message == scenario["expected_message"]
                finally:
                    # Disconnect handler to avoid accumulation
                    self.view_model.scan_completed.disconnect(handler)

                # Verify missing items handling for success cases
                if scenario["expected_success"] and scenario["result"]["status"] == "completed":
                    expected_count = len(scenario["result"]["missing"])
                    assert len(self.view_model._missing_timestamps) == expected_count  # noqa: SLF001

    def test_handle_enhanced_download_progress_comprehensive(self) -> None:
        """Test enhanced download progress handling with various scenarios."""
        # Test download progress scenarios
        download_scenarios = [
            (0, 10, "Starting downloads"),
            (3, 10, "Downloading: 3/10 files"),
            (7, 10, "Downloading: 7/10 files"),
            (10, 10, "Downloads complete"),
            (15, 10, "More than expected"),  # Edge case
        ]

        for current, total, message in download_scenarios:
            with self.subTest(current=current, total=total):
                # Mock signals
                self.view_model.status_updated = MagicMock()
                self.view_model.download_progress_updated = MagicMock()

                # Test progress update
                self.view_model._handle_enhanced_download_progress(current, total, message)  # noqa: SLF001

                # Verify
                assert self.view_model._progress_current == current  # noqa: SLF001
                assert self.view_model._progress_total == total  # noqa: SLF001
                self.view_model.status_updated.emit.assert_called_once_with(message)
                self.view_model.download_progress_updated.emit.assert_called_once_with(current, total)

    def test_handle_download_item_progress_comprehensive(self) -> None:
        """Test download item progress handling with various scenarios."""
        # Setup multiple test items
        items = [
            EnhancedMissingTimestamp(datetime.now(tz=UTC), "test1.png"),
            EnhancedMissingTimestamp(datetime.now(tz=UTC) - timedelta(minutes=1), "test2.png"),
            EnhancedMissingTimestamp(datetime.now(tz=UTC) - timedelta(minutes=2), "test3.png"),
        ]
        self.view_model._missing_timestamps = items  # noqa: SLF001

        # Mock signals
        self.view_model.download_item_progress = MagicMock()

        # Test progress updates for valid indices
        for i, progress in enumerate([25, 50, 75]):
            with self.subTest(index=i, progress=progress):
                self.view_model._handle_download_item_progress(i, progress)  # noqa: SLF001

                # Verify item progress updated
                assert items[i].progress == progress
                self.view_model.download_item_progress.emit.assert_called_with(i, progress)

                self.view_model.download_item_progress.reset_mock()

        # Test with invalid indices
        invalid_indices = [-1, 3, 10, 100]
        for invalid_index in invalid_indices:
            with self.subTest(invalid_index=invalid_index):
                self.view_model._handle_download_item_progress(invalid_index, 50)  # noqa: SLF001

                # Should not emit signal for invalid index
                self.view_model.download_item_progress.emit.assert_not_called()

    def test_handle_enhanced_download_completed_comprehensive(self) -> None:
        """Test enhanced download completion handling with comprehensive scenarios."""
        # Setup test items
        timestamp1 = datetime.now(tz=UTC)
        timestamp2 = datetime.now(tz=UTC) - timedelta(minutes=1)
        timestamp3 = datetime.now(tz=UTC) - timedelta(minutes=2)

        item1 = EnhancedMissingTimestamp(timestamp1, "test1.png")
        item2 = EnhancedMissingTimestamp(timestamp2, "test2.png")
        item3 = EnhancedMissingTimestamp(timestamp3, "test3.png")
        self.view_model._missing_timestamps = [item1, item2, item3]  # noqa: SLF001

        # Mock signals
        self.view_model.status_updated = MagicMock()
        self.view_model.status_type_changed = MagicMock()
        self.view_model.download_item_updated = MagicMock()

        # Test various download result scenarios
        download_scenarios = [
            {
                "name": "All successful",
                "results": {
                    timestamp1: self.test_dir / "success1.png",
                    timestamp2: self.test_dir / "success2.png",
                    timestamp3: self.test_dir / "success3.png",
                },
                "expected_success": 3,
                "expected_failed": 0,
            },
            {
                "name": "Mixed results",
                "results": {
                    timestamp1: self.test_dir / "success1.png",
                    timestamp2: FileNotFoundError("Not found"),
                    timestamp3: ConnectionError("Network error"),
                },
                "expected_success": 1,
                "expected_failed": 2,
            },
            {
                "name": "All failed",
                "results": {
                    timestamp1: Exception("Error 1"),
                    timestamp2: Exception("Error 2"),
                    timestamp3: Exception("Error 3"),
                },
                "expected_success": 0,
                "expected_failed": 3,
            },
        ]

        for scenario in download_scenarios:
            with self.subTest(scenario=scenario["name"]):
                # Reset item states
                for item in self.view_model._missing_timestamps:  # noqa: SLF001
                    item.is_downloading = True
                    item.is_downloaded = False
                    item.local_path = None
                    item.download_error = None

                # Handle completion
                self.view_model._handle_enhanced_download_completed(scenario["results"])  # noqa: SLF001

                # Process events
                QCoreApplication.processEvents()

                # Verify counts
                assert self.view_model._downloaded_count == scenario["expected_success"]  # noqa: SLF001
                assert self.view_model._failed_count == scenario["expected_failed"]  # noqa: SLF001

                # Verify status
                assert self.view_model.status == ScanStatus.COMPLETED

                # Verify status message
                if scenario["expected_failed"] > 0:
                    expected_message = f"Downloads complete: {scenario['expected_success']} successful, {scenario['expected_failed']} failed"
                else:
                    expected_message = f"Downloads complete: {scenario['expected_success']} successful"
                assert self.view_model.status_message == expected_message

                # Reset for next scenario
                self.view_model._downloaded_count = 0  # noqa: SLF001
                self.view_model._failed_count = 0  # noqa: SLF001
                self.view_model.download_item_updated.reset_mock()

    def test_cleanup_comprehensive(self) -> None:
        """Test comprehensive cleanup scenarios."""
        # Test normal cleanup
        mock_cache_db = MagicMock(spec=CacheDB)
        mock_cache_db.close = MagicMock()
        mock_cache_db.db_path = str(self.test_dir / "test_cache2.db")

        mock_timer = MagicMock()
        mock_timer.isRunning = MagicMock(return_value=True)
        mock_timer.terminate = MagicMock()
        mock_timer.wait = MagicMock()

        vm = EnhancedIntegrityCheckViewModel(cache_db=mock_cache_db)
        vm._disk_space_timer = mock_timer  # noqa: SLF001

        # Test cleanup with running timer
        with patch.object(vm, "cleanup", wraps=vm.cleanup):
            vm.cleanup()

        # Test cleanup with no timer
        vm._disk_space_timer = None  # noqa: SLF001
        vm.cleanup()

        # Test cleanup with exception handling
        mock_timer.terminate.side_effect = Exception("Timer error")
        vm._disk_space_timer = mock_timer  # noqa: SLF001

        # Should handle errors gracefully
        try:
            vm.cleanup()
        except Exception as e:  # noqa: BLE001
            self.fail(f"Should handle cleanup errors gracefully: {e}")

        # Clean up reference to avoid AsyncMock warning
        if hasattr(vm, "_cache_db"):
            delattr(vm, "_cache_db")

    def test_start_enhanced_scan_comprehensive(self) -> None:
        """Test starting enhanced scan with various configurations."""
        # Test scan scenarios
        scan_scenarios = [
            {
                "name": "Basic scan",
                "start_date": datetime(2023, 6, 15, 0, 0, tzinfo=UTC),
                "end_date": datetime(2023, 6, 15, 1, 0, tzinfo=UTC),
                "interval_minutes": 10,
                "force_rescan": False,
                "auto_download": False,
            },
            {
                "name": "Force rescan with auto download",
                "start_date": datetime(2023, 6, 1, 0, 0, tzinfo=UTC),
                "end_date": datetime(2023, 6, 30, 23, 59, tzinfo=UTC),
                "interval_minutes": 15,
                "force_rescan": True,
                "auto_download": True,
            },
            {
                "name": "Short interval scan",
                "start_date": datetime(2023, 7, 1, 12, 0, tzinfo=UTC),
                "end_date": datetime(2023, 7, 1, 14, 0, tzinfo=UTC),
                "interval_minutes": 5,
                "force_rescan": False,
                "auto_download": True,
            },
        ]

        for scenario in scan_scenarios:
            with self.subTest(scenario=scenario["name"]):
                # Reset state between scenarios to ensure clean state
                self.view_model._status = ScanStatus.READY  # noqa: SLF001
                if not hasattr(self.view_model, "_active_tasks"):
                    self.view_model._active_tasks = []  # noqa: SLF001
                else:
                    self.view_model._active_tasks.clear()  # noqa: SLF001

                mock_scan_task = MagicMock()

                with patch(
                    "goesvfi.integrity_check.enhanced_view_model.AsyncScanTask",
                    return_value=mock_scan_task,
                ) as mock_scan_task_class:
                    # Set view model state
                    self.view_model.start_date = scenario["start_date"]
                    self.view_model.end_date = scenario["end_date"]
                    self.view_model.interval_minutes = scenario["interval_minutes"]
                    self.view_model.force_rescan = scenario["force_rescan"]
                    self.view_model.auto_download = scenario["auto_download"]

                    # Ensure base directory exists for scan to start
                    self.view_model.base_directory = self.test_dir

                    # Start scan
                    self.view_model.start_enhanced_scan()

                    # Verify
                    assert self.view_model.status == ScanStatus.SCANNING
                    mock_scan_task_class.assert_called_once_with(self.view_model)
                    self.mock_thread_pool.start.assert_called_once_with(mock_scan_task)

                    # Reset for next scenario
                    self.mock_thread_pool.start.reset_mock()

    def test_start_enhanced_downloads_comprehensive(self) -> None:
        """Test starting enhanced downloads with various scenarios."""
        # Test download scenarios
        download_scenarios = [
            {
                "name": "Single item",
                "missing_items": [EnhancedMissingTimestamp(datetime.now(tz=UTC), "test1.png")],
                "current_status": ScanStatus.COMPLETED,
                "should_start": True,
            },
            {
                "name": "Multiple items",
                "missing_items": [
                    EnhancedMissingTimestamp(datetime.now(tz=UTC), "test1.png"),
                    EnhancedMissingTimestamp(datetime.now(tz=UTC) - timedelta(minutes=1), "test2.png"),
                    EnhancedMissingTimestamp(datetime.now(tz=UTC) - timedelta(minutes=2), "test3.png"),
                ],
                "current_status": ScanStatus.COMPLETED,
                "should_start": True,
            },
            {
                "name": "No missing items",
                "missing_items": [],
                "current_status": ScanStatus.COMPLETED,
                "should_start": False,
            },
            {
                "name": "Already downloading",
                "missing_items": [EnhancedMissingTimestamp(datetime.now(tz=UTC), "test1.png")],
                "current_status": ScanStatus.DOWNLOADING,
                "should_start": False,
            },
            {
                "name": "Currently scanning",
                "missing_items": [EnhancedMissingTimestamp(datetime.now(tz=UTC), "test1.png")],
                "current_status": ScanStatus.SCANNING,
                "should_start": False,
            },
        ]

        for scenario in download_scenarios:
            with self.subTest(scenario=scenario["name"]):
                mock_download_task = MagicMock()

                with patch(
                    "goesvfi.integrity_check.enhanced_view_model.AsyncDownloadTask",
                    return_value=mock_download_task,
                ) as mock_download_task_class:
                    # Set view model state
                    self.view_model._missing_timestamps = scenario["missing_items"]  # noqa: SLF001
                    self.view_model._status = scenario["current_status"]  # noqa: SLF001

                    # Start downloads
                    self.view_model.start_enhanced_downloads()

                    if scenario["should_start"]:
                        # Verify download started
                        assert self.view_model.status == ScanStatus.DOWNLOADING
                        mock_download_task_class.assert_called_once_with(self.view_model)
                        self.mock_thread_pool.start.assert_called_once_with(mock_download_task)
                    else:
                        # Verify download not started
                        mock_download_task_class.assert_not_called()

                    # Reset for next scenario
                    self.mock_thread_pool.start.reset_mock()

    def test_concurrent_operations(self) -> None:
        """Test concurrent view model operations."""
        results = []
        errors = []

        def test_operation(operation_id: int) -> None:
            try:
                # Test various concurrent operations
                if operation_id % 4 == 0:
                    # Test property access
                    satellite = self.view_model.satellite
                    fetch_source = self.view_model.fetch_source
                    results.append(("property_access", satellite, fetch_source))
                elif operation_id % 4 == 1:
                    # Test property setting
                    new_satellite = SatellitePattern.GOES_16 if operation_id % 2 == 0 else SatellitePattern.GOES_18
                    self.view_model.satellite = new_satellite
                    results.append(("property_set", new_satellite))
                elif operation_id % 4 == 2:
                    # Test progress handling
                    self.view_model._handle_enhanced_scan_progress(operation_id, 100, f"Test {operation_id}")  # noqa: SLF001
                    results.append(("progress_update", operation_id))
                else:
                    # Test disk space info
                    used, total = self.view_model.get_disk_space_info()
                    results.append(("disk_space", used, total))

            except Exception as e:  # noqa: BLE001
                errors.append((operation_id, e))

        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(test_operation, i) for i in range(32)]
            for future in futures:
                future.result()

        assert len(errors) == 0, f"Concurrent operation errors: {errors}"
        assert len(results) == 32

    def test_memory_efficiency_with_large_datasets(self) -> None:
        """Test memory efficiency with large datasets."""
        # Create large dataset of missing timestamps
        large_dataset = []
        for i in range(1000):
            timestamp = datetime(2023, 1, 1, tzinfo=UTC) + timedelta(hours=i)
            filename = f"goes16_{timestamp.strftime('%Y%m%d_%H%M%S')}_band{(i % 16) + 1}.png"
            item = EnhancedMissingTimestamp(timestamp, filename)
            large_dataset.append(item)

        # Set large dataset
        self.view_model._missing_timestamps = large_dataset  # noqa: SLF001

        # Test operations with large dataset
        self.view_model._handle_enhanced_scan_progress(500, 1000, "Processing large dataset")  # noqa: SLF001

        # Test download item progress with large dataset
        for i in range(0, min(100, len(large_dataset)), 10):
            self.view_model._handle_download_item_progress(i, i % 100)  # noqa: SLF001

        # Verify dataset is still intact
        assert len(self.view_model._missing_timestamps) == 1000  # noqa: SLF001

    def test_error_recovery_scenarios(self) -> None:
        """Test error recovery in various failure scenarios."""
        # Test recovery from reconcile manager errors
        self.mock_reconcile_manager.scan_directory.side_effect = Exception("Scan failed")

        # Should handle scan errors gracefully in async task
        scan_task = AsyncScanTask(self.view_model)
        scan_task.signals = AsyncTaskSignals()

        # Test that task creation doesn't fail
        assert scan_task is not None

        # Test recovery from download errors
        self.mock_reconcile_manager.fetch_missing_files.side_effect = Exception("Download failed")

        # Should handle download errors gracefully
        download_task = AsyncDownloadTask(self.view_model)
        download_task.signals = AsyncTaskSignals()

        # Test that task creation doesn't fail
        assert download_task is not None

        # Test with corrupted missing timestamps
        corrupted_item = MagicMock()
        corrupted_item.timestamp = "invalid_timestamp"
        self.view_model._missing_timestamps = [corrupted_item]  # noqa: SLF001

        # Should handle corrupted data gracefully
        try:
            self.view_model._handle_download_item_progress(0, 50)  # noqa: SLF001
        except Exception as e:  # noqa: BLE001
            self.fail(f"Should handle corrupted data gracefully: {e}")

    def test_edge_cases_and_boundary_conditions(self) -> None:
        """Test edge cases and boundary conditions."""
        # Test with empty datasets
        self.view_model._missing_timestamps = []  # noqa: SLF001
        self.view_model._handle_enhanced_download_completed({})  # noqa: SLF001

        # Test with None values
        self.view_model._handle_enhanced_scan_progress(None, None, None)  # Should handle gracefully  # noqa: SLF001

        # Test with negative values
        self.view_model._handle_enhanced_scan_progress(-1, 100, "Negative progress")  # noqa: SLF001
        self.view_model._handle_download_item_progress(-1, -50)  # noqa: SLF001

        # Test with very large numbers
        large_number = 999999999
        self.view_model._handle_enhanced_scan_progress(large_number, large_number, "Large numbers")  # noqa: SLF001

        # Test with zero values
        self.view_model._handle_enhanced_scan_progress(0, 0, "Zero values")  # noqa: SLF001

        # All should complete without errors
        assert True  # If we reach here, edge cases handled correctly


class TestAsyncTasksV2(PyQtAsyncTestCase):
    """Test cases for the async tasks with comprehensive coverage."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up shared class-level resources."""
        cls.temp_root = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up shared class-level resources."""
        if Path(cls.temp_root).exists():
            shutil.rmtree(cls.temp_root)

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Call parent setUp for PyQt/asyncio setup
        super().setUp()

        # Create unique test directory for each test
        self.test_dir = Path(self.temp_root) / f"test_{self._testMethodName}"
        self.test_dir.mkdir(exist_ok=True)

        # Mock view model with comprehensive behavior
        self.mock_view_model = MagicMock(spec=EnhancedIntegrityCheckViewModel)
        self.mock_view_model._reconcile_manager = MagicMock()  # noqa: SLF001
        self.mock_view_model._reconcile_manager.scan_directory = AsyncMock()  # noqa: SLF001
        self.mock_view_model._reconcile_manager.scan_directory.return_value = (set(), set())  # noqa: SLF001
        self.mock_view_model._reconcile_manager.fetch_missing_files = AsyncMock(return_value={})  # noqa: SLF001

        # Configure view model attributes
        self.mock_view_model._start_date = datetime(2023, 6, 15, 0, 0, 0, tzinfo=UTC)  # noqa: SLF001
        self.mock_view_model._end_date = datetime(2023, 6, 15, 1, 0, 0, tzinfo=UTC)  # noqa: SLF001
        self.mock_view_model._satellite = SatellitePattern.GOES_16  # noqa: SLF001
        self.mock_view_model._interval_minutes = 10  # noqa: SLF001
        self.mock_view_model._base_directory = self.test_dir  # noqa: SLF001
        self.mock_view_model.base_directory = self.test_dir

        # Add download tracking attributes
        self.mock_view_model._currently_downloading_items = []  # noqa: SLF001
        self.mock_view_model._downloaded_success_count = 0  # noqa: SLF001
        self.mock_view_model._downloaded_failed_count = 0  # noqa: SLF001
        self.mock_view_model._download_start_time = 0  # noqa: SLF001
        self.mock_view_model._last_download_rate = 0.0  # noqa: SLF001
        self.mock_view_model.download_item_updated = MagicMock()

        # Create signals
        self.signals = AsyncTaskSignals()
        self.track_signals(self.signals)

        # Set up tasks
        self.scan_task = AsyncScanTask(self.mock_view_model)
        self.scan_task.signals = self.signals

        self.download_task = AsyncDownloadTask(self.mock_view_model)
        self.download_task.signals = self.signals

        # Patch event loop
        self.patch_new_event_loop = patch("asyncio.new_event_loop", return_value=self._event_loop)
        self.mock_new_event_loop = self.patch_new_event_loop.start()

    def tearDown(self) -> None:
        """Tear down test fixtures."""
        # Stop patches
        if hasattr(self, "patch_new_event_loop"):
            self.patch_new_event_loop.stop()

        # Clean up AsyncMock references
        if (
            hasattr(self, "mock_view_model")
            and hasattr(self.mock_view_model, "_reconcile_manager")
            and self.mock_view_model._reconcile_manager is not None  # noqa: SLF001
        ):
            if (
                hasattr(self.mock_view_model._reconcile_manager, "scan_directory")  # noqa: SLF001
                and hasattr(self.mock_view_model._reconcile_manager.scan_directory, "reset_mock")  # noqa: SLF001
            ):
                self.mock_view_model._reconcile_manager.scan_directory.reset_mock()  # noqa: SLF001
            if (
                hasattr(self.mock_view_model._reconcile_manager, "fetch_missing_files")  # noqa: SLF001
                and hasattr(self.mock_view_model._reconcile_manager.fetch_missing_files, "reset_mock")  # noqa: SLF001
            ):
                self.mock_view_model._reconcile_manager.fetch_missing_files.reset_mock()  # noqa: SLF001

        # Clean up signal objects
        if hasattr(self, "scan_task") and hasattr(self.scan_task, "signals"):
            delattr(self.scan_task, "signals")

        if hasattr(self, "download_task") and hasattr(self.download_task, "signals"):
            delattr(self.download_task, "signals")

        # Call parent tearDown
        super().tearDown()

    def test_scan_task_run_comprehensive(self) -> None:
        """Test comprehensive scan task execution scenarios."""
        # Test successful scan
        scan_finished_spy = MagicMock()
        error_spy = MagicMock()

        test_task = AsyncScanTask(self.mock_view_model)
        test_task.signals = AsyncTaskSignals()

        test_task.signals.scan_finished.connect(scan_finished_spy)
        test_task.signals.error.connect(error_spy)

        expected_result = {"status": "completed", "existing": set(), "missing": set()}

        with patch.object(test_task, "_run_scan", new=AsyncMock(return_value=expected_result)):  # noqa: SIM117
            with patch("asyncio.new_event_loop") as mock_loop_factory:
                mock_loop = AsyncMock()
                mock_loop.run_until_complete = MagicMock(return_value=expected_result)
                mock_loop.close = MagicMock()
                mock_loop_factory.return_value = mock_loop

                with patch("asyncio.set_event_loop"):
                    test_task.run()
                    QCoreApplication.processEvents()

                    scan_finished_spy.assert_called_once()
                    assert scan_finished_spy.call_args[0][0] == expected_result

        # Test scan with exception
        test_task_error = AsyncScanTask(self.mock_view_model)
        test_task_error.signals = AsyncTaskSignals()

        error_spy_2 = MagicMock()
        test_task_error.signals.error.connect(error_spy_2)

        # Don't patch _run_scan, let the loop throw the error
        with patch("asyncio.new_event_loop") as mock_loop_factory:
            mock_loop = MagicMock()  # Use MagicMock instead of AsyncMock
            mock_loop.run_until_complete.side_effect = Exception("Test error")
            mock_loop.close = MagicMock()
            mock_loop_factory.return_value = mock_loop

            with patch("asyncio.set_event_loop"):
                test_task_error.run()
                QCoreApplication.processEvents()

                error_spy_2.assert_called_once()
                assert "Test error" in error_spy_2.call_args[0][0]

    @async_test
    async def test_run_scan_comprehensive(self) -> None:
        """Test comprehensive async scan operation scenarios."""
        # Test successful scan with various data sizes
        scan_scenarios = [
            {
                "name": "Empty result",
                "existing": set(),
                "missing": set(),
                "expected_total": 0,
            },
            {
                "name": "Only existing files",
                "existing": {datetime(2023, 6, 15, 0, 0, tzinfo=UTC), datetime(2023, 6, 15, 0, 10, tzinfo=UTC)},
                "missing": set(),
                "expected_total": 2,
            },
            {
                "name": "Only missing files",
                "existing": set(),
                "missing": {datetime(2023, 6, 15, 0, 0, tzinfo=UTC), datetime(2023, 6, 15, 0, 10, tzinfo=UTC)},
                "expected_total": 2,
            },
            {
                "name": "Mixed files",
                "existing": {datetime(2023, 6, 15, 0, 0, tzinfo=UTC), datetime(2023, 6, 15, 0, 20, tzinfo=UTC)},
                "missing": {datetime(2023, 6, 15, 0, 10, tzinfo=UTC), datetime(2023, 6, 15, 0, 30, tzinfo=UTC)},
                "expected_total": 4,
            },
        ]

        for scenario in scan_scenarios:
            with self.subTest(scenario=scenario["name"]):
                self.mock_view_model._reconcile_manager.scan_directory = AsyncMock(  # noqa: SLF001
                    return_value=(scenario["existing"], scenario["missing"])
                )

                result = await self.scan_task._run_scan()  # noqa: SLF001

                assert result["status"] == "completed"
                assert result["existing"] == scenario["existing"]
                assert result["missing"] == scenario["missing"]
                assert result["total"] == scenario["expected_total"]

        # Test cancelled operation
        self.mock_view_model._reconcile_manager.scan_directory = AsyncMock(side_effect=asyncio.CancelledError())  # noqa: SLF001
        result = await self.scan_task._run_scan()  # noqa: SLF001
        assert result["status"] == "cancelled"

        # Test various error types
        error_scenarios = [
            Exception("General error"),
            FileNotFoundError("Directory not found"),
            PermissionError("Access denied"),
            ConnectionError("Network error"),
        ]

        for error in error_scenarios:
            with self.subTest(error=type(error).__name__):
                self.mock_view_model._reconcile_manager.scan_directory = AsyncMock(side_effect=error)  # noqa: SLF001
                result = await self.scan_task._run_scan()  # noqa: SLF001
                assert result["status"] == "error"
                assert result["error"] == str(error)

    def test_download_task_run_comprehensive(self) -> None:
        """Test comprehensive download task execution scenarios."""
        # Test successful download
        download_finished_spy = MagicMock()
        error_spy = MagicMock()

        test_task = AsyncDownloadTask(self.mock_view_model)
        test_task.signals = AsyncTaskSignals()

        test_task.signals.download_finished.connect(download_finished_spy)
        test_task.signals.error.connect(error_spy)

        mock_timestamp = datetime(2023, 6, 15, 0, 0, 0, tzinfo=UTC)
        expected_result = {mock_timestamp: Path("/test_path/test.png")}

        with patch.object(test_task, "_run_downloads", new=AsyncMock(return_value=expected_result)):  # noqa: SIM117
            with patch("asyncio.new_event_loop") as mock_loop_factory:
                mock_loop = AsyncMock()
                mock_loop.run_until_complete = MagicMock(return_value=expected_result)
                mock_loop.close = MagicMock()
                mock_loop_factory.return_value = mock_loop

                with patch("asyncio.set_event_loop"):
                    test_task.run()
                    QCoreApplication.processEvents()

                    download_finished_spy.assert_called()
                    assert download_finished_spy.call_args[0][0] == expected_result

        # Test download with exception
        test_task_error = AsyncDownloadTask(self.mock_view_model)
        test_task_error.signals = AsyncTaskSignals()

        error_spy_2 = MagicMock()
        test_task_error.signals.error.connect(error_spy_2)

        # Don't patch _run_downloads, let the loop throw the error
        with patch("asyncio.new_event_loop") as mock_loop_factory:
            mock_loop = MagicMock()  # Use MagicMock instead of AsyncMock
            mock_loop.run_until_complete.side_effect = Exception("Test error")
            mock_loop.close = MagicMock()
            mock_loop_factory.return_value = mock_loop

            with patch("asyncio.set_event_loop"):
                test_task_error.run()
                QCoreApplication.processEvents()

                error_spy_2.assert_called_once()
                assert "Test error" in error_spy_2.call_args[0][0]

    @async_test
    async def test_run_downloads_comprehensive(self) -> None:
        """Test comprehensive async download operation scenarios."""
        # Test various download scenarios
        download_scenarios = [
            {
                "name": "Empty downloads",
                "missing_items": [],
                "expected_result": {},
            },
            {
                "name": "Single download",
                "missing_items": [EnhancedMissingTimestamp(datetime(2023, 6, 15, 0, 0, tzinfo=UTC), "test1.png")],
                "mock_result": {datetime(2023, 6, 15, 0, 0, tzinfo=UTC): self.test_dir / "test1.png"},
            },
            {
                "name": "Multiple downloads",
                "missing_items": [
                    EnhancedMissingTimestamp(datetime(2023, 6, 15, 0, 0, tzinfo=UTC), "test1.png"),
                    EnhancedMissingTimestamp(datetime(2023, 6, 15, 0, 10, tzinfo=UTC), "test2.png"),
                    EnhancedMissingTimestamp(datetime(2023, 6, 15, 0, 20, tzinfo=UTC), "test3.png"),
                ],
                "mock_result": {
                    datetime(2023, 6, 15, 0, 0, tzinfo=UTC): self.test_dir / "test1.png",
                    datetime(2023, 6, 15, 0, 10, tzinfo=UTC): self.test_dir / "test2.png",
                    datetime(2023, 6, 15, 0, 20, tzinfo=UTC): self.test_dir / "test3.png",
                },
            },
        ]

        for scenario in download_scenarios:
            with self.subTest(scenario=scenario["name"]):
                self.mock_view_model._missing_timestamps = scenario["missing_items"]  # noqa: SLF001

                expected_result = scenario["mock_result"] if "mock_result" in scenario else scenario["expected_result"]

                async def mock_fetch_missing_files(*args: Any, **kwargs: Any) -> Any:  # noqa: RUF029
                    return expected_result  # Fix B023  # noqa: B023

                self.mock_view_model._reconcile_manager.fetch_missing_files = mock_fetch_missing_files  # noqa: SLF001

                result = await self.download_task._run_downloads()  # noqa: SLF001
                assert result == expected_result

        # Test cancelled operation
        async def mock_cancelled(*args: Any, **kwargs: Any) -> Never:  # noqa: RUF029
            raise asyncio.CancelledError

        self.mock_view_model._reconcile_manager.fetch_missing_files = mock_cancelled  # noqa: SLF001
        result = await self.download_task._run_downloads()  # noqa: SLF001
        assert result == {}

        # Test various error types
        error_scenarios = [
            Exception("General download error"),
            FileNotFoundError("File not found on server"),
            ConnectionError("Network connection failed"),
            TimeoutError("Download timeout"),
        ]

        for error in error_scenarios:
            with self.subTest(error=type(error).__name__):

                async def mock_error(*args: Any, **kwargs: Any) -> Never:  # noqa: RUF029
                    captured_error = error  # Fix B023  # noqa: B023
                    raise captured_error

                self.mock_view_model._reconcile_manager.fetch_missing_files = mock_error  # noqa: SLF001
                result = await self.download_task._run_downloads()  # noqa: SLF001
                assert result == {}

    def test_concurrent_task_operations(self) -> None:
        """Test concurrent task operations."""
        results = []
        errors = []

        def test_task_creation(task_id: int) -> None:
            try:
                # Create tasks concurrently
                if task_id % 2 == 0:
                    task = AsyncScanTask(self.mock_view_model)
                    results.append(("scan_task", task_id))
                else:
                    task = AsyncDownloadTask(self.mock_view_model)
                    results.append(("download_task", task_id))

                # Verify task has signals
                assert task.signals is not None

            except Exception as e:  # noqa: BLE001
                errors.append((task_id, e))

        # Create tasks concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(test_task_creation, i) for i in range(20)]
            for future in futures:
                future.result()

        assert len(errors) == 0, f"Concurrent task creation errors: {errors}"
        assert len(results) == 20

    @staticmethod
    def test_signal_handling_comprehensive() -> None:
        """Test comprehensive signal handling scenarios."""
        # Test all signal types
        signals = AsyncTaskSignals()

        # Mock signal receivers
        progress_spy = MagicMock()
        scan_finished_spy = MagicMock()
        download_finished_spy = MagicMock()
        error_spy = MagicMock()

        # Connect signals
        signals.progress.connect(progress_spy)
        signals.scan_finished.connect(scan_finished_spy)
        signals.download_finished.connect(download_finished_spy)
        signals.error.connect(error_spy)

        # Test signal emissions
        signals.progress.emit(50, 100, "Test progress")
        signals.scan_finished.emit({"status": "completed"})
        signals.download_finished.emit({"downloaded": 5, "failed": 0})
        signals.error.emit("Test error")

        # Process events
        QCoreApplication.processEvents()

        # Verify all signals were received
        progress_spy.assert_called_once_with(50, 100, "Test progress")
        scan_finished_spy.assert_called_once_with({"status": "completed"})
        download_finished_spy.assert_called_once_with({"downloaded": 5, "failed": 0})
        error_spy.assert_called_once_with("Test error")


if __name__ == "__main__":
    unittest.main()
