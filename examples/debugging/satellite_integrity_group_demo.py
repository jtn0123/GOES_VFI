#!/usr/bin/env python3
"""
Demo of the Satellite Integrity Tab Group.

This script demonstrates the integrated Satellite Integrity Tab Group
that combines date selection, timeline visualization, and results organization
in a cohesive interface designed to bridge GOES imagery and file integrity.
"""

import os
import sys
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path

# Add the repository root to the Python path
repo_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, repo_root)

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from goesvfi.integrity_check.enhanced_view_model import EnhancedIntegrityCheckViewModel

# Import dark mode styling
from goesvfi.integrity_check.optimized_dark_mode import (
    OPTIMIZED_DARK_STYLESHEET,
    apply_optimized_dark_palette,
)
from goesvfi.integrity_check.satellite_integrity_tab_group import (
    SatelliteIntegrityTabGroup,
)
from goesvfi.integrity_check.thread_cache_db import ThreadLocalCacheDB
from goesvfi.integrity_check.view_model import MissingTimestamp
from goesvfi.utils import log


# Define a simple Satellite enum for demonstration
class Satellite(Enum):
    GOES16 = auto()
    GOES18 = auto()


class SatelliteIntegrityGroupDemo(QMainWindow):
    """Main demo window for the Satellite Integrity Tab Group."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Satellite Integrity Tab Group Demo")
        self.resize(1200, 800)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create layout
        main_layout = QVBoxLayout(central_widget)

        # Create thread-safe cache for demo
        thread_safe_cache = ThreadLocalCacheDB()

        # Create view model
        downloads_dir = os.path.expanduser("~/Downloads")
        self.view_model = EnhancedIntegrityCheckViewModel(cache_db=thread_safe_cache)
        self.view_model.base_directory = downloads_dir

        # Set up attributes for demo - use private attributes directly
        self.view_model._can_start_scan = True
        self.view_model._total_expected = 0
        self.view_model._missing_count = 0
        self.view_model._is_scanning = False
        self.view_model._is_downloading = False
        self.view_model._status_message = "Ready"

        # Set demo data
        self._generate_demo_data()

        # Create a frame with description
        description_frame = QFrame()
        description_frame.setObjectName("descriptionFrame")
        description_frame.setStyleSheet(
            """
            #descriptionFrame {
                background-color: #2d2d2d;
                border: 1px solid #454545;
                border-radius: 4px;
                padding: 10px;
                margin-bottom: 10px;
            }
        """
        )
        desc_layout = QVBoxLayout(description_frame)

        title = QLabel("Satellite Integrity Tab Group Demo")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        desc_layout.addWidget(title)

        description = QLabel(
            "This demo showcases the integrated Satellite Integrity Tab Group component "
            "that combines date selection, timeline visualization, and results organization "
            "in a cohesive interface. It is designed to bridge GOES imagery and file integrity "
            "tabs in the main application."
        )
        description.setWordWrap(True)
        desc_layout.addWidget(description)

        implementation_notes = QLabel(
            "Implementation Notes:\n"
            "- The tabs share data and selections between them\n"
            "- Date selections in one tab propagate to others\n"
            "- Timeline selections highlight matching items in the results\n"
            "- The interface uses consistent styling and organization"
        )
        implementation_notes.setStyleSheet("margin-top: 5px;")
        desc_layout.addWidget(implementation_notes)

        # Add description frame to main layout
        main_layout.addWidget(description_frame)

        # Create the satellite integrity tab group
        self.satellite_integrity_tabs = SatelliteIntegrityTabGroup()

        # Set data for the tab group
        self.satellite_integrity_tabs.set_data(
            self.view_model.missing_items,
            self.view_model.start_date,
            self.view_model.end_date,
            self.view_model.total_expected,
            60,  # Assume hourly data
        )

        # Connect tab group signals
        self.satellite_integrity_tabs.dateRangeSelected.connect(
            self._handle_date_range_selected
        )
        self.satellite_integrity_tabs.timestampSelected.connect(
            self._handle_timestamp_selected
        )
        self.satellite_integrity_tabs.itemSelected.connect(self._handle_item_selected)
        self.satellite_integrity_tabs.downloadRequested.connect(
            self._handle_download_requested
        )
        self.satellite_integrity_tabs.viewRequested.connect(self._handle_view_requested)

        # Add tab group to main layout
        main_layout.addWidget(self.satellite_integrity_tabs, 1)  # Give stretch priority

        # Add actions panel at the bottom
        actions_panel = self._create_actions_panel()
        main_layout.addWidget(actions_panel)

        # Status bar
        self.statusBar().showMessage("Ready")

    def _generate_demo_data(self) -> None:
        """Generate demo data for the visualizations."""
        # Create timestamps spanning the last 7 days, one per hour
        self.view_model.start_date = datetime.now() - timedelta(days=7)
        self.view_model.end_date = datetime.now()

        # Generate missing items
        missing_items = []

        # Create timestamps from the last 7 days, one per hour
        base_time = datetime.now() - timedelta(days=7)
        end_time = datetime.now()

        total_hours = int((end_time - base_time).total_seconds() / 3600)
        self.view_model._total_expected = total_hours  # Use private attribute

        for i in range(total_hours):
            timestamp = base_time + timedelta(hours=i)

            # Create missing timestamp with different statuses
            expected_filename = (
                f"OR_ABI-L1b-RadF-M6C13_G16_{timestamp.strftime('%Y%j%H%M%S')}.nc"
            )

            item = MissingTimestamp(timestamp, expected_filename)

            # Set status based on pattern
            if i % 10 == 0:
                # Downloaded
                item.is_downloaded = True
                item.local_path = f"/tmp/GOES/OR_ABI-L1b-RadF-M6C13_G16_{timestamp.strftime('%Y%j%H%M%S')}.nc"
            elif i % 10 == 1:
                # Downloading
                item.is_downloading = True
            elif i % 10 == 2:
                # Error
                item.download_error = (
                    "Connection timeout while downloading from S3 bucket"
                )
            elif i % 10 >= 7:
                # Missing
                pass
            elif i % 10 == 3:
                # Another error
                item.download_error = (
                    "404 Not Found: The specified key does not exist [Error 404]"
                )
            elif i % 10 == 4:
                # Another error
                item.download_error = "S3 permissions error: Access denied [Error 403]"
            else:
                # Skip this item (available)
                continue

            # Add satellite attribute
            setattr(
                item, "satellite", Satellite.GOES16 if i % 2 == 0 else Satellite.GOES18
            )

            # Add source attribute
            setattr(item, "source", "s3" if i % 3 == 0 else "cdn")

            # Add progress attribute for downloading items
            if getattr(item, "is_downloading", False):
                setattr(item, "progress", 35 + (i * 5) % 60)

            missing_items.append(item)

        # Set properties that would normally be set during a scan
        self.view_model._missing_items = missing_items
        self.view_model._missing_count = len(missing_items)
        self.view_model._has_missing_items = True
        self.view_model._total_expected = (
            total_hours  # Make sure total_expected is set correctly
        )

    def _create_actions_panel(self) -> QFrame:
        """Create the actions panel at the bottom of the window."""
        panel = QFrame()
        panel.setObjectName("actionsPanel")
        panel.setStyleSheet(
            """
            #actionsPanel {
                background-color: #2d2d2d;
                border: 1px solid #454545;
                border-radius: 4px;
                padding: 10px;
                margin-top: 10px;
            }
        """
        )
        panel.setMaximumHeight(80)

        layout = QHBoxLayout(panel)

        layout.addWidget(QLabel("Integration Demo Actions:"))

        # Add buttons representing actions from other tabs
        scan_btn = QPushButton("Simulate Scan")
        scan_btn.clicked.connect(self._simulate_scan)
        layout.addWidget(scan_btn)

        download_btn = QPushButton("Download Selected")
        download_btn.clicked.connect(self._simulate_download)
        layout.addWidget(download_btn)

        integrity_btn = QPushButton("Check Integrity")
        integrity_btn.clicked.connect(self._simulate_integrity_check)
        layout.addWidget(integrity_btn)

        visualize_btn = QPushButton("Visualize Selected")
        visualize_btn.clicked.connect(self._simulate_visualization)
        layout.addWidget(visualize_btn)

        return panel

    def _handle_date_range_selected(self, start: datetime, end: datetime) -> None:
        """
        Handle date range selection.

        Args:
            start: Start date
            end: End date
        """
        self.statusBar().showMessage(
            f"Date range selected: {start.strftime('%Y-%m-%d %H:%M')} to {end.strftime('%Y-%m-%d %H:%M')}"
        )

    def _handle_timestamp_selected(self, timestamp: datetime) -> None:
        """
        Handle timestamp selection.

        Args:
            timestamp: Selected timestamp
        """
        self.statusBar().showMessage(
            f"Timestamp selected: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        )

    def _handle_item_selected(self, item: MissingTimestamp) -> None:
        """
        Handle item selection.

        Args:
            item: Selected missing timestamp
        """
        self.statusBar().showMessage(
            f"Item selected: {item.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {item.expected_filename}"
        )

    def _handle_download_requested(self, item: MissingTimestamp) -> None:
        """
        Handle download request.

        Args:
            item: Missing timestamp to download
        """
        self.statusBar().showMessage(f"Download requested: {item.expected_filename}")

    def _handle_view_requested(self, item: MissingTimestamp) -> None:
        """
        Handle view request.

        Args:
            item: Missing timestamp to view
        """
        self.statusBar().showMessage(f"View requested: {item.expected_filename}")

    def _simulate_scan(self) -> None:
        """Simulate a scan action from the integrity tab."""
        self.statusBar().showMessage(
            "Scan simulation triggered (would normally scan for missing files)"
        )

    def _simulate_download(self) -> None:
        """Simulate a download action from the integrity tab."""
        self.statusBar().showMessage(
            "Download simulation triggered (would normally download missing files)"
        )

    def _simulate_integrity_check(self) -> None:
        """Simulate an integrity check action."""
        self.statusBar().showMessage(
            "Integrity check simulation triggered (would check file integrity)"
        )

    def _simulate_visualization(self) -> None:
        """Simulate a visualization action from the imagery tab."""
        self.statusBar().showMessage(
            "Visualization simulation triggered (would display selected data)"
        )


def main():
    """Main entry point for the demo application."""
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle("Fusion")

    # Apply optimized dark mode
    apply_optimized_dark_palette(app)
    app.setStyleSheet(OPTIMIZED_DARK_STYLESHEET)

    window = SatelliteIntegrityGroupDemo()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
