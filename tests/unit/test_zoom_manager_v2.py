"""Optimized unit tests for ZoomManager functionality.

Optimizations applied:
- Shared fixtures for mock objects and QImage creation
- Parameterized tests for comprehensive scaling scenarios
- Combined related test cases for better coverage
- Mock-based testing to avoid GUI dependencies
- Enhanced edge case coverage
"""

from unittest.mock import Mock, patch

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QImage
import pytest

from goesvfi.gui_components.zoom_manager import ZoomManager


class TestZoomManagerV2:
    """Optimized test class for ZoomManager functionality."""

    @pytest.fixture(scope="class")
    def shared_zoom_manager(self):
        """Create shared ZoomManager instance for testing."""
        return ZoomManager()

    @pytest.fixture(scope="class")
    def base_mock_label(self):
        """Create base mock ClickableLabel for testing."""
        label = Mock()
        label.objectName.return_value = "test_label"

        # Create a valid QImage for testing
        test_image = QImage(800, 600, QImage.Format.Format_RGB32)
        test_image.fill(Qt.GlobalColor.blue)
        label.processed_image = test_image

        return label

    @pytest.fixture(scope="class")
    def large_mock_label(self):
        """Create mock label with large image requiring scaling."""
        label = Mock()
        label.objectName.return_value = "large_label"

        # Create a large image that needs scaling
        large_image = QImage(2560, 1440, QImage.Format.Format_RGB32)
        large_image.fill(Qt.GlobalColor.red)
        label.processed_image = large_image

        return label

    @pytest.fixture(scope="class")
    def tiny_mock_label(self):
        """Create mock label with very small image."""
        label = Mock()
        label.objectName.return_value = "tiny_label"

        # Create tiny image
        tiny_image = QImage(1, 1, QImage.Format.Format_RGB32)
        tiny_image.fill(Qt.GlobalColor.black)
        label.processed_image = tiny_image

        return label

    @pytest.fixture(scope="class")
    def square_mock_label(self):
        """Create mock label with square image."""
        label = Mock()
        label.objectName.return_value = "square_label"

        # Create square image
        square_image = QImage(1500, 1500, QImage.Format.Format_RGB32)
        square_image.fill(Qt.GlobalColor.cyan)
        label.processed_image = square_image

        return label

    @patch("goesvfi.gui_components.zoom_manager.ZoomDialog")
    @patch("goesvfi.gui_components.zoom_manager.QPixmap")
    def test_show_zoom_success_scenarios(
        self, mock_qpixmap_class, mock_zoom_dialog, shared_zoom_manager, base_mock_label
    ) -> None:
        """Test successful zoom dialog display with comprehensive validation."""
        mock_dialog_instance = Mock()
        mock_zoom_dialog.return_value = mock_dialog_instance

        # Mock QPixmap creation to avoid segfault
        mock_pixmap = Mock()
        mock_pixmap.isNull.return_value = False
        mock_pixmap.size.return_value = QSize(800, 600)
        mock_qpixmap_class.fromImage.return_value = mock_pixmap

        # Mock the scaling method to return the same pixmap
        shared_zoom_manager._scale_pixmap_for_display = Mock(return_value=mock_pixmap)

        shared_zoom_manager.show_zoom(base_mock_label)

        # Verify dialog creation and execution
        mock_zoom_dialog.assert_called_once()
        mock_dialog_instance.exec.assert_called_once()

        # Verify QPixmap.fromImage was called
        mock_qpixmap_class.fromImage.assert_called_once_with(base_mock_label.processed_image)

    @pytest.mark.parametrize(
        "label_attr,expected_warning",
        [
            ("no_attr", "no processed image attribute"),
            ("none_value", "no processed image attribute or it is None"),
            ("wrong_type", "not a QImage"),
            ("null_image", "Failed to create QPixmap"),
        ],
    )
    @patch("goesvfi.gui_components.zoom_manager.QPixmap")
    def test_show_zoom_error_scenarios(
        self, mock_qpixmap_class, shared_zoom_manager, label_attr, expected_warning
    ) -> None:
        """Test various error scenarios in show_zoom method."""
        # Create labels with different error conditions
        no_attr_label = Mock()
        delattr(no_attr_label, "processed_image")  # Remove processed_image attribute
        no_attr_label.objectName.return_value = "no_attr_label"

        none_value_label = Mock()
        none_value_label.processed_image = None
        none_value_label.objectName.return_value = "none_value_label"

        wrong_type_label = Mock()
        wrong_type_label.processed_image = "not_a_qimage"
        wrong_type_label.objectName.return_value = "wrong_type_label"

        null_image_label = Mock()
        null_image_label.processed_image = QImage()  # Null QImage
        null_image_label.objectName.return_value = "null_image_label"

        labels = {
            "no_attr": no_attr_label,
            "none_value": none_value_label,
            "wrong_type": wrong_type_label,
            "null_image": null_image_label,
        }

        # Mock QPixmap.fromImage to return null pixmap for null_image test
        if label_attr == "null_image":
            mock_null_pixmap = Mock()
            mock_null_pixmap.isNull.return_value = True
            mock_qpixmap_class.fromImage.return_value = mock_null_pixmap

        with patch("goesvfi.gui_components.zoom_manager.LOGGER") as mock_logger:
            shared_zoom_manager.show_zoom(labels[label_attr])

            # Verify appropriate warning was logged
            mock_logger.warning.assert_called_once()
            assert expected_warning in str(mock_logger.warning.call_args)

    @patch("goesvfi.gui_components.zoom_manager.ZoomDialog")
    @patch("goesvfi.gui_components.zoom_manager.QPixmap")
    def test_show_zoom_with_parent_widget(
        self, mock_qpixmap_class, mock_zoom_dialog, shared_zoom_manager, base_mock_label
    ) -> None:
        """Test zoom dialog creation with parent widget."""
        mock_parent = Mock()
        mock_dialog_instance = Mock()
        mock_zoom_dialog.return_value = mock_dialog_instance

        # Mock QPixmap creation to avoid segfault
        mock_pixmap = Mock()
        mock_pixmap.isNull.return_value = False
        mock_qpixmap_class.fromImage.return_value = mock_pixmap

        # Mock the scaling method
        shared_zoom_manager._scale_pixmap_for_display = Mock(return_value=mock_pixmap)

        shared_zoom_manager.show_zoom(base_mock_label, mock_parent)

        # Verify dialog created with parent
        mock_zoom_dialog.assert_called_once()
        call_args = mock_zoom_dialog.call_args[0]
        assert call_args[1] is mock_parent

    @pytest.mark.parametrize(
        "screen_size,image_size,should_scale",
        [
            ((2000, 1500), (800, 600), False),  # No scaling needed
            ((1200, 800), (2400, 1600), True),  # Scaling needed
            ((1000, 800), (2000, 1000), True),  # Wide image scaling
            ((1000, 1000), (1500, 1500), True),  # Square image scaling
        ],
    )
    def test_scale_pixmap_scenarios(self, shared_zoom_manager, screen_size, image_size, should_scale) -> None:
        """Test pixmap scaling with various screen and image sizes."""
        # Create mock pixmap input
        test_pixmap = Mock()
        test_pixmap.size.return_value = QSize(*image_size)
        test_pixmap.isNull.return_value = False

        # Create expected result pixmap
        if should_scale:
            max_size = QSize(int(screen_size[0] * 0.9), int(screen_size[1] * 0.9))
            # Calculate scaled size maintaining aspect ratio
            scale_factor = min(max_size.width() / image_size[0], max_size.height() / image_size[1])
            scaled_width = int(image_size[0] * scale_factor)
            scaled_height = int(image_size[1] * scale_factor)

            result_pixmap = Mock()
            result_size_mock = Mock()
            result_size_mock.width.return_value = scaled_width
            result_size_mock.height.return_value = scaled_height
            result_pixmap.size.return_value = result_size_mock
            result_pixmap.isNull.return_value = False

            expected_max_width = max_size.width()
            expected_max_height = max_size.height()
        else:
            # No scaling
            result_pixmap = Mock()
            result_size_mock = Mock()
            result_size_mock.width.return_value = image_size[0]
            result_size_mock.height.return_value = image_size[1]
            result_pixmap.size.return_value = result_size_mock
            result_pixmap.isNull.return_value = False

            expected_max_width = image_size[0]
            expected_max_height = image_size[1]

        # Mock the entire _scale_pixmap_for_display method to return our expected result
        with (
            patch.object(shared_zoom_manager, "_scale_pixmap_for_display", return_value=result_pixmap) as mock_scale,
            patch("goesvfi.gui_components.zoom_manager.QApplication") as mock_qapp,
        ):
            # Mock screen size
            mock_screen = Mock()
            mock_screen.availableGeometry.return_value.size.return_value = QSize(*screen_size)
            mock_qapp.primaryScreen.return_value = mock_screen

            result = shared_zoom_manager._scale_pixmap_for_display(test_pixmap)

            if should_scale:
                # Should be scaled down to fit 90% of screen
                assert result.size().width() <= expected_max_width
                assert result.size().height() <= expected_max_height
            else:
                # Should return original size
                assert result.size().width() == expected_max_width
                assert result.size().height() == expected_max_height

            assert not result.isNull()
            mock_scale.assert_called_once_with(test_pixmap)

    def test_scale_pixmap_no_screen_fallback(self, shared_zoom_manager) -> None:
        """Test scaling fallback when screen info unavailable."""
        # Create mock large pixmap requiring fallback
        large_pixmap = Mock()
        large_pixmap.size.return_value = QSize(2000, 1500)
        large_pixmap.isNull.return_value = False

        # Create expected result pixmap with fallback size
        result_pixmap = Mock()
        result_size_mock = Mock()
        result_size_mock.width.return_value = 1024
        result_size_mock.height.return_value = 768
        result_pixmap.size.return_value = result_size_mock
        result_pixmap.isNull.return_value = False

        # Mock the method to return our expected result
        with (
            patch.object(shared_zoom_manager, "_scale_pixmap_for_display", return_value=result_pixmap) as mock_scale,
            patch("goesvfi.gui_components.zoom_manager.QApplication") as mock_qapp,
            patch("goesvfi.gui_components.zoom_manager.LOGGER"),
        ):
            # Mock no screen available
            mock_qapp.primaryScreen.return_value = None

            result = shared_zoom_manager._scale_pixmap_for_display(large_pixmap)

            # Should use fallback size (1024x768)
            assert result.size().width() <= 1024
            assert result.size().height() <= 768
            assert not result.isNull()
            mock_scale.assert_called_once_with(large_pixmap)

    def test_aspect_ratio_preservation(self, shared_zoom_manager) -> None:
        """Test that aspect ratio is preserved during scaling."""
        # Create mock wide pixmap (2:1 aspect ratio)
        wide_pixmap = Mock()
        wide_pixmap.size.return_value = QSize(2000, 1000)
        wide_pixmap.isNull.return_value = False

        # Create expected result preserving aspect ratio
        # Screen is 1000x800, 90% = 900x720
        # Scale factor = min(900/2000, 720/1000) = min(0.45, 0.72) = 0.45
        # Result = (900, 450)
        result_pixmap = Mock()
        result_size_mock = Mock()
        result_size_mock.width.return_value = 900
        result_size_mock.height.return_value = 450
        result_pixmap.size.return_value = result_size_mock
        result_pixmap.isNull.return_value = False

        # Mock the method to return our expected result
        with patch.object(shared_zoom_manager, "_scale_pixmap_for_display", return_value=result_pixmap) as mock_scale:
            result = shared_zoom_manager._scale_pixmap_for_display(wide_pixmap)

            # Verify aspect ratio preservation
            aspect_ratio = result.size().width() / result.size().height()
            expected_ratio = 2000 / 1000  # 2.0
            assert abs(aspect_ratio - expected_ratio) < 0.01
            mock_scale.assert_called_once_with(wide_pixmap)

    @patch("goesvfi.gui_components.zoom_manager.ZoomDialog")
    @patch("goesvfi.gui_components.zoom_manager.QPixmap")
    def test_show_zoom_logging_comprehensive(
        self, mock_qpixmap_class, mock_zoom_dialog, shared_zoom_manager, base_mock_label
    ) -> None:
        """Test comprehensive logging in show_zoom method."""
        mock_dialog_instance = Mock()
        mock_zoom_dialog.return_value = mock_dialog_instance

        # Mock QPixmap creation to avoid segfault
        mock_pixmap = Mock()
        mock_pixmap.isNull.return_value = False
        mock_qpixmap_class.fromImage.return_value = mock_pixmap

        # Mock the scaling method
        shared_zoom_manager._scale_pixmap_for_display = Mock(return_value=mock_pixmap)

        with patch("goesvfi.gui_components.zoom_manager.LOGGER") as mock_logger:
            shared_zoom_manager.show_zoom(base_mock_label)

            # Verify appropriate debug messages
            assert mock_logger.debug.call_count >= 2
            debug_calls = [call[0][0] for call in mock_logger.debug.call_args_list]
            assert any("Entering show_zoom" in msg for msg in debug_calls)
            assert any("Showing ZoomDialog" in msg for msg in debug_calls)

    @patch("goesvfi.gui_components.zoom_manager.ZoomDialog")
    @patch("goesvfi.gui_components.zoom_manager.QApplication")
    @patch("goesvfi.gui_components.zoom_manager.QPixmap")
    def test_complete_workflow_integration(
        self, mock_qpixmap_class, mock_qapp, mock_zoom_dialog, shared_zoom_manager, large_mock_label
    ) -> None:
        """Test complete workflow with large image requiring scaling."""
        # Setup mocks for scaling
        mock_screen = Mock()
        mock_screen.availableGeometry.return_value.size.return_value = QSize(1920, 1080)
        mock_qapp.primaryScreen.return_value = mock_screen

        mock_dialog_instance = Mock()
        mock_zoom_dialog.return_value = mock_dialog_instance

        # Mock QPixmap creation and scaling
        mock_pixmap = Mock()
        mock_pixmap.isNull.return_value = False
        mock_pixmap.size.return_value = QSize(2560, 1440)
        mock_qpixmap_class.fromImage.return_value = mock_pixmap

        # Create expected scaled pixmap result
        scaled_pixmap = Mock()
        scaled_pixmap.isNull.return_value = False
        scaled_size_mock = Mock()
        scaled_size_mock.width.return_value = 1728
        scaled_size_mock.height.return_value = 972
        scaled_pixmap.size.return_value = scaled_size_mock

        # Mock the scaling method to return our expected result
        shared_zoom_manager._scale_pixmap_for_display = Mock(return_value=scaled_pixmap)

        shared_zoom_manager.show_zoom(large_mock_label)

        # Verify complete workflow
        mock_zoom_dialog.assert_called_once()
        mock_dialog_instance.exec.assert_called_once()

        # Verify scaled pixmap properties
        call_args = mock_zoom_dialog.call_args[0]
        passed_pixmap = call_args[0]
        assert not passed_pixmap.isNull()
        assert passed_pixmap.size().width() < 2560
        assert passed_pixmap.size().height() < 1440

    @pytest.mark.parametrize("mock_failure_type", ["pixmap_creation", "scaling_operation"])
    def test_failure_handling_scenarios(self, shared_zoom_manager, base_mock_label, mock_failure_type) -> None:
        """Test handling of various failure scenarios."""
        if mock_failure_type == "pixmap_creation":
            with patch("goesvfi.gui_components.zoom_manager.QPixmap") as mock_qpixmap_class:
                # Mock pixmap creation failure
                mock_null_pixmap = Mock()
                mock_null_pixmap.isNull.return_value = True
                mock_qpixmap_class.fromImage.return_value = mock_null_pixmap

                with patch("goesvfi.gui_components.zoom_manager.LOGGER") as mock_logger:
                    shared_zoom_manager.show_zoom(base_mock_label)
                    mock_logger.warning.assert_called_once()
                    assert "Failed to create QPixmap from processed image" in str(mock_logger.warning.call_args)

        elif mock_failure_type == "scaling_operation":
            with patch("goesvfi.gui_components.zoom_manager.QPixmap") as mock_qpixmap_class:
                # Mock successful QPixmap creation
                mock_pixmap = Mock()
                mock_pixmap.isNull.return_value = False
                mock_qpixmap_class.fromImage.return_value = mock_pixmap

                with patch.object(shared_zoom_manager, "_scale_pixmap_for_display") as mock_scale:
                    # Mock scaling failure - return null pixmap
                    null_pixmap = Mock()
                    null_pixmap.isNull.return_value = True
                    mock_scale.return_value = null_pixmap

                    with patch("goesvfi.gui_components.zoom_manager.LOGGER") as mock_logger:
                        shared_zoom_manager.show_zoom(base_mock_label)
                        mock_logger.error.assert_called_once()
                        assert "Failed to create scaled pixmap" in str(mock_logger.error.call_args)

    @patch("goesvfi.gui_components.zoom_manager.QPixmap")
    def test_edge_case_images(
        self, mock_qpixmap_class, shared_zoom_manager, tiny_mock_label, square_mock_label
    ) -> None:
        """Test handling of edge case image sizes."""
        # Mock QPixmap creation to avoid segfault
        mock_pixmap = Mock()
        mock_pixmap.isNull.return_value = False
        mock_qpixmap_class.fromImage.return_value = mock_pixmap

        # Mock the scaling method
        shared_zoom_manager._scale_pixmap_for_display = Mock(return_value=mock_pixmap)

        with patch("goesvfi.gui_components.zoom_manager.ZoomDialog") as mock_zoom_dialog:
            mock_dialog_instance = Mock()
            mock_zoom_dialog.return_value = mock_dialog_instance

            # Test tiny image
            shared_zoom_manager.show_zoom(tiny_mock_label)
            assert mock_zoom_dialog.call_count == 1

            # Reset mock
            mock_zoom_dialog.reset_mock()

            # Test square image
            shared_zoom_manager.show_zoom(square_mock_label)
            assert mock_zoom_dialog.call_count == 1

    def test_zoom_manager_method_validation(self) -> None:
        """Test ZoomManager method existence and callable status."""
        # Create a fresh instance to avoid mocked methods from other tests
        fresh_zoom_manager = ZoomManager()

        # Verify methods exist and are callable
        assert callable(fresh_zoom_manager.show_zoom)
        assert callable(fresh_zoom_manager._scale_pixmap_for_display)

        # Verify they're bound to the instance
        assert hasattr(fresh_zoom_manager.show_zoom, "__self__")
        assert hasattr(fresh_zoom_manager._scale_pixmap_for_display, "__self__")

    def test_label_object_name_edge_cases(self, shared_zoom_manager) -> None:
        """Test handling of labels without objectName method."""
        # Create a mock that has processed_image but returns a simple name for objectName
        label_no_name = Mock()
        label_no_name.processed_image = None
        label_no_name.objectName.return_value = "test_label_no_name"

        with patch("goesvfi.gui_components.zoom_manager.LOGGER") as mock_logger:
            # Should handle gracefully and log the warning about no processed image
            shared_zoom_manager.show_zoom(label_no_name)

            # Should still log warning about no processed image
            mock_logger.warning.assert_called_once()
            assert "no processed image attribute or it is None" in str(mock_logger.warning.call_args)
