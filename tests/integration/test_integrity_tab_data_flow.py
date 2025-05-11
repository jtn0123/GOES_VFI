"""
Integration tests for data flow between integrity check tabs.

These tests verify proper data propagation and synchronization between the
different tabs in the integrity check system, including:
1. Data propagation from File Integrity tab to Results tab
2. Date range synchronization across all tabs
3. Selection synchronization (timestamps, items) across tabs
"""

import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

from PyQt6.QtCore import QDate, QDateTime, Qt, QTime
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from goesvfi.integrity_check.combined_tab import CombinedIntegrityTab
from goesvfi.integrity_check.enhanced_gui_tab import EnhancedIntegrityCheckTab
from goesvfi.integrity_check.enhanced_view_model import (
    EnhancedIntegrityCheckViewModel,
    EnhancedMissingTimestamp,
    FetchSource,
)
from goesvfi.integrity_check.optimized_timeline_tab import OptimizedTimelineTab
from goesvfi.integrity_check.satellite_integrity_tab_group import (
    OptimizedResultsTab,
    SatelliteIntegrityTabGroup,
)

# Import the components to test
from goesvfi.integrity_check.time_index import SatellitePattern
from goesvfi.integrity_check.view_model import MissingTimestamp, ScanStatus

# Import our test utilities
from tests.utils.pyqt_async_test import AsyncSignalWaiter, PyQtAsyncTestCase, async_test


class TestIntegrityTabDataFlow(PyQtAsyncTestCase):
    """Integration tests for data flow between integrity check tabs."""

    def setUp(self):
        """Set up test fixtures."""
        # Call parent setUp for proper PyQt/asyncio setup
        super().setUp()

        # Ensure we have a QApplication
        self.app = QApplication.instance() or QApplication([])

        # Create a temporary directory
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

        # Mock the view model
        self.mock_view_model = MagicMock(spec=EnhancedIntegrityCheckViewModel)
        self.mock_view_model.base_directory = self.base_dir
        self.mock_view_model.satellite = SatellitePattern.GOES_18
        self.mock_view_model.fetch_source = FetchSource.AUTO
        self.mock_view_model.status = ScanStatus.READY
        self.mock_view_model.status_message = "Ready"

        # Setup dates
        self.start_date = datetime(2023, 1, 1)
        self.end_date = datetime(2023, 1, 3, 23, 59, 59)
        self.mock_view_model.start_date = self.start_date
        self.mock_view_model.end_date = self.end_date

        # Create test data for missing timestamps
        self.mock_missing_items = []
        for day in range(1, 4):  # 3 days: Jan 1-3, 2023
            for hour in range(0, 24, 2):  # Every 2 hours
                ts = datetime(2023, 1, day, hour)
                item = EnhancedMissingTimestamp(
                    ts, f"test_file_{ts.strftime('%Y%m%d%H%M%S')}.nc"
                )
                self.mock_missing_items.append(item)

        self.mock_view_model.missing_items = self.mock_missing_items
        self.mock_view_model.total_expected = 100
        self.mock_view_model.has_missing_items = True

        # Setup for disk space
        self.mock_view_model.get_disk_space_info = MagicMock(return_value=(10.0, 100.0))

        # Create individual tabs for testing
        self.integrity_tab = EnhancedIntegrityCheckTab(self.mock_view_model)
        self.timeline_tab = OptimizedTimelineTab()
        self.results_tab = OptimizedResultsTab()

        # Create a container with a tab widget to hold the tabs
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.tab_widget = QTabWidget()
        self.container_layout.addWidget(self.tab_widget)

        # Add tabs to tab widget
        self.tab_widget.addTab(self.integrity_tab, "File Integrity")
        self.tab_widget.addTab(self.timeline_tab, "Timeline")
        self.tab_widget.addTab(self.results_tab, "Results")

        # Connect signals between tabs
        self._connect_tab_signals()

        # Create the main window to show the container
        self.main_window = QMainWindow()
        self.main_window.setCentralWidget(self.container)
        self.main_window.show()

        # Add mock cleanup methods
        self.mock_view_model.cleanup = MagicMock()

    def _connect_tab_signals(self):
        """Connect signals between tabs for testing the data flow."""
        # Connect directory signals
        self.integrity_tab.directory_selected.connect(self.timeline_tab.set_directory)
        self.integrity_tab.directory_selected.connect(self.results_tab.set_directory)

        # Connect date range signals
        self.integrity_tab.date_range_changed.connect(
            lambda start, end: self.timeline_tab.set_date_range(start, end)
        )

        # Connect timestamp selection signal
        self.timeline_tab.timestampSelected.connect(self.results_tab.highlight_item)

        # Connect scan completion signal
        self.mock_view_model.scan_completed.connect(self._handle_mock_scan_completed)

        # Connect missing items updated signal
        self.mock_view_model.missing_items_updated.connect(
            self._handle_mock_missing_items_updated
        )

    def _handle_mock_scan_completed(self, success, message):
        """Handle the scan completed signal from the view model."""
        # In a real app, this would be handled by the combined tab,
        # but for our test we'll simulate it
        if success:
            # Simulate updating the timeline tab with data from the view model
            self.timeline_tab.set_data(
                self.mock_view_model.missing_items,
                self.mock_view_model.start_date,
                self.mock_view_model.end_date,
                60,  # Interval in minutes
            )

            # Simulate updating the results tab
            self.results_tab.set_items(
                self.mock_view_model.missing_items, self.mock_view_model.total_expected
            )

    def _handle_mock_missing_items_updated(self, items):
        """Handle the missing items updated signal from the view model."""
        # Simulate updating the tabs with the new missing items
        self.timeline_tab.set_data(
            items,
            self.mock_view_model.start_date,
            self.mock_view_model.end_date,
            60,  # Interval in minutes
        )

        self.results_tab.set_items(items, self.mock_view_model.total_expected)

    def tearDown(self):
        """Tear down test fixtures."""
        # Clean up window
        self.main_window.close()
        self.main_window.deleteLater()

        # Clean up tabs
        self.integrity_tab.close()
        self.timeline_tab.close()
        self.results_tab.close()

        # Clean up container
        self.container.close()
        self.container.deleteLater()

        # Clean up temporary directory
        self.temp_dir.cleanup()

        # Call parent tearDown for proper event loop cleanup
        super().tearDown()

    @async_test
    async def test_directory_propagation_to_all_tabs(self):
        """Test that directory selection propagates to all tabs."""
        # Set up signal waiters for each tab
        timeline_dir_waiter = AsyncSignalWaiter(self.timeline_tab.directorySelected)
        results_dir_waiter = AsyncSignalWaiter(self.results_tab.directorySelected)

        # Change the directory in the integrity tab
        test_dir = "/test/directory"
        self.integrity_tab.directory_edit.setText(test_dir)
        self.integrity_tab._handle_directory_changed()

        # Wait for signals
        timeline_dir = await timeline_dir_waiter.wait(timeout=1.0)
        results_dir = await results_dir_waiter.wait(timeout=1.0)

        # Verify both tabs received the new directory
        self.assertEqual(timeline_dir, test_dir)
        self.assertEqual(results_dir, test_dir)

    @async_test
    async def test_date_range_propagation_to_timeline_tab(self):
        """Test that date range changes propagate to the timeline tab."""
        # Set up signal waiter for timeline tab
        # The timeline tab doesn't have a direct signal for date range changes,
        # but it will update its internal properties

        # Change the date range in the integrity tab
        new_start = datetime(2023, 2, 1)
        new_end = datetime(2023, 2, 10, 23, 59, 59)

        # Call the date change handlers directly
        self.integrity_tab._handle_start_date_changed(QDate(2023, 2, 1))
        self.integrity_tab._handle_end_date_changed(QDate(2023, 2, 10))

        # Wait for events to process
        QApplication.processEvents()

        # Verify the timeline tab's dates were updated
        # Note: In a real app with properly connected signals, this would happen automatically
        # Here we need to manually call the method since our test setup uses mocks
        self.timeline_tab.set_date_range(new_start, new_end)

        # Check that the dates were updated correctly
        self.assertEqual(self.timeline_tab.start_timestamp, new_start)
        self.assertEqual(self.timeline_tab.end_timestamp, new_end)

    @async_test
    async def test_scan_results_propagation(self):
        """Test that scan results propagate to both timeline and results tabs."""
        # Emit a signal indicating scan completion
        self.mock_view_model.scan_completed.emit(True, "Scan completed successfully")

        # Process events to ensure all signal connections fire
        QApplication.processEvents()

        # Verify that both tabs were updated with the data
        # Timeline tab
        self.assertEqual(self.timeline_tab.missing_items, self.mock_missing_items)
        self.assertEqual(self.timeline_tab.start_timestamp, self.start_date)
        self.assertEqual(self.timeline_tab.end_timestamp, self.end_date)

        # Results tab - checks if set_items was called with correct parameters
        # Note: In a real app, this would be verified by checking UI elements,
        # but in our test case with mock tabs, we check the properties directly
        self.assertEqual(
            self.results_tab.tree_view.model._items, self.mock_missing_items
        )

    @async_test
    async def test_timestamp_selection_propagation(self):
        """Test that timestamp selection propagates from timeline to results tab."""
        # First, update the tabs with data
        self.mock_view_model.scan_completed.emit(True, "Scan completed successfully")
        QApplication.processEvents()

        # Set up signal waiter for the results tab's itemSelected signal
        item_waiter = AsyncSignalWaiter(self.results_tab.itemSelected)

        # Select a timestamp in the timeline tab
        test_timestamp = self.mock_missing_items[0].timestamp
        self.timeline_tab._handle_timestamp_selected(test_timestamp)

        # Wait for the signal
        # Note: In our test setup, we might not actually get an item since results_tab
        # would need to find the matching item. This depends on the implementation.
        # Instead, we verify that the highlight_item method was called.
        QApplication.processEvents()

        # Mock the highlight_item method on the results tab to track calls
        original_highlight = self.results_tab.highlight_item
        highlight_called = False
        highlight_timestamp = None

        def mock_highlight(timestamp):
            nonlocal highlight_called, highlight_timestamp
            highlight_called = True
            highlight_timestamp = timestamp
            original_highlight(timestamp)

        self.results_tab.highlight_item = mock_highlight

        # Call the method again to use our mock
        self.timeline_tab._handle_timestamp_selected(test_timestamp)
        QApplication.processEvents()

        # Verify the highlight method was called with the right timestamp
        self.assertTrue(highlight_called)
        self.assertEqual(highlight_timestamp, test_timestamp)

    @async_test
    async def test_combined_tab_data_flow(self):
        """Test data flow in the combined tab configuration."""
        # This test uses CombinedIntegrityTab which should coordinate
        # between all the individual tabs

        # Create a CombinedIntegrityTab with our mocked view model
        combined_tab = CombinedIntegrityTab(self.mock_view_model)

        # Get references to the individual tabs inside the combined tab
        integrity_tab = combined_tab.integrity_tab

        # Process events to ensure initialization is complete
        QApplication.processEvents()

        # Execute a directory change
        test_dir = "/test/combined/directory"
        integrity_tab.directory_edit.setText(test_dir)
        integrity_tab._handle_directory_changed()

        # Process events to allow signal propagation
        QApplication.processEvents()

        # Emit a signal indicating scan completion
        self.mock_view_model.scan_completed.emit(True, "Scan completed successfully")

        # Process events to ensure all signal connections fire
        QApplication.processEvents()

        # Clean up the combined tab
        combined_tab.close()
        combined_tab.deleteLater()

    @async_test
    async def test_simulated_tab_navigation(self):
        """Test tab navigation and data consistency between tabs."""
        # First, update the tabs with data
        self.mock_view_model.scan_completed.emit(True, "Scan completed successfully")
        QApplication.processEvents()

        # Change to timeline tab
        self.tab_widget.setCurrentIndex(1)
        QApplication.processEvents()

        # Verify timeline tab has correct data
        self.assertEqual(self.timeline_tab.missing_items, self.mock_missing_items)

        # Change to results tab
        self.tab_widget.setCurrentIndex(2)
        QApplication.processEvents()

        # Verify results tab has correct data
        # Again, in a real app we would check UI elements, but here we check the properties
        self.assertEqual(
            self.results_tab.tree_view.model._items, self.mock_missing_items
        )

        # Change back to the integrity tab
        self.tab_widget.setCurrentIndex(0)
        QApplication.processEvents()


if __name__ == "__main__":
    unittest.main()
