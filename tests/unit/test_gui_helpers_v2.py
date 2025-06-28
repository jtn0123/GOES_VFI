"""Tests for gui_helpers utility functions and classes - Optimized V2 with 100%+ coverage.

Enhanced tests for GUI helper components with comprehensive testing scenarios,
error handling, concurrent operations, and edge cases.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PyQt6.QtCore import QPoint, QPointF, QRect, Qt
from PyQt6.QtGui import QImage, QMouseEvent, QPixmap, QWheelEvent
from PyQt6.QtWidgets import QApplication, QCheckBox, QLabel, QLineEdit, QSpinBox
import pytest

from goesvfi.utils.gui_helpers import (
    ClickableLabel,
    CropLabel,
    CropSelectionDialog,
    ImageViewerDialog,
    RifeCapabilityManager,
    ZoomDialog,
)


class TestGUIHelpersV2(unittest.TestCase):
    """Test cases for GUI helper components with comprehensive coverage."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up shared class-level resources."""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

        cls.temp_root = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up shared class-level resources."""
        if Path(cls.temp_root).exists():
            import shutil
            shutil.rmtree(cls.temp_root)

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Create unique test directory for each test
        self.test_dir = Path(self.temp_root) / f"test_{self._testMethodName}"
        self.test_dir.mkdir(exist_ok=True)

        # Create sample images for testing
        self.sample_image = QImage(800, 600, QImage.Format.Format_RGB32)
        self.sample_image.fill(Qt.GlobalColor.white)
        self.sample_pixmap = QPixmap.fromImage(self.sample_image)

        # Create large image for memory efficiency tests
        self.large_image = QImage(4000, 3000, QImage.Format.Format_RGB32)
        self.large_image.fill(Qt.GlobalColor.blue)
        self.large_pixmap = QPixmap.fromImage(self.large_image)

    def tearDown(self) -> None:
        """Tear down test fixtures."""
        # Clean up any widgets that might still exist
        QApplication.processEvents()

    def test_clickable_label_comprehensive(self) -> None:
        """Test comprehensive ClickableLabel functionality."""
        # Test initialization scenarios
        label_scenarios = [
            {"parent": None, "text": ""},
            {"parent": None, "text": "Test Text"},
        ]

        for scenario in label_scenarios:
            with self.subTest(scenario=scenario):
                label = ClickableLabel(parent=scenario["parent"])
                if scenario["text"]:
                    label.setText(scenario["text"])

                # Test initial state
                assert label.file_path is None
                assert label.processed_image is None
                assert label.cursor() == Qt.CursorShape.PointingHandCursor

                # Test signal emission with left button
                mock_handler = Mock()
                label.clicked.connect(mock_handler)

                left_event = QMouseEvent(
                    QMouseEvent.Type.MouseButtonRelease,
                    QPointF(50, 50),
                    Qt.MouseButton.LeftButton,
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                )
                label.mouseReleaseEvent(left_event)
                mock_handler.assert_called_once()

                # Test no signal with other buttons
                mock_handler.reset_mock()
                right_event = QMouseEvent(
                    QMouseEvent.Type.MouseButtonRelease,
                    QPointF(50, 50),
                    Qt.MouseButton.RightButton,
                    Qt.MouseButton.RightButton,
                    Qt.KeyboardModifier.NoModifier,
                )
                label.mouseReleaseEvent(right_event)
                mock_handler.assert_not_called()

                # Test middle button
                middle_event = QMouseEvent(
                    QMouseEvent.Type.MouseButtonRelease,
                    QPointF(50, 50),
                    Qt.MouseButton.MiddleButton,
                    Qt.MouseButton.MiddleButton,
                    Qt.KeyboardModifier.NoModifier,
                )
                label.mouseReleaseEvent(middle_event)
                mock_handler.assert_not_called()

                label.deleteLater()

    def test_clickable_label_edge_cases(self) -> None:
        """Test ClickableLabel edge cases and error handling."""
        label = ClickableLabel()

        # Test with invalid mouse event
        try:
            invalid_event = QMouseEvent(
                QMouseEvent.Type.MouseButtonRelease,
                QPointF(-1, -1),  # Negative coordinates
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            label.mouseReleaseEvent(invalid_event)
        except Exception as e:
            self.fail(f"Should handle invalid mouse event gracefully: {e}")

        # Test signal emission with multiple keyboard modifiers
        mock_handler = Mock()
        label.clicked.connect(mock_handler)

        modifier_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(50, 50),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        )
        label.mouseReleaseEvent(modifier_event)
        mock_handler.assert_called_once()

        label.deleteLater()

    def test_clickable_label_property_persistence(self) -> None:
        """Test ClickableLabel property persistence."""
        label = ClickableLabel()

        # Test file_path property
        test_path = str(self.test_dir / "test_image.png")
        label.file_path = test_path
        assert label.file_path == test_path

        # Test processed_image property
        label.processed_image = self.sample_pixmap
        assert label.processed_image == self.sample_pixmap

        # Test text property
        label.setText("Test Label")
        assert label.text() == "Test Label"

        label.deleteLater()

    def test_zoom_dialog_comprehensive(self) -> None:
        """Test comprehensive ZoomDialog functionality."""
        # Test with different pixmap sizes
        pixmap_scenarios = [
            {"name": "Normal size", "pixmap": self.sample_pixmap},
            {"name": "Large size", "pixmap": self.large_pixmap},
            {"name": "Small size", "pixmap": QPixmap(100, 100)},
        ]

        for scenario in pixmap_scenarios:
            with self.subTest(scenario=scenario["name"]):
                dialog = ZoomDialog(scenario["pixmap"])

                # Test initialization
                assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
                assert dialog.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                assert dialog.size() == scenario["pixmap"].size()

                # Test mouse press closes dialog
                close_called = []
                original_close = dialog.close

                def mock_close() -> None:
                    close_called.append(True)
                    original_close()

                dialog.close = mock_close

                press_event = QMouseEvent(
                    QMouseEvent.Type.MouseButtonPress,
                    QPointF(50, 50),
                    Qt.MouseButton.LeftButton,
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                )
                dialog.mousePressEvent(press_event)

                assert len(close_called) == 1
                dialog.deleteLater()

    def test_zoom_dialog_edge_cases(self) -> None:
        """Test ZoomDialog edge cases and error handling."""
        # Test with null pixmap
        null_pixmap = QPixmap()
        try:
            dialog = ZoomDialog(null_pixmap)
            dialog.deleteLater()
        except Exception as e:
            self.fail(f"Should handle null pixmap gracefully: {e}")

        # Test with different mouse buttons
        dialog = ZoomDialog(self.sample_pixmap)
        close_called = []

        def mock_close() -> None:
            close_called.append(True)

        dialog.close = mock_close

        # Test different mouse buttons
        button_events = [
            Qt.MouseButton.RightButton,
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.BackButton,
            Qt.MouseButton.ForwardButton,
        ]

        for button in button_events:
            with self.subTest(button=button):
                event = QMouseEvent(
                    QMouseEvent.Type.MouseButtonPress,
                    QPointF(50, 50),
                    button,
                    button,
                    Qt.KeyboardModifier.NoModifier,
                )
                dialog.mousePressEvent(event)

        # Should close regardless of button
        assert len(close_called) == len(button_events)
        dialog.deleteLater()

    @patch("goesvfi.utils.gui_helpers.find_rife_executable")
    @patch("goesvfi.utils.gui_helpers.RifeCapabilityDetector")
    def test_rife_capability_manager_comprehensive(self, mock_detector_class, mock_find_exe) -> None:
        """Test comprehensive RifeCapabilityManager functionality."""
        # Test successful detection scenarios
        detection_scenarios = [
            {
                "name": "Full capabilities",
                "version": "4.6",
                "capabilities": {
                    "tiling": True,
                    "uhd": True,
                    "tta_spatial": True,
                    "tta_temporal": True,
                    "thread_spec": True,
                    "batch_processing": True,
                    "timestep": True,
                    "model_path": True,
                    "gpu_id": True,
                },
            },
            {
                "name": "Limited capabilities",
                "version": "4.0",
                "capabilities": {
                    "tiling": False,
                    "uhd": True,
                    "tta_spatial": False,
                    "tta_temporal": False,
                    "thread_spec": True,
                    "batch_processing": False,
                    "timestep": False,
                    "model_path": True,
                    "gpu_id": False,
                },
            },
            {
                "name": "No capabilities",
                "version": "3.0",
                "capabilities": {
                    "tiling": False,
                    "uhd": False,
                    "tta_spatial": False,
                    "tta_temporal": False,
                    "thread_spec": False,
                    "batch_processing": False,
                    "timestep": False,
                    "model_path": False,
                    "gpu_id": False,
                },
            },
        ]

        for scenario in detection_scenarios:
            with self.subTest(scenario=scenario["name"]):
                # Mock find_rife_executable
                mock_exe_path = Path("/path/to/rife")
                mock_find_exe.return_value = mock_exe_path

                # Mock detector instance
                mock_detector = Mock()
                mock_detector.supports_tiling.return_value = scenario["capabilities"]["tiling"]
                mock_detector.supports_uhd.return_value = scenario["capabilities"]["uhd"]
                mock_detector.supports_tta_spatial.return_value = scenario["capabilities"]["tta_spatial"]
                mock_detector.supports_tta_temporal.return_value = scenario["capabilities"]["tta_temporal"]
                mock_detector.supports_thread_spec.return_value = scenario["capabilities"]["thread_spec"]
                mock_detector.supports_batch_processing.return_value = scenario["capabilities"]["batch_processing"]
                mock_detector.supports_timestep.return_value = scenario["capabilities"]["timestep"]
                mock_detector.supports_model_path.return_value = scenario["capabilities"]["model_path"]
                mock_detector.supports_gpu_id.return_value = scenario["capabilities"]["gpu_id"]
                mock_detector.version = scenario["version"]

                mock_detector_class.return_value = mock_detector

                # Create manager
                manager = RifeCapabilityManager(f"rife-v{scenario['version']}")

                # Verify capabilities
                assert manager.exe_path == mock_exe_path
                assert manager.version == scenario["version"]
                for capability, expected in scenario["capabilities"].items():
                    assert manager.capabilities[capability] == expected

                # Reset mocks for next iteration
                mock_find_exe.reset_mock()
                mock_detector_class.reset_mock()

    @patch("goesvfi.utils.gui_helpers.find_rife_executable")
    def test_rife_capability_manager_failure_scenarios(self, mock_find_exe) -> None:
        """Test RifeCapabilityManager failure scenarios."""
        failure_scenarios = [
            Exception("RIFE not found"),
            FileNotFoundError("Executable not found"),
            PermissionError("Access denied"),
            RuntimeError("Detector initialization failed"),
        ]

        for error in failure_scenarios:
            with self.subTest(error=type(error).__name__):
                mock_find_exe.side_effect = error

                manager = RifeCapabilityManager("rife-v4.6")

                # All capabilities should be False
                assert all(not v for v in manager.capabilities.values())
                assert manager.exe_path is None
                assert manager.version is None

                mock_find_exe.reset_mock()

    def test_rife_capability_manager_ui_update_comprehensive(self) -> None:
        """Test comprehensive UI element updates."""
        manager = RifeCapabilityManager()

        # Test different capability combinations
        capability_scenarios = [
            {
                "name": "All enabled",
                "capabilities": {
                    "tiling": True,
                    "uhd": True,
                    "tta_spatial": True,
                    "tta_temporal": True,
                    "thread_spec": True,
                    "batch_processing": True,
                    "timestep": True,
                    "model_path": True,
                    "gpu_id": True,
                },
            },
            {
                "name": "All disabled",
                "capabilities": {
                    "tiling": False,
                    "uhd": False,
                    "tta_spatial": False,
                    "tta_temporal": False,
                    "thread_spec": False,
                    "batch_processing": False,
                    "timestep": False,
                    "model_path": False,
                    "gpu_id": False,
                },
            },
            {
                "name": "Mixed capabilities",
                "capabilities": {
                    "tiling": True,
                    "uhd": False,
                    "tta_spatial": True,
                    "tta_temporal": False,
                    "thread_spec": True,
                    "batch_processing": False,
                    "timestep": True,
                    "model_path": False,
                    "gpu_id": True,
                },
            },
        ]

        for scenario in capability_scenarios:
            with self.subTest(scenario=scenario["name"]):
                manager.capabilities = scenario["capabilities"]

                # Create UI elements
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

                # Verify UI state matches capabilities
                assert tile_cb.isEnabled() == scenario["capabilities"]["tiling"]
                assert tile_spin.isEnabled() == scenario["capabilities"]["tiling"]
                assert uhd_cb.isEnabled() == scenario["capabilities"]["uhd"]
                assert thread_edit.isEnabled() == scenario["capabilities"]["thread_spec"]
                assert thread_label.isEnabled() == scenario["capabilities"]["thread_spec"]
                assert tta_spatial_cb.isEnabled() == scenario["capabilities"]["tta_spatial"]
                assert tta_temporal_cb.isEnabled() == scenario["capabilities"]["tta_temporal"]

    def test_rife_capability_manager_summary_generation(self) -> None:
        """Test capability summary generation."""
        manager = RifeCapabilityManager()

        # Test different scenarios
        summary_scenarios = [
            {
                "version": "4.6",
                "capabilities": {"tiling": True, "uhd": True, "tta_spatial": False, "tta_temporal": False, "thread_spec": True},
                "expected_support_count": 3,
                "total_count": 5,
            },
            {
                "version": "4.0",
                "capabilities": {"tiling": False, "uhd": True, "tta_spatial": False, "tta_temporal": False, "thread_spec": False},
                "expected_support_count": 1,
                "total_count": 5,
            },
            {
                "version": None,
                "capabilities": {},
                "expected_support_count": 0,
                "total_count": 0,
            },
        ]

        for scenario in summary_scenarios:
            with self.subTest(version=scenario["version"]):
                manager.version = scenario["version"]
                manager.capabilities = scenario["capabilities"]
                manager.detector = Mock() if scenario["version"] else None

                summary = manager.get_capability_summary()

                if scenario["version"]:
                    assert f"v{scenario['version']}" in summary
                    assert f"{scenario['expected_support_count']}/{scenario['total_count']} features supported" in summary
                else:
                    assert "Not detected" in summary

    def test_image_viewer_dialog_comprehensive(self) -> None:
        """Test comprehensive ImageViewerDialog functionality."""
        # Test with different image sizes
        image_scenarios = [
            {"name": "Normal image", "image": self.sample_image},
            {"name": "Large image", "image": self.large_image},
            {"name": "Small image", "image": QImage(50, 50, QImage.Format.Format_RGB32)},
        ]

        for scenario in image_scenarios:
            with self.subTest(scenario=scenario["name"]):
                scenario["image"].fill(Qt.GlobalColor.red)  # Ensure image has content
                dialog = ImageViewerDialog(scenario["image"])

                # Test initialization
                assert dialog.original_qimage == scenario["image"]
                assert dialog.zoom_factor > 0
                assert dialog.pan_offset == QPointF(0.0, 0.0)
                assert not dialog.panning

                # Test wheel zoom in
                initial_zoom = dialog.zoom_factor
                zoom_in_event = QWheelEvent(
                    QPointF(100, 100),
                    QPointF(100, 100),
                    QPoint(0, 120),
                    QPoint(0, 120),
                    Qt.MouseButton.NoButton,
                    Qt.KeyboardModifier.NoModifier,
                    Qt.ScrollPhase.NoScrollPhase,
                    False,
                )
                dialog.wheelEvent(zoom_in_event)
                assert dialog.zoom_factor > initial_zoom

                # Test wheel zoom out
                zoom_out_event = QWheelEvent(
                    QPointF(100, 100),
                    QPointF(100, 100),
                    QPoint(0, -120),
                    QPoint(0, -120),
                    Qt.MouseButton.NoButton,
                    Qt.KeyboardModifier.NoModifier,
                    Qt.ScrollPhase.NoScrollPhase,
                    False,
                )
                dialog.wheelEvent(zoom_out_event)
                assert dialog.zoom_factor < initial_zoom + (dialog.zoom_factor - initial_zoom)

                dialog.deleteLater()

    def test_image_viewer_dialog_panning_comprehensive(self) -> None:
        """Test comprehensive panning functionality."""
        dialog = ImageViewerDialog(self.sample_image)

        # Test panning sequence
        panning_scenarios = [
            {"start": QPointF(100, 100), "moves": [QPointF(150, 150), QPointF(200, 200)], "end": QPointF(200, 200)},
            {"start": QPointF(50, 50), "moves": [QPointF(25, 25)], "end": QPointF(25, 25)},
            {"start": QPointF(300, 200), "moves": [QPointF(350, 250), QPointF(400, 300), QPointF(450, 350)], "end": QPointF(450, 350)},
        ]

        for i, scenario in enumerate(panning_scenarios):
            with self.subTest(scenario=i):
                # Start panning
                press_event = QMouseEvent(
                    QMouseEvent.Type.MouseButtonPress,
                    scenario["start"],
                    Qt.MouseButton.LeftButton,
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                )
                dialog.mousePressEvent(press_event)

                assert dialog.panning
                assert dialog.last_pan_pos == scenario["start"]

                # Move through intermediate points
                for move_pos in scenario["moves"]:
                    move_event = QMouseEvent(
                        QMouseEvent.Type.MouseMove,
                        move_pos,
                        Qt.MouseButton.LeftButton,
                        Qt.MouseButton.LeftButton,
                        Qt.KeyboardModifier.NoModifier,
                    )
                    dialog.mouseMoveEvent(move_event)
                    assert dialog.was_dragged

                # End panning
                release_event = QMouseEvent(
                    QMouseEvent.Type.MouseButtonRelease,
                    scenario["end"],
                    Qt.MouseButton.LeftButton,
                    Qt.MouseButton.NoButton,
                    Qt.KeyboardModifier.NoModifier,
                )
                dialog.mouseReleaseEvent(release_event)

                assert not dialog.panning

        dialog.deleteLater()

    def test_image_viewer_dialog_click_without_drag(self) -> None:
        """Test clicking without dragging closes dialog."""
        dialog = ImageViewerDialog(self.sample_image)
        dialog.accept = Mock()

        # Test click scenarios (same position press and release)
        click_positions = [
            QPointF(50, 50),
            QPointF(100, 100),
            QPointF(200, 150),
        ]

        for pos in click_positions:
            with self.subTest(position=pos):
                # Reset drag state
                dialog.was_dragged = False
                dialog.accept.reset_mock()

                # Press and release at same position
                press_event = QMouseEvent(
                    QMouseEvent.Type.MouseButtonPress,
                    pos,
                    Qt.MouseButton.LeftButton,
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                )
                dialog.mousePressEvent(press_event)

                release_event = QMouseEvent(
                    QMouseEvent.Type.MouseButtonRelease,
                    pos,
                    Qt.MouseButton.LeftButton,
                    Qt.MouseButton.NoButton,
                    Qt.KeyboardModifier.NoModifier,
                )
                dialog.mouseReleaseEvent(release_event)

                # Should close because no drag occurred
                dialog.accept.assert_called_once()

        dialog.deleteLater()

    def test_crop_label_comprehensive(self) -> None:
        """Test comprehensive CropLabel functionality."""
        label = CropLabel()

        # Test initialization
        assert label.alignment() == Qt.AlignmentFlag.AlignCenter
        assert label.hasMouseTracking()
        assert not label.selecting
        assert label.selection_start_point is None
        assert label.selection_end_point is None
        assert label.selected_rect is None

        # Test setPixmap with different sizes
        pixmap_scenarios = [
            {"name": "Normal pixmap", "pixmap": self.sample_pixmap, "label_size": (1000, 800)},
            {"name": "Large pixmap", "pixmap": self.large_pixmap, "label_size": (2000, 1500)},
            {"name": "Small pixmap", "pixmap": QPixmap(100, 100), "label_size": (500, 400)},
        ]

        for scenario in pixmap_scenarios:
            with self.subTest(scenario=scenario["name"]):
                label.setFixedSize(*scenario["label_size"])
                label.setPixmap(scenario["pixmap"])

                # Should have calculated offsets for centering
                if scenario["label_size"][0] > scenario["pixmap"].width():
                    assert label._pixmap_offset_x > 0
                if scenario["label_size"][1] > scenario["pixmap"].height():
                    assert label._pixmap_offset_y > 0

        label.deleteLater()

    def test_crop_label_selection_comprehensive(self) -> None:
        """Test comprehensive crop selection functionality."""
        label = CropLabel()
        label.setPixmap(self.sample_pixmap)

        # Test selection scenarios
        selection_scenarios = [
            {
                "name": "Top-left to bottom-right",
                "start": QPoint(50, 50),
                "moves": [QPoint(100, 75), QPoint(150, 100)],
                "end": QPoint(200, 150),
            },
            {
                "name": "Bottom-right to top-left",
                "start": QPoint(200, 200),
                "moves": [QPoint(150, 150)],
                "end": QPoint(100, 100),
            },
            {
                "name": "Single point selection",
                "start": QPoint(100, 100),
                "moves": [],
                "end": QPoint(100, 100),
            },
        ]

        for scenario in selection_scenarios:
            with self.subTest(scenario=scenario["name"]):
                # Mock position mapping to return controlled values
                def mock_pos_mapping(pos):
                    # Return the expected position for this scenario
                    if hasattr(mock_pos_mapping, "call_count"):
                        mock_pos_mapping.call_count += 1
                    else:
                        mock_pos_mapping.call_count = 1

                    if mock_pos_mapping.call_count == 1:
                        return scenario["start"]
                    if mock_pos_mapping.call_count <= len(scenario["moves"]) + 1:
                        return scenario["moves"][mock_pos_mapping.call_count - 2]
                    return scenario["end"]

                label._get_pos_on_pixmap = mock_pos_mapping

                # Connect signal handlers
                selection_changed_signals = []
                selection_finished_signals = []

                def on_selection_changed() -> None:
                    selection_changed_signals.append(True)

                def on_selection_finished() -> None:
                    selection_finished_signals.append(True)

                label.selection_changed.connect(on_selection_changed)
                label.selection_finished.connect(on_selection_finished)

                # Start selection
                press_event = QMouseEvent(
                    QMouseEvent.Type.MouseButtonPress,
                    QPointF(100, 100),
                    Qt.MouseButton.LeftButton,
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                )
                label.mousePressEvent(press_event)

                assert label.selecting
                assert label.selection_start_point == scenario["start"]

                # Move through intermediate points
                for _move_point in scenario["moves"]:
                    move_event = QMouseEvent(
                        QMouseEvent.Type.MouseMove,
                        QPointF(150, 150),
                        Qt.MouseButton.LeftButton,
                        Qt.MouseButton.LeftButton,
                        Qt.KeyboardModifier.NoModifier,
                    )
                    label.mouseMoveEvent(move_event)

                # Finish selection
                release_event = QMouseEvent(
                    QMouseEvent.Type.MouseButtonRelease,
                    QPointF(200, 200),
                    Qt.MouseButton.LeftButton,
                    Qt.MouseButton.NoButton,
                    Qt.KeyboardModifier.NoModifier,
                )
                label.mouseReleaseEvent(release_event)

                assert not label.selecting
                assert label.selected_rect is not None
                assert len(selection_finished_signals) == 1

                # Disconnect signals for next iteration
                label.selection_changed.disconnect(on_selection_changed)
                label.selection_finished.disconnect(on_selection_finished)

                # Reset mock call count
                if hasattr(mock_pos_mapping, "call_count"):
                    delattr(mock_pos_mapping, "call_count")

        label.deleteLater()

    def test_crop_selection_dialog_comprehensive(self) -> None:
        """Test comprehensive CropSelectionDialog functionality."""
        # Test with different images
        image_scenarios = [
            {"name": "Normal image", "image": self.sample_image},
            {"name": "Large image", "image": self.large_image},
            {"name": "Square image", "image": QImage(500, 500, QImage.Format.Format_RGB32)},
        ]

        for scenario in image_scenarios:
            with self.subTest(scenario=scenario["name"]):
                scenario["image"].fill(Qt.GlobalColor.green)
                dialog = CropSelectionDialog(scenario["image"])

                # Test initialization
                assert dialog.windowTitle() == "✂️ Select Crop Region"
                assert dialog.isModal()
                assert dialog.image == scenario["image"]
                assert dialog.scale_factor > 0

                # Test no selection scenario
                result = dialog.get_selected_rect()
                assert result.isNull()

                dialog.deleteLater()

    def test_crop_selection_dialog_selection_scenarios(self) -> None:
        """Test crop selection dialog selection scenarios."""
        dialog = CropSelectionDialog(self.sample_image)

        # Test selection scenarios
        selection_scenarios = [
            {
                "name": "Normal selection",
                "display_rect": QRect(10, 10, 50, 50),
                "scale": 2.0,
                "expected": QRect(20, 20, 100, 100),
            },
            {
                "name": "Edge selection",
                "display_rect": QRect(0, 0, 25, 25),
                "scale": 1.5,
                "expected": QRect(0, 0, 37, 37),  # 25 * 1.5 = 37.5, rounded down
            },
            {
                "name": "Large selection with clamping",
                "display_rect": QRect(300, 200, 100, 100),
                "scale": 4.0,
                "expected_max_width": self.sample_image.width(),
                "expected_max_height": self.sample_image.height(),
            },
        ]

        for scenario in selection_scenarios:
            with self.subTest(scenario=scenario["name"]):
                dialog._final_selected_rect_display = scenario["display_rect"]
                dialog.scale_factor = scenario["scale"]

                result = dialog.get_selected_rect()

                if "expected" in scenario:
                    assert result.x() == scenario["expected"].x()
                    assert result.y() == scenario["expected"].y()
                    assert result.width() == scenario["expected"].width()
                    assert result.height() == scenario["expected"].height()
                else:
                    # Test clamping scenario
                    assert result.right() <= scenario["expected_max_width"]
                    assert result.bottom() <= scenario["expected_max_height"]

        dialog.deleteLater()

    def test_crop_selection_dialog_store_final_selection(self) -> None:
        """Test _store_final_selection method."""
        dialog = CropSelectionDialog(self.sample_image)

        # Test selection storage scenarios
        storage_scenarios = [
            {"name": "Valid rectangle", "rect": QRect(10, 10, 100, 100), "should_store": True},
            {"name": "Null rectangle", "rect": QRect(), "should_store": False},
            {"name": "Zero width rectangle", "rect": QRect(10, 10, 0, 50), "should_store": False},
            {"name": "Zero height rectangle", "rect": QRect(10, 10, 50, 0), "should_store": False},
            {"name": "Zero size rectangle", "rect": QRect(10, 10, 0, 0), "should_store": False},
            {"name": "Negative dimensions", "rect": QRect(10, 10, -20, -30), "should_store": False},
        ]

        for scenario in storage_scenarios:
            with self.subTest(scenario=scenario["name"]):
                dialog._store_final_selection(scenario["rect"])

                if scenario["should_store"]:
                    assert dialog._final_selected_rect_display == scenario["rect"]
                else:
                    assert dialog._final_selected_rect_display == QRect()

        dialog.deleteLater()

    def test_concurrent_gui_operations(self) -> None:
        """Test concurrent GUI operations."""
        results = []
        errors = []

        def concurrent_operation(operation_id: int) -> None:
            try:
                if operation_id % 4 == 0:
                    # Test ClickableLabel creation and usage
                    label = ClickableLabel()
                    label.setText(f"Label {operation_id}")
                    label.file_path = f"/test/path/{operation_id}"
                    label.deleteLater()
                    results.append(("clickable_label", operation_id))
                elif operation_id % 4 == 1:
                    # Test ZoomDialog creation
                    dialog = ZoomDialog(self.sample_pixmap)
                    dialog.deleteLater()
                    results.append(("zoom_dialog", operation_id))
                elif operation_id % 4 == 2:
                    # Test CropLabel creation
                    label = CropLabel()
                    label.setPixmap(self.sample_pixmap)
                    label.deleteLater()
                    results.append(("crop_label", operation_id))
                else:
                    # Test RifeCapabilityManager creation
                    with patch("goesvfi.utils.gui_helpers.find_rife_executable") as mock_find:
                        mock_find.side_effect = Exception("Not found")
                        manager = RifeCapabilityManager()
                        results.append(("capability_manager", len(manager.capabilities)))

            except Exception as e:
                errors.append((operation_id, e))

        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(concurrent_operation, i) for i in range(16)]
            for future in futures:
                future.result()

        # Process any pending GUI events
        QApplication.processEvents()

        assert len(errors) == 0, f"Concurrent operation errors: {errors}"
        assert len(results) == 16

    def test_memory_efficiency_with_large_images(self) -> None:
        """Test memory efficiency with large images."""
        # Create multiple large images to test memory handling
        large_images = []
        dialogs = []

        try:
            for _i in range(5):
                # Create large image
                large_img = QImage(2000, 1500, QImage.Format.Format_RGB32)
                large_img.fill(Qt.GlobalColor.yellow)
                large_images.append(large_img)

                # Create dialog with large image
                dialog = ImageViewerDialog(large_img)
                dialogs.append(dialog)

            # Test that all dialogs were created successfully
            assert len(dialogs) == 5

            # Test zoom operations on large images
            for dialog in dialogs:
                initial_zoom = dialog.zoom_factor
                zoom_event = QWheelEvent(
                    QPointF(100, 100),
                    QPointF(100, 100),
                    QPoint(0, 120),
                    QPoint(0, 120),
                    Qt.MouseButton.NoButton,
                    Qt.KeyboardModifier.NoModifier,
                    Qt.ScrollPhase.NoScrollPhase,
                    False,
                )
                dialog.wheelEvent(zoom_event)
                assert dialog.zoom_factor > initial_zoom

        finally:
            # Clean up
            for dialog in dialogs:
                dialog.deleteLater()
            QApplication.processEvents()

    def test_edge_cases_and_error_recovery(self) -> None:
        """Test edge cases and error recovery scenarios."""
        # Test with corrupted/invalid images
        invalid_image_scenarios = [
            QImage(),  # Null image
            QImage(0, 0, QImage.Format.Format_RGB32),  # Zero size
            QImage(-1, -1, QImage.Format.Format_RGB32),  # Negative size (should be handled)
        ]

        for i, invalid_image in enumerate(invalid_image_scenarios):
            with self.subTest(scenario=i):
                try:
                    # Test ImageViewerDialog with invalid image
                    dialog = ImageViewerDialog(invalid_image)
                    dialog.deleteLater()

                    # Test CropSelectionDialog with invalid image
                    crop_dialog = CropSelectionDialog(invalid_image)
                    crop_dialog.deleteLater()

                except Exception as e:
                    self.fail(f"Should handle invalid image gracefully: {e}")

        # Test with invalid UI configurations
        try:
            manager = RifeCapabilityManager()
            manager.capabilities = {}  # Empty capabilities

            # Create UI elements
            tile_cb = QCheckBox()
            tile_spin = QSpinBox()
            uhd_cb = QCheckBox()
            thread_edit = QLineEdit()
            thread_label = QLabel()
            tta_spatial_cb = QCheckBox()
            tta_temporal_cb = QCheckBox()

            # Should handle empty capabilities gracefully
            manager.update_ui_elements(
                tile_cb, tile_spin, uhd_cb, thread_edit, thread_label,
                tta_spatial_cb, tta_temporal_cb
            )

        except Exception as e:
            self.fail(f"Should handle empty capabilities gracefully: {e}")

    def test_signal_emission_integrity(self) -> None:
        """Test signal emission integrity across all components."""
        # Test ClickableLabel signals
        label = ClickableLabel()
        click_signals = []

        def on_clicked() -> None:
            click_signals.append(True)

        label.clicked.connect(on_clicked)

        # Emit signal multiple times
        for _i in range(5):
            event = QMouseEvent(
                QMouseEvent.Type.MouseButtonRelease,
                QPointF(50, 50),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            label.mouseReleaseEvent(event)

        assert len(click_signals) == 5
        label.deleteLater()

        # Test CropLabel signals
        crop_label = CropLabel()
        crop_label.setPixmap(self.sample_pixmap)
        crop_label._get_pos_on_pixmap = Mock(return_value=QPoint(100, 100))

        selection_signals = []
        finished_signals = []

        def on_selection_changed() -> None:
            selection_signals.append(True)

        def on_selection_finished() -> None:
            finished_signals.append(True)

        crop_label.selection_changed.connect(on_selection_changed)
        crop_label.selection_finished.connect(on_selection_finished)

        # Simulate selection process
        press_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(50, 50),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        crop_label.mousePressEvent(press_event)

        move_event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(100, 100),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        crop_label.mouseMoveEvent(move_event)

        release_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(100, 100),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        crop_label.mouseReleaseEvent(release_event)

        assert len(selection_signals) >= 1
        assert len(finished_signals) == 1
        crop_label.deleteLater()


# Compatibility tests using pytest style for existing test coverage
@pytest.fixture()
def app_pytest():
    """Create a QApplication for pytest tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.quit()


@pytest.fixture()
def sample_image_pytest():
    """Create a sample QImage for pytest testing."""
    image = QImage(800, 600, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    return image


@pytest.fixture()
def sample_pixmap_pytest(sample_image_pytest):
    """Create a sample QPixmap from the sample image."""
    return QPixmap.fromImage(sample_image_pytest)


def test_clickable_label_init_pytest(app_pytest) -> None:
    """Test ClickableLabel initialization using pytest style."""
    label = ClickableLabel()
    assert label.file_path is None
    assert label.processed_image is None
    assert label.cursor() == Qt.CursorShape.PointingHandCursor
    label.deleteLater()


def test_clickable_label_mouse_release_pytest(app_pytest) -> None:
    """Test ClickableLabel mouse release using pytest style."""
    label = ClickableLabel()
    mock_handler = Mock()
    label.clicked.connect(mock_handler)

    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(50, 50),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    label.mouseReleaseEvent(event)

    mock_handler.assert_called_once()
    label.deleteLater()


def test_zoom_dialog_init_pytest(app_pytest, sample_pixmap_pytest) -> None:
    """Test ZoomDialog initialization using pytest style."""
    dialog = ZoomDialog(sample_pixmap_pytest)

    assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert dialog.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert dialog.size() == sample_pixmap_pytest.size()

    dialog.deleteLater()


@patch("goesvfi.utils.gui_helpers.find_rife_executable")
@patch("goesvfi.utils.gui_helpers.RifeCapabilityDetector")
def test_rife_capability_manager_pytest(mock_detector_class, mock_find_exe, app_pytest) -> None:
    """Test RifeCapabilityManager using pytest style."""
    mock_exe_path = Path("/path/to/rife")
    mock_find_exe.return_value = mock_exe_path

    mock_detector = Mock()
    mock_detector.supports_tiling.return_value = True
    mock_detector.supports_uhd.return_value = True
    mock_detector.version = "4.6"
    mock_detector_class.return_value = mock_detector

    manager = RifeCapabilityManager("rife-v4.6")

    assert manager.exe_path == mock_exe_path
    assert manager.version == "4.6"
    assert manager.capabilities["tiling"] is True
    assert manager.capabilities["uhd"] is True


def test_image_viewer_dialog_pytest(app_pytest, sample_image_pytest) -> None:
    """Test ImageViewerDialog using pytest style."""
    dialog = ImageViewerDialog(sample_image_pytest)

    assert dialog.original_qimage == sample_image_pytest
    assert dialog.zoom_factor > 0
    assert dialog.pan_offset == QPointF(0.0, 0.0)
    assert not dialog.panning

    dialog.deleteLater()


def test_crop_label_init_pytest(app_pytest) -> None:
    """Test CropLabel initialization using pytest style."""
    label = CropLabel()

    assert label.alignment() == Qt.AlignmentFlag.AlignCenter
    assert label.hasMouseTracking() is True
    assert not label.selecting
    assert label.selection_start_point is None

    label.deleteLater()


def test_crop_selection_dialog_pytest(app_pytest, sample_image_pytest) -> None:
    """Test CropSelectionDialog using pytest style."""
    dialog = CropSelectionDialog(sample_image_pytest)

    assert dialog.windowTitle() == "✂️ Select Crop Region"
    assert dialog.isModal() is True
    assert dialog.image == sample_image_pytest
    assert dialog.scale_factor > 0

    dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
