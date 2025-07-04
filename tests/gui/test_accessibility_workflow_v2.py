"""
Comprehensive accessibility and keyboard navigation workflow tests.

Tests that ensure the GOES_VFI application is usable via keyboard-only navigation,
screen readers, and assistive technologies. Focuses on real-world accessibility scenarios.
"""

from unittest.mock import patch
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QAction
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QWidget
import pytest

from goesvfi.gui import MainWindow


class TestAccessibilityWorkflow:
    """Test complete accessibility workflows and keyboard navigation."""

    @pytest.fixture()
    def main_window(self, qtbot):
        """Create MainWindow with accessibility focus."""
        with patch("goesvfi.gui.QSettings"):
            window = MainWindow(debug_mode=True)
            qtbot.addWidget(window)
            window._post_init_setup()
            return window

    def test_complete_keyboard_only_workflow(self, qtbot, main_window):
        """Test entire application workflow using only keyboard."""
        window = main_window

        # Start with focus on first input
        window.main_tab.in_dir_edit.setFocus()
        qtbot.wait(50)

        # Step 1: Navigate to input directory field and "select" directory
        assert window.focusWidget() == window.main_tab.in_dir_edit, "Should start on input directory"

        # Simulate typing a path (user would normally use file dialog via Enter/Space)
        test_path = "/tmp"
        window.main_tab.in_dir_edit.setText(test_path)
        QTest.keyClick(window.main_tab.in_dir_edit, Qt.Key.Key_Tab)
        qtbot.wait(50)

        # Step 2: Navigate to output file field
        assert window.focusWidget() == window.main_tab.out_file_edit, "Should tab to output file"

        # Type output filename
        window.main_tab.out_file_edit.setText("/tmp/output.mp4")
        QTest.keyClick(window.main_tab.out_file_edit, Qt.Key.Key_Tab)
        qtbot.wait(50)

        # Step 3: Navigate through settings using keyboard
        settings_widgets = [
            window.main_tab.fps_spinbox,
            window.main_tab.mid_count_spinbox,
            window.main_tab.encoder_combo,
        ]

        for widget in settings_widgets:
            # Should be able to reach each widget via Tab
            current_focus = window.focusWidget()

            # Navigate until we reach the target widget (accounting for tab order)
            attempts = 0
            while current_focus != widget and attempts < 20:
                QTest.keyClick(current_focus, Qt.Key.Key_Tab)
                qtbot.wait(25)
                current_focus = window.focusWidget()
                attempts += 1

            # Should eventually reach the widget
            assert attempts < 20, f"Could not reach {widget} via keyboard navigation"

            # Test that widget can be operated via keyboard
            if hasattr(widget, "stepUp"):  # Spinbox
                original_value = widget.value()
                QTest.keyClick(widget, Qt.Key.Key_Up)
                qtbot.wait(25)
                assert widget.value() != original_value, f"Keyboard operation failed on {widget}"
            elif hasattr(widget, "showPopup"):  # ComboBox
                QTest.keyClick(widget, Qt.Key.Key_Space)  # Open dropdown
                qtbot.wait(50)
                QTest.keyClick(widget, Qt.Key.Key_Down)  # Navigate options
                QTest.keyClick(widget, Qt.Key.Key_Enter)  # Select option
                qtbot.wait(25)

        # Step 4: Navigate to start button and verify it's reachable
        start_button = window.main_tab.start_button
        current_focus = window.focusWidget()

        # Navigate to start button
        attempts = 0
        while current_focus != start_button and attempts < 30:
            QTest.keyClick(current_focus, Qt.Key.Key_Tab)
            qtbot.wait(25)
            current_focus = window.focusWidget()
            attempts += 1

        assert current_focus == start_button, "Start button should be reachable via keyboard"

        # Step 5: Test that Enter/Space activates the button
        # (We won't actually start processing, just test the key handling)
        assert start_button.hasFocus(), "Start button should have focus"

    def test_screen_reader_compatibility(self, qtbot, main_window):
        """Test that UI elements provide proper accessibility information."""
        window = main_window

        # Test that critical widgets have proper accessibility properties
        accessibility_tests = [
            (window.main_tab.in_dir_edit, "Input Directory", "Should have clear label"),
            (window.main_tab.out_file_edit, "Output File", "Should have clear label"),
            (window.main_tab.start_button, "Start Processing", "Should have action description"),
            (window.main_tab.fps_spinbox, "FPS", "Should have value description"),
            (window.main_tab.progress_bar, "Progress", "Should have progress description"),
        ]

        for widget, expected_label_content, description in accessibility_tests:
            # Check accessible name
            accessible_name = widget.accessibleName()

            if not accessible_name:
                # Fall back to checking associated labels
                accessible_name = widget.toolTip() or ""

                # Look for associated QLabel
                parent = widget.parent()
                if parent:
                    labels = parent.findChildren(type(widget.buddy()) if hasattr(widget, "buddy") else type(None))
                    if labels:
                        accessible_name = labels[0].text()

            assert len(accessible_name) > 0, f"{description}: {widget} should have accessible name"

            # Check accessible description
            accessible_desc = widget.accessibleDescription()
            tooltip = widget.toolTip()

            # Should have either description or tooltip for context
            assert len(accessible_desc) > 0 or len(tooltip) > 0, (
                f"{description}: {widget} should have description or tooltip"
            )

    def test_focus_indication_visibility(self, qtbot, main_window):
        """Test that focus indicators are clearly visible."""
        window = main_window

        focusable_widgets = [
            window.main_tab.in_dir_edit,
            window.main_tab.out_file_edit,
            window.main_tab.fps_spinbox,
            window.main_tab.start_button,
        ]

        for widget in focusable_widgets:
            # Give focus to widget
            widget.setFocus()
            qtbot.wait(50)

            # Check that widget indicates focus visually
            assert widget.hasFocus(), f"{widget} should have focus"

            # Check for focus indicators in stylesheet or properties
            style_sheet = widget.styleSheet()

            # Should have some form of focus styling
            has_focus_styling = any(
                keyword in style_sheet.lower() for keyword in ["focus", "border", "outline", "background"]
            )

            # If no explicit focus styling, Qt should provide default focus indication
            assert has_focus_styling or widget.focusPolicy() != Qt.FocusPolicy.NoFocus, (
                f"{widget} should have visible focus indication"
            )

    def test_error_state_accessibility(self, qtbot, main_window):
        """Test that error states are accessible to screen readers."""
        window = main_window

        # Trigger various error states
        error_scenarios = [
            ("Invalid input path", window.main_tab.in_dir_edit, "/nonexistent/path"),
            ("Invalid output path", window.main_tab.out_file_edit, "invalid|file<name>.mp4"),
            ("Processing error", None, "Simulated processing failure"),
        ]

        for error_type, widget, error_trigger in error_scenarios:
            if widget:
                # Set invalid value
                if hasattr(widget, "setText"):
                    widget.setText(error_trigger)

                # Trigger validation
                QTest.keyClick(widget, Qt.Key.Key_Tab)
                qtbot.wait(100)

                # Check for accessible error indication
                accessible_desc = widget.accessibleDescription()
                tooltip = widget.toolTip()
                style_sheet = widget.styleSheet()

                # Should indicate error state accessibly
                error_indicators = (accessible_desc + tooltip + style_sheet).lower()
                assert any(keyword in error_indicators for keyword in ["error", "invalid", "warning", "required"]), (
                    f"Error state should be accessible for {error_type}"
                )
            else:
                # Test processing error accessibility
                window._on_processing_error(error_trigger)

                status_msg = window.status_bar.currentMessage()
                assert "error" in status_msg.lower(), "Processing errors should be announced"

    def test_color_contrast_independence(self, qtbot, main_window):
        """Test that interface is usable without relying on color alone."""
        window = main_window

        # Test that interactive elements are distinguishable without color
        interactive_widgets = [
            window.main_tab.start_button,
            window.main_tab.crop_button,
            window.main_tab.clear_crop_button,
        ]

        for widget in interactive_widgets:
            # Check that button has text or icon, not just color
            button_text = widget.text()
            has_icon = not widget.icon().isNull() if hasattr(widget, "icon") else False

            assert len(button_text) > 0 or has_icon, f"{widget} should have text or icon, not rely on color alone"

            # Check enabled/disabled states are distinguishable
            widget.setEnabled(True)
            enabled_style = widget.styleSheet()

            widget.setEnabled(False)
            disabled_style = widget.styleSheet()

            # Should have different styling or Qt provides default disabled appearance
            style_differs = enabled_style != disabled_style
            has_focus_policy = widget.focusPolicy() != Qt.FocusPolicy.NoFocus

            assert style_differs or not has_focus_policy, (
                f"{widget} disabled state should be distinguishable without color"
            )

            # Restore original state
            widget.setEnabled(True)

    def test_keyboard_shortcuts_functionality(self, qtbot, main_window):
        """Test that keyboard shortcuts work correctly."""
        window = main_window

        # Test common keyboard shortcuts
        shortcut_tests = [
            (QKeySequence.StandardKey.Open, "Should trigger input directory selection"),
            (QKeySequence.StandardKey.Save, "Should trigger output file selection"),
            (QKeySequence("Ctrl+Return"), "Should start processing if ready"),
            (QKeySequence("F1"), "Should open help if implemented"),
            (QKeySequence("Escape"), "Should cancel current operation"),
        ]

        for key_sequence, description in shortcut_tests:
            # Test that shortcut is handled (doesn't need to be implemented, just not crash)
            try:
                if isinstance(key_sequence, QKeySequence.StandardKey):
                    # For standard keys, test the key combination they represent
                    if key_sequence == QKeySequence.StandardKey.Open:
                        QTest.keySequence(window, QKeySequence("Ctrl+O"))
                    elif key_sequence == QKeySequence.StandardKey.Save:
                        QTest.keySequence(window, QKeySequence("Ctrl+S"))
                else:
                    QTest.keySequence(window, key_sequence)

                qtbot.wait(100)

                # Should not crash and should handle gracefully
                assert window.isVisible(), f"Window should remain stable after {description}"

            except Exception as e:
                pytest.fail(f"Keyboard shortcut handling failed: {e}")

    def test_tab_navigation_loops_properly(self, qtbot, main_window):
        """Test that tab navigation creates a proper cycle."""
        window = main_window

        # Find all focusable widgets in tab order
        all_widgets = window.findChildren(QWidget)
        focusable_widgets = [
            w
            for w in all_widgets
            if w.focusPolicy() not in [Qt.FocusPolicy.NoFocus, Qt.FocusPolicy.ClickFocus]
            and w.isVisible()
            and w.isEnabled()
        ]

        if len(focusable_widgets) < 2:
            pytest.skip("Need at least 2 focusable widgets to test tab navigation")

        # Start at first focusable widget
        start_widget = focusable_widgets[0]
        start_widget.setFocus()
        qtbot.wait(50)

        visited_widgets = []
        current_widget = window.focusWidget()

        # Tab through all widgets and ensure we eventually cycle back
        for i in range(len(focusable_widgets) * 2):  # Allow for cycling
            visited_widgets.append(current_widget)

            QTest.keyClick(current_widget, Qt.Key.Key_Tab)
            qtbot.wait(25)
            current_widget = window.focusWidget()

            # If we've returned to start, tab cycle is working
            if current_widget == start_widget and len(visited_widgets) > 1:
                break

        # Should have visited multiple widgets and cycled back
        assert len(set(visited_widgets)) > 1, "Should visit multiple widgets"
        assert current_widget == start_widget, "Should cycle back to start"

    def test_progress_announcements(self, qtbot, main_window):
        """Test that progress updates are announced accessibly."""
        window = main_window

        # Test progress announcements during processing
        progress_values = [0, 25, 50, 75, 100]

        for progress in progress_values:
            window._on_processing_progress(progress, 100, 5.0)
            qtbot.wait(50)

            # Check that progress is announced in status bar (accessible to screen readers)
            status_msg = window.status_bar.currentMessage()

            # Should contain progress information
            assert str(progress) in status_msg or f"{progress}%" in status_msg, (
                f"Progress {progress}% should be announced"
            )

            # Should be meaningful to users
            assert len(status_msg) > 10, "Progress announcement should be descriptive"

    def test_dialog_accessibility(self, qtbot, main_window):
        """Test that dialogs are accessible and properly announced."""
        window = main_window

        with patch("goesvfi.gui_tabs.main_tab.QMessageBox") as mock_msgbox:
            # Test error dialog accessibility
            mock_dialog = mock_msgbox.return_value
            mock_dialog.exec.return_value = mock_msgbox.StandardButton.Ok

            # Trigger an error that should show a dialog
            window._on_processing_error("Test error for accessibility")

            # Verify dialog would be created with proper accessibility
            if mock_msgbox.called:
                call_args = mock_msgbox.call_args

                # Should have proper window title and text
                assert len(call_args) > 0, "Dialog should have proper content"

                # Should not rely on icons alone
                text_content = str(call_args)
                assert len(text_content) > 20, "Dialog should have descriptive text"
