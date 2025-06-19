"""Tests for gui_helpers utility functions and classes."""

from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, Mock, patch

import pytest
from PyQt6.QtCore import QPoint, QPointF, QRect, QSize, Qt
from PyQt6.QtGui import QImage, QMouseEvent, QPixmap, QWheelEvent
from PyQt6.QtWidgets import QApplication, QCheckBox, QLabel, QLineEdit, QSpinBox

from goesvfi.utils.gui_helpers import (
    ClickableLabel,
    CropDialog,
    CropLabel,
    CropSelectionDialog,
    ImageViewerDialog,
    RifeCapabilityManager,
    ZoomDialog,
)


@pytest.fixture
def app():
    """Create a QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.quit()


@pytest.fixture
def sample_image():
    """Create a sample QImage for testing."""
    image = QImage(800, 600, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    return image


@pytest.fixture
def sample_pixmap(sample_image):
    """Create a sample QPixmap from the sample image."""
    return QPixmap.fromImage(sample_image)


class TestClickableLabel:
    """Tests for the ClickableLabel class."""

    def test_init(self, app):
        """Test ClickableLabel initialization."""
        label = ClickableLabel()
        assert label.file_path is None
        assert label.processed_image is None
        assert label.cursor() == Qt.CursorShape.PointingHandCursor

    def test_mouse_release_emits_clicked(self, app):
        """Test that mouse release emits clicked signal."""
        label = ClickableLabel()

        # Connect a mock to the clicked signal
        mock_handler = Mock()
        label.clicked.connect(mock_handler)

        # Create a left button release event
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(50, 50),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        # Trigger the event
        label.mouseReleaseEvent(event)

        # Verify signal was emitted
        mock_handler.assert_called_once()

    def test_mouse_release_right_button_no_signal(self, app):
        """Test that right mouse button doesn't emit clicked signal."""
        label = ClickableLabel()

        # Connect a mock to the clicked signal
        mock_handler = Mock()
        label.clicked.connect(mock_handler)

        # Create a right button release event
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(50, 50),
            Qt.MouseButton.RightButton,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
        )

        # Trigger the event
        label.mouseReleaseEvent(event)

        # Verify signal was not emitted
        mock_handler.assert_not_called()


class TestZoomDialog:
    """Tests for the ZoomDialog class."""

    def test_init(self, app, sample_pixmap):
        """Test ZoomDialog initialization."""
        dialog = ZoomDialog(sample_pixmap)

        assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
        assert dialog.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        assert dialog.size() == sample_pixmap.size()

    def test_mouse_press_closes_dialog(self, app, sample_pixmap):
        """Test that mouse press closes the dialog."""
        dialog = ZoomDialog(sample_pixmap)

        # Mock the close method
        dialog.close = Mock()

        # Create a mouse press event
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(50, 50),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        # Trigger the event
        dialog.mousePressEvent(event)

        # Verify close was called
        dialog.close.assert_called_once()


class TestCropDialog:
    """Tests for the CropDialog class."""

    def test_init_without_initial_rect(self, app, sample_pixmap):
        """Test CropDialog initialization without initial rectangle."""
        dialog = CropDialog(sample_pixmap, None)

        assert dialog.windowTitle() == "Select Crop Region"
        assert dialog.original_pixmap == sample_pixmap
        assert dialog.scale_factor > 0
        assert dialog.crop_rect_scaled.isNull()

    def test_init_with_initial_rect(self, app, sample_pixmap):
        """Test CropDialog initialization with initial rectangle."""
        init_rect = (100, 100, 200, 150)
        dialog = CropDialog(sample_pixmap, init_rect)

        # Verify rubber band is set with scaled rectangle
        assert dialog.rubber.geometry().width() > 0
        assert dialog.rubber.geometry().height() > 0
        # Note: rubber band visibility is handled by show() call in __init__
        # but may not be visible until the dialog itself is shown

    def test_get_rect_with_scaling(self, app, sample_pixmap):
        """Test getRect returns properly scaled coordinates."""
        dialog = CropDialog(sample_pixmap, None)

        # Set a crop rectangle on the scaled image
        dialog.crop_rect_scaled = QRect(10, 10, 50, 50)
        dialog.scale_factor = 2.0  # Simulate 2x scaling

        result = dialog.getRect()

        # Should be scaled up by factor of 2
        assert result.x() == 20
        assert result.y() == 20
        assert result.width() == 100
        assert result.height() == 100

    def test_mouse_press_starts_selection(self, app, sample_pixmap):
        """Test mouse press starts crop selection."""
        dialog = CropDialog(sample_pixmap, None)

        # Create a mouse press event within label bounds
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(100, 100),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        # Make sure event position is within label geometry
        dialog.lbl.setGeometry(0, 0, 800, 600)

        dialog.mousePressEvent(event)

        assert not dialog.origin.isNull()
        # Note: rubber band visibility is controlled by show() call in mousePressEvent


class TestRifeCapabilityManager:
    """Tests for the RifeCapabilityManager class."""

    @patch("goesvfi.utils.gui_helpers.find_rife_executable")
    @patch("goesvfi.utils.gui_helpers.RifeCapabilityDetector")
    def test_init_successful_detection(self, mock_detector_class, mock_find_exe, app):
        """Test successful capability detection."""
        # Mock find_rife_executable
        mock_exe_path = Path("/path/to/rife")
        mock_find_exe.return_value = mock_exe_path

        # Mock detector instance
        mock_detector = Mock()
        mock_detector.supports_tiling.return_value = True
        mock_detector.supports_uhd.return_value = True
        mock_detector.supports_tta_spatial.return_value = False
        mock_detector.supports_tta_temporal.return_value = False
        mock_detector.supports_thread_spec.return_value = True
        mock_detector.supports_batch_processing.return_value = True
        mock_detector.supports_timestep.return_value = False
        mock_detector.supports_model_path.return_value = True
        mock_detector.supports_gpu_id.return_value = False
        mock_detector.version = "4.6"

        mock_detector_class.return_value = mock_detector

        # Create manager
        manager = RifeCapabilityManager("rife-v4.6")

        # Verify capabilities were detected
        assert manager.exe_path == mock_exe_path
        assert manager.version == "4.6"
        assert manager.capabilities["tiling"] is True
        assert manager.capabilities["uhd"] is True
        assert manager.capabilities["tta_spatial"] is False
        assert manager.capabilities["thread_spec"] is True

    @patch("goesvfi.utils.gui_helpers.find_rife_executable")
    def test_init_detection_failure(self, mock_find_exe, app):
        """Test handling of detection failure."""
        # Make find_rife_executable raise an exception
        mock_find_exe.side_effect = Exception("RIFE not found")

        # Create manager
        manager = RifeCapabilityManager("rife-v4.6")

        # All capabilities should be False
        assert all(not v for v in manager.capabilities.values())
        assert manager.exe_path is None
        assert manager.version is None

    def test_update_ui_elements_with_capabilities(self, app):
        """Test updating UI elements based on capabilities."""
        manager = RifeCapabilityManager()

        # Manually set capabilities for testing
        manager.capabilities = {
            "tiling": True,
            "uhd": True,
            "tta_spatial": False,
            "tta_temporal": False,
            "thread_spec": True,
            "batch_processing": True,
            "timestep": False,
            "model_path": True,
            "gpu_id": False,
        }

        # Create mock UI elements
        tile_cb = QCheckBox()
        tile_spin = QSpinBox()
        uhd_cb = QCheckBox()
        thread_edit = QLineEdit()
        thread_label = QLabel()
        tta_spatial_cb = QCheckBox()
        tta_temporal_cb = QCheckBox()

        # Update UI elements
        manager.update_ui_elements(
            tile_cb,
            tile_spin,
            uhd_cb,
            thread_edit,
            thread_label,
            tta_spatial_cb,
            tta_temporal_cb,
        )

        # Verify UI state
        assert tile_cb.isEnabled() is True
        assert uhd_cb.isEnabled() is True
        assert thread_edit.isEnabled() is True
        assert thread_label.isEnabled() is True
        assert tta_spatial_cb.isEnabled() is False
        assert tta_temporal_cb.isEnabled() is False

    def test_get_capability_summary(self, app):
        """Test capability summary generation."""
        manager = RifeCapabilityManager()

        # Set up test state
        manager.version = "4.6"
        manager.capabilities = {
            "tiling": True,
            "uhd": True,
            "tta_spatial": False,
            "tta_temporal": False,
            "thread_spec": True,
        }
        manager.detector = Mock()  # Just need it to be non-None

        summary = manager.get_capability_summary()

        assert "v4.6" in summary
        assert "3/5 features supported" in summary


class TestImageViewerDialog:
    """Tests for the ImageViewerDialog class."""

    def test_init_with_valid_image(self, app, sample_image):
        """Test ImageViewerDialog initialization with valid image."""
        dialog = ImageViewerDialog(sample_image)

        assert dialog.original_qimage == sample_image
        assert dialog.zoom_factor > 0
        assert dialog.pan_offset == QPointF(0.0, 0.0)
        assert not dialog.panning

    def test_init_with_null_image(self, app):
        """Test ImageViewerDialog with null image."""
        null_image = QImage()
        dialog = ImageViewerDialog(null_image)

        # Should handle gracefully
        assert dialog.original_qimage.isNull()

    def test_wheel_zoom_in(self, app, sample_image):
        """Test zooming in with mouse wheel."""
        dialog = ImageViewerDialog(sample_image)
        initial_zoom = dialog.zoom_factor

        # Create wheel event for zoom in
        event = QWheelEvent(
            QPointF(100, 100),  # Position
            QPointF(100, 100),  # Global position
            QPoint(0, 120),  # Pixel delta (not used)
            QPoint(0, 120),  # Angle delta (positive = zoom in)
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,  # Not inverted
        )

        dialog.wheelEvent(event)

        assert dialog.zoom_factor > initial_zoom

    def test_wheel_zoom_out(self, app, sample_image):
        """Test zooming out with mouse wheel."""
        dialog = ImageViewerDialog(sample_image)

        # First zoom in to have room to zoom out
        dialog.zoom_factor = 2.0
        initial_zoom = dialog.zoom_factor

        # Create wheel event for zoom out
        event = QWheelEvent(
            QPointF(100, 100),  # Position
            QPointF(100, 100),  # Global position
            QPoint(0, -120),  # Pixel delta (not used)
            QPoint(0, -120),  # Angle delta (negative = zoom out)
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,  # Not inverted
        )

        dialog.wheelEvent(event)

        assert dialog.zoom_factor < initial_zoom

    def test_mouse_drag_panning(self, app, sample_image):
        """Test panning with mouse drag."""
        dialog = ImageViewerDialog(sample_image)

        # Start panning
        press_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(100, 100),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        dialog.mousePressEvent(press_event)

        assert dialog.panning is True
        assert dialog.last_pan_pos == QPointF(100, 100)

        # Move mouse to pan
        move_event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(150, 150),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        dialog.mouseMoveEvent(move_event)

        assert dialog.was_dragged is True

        # Release to stop panning
        release_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(150, 150),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        dialog.mouseReleaseEvent(release_event)

        assert dialog.panning is False

    def test_click_closes_dialog(self, app, sample_image):
        """Test that clicking without dragging closes the dialog."""
        dialog = ImageViewerDialog(sample_image)
        dialog.accept = Mock()

        # Press and release at same position (no drag)
        press_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(100, 100),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        dialog.mousePressEvent(press_event)

        release_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(100, 100),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        dialog.mouseReleaseEvent(release_event)

        # Should close because no drag occurred
        dialog.accept.assert_called_once()


class TestCropLabel:
    """Tests for the CropLabel class."""

    def test_init(self, app):
        """Test CropLabel initialization."""
        label = CropLabel()

        assert label.alignment() == Qt.AlignmentFlag.AlignCenter
        assert label.hasMouseTracking() is True
        assert not label.selecting
        assert label.selection_start_point is None
        assert label.selection_end_point is None
        assert label.selected_rect is None

    def test_set_pixmap_updates_offset(self, app, sample_pixmap):
        """Test that setPixmap updates pixmap offset."""
        label = CropLabel()
        label.setFixedSize(1000, 800)  # Larger than pixmap

        label.setPixmap(sample_pixmap)

        # Should have non-zero offsets for centering
        assert label._pixmap_offset_x > 0
        assert label._pixmap_offset_y > 0

    def test_mouse_press_starts_selection(self, app, sample_pixmap):
        """Test mouse press starts selection."""
        label = CropLabel()
        label.setPixmap(sample_pixmap)

        # Mock the position mapping
        label._get_pos_on_pixmap = Mock(return_value=QPoint(50, 50))

        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(100, 100),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        label.mousePressEvent(event)

        assert label.selecting is True
        assert label.selection_start_point == QPoint(50, 50)
        assert label.selection_end_point == QPoint(50, 50)
        assert label.selected_rect is None

    def test_mouse_move_updates_selection(self, app, sample_pixmap):
        """Test mouse move updates selection during drag."""
        label = CropLabel()
        label.setPixmap(sample_pixmap)

        # Start selection
        label.selecting = True
        label.selection_start_point = QPoint(50, 50)

        # Mock the position mapping
        label._get_pos_on_pixmap = Mock(return_value=QPoint(150, 150))

        # Connect signal handler
        mock_handler = Mock()
        label.selection_changed.connect(mock_handler)

        event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(200, 200),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        label.mouseMoveEvent(event)

        assert label.selection_end_point == QPoint(150, 150)
        mock_handler.assert_called_once()

    def test_mouse_release_finalizes_selection(self, app, sample_pixmap):
        """Test mouse release finalizes selection."""
        label = CropLabel()
        label.setPixmap(sample_pixmap)

        # Set up ongoing selection
        label.selecting = True
        label.selection_start_point = QPoint(50, 50)
        label.selection_end_point = QPoint(150, 150)

        # Mock the position mapping
        label._get_pos_on_pixmap = Mock(return_value=QPoint(150, 150))

        # Connect signal handler
        mock_handler = Mock()
        label.selection_finished.connect(mock_handler)

        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(200, 200),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )

        label.mouseReleaseEvent(event)

        assert not label.selecting
        assert label.selected_rect is not None
        # QRect.normalized() may add 1 to width/height
        assert label.selected_rect.width() >= 100
        assert label.selected_rect.height() >= 100
        mock_handler.assert_called_once()


class TestCropSelectionDialog:
    """Tests for the CropSelectionDialog class."""

    def test_init_with_valid_image(self, app, sample_image):
        """Test CropSelectionDialog initialization with valid image."""
        dialog = CropSelectionDialog(sample_image)

        assert dialog.windowTitle() == "Select Crop Region"
        assert dialog.isModal() is True
        assert dialog.image == sample_image
        assert dialog.scale_factor > 0

    def test_init_with_null_image(self, app):
        """Test CropSelectionDialog with null image."""
        null_image = QImage()
        dialog = CropSelectionDialog(null_image)

        assert dialog.image.isNull()

    def test_get_selected_rect_no_selection(self, app, sample_image):
        """Test get_selected_rect returns empty rect when no selection."""
        dialog = CropSelectionDialog(sample_image)

        result = dialog.get_selected_rect()

        assert result.isNull()

    def test_get_selected_rect_with_selection(self, app, sample_image):
        """Test get_selected_rect with valid selection."""
        dialog = CropSelectionDialog(sample_image)

        # Simulate a selection
        dialog._final_selected_rect_display = QRect(10, 10, 50, 50)
        dialog.scale_factor = 2.0  # Display is scaled down by factor of 2

        result = dialog.get_selected_rect()

        # Should be scaled up by factor of 2
        assert result.x() == 20
        assert result.y() == 20
        assert result.width() == 100
        assert result.height() == 100

    def test_get_selected_rect_clamping(self, app, sample_image):
        """Test that get_selected_rect clamps to image boundaries."""
        dialog = CropSelectionDialog(sample_image)

        # Set a selection that would exceed image bounds when scaled
        dialog._final_selected_rect_display = QRect(300, 200, 100, 100)
        dialog.scale_factor = 4.0  # Would result in 1200, 800, 400, 400

        result = dialog.get_selected_rect()

        # Should be clamped to image size (800x600)
        assert result.right() < sample_image.width()
        assert result.bottom() < sample_image.height()

    def test_store_final_selection(self, app, sample_image):
        """Test _store_final_selection method."""
        dialog = CropSelectionDialog(sample_image)

        # Test with valid rectangle
        valid_rect = QRect(10, 10, 100, 100)
        dialog._store_final_selection(valid_rect)
        assert dialog._final_selected_rect_display == valid_rect

        # Test with null rectangle
        dialog._store_final_selection(QRect())
        assert dialog._final_selected_rect_display is None

        # Test with zero-size rectangle
        dialog._store_final_selection(QRect(10, 10, 0, 0))
        assert dialog._final_selected_rect_display is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
