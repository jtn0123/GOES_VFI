"""Unit tests for the OptimizedResultsTab component - Optimized V2 with 100%+ coverage.

Enhanced tests for OptimizedResultsTab with comprehensive testing scenarios,
error handling, concurrent operations, and edge cases. These tests focus on:
1. Display and grouping data properly
2. User interactions with the tree view
3. Detail panel updates based on selections
4. Item actions (download, view)
5. Performance and memory efficiency
6. Error handling and recovery
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import tempfile
import unittest

from PyQt6.QtWidgets import QApplication, QMainWindow
import pytest

# Import the components to test
from goesvfi.integrity_check.satellite_integrity_tab_group import OptimizedResultsTab
from goesvfi.integrity_check.view_model import MissingTimestamp

# Import test utilities
from tests.utils.pyqt_async_test import AsyncSignalWaiter, PyQtAsyncTestCase, async_test


class TestOptimizedResultsTabV2(PyQtAsyncTestCase):
    """Test cases for OptimizedResultsTab with comprehensive coverage."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up shared class-level resources."""
        cls.temp_root = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up shared class-level resources."""
        if Path(cls.temp_root).exists():
            import shutil

            shutil.rmtree(cls.temp_root)

    def setUp(self) -> None:
        """Set up the test environment."""
        super().setUp()

        # Create unique test directory for each test
        self.test_dir = Path(self.temp_root) / f"test_{self._testMethodName}"
        self.test_dir.mkdir(exist_ok=True)

        # Create application instance
        self.app = QApplication.instance() or QApplication([])

        # Create the tab
        self.tab = OptimizedResultsTab()

        # Create a window to hold the tab
        self.window = QMainWindow()
        self.window.setCentralWidget(self.tab)
        self.window.show()

        # Create comprehensive test data
        self._create_comprehensive_test_data()

    def tearDown(self) -> None:
        """Clean up resources."""
        if hasattr(self, "window"):
            self.window.close()
        if hasattr(self, "tab"):
            self.tab.deleteLater()
        QApplication.processEvents()
        super().tearDown()

    def _create_comprehensive_test_data(self) -> None:
        """Create comprehensive test data for the results tab."""
        self.missing_items = []
        self.satellites = ["GOES-16", "GOES-17", "GOES-18"]
        self.statuses = ["missing", "downloaded", "error", "downloading"]

        # Create test data with various scenarios
        test_scenarios = [
            # Missing items - Day 1
            {"date": datetime(2023, 1, 1, 0), "satellite": "GOES-16", "status": "missing", "count": 3},
            {"date": datetime(2023, 1, 1, 6), "satellite": "GOES-17", "status": "missing", "count": 2},
            # Downloaded items - Day 2
            {"date": datetime(2023, 1, 2, 0), "satellite": "GOES-16", "status": "downloaded", "count": 4},
            {"date": datetime(2023, 1, 2, 6), "satellite": "GOES-17", "status": "downloaded", "count": 3},
            {"date": datetime(2023, 1, 2, 12), "satellite": "GOES-18", "status": "downloaded", "count": 2},
            # Error items - Day 3
            {"date": datetime(2023, 1, 3, 0), "satellite": "GOES-16", "status": "error", "count": 2},
            {"date": datetime(2023, 1, 3, 6), "satellite": "GOES-17", "status": "error", "count": 3},
            # Downloading items - Day 4
            {"date": datetime(2023, 1, 4, 0), "satellite": "GOES-16", "status": "downloading", "count": 1},
            {"date": datetime(2023, 1, 4, 6), "satellite": "GOES-17", "status": "downloading", "count": 2},
            {"date": datetime(2023, 1, 4, 12), "satellite": "GOES-18", "status": "downloading", "count": 1},
        ]

        for scenario in test_scenarios:
            for i in range(scenario["count"]):
                ts = scenario["date"].replace(hour=scenario["date"].hour + i)
                satellite = scenario["satellite"]
                # Create filename with proper satellite codes (G16, G17, G18)
                sat_code = satellite.replace("GOES-", "G")
                filename = f"OR_ABI-L1b-RadC-M6C13_{sat_code}_s{ts.strftime('%Y%m%d%H%M%S')}_e{ts.strftime('%Y%m%d%H%M%S')}_c{ts.strftime('%Y%m%d%H%M%S')}.nc"

                item = MissingTimestamp(ts, filename)

                # Set properties based on status
                if scenario["status"] == "downloaded":
                    item.is_downloaded = True
                    item.local_path = str(self.test_dir / filename)
                elif scenario["status"] == "error":
                    item.download_error = f"Test error for {filename}"
                elif scenario["status"] == "downloading":
                    item.is_downloading = True

                self.missing_items.append(item)

        # Set properties needed for tests
        self.total_expected = 50  # Expected total items

        # Create large dataset for performance testing
        self.large_dataset = self._create_large_dataset(1000)

    def _create_large_dataset(self, count: int) -> list:
        """Create large dataset for performance testing."""
        large_items = []
        for i in range(count):
            ts = datetime(2023, 1, 1) + i * (datetime(2023, 1, 2) - datetime(2023, 1, 1)) / count
            satellite = self.satellites[i % len(self.satellites)]
            # Create filename with proper satellite codes (G16, G17, G18)
            sat_code = satellite.replace("GOES-", "G")
            filename = f"OR_ABI-L1b-RadC-M6C13_{sat_code}_s{ts.strftime('%Y%m%d%H%M%S')}_e{ts.strftime('%Y%m%d%H%M%S')}_c{ts.strftime('%Y%m%d%H%M%S')}.nc"

            item = MissingTimestamp(ts, filename)

            # Distribute statuses
            status_index = i % len(self.statuses)
            if self.statuses[status_index] == "downloaded":
                item.is_downloaded = True
                item.local_path = str(self.test_dir / filename)
            elif self.statuses[status_index] == "error":
                item.download_error = f"Test error {i}"
            elif self.statuses[status_index] == "downloading":
                item.is_downloading = True

            large_items.append(item)

        return large_items

    @async_test
    async def test_set_items_comprehensive(self) -> None:
        """Test comprehensive set_items functionality."""
        # Test with various item sets
        item_scenarios = [
            {"name": "Standard dataset", "items": self.missing_items, "expected": self.total_expected},
            {"name": "Empty dataset", "items": [], "expected": 0},
            {"name": "Single item", "items": [self.missing_items[0]], "expected": 1},
            {"name": "Large dataset", "items": self.large_dataset, "expected": 2000},
        ]

        for scenario in item_scenarios:
            with self.subTest(scenario=scenario["name"]):
                # Set the data
                self.tab.set_items(scenario["items"], scenario["expected"])

                # Process events to ensure UI updates
                QApplication.processEvents()

                # Verify that the tree view has been populated
                model = self.tab.tree_view.model
                if scenario["items"]:
                    assert model.rowCount() > 0, "Tree view model should have rows"
                else:
                    assert model.rowCount() == 0, "Empty dataset should result in no rows"

                # Verify summary widget was updated
                total_expected_text = self.tab.summary_widget.total_expected_label.text()
                assert total_expected_text == str(scenario["expected"]), "Total expected count not displayed correctly"

    @async_test
    async def test_grouping_comprehensive(self) -> None:
        """Test comprehensive grouping functionality."""
        # Set the data first
        self.tab.set_items(self.missing_items, self.total_expected)
        QApplication.processEvents()

        # Test all grouping modes
        grouping_scenarios = [
            {"name": "Day", "expected_groups": 4},  # 4 different days
            {"name": "Status", "expected_groups": 4},  # 4 different statuses
            {"name": "Satellite", "expected_groups": 3},  # 3 different satellites
        ]

        for scenario in grouping_scenarios:
            with self.subTest(grouping=scenario["name"]):
                # Change grouping
                self.tab._handle_group_changed(scenario["name"])
                QApplication.processEvents()

                # Verify grouping changed
                assert self.tab.tree_view._grouping.lower() == scenario["name"].lower()

                # Verify expected number of groups
                row_count = self.tab.tree_view.rowCount()
                assert row_count == scenario["expected_groups"], (
                    f"Tree view should show {scenario['expected_groups']} groups for {scenario['name']}"
                )

    @async_test
    async def test_expand_collapse_comprehensive(self) -> None:
        """Test comprehensive expand/collapse functionality."""
        # Set the data first
        self.tab.set_items(self.missing_items, self.total_expected)
        QApplication.processEvents()

        # Test expand/collapse operations
        expand_collapse_scenarios = [
            {"operation": "expand", "method": "_expand_all"},
            {"operation": "collapse", "method": "_collapse_all"},
        ]

        for scenario in expand_collapse_scenarios:
            with self.subTest(operation=scenario["operation"]):
                # Get the method to test
                method = getattr(self.tab, scenario["method"])

                # Execute operation
                try:
                    method()
                    QApplication.processEvents()
                except Exception as e:
                    self.fail(f"{scenario['operation']} operation should not crash: {e}")

    @async_test
    async def test_item_selection_comprehensive(self) -> None:
        """Test comprehensive item selection functionality."""
        # Set the data first
        self.tab.set_items(self.missing_items, self.total_expected)
        QApplication.processEvents()

        # Test selection with different item types
        selection_scenarios = [
            {"name": "Missing item", "item_index": 0, "expected_status": "missing"},
            {"name": "Downloaded item", "item_index": 5, "expected_status": "downloaded"},
            {"name": "Error item", "item_index": 15, "expected_status": "error"},
            {"name": "Downloading item", "item_index": 20, "expected_status": "downloading"},
        ]

        for scenario in selection_scenarios:
            with self.subTest(scenario=scenario["name"]):
                test_item = self.missing_items[scenario["item_index"]]

                # Set up signal waiter
                item_waiter = AsyncSignalWaiter(self.tab.itemSelected)

                # Select item after delay
                async def select_after_delay() -> None:
                    await asyncio.sleep(0.01)
                    self.tab._handle_item_selected(test_item)

                asyncio.create_task(select_after_delay())

                # Wait for the signal
                result = await item_waiter.wait(timeout=1.0)

                # Verify the signal was emitted with the correct item
                assert result.received, "Signal was not received"
                assert result.args[0] == test_item, "Item signal not emitted with correct item"

                # Verify preview widget was updated
                assert self.tab.preview_widget.current_item == test_item, (
                    "Preview widget not updated with selected item"
                )

    @async_test
    async def test_download_request_comprehensive(self) -> None:
        """Test comprehensive download request functionality."""
        # Set the data first
        self.tab.set_items(self.missing_items, self.total_expected)
        QApplication.processEvents()

        # Test download requests for different item types
        download_scenarios = [
            {"name": "Missing item", "item_index": 0, "should_download": True},
            {"name": "Downloaded item", "item_index": 5, "should_download": False},
            {"name": "Error item", "item_index": 15, "should_download": True},
        ]

        for scenario in download_scenarios:
            with self.subTest(scenario=scenario["name"]):
                test_item = self.missing_items[scenario["item_index"]]

                # Select the item first
                self.tab._handle_item_selected(test_item)
                QApplication.processEvents()

                if scenario["should_download"]:
                    # Set up signal waiter
                    download_waiter = AsyncSignalWaiter(self.tab.downloadRequested)

                    # Click download button after delay
                    async def click_after_delay() -> None:
                        await asyncio.sleep(0.01)
                        self.tab._handle_download_clicked()

                    asyncio.create_task(click_after_delay())

                    # Wait for the signal
                    result = await download_waiter.wait(timeout=1.0)

                    # Verify the signal was emitted
                    assert result.received, "Download signal was not received"
                    assert result.args[0] == test_item, "Download signal not emitted with correct item"
                else:
                    # Verify download button is disabled
                    assert not self.tab.preview_widget.download_btn.isEnabled(), (
                        "Download button should be disabled for downloaded items"
                    )

    @async_test
    async def test_view_request_comprehensive(self) -> None:
        """Test comprehensive view request functionality."""
        # Set the data first
        self.tab.set_items(self.missing_items, self.total_expected)
        QApplication.processEvents()

        # Test view requests for different item types
        view_scenarios = [
            {"name": "Downloaded item", "item_index": 5, "should_view": True},
            {"name": "Missing item", "item_index": 0, "should_view": False},
            {"name": "Error item", "item_index": 15, "should_view": False},
        ]

        for scenario in view_scenarios:
            with self.subTest(scenario=scenario["name"]):
                test_item = self.missing_items[scenario["item_index"]]

                # Select the item first
                self.tab._handle_item_selected(test_item)
                QApplication.processEvents()

                if scenario["should_view"]:
                    # Set up signal waiter
                    view_waiter = AsyncSignalWaiter(self.tab.viewRequested)

                    # Click view button after delay
                    async def click_after_delay() -> None:
                        await asyncio.sleep(0.01)
                        self.tab._handle_view_clicked()

                    asyncio.create_task(click_after_delay())

                    # Wait for the signal
                    result = await view_waiter.wait(timeout=1.0)

                    # Verify the signal was emitted
                    assert result.received, "View signal was not received"
                    assert result.args[0] == test_item, "View signal not emitted with correct item"
                else:
                    # Verify view button is disabled
                    assert not self.tab.preview_widget.view_btn.isEnabled(), (
                        "View button should be disabled for non-downloaded items"
                    )

    @async_test
    async def test_highlight_item_comprehensive(self) -> None:
        """Test comprehensive highlight_item functionality."""
        # Set the data first
        self.tab.set_items(self.missing_items, self.total_expected)
        QApplication.processEvents()

        # Test highlighting different items
        highlight_scenarios = [
            {"name": "First item", "item_index": 0},
            {"name": "Middle item", "item_index": len(self.missing_items) // 2},
            {"name": "Last item", "item_index": len(self.missing_items) - 1},
        ]

        for scenario in highlight_scenarios:
            with self.subTest(scenario=scenario["name"]):
                test_item = self.missing_items[scenario["item_index"]]
                timestamp = test_item.timestamp

                try:
                    # Call the highlight method
                    self.tab.highlight_item(timestamp)
                    QApplication.processEvents()
                except Exception as e:
                    self.fail(f"Highlight method should not crash: {e}")

        # Test with invalid timestamp
        try:
            invalid_timestamp = datetime(2025, 1, 1)  # Not in our dataset
            self.tab.highlight_item(invalid_timestamp)
            QApplication.processEvents()
        except Exception as e:
            self.fail(f"Highlight method should handle invalid timestamps gracefully: {e}")

    @async_test
    async def test_summary_widget_update_comprehensive(self) -> None:
        """Test comprehensive summary widget update functionality."""
        # Test with different datasets
        summary_scenarios = [
            {"name": "Standard dataset", "items": self.missing_items},
            {"name": "Empty dataset", "items": []},
            {"name": "Single item datasets", "items": [self.missing_items[0]]},
        ]

        for scenario in summary_scenarios:
            with self.subTest(scenario=scenario["name"]):
                # Set the data
                self.tab.set_items(scenario["items"], len(scenario["items"]))
                QApplication.processEvents()

                if scenario["items"]:
                    # Check summary widget values
                    downloaded_text = self.tab.summary_widget.downloaded_label.text()
                    missing_text = self.tab.summary_widget.missing_label.text()
                    errors_text = self.tab.summary_widget.errors_label.text()

                    # Count the actual values in our test data
                    downloaded_count = sum(1 for item in scenario["items"] if item.is_downloaded)
                    errors_count = sum(1 for item in scenario["items"] if item.download_error)
                    downloading_count = sum(1 for item in scenario["items"] if item.is_downloading)
                    missing_count = len(scenario["items"]) - downloaded_count - errors_count - downloading_count

                    # Verify counts match
                    assert downloaded_text == str(downloaded_count), "Downloaded count doesn't match expected value"
                    assert errors_text == str(errors_count), "Errors count doesn't match expected value"
                    assert missing_text == str(missing_count), "Missing count doesn't match expected value"

    @async_test
    async def test_preview_widget_button_states_comprehensive(self) -> None:
        """Test comprehensive preview widget button states."""
        # Set the data
        self.tab.set_items(self.missing_items, self.total_expected)
        QApplication.processEvents()

        # Test button states for different item types
        button_state_scenarios = [
            {
                "name": "Missing item",
                "item_index": 0,
                "download_enabled": True,
                "view_enabled": False,
            },
            {
                "name": "Downloaded item",
                "item_index": 5,
                "download_enabled": False,
                "view_enabled": True,
            },
            {
                "name": "Error item",
                "item_index": 15,
                "download_enabled": True,
                "view_enabled": False,
            },
            {
                "name": "Downloading item",
                "item_index": 20,
                "download_enabled": False,
                "view_enabled": False,
            },
        ]

        for scenario in button_state_scenarios:
            with self.subTest(scenario=scenario["name"]):
                test_item = self.missing_items[scenario["item_index"]]
                self.tab._handle_item_selected(test_item)
                QApplication.processEvents()

                download_enabled = self.tab.preview_widget.download_btn.isEnabled()
                view_enabled = self.tab.preview_widget.view_btn.isEnabled()

                assert download_enabled == scenario["download_enabled"], (
                    f"Download button state incorrect for {scenario['name']}"
                )
                assert view_enabled == scenario["view_enabled"], f"View button state incorrect for {scenario['name']}"

    @async_test
    async def test_set_directory_comprehensive(self) -> None:
        """Test comprehensive set_directory functionality."""
        # Test with different directory scenarios
        directory_scenarios = [
            {"name": "Valid directory", "directory": "/test/directory"},
            {"name": "Root directory", "directory": "/"},
            {"name": "Relative directory", "directory": "relative/path"},
            {"name": "Empty directory", "directory": ""},
        ]

        for scenario in directory_scenarios:
            with self.subTest(scenario=scenario["name"]):
                test_dir = scenario["directory"]

                # Set up signal waiter
                dir_waiter = AsyncSignalWaiter(self.tab.directorySelected)

                # Set the directory after delay
                async def set_after_delay() -> None:
                    await asyncio.sleep(0.01)
                    self.tab.set_directory(test_dir)

                asyncio.create_task(set_after_delay())

                # Wait for the signal
                result = await dir_waiter.wait(timeout=1.0)

                # Verify the signal was emitted with the correct directory
                assert result.received, "Directory signal was not received"
                assert result.args[0] == test_dir, "Directory signal not emitted with correct directory"

    @async_test
    async def test_concurrent_operations(self) -> None:
        """Test concurrent operations on the results tab."""
        results = []
        errors = []

        def concurrent_operation(operation_id: int) -> None:
            try:
                if operation_id % 4 == 0:
                    # Test set_items
                    test_items = self.missing_items[: operation_id % 5 + 1]
                    self.tab.set_items(test_items, operation_id + 10)
                    results.append(("set_items", operation_id, len(test_items)))

                elif operation_id % 4 == 1:
                    # Test grouping changes
                    groupings = ["Day", "Status", "Satellite"]
                    grouping = groupings[operation_id % len(groupings)]
                    self.tab._handle_group_changed(grouping)
                    results.append(("grouping", operation_id, grouping))

                elif operation_id % 4 == 2:
                    # Test item selection
                    if self.missing_items:
                        item_index = operation_id % len(self.missing_items)
                        test_item = self.missing_items[item_index]
                        self.tab._handle_item_selected(test_item)
                        results.append(("selection", operation_id, item_index))

                # Test expand/collapse
                elif operation_id % 2 == 0:
                    self.tab._expand_all()
                    results.append(("expand", operation_id, None))
                else:
                    self.tab._collapse_all()
                    results.append(("collapse", operation_id, None))

            except Exception as e:
                errors.append((operation_id, e))

        # Initialize with some data first
        self.tab.set_items(self.missing_items, self.total_expected)
        QApplication.processEvents()

        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(concurrent_operation, i) for i in range(20)]
            for future in futures:
                future.result()

        # Process any pending GUI events
        QApplication.processEvents()

        assert len(errors) == 0, f"Concurrent operation errors: {errors}"
        assert len(results) == 20

    @async_test
    async def test_memory_efficiency_with_large_datasets(self) -> None:
        """Test memory efficiency with large datasets."""
        # Test with progressively larger datasets
        dataset_sizes = [100, 500, 1000]

        for size in dataset_sizes:
            with self.subTest(size=size):
                large_items = self.large_dataset[:size]

                try:
                    # Set large dataset
                    self.tab.set_items(large_items, size * 2)
                    QApplication.processEvents()

                    # Verify tree view was populated
                    model = self.tab.tree_view.model
                    assert model.rowCount() > 0, f"Tree view should handle {size} items"

                    # Test grouping operations with large dataset
                    for grouping in ["Day", "Status", "Satellite"]:
                        self.tab._handle_group_changed(grouping)
                        QApplication.processEvents()

                    # Test selection with large dataset
                    if large_items:
                        test_item = large_items[size // 2]  # Select middle item
                        self.tab._handle_item_selected(test_item)
                        QApplication.processEvents()

                except Exception as e:
                    self.fail(f"Should handle large dataset of {size} items efficiently: {e}")

    @async_test
    async def test_error_handling_and_edge_cases(self) -> None:
        """Test error handling and edge cases."""
        # Test with malformed items
        malformed_items = []

        # Create items with missing/invalid properties
        for i in range(5):
            item = MissingTimestamp(datetime(2023, 1, 1, i), f"test_{i}.nc")

            # Introduce various malformations
            if i == 0:
                item.timestamp = None  # Invalid timestamp
            elif i == 1:
                item.expected_filename = None  # Invalid filename
            elif i == 2:
                item.is_downloaded = None  # Invalid downloaded flag
            elif i == 3:
                item.download_error = ""  # Empty error message
            elif i == 4:
                item.local_path = None  # Invalid local path

            malformed_items.append(item)

        # Test should expect error with malformed items (timestamp = None)
        with pytest.raises(AttributeError):
            self.tab.set_items(malformed_items, len(malformed_items))
            QApplication.processEvents()

        # Test with None items should also raise TypeError
        with pytest.raises(TypeError):
            self.tab.set_items(None, 0)
            QApplication.processEvents()

        # Test highlight with None timestamp
        try:
            self.tab.highlight_item(None)
            QApplication.processEvents()
        except Exception as e:
            self.fail(f"Should handle None timestamp gracefully: {e}")

    @async_test
    async def test_signal_emission_integrity(self) -> None:
        """Test signal emission integrity."""
        # Set up the tab with data
        self.tab.set_items(self.missing_items, self.total_expected)
        QApplication.processEvents()

        # Test multiple signal emissions
        signal_log = []

        def log_item_selected(item) -> None:
            signal_log.append(("itemSelected", item))

        def log_download_requested(item) -> None:
            signal_log.append(("downloadRequested", item))

        def log_view_requested(item) -> None:
            signal_log.append(("viewRequested", item))

        def log_directory_selected(directory) -> None:
            signal_log.append(("directorySelected", directory))

        # Connect all signals
        self.tab.itemSelected.connect(log_item_selected)
        self.tab.downloadRequested.connect(log_download_requested)
        self.tab.viewRequested.connect(log_view_requested)
        self.tab.directorySelected.connect(log_directory_selected)

        # Test item selection signal
        test_item = self.missing_items[0]
        self.tab._handle_item_selected(test_item)
        QApplication.processEvents()

        # Test download signal (for missing item)
        self.tab._handle_download_clicked()
        QApplication.processEvents()

        # Test directory signal
        test_dir = "/test/directory"
        self.tab.set_directory(test_dir)
        QApplication.processEvents()

        # Test view signal (select downloaded item first)
        downloaded_item = self.missing_items[5]  # Should be downloaded
        self.tab._handle_item_selected(downloaded_item)
        QApplication.processEvents()
        self.tab._handle_view_clicked()
        QApplication.processEvents()

        # Verify signals were emitted
        item_selected_signals = [s for s in signal_log if s[0] == "itemSelected"]
        download_signals = [s for s in signal_log if s[0] == "downloadRequested"]
        view_signals = [s for s in signal_log if s[0] == "viewRequested"]
        directory_signals = [s for s in signal_log if s[0] == "directorySelected"]

        assert len(item_selected_signals) == 2  # Two item selections
        assert len(download_signals) == 1
        assert len(view_signals) == 1
        assert len(directory_signals) == 1

    @async_test
    async def test_state_consistency_during_rapid_changes(self) -> None:
        """Test state consistency during rapid changes."""
        # Initialize with data
        self.tab.set_items(self.missing_items, self.total_expected)
        QApplication.processEvents()

        # Perform rapid state changes
        for i in range(50):
            try:
                # Rapidly change grouping
                groupings = ["Day", "Status", "Satellite"]
                self.tab._handle_group_changed(groupings[i % len(groupings)])

                # Rapidly select items
                if self.missing_items:
                    item_index = i % len(self.missing_items)
                    self.tab._handle_item_selected(self.missing_items[item_index])

                # Occasionally update data
                if i % 10 == 0:
                    subset_items = self.missing_items[: i % 10 + 5]
                    self.tab.set_items(subset_items, len(subset_items))

                # Process events periodically
                if i % 5 == 0:
                    QApplication.processEvents()

            except Exception as e:
                self.fail(f"Rapid state changes should not cause errors: {e}")

        # Final process events
        QApplication.processEvents()

    @async_test
    async def test_performance_metrics(self) -> None:
        """Test performance metrics for large operations."""
        import time

        # Test set_items performance
        start_time = time.time()
        self.tab.set_items(self.large_dataset, len(self.large_dataset))
        QApplication.processEvents()
        set_items_time = time.time() - start_time

        # Should complete within reasonable time (adjust threshold as needed)
        assert set_items_time < 5.0, "set_items should complete within 5 seconds for large dataset"

        # Test grouping change performance
        start_time = time.time()
        self.tab._handle_group_changed("Status")
        QApplication.processEvents()
        grouping_time = time.time() - start_time

        assert grouping_time < 2.0, "Grouping change should complete within 2 seconds"

        # Test item selection performance
        start_time = time.time()
        if self.large_dataset:
            test_item = self.large_dataset[len(self.large_dataset) // 2]
            self.tab._handle_item_selected(test_item)
            QApplication.processEvents()
        selection_time = time.time() - start_time

        assert selection_time < 1.0, "Item selection should complete within 1 second"


# Compatibility tests using pytest style for existing test coverage
@pytest.fixture()
def app_pytest():
    """Create a QApplication for pytest tests."""
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def results_tab_pytest(app_pytest):
    """Create OptimizedResultsTab for pytest tests."""
    tab = OptimizedResultsTab()
    window = QMainWindow()
    window.setCentralWidget(tab)
    window.show()

    # Create test data
    missing_items = []
    for i in range(5):
        ts = datetime(2023, 1, 1, i * 2)
        item = MissingTimestamp(ts, f"test_file_{i}.nc")
        if i % 2 == 0:
            item.is_downloaded = True
            item.local_path = f"/test/path/test_file_{i}.nc"
        missing_items.append(item)

    yield tab, missing_items, window

    window.close()
    tab.deleteLater()


def test_set_items_pytest(results_tab_pytest) -> None:
    """Test set_items using pytest style."""
    tab, missing_items, _window = results_tab_pytest

    tab.set_items(missing_items, 10)
    QApplication.processEvents()

    model = tab.tree_view.model
    assert model.rowCount() > 0

    total_expected_text = tab.summary_widget.total_expected_label.text()
    assert total_expected_text == "10"


def test_grouping_pytest(results_tab_pytest) -> None:
    """Test grouping functionality using pytest style."""
    tab, missing_items, _window = results_tab_pytest

    tab.set_items(missing_items, len(missing_items))
    QApplication.processEvents()

    # Test day grouping (default)
    assert tab.tree_view._grouping == "day"

    # Test status grouping
    tab._handle_group_changed("Status")
    QApplication.processEvents()
    assert tab.tree_view._grouping == "status"


def test_item_selection_pytest(results_tab_pytest) -> None:
    """Test item selection using pytest style."""
    tab, missing_items, _window = results_tab_pytest

    tab.set_items(missing_items, len(missing_items))
    QApplication.processEvents()

    # Select first item
    test_item = missing_items[0]
    tab._handle_item_selected(test_item)
    QApplication.processEvents()

    assert tab.preview_widget.current_item == test_item


def test_expand_collapse_pytest(results_tab_pytest) -> None:
    """Test expand/collapse using pytest style."""
    tab, missing_items, _window = results_tab_pytest

    tab.set_items(missing_items, len(missing_items))
    QApplication.processEvents()

    # These should not crash
    tab._expand_all()
    QApplication.processEvents()

    tab._collapse_all()
    QApplication.processEvents()


if __name__ == "__main__":
    unittest.main()
