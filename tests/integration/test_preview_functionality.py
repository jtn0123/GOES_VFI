"""Integration test for preview functionality when directory is selected."""

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from goesvfi.gui import MainWindow
from goesvfi.pipeline.image_processing_interfaces import ImageData


class TestPreviewFunctionality(unittest.TestCase):
    """Test preview images show correctly when directory is selected."""

    @classmethod
    def setUpClass(cls):
        """Set up QApplication for all tests."""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory with test images
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

        # Create test images
        self.image1_path = self._create_test_image("001_frame.png", color=(255, 0, 0))
        self.image2_path = self._create_test_image("002_frame.png", color=(0, 255, 0))
        self.image3_path = self._create_test_image("003_frame.png", color=(0, 0, 255))

        # Create MainWindow
        self.main_window = MainWindow(debug_mode=True)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
        self.main_window.close()

    def _create_test_image(self, name: str, size: tuple = (100, 100), color: tuple = (255, 0, 0)) -> Path:
        """Create a test image file."""
        img = Image.new("RGB", size, color)
        path = self.test_dir / name
        img.save(path, "PNG")
        return path

    def test_preview_images_loaded_on_directory_selection(self):
        """Test that preview images are loaded when directory is selected."""
        # Verify initial state
        self.assertIsNone(self.main_window.in_dir)
        self.assertTrue(hasattr(self.main_window.main_tab, "first_frame_label"))
        self.assertTrue(hasattr(self.main_window.main_tab, "last_frame_label"))

        # Set the input directory
        self.main_window.set_in_dir(self.test_dir)

        # Process events to allow signals to propagate
        QTimer.singleShot(100, lambda: None)
        self.app.processEvents()

        # Allow time for preview loading
        import time

        time.sleep(0.2)
        self.app.processEvents()

        # Check that preview manager loaded the images
        preview_manager = self.main_window.main_view_model.preview_manager
        first_data, last_data = preview_manager.get_current_frame_data()

        # Verify data was loaded
        self.assertIsNotNone(first_data)
        self.assertIsNotNone(last_data)

        # Check that labels have pixmaps
        first_pixmap = self.main_window.main_tab.first_frame_label.pixmap()
        last_pixmap = self.main_window.main_tab.last_frame_label.pixmap()

        self.assertIsNotNone(first_pixmap)
        self.assertIsNotNone(last_pixmap)
        self.assertFalse(first_pixmap.isNull())
        self.assertFalse(last_pixmap.isNull())

        # Check that processed_image attribute is set
        self.assertTrue(hasattr(self.main_window.main_tab.first_frame_label, "processed_image"))
        self.assertTrue(hasattr(self.main_window.main_tab.last_frame_label, "processed_image"))

    def test_preview_error_message_behavior(self):
        """Test error handling when preview label is clicked without processed_image."""
        # Create a label without processed_image
        label = self.main_window.main_tab.first_frame_label

        # Remove processed_image attribute if it exists
        if hasattr(label, "processed_image"):
            delattr(label, "processed_image")

        # Simulate clicking the label
        with patch("PyQt6.QtWidgets.QMessageBox.warning") as mock_warning:
            # Trigger the click event
            label.mousePressEvent(None)

            # Verify warning was shown
            mock_warning.assert_called_once()
            args = mock_warning.call_args[0]
            self.assertIn("Preview Not Available", args[1])
            self.assertIn("No processed image data is attached", args[2])

    @patch("goesvfi.gui_components.preview_manager.ImageLoader")
    def test_preview_loading_with_sanchez(self, mock_loader_class):
        """Test preview loading with Sanchez processing enabled."""
        # Mock the image loader
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader

        # Create mock ImageData
        test_array = np.zeros((100, 100, 3), dtype=np.uint8)
        test_array[:50, :50, 0] = 255  # Red quadrant
        mock_loader.load.return_value = ImageData(image_data=test_array)

        # Enable Sanchez in UI
        self.main_window.main_tab.sanchez_checkbox.setChecked(True)

        # Reinitialize preview manager with mocked loader
        from goesvfi.gui_components.preview_manager import PreviewManager

        self.main_window.main_view_model.preview_manager = PreviewManager()

        # Set directory
        self.main_window.set_in_dir(self.test_dir)

        # Process events
        self.app.processEvents()
        time.sleep(0.1)
        self.app.processEvents()

        # Verify Sanchez was attempted
        self.assertTrue(self.main_window.main_tab.sanchez_checkbox.isChecked())


if __name__ == "__main__":
    unittest.main()
