"""Combined Integrity Check and Satellite Visualization Tab.

This module provides a comprehensive tab that includes the enhanced integrity check
functionality with integrated date selection, timeline visualization, results organization,
and GOES imagery visualization features in a unified interface.
"""

from datetime import datetime
import logging

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
from .optimized_timeline_tab import OptimizedTimelineTab
from .results_organization import MissingItemsTreeView as OptimizedResultsTab
from .view_model import MissingTimestamp

# Configure logging
LOGGER = logging.getLogger(__name__)


class CombinedIntegrityAndImageryTab(QWidget):
    """Combined tab that includes file integrity and satellite visualization components.

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
        view_model: EnhancedIntegrityCheckViewModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.view_model = view_model
        self.setupUI()
        self.connectSignals()

    def setupUI(self) -> None:
        """Set up the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Add header
        from PyQt6.QtWidgets import QFrame, QLabel

        header = QLabel("🛰️ Satellite Integrity Check")
        header.setProperty("class", "AppHeader")
        layout.addWidget(header)

        # Tab selection buttons in a frame
        button_frame = QFrame()
        button_frame.setProperty("class", "ControlFrame")
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(10, 10, 10, 10)
        button_layout.setSpacing(10)

        self.integrity_button = QPushButton("📁 File Integrity")
        self.integrity_button.setCheckable(True)
        self.integrity_button.setChecked(True)
        self.integrity_button.setProperty("class", "TabButton")
        button_layout.addWidget(self.integrity_button)

        self.timeline_button = QPushButton("📈 Timeline")
        self.timeline_button.setCheckable(True)
        self.timeline_button.setProperty("class", "TabButton")
        button_layout.addWidget(self.timeline_button)

        self.results_button = QPushButton("📋 Results")
        self.results_button.setCheckable(True)
        self.results_button.setProperty("class", "TabButton")
        button_layout.addWidget(self.results_button)

        self.imagery_button = QPushButton("🌍 GOES Imagery")
        self.imagery_button.setCheckable(True)
        self.imagery_button.setProperty("class", "TabButton")
        button_layout.addWidget(self.imagery_button)

        button_layout.addStretch()
        layout.addWidget(button_frame)

        # Stacked widget for tab content
        self.stacked_widget = QStackedWidget()

        # Create view model if not provided
        if self.view_model is None:
            self.view_model = EnhancedIntegrityCheckViewModel()

        # Create tabs
        self.integrity_tab = EnhancedIntegrityCheckTab(self.view_model, parent=self)
        self.timeline_tab = OptimizedTimelineTab()
        self.results_tab = OptimizedResultsTab()
        self.imagery_tab = EnhancedGOESImageryTab()

        # Add tabs to stacked widget
        self.stacked_widget.addWidget(self.integrity_tab)
        self.stacked_widget.addWidget(self.timeline_tab)
        self.stacked_widget.addWidget(self.results_tab)
        self.stacked_widget.addWidget(self.imagery_tab)

        layout.addWidget(self.stacked_widget)

    def connectSignals(self) -> None:
        """Connect signals between components."""
        # Button connections
        self.integrity_button.clicked.connect(lambda: self.switchTab(0))
        self.timeline_button.clicked.connect(lambda: self.switchTab(1))
        self.results_button.clicked.connect(lambda: self.switchTab(2))
        self.imagery_button.clicked.connect(lambda: self.switchTab(3))

        # Cross-tab communication
        self.integrity_tab.dateRangeSelected.connect(self.onDateRangeSelected)
        self.timeline_tab.timestampSelected.connect(self.onTimestampSelected)
        self.results_tab.itemSelected.connect(self.onItemSelected)

    def switchTab(self, index: int) -> None:
        """Switch to the specified tab."""
        self.stacked_widget.setCurrentIndex(index)

        # Update button states
        buttons = [
            self.integrity_button,
            self.timeline_button,
            self.results_button,
            self.imagery_button,
        ]
        for i, button in enumerate(buttons):
            button.setChecked(i == index)

    def onDateRangeSelected(self, start: datetime, end: datetime) -> None:
        """Handle date range selection from integrity tab."""
        LOGGER.info("Date range selected: %s to %s", start, end)
        self.dateRangeSelected.emit(start, end)

        # Update timeline tab
        self.timeline_tab.setDateRange(start, end)

    def onTimestampSelected(self, timestamp: datetime) -> None:
        """Handle timestamp selection from timeline."""
        LOGGER.info("Timestamp selected: %s", timestamp)
        self.timestampSelected.emit(timestamp)

        # Update imagery tab
        self.imagery_tab.loadTimestamp(timestamp)

    def onItemSelected(self, item: MissingTimestamp) -> None:
        """Handle item selection from results."""
        LOGGER.info("Item selected: %s", item)
        self.itemSelected.emit(item)

        # Switch to imagery tab and load the item
        self.switchTab(3)
        if hasattr(self.imagery_tab, "loadMissingItem"):
            self.imagery_tab.loadMissingItem(item)

    def getScanResults(self) -> list[MissingTimestamp]:
        """Get the current scan results."""
        if self.view_model:
            items = getattr(self.view_model, "missing_items", [])
            return items if items is not None else []
        return []

    def clearResults(self) -> None:
        """Clear all results."""
        if self.view_model and hasattr(self.view_model, "clear_results"):
            self.view_model.clear_results()
        if hasattr(self.results_tab, "clearResults"):
            self.results_tab.clearResults()
        if hasattr(self.timeline_tab, "clearTimeline"):
            self.timeline_tab.clearTimeline()
