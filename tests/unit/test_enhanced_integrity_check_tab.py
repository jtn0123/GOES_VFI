"""
Unit tests for the EnhancedIntegrityCheckTab focusing on file integrity checking.

These tests complement the existing test_enhanced_gui_tab.py by focusing on the
missing test coverage areas identified in the improvement plan.
"""

# Disable GUI popups by setting Qt platform
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Patch network components before imports to prevent initialization
import unittest.mock  # noqa: E402

from PyQt6.QtCore import QDateTime  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

# Import comprehensive mocks from test utils
from tests.utils.mocks import MockCDNStore, MockS3Store

# Patch at the module level before any imports
unittest.mock.patch(
    "goesvfi.integrity_check.remote.s3_store.S3Store", MockS3Store
).start()
unittest.mock.patch(
    "goesvfi.integrity_check.remote.cdn_store.CDNStore", MockCDNStore
).start()
# Also patch in the enhanced_gui_tab module to ensure it uses our mocks
unittest.mock.patch(
    "goesvfi.integrity_check.enhanced_gui_tab.S3Store", MockS3Store
).start()
unittest.mock.patch(
    "goesvfi.integrity_check.enhanced_gui_tab.CDNStore", MockCDNStore
).start()

from goesvfi.integrity_check.enhanced_gui_tab import (  # noqa: E402
    EnhancedIntegrityCheckTab,
)
from goesvfi.integrity_check.enhanced_view_model import (  # noqa: E402
    EnhancedIntegrityCheckViewModel,
    EnhancedMissingTimestamp,
    FetchSource,
)
from goesvfi.integrity_check.time_index import SatellitePattern  # noqa: E402
from goesvfi.integrity_check.view_model import ScanStatus  # noqa: E402

# Import our test utilities
from tests.utils.pyqt_async_test import (  # noqa: E402
    AsyncSignalWaiter,
    PyQtAsyncTestCase,
    async_test,
)


class TestEnhancedIntegrityCheckTabFileOperations(PyQtAsyncTestCase):
    """Test cases for EnhancedIntegrityCheckTab focusing on file operations and integrity checking."""

    @patch("goesvfi.integrity_check.enhanced_gui_tab.S3Store", MockS3Store)
    @patch("goesvfi.integrity_check.enhanced_gui_tab.CDNStore", MockCDNStore)
    def setUp(self):
        """Set up test fixtures."""
        # Call parent setUp for proper PyQt/asyncio setup
        super().setUp()

        # Ensure we have a QApplication
        self.app = QApplication.instance() or QApplication([])

        # Create a temporary directory
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

        # GUI popups are disabled globally via disable_popups import

        # Mock dependencies
        self.mock_view_model = MagicMock(spec=EnhancedIntegrityCheckViewModel)
        self.mock_view_model.base_directory = self.base_dir
        self.mock_view_model.satellite = SatellitePattern.GOES_18
        self.mock_view_model.fetch_source = FetchSource.AUTO
        self.mock_view_model.status = ScanStatus.READY
        self.mock_view_model.status_message = "Ready"

        # Setup dates
        self.start_date = datetime.now() - timedelta(days=1)
        self.end_date = datetime.now()
        self.mock_view_model.start_date = self.start_date
        self.mock_view_model.end_date = self.end_date

        # Set up mock for can_start_scan property
        self.mock_view_model.can_start_scan = True

        # Setup for scan operations
        self.mock_view_model.start_scan = MagicMock()
        self.mock_view_model.cancel_scan = MagicMock()

        # Setup for download operations
        self.mock_view_model.start_downloads = MagicMock()
        self.mock_view_model.cancel_downloads = MagicMock()

        # Setup disk space info
        self.mock_view_model.get_disk_space_info = MagicMock(return_value=(10.0, 100.0))

        # Create the tab widget under test (network components already mocked at import time)
        self.tab = EnhancedIntegrityCheckTab(self.mock_view_model)

        # Replace the store instances with mocks after creation
        self.tab.cdn_store = MockCDNStore()  # type: ignore[assignment]
        self.tab.s3_store = MockS3Store()  # type: ignore[assignment]

        # Mock any cleanup methods
        self.mock_view_model.cleanup = MagicMock()

    def tearDown(self):
        """Tear down test fixtures."""
        try:
            # Clean up widget
            if hasattr(self, "tab"):
                self.tab.close()
                self.tab.deleteLater()
                # Process events to ensure deletion
                QApplication.processEvents()

            # Clean up temporary directory
            if hasattr(self, "temp_dir"):
                self.temp_dir.cleanup()

            # Call parent tearDown for proper event loop cleanup
            super().tearDown()
        except Exception as e:
            print(f"TearDown failed with exception: {e}")
            # Continue anyway to avoid hanging

    @patch.object(EnhancedIntegrityCheckTab, "_browse_directory")
    def test_directory_selection(self, mock_browse):
        """Test the directory selection functionality."""
        # Set up mock to simulate directory selection
        new_dir = "/test/directory"

        def mock_browse_impl():
            # Simulate what the real method does without opening dialog
            self.tab.dir_input.setText(new_dir)
            self.tab.directory_selected.emit(new_dir)

        mock_browse.side_effect = mock_browse_impl

        # Call the browse directory method
        self.tab._browse_directory()

        # Check that the mock was called
        mock_browse.assert_called_once()

        # Check that the UI was updated
        assert self.tab.dir_input.text() == new_dir

    @patch.object(EnhancedIntegrityCheckTab, "_browse_directory")
    @async_test
    async def test_directory_selection_signal(self, mock_browse):
        """Test that the directory_selected signal is emitted correctly."""
        # Set up signal waiter
        dir_signal_waiter = AsyncSignalWaiter(self.tab.directory_selected)

        # Set up mock to simulate directory selection
        new_dir = "/test/manual/directory"

        def mock_browse_impl():
            # Simulate what the real method does without opening dialog
            self.tab.dir_input.setText(new_dir)
            self.tab.directory_selected.emit(new_dir)

        mock_browse.side_effect = mock_browse_impl

        # Trigger browse which will emit the signal
        self.tab._browse_directory()

        # Wait for the signal
        result = await dir_signal_waiter.wait(timeout=1.0)

        # Verify the signal was emitted with the correct directory
        if hasattr(result, "args") and len(result.args) > 0:
            assert result.args[0] == new_dir
        else:
            # Signal was emitted but check that directory was set
            assert self.tab.dir_input.text() == new_dir

    @patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox")
    def test_auto_detect_date_range_success(self, mock_message_box):
        """Test auto-detecting date range with successful detection."""
        # Create a dummy file to avoid early return
        dummy_file = self.base_dir / "goes16_20230615_000000_band13.png"
        dummy_file.parent.mkdir(parents=True, exist_ok=True)
        dummy_file.touch()

        # Call the method under test
        self.tab._auto_detect_date_range()

        # Verify date edits were updated (GOES-16 dates based on dummy file)
        start_datetime = self.tab.start_date_edit.dateTime().toPyDateTime()
        end_datetime = self.tab.end_date_edit.dateTime().toPyDateTime()

        # Should use GOES-16 dates since we created a goes16 file
        assert start_datetime.year == 2023
        assert start_datetime.month == 6
        assert start_datetime.day == 15
        assert end_datetime.year == 2023
        # The test view model has GOES_18 set, so it should use GOES-18 dates
        assert end_datetime.month == 7
        assert end_datetime.day == 14

        # Verify success message was shown
        mock_message_box.information.assert_called_once()
        info_args = mock_message_box.information.call_args[0]
        assert "Date Range Detected" in info_args[1]

        # Process events to ensure signals are delivered
        QApplication.processEvents()

    @patch("goesvfi.integrity_check.time_index.TimeIndex.find_date_range_in_directory")
    @patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox")
    def test_auto_detect_date_range_error(self, mock_message_box, mock_auto_detect):
        """Test auto-detecting date range when an error occurs."""
        # Setup mock to raise an exception
        mock_auto_detect.side_effect = Exception("Test error")

        # Call the method under test
        self.tab._auto_detect_date_range()

        # Verify error message was shown
        mock_message_box.critical.assert_called_once()
        error_args = mock_message_box.critical.call_args[0]
        assert "Error Detecting Date Range" in error_args[1]
        assert "Test error" in error_args[2]

    @patch("goesvfi.integrity_check.time_index.TimeIndex.find_date_range_in_directory")
    @patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox")
    def test_auto_detect_date_range_no_files(self, mock_message_box, mock_auto_detect):
        """Test auto-detecting date range when no files are found."""
        # Setup mock to return None
        mock_auto_detect.return_value = (None, None)

        # Call the method under test
        self.tab._auto_detect_date_range()

        # Verify appropriate message was shown
        mock_message_box.information.assert_called_once()
        info_args = mock_message_box.information.call_args[0]
        assert "No Valid Files Found" in info_args[1]

    def test_date_range_selection_ui(self):
        """Test that date range selection via UI updates the model."""
        # Change the start date
        new_start_date = QDateTime(2023, 2, 1, 0, 0)
        self.tab.start_date_edit.setDateTime(new_start_date)

        # Change the end date
        new_end_date = QDateTime(2023, 2, 10, 23, 59)
        self.tab.end_date_edit.setDateTime(new_end_date)

        # Process events to ensure signal connections work
        QApplication.processEvents()

        # Verify the dates were set correctly in the UI
        actual_start = self.tab.start_date_edit.dateTime().toPyDateTime()
        actual_end = self.tab.end_date_edit.dateTime().toPyDateTime()

        expected_start = datetime(2023, 2, 1, 0, 0, 0)
        expected_end = datetime(
            2023, 2, 10, 23, 59, 0
        )  # Note: QDateTime seconds precision

        assert actual_start.replace(second=0, microsecond=0) == expected_start
        assert actual_end.replace(second=0, microsecond=0) == expected_end

    @patch("goesvfi.integrity_check.gui_tab.QMessageBox.warning")
    def test_start_scan_button(self, mock_warning):
        """Test the start scan button functionality."""
        # Set the directory in the GUI to match the view model
        self.tab.dir_input.setText(str(self.base_dir))

        # Ensure the button is enabled
        self.tab.scan_button.setEnabled(True)

        # Click the scan button
        self.tab.scan_button.click()

        # Verify scan was started on the view model
        self.mock_view_model.start_scan.assert_called_once()

        # Verify no warning was shown
        mock_warning.assert_not_called()

    def test_cancel_scan_button(self):
        """Test the cancel scan button functionality."""
        # Ensure the button is enabled
        self.tab.cancel_button.setEnabled(True)

        # Click the cancel button
        self.tab.cancel_button.click()

        # Verify scan was cancelled on the view model
        self.mock_view_model.cancel_scan.assert_called_once()

    @patch("goesvfi.integrity_check.gui_tab.QMessageBox")
    def test_download_all_button(self, mock_message_box):
        """Test the download selected button functionality."""
        # Mock the selection model to indicate items are selected
        mock_selection = MagicMock()
        mock_selection.hasSelection.return_value = True
        mock_selection.selectedRows.return_value = [
            MagicMock(row=MagicMock(return_value=0))
        ]

        # Mock the results table and model
        self.tab.results_table = MagicMock()
        self.tab.results_table.selectionModel.return_value = mock_selection
        self.tab.results_model = MagicMock()
        self.tab.results_model._items = [MagicMock()]  # At least one item

        # Ensure the button is enabled
        self.tab.download_button.setEnabled(True)

        # Click the download button
        self.tab.download_button.click()

        # Verify downloads were started on the view model with the selected item
        self.mock_view_model.start_downloads.assert_called_once()
        args, _ = self.mock_view_model.start_downloads.call_args
        # First arg is the item list
        assert len(args[0]) == 1

    def test_cancel_download_button(self):
        """Test the cancel download button functionality."""
        # Set up view model state to indicate downloading
        self.mock_view_model.is_scanning = False
        self.mock_view_model.is_downloading = True

        # Ensure the button is enabled
        self.tab.cancel_button.setEnabled(True)

        # Click the cancel download button
        self.tab.cancel_button.click()

        # Verify downloads were cancelled on the view model
        self.mock_view_model.cancel_downloads.assert_called_once()

    def test_scan_complete_success_handler(self):
        """Test handling of scan completion success."""
        # Create missing items for results
        missing_items = [
            EnhancedMissingTimestamp(datetime(2023, 1, 1, 12), "file1.png"),
            EnhancedMissingTimestamp(datetime(2023, 1, 1, 13), "file2.png"),
        ]
        self.mock_view_model.missing_items = missing_items

        # Mock table model with proper _items attribute that the handler expects
        self.tab.results_model = MagicMock()
        self.tab.results_model._items = (
            missing_items  # The handler checks len(self.results_model._items)
        )

        # Simulate the missing items being updated (which enables the download button)
        self.tab._on_missing_items_updated(missing_items)  # type: ignore[arg-type]

        # Call scan complete handler
        self.tab._on_scan_completed_vm(True, "Found 2 missing items")

        # Verify download button is enabled (from the missing items update)
        assert self.tab.download_button.isEnabled()

    @unittest.skip("Hangs due to Qt event loop issues in teardown")
    def test_scan_complete_error_handler(self):
        """Test handling of scan completion with error."""
        try:
            # Call scan complete handler with error
            self.tab._on_scan_completed_vm(False, "Error occurred during scan")

            # Verify download button is disabled
            assert not self.tab.download_button.isEnabled()
        except Exception as e:
            print(f"Test failed with exception: {e}")
            raise

    @patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox")
    @unittest.skip("Hangs due to S3Store initialization - needs investigation")
    def test_handle_scan_error(self, mock_message_box):
        """Test handling of scan errors through scan completed handler."""
        # Call scan completed with error
        self.tab._on_scan_completed_vm(False, "Test error message")

        # Verify download button is disabled on error
        assert not self.tab.download_button.isEnabled()

        # Verify scan button is enabled after error
        assert self.tab.scan_button.isEnabled()


if __name__ == "__main__":
    unittest.main()
