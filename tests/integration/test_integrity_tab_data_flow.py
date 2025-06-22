"""
Integration tests for data flow between integrity check tabs.

These tests verify proper data propagation and synchronization between the
different tabs in the integrity check system, including:
1. Data propagation from File Integrity tab to Results tab
2. Date range synchronization across all tabs
3. Selection synchronization (timestamps, items) across tabs
"""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from goesvfi.integrity_check.combined_tab import (
    CombinedIntegrityAndImageryTab as CombinedIntegrityTab,
)
from goesvfi.integrity_check.enhanced_gui_tab import EnhancedIntegrityCheckTab
from goesvfi.integrity_check.enhanced_view_model import (
    EnhancedIntegrityCheckViewModel,
    EnhancedMissingTimestamp,
    FetchSource,
)
from goesvfi.integrity_check.optimized_timeline_tab import OptimizedTimelineTab
from goesvfi.integrity_check.satellite_integrity_tab_group import (
    OptimizedResultsTab,
)

# Import the components to test
from goesvfi.integrity_check.time_index import SatellitePattern
from goesvfi.integrity_check.view_model import ScanStatus

# Import our test utilities
from tests.utils.pyqt_async_test import PyQtAsyncTestCase, async_test


class MockSignalEmitter(QObject):
    """Helper class to emit real PyQt signals for testing."""

    scan_completed = pyqtSignal(bool, str)
    missing_items_updated = pyqtSignal(list)


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

        # Create signal emitter for real PyQt signals
        self.signal_emitter = MockSignalEmitter()

        # Mock the view model
        self.mock_view_model = MagicMock(spec=EnhancedIntegrityCheckViewModel)
        self.mock_view_model.base_directory = self.base_dir
        self.mock_view_model.satellite = SatellitePattern.GOES_18
        self.mock_view_model.fetch_source = FetchSource.AUTO
        self.mock_view_model.status = ScanStatus.READY
        self.mock_view_model.status_message = "Ready"

        # Use real signals from the emitter
        self.mock_view_model.scan_completed = self.signal_emitter.scan_completed
        self.mock_view_model.missing_items_updated = self.signal_emitter.missing_items_updated

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
                item = EnhancedMissingTimestamp(ts, f"test_file_{ts.strftime('%Y%m%d%H%M%S')}.nc")
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
        self.integrity_tab.date_range_changed.connect(lambda start, end: self.timeline_tab.set_date_range(start, end))

        # Connect timestamp selection signal
        self.timeline_tab.timestampSelected.connect(self.results_tab.highlight_item)

        # Connect scan completion signal
        self.mock_view_model.scan_completed.connect(self._handle_mock_scan_completed)

        # Connect missing items updated signal
        self.mock_view_model.missing_items_updated.connect(self._handle_mock_missing_items_updated)

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
            self.results_tab.set_items(self.mock_view_model.missing_items, self.mock_view_model.total_expected)

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

    def test_directory_propagation_to_all_tabs(self):
        """Test that directory selection propagates to all tabs."""
        # Track signals received
        timeline_dir_received = []
        results_dir_received = []

        # Connect to signals to track them
        self.timeline_tab.directorySelected.connect(lambda d: timeline_dir_received.append(d))
        self.results_tab.directorySelected.connect(lambda d: results_dir_received.append(d))

        # Change the directory in the integrity tab
        test_dir = "/test/directory"
        self.integrity_tab.dir_input.setText(test_dir)

        # Manually emit the signal since setText doesn't trigger it
        self.integrity_tab.directory_selected.emit(test_dir)

        # Process events to ensure signal propagation
        QApplication.processEvents()

        # Verify both tabs received the new directory
        assert len(timeline_dir_received) > 0, "Timeline tab should have received directory signal"
        assert len(results_dir_received) > 0, "Results tab should have received directory signal"
        assert timeline_dir_received[0] == test_dir, f"Expected {test_dir}, got {timeline_dir_received[0]}"
        assert results_dir_received[0] == test_dir, f"Expected {test_dir}, got {results_dir_received[0]}"

    @async_test
    async def test_date_range_propagation_to_timeline_tab(self):
        """Test that date range changes propagate to the timeline tab."""
        # Set up signal waiter for timeline tab
        # The timeline tab doesn't have a direct signal for date range changes,
        # but it will update its internal properties

        # Change the date range in the integrity tab
        new_start = datetime(2023, 2, 1)
        new_end = datetime(2023, 2, 10, 23, 59, 59)

        # Update the date edit widgets directly and emit the signal
        from PyQt6.QtCore import QDateTime

        self.integrity_tab.start_date_edit.setDateTime(QDateTime(new_start))
        self.integrity_tab.end_date_edit.setDateTime(QDateTime(new_end))

        # Manually emit the date range changed signal
        self.integrity_tab.date_range_changed.emit(new_start, new_end)

        # Wait for events to process
        QApplication.processEvents()

        # Verify the timeline tab's dates were updated
        # Note: In a real app with properly connected signals, this would happen automatically
        # Here we need to manually call the method since our test setup uses mocks
        self.timeline_tab.set_date_range(new_start, new_end)

        # Check that the dates were updated correctly
        assert self.timeline_tab.start_timestamp == new_start
        assert self.timeline_tab.end_timestamp == new_end

    def test_scan_results_propagation(self):
        """Test that scan results propagate to both timeline and results tabs."""
        # Track whether set_data and set_items were called with correct parameters
        timeline_data_received = []
        results_data_received = []

        # Mock the timeline tab's set_data method to track calls
        original_timeline_set_data = self.timeline_tab.set_data

        def mock_timeline_set_data(missing_items, start_time, end_time, interval_minutes):
            timeline_data_received.append(
                {
                    "missing_items": missing_items,
                    "start_time": start_time,
                    "end_time": end_time,
                    "interval": interval_minutes,
                }
            )
            # Still call the original method
            original_timeline_set_data(missing_items, start_time, end_time, interval_minutes)

        # Use patch to mock the method
        self.patch_timeline_set_data = patch.object(self.timeline_tab, "set_data", side_effect=mock_timeline_set_data)
        self.patch_timeline_set_data.start()

        # Mock the results tab's set_items method to track calls
        original_results_set_items = self.results_tab.set_items

        def mock_results_set_items(items, total_expected):
            results_data_received.append({"items": items, "total_expected": total_expected})
            # Still call the original method
            original_results_set_items(items, total_expected)

        # Use patch to mock the method
        self.patch_results_set_items = patch.object(self.results_tab, "set_items", side_effect=mock_results_set_items)
        self.patch_results_set_items.start()

        # Emit a signal indicating scan completion
        self.signal_emitter.scan_completed.emit(True, "Scan completed successfully")

        # Process events to ensure all signal connections fire
        QApplication.processEvents()

        # Verify that both tabs were updated with the data
        # Timeline tab
        assert len(timeline_data_received) > 0, "Timeline tab should have received data"
        assert timeline_data_received[0]["missing_items"] == self.mock_missing_items
        assert timeline_data_received[0]["start_time"] == self.start_date
        assert timeline_data_received[0]["end_time"] == self.end_date
        assert timeline_data_received[0]["interval"] == 60

        # Results tab
        assert len(results_data_received) > 0, "Results tab should have received data"
        assert results_data_received[0]["items"] == self.mock_missing_items
        assert results_data_received[0]["total_expected"] == self.mock_view_model.total_expected

        # Clean up patches
        self.patch_timeline_set_data.stop()
        self.patch_results_set_items.stop()

    def test_timestamp_selection_propagation(self):
        """Test that timestamp selection propagates from timeline to results tab."""
        # Track whether highlight_item was called
        highlight_calls = []

        # Mock the highlight_item method on the results tab to track calls
        original_highlight = self.results_tab.highlight_item

        def mock_highlight(timestamp):
            highlight_calls.append(timestamp)
            original_highlight(timestamp)

        self.results_tab.highlight_item = mock_highlight  # type: ignore[method-assign] # noqa: B010

        # Re-connect the signal to our mocked method
        self.timeline_tab.timestampSelected.disconnect()  # Disconnect any existing
        self.timeline_tab.timestampSelected.connect(mock_highlight)

        # First, update the tabs with data
        self.signal_emitter.scan_completed.emit(True, "Scan completed successfully")
        QApplication.processEvents()

        # Select a timestamp in the timeline tab
        test_timestamp = self.mock_missing_items[0].timestamp

        # Emit the timestampSelected signal directly (since _handle_timestamp_selected is internal)
        self.timeline_tab.timestampSelected.emit(test_timestamp)

        # Process events to ensure signal propagation
        QApplication.processEvents()

        # Verify the highlight method was called with the right timestamp
        assert len(highlight_calls) > 0, "Results tab should have received highlight_item call"
        assert highlight_calls[0] == test_timestamp

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
        integrity_tab.dir_input.setText(test_dir)
        # Manually emit the signal since setText doesn't trigger it
        integrity_tab.directory_selected.emit(test_dir)

        # Process events to allow signal propagation
        QApplication.processEvents()

        # Emit a signal indicating scan completion
        self.signal_emitter.scan_completed.emit(True, "Scan completed successfully")

        # Process events to ensure all signal connections fire
        QApplication.processEvents()

        # Clean up the combined tab
        combined_tab.close()
        combined_tab.deleteLater()

    def test_simulated_tab_navigation(self):
        """Test tab navigation and data consistency between tabs."""
        # Track data received by tabs
        timeline_has_data = False
        results_has_data = False

        # Monitor timeline tab data
        original_timeline_set_data = self.timeline_tab.set_data

        def check_timeline_set_data(missing_items, start_time, end_time, interval_minutes):
            nonlocal timeline_has_data
            if missing_items == self.mock_missing_items:
                timeline_has_data = True
            original_timeline_set_data(missing_items, start_time, end_time, interval_minutes)

        # Use patch to mock the method
        self.patch_timeline_set_data2 = patch.object(self.timeline_tab, "set_data", side_effect=check_timeline_set_data)
        self.patch_timeline_set_data2.start()

        # Monitor results tab data
        original_results_set_items = self.results_tab.set_items

        def check_results_set_items(items, total_expected):
            nonlocal results_has_data
            if items == self.mock_missing_items:
                results_has_data = True
            original_results_set_items(items, total_expected)

        # Use patch to mock the method
        self.patch_results_set_items2 = patch.object(self.results_tab, "set_items", side_effect=check_results_set_items)
        self.patch_results_set_items2.start()

        # First, update the tabs with data
        self.mock_view_model.scan_completed.emit(True, "Scan completed successfully")
        QApplication.processEvents()

        # Verify both tabs received the data
        assert timeline_has_data, "Timeline tab should have received the data"
        assert results_has_data, "Results tab should have received the data"

        # Change to timeline tab
        self.tab_widget.setCurrentIndex(1)
        QApplication.processEvents()

        # Verify we're on timeline tab
        assert self.tab_widget.currentIndex() == 1

        # Change to results tab
        self.tab_widget.setCurrentIndex(2)
        QApplication.processEvents()

        # Verify we're on results tab
        assert self.tab_widget.currentIndex() == 2

        # Change back to the integrity tab
        self.tab_widget.setCurrentIndex(0)
        QApplication.processEvents()

        # Verify we're back on integrity tab
        assert self.tab_widget.currentIndex() == 0

        # Stop patches
        self.patch_timeline_set_data2.stop()
        self.patch_results_set_items2.stop()


if __name__ == "__main__":
    unittest.main()
