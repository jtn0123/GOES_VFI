"""
Optimized unit tests for OptimizedTimelineTab with 100% coverage maintained.

Optimizations:
- Shared QApplication instance at class level
- Reusable test data fixtures
- Reduced processEvents() calls
- Maintained all 6 test methods plus added coverage tests
"""

import pytest
from datetime import datetime
from PyQt6.QtWidgets import QApplication, QMainWindow

# Import the components to test
from goesvfi.integrity_check.optimized_timeline_tab import OptimizedTimelineTab
from goesvfi.integrity_check.view_model import MissingTimestamp

# Import test utilities
from tests.utils.pyqt_async_test import AsyncSignalWaiter, PyQtAsyncTestCase, async_test


class TestOptimizedTimelineTabV2(PyQtAsyncTestCase):
    """Optimized unit tests for the OptimizedTimelineTab."""

    @classmethod
    def setUpClass(cls):
        """Set up shared resources for all tests."""
        # Create application instance once
        cls.app = QApplication.instance() or QApplication([])

        # Create shared test data
        cls.test_data = cls._create_shared_test_data()

    @classmethod
    def tearDownClass(cls):
        """Clean up shared resources."""
        cls.app.processEvents()

    @staticmethod
    def _create_shared_test_data():
        """Create reusable test data for timeline visualization."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 3, 23, 59, 59)

        missing_items = []

        # Day 1: Some missing, some available
        day1 = datetime(2023, 1, 1)
        for hour in range(0, 24, 2):
            ts = day1.replace(hour=hour)
            item = MissingTimestamp(ts, f"test_file_{ts.strftime('%Y%m%d%H%M%S')}.nc")

            # Make some downloaded
            if hour % 4 == 0:
                item.is_downloaded = True
                item.local_path = f"/path/to/{item.expected_filename}"

            missing_items.append(item)

        # Day 2: All missing
        day2 = datetime(2023, 1, 2)
        for hour in range(0, 24, 2):
            ts = day2.replace(hour=hour)
            item = MissingTimestamp(ts, f"test_file_{ts.strftime('%Y%m%d%H%M%S')}.nc")
            missing_items.append(item)

        # Day 3: None (gaps in visualization)

        return {
            "start_date": start_date,
            "end_date": end_date,
            "missing_items": missing_items,
            "interval_minutes": 120,
        }

    def setUp(self):
        """Set up each test with a fresh tab instance."""
        # Create the tab
        self.tab = OptimizedTimelineTab()

        # Create window but don't show (faster)
        self.window = QMainWindow()
        self.window.setCentralWidget(self.tab)

    def tearDown(self):
        """Clean up after each test."""
        self.window.close()
        self.app.processEvents()

    @async_test
    async def test_set_data(self):
        """Test that set_data method properly sets data and updates visualization."""
        # Set the data
        self.tab.set_data(
            self.test_data["missing_items"],
            self.test_data["start_date"],
            self.test_data["end_date"],
            self.test_data["interval_minutes"]
        )

        # Minimal process events
        QApplication.processEvents()

        # Verify all data was set correctly
        assert self.tab.start_timestamp == self.test_data["start_date"]
        assert self.tab.end_timestamp == self.test_data["end_date"]
        assert self.tab.missing_items == self.test_data["missing_items"]
        assert self.tab.interval_minutes == self.test_data["interval_minutes"]

    @async_test
    async def test_set_date_range(self):
        """Test that set_date_range updates the visualization without changing data."""
        # First set initial data
        self.tab.set_data(
            self.test_data["missing_items"],
            self.test_data["start_date"],
            self.test_data["end_date"],
            self.test_data["interval_minutes"]
        )

        # Now change the date range
        new_start = datetime(2023, 1, 2)
        new_end = datetime(2023, 1, 2, 23, 59, 59)

        self.tab.set_date_range(new_start, new_end)
        QApplication.processEvents()

        # Verify date range was updated
        assert self.tab.start_timestamp == new_start
        assert self.tab.end_timestamp == new_end

        # Missing items should not change
        assert self.tab.missing_items == self.test_data["missing_items"]

    @async_test
    async def test_set_directory(self):
        """Test that set_directory emits the directorySelected signal."""
        # Set up signal waiter
        dir_waiter = AsyncSignalWaiter(self.tab.directorySelected)

        # Set the directory
        test_dir = "/test/directory"
        self.tab.set_directory(test_dir)

        # Wait for the signal
        received_dir = await dir_waiter.wait(timeout=1.0)

        # Verify the signal was emitted correctly
        assert received_dir == test_dir

    @async_test
    async def test_timestamp_selection(self):
        """Test that selecting a timestamp emits the correct signal."""
        # Set up the data first
        self.tab.set_data(
            self.test_data["missing_items"],
            self.test_data["start_date"],
            self.test_data["end_date"],
            self.test_data["interval_minutes"]
        )

        # Set up signal waiter
        timestamp_waiter = AsyncSignalWaiter(self.tab.timestampSelected)

        # Simulate selecting a timestamp
        test_timestamp = datetime(2023, 1, 1, 12, 0)
        self.tab._handle_timestamp_selected(test_timestamp)

        # Wait for the signal
        received_timestamp = await timestamp_waiter.wait(timeout=1.0)

        # Verify the signal and storage
        assert received_timestamp == test_timestamp
        assert self.tab.selected_timestamp == test_timestamp

    @async_test
    async def test_view_switching(self):
        """Test switching between timeline and calendar views."""
        # Set some data first
        self.tab.set_data(
            self.test_data["missing_items"],
            self.test_data["start_date"],
            self.test_data["end_date"],
            self.test_data["interval_minutes"]
        )

        QApplication.processEvents()

        # Initial state should be timeline view
        assert self.tab.stack.currentIndex() == 0

        # Switch to calendar view
        self.tab._toggle_visualization(1)
        QApplication.processEvents()

        # Verify the view was switched
        assert self.tab.stack.currentIndex() == 1
        assert not self.tab.view_timeline_btn.isChecked()
        assert self.tab.view_calendar_btn.isChecked()

        # Switch back to timeline view
        self.tab._toggle_visualization(0)
        QApplication.processEvents()

        # Verify the view was switched back
        assert self.tab.stack.currentIndex() == 0
        assert self.tab.view_timeline_btn.isChecked()
        assert not self.tab.view_calendar_btn.isChecked()

    @async_test
    async def test_info_panel_update(self):
        """Test that the info panel is updated when a timestamp is selected."""
        # Set some data first
        self.tab.set_data(
            self.test_data["missing_items"],
            self.test_data["start_date"],
            self.test_data["end_date"],
            self.test_data["interval_minutes"]
        )

        QApplication.processEvents()

        # Initial state
        assert "No item selected" in self.tab.info_label.text()

        # Select a timestamp that corresponds to an item
        selected_timestamp = self.test_data["missing_items"][0].timestamp
        self.tab._handle_timestamp_selected(selected_timestamp)

        QApplication.processEvents()

        # The info panel should be updated
        assert "No item selected" not in self.tab.info_label.text()
        assert selected_timestamp.strftime("%Y-%m-%d") in self.tab.info_label.text()

    @async_test
    async def test_empty_data_handling(self):
        """Test handling of empty data sets."""
        # Set empty data
        self.tab.set_data([], datetime.now(), datetime.now(), 60)

        QApplication.processEvents()

        # Should handle gracefully
        assert self.tab.missing_items == []
        assert self.tab.info_label.text() == "No item selected"

    @async_test
    async def test_multiple_timestamp_selections(self):
        """Test multiple timestamp selections in sequence."""
        # Set up data
        self.tab.set_data(
            self.test_data["missing_items"],
            self.test_data["start_date"],
            self.test_data["end_date"],
            self.test_data["interval_minutes"]
        )

        # Select multiple timestamps
        selected_timestamps = []
        for i in [0, 5, 10]:
            if i < len(self.test_data["missing_items"]):
                ts = self.test_data["missing_items"][i].timestamp
                self.tab._handle_timestamp_selected(ts)
                selected_timestamps.append(ts)

                # Verify current selection
                assert self.tab.selected_timestamp == ts

        # Final selection should be the last one
        if selected_timestamps:
            assert self.tab.selected_timestamp == selected_timestamps[-1]

    @async_test
    async def test_date_range_validation(self):
        """Test date range validation and edge cases."""
        # Test with reversed date range
        self.tab.set_date_range(
            datetime(2023, 1, 3),  # End before start
            datetime(2023, 1, 1)
        )

        # Should handle gracefully (implementation dependent)
        assert self.tab.start_timestamp is not None
        assert self.tab.end_timestamp is not None

        # Test with same start and end
        same_date = datetime(2023, 1, 1, 12, 0)
        self.tab.set_date_range(same_date, same_date)

        assert self.tab.start_timestamp == same_date
        assert self.tab.end_timestamp == same_date