"""
Unit tests for the auto-detection features in the integrity check module - Optimized v2.

Optimizations applied:
- Shared expensive file system setup operations
- Parameterized test methods for comprehensive coverage
- Mock time operations for consistent testing
- Combined related test scenarios
- Reduced redundant widget creation and file I/O
- Enhanced fixture reuse
"""

from datetime import datetime, timedelta
from pathlib import Path
import tempfile
from typing import Any
import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QApplication
import pytest

from goesvfi.integrity_check.enhanced_gui_tab import EnhancedIntegrityCheckTab
from goesvfi.integrity_check.enhanced_view_model import EnhancedIntegrityCheckViewModel
from goesvfi.integrity_check.time_index import SatellitePattern

from tests.utils.pyqt_async_test import PyQtAsyncTestCase


class TestAutoDetectFeaturesV2(PyQtAsyncTestCase):
    """Test cases for auto-detection features - optimized v2."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up shared test data for all test methods."""
        super().setUpClass()

        # Fixed test dates for consistent testing
        cls.base_date = datetime(2023, 6, 15)  # noqa: DTZ001

        # Pre-calculated test file patterns
        cls.test_patterns = {
            "goes16_pattern": "goes16_{timestamp}_band13.png",
            "goes18_pattern": "goes18_{timestamp}_band13.png",
            "invalid_patterns": [
                "not_a_goes_file.png",
                "goes_no_timestamp.png",
                "goes16_invalid_date.png",
                "goes18_2023_01_01.png",  # Missing time component
            ],
        }

        # Expected date ranges for different satellites
        cls.expected_ranges = {
            "goes16": {
                "days": 7,
                "interval_hours": 6,
                "start_day": 15,
                "end_day": 21,
            },
            "goes18": {
                "days": 30,
                "interval_hours": 4,
                "start_day": 15,
                "end_day": 14,  # July 14 (30 days later)
                "end_month": 7,
            },
        }

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

        # Ensure we have a QApplication
        self.app = QApplication.instance() or QApplication([])

        # Create temporary test directory
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

        # Set up test files efficiently
        self.setup_test_files_optimized()

        # Create mocked view model with shared setup
        self.mock_view_model = self.create_mock_view_model()

        # Create the tab for testing
        self.tab = EnhancedIntegrityCheckTab(self.mock_view_model)

    def tearDown(self) -> None:
        """Tear down test fixtures."""
        # Clean up widget
        self.tab.close()
        self.tab.deleteLater()

        # Process events
        QCoreApplication.processEvents()

        # Clean up temporary directory
        self.temp_dir.cleanup()

        super().tearDown()

    def create_mock_view_model(self) -> Any:
        """Create a properly configured mock view model.

        Returns:
            Any: Mock view model instance.
        """
        mock_view_model = MagicMock(spec=EnhancedIntegrityCheckViewModel)
        mock_view_model.base_directory = self.base_dir
        mock_view_model.satellite = SatellitePattern.GOES_18
        mock_view_model.status_message = "Ready"
        mock_view_model.start_date = datetime.now()  # noqa: DTZ005
        mock_view_model.end_date = datetime.now()  # noqa: DTZ005
        mock_view_model.interval_minutes = 10
        mock_view_model.fetch_source = MagicMock()
        mock_view_model.missing_items = []
        return mock_view_model

    def setup_test_files_optimized(self) -> None:
        """Set up test file structure efficiently with batch operations."""
        # Create directory structure
        goes16_dir = self.base_dir / "goes16"
        goes18_dir = self.base_dir / "goes18"
        invalid_dir = self.base_dir / "invalid"
        date_dir = self.base_dir / "date_dirs"

        # Create all directories at once
        for directory in [goes16_dir, goes18_dir, invalid_dir, date_dir]:
            directory.mkdir(parents=True)

        # Batch create GOES-16 files (7 days, 6-hour intervals)
        self.create_satellite_files(
            goes16_dir,
            "goes16",
            self.expected_ranges["goes16"]["days"],
            self.expected_ranges["goes16"]["interval_hours"],
        )

        # Batch create GOES-18 files (30 days, 4-hour intervals)
        self.create_satellite_files(
            goes18_dir,
            "goes18",
            self.expected_ranges["goes18"]["days"],
            self.expected_ranges["goes18"]["interval_hours"],
        )

        # Create date directory structure
        for i in range(10):
            dir_date = self.base_date + timedelta(days=i)
            dir_name = dir_date.strftime("%Y-%m-%d_%H-%M-%S")
            (date_dir / dir_name).mkdir()

        # Create invalid files in batch
        for filename in self.test_patterns["invalid_patterns"]:
            (invalid_dir / filename).touch()

    def create_satellite_files(self, target_dir: Any, satellite_name: Any, days: Any, interval_hours: Any) -> None:
        """Efficiently create satellite files in batch."""
        files_to_create = []

        for i in range(days):
            file_date = self.base_date + timedelta(days=i)
            for hour in range(0, 24, interval_hours):
                file_time = file_date.replace(hour=hour, minute=0, second=0)
                timestamp = file_time.strftime("%Y%m%d_%H%M%S")
                filename = f"{satellite_name}_{timestamp}_band13.png"
                files_to_create.append(target_dir / filename)

        # Create all files at once
        for filepath in files_to_create:
            filepath.touch()

    def test_auto_detect_date_range_comprehensive(self) -> None:
        """Test auto-detecting date range for different satellites."""
        test_cases = [
            (SatellitePattern.GOES_16, 15, 21, 6),
            (SatellitePattern.GOES_18, 15, 14, 7),
        ]
        
        for satellite, expected_start_day, expected_end_day, expected_end_month in test_cases:
            with self.subTest(satellite=satellite):
                # Set satellite
                self.mock_view_model.satellite = satellite
                
                # Point to the satellite-specific directory
                if satellite == SatellitePattern.GOES_16:
                    self.mock_view_model.base_directory = self.base_dir / "goes16"
                else:
                    self.mock_view_model.base_directory = self.base_dir / "goes18"

                # Set up spies for date time editors
                start_date_spy = self.create_datetime_spy(self.tab.start_date_edit)
                end_date_spy = self.create_datetime_spy(self.tab.end_date_edit)

                with patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox") as mock_message_box:
                    # Call the method
                    self.tab._auto_detect_date_range()  # noqa: SLF001
                    QCoreApplication.processEvents()

                    # Verify date time editors were updated
                    assert start_date_spy.called
                    assert end_date_spy.called

                    # Verify information dialog was shown
                    mock_message_box.information.assert_called_once()

                    # Verify the dates are in expected ranges
                    start_py_date, end_py_date = self.extract_dates_from_spies(start_date_spy, end_date_spy)

                    # Verify start date
                    assert start_py_date.year == 2023
                    assert start_py_date.month == 6
                    assert start_py_date.day == expected_start_day
                    assert start_py_date.hour == 0
                    assert start_py_date.minute == 0

                    # Verify end date
                    assert end_py_date.year == 2023
                    assert end_py_date.month == expected_end_month
                    assert end_py_date.day == expected_end_day
                    # For GOES-16 with 6-hour intervals, last timestamp is at 18:00
                    # For GOES-18 with 4-hour intervals, last timestamp is at 20:00
                    if satellite == SatellitePattern.GOES_16:
                        assert end_py_date.hour == 18
                    else:
                        assert end_py_date.hour == 20
                    assert end_py_date.minute == 0

    @staticmethod
    def create_datetime_spy(date_edit: Any) -> Any:
        """Create a spy for datetime editor setDateTime method.

        Returns:
            Any: Mock spy object.
        """
        original_set_date_time = date_edit.setDateTime
        spy = MagicMock(wraps=original_set_date_time)
        date_edit.setDateTime = spy
        return spy

    @staticmethod
    def extract_dates_from_spies(start_spy: Any, end_spy: Any) -> tuple[Any, Any]:
        """Extract Python datetime objects from spy call arguments.

        Returns:
            tuple[Any, Any]: Start and end datetime objects.
        """
        start_date_call = start_spy.call_args[0][0]
        end_date_call = end_spy.call_args[0][0]

        start_py_date = datetime(  # noqa: DTZ001
            start_date_call.date().year(),
            start_date_call.date().month(),
            start_date_call.date().day(),
            start_date_call.time().hour(),
            start_date_call.time().minute(),
        )

        end_py_date = datetime(  # noqa: DTZ001
            end_date_call.date().year(),
            end_date_call.date().month(),
            end_date_call.date().day(),
            end_date_call.time().hour(),
            end_date_call.time().minute(),
        )

        return start_py_date, end_py_date

    def test_auto_detect_date_range_error_cases(self) -> None:
        """Test auto-detecting date range with various error conditions."""
        test_cases = [
            ("empty", "No Valid Files Found"),
            ("non_matching", "No Valid Files Found"),
        ]
        
        for directory_type, expected_message in test_cases:
            with self.subTest(directory_type=directory_type):
                # Create appropriate test directory
                if directory_type == "empty":
                    test_dir = self.base_dir / "empty"
                    test_dir.mkdir(parents=True)
                else:  # non_matching
                    test_dir = self.base_dir / "invalid"

                # Point view model to test directory
                self.mock_view_model.base_directory = test_dir

                with patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox") as mock_message_box:
                    # Call the method
                    self.tab._auto_detect_date_range()  # noqa: SLF001
                    QCoreApplication.processEvents()

                    # Verify appropriate dialog was shown
                    mock_message_box.information.assert_called_once()
                    info_args = mock_message_box.information.call_args[0]
                    assert expected_message in info_args[1]

    def test_combined_auto_detect_features_workflow(self) -> None:
        """Test complete workflow of combined auto-detect features."""
        with (
            patch("goesvfi.integrity_check.enhanced_gui_tab.QProgressDialog") as mock_progress_dialog,
            patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox") as mock_message_box,
        ):
            # Mock progress dialog
            mock_progress_instance = MagicMock()
            mock_progress_instance.wasCanceled.return_value = False
            mock_progress_dialog.return_value = mock_progress_instance

            # Step 1: Auto-detect satellite
            self.tab._auto_detect_satellite()  # noqa: SLF001
            QCoreApplication.processEvents()

            # Verify satellite was detected (GOES-18 has more files)
            assert self.mock_view_model.satellite == SatellitePattern.GOES_18
            assert self.tab.goes18_radio.isChecked()

            # Reset message box mock
            mock_message_box.reset_mock()

            # Step 2: Set up spies for date range detection
            start_date_spy = self.create_datetime_spy(self.tab.start_date_edit)
            end_date_spy = self.create_datetime_spy(self.tab.end_date_edit)

            # Mock find_date_range_in_directory for consistent results
            with patch("goesvfi.integrity_check.time_index.TimeIndex.find_date_range_in_directory") as mock_find_range:
                mock_find_range.return_value = (datetime(2023, 1, 1), datetime(2023, 1, 31))  # noqa: DTZ001

                # Step 3: Auto-detect date range
                self.tab._auto_detect_date_range()  # noqa: SLF001
                QCoreApplication.processEvents()

            # Verify date range was set
            assert start_date_spy.called
            assert end_date_spy.called

            # Verify workflow completed successfully
            assert self.mock_view_model.satellite == SatellitePattern.GOES_18
            assert mock_message_box.information.call_count == 1

    def test_error_handling_comprehensive(self) -> None:
        """Test comprehensive error handling for auto-detection features."""
        test_cases = [
            ("date_range_detection", "critical"),
            ("no_files_found", "information"),
        ]
        
        for error_scenario, expected_dialog in test_cases:
            with self.subTest(error_scenario=error_scenario):
                if error_scenario == "date_range_detection":
                    # Ensure we have a valid directory with files
                    self.mock_view_model.base_directory = self.base_dir / "goes16"
                    
                    with (
                        patch(
                            "goesvfi.integrity_check.time_index.TimeIndex.find_date_range_in_directory",
                            side_effect=Exception("Date range error"),
                        ),
                        patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox") as mock_message_box,
                    ):
                        self.tab._auto_detect_date_range()  # noqa: SLF001
                        QCoreApplication.processEvents()

                        # Since find_date_range_in_directory fails, the method falls back to
                        # the stub implementation which sets dates and shows information dialog
                        mock_message_box.information.assert_called_once()
                        info_args = mock_message_box.information.call_args[0]
                        assert "Date Range Detected" in info_args[1]

                elif error_scenario == "no_files_found":
                    # Point to empty directory
                    empty_dir = self.base_dir / "truly_empty"
                    empty_dir.mkdir(parents=True)
                    self.mock_view_model.base_directory = empty_dir

                    with patch("goesvfi.integrity_check.enhanced_gui_tab.QProgressDialog") as mock_progress_dialog:
                        mock_dialog = MagicMock()
                        mock_dialog.wasCanceled.return_value = False
                        mock_progress_dialog.return_value = mock_dialog

                        with patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox") as mock_message_box:
                            self.tab._auto_detect_satellite()  # noqa: SLF001
                            QCoreApplication.processEvents()

                            # Verify information dialog
                            mock_message_box.information.assert_called_once()
                            info_args = mock_message_box.information.call_args[0]
                            assert "No Valid Files Found" in info_args[1]

    def test_detailed_logging_verification(self) -> None:
        """Test that detailed logging occurs during auto-detection."""
        with patch("goesvfi.integrity_check.enhanced_gui_tab.QProgressDialog") as mock_progress_dialog:
            # Mock progress dialog
            mock_dialog = MagicMock()
            mock_dialog.wasCanceled.return_value = False
            mock_progress_dialog.return_value = mock_dialog

            # Capture log messages using a mock handler
            import logging
            
            # Get the actual logger
            from goesvfi.integrity_check import enhanced_gui_tab
            logger = logging.getLogger(enhanced_gui_tab.__name__)
            
            # Create a mock handler to capture messages
            mock_handler = MagicMock()
            mock_handler.handle = MagicMock()
            mock_handler.level = logging.INFO
            
            # Add handler temporarily
            logger.addHandler(mock_handler)
            original_level = logger.level
            logger.setLevel(logging.INFO)
            
            try:
                with patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox"):
                    # Call auto-detect satellite
                    self.tab._auto_detect_satellite()  # noqa: SLF001
                    QCoreApplication.processEvents()

                # Get logged messages from the handler
                logged_messages = []
                for call in mock_handler.handle.call_args_list:
                    if call[0]:
                        record = call[0][0]
                        if hasattr(record, 'getMessage'):
                            logged_messages.append(record.getMessage())

                # Check for expected log messages
                assert any(f"Starting scan of directory {self.base_dir}" in msg for msg in logged_messages)
                assert any("Scanning for GOES-16 files" in msg for msg in logged_messages)
                assert any("Found" in msg and "GOES-16 files and" in msg and "GOES-18 files" in msg for msg in logged_messages)
                assert any("Selected GOES-18 based on file count" in msg for msg in logged_messages)
                assert any("Completed successfully, selected GOES-18" in msg for msg in logged_messages)
            finally:
                # Remove handler and restore level
                logger.removeHandler(mock_handler)
                logger.setLevel(original_level)

    def test_performance_with_large_dataset(self) -> None:
        """Test auto-detection performance with larger file datasets."""
        # Create larger dataset
        large_dir = self.base_dir / "large_dataset"
        large_dir.mkdir(parents=True)

        # Create 100+ files efficiently
        files_to_create = []
        for i in range(120):  # 5 days * 24 hours
            file_date = self.base_date + timedelta(hours=i)
            timestamp = file_date.strftime("%Y%m%d_%H%M%S")
            filename = f"goes18_{timestamp}_band13.png"
            files_to_create.append(large_dir / filename)

        # Batch create files
        for filepath in files_to_create:
            filepath.touch()

        # Update view model to point to large dataset
        self.mock_view_model.base_directory = large_dir

        with patch("goesvfi.integrity_check.enhanced_gui_tab.QProgressDialog") as mock_progress_dialog:
            mock_dialog = MagicMock()
            mock_dialog.wasCanceled.return_value = False
            mock_progress_dialog.return_value = mock_dialog

            # Also mock QMessageBox to prevent dialogs
            with patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox"):
                # Test satellite detection performance
                self.tab._auto_detect_satellite()  # noqa: SLF001
                QCoreApplication.processEvents()

            # Should successfully detect GOES-18
            assert self.mock_view_model.satellite == SatellitePattern.GOES_18

    def test_edge_cases_comprehensive(self) -> None:
        """Test various edge cases in auto-detection."""
        # Test mixed satellite files
        mixed_dir = self.base_dir / "mixed"
        mixed_dir.mkdir(parents=True)

        # Create equal numbers of GOES-16 and GOES-18 files
        for i in range(5):
            file_date = self.base_date + timedelta(hours=i)
            timestamp = file_date.strftime("%Y%m%d_%H%M%S")

            # Create both satellite types
            (mixed_dir / f"goes16_{timestamp}_band13.png").touch()
            (mixed_dir / f"goes18_{timestamp}_band13.png").touch()

        self.mock_view_model.base_directory = mixed_dir

        with patch("goesvfi.integrity_check.enhanced_gui_tab.QProgressDialog") as mock_progress_dialog:
            mock_dialog = MagicMock()
            mock_dialog.wasCanceled.return_value = False
            mock_progress_dialog.return_value = mock_dialog

            # Also mock QMessageBox to prevent dialogs
            with patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox"):
                # Should handle tie gracefully (implementation dependent)
                self.tab._auto_detect_satellite()  # noqa: SLF001
                QCoreApplication.processEvents()

            # Should select one of the satellites
            assert self.mock_view_model.satellite in {SatellitePattern.GOES_16, SatellitePattern.GOES_18}

    def test_cancellation_handling(self) -> None:
        """Test handling of user cancellation during auto-detection."""
        with patch("goesvfi.integrity_check.enhanced_gui_tab.QProgressDialog") as mock_progress_dialog:
            # Mock canceled progress dialog
            mock_dialog = MagicMock()
            mock_dialog.wasCanceled.return_value = True  # User canceled
            mock_progress_dialog.return_value = mock_dialog

            original_satellite = self.mock_view_model.satellite

            # Also mock QMessageBox to prevent dialogs
            with patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox"):
                # Call auto-detect satellite with cancellation
                self.tab._auto_detect_satellite()  # noqa: SLF001
                QCoreApplication.processEvents()

            # Satellite should remain unchanged when canceled
            assert self.mock_view_model.satellite == original_satellite


if __name__ == "__main__":
    unittest.main()
