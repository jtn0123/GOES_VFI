"""Theme management for the GUI application using qt-material.

This module handles application theming with Material Design themes,
supporting multiple themes and runtime theme switching.
"""

from pathlib import Path

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
            LOGGER.warning("Invalid theme '%s' in config, using default", self._current_theme)
            self._current_theme = DEFAULT_THEME

        self._custom_overrides = self._create_custom_overrides()
        LOGGER.info("ThemeManager initialized with theme: %s", self._current_theme)
        LOGGER.debug(
            "Custom overrides: %s, Fallback: %s, Density scale: %s",
            self._custom_overrides_enabled,
            self._fallback_enabled,
            self._density_scale,
        )

    @property
    def current_theme(self) -> str:
        """Get the current theme name."""
        return self._current_theme

    @property
    def available_themes(self) -> list[str]:
        """Get list of available theme names."""
        return AVAILABLE_THEMES.copy()

    def apply_theme(self, app: QApplication, theme_name: str | None = None) -> None:
        """Apply qt-material theme to the application.

        Args:
            app: The QApplication instance
            theme_name: Theme name to apply (defaults to current theme)
        """
        if theme_name is None:
            theme_name = self._current_theme

        if theme_name not in AVAILABLE_THEMES:
            LOGGER.warning("Unknown theme '%s', using default '%s'", theme_name, DEFAULT_THEME)
            theme_name = DEFAULT_THEME

        try:
            import qt_material  # type: ignore[import-not-found]

            # Apply qt-material theme with density scaling if configured
            extra = {}
            if self._density_scale and self._density_scale != "0":
                extra["density_scale"] = self._density_scale

            qt_material.apply_stylesheet(app, theme=f"{theme_name}.xml", **extra)
            self._current_theme = theme_name

            LOGGER.info("Applied qt-material theme: %s", theme_name)
            if extra:
                LOGGER.debug("Applied with extra options: %s", extra)

            # Apply custom overrides for brand-specific styling if enabled
            if self._custom_overrides_enabled:
                self._apply_custom_overrides(app)

        except ImportError:
            LOGGER.exception("qt-material not installed")
            if self._fallback_enabled:
                LOGGER.info("Falling back to basic dark theme")
                self._apply_fallback_theme(app)
            else:
                LOGGER.exception("Fallback disabled, theme application failed")
        except Exception:
            LOGGER.exception("Failed to apply theme '%s'", theme_name)
            if self._fallback_enabled:
                self._apply_fallback_theme(app)
            else:
                LOGGER.exception("Fallback disabled, theme application failed")

    def change_theme(self, app: QApplication, theme_name: str) -> bool:
        """Change the current theme at runtime.

        Args:
            app: The QApplication instance
            theme_name: New theme name to apply

        Returns:
            True if theme was changed successfully, False otherwise
        """
        if theme_name not in AVAILABLE_THEMES:
            LOGGER.warning("Invalid theme name: %s", theme_name)
            return False

        try:
            self.apply_theme(app, theme_name)
            LOGGER.info("Theme changed to: %s", theme_name)
            return True
        except Exception:
            LOGGER.exception("Failed to change theme")
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
            LOGGER.warning("Failed to apply custom overrides: %s", e)

    def _create_custom_overrides(self) -> str:
        """Load custom CSS overrides for brand-specific styling."""
        overrides_path = Path(__file__).with_name("resources") / "styles" / "default.qss"
        try:
            overrides = overrides_path.read_text()
        except Exception as e:  # pragma: no cover - file missing or unreadable
            LOGGER.warning("Failed to load override stylesheet: %s", e)
            overrides = ""

        # Minimal overrides maintained in code
        minimal = """
            QLabel.AppHeader {
                font-weight: bold;
            }
        """

        return overrides + minimal

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

    def validate_theme_config(self) -> tuple[bool, list[str]]:
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

        except Exception:
            LOGGER.exception("Failed to apply accessibility mode")

    def get_theme_classes_list(self) -> dict[str, list[str]]:
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
            docs.extend(f"- `{class_name}`" for class_name in class_list)
            docs.append("")  # Empty line

        return "\n".join(docs)

    def get_theme_config(self) -> dict[str, str]:
        """Get current theme configuration.

        Returns:
            Dictionary with theme configuration
        """
        return {
            "current": self._current_theme,
            "available": ",".join(AVAILABLE_THEMES),
            "default": DEFAULT_THEME,
        }
