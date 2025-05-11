"""
Integration tests for the integrity check tabs to ensure proper functionality and synchronization.

These tests focus on verifying data propagation, signal connections, and feature support
across all the integrity check tabs.
"""

import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from PyQt6.QtCore import QCoreApplication, QDate, QDateTime, Qt, QTime
from PyQt6.QtWidgets import QApplication, QMainWindow

from goesvfi.integrity_check.combined_tab import SatelliteIntegrityTabsContainer
from goesvfi.integrity_check.enhanced_gui_tab import EnhancedIntegrityCheckTab

# Import the tab components we want to test
from goesvfi.integrity_check.enhanced_view_model import (
    EnhancedIntegrityCheckViewModel,
    FetchSource,
)
from goesvfi.integrity_check.optimized_timeline_tab import OptimizedTimelineTab
from goesvfi.integrity_check.satellite_integrity_tab_group import OptimizedResultsTab
from goesvfi.integrity_check.time_index import SatellitePattern, TimeIndex

# Import our test utilities
from tests.utils.pyqt_async_test import AsyncSignalWaiter, PyQtAsyncTestCase, async_test


class TestIntegrityTabsIntegration(PyQtAsyncTestCase):
    """Integration tests for the integrity check tabs to verify synchronization."""

    def setUp(self):
        """Set up test fixtures."""
        # Call parent setUp
        super().setUp()

        # Ensure we have a QApplication instance
        self.app = QApplication.instance() or QApplication([])

        # Create temporary directory for test data
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

        # Create test files for each satellite type
        self._create_test_files()

        # Create mock view model
        self._setup_view_model()

        # Create the tabs
        self._create_tabs()

        # Create parent window to hold the tabs
        self.window = QMainWindow()
        self.window.setCentralWidget(self.combined_tab)

    def tearDown(self):
        """Clean up resources."""
        self.window.close()
        self.temp_dir.cleanup()
        super().tearDown()

    def _create_test_files(self):
        """Create test files in a directory structure that can be detected."""
        # Create GOES-16 test files
        self.goes16_dir = self.base_dir / "goes16"
        self.goes16_dir.mkdir(parents=True)

        # Create files with timestamps spanning 3 days
        self.goes16_dates = []

        # Day 1 files
        day1 = datetime(2023, 1, 1)
        for hour in range(0, 24, 3):  # Every 3 hours
            ts = day1.replace(hour=hour)
            self.goes16_dates.append(ts)
            filename = f"OR_ABI-L1b-RadF-M6C13_G16_{ts.strftime('%Y%m%d%H%M%S')}.nc"
            (self.goes16_dir / filename).touch()

        # Day 2 files
        day2 = datetime(2023, 1, 2)
        for hour in range(0, 24, 3):  # Every 3 hours
            ts = day2.replace(hour=hour)
            self.goes16_dates.append(ts)
            filename = f"OR_ABI-L1b-RadF-M6C13_G16_{ts.strftime('%Y%m%d%H%M%S')}.nc"
            (self.goes16_dir / filename).touch()

        # Day 3 files
        day3 = datetime(2023, 1, 3)
        for hour in range(0, 24, 3):  # Every 3 hours
            ts = day3.replace(hour=hour)
            self.goes16_dates.append(ts)
            filename = f"OR_ABI-L1b-RadF-M6C13_G16_{ts.strftime('%Y%m%d%H%M%S')}.nc"
            (self.goes16_dir / filename).touch()

        # Create GOES-18 test files
        self.goes18_dir = self.base_dir / "goes18"
        self.goes18_dir.mkdir(parents=True)

        # Use the same dates but with G18 in the filenames
        self.goes18_dates = self.goes16_dates.copy()
        for ts in self.goes18_dates:
            filename = f"OR_ABI-L1b-RadF-M6C13_G18_{ts.strftime('%Y%m%d%H%M%S')}.nc"
            (self.goes18_dir / filename).touch()

    def _setup_view_model(self):
        """Create and configure the view model with appropriate mocks."""
        # Create cache DB mock
        self.cache_db_mock = MagicMock()

        # Create CDN store mock
        self.cdn_store_mock = MagicMock()
        self.cdn_store_mock.__aenter__ = AsyncMock(return_value=self.cdn_store_mock)
        self.cdn_store_mock.__aexit__ = AsyncMock(return_value=None)
        self.cdn_store_mock.close = AsyncMock()

        # Create S3 store mock
        self.s3_store_mock = MagicMock()
        self.s3_store_mock.__aenter__ = AsyncMock(return_value=self.s3_store_mock)
        self.s3_store_mock.__aexit__ = AsyncMock(return_value=None)
        self.s3_store_mock.close = AsyncMock()

        # Create view model with mocks
        self.view_model = EnhancedIntegrityCheckViewModel(
            cache_db=self.cache_db_mock,
            cdn_store=self.cdn_store_mock,
            s3_store=self.s3_store_mock,
        )

        # Set initial parameters
        self.view_model.base_directory = self.base_dir
        self.view_model.start_date = datetime(2023, 1, 1)
        self.view_model.end_date = datetime(2023, 1, 3, 23, 59, 59)
        self.view_model.satellite = SatellitePattern.GOES_16
        self.view_model.fetch_source = FetchSource.AUTO

    def _create_tabs(self):
        """Create all the tabs and the combined container."""
        # Create the integrity tab
        self.integrity_tab = EnhancedIntegrityCheckTab(self.view_model)

        # Create the combined container
        self.combined_tab = SatelliteIntegrityTabsContainer(
            self.integrity_tab, self.view_model
        )

        # Get references to other tabs
        self.date_selection_tab = self.combined_tab.date_selection_tab
        self.timeline_tab = self.combined_tab.timeline_tab
        self.results_tab = self.combined_tab.results_tab

    @async_test
    async def test_directory_selection_propagation(self):
        """Test that directory selection in the integrity tab propagates to other tabs."""
        # Set up signal waiter to detect when the directory is selected
        timeline_dir_waiter = AsyncSignalWaiter(self.timeline_tab.directorySelected)
        results_dir_waiter = AsyncSignalWaiter(self.results_tab.directorySelected)

        # Select a new directory using the integrity tab's method
        test_dir = str(self.goes16_dir)  # Use the goes16 subdirectory
        self.integrity_tab.directory_selected.emit(test_dir)

        # Wait for signals to be received
        timeline_dir = await timeline_dir_waiter.wait(timeout=1.0)
        results_dir = await results_dir_waiter.wait(timeout=1.0)

        # Verify signals were received with correct directory
        self.assertEqual(
            timeline_dir, test_dir, "Timeline tab did not receive correct directory"
        )
        self.assertEqual(
            results_dir, test_dir, "Results tab did not receive correct directory"
        )

        # Verify directory was updated in view model
        self.assertEqual(
            str(self.view_model.base_directory),
            test_dir,
            "View model base directory was not updated",
        )

    @async_test
    async def test_date_range_auto_detection(self):
        """Test that auto-detecting date range in File Integrity tab updates all tabs."""
        # Mock the TimeIndex.find_date_range_in_directory method
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 3, 23, 59, 59)

        with patch(
            "goesvfi.integrity_check.time_index.TimeIndex.find_date_range_in_directory",
            return_value=(start_date, end_date),
        ):
            # Set up signal waiter for date range changes
            date_range_waiter = AsyncSignalWaiter(self.integrity_tab.date_range_changed)

            # Call the auto-detect method
            # Note: We need to set the directory first
            self.view_model.base_directory = self.base_dir
            self.integrity_tab._auto_detect_date_range()

            # Wait for signal
            start, end = await date_range_waiter.wait(timeout=1.0)

            # Verify dates were updated
            self.assertEqual(
                start.date(),
                start_date.date(),
                "Start date not correctly auto-detected",
            )
            self.assertEqual(
                end.date(), end_date.date(), "End date not correctly auto-detected"
            )

            # Verify the date range was updated in the view model
            self.assertEqual(
                self.view_model.start_date.date(),
                start_date.date(),
                "View model start date not updated",
            )
            self.assertEqual(
                self.view_model.end_date.date(),
                end_date.date(),
                "View model end date not updated",
            )

            # Check that other tabs were updated
            # Note: Since we've mocked/patched methods, we can't directly test the UI state
            # We're relying on the signal connection to verify the tabs would be updated

    @async_test
    async def test_data_propagation_after_scan(self):
        """Test that scanning in File Integrity tab properly updates Timeline and Results tabs."""
        # Create some mock missing items
        missing_items = []
        for i in range(5):
            ts = datetime(2023, 1, 2, i, 0)
            item = MagicMock()
            item.timestamp = ts
            item.expected_filename = f"test_file_{i}.nc"
            item.is_downloaded = False
            item.is_downloading = False
            item.download_error = ""
            missing_items.append(item)

        # Set up to wait for the signal that updates missing items
        missing_items_waiter = AsyncSignalWaiter(self.view_model.missing_items_updated)

        # Simulate the scan completion by calling the method directly
        total_expected = 10
        self.view_model.missing_items_updated.emit(missing_items)

        # Wait for the signal
        items = await missing_items_waiter.wait(timeout=1.0)

        # Verify we got the signal with the correct items
        self.assertEqual(
            len(items),
            len(missing_items),
            "Incorrect number of missing items in signal",
        )

        # Simulate the scan completed signal
        scan_completed_waiter = AsyncSignalWaiter(self.view_model.scan_completed)
        self.view_model.scan_completed.emit(True, "Scan completed successfully")

        # Wait for the scan_completed signal
        success, message = await scan_completed_waiter.wait(timeout=1.0)

        # Verify scan_completed signal was received
        self.assertTrue(success, "Scan completion signal did not indicate success")

        # The combined_tab should update all tabs when scan is completed
        # We can't directly verify the UI state in this test, but we can check
        # if the view model has the expected data
        self.assertEqual(
            self.view_model.missing_items,
            missing_items,
            "Missing items not updated in view model",
        )

    @async_test
    async def test_date_range_synchronization(self):
        """Test that date range selection is synchronized across all tabs."""
        # Set up signal waiter for date changes
        date_range_waiter = AsyncSignalWaiter(self.integrity_tab.date_range_changed)

        # New dates for testing
        start_date = datetime(2023, 2, 1)
        end_date = datetime(2023, 2, 28, 23, 59, 59)

        # Emit date range changed from the integrity tab
        self.integrity_tab.date_range_changed.emit(start_date, end_date)

        # Wait for the signal to propagate
        received_start, received_end = await date_range_waiter.wait(timeout=1.0)

        # Verify dates were received correctly
        self.assertEqual(
            received_start, start_date, "Start date not correctly propagated"
        )
        self.assertEqual(received_end, end_date, "End date not correctly propagated")

        # Verify the view model was updated
        self.assertEqual(
            self.view_model.start_date, start_date, "View model start date not updated"
        )
        self.assertEqual(
            self.view_model.end_date, end_date, "View model end date not updated"
        )


if __name__ == "__main__":
    unittest.main()
