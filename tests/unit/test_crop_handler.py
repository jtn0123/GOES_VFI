"""Tests for CropHandler functionality."""

from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from PyQt6.QtCore import QRect
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QDialog
import pytest

from goesvfi.gui_components.crop_handler import CropHandler


class TestCropHandler:
    """Test CropHandler functionality."""

    @pytest.fixture()
    def crop_handler(self):
        """Create CropHandler instance for testing."""
        return CropHandler()

    @pytest.fixture()
    def mock_main_window(self):
        """Create a comprehensive mock main window for testing."""
        main_window = Mock()

        # Directory setup
        main_window.in_dir = None
        main_window.current_crop_rect = None

        # Methods
        main_window._update_crop_buttons_state = Mock()
        main_window.request_previews_update = Mock()
        main_window.request_previews_update.emit = Mock()

        # Main tab with Sanchez checkbox
        main_tab = Mock()
        sanchez_checkbox = Mock()
        sanchez_checkbox.isChecked.return_value = False
        main_tab.sanchez_false_colour_checkbox = sanchez_checkbox

        # First frame label for preview
        first_frame_label = Mock()
        main_tab.first_frame_label = first_frame_label
        main_window.main_tab = main_tab

        return main_window

    @pytest.fixture()
    def temp_image_dir(self):
        """Create a temporary directory with test images."""
        with tempfile.TemporaryDirectory() as temp_dir:
            image_dir = Path(temp_dir)

            # Create test image files
            (image_dir / "image1.png").write_text("fake png")
            (image_dir / "image2.jpg").write_text("fake jpg")
            (image_dir / "image3.jpeg").write_text("fake jpeg")
            (image_dir / "not_image.txt").write_text("not an image")

            yield image_dir

    def test_on_crop_clicked_no_input_directory(self, crop_handler, mock_main_window) -> None:
        """Test crop clicked when no input directory is selected."""
        mock_main_window.in_dir = None

        with patch("goesvfi.gui_components.crop_handler.QMessageBox") as mock_msgbox:
            crop_handler.on_crop_clicked(mock_main_window)

            # Should show warning message
            mock_msgbox.warning.assert_called_once()
            call_args = mock_msgbox.warning.call_args[0]
            assert "select an input directory first" in call_args[2]

    def test_on_crop_clicked_invalid_directory(self, crop_handler, mock_main_window) -> None:
        """Test crop clicked when input directory doesn't exist."""
        mock_main_window.in_dir = Path("/nonexistent/directory")

        with patch("goesvfi.gui_components.crop_handler.QMessageBox") as mock_msgbox:
            crop_handler.on_crop_clicked(mock_main_window)

            # Should show warning message
            mock_msgbox.warning.assert_called_once()

    def test_on_crop_clicked_no_images(self, crop_handler, mock_main_window) -> None:
        """Test crop clicked when directory has no images."""
        with tempfile.TemporaryDirectory() as temp_dir:
            empty_dir = Path(temp_dir)
            # Create only non-image files
            (empty_dir / "text.txt").write_text("not an image")

            mock_main_window.in_dir = empty_dir

            with patch("goesvfi.gui_components.crop_handler.QMessageBox") as mock_msgbox:
                crop_handler.on_crop_clicked(mock_main_window)

                # Should show warning about no images
                mock_msgbox.warning.assert_called_once()
                call_args = mock_msgbox.warning.call_args[0]
                assert "No images found" in call_args[2]

    @patch("goesvfi.gui_components.crop_handler.QImage")
    def test_on_crop_clicked_image_load_failure(
        self, mock_qimage, crop_handler, mock_main_window, temp_image_dir
    ) -> None:
        """Test crop clicked when image loading fails."""
        mock_main_window.in_dir = temp_image_dir

        # Mock image loading to fail
        mock_qimage.return_value.isNull.return_value = True

        with patch.object(crop_handler, "prepare_image_for_crop_dialog", return_value=None):
            with patch("goesvfi.gui_components.crop_handler.QMessageBox") as mock_msgbox:
                crop_handler.on_crop_clicked(mock_main_window)

                # Should show error message
                mock_msgbox.critical.assert_called_once()
                call_args = mock_msgbox.critical.call_args[0]
                assert "Could not load or process image" in call_args[2]

    @patch("goesvfi.gui_components.crop_handler.QImage")
    def test_on_crop_clicked_success(self, mock_qimage, crop_handler, mock_main_window, temp_image_dir) -> None:
        """Test successful crop dialog workflow."""
        mock_main_window.in_dir = temp_image_dir

        # Mock successful image loading
        mock_image = Mock()
        mock_image.isNull.return_value = False
        mock_qimage.return_value = mock_image

        mock_pixmap = Mock()

        with patch.object(crop_handler, "prepare_image_for_crop_dialog", return_value=mock_pixmap):
            with patch.object(crop_handler, "show_crop_dialog") as mock_show_dialog:
                crop_handler.on_crop_clicked(mock_main_window)

                # Should call show_crop_dialog
                mock_show_dialog.assert_called_once_with(mock_main_window, mock_pixmap)

    def test_get_sorted_image_files_no_directory(self, crop_handler, mock_main_window) -> None:
        """Test getting image files when no directory is set."""
        mock_main_window.in_dir = None

        result = crop_handler.get_sorted_image_files(mock_main_window)

        assert result == []

    def test_get_sorted_image_files_with_images(self, crop_handler, mock_main_window, temp_image_dir) -> None:
        """Test getting image files from directory with mixed file types."""
        mock_main_window.in_dir = temp_image_dir

        result = crop_handler.get_sorted_image_files(mock_main_window)

        # Should return only image files, sorted
        assert len(result) == 3
        assert all(f.suffix.lower() in {".png", ".jpg", ".jpeg"} for f in result)
        assert result == sorted(result)  # Should be sorted

    def test_get_sorted_image_files_case_insensitive(self, crop_handler, mock_main_window) -> None:
        """Test that image file detection is case insensitive."""
        with tempfile.TemporaryDirectory() as temp_dir:
            image_dir = Path(temp_dir)

            # Create files with different case extensions
            (image_dir / "image1.PNG").write_text("fake png")
            (image_dir / "image2.JPG").write_text("fake jpg")
            (image_dir / "image3.JPEG").write_text("fake jpeg")

            mock_main_window.in_dir = image_dir

            result = crop_handler.get_sorted_image_files(mock_main_window)

            assert len(result) == 3

    @patch("goesvfi.gui_components.crop_handler.QImage")
    @patch("goesvfi.gui_components.crop_handler.QPixmap")
    def test_prepare_image_for_crop_dialog_original_image(
        self, mock_qpixmap, mock_qimage, crop_handler, mock_main_window
    ) -> None:
        """Test preparing original image for crop dialog."""
        # Disable Sanchez preview
        mock_main_window.main_tab.sanchez_false_colour_checkbox.isChecked.return_value = False

        # Mock successful image loading
        mock_image = Mock()
        mock_image.isNull.return_value = False
        mock_qimage.return_value = mock_image

        mock_pixmap_result = Mock()
        mock_qpixmap.fromImage.return_value = mock_pixmap_result

        test_path = Path("/test/image.png")
        result = crop_handler.prepare_image_for_crop_dialog(mock_main_window, test_path)

        # Should load original image
        mock_qimage.assert_called_once_with(str(test_path))
        mock_qpixmap.fromImage.assert_called_once_with(mock_image)
        assert result is mock_pixmap_result

    @patch("goesvfi.gui_components.crop_handler.QImage")
    def test_prepare_image_for_crop_dialog_original_load_failure(
        self, mock_qimage, crop_handler, mock_main_window
    ) -> None:
        """Test handling when original image loading fails."""
        # Disable Sanchez preview
        mock_main_window.main_tab.sanchez_false_colour_checkbox.isChecked.return_value = False

        # Mock failed image loading
        mock_image = Mock()
        mock_image.isNull.return_value = True
        mock_qimage.return_value = mock_image

        test_path = Path("/test/image.png")

        with patch("goesvfi.gui_components.crop_handler.LOGGER") as mock_logger:
            result = crop_handler.prepare_image_for_crop_dialog(mock_main_window, test_path)

            assert result is None
            mock_logger.error.assert_called_once()

    def test_prepare_image_for_crop_dialog_sanchez_enabled(self, crop_handler, mock_main_window) -> None:
        """Test preparing image with Sanchez preview enabled."""
        # Enable Sanchez preview
        mock_main_window.main_tab.sanchez_false_colour_checkbox.isChecked.return_value = True

        mock_processed_pixmap = Mock()

        with patch.object(crop_handler, "get_processed_preview_pixmap", return_value=mock_processed_pixmap):
            test_path = Path("/test/image.png")
            result = crop_handler.prepare_image_for_crop_dialog(mock_main_window, test_path)

            assert result is mock_processed_pixmap

    def test_prepare_image_for_crop_dialog_sanchez_fallback(self, crop_handler, mock_main_window) -> None:
        """Test fallback to original image when Sanchez processing fails."""
        # Enable Sanchez preview
        mock_main_window.main_tab.sanchez_false_colour_checkbox.isChecked.return_value = True

        with patch.object(crop_handler, "get_processed_preview_pixmap", return_value=None):
            with patch("goesvfi.gui_components.crop_handler.QImage") as mock_qimage:
                with patch("goesvfi.gui_components.crop_handler.QPixmap") as mock_qpixmap:
                    # Mock successful original image loading
                    mock_image = Mock()
                    mock_image.isNull.return_value = False
                    mock_qimage.return_value = mock_image

                    mock_pixmap_result = Mock()
                    mock_qpixmap.fromImage.return_value = mock_pixmap_result

                    test_path = Path("/test/image.png")
                    result = crop_handler.prepare_image_for_crop_dialog(mock_main_window, test_path)

                    # Should fall back to original image
                    assert result is mock_pixmap_result

    def test_prepare_image_for_crop_dialog_exception_handling(self, crop_handler, mock_main_window) -> None:
        """Test exception handling in image preparation."""
        mock_main_window.main_tab.sanchez_false_colour_checkbox.isChecked.side_effect = Exception("Test error")

        with patch("goesvfi.gui_components.crop_handler.LOGGER") as mock_logger:
            test_path = Path("/test/image.png")
            result = crop_handler.prepare_image_for_crop_dialog(mock_main_window, test_path)

            assert result is None
            mock_logger.exception.assert_called_once()

    def test_get_processed_preview_pixmap_success(self, crop_handler, mock_main_window) -> None:
        """Test getting processed preview pixmap successfully."""
        # Mock processed image on first frame label
        test_image = QImage(100, 100, QImage.Format.Format_RGB32)
        test_image.fill(0xFF0000)  # Red

        mock_main_window.main_tab.first_frame_label.processed_image = test_image

        with patch("goesvfi.gui_components.crop_handler.QPixmap") as mock_qpixmap:
            mock_pixmap_result = Mock()
            mock_qpixmap.fromImage.return_value = mock_pixmap_result

            result = crop_handler.get_processed_preview_pixmap(mock_main_window)

            assert result is mock_pixmap_result
            mock_qpixmap.fromImage.assert_called_once_with(test_image)

    def test_get_processed_preview_pixmap_no_label(self, crop_handler, mock_main_window) -> None:
        """Test getting processed preview when first frame label is missing."""
        delattr(mock_main_window.main_tab, "first_frame_label")

        with patch("goesvfi.gui_components.crop_handler.LOGGER") as mock_logger:
            result = crop_handler.get_processed_preview_pixmap(mock_main_window)

            assert result is None
            mock_logger.warning.assert_called_once()

    def test_get_processed_preview_pixmap_no_processed_image(self, crop_handler, mock_main_window) -> None:
        """Test getting processed preview when processed_image is missing."""
        # Remove processed_image attribute
        mock_main_window.main_tab.first_frame_label.processed_image = None

        with patch("goesvfi.gui_components.crop_handler.LOGGER") as mock_logger:
            result = crop_handler.get_processed_preview_pixmap(mock_main_window)

            assert result is None
            mock_logger.warning.assert_called_once()

    def test_get_processed_preview_pixmap_invalid_image(self, crop_handler, mock_main_window) -> None:
        """Test getting processed preview with invalid image."""
        # Set invalid processed_image
        mock_main_window.main_tab.first_frame_label.processed_image = "not_an_image"

        with patch("goesvfi.gui_components.crop_handler.LOGGER") as mock_logger:
            result = crop_handler.get_processed_preview_pixmap(mock_main_window)

            assert result is None
            mock_logger.warning.assert_called_once()

    @patch("goesvfi.gui_components.crop_handler.CropSelectionDialog")
    def test_show_crop_dialog_success(self, mock_dialog_class, crop_handler, mock_main_window) -> None:
        """Test successful crop dialog workflow."""
        # Setup mock dialog
        mock_dialog = Mock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
        mock_crop_rect = QRect(10, 20, 300, 400)
        mock_dialog.get_selected_rect.return_value = mock_crop_rect
        mock_dialog_class.return_value = mock_dialog

        test_pixmap = QPixmap(800, 600)
        crop_handler.show_crop_dialog(mock_main_window, test_pixmap)

        # Should create dialog and handle result
        mock_dialog_class.assert_called_once()
        mock_dialog.exec.assert_called_once()

        # Should update crop rectangle
        assert mock_main_window.current_crop_rect == (10, 20, 300, 400)
        mock_main_window._update_crop_buttons_state.assert_called_once()
        mock_main_window.request_previews_update.emit.assert_called_once()

    @patch("goesvfi.gui_components.crop_handler.CropSelectionDialog")
    def test_show_crop_dialog_cancelled(self, mock_dialog_class, crop_handler, mock_main_window) -> None:
        """Test crop dialog when user cancels."""
        # Setup mock dialog
        mock_dialog = Mock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Rejected
        mock_dialog_class.return_value = mock_dialog

        original_crop_rect = mock_main_window.current_crop_rect

        test_pixmap = QPixmap(800, 600)
        crop_handler.show_crop_dialog(mock_main_window, test_pixmap)

        # Should not update crop rectangle
        assert mock_main_window.current_crop_rect == original_crop_rect
        mock_main_window._update_crop_buttons_state.assert_not_called()
        mock_main_window.request_previews_update.emit.assert_not_called()

    @patch("goesvfi.gui_components.crop_handler.CropSelectionDialog")
    def test_show_crop_dialog_with_initial_rect(self, mock_dialog_class, crop_handler, mock_main_window) -> None:
        """Test crop dialog with existing crop rectangle."""
        # Set existing crop rectangle
        mock_main_window.current_crop_rect = (5, 10, 200, 300)

        mock_dialog = Mock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Rejected
        mock_dialog_class.return_value = mock_dialog

        test_pixmap = QPixmap(800, 600)
        crop_handler.show_crop_dialog(mock_main_window, test_pixmap)

        # Should pass initial rect to dialog
        call_args = mock_dialog_class.call_args[0]
        initial_rect = call_args[1]
        assert isinstance(initial_rect, QRect)
        assert initial_rect.x() == 5
        assert initial_rect.y() == 10
        assert initial_rect.width() == 200
        assert initial_rect.height() == 300

    @patch("goesvfi.gui_components.crop_handler.CropSelectionDialog")
    def test_show_crop_dialog_no_rect_returned(self, mock_dialog_class, crop_handler, mock_main_window) -> None:
        """Test crop dialog when no rect is returned."""
        mock_dialog = Mock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
        mock_dialog.get_selected_rect.return_value = None
        mock_dialog_class.return_value = mock_dialog

        original_crop_rect = mock_main_window.current_crop_rect

        test_pixmap = QPixmap(800, 600)
        crop_handler.show_crop_dialog(mock_main_window, test_pixmap)

        # Should not update crop rectangle
        assert mock_main_window.current_crop_rect == original_crop_rect
        mock_main_window._update_crop_buttons_state.assert_not_called()

    def test_on_clear_crop_clicked(self, crop_handler, mock_main_window) -> None:
        """Test clearing crop rectangle."""
        # Set existing crop rectangle
        mock_main_window.current_crop_rect = (10, 20, 300, 400)

        crop_handler.on_clear_crop_clicked(mock_main_window)

        # Should clear crop rectangle and update UI
        assert mock_main_window.current_crop_rect is None
        mock_main_window._update_crop_buttons_state.assert_called_once()
        mock_main_window.request_previews_update.emit.assert_called_once()

    def test_logging_behavior(self, crop_handler, mock_main_window, temp_image_dir) -> None:
        """Test that appropriate logging occurs."""
        mock_main_window.in_dir = temp_image_dir

        with patch("goesvfi.gui_components.crop_handler.LOGGER") as mock_logger:
            with patch.object(crop_handler, "prepare_image_for_crop_dialog", return_value=None):
                crop_handler.on_crop_clicked(mock_main_window)

                # Should log debug messages
                mock_logger.debug.assert_called()

    @patch("goesvfi.gui_components.crop_handler.CropSelectionDialog")
    def test_show_crop_dialog_logging(self, mock_dialog_class, crop_handler, mock_main_window) -> None:
        """Test logging in crop dialog workflow."""
        mock_dialog = Mock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
        mock_crop_rect = QRect(10, 20, 300, 400)
        mock_dialog.get_selected_rect.return_value = mock_crop_rect
        mock_dialog_class.return_value = mock_dialog

        with patch("goesvfi.gui_components.crop_handler.LOGGER") as mock_logger:
            test_pixmap = QPixmap(800, 600)
            crop_handler.show_crop_dialog(mock_main_window, test_pixmap)

            # Should log crop rectangle setting
            mock_logger.info.assert_called_once()
            assert "Crop rectangle set to" in str(mock_logger.info.call_args)

    def test_clear_crop_logging(self, crop_handler, mock_main_window) -> None:
        """Test logging when clearing crop."""
        with patch("goesvfi.gui_components.crop_handler.LOGGER") as mock_logger:
            crop_handler.on_clear_crop_clicked(mock_main_window)

            # Should log crop clearing
            mock_logger.info.assert_called_once()
            assert "Crop rectangle cleared" in str(mock_logger.info.call_args)

    def test_integration_workflow_end_to_end(self, crop_handler, mock_main_window, temp_image_dir) -> None:
        """Test complete crop workflow from start to finish."""
        mock_main_window.in_dir = temp_image_dir
        mock_main_window.current_crop_rect = None

        with patch("goesvfi.gui_components.crop_handler.QImage") as mock_qimage:
            with patch("goesvfi.gui_components.crop_handler.QPixmap") as mock_qpixmap:
                with patch("goesvfi.gui_components.crop_handler.CropSelectionDialog") as mock_dialog_class:
                    # Mock successful image loading
                    mock_image = Mock()
                    mock_image.isNull.return_value = False
                    mock_qimage.return_value = mock_image

                    mock_pixmap = Mock()
                    mock_qpixmap.fromImage.return_value = mock_pixmap

                    # Mock successful dialog
                    mock_dialog = Mock()
                    mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
                    mock_crop_rect = QRect(50, 60, 400, 300)
                    mock_dialog.get_selected_rect.return_value = mock_crop_rect
                    mock_dialog_class.return_value = mock_dialog

                    # Execute workflow
                    crop_handler.on_crop_clicked(mock_main_window)

                    # Verify complete workflow
                    mock_qimage.assert_called_once()
                    mock_dialog_class.assert_called_once()
                    assert mock_main_window.current_crop_rect == (50, 60, 400, 300)
                    mock_main_window._update_crop_buttons_state.assert_called_once()
                    mock_main_window.request_previews_update.emit.assert_called_once()
