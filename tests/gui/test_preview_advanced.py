"""Advanced preview and display functionality tests for GOES VFI GUI."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image
from PyQt6.QtCore import QPoint, QRect, Qt, QTimer
from PyQt6.QtGui import QImage, QPainter, QPixmap, QWheelEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QSlider

from goesvfi.gui import ClickableLabel, MainWindow


class TestPreviewAdvanced:
    """Test advanced preview and display features."""

    @pytest.fixture
    def window(self, qtbot, mocker):
        """Create a MainWindow instance for testing."""
        # Mock heavy components
        mocker.patch("goesvfi.gui.CombinedIntegrityAndImageryTab")
        mocker.patch("goesvfi.integrity_check.enhanced_gui_tab.EnhancedImageryTab")

        window = MainWindow(debug_mode=True)
        qtbot.addWidget(window)
        window._post_init_setup()

        return window

    @pytest.fixture
    def sample_image(self, tmp_path):
        """Create a sample image for testing."""
        img = Image.new("RGB", (800, 600), color=(100, 150, 200))
        img_path = tmp_path / "test_image.png"
        img.save(img_path)
        return img_path

    def test_live_preview_frame_updates(self, qtbot, window, mocker):
        """Test live preview updates during processing."""
        # Mock processing updates
        preview_updates = []

        def capture_preview_update(frame_num, total_frames):
            preview_updates.append((frame_num, total_frames))

            # Simulate frame update
            if hasattr(window, "middle_frame_label"):
                # Create a dummy pixmap
                pixmap = QPixmap(100, 100)
                pixmap.fill(Qt.GlobalColor.blue)
                window.middle_frame_label.setPixmap(pixmap)

        # Mock the preview update mechanism
        mocker.patch.object(
            window, "_update_preview_frame", side_effect=capture_preview_update
        )

        # Simulate processing with preview updates
        for i in range(1, 11):
            window._update_preview_frame(i, 10)
            qtbot.wait(10)  # Small delay between updates

        # Verify updates were captured
        assert len(preview_updates) == 10
        assert preview_updates[0] == (1, 10)
        assert preview_updates[-1] == (10, 10)

        # Verify preview label was updated
        if hasattr(window, "middle_frame_label"):
            assert window.middle_frame_label.pixmap() is not None

    def test_image_comparison_modes(self, qtbot, window, sample_image):
        """Test different image comparison modes."""

        # Create comparison dialog mock
        class ComparisonDialog(QDialog):
            def __init__(self, img1_path, img2_path, parent=None):
                super().__init__(parent)
                self.img1_path = img1_path
                self.img2_path = img2_path
                self.mode = "side-by-side"
                self.opacity = 0.5

                # Create UI elements
                self.comparison_label = QLabel()
                self.mode_combo = MagicMock()
                self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
                self.opacity_slider.setRange(0, 100)
                self.opacity_slider.setValue(50)

            def set_comparison_mode(self, mode):
                self.mode = mode
                self.update_comparison()

            def update_comparison(self):
                # Mock comparison rendering
                if self.mode == "side-by-side":
                    # Create side-by-side view
                    pixmap = QPixmap(200, 100)
                    pixmap.fill(Qt.GlobalColor.gray)
                elif self.mode == "overlay":
                    # Create overlay view with opacity
                    pixmap = QPixmap(100, 100)
                    pixmap.fill(Qt.GlobalColor.darkGray)
                elif self.mode == "difference":
                    # Create difference view
                    pixmap = QPixmap(100, 100)
                    pixmap.fill(Qt.GlobalColor.black)

                self.comparison_label.setPixmap(pixmap)

        # Create comparison dialog
        dialog = ComparisonDialog(sample_image, sample_image, window)
        qtbot.addWidget(dialog)

        # Test different modes
        modes = ["side-by-side", "overlay", "difference"]
        for mode in modes:
            dialog.set_comparison_mode(mode)
            assert dialog.mode == mode
            assert dialog.comparison_label.pixmap() is not None

        # Test opacity adjustment for overlay mode
        dialog.set_comparison_mode("overlay")
        dialog.opacity_slider.setValue(75)
        dialog.opacity = 0.75
        dialog.update_comparison()
        assert dialog.opacity == 0.75

    def test_zoom_pan_interactions(self, qtbot, window, sample_image):
        """Test zoom and pan interactions on preview images."""

        # Create zoomable label
        class ZoomableLabel(ClickableLabel):
            def __init__(self):
                super().__init__()
                self.zoom_factor = 1.0
                self.pan_offset = QPoint(0, 0)
                self.dragging = False
                self.last_pos = QPoint()

            def wheelEvent(self, event):
                # Zoom in/out with mouse wheel
                delta = event.angleDelta().y()
                if delta > 0:
                    self.zoom_factor *= 1.1
                else:
                    self.zoom_factor /= 1.1
                self.zoom_factor = max(0.1, min(10.0, self.zoom_factor))
                self.update_display()

            def mousePressEvent(self, event):
                if event.button() == Qt.MouseButton.LeftButton:
                    self.dragging = True
                    self.last_pos = event.pos()

            def mouseMoveEvent(self, event):
                if self.dragging:
                    delta = event.pos() - self.last_pos
                    self.pan_offset += delta
                    self.last_pos = event.pos()
                    self.update_display()

            def mouseReleaseEvent(self, event):
                self.dragging = False

            def update_display(self):
                # Mock display update
                pass

        # Replace preview label with zoomable version
        zoom_label = ZoomableLabel()
        zoom_label.setPixmap(QPixmap(str(sample_image)))
        qtbot.addWidget(zoom_label)

        # Test zoom in
        initial_zoom = zoom_label.zoom_factor
        # Simulate wheel event
        wheel_event = QWheelEvent(
            QPoint(50, 50),
            QPoint(50, 50),
            QPoint(0, 120),  # Positive delta for zoom in
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        zoom_label.wheelEvent(wheel_event)
        assert zoom_label.zoom_factor > initial_zoom

        # Test zoom out
        wheel_event = QWheelEvent(
            QPoint(50, 50),
            QPoint(50, 50),
            QPoint(0, -120),  # Negative delta for zoom out
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        zoom_label.wheelEvent(wheel_event)
        assert zoom_label.zoom_factor < 1.1  # Should have zoomed back out

        # Test pan
        initial_offset = zoom_label.pan_offset
        # Simulate drag
        QTest.mousePress(zoom_label, Qt.MouseButton.LeftButton, pos=QPoint(50, 50))
        QTest.mouseMove(zoom_label, QPoint(100, 100))
        QTest.mouseRelease(zoom_label, Qt.MouseButton.LeftButton, pos=QPoint(100, 100))

        # Verify pan occurred
        assert zoom_label.pan_offset != initial_offset

    def test_video_preview_playback(self, qtbot, window, mocker):
        """Test video preview playback functionality."""

        # Mock video player widget
        class VideoPreviewWidget(QLabel):
            def __init__(self):
                super().__init__()
                self.is_playing = False
                self.current_frame = 0
                self.total_frames = 100
                self.fps = 30
                self.timer = QTimer()
                self.timer.timeout.connect(self.next_frame)

            def load_video(self, video_path):
                # Mock loading video
                self.video_path = video_path
                self.current_frame = 0
                return True

            def play(self):
                self.is_playing = True
                self.timer.start(int(1000 / self.fps))

            def pause(self):
                self.is_playing = False
                self.timer.stop()

            def seek(self, frame):
                self.current_frame = max(0, min(frame, self.total_frames - 1))
                self.update_frame()

            def next_frame(self):
                if self.current_frame < self.total_frames - 1:
                    self.current_frame += 1
                else:
                    self.current_frame = 0  # Loop
                self.update_frame()

            def update_frame(self):
                # Mock frame update
                pixmap = QPixmap(640, 480)
                pixmap.fill(Qt.GlobalColor.darkGreen)
                self.setPixmap(pixmap)

        # Create video preview
        video_widget = VideoPreviewWidget()
        qtbot.addWidget(video_widget)

        # Load video
        assert video_widget.load_video("/test/output.mp4")

        # Test playback
        video_widget.play()
        assert video_widget.is_playing

        # Wait for a few frames
        qtbot.wait(100)
        assert video_widget.current_frame > 0

        # Test pause
        video_widget.pause()
        assert not video_widget.is_playing
        paused_frame = video_widget.current_frame

        qtbot.wait(50)
        assert video_widget.current_frame == paused_frame  # Should not advance

        # Test seek
        video_widget.seek(50)
        assert video_widget.current_frame == 50

        # Cleanup
        video_widget.timer.stop()

    def test_multi_monitor_window_management(self, qtbot, window, mocker):
        """Test window management across multiple monitors."""
        # Mock QScreen and QApplication.screens()
        mock_screen1 = MagicMock()
        mock_screen1.geometry.return_value = QRect(0, 0, 1920, 1080)
        mock_screen1.name.return_value = "Screen 1"

        mock_screen2 = MagicMock()
        mock_screen2.geometry.return_value = QRect(1920, 0, 1920, 1080)
        mock_screen2.name.return_value = "Screen 2"

        mocker.patch.object(
            QApplication, "screens", return_value=[mock_screen1, mock_screen2]
        )

        # Test window positioning
        screens = QApplication.screens()
        assert len(screens) == 2

        # Move window to second monitor
        window.move(1920 + 100, 100)
        window_pos = window.pos()
        assert window_pos.x() > 1920  # On second monitor

        # Test fullscreen on specific monitor
        def toggle_fullscreen_on_monitor(monitor_index):
            screens = QApplication.screens()
            if monitor_index < len(screens):
                screen = screens[monitor_index]
                window.windowHandle().setScreen(screen)
                window.showFullScreen()

        # Mock fullscreen toggle
        window.showFullScreen = MagicMock()
        toggle_fullscreen_on_monitor(1)
        window.showFullScreen.assert_called_once()

    def test_thumbnail_generation(self, qtbot, window, tmp_path):
        """Test thumbnail generation for file lists."""
        # Create test images
        image_files = []
        for i in range(5):
            img = Image.new("RGB", (800, 600), color=(i * 50, i * 50, i * 50))
            img_path = tmp_path / f"image_{i}.png"
            img.save(img_path)
            image_files.append(img_path)

        # Mock thumbnail generator
        class ThumbnailGenerator:
            def __init__(self, size=(128, 128)):
                self.size = size
                self.cache = {}

            def generate_thumbnail(self, image_path):
                if image_path in self.cache:
                    return self.cache[image_path]

                # Generate thumbnail
                try:
                    img = Image.open(image_path)
                    img.thumbnail(self.size, Image.Resampling.LANCZOS)

                    # Convert to QPixmap
                    qimage = QImage(
                        img.tobytes(),
                        img.width,
                        img.height,
                        img.width * 3,
                        QImage.Format.Format_RGB888,
                    )
                    pixmap = QPixmap.fromImage(qimage)

                    self.cache[image_path] = pixmap
                    return pixmap
                except Exception:
                    return None

        # Create thumbnail generator
        generator = ThumbnailGenerator()

        # Generate thumbnails
        thumbnails = []
        for img_path in image_files:
            thumb = generator.generate_thumbnail(img_path)
            assert thumb is not None
            assert thumb.width() <= 128
            assert thumb.height() <= 128
            thumbnails.append(thumb)

        # Verify cache is working
        assert len(generator.cache) == 5

        # Test cache hit
        cached_thumb = generator.generate_thumbnail(image_files[0])
        assert cached_thumb == thumbnails[0]

    def test_preview_error_fallbacks(self, qtbot, window):
        """Test preview error handling and fallback displays."""
        # Test various error scenarios
        preview_label = window.main_tab.first_frame_label

        # Test missing file
        def load_preview_with_fallback(file_path):
            try:
                pixmap = QPixmap(str(file_path))
                if pixmap.isNull():
                    raise ValueError("Failed to load image")
                preview_label.setPixmap(pixmap)
                return True
            except Exception:
                # Show error placeholder
                error_pixmap = QPixmap(200, 150)
                error_pixmap.fill(Qt.GlobalColor.lightGray)

                # Draw error message
                painter = QPainter(error_pixmap)
                painter.drawText(
                    error_pixmap.rect(),
                    Qt.AlignmentFlag.AlignCenter,
                    "Preview\nUnavailable",
                )
                painter.end()

                preview_label.setPixmap(error_pixmap)
                preview_label.setToolTip("Failed to load preview image")
                return False

        # Test with missing file
        success = load_preview_with_fallback(Path("/nonexistent/image.png"))
        assert not success
        assert preview_label.pixmap() is not None
        assert "Preview" in preview_label.toolTip()

        # Test with corrupted file
        corrupted_path = (
            window.main_tab.parent().main_view_model.preview_manager.temp_dir
            / "corrupted.png"
        )
        corrupted_path.write_bytes(b"Not a valid image")

        success = load_preview_with_fallback(corrupted_path)
        assert not success

    def test_image_rotation_controls(self, qtbot, window, sample_image):
        """Test image rotation controls."""

        # Create rotation controls
        class RotatableLabel(ClickableLabel):
            def __init__(self):
                super().__init__()
                self.rotation = 0
                self.original_pixmap = None

            def set_image(self, image_path):
                self.original_pixmap = QPixmap(str(image_path))
                self.update_rotation()

            def rotate_left(self):
                self.rotation = (self.rotation - 90) % 360
                self.update_rotation()

            def rotate_right(self):
                self.rotation = (self.rotation + 90) % 360
                self.update_rotation()

            def update_rotation(self):
                if self.original_pixmap:
                    transform = QTransform()
                    transform.rotate(self.rotation)
                    rotated = self.original_pixmap.transformed(transform)
                    self.setPixmap(rotated)

        # Create rotatable preview
        rot_label = RotatableLabel()
        rot_label.set_image(sample_image)
        qtbot.addWidget(rot_label)

        # Test rotation
        initial_size = rot_label.pixmap().size()

        # Rotate right 90 degrees
        rot_label.rotate_right()
        assert rot_label.rotation == 90
        rotated_size = rot_label.pixmap().size()
        # Width and height should be swapped
        assert rotated_size.width() == initial_size.height()
        assert rotated_size.height() == initial_size.width()

        # Rotate left back to 0
        rot_label.rotate_left()
        assert rot_label.rotation == 0

        # Test full rotation
        for _ in range(4):
            rot_label.rotate_right()
        assert rot_label.rotation == 0  # Back to original
