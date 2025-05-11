"""
Satellite Integrity Tab Group for the GOES Integrity Check application.

This module provides a cohesive group of tabs that bridge the gap between
visualizing GOES imagery and checking file integrity, with a focus on
temporal analysis and organization of satellite data.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from goesvfi.integrity_check.optimized_timeline_tab import OptimizedTimelineTab
from goesvfi.integrity_check.results_organization import (
    ItemPreviewWidget,
    MissingItemsTreeView,
    ResultsSummaryWidget,
)
from goesvfi.integrity_check.view_model import MissingTimestamp
from goesvfi.integrity_check.visual_date_picker import (
    TimelinePickerWidget,
    VisualDateRangePicker,
)


class OptimizedDateSelectionTab(QWidget):
    """
    Date selection tab optimized for satellite data analysis.
    """

    dateRangeSelected = pyqtSignal(datetime, datetime)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the optimized date selection tab."""
        super().__init__(parent)

        # Set up layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Add header
        header = QLabel(self.tr("Select Date Range for Analysis"))
        header.setStyleSheet(
            """
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 5px;
        """
        )
        layout.addWidget(header)

        # Add descriptive text
        description = QLabel(
            "Use the visual date picker or timeline slider to select a date range "
            "for analysis. The selected range will be used for all visualization "
            "and integrity check operations."
        )
        description.setWordWrap(True)
        description.setStyleSheet("margin-bottom: 10px;")
        layout.addWidget(description)

        # Create date controls section
        controls_frame = QFrame()
        controls_frame.setObjectName("dateControlsFrame")
        controls_frame.setStyleSheet(
            """
            #dateControlsFrame {
                background-color: #2d2d2d;
                border: 1px solid #454545;
                border-radius: 4px;
                padding: 10px;
            }
        """
        )
        controls_layout = QVBoxLayout(controls_frame)

        # Add visual date picker button
        visual_button = QPushButton(self.tr("Open Visual Date Picker"))
        visual_button.setProperty("class", "ActionButton")
        visual_button.clicked.connect(self._open_visual_date_picker)
        controls_layout.addWidget(visual_button)

        # Add timeline picker
        controls_layout.addWidget(QLabel(self.tr("Timeline Picker:")))

        self.timeline_picker = TimelinePickerWidget()
        self.timeline_picker.dateRangeSelected.connect(self._handle_date_range_selected)
        controls_layout.addWidget(self.timeline_picker)

        # Add date range display
        self.date_range_label = QLabel(self.tr("No date range selected"))
        self.date_range_label.setStyleSheet(
            """
            background-color: #3a3a3a;
            padding: 8px;
            border-radius: 4px;
            margin-top: 10px;
        """
        )
        controls_layout.addWidget(self.date_range_label)

        # Add controls frame to main layout
        layout.addWidget(controls_frame)

        # Add quick select buttons
        quick_select_frame = QFrame()
        quick_select_frame.setObjectName("quickSelectFrame")
        quick_select_frame.setStyleSheet(
            """
            #quickSelectFrame {
                background-color: #2d2d2d;
                border: 1px solid #454545;
                border-radius: 4px;
                padding: 10px;
                margin-top: 10px;
            }
        """
        )
        quick_select_layout = QVBoxLayout(quick_select_frame)

        quick_select_layout.addWidget(QLabel(self.tr("Quick Select:")))

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(5)

        # Add quick select buttons
        today_btn = QPushButton(self.tr("Today"))
        today_btn.clicked.connect(self._select_today)
        buttons_layout.addWidget(today_btn)

        yesterday_btn = QPushButton(self.tr("Yesterday"))
        yesterday_btn.clicked.connect(self._select_yesterday)
        buttons_layout.addWidget(yesterday_btn)

        last_week_btn = QPushButton(self.tr("Last 7 Days"))
        last_week_btn.clicked.connect(self._select_last_week)
        buttons_layout.addWidget(last_week_btn)

        last_month_btn = QPushButton(self.tr("Last 30 Days"))
        last_month_btn.clicked.connect(self._select_last_month)
        buttons_layout.addWidget(last_month_btn)

        quick_select_layout.addLayout(buttons_layout)

        # Add quick select frame to main layout
        layout.addWidget(quick_select_frame)

        # Add spacer
        layout.addStretch()

    def set_date_range(self, start: datetime, end: datetime) -> None:
        """
        Set the displayed date range.

        Args:
            start: Start date
            end: End date
        """
        # Update timeline picker
        self.timeline_picker.set_date_range(start, end)

        # Update label
        self.date_range_label.setText(
            f"Selected range: {start.strftime('%Y-%m-%d %H:%M')} - "
            f"{end.strftime('%Y-%m-%d %H:%M')}"
        )

    def _open_visual_date_picker(self) -> None:
        """Open the visual date picker dialog."""
        # Use default range (last 7 days) since get_date_range isn't available
        from datetime import datetime, timedelta

        current_start = datetime.now() - timedelta(days=7)
        current_end = datetime.now()

        dialog = VisualDateRangePicker(self, current_start, current_end)
        dialog.dateRangeSelected.connect(self._handle_date_range_selected)
        dialog.exec()

    def _handle_date_range_selected(self, start: datetime, end: datetime) -> None:
        """
        Handle date range selection.

        Args:
            start: Start date
            end: End date
        """
        # Update label
        self.date_range_label.setText(
            f"Selected range: {start.strftime('%Y-%m-%d %H:%M')} - "
            f"{end.strftime('%Y-%m-%d %H:%M')}"
        )

        # Update timeline picker
        self.timeline_picker.set_date_range(start, end)

        # Emit signal for other tabs
        self.dateRangeSelected.emit(start, end)

    def _select_today(self) -> None:
        """Select today's date range."""
        from datetime import datetime, timedelta

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        self._handle_date_range_selected(today, tomorrow)

    def _select_yesterday(self) -> None:
        """Select yesterday's date range."""
        from datetime import datetime, timedelta

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday = today - timedelta(days=1)
        self._handle_date_range_selected(yesterday, today)

    def _select_last_week(self) -> None:
        """Select last 7 days date range."""
        from datetime import datetime, timedelta

        end = datetime.now()
        start = end - timedelta(days=7)
        self._handle_date_range_selected(start, end)

    def _select_last_month(self) -> None:
        """Select last 30 days date range."""
        from datetime import datetime, timedelta

        end = datetime.now()
        start = end - timedelta(days=30)
        self._handle_date_range_selected(start, end)


class OptimizedResultsTab(QWidget):
    """
    Optimized results organization tab for satellite data.
    """

    itemSelected = pyqtSignal(MissingTimestamp)
    downloadRequested = pyqtSignal(MissingTimestamp)
    viewRequested = pyqtSignal(MissingTimestamp)
    directorySelected = pyqtSignal(str)  # Signal for directory selection

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the optimized results tab."""
        super().__init__(parent)

        # Set up layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Add control panel
        control_panel = self._create_control_panel()
        layout.addWidget(control_panel)

        # Create splitter for main content
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Missing items tree view
        self.tree_view = MissingItemsTreeView()
        self.tree_view.itemSelected.connect(self._handle_item_selected)
        splitter.addWidget(self.tree_view)

        # Right: Detail panels
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # Top-right: Summary widget
        self.summary_widget = ResultsSummaryWidget()
        right_layout.addWidget(self.summary_widget)

        # Bottom-right: Preview widget
        self.preview_widget = ItemPreviewWidget()
        right_layout.addWidget(self.preview_widget)

        # Connect preview widget buttons
        self.preview_widget.download_btn.clicked.connect(self._handle_download_clicked)
        self.preview_widget.view_btn.clicked.connect(self._handle_view_clicked)

        # Add right panel to splitter
        splitter.addWidget(right_panel)

        # Set initial splitter sizes
        splitter.setSizes([400, 400])

        # Add splitter to main layout
        layout.addWidget(splitter, 1)  # Give stretch priority

    def _create_control_panel(self) -> QFrame:
        """Create the control panel for filtering and grouping results."""
        panel = QFrame()
        panel.setObjectName("resultsControlPanel")
        panel.setMaximumHeight(50)
        panel.setStyleSheet(
            """
            #resultsControlPanel {
                background-color: #2d2d2d;
                border: 1px solid #454545;
                border-radius: 4px;
            }
        """
        )

        layout = QHBoxLayout(panel)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)

        # Group by control
        layout.addWidget(QLabel(self.tr("Group by:")))

        self.group_combo = QComboBox()
        self.group_combo.addItems([self.tr("Day"), self.tr("Hour"), self.tr("Satellite"), self.tr("Status"), self.tr("Source")])
        self.group_combo.currentTextChanged.connect(self._handle_group_changed)
        layout.addWidget(self.group_combo)

        # Spacer
        layout.addStretch(1)

        # Add expand/collapse buttons
        self.expand_btn = QPushButton(self.tr("Expand All"))
        self.expand_btn.clicked.connect(self._expand_all)
        layout.addWidget(self.expand_btn)

        self.collapse_btn = QPushButton(self.tr("Collapse All"))
        self.collapse_btn.clicked.connect(self._collapse_all)
        layout.addWidget(self.collapse_btn)

        return panel

    def set_items(self, items: List[MissingTimestamp], total_expected: int) -> None:
        """
        Set the items for display in this tab.

        Args:
            items: List of missing timestamps
            total_expected: Total number of expected timestamps
        """
        # Update tree view
        self.tree_view.set_items(items)

        # Update summary widget
        self.summary_widget.update_summary(items, total_expected)

        # Clear preview if no items
        if not items:
            self.preview_widget.clear()

    def highlight_item(self, timestamp: datetime) -> None:
        """
        Highlight an item with the given timestamp.

        Args:
            timestamp: Timestamp to highlight
        """
        self.tree_view.highlight_timestamp(timestamp)

    def _handle_item_selected(self, item: MissingTimestamp) -> None:
        """
        Handle item selection from the tree view.

        Args:
            item: Selected missing timestamp
        """
        # Update preview widget
        self.preview_widget.set_item(item)

        # Emit signal
        self.itemSelected.emit(item)

    def _handle_download_clicked(self) -> None:
        """Handle download button click in preview widget."""
        item = self.preview_widget.current_item
        if item:
            self.downloadRequested.emit(item)

    def _handle_view_clicked(self) -> None:
        """Handle view button click in preview widget."""
        item = self.preview_widget.current_item
        if item:
            self.viewRequested.emit(item)

    def _handle_group_changed(self, group_by: str) -> None:
        """
        Handle change in grouping option.

        Args:
            group_by: Grouping method (Day, Hour, Satellite, etc.)
        """
        self.tree_view.set_grouping(group_by.lower())

    def _expand_all(self) -> None:
        """Expand all groups in the tree view."""
        self.tree_view.expandAll()

    def _collapse_all(self) -> None:
        """Collapse all groups in the tree view."""
        self.tree_view.collapseAll()

    def set_directory(self, directory: str) -> None:
        """
        Set the current working directory for the results tab.

        Args:
            directory: Path to the directory to analyze
        """
        # In a real implementation, this would trigger data loading for the directory
        # For now, we'll just emit the signal to maintain synchronization
        self.directorySelected.emit(directory)


class SatelliteIntegrityTabGroup(QWidget):
    """
    Container for satellite integrity analysis tabs.

    This class contains and coordinates the three tabs for satellite integrity analysis:
    1. Date Selection
    2. Timeline Visualization
    3. Results Organization

    It provides a cohesive interface that bridges the gap between visualizing GOES imagery
    and checking file integrity, with a focus on temporal analysis.
    """

    # Signals for communicating with other tabs
    dateRangeSelected = pyqtSignal(datetime, datetime)
    timestampSelected = pyqtSignal(datetime)
    itemSelected = pyqtSignal(MissingTimestamp)
    downloadRequested = pyqtSignal(MissingTimestamp)
    viewRequested = pyqtSignal(MissingTimestamp)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the satellite integrity tab group."""
        super().__init__(parent)

        # Set up layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create tab widget
        self.tab_widget = QTabWidget()

        # Create tabs
        self.date_selection_tab = OptimizedDateSelectionTab()
        self.timeline_tab = OptimizedTimelineTab()
        self.results_tab = OptimizedResultsTab()

        # Add tabs to tab widget
        self.tab_widget.addTab(self.date_selection_tab, "Date Selection")
        self.tab_widget.addTab(self.timeline_tab, "Timeline Visualization")
        self.tab_widget.addTab(self.results_tab, "Results Organization")

        # Add tab widget to layout
        layout.addWidget(self.tab_widget)

        # Connect signals between tabs
        self._connect_internal_signals()

    def _connect_internal_signals(self) -> None:
        """Connect signals between internal tabs."""
        # From date selection tab to timeline tab
        self.date_selection_tab.dateRangeSelected.connect(
            self._handle_date_range_selected
        )

        # From timeline tab to results tab
        self.timeline_tab.timestampSelected.connect(self.results_tab.highlight_item)
        self.timeline_tab.timestampSelected.connect(self.timestampSelected)

        # From results tab to external connections
        self.results_tab.itemSelected.connect(self.itemSelected)
        self.results_tab.downloadRequested.connect(self.downloadRequested)
        self.results_tab.viewRequested.connect(self.viewRequested)

    def _handle_date_range_selected(self, start: datetime, end: datetime) -> None:
        """
        Handle date range selection from the date selection tab.

        Args:
            start: Start date
            end: End date
        """
        # Update timeline tab if it has set_date_range method
        # Note: This doesn't update the data, just the displayed range
        # The actual data update needs to come from the view model
        if hasattr(self.timeline_tab, "set_date_range"):
            self.timeline_tab.set_date_range(start, end)

        # Emit signal for external connections
        self.dateRangeSelected.emit(start, end)

    def set_data(
        self,
        items: List[MissingTimestamp],
        start_date: datetime,
        end_date: datetime,
        total_expected: int,
        interval_minutes: Optional[int] = None,
    ) -> None:
        """
        Set data for all tabs in the group.

        Args:
            items: List of missing timestamps
            start_date: Start date for the analysis
            end_date: End date for the analysis
            total_expected: Total number of expected timestamps
            interval_minutes: Expected interval between timestamps (in minutes)
        """
        # Update date selection tab
        self.date_selection_tab.set_date_range(start_date, end_date)

        # Update timeline tab
        self.timeline_tab.set_data(items, start_date, end_date, interval_minutes)

        # Update results tab
        self.results_tab.set_items(items, total_expected)

    def connect_to_goes_imagery_tab(self, tab: Any) -> None:
        """
        Connect to the GOES imagery tab for data flow.

        Args:
            tab: GOES imagery tab object
        """
        # Connect signals based on available interfaces
        # This method would need to be customized based on the actual
        # interface provided by the GOES imagery tab
        try:
            # Example connections (adjust based on actual interfaces)
            if hasattr(tab, "dateRangeSelected"):
                tab.dateRangeSelected.connect(self._handle_date_range_selected)

            if hasattr(tab, "satelliteSelected"):
                tab.satelliteSelected.connect(self._handle_satellite_selected)
        except Exception as e:
            import traceback

            print(f"Error connecting to GOES imagery tab: {e}")
            print(traceback.format_exc())

    def connect_to_integrity_tab(self, tab: Any) -> None:
        """
        Connect to the file integrity tab for data flow.

        Args:
            tab: File integrity tab object
        """
        # Connect signals based on available interfaces
        # This method would need to be customized based on the actual
        # interface provided by the file integrity tab
        try:
            # Example: Pass selected items to integrity check
            self.itemSelected.connect(tab.check_item)

            # Example: Pass download requests to integrity tab
            self.downloadRequested.connect(tab.download_item)
        except Exception as e:
            import traceback

            print(f"Error connecting to integrity tab: {e}")
            print(traceback.format_exc())

    def _handle_satellite_selected(self, satellite: Any) -> None:
        """
        Handle satellite selection from GOES imagery tab.

        Args:
            satellite: Selected satellite object or identifier
        """
        # This method would need to be customized based on how
        # satellites are represented in the application
        pass
