#!/usr/bin/env python
"""
Simple test runner for the GOES Imagery UI

This script demonstrates the UI integration for GOES satellite imagery
without requiring actual S3 or web requests.
"""

import sys
from unittest.mock import MagicMock, patch

# Patch boto3 and botocore before importing the module
with (
    patch("boto3.client"),
    patch("botocore.UNSIGNED", create=True),
    patch("requests.get"),
):
    from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

    from goesvfi.integrity_check.goes_imagery_tab import GOESImageryTab


class MockWindow(QMainWindow):
    """Test window for the GOES Imagery Tab."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("GOES Imagery Tab Test")
        self.setGeometry(100, 100, 1200, 800)

        # Create central widget
        central = QWidget()
        self.setCentralWidget(central)

        # Create layout
        layout = QVBoxLayout(central)

        # Create tab
        self.tab = GOESImageryTab()

        # Mock the imagery manager to avoid real network requests
        self.tab.imagery_manager = MagicMock()

        # Add tab to layout
        layout.addWidget(self.tab)


def main():
    """Main function to run the test."""
    # Create QApplication
    app = QApplication(sys.argv)

    # Create window
    window = MockWindow()
    window.show()

    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
