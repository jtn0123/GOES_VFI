"""Unit tests for enhanced status messages in the integrity check tab."""

import unittest
from unittest.mock import MagicMock, patch, call

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QCoreApplication

from goesvfi.integrity_check.enhanced_gui_tab import EnhancedIntegrityCheckTab
from goesvfi.integrity_check.enhanced_view_model import EnhancedIntegrityCheckViewModel
from goesvfi.integrity_check.time_index import SatellitePattern


class TestEnhancedStatusMessages(unittest.TestCase):
    """Test cases for enhanced status messages in the IntegrityCheckTab."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Ensure we have a QApplication
        self.app = QApplication.instance() or QApplication([])
        
        # Create mocked view model
        self.mock_view_model = MagicMock(spec=EnhancedIntegrityCheckViewModel)
        self.mock_view_model.satellite = SatellitePattern.GOES_18
        
        # Create the tab with mocked setText method
        with patch('PyQt6.QtWidgets.QLabel.setText') as self.mock_set_text:
            self.tab = EnhancedIntegrityCheckTab(self.mock_view_model)
    
    def tearDown(self):
        """Tear down test fixtures."""
        try:
            self.tab.close()
            self.tab.deleteLater()
            QCoreApplication.processEvents()
        except (AttributeError, RuntimeError):
            # Widget might already be deleted
            pass
    
    def test_step_progress_message_formatting(self):
        """Test that step progress messages are properly formatted."""
        # Test a step progress message (middle step)
        with patch('PyQt6.QtWidgets.QLabel.setText') as mock_set_text:
            self.tab._update_status("Step 3/5: Checking timestamps")
            mock_set_text.assert_called_once()
            
            # Should be formatted with blue color for progress steps
            text = mock_set_text.call_args[0][0]
            self.assertIn("color: #66aaff", text)  # Blue color
            self.assertIn("font-weight: bold", text)
            self.assertIn("Step 3/5:", text)
            self.assertIn("Checking timestamps", text)
    
    def test_completion_step_message_formatting(self):
        """Test that completion step messages are properly formatted."""
        # Test a completion step message
        with patch('PyQt6.QtWidgets.QLabel.setText') as mock_set_text:
            self.tab._update_status("Step 5/5: Scan complete")
            mock_set_text.assert_called_once()
            
            # Should be formatted with green color for completion
            text = mock_set_text.call_args[0][0]
            self.assertIn("color: #66ff66", text)  # Green color
            self.assertIn("font-weight: bold", text)
            self.assertIn("Step 5/5:", text)
            self.assertIn("Scan complete", text)
    
    def test_error_message_formatting(self):
        """Test that error messages are properly formatted with troubleshooting tips."""
        # Test a generic error message
        with patch('PyQt6.QtWidgets.QLabel.setText') as mock_set_text:
            self.tab._update_status("Error: Failed to process files")
            mock_set_text.assert_called_once()
            
            # Should be formatted with red color for errors
            text = mock_set_text.call_args[0][0]
            self.assertIn("color: #ff6666", text)  # Red color
            self.assertIn("font-weight: bold", text)
            self.assertIn("Error: Failed to process files", text)
    
    def test_unexpected_error_with_satellite_message(self):
        """Test that unexpected satellite errors include detailed troubleshooting tips."""
        with patch('PyQt6.QtWidgets.QLabel.setText') as mock_set_text:
            self.tab._update_status("Unexpected error GOES-18 data")
            mock_set_text.assert_called_once()
            
            # Should include detailed troubleshooting tips
            text = mock_set_text.call_args[0][0]
            self.assertIn("Troubleshooting Tips:", text)
            self.assertIn("Check your internet connection", text)
            self.assertIn("Verify satellite selection is correct", text)
            self.assertIn("Try a smaller date range", text)
    
    def test_unexpected_error_with_auto_detect(self):
        """Test that auto-detect error messages include specific troubleshooting tips."""
        with patch('PyQt6.QtWidgets.QLabel.setText') as mock_set_text:
            self.tab._update_status("Unexpected error auto detect what satellite it is")
            mock_set_text.assert_called_once()
            
            # Should include auto-detection specific troubleshooting tips
            text = mock_set_text.call_args[0][0]
            self.assertIn("Troubleshooting Tips:", text)
            self.assertIn("Check if your files follow the correct GOES naming pattern", text)
            self.assertIn("Ensure directory contains GOES-16 or GOES-18 files", text)
            self.assertIn("Try manually selecting the satellite type", text)
    
    def test_unexpected_error_with_fetch_download(self):
        """Test that download error messages include specific troubleshooting tips."""
        with patch('PyQt6.QtWidgets.QLabel.setText') as mock_set_text:
            self.tab._update_status("Unexpected error fetching or downloading the missing files")
            mock_set_text.assert_called_once()
            
            # Should include download-specific troubleshooting tips
            text = mock_set_text.call_args[0][0]
            self.assertIn("Troubleshooting Tips:", text)
            self.assertIn("Check your internet connection", text)
            self.assertIn("Verify you can access AWS S3 services", text)
            self.assertIn("Ensure the timestamp exists in NOAA archives", text)
    
    def test_s3_specific_error_message(self):
        """Test that S3 errors include specific troubleshooting tips."""
        with patch('PyQt6.QtWidgets.QLabel.setText') as mock_set_text:
            self.tab._update_status("Unexpected error aws s3 data")
            mock_set_text.assert_called_once()
            
            # Should include S3-specific troubleshooting tips
            text = mock_set_text.call_args[0][0]
            self.assertIn("Troubleshooting Tips:", text)
            self.assertIn("Check your internet connection", text)
            self.assertIn("Verify AWS S3 is accessible from your network", text)
            self.assertIn("Try using CDN source instead of S3", text)
    
    def test_timeout_error_message(self):
        """Test that timeout errors include specific troubleshooting tips."""
        with patch('PyQt6.QtWidgets.QLabel.setText') as mock_set_text:
            self.tab._update_status("Timeout error occurred")
            mock_set_text.assert_called_once()
            
            # Should include timeout-specific troubleshooting tips
            text = mock_set_text.call_args[0][0]
            self.assertIn("Connection Tips:", text)
            self.assertIn("Check your internet connection speed and stability", text)
    
    def test_download_operation_message(self):
        """Test that download operation messages include helpful information."""
        with patch('PyQt6.QtWidgets.QLabel.setText') as mock_set_text:
            self.tab._update_status("Downloading files")
            mock_set_text.assert_called_once()
            
            # Should include helpful download context
            text = mock_set_text.call_args[0][0]
            self.assertIn("color: #66aaff", text)  # Blue color
            self.assertIn("font-weight: bold", text)
            self.assertIn("Download speed depends on your internet connection", text)
    
    def test_scanning_operation_message(self):
        """Test that scanning operation messages include helpful information."""
        with patch('PyQt6.QtWidgets.QLabel.setText') as mock_set_text:
            self.tab._update_status("Scanning directory")
            mock_set_text.assert_called_once()
            
            # Should include helpful scanning context
            text = mock_set_text.call_args[0][0]
            self.assertIn("color: #66aaff", text)  # Blue color
            self.assertIn("font-weight: bold", text)
            self.assertIn("This may take a few moments depending on the date range", text)
    
    def test_satellite_detection_message(self):
        """Test that satellite detection messages include helpful information."""
        with patch('PyQt6.QtWidgets.QLabel.setText') as mock_set_text:
            self.tab._update_status("Detected satellite GOES-18")
            mock_set_text.assert_called_once()
            
            # Should include helpful detection context
            text = mock_set_text.call_args[0][0]
            self.assertIn("color: #66aaff", text)  # Blue color
            self.assertIn("Auto-detection complete", text)
            self.assertIn("You can proceed with the integrity check", text)
    
    def test_failed_downloads_message(self):
        """Test that failed download messages include helpful information."""
        with patch('PyQt6.QtWidgets.QLabel.setText') as mock_set_text:
            self.tab._update_status("Download complete: 0 successful, 3 failed")
            mock_set_text.assert_called_once()
            
            # Should include helpful failed download tips
            text = mock_set_text.call_args[0][0]
            self.assertIn("color: #66ff66", text)  # Green color for completion
            self.assertIn("Download Issues Tips:", text)
            self.assertIn("Check the application log for detailed error reasons", text)
            self.assertIn("Try a different date range or satellite", text)


if __name__ == '__main__':
    unittest.main()