"""
Optimized dark mode styling for the GOES Integrity Check UI.

This module provides a consistent dark mode styling that's specifically
designed for the optimized UI components with improved contrast and
visual design.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QLinearGradient, QPalette
from PyQt6.QtWidgets import QApplication, QStyle


def apply_optimized_dark_palette(app: QApplication) -> None:
    """
    Apply an optimized dark mode color palette to the application.

    Args:
        app: QApplication instance
    """
    # Create palette
    dark_palette = QPalette()

    # Define optimized color palette with higher contrast
    # Base colors
    bg_dark = QColor(35, 35, 35)  # Darker background
    bg_medium = QColor(45, 45, 45)  # Medium background
    bg_light = QColor(55, 55, 55)  # Lighter background

    # Text colors
    text_bright = QColor(240, 240, 240)  # Bright text
    text_medium = QColor(200, 200, 200)  # Medium text
    text_disabled = QColor(130, 130, 130)  # Disabled text

    # Accent colors
    accent_blue = QColor(42, 130, 218)  # Blue accent
    accent_blue_light = QColor(70, 150, 230)  # Lighter blue
    accent_blue_dark = QColor(30, 110, 200)  # Darker blue

    # Status colors
    status_success = QColor(60, 180, 80)  # Success green
    status_warning = QColor(230, 180, 40)  # Warning yellow
    status_error = QColor(230, 70, 80)  # Error red

    # Basic window settings
    dark_palette.setColor(QPalette.ColorRole.Window, bg_medium)
    dark_palette.setColor(QPalette.ColorRole.WindowText, text_bright)
    dark_palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, text_disabled
    )

    # Text settings
    dark_palette.setColor(QPalette.ColorRole.Text, text_bright)
    dark_palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, text_disabled
    )

    # Button settings
    dark_palette.setColor(QPalette.ColorRole.Button, bg_light)
    dark_palette.setColor(QPalette.ColorRole.ButtonText, text_bright)
    dark_palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, text_disabled
    )

    # Base settings
    dark_palette.setColor(QPalette.ColorRole.Base, bg_dark)
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, bg_medium)

    # Highlight settings
    dark_palette.setColor(QPalette.ColorRole.Highlight, accent_blue)
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)

    # Link settings
    dark_palette.setColor(QPalette.ColorRole.Link, accent_blue_light)
    dark_palette.setColor(QPalette.ColorRole.LinkVisited, accent_blue)

    # ToolTip settings
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, bg_medium)
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, text_bright)

    # Apply the palette
    app.setPalette(dark_palette)


# Optimized dark stylesheet with better visual hierarchy and consistency
OPTIMIZED_DARK_STYLESHEET = """
/* Base styling */
QWidget {
    background-color: #2d2d2d;
    color: #f0f0f0;
    selection-background-color: #2a82da;
    selection-color: #ffffff;
    font-size: 11pt;
}

/* Main container styling */
#mainContainer {
    background-color: #252525;
    border-radius: 6px;
}

/* Control panel styling */
#controlPanel {
    background-color: #2d2d2d;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
}

.ControlGroup {
    background-color: #3a3a3a;
    border: 1px solid #545454;
    border-radius: 4px;
}

.ControlLabel {
    color: #f0f0f0;
    font-weight: bold;
    padding-right: 4px;
    font-size: 11px;
}

/* Information panel styling */
#infoPanel {
    background-color: #2d2d2d;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    padding: 10px;
}

#infoTitle {
    font-weight: bold;
    font-size: 13px;
    color: #f0f0f0;
    margin-bottom: 5px;
}

.InfoLabel {
    color: #d0d0d0;
    font-size: 11px;
}

.InfoValue {
    color: #f0f0f0;
    font-weight: bold;
    font-size: 11px;
}

.StatusLabel {
    padding: 3px 6px;
    border-radius: 4px;
    font-weight: bold;
    font-size: 11px;
}

.StatusLabel[status="success"] {
    background-color: #28a745;
    color: white;
}

.StatusLabel[status="error"] {
    background-color: #dc3545;
    color: white;
}

.StatusLabel[status="warning"] {
    background-color: #ffc107;
    color: black;
}

.StatusLabel[status="info"] {
    background-color: #17a2b8;
    color: white;
}

.StatusLabel[status="processing"] {
    background-color: #007bff;
    color: white;
}

/* Button styling */
QPushButton {
    background-color: #3a3a3a;
    color: #f0f0f0;
    border: 1px solid #545454;
    border-radius: 4px;
    padding: 4px 12px;
    min-height: 22px;
}

QPushButton:hover {
    background-color: #454545;
    border-color: #646464;
}

QPushButton:pressed {
    background-color: #2a82da;
    border-color: #1a72ca;
    color: white;
}

QPushButton:checked {
    background-color: #2a82da;
    border-color: #2a82da;
    color: white;
}

QPushButton:disabled {
    background-color: #2d2d2d;
    color: #777777;
    border-color: #3d3d3d;
}

QPushButton.ActionButton {
    background-color: #2a82da;
    color: white;
    border: none;
    font-weight: bold;
}

QPushButton.ActionButton:hover {
    background-color: #3a92ea;
}

QPushButton.ActionButton:pressed {
    background-color: #1a72ca;
}

QPushButton.ActionButton:disabled {
    background-color: #3d3d3d;
    color: #777777;
}

QPushButton.DangerButton {
    background-color: #dc3545;
    color: white;
    border: none;
    font-weight: bold;
}

QPushButton.DangerButton:hover {
    background-color: #e04555;
}

QPushButton.DangerButton:pressed {
    background-color: #c02535;
}

QPushButton.DangerButton:disabled {
    background-color: #3d3d3d;
    color: #777777;
}

/* Radio button styling */
QRadioButton {
    color: #f0f0f0;
    spacing: 8px;
    padding: 2px 4px;
    border-radius: 3px;
}

QRadioButton:hover {
    background-color: #3d3d3d;
}

QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border-radius: 7px;
    border: 1px solid #646464;
}

QRadioButton::indicator:unchecked {
    background-color: #2d2d2d;
}

QRadioButton::indicator:checked {
    background-color: #2a82da;
    border: 1px solid #2a82da;
}

QRadioButton::indicator:checked:disabled {
    background-color: #555555;
    border: 1px solid #555555;
}

/* Progress bar styling */
QProgressBar {
    border: 1px solid #545454;
    border-radius: 3px;
    text-align: center;
    height: 16px;
    background-color: #2d2d2d;
    color: #f0f0f0;
}

QProgressBar::chunk {
    background-color: #2a82da;
    border-radius: 2px;
}

/* Scrollbar styling */
QScrollBar:vertical {
    border: none;
    background-color: #2d2d2d;
    width: 12px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #3d3d3d;
    min-height: 30px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background-color: #4d4d4d;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background-color: none;
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background-color: #2d2d2d;
    height: 12px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background-color: #3d3d3d;
    min-width: 30px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #4d4d4d;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    border: none;
    background-color: none;
    width: 0px;
}

/* Tooltip styling */
QToolTip {
    background-color: #3a3a3a;
    color: #f0f0f0;
    border: 1px solid #545454;
    padding: 4px;
    border-radius: 3px;
}

/* QComboBox styling */
QComboBox {
    background-color: #3a3a3a;
    border: 1px solid #555555;
    border-radius: 3px;
    padding: 4px 8px;
    min-width: 120px;
    color: #f0f0f0;
    selection-background-color: #2a82da;
}

QComboBox:hover {
    background-color: #454545;
    border-color: #656565;
}

QComboBox:focus {
    border-color: #2a82da;
}

QComboBox:disabled {
    background-color: #2d2d2d;
    color: #777777;
    border-color: #3d3d3d;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 20px;
    border-left: 1px solid #555555;
    border-top-right-radius: 3px;
    border-bottom-right-radius: 3px;
}

QComboBox::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
    border-style: solid;
    border-width: 5px 5px 0 5px;
    border-color: #f0f0f0 transparent transparent transparent;
}

QComboBox QAbstractItemView {
    background-color: #3a3a3a;
    border: 1px solid #555555;
    border-radius: 3px;
    selection-background-color: #2a82da;
    selection-color: #ffffff;
    padding: 4px;
    outline: none;
}

QComboBox QAbstractItemView::item {
    min-height: 24px;
    padding: 4px 8px;
    border-radius: 2px;
}

QComboBox QAbstractItemView::item:hover {
    background-color: #454545;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #2a82da;
    color: white;
}
"""
