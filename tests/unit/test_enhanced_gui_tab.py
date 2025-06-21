"""Unit tests for the integrity_check enhanced GUI tab functionality."""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication

from goesvfi.integrity_check.enhanced_gui_tab import EnhancedIntegrityCheckTab
from goesvfi.integrity_check.enhanced_view_model import (
    EnhancedIntegrityCheckViewModel,
    FetchSource,
)
from goesvfi.integrity_check.time_index import SatellitePattern
from goesvfi.integrity_check.view_model import ScanStatus

# Import our test utilities
from tests.utils.pyqt_async_test import PyQtAsyncTestCase


class TestEnhancedIntegrityCheckTab(PyQtAsyncTestCase):
    """Test cases for the EnhancedIntegrityCheckTab class."""

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
        start_date = datetime.now() - timedelta(days=1)
        end_date = datetime.now()
        self.mock_view_model.start_date = start_date
        self.mock_view_model.end_date = end_date

        # Setup for disk space
        self.mock_view_model.get_disk_space_info = MagicMock(return_value=(10.0, 100.0))

        # Create the tab widget under test
        self.tab = EnhancedIntegrityCheckTab(self.mock_view_model)

        # Add mock cleanup methods to the view model to avoid real calls
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

    def test_initialization(self):
        """Test that the tab initializes correctly."""
        # Check that enhanced UI elements are correctly set up
        assert self.tab.configure_fetchers_btn is not None
        assert self.tab.fetcher_status_label is not None
        assert self.tab.fetcher_status_label.text() == "CDN/S3 Ready"

        # Check that stores are initialized
        assert self.tab.cdn_store is not None
        assert self.tab.s3_store is not None

        # Check default fetcher configuration
        assert self.tab.fetcher_config["cdn"]["enabled"]
        assert self.tab.fetcher_config["s3"]["enabled"]
        assert self.tab.fetcher_config["fallback_strategy"] == "CDN first, then S3"

    @patch("goesvfi.integrity_check.enhanced_gui_tab.QMessageBox.information")
    def test_auto_detect_date_range(self, mock_message_box):
        """Test the auto-detect date range functionality."""
        # Create some dummy files in the test directory to avoid early return
        dummy_file = self.base_dir / "goes18_20230615_000000_band13.png"
        dummy_file.parent.mkdir(parents=True, exist_ok=True)
        dummy_file.touch()

        # Call the method
        self.tab._auto_detect_date_range()

        # Check that dates were set (using the stub implementation)
        start_datetime = self.tab.start_date_edit.dateTime().toPyDateTime()
        end_datetime = self.tab.end_date_edit.dateTime().toPyDateTime()

        # Verify dates were set as expected by the stub
        # Since we created a goes18 file, it should use GOES-18 dates
        assert start_datetime.year == 2023
        assert start_datetime.month == 6
        assert start_datetime.day == 15
        assert end_datetime.year == 2023
        assert end_datetime.month == 7
        assert end_datetime.day == 14

        # Verify message box was called but without showing the actual popup
        mock_message_box.assert_called_once()

    def test_fetcher_configuration(self):
        """Test the fetcher configuration functionality."""
        # Test default configuration
        default_config = self.tab._default_fetcher_config()
        assert default_config["cdn"]["enabled"]
        assert default_config["s3"]["enabled"]
        assert default_config["cdn"]["max_retries"] == 3
        assert default_config["s3"]["timeout"] == 30
        assert default_config["fallback_strategy"] == "CDN first, then S3"

        # Test configuration update
        new_config = {
            "cdn": {"enabled": False, "max_retries": 5, "timeout": 60},
            "s3": {"enabled": True, "max_retries": 2, "timeout": 45},
            "fallback_strategy": "S3 only",
        }
        self.tab.fetcher_config = new_config
        self.tab._update_fetcher_config()

        # Verify status label was updated
        assert self.tab.fetcher_status_label.text() == "Strategy: S3 only"

    def test_get_scan_summary(self):
        """Test the scan summary functionality."""
        # Get summary (should return empty counts since tree_model is not set)
        summary = self.tab.get_scan_summary()

        # Verify summary structure exists with default values
        assert summary["total"] == 0
        assert summary["missing"] == 0
        assert summary["downloaded"] == 0
        assert summary["failed"] == 0
        assert "goes16" in summary["by_satellite"]
        assert "goes18" in summary["by_satellite"]
        assert isinstance(summary["by_product"], dict)


# Run the tests if this file is executed directly
if __name__ == "__main__":
    unittest.main()
