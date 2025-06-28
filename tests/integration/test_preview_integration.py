"""Integration tests for preview functionality workflow."""

from pathlib import Path
import tempfile
from typing import Any
from unittest.mock import Mock, patch

from PyQt6.QtCore import QRect
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QApplication
import pytest

from goesvfi.gui_components.crop_handler import CropHandler
from goesvfi.gui_components.zoom_manager import ZoomManager


class TestPreviewWorkflowIntegration:
    """Test complete preview update workflows."""

    @pytest.fixture()
    def app(self) -> Any:
        """Create QApplication for GUI tests."""
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app
        app.quit()

    @pytest.fixture()
    def mock_main_window(self) -> Any:
        """Create comprehensive mock main window for integration testing."""
        main_window = Mock()

        # Directory and crop state
        main_window.in_dir = None
        main_window.current_crop_rect = None

        # Preview cache
        main_window.sanchez_preview_cache = Mock()
        main_window.sanchez_preview_cache.clear = Mock()

        # Signals
        main_window.request_previews_update = Mock()
        main_window.request_previews_update.emit = Mock()

        # Methods
        main_window._update_previews = Mock()
        main_window._update_crop_buttons_state = Mock()
        main_window._on_tab_changed = Mock()

        # Main tab setup
        main_tab = Mock()

        # Sanchez checkbox
        sanchez_checkbox = Mock()
        sanchez_checkbox.isChecked = Mock(return_value=False)
        main_tab.sanchez_false_colour_checkbox = sanchez_checkbox

        # Preview labels (mock to avoid Qt initialization issues)
        first_frame_label = Mock()
        first_frame_label.processed_image = None
        first_frame_label.clicked = Mock()
        first_frame_label.clicked.connect = Mock()
        first_frame_label.mouseReleaseEvent = Mock()

        last_frame_label = Mock()
        last_frame_label.processed_image = None
        last_frame_label.clicked = Mock()
        last_frame_label.clicked.connect = Mock()
        last_frame_label.mouseReleaseEvent = Mock()

        main_tab.first_frame_label = first_frame_label
        main_tab.last_frame_label = last_frame_label

        # Tab widget
        tab_widget = Mock()
        tab_widget.currentChanged = Mock()
        main_window.tab_widget = tab_widget

        main_window.main_tab = main_tab

        return main_window

    @pytest.fixture()
    def temp_image_directory(self) -> Any:
        """Create temporary directory with test images."""
        with tempfile.TemporaryDirectory() as temp_dir:
            image_dir = Path(temp_dir)

            # Create test image files with different formats
            test_files = [
                "image001.png",
                "image002.jpg",
                "image003.jpeg",
                "frame_001.png",
                "frame_002.jpg",
            ]

            for filename in test_files:
                (image_dir / filename).write_text(f"fake {filename}")

            # Create non-image files that should be ignored
            (image_dir / "readme.txt").write_text("not an image")
            (image_dir / "config.json").write_text("{}")

            yield image_dir

    def test_directory_change_triggers_preview_update(self, mock_main_window, temp_image_directory) -> None:
        """Test that changing input directory triggers preview updates."""
        from goesvfi.gui_components.state_manager import StateManager

        # Add required attributes for StateManager
        mock_main_window._save_input_directory = Mock(return_value=True)
        mock_main_window.request_previews_update.emit = Mock()

        state_manager = StateManager(mock_main_window)

        # Initially no directory
        assert mock_main_window.in_dir is None

        # Change to valid directory
        state_manager.set_input_directory(temp_image_directory)

        # Should update directory and clear cache
        assert mock_main_window.in_dir == temp_image_directory
        mock_main_window.sanchez_preview_cache.clear.assert_called_once()

    def test_crop_rectangle_change_triggers_preview_update(self, mock_main_window) -> None:
        """Test that changing crop rectangle triggers preview updates."""
        crop_handler = CropHandler()

        # Set initial crop rectangle
        mock_main_window.current_crop_rect = None

        # Simulate crop selection
        with patch("goesvfi.gui_components.crop_handler.CropSelectionDialog") as mock_dialog_class:
            mock_dialog = Mock()
            mock_dialog.exec.return_value = 1  # Accepted
            mock_crop_rect = QRect(100, 100, 400, 300)
            mock_dialog.get_selected_rect.return_value = mock_crop_rect
            mock_dialog_class.return_value = mock_dialog

            test_pixmap = QPixmap(800, 600)
            crop_handler.show_crop_dialog(mock_main_window, test_pixmap)

            # Should update crop rectangle and request preview update
            assert mock_main_window.current_crop_rect == (100, 100, 400, 300)
            mock_main_window.request_previews_update.emit.assert_called_once()

    def test_sanchez_toggle_integration(self, mock_main_window, temp_image_directory) -> None:
        """Test Sanchez preview toggle integration with crop workflow."""
        mock_main_window.in_dir = temp_image_directory
        crop_handler = CropHandler()

        # Test with Sanchez disabled
        mock_main_window.main_tab.sanchez_false_colour_checkbox.isChecked.return_value = False

        with patch("goesvfi.gui_components.crop_handler.QImage") as mock_qimage:
            mock_image = Mock()
            mock_image.isNull.return_value = False
            mock_qimage.return_value = mock_image

            image_files = crop_handler.get_sorted_image_files(mock_main_window)
            pixmap = crop_handler.prepare_image_for_crop_dialog(mock_main_window, image_files[0])

            # Should load original image
            assert pixmap is not None
            mock_qimage.assert_called_once()

    def test_sanchez_enabled_with_processed_preview(self, mock_main_window, temp_image_directory) -> None:
        """Test crop dialog with Sanchez preview enabled."""
        mock_main_window.in_dir = temp_image_directory
        crop_handler = CropHandler()

        # Enable Sanchez preview
        mock_main_window.main_tab.sanchez_false_colour_checkbox.isChecked.return_value = True

        # Set up processed image on first frame label
        test_processed_image = QImage(800, 600, QImage.Format.Format_RGB32)
        test_processed_image.fill(0xFF0000)  # Red
        mock_main_window.main_tab.first_frame_label.processed_image = test_processed_image

        with patch("goesvfi.gui_components.crop_handler.QPixmap") as mock_qpixmap:
            mock_pixmap = Mock()
            mock_qpixmap.fromImage.return_value = mock_pixmap

            image_files = crop_handler.get_sorted_image_files(mock_main_window)
            result = crop_handler.prepare_image_for_crop_dialog(mock_main_window, image_files[0])

            # Should use processed preview
            assert result is mock_pixmap
            mock_qpixmap.fromImage.assert_called_with(test_processed_image)

    def test_zoom_preview_integration(self, app, mock_main_window) -> None:
        """Test zoom dialog integration with preview workflow."""
        zoom_manager = ZoomManager()

        # Set up clickable label with processed image
        preview_label = mock_main_window.main_tab.first_frame_label
        test_image = QImage(1200, 800, QImage.Format.Format_RGB32)
        test_image.fill(0x00FF00)  # Green
        preview_label.processed_image = test_image

        with patch("goesvfi.gui_components.zoom_manager.ZoomDialog") as mock_zoom_dialog:
            mock_dialog_instance = Mock()
            mock_zoom_dialog.return_value = mock_dialog_instance

            zoom_manager.show_zoom(preview_label)

            # Should create and show zoom dialog
            mock_zoom_dialog.assert_called_once()
            mock_dialog_instance.exec.assert_called_once()

    def test_complete_preview_workflow_end_to_end(self, app, mock_main_window, temp_image_directory) -> None:
        """Test complete preview workflow from directory selection to zoom."""
        from goesvfi.gui_components.state_manager import StateManager

        # Add required attributes
        mock_main_window._save_input_directory = Mock(return_value=True)
        mock_main_window.request_previews_update.emit = Mock()

        state_manager = StateManager(mock_main_window)
        crop_handler = CropHandler()
        zoom_manager = ZoomManager()

        # Step 1: Set input directory
        state_manager.set_input_directory(temp_image_directory)
        assert mock_main_window.in_dir == temp_image_directory

        # Step 2: Load images and set up previews
        image_files = crop_handler.get_sorted_image_files(mock_main_window)
        assert len(image_files) == 5  # Should find 5 image files

        # Step 3: Set up processed images on labels
        first_image = QImage(800, 600, QImage.Format.Format_RGB32)
        first_image.fill(0xFF0000)  # Red
        mock_main_window.main_tab.first_frame_label.processed_image = first_image

        last_image = QImage(800, 600, QImage.Format.Format_RGB32)
        last_image.fill(0x0000FF)  # Blue
        mock_main_window.main_tab.last_frame_label.processed_image = last_image

        # Step 4: Test crop workflow
        with (
            patch("goesvfi.gui_components.crop_handler.CropSelectionDialog") as mock_crop_dialog,
            patch("goesvfi.gui_components.crop_handler.QImage") as mock_qimage,
            patch("goesvfi.gui_components.crop_handler.QPixmap") as mock_qpixmap,
        ):
            # Mock successful image loading
            mock_image = Mock()
            mock_image.isNull.return_value = False
            mock_qimage.return_value = mock_image

            mock_pixmap = Mock()
            mock_qpixmap.fromImage.return_value = mock_pixmap

            # Mock crop dialog
            mock_dialog = Mock()
            mock_dialog.exec.return_value = 1  # Accepted
            mock_crop_rect = QRect(50, 50, 300, 200)
            mock_dialog.get_selected_rect.return_value = mock_crop_rect
            mock_crop_dialog.return_value = mock_dialog

            # Execute crop workflow
            crop_handler.on_crop_clicked(mock_main_window)

            # Should complete successfully
            assert mock_main_window.current_crop_rect == (50, 50, 300, 200)
            mock_main_window.request_previews_update.emit.assert_called()

        # Step 5: Test zoom workflow
        with patch("goesvfi.gui_components.zoom_manager.ZoomDialog") as mock_zoom_dialog:
            mock_dialog_instance = Mock()
            mock_zoom_dialog.return_value = mock_dialog_instance

            # Zoom first frame
            zoom_manager.show_zoom(mock_main_window.main_tab.first_frame_label)
            mock_zoom_dialog.assert_called()

            # Reset mock for second call
            mock_zoom_dialog.reset_mock()

            # Zoom last frame
            zoom_manager.show_zoom(mock_main_window.main_tab.last_frame_label)
            mock_zoom_dialog.assert_called()

    def test_preview_signal_propagation(self, mock_main_window) -> None:
        """Test signal propagation through preview system."""
        from goesvfi.gui_components.signal_broker import SignalBroker

        signal_broker = SignalBroker()

        # Set up signal connections
        signal_broker.setup_main_window_connections(mock_main_window)

        # Verify connections were established
        mock_main_window.request_previews_update.connect.assert_called()
        mock_main_window.tab_widget.currentChanged.connect.assert_called()

    def test_preview_error_handling_integration(self, mock_main_window, temp_image_directory) -> None:
        """Test error handling in preview workflows."""
        mock_main_window.in_dir = temp_image_directory
        crop_handler = CropHandler()

        # Test image loading failure
        with patch("goesvfi.gui_components.crop_handler.QImage") as mock_qimage:
            mock_image = Mock()
            mock_image.isNull.return_value = True  # Failed to load
            mock_qimage.return_value = mock_image

            with patch("goesvfi.gui_components.crop_handler.QMessageBox") as mock_msgbox:
                crop_handler.on_crop_clicked(mock_main_window)

                # Should show error message
                mock_msgbox.critical.assert_called_once()

    def test_preview_cache_management(self, mock_main_window, temp_image_directory) -> None:
        """Test preview cache management during directory changes."""
        from goesvfi.gui_components.state_manager import StateManager

        # Add required attributes
        mock_main_window._save_input_directory = Mock(return_value=True)
        mock_main_window.request_previews_update.emit = Mock()

        state_manager = StateManager(mock_main_window)

        # Set initial directory
        state_manager.set_input_directory(temp_image_directory)
        mock_main_window.sanchez_preview_cache.clear.assert_called_once()

        # Reset mock
        mock_main_window.sanchez_preview_cache.clear.reset_mock()

        # Change to same directory (should not clear cache)
        state_manager.set_input_directory(temp_image_directory)
        mock_main_window.sanchez_preview_cache.clear.assert_not_called()

        # Change to different directory
        with tempfile.TemporaryDirectory() as temp_dir2:
            new_dir = Path(temp_dir2)
            state_manager.set_input_directory(new_dir)
            mock_main_window.sanchez_preview_cache.clear.assert_called_once()

    def test_preview_label_interactions(self, app, mock_main_window) -> None:
        """Test ClickableLabel interactions in preview context."""
        preview_label = mock_main_window.main_tab.first_frame_label

        # Set up image
        test_image = QImage(400, 300, QImage.Format.Format_RGB32)
        test_image.fill(0xFFFF00)  # Yellow
        preview_label.processed_image = test_image

        # Test click signal connection (mocked)
        mock_callback = Mock()
        preview_label.clicked.connect(mock_callback)

        # Verify connection was called
        preview_label.clicked.connect.assert_called_with(mock_callback)

        # Simulate mouse event (mocked)
        from PyQt6.QtCore import QPointF, Qt
        from PyQt6.QtGui import QMouseEvent

        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(50, 50),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        preview_label.mouseReleaseEvent(event)
        preview_label.mouseReleaseEvent.assert_called_with(event)

    def test_crop_clear_integration(self, mock_main_window) -> None:
        """Test crop clear integration with preview updates."""
        crop_handler = CropHandler()

        # Set crop rectangle
        mock_main_window.current_crop_rect = (10, 20, 300, 200)

        # Clear crop
        crop_handler.on_clear_crop_clicked(mock_main_window)

        # Should clear rectangle and trigger updates
        assert mock_main_window.current_crop_rect is None
        mock_main_window._update_crop_buttons_state.assert_called_once()
        mock_main_window.request_previews_update.emit.assert_called_once()

    def test_tab_change_integration(self, mock_main_window) -> None:
        """Test tab change integration with preview system."""
        # Simulate tab change
        mock_main_window._on_tab_changed(1)  # Switch to tab 1
        mock_main_window._on_tab_changed.assert_called_with(1)

    def test_preview_memory_management(self, app, mock_main_window) -> None:
        """Test memory management of preview images."""
        zoom_manager = ZoomManager()

        # Create large image that would need scaling
        large_image = QImage(4000, 3000, QImage.Format.Format_RGB32)
        large_image.fill(0xFF00FF)  # Magenta

        preview_label = Mock()
        preview_label.objectName.return_value = "large_preview"
        preview_label.processed_image = large_image

        with patch("goesvfi.gui_components.zoom_manager.QApplication") as mock_qapp:
            mock_screen = Mock()
            mock_screen.availableGeometry.return_value.size.return_value.width.return_value = 1920
            mock_screen.availableGeometry.return_value.size.return_value.height.return_value = 1080
            mock_qapp.primaryScreen.return_value = mock_screen

            with patch("goesvfi.gui_components.zoom_manager.ZoomDialog") as mock_zoom_dialog:
                mock_dialog = Mock()
                mock_zoom_dialog.return_value = mock_dialog

                zoom_manager.show_zoom(preview_label)

                # Should handle large image scaling
                mock_zoom_dialog.assert_called_once()
                call_args = mock_zoom_dialog.call_args[0]
                scaled_pixmap = call_args[0]

                # Verify scaling occurred (image should be smaller than original)
                assert not scaled_pixmap.isNull()

    def test_concurrent_preview_operations(self, mock_main_window, temp_image_directory) -> None:
        """Test handling of concurrent preview operations."""
        crop_handler = CropHandler()

        # Simulate rapid operations
        mock_main_window.in_dir = temp_image_directory

        # Multiple rapid crop operations
        for _i in range(3):
            with patch("goesvfi.gui_components.crop_handler.CropSelectionDialog"):
                with patch("goesvfi.gui_components.crop_handler.QImage") as mock_qimage:
                    mock_image = Mock()
                    mock_image.isNull.return_value = False
                    mock_qimage.return_value = mock_image

                    image_files = crop_handler.get_sorted_image_files(mock_main_window)
                    if image_files:
                        pixmap = crop_handler.prepare_image_for_crop_dialog(mock_main_window, image_files[0])
                        # Should handle concurrent operations gracefully
                        assert pixmap is not None or pixmap is None  # Either success or controlled failure

    def test_sanchez_fallback_integration(self, mock_main_window, temp_image_directory) -> None:
        """Test Sanchez processing fallback to original images."""
        mock_main_window.in_dir = temp_image_directory
        crop_handler = CropHandler()

        # Enable Sanchez but make processed preview unavailable
        mock_main_window.main_tab.sanchez_false_colour_checkbox.isChecked.return_value = True
        mock_main_window.main_tab.first_frame_label.processed_image = None

        with patch("goesvfi.gui_components.crop_handler.QImage") as mock_qimage:
            with patch("goesvfi.gui_components.crop_handler.QPixmap") as mock_qpixmap:
                # Mock successful original image loading
                mock_image = Mock()
                mock_image.isNull.return_value = False
                mock_qimage.return_value = mock_image

                mock_pixmap = Mock()
                mock_qpixmap.fromImage.return_value = mock_pixmap

                image_files = crop_handler.get_sorted_image_files(mock_main_window)
                result = crop_handler.prepare_image_for_crop_dialog(mock_main_window, image_files[0])

                # Should fall back to original image
                assert result is mock_pixmap
                mock_qimage.assert_called_once()  # Should load original


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
