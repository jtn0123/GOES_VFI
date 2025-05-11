"""
Combined Integrity Check and Satellite Visualization Tab

This module provides a comprehensive tab that includes the enhanced integrity check
functionality with integrated date selection, timeline visualization, results organization,
and GOES imagery visualization features in a unified interface.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .enhanced_gui_tab import EnhancedIntegrityCheckTab
from .enhanced_imagery_tab import EnhancedGOESImageryTab
from .enhanced_view_model import EnhancedIntegrityCheckViewModel
from .satellite_integrity_tab_group import OptimizedResultsTab, OptimizedTimelineTab
from .view_model import MissingTimestamp

# Configure logging
LOGGER = logging.getLogger(__name__)


class CombinedIntegrityAndImageryTab(QWidget):
    """
    Combined tab that includes file integrity and satellite visualization components.

    This tab contains:
    1. File Integrity - Verify and download missing imagery files with integrated date selection
    2. Timeline - Visualize data availability over time
    3. Results - Organize and manage results
    4. GOES Imagery - View and process satellite imagery
    """

    # Signals for communication between tabs
    dateRangeSelected = pyqtSignal(datetime, datetime)
    timestampSelected = pyqtSignal(datetime)
    itemSelected = pyqtSignal(MissingTimestamp)

    def __init__(
        self,
        view_model: EnhancedIntegrityCheckViewModel,
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Initialize the combined tab.

        Args:
            view_model: The EnhancedIntegrityCheckViewModel instance to use
            parent: Optional parent widget
        """
        super().__init__(parent)

        # Store view model reference
        self.view_model = view_model

        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create a more compact tab switcher using buttons in a horizontal layout
        tab_switcher = QWidget()
        tab_switcher.setMaximumHeight(40)  # Limit height for compactness
        switcher_layout = QHBoxLayout(tab_switcher)
        switcher_layout.setContentsMargins(5, 0, 5, 0)  # Minimal margins

        # Create the stacked widget (instead of tab widget)
        self.stacked_widget = QStackedWidget(self)

        # Create the four main components (removing separate Date Selection tab)
        # Create an enhanced integrity tab with the unified date range selector
        self.integrity_tab = EnhancedIntegrityCheckTab(view_model, self)

        # Create other tabs
        self.timeline_tab = OptimizedTimelineTab(parent=self)
        self.results_tab = OptimizedResultsTab(parent=self)
        self.imagery_tab = EnhancedGOESImageryTab(parent=self)

        # Add all pages to the stacked widget
        self.stacked_widget.addWidget(self.integrity_tab)  # Index 0
        self.stacked_widget.addWidget(self.timeline_tab)  # Index 1
        self.stacked_widget.addWidget(self.results_tab)  # Index 2
        self.stacked_widget.addWidget(self.imagery_tab)  # Index 3

        # Create switcher buttons (removed date selection button)
        self.integrity_button = QPushButton(self.tr("File Integrity"))
        self.timeline_button = QPushButton(self.tr("Timeline"))
        self.results_button = QPushButton(self.tr("Results"))
        self.imagery_button = QPushButton(self.tr("GOES Imagery"))

        # Style the buttons to look like tabs
        button_style = """
            QPushButton {
                background-color: #3a3a3a;
                color: #b0b0b0;
                border: none;
                padding: 5px 10px;
                border-bottom: 2px solid transparent;
            }
            QPushButton:checked, QPushButton:pressed {
                color: white;
                background-color: #444444;
                border-bottom: 2px solid #3498db;
            }
        """
        self.integrity_button.setStyleSheet(button_style)
        self.timeline_button.setStyleSheet(button_style)
        self.results_button.setStyleSheet(button_style)
        self.imagery_button.setStyleSheet(button_style)

        self.integrity_button.setCheckable(True)
        self.timeline_button.setCheckable(True)
        self.results_button.setCheckable(True)
        self.imagery_button.setCheckable(True)

        # Set fixed width for consistent appearance - slightly narrower for more tabs
        button_width = 110
        self.integrity_button.setMinimumWidth(button_width)
        self.timeline_button.setMinimumWidth(button_width)
        self.results_button.setMinimumWidth(button_width)
        self.imagery_button.setMinimumWidth(button_width)

        # Add to switcher layout (removed date selection button)
        switcher_layout.addWidget(self.integrity_button)
        switcher_layout.addWidget(self.timeline_button)
        switcher_layout.addWidget(self.results_button)
        switcher_layout.addWidget(self.imagery_button)
        switcher_layout.addStretch(1)  # Push buttons to the left

        # Connect button signals (updated indices)
        self.integrity_button.clicked.connect(lambda: self._switch_tab(0))
        self.timeline_button.clicked.connect(lambda: self._switch_tab(1))
        self.results_button.clicked.connect(lambda: self._switch_tab(2))
        self.imagery_button.clicked.connect(lambda: self._switch_tab(3))

        # Set initial state
        self.integrity_button.setChecked(True)

        # Add components to main layout
        layout.addWidget(tab_switcher)
        layout.addWidget(self.stacked_widget)

        # Initialize the satellite visualization tabs
        self._initialize_satellite_tabs()

        # Connect signals between tabs
        self._connect_tab_signals()

        LOGGER.info("Combined integrity and satellite visualization tab initialized")

    def _initialize_satellite_tabs(self) -> None:
        """Initialize all satellite-related tabs with data from the view model."""
        if hasattr(self.view_model, "missing_items") and self.view_model.missing_items:
            # Get the date range and interval from the view model
            start_date = self.view_model.start_date
            end_date = self.view_model.end_date
            # Get total expected count, default to current item count if not set
            items_count = len(self.view_model.missing_items)
            total_expected = getattr(self.view_model, "total_expected", items_count)

            # Determine the interval (assume hourly if not specified)
            interval_minutes = 60
            if hasattr(self.view_model, "expected_interval_minutes"):
                interval_minutes = self.view_model.expected_interval_minutes

            # Set the data for each tab
            # We update the date selector in the integrity tab
            tab = self.integrity_tab
            if hasattr(tab, "date_selector") and hasattr(
                tab.date_selector, "set_date_range"
            ):
                tab.date_selector.set_date_range(start_date, end_date)

            # Timeline Tab
            self.timeline_tab.set_data(
                self.view_model.missing_items, start_date, end_date, interval_minutes
            )

            # Results Tab
            self.results_tab.set_items(self.view_model.missing_items, total_expected)

            # Log initialization status
            items_count = len(self.view_model.missing_items)
            LOGGER.info("Satellite tabs initialized with %d items", items_count)

    def _connect_tab_signals(self) -> None:
        """Connect signals between tabs for integrated functionality."""
        # Connect integrity tab signals
        if hasattr(self.integrity_tab, "download_completed"):
            self.integrity_tab.download_completed.connect(self._on_download_completed)

        # Connect scan completion signal
        if hasattr(self.integrity_tab.view_model, "scan_completed"):
            self.integrity_tab.view_model.scan_completed.connect(
                self._on_scan_completed
            )

        # Connect missing items updated signal
        if hasattr(self.integrity_tab.view_model, "missing_items_updated"):
            # Connect missing items update signal
            view_model = self.integrity_tab.view_model
            view_model.missing_items_updated.connect(self._on_missing_items_updated)

        # Connect integrity tab directory selection
        if hasattr(self.integrity_tab, "directory_selected"):
            self.integrity_tab.directory_selected.connect(self._on_directory_selected)

        # Connect integrity tab date range selection
        if hasattr(self.integrity_tab, "date_range_changed"):
            self.integrity_tab.date_range_changed.connect(self._on_date_range_selected)
        elif hasattr(self.integrity_tab, "dateRangeSelected"):
            self.integrity_tab.dateRangeSelected.connect(self._on_date_range_selected)

        # Connect to the date_selector signal if available
        tab = self.integrity_tab
        if hasattr(tab, "date_selector") and hasattr(
            tab.date_selector, "dateRangeSelected"
        ):
            tab.date_selector.dateRangeSelected.connect(self._on_date_range_selected)

        # Connect unified date selector's signal from our date selection tab
        # This is already connected when we created the tab

        # Connect timeline tab signals
        self.timeline_tab.timestampSelected.connect(self._on_timestamp_selected)
        self.timeline_tab.rangeSelected.connect(self._on_date_range_selected)
        if hasattr(self.timeline_tab, "directorySelected"):
            self.timeline_tab.directorySelected.connect(self._on_directory_selected)

        # Connect results tab signals
        self.results_tab.itemSelected.connect(self._on_item_selected)
        self.results_tab.downloadRequested.connect(self._on_download_requested)
        self.results_tab.viewRequested.connect(self._on_view_requested)
        if hasattr(self.results_tab, "directorySelected"):
            self.results_tab.directorySelected.connect(self._on_directory_selected)

        # Connect imagery tab signals if available
        if hasattr(self.imagery_tab, "file_selected"):
            self.imagery_tab.file_selected.connect(self._on_imagery_file_selected)

    def _on_download_completed(self) -> None:
        """Handle download completion from integrity tab."""
        # Update satellite tabs with new data
        self._initialize_satellite_tabs()

    def _on_scan_completed(self, success: bool, message: str) -> None:
        """
        Handle scan completion from the integrity check tab.

        Args:
            success: Whether the scan was successful
            message: Status message
        """
        if success:
            LOGGER.info("Scan completed successfully: %s", message)
            # Update all tabs with the new data
            self._initialize_satellite_tabs()
        else:
            LOGGER.error("Scan failed: %s", message)

    def _on_missing_items_updated(self, items: list) -> None:
        """
        Handle missing items updates from the integrity check tab.

        Args:
            items: List of missing timestamp items
        """
        LOGGER.info("Missing items updated: %d items", len(items))
        # Update all tabs with the new data
        self._initialize_satellite_tabs()

    def _on_date_range_selected(self, start: datetime, end: datetime) -> None:
        """Handle date range selection from any tab."""
        # Update view model date range
        self.view_model.start_date = start
        self.view_model.end_date = end

        # Update the date selector in the integrity tab with the new date range (if it exists)
        tab = self.integrity_tab
        if hasattr(tab, "date_selector") and hasattr(
            tab.date_selector, "set_date_range"
        ):
            tab.date_selector.set_date_range(start, end)

        # If timeline has data from the model, update that too
        if hasattr(self.timeline_tab, "set_date_range"):
            self.timeline_tab.set_date_range(start, end)

        # Emit signal
        self.dateRangeSelected.emit(start, end)

        LOGGER.debug("Date range selected: %s to %s", start, end)

    def _on_integrity_date_changed(self) -> None:
        """
        Handle date range changes in the integrity tab.

        This method is called when the date range changes in the integrity tab.
        It propagates the changes to the other tabs.
        """
        tab = self.integrity_tab
        if hasattr(tab, "date_selector") and hasattr(
            tab.date_selector, "get_date_range"
        ):
            # Get the date values from the unified date range selector
            start_date, end_date = tab.date_selector.get_date_range()

            # Call the date range handler with the new range
            self._on_date_range_selected(start_date, end_date)

            # Emit the date range change signal if available
            if hasattr(self.integrity_tab, "date_range_changed"):
                self.integrity_tab.date_range_changed.emit(start_date, end_date)
            elif hasattr(self.integrity_tab, "dateRangeSelected"):
                self.integrity_tab.dateRangeSelected.emit(start_date, end_date)

            LOGGER.debug(
                "Date range changed in integrity tab: %s to %s", start_date, end_date
            )

    def _on_timestamp_selected(self, timestamp: datetime) -> None:
        """Handle timestamp selection from timeline tab."""
        # Find matching item
        selected_item = None
        for item in self.view_model.missing_items:
            if (
                abs((item.timestamp - timestamp).total_seconds()) < 60
            ):  # Within a minute
                selected_item = item
                break

        # Update results tab
        if selected_item:
            self.results_tab.highlight_item(timestamp)

        # Emit signal
        self.timestampSelected.emit(timestamp)

        LOGGER.debug("Timestamp selected: %s", timestamp)

    def _on_item_selected(self, item: MissingTimestamp) -> None:
        """Handle item selection from results tab."""
        # Emit signal
        self.itemSelected.emit(item)

        LOGGER.debug("Item selected: %s", item.expected_filename)

    def _on_download_requested(self, item: MissingTimestamp) -> None:
        """Handle download request from results tab."""
        # Forward to integrity tab
        if hasattr(self.integrity_tab, "download_item"):
            self.integrity_tab.download_item(item)

    def _on_view_requested(self, item: MissingTimestamp) -> None:
        """Handle view request from results tab."""
        # Switch to imagery tab and load the file
        if hasattr(item, "local_path") and item.local_path:
            self._switch_tab(3)  # Switch to imagery tab (index 3)
            if hasattr(self.imagery_tab, "load_file"):
                self.imagery_tab.load_file(item.local_path)

    def _on_imagery_file_selected(self, file_path: str) -> None:
        """Handle file selection from imagery tab."""
        # Could update timeline or results tabs to highlight the corresponding file
        LOGGER.debug("Imagery file selected: %s", file_path)

    def _on_directory_selected(self, directory: str) -> None:
        """
        Handle directory selection from any tab.

        Args:
            directory: Selected directory path
        """
        LOGGER.debug("Directory selected: %s", directory)

        # Set directory in view model
        if hasattr(self.view_model, "base_directory"):
            if isinstance(self.view_model.base_directory, Path):
                self.view_model.base_directory = Path(directory)
            else:
                self.view_model.base_directory = directory

        # Propagate to all tabs
        # Timeline tab
        if hasattr(self.timeline_tab, "set_directory"):
            self.timeline_tab.set_directory(directory)

        # Results tab
        if hasattr(self.results_tab, "set_directory"):
            self.results_tab.set_directory(directory)

        # Update UI in integrity tab if it has a directory field
        if hasattr(self.integrity_tab, "directory_edit"):
            self.integrity_tab.directory_edit.setText(directory)

    def _switch_tab(self, index: int) -> None:
        """Switch to the tab at the specified index and update button states."""
        self.stacked_widget.setCurrentIndex(index)

        # Update button checked states
        self.integrity_button.setChecked(index == 0)
        self.timeline_button.setChecked(index == 1)
        self.results_button.setChecked(index == 2)
        self.imagery_button.setChecked(index == 3)

    # --- Public methods for external interaction ---

    def update_data(
        self, missing_items=None, start_date=None, end_date=None, total_expected=None
    ) -> None:
        """
        Update the tab with new data.

        Args:
            missing_items: Optional list of missing timestamps to update
            start_date: Optional new start date
            end_date: Optional new end date
            total_expected: Optional total expected count
        """
        # Update view model if values provided
        if missing_items is not None:
            if hasattr(self.view_model, "_missing_items"):
                self.view_model._missing_items = missing_items
            elif hasattr(self.view_model, "set_missing_items"):
                self.view_model.set_missing_items(missing_items)
            # Don't use missing_items property directly as it may be read-only

        if start_date is not None:
            self.view_model.start_date = start_date

        if end_date is not None:
            self.view_model.end_date = end_date

        if total_expected is not None:
            self.view_model._total_expected = total_expected

        # Update internal tabs
        self._initialize_satellite_tabs()

        # Also update integrity tab if it has an update method
        if hasattr(self.integrity_tab, "update_data"):
            self.integrity_tab.update_data()

    # Removed the show_date_selection_tab method since we no longer have that tab

    def show_timeline_tab(self) -> None:
        """Switch to the timeline visualization tab."""
        self._switch_tab(1)

    def show_results_tab(self) -> None:
        """Switch to the results organization tab."""
        self._switch_tab(2)

    def show_integrity_tab(self) -> None:
        """Switch to the file integrity tab."""
        self._switch_tab(0)

    def show_imagery_tab(self) -> None:
        """Switch to the GOES imagery tab."""
        self._switch_tab(3)
