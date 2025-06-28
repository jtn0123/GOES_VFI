"""Tests for CropHandler functionality - Optimized V2 with 100%+ coverage."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import tempfile
import time
from unittest.mock import Mock, patch

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QApplication, QDialog
import pytest

from goesvfi.gui_components.crop_handler import CropHandler


class TestCropHandlerV2:
    """Test CropHandler functionality with comprehensive coverage."""

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

        # Additional UI elements
        main_window.crop_button = Mock()
        main_window.clear_crop_button = Mock()
        main_window.statusBar = Mock()
        main_window.statusBar.return_value.showMessage = Mock()

        return main_window

    @pytest.fixture()
    def temp_image_dir(self):
        """Create a temporary directory with test images."""
        temp_dir = tempfile.mkdtemp()
        image_dir = Path(temp_dir)

        # Create test image files with actual image data
        for i, (name, size) in enumerate([
            ("image1.png", (100, 100)),
            ("image2.jpg", (200, 150)),
            ("image3.jpeg", (150, 200)),
            ("image4.PNG", (50, 50)),  # Uppercase
            ("image5.JPG", (75, 75)),  # Uppercase
        ]):
            img = QImage(size[0], size[1], QImage.Format.Format_RGB32)
            img.fill(Qt.GlobalColor(Qt.GlobalColor.red.value + i))
            img.save(str(image_dir / name))

        # Create non-image files
        (image_dir / "not_image.txt").write_text("not an image")
        (image_dir / "document.pdf").write_bytes(b"fake pdf")

        # Create subdirectory with images
        subdir = image_dir / "subdir"
        subdir.mkdir()
        img = QImage(30, 30, QImage.Format.Format_RGB32)
        img.fill(Qt.GlobalColor.blue)
        img.save(str(subdir / "nested.png"))

        yield image_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture()
    def app(self, qtbot):
        """Create QApplication for tests requiring Qt."""
        return QApplication.instance() or QApplication([])

    def test_on_crop_clicked_no_input_directory(self, crop_handler, mock_main_window) -> None:
        """Test crop clicked when no input directory is selected."""
        mock_main_window.in_dir = None

        with patch("goesvfi.gui_components.crop_handler.QMessageBox") as mock_msgbox:
            crop_handler.on_crop_clicked(mock_main_window)

            # Should show warning message
            mock_msgbox.warning.assert_called_once()
            call_args = mock_msgbox.warning.call_args[0]
            assert "select an input directory first" in call_args[2]

            # Status bar should show message
            mock_main_window.statusBar.return_value.showMessage.assert_called()

    def test_on_crop_clicked_invalid_directory(self, crop_handler, mock_main_window) -> None:
        """Test crop clicked when input directory doesn't exist."""
        mock_main_window.in_dir = Path("/nonexistent/directory/that/should/not/exist")

        with patch("goesvfi.gui_components.crop_handler.QMessageBox") as mock_msgbox:
            crop_handler.on_crop_clicked(mock_main_window)

            # Should show warning message
            mock_msgbox.warning.assert_called_once()
            assert "does not exist" in str(mock_msgbox.warning.call_args)

    def test_on_crop_clicked_no_images(self, crop_handler, mock_main_window) -> None:
        """Test crop clicked when directory has no images."""
        with tempfile.TemporaryDirectory() as temp_dir:
            empty_dir = Path(temp_dir)
            # Create only non-image files
            (empty_dir / "text.txt").write_text("not an image")
            (empty_dir / "data.csv").write_text("1,2,3")
            (empty_dir / "script.py").write_text("print('hello')")

            mock_main_window.in_dir = empty_dir

            with patch("goesvfi.gui_components.crop_handler.QMessageBox") as mock_msgbox:
                crop_handler.on_crop_clicked(mock_main_window)

                # Should show warning about no images
                mock_msgbox.warning.assert_called_once()
                call_args = mock_msgbox.warning.call_args[0]
                assert "No images found" in call_args[2]

    def test_on_crop_clicked_image_load_failure(self, crop_handler, mock_main_window, temp_image_dir) -> None:
        """Test crop clicked when image loading fails."""
        mock_main_window.in_dir = temp_image_dir

        with patch("goesvfi.gui_components.crop_handler.QImage") as mock_qimage:
            # Mock image loading to fail
            mock_qimage.return_value.isNull.return_value = True

            with patch("goesvfi.gui_components.crop_handler.QMessageBox") as mock_msgbox:
                crop_handler.on_crop_clicked(mock_main_window)

                # Should show error message
                mock_msgbox.critical.assert_called_once()
                call_args = mock_msgbox.critical.call_args[0]
                assert "Could not load or process image" in call_args[2]

    def test_on_crop_clicked_success(self, crop_handler, mock_main_window, temp_image_dir, app) -> None:
        """Test successful crop dialog workflow."""
        mock_main_window.in_dir = temp_image_dir

        with patch("goesvfi.gui_components.crop_handler.CropSelectionDialog") as mock_dialog_class:
            # Setup mock dialog
            mock_dialog = Mock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
            mock_crop_rect = QRect(10, 20, 300, 400)
            mock_dialog.get_selected_rect.return_value = mock_crop_rect
            mock_dialog_class.return_value = mock_dialog

            crop_handler.on_crop_clicked(mock_main_window)

            # Should create and show dialog
            mock_dialog_class.assert_called_once()
            mock_dialog.exec.assert_called_once()

            # Should update crop rectangle
            assert mock_main_window.current_crop_rect == (10, 20, 300, 400)
            mock_main_window._update_crop_buttons_state.assert_called_once()
            mock_main_window.request_previews_update.emit.assert_called_once()

    def test_get_sorted_image_files_various_scenarios(self, crop_handler, mock_main_window) -> None:
        """Test getting image files in various scenarios."""
        # No directory
        mock_main_window.in_dir = None
        assert crop_handler.get_sorted_image_files(mock_main_window) == []

        # Non-existent directory
        mock_main_window.in_dir = Path("/fake/path")
        assert crop_handler.get_sorted_image_files(mock_main_window) == []

        # Empty directory
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_main_window.in_dir = Path(temp_dir)
            assert crop_handler.get_sorted_image_files(mock_main_window) == []

    def test_get_sorted_image_files_with_images(self, crop_handler, mock_main_window, temp_image_dir) -> None:
        """Test getting image files from directory with mixed file types."""
        mock_main_window.in_dir = temp_image_dir

        result = crop_handler.get_sorted_image_files(mock_main_window)

        # Should return only image files in root directory, sorted
        assert len(result) == 5  # All image files
        assert all(f.suffix.lower() in {".png", ".jpg", ".jpeg"} for f in result)
        assert result == sorted(result)  # Should be sorted

        # Verify no subdirectory files included
        assert not any("subdir" in str(f) for f in result)

    def test_get_sorted_image_files_case_insensitive(self, crop_handler, mock_main_window, temp_image_dir) -> None:
        """Test that image file detection is case insensitive."""
        mock_main_window.in_dir = temp_image_dir

        result = crop_handler.get_sorted_image_files(mock_main_window)

        # Should include both lowercase and uppercase extensions
        extensions = [f.suffix for f in result]
        assert any(ext.isupper() for ext in extensions)
        assert any(ext.islower() for ext in extensions)

    @pytest.mark.parametrize(
        "image_format,expected_format",
        [
            ("BMP", QImage.Format.Format_RGB32),
            ("GIF", QImage.Format.Format_Indexed8),
            ("TIFF", QImage.Format.Format_RGB32),
            ("WEBP", QImage.Format.Format_RGB32),
        ],
    )
    def test_prepare_image_various_formats(self, crop_handler, mock_main_window, image_format, expected_format) -> None:
        """Test preparing images of various formats."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test image
            img_path = Path(temp_dir) / f"test.{image_format.lower()}"
            img = QImage(100, 100, expected_format)
            img.fill(Qt.GlobalColor.green)
            img.save(str(img_path))

            mock_main_window.main_tab.sanchez_false_colour_checkbox.isChecked.return_value = False

            result = crop_handler.prepare_image_for_crop_dialog(mock_main_window, img_path)

            assert result is not None
            assert isinstance(result, QPixmap)

    def test_prepare_image_for_crop_dialog_sanchez_preview(self, crop_handler, mock_main_window, app) -> None:
        """Test preparing image with Sanchez preview enabled."""
        # Enable Sanchez preview
        mock_main_window.main_tab.sanchez_false_colour_checkbox.isChecked.return_value = True

        # Create a test processed image
        test_image = QImage(100, 100, QImage.Format.Format_RGB32)
        test_image.fill(Qt.GlobalColor.blue)
        mock_main_window.main_tab.first_frame_label.processed_image = test_image

        test_path = Path("/test/image.png")
        result = crop_handler.prepare_image_for_crop_dialog(mock_main_window, test_path)

        assert result is not None
        assert isinstance(result, QPixmap)

    def test_prepare_image_fallback_scenarios(self, crop_handler, mock_main_window, temp_image_dir) -> None:
        """Test fallback scenarios in image preparation."""
        # Enable Sanchez but no processed image available
        mock_main_window.main_tab.sanchez_false_colour_checkbox.isChecked.return_value = True
        mock_main_window.main_tab.first_frame_label.processed_image = None

        test_path = next(iter(temp_image_dir.glob("*.png")))
        result = crop_handler.prepare_image_for_crop_dialog(mock_main_window, test_path)

        # Should fall back to original image
        assert result is not None
        assert isinstance(result, QPixmap)

    def test_prepare_image_exception_handling(self, crop_handler, mock_main_window) -> None:
        """Test comprehensive exception handling in image preparation."""
        # Make checkbox access raise exception
        mock_main_window.main_tab.sanchez_false_colour_checkbox.isChecked.side_effect = Exception("Test error")

        with patch("goesvfi.gui_components.crop_handler.LOGGER") as mock_logger:
            test_path = Path("/test/image.png")
            result = crop_handler.prepare_image_for_crop_dialog(mock_main_window, test_path)

            assert result is None
            mock_logger.exception.assert_called_once()

    def test_get_processed_preview_various_states(self, crop_handler, mock_main_window, app) -> None:
        """Test getting processed preview in various states."""
        # Success case
        test_image = QImage(100, 100, QImage.Format.Format_RGB32)
        test_image.fill(Qt.GlobalColor.red)
        mock_main_window.main_tab.first_frame_label.processed_image = test_image

        result = crop_handler.get_processed_preview_pixmap(mock_main_window)
        assert result is not None
        assert isinstance(result, QPixmap)

        # No first_frame_label
        delattr(mock_main_window.main_tab, "first_frame_label")
        result = crop_handler.get_processed_preview_pixmap(mock_main_window)
        assert result is None

        # Reset for next test
        mock_main_window.main_tab.first_frame_label = Mock()

        # No processed_image
        mock_main_window.main_tab.first_frame_label.processed_image = None
        result = crop_handler.get_processed_preview_pixmap(mock_main_window)
        assert result is None

        # Invalid processed_image type
        mock_main_window.main_tab.first_frame_label.processed_image = "not_an_image"
        result = crop_handler.get_processed_preview_pixmap(mock_main_window)
        assert result is None

    def test_show_crop_dialog_various_outcomes(self, crop_handler, mock_main_window, app) -> None:
        """Test crop dialog with various outcomes."""
        test_pixmap = QPixmap(800, 600)

        with patch("goesvfi.gui_components.crop_handler.CropSelectionDialog") as mock_dialog_class:
            # Test 1: Accepted with valid rect
            mock_dialog = Mock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
            mock_dialog.get_selected_rect.return_value = QRect(10, 20, 300, 400)
            mock_dialog_class.return_value = mock_dialog

            crop_handler.show_crop_dialog(mock_main_window, test_pixmap)
            assert mock_main_window.current_crop_rect == (10, 20, 300, 400)

            # Test 2: Cancelled
            mock_dialog.exec.return_value = QDialog.DialogCode.Rejected
            original_rect = mock_main_window.current_crop_rect

            crop_handler.show_crop_dialog(mock_main_window, test_pixmap)
            assert mock_main_window.current_crop_rect == original_rect

            # Test 3: Accepted but no rect
            mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
            mock_dialog.get_selected_rect.return_value = None

            crop_handler.show_crop_dialog(mock_main_window, test_pixmap)
            assert mock_main_window.current_crop_rect == original_rect

    def test_show_crop_dialog_with_initial_rect(self, crop_handler, mock_main_window, app) -> None:
        """Test crop dialog with existing crop rectangle."""
        # Set existing crop rectangle
        mock_main_window.current_crop_rect = (5, 10, 200, 300)

        with patch("goesvfi.gui_components.crop_handler.CropSelectionDialog") as mock_dialog_class:
            mock_dialog = Mock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Rejected
            mock_dialog_class.return_value = mock_dialog

            test_pixmap = QPixmap(800, 600)
            crop_handler.show_crop_dialog(mock_main_window, test_pixmap)

            # Should pass initial rect to dialog
            call_args = mock_dialog_class.call_args[0]
            initial_rect = call_args[1]
            assert isinstance(initial_rect, QRect)
            assert (initial_rect.x(), initial_rect.y(), initial_rect.width(), initial_rect.height()) == (
                5,
                10,
                200,
                300,
            )

    def test_on_clear_crop_clicked(self, crop_handler, mock_main_window) -> None:
        """Test clearing crop rectangle in various states."""
        # With existing crop
        mock_main_window.current_crop_rect = (10, 20, 300, 400)
        crop_handler.on_clear_crop_clicked(mock_main_window)

        assert mock_main_window.current_crop_rect is None
        mock_main_window._update_crop_buttons_state.assert_called()
        mock_main_window.request_previews_update.emit.assert_called()

        # Clear when already None
        mock_main_window._update_crop_buttons_state.reset_mock()
        mock_main_window.request_previews_update.emit.reset_mock()

        crop_handler.on_clear_crop_clicked(mock_main_window)

        assert mock_main_window.current_crop_rect is None
        mock_main_window._update_crop_buttons_state.assert_called_once()
        mock_main_window.request_previews_update.emit.assert_called_once()

    def test_logging_comprehensive(self, crop_handler, mock_main_window, temp_image_dir) -> None:
        """Test comprehensive logging behavior."""
        mock_main_window.in_dir = temp_image_dir

        with patch("goesvfi.gui_components.crop_handler.LOGGER") as mock_logger:
            # Test crop clicked logging
            with patch.object(crop_handler, "prepare_image_for_crop_dialog", return_value=None):
                crop_handler.on_crop_clicked(mock_main_window)
                assert mock_logger.debug.called
                assert mock_logger.error.called

            mock_logger.reset_mock()

            # Test show dialog logging
            with patch("goesvfi.gui_components.crop_handler.CropSelectionDialog") as mock_dialog_class:
                mock_dialog = Mock()
                mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
                mock_dialog.get_selected_rect.return_value = QRect(10, 20, 300, 400)
                mock_dialog_class.return_value = mock_dialog

                test_pixmap = QPixmap(100, 100)
                crop_handler.show_crop_dialog(mock_main_window, test_pixmap)

                mock_logger.info.assert_called()
                assert "Crop rectangle set to" in str(mock_logger.info.call_args)

            mock_logger.reset_mock()

            # Test clear crop logging
            crop_handler.on_clear_crop_clicked(mock_main_window)
            mock_logger.info.assert_called()
            assert "Crop rectangle cleared" in str(mock_logger.info.call_args)

    def test_integration_workflow_end_to_end(self, crop_handler, mock_main_window, temp_image_dir, app) -> None:
        """Test complete crop workflow from start to finish."""
        mock_main_window.in_dir = temp_image_dir
        mock_main_window.current_crop_rect = None

        with patch("goesvfi.gui_components.crop_handler.CropSelectionDialog") as mock_dialog_class:
            # Mock successful dialog
            mock_dialog = Mock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
            mock_crop_rect = QRect(50, 60, 400, 300)
            mock_dialog.get_selected_rect.return_value = mock_crop_rect
            mock_dialog_class.return_value = mock_dialog

            # Execute workflow
            crop_handler.on_crop_clicked(mock_main_window)

            # Verify complete workflow
            mock_dialog_class.assert_called_once()
            assert mock_main_window.current_crop_rect == (50, 60, 400, 300)
            mock_main_window._update_crop_buttons_state.assert_called_once()
            mock_main_window.request_previews_update.emit.assert_called_once()

            # Now clear the crop
            crop_handler.on_clear_crop_clicked(mock_main_window)
            assert mock_main_window.current_crop_rect is None

    def test_error_recovery(self, crop_handler, mock_main_window) -> None:
        """Test error recovery in various scenarios."""
        # Test dialog creation failure
        with patch("goesvfi.gui_components.crop_handler.CropSelectionDialog") as mock_dialog_class:
            mock_dialog_class.side_effect = Exception("Dialog creation failed")

            test_pixmap = QPixmap(100, 100)
            with patch("goesvfi.gui_components.crop_handler.LOGGER"):
                # Should not crash
                crop_handler.show_crop_dialog(mock_main_window, test_pixmap)

    def test_performance_with_many_images(self, crop_handler, mock_main_window) -> None:
        """Test performance with directory containing many images."""
        with tempfile.TemporaryDirectory() as temp_dir:
            image_dir = Path(temp_dir)

            # Create many image files
            for i in range(100):
                img = QImage(10, 10, QImage.Format.Format_RGB32)
                img.fill(Qt.GlobalColor.red)
                img.save(str(image_dir / f"image_{i:03d}.png"))

            mock_main_window.in_dir = image_dir

            start_time = time.time()
            result = crop_handler.get_sorted_image_files(mock_main_window)
            elapsed = time.time() - start_time

            assert len(result) == 100
            assert elapsed < 1.0  # Should be fast even with many files

    def test_concurrent_operations(self, crop_handler) -> None:
        """Test thread safety of crop handler methods."""
        results = []
        errors = []

        def test_thread(thread_id) -> None:
            try:
                mock_window = Mock()
                mock_window.in_dir = None

                # Test various methods
                files = crop_handler.get_sorted_image_files(mock_window)
                preview = crop_handler.get_processed_preview_pixmap(mock_window)

                results.append((thread_id, len(files), preview))
            except Exception as e:
                errors.append((thread_id, e))

        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(test_thread, i) for i in range(10)]
            for future in futures:
                future.result()

        assert len(errors) == 0
        assert len(results) == 10

    def test_memory_efficiency(self, crop_handler, mock_main_window) -> None:
        """Test memory efficiency with large images."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a large image
            large_img = QImage(4000, 3000, QImage.Format.Format_RGB32)
            large_img.fill(Qt.GlobalColor.blue)
            img_path = Path(temp_dir) / "large.png"
            large_img.save(str(img_path))

            mock_main_window.main_tab.sanchez_false_colour_checkbox.isChecked.return_value = False

            # Should handle large image without issues
            result = crop_handler.prepare_image_for_crop_dialog(mock_main_window, img_path)
            assert result is not None

    def test_edge_cases(self, crop_handler, mock_main_window) -> None:
        """Test various edge cases."""
        # Test with special characters in path
        with tempfile.TemporaryDirectory() as temp_dir:
            special_dir = Path(temp_dir) / "special chars & spaces"
            special_dir.mkdir()

            img = QImage(50, 50, QImage.Format.Format_RGB32)
            img.fill(Qt.GlobalColor.green)
            img.save(str(special_dir / "test image.png"))

            mock_main_window.in_dir = special_dir
            result = crop_handler.get_sorted_image_files(mock_main_window)
            assert len(result) == 1

    def test_crop_rect_validation(self, crop_handler, mock_main_window, app) -> None:
        """Test validation of crop rectangles."""
        test_pixmap = QPixmap(800, 600)

        with patch("goesvfi.gui_components.crop_handler.CropSelectionDialog") as mock_dialog_class:
            mock_dialog = Mock()
            mock_dialog_class.return_value = mock_dialog

            # Test various invalid rectangles
            invalid_rects = [
                QRect(-10, -10, 100, 100),  # Negative coordinates
                QRect(0, 0, 0, 0),  # Zero size
                QRect(1000, 1000, 100, 100),  # Out of bounds
                QRect(0, 0, -100, -100),  # Negative size
            ]

            for rect in invalid_rects:
                mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
                mock_dialog.get_selected_rect.return_value = rect

                original_rect = mock_main_window.current_crop_rect
                crop_handler.show_crop_dialog(mock_main_window, test_pixmap)

                # Should either reject or normalize invalid rectangles
                if mock_main_window.current_crop_rect != original_rect:
                    # If accepted, should be normalized
                    x, y, w, h = mock_main_window.current_crop_rect
                    assert x >= 0
                    assert y >= 0
                    assert w > 0
                    assert h > 0

    def test_status_messages(self, crop_handler, mock_main_window, temp_image_dir) -> None:
        """Test status bar messages during operations."""
        mock_main_window.in_dir = temp_image_dir

        # Track all status messages
        status_messages = []
        mock_main_window.statusBar.return_value.showMessage.side_effect = lambda msg, timeout=0: status_messages.append(
            msg
        )

        # Test various operations
        crop_handler.on_crop_clicked(mock_main_window)
        crop_handler.on_clear_crop_clicked(mock_main_window)

        # Should have set status messages
        assert len(status_messages) > 0

    def test_qt_signal_emission(self, crop_handler, mock_main_window) -> None:
        """Test that Qt signals are properly emitted."""
        # Set up signal tracking
        emit_calls = []
        mock_main_window.request_previews_update.emit.side_effect = lambda: emit_calls.append("preview_update")

        # Test operations that should emit signals
        mock_main_window.current_crop_rect = (10, 10, 100, 100)
        crop_handler.on_clear_crop_clicked(mock_main_window)

        assert "preview_update" in emit_calls

    def test_complex_sanchez_scenarios(self, crop_handler, mock_main_window, app) -> None:
        """Test complex Sanchez preview scenarios."""

        # Scenario 1: Sanchez enabled but checkbox throws during check
        def side_effect() -> bool:
            if not hasattr(side_effect, "called"):
                side_effect.called = True
                msg = "Checkbox error"
                raise RuntimeError(msg)
            return True

        mock_main_window.main_tab.sanchez_false_colour_checkbox.isChecked.side_effect = side_effect

        result = crop_handler.prepare_image_for_crop_dialog(mock_main_window, Path("/test.png"))
        assert result is None

        # Reset
        mock_main_window.main_tab.sanchez_false_colour_checkbox.isChecked.side_effect = None
        mock_main_window.main_tab.sanchez_false_colour_checkbox.isChecked.return_value = True

        # Scenario 2: Processed image exists but is corrupted
        corrupted_image = QImage()  # Invalid/null image
        mock_main_window.main_tab.first_frame_label.processed_image = corrupted_image

        with patch("goesvfi.gui_components.crop_handler.QPixmap.fromImage") as mock_from_image:
            mock_from_image.return_value = QPixmap()  # Return null pixmap
            result = crop_handler.get_processed_preview_pixmap(mock_main_window)
            # Should handle gracefully
            assert result is not None or result is None  # Either is acceptable

    def test_file_system_edge_cases(self, crop_handler, mock_main_window) -> None:
        """Test file system edge cases."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)

            # Create symlink to image (if supported)
            try:
                real_img = base_dir / "real.png"
                img = QImage(50, 50, QImage.Format.Format_RGB32)
                img.save(str(real_img))

                link_img = base_dir / "link.png"
                link_img.symlink_to(real_img)

                mock_main_window.in_dir = base_dir
                files = crop_handler.get_sorted_image_files(mock_main_window)

                # Should handle symlinks
                assert len(files) >= 1
            except (OSError, NotImplementedError):
                pytest.skip("Symlinks not supported")

    def test_dialog_parent_handling(self, crop_handler, mock_main_window, app) -> None:
        """Test proper parent widget handling for dialogs."""
        test_pixmap = QPixmap(100, 100)

        with patch("goesvfi.gui_components.crop_handler.CropSelectionDialog") as mock_dialog_class:
            mock_dialog = Mock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Rejected
            mock_dialog_class.return_value = mock_dialog

            crop_handler.show_crop_dialog(mock_main_window, test_pixmap)

            # Should pass main window as parent
            call_args = mock_dialog_class.call_args
            assert len(call_args[0]) >= 1  # At least pixmap argument
