#!/usr/bin/env python3
"""
Debug script for testing the EnhancedIntegrityCheckTab with UnifiedDateRangeSelector.

This script creates a standalone window with the EnhancedIntegrityCheckTab
to verify that the UnifiedDateRangeSelector integration works correctly.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add repository root to Python path
repo_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, repo_root)

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

from goesvfi.integrity_check.enhanced_gui_tab import EnhancedIntegrityCheckTab
from goesvfi.integrity_check.enhanced_view_model import EnhancedIntegrityCheckViewModel


class DebugWindow(QMainWindow):
    """Debug window for testing the EnhancedIntegrityCheckTab."""

    def __init__(self):
        """Initialize the debug window."""
        super().__init__()

        self.setWindowTitle("Debug Enhanced Integrity Tab")
        self.setGeometry(100, 100, 1200, 800)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create layout
        layout = QVBoxLayout(central_widget)

        # Create view model
        self.view_model = EnhancedIntegrityCheckViewModel()

        # Initialize with default values
        yesterday = datetime.now() - timedelta(days=1)
        self.view_model.start_date = yesterday.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        self.view_model.end_date = yesterday.replace(
            hour=23, minute=59, second=59, microsecond=0
        )
        self.view_model.base_directory = Path.home() / "Desktop" / "GOES_Data"

        # Create the EnhancedIntegrityCheckTab
        self.tab = EnhancedIntegrityCheckTab(self.view_model, self)
        layout.addWidget(self.tab)

        # Register debug handlers
        self.tab.date_range_changed.connect(self._on_date_changed)
        self.tab.directory_selected.connect(self._on_directory_changed)

        # Set up a timer to verify the date range after initialization
        QTimer.singleShot(500, self._verify_initial_state)

    def _on_date_changed(self, start_date, end_date):
        """Handle date range changes."""
        print(f"Date range changed: {start_date.isoformat()} to {end_date.isoformat()}")

    def _on_directory_changed(self, directory):
        """Handle directory changes."""
        print(f"Directory changed: {directory}")

    def _verify_initial_state(self):
        """Verify the initial state of the tab."""
        # Get current date range from the date selector
        start, end = self.tab.date_selector.get_date_range()
        print(f"Initial date range: {start.isoformat()} to {end.isoformat()}")

        # Verify the range matches the view model
        view_model_range = (self.view_model.start_date, self.view_model.end_date)
        selector_range = (start, end)

        if view_model_range == selector_range:
            print("✅ Date range initialized correctly")
        else:
            print("❌ Date range mismatch between view model and selector")
            print(
                f"View model: {view_model_range[0].isoformat()} to {view_model_range[1].isoformat()}"
            )
            print(
                f"Selector:   {selector_range[0].isoformat()} to {selector_range[1].isoformat()}"
            )


def main():
    """Run the debug application."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Use Fusion style for better dark mode support

    # Set dark palette
    dark_palette = app.palette()
    dark_palette.setColor(dark_palette.ColorRole.Window, Qt.GlobalColor.darkGray)
    dark_palette.setColor(dark_palette.ColorRole.WindowText, Qt.GlobalColor.white)
    dark_palette.setColor(dark_palette.ColorRole.Base, Qt.GlobalColor.darkGray)
    dark_palette.setColor(dark_palette.ColorRole.AlternateBase, Qt.GlobalColor.gray)
    dark_palette.setColor(dark_palette.ColorRole.ToolTipBase, Qt.GlobalColor.darkGray)
    dark_palette.setColor(dark_palette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    dark_palette.setColor(dark_palette.ColorRole.Text, Qt.GlobalColor.white)
    dark_palette.setColor(dark_palette.ColorRole.Button, Qt.GlobalColor.darkGray)
    dark_palette.setColor(dark_palette.ColorRole.ButtonText, Qt.GlobalColor.white)
    dark_palette.setColor(dark_palette.ColorRole.BrightText, Qt.GlobalColor.red)
    dark_palette.setColor(dark_palette.ColorRole.Link, Qt.GlobalColor.blue)
    dark_palette.setColor(dark_palette.ColorRole.Highlight, Qt.GlobalColor.cyan)
    dark_palette.setColor(dark_palette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(dark_palette)

    window = DebugWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
