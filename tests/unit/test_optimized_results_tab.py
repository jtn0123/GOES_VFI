"""
Unit tests for the OptimizedResultsTab component to verify functionality.

These tests focus on the results tab's ability to:
1. Display and group data properly
2. Handle user interactions with the tree view
3. Update detail panels based on selections
4. Process item actions (download, view)
"""

import unittest
from datetime import datetime

from PyQt6.QtWidgets import QApplication, QMainWindow

# Import the components to test
from goesvfi.integrity_check.satellite_integrity_tab_group import OptimizedResultsTab
from goesvfi.integrity_check.view_model import MissingTimestamp

# Import our test utilities
from tests.utils.pyqt_async_test import AsyncSignalWaiter, PyQtAsyncTestCase, async_test


class TestOptimizedResultsTab(PyQtAsyncTestCase):
    """Unit tests for the OptimizedResultsTab."""

    def setUp(self):
        """Set up the test environment."""
        super().setUp()

        # Create application instance
        self.app = QApplication.instance() or QApplication([])

        # Create the tab
        self.tab = OptimizedResultsTab()

        # Create a window to hold the tab
        self.window = QMainWindow()
        self.window.setCentralWidget(self.tab)
        self.window.show()

        # Create temporary data for tests
        self._create_test_data()

    def tearDown(self):
        """Clean up resources."""
        self.window.close()
        super().tearDown()

    def _create_test_data(self):
        """Create test data for the results tab."""
        # Create a list of mock missing timestamps with various states
        self.missing_items = []

        # Missing items
        for i in range(5):
            ts = datetime(2023, 1, 1, i * 2)  # Every 2 hours on day 1
            item = MissingTimestamp(ts, f"G16_file_{ts.strftime('%Y%m%d%H%M%S')}.nc")
            self.missing_items.append(item)

        # Downloaded items
        for i in range(5):
            ts = datetime(2023, 1, 2, i * 2)  # Every 2 hours on day 2
            item = MissingTimestamp(ts, f"G16_file_{ts.strftime('%Y%m%d%H%M%S')}.nc")
            item.is_downloaded = True
            item.local_path = f"/test/path/{item.expected_filename}"
            self.missing_items.append(item)

        # Error items
        for i in range(5):
            ts = datetime(2023, 1, 3, i * 2)  # Every 2 hours on day 3
            item = MissingTimestamp(ts, f"G17_file_{ts.strftime('%Y%m%d%H%M%S')}.nc")
            item.download_error = "Test error message"
            self.missing_items.append(item)

        # Downloading items
        for i in range(5):
            ts = datetime(2023, 1, 4, i * 2)  # Every 2 hours on day 4
            item = MissingTimestamp(ts, f"G17_file_{ts.strftime('%Y%m%d%H%M%S')}.nc")
            item.is_downloading = True
            self.missing_items.append(item)

        # Set properties needed for tests
        self.total_expected = 30  # Expected total items

    @async_test
    async def test_set_items(self):
        """Test the set_items method properly sets data and updates widgets."""
        # Set the data
        self.tab.set_items(self.missing_items, self.total_expected)

        # Process events to ensure UI updates
        QApplication.processEvents()

        # Verify that the tree view has been populated
        model = self.tab.tree_view.model
        assert model.rowCount() > 0, "Tree view model should have rows"

        # Verify summary widget was updated
        total_expected_text = self.tab.summary_widget.total_expected_label.text()
        assert total_expected_text == str(self.total_expected), "Total expected count not displayed correctly"

    @async_test
    async def test_group_by_day(self):
        """Test grouping items by day."""
        # Set the data first
        self.tab.set_items(self.missing_items, self.total_expected)

        # Process events
        QApplication.processEvents()

        # Default grouping should be "day"
        assert self.tab.tree_view._grouping == "day", "Default grouping should be by day"

        # There should be 4 days in the tree (days 1-4)
        row_count = self.tab.tree_view.rowCount()
        assert row_count == 4, "Tree view should show 4 days"

    @async_test
    async def test_group_by_status(self):
        """Test grouping items by status."""
        # Set the data first
        self.tab.set_items(self.missing_items, self.total_expected)

        # Process events
        QApplication.processEvents()

        # Change grouping to status
        self.tab._handle_group_changed("Status")

        # Process events
        QApplication.processEvents()

        # There should be 4 status groups (Downloaded, Downloading, Error, Missing)
        row_count = self.tab.tree_view.rowCount()
        assert row_count == 4, "Tree view should show 4 status groups"

    @async_test
    async def test_group_by_satellite(self):
        """Test grouping items by satellite."""
        # Set the data first
        self.tab.set_items(self.missing_items, self.total_expected)

        # Process events
        QApplication.processEvents()

        # Change grouping to satellite
        self.tab._handle_group_changed("Satellite")

        # Process events
        QApplication.processEvents()

        # There should be at least 2 satellite groups (GOES-16, GOES-17)
        row_count = self.tab.tree_view.rowCount()
        assert row_count >= 2, "Tree view should show at least 2 satellite groups"

    @async_test
    async def test_expand_collapse(self):
        """Test expand all and collapse all functionality."""
        # Set the data first
        self.tab.set_items(self.missing_items, self.total_expected)

        # Process events
        QApplication.processEvents()

        # Test expand all
        self.tab._expand_all()

        # Process events
        QApplication.processEvents()

        # Test collapse all
        self.tab._collapse_all()

        # Process events
        QApplication.processEvents()

        # These tests just verify that the methods don't crash
        # A more thorough test would check the expanded state of items,
        # but that's difficult to do directly with QTreeView

    @async_test
    async def test_item_selection(self):
        """Test that selecting an item emits the correct signal and updates preview."""
        import asyncio

        # Set the data first
        self.tab.set_items(self.missing_items, self.total_expected)

        # Process events
        QApplication.processEvents()

        # Set up signal waiter
        item_waiter = AsyncSignalWaiter(self.tab.itemSelected)

        # Select the first item - can't easily select through the tree view in tests,
        # so we'll simulate selection by calling the handler directly
        test_item = self.missing_items[0]

        # Use asyncio to ensure waiter is ready
        async def select_after_delay():
            await asyncio.sleep(0.01)
            self.tab._handle_item_selected(test_item)

        asyncio.create_task(select_after_delay())

        # Wait for the signal
        result = await item_waiter.wait(timeout=1.0)

        # Verify the signal was emitted with the correct item
        assert result.received, "Signal was not received"
        assert result.args[0] == test_item, "Item signal not emitted with correct item"

        # The preview widget should be updated
        assert self.tab.preview_widget.current_item == test_item, "Preview widget not updated with selected item"

    @async_test
    async def test_download_request(self):
        """Test that clicking download button emits the downloadRequested signal."""
        import asyncio

        # Set the data first
        self.tab.set_items(self.missing_items, self.total_expected)

        # Select a missing item
        test_item = self.missing_items[0]  # First one should be missing
        self.tab._handle_item_selected(test_item)

        # Process events
        QApplication.processEvents()

        # Set up signal waiter
        download_waiter = AsyncSignalWaiter(self.tab.downloadRequested)

        # Click the download button after a short delay to ensure waiter is ready
        async def click_after_delay():
            await asyncio.sleep(0.01)
            self.tab._handle_download_clicked()

        asyncio.create_task(click_after_delay())

        # Wait for the signal
        result = await download_waiter.wait(timeout=1.0)

        # Verify the signal was emitted with the correct item
        assert result.received, "Signal was not received"
        assert result.args[0] == test_item, "Download signal not emitted with correct item"

    @async_test
    async def test_view_request(self):
        """Test that clicking view button emits the viewRequested signal."""
        import asyncio

        # Set the data first
        self.tab.set_items(self.missing_items, self.total_expected)

        # Select a downloaded item
        test_item = self.missing_items[5]  # Should be downloaded
        self.tab._handle_item_selected(test_item)

        # Process events
        QApplication.processEvents()

        # Set up signal waiter
        view_waiter = AsyncSignalWaiter(self.tab.viewRequested)

        # Click the view button after a short delay
        async def click_after_delay():
            await asyncio.sleep(0.01)
            self.tab._handle_view_clicked()

        asyncio.create_task(click_after_delay())

        # Wait for the signal
        result = await view_waiter.wait(timeout=1.0)

        # Verify the signal was emitted with the correct item
        assert result.received, "Signal was not received"
        assert result.args[0] == test_item, "View signal not emitted with correct item"

    @async_test
    async def test_highlight_item(self):
        """Test the highlight_item method selects the correct tree item."""
        # Set the data first
        self.tab.set_items(self.missing_items, self.total_expected)

        # Process events
        QApplication.processEvents()

        # Set up signal waiter
        item_waiter = AsyncSignalWaiter(self.tab.itemSelected)

        # Call the highlight method with a timestamp
        timestamp = self.missing_items[0].timestamp
        self.tab.highlight_item(timestamp)

        # Process events
        QApplication.processEvents()

        # This test mainly verifies the method doesn't crash
        # A more thorough test would verify the exact item is selected

    @async_test
    async def test_summary_widget_update(self):
        """Test that the summary widget is updated correctly."""
        # Set the data
        self.tab.set_items(self.missing_items, self.total_expected)

        # Process events
        QApplication.processEvents()

        # Check summary widget values
        downloaded_text = self.tab.summary_widget.downloaded_label.text()
        missing_text = self.tab.summary_widget.missing_label.text()
        errors_text = self.tab.summary_widget.errors_label.text()

        # Count the actual values in our test data
        downloaded_count = sum(1 for item in self.missing_items if item.is_downloaded)
        errors_count = sum(1 for item in self.missing_items if item.download_error)
        missing_count = (
            len(self.missing_items)
            - downloaded_count
            - errors_count
            - sum(1 for item in self.missing_items if item.is_downloading)
        )

        # Verify counts match
        assert downloaded_text == str(downloaded_count), "Downloaded count doesn't match expected value"
        assert errors_text == str(errors_count), "Errors count doesn't match expected value"
        assert missing_text == str(missing_count), "Missing count doesn't match expected value"

    @async_test
    async def test_preview_widget_button_states(self):
        """Test that the preview widget buttons are enabled/disabled correctly."""
        # Set the data
        self.tab.set_items(self.missing_items, self.total_expected)

        # Process events
        QApplication.processEvents()

        # Case 1: Missing item (download enabled, view disabled)
        missing_item = self.missing_items[0]
        self.tab._handle_item_selected(missing_item)
        QApplication.processEvents()

        assert self.tab.preview_widget.download_btn.isEnabled(), "Download button should be enabled for missing item"
        assert not self.tab.preview_widget.view_btn.isEnabled(), "View button should be disabled for missing item"

        # Case 2: Downloaded item (download disabled, view enabled)
        downloaded_item = self.missing_items[5]  # Should be downloaded
        self.tab._handle_item_selected(downloaded_item)
        QApplication.processEvents()

        assert (
            not self.tab.preview_widget.download_btn.isEnabled()
        ), "Download button should be disabled for downloaded item"
        assert self.tab.preview_widget.view_btn.isEnabled(), "View button should be enabled for downloaded item"

    @async_test
    async def test_set_directory(self):
        """Test that set_directory emits the directorySelected signal."""
        import asyncio

        # Set up signal waiter
        dir_waiter = AsyncSignalWaiter(self.tab.directorySelected)

        # Set the directory after a short delay
        test_dir = "/test/directory"

        async def set_after_delay():
            await asyncio.sleep(0.01)
            self.tab.set_directory(test_dir)

        asyncio.create_task(set_after_delay())

        # Wait for the signal
        result = await dir_waiter.wait(timeout=1.0)

        # Verify the signal was emitted with the correct directory
        assert result.received, "Signal was not received"
        assert result.args[0] == test_dir, "Directory signal not emitted with correct directory"


if __name__ == "__main__":
    unittest.main()
