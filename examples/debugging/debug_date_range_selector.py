#!/usr/bin/env python3
"""
Example script demonstrating the unified date range selector components.

This script shows how to use the UnifiedDateRangeSelector and CompactDateRangeSelector
components in a simple PyQt application.
"""

import sys
from datetime import datetime
from pathlib import Path

# Add repository root to Python path
repo_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, repo_root)

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from goesvfi.integrity_check.date_range_selector import (
    CompactDateRangeSelector,
    UnifiedDateRangeSelector,
)


class DateRangeDemoWindow(QMainWindow):
    """Demo window for date range selector components."""

    def __init__(self) -> None:
        """Initialize the demo window."""
        super().__init__()

        self.setWindowTitle("Date Range Selector Demo")
        self.setMinimumSize(800, 600)

        # Create central widget
        central = QWidget()
        self.setCentralWidget(central)

        # Create main layout
        main_layout = QVBoxLayout(central)

        # Add header
        header = QLabel("Date Range Selector Components")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header)

        # Create tab widget for different examples
        tabs = QTabWidget()

        # Add tabs for different selector variants
        tabs.addTab(self._create_standard_tab(), "Standard Selector")
        tabs.addTab(self._create_compact_tab(), "Compact Selector")
        tabs.addTab(self._create_variants_tab(), "Variants")

        main_layout.addWidget(tabs)

        # Add info display at bottom
        self.info_frame = QFrame()
        self.info_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.info_frame.setStyleSheet("background-color: #f0f0f0; padding: 10px;")
        info_layout = QVBoxLayout(self.info_frame)

        info_layout.addWidget(QLabel("Selected Date Range:"))
        self.date_display = QLabel("No selection yet")
        self.date_display.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.date_display)

        main_layout.addWidget(self.info_frame)

    def _create_standard_tab(self) -> QWidget:
        """Create tab with standard date range selector."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Add description
        desc = QLabel(
            "The UnifiedDateRangeSelector provides a complete date selection experience "
            "with manual date entry, visual date picker, and preset buttons."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Add selector
        selector = UnifiedDateRangeSelector()
        selector.dateRangeSelected.connect(self._update_date_display)
        layout.addWidget(selector)

        # Add spacer
        layout.addStretch()

        return tab

    def _create_compact_tab(self) -> QWidget:
        """Create tab with compact date range selector."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Add description
        desc = QLabel(
            "The CompactDateRangeSelector provides a streamlined date selection experience "
            "with a dropdown for presets and a compact display, ideal for toolbar or header usage."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Container for compact selector
        compact_container = QWidget()
        compact_layout = QHBoxLayout(compact_container)

        # Add selector
        selector = CompactDateRangeSelector()
        selector.dateRangeSelected.connect(self._update_date_display)
        compact_layout.addWidget(selector)

        # Add container to layout
        layout.addWidget(compact_container)

        # Create example toolbar with compact selector
        toolbar_example = QFrame()
        toolbar_example.setFrameShape(QFrame.Shape.StyledPanel)
        toolbar_example.setStyleSheet("background-color: #e0e0e0; padding: 5px;")
        toolbar_layout = QHBoxLayout(toolbar_example)

        # Add controls to toolbar
        toolbar_layout.addWidget(QPushButton("Home"))
        toolbar_layout.addWidget(QPushButton("Browse"))

        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        toolbar_layout.addWidget(separator)

        # Add compact selector
        toolbar_selector = CompactDateRangeSelector()
        toolbar_selector.dateRangeSelected.connect(self._update_date_display)
        toolbar_layout.addWidget(toolbar_selector)

        toolbar_layout.addStretch()
        toolbar_layout.addWidget(QPushButton("Settings"))

        # Add toolbar example
        layout.addWidget(QLabel("Example toolbar integration:"))
        layout.addWidget(toolbar_example)

        # Add spacer
        layout.addStretch()

        return tab

    def _create_variants_tab(self) -> QWidget:
        """Create tab showing different selector variants."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Add description
        desc = QLabel(
            "The UnifiedDateRangeSelector can be customized with different options " "to fit various UI needs."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Horizontal variant
        horiz_group = QGroupBox("Horizontal Layout (default)")
        horiz_layout = QVBoxLayout(horiz_group)

        selector_h = UnifiedDateRangeSelector(layout_direction=Qt.Orientation.Horizontal)
        selector_h.dateRangeSelected.connect(self._update_date_display)
        horiz_layout.addWidget(selector_h)

        layout.addWidget(horiz_group)

        # Vertical variant
        vert_group = QGroupBox("Vertical Layout")
        vert_layout = QVBoxLayout(vert_group)

        selector_v = UnifiedDateRangeSelector(layout_direction=Qt.Orientation.Vertical)
        selector_v.dateRangeSelected.connect(self._update_date_display)
        vert_layout.addWidget(selector_v)

        layout.addWidget(vert_group)

        # Minimal variant
        minimal_group = QGroupBox("Minimal Variant (No Presets)")
        minimal_layout = QVBoxLayout(minimal_group)

        selector_min = UnifiedDateRangeSelector(include_presets=False)
        selector_min.dateRangeSelected.connect(self._update_date_display)
        minimal_layout.addWidget(selector_min)

        layout.addWidget(minimal_group)

        return tab

    def _update_date_display(self, start: datetime, end: datetime) -> None:
        """Update the date display with the selected range."""
        # Format the date range for display
        if start.date() == end.date():
            # Same day
            display_text = f"{start.strftime('%Y-%m-%d')}, " f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}"
        else:
            # Different days
            display_text = f"{start.strftime('%Y-%m-%d %H:%M')} - " f"{end.strftime('%Y-%m-%d %H:%M')}"

        self.date_display.setText(display_text)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Set fusion style for a consistent look across platforms
    app.setStyle("Fusion")

    window = DateRangeDemoWindow()
    window.show()

    sys.exit(app.exec())
