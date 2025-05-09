"""Integration tests for the integrity check tab functionality."""

import unittest
import tempfile
import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock, call

from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt6.QtCore import Qt, QDateTime, QDate, QTime, QCoreApplication

# Import our test utilities
from tests.utils.pyqt_async_test import PyQtAsyncTestCase, AsyncSignalWaiter, async_test

from goesvfi.integrity_check.cache_db import CacheDB
from goesvfi.integrity_check.remote.cdn_store import CDNStore
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.view_model import ScanStatus
from goesvfi.integrity_check.enhanced_view_model import (
    EnhancedIntegrityCheckViewModel, FetchSource
)
from goesvfi.integrity_check.enhanced_gui_tab import EnhancedIntegrityCheckTab
from goesvfi.integrity_check.time_index import SatellitePattern, TimeIndex


class TestIntegrityCheckTabIntegration(PyQtAsyncTestCase):
    """Integration tests for the IntegrityCheckTab with both UI and ViewModel."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Call parent setUp
        super().setUp()
        
        # Ensure we have a QApplication instance
        self.app = QApplication.instance() or QApplication([])
        
        # Create temporary directory for test data
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        
        # Create test files to be detected
        # Create GOES-16 test files
        self.goes16_dir = self.base_dir / "goes16"
        self.goes16_dir.mkdir(parents=True)
        for i in range(3):
            ts = datetime(2023, 1, 1, 12, i*5, 0)
            filename = f"goes16_{ts.strftime('%Y%m%d_%H%M%S')}_band13.png"
            (self.goes16_dir / filename).touch()
        
        # Create GOES-18 test files (more of these)
        self.goes18_dir = self.base_dir / "goes18"
        self.goes18_dir.mkdir(parents=True)
        for i in range(5):
            ts = datetime(2023, 1, 1, 12, i*5, 0)
            filename = f"goes18_{ts.strftime('%Y%m%d_%H%M%S')}_band13.png"
            (self.goes18_dir / filename).touch()
            
        # Mock dependencies for the ViewModel
        self.mock_cache_db = MagicMock(spec=CacheDB)
        self.mock_cache_db.reset_database = AsyncMock()
        self.mock_cache_db.close = AsyncMock()
        
        self.mock_cdn_store = MagicMock(spec=CDNStore)
        self.mock_cdn_store.download = AsyncMock()
        self.mock_cdn_store.exists = AsyncMock(return_value=True)
        self.mock_cdn_store.close = AsyncMock()
        
        self.mock_s3_store = MagicMock(spec=S3Store)
        self.mock_s3_store.download = AsyncMock()
        self.mock_s3_store.exists = AsyncMock(return_value=True)
        self.mock_s3_store.close = AsyncMock()
        
        # Create real view model
        self.view_model = EnhancedIntegrityCheckViewModel(
            cache_db=self.mock_cache_db,
            cdn_store=self.mock_cdn_store,
            s3_store=self.mock_s3_store
        )
        
        # Set the base directory
        self.view_model.base_directory = self.base_dir
        
        # Create the tab widget
        self.tab = EnhancedIntegrityCheckTab(self.view_model)
        
        # Create a window to prevent orphaned widgets
        self.window = QMainWindow()
        self.window.setCentralWidget(self.tab)
        
        # Don't show the window to avoid UI interference
        # self.window.show()
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Clean up the window
        if hasattr(self, 'window'):
            self.window.close()
            self.window.deleteLater()
        
        # Process events to ensure deleteLater executes
        QCoreApplication.processEvents()
        
        # Clean up temporary directory
        self.temp_dir.cleanup()
        
        # Clean up view model resources
        if hasattr(self, 'view_model'):
            try:
                self.view_model.cleanup()
            except Exception:
                pass
                
        # Call parent tearDown
        super().tearDown()
    
    def test_satellite_auto_detection(self):
        """Test that satellite auto-detection works with real files."""
        # Patch the QMessageBox to avoid dialog showing
        with patch('goesvfi.integrity_check.enhanced_gui_tab.QMessageBox.information'):
            # Don't mock TimeIndex scanning - let it use the real directory
            # But patch the QProgressDialog to avoid UI
            with patch('goesvfi.integrity_check.enhanced_gui_tab.QProgressDialog'):
                # Call the auto-detect method
                self.tab._auto_detect_satellite()
                
                # Process events to ensure signals propagate
                QCoreApplication.processEvents()
                
                # Verify the correct satellite was detected (GOES-18 has more files)
                self.assertEqual(self.view_model.satellite, SatellitePattern.GOES_18)
                self.assertTrue(self.tab.goes18_radio.isChecked())
                self.assertFalse(self.tab.goes16_radio.isChecked())
    
    def test_fetch_source_radio_buttons(self):
        """Test that fetch source radio buttons correctly update the view model."""
        # Initial state should be AUTO
        self.assertEqual(self.view_model.fetch_source, FetchSource.AUTO)
        self.assertTrue(self.tab.auto_radio.isChecked())
        
        # Click CDN radio
        self.tab.cdn_radio.setChecked(True)
        
        # Process events to ensure signals propagate
        QCoreApplication.processEvents()
        
        # Check view model was updated
        self.assertEqual(self.view_model.fetch_source, FetchSource.CDN)
        
        # Click S3 radio
        self.tab.s3_radio.setChecked(True)
        
        # Process events
        QCoreApplication.processEvents()
        
        # Check view model was updated
        self.assertEqual(self.view_model.fetch_source, FetchSource.S3)
        
        # Click LOCAL radio
        self.tab.local_radio.setChecked(True)
        
        # Process events
        QCoreApplication.processEvents()
        
        # Check view model was updated
        self.assertEqual(self.view_model.fetch_source, FetchSource.LOCAL)
        
        # Back to AUTO
        self.tab.auto_radio.setChecked(True)
        
        # Process events
        QCoreApplication.processEvents()
        
        # Check view model was updated
        self.assertEqual(self.view_model.fetch_source, FetchSource.AUTO)
    
    def test_enhanced_status_updates(self):
        """Test that status updates correctly format different message types."""
        # Test error message
        self.tab._update_status("Error: something went wrong")
        
        # Get the formatted message
        status_text = self.tab.status_label.text()
        
        # Verify formatting
        self.assertIn("color: #ff6666", status_text)  # Red color for errors
        self.assertIn("Error: something went wrong", status_text)
        
        # Test success message
        self.tab._update_status("Completed successfully")
        
        # Get the formatted message
        status_text = self.tab.status_label.text()
        
        # Verify formatting
        self.assertIn("color: #66ff66", status_text)  # Green color for success
        self.assertIn("Completed successfully", status_text)
        
        # Test in-progress message
        self.tab._update_status("Scanning for files...")
        
        # Get the formatted message
        status_text = self.tab.status_label.text()
        
        # Verify formatting
        self.assertIn("color: #66aaff", status_text)  # Blue color for in-progress
        self.assertIn("Scanning for files...", status_text)
    
    def test_enhanced_progress_updates(self):
        """Test that progress updates include more detailed information."""
        # Test with ETA
        self.tab._update_progress(25, 100, 120.0)  # 25%, ETA: 2min
        
        # Verify progress bar format
        progress_format = self.tab.progress_bar.format()
        self.assertIn("25%", progress_format)
        self.assertIn("ETA: 2m 0s", progress_format)
        self.assertIn("(25/100)", progress_format)
        
        # Test without ETA
        self.tab._update_progress(50, 100, 0.0)  # 50%, no ETA
        
        # Verify progress bar format
        progress_format = self.tab.progress_bar.format()
        self.assertIn("50%", progress_format)
        self.assertIn("(50/100)", progress_format)
    
    def test_setting_date_range_from_ui(self):
        """Test that changes to date range widgets correctly update the view model."""
        # Set start date to 2023-01-01 00:00
        start_date = QDateTime(
            QDate(2023, 1, 1),
            QTime(0, 0)
        )
        self.tab.start_date_edit.setDateTime(start_date)
        
        # Set end date to 2023-01-02 23:59
        end_date = QDateTime(
            QDate(2023, 1, 2),
            QTime(23, 59)
        )
        self.tab.end_date_edit.setDateTime(end_date)
        
        # Process events
        QCoreApplication.processEvents()
        
        # Now start a scan to trigger view model update from UI
        with patch('goesvfi.integrity_check.enhanced_gui_tab.EnhancedIntegrityCheckViewModel.start_enhanced_scan'):
            self.tab._start_enhanced_scan()
            
            # Verify view model date range was updated
            expected_start = datetime(2023, 1, 1, 0, 0, 0)
            expected_end = datetime(2023, 1, 2, 23, 59, 0)
            
            self.assertEqual(self.view_model.start_date.year, expected_start.year)
            self.assertEqual(self.view_model.start_date.month, expected_start.month)
            self.assertEqual(self.view_model.start_date.day, expected_start.day)
            self.assertEqual(self.view_model.start_date.hour, expected_start.hour)
            self.assertEqual(self.view_model.start_date.minute, expected_start.minute)
            
            self.assertEqual(self.view_model.end_date.year, expected_end.year)
            self.assertEqual(self.view_model.end_date.month, expected_end.month)
            self.assertEqual(self.view_model.end_date.day, expected_end.day)
            self.assertEqual(self.view_model.end_date.hour, expected_end.hour)
            self.assertEqual(self.view_model.end_date.minute, expected_end.minute)


# Run the tests if this file is executed directly
if __name__ == '__main__':
    unittest.main()