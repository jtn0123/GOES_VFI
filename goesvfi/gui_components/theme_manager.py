"""Theme management for the GUI application using qt-material.

This module handles application theming with Material Design themes,
supporting multiple themes and runtime theme switching.
"""

from typing import Dict, List, Optional

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
            import qt_material

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
        LOGGER.warning("apply_dark_theme is deprecated, use apply_theme instead")
        app = QApplication.instance()
        if app:
            self.apply_theme(app)
        else:
            LOGGER.error("No QApplication instance found for theme application")

    def get_theme_config(self) -> Dict[str, str]:
        """Get current theme configuration.

        Returns:
            Dictionary with theme configuration
        """
        return {"current": self._current_theme, "available": ",".join(AVAILABLE_THEMES), "default": DEFAULT_THEME}
