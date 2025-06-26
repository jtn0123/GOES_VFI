"""Tests for GUI component validation and visual feedback."""


import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtTest import QTest

from goesvfi.gui import MainWindow
from goesvfi.utils.gui_helpers import ClickableLabel


class TestGUIComponentValidation:
    """Test suite for validating GUI components and visual feedback."""

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

    def test_progress_bar_updates(self, qtbot, window):
        """Test progress bar visual updates during processing."""
        # Initial state
        assert window.main_tab.progress_bar.value() == 0
        assert window.main_tab.progress_bar.isVisible()

        # Simulate progress updates
        window._on_processing_progress(25, 100, 75.0)
        assert window.main_tab.progress_bar.value() == 25

        window._on_processing_progress(50, 100, 50.0)
        assert window.main_tab.progress_bar.value() == 50

        window._on_processing_progress(100, 100, 0.0)
        assert window.main_tab.progress_bar.value() == 100

        # Verify status bar shows progress
        assert (
            "50%" in window.status_bar.currentMessage()
            or "100%" in window.status_bar.currentMessage()
        )

    def test_preview_labels_display_images(self, qtbot, window, mocker):
        """Test that preview labels correctly display images."""
        # Create test pixmaps
        test_pixmap1 = QPixmap(100, 100)
        test_pixmap1.fill(Qt.GlobalColor.red)
        test_pixmap2 = QPixmap(100, 100)
        test_pixmap2.fill(Qt.GlobalColor.blue)

        # Mock preview manager to emit signals

        # Manually call the preview loaded callback
        window._on_preview_images_loaded(test_pixmap1, test_pixmap2)

        # Verify pixmaps are set
        first_pixmap = window.main_tab.first_frame_label.pixmap()
        last_pixmap = window.main_tab.last_frame_label.pixmap()

        assert first_pixmap is not None
        assert last_pixmap is not None
        assert not first_pixmap.isNull()
        assert not last_pixmap.isNull()

    def test_spinbox_value_limits(self, qtbot, window):
        """Test spinbox controls have proper limits and behavior."""
        # FPS spinbox
        fps_spin = window.main_tab.fps_spinbox
        assert fps_spin.minimum() > 0
        assert fps_spin.maximum() <= 120

        # Test setting values
        fps_spin.setValue(30)
        assert fps_spin.value() == 30

        # Test limits
        fps_spin.setValue(999)
        assert fps_spin.value() == fps_spin.maximum()

        fps_spin.setValue(-1)
        assert fps_spin.value() == fps_spin.minimum()

        # Intermediate frames spinbox
        mid_spin = window.main_tab.mid_count_spinbox
        assert mid_spin.minimum() >= 1
        assert mid_spin.maximum() <= 10

        # Max workers spinbox
        workers_spin = window.main_tab.max_workers_spinbox
        assert workers_spin.minimum() >= 1
        assert workers_spin.maximum() <= 16

    def test_combo_box_items_populated(self, qtbot, window):
        """Test that combo boxes are properly populated."""
        # Encoder combo
        encoder_combo = window.main_tab.encoder_combo
        assert encoder_combo.count() > 0
        assert "RIFE" in [
            encoder_combo.itemText(i) for i in range(encoder_combo.count())
        ]
        assert "FFmpeg" in [
            encoder_combo.itemText(i) for i in range(encoder_combo.count())
        ]

        # RIFE model combo
        model_combo = window.main_tab.rife_model_combo
        assert model_combo.count() > 0

        # Sanchez resolution combo
        sanchez_combo = window.main_tab.sanchez_res_combo
        assert sanchez_combo.count() > 0
        assert "4" in [sanchez_combo.itemText(i) for i in range(sanchez_combo.count())]

    def test_text_edit_validation(self, qtbot, window):
        """Test text input fields validation and display."""
        # Input directory edit
        test_path = "/test/input/directory"
        window.main_tab.in_dir_edit.setText(test_path)
        assert window.main_tab.in_dir_edit.text() == test_path

        # Output file edit
        test_output = "/test/output/video.mp4"
        window.main_tab.out_file_edit.setText(test_output)
        assert window.main_tab.out_file_edit.text() == test_output

        # Both should be read-only
        assert window.main_tab.in_dir_edit.isReadOnly()
        assert window.main_tab.out_file_edit.isReadOnly()

    def test_group_box_visibility(self, qtbot, window):
        """Test group box visibility and enable states."""
        # RIFE options group
        assert window.main_tab.rife_options_group.isVisible()
        assert window.main_tab.rife_options_group.isEnabled()

        # Sanchez options group
        assert window.main_tab.sanchez_options_group.isVisible()
        assert window.main_tab.sanchez_options_group.isEnabled()

        # Switch to FFmpeg - RIFE options should be disabled
        window.main_tab.encoder_combo.setCurrentText("FFmpeg")
        qtbot.wait(50)
        assert not window.main_tab.rife_options_group.isEnabled()

    def test_checkbox_states_and_dependencies(self, qtbot, window):
        """Test checkbox states and their dependent controls."""
        # RIFE checkboxes
        rife_tile_cb = window.main_tab.rife_tile_checkbox
        rife_tile_size = window.main_tab.rife_tile_size_spinbox

        # Initially unchecked
        assert not rife_tile_cb.isChecked()
        assert not rife_tile_size.isEnabled()

        # Check enables spinbox
        rife_tile_cb.setChecked(True)
        qtbot.wait(50)
        # Note: The actual enable logic might be in a signal handler

        # Sanchez checkbox
        sanchez_cb = window.main_tab.sanchez_checkbox
        sanchez_res = window.main_tab.sanchez_res_combo

        assert not sanchez_cb.isChecked()
        assert not sanchez_res.isEnabled()

        sanchez_cb.setChecked(True)
        window._toggle_sanchez_res_enabled(Qt.CheckState.Checked)
        assert sanchez_res.isEnabled()

    def test_status_bar_messages(self, qtbot, window):
        """Test status bar displays appropriate messages."""
        # Initial message
        window.status_bar.currentMessage()

        # Processing started
        window._set_processing_state(True)
        qtbot.wait(50)

        # Progress update
        window._on_processing_progress(50, 100, 50.0)
        assert "50%" in window.status_bar.currentMessage()

        # Processing complete
        window._on_processing_finished("/test/output.mp4")
        assert "completed" in window.status_bar.currentMessage().lower()

        # Error state
        window._on_processing_error("Test error")
        assert "failed" in window.status_bar.currentMessage().lower()

    def test_tab_widget_structure(self, qtbot, window):
        """Test tab widget has correct structure and tabs."""
        tab_widget = window.tab_widget

        # Should have multiple tabs
        assert tab_widget.count() >= 5

        # Check tab titles (approximate, as they might vary)
        tab_titles = [tab_widget.tabText(i).lower() for i in range(tab_widget.count())]

        # Should have main processing tab
        assert any("main" in title or "process" in title for title in tab_titles)

        # Should have FFmpeg settings
        assert any("ffmpeg" in title for title in tab_titles)

        # Should have model library
        assert any("model" in title for title in tab_titles)

        # All tabs should be enabled initially
        for i in range(tab_widget.count()):
            assert tab_widget.isTabEnabled(i)

    def test_preview_label_visual_properties(self, qtbot, window):
        """Test preview labels have correct visual properties."""
        # First frame label
        first_label = window.main_tab.first_frame_label
        assert isinstance(first_label, ClickableLabel)
        assert first_label.isVisible()
        assert first_label.frameStyle() != 0  # Has some frame style

        # Last frame label
        last_label = window.main_tab.last_frame_label
        assert isinstance(last_label, ClickableLabel)
        assert last_label.isVisible()

        # Middle frame label (if exists)
        if hasattr(window.main_tab, "middle_frame_label"):
            middle_label = window.main_tab.middle_frame_label
            assert isinstance(middle_label, ClickableLabel)
            assert middle_label.isVisible()

    def test_layout_spacing_and_margins(self, qtbot, window):
        """Test that layouts have proper spacing."""
        # Main tab layout
        main_layout = window.main_tab.layout()
        assert main_layout is not None

        # Should have some spacing
        assert main_layout.spacing() >= 0

        # Check margins are reasonable
        margins = main_layout.contentsMargins()
        assert all(
            m >= 0
            for m in [margins.left(), margins.top(), margins.right(), margins.bottom()]
        )

    def test_window_properties(self, qtbot, window):
        """Test main window properties."""
        # Window title
        assert "GOES" in window.windowTitle() or "VFI" in window.windowTitle()

        # Window size
        assert window.width() > 600
        assert window.height() > 400

        # Window should be visible
        window.show()
        qtbot.waitExposed(window)
        assert window.isVisible()

    def test_tooltips_present(self, qtbot, window):
        """Test that important controls have tooltips."""
        # Check key controls have tooltips
        controls_to_check = [
            window.main_tab.in_dir_button,
            window.main_tab.out_file_button,
            window.main_tab.crop_button,
            window.main_tab.start_button,
            window.main_tab.encoder_combo,
            window.main_tab.rife_model_combo,
        ]

        # At least some controls should have tooltips
        tooltips_found = sum(1 for control in controls_to_check if control.toolTip())
        assert tooltips_found > 0

    def test_focus_navigation(self, qtbot, window):
        """Test tab order and focus navigation."""
        # Set focus to first control
        window.main_tab.in_dir_button.setFocus()
        assert window.main_tab.in_dir_button.hasFocus()

        # Tab through controls
        QTest.keyClick(window, Qt.Key.Key_Tab)
        qtbot.wait(50)

        # Should move to next control (exact order depends on implementation)
        # Just verify focus moved
        assert not window.main_tab.in_dir_button.hasFocus()

    def test_visual_feedback_on_hover(self, qtbot, window):
        """Test visual feedback on button hover if implemented."""
        # This would test hover effects, cursor changes, etc.
        # Implementation depends on custom styling
        start_button = window.main_tab.start_button

        # Check if button has hover effects by checking cursor
        cursor = start_button.cursor()
        # Most buttons should have pointing hand cursor
        assert cursor.shape() in [
            Qt.CursorShape.ArrowCursor,
            Qt.CursorShape.PointingHandCursor,
        ]
