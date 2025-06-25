"""Theme management for the GUI application.

This module handles application theming, including dark theme styling.
"""

from PyQt6.QtWidgets import QWidget

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class ThemeManager:
    """Manages application themes and styling."""

    def __init__(self) -> None:
        """Initialize the theme manager."""
        self._dark_theme_stylesheet = self._create_dark_theme_stylesheet()

    def apply_dark_theme(self, widget: QWidget) -> None:
        """Apply dark theme styling to a widget.

        Args:
            widget: The widget to apply the theme to
        """
        LOGGER.debug("Applying dark theme to widget")
        widget.setStyleSheet(self._dark_theme_stylesheet)

    def _create_dark_theme_stylesheet(self) -> str:
        """Create the dark theme stylesheet.

        Returns:
            The complete dark theme stylesheet as a string
        """
        return """
            /* Main Window and General Styling */
            QWidget {
                background-color:  #2D2D2D;
                color:  #EFEFEF;
                font-family: Arial, Helvetica, sans;
            }

            /* Tab Widget Styling */
            QTabWidget::pane {
                border: 1px solid  #444444;
                background-color:  #2D2D2D;
            }

            QTabBar::tab {
                background-color:  #3D3D3D;
                color:  #EFEFEF;
                padding: 8px 12px;
                border: 1px solid  #444444;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }

            QTabBar::tab:selected {
                background-color:  #505050;
                border-bottom: none;
            }

            /* Group Box Styling */
            QGroupBox {
                border: 1px solid  #444444;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 1.5ex;
                font-weight: bold;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
            }

            /* Input Field Styling */
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background-color:  #3D3D3D;
                border: 1px solid  #555555;
                border-radius: 3px;
                padding: 5px;
                color:  #EFEFEF;
            }

            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border: 1px solid  #6C9BD1;
            }

            /* Button Styling */
            QPushButton {
                background-color:  #4A4A4A;
                border: 1px solid  #555555;
                border-radius: 3px;
                padding: 5px 15px;
                color:  #EFEFEF;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color:  #5A5A5A;
            }

            QPushButton:pressed {
                background-color:  #3A3A3A;
            }

            QPushButton:disabled {
                background-color:  #333333;
                color:  #777777;
            }

            /* Checkbox and Radio Button Styling */
            QCheckBox, QRadioButton {
                color:  #EFEFEF;
            }

            QCheckBox::indicator, QRadioButton::indicator {
                width: 13px;
                height: 13px;
                background-color:  #3D3D3D;
                border: 1px solid  #555555;
                border-radius: 2px;
            }

            QCheckBox::indicator:checked, QRadioButton::indicator:checked {
                background-color:  #6C9BD1;
                border: 1px solid  #6C9BD1;
            }

            /* Progress Bar Styling */
            QProgressBar {
                background-color:  #3D3D3D;
                border: 1px solid  #555555;
                border-radius: 3px;
                text-align: center;
            }

            QProgressBar::chunk {
                background-color:  #6C9BD1;
                border-radius: 2px;
            }

            /* Label Styling */
            QLabel {
                color:  #EFEFEF;
            }

            /* Status Bar Styling */
            QStatusBar {
                background-color:  #2D2D2D;
                border-top: 1px solid  #444444;
            }

            /* Splitter Styling */
            QSplitter::handle {
                background-color:  #444444;
            }

            /* ScrollBar Styling */
            QScrollBar:vertical {
                background-color:  #2D2D2D;
                width: 12px;
                border: none;
            }

            QScrollBar::handle:vertical {
                background-color:  #555555;
                min-height: 20px;
                border-radius: 6px;
            }

            QScrollBar::handle:vertical:hover {
                background-color:  #666666;
            }
        """
