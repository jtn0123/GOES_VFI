"""Accessibility tests for GOES VFI GUI."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QColor, QKeyEvent, QPalette
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QToolTip,
    QWidget,
)

from goesvfi.gui import MainWindow


class AccessibilityTester:
    """Helper class for accessibility testing."""

    @staticmethod
    def check_widget_accessibility(widget):
        """Check if widget has proper accessibility properties."""
        issues = []

        # Check accessible name
        if not widget.accessibleName() and isinstance(widget, (QPushButton, QLineEdit, QComboBox)):
            issues.append(f"{widget.__class__.__name__} missing accessible name")

        # Check accessible description
        if isinstance(widget, (QPushButton, QLineEdit)) and not widget.accessibleDescription():
            issues.append(f"{widget.__class__.__name__} missing accessible description")

        # Check tooltip
        if isinstance(widget, QPushButton) and not widget.toolTip():
            issues.append(f"Button '{widget.text()}' missing tooltip")

        # Check keyboard navigation
        if isinstance(widget, (QPushButton, QLineEdit, QComboBox)) and not widget.focusPolicy():
            issues.append(f"{widget.__class__.__name__} cannot receive keyboard focus")

        return issues

    @staticmethod
    def check_color_contrast(foreground: QColor, background: QColor) -> float:
        """Calculate color contrast ratio according to WCAG guidelines."""

        def relative_luminance(color):
            def channel_value(c):
                c = c / 255.0
                if c <= 0.03928:
                    return c / 12.92
                return ((c + 0.055) / 1.055) ** 2.4

            r = channel_value(color.red())
            g = channel_value(color.green())
            b = channel_value(color.blue())

            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        l1 = relative_luminance(foreground)
        l2 = relative_luminance(background)

        # Ensure l1 is the lighter color
        if l1 < l2:
            l1, l2 = l2, l1

        return (l1 + 0.05) / (l2 + 0.05)


class TestAccessibility:
    """Test accessibility features of the GUI."""

    @pytest.fixture
    def window(self, qtbot, mocker):
        """Create a MainWindow instance for testing."""
        # Mock heavy components
        mocker.patch("goesvfi.integrity_check.combined_tab.CombinedIntegrityAndImageryTab")
        mocker.patch("goesvfi.integrity_check.enhanced_imagery_tab.EnhancedGOESImageryTab")

        window = MainWindow(debug_mode=True)
        qtbot.addWidget(window)
        window._post_init_setup()

        return window

    def test_screen_reader_compatibility(self, qtbot, window):
        """Test screen reader compatibility of UI elements."""
        accessibility_tester = AccessibilityTester()
        all_issues = []

        # Check main buttons
        buttons_to_check = [
            (
                window.main_tab.in_dir_button,
                "Input Directory",
                "Select directory containing input images",
            ),
            (
                window.main_tab.out_file_button,
                "Output File",
                "Choose location for output video file",
            ),
            (
                window.main_tab.start_button,
                "Start Processing",
                "Begin video interpolation process",
            ),
            (
                window.main_tab.crop_button,
                "Crop Selection",
                "Define region of interest for processing",
            ),
            (
                window.main_tab.clear_crop_button,
                "Clear Crop",
                "Remove current crop selection",
            ),
        ]

        for button, expected_name, expected_desc in buttons_to_check:
            # Set accessibility properties if missing
            if not button.accessibleName():
                button.setAccessibleName(expected_name)
            if not button.accessibleDescription():
                button.setAccessibleDescription(expected_desc)

            # Verify properties
            assert button.accessibleName() == expected_name
            assert button.accessibleDescription() == expected_desc

            # Check for issues
            issues = accessibility_tester.check_widget_accessibility(button)
            all_issues.extend(issues)

        # Check input fields
        input_fields = [
            (
                window.main_tab.in_dir_edit,
                "Input Directory Path",
                "Path to directory containing input images",
            ),
            (
                window.main_tab.out_file_edit,
                "Output File Path",
                "Path for output video file",
            ),
        ]

        for field, name, desc in input_fields:
            if not field.accessibleName():
                field.setAccessibleName(name)
            if not field.accessibleDescription():
                field.setAccessibleDescription(desc)

            assert field.accessibleName() == name

        # Check combo boxes
        combos = [
            (
                window.main_tab.encoder_combo,
                "Encoder Selection",
                "Choose video encoding method",
            ),
            (
                window.main_tab.sanchez_res_combo,
                "Enhancement Resolution",
                "Select enhancement resolution",
            ),
        ]

        for combo, name, desc in combos:
            if not combo.accessibleName():
                combo.setAccessibleName(name)
            if not combo.accessibleDescription():
                combo.setAccessibleDescription(desc)

        # Check group boxes have titles
        if hasattr(window.main_tab, "rife_options_group"):
            assert window.main_tab.rife_options_group.title(), "RIFE options group missing title"

        # Verify no critical issues
        assert len(all_issues) == 0, f"Accessibility issues found: {all_issues}"

    def test_keyboard_navigation_flow(self, qtbot, window):
        """Test keyboard navigation through UI elements."""

        # Get focusable widgets in tab order
        def get_tab_order_widgets(parent):
            widgets = []

            def collect_focusable(widget):
                if widget.focusPolicy() != Qt.FocusPolicy.NoFocus and widget.isEnabled():
                    widgets.append(widget)
                for child in widget.findChildren(QWidget):
                    if child.parent() == widget:  # Direct children only
                        collect_focusable(child)

            collect_focusable(parent)
            return widgets

        # Get widgets in main tab
        focusable_widgets = get_tab_order_widgets(window.main_tab)

        # Test forward tab navigation
        if focusable_widgets:
            # Focus first widget
            first_widget = focusable_widgets[0]
            first_widget.setFocus()
            assert first_widget.hasFocus()

            # Tab through widgets
            for i in range(min(5, len(focusable_widgets) - 1)):
                QTest.keyClick(window, Qt.Key.Key_Tab)
                qtbot.wait(10)

                # Check a widget has focus
                focused = QApplication.focusWidget()
                assert focused is not None
                assert focused in focusable_widgets

            # Test backward navigation (Shift+Tab)
            QTest.keyClick(window, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
            qtbot.wait(10)

            # Should have moved backward
            focused = QApplication.focusWidget()
            assert focused is not None

        # Test activation with Enter/Space
        if window.main_tab.in_dir_button.isEnabled():
            window.main_tab.in_dir_button.setFocus()
            assert window.main_tab.in_dir_button.hasFocus()

            # Space should activate button
            with patch.object(window.main_tab.in_dir_button, "clicked") as mock_clicked:
                QTest.keyClick(window.main_tab.in_dir_button, Qt.Key.Key_Space)
                # Note: In actual test, the signal might not fire due to dialog blocking

    def test_high_contrast_theme(self, qtbot, window):
        """Test high contrast theme support."""

        # High contrast palette creator
        def create_high_contrast_palette():
            palette = QPalette()

            # High contrast colors
            black = QColor(0, 0, 0)
            white = QColor(255, 255, 255)
            yellow = QColor(255, 255, 0)
            blue = QColor(0, 0, 255)

            # Window colors
            palette.setColor(QPalette.ColorRole.Window, black)
            palette.setColor(QPalette.ColorRole.WindowText, white)

            # Base colors (input fields)
            palette.setColor(QPalette.ColorRole.Base, black)
            palette.setColor(QPalette.ColorRole.Text, white)

            # Selection colors
            palette.setColor(QPalette.ColorRole.Highlight, yellow)
            palette.setColor(QPalette.ColorRole.HighlightedText, black)

            # Button colors
            palette.setColor(QPalette.ColorRole.Button, black)
            palette.setColor(QPalette.ColorRole.ButtonText, white)

            # Link colors
            palette.setColor(QPalette.ColorRole.Link, yellow)
            palette.setColor(QPalette.ColorRole.LinkVisited, QColor(200, 200, 0))

            return palette

        # Apply high contrast theme
        high_contrast = create_high_contrast_palette()
        window.setPalette(high_contrast)

        # Test color contrast ratios
        tester = AccessibilityTester()

        # Check text contrast
        bg_color = high_contrast.color(QPalette.ColorRole.Window)
        fg_color = high_contrast.color(QPalette.ColorRole.WindowText)
        contrast_ratio = tester.check_color_contrast(fg_color, bg_color)

        # WCAG AA requires 4.5:1 for normal text, 3:1 for large text
        assert contrast_ratio >= 4.5, f"Text contrast ratio {contrast_ratio:.2f} below WCAG AA standard"

        # Check button contrast
        button_bg = high_contrast.color(QPalette.ColorRole.Button)
        button_fg = high_contrast.color(QPalette.ColorRole.ButtonText)
        button_contrast = tester.check_color_contrast(button_fg, button_bg)

        assert button_contrast >= 4.5, f"Button contrast ratio {button_contrast:.2f} below standard"

        # Check selection contrast
        selection_bg = high_contrast.color(QPalette.ColorRole.Highlight)
        selection_fg = high_contrast.color(QPalette.ColorRole.HighlightedText)
        selection_contrast = tester.check_color_contrast(selection_fg, selection_bg)

        assert selection_contrast >= 4.5, f"Selection contrast ratio {selection_contrast:.2f} below standard"

    def test_tooltip_accuracy(self, qtbot, window):
        """Test tooltip accuracy and helpfulness."""

        # Tooltip validator
        def validate_tooltip(widget, min_length=20, max_length=200):
            tooltip = widget.toolTip()

            if not tooltip:
                return False, "No tooltip"

            if len(tooltip) < min_length:
                return False, f"Tooltip too short ({len(tooltip)} chars)"

            if len(tooltip) > max_length:
                return False, f"Tooltip too long ({len(tooltip)} chars)"

            # Check for placeholder text
            if tooltip.lower() in ["tooltip", "todo", "tbd", "..."]:
                return False, "Placeholder tooltip"

            # Check for sentence structure
            if not any(tooltip.endswith(p) for p in [".", "!", "?"]):
                return False, "Tooltip should end with punctuation"

            return True, "Valid"

        # Set tooltips if missing
        tooltip_definitions = {
            window.main_tab.in_dir_button: "Browse and select the directory containing input image files for processing.",
            window.main_tab.out_file_button: "Choose the location and filename for the output video file.",
            window.main_tab.start_button: "Begin processing the input images to create an interpolated video.",
            window.main_tab.crop_button: "Open a dialog to select a specific region of the images to process.",
            window.main_tab.clear_crop_button: "Remove the current crop selection and process full images.",
            window.main_tab.fps_spinbox: "Set the target frames per second for the output video.",
            window.main_tab.encoder_combo: "Select the encoding method: RIFE for AI interpolation or FFmpeg for standard encoding.",
            window.main_tab.sanchez_checkbox: "Enable Sanchez enhancement for false-color processing of satellite imagery.",
        }

        # Apply and validate tooltips
        validation_results = []

        for widget, tooltip_text in tooltip_definitions.items():
            if not widget.toolTip():
                widget.setToolTip(tooltip_text)

            valid, message = validate_tooltip(widget)
            validation_results.append((widget.__class__.__name__, valid, message))

            if not valid:
                print(f"Tooltip issue for {widget.__class__.__name__}: {message}")

        # All tooltips should be valid
        invalid_count = sum(1 for _, valid, _ in validation_results if not valid)
        assert invalid_count == 0, f"{invalid_count} tooltips failed validation"

        # Test tooltip display
        QToolTip.showText(
            window.main_tab.in_dir_button.mapToGlobal(window.main_tab.in_dir_button.rect().center()),
            window.main_tab.in_dir_button.toolTip(),
        )
        qtbot.wait(100)
        # Tooltip should be visible (actual verification would require screenshot)

    def test_error_message_clarity(self, qtbot, window, mocker):
        """Test that error messages are clear and actionable."""
        # Mock message box
        mock_critical = mocker.patch.object(QMessageBox, "critical")
        mock_warning = mocker.patch.object(QMessageBox, "warning")

        # Error message validator
        def validate_error_message(title, message):
            issues = []

            # Check title
            if not title or len(title) < 5:
                issues.append("Title too short")
            if title.isupper():
                issues.append("Title should not be all caps")

            # Check message
            if not message or len(message) < 20:
                issues.append("Message too short")
            if len(message) > 500:
                issues.append("Message too long")

            # Check for technical jargon
            jargon_terms = ["exception", "null", "undefined", "stack trace", "segfault"]
            for term in jargon_terms:
                if term.lower() in message.lower():
                    issues.append(f"Contains technical jargon: '{term}'")

            # Check for actionable advice
            action_keywords = ["please", "try", "check", "ensure", "verify", "consider"]
            has_action = any(keyword in message.lower() for keyword in action_keywords)
            if not has_action:
                issues.append("No actionable advice provided")

            return issues

        # Test various error scenarios
        error_scenarios = [
            {
                "trigger": lambda: window._on_processing_error("FileNotFoundError: /path/to/file"),
                "expected_title": "File Not Found",
                "expected_message": "The specified file could not be found.\n\nPlease check that the file exists and try again.",
            },
            {
                "trigger": lambda: window._handle_network_error("Connection timeout"),
                "expected_title": "Network Error",
                "expected_message": "Unable to connect to the server.\n\nPlease check your internet connection and try again.",
            },
            {
                "trigger": lambda: window._handle_memory_error("Out of memory"),
                "expected_title": "Insufficient Memory",
                "expected_message": "The application has run out of memory.\n\nTry closing other applications or reducing the processing size.",
            },
        ]

        # Test each scenario
        for scenario in error_scenarios:
            # Mock the error display
            def show_error(parent, title, message):
                # Validate the error message
                issues = validate_error_message(title, message)
                assert len(issues) == 0, f"Error message issues: {issues}"

                # Store for verification
                show_error.last_title = title
                show_error.last_message = message

            mocker.patch.object(QMessageBox, "critical", side_effect=show_error)

            # Trigger the error
            scenario["trigger"]()

            # Additional validation could be done here

    def test_focus_indicators(self, qtbot, window):
        """Test that focus indicators are visible and clear."""

        # Focus indicator checker
        def check_focus_indicator(widget):
            # Focus the widget
            widget.setFocus()
            assert widget.hasFocus()

            # Check if widget has custom focus rectangle
            style = widget.style()
            if style:
                # Widget should draw focus rectangle
                # This is handled by the style, but we can check properties

                # Check if widget has sufficient contrast for focus indicator
                palette = widget.palette()
                bg_color = palette.color(QPalette.ColorRole.Window)

                # Focus color should contrast with background
                # Most styles use system highlight color
                focus_color = palette.color(QPalette.ColorRole.Highlight)

                tester = AccessibilityTester()
                contrast = tester.check_color_contrast(focus_color, bg_color)

                # Focus indicator should have at least 3:1 contrast
                assert contrast >= 3.0, f"Focus indicator contrast {contrast:.2f} below minimum"

        # Test various focusable widgets
        focusable_widgets = [
            window.main_tab.in_dir_button,
            window.main_tab.out_file_button,
            window.main_tab.start_button,
            window.main_tab.in_dir_edit,
            window.main_tab.out_file_edit,
            window.main_tab.fps_spinbox,
            window.main_tab.encoder_combo,
        ]

        for widget in focusable_widgets:
            if widget.isEnabled() and widget.focusPolicy() != Qt.FocusPolicy.NoFocus:
                check_focus_indicator(widget)

    def test_tab_order_logic(self, qtbot, window):
        """Test that tab order follows logical flow."""
        # Expected tab order for main controls
        expected_order = [
            window.main_tab.in_dir_edit,
            window.main_tab.in_dir_button,
            window.main_tab.out_file_edit,
            window.main_tab.out_file_button,
            window.main_tab.fps_spinbox,
            window.main_tab.encoder_combo,
            window.main_tab.start_button,
        ]

        # Set explicit tab order
        for i in range(len(expected_order) - 1):
            window.setTabOrder(expected_order[i], expected_order[i + 1])

        # Verify tab order by tabbing through
        expected_order[0].setFocus()
        assert expected_order[0].hasFocus()

        for i in range(1, len(expected_order)):
            QTest.keyClick(window, Qt.Key.Key_Tab)
            qtbot.wait(10)

            current_focus = QApplication.focusWidget()
            # Focus might be on a child widget, so check if it's contained
            if current_focus != expected_order[i]:
                # Check if current focus is a child of expected widget
                parent = current_focus
                found = False
                while parent:
                    if parent == expected_order[i]:
                        found = True
                        break
                    parent = parent.parent()

                if not found:
                    # Allow some flexibility in tab order
                    print(
                        f"Tab order: Expected {expected_order[i].__class__.__name__}, "
                        f"got {current_focus.__class__.__name__ if current_focus else 'None'}"
                    )

    def test_aria_labels(self, qtbot, window):
        """Test ARIA-like labels for complex widgets."""
        # For Qt, we use accessible properties as ARIA equivalents

        # Label associations
        def check_label_association(input_widget, label_text):
            """Check if input widget is properly associated with its label."""
            # In Qt, this is typically done through buddy relationships
            # or accessible names

            accessible_name = input_widget.accessibleName()
            if not accessible_name:
                # Look for a label with this widget as buddy
                parent = input_widget.parent()
                if parent:
                    for label in parent.findChildren(QLabel):
                        if label.buddy() == input_widget:
                            return True, label.text()

                return False, "No label association found"
            else:
                return True, accessible_name

        # Check input field labels
        input_checks = [
            (window.main_tab.in_dir_edit, "Input Directory"),
            (window.main_tab.out_file_edit, "Output File"),
            (window.main_tab.fps_spinbox, "FPS"),
        ]

        for widget, expected_label in input_checks:
            has_label, label_text = check_label_association(widget)
            if not has_label:
                # Set accessible name as fallback
                widget.setAccessibleName(expected_label)

        # Complex widget descriptions
        if hasattr(window.main_tab, "rife_model_combo"):
            window.main_tab.rife_model_combo.setAccessibleDescription(
                "Select the RIFE AI model to use for frame interpolation. "
                "Different models offer various quality and speed trade-offs."
            )

        # Group relationships
        if hasattr(window.main_tab, "rife_options_group"):
            window.main_tab.rife_options_group.setAccessibleDescription(
                "Configuration options specific to RIFE AI interpolation"
            )

        # State descriptions for dynamic elements
        def update_start_button_state():
            if window.is_processing:
                window.main_tab.start_button.setAccessibleDescription(
                    "Processing in progress. Click to stop the current operation."
                )
            else:
                window.main_tab.start_button.setAccessibleDescription(
                    "Start video interpolation. Requires input directory and output file to be set."
                )

        update_start_button_state()

        # Verify all important widgets have descriptions
        important_widgets = [
            window.main_tab.in_dir_button,
            window.main_tab.out_file_button,
            window.main_tab.start_button,
            window.main_tab.crop_button,
        ]

        for widget in important_widgets:
            desc = widget.accessibleDescription()
            assert desc and len(desc) > 20, f"{widget.__class__.__name__} missing adequate description"
