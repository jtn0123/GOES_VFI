"""Dynamic theme management with color extraction from qt-material themes.

This module extends the theme management to support dynamic color updates
based on the selected qt-material theme.
"""

from pathlib import Path

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

from goesvfi.gui_components.theme_manager import AVAILABLE_THEMES, ThemeManager
from goesvfi.gui_components.widget_factory import WidgetFactory
from goesvfi.utils import log

LOGGER = log.get_logger(__name__)

# Re-export AVAILABLE_THEMES for compatibility
__all__ = ["AVAILABLE_THEMES", "DynamicThemeManager"]

# Theme color mappings for each qt-material theme
THEME_COLOR_MAPPINGS = {
    "dark_teal": {
        "primary": "#00bfa5",
        "primary_light": "#5df2d6",
        "primary_dark": "#008e76",
        "accent": "#00e5ff",
        "accent_light": "#6effff",
        "accent_dark": "#00b2cc",
    },
    "dark_blue": {
        "primary": "#448aff",
        "primary_light": "#83b9ff",
        "primary_dark": "#005ecb",
        "accent": "#40c4ff",
        "accent_light": "#82f7ff",
        "accent_dark": "#0094cc",
    },
    "dark_amber": {
        "primary": "#ffc107",
        "primary_light": "#fff350",
        "primary_dark": "#c79100",
        "accent": "#ffab00",
        "accent_light": "#ffdd4b",
        "accent_dark": "#c67c00",
    },
    "dark_cyan": {
        "primary": "#00bcd4",
        "primary_light": "#62efff",
        "primary_dark": "#008ba3",
        "accent": "#00e5ff",
        "accent_light": "#6effff",
        "accent_dark": "#00b2cc",
    },
    "dark_lightgreen": {
        "primary": "#8bc34a",
        "primary_light": "#bef67a",
        "primary_dark": "#5a9216",
        "accent": "#76ff03",
        "accent_light": "#b0ff57",
        "accent_dark": "#32cb00",
    },
    "dark_pink": {
        "primary": "#e91e63",
        "primary_light": "#ff6090",
        "primary_dark": "#b0003a",
        "accent": "#ff4081",
        "accent_light": "#ff79b0",
        "accent_dark": "#c60055",
    },
    "dark_purple": {
        "primary": "#9c27b0",
        "primary_light": "#d05ce3",
        "primary_dark": "#6a0080",
        "accent": "#e040fb",
        "accent_light": "#ff79ff",
        "accent_dark": "#aa00c7",
    },
    "dark_red": {
        "primary": "#f44336",
        "primary_light": "#ff7961",
        "primary_dark": "#ba000d",
        "accent": "#ff5252",
        "accent_light": "#ff867f",
        "accent_dark": "#c50e29",
    },
    "dark_yellow": {
        "primary": "#ffeb3b",
        "primary_light": "#ffff72",
        "primary_dark": "#c8b900",
        "accent": "#ffd600",
        "accent_light": "#ffff52",
        "accent_dark": "#c7a500",
    },
}


class DynamicThemeManager(ThemeManager):
    """Extended theme manager with dynamic color support."""

    def __init__(self) -> None:
        """Initialize the dynamic theme manager."""
        super().__init__()
        self._theme_colors: dict[str, str] = {}
        self._extract_theme_colors()

    def _extract_theme_colors(self) -> None:
        """Extract colors for the current theme."""
        theme_colors = THEME_COLOR_MAPPINGS.get(self._current_theme, THEME_COLOR_MAPPINGS["dark_teal"])
        self._theme_colors = theme_colors.copy()

        # Add derived colors
        self._theme_colors["primary_gradient_start"] = DynamicThemeManager._lighten_color(theme_colors["primary"], 0.1)
        self._theme_colors["primary_gradient_end"] = DynamicThemeManager._darken_color(theme_colors["primary"], 0.1)
        self._theme_colors["button_hover"] = DynamicThemeManager._lighten_color(theme_colors["primary"], 0.2)
        self._theme_colors["button_pressed"] = DynamicThemeManager._darken_color(theme_colors["primary"], 0.2)

        # Add RGB values for use in rgba() functions
        primary_color = QColor(theme_colors["primary"])
        self._theme_colors["primary_rgb"] = f"{primary_color.red()}, {primary_color.green()}, {primary_color.blue()}"

    @staticmethod
    def _lighten_color(hex_color: str, factor: float) -> str:
        """Lighten a color by a factor (0-1).

        Returns:
            str: The lightened color as a hex string.
        """
        color = QColor(hex_color)
        h, s, lightness, a = color.getHslF()
        lightness = min(1.0, lightness + (1.0 - lightness) * factor)
        color.setHslF(h, s, lightness, a)
        return str(color.name())

    @staticmethod
    def _darken_color(hex_color: str, factor: float) -> str:
        """Darken a color by a factor (0-1).

        Returns:
            str: The darkened color as a hex string.
        """
        color = QColor(hex_color)
        h, s, lightness, a = color.getHslF()
        lightness = max(0.0, lightness - lightness * factor)
        color.setHslF(h, s, lightness, a)
        return str(color.name())

    @staticmethod
    def _extract_palette_colors(app: QApplication) -> dict[str, str]:
        """Extract colors from the application palette after theme is applied.

        Returns:
            dict[str, str]: Dictionary mapping color names to hex values.
        """
        palette = app.palette()

        return {
            "window": palette.color(QPalette.ColorRole.Window).name(),
            "window_text": palette.color(QPalette.ColorRole.WindowText).name(),
            "base": palette.color(QPalette.ColorRole.Base).name(),
            "alternate_base": palette.color(QPalette.ColorRole.AlternateBase).name(),
            "text": palette.color(QPalette.ColorRole.Text).name(),
            "button": palette.color(QPalette.ColorRole.Button).name(),
            "button_text": palette.color(QPalette.ColorRole.ButtonText).name(),
            "highlight": palette.color(QPalette.ColorRole.Highlight).name(),
            "highlight_text": palette.color(QPalette.ColorRole.HighlightedText).name(),
        }

    def _create_dynamic_overrides(self) -> str:
        """Create dynamic CSS overrides based on the current theme colors.

        Returns:
            str: CSS stylesheet string with dynamic overrides.
        """
        colors = self._theme_colors

        # Load the template
        template_path = Path(__file__).with_name("resources") / "styles" / "dynamic_template.qss"

        # If template doesn't exist, create it from default.qss
        if not template_path.exists():
            default_path = Path(__file__).with_name("resources") / "styles" / "default.qss"
            if default_path.exists():
                template_content = default_path.read_text()
                # Replace hardcoded colors with placeholders
                template_content = template_content.replace("#4a6fa5", "{primary}")
                template_content = template_content.replace("#3a5f95", "{primary_dark}")
                template_content = template_content.replace("#5a7fb5", "{primary_light}")
                template_content = template_content.replace("#6c9bd1", "{accent}")
                template_content = template_content.replace("#66ff66", "{success}")
                template_content = template_content.replace("#44dd44", "{success_dark}")
                template_content = template_content.replace("#77ff77", "{success_light}")
                template_content = template_content.replace("#ff6666", "{error}")
                template_content = template_content.replace("#dd4444", "{error_dark}")
                template_content = template_content.replace("#ff7777", "{error_light}")
                template_content = template_content.replace("#ffaa66", "{warning}")
                template_content = template_content.replace("#66aaff", "{info}")
                template_content = template_content.replace("#2a82da", "{date_picker}")
                template_content = template_content.replace("#1a72ca", "{date_picker_dark}")
                template_content = template_content.replace("#3a92ea", "{date_picker_light}")
            else:
                template_content = DynamicThemeManager._get_default_template()
        else:
            template_content = template_path.read_text()

        # Add status colors based on theme
        colors["success"] = "#66ff66"
        colors["success_dark"] = "#44dd44"
        colors["success_light"] = "#77ff77"
        colors["error"] = "#ff6666"
        colors["error_dark"] = "#dd4444"
        colors["error_light"] = "#ff7777"
        colors["warning"] = "#ffaa66"
        colors["info"] = colors["accent_light"]
        colors["date_picker"] = colors["primary"]
        colors["date_picker_dark"] = colors["primary_dark"]
        colors["date_picker_light"] = colors["primary_light"]

        # Format the template with actual colors
        try:
            return template_content.format(**colors)
        except KeyError as e:
            LOGGER.warning("Missing color key in template: %s", e)
            return template_content

    @staticmethod
    def _get_default_template() -> str:
        """Get a default template with color placeholders.

        Returns:
            str: CSS template string with placeholders.
        """
        return """
/* Dynamic Theme Colors */

/* Application Headers */
QLabel.AppHeader {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {primary}, stop:1 {primary_dark});
    color: #ffffff;
    font-weight: bold;
    border-radius: 6px;
    padding: 8px 12px;
}}

/* Primary Buttons */
QPushButton.DialogPrimaryButton {{
    background-color: {primary};
    color: #ffffff;
    border: 1px solid {accent};
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: bold;
}}

QPushButton.DialogPrimaryButton:hover {{
    background-color: {primary_light};
}}

QPushButton.DialogPrimaryButton:pressed {{
    background-color: {primary_dark};
}}

/* Tab Styling */
QTabBar::tab:selected {{
    background: {primary};
    color: #ffffff;
    font-weight: 500;
}}

QTabBar::tab:hover {{
    background: rgba({primary}, 0.7);
    color: #ffffff;
}}

/* Progress Bars */
QProgressBar.DataProgress::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {primary}, stop:1 {accent});
    border-radius: 3px;
}}

/* Data Frames */
QFrame.SatelliteDataFrame {{
    border: 2px solid {primary};
    border-radius: 8px;
    background: rgba({primary}, 0.1);
}}

/* Tab Buttons */
QPushButton.TabButton:checked {{
    background-color: {primary};
    color: #ffffff;
    border: 1px solid {accent};
}}

/* Date Range Display */
QLabel.DateRangeDisplay {{
    font-weight: bold;
    padding: 4px 8px;
    border-radius: 4px;
    background-color: rgba({primary}, 0.1);
}}

/* Date Picker Buttons */
QPushButton.DatePickerPrimary {{
    background-color: {date_picker};
    border: 1px solid {date_picker_light};
    border-radius: 4px;
    padding: 6px 12px;
    color: #ffffff;
    font-weight: bold;
}}

QPushButton.DatePickerPrimary:hover {{
    background-color: {date_picker_light};
}}

QPushButton.DatePickerPrimary:pressed {{
    background-color: {date_picker_dark};
}}

/* Status Colors */
QLabel.StatusSuccess {{
    color: {success};
    font-weight: bold;
    padding: 8px;
    border-radius: 4px;
    background-color: rgba({success}, 0.1);
}}

QLabel.StatusError {{
    color: {error};
    font-weight: bold;
    padding: 8px;
    border-radius: 4px;
    background-color: rgba({error}, 0.1);
}}

QLabel.StatusWarning {{
    color: {warning};
    font-weight: bold;
    padding: 8px;
    border-radius: 4px;
    background-color: rgba({warning}, 0.1);
}}

QLabel.StatusInfo {{
    color: {info};
    font-weight: bold;
    padding: 8px;
    border-radius: 4px;
    background-color: rgba({info}, 0.1);
}}
"""

    def apply_theme(self, app: QApplication, theme_name: str | None = None) -> None:
        """Apply theme with dynamic color support."""
        if theme_name is None:
            theme_name = self._current_theme

        # Apply base qt-material theme
        super().apply_theme(app, theme_name)

        # Update theme colors for the new theme
        self._current_theme = theme_name
        self._extract_theme_colors()

        # Apply dynamic overrides
        if self._custom_overrides_enabled:
            self._apply_dynamic_overrides(app)

        # Force refresh all widgets to pick up new theme
        DynamicThemeManager._refresh_all_widgets(app)

    @staticmethod
    def _refresh_all_widgets(app: QApplication) -> None:
        """Force refresh all widgets in the application to pick up theme changes."""
        try:
            # Get all top-level widgets
            for widget in app.allWidgets():
                if widget.isTopLevel():
                    WidgetFactory.update_all_widget_styles(widget)
        except ImportError as e:
            LOGGER.warning("Failed to refresh widget styles: %s", e)

    def _apply_dynamic_overrides(self, app: QApplication) -> None:
        """Apply dynamic CSS overrides based on current theme colors."""
        try:
            # Extract additional colors from the applied palette
            palette_colors = DynamicThemeManager._extract_palette_colors(app)
            self._theme_colors.update(palette_colors)

            # Generate dynamic CSS
            dynamic_css = self._create_dynamic_overrides()

            # Get existing stylesheet and append our dynamic overrides
            existing_style = app.styleSheet()
            combined_style = existing_style + "\n" + dynamic_css
            app.setStyleSheet(combined_style)

            LOGGER.info("Applied dynamic theme overrides for %s", self._current_theme)
            LOGGER.debug("Theme colors: %s", self._theme_colors)
        except Exception:
            LOGGER.exception("Failed to apply dynamic overrides")
            # Fall back to parent implementation
            super()._apply_custom_overrides(app)

    def get_theme_color(self, color_key: str) -> str | None:
        """Get a specific color from the current theme.

        Args:
            color_key: The color key (e.g., 'primary', 'accent', 'success')

        Returns:
            The color hex value or None if not found
        """
        return self._theme_colors.get(color_key)

    def get_all_theme_colors(self) -> dict[str, str]:
        """Get all colors for the current theme.

        Returns:
            dict[str, str]: Copy of all theme colors.
        """
        return self._theme_colors.copy()

    def create_themed_stylesheet(self, widget_class: str, properties: dict[str, str]) -> str:
        """Create a stylesheet for a widget using theme colors.

        Args:
            widget_class: The widget class selector (e.g., 'QPushButton.MyButton')
            properties: CSS properties with color placeholders

        Returns:
            Formatted CSS string
        """
        css_lines = [f"{widget_class} {{"]

        for prop, value in properties.items():
            # Replace color placeholders
            css_value = value
            for color_key, color_value in self._theme_colors.items():
                css_value = css_value.replace(f"{{{color_key}}}", color_value)
            css_lines.append(f"    {prop}: {css_value};")

        css_lines.append("}")
        return "\n".join(css_lines)
