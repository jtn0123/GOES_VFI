#!/usr/bin/env python3
"""
Debug script for integrity check tab directory selection.
This script adds extra logging to diagnose issues when browsing for directories.
"""

import logging
import sys
import traceback
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("debug_integrity")

# Add console handler for immediate feedback
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
logger.addHandler(console)

# Add file handler for persistent logs
file_handler = logging.FileHandler("integrity_debug.log")
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)


def safe_directory_browse(parent=None, caption="Select Directory", start_dir=None):
    """
    A wrapped version of QFileDialog.getExistingDirectory with extra debugging.
    """
    logger.debug("Directory browse dialog requested")
    logger.debug(f"  Caption: {caption}")
    logger.debug(f"  Start directory: {start_dir}")

    try:
        # Default to home directory if start_dir is None or invalid
        if start_dir is None or not Path(start_dir).exists():
            start_dir = str(Path.home())
            logger.debug(f"  Using fallback start directory: {start_dir}")

        logger.debug("  Opening file dialog...")
        directory = QFileDialog.getExistingDirectory(
            parent, caption, start_dir, QFileDialog.Option.ShowDirsOnly
        )

        logger.debug(f"  Selected directory: {directory}")
        return directory
    except Exception as e:
        logger.error(f"Exception during directory browse: {e}")
        logger.error(traceback.format_exc())
        return None


class DebugWindow(QMainWindow):
    """Simple test window for debugging directory selection."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Directory Browse Debug")
        self.setGeometry(100, 100, 400, 200)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        # Layout
        layout = QVBoxLayout(central)

        # Test button
        self.browse_button = QPushButton("Browse Directory")
        self.browse_button.clicked.connect(self.test_directory_browse)
        layout.addWidget(self.browse_button)

    def test_directory_browse(self):
        """Test the directory browse function."""
        logger.debug("Test browse button clicked")
        try:
            directory = safe_directory_browse(self, "Select Test Directory")
            logger.debug(f"Browse function returned: {directory}")
        except Exception as e:
            logger.error(f"Uncaught exception in button handler: {e}")
            logger.error(traceback.format_exc())


if __name__ == "__main__":
    try:
        logger.debug("Starting debug application")
        app = QApplication(sys.argv)
        window = DebugWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        logger.error(f"Application error: {e}")
        logger.error(traceback.format_exc())
