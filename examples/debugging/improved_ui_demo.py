#!/usr/bin/env python3
"""
Demo of the improved UI components for the integrity check tab.

This script demonstrates the new UI components for the integrity check tab,
including the visual date picker, timeline visualization, and improved results organization.
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
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# Import dark mode styling
from goesvfi.integrity_check.dark_mode_style import (
    DARK_MODE_STYLESHEET,
    apply_dark_mode_palette,
)
from goesvfi.integrity_check.enhanced_view_model import EnhancedIntegrityCheckViewModel
from goesvfi.integrity_check.optimized_dark_mode import (
    OPTIMIZED_DARK_STYLESHEET,
    apply_optimized_dark_palette,
)
from goesvfi.integrity_check.optimized_timeline_tab import OptimizedTimelineTab
from goesvfi.integrity_check.results_organization import (
    ItemPreviewWidget,
    MissingItemsTreeView,
    ResultsSummaryWidget,
)
from goesvfi.integrity_check.thread_cache_db import ThreadLocalCacheDB
from goesvfi.integrity_check.timeline_visualization import (
    MissingDataCalendarView,
    TimelineVisualization,
)
from goesvfi.integrity_check.view_model import MissingTimestamp
from goesvfi.integrity_check.visual_date_picker import (
    TimelinePickerWidget,
    VisualDateRangePicker,
)
from goesvfi.utils import log


# Define a simple Satellite enum for demonstration
class Satellite(Enum):
    GOES16 = auto()
    GOES18 = auto()


class ImprovedUIDemo(QMainWindow):
    """Main demo window for the improved UI components."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Integrity Check UI Components Demo")
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

        # Create tabs for different components
        tabs = QTabWidget()

        # Tab 1: Date Selection
        date_tab = self._create_date_selection_tab()
        tabs.addTab(date_tab, "Date Selection")

        # Tab 2: Timeline Visualization
        timeline_tab = self._create_timeline_tab()
        tabs.addTab(timeline_tab, "Timeline Visualization")

        # Tab 3: Results Organization
        results_tab = self._create_results_tab()
        tabs.addTab(results_tab, "Results Organization")

        # Add tabs to layout
        main_layout.addWidget(tabs)

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

    def _create_date_selection_tab(self) -> QWidget:
        """Create the date selection component tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Add instructions
        instructions = QLabel(
            "This tab demonstrates the enhanced date selection components. "
            "Click the buttons below to open the different date picker dialogs."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Add visual date picker button
        visual_button = QPushButton("Open Visual Date Picker")
        visual_button.clicked.connect(self._open_visual_date_picker)
        layout.addWidget(visual_button)

        # Add timeline picker
        layout.addWidget(QLabel("Timeline Picker:"))

        self.timeline_picker = TimelinePickerWidget()
        self.timeline_picker.dateRangeSelected.connect(self._handle_timeline_selection)

        # Set date range
        self.timeline_picker.set_date_range(
            self.view_model.start_date, self.view_model.end_date
        )

        layout.addWidget(self.timeline_picker)

        # Add selected date range display
        self.date_range_label = QLabel("No date range selected")
        layout.addWidget(self.date_range_label)

        layout.addStretch()
        return tab

    def _create_timeline_tab(self) -> QWidget:
        """Create the optimized timeline visualization component tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

        # Add instructions
        instructions = QLabel(
            "This tab demonstrates the optimized timeline visualization components. "
            "Hover over the timeline to see details and click to select points."
        )
        instructions.setStyleSheet("padding: 5px 10px;")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Create optimized timeline tab with both visualizations
        self.optimized_timeline = OptimizedTimelineTab()
        self.optimized_timeline.timestampSelected.connect(
            self._handle_timestamp_selected
        )
        self.optimized_timeline.rangeSelected.connect(self._handle_timeline_selection)

        # Set data
        self.optimized_timeline.set_data(
            self.view_model.missing_items,
            self.view_model.start_date,
            self.view_model.end_date,
            60,  # Assume hourly data
        )

        layout.addWidget(self.optimized_timeline)

        # No need to add selected item display as it's included in the optimized component

        return tab

    def _create_results_tab(self) -> QWidget:
        """Create the results organization component tab."""
        tab = QWidget()
        layout = QHBoxLayout(tab)

        # Create a splitter for the components
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Tree view
        self.tree_view = MissingItemsTreeView()
        self.tree_view.itemSelected.connect(self._handle_item_selected)
        self.tree_view.set_items(self.view_model.missing_items)
        splitter.addWidget(self.tree_view)

        # Right side
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Top: Summary widget
        self.summary_widget = ResultsSummaryWidget()
        self.summary_widget.update_summary(
            self.view_model.missing_items, self.view_model.total_expected
        )
        right_layout.addWidget(self.summary_widget)

        # Bottom: Preview widget
        self.preview_widget = ItemPreviewWidget()
        right_layout.addWidget(self.preview_widget)

        # Connect download button
        self.preview_widget.download_btn.clicked.connect(self._handle_download_clicked)

        # Connect view button
        self.preview_widget.view_btn.clicked.connect(self._handle_view_clicked)

        splitter.addWidget(right_widget)

        # Set initial splitter sizes
        splitter.setSizes([400, 400])

        layout.addWidget(splitter)
        return tab

    def _open_visual_date_picker(self) -> None:
        """Open the visual date picker dialog."""
        dialog = VisualDateRangePicker(
            self, self.view_model.start_date, self.view_model.end_date
        )
        dialog.dateRangeSelected.connect(self._handle_date_range_selected)
        dialog.exec()

    def _handle_date_range_selected(self, start: datetime, end: datetime) -> None:
        """
        Handle date range selection from the visual picker.

        Args:
            start: Start date
            end: End date
        """
        self.view_model.start_date = start
        self.view_model.end_date = end

        # Update date range label
        self.date_range_label.setText(
            f"Selected range: {start.strftime('%Y-%m-%d %H:%M')} - "
            f"{end.strftime('%Y-%m-%d %H:%M')}"
        )

        # Update timeline picker
        self.timeline_picker.set_date_range(start, end)

        self.statusBar().showMessage(f"Date range selected: {start} - {end}")

    def _handle_timeline_selection(self, start: datetime, end: datetime) -> None:
        """
        Handle selection from the timeline widget.

        Args:
            start: Start date
            end: End date
        """
        self.view_model.start_date = start
        self.view_model.end_date = end

        # Update date range label
        self.date_range_label.setText(
            f"Selected range: {start.strftime('%Y-%m-%d %H:%M')} - "
            f"{end.strftime('%Y-%m-%d %H:%M')}"
        )

        self.statusBar().showMessage(f"Timeline selection: {start} - {end}")

    def _handle_timestamp_selected(self, timestamp: datetime) -> None:
        """
        Handle single timestamp selection.

        Args:
            timestamp: Selected timestamp
        """
        # Find matching item
        selected_item = None
        for item in self.view_model.missing_items:
            if (
                abs((item.timestamp - timestamp).total_seconds()) < 60
            ):  # Within a minute
                selected_item = item
                break

        if selected_item:
            # Update status bar
            self.statusBar().showMessage(f"Selected timestamp: {timestamp}")

            # Update preview
            self.preview_widget.set_item(selected_item)
        else:
            # Update status bar only
            self.statusBar().showMessage(f"No item found at {timestamp}")

    def _handle_item_selected(self, item: MissingTimestamp) -> None:
        """
        Handle item selection from the tree view.

        Args:
            item: Selected missing timestamp
        """
        self.statusBar().showMessage(f"Selected item: {item.timestamp}")

        # Update preview
        self.preview_widget.set_item(item)

    def _handle_download_clicked(self) -> None:
        """Handle download button click."""
        self.statusBar().showMessage("Download requested (demo only)")

    def _handle_view_clicked(self) -> None:
        """Handle view button click."""
        self.statusBar().showMessage("View file requested (demo only)")


def main():
    """Main entry point for the demo application."""
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle("Fusion")

    # Apply optimized dark mode instead of regular dark mode
    apply_optimized_dark_palette(app)
    app.setStyleSheet(OPTIMIZED_DARK_STYLESHEET)

    window = ImprovedUIDemo()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
