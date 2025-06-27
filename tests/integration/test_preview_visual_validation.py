"""Comprehensive visual validation tests for preview functionality.

This test suite validates that preview images are actually displayed correctly
in the GUI, addressing the persistent issue of invisible/tiny previews.
"""

from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from PIL import Image
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication

from goesvfi.gui import MainWindow
from goesvfi.pipeline.image_processing_interfaces import ImageData


class TestPreviewVisualValidation(unittest.TestCase):
    """Test that preview images are actually visible and properly sized."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up QApplication for all tests."""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Create temporary directory with test images
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

        # Create test images with distinct colors and sizes
        self.create_test_images()

        # Create MainWindow but clear any existing directory settings
        with patch("goesvfi.utils.settings.sections.BasicSettings.apply_values") as mock_apply:
            # Mock apply_values to not set in_dir from settings
            def mock_apply_values(target_object, values) -> None:
                # Only apply non-directory settings
                for key, value in values.items():
                    if key != "in_dir" and hasattr(target_object, key):
                        setattr(target_object, key, value)

            mock_apply.side_effect = mock_apply_values

            self.main_window = MainWindow(debug_mode=True)
            # Ensure in_dir is None initially
            self.main_window.in_dir = None

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
        self.main_window.close()

    def create_test_images(self) -> None:
        """Create test images with different colors and known properties."""
        # Create first frame - red image
        img1 = Image.new("RGB", (500, 400), color=(255, 0, 0))
        self.img1_path = self.test_dir / "001_frame.png"
        img1.save(self.img1_path, "PNG")

        # Create middle frame - green image
        img2 = Image.new("RGB", (500, 400), color=(0, 255, 0))
        self.img2_path = self.test_dir / "002_frame.png"
        img2.save(self.img2_path, "PNG")

        # Create last frame - blue image
        img3 = Image.new("RGB", (500, 400), color=(0, 0, 255))
        self.img3_path = self.test_dir / "003_frame.png"
        img3.save(self.img3_path, "PNG")

    def wait_for_previews(self, timeout=2.0) -> bool:
        """Wait for preview images to load with timeout."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            self.app.processEvents()

            # Check if all preview pixmaps are loaded and non-null
            first_pixmap = self.main_window.main_tab.first_frame_label.pixmap()
            last_pixmap = self.main_window.main_tab.last_frame_label.pixmap()

            if first_pixmap and not first_pixmap.isNull() and last_pixmap and not last_pixmap.isNull():
                return True

            time.sleep(0.1)

        return False

    def test_preview_images_are_actually_visible(self) -> None:
        """Test that preview images are visible with proper dimensions."""
        # Verify initial state - no images loaded
        assert self.main_window.in_dir is None

        first_label = self.main_window.main_tab.first_frame_label
        last_label = self.main_window.main_tab.last_frame_label

        # Check initial pixmaps are null or empty
        initial_first = first_label.pixmap()
        initial_last = last_label.pixmap()

        if initial_first:
            assert initial_first.isNull()
        if initial_last:
            assert initial_last.isNull()

        # Set the input directory to trigger preview loading
        self.main_window.set_in_dir(self.test_dir)

        # Wait for preview loading to complete
        assert self.wait_for_previews(timeout=3.0), "Preview images failed to load within timeout"

        # Verify images are now loaded and visible
        first_pixmap = first_label.pixmap()
        last_pixmap = last_label.pixmap()

        assert first_pixmap is not None, "First frame pixmap should not be None"
        assert last_pixmap is not None, "Last frame pixmap should not be None"
        assert not first_pixmap.isNull(), "First frame pixmap should not be null"
        assert not last_pixmap.isNull(), "Last frame pixmap should not be null"

        # CRITICAL: Verify pixmaps have reasonable dimensions (not tiny like 80x80)
        first_size = first_pixmap.size()
        last_size = last_pixmap.size()

        assert first_size.width() >= 150, f"First frame width {first_size.width()} should be at least 150px"
        assert first_size.height() >= 150, f"First frame height {first_size.height()} should be at least 150px"
        assert last_size.width() >= 150, f"Last frame width {last_size.width()} should be at least 150px"
        assert last_size.height() >= 150, f"Last frame height {last_size.height()} should be at least 150px"

    def test_preview_label_minimum_size_constraints(self) -> None:
        """Test that preview labels maintain minimum size constraints."""
        first_label = self.main_window.main_tab.first_frame_label
        middle_label = self.main_window.main_tab.middle_frame_label
        last_label = self.main_window.main_tab.last_frame_label

        # Check minimum size constraints
        for label_name, label in [("first", first_label), ("middle", middle_label), ("last", last_label)]:
            min_size = label.minimumSize()
            assert min_size.width() >= 200, (
                f"{label_name} label minimum width should be at least 200px, got {min_size.width()}"
            )
            assert min_size.height() >= 200, (
                f"{label_name} label minimum height should be at least 200px, got {min_size.height()}"
            )

    def test_preview_scaling_logic(self) -> None:
        """Test the preview scaling logic with various label sizes."""
        # Get the preview manager
        preview_manager = self.main_window.main_view_model.preview_manager

        # Create a test pixmap
        test_pixmap = QPixmap(800, 600)
        test_pixmap.fill()

        # Test scaling with small target size (should use minimum 200x200)
        small_target = QSize(80, 80)  # This was causing the original problem
        scaled_small = preview_manager.scale_preview_pixmap(test_pixmap, small_target)

        # Should be scaled to at least 150x150 (aspect ratio preserved from 200x200 min)
        assert scaled_small.width() >= 150, f"Scaled pixmap width should be at least 150px, got {scaled_small.width()}"
        assert scaled_small.height() >= 150, (
            f"Scaled pixmap height should be at least 150px, got {scaled_small.height()}"
        )

        # Test scaling with large target size
        large_target = QSize(400, 400)
        scaled_large = preview_manager.scale_preview_pixmap(test_pixmap, large_target)

        # Should use the larger target size
        assert scaled_large.width() <= 400
        assert scaled_large.height() <= 400
        assert scaled_large.width() >= 300  # Aspect ratio maintained

    def test_preview_manager_data_integrity(self) -> None:
        """Test that preview manager loads and stores data correctly."""
        # Load preview images
        self.main_window.set_in_dir(self.test_dir)
        assert self.wait_for_previews(timeout=3.0)

        # Check preview manager data
        preview_manager = self.main_window.main_view_model.preview_manager
        first_data, middle_data, last_data = preview_manager.get_current_frame_data()

        # Verify data was loaded
        assert first_data is not None, "First frame data should be loaded"
        assert middle_data is not None, "Middle frame data should be loaded"
        assert last_data is not None, "Last frame data should be loaded"

        # Verify data has correct properties
        assert isinstance(first_data, ImageData), "First frame should be ImageData"
        assert isinstance(last_data, ImageData), "Last frame should be ImageData"

        # Check image data is proper numpy array
        assert first_data.image_data is not None, "First frame image_data should not be None"
        assert last_data.image_data is not None, "Last frame image_data should not be None"

        # Verify image dimensions match our test images
        if hasattr(first_data.image_data, "shape"):
            height, width = first_data.image_data.shape[:2]
            assert width == 500, f"First frame width should be 500, got {width}"
            assert height == 400, f"First frame height should be 400, got {height}"

    def test_preview_error_handling_with_empty_directory(self) -> None:
        """Test preview behavior with empty directory."""
        # Create empty directory
        empty_dir = tempfile.TemporaryDirectory()
        empty_path = Path(empty_dir.name)

        try:
            # Set empty directory
            self.main_window.set_in_dir(empty_path)

            # Process events
            self.app.processEvents()
            time.sleep(0.2)
            self.app.processEvents()

            # Verify no pixmaps are set (or they are null)
            first_pixmap = self.main_window.main_tab.first_frame_label.pixmap()
            last_pixmap = self.main_window.main_tab.last_frame_label.pixmap()

            if first_pixmap:
                assert first_pixmap.isNull(), "First frame should be null for empty directory"
            if last_pixmap:
                assert last_pixmap.isNull(), "Last frame should be null for empty directory"

        finally:
            empty_dir.cleanup()

    def test_preview_with_different_image_formats(self) -> None:
        """Test preview loading with different image formats."""
        # Create images in different formats
        formats_dir = tempfile.TemporaryDirectory()
        formats_path = Path(formats_dir.name)

        try:
            # Create JPEG image
            jpg_img = Image.new("RGB", (300, 300), color=(255, 255, 0))
            jpg_path = formats_path / "test.jpg"
            jpg_img.save(jpg_path, "JPEG")

            # Create PNG image
            png_img = Image.new("RGB", (300, 300), color=(255, 0, 255))
            png_path = formats_path / "test.png"
            png_img.save(png_path, "PNG")

            # Set directory and wait for loading
            self.main_window.set_in_dir(formats_path)
            assert self.wait_for_previews(timeout=3.0)

            # Verify images loaded
            first_pixmap = self.main_window.main_tab.first_frame_label.pixmap()
            last_pixmap = self.main_window.main_tab.last_frame_label.pixmap()

            assert first_pixmap is not None
            assert last_pixmap is not None
            assert not first_pixmap.isNull()
            assert not last_pixmap.isNull()

        finally:
            formats_dir.cleanup()

    def test_preview_labels_processed_image_attribute(self) -> None:
        """Test that processed_image attribute is set for zoom functionality."""
        # Load preview images
        self.main_window.set_in_dir(self.test_dir)
        assert self.wait_for_previews(timeout=3.0)

        # Check processed_image attributes
        first_label = self.main_window.main_tab.first_frame_label
        last_label = self.main_window.main_tab.last_frame_label

        assert hasattr(first_label, "processed_image"), "First frame label should have processed_image attribute"
        assert hasattr(last_label, "processed_image"), "Last frame label should have processed_image attribute"

        if hasattr(first_label, "processed_image") and first_label.processed_image:
            assert not first_label.processed_image.isNull(), "First frame processed_image should not be null"

        if hasattr(last_label, "processed_image") and last_label.processed_image:
            assert not last_label.processed_image.isNull(), "Last frame processed_image should not be null"

    def test_full_preview_workflow_end_to_end(self) -> None:
        """Comprehensive end-to-end test of the entire preview workflow."""

        # Step 1: Initial state
        assert self.main_window.in_dir is None

        # Step 2: Set directory
        self.main_window.set_in_dir(self.test_dir)

        # Step 3: Wait for loading
        assert self.wait_for_previews(timeout=3.0)

        # Step 4: Verify directory is set
        assert self.main_window.in_dir == self.test_dir

        # Step 5: Verify preview manager has data
        preview_manager = self.main_window.main_view_model.preview_manager
        first_data, _middle_data, last_data = preview_manager.get_current_frame_data()
        assert first_data is not None
        assert last_data is not None

        # Step 6: Verify labels have pixmaps
        first_pixmap = self.main_window.main_tab.first_frame_label.pixmap()
        last_pixmap = self.main_window.main_tab.last_frame_label.pixmap()
        assert first_pixmap is not None
        assert last_pixmap is not None
        assert not first_pixmap.isNull()
        assert not last_pixmap.isNull()

        # Step 7: Verify pixmap sizes are reasonable
        first_size = first_pixmap.size()
        last_size = last_pixmap.size()
        assert first_size.width() >= 150
        assert first_size.height() >= 150
        assert last_size.width() >= 150
        assert last_size.height() >= 150

        # Step 8: Verify processed_image attributes
        assert hasattr(self.main_window.main_tab.first_frame_label, "processed_image")
        assert hasattr(self.main_window.main_tab.last_frame_label, "processed_image")


if __name__ == "__main__":
    unittest.main()
