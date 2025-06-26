"""Theme management for the GUI application using qt-material.

This module handles application theming with Material Design themes,
supporting multiple themes and runtime theme switching.
"""

from typing import Dict, List, Optional, Tuple

from PyQt6.QtWidgets import QApplication, QWidget

from goesvfi.utils import config, log

LOGGER = log.get_logger(__name__)

# Available qt-material themes
AVAILABLE_THEMES = [
    "dark_teal",
    "dark_blue",
    "dark_amber",
    "dark_cyan",
    "dark_lightgreen",
    "dark_pink",
    "dark_purple",
    "dark_red",
    "dark_yellow",
]

# Default theme
DEFAULT_THEME = "dark_teal"


class ThemeManager:
    """Manages application themes using qt-material with custom overrides."""

    def __init__(self) -> None:
        """Initialize the theme manager."""
        # Load theme configuration from config file
        self._current_theme = config.get_theme_name()
        self._custom_overrides_enabled = config.get_theme_custom_overrides()
        self._fallback_enabled = config.get_theme_fallback_enabled()
        self._density_scale = config.get_theme_density_scale()

        # Validate theme name
        if self._current_theme not in AVAILABLE_THEMES:
            LOGGER.warning(f"Invalid theme '{self._current_theme}' in config, using default")
            self._current_theme = DEFAULT_THEME

        self._custom_overrides = self._create_custom_overrides()
        LOGGER.info(f"ThemeManager initialized with theme: {self._current_theme}")
        LOGGER.debug(
            f"Custom overrides: {self._custom_overrides_enabled}, "
            f"Fallback: {self._fallback_enabled}, "
            f"Density scale: {self._density_scale}"
        )

    @property
    def current_theme(self) -> str:
        """Get the current theme name."""
        return self._current_theme

    @property
    def available_themes(self) -> List[str]:
        """Get list of available theme names."""
        return AVAILABLE_THEMES.copy()

    def apply_theme(self, app: QApplication, theme_name: Optional[str] = None) -> None:
        """Apply qt-material theme to the application.

        Args:
            app: The QApplication instance
            theme_name: Theme name to apply (defaults to current theme)
        """
        if theme_name is None:
            theme_name = self._current_theme

        if theme_name not in AVAILABLE_THEMES:
            LOGGER.warning(f"Unknown theme '{theme_name}', using default '{DEFAULT_THEME}'")
            theme_name = DEFAULT_THEME

        try:
            import qt_material  # type: ignore[import-not-found]

            # Apply qt-material theme with density scaling if configured
            extra = {}
            if self._density_scale and self._density_scale != "0":
                extra["density_scale"] = self._density_scale

            qt_material.apply_stylesheet(app, theme=f"{theme_name}.xml", **extra)
            self._current_theme = theme_name

            LOGGER.info(f"Applied qt-material theme: {theme_name}")
            if extra:
                LOGGER.debug(f"Applied with extra options: {extra}")

            # Apply custom overrides for brand-specific styling if enabled
            if self._custom_overrides_enabled:
                self._apply_custom_overrides(app)

        except ImportError:
            LOGGER.error("qt-material not installed")
            if self._fallback_enabled:
                LOGGER.info("Falling back to basic dark theme")
                self._apply_fallback_theme(app)
            else:
                LOGGER.error("Fallback disabled, theme application failed")
        except Exception as e:
            LOGGER.error(f"Failed to apply theme '{theme_name}': {e}")
            if self._fallback_enabled:
                self._apply_fallback_theme(app)
            else:
                LOGGER.error("Fallback disabled, theme application failed")

    def change_theme(self, app: QApplication, theme_name: str) -> bool:
        """Change the current theme at runtime.

        Args:
            app: The QApplication instance
            theme_name: New theme name to apply

        Returns:
            True if theme was changed successfully, False otherwise
        """
        if theme_name not in AVAILABLE_THEMES:
            LOGGER.warning(f"Invalid theme name: {theme_name}")
            return False

        try:
            self.apply_theme(app, theme_name)
            LOGGER.info(f"Theme changed to: {theme_name}")
            return True
        except Exception as e:
            LOGGER.error(f"Failed to change theme: {e}")
            return False

    def _apply_custom_overrides(self, app: QApplication) -> None:
        """Apply custom styling overrides for brand-specific elements.

        Args:
            app: The QApplication instance
        """
        try:
            # Get existing stylesheet and append our custom overrides
            existing_style = app.styleSheet()
            combined_style = existing_style + "\n" + self._custom_overrides
            app.setStyleSheet(combined_style)

            LOGGER.debug("Applied custom styling overrides")
        except Exception as e:
            LOGGER.warning(f"Failed to apply custom overrides: {e}")

    def _create_custom_overrides(self) -> str:
        """Create custom CSS overrides for brand-specific styling.

        Returns:
            CSS stylesheet with custom overrides
        """
        return """
            /* Custom overrides for GOES_VFI branding and domain-specific styling */

            /* Application header gradients for visual hierarchy */
            QLabel.AppHeader {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a6fa5, stop:1 #3a5f95);
                color: #ffffff;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 12px;
            }

            /* Status indicators with domain-specific colors */
            QLabel.StatusSuccess {
                color: #66ff66;
                font-weight: bold;
            }

            QLabel.StatusError {
                color: #ff6666;
                font-weight: bold;
            }

            QLabel.StatusWarning {
                color: #ffaa66;
                font-weight: bold;
            }

            QLabel.StatusInfo {
                color: #66aaff;
                font-weight: bold;
            }

            /* Progress bars for data processing */
            QProgressBar.DataProgress {
                text-align: center;
                font-weight: bold;
            }

            QProgressBar.DataProgress::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a6fa5, stop:1 #6C9BD1);
            }

            /* Satellite data visualization elements */
            QFrame.SatelliteDataFrame {
                border: 2px solid #4a6fa5;
                border-radius: 8px;
                background: rgba(74, 111, 165, 0.1);
            }

            /* Timeline visualization custom colors */
            QWidget.TimelineViz {
                background-color: transparent;
            }

            /* Keep scientific accuracy for imagery components */
            QLabel.ImageryLabel {
                background-color: #1a1a1a;
                border: 1px solid #333333;
            }

            /* Integrity Check Tab styling */
            QWidget.IntegrityCheckTab {
                background-color: transparent;
            }

            /* Enhanced Tab Widget Styling for Left-positioned Tabs */
            QTabWidget::tab-bar {
                alignment: left;
                width: 40px;  /* Ultra-compact sidebar */
            }

            QTabBar::tab {
                background: rgba(60, 60, 60, 0.6);
                border: none;
                border-radius: 2px;
                padding: 4px 2px;
                margin: 1px 0px;
                min-width: 36px;
                max-width: 38px;
                min-height: 24px;
                color: #ffffff;
                font-weight: 400;
                font-size: 10px;
                text-align: center;
            }

            QTabBar::tab:hover {
                background: rgba(74, 111, 165, 0.7);
                color: #ffffff;
            }

            QTabBar::tab:selected {
                background: #4a6fa5;
                color: #ffffff;
                font-weight: 500;
            }

            QTabBar::tab:!selected {
                margin-left: 2px;
            }

            /* For left-positioned tabs specifically */
            QTabWidget[tabPosition="2"] QTabBar::tab {
                padding: 3px 1px;
                margin: 1px 0px;
                text-align: center;
                border-radius: 2px;
            }

            QTabWidget[tabPosition="2"] QTabBar::tab:selected {
                border-right: 2px solid #6c9bd1;
            }

            /* Tab widget pane styling */
            QTabWidget::pane {
                border: none;
                background-color: transparent;
                margin-left: 0px;
            }

            /* Status labels with improved styling */
            QLabel.StatusLabel {
                padding: 5px 8px;
                border-radius: 4px;
                background-color: rgba(255, 255, 255, 0.1);
                font-weight: normal;
            }

            QLabel.StatusSuccess {
                color: #66ff66;
                font-weight: bold;
                padding: 5px 8px;
                border-radius: 4px;
                background-color: rgba(102, 255, 102, 0.1);
            }

            QLabel.StatusError {
                color: #ff6666;
                font-weight: bold;
                padding: 5px 8px;
                border-radius: 4px;
                background-color: rgba(255, 102, 102, 0.1);
            }

            QLabel.StatusWarning {
                color: #ffaa66;
                font-weight: bold;
                padding: 5px 8px;
                border-radius: 4px;
                background-color: rgba(255, 170, 102, 0.1);
            }

            /* Main Tab specific styling */
            QWidget.MainTab {
                background-color: transparent;
            }

            /* Start Button styling */
            QPushButton.StartButton {
                font-weight: bold;
                font-size: 16px;
                border-radius: 5px;
                padding: 8px 16px;
                min-height: 50px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #66ff66, stop:1 #44dd44);
                color: #000000;
            }

            QPushButton.StartButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #77ff77, stop:1 #55ee55);
            }

            QPushButton.StartButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #44dd44, stop:1 #22bb22);
            }

            QPushButton.CancelButton {
                font-weight: bold;
                font-size: 16px;
                border-radius: 5px;
                padding: 8px 16px;
                min-height: 50px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ff6666, stop:1 #dd4444);
                color: #ffffff;
            }

            QPushButton.CancelButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ff7777, stop:1 #ee5555);
            }

            QPushButton.StartButtonDisabled {
                font-weight: bold;
                font-size: 16px;
                border-radius: 5px;
                padding: 8px 16px;
                min-height: 50px;
                background-color: rgba(128, 128, 128, 0.3);
                color: rgba(255, 255, 255, 0.5);
            }

            /* Image Preview styling */
            QLabel.ImagePreview {
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 4px;
            }

            /* Validation Error styling */
            QLineEdit.ValidationError {
                background-color: rgba(255, 102, 102, 0.2);
                border: 2px solid #ff6666;
                border-radius: 4px;
            }

            /* Crop Selection Dialog styling */
            QDialog.CropSelectionDialog {
                background-color: rgba(20, 20, 20, 0.95);
                border: 2px solid rgba(255, 255, 255, 0.3);
                border-radius: 8px;
            }

            QWidget.CropDialogHeader {
                background-color: rgba(0, 0, 0, 0.8);
                border-bottom: 1px solid rgba(255, 255, 255, 0.3);
            }

            QLabel.CropDialogInstruction {
                color: rgba(255, 255, 255, 0.9);
                font-size: 14px;
                font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            }

            /* Image Viewer Dialog styling */
            QDialog.ImageViewerDialog {
                background-color: rgba(30, 30, 30, 0.98);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }

            /* General Dialog Button styling */
            QPushButton.DialogButton {
                background-color: rgba(60, 60, 60, 0.9);
                color: rgba(255, 255, 255, 0.9);
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: normal;
            }

            QPushButton.DialogButton:hover {
                background-color: rgba(80, 80, 80, 0.9);
                border-color: rgba(255, 255, 255, 0.5);
            }

            QPushButton.DialogButton:pressed {
                background-color: rgba(40, 40, 40, 0.9);
            }

            QPushButton.DialogPrimaryButton {
                background-color: #4a6fa5;
                color: #ffffff;
                border: 1px solid #6C9BD1;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }

            QPushButton.DialogPrimaryButton:hover {
                background-color: #5a7fb5;
            }

            QPushButton.DialogPrimaryButton:pressed {
                background-color: #3a5f95;
            }

            /* Feedback System styling */
            QLabel.FeedbackStatusLabel {
                padding: 8px;
                border-radius: 4px;
                background-color: rgba(240, 240, 240, 0.1);
                font-weight: bold;
            }

            QLabel.FeedbackStatusInfo {
                padding: 8px;
                border-radius: 4px;
                background-color: rgba(212, 237, 218, 0.3);
                color: #155724;
                font-weight: bold;
            }

            QLabel.FeedbackStatusSuccess {
                padding: 8px;
                border-radius: 4px;
                background-color: rgba(195, 230, 203, 0.3);
                color: #155724;
                font-weight: bold;
            }

            QLabel.FeedbackStatusWarning {
                padding: 8px;
                border-radius: 4px;
                background-color: rgba(255, 243, 205, 0.3);
                color: #856404;
                font-weight: bold;
            }

            QLabel.FeedbackStatusError {
                padding: 8px;
                border-radius: 4px;
                background-color: rgba(248, 215, 218, 0.3);
                color: #721c24;
                font-weight: bold;
            }

            QLabel.FeedbackStatusDebug {
                padding: 8px;
                border-radius: 4px;
                background-color: rgba(240, 240, 240, 0.2);
                color: rgba(255, 255, 255, 0.7);
                font-weight: bold;
            }

            QListWidget.FeedbackMessageList {
                background-color: rgba(245, 245, 245, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
            }

            /* Error Dialog styling */
            QLabel.ErrorDialogMessage {
                padding: 10px;
                background-color: rgba(248, 215, 218, 0.3);
                border: 1px solid rgba(245, 198, 203, 0.5);
                border-radius: 4px;
                color: #721c24;
            }

            QPlainTextEdit.ErrorDialogTraceback {
                font-family: "Consolas", "Monaco", "Courier New", monospace;
                font-size: 10pt;
                background-color: rgba(245, 245, 245, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
            }

            /* Date Range and Visual Date Picker styling */
            QLabel.DateRangeDisplay {
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
                background-color: rgba(74, 111, 165, 0.1);
            }

            QFrame.DatePickerGroup {
                background-color: rgba(53, 53, 53, 0.3);
                border-radius: 4px;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }

            QFrame.DatePickerPreview {
                background-color: rgba(30, 47, 69, 0.3);
                border-radius: 4px;
                border: 1px solid rgba(74, 111, 165, 0.3);
            }

            QLabel.DatePickerTitle {
                font-weight: bold;
                font-size: 14px;
                color: rgba(255, 255, 255, 0.9);
            }

            QLabel.DatePickerMonospace {
                font-family: "Consolas", "Monaco", "Courier New", monospace;
                color: rgba(255, 255, 255, 0.8);
            }

            QPushButton.DatePickerButton {
                background-color: rgba(58, 58, 58, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                padding: 6px 12px;
                color: rgba(255, 255, 255, 0.9);
            }

            QPushButton.DatePickerButton:hover {
                background-color: rgba(69, 69, 69, 0.8);
                border-color: rgba(255, 255, 255, 0.3);
            }

            QPushButton.DatePickerButton:pressed {
                background-color: #2a82da;
                border-color: #2a82da;
            }

            QPushButton.DatePickerPrimary {
                background-color: #2a82da;
                border: 1px solid #3a92ea;
                border-radius: 4px;
                padding: 6px 12px;
                color: #ffffff;
                font-weight: bold;
            }

            QPushButton.DatePickerPrimary:hover {
                background-color: #3a92ea;
            }

            QPushButton.DatePickerPrimary:pressed {
                background-color: #1a72ca;
            }

            QCalendarWidget.DatePickerCalendar {
                background-color: rgba(45, 45, 45, 0.8);
                color: rgba(255, 255, 255, 0.9);
                selection-background-color: #2a82da;
                selection-color: #ffffff;
            }

            QTimeEdit.DatePickerTime {
                background-color: rgba(58, 58, 58, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                padding: 4px;
                color: rgba(255, 255, 255, 0.9);
            }

            QTimeEdit.DatePickerTime:focus {
                background-color: rgba(69, 69, 69, 0.8);
                border-color: #2a82da;
            }

            /* FFmpeg Settings Tab styling */
            QWidget.FFmpegSettingsTab {
                background-color: transparent;
            }

            /* Common label styling for consistent alignment */
            QLabel.FFmpegLabel, QLabel.StandardLabel {
                font-weight: bold;
                color: rgba(255, 255, 255, 0.9);
                padding: 2px 4px;
                min-width: 100px;
                text-align: right;
            }

            /* Form layout labels - right aligned for consistency */
            QFormLayout QLabel {
                font-weight: bold;
                color: rgba(255, 255, 255, 0.9);
                padding: 2px 4px;
                text-align: right;
            }

            /* Group box titles */
            QGroupBox {
                font-weight: bold;
                border: 2px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                background-color: rgba(45, 45, 45, 0.9);
                border-radius: 3px;
            }

            /* Control Frame styling for satellite tabs */
            QFrame.ControlFrame {
                background-color: rgba(50, 50, 50, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 10px;
            }

            /* Consistent grid layout spacing */
            QGridLayout {
                spacing: 10px;
            }

            /* Ensure consistent alignment in grid layouts */
            QGridLayout QLabel {
                min-width: 100px;
            }

            /* Tab button styling for satellite integrity sub-tabs */
            QPushButton.TabButton {
                font-weight: bold;
                padding: 8px 16px;
                min-height: 35px;
                border-radius: 4px;
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }

            QPushButton.TabButton:checked {
                background-color: #4a6fa5;
                color: #ffffff;
                border: 1px solid #6C9BD1;
            }

            QPushButton.TabButton:hover:!checked {
                background-color: rgba(255, 255, 255, 0.15);
                border: 1px solid rgba(255, 255, 255, 0.3);
            }
        """

    def _apply_fallback_theme(self, app: QApplication) -> None:
        """Apply a basic fallback theme if qt-material is not available.

        Args:
            app: The QApplication instance
        """
        fallback_style = """
            QWidget {
                background-color: #2D2D2D;
                color: #EFEFEF;
                font-family: Arial, Helvetica, sans-serif;
            }

            QPushButton {
                background-color: #4A4A4A;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px 15px;
                color: #EFEFEF;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #5A5A5A;
            }

            QPushButton:pressed {
                background-color: #3A3A3A;
            }

            QLineEdit, QComboBox, QSpinBox {
                background-color: #3D3D3D;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px;
                color: #EFEFEF;
            }

            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border: 1px solid #6C9BD1;
            }
        """

        combined_style = fallback_style + "\n" + self._custom_overrides
        app.setStyleSheet(combined_style)
        LOGGER.info("Applied fallback theme")

    # Legacy compatibility methods
    def apply_dark_theme(self, widget: QWidget) -> None:
        """Legacy method for backward compatibility.

        Args:
            widget: The widget to apply theme to (now applies to whole app)
        """
        _ = widget  # Unused but kept for API compatibility
        LOGGER.warning("apply_dark_theme is deprecated, use apply_theme instead")
        app = QApplication.instance()
        if app and isinstance(app, QApplication):
            self.apply_theme(app)
        else:
            LOGGER.error("No QApplication instance found for theme application")

    def validate_theme_config(self) -> Tuple[bool, List[str]]:
        """Validate current theme configuration.

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # Check theme name
        if self._current_theme not in AVAILABLE_THEMES:
            issues.append(f"Invalid theme name: {self._current_theme}")

        # Check density scale
        try:
            if self._density_scale and self._density_scale != "0":
                density_val = float(self._density_scale)
                if not -2.0 <= density_val <= 2.0:
                    issues.append(f"Density scale out of range: {density_val}")
        except ValueError:
            issues.append(f"Invalid density scale format: {self._density_scale}")

        # Validate custom overrides syntax
        if self._custom_overrides_enabled:
            try:
                # Basic CSS syntax check
                overrides = self._create_custom_overrides()
                if "/*" in overrides and "*/" not in overrides:
                    issues.append("Unclosed comment in custom overrides")
                if overrides.count("{") != overrides.count("}"):
                    issues.append("Mismatched braces in custom overrides")
            except Exception as e:
                issues.append(f"Custom overrides syntax error: {e}")

        return len(issues) == 0, issues

    def get_accessibility_overrides(self) -> str:
        """Get accessibility-focused theme overrides.

        Returns:
            CSS string with high contrast and accessibility improvements
        """
        return """
            /* Accessibility Enhancements */

            /* High contrast focus indicators */
            QWidget:focus {
                outline: 2px solid #ffff00;
                outline-offset: 2px;
            }

            /* Enhanced button focus */
            QPushButton:focus {
                border: 3px solid #ffff00;
                outline: none;
            }

            /* High contrast status colors */
            QLabel.StatusSuccess.HighContrast {
                color: #00ff00;
                background-color: rgba(0, 255, 0, 0.2);
                font-weight: bold;
            }

            QLabel.StatusError.HighContrast {
                color: #ff0000;
                background-color: rgba(255, 0, 0, 0.2);
                font-weight: bold;
            }

            QLabel.StatusWarning.HighContrast {
                color: #ffff00;
                background-color: rgba(255, 255, 0, 0.2);
                font-weight: bold;
            }

            /* Larger click targets */
            QPushButton.AccessibilityEnhanced {
                min-height: 44px;
                min-width: 44px;
                padding: 8px 16px;
            }

            /* Enhanced text visibility */
            QLabel.AccessibilityText {
                font-size: 14pt;
                line-height: 1.5;
                color: #ffffff;
                background-color: rgba(0, 0, 0, 0.8);
                padding: 4px 8px;
                border-radius: 4px;
            }
        """

    def apply_accessibility_mode(self, app: QApplication, enabled: bool = True) -> None:
        """Apply or remove accessibility enhancements.

        Args:
            app: QApplication instance
            enabled: Whether to enable accessibility mode
        """
        try:
            if enabled:
                # Apply base theme first
                self.apply_theme(app)

                # Add accessibility overrides
                existing_style = app.styleSheet()
                accessibility_style = self.get_accessibility_overrides()
                combined_style = existing_style + "\n" + accessibility_style
                app.setStyleSheet(combined_style)

                LOGGER.info("Accessibility mode enabled")
            else:
                # Reapply base theme without accessibility overrides
                self.apply_theme(app)
                LOGGER.info("Accessibility mode disabled")

        except Exception as e:
            LOGGER.error(f"Failed to apply accessibility mode: {e}")

    def get_theme_classes_list(self) -> Dict[str, List[str]]:
        """Get organized list of all available theme classes.

        Returns:
            Dictionary organized by category
        """
        return {
            "Core Application": [
                "AppHeader",
                "MainTab",
                "IntegrityCheckTab",
                "FFmpegSettingsTab",
            ],
            "Status Indicators": [
                "StatusSuccess",
                "StatusError",
                "StatusWarning",
                "StatusInfo",
                "StatusLabel",
            ],
            "Buttons": [
                "StartButton",
                "CancelButton",
                "StartButtonDisabled",
                "DialogButton",
                "DialogPrimaryButton",
                "TabButton",
            ],
            "Input Validation": ["ValidationError", "ImagePreview"],
            "Dialogs": [
                "CropSelectionDialog",
                "CropDialogHeader",
                "CropDialogInstruction",
                "ImageViewerDialog",
            ],
            "Feedback System": [
                "FeedbackStatusLabel",
                "FeedbackStatusSuccess",
                "FeedbackStatusError",
                "FeedbackStatusWarning",
                "FeedbackStatusInfo",
                "FeedbackStatusDebug",
                "FeedbackMessageList",
            ],
            "Error Handling": ["ErrorDialogMessage", "ErrorDialogTraceback"],
            "Date/Time": [
                "DateRangeDisplay",
                "DatePickerGroup",
                "DatePickerPreview",
                "DatePickerTitle",
                "DatePickerMonospace",
                "DatePickerButton",
                "DatePickerPrimary",
                "DatePickerCalendar",
                "DatePickerTime",
            ],
            "Specialized": [
                "FFmpegLabel",
                "StandardLabel",
                "SatelliteDataFrame",
                "ImageryLabel",
                "DataProgress",
                "ControlFrame",
            ],
            "Accessibility": [
                "HighContrast",
                "AccessibilityEnhanced",
                "AccessibilityText",
            ],
        }

    def export_theme_classes_documentation(self) -> str:
        """Export theme classes as formatted documentation string.

        Returns:
            Formatted documentation string
        """
        classes = self.get_theme_classes_list()
        docs = ["# Available Theme Classes\n"]

        for category, class_list in classes.items():
            docs.append(f"## {category}\n")
            for class_name in class_list:
                docs.append(f"- `{class_name}`")
            docs.append("")  # Empty line

        return "\n".join(docs)

    def get_theme_config(self) -> Dict[str, str]:
        """Get current theme configuration.

        Returns:
            Dictionary with theme configuration
        """
        return {
            "current": self._current_theme,
            "available": ",".join(AVAILABLE_THEMES),
            "default": DEFAULT_THEME,
        }
