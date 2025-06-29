"""
Unit tests for the OptimizedTimelineTab component to verify functionality.

These tests focus on the timeline visualization tab's ability to:
1. Receive and display data
2. Synchronize with other tabs
3. Handle user interactions properly
"""

from datetime import UTC, datetime
import unittest

from PyQt6.QtWidgets import QApplication, QMainWindow

# Import the components to test
from goesvfi.integrity_check.optimized_timeline_tab import OptimizedTimelineTab
from goesvfi.integrity_check.view_model import MissingTimestamp

# Import our test utilities
from tests.utils.pyqt_async_test import AsyncSignalWaiter, PyQtAsyncTestCase, async_test


class TestOptimizedTimelineTab(PyQtAsyncTestCase):
    """Unit tests for the OptimizedTimelineTab."""

    def setUp(self) -> None:
        """Set up the test environment."""
        super().setUp()

        # Create application instance
        self.app = QApplication.instance() or QApplication([])

        # Create the tab
        self.tab = OptimizedTimelineTab()

        # Create a window to hold the tab
        self.window = QMainWindow()
        self.window.setCentralWidget(self.tab)
        self.window.show()

        # Create temporary data for tests
        self._create_test_data()

    def tearDown(self) -> None:
        """Clean up resources."""
        self.window.close()
        super().tearDown()

    def _create_test_data(self) -> None:
        """Create test data for the timeline visualization."""
        self.start_date = datetime(2023, 1, 1, tzinfo=UTC)
        self.end_date = datetime(2023, 1, 3, 23, 59, 59, tzinfo=UTC)

        # Create a list of mock missing timestamps
        self.missing_items = []

        # Day 1: Some missing, some available
        day1 = datetime(2023, 1, 1, tzinfo=UTC)
        for hour in range(0, 24, 2):
            # Create a missing timestamp every 2 hours
            ts = day1.replace(hour=hour)
            item = MissingTimestamp(ts, f"test_file_{ts.strftime('%Y%m%d%H%M%S')}.nc")

            # Make some downloaded, some missing
            if hour % 4 == 0:
                item.is_downloaded = True
                item.local_path = f"/path/to/{item.expected_filename}"

            self.missing_items.append(item)

        # Day 2: All missing
        day2 = datetime(2023, 1, 2, tzinfo=UTC)
        for hour in range(0, 24, 2):
            ts = day2.replace(hour=hour)
            item = MissingTimestamp(ts, f"test_file_{ts.strftime('%Y%m%d%H%M%S')}.nc")
            self.missing_items.append(item)

        # Day 3: None missing (will be represented as gaps in the visualization)

        # Set the interval to 2 hours
        self.interval_minutes = 120

    @async_test
    async def test_set_data(self) -> None:
        """Test that the set_data method properly sets data and updates visualization."""
        # Set the data
        self.tab.set_data(self.missing_items, self.start_date, self.end_date, self.interval_minutes)

        # Process events to ensure UI updates
        QApplication.processEvents()

        # Verify the tab has stored the data
        assert self.tab.start_timestamp == self.start_date, "Start timestamp not set correctly"
        assert self.tab.end_timestamp == self.end_date, "End timestamp not set correctly"
        assert self.tab.missing_items == self.missing_items, "Missing items not set correctly"
        assert self.tab.interval_minutes == self.interval_minutes, "Interval minutes not set correctly"

    @async_test
    async def test_set_date_range(self) -> None:
        """Test that set_date_range updates the visualization without changing the data."""
        # First set initial data
        self.tab.set_data(self.missing_items, self.start_date, self.end_date, self.interval_minutes)

        # Process events
        QApplication.processEvents()

        # Now change the date range
        new_start = datetime(2023, 1, 2, tzinfo=UTC)  # Day 2 only
        new_end = datetime(2023, 1, 2, 23, 59, 59, tzinfo=UTC)

        # Set the new date range
        self.tab.set_date_range(new_start, new_end)

        # Process events
        QApplication.processEvents()

        # Verify date range was updated
        assert self.tab.start_timestamp == new_start, "Start timestamp not updated correctly"
        assert self.tab.end_timestamp == new_end, "End timestamp not updated correctly"

        # The missing items should not change
        assert self.tab.missing_items == self.missing_items, "Missing items should not change when updating date range"

    @async_test
    async def test_set_directory(self) -> None:
        """Test that set_directory emits the directorySelected signal."""
        # Set up signal waiter
        dir_waiter = AsyncSignalWaiter(self.tab.directorySelected)

        # Set the directory
        test_dir = "/test/directory"
        self.tab.set_directory(test_dir)

        # Wait for the signal
        received_dir = await dir_waiter.wait(timeout=1.0)

        # Verify the signal was emitted with the correct directory
        assert received_dir == test_dir, "Directory signal not emitted with correct directory"

    @async_test
    async def test_timestamp_selection(self) -> None:
        """Test that selecting a timestamp emits the correct signal."""
        # Set up the data first
        self.tab.set_data(self.missing_items, self.start_date, self.end_date, self.interval_minutes)

        # Set up signal waiter
        timestamp_waiter = AsyncSignalWaiter(self.tab.timestampSelected)

        # Simulate selecting a timestamp by calling the handler directly
        test_timestamp = datetime(2023, 1, 1, 12, 0, tzinfo=UTC)
        self.tab._handle_timestamp_selected(test_timestamp)  # noqa: SLF001

        # Wait for the signal
        received_timestamp = await timestamp_waiter.wait(timeout=1.0)

        # Verify the signal was emitted with the correct timestamp
        assert received_timestamp == test_timestamp, "Timestamp signal not emitted with correct timestamp"

        # The selected timestamp should be stored
        assert self.tab.selected_timestamp == test_timestamp, "Selected timestamp not stored correctly"

    @async_test
    async def test_view_switching(self) -> None:
        """Test switching between timeline and calendar views."""
        # Set some data first
        self.tab.set_data(self.missing_items, self.start_date, self.end_date, self.interval_minutes)

        # Process events
        QApplication.processEvents()

        # Initial state should be timeline view (index 0)
        assert self.tab.stack.currentIndex() == 0, "Initial view should be timeline"

        # Switch to calendar view
        self.tab._toggle_visualization(1)  # noqa: SLF001

        # Process events
        QApplication.processEvents()

        # Verify the view was switched
        assert self.tab.stack.currentIndex() == 1, "View not switched to calendar"

        # The view buttons should reflect the current state
        assert not self.tab.view_timeline_btn.isChecked(), "Timeline button should not be checked"
        assert self.tab.view_calendar_btn.isChecked(), "Calendar button should be checked"

        # Switch back to timeline view
        self.tab._toggle_visualization(0)  # noqa: SLF001

        # Process events
        QApplication.processEvents()

        # Verify the view was switched back
        assert self.tab.stack.currentIndex() == 0, "View not switched back to timeline"

        # The view buttons should reflect the current state
        assert self.tab.view_timeline_btn.isChecked(), "Timeline button should be checked"
        assert not self.tab.view_calendar_btn.isChecked(), "Calendar button should not be checked"

    @async_test
    async def test_info_panel_update(self) -> None:
        """Test that the info panel is updated when a timestamp is selected."""
        # Set some data first
        self.tab.set_data(self.missing_items, self.start_date, self.end_date, self.interval_minutes)

        # Process events
        QApplication.processEvents()

        # Initial state should be "No item selected"
        assert "No item selected" in self.tab.info_label.text(), "Initial info panel should indicate no selection"

        # Select a timestamp that corresponds to an item
        selected_timestamp = self.missing_items[0].timestamp
        self.tab._handle_timestamp_selected(selected_timestamp)  # noqa: SLF001

        # Process events
        QApplication.processEvents()

        # The info panel should be updated with the item details
        assert "No item selected" not in self.tab.info_label.text(), "Info panel should be updated with selection"

        # The timestamp should be mentioned in the text
        assert selected_timestamp.strftime("%Y-%m-%d") in self.tab.info_label.text(), (
            "Selected timestamp date should appear in info panel"
        )


if __name__ == "__main__":
    unittest.main()
