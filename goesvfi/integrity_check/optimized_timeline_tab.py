"""Optimized timeline visualization tab for GOES satellite data integrity.

This module provides a streamlined interface for visualizing satellite data availability
over time with improved organization and focus.
"""

from datetime import datetime
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from goesvfi.integrity_check.enhanced_timeline import EnhancedTimeline
from goesvfi.integrity_check.timeline_visualization import MissingDataCalendarView
from goesvfi.integrity_check.view_model import MissingTimestamp


class OptimizedTimelineTab(QWidget):
    """
    Optimized timeline visualization tab that provides a more focused
    and user-friendly interface for exploring satellite data availability.
    """

    timestampSelected = pyqtSignal(datetime)
    rangeSelected = pyqtSignal(datetime, datetime)
    directorySelected = pyqtSignal(str)  # Signal for directory selection

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the optimized timeline tab."""
        super().__init__(parent)

        # Set up core layout structure
        self._setup_layout()

        # Data for visualization
        self.start_timestamp: Optional[datetime] = None
        self.end_timestamp: Optional[datetime] = None
        self.missing_items: List[MissingTimestamp] = []
        self.interval_minutes: Optional[int] = None

        # Current selection
        self.selected_timestamp: Optional[datetime] = None
        self.selected_range: Optional[Tuple[datetime, datetime]] = None
        self.selected_item: Optional[MissingTimestamp] = None

    def _setup_layout(self) -> None:
        """Set up the main layout structure."""
        # Set main container ID for styling
        self.setObjectName("mainContainer")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Section 1: Compact Control Panel
        self.control_panel = self._create_control_panel()  # pylint: disable=attribute-defined-outside-init
        main_layout.addWidget(self.control_panel)

        # Section 2: View Selector and Visualizations
        self.view_selector = self._create_view_selector()  # pylint: disable=attribute-defined-outside-init
        main_layout.addWidget(self.view_selector, 1)  # Give stretch priority

        # Section 3: Information Panel
        self.info_panel = self._create_info_panel()  # pylint: disable=attribute-defined-outside-init
        main_layout.addWidget(self.info_panel)

    def _create_control_panel(self) -> QFrame:
        """Create the compact control panel with all controls in one row."""
        panel = QFrame()
        panel.setObjectName("controlPanel")
        panel.setMaximumHeight(45)  # Constrain height for compactness
        panel.setStyleSheet(
            """
            #controlPanel {
                background-color: #2d2d2d;
                border: 1px solid #454545;
                border-radius: 4px;
            }
            """
        )

        layout = QHBoxLayout(panel)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(8)

        # Add a spacer at the beginning
        layout.addSpacerItem(QSpacerItem(10, 10, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed))

        # Add separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("color: #454545;")
        layout.addWidget(separator)

        # Create button row styling - unified style for all controls
        control_style = """
        QFrame.ControlGroup {
        background-color: #3a3a3a;
        border: 1px solid #545454;
        border-radius: 4px;
        }
        QLabel.ControlLabel {
        color: #f0f0f0;
        font-weight: bold;
        padding-right: 4px;
        font-size: 11px;
        }
        QRadioButton {
        color: #f0f0f0;
        spacing: 4px;
        padding: 0px 3px;
        font-size: 11px;
        }
        QRadioButton::indicator {
        width: 12px;
        height: 12px;
        border-radius: 6px;
        border: 1px solid #646464;
        }
        QRadioButton::indicator:unchecked {
        background-color: #333333;
        }
        QRadioButton::indicator:checked {
        background-color: #2a82da;
        border: 1px solid #2a82da;
        }
        QPushButton {
        background-color: #454545;
        color: #f0f0f0;
        border: 1px solid #646464;
        border-radius: 4px;
        padding: 1px 6px;
        min-height: 20px;
        max-height: 20px;
        min-width: 24px;
        font-size: 11px;
        }
        QPushButton:hover {
        background-color: #505050;
        border-color: #787878;
        }
        QPushButton:pressed {
        background-color: #2a82da;
        border-color: #1a72ca;
        }
        """
        panel.setStyleSheet(panel.styleSheet() + control_style)

        # === Data Filter Controls ===
        filter_group = QFrame()
        filter_group.setObjectName("filterGroup")
        filter_group.setProperty("class", "ControlGroup")
        filter_layout = QHBoxLayout(filter_group)
        filter_layout.setContentsMargins(6, 2, 6, 2)
        filter_layout.setSpacing(2)

        filter_label = QLabel(self.tr("Filter:"))
        filter_label.setProperty("class", "ControlLabel")
        filter_layout.addWidget(filter_label)

        # Data filter buttons - use material design inspired buttons with icons
        self.filter_all_btn = QPushButton(self.tr("All"))
        self.filter_all_btn.setCheckable(True)
        self.filter_all_btn.setChecked(True)
        self.filter_all_btn.setToolTip(self.tr("Show all data points"))
        self.filter_all_btn.clicked.connect(lambda: self._set_view_mode("both"))
        filter_layout.addWidget(self.filter_all_btn)

        self.filter_missing_btn = QPushButton(self.tr("Missing"))
        self.filter_missing_btn.setCheckable(True)
        self.filter_missing_btn.setToolTip(self.tr("Show only missing data points"))
        self.filter_missing_btn.clicked.connect(lambda: self._set_view_mode("missing"))
        filter_layout.addWidget(self.filter_missing_btn)

        self.filter_available_btn = QPushButton(self.tr("Available"))
        self.filter_available_btn.setCheckable(True)
        self.filter_available_btn.setToolTip(self.tr("Show only available data points"))
        self.filter_available_btn.clicked.connect(lambda: self._set_view_mode("available"))
        filter_layout.addWidget(self.filter_available_btn)

        # Connect buttons to work as a group (when one is checked, others are unchecked)
        def update_filter_buttons(btn_name: str) -> None:
            self.filter_all_btn.setChecked(btn_name == "all")
            self.filter_missing_btn.setChecked(btn_name == "missing")
            self.filter_available_btn.setChecked(btn_name == "available")

        self.filter_all_btn.clicked.connect(lambda: update_filter_buttons("all"))
        self.filter_missing_btn.clicked.connect(lambda: update_filter_buttons("missing"))
        self.filter_available_btn.clicked.connect(lambda: update_filter_buttons("available"))

        layout.addWidget(filter_group)

        # Add separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("color: #454545;")
        layout.addWidget(separator)

        # === View Mode Controls ===
        view_group = QFrame()
        view_group.setObjectName("viewGroup")
        view_group.setProperty("class", "ControlGroup")
        view_layout = QHBoxLayout(view_group)
        view_layout.setContentsMargins(6, 2, 6, 2)
        view_layout.setSpacing(2)

        view_label = QLabel(self.tr("View:"))
        view_label.setProperty("class", "ControlLabel")
        view_layout.addWidget(view_label)

        # Tab-style buttons for view switching
        self.view_timeline_btn = QPushButton(self.tr("Timeline"))
        self.view_timeline_btn.setCheckable(True)
        self.view_timeline_btn.setChecked(True)
        self.view_timeline_btn.setToolTip(self.tr("Show timeline visualization"))
        self.view_timeline_btn.clicked.connect(lambda: self._toggle_visualization(0))
        view_layout.addWidget(self.view_timeline_btn)

        self.view_calendar_btn = QPushButton(self.tr("Calendar"))
        self.view_calendar_btn.setCheckable(True)
        self.view_calendar_btn.setToolTip(self.tr("Show calendar visualization"))
        self.view_calendar_btn.clicked.connect(lambda: self._toggle_visualization(1))
        view_layout.addWidget(self.view_calendar_btn)

        # Connect buttons to work as a tab group
        def update_view_buttons(btn_name: str) -> None:
            self.view_timeline_btn.setChecked(btn_name == "timeline")
            self.view_calendar_btn.setChecked(btn_name == "calendar")

        self.view_timeline_btn.clicked.connect(lambda: update_view_buttons("timeline"))
        self.view_calendar_btn.clicked.connect(lambda: update_view_buttons("calendar"))

        layout.addWidget(view_group)

        # Add flexible space to separate groups
        layout.addStretch(1)

        # === Zoom Controls ===
        self.zoom_group = QFrame()
        self.zoom_group.setObjectName("zoomGroup")
        self.zoom_group.setProperty("class", "ControlGroup")
        zoom_layout = QHBoxLayout(self.zoom_group)
        zoom_layout.setContentsMargins(6, 2, 6, 2)
        zoom_layout.setSpacing(2)

        zoom_label = QLabel(self.tr("Zoom:"))
        zoom_label.setProperty("class", "ControlLabel")
        zoom_layout.addWidget(zoom_label)

        # Zoom controls with more compact styling
        self.zoom_out_btn = QPushButton(self.tr("−"))  # Using Unicode minus sign
        self.zoom_out_btn.setToolTip(self.tr("Zoom out"))
        self.zoom_out_btn.setMaximumWidth(24)
        self.zoom_out_btn.clicked.connect(self._zoom_out)
        zoom_layout.addWidget(self.zoom_out_btn)

        self.zoom_level_label = QLabel(self.tr("100%"))
        self.zoom_level_label.setStyleSheet("color: #f0f0f0; min-width: 36px; text-align: center; font-size: 11px;")
        self.zoom_level_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        zoom_layout.addWidget(self.zoom_level_label)

        self.zoom_in_btn = QPushButton(self.tr("+"))
        self.zoom_in_btn.setToolTip(self.tr("Zoom in"))
        self.zoom_in_btn.setMaximumWidth(24)
        self.zoom_in_btn.clicked.connect(self._zoom_in)
        zoom_layout.addWidget(self.zoom_in_btn)

        self.zoom_reset_btn = QPushButton(self.tr("Reset"))
        self.zoom_reset_btn.setToolTip(self.tr("Reset zoom to 100%"))
        self.zoom_reset_btn.clicked.connect(self._zoom_reset)
        zoom_layout.addWidget(self.zoom_reset_btn)

        layout.addWidget(self.zoom_group)

        return panel

    def _create_view_selector(self) -> QWidget:
        """Create the view selector with stacked visualizations."""
        # Container widget
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Add a header with view name and status indicator
        self.view_header = QLabel(self.tr("📊 Timeline View"))
        self.view_header.setObjectName("viewHeader")
        self.view_header.setStyleSheet(
            """
            #viewHeader {
                color: #f0f0f0;
                font-weight: bold;
                font-size: 14px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4a4a4a, stop:1 #3a3a3a);
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 6px 12px;
                margin-bottom: 8px;
            }
            """
        )
        layout.addWidget(self.view_header)

        # Stacked widget to hold visualizations
        self.stack = QStackedWidget()

        # Enhanced timeline visualization
        self.timeline_viz = EnhancedTimeline()
        self.timeline_viz.timestampSelected.connect(self._handle_timestamp_selected)
        self.timeline_viz.rangeSelected.connect(self._handle_range_selected)
        self.stack.addWidget(self.timeline_viz)

        # Calendar visualization
        self.calendar_view = MissingDataCalendarView()
        self.calendar_view.dateSelected.connect(self._handle_timestamp_selected)
        self.stack.addWidget(self.calendar_view)

        # Add stacked widget to container
        layout.addWidget(self.stack)

        return container

    def _create_info_panel(self) -> QFrame:
        """Create the information panel for displaying selection details."""
        panel = QFrame()
        panel.setObjectName("infoPanel")
        panel.setFixedHeight(100)  # Fixed height for consistency
        panel.setStyleSheet(
            """
            #infoPanel {
                background-color: #2d2d2d;
                border: 1px solid #454545;
                border-radius: 4px;
            }
            """
        )

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 10, 15, 10)

        # Panel title with icon
        title = QLabel(self.tr("📎 Selection Details"))
        title.setStyleSheet("color: #f0f0f0; font-weight: bold; font-size: 14px; padding-bottom: 5px;")
        layout.addWidget(title)

        # Content area
        content_layout = QHBoxLayout()

        # Info section
        self.info_label = QLabel(self.tr("No item selected"))
        self.info_label.setStyleSheet("color: #f0f0f0;")
        self.info_label.setWordWrap(True)
        content_layout.addWidget(self.info_label, 3)  # Give more space to info

        # Actions section
        actions_frame = QFrame()
        actions_layout = QVBoxLayout(actions_frame)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(5)

        # Action buttons with optimized styling
        self.action_view_btn = QPushButton(self.tr("View Details"))
        self.action_view_btn.setProperty("class", "ActionButton")
        self.action_view_btn.setEnabled(False)
        self.action_view_btn.clicked.connect(self._action_view_details)
        actions_layout.addWidget(self.action_view_btn)

        self.action_download_btn = QPushButton(self.tr("Download"))
        self.action_download_btn.setProperty("class", "ActionButton")
        self.action_download_btn.setEnabled(False)
        self.action_download_btn.clicked.connect(self._action_download)
        actions_layout.addWidget(self.action_download_btn)

        actions_layout.addStretch()

        content_layout.addWidget(actions_frame, 1)

        layout.addLayout(content_layout)

        return panel

    def set_data(
        self,
        missing_items: List[MissingTimestamp],
        start_time: datetime,
        end_time: datetime,
        interval_minutes: Optional[int] = None,
    ) -> None:
        """
        Set the data for visualization.

        Args:
            missing_items: List of missing timestamps
            start_time: Start of the time range
            end_time: End of the time range
            interval_minutes: Expected interval between timestamps (in minutes)
        """
        self.start_timestamp = start_time
        self.end_timestamp = end_time
        self.missing_items = missing_items
        self.interval_minutes = interval_minutes

        # Update timeline visualization
        self.timeline_viz.set_data(missing_items, start_time, end_time, interval_minutes or 60)

        # Update calendar visualization
        self.calendar_view.set_data(missing_items, start_time, end_time, interval_minutes or 60)

        # Reset selection state
        self.selected_timestamp = None
        self.selected_range = None
        self.selected_item = None
        self._update_info_panel()

    def _set_view_mode(self, mode: str) -> None:
        """
        Set the view mode for the timeline visualization.

        Args:
            mode: View mode ('both', 'missing', 'available')
        """
        # Timeline view mode
        self.timeline_viz.view_mode = mode
        self.timeline_viz.update()

        # No direct mode control for calendar view (always shows all)

    def _toggle_visualization(self, index: int) -> None:
        """
        Toggle between timeline and calendar visualizations.

        Args:
            index: Index of the visualization to show (0=timeline, 1=calendar)
        """
        self.stack.setCurrentIndex(index)

        # Update the buttons to match the current state
        self.view_timeline_btn.setChecked(index == 0)
        self.view_calendar_btn.setChecked(index == 1)

        # Update the view header label with icons
        if index == 0:
            self.view_header.setText(self.tr("📊 Timeline View"))
        else:
            self.view_header.setText(self.tr("📅 Calendar View"))

        # Also update the zoom controls visibility - only available for timeline view
        zoom_controls_visible = index == 0
        self.zoom_group.setVisible(zoom_controls_visible)

    def _zoom_in(self) -> None:
        """Zoom in on the timeline visualization."""
        # Only applies to timeline view
        if self.timeline_viz.zoom_level < 10.0:
            pass
            self.timeline_viz.zoom_level *= 1.5
            self.timeline_viz.update()

            # Update zoom level label
            zoom_percent = int(self.timeline_viz.zoom_level * 100)
            self.zoom_level_label.setText(f"{zoom_percent}%")

    def _zoom_out(self) -> None:
        """Zoom out on the timeline visualization."""
        # Only applies to timeline view
        if self.timeline_viz.zoom_level > 0.5:
            pass
            self.timeline_viz.zoom_level /= 1.5
            if self.timeline_viz.zoom_level < 1.0:
                pass
                self.timeline_viz.zoom_level = 1.0
            self.timeline_viz.update()

            # Update zoom level label
            zoom_percent = int(self.timeline_viz.zoom_level * 100)
            self.zoom_level_label.setText(f"{zoom_percent}%")

    def _zoom_reset(self) -> None:
        """Reset zoom level on the timeline visualization."""
        # Only applies to timeline view
        self.timeline_viz.zoom_level = 1.0
        self.timeline_viz.viewport_start = 0
        self.timeline_viz.update()

        # Update zoom level label
        self.zoom_level_label.setText(self.tr("100%"))

    def _handle_timestamp_selected(self, timestamp: datetime) -> None:
        """
        Handle selection of a single timestamp.

        Args:
            timestamp: Selected timestamp
        """
        self.selected_timestamp = timestamp
        self.selected_range = None

        # Find the corresponding item if it exists
        self.selected_item = None
        for item in self.missing_items:
            if abs((item.timestamp - timestamp).total_seconds()) < 60:  # Within a minute
                self.selected_item = item
                break

        # Update the info panel
        self._update_info_panel()

        # Emit signal
        self.timestampSelected.emit(timestamp)

    def _handle_range_selected(self, start: datetime, end: datetime) -> None:
        """
        Handle selection of a date range.

        Args:
            start: Start date
            end: End date
        """
        self.selected_range = (start, end)
        self.selected_timestamp = None
        self.selected_item = None

        # Update the info panel
        self._update_info_panel()

        # Emit signal
        self.rangeSelected.emit(start, end)

    def _update_info_panel(self) -> None:
        """Update the information panel with current selection details."""
        if self.selected_item:
            pass
            # Display information about the selected item
            status = self._get_item_status(self.selected_item)

            self.info_label.setText(
                f"<b>Selected:</b> {self.selected_item.timestamp.strftime('%Y-%m-%d %H:%M:%S')}<br>"
                f"<b>Filename:</b> {self.selected_item.expected_filename}<br>"
                f"<b>Status:</b> {status}"
            )

            # Enable/disable action buttons based on status
            self.action_view_btn.setEnabled(getattr(self.selected_item, "is_downloaded", False))
            self.action_download_btn.setEnabled(
                not getattr(self.selected_item, "is_downloaded", False)
                and not getattr(self.selected_item, "is_downloading", False)
            )

        elif self.selected_timestamp:
            pass
            # Display information about the selected timestamp (no matching item)
            self.info_label.setText(
                f"<b>Selected:</b> {self.selected_timestamp.strftime('%Y-%m-%d %H:%M:%S')}<br>"
                f"<b>No matching item found</b>"
            )

            # Disable action buttons
            self.action_view_btn.setEnabled(False)
            self.action_download_btn.setEnabled(False)

        elif self.selected_range:
            pass
            # Display information about the selected range
            start, end = self.selected_range
            duration = end - start

            # Calculate duration text
            days = duration.days
            hours, remainder = divmod(duration.seconds, 3600)
            minutes, _ = divmod(remainder, 60)

            duration_text = ""
            if days > 0:
                pass
                duration_text += f"{days} day{'s' if days != 1 else ''} "
            if hours > 0:
                pass
                duration_text += f"{hours} hour{'s' if hours != 1 else ''} "
            if minutes > 0:
                pass
                duration_text += f"{minutes} minute{'s' if minutes != 1 else ''}"

            self.info_label.setText(
                f"<b>Selected Range:</b> {start.strftime('%Y-%m-%d %H:%M')} to {end.strftime('%Y-%m-%d %H:%M')}<br>"
                f"<b>Duration:</b> {duration_text.strip()}"
            )

            # Disable action buttons
            self.action_view_btn.setEnabled(False)
            self.action_download_btn.setEnabled(False)

        else:
            # No selection
            self.info_label.setText(self.tr("No item selected"))

            # Disable action buttons
            self.action_view_btn.setEnabled(False)
            self.action_download_btn.setEnabled(False)

    def _get_item_status(self, item: MissingTimestamp) -> str:
        """
        Get human-readable status for an item with HTML styling.

        Args:
            item: Missing timestamp item

        Returns:
            HTML-formatted status string with appropriate styling
        """
        if getattr(item, "is_downloaded", False):
            pass
            return '<span class="StatusLabel" status="success">Downloaded</span>'
        elif getattr(item, "is_downloading", False):
            pass
            progress = getattr(item, "progress", 0)
            return f'<span class="StatusLabel" status="processing">Downloading ({progress}%)</span>'
        elif getattr(item, "download_error", ""):
            pass
            return f'<span class="StatusLabel" status="error">Error</span> {item.download_error}'
        return '<span class="StatusLabel" status="warning">Missing</span>'

    def _action_view_details(self) -> None:
        """Handle action to view item details."""
        # Simply a placeholder for demo purposes
        if self.selected_item and getattr(self.selected_item, "is_downloaded", False):
            pass
            print(f"Viewing details for {self.selected_item.expected_filename}")

    def _action_download(self) -> None:
        """Handle action to download item."""
        # Simply a placeholder for demo purposes
        if self.selected_item and not getattr(self.selected_item, "is_downloaded", False):
            pass
            print(f"Downloading {self.selected_item.expected_filename}")

    def set_directory(self, directory: str) -> None:
        """
        Set the current working directory for the timeline tab.

        Args:
            directory: Path to the directory to analyze
        """
        # In a real implementation, this would trigger data loading for the directory
        # For now, we'll just emit the signal to maintain synchronization
        self.directorySelected.emit(directory)

    def set_date_range(self, start_time: datetime, end_time: datetime) -> None:
        """
        Set the date range for visualization without changing the data.

        Args:
            start_time: Start of the time range
            end_time: End of the time range
        """
        self.start_timestamp = start_time
        self.end_timestamp = end_time

        # Update both visualizations with the new date range
        if hasattr(self.timeline_viz, "set_date_range"):
            pass
            self.timeline_viz.set_date_range(start_time, end_time)

        if hasattr(self.calendar_view, "set_date_range"):
            pass
            self.calendar_view.set_date_range(start_time, end_time)

    def setDateRange(self, start_time: datetime, end_time: datetime) -> None:
        """Alias for set_date_range for backward compatibility."""
        self.set_date_range(start_time, end_time)
