#!/usr/bin/env python3
"""
Test script for the Enhanced GOES Imagery Tab.

This script launches a standalone window to test the enhanced GOES imagery
visualization features without running the full application.
"""

import logging
import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

from goesvfi.integrity_check.enhanced_imagery_tab import EnhancedGOESImageryTab

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


class MockWindow(QMainWindow):
    """Test window for the enhanced GOES imagery tab."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Enhanced GOES Imagery Tab Test")
        self.setGeometry(100, 100, 1200, 900)  # Increased height for better fit

        # Create central widget
        central = QWidget()
        self.setCentralWidget(central)

        # Create layout with reduced margins for more space efficiency
        layout = QVBoxLayout(central)
        layout.setContentsMargins(5, 5, 5, 5)  # Reduce margins
        layout.setSpacing(5)  # Reduce spacing between widgets

        # Create and add the imagery tab
        self.imagery_tab = EnhancedGOESImageryTab()
        layout.addWidget(self.imagery_tab)

        # Make sure directories exist for testing
        self.ensure_test_directories()

    def ensure_test_directories(self):
        """Ensure necessary directories exist for testing."""
        # Base directories
        dirs = [
            Path.home() / "Downloads" / "goes_imagery",
            Path.home() / "Downloads" / "goes_channels" / "visualized",
            Path.home() / "Downloads" / "goes_channels" / "rgb_composites",
            Path.home() / "Downloads" / "goes_channels" / "visualized" / "derived_products",
        ]

        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)


def main():
    """Main function to run the test application."""
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle("Fusion")

    # Create and show the window
    window = MockWindow()
    window.show()

    # Run the application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
