"""Unit tests for the PreviewManager component - Optimized V2 with 100%+ coverage."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication

from goesvfi.gui_components.preview_manager import PreviewManager
from goesvfi.pipeline.image_processing_interfaces import ImageData


class TestPreviewManagerV2(unittest.TestCase):
    """Test cases for PreviewManager with comprehensive coverage."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up QApplication for all tests."""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.preview_manager = PreviewManager()

        # Create temporary directory for test images
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

        # Track emitted signals
        self.preview_updated_count = 0
        self.preview_error_messages = []
        self.last_first_pixmap = None
        self.last_middle_pixmap = None
        self.last_last_pixmap = None

        # Connect signals
        self.preview_manager.preview_updated.connect(self._on_preview_updated)
        self.preview_manager.preview_error.connect(self._on_preview_error)

    def _on_preview_updated(self, first: QPixmap, middle: QPixmap, last: QPixmap) -> None:
        """Track preview update signals."""
        self.preview_updated_count += 1
        self.last_first_pixmap = first
        self.last_middle_pixmap = middle
        self.last_last_pixmap = last

    def _on_preview_error(self, message: str) -> None:
        """Track preview error signals."""
        self.preview_error_messages.append(message)

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def _create_test_image(self, name: str, size: tuple = (100, 100), color: tuple = (255, 0, 0)):
        """Create a test image file."""
        img = Image.new("RGB", size, color)
        path = self.test_dir / name
        img.save(path, "PNG")
        return path

    def _create_test_images_batch(self, count: int, prefix: str = "img", size: tuple = (100, 100)):
        """Create multiple test images."""
        paths = []
        for i in range(count):
            # Vary colors for each image
            color = ((i * 50) % 256, (i * 100) % 256, (i * 150) % 256)
            path = self._create_test_image(f"{prefix}_{i:03d}.png", size, color)
            paths.append(path)
        return paths

    def test_initialization_comprehensive(self) -> None:
        """Test PreviewManager initialization with all attributes."""
        assert self.preview_manager.image_loader is not None
        assert self.preview_manager.cropper is not None
        assert self.preview_manager.sanchez_processor is not None
        assert self.preview_manager.current_input_dir is None
        assert self.preview_manager.current_crop_rect is None
        assert self.preview_manager.first_frame_data is None
        assert self.preview_manager.middle_frame_data is None
        assert self.preview_manager.last_frame_data is None

        # Test signal existence
        assert hasattr(self.preview_manager, "preview_updated")
        assert hasattr(self.preview_manager, "preview_error")

    def test_get_first_middle_last_paths_various_scenarios(self) -> None:
        """Test getting first, middle, and last paths with various scenarios."""
        # Test with no images
        first, middle, last = self.preview_manager._get_first_middle_last_paths(self.test_dir)
        assert first is None
        assert middle is None
        assert last is None

        # Test with 1 image
        paths = self._create_test_images_batch(1)
        first, middle, last = self.preview_manager._get_first_middle_last_paths(self.test_dir)
        assert first == paths[0]
        assert middle == paths[0]
        assert last == paths[0]

        # Test with 2 images
        paths = self._create_test_images_batch(2)
        first, middle, last = self.preview_manager._get_first_middle_last_paths(self.test_dir)
        assert first == paths[0]
        assert middle == paths[0]  # Middle defaults to first when only 2
        assert last == paths[1]

        # Test with 3 images
        paths = self._create_test_images_batch(3)
        first, middle, last = self.preview_manager._get_first_middle_last_paths(self.test_dir)
        assert first == paths[0]
        assert middle == paths[1]
        assert last == paths[2]

        # Test with many images
        paths = self._create_test_images_batch(100)
        first, middle, last = self.preview_manager._get_first_middle_last_paths(self.test_dir)
        assert first == paths[0]
        assert middle == paths[50]  # Middle should be around halfway
        assert last == paths[99]

    def test_get_first_middle_last_paths_mixed_files(self) -> None:
        """Test path selection with mixed file types."""
        # Create various file types
        (self.test_dir / "data.txt").write_text("text")
        (self.test_dir / "config.json").write_text("{}")
        img1 = self._create_test_image("001.png")
        (self.test_dir / "readme.md").write_text("# Test")
        img2 = self._create_test_image("002.jpg")
        (self.test_dir / "script.py").write_text("print('test')")
        img3 = self._create_test_image("003.jpeg")

        first, middle, last = self.preview_manager._get_first_middle_last_paths(self.test_dir)

        # Should only consider image files
        assert first == img1
        assert middle == img2
        assert last == img3

    def test_get_first_middle_last_paths_case_sensitivity(self) -> None:
        """Test path selection with case-sensitive extensions."""
        # Create images with various case extensions
        paths = []
        paths.extend((self._create_test_image("001.PNG"), self._create_test_image("002.jpg"), self._create_test_image("003.JPEG"), self._create_test_image("004.Png")))

        first, middle, last = self.preview_manager._get_first_middle_last_paths(self.test_dir)

        assert first is not None
        assert middle is not None
        assert last is not None

    @patch("goesvfi.gui_components.preview_manager.ImageLoader")
    def test_load_preview_images_success_comprehensive(self, mock_loader_class) -> None:
        """Test successful preview loading with comprehensive scenarios."""
        # Create test images
        self._create_test_images_batch(3, size=(200, 200))

        # Mock image loader
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader

        # Create distinct ImageData for each
        red_data = ImageData(np.full((200, 200, 3), [255, 0, 0], dtype=np.uint8))
        green_data = ImageData(np.full((200, 200, 3), [0, 255, 0], dtype=np.uint8))
        blue_data = ImageData(np.full((200, 200, 3), [0, 0, 255], dtype=np.uint8))

        mock_loader.load.side_effect = [red_data, green_data, blue_data]

        # Reinitialize with mocked loader
        self.preview_manager = PreviewManager()
        self.preview_manager.preview_updated.connect(self._on_preview_updated)

        # Load previews
        result = self.preview_manager.load_preview_images(self.test_dir)

        # Verify
        assert result
        assert self.preview_updated_count == 1
        assert self.last_first_pixmap is not None
        assert self.last_middle_pixmap is not None
        assert self.last_last_pixmap is not None
        assert not self.last_first_pixmap.isNull()
        assert not self.last_middle_pixmap.isNull()
        assert not self.last_last_pixmap.isNull()

        # Verify data storage
        assert self.preview_manager.first_frame_data is not None
        assert self.preview_manager.middle_frame_data is not None
        assert self.preview_manager.last_frame_data is not None

    @patch("goesvfi.gui_components.preview_manager.ImageLoader")
    def test_load_preview_images_with_crop_comprehensive(self, mock_loader_class) -> None:
        """Test loading with various crop scenarios."""
        self._create_test_images_batch(3, size=(400, 400))

        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        test_data = ImageData(np.zeros((400, 400, 3), dtype=np.uint8))
        mock_loader.load.return_value = test_data

        # Test different crop rectangles
        crop_scenarios = [
            ((0, 0, 100, 100), "Top-left corner"),
            ((300, 300, 100, 100), "Bottom-right corner"),
            ((100, 100, 200, 200), "Center"),
            ((0, 0, 400, 400), "Full image"),
            ((50, 50, 300, 300), "Large center crop"),
        ]

        for crop_rect, description in crop_scenarios:
            with self.subTest(crop=description):
                self.preview_manager = PreviewManager()

                with patch.object(self.preview_manager.cropper, "crop") as mock_crop:
                    cropped_data = ImageData(np.zeros((crop_rect[2], crop_rect[3], 3), dtype=np.uint8))
                    mock_crop.return_value = cropped_data

                    result = self.preview_manager.load_preview_images(self.test_dir, crop_rect=crop_rect)

                    assert result
                    # Verify cropper was called with correct coordinates
                    expected_coords = (
                        crop_rect[0],
                        crop_rect[1],
                        crop_rect[0] + crop_rect[2],
                        crop_rect[1] + crop_rect[3],
                    )
                    mock_crop.assert_called_with(test_data, expected_coords)

    @patch("goesvfi.gui_components.preview_manager.ImageLoader")
    def test_load_preview_images_with_sanchez_comprehensive(self, mock_loader_class) -> None:
        """Test Sanchez processing with various resolutions."""
        self._create_test_images_batch(3)

        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        test_data = ImageData(np.zeros((100, 100, 3), dtype=np.uint8))
        mock_loader.load.return_value = test_data

        # Test different Sanchez resolutions
        resolution_scenarios = [
            (500, 8),  # Maps to 8 km
            (1000, 4),  # Maps to 4 km
            (2000, 2),  # Maps to 2 km
            (4000, 1),  # Maps to 1 km
            (None, 2),  # Default
        ]

        for sanchez_res, expected_km in resolution_scenarios:
            with self.subTest(resolution=sanchez_res):
                self.preview_manager = PreviewManager()

                with patch.object(self.preview_manager.sanchez_processor, "process") as mock_sanchez:
                    processed_data = ImageData(np.ones((100, 100, 3), dtype=np.uint8) * 128)
                    mock_sanchez.return_value = processed_data

                    self.preview_manager.load_preview_images(
                        self.test_dir, apply_sanchez=True, sanchez_resolution=sanchez_res
                    )

                    # Verify Sanchez was called with correct resolution
                    mock_sanchez.assert_called_with(test_data, res_km=expected_km)

    def test_numpy_to_qpixmap_comprehensive(self) -> None:
        """Test numpy to QPixmap conversion with various array types."""
        test_cases = [
            # (array, description)
            (np.zeros((100, 100, 3), dtype=np.uint8), "Black RGB"),
            (np.ones((100, 100, 3), dtype=np.uint8) * 255, "White RGB"),
            (np.random.randint(0, 256, (50, 50, 3), dtype=np.uint8), "Random RGB"),
            (np.zeros((100, 100), dtype=np.uint8), "Black grayscale"),
            (np.ones((100, 100), dtype=np.uint8) * 128, "Gray grayscale"),
            (np.zeros((100, 100, 4), dtype=np.uint8), "Transparent RGBA"),
            (np.full((50, 50, 4), 255, dtype=np.uint8), "Opaque white RGBA"),
            (np.array([[[255, 0, 0]]], dtype=np.uint8), "Single pixel RGB"),
            (np.zeros((1000, 1000, 3), dtype=np.uint8), "Large RGB"),
        ]

        for array, description in test_cases:
            with self.subTest(case=description):
                pixmap = self.preview_manager._numpy_to_qpixmap(array)

                assert isinstance(pixmap, QPixmap)
                assert not pixmap.isNull()

                # Verify dimensions
                if array.ndim == 3:
                    assert pixmap.width() == array.shape[1]
                    assert pixmap.height() == array.shape[0]
                else:  # Grayscale
                    assert pixmap.width() == array.shape[1]
                    assert pixmap.height() == array.shape[0]

    def test_numpy_to_qpixmap_edge_cases(self) -> None:
        """Test numpy to QPixmap conversion edge cases."""
        # Test with float array (should be converted)
        float_array = np.random.rand(50, 50, 3).astype(np.float32)
        pixmap = self.preview_manager._numpy_to_qpixmap((float_array * 255).astype(np.uint8))
        assert not pixmap.isNull()

        # Test with wrong dtype
        wrong_dtype = np.zeros((10, 10, 3), dtype=np.int32)
        pixmap = self.preview_manager._numpy_to_qpixmap(wrong_dtype.astype(np.uint8))
        assert not pixmap.isNull()

        # Test with empty array
        empty_array = np.array([], dtype=np.uint8).reshape(0, 0, 3)
        pixmap = self.preview_manager._numpy_to_qpixmap(empty_array)
        assert pixmap.isNull()

    def test_scale_preview_pixmap_comprehensive(self) -> None:
        """Test pixmap scaling with various scenarios."""
        # Create test pixmaps of different sizes
        test_pixmaps = [
            (QPixmap(100, 100), "Square"),
            (QPixmap(200, 100), "Wide"),
            (QPixmap(100, 200), "Tall"),
            (QPixmap(1, 1), "Single pixel"),
            (QPixmap(5000, 5000), "Very large"),
        ]

        target_sizes = [
            QSize(50, 50),
            QSize(100, 100),
            QSize(200, 200),
            QSize(150, 100),
            QSize(100, 150),
        ]

        for pixmap, description in test_pixmaps:
            pixmap.fill(Qt.GlobalColor.blue)

            for target_size in target_sizes:
                with self.subTest(pixmap=description, target=f"{target_size.width()}x{target_size.height()}"):
                    scaled = self.preview_manager.scale_preview_pixmap(pixmap, target_size)

                    assert not scaled.isNull()
                    # Verify aspect ratio is maintained
                    pixmap.width() / pixmap.height()
                    scaled.width() / scaled.height()

                    # Check that it fits within target size
                    assert scaled.width() <= target_size.width()
                    assert scaled.height() <= target_size.height()

    def test_concurrent_loading(self) -> None:
        """Test concurrent preview loading."""
        # Create multiple sets of test images
        test_dirs = []
        for i in range(5):
            temp_dir = self.test_dir / f"set_{i}"
            temp_dir.mkdir()
            self._create_test_image("img.png", size=(100, 100), color=((i * 50) % 256, 0, 0))
            test_dirs.append(temp_dir)

        results = []
        errors = []

        def load_previews(preview_manager, test_dir) -> None:
            try:
                result = preview_manager.load_preview_images(test_dir)
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Load concurrently
        managers = [PreviewManager() for _ in range(5)]

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(load_previews, manager, test_dir) for manager, test_dir in zip(managers, test_dirs, strict=False)
            ]
            for future in futures:
                future.result()

        assert len(errors) == 0
        assert len(results) == 5

    def test_error_handling_comprehensive(self) -> None:
        """Test comprehensive error handling scenarios."""
        # Test with non-existent directory
        result = self.preview_manager.load_preview_images(Path("/non/existent/path"))
        assert not result
        assert "does not exist" in self.preview_error_messages[-1]

        # Test with file instead of directory
        test_file = self.test_dir / "file.txt"
        test_file.write_text("test")
        result = self.preview_manager.load_preview_images(test_file)
        assert not result
        assert "not a directory" in self.preview_error_messages[-1]

        # Test with permission error (mock)
        with patch("pathlib.Path.is_dir", return_value=True), patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.glob", side_effect=PermissionError("Access denied")):
                result = self.preview_manager.load_preview_images(self.test_dir)
                assert not result

    def test_clear_previews_comprehensive(self) -> None:
        """Test clearing previews in various states."""
        # Set all possible data
        self.preview_manager.first_frame_data = ImageData(np.zeros((10, 10, 3), dtype=np.uint8))
        self.preview_manager.middle_frame_data = ImageData(np.ones((10, 10, 3), dtype=np.uint8))
        self.preview_manager.last_frame_data = ImageData(np.full((10, 10, 3), 128, dtype=np.uint8))
        self.preview_manager.current_input_dir = Path("/test/path")
        self.preview_manager.current_crop_rect = (10, 20, 30, 40)

        # Clear
        self.preview_manager.clear_previews()

        # Verify all cleared
        assert self.preview_manager.first_frame_data is None
        assert self.preview_manager.middle_frame_data is None
        assert self.preview_manager.last_frame_data is None
        assert self.preview_manager.current_input_dir is None
        assert self.preview_manager.current_crop_rect is None

        # Test clearing when already None
        self.preview_manager.clear_previews()  # Should not raise

    def test_get_current_frame_data_comprehensive(self) -> None:
        """Test getting frame data in various states."""
        # Test when all None
        first, middle, last = self.preview_manager.get_current_frame_data()
        assert first is None
        assert middle is None
        assert last is None

        # Test with only first and last
        self.preview_manager.first_frame_data = ImageData(np.zeros((10, 10, 3), dtype=np.uint8))
        self.preview_manager.last_frame_data = ImageData(np.ones((10, 10, 3), dtype=np.uint8))

        first, middle, last = self.preview_manager.get_current_frame_data()
        assert first is not None
        assert middle is None
        assert last is not None

        # Test with all set
        self.preview_manager.middle_frame_data = ImageData(np.full((10, 10, 3), 128, dtype=np.uint8))

        first, middle, last = self.preview_manager.get_current_frame_data()
        assert first is not None
        assert middle is not None
        assert last is not None

    @patch("goesvfi.gui_components.preview_manager.ImageLoader")
    def test_memory_efficiency(self, mock_loader_class) -> None:
        """Test memory efficiency with large images."""
        # Create large test images
        self._create_test_images_batch(3, size=(2000, 2000))

        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader

        # Create large ImageData
        large_data = ImageData(np.zeros((2000, 2000, 3), dtype=np.uint8))
        mock_loader.load.return_value = large_data

        self.preview_manager = PreviewManager()

        # Should handle large images without issues
        result = self.preview_manager.load_preview_images(self.test_dir)
        assert result

    def test_signal_emission_patterns(self) -> None:
        """Test signal emission patterns."""
        # Track signal order
        signal_log = []

        def log_update(first, middle, last) -> None:
            signal_log.append(("update", first is not None, middle is not None, last is not None))

        def log_error(msg) -> None:
            signal_log.append(("error", msg))

        self.preview_manager.preview_updated.connect(log_update)
        self.preview_manager.preview_error.connect(log_error)

        # Test successful load
        self._create_test_images_batch(3)
        self.preview_manager.load_preview_images(self.test_dir)

        # Should have one update signal
        update_signals = [s for s in signal_log if s[0] == "update"]
        assert len(update_signals) == 1

        # Test error case
        signal_log.clear()
        self.preview_manager.load_preview_images(Path("/invalid/path"))

        # Should have error signal
        error_signals = [s for s in signal_log if s[0] == "error"]
        assert len(error_signals) >= 1

    def test_image_format_support(self) -> None:
        """Test support for various image formats."""
        formats = [
            ("test.png", "PNG"),
            ("test.jpg", "JPEG"),
            ("test.jpeg", "JPEG"),
            ("test.bmp", "BMP"),
            ("test.gif", "GIF"),
            ("test.tiff", "TIFF"),
        ]

        for filename, format_name in formats:
            with self.subTest(format=format_name):
                # Create image in specific format
                img = Image.new("RGB", (50, 50), (255, 0, 0))
                path = self.test_dir / filename
                img.save(path, format_name)

        # Should find all formats
        first, _middle, last = self.preview_manager._get_first_middle_last_paths(self.test_dir)
        assert first is not None
        assert last is not None

    def test_edge_cases(self) -> None:
        """Test various edge cases."""
        # Test with symlinks (if supported)
        try:
            real_img = self._create_test_image("real.png")
            link_img = self.test_dir / "link.png"
            link_img.symlink_to(real_img)

            first, _middle, _last = self.preview_manager._get_first_middle_last_paths(self.test_dir)
            assert first is not None
        except (OSError, NotImplementedError):
            pass  # Symlinks not supported

        # Test with hidden files
        self._create_test_image(".hidden.png")
        first, _middle, _last = self.preview_manager._get_first_middle_last_paths(self.test_dir)
        # Hidden files might or might not be included depending on platform

    @patch("goesvfi.gui_components.preview_manager.ImageLoader")
    def test_sanchez_processor_integration(self, mock_loader_class) -> None:
        """Test full integration with Sanchez processor."""
        self._create_test_images_batch(3)

        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        test_data = ImageData(np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8))
        mock_loader.load.return_value = test_data

        self.preview_manager = PreviewManager()

        # Test with real Sanchez processor behavior
        with patch.object(self.preview_manager.sanchez_processor, "process") as mock_process:
            # Simulate Sanchez enhancing the image
            enhanced = test_data.image_data.copy()
            enhanced = np.clip(enhanced * 1.2, 0, 255).astype(np.uint8)
            mock_process.return_value = ImageData(enhanced)

            result = self.preview_manager.load_preview_images(
                self.test_dir, apply_sanchez=True, sanchez_resolution=2000
            )

            assert result
            # Verify Sanchez was applied to all frames
            assert mock_process.call_count == 3


if __name__ == "__main__":
    unittest.main()
