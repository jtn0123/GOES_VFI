"""
Integration tests for GOES Imagery Tab UI
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from goesvfi.integrity_check.goes_imagery import (
    ChannelType,
    ImageryMode,
    ProcessingMode,
    ProductType,
)
from goesvfi.integrity_check.goes_imagery_tab import (
    GOESImageryTab,
    ImageSelectionPanel,
    ImageViewPanel,
)

# Create QApplication instance for tests
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)


class TestImageSelectionPanel(unittest.TestCase):
    """Tests for the image selection panel."""

    def setUp(self):
        """Set up test fixture."""
        self.panel = ImageSelectionPanel()

        # Capture emitted signals
        self.request_data = None
        self.panel.imageRequested.connect(self.captureRequest)

    def captureRequest(self, data):
        """Capture request data from signal."""
        self.request_data = data

    def test_initial_state(self):
        """Test initial state of the panel."""
        # Check default selection
        self.assertTrue(self.panel.ch13_btn.isChecked())
        self.assertTrue(self.panel.image_product_btn.isChecked())

        # Check default combo box selections
        self.assertEqual(self.panel.resolution_combo.currentData(), "2.7k")
        self.assertEqual(
            self.panel.processing_combo.currentData(), ProcessingMode.BASIC
        )
        self.assertEqual(self.panel.size_combo.currentData(), "1200")

    def test_ui_state_update(self):
        """Test UI state update based on mode."""
        # Check initial state (Image Product Mode)
        self.assertTrue(self.panel.size_combo.isEnabled())
        self.assertFalse(self.panel.resolution_combo.isEnabled())
        self.assertFalse(self.panel.processing_combo.isEnabled())

        # Switch to Raw Data Mode
        self.panel.raw_data_btn.setChecked(True)
        self.panel.updateUIState()

        # Check updated state
        self.assertFalse(self.panel.size_combo.isEnabled())
        self.assertTrue(self.panel.resolution_combo.isEnabled())
        self.assertTrue(self.panel.processing_combo.isEnabled())

    def test_request_image(self):
        """Test requesting an image."""
        # Set up selections
        self.panel.ch13_btn.setChecked(True)
        index = self.panel.product_combo.findData(ProductType.FULL_DISK)
        self.panel.product_combo.setCurrentIndex(index)
        self.panel.image_product_btn.setChecked(True)

        # Request image
        self.panel.download_btn.click()

        # Verify request data
        self.assertIsNotNone(self.request_data)
        self.assertEqual(self.request_data["channel"], ChannelType.CH13)
        self.assertEqual(self.request_data["product_type"], ProductType.FULL_DISK)
        self.assertEqual(self.request_data["mode"], ImageryMode.IMAGE_PRODUCT)
        self.assertEqual(self.request_data["size"], "1200")


class TestImageViewPanel(unittest.TestCase):
    """Tests for the image view panel."""

    def setUp(self):
        """Set up test fixture."""
        self.panel = ImageViewPanel()

    def test_initial_state(self):
        """Test initial state of the panel."""
        self.assertEqual(self.panel.image_label.text(), "No imagery loaded")
        self.assertEqual(self.panel.status_label.text(), "")
        self.assertFalse(self.panel.progress.isVisible())

    def test_show_loading(self):
        """Test showing loading state."""
        self.panel.showLoading("Test loading...")
        self.assertEqual(self.panel.status_label.text(), "Test loading...")
        self.assertIsNotNone(self.panel.image_label.movie())

    def test_clear_image(self):
        """Test clearing image."""
        # First set some state
        self.panel.showLoading()
        self.panel.setProgress(50)

        # Then clear
        self.panel.clearImage()

        # Check cleared state
        self.assertEqual(self.panel.image_label.text(), "No imagery loaded")
        self.assertEqual(self.panel.status_label.text(), "")
        self.assertFalse(self.panel.progress.isVisible())

    def test_show_image(self):
        """Test showing an image (without using QPixmap mock)."""
        # Use a different approach to test the functionality
        # without dealing with Qt's QPixmap internals

        # Create a test Path
        test_path = Path(self.panel.image_label.objectName() or "dummy_path")

        # Make a mock with special behavior for exists method
        with patch.object(Path, "exists", return_value=True), patch(
            "os.path.getsize", return_value=1024
        ), patch("PyQt6.QtGui.QPixmap"), patch.object(
            self.panel.image_label, "setPixmap"
        ):
            # Test showing image
            self.panel.showImage(test_path)

            # Verify status message contains expected text
            self.assertIn("Loaded:", self.panel.status_label.text())
            self.assertIn(test_path.name, self.panel.status_label.text())


@patch("goesvfi.integrity_check.goes_imagery_tab.GOESImageryManager")
class TestGOESImageryTab(unittest.TestCase):
    """Integration tests for GOES Imagery Tab."""

    def setUp(self):
        """Set up test fixture."""
        # Create tab with mocked manager
        with patch("goesvfi.integrity_check.goes_imagery_tab.GOESImageryManager"):
            self.tab = GOESImageryTab()

    def test_initial_state(self, mock_manager_class):
        """Test initial state of the tab."""
        # Verify panels exist
        self.assertIsNotNone(self.tab.selection_panel)
        self.assertIsNotNone(self.tab.view_panel)

    def test_handle_image_request(self, mock_manager_class):
        """Test handling an image request."""
        # Setup mock
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        mock_image_path = MagicMock()
        mock_image_path.exists.return_value = True
        mock_image_path.name = "test_image.jpg"
        mock_manager.get_imagery.return_value = mock_image_path
        self.tab.imagery_manager = mock_manager

        # Mock the view panel's showImage method
        self.tab.view_panel.showImage = MagicMock()

        # Create request
        request = {
            "channel": ChannelType.CH13,
            "product_type": ProductType.FULL_DISK,
            "mode": ImageryMode.IMAGE_PRODUCT,
            "processing": ProcessingMode.BASIC,
            "resolution": None,
            "size": "1200",
        }

        # Handle request directly (bypass timer)
        self.tab.processImageRequest(request)

        # Verify manager was called with correct args
        mock_manager.get_imagery.assert_called_once_with(
            channel=ChannelType.CH13,
            product_type=ProductType.FULL_DISK,
            mode=ImageryMode.IMAGE_PRODUCT,
            processing=ProcessingMode.BASIC,
            resolution=None,
            size="1200",
        )

        # Verify view panel was updated
        self.tab.view_panel.showImage.assert_called_once_with(mock_image_path)


if __name__ == "__main__":
    unittest.main()
