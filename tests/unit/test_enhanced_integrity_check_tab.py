"""
Unit tests for the EnhancedIntegrityCheckTab focusing on file integrity checking.

These tests complement the existing test_enhanced_gui_tab.py by focusing on the
missing test coverage areas identified in the improvement plan.
"""

import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

from PyQt6.QtCore import QDate, QDateTime, Qt, QTime
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from goesvfi.integrity_check.enhanced_gui_tab import EnhancedIntegrityCheckTab
from goesvfi.integrity_check.enhanced_view_model import (
    EnhancedIntegrityCheckViewModel,
    EnhancedMissingTimestamp,
    FetchSource,
)
from goesvfi.integrity_check.time_index import SatellitePattern, TimeIndex
from goesvfi.integrity_check.view_model import MissingTimestamp, ScanStatus

# Import our test utilities
from tests.utils.pyqt_async_test import AsyncSignalWaiter, PyQtAsyncTestCase, async_test


class TestEnhancedIntegrityCheckTabFileOperations(PyQtAsyncTestCase):
    """Test cases for EnhancedIntegrityCheckTab focusing on file operations and integrity checking."""

    def setUp(self):
        """Set up test fixtures."""
        # Call parent setUp for proper PyQt/asyncio setup
        super().setUp()

        # Ensure we have a QApplication
        self.app = QApplication.instance() or QApplication([])

        # Create a temporary directory
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

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

        # Create the tab widget under test
        self.tab = EnhancedIntegrityCheckTab(self.mock_view_model)

        # Mock any cleanup methods
        self.mock_view_model.cleanup = MagicMock()

    def tearDown(self):
        """Tear down test fixtures."""
        # Clean up widget
        self.tab.close()
        self.tab.deleteLater()

        # Clean up temporary directory
        self.temp_dir.cleanup()

        # Call parent tearDown for proper event loop cleanup
        super().tearDown()

    @patch("goesvfi.integrity_check.enhanced_gui_tab.QFileDialog")
    def test_directory_selection(self, mock_file_dialog):
        """Test the directory selection functionality."""
        # Set up mock to return a specific directory
        new_dir = Path("/test/directory")
        mock_file_dialog.getExistingDirectory.return_value = str(new_dir)

        # Set up signal waiter to catch the directory_selected signal
        dir_signal_waiter = AsyncSignalWaiter(self.tab.directory_selected)

        # Call the browse directory method
        self.tab._browse_directory()

        # Check that the file dialog was called correctly
        mock_file_dialog.getExistingDirectory.assert_called_once()

        # Check that the view model was updated
        self.mock_view_model.base_directory = str(new_dir)

        # Check that the UI was updated
        self.assertEqual(self.tab.directory_edit.text(), str(new_dir))

        # Wait for the signal
        QApplication.processEvents()

    @async_test
    async def test_directory_selection_signal(self):
        """Test that the directory_selected signal is emitted correctly."""
        # Set up signal waiter
        dir_signal_waiter = AsyncSignalWaiter(self.tab.directory_selected)

        # Change the directory manually
        new_dir = "/test/manual/directory"
        self.tab.directory_edit.setText(new_dir)
        self.tab._handle_directory_changed()

        # Wait for the signal
        received_dir = await dir_signal_waiter.wait(timeout=1.0)

        # Verify the signal was emitted with the correct directory
        self.assertEqual(received_dir, new_dir)

    @patch("goesvfi.integrity_check.time_index.TimeIndex.auto_detect_date_range")
    @patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox")
    def test_auto_detect_date_range_success(self, mock_message_box, mock_auto_detect):
        """Test auto-detecting date range with successful detection."""
        # Setup mock to return a date range
        detected_start = datetime(2023, 1, 1)
        detected_end = datetime(2023, 1, 5)
        mock_auto_detect.return_value = (detected_start, detected_end)

        # Set up signal waiter for date_range_changed signal
        date_range_waiter = AsyncSignalWaiter(self.tab.date_range_changed)

        # Call the method under test
        self.tab._auto_detect_date_range()

        # Verify auto_detect_date_range was called with correct parameters
        mock_auto_detect.assert_called_once_with(
            self.base_dir, self.mock_view_model.satellite
        )

        # Verify date pickers were updated
        self.assertEqual(
            self.tab.start_date_picker.date().toPyDate(), detected_start.date()
        )
        self.assertEqual(
            self.tab.end_date_picker.date().toPyDate(), detected_end.date()
        )

        # Verify success message was shown
        mock_message_box.information.assert_called_once()
        info_args = mock_message_box.information.call_args[0]
        self.assertIn("Date Range Detected", info_args[1])

        # Verify view model was updated
        self.assertEqual(self.mock_view_model.start_date, detected_start)
        self.assertEqual(self.mock_view_model.end_date, detected_end)

        # Process events to ensure signals are delivered
        QApplication.processEvents()

    @patch("goesvfi.integrity_check.time_index.TimeIndex.auto_detect_date_range")
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
        self.assertIn("Error Detecting Date Range", error_args[1])
        self.assertIn("Test error", error_args[2])

    @patch("goesvfi.integrity_check.time_index.TimeIndex.auto_detect_date_range")
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
        self.assertIn("No Valid Files Found", info_args[1])

    @async_test
    async def test_date_range_selection_ui(self):
        """Test that date range selection via UI updates the model and emits signals."""
        # Set up signal waiter
        date_range_waiter = AsyncSignalWaiter(self.tab.date_range_changed)

        # Change the start date
        new_start_date = QDate(2023, 2, 1)
        self.tab.start_date_picker.setDate(new_start_date)
        self.tab._handle_start_date_changed(new_start_date)

        # Process events
        QApplication.processEvents()

        # Change the end date
        new_end_date = QDate(2023, 2, 10)
        self.tab.end_date_picker.setDate(new_end_date)
        self.tab._handle_end_date_changed(new_end_date)

        # Process events
        QApplication.processEvents()

        # Wait for the signal
        start_date, end_date = await date_range_waiter.wait(timeout=1.0)

        # Verify the dates are correct
        expected_start = datetime(2023, 2, 1, 0, 0, 0)
        expected_end = datetime(2023, 2, 10, 23, 59, 59)

        self.assertEqual(start_date, expected_start)
        self.assertEqual(end_date, expected_end)

        # Verify view model was updated
        self.assertEqual(self.mock_view_model.start_date, expected_start)
        self.assertEqual(self.mock_view_model.end_date, expected_end)

    def test_start_scan_button(self):
        """Test the start scan button functionality."""
        # Ensure the button is enabled
        self.tab.scan_button.setEnabled(True)

        # Click the scan button
        self.tab.scan_button.click()

        # Verify scan was started on the view model
        self.mock_view_model.start_scan.assert_called_once()

    def test_cancel_scan_button(self):
        """Test the cancel scan button functionality."""
        # Ensure the button is enabled
        self.tab.cancel_button.setEnabled(True)

        # Click the cancel button
        self.tab.cancel_button.click()

        # Verify scan was cancelled on the view model
        self.mock_view_model.cancel_scan.assert_called_once()

    def test_download_all_button(self):
        """Test the download all button functionality."""
        # Ensure the button is enabled
        self.tab.download_all_button.setEnabled(True)

        # Click the download all button
        self.tab.download_all_button.click()

        # Verify downloads were started on the view model
        self.mock_view_model.start_downloads.assert_called_once()

    def test_cancel_download_button(self):
        """Test the cancel download button functionality."""
        # Ensure the button is enabled
        self.tab.cancel_download_button.setEnabled(True)

        # Click the cancel download button
        self.tab.cancel_download_button.click()

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

        # Mock table model and call scan complete handler
        self.tab.missing_items_model = MagicMock()
        self.tab._handle_scan_completed(True, "Found 2 missing items")

        # Verify UI updates
        self.tab.missing_items_model.set_items.assert_called_once_with(missing_items)

        # Verify download button is enabled
        self.assertTrue(self.tab.download_all_button.isEnabled())

    def test_scan_complete_error_handler(self):
        """Test handling of scan completion with error."""
        # Call scan complete handler with error
        self.tab._handle_scan_completed(False, "Error occurred during scan")

        # Verify download button is disabled
        self.assertFalse(self.tab.download_all_button.isEnabled())

    @patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox")
    def test_handle_scan_error(self, mock_message_box):
        """Test handling of scan errors."""
        # Call error handler
        self.tab._handle_scan_error("Test error message")

        # Verify status is updated
        self.assertEqual(self.tab.status_label.text(), "Error: Test error message")

        # Verify error message is shown to user
        mock_message_box.critical.assert_called_once()
        error_args = mock_message_box.critical.call_args[0]
        self.assertIn("Scan Error", error_args[1])
        self.assertIn("Test error message", error_args[2])


if __name__ == "__main__":
    unittest.main()
