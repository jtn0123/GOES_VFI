#!/usr/bin/env python3
"""
Test script for the Combined Integrity and Imagery Tab.

This script launches a standalone window with the combined tab for testing purposes.
It creates all necessary components to support both tabs.
"""

import logging
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

from goesvfi.integrity_check.cache_db import CacheDB
from goesvfi.integrity_check.combined_tab import CombinedIntegrityAndImageryTab
from goesvfi.integrity_check.enhanced_view_model import EnhancedIntegrityCheckViewModel
from goesvfi.integrity_check.reconciler import Reconciler
from goesvfi.integrity_check.remote.cdn_store import CDNStore
from goesvfi.integrity_check.remote.s3_store import S3Store

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


class TestWindow(QMainWindow):
    """Test window for the combined tab."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Combined Integrity and Imagery Tab Test")
        self.setGeometry(100, 100, 1200, 900)  # Increased height for better fit

        # Create central widget
        central = QWidget()
        self.setCentralWidget(central)

        # Create layout with reduced margins for more space efficiency
        layout = QVBoxLayout(central)
        layout.setContentsMargins(5, 5, 5, 5)  # Reduce margins
        layout.setSpacing(5)  # Reduce spacing between widgets

        # Create components for the integrity check tab
        self.setup_integrity_components()

        # Create and add the combined tab
        self.combined_tab = CombinedIntegrityAndImageryTab(self.integrity_check_vm)
        layout.addWidget(self.combined_tab)

        # Make sure directories exist for testing
        self.ensure_test_directories()

    def setup_integrity_components(self):
        """Set up components needed for the integrity check functionality."""
        # Create a temporary DB path
        db_path = Path.home() / ".goes_vfi" / "integrity_check.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create cache DB
        cache_db = CacheDB(path=db_path)

        # Create remote stores
        cdn_store = CDNStore(cache_db=cache_db)
        s3_store = S3Store(cache_db=cache_db)

        # Create reconciler
        reconciler = Reconciler(cache_db_path=db_path)

        # Create view model
        self.integrity_check_vm = EnhancedIntegrityCheckViewModel(
            base_reconciler=reconciler,
            cache_db=cache_db,
            cdn_store=cdn_store,
            s3_store=s3_store,
        )

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
    window = TestWindow()
    window.show()

    # Run the application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
