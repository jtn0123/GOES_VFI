"""Unit tests for the auto-detection features in the integrity check module."""

import os
import tempfile
import traceback
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from goesvfi.integrity_check.enhanced_gui_tab import EnhancedIntegrityCheckTab
from goesvfi.integrity_check.enhanced_view_model import EnhancedIntegrityCheckViewModel
from goesvfi.integrity_check.time_index import SatellitePattern, TimeIndex

# Import our test utilities
from tests.utils.pyqt_async_test import PyQtAsyncTestCase


class TestAutoDetectFeatures(PyQtAsyncTestCase):
    """Test cases for auto-detection features in integrity check module."""

    def setUp(self):
        """Set up test fixtures."""
        # Call parent setUp
        super().setUp()

        # Ensure we have a QApplication
        self.app = QApplication.instance() or QApplication([])

        # Create a temporary test directory
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

        # Create test structures
        self.setup_test_files()

        # Create mocked view model
        self.mock_view_model = MagicMock(spec=EnhancedIntegrityCheckViewModel)
        self.mock_view_model.base_directory = self.base_dir
        self.mock_view_model.satellite = SatellitePattern.GOES_18
        self.mock_view_model.status_message = "Ready"
        self.mock_view_model.start_date = datetime.now() - timedelta(days=7)
        self.mock_view_model.end_date = datetime.now()
        self.mock_view_model.interval_minutes = 10
        self.mock_view_model.fetch_source = MagicMock()
        self.mock_view_model.missing_items = []

        # Create the tab for testing
        self.tab = EnhancedIntegrityCheckTab(self.mock_view_model)

    def tearDown(self):
        """Tear down test fixtures."""
        # Clean up widget
        self.tab.close()
        self.tab.deleteLater()

        # Process events
        QCoreApplication.processEvents()

        # Clean up temporary test directory
        self.temp_dir.cleanup()

        # Call parent tearDown
        super().tearDown()

    def setup_test_files(self):
        """Set up test file structure with various date patterns."""
        # GOES-16 files with different date patterns
        # Pattern 1: goes16_YYYYMMDD_HHMMSS_band13.png
        goes16_dir = self.base_dir / "goes16"
        goes16_dir.mkdir(parents=True)

        # Create files with timestamps spread over a week
        base_date = datetime(2023, 6, 15)
        for i in range(7):
            file_date = base_date + timedelta(days=i)
            for hour in range(0, 24, 6):  # 6-hour intervals
                file_time = file_date.replace(hour=hour, minute=0, second=0)
                filename = f"goes16_{file_time.strftime('%Y%m%d_%H%M%S')}_band13.png"
                (goes16_dir / filename).touch()

        # GOES-18 files with different date patterns
        # Pattern 1: goes18_YYYYMMDD_HHMMSS_band13.png
        goes18_dir = self.base_dir / "goes18"
        goes18_dir.mkdir(parents=True)

        # Create files with timestamps spread over a month
        for i in range(30):
            file_date = base_date + timedelta(days=i)
            for hour in range(0, 24, 4):  # 4-hour intervals
                file_time = file_date.replace(hour=hour, minute=0, second=0)
                filename = f"goes18_{file_time.strftime('%Y%m%d_%H%M%S')}_band13.png"
                (goes18_dir / filename).touch()

        # Create directory structure pattern: YYYY-MM-DD_HH-MM-SS
        date_dir = self.base_dir / "date_dirs"
        date_dir.mkdir(parents=True)

        for i in range(10):
            dir_date = base_date + timedelta(days=i)
            dir_name = dir_date.strftime("%Y-%m-%d_%H-%M-%S")
            (date_dir / dir_name).mkdir()

        # Create some non-standard format files that shouldn't match
        invalid_dir = self.base_dir / "invalid"
        invalid_dir.mkdir(parents=True)

        # Non-matching file patterns
        (invalid_dir / "not_a_goes_file.png").touch()
        (invalid_dir / "goes_no_timestamp.png").touch()
        (invalid_dir / "goes16_invalid_date.png").touch()
        (invalid_dir / "goes18_2023_01_01.png").touch()  # Missing time component

    @patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox")
    def test_auto_detect_date_range_goes16(self, mock_message_box):
        """Test auto-detecting date range for GOES-16 files."""
        # Set satellite to GOES-16
        self.mock_view_model.satellite = SatellitePattern.GOES_16

        # Set up a spy for the date time editors
        original_setDateTime = self.tab.start_date_edit.setDateTime
        start_date_spy = MagicMock(wraps=original_setDateTime)
        self.tab.start_date_edit.setDateTime = start_date_spy

        original_end_setDateTime = self.tab.end_date_edit.setDateTime
        end_date_spy = MagicMock(wraps=original_end_setDateTime)
        self.tab.end_date_edit.setDateTime = end_date_spy

        # Call the method
        self.tab._auto_detect_date_range()

        # Process events
        QCoreApplication.processEvents()

        # Verify date time editors were updated
        self.assertTrue(start_date_spy.called)
        self.assertTrue(end_date_spy.called)

        # Verify information dialog was shown
        mock_message_box.information.assert_called_once()

        # Verify the dates are in the expected range (June 15-21, 2023)
        # Since we're mocking setDateTime, we need to check the call args
        start_date_call = start_date_spy.call_args[0][0]
        end_date_call = end_date_spy.call_args[0][0]

        # Convert QDateTime to Python datetime
        start_py_date = datetime(
            start_date_call.date().year(),
            start_date_call.date().month(),
            start_date_call.date().day(),
            start_date_call.time().hour(),
            start_date_call.time().minute(),
        )

        end_py_date = datetime(
            end_date_call.date().year(),
            end_date_call.date().month(),
            end_date_call.date().day(),
            end_date_call.time().hour(),
            end_date_call.time().minute(),
        )

        # Start date should be around 2023-06-15 with hour=0, minute=0
        self.assertEqual(start_py_date.year, 2023)
        self.assertEqual(start_py_date.month, 6)
        self.assertEqual(start_py_date.day, 15)
        self.assertEqual(start_py_date.hour, 0)
        self.assertEqual(start_py_date.minute, 0)

        # End date should be around 2023-06-21 with hour=23, minute=59
        self.assertEqual(end_py_date.year, 2023)
        self.assertEqual(end_py_date.month, 6)
        self.assertEqual(end_py_date.day, 21)
        self.assertEqual(end_py_date.hour, 23)
        self.assertEqual(end_py_date.minute, 59)

    @patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox")
    def test_auto_detect_date_range_goes18(self, mock_message_box):
        """Test auto-detecting date range for GOES-18 files."""
        # Set satellite to GOES-18
        self.mock_view_model.satellite = SatellitePattern.GOES_18

        # Set up a spy for the date time editors
        original_setDateTime = self.tab.start_date_edit.setDateTime
        start_date_spy = MagicMock(wraps=original_setDateTime)
        self.tab.start_date_edit.setDateTime = start_date_spy

        original_end_setDateTime = self.tab.end_date_edit.setDateTime
        end_date_spy = MagicMock(wraps=original_end_setDateTime)
        self.tab.end_date_edit.setDateTime = end_date_spy

        # Call the method
        self.tab._auto_detect_date_range()

        # Process events
        QCoreApplication.processEvents()

        # Verify date time editors were updated
        self.assertTrue(start_date_spy.called)
        self.assertTrue(end_date_spy.called)

        # Verify information dialog was shown
        mock_message_box.information.assert_called_once()

        # Verify the dates are in the expected range (June 15 - July 15, 2023)
        # Since we're mocking setDateTime, we need to check the call args
        start_date_call = start_date_spy.call_args[0][0]
        end_date_call = end_date_spy.call_args[0][0]

        # Convert QDateTime to Python datetime
        start_py_date = datetime(
            start_date_call.date().year(),
            start_date_call.date().month(),
            start_date_call.date().day(),
            start_date_call.time().hour(),
            start_date_call.time().minute(),
        )

        end_py_date = datetime(
            end_date_call.date().year(),
            end_date_call.date().month(),
            end_date_call.date().day(),
            end_date_call.time().hour(),
            end_date_call.time().minute(),
        )

        # Start date should be around 2023-06-15 with hour=0, minute=0
        self.assertEqual(start_py_date.year, 2023)
        self.assertEqual(start_py_date.month, 6)
        self.assertEqual(start_py_date.day, 15)
        self.assertEqual(start_py_date.hour, 0)
        self.assertEqual(start_py_date.minute, 0)

        # End date should be around 2023-07-15 with hour=23, minute=59
        self.assertEqual(end_py_date.year, 2023)
        self.assertEqual(end_py_date.month, 7)
        # Day can be 14 or 15 depending on how the test runs
        self.assertIn(end_py_date.day, [14, 15])
        self.assertEqual(end_py_date.hour, 23)
        self.assertEqual(end_py_date.minute, 59)

    @patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox")
    def test_auto_detect_date_range_no_files(self, mock_message_box):
        """Test auto-detecting date range when no matching files exist."""
        # Create empty directory to test with
        empty_dir = self.base_dir / "empty"
        empty_dir.mkdir(parents=True)

        # Point the view model to the empty directory
        self.mock_view_model.base_directory = empty_dir

        # Call the method
        self.tab._auto_detect_date_range()

        # Process events
        QCoreApplication.processEvents()

        # Verify error dialog was shown
        mock_message_box.information.assert_called_once()
        info_args = mock_message_box.information.call_args[0]
        self.assertIn("No Valid Files Found", info_args[1])

    @patch("goesvfi.integrity_check.enhanced_gui_tab.QProgressDialog")
    @patch("goesvfi.integrity_check.time_index.TimeIndex.scan_directory_for_timestamps")
    @patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox")
    def test_combined_auto_detect_features(
        self, mock_message_box, mock_scan, mock_progress_dialog
    ):
        """Test combined auto-detect features (satellite type and date range)."""
        # First, we'll auto-detect satellite type
        # Setup mock to return files
        goes16_files = [datetime(2023, 1, 1, 12, 0, 0)] * 3
        goes18_files = [datetime(2023, 1, 1, 12, 0, 0)] * 5

        def scan_side_effect(directory, satellite, **kwargs):
            if satellite == SatellitePattern.GOES_16:
                return goes16_files
            elif satellite == SatellitePattern.GOES_18:
                return goes18_files
            return []

        mock_scan.side_effect = scan_side_effect

        # Mock progress dialog
        mock_progress_instance = MagicMock()
        mock_progress_dialog.return_value = mock_progress_instance

        # Call auto-detect satellite
        self.tab._auto_detect_satellite()

        # Process events
        QCoreApplication.processEvents()

        # Verify satellite was set to GOES-18 (more files)
        self.mock_view_model.satellite = SatellitePattern.GOES_18

        # Reset the message box mock to check calls separately
        mock_message_box.reset_mock()

        # Now auto-detect date range
        # Set up spies for the date time editors
        original_setDateTime = self.tab.start_date_edit.setDateTime
        start_date_spy = MagicMock(wraps=original_setDateTime)
        self.tab.start_date_edit.setDateTime = start_date_spy

        original_end_setDateTime = self.tab.end_date_edit.setDateTime
        end_date_spy = MagicMock(wraps=original_end_setDateTime)
        self.tab.end_date_edit.setDateTime = end_date_spy

        # Mock TimeIndex.find_date_range_in_directory to return fixed dates
        with patch(
            "goesvfi.integrity_check.time_index.TimeIndex.find_date_range_in_directory"
        ) as mock_find_range:
            # Return Jan 1, 2023 to Jan 31, 2023
            mock_find_range.return_value = (datetime(2023, 1, 1), datetime(2023, 1, 31))

            # Call auto-detect date range
            self.tab._auto_detect_date_range()

        # Process events
        QCoreApplication.processEvents()

        # Verify date range was set correctly
        self.assertTrue(start_date_spy.called)
        self.assertTrue(end_date_spy.called)

        # Verify both auto-detect features worked together
        # First satellite detection, then date range detection
        self.assertEqual(self.mock_view_model.satellite, SatellitePattern.GOES_18)
        self.assertEqual(
            mock_message_box.information.call_count, 1
        )  # Only from date range detection

    @patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox")
    @patch("goesvfi.integrity_check.enhanced_gui_tab.QProgressDialog")
    def test_auto_detect_satellite_no_valid_files(
        self, mock_progress_dialog, mock_message_box
    ):
        """Test auto-detecting satellite type when no valid files exist."""
        # Create a mock progress dialog instance
        mock_dialog = MagicMock()
        mock_progress_dialog.return_value = mock_dialog

        # Point the view model to the invalid files directory
        self.mock_view_model.base_directory = self.base_dir / "invalid"

        # Call the method
        self.tab._auto_detect_satellite()

        # Process events
        QCoreApplication.processEvents()

        # Verify error dialog was shown
        mock_message_box.information.assert_called_once()
        info_args = mock_message_box.information.call_args[0]
        self.assertIn("No Valid Files Found", info_args[1])

        # Verify that neither satellite was selected (should stay as default)
        self.mock_view_model.satellite = SatellitePattern.GOES_18  # Default from setUp

    @patch("goesvfi.integrity_check.enhanced_gui_tab.QProgressDialog")
    @patch("goesvfi.integrity_check.time_index.TimeIndex.scan_directory_for_timestamps")
    @patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox")
    def test_auto_detect_satellite_with_error(
        self, mock_message_box, mock_scan, mock_progress_dialog
    ):
        """Test error handling when auto-detecting satellite type."""
        # Mock progress dialog
        mock_dialog = MagicMock()
        mock_progress_dialog.return_value = mock_dialog

        # Make the scan operation raise an exception
        mock_scan.side_effect = Exception("Test exception")

        # Call the method
        self.tab._auto_detect_satellite()

        # Process events
        QCoreApplication.processEvents()

        # Verify error dialog was shown
        mock_message_box.critical.assert_called_once()
        critical_args = mock_message_box.critical.call_args[0]
        self.assertIn("Error Detecting Satellite Type", critical_args[1])
        self.assertIn("Test exception", critical_args[2])

        # Satellite should remain unchanged
        self.assertEqual(self.mock_view_model.satellite, SatellitePattern.GOES_18)

    @patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox")
    def test_auto_detect_date_range_with_error(self, mock_message_box):
        """Test error handling when auto-detecting date range."""
        # Set up to raise an exception during find_date_range_in_directory
        with patch(
            "goesvfi.integrity_check.time_index.TimeIndex.find_date_range_in_directory",
            side_effect=Exception("Date range detection error"),
        ):
            # Call the method
            self.tab._auto_detect_date_range()

        # Process events
        QCoreApplication.processEvents()

        # Verify error dialog was shown
        mock_message_box.critical.assert_called_once()
        critical_args = mock_message_box.critical.call_args[0]
        self.assertIn("Error Detecting Date Range", critical_args[1])
        self.assertIn("Date range detection error", critical_args[2])

    @patch("goesvfi.integrity_check.enhanced_gui_tab.QProgressDialog")
    @patch("goesvfi.integrity_check.time_index.TimeIndex.scan_directory_for_timestamps")
    def test_auto_detect_satellite_detail_logging(
        self, mock_scan, mock_progress_dialog
    ):
        """Test detailed logging during satellite auto-detection."""
        # Setup mock to return files with imbalance between types
        goes16_files = [datetime(2023, 1, 1, 12, 0, 0)] * 2  # Fewer GOES-16 files
        goes18_files = [datetime(2023, 1, 1, 12, 0, 0)] * 8  # More GOES-18 files

        def scan_side_effect(directory, satellite, **kwargs):
            if satellite == SatellitePattern.GOES_16:
                return goes16_files
            elif satellite == SatellitePattern.GOES_18:
                return goes18_files
            return []

        mock_scan.side_effect = scan_side_effect

        # Mock progress dialog
        mock_dialog = MagicMock()
        mock_progress_dialog.return_value = mock_dialog

        # Spy on the logger to verify detailed logging
        with patch("goesvfi.integrity_check.enhanced_gui_tab.LOGGER") as mock_logger:
            # Call the method
            self.tab._auto_detect_satellite()

            # Process events
            QCoreApplication.processEvents()

            # Verify detailed logging occurred
            # Verify initial scan announcement was logged
            mock_logger.info.assert_any_call(
                f"Auto-detect satellite: Starting scan of directory {self.base_dir}"
            )

            # Verify scanning for GOES-16 files was logged
            mock_logger.info.assert_any_call(
                f"Auto-detect satellite: Scanning for GOES-16 files in {self.base_dir}"
            )

            # Verify found file counts were logged
            mock_logger.info.assert_any_call(
                f"Auto-detect satellite: Found {len(goes16_files)} GOES-16 files and {len(goes18_files)} GOES-18 files"
            )

            # Verify the satellite selection was logged
            mock_logger.info.assert_any_call(
                f"Auto-detect satellite: Selected GOES-18 based on file count ({len(goes18_files)} vs {len(goes16_files)})"
            )

            # Verify completion was logged
            mock_logger.info.assert_any_call(
                f"Auto-detect satellite: Completed successfully, selected GOES-18 (West)"
            )


# Run the tests if this file is executed directly
if __name__ == "__main__":
    unittest.main()
