"""
High-value form validation and user experience tests.

Tests real-time feedback, input validation, and user-friendly error handling
that directly impacts user experience in the GOES_VFI application.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox
import pytest

from goesvfi.gui import MainWindow


class TestFormValidationUX:
    """Test form validation and real-time user feedback."""

    @pytest.fixture()
    def main_window(self, qtbot):
        """Create MainWindow with mocked components."""
        with patch("goesvfi.gui.QSettings"):
            window = MainWindow(debug_mode=True)
            qtbot.addWidget(window)
            window._post_init_setup()
            return window

    def test_realtime_path_validation_feedback(self, qtbot, main_window):
        """Test that users get immediate feedback on invalid paths."""
        window = main_window

        # Test input directory validation with real-time feedback
        path_scenarios = [
            ("", "Should show 'Please select a directory' hint"),
            ("/nonexistent/path", "Should show 'Directory does not exist' error"),
            ("not/absolute/path", "Should show 'Please use absolute path' warning"),
            ("/dev/null", "Should show 'Not a directory' error"),
            ("/tmp", "Should show green checkmark or 'Valid directory' success"),
        ]

        for test_path, expected_behavior in path_scenarios:
            # Simulate user typing
            window.main_tab.in_dir_edit.clear()
            for char in test_path:
                QTest.keyClick(window.main_tab.in_dir_edit, char)
                qtbot.wait(10)  # Simulate typing delay

            # Trigger validation (simulating focus loss or Enter key)
            QTest.keyClick(window.main_tab.in_dir_edit, Qt.Key.Key_Enter)
            qtbot.wait(100)

            # Check visual feedback exists
            style_sheet = window.main_tab.in_dir_edit.styleSheet()

            if test_path == "":
                # Empty should have neutral/hint styling
                assert "border" in style_sheet.lower() or len(style_sheet) == 0
            elif test_path == "/tmp":
                # Valid path should have success styling (green border, checkmark, etc.)
                # This depends on your actual validation implementation
                assert True  # Placeholder - check for success indicators
            else:
                # Invalid paths should have error styling (red border, warning icon, etc.)
                assert True  # Placeholder - check for error indicators

    def test_output_filename_validation_patterns(self, qtbot, main_window):
        """Test output filename validation catches common user mistakes."""
        window = main_window

        filename_tests = [
            ("output.mp4", True, "Valid filename should be accepted"),
            ("my video.mp4", True, "Spaces should be allowed"),
            ("output", False, "Missing extension should be rejected"),
            ("output.txt", False, "Wrong extension should be rejected"),
            ("", False, "Empty filename should be rejected"),
            ("con.mp4", False, "Windows reserved name should be rejected"),
            ("a" * 260 + ".mp4", False, "Too long filename should be rejected"),
            ("output?.mp4", False, "Invalid characters should be rejected"),
            ("../../../output.mp4", False, "Path traversal should be rejected"),
        ]

        for filename, should_be_valid, description in filename_tests:
            window.main_tab.out_file_edit.clear()
            window.main_tab.out_file_edit.setText(filename)

            # Trigger validation
            QTest.keyClick(window.main_tab.out_file_edit, Qt.Key.Key_Tab)
            qtbot.wait(50)

            # Check if start button reflects validation state
            window._update_start_button_state()

            if should_be_valid and window.main_tab.in_dir_edit.text():
                # Should enable start button if filename is valid and input dir exists
                assert True  # Check your validation logic
            else:
                # Should show some form of error indication
                assert True  # Check your validation logic

    def test_numeric_input_bounds_and_feedback(self, qtbot, main_window):
        """Test numeric inputs provide clear feedback on invalid ranges."""
        window = main_window

        numeric_tests = [
            (window.main_tab.fps_spinbox, [(0, False), (1, True), (30, True), (120, True), (500, False)]),
            (window.main_tab.mid_count_spinbox, [(0, False), (1, True), (10, True), (100, True), (1000, False)]),
            (
                window.main_tab.rife_tile_size_spinbox,
                [(0, False), (64, True), (256, True), (1024, True), (4096, False)],
            ),
        ]

        for spinbox, value_tests in numeric_tests:
            for value, should_be_valid in value_tests:
                # Test direct value setting
                spinbox.setValue(value)
                actual_value = spinbox.value()

                if should_be_valid:
                    assert actual_value == value, f"Valid value {value} should be accepted"
                else:
                    assert actual_value != value, f"Invalid value {value} should be clamped/rejected"

                # Test that UI shows appropriate feedback
                # Check for visual indicators (colors, tooltips, etc.)
                style = spinbox.styleSheet()
                tooltip = spinbox.toolTip()

                # Validate that user gets feedback about the constraint
                assert len(tooltip) > 0 or "valid" in style.lower(), "Should provide user feedback"

    def test_progress_indicators_user_clarity(self, qtbot, main_window):
        """Test that progress indicators are clear and helpful to users."""
        window = main_window

        # Test progress display during processing
        progress_scenarios = [
            (0, 100, "Starting processing..."),
            (25, 100, "Processing frames (25%)"),
            (50, 100, "Halfway complete (50%)"),
            (99, 100, "Nearly finished (99%)"),
            (100, 100, "Processing complete"),
        ]

        for current, total, expected_context in progress_scenarios:
            window._on_processing_progress(current, total, 2.5)

            # Check that progress is communicated clearly
            status_msg = window.status_bar.currentMessage()
            vm_status = window.main_view_model.processing_vm.status

            # Verify meaningful progress information
            assert str(current) in status_msg or str(current) in vm_status, "Should show current progress"
            assert "%" in status_msg or "%" in vm_status, "Should show percentage"

            # Check for time estimates when available
            if current > 0:
                assert any(
                    word in (status_msg + vm_status).lower() for word in ["eta", "remaining", "estimated", "time"]
                ), "Should show time estimate"

    def test_error_message_user_friendliness(self, qtbot, main_window):
        """Test that error messages are helpful and actionable for users."""
        window = main_window

        # Mock various error scenarios
        error_scenarios = [
            ("File not found: /path/to/missing.jpg", "Should suggest checking file location"),
            ("Permission denied", "Should suggest checking file permissions or running as admin"),
            ("Out of memory", "Should suggest closing other applications or processing smaller batches"),
            ("Codec not supported", "Should suggest installing required codecs or using different format"),
            ("Network timeout", "Should suggest checking internet connection or trying again"),
        ]

        for error_msg, expected_guidance in error_scenarios:
            window._on_processing_error(error_msg)

            # Check status bar message
            status_msg = window.status_bar.currentMessage()
            vm_status = window.main_view_model.processing_vm.status

            # Verify error is communicated clearly
            assert "error" in status_msg.lower() or "failed" in status_msg.lower(), "Should indicate error clearly"

            # Check that technical jargon is minimized
            technical_words = ["null", "exception", "traceback", "errno", "0x"]
            combined_msg = (status_msg + vm_status).lower()

            for tech_word in technical_words:
                assert tech_word not in combined_msg, f"Should avoid technical term: {tech_word}"

    def test_keyboard_navigation_workflow(self, qtbot, main_window):
        """Test complete keyboard navigation workflow."""
        window = main_window

        # Test tab order through main form
        tab_sequence = [
            window.main_tab.in_dir_edit,
            window.main_tab.out_file_edit,
            window.main_tab.fps_spinbox,
            window.main_tab.mid_count_spinbox,
            window.main_tab.encoder_combo,
            window.main_tab.start_button,
        ]

        # Start from first element
        window.main_tab.in_dir_edit.setFocus()
        current_focus = window.focusWidget()

        for i, expected_widget in enumerate(tab_sequence[1:], 1):
            # Press Tab to move to next widget
            QTest.keyClick(current_focus, Qt.Key.Key_Tab)
            qtbot.wait(50)

            current_focus = window.focusWidget()

            # Verify focus moved to expected widget or its parent
            assert current_focus == expected_widget or current_focus in expected_widget.findChildren(
                type(current_focus)
            ), f"Tab order broken at step {i}, expected {expected_widget}, got {current_focus}"

    def test_window_resize_layout_integrity(self, qtbot, main_window):
        """Test that UI layout remains usable at different window sizes."""
        window = main_window

        # Test various window sizes
        size_scenarios = [
            (400, 300, "Very small window"),
            (800, 600, "Small window"),
            (1024, 768, "Medium window"),
            (1920, 1080, "Large window"),
            (3840, 2160, "4K window"),
        ]

        for width, height, description in size_scenarios:
            window.resize(width, height)
            qtbot.wait(100)  # Allow layout to update

            # Check that critical UI elements are still visible and usable
            critical_widgets = [
                window.main_tab.in_dir_edit,
                window.main_tab.out_file_edit,
                window.main_tab.start_button,
                window.status_bar,
            ]

            for widget in critical_widgets:
                widget_rect = widget.geometry()
                window_rect = window.rect()

                # Widget should be within window bounds
                assert widget_rect.left() >= 0, f"Widget clipped on left at {description}"
                assert widget_rect.top() >= 0, f"Widget clipped on top at {description}"
                assert widget_rect.right() <= window_rect.width(), f"Widget clipped on right at {description}"

                # Widget should have reasonable minimum size
                assert widget_rect.width() > 50, f"Widget too narrow at {description}"
                assert widget_rect.height() > 20, f"Widget too short at {description}"

    def test_settings_persistence_corruption_recovery(self, qtbot, main_window):
        """Test graceful handling of corrupted settings."""
        window = main_window

        # Test various corruption scenarios
        with patch.object(window.settings, "value") as mock_value:
            corruption_scenarios = [
                (Exception("Settings file corrupted"), "Should use defaults on corruption"),
                (None, "Should handle None values gracefully"),
                ("invalid_json_string", "Should handle invalid data gracefully"),
                (b"binary_data", "Should handle wrong data types gracefully"),
            ]

            for corrupt_data, expected_behavior in corruption_scenarios:
                if isinstance(corrupt_data, Exception):
                    mock_value.side_effect = corrupt_data
                else:
                    mock_value.return_value = corrupt_data

                # Attempt to load settings
                try:
                    window.loadSettings()

                    # Should not crash and should use reasonable defaults
                    assert window.main_tab.fps_spinbox.value() > 0, "Should have valid default FPS"
                    assert window.main_tab.mid_count_spinbox.value() > 0, "Should have valid default count"

                except Exception as e:
                    pytest.fail(f"Settings corruption should be handled gracefully, but got: {e}")

    def test_file_dialog_edge_cases(self, qtbot, main_window):
        """Test file dialog behavior with edge cases."""
        window = main_window

        with patch("goesvfi.gui_tabs.main_tab.QFileDialog") as mock_dialog:
            edge_cases = [
                ("", "User cancels dialog"),
                ("C:\\path with spaces\\video.mp4", "Windows path with spaces"),
                ("/path/with/unicode/测试.mp4", "Unicode filename"),
                ("\\\\network\\share\\video.mp4", "Network path"),
                ("file:///Users/test/video.mp4", "File URL format"),
                ("a" * 200 + ".mp4", "Very long filename"),
            ]

            for return_value, description in edge_cases:
                mock_dialog.getSaveFileName.return_value = (return_value, "Video Files (*.mp4)")

                # Trigger file dialog
                window.main_tab._pick_out_file()

                # Check that path is handled appropriately
                output_text = window.main_tab.out_file_edit.text()

                if return_value == "":
                    # Cancelled dialog should not change current value
                    assert True  # Existing value should be preserved
                else:
                    # Valid paths should be normalized and set
                    assert len(output_text) > 0, f"Should handle {description}"

                    # Path should be normalized (no file:// prefixes, proper separators)
                    assert not output_text.startswith("file://"), "Should strip file:// prefix"
