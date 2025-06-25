"""Unit tests for the PreviewManager component."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
from PIL import Image
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication

from goesvfi.gui_components.preview_manager import PreviewManager
from goesvfi.pipeline.image_processing_interfaces import ImageData


class TestPreviewManager(unittest.TestCase):
    """Test cases for PreviewManager."""

    @classmethod
    def setUpClass(cls):
        """Set up QApplication for all tests."""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        """Set up test fixtures."""
        self.preview_manager = PreviewManager()

        # Create temporary directory for test images
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

        # Track emitted signals
        self.preview_updated_count = 0
        self.preview_error_message = None
        self.last_before_pixmap = None
        self.last_after_pixmap = None

        # Connect signals
        self.preview_manager.preview_updated.connect(self._on_preview_updated)
        self.preview_manager.preview_error.connect(self._on_preview_error)

    def _on_preview_updated(self, first: QPixmap, middle: QPixmap, last: QPixmap):
        """Track preview update signals."""
        self.preview_updated_count += 1
        self.last_before_pixmap = first
        self.last_after_pixmap = last

    def _on_preview_error(self, message: str):
        """Track preview error signals."""
        self.preview_error_message = message

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def _create_test_image(self, name: str, size: tuple = (100, 100), color: tuple = (255, 0, 0)):
        """Create a test image file."""
        img = Image.new("RGB", size, color)
        path = self.test_dir / name
        img.save(path, "PNG")
        return path

    def test_initialization(self):
        """Test PreviewManager initialization."""
        self.assertIsNotNone(self.preview_manager.image_loader)
        self.assertIsNotNone(self.preview_manager.cropper)
        self.assertIsNotNone(self.preview_manager.sanchez_processor)
        self.assertIsNone(self.preview_manager.current_input_dir)
        self.assertIsNone(self.preview_manager.current_crop_rect)
        self.assertIsNone(self.preview_manager.first_frame_data)
        self.assertIsNone(self.preview_manager.last_frame_data)

    def test_get_first_last_paths_with_images(self):
        """Test getting first and last image paths."""
        # Create test images
        img1 = self._create_test_image("001_image.png")
        img2 = self._create_test_image("002_image.png")
        img3 = self._create_test_image("003_image.png")

        # Get paths
        first, middle, last = self.preview_manager._get_first_middle_last_paths(self.test_dir)

        # Verify
        self.assertEqual(first, img1)
        self.assertEqual(last, img3)

    def test_get_first_last_paths_empty_directory(self):
        """Test getting paths from empty directory."""
        first, middle, last = self.preview_manager._get_first_middle_last_paths(self.test_dir)

        self.assertIsNone(first)
        self.assertIsNone(last)

    def test_get_first_last_paths_no_images(self):
        """Test getting paths when directory has no image files."""
        # Create non-image files
        (self.test_dir / "file.txt").write_text("test")
        (self.test_dir / "data.json").write_text("{}")

        first, middle, last = self.preview_manager._get_first_middle_last_paths(self.test_dir)

        self.assertIsNone(first)
        self.assertIsNone(last)

    def test_get_first_last_paths_single_image(self):
        """Test getting paths with only one image."""
        img = self._create_test_image("single.png")

        first, middle, last = self.preview_manager._get_first_middle_last_paths(self.test_dir)

        self.assertEqual(first, img)
        self.assertEqual(last, img)

    @patch("goesvfi.gui_components.preview_manager.ImageLoader")
    def test_load_preview_images_success(self, mock_loader_class):
        """Test successful preview image loading."""
        # Create test images
        self._create_test_image("001.png", color=(255, 0, 0))
        self._create_test_image("002.png", color=(0, 255, 0))

        # Mock image loader
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader

        # Create mock ImageData
        red_data = ImageData(np.full((100, 100, 3), 255, dtype=np.uint8))
        red_data.image_data[:, :, 1:] = 0  # Red only
        green_data = ImageData(np.full((100, 100, 3), 255, dtype=np.uint8))
        green_data.image_data[:, :, 0] = 0  # Green only
        green_data.image_data[:, :, 2] = 0

        mock_loader.load.side_effect = [red_data, green_data]

        # Reinitialize with mocked loader
        self.preview_manager = PreviewManager()
        self.preview_manager.preview_updated.connect(self._on_preview_updated)

        # Load previews
        result = self.preview_manager.load_preview_images(self.test_dir)

        # Verify
        self.assertTrue(result)
        self.assertEqual(self.preview_updated_count, 1)
        self.assertIsNotNone(self.last_before_pixmap)
        self.assertIsNotNone(self.last_after_pixmap)
        self.assertFalse(self.last_before_pixmap.isNull())
        self.assertFalse(self.last_after_pixmap.isNull())

    def test_load_preview_images_no_images(self):
        """Test loading previews from directory with no images."""
        result = self.preview_manager.load_preview_images(self.test_dir)

        self.assertFalse(result)
        self.assertEqual(self.preview_error_message, "No images found in directory")

    @patch("goesvfi.gui_components.preview_manager.ImageLoader")
    def test_load_preview_images_with_crop(self, mock_loader_class):
        """Test loading previews with crop rectangle."""
        # Create test images
        self._create_test_image("001.png", size=(200, 200))
        self._create_test_image("002.png", size=(200, 200))

        # Mock components
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader

        # Create mock ImageData
        test_data = ImageData(np.zeros((200, 200, 3), dtype=np.uint8))
        mock_loader.load.return_value = test_data

        # Reinitialize preview manager first
        self.preview_manager = PreviewManager()

        # Mock cropper on the new instance
        with patch.object(self.preview_manager.cropper, "crop") as mock_crop:
            cropped_data = ImageData(np.zeros((100, 100, 3), dtype=np.uint8))
            mock_crop.return_value = cropped_data

            # Load with crop
            crop_rect = (50, 50, 100, 100)
            result = self.preview_manager.load_preview_images(self.test_dir, crop_rect=crop_rect)

            # Verify cropper was called
            self.assertEqual(mock_crop.call_count, 2)  # Once for each image
            # Preview manager converts (x, y, width, height) to (left, top, right, bottom)
            expected_coords = (50, 50, 150, 150)  # (x, y, x+width, y+height)
            mock_crop.assert_called_with(test_data, expected_coords)

    @patch("goesvfi.gui_components.preview_manager.ImageLoader")
    def test_load_preview_images_with_sanchez(self, mock_loader_class):
        """Test loading previews with Sanchez processing."""
        # Create test images
        self._create_test_image("001.png")
        self._create_test_image("002.png")

        # Mock components
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        test_data = ImageData(np.zeros((100, 100, 3), dtype=np.uint8))
        mock_loader.load.return_value = test_data

        # Reinitialize preview manager first
        self.preview_manager = PreviewManager()

        # Mock Sanchez processor on the new instance
        with patch.object(self.preview_manager.sanchez_processor, "process") as mock_sanchez:
            processed_data = ImageData(np.ones((100, 100, 3), dtype=np.uint8) * 128)
            mock_sanchez.return_value = processed_data

            # Load with Sanchez
            result = self.preview_manager.load_preview_images(
                self.test_dir,
                apply_sanchez=True,
                sanchez_resolution=1000,  # Will map to res_km=4
            )

            # Verify Sanchez was called
            self.assertEqual(mock_sanchez.call_count, 2)
            mock_sanchez.assert_called_with(test_data, res_km=4)

    def test_numpy_to_qpixmap_rgb(self):
        """Test converting RGB numpy array to QPixmap."""
        # Create RGB array
        array = np.zeros((100, 100, 3), dtype=np.uint8)
        array[:50, :50, 0] = 255  # Red quadrant
        array[:50, 50:, 1] = 255  # Green quadrant
        array[50:, :50, 2] = 255  # Blue quadrant

        # Convert
        pixmap = self.preview_manager._numpy_to_qpixmap(array)

        # Verify
        self.assertIsInstance(pixmap, QPixmap)
        self.assertFalse(pixmap.isNull())
        self.assertEqual(pixmap.width(), 100)
        self.assertEqual(pixmap.height(), 100)

    def test_numpy_to_qpixmap_grayscale(self):
        """Test converting grayscale numpy array to QPixmap."""
        # Create grayscale array
        array = np.arange(0, 256, 256 / 100).reshape(10, 10).astype(np.uint8)

        # Convert
        pixmap = self.preview_manager._numpy_to_qpixmap(array)

        # Verify
        self.assertIsInstance(pixmap, QPixmap)
        self.assertFalse(pixmap.isNull())
        self.assertEqual(pixmap.width(), 10)
        self.assertEqual(pixmap.height(), 10)

    def test_numpy_to_qpixmap_rgba(self):
        """Test converting RGBA numpy array to QPixmap."""
        # Create RGBA array
        array = np.zeros((50, 50, 4), dtype=np.uint8)
        array[:, :, :3] = 255  # White
        array[:, :, 3] = 128  # Half transparent

        # Convert
        pixmap = self.preview_manager._numpy_to_qpixmap(array)

        # Verify
        self.assertIsInstance(pixmap, QPixmap)
        self.assertFalse(pixmap.isNull())
        self.assertEqual(pixmap.width(), 50)
        self.assertEqual(pixmap.height(), 50)

    def test_numpy_to_qpixmap_invalid(self):
        """Test converting invalid array to QPixmap."""
        # Create invalid array (wrong shape)
        array = np.zeros((10, 10, 10, 10), dtype=np.uint8)

        # Convert
        pixmap = self.preview_manager._numpy_to_qpixmap(array)

        # Should return empty pixmap
        self.assertTrue(pixmap.isNull())

    def test_scale_preview_pixmap(self):
        """Test scaling preview pixmap."""
        # Create a pixmap
        original = QPixmap(200, 200)
        original.fill()

        # Scale to smaller size
        target_size = QSize(100, 100)
        scaled = self.preview_manager.scale_preview_pixmap(original, target_size)

        # Verify
        self.assertEqual(scaled.width(), 100)
        self.assertEqual(scaled.height(), 100)

    def test_scale_preview_pixmap_null(self):
        """Test scaling null pixmap."""
        # Create null pixmap
        null_pixmap = QPixmap()

        # Scale
        scaled = self.preview_manager.scale_preview_pixmap(null_pixmap, QSize(100, 100))

        # Should return null
        self.assertTrue(scaled.isNull())

    def test_get_current_frame_data(self):
        """Test getting current frame data."""
        # Initially None
        first, middle, last = self.preview_manager.get_current_frame_data()
        self.assertIsNone(first)
        self.assertIsNone(middle)
        self.assertIsNone(last)

        # Set some data
        self.preview_manager.first_frame_data = ImageData(np.zeros((10, 10, 3), dtype=np.uint8))
        self.preview_manager.middle_frame_data = ImageData(np.full((10, 10, 3), 128, dtype=np.uint8))
        self.preview_manager.last_frame_data = ImageData(np.ones((10, 10, 3), dtype=np.uint8))

        # Get data
        first, middle, last = self.preview_manager.get_current_frame_data()
        self.assertIsNotNone(first)
        self.assertIsNotNone(middle)
        self.assertIsNotNone(last)

    def test_clear_previews(self):
        """Test clearing preview data."""
        # Set some data
        self.preview_manager.first_frame_data = ImageData(np.zeros((10, 10, 3), dtype=np.uint8))
        self.preview_manager.last_frame_data = ImageData(np.ones((10, 10, 3), dtype=np.uint8))
        self.preview_manager.current_input_dir = Path("/test")
        self.preview_manager.current_crop_rect = (0, 0, 10, 10)

        # Clear
        self.preview_manager.clear_previews()

        # Verify all cleared
        self.assertIsNone(self.preview_manager.first_frame_data)
        self.assertIsNone(self.preview_manager.last_frame_data)
        self.assertIsNone(self.preview_manager.current_input_dir)
        self.assertIsNone(self.preview_manager.current_crop_rect)

    @patch("goesvfi.gui_components.preview_manager.ImageLoader")
    def test_load_preview_images_error_handling(self, mock_loader_class):
        """Test error handling during preview loading."""
        # Create test image
        self._create_test_image("001.png")
        self._create_test_image("002.png")

        # Mock loader to raise exception
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load.side_effect = Exception("Load failed")

        # Reinitialize with mocked loader
        self.preview_manager = PreviewManager()
        self.preview_manager.preview_error.connect(self._on_preview_error)

        # Load should fail gracefully
        result = self.preview_manager.load_preview_images(self.test_dir)

        self.assertFalse(result)
        self.assertIn("Failed to load preview images", self.preview_error_message)


if __name__ == "__main__":
    unittest.main()
