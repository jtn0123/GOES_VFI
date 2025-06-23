"""Integration test for crop dialog functionality."""

import pytest
from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication

from goesvfi.utils.gui_helpers import CropSelectionDialog


@pytest.fixture
def app():
    """Create a QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def test_image():
    """Create a test image."""
    image = QImage(800, 600, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.blue)
    return image


class TestCropDialogIntegration:
    """Integration tests for crop dialog functionality."""

    def test_crop_dialog_creation_and_workflow(self, app, test_image):
        """Test complete crop dialog workflow."""
        # Test creation without initial rect
        dialog = CropSelectionDialog(test_image)
        assert dialog.windowTitle() == "Select Crop Region"
        assert dialog.image == test_image
        assert dialog.scale_factor > 0

        # Test with initial rect
        initial_rect = QRect(100, 100, 200, 200)
        dialog_with_rect = CropSelectionDialog(test_image, initial_rect)
        assert dialog_with_rect.crop_label.selected_rect is not None

    def test_coordinate_conversion(self, app, test_image):
        """Test coordinate conversion between display and original."""
        dialog = CropSelectionDialog(test_image)

        # Simulate a selection
        display_rect = QRect(50, 50, 100, 100)
        dialog._store_final_selection(display_rect)

        # Get result in original coordinates
        original_rect = dialog.get_selected_rect()

        # Verify scaling is applied correctly
        expected_x = int(50 * dialog.scale_factor)
        expected_y = int(50 * dialog.scale_factor)
        expected_w = int(100 * dialog.scale_factor)
        expected_h = int(100 * dialog.scale_factor)

        assert original_rect.x() == expected_x
        assert original_rect.y() == expected_y
        assert original_rect.width() == expected_w
        assert original_rect.height() == expected_h

    def test_large_image_scaling(self, app):
        """Test that large images are scaled properly."""
        # Create a large image (satellite-like size)
        large_image = QImage(2712, 2712, QImage.Format.Format_RGB32)
        large_image.fill(Qt.GlobalColor.red)

        dialog = CropSelectionDialog(large_image)

        # Should be scaled down
        assert dialog.scale_factor > 1.0

        # Test coordinate conversion works with scaling
        display_rect = QRect(10, 10, 50, 50)
        dialog._store_final_selection(display_rect)
        original_rect = dialog.get_selected_rect()

        # Verify coordinates are scaled up correctly
        assert original_rect.width() > display_rect.width()
        assert original_rect.height() > display_rect.height()

    def test_edge_cases(self, app, test_image):
        """Test edge cases and error handling."""
        dialog = CropSelectionDialog(test_image)

        # Test no selection
        result = dialog.get_selected_rect()
        assert result.isNull()

        # Test zero-size selection
        dialog._store_final_selection(QRect(10, 10, 0, 0))
        result = dialog.get_selected_rect()
        assert result.isNull() or result == QRect()

        # Test null image
        null_image = QImage()
        null_dialog = CropSelectionDialog(null_image)
        assert null_dialog.image.isNull()
