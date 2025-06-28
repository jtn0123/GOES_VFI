"""Tests for ZoomManager functionality."""

from unittest.mock import Mock, patch

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QImage, QPixmap
import pytest

from goesvfi.gui_components.zoom_manager import ZoomManager


class TestZoomManager:
    """Test ZoomManager functionality."""

    @pytest.fixture()
    def zoom_manager(self):
        """Create ZoomManager instance for testing."""
        return ZoomManager()

    @pytest.fixture()
    def mock_clickable_label(self):
        """Create a mock ClickableLabel for testing."""
        label = Mock()
        label.objectName.return_value = "test_label"

        # Create a valid QImage for testing
        test_image = QImage(800, 600, QImage.Format.Format_RGB32)
        test_image.fill(Qt.GlobalColor.blue)
        label.processed_image = test_image

        return label

    @pytest.fixture()
    def large_mock_label(self):
        """Create a mock label with a large image requiring scaling."""
        label = Mock()
        label.objectName.return_value = "large_label"

        # Create a large image that would need scaling
        large_image = QImage(2560, 1440, QImage.Format.Format_RGB32)
        large_image.fill(Qt.GlobalColor.red)
        label.processed_image = large_image

        return label

    @patch("goesvfi.gui_components.zoom_manager.ZoomDialog")
    def test_show_zoom_success(self, mock_zoom_dialog, zoom_manager, mock_clickable_label) -> None:
        """Test successful zoom dialog display."""
        mock_dialog_instance = Mock()
        mock_zoom_dialog.return_value = mock_dialog_instance

        zoom_manager.show_zoom(mock_clickable_label)

        # Verify dialog was created and shown
        mock_zoom_dialog.assert_called_once()
        mock_dialog_instance.exec.assert_called_once()

        # Verify the dialog was called with a QPixmap
        call_args = mock_zoom_dialog.call_args[0]
        assert isinstance(call_args[0], QPixmap)
        assert not call_args[0].isNull()

    def test_show_zoom_no_processed_image_attribute(self, zoom_manager) -> None:
        """Test handling when label has no processed_image attribute."""
        label_without_image = Mock()
        label_without_image.objectName.return_value = "no_image_label"
        # Remove the processed_image attribute
        if hasattr(label_without_image, "processed_image"):
            delattr(label_without_image, "processed_image")

        with patch("goesvfi.gui_components.zoom_manager.LOGGER") as mock_logger:
            zoom_manager.show_zoom(label_without_image)

            # Should log warning and return early
            mock_logger.warning.assert_called_once()
            assert "no processed image attribute" in str(mock_logger.warning.call_args)

    def test_show_zoom_none_processed_image(self, zoom_manager) -> None:
        """Test handling when processed_image is None."""
        label_with_none = Mock()
        label_with_none.objectName.return_value = "none_image_label"
        label_with_none.processed_image = None

        with patch("goesvfi.gui_components.zoom_manager.LOGGER") as mock_logger:
            zoom_manager.show_zoom(label_with_none)

            # Should log warning and return early
            mock_logger.warning.assert_called_once()
            assert "no processed image attribute or it is None" in str(mock_logger.warning.call_args)

    def test_show_zoom_invalid_image_type(self, zoom_manager) -> None:
        """Test handling when processed_image is not a QImage."""
        label_with_invalid = Mock()
        label_with_invalid.objectName.return_value = "invalid_image_label"
        label_with_invalid.processed_image = "not_a_qimage"

        with patch("goesvfi.gui_components.zoom_manager.LOGGER") as mock_logger:
            zoom_manager.show_zoom(label_with_invalid)

            # Should log warning about wrong type
            mock_logger.warning.assert_called_once()
            assert "not a QImage" in str(mock_logger.warning.call_args)

    def test_show_zoom_null_qimage(self, zoom_manager) -> None:
        """Test handling when QImage is null/invalid."""
        label_with_null = Mock()
        label_with_null.objectName.return_value = "null_image_label"
        # Create a null QImage
        null_image = QImage()
        label_with_null.processed_image = null_image

        with patch("goesvfi.gui_components.zoom_manager.LOGGER") as mock_logger:
            zoom_manager.show_zoom(label_with_null)

            # Should log warning about failed pixmap creation
            mock_logger.warning.assert_called_once()
            assert "Failed to create QPixmap" in str(mock_logger.warning.call_args)

    @patch("goesvfi.gui_components.zoom_manager.ZoomDialog")
    def test_show_zoom_with_parent(self, mock_zoom_dialog, zoom_manager, mock_clickable_label) -> None:
        """Test zoom dialog with parent widget."""
        mock_parent = Mock()
        mock_dialog_instance = Mock()
        mock_zoom_dialog.return_value = mock_dialog_instance

        zoom_manager.show_zoom(mock_clickable_label, mock_parent)

        # Verify dialog was created with parent
        mock_zoom_dialog.assert_called_once()
        call_args = mock_zoom_dialog.call_args[0]
        assert call_args[1] is mock_parent

    @patch("goesvfi.gui_components.zoom_manager.QApplication")
    def test_scale_pixmap_for_display_no_scaling_needed(self, mock_qapp, zoom_manager) -> None:
        """Test scaling when image fits within screen."""
        # Mock screen with large available space
        mock_screen = Mock()
        mock_screen.availableGeometry.return_value.size.return_value = QSize(2000, 1500)
        mock_qapp.primaryScreen.return_value = mock_screen

        # Create small pixmap that doesn't need scaling
        small_pixmap = QPixmap(800, 600)
        small_pixmap.fill(Qt.GlobalColor.green)

        result = zoom_manager._scale_pixmap_for_display(small_pixmap)

        # Should return original pixmap without scaling
        assert result.size() == QSize(800, 600)

    @patch("goesvfi.gui_components.zoom_manager.QApplication")
    def test_scale_pixmap_for_display_scaling_needed(self, mock_qapp, zoom_manager) -> None:
        """Test scaling when image is larger than screen."""
        # Mock screen with limited space
        mock_screen = Mock()
        mock_screen.availableGeometry.return_value.size.return_value = QSize(1200, 800)
        mock_qapp.primaryScreen.return_value = mock_screen

        # Create large pixmap that needs scaling
        large_pixmap = QPixmap(2400, 1600)
        large_pixmap.fill(Qt.GlobalColor.red)

        result = zoom_manager._scale_pixmap_for_display(large_pixmap)

        # Should be scaled down to fit 90% of screen (1080x720)
        expected_max = QSize(1080, 720)
        assert result.size().width() <= expected_max.width()
        assert result.size().height() <= expected_max.height()
        assert not result.isNull()

    @patch("goesvfi.gui_components.zoom_manager.QApplication")
    def test_scale_pixmap_for_display_no_screen(self, mock_qapp, zoom_manager) -> None:
        """Test scaling fallback when screen info unavailable."""
        # Mock no screen available
        mock_qapp.primaryScreen.return_value = None

        # Create large pixmap
        large_pixmap = QPixmap(2000, 1500)
        large_pixmap.fill(Qt.GlobalColor.yellow)

        with patch("goesvfi.gui_components.zoom_manager.LOGGER") as mock_logger:
            result = zoom_manager._scale_pixmap_for_display(large_pixmap)

            # Should use fallback size (1024x768)
            assert result.size().width() <= 1024
            assert result.size().height() <= 768
            assert not result.isNull()

            # Should log warning about fallback
            mock_logger.warning.assert_called_once()
            assert "Could not get screen geometry" in str(mock_logger.warning.call_args)

    @patch("goesvfi.gui_components.zoom_manager.QApplication")
    def test_scale_pixmap_aspect_ratio_preservation(self, mock_qapp, zoom_manager) -> None:
        """Test that aspect ratio is preserved during scaling."""
        # Mock screen
        mock_screen = Mock()
        mock_screen.availableGeometry.return_value.size.return_value = QSize(1000, 800)
        mock_qapp.primaryScreen.return_value = mock_screen

        # Create wide pixmap (2:1 aspect ratio)
        wide_pixmap = QPixmap(2000, 1000)
        wide_pixmap.fill(Qt.GlobalColor.blue)

        result = zoom_manager._scale_pixmap_for_display(wide_pixmap)

        # Aspect ratio should be preserved (2:1)
        aspect_ratio = result.size().width() / result.size().height()
        expected_ratio = 2000 / 1000  # 2.0
        assert abs(aspect_ratio - expected_ratio) < 0.01  # Allow small floating point differences

    @patch("goesvfi.gui_components.zoom_manager.ZoomDialog")
    def test_show_zoom_logging(self, mock_zoom_dialog, zoom_manager, mock_clickable_label) -> None:
        """Test that appropriate logging occurs."""
        mock_dialog_instance = Mock()
        mock_zoom_dialog.return_value = mock_dialog_instance

        with patch("goesvfi.gui_components.zoom_manager.LOGGER") as mock_logger:
            zoom_manager.show_zoom(mock_clickable_label)

            # Should log entry and dialog creation
            assert mock_logger.debug.call_count >= 2

            # Check specific log messages
            debug_calls = [call[0][0] for call in mock_logger.debug.call_args_list]
            assert any("Entering show_zoom" in msg for msg in debug_calls)
            assert any("Showing ZoomDialog" in msg for msg in debug_calls)

    def test_show_zoom_label_without_object_name(self, zoom_manager) -> None:
        """Test handling label without objectName method."""
        label_no_name = Mock()
        # Remove objectName method
        if hasattr(label_no_name, "objectName"):
            delattr(label_no_name, "objectName")
        label_no_name.processed_image = None

        with patch("goesvfi.gui_components.zoom_manager.LOGGER") as mock_logger:
            # Should not crash, should handle gracefully
            zoom_manager.show_zoom(label_no_name)

            # Should still log warning about no processed image
            mock_logger.warning.assert_called_once()

    @patch("goesvfi.gui_components.zoom_manager.ZoomDialog")
    @patch("goesvfi.gui_components.zoom_manager.QApplication")
    def test_show_zoom_integration_with_scaling(
        self, mock_qapp, mock_zoom_dialog, zoom_manager, large_mock_label
    ) -> None:
        """Test complete workflow with large image requiring scaling."""
        # Mock screen for scaling
        mock_screen = Mock()
        mock_screen.availableGeometry.return_value.size.return_value = QSize(1920, 1080)
        mock_qapp.primaryScreen.return_value = mock_screen

        mock_dialog_instance = Mock()
        mock_zoom_dialog.return_value = mock_dialog_instance

        zoom_manager.show_zoom(large_mock_label)

        # Verify dialog was created
        mock_zoom_dialog.assert_called_once()
        mock_dialog_instance.exec.assert_called_once()

        # Verify the pixmap was scaled appropriately
        call_args = mock_zoom_dialog.call_args[0]
        scaled_pixmap = call_args[0]

        # Should be smaller than original (2560x1440) but not null
        assert not scaled_pixmap.isNull()
        assert scaled_pixmap.size().width() < 2560
        assert scaled_pixmap.size().height() < 1440

    def test_show_zoom_edge_case_very_small_image(self, zoom_manager) -> None:
        """Test with very small image (1x1 pixel)."""
        tiny_label = Mock()
        tiny_label.objectName.return_value = "tiny_label"

        # Create tiny image
        tiny_image = QImage(1, 1, QImage.Format.Format_RGB32)
        tiny_image.fill(Qt.GlobalColor.black)
        tiny_label.processed_image = tiny_image

        with patch("goesvfi.gui_components.zoom_manager.ZoomDialog") as mock_zoom_dialog:
            mock_dialog_instance = Mock()
            mock_zoom_dialog.return_value = mock_dialog_instance

            zoom_manager.show_zoom(tiny_label)

            # Should still work with tiny image
            mock_zoom_dialog.assert_called_once()
            mock_dialog_instance.exec.assert_called_once()

    @patch("goesvfi.gui_components.zoom_manager.QPixmap")
    def test_show_zoom_pixmap_creation_failure(self, mock_qpixmap_class, zoom_manager, mock_clickable_label) -> None:
        """Test handling when QPixmap.fromImage fails."""
        # Mock QPixmap.fromImage to return null pixmap
        mock_null_pixmap = Mock()
        mock_null_pixmap.isNull.return_value = True
        mock_qpixmap_class.fromImage.return_value = mock_null_pixmap

        with patch("goesvfi.gui_components.zoom_manager.LOGGER") as mock_logger:
            zoom_manager.show_zoom(mock_clickable_label)

            # Should log warning about failed pixmap creation
            mock_logger.warning.assert_called_once()
            assert "Failed to create QPixmap from processed image" in str(mock_logger.warning.call_args)

    def test_show_zoom_scaling_failure(self, zoom_manager, mock_clickable_label) -> None:
        """Test handling when scaling operation fails."""
        with patch.object(zoom_manager, "_scale_pixmap_for_display") as mock_scale:
            # Mock scaling to return null pixmap
            null_pixmap = QPixmap()
            mock_scale.return_value = null_pixmap

            with patch("goesvfi.gui_components.zoom_manager.LOGGER") as mock_logger:
                zoom_manager.show_zoom(mock_clickable_label)

                # Should log error about failed scaling
                mock_logger.error.assert_called_once()
                assert "Failed to create scaled pixmap" in str(mock_logger.error.call_args)

    @patch("goesvfi.gui_components.zoom_manager.QApplication")
    def test_scale_pixmap_edge_case_square_image(self, mock_qapp, zoom_manager) -> None:
        """Test scaling with square image."""
        mock_screen = Mock()
        mock_screen.availableGeometry.return_value.size.return_value = QSize(1000, 1000)
        mock_qapp.primaryScreen.return_value = mock_screen

        # Create square pixmap
        square_pixmap = QPixmap(1500, 1500)
        square_pixmap.fill(Qt.GlobalColor.cyan)

        result = zoom_manager._scale_pixmap_for_display(square_pixmap)

        # Should be scaled to fit 90% of screen (900x900)
        assert result.size().width() <= 900
        assert result.size().height() <= 900
        # Should maintain square aspect ratio
        assert result.size().width() == result.size().height()

    def test_zoom_manager_methods_are_instance_methods(self, zoom_manager) -> None:
        """Test that ZoomManager methods work as instance methods."""
        # Verify methods exist and are callable
        assert callable(zoom_manager.show_zoom)
        assert callable(zoom_manager._scale_pixmap_for_display)

        # Verify they're bound to the instance
        assert hasattr(zoom_manager.show_zoom, "__self__")
        assert hasattr(zoom_manager._scale_pixmap_for_display, "__self__")
