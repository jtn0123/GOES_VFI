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
    darker_color = QColor(36, 36, 36)
    text_color = QColor(240, 240, 240)
    disabled_text_color = QColor(127, 127, 127)
    highlight_color = QColor(42, 130, 218)
    link_color = QColor(42, 130, 218)

    # Window colors
    dark_palette.setColor(QPalette.ColorRole.Window, dark_color)
    dark_palette.setColor(QPalette.ColorRole.WindowText, text_color)
    dark_palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.WindowText,
        disabled_text_color,
    )

    # Base and alternate base
    dark_palette.setColor(QPalette.ColorRole.Base, darker_color)
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))

    # Text
    dark_palette.setColor(QPalette.ColorRole.Text, text_color)
    dark_palette.setColor(
        QPalette.ColorGroup.Disabled, 
        QPalette.ColorRole.Text, 
        disabled_text_color
    )

    # Button
    dark_palette.setColor(QPalette.ColorRole.Button, dark_color)
    dark_palette.setColor(QPalette.ColorRole.ButtonText, text_color)
    dark_palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        disabled_text_color,
    )

    # Highlight
    dark_palette.setColor(QPalette.ColorRole.Highlight, highlight_color)
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)

    # Link
    dark_palette.setColor(QPalette.ColorRole.Link, link_color)

    # Set the palette
    app.setPalette(dark_palette)


# Dark mode stylesheet for integrity check components
INTEGRITY_CHECK_DARK_STYLE = """
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
QComboBox, QLineEdit, QSpinBox, QDateEdit, QTimeEdit, QDateTimeEdit {
    background-color: #363636;
    border: 1px solid #545454;
    border-radius: 4px;
    padding: 5px;
    color: #f0f0f0;
}

QComboBox:hover, QLineEdit:hover, QSpinBox:hover, 
QDateEdit:hover, QTimeEdit:hover, QDateTimeEdit:hover {
    border-color: #646464;
}

QComboBox:focus, QLineEdit:focus, QSpinBox:focus, 
QDateEdit:focus, QTimeEdit:focus, QDateTimeEdit:focus {
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
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #f0f0f0;
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
    border-radius: 3px;
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
QGroupBox {
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

/* List widget */
QListWidget {
    background-color: #242424;
    border: 1px solid #545454;
    border-radius: 4px;
}

QListWidget::item {
    padding: 5px;
    border-bottom: 1px solid #3a3a3a;
}

QListWidget::item:selected {
    background-color: #2a82da;
    color: #ffffff;
}

QListWidget::item:hover {
    background-color: #454545;
}

/* Status labels */
QLabel {
    color: #f0f0f0;
}

/* Scroll bars */
QScrollBar:vertical {
    background-color: #2d2d2d;
    width: 12px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background-color: #545454;
    border-radius: 6px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #646464;
}

QScrollBar:horizontal {
    background-color: #2d2d2d;
    height: 12px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background-color: #545454;
    border-radius: 6px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #646464;
}

/* Tab widget */
QTabWidget::pane {
    border: 1px solid #545454;
    background-color: #2d2d2d;
}

QTabBar::tab {
    background-color: #3a3a3a;
    color: #f0f0f0;
    padding: 8px 16px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #2d2d2d;
    border-bottom: 2px solid #2a82da;
}

QTabBar::tab:hover {
    background-color: #454545;
}

/* Progress dialog */
QProgressDialog {
    background-color: #2d2d2d;
    color: #f0f0f0;
}

QProgressDialog QLabel {
    color: #f0f0f0;
}

/* Message box */
QMessageBox {
    background-color: #2d2d2d;
    color: #f0f0f0;
}

QMessageBox QPushButton {
    min-width: 80px;
}
"""


def apply_integrity_check_dark_mode(widget) -> None:
    """
    Apply dark mode styling to integrity check widgets.
    
    Args:
        widget: The widget to apply styling to
    """
    widget.setStyleSheet(INTEGRITY_CHECK_DARK_STYLE)