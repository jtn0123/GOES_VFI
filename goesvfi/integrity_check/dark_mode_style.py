"""
Dark mode stylesheets for the improved UI components.

This module provides consistent dark mode styling that matches the main application's
look and feel.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication


def apply_dark_mode_palette(app: QApplication) -> None:
    """
    Apply a dark mode color palette to the entire application.

    Args:
        app: QApplication instance
    """
    dark_palette = QPalette()

    # Base colors
    dark_color = QColor(45, 45, 45)
    disabled_color = QColor(70, 70, 70)
    text_color = QColor(240, 240, 240)
    highlight_color = QColor(42, 130, 218)
    link_color = QColor(42, 130, 218)

    # Window colors
    dark_palette.setColor(QPalette.ColorRole.Window, dark_color)
    dark_palette.setColor(QPalette.ColorRole.WindowText, text_color)
    dark_palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.WindowText,
        QColor(127, 127, 127),
    )

    # Base and alternate base
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(36, 36, 36))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))

    # Text
    dark_palette.setColor(QPalette.ColorRole.Text, text_color)
    dark_palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(127, 127, 127)
    )

    # Button
    dark_palette.setColor(QPalette.ColorRole.Button, dark_color)
    dark_palette.setColor(QPalette.ColorRole.ButtonText, text_color)
    dark_palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor(127, 127, 127),
    )

    # Highlight
    dark_palette.setColor(QPalette.ColorRole.Highlight, highlight_color)
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)

    # Link
    dark_palette.setColor(QPalette.ColorRole.Link, link_color)

    # Set the palette
    app.setPalette(dark_palette)


DARK_MODE_STYLESHEET = """
/* General widget styling */
QWidget {
    background-color: #2d2d2d;
    color: #f0f0f0;
    selection-background-color: #2a82da;
    selection-color: #ffffff;
}

/* Push buttons */
QPushButton {
    background-color: #3a3a3a;
    border: 1px solid #545454;
    border-radius: 4px;
    padding: 6px 12px;
    min-width: 80px;
    color: #f0f0f0;
}

QPushButton:hover {
    background-color: #454545;
    border-color: #646464;
}

QPushButton:pressed {
    background-color: #2a82da;
    border-color: #2a82da;
}

QPushButton:disabled {
    background-color: #222222;
    border-color: #444444;
    color: #777777;
}

/* Combo boxes and line edits */
QComboBox, QLineEdit, QSpinBox, QDateEdit, QTimeEdit {
    background-color: #363636;
    border: 1px solid #545454;
    border-radius: 4px;
    padding: 5px;
    color: #f0f0f0;
}

QComboBox:hover, QLineEdit:hover, QSpinBox:hover, QDateEdit:hover, QTimeEdit:hover {
    border-color: #646464;
}

QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDateEdit:focus, QTimeEdit:focus {
    border-color: #2a82da;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid #545454;
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
}

QComboBox::down-arrow {
    image: url(":/icons/down_arrow.png");
}

/* Progress bar */
QProgressBar {
    border: 1px solid #545454;
    border-radius: 4px;
    text-align: center;
    height: 20px;
    background-color: #363636;
    color: #f0f0f0;
}

QProgressBar::chunk {
    background-color: #2a82da;
    width: 20px;
}

/* Table and tree views */
QTreeView, QTableView {
    background-color: #242424;
    border: 1px solid #545454;
    alternate-background-color: #353535;
    selection-background-color: #2a82da;
    selection-color: #ffffff;
    gridline-color: #3a3a3a;
}

QTreeView::item, QTableView::item {
    padding: 5px;
}

QHeaderView::section {
    background-color: #3a3a3a;
    border: 1px solid #545454;
    padding: 5px;
    font-weight: bold;
    color: #f0f0f0;
}

/* Group box and frames */
QGroupBox, QFrame {
    border: 1px solid #545454;
    border-radius: 4px;
    margin-top: 12px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #f0f0f0;
}

/* Calendar widget */
QCalendarWidget QToolButton {
    background-color: #2d2d2d;
    color: #f0f0f0;
    height: 30px;
    width: 150px;
    icon-size: 24px, 24px;
    border: 1px solid #545454;
}

QCalendarWidget QMenu {
    background-color: #363636;
    color: #f0f0f0;
}

QCalendarWidget QSpinBox {
    background-color: #363636;
    color: #f0f0f0;
    selection-background-color: #2a82da;
    selection-color: #ffffff;
}

QCalendarWidget QTableView {
    alternate-background-color: #353535;
}

/* Scroll bars */
QScrollBar:vertical {
    border: none;
    background-color: #2d2d2d;
    width: 12px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #545454;
    min-height: 30px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background-color: #646464;
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
    background-color: #545454;
    min-width: 30px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #646464;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    border: none;
    background-color: none;
    width: 0px;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #545454;
    background-color: #2d2d2d;
}

QTabBar::tab {
    background-color: #3a3a3a;
    border: 1px solid #545454;
    padding: 8px 12px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #2a82da;
    border-color: #2a82da;
    color: #ffffff;
}

QTabBar::tab:!selected:hover {
    background-color: #454545;
}

/* Labels */
QLabel {
    color: #f0f0f0;
}

/* Tooltip */
QToolTip {
    background-color: #363636;
    color: #f0f0f0;
    border: 1px solid #545454;
    padding: 5px;
}

/* Specific styling for results/status colors */
.success-text {
    color: #28a745;
}

.error-text {
    color: #dc3545;
}

.warning-text {
    color: #ffc107;
}

.info-text {
    color: #2a82da;
}
"""
