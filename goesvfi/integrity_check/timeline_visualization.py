"""
Interactive timeline visualization for GOES satellite data integrity.

This module provides interactive visualizations of satellite data availability over time,
allowing users to easily identify gaps and patterns in the data coverage.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Union, Any, cast, TypeVar
import math

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel, 
    QPushButton, QSizePolicy, QFrame, QToolTip, QStyleOption,
    QStyle, QGridLayout, QButtonGroup, QRadioButton
)
from PyQt6.QtCore import Qt, QRect, QRectF, QSize, QPoint, QDateTime, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient, 
    QFont, QFontMetrics, QPainterPath, QResizeEvent, QMouseEvent
)

from goesvfi.integrity_check.view_model import MissingTimestamp


class TimelineVisualization(QWidget):
    """
    Interactive timeline visualization of GOES satellite data coverage.
    
    This widget provides a visual representation of data coverage over time,
    highlighting gaps and missing timestamps with interactive tooltips.
    """
    
    timestampSelected = pyqtSignal(datetime)
    rangeSelected = pyqtSignal(datetime, datetime)
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the timeline visualization widget."""
        super().__init__(parent)
        
        # UI setup
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        
        # Configure the widget for mouse tracking
        self.setMouseTracking(True)
        
        # Data for visualization
        self.start_timestamp: Optional[datetime] = None
        self.end_timestamp: Optional[datetime] = None
        self.available_timestamps: List[datetime] = []
        self.missing_timestamps: List[datetime] = []
        self.downloaded_timestamps: List[datetime] = []
        self.expected_interval: Optional[int] = None  # in minutes
        
        # Colors (tuned for dark mode)
        self.available_color = QColor(40, 167, 69)    # Green
        self.missing_color = QColor(220, 53, 69)      # Red
        self.downloaded_color = QColor(0, 123, 255)   # Blue
        self.bg_color = QColor(45, 45, 45)            # Dark gray for dark mode
        self.timeline_bg_color = QColor(60, 60, 60)   # Slightly lighter gray for dark mode
        self.axis_color = QColor(180, 180, 180)       # Light gray for axis
        
        # Selection state
        self.selection_start: Optional[int] = None
        self.selection_end: Optional[int] = None
        self.is_selecting = False
        self.hover_timestamp: Optional[datetime] = None
        
        # UI state
        self.zoom_level = 1.0  # 1.0 = 100% (showing all data)
        self.viewport_start = 0.0  # 0-1 range representing visible portion start
        
        # Control panel shown/hidden
        self.show_controls = True
        
        # Default view settings
        self.view_mode = 'both'  # 'missing', 'available', or 'both'
        
        # Set up the UI
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        
        # Control panel
        self.control_panel = QWidget()
        control_layout = QHBoxLayout(self.control_panel)
        control_layout.setContentsMargins(0, 0, 0, 0)
        
        # View mode selection - Enhanced with dark mode styling
        view_group = QFrame()
        view_group.setFrameShape(QFrame.Shape.StyledPanel)
        view_group.setStyleSheet("""
            QFrame {
                background-color: #3a3a3a;
                border: 1px solid #545454;
                border-radius: 4px;
            }
        """)
        view_layout = QHBoxLayout(view_group)
        view_layout.setContentsMargins(8, 5, 8, 5)

        view_label = QLabel("View:")
        view_label.setStyleSheet("color: #f0f0f0; font-weight: bold;")
        view_layout.addWidget(view_label)

        self.view_mode_group = QButtonGroup(self)

        # Enhanced radio button styling
        radio_style = """
            QRadioButton {
                color: #f0f0f0;
                spacing: 5px;
            }
            QRadioButton::indicator {
                width: 14px;
                height: 14px;
                border-radius: 7px;
                border: 1px solid #646464;
            }
            QRadioButton::indicator:unchecked {
                background-color: #333333;
            }
            QRadioButton::indicator:checked {
                background-color: #2a82da;
                border: 1px solid #2a82da;
            }
            QRadioButton::indicator:checked:disabled {
                background-color: #666666;
            }
        """

        self.view_all_radio = QRadioButton("All")
        self.view_all_radio.setChecked(True)
        self.view_all_radio.setStyleSheet(radio_style)
        self.view_mode_group.addButton(self.view_all_radio)
        view_layout.addWidget(self.view_all_radio)

        self.view_missing_radio = QRadioButton("Missing")
        self.view_missing_radio.setStyleSheet(radio_style)
        self.view_mode_group.addButton(self.view_missing_radio)
        view_layout.addWidget(self.view_missing_radio)

        self.view_available_radio = QRadioButton("Available")
        self.view_available_radio.setStyleSheet(radio_style)
        self.view_mode_group.addButton(self.view_available_radio)
        view_layout.addWidget(self.view_available_radio)
        
        # Connect radio buttons
        self.view_all_radio.toggled.connect(lambda: self._set_view_mode('both'))
        self.view_missing_radio.toggled.connect(lambda: self._set_view_mode('missing'))
        self.view_available_radio.toggled.connect(lambda: self._set_view_mode('available'))
        
        control_layout.addWidget(view_group)
        control_layout.addStretch(1)
        
        # Zoom controls - Enhanced with dark mode styling
        zoom_group = QFrame()
        zoom_group.setFrameShape(QFrame.Shape.StyledPanel)
        zoom_group.setStyleSheet("""
            QFrame {
                background-color: #3a3a3a;
                border: 1px solid #545454;
                border-radius: 4px;
            }
        """)
        zoom_layout = QHBoxLayout(zoom_group)
        zoom_layout.setContentsMargins(8, 5, 8, 5)

        zoom_label = QLabel("Zoom:")
        zoom_label.setStyleSheet("color: #f0f0f0; font-weight: bold;")
        zoom_layout.addWidget(zoom_label)

        # Enhanced button styles for dark mode
        button_style = """
            QPushButton {
                background-color: #454545;
                color: #f0f0f0;
                border: 1px solid #646464;
                border-radius: 4px;
                padding: 4px 8px;
                min-height: 24px;
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

        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.setMaximumWidth(30)
        self.zoom_out_btn.setStyleSheet(button_style)
        self.zoom_out_btn.setToolTip("Zoom out")
        self.zoom_out_btn.clicked.connect(self._zoom_out)
        zoom_layout.addWidget(self.zoom_out_btn)

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setMaximumWidth(30)
        self.zoom_in_btn.setStyleSheet(button_style)
        self.zoom_in_btn.setToolTip("Zoom in")
        self.zoom_in_btn.clicked.connect(self._zoom_in)
        zoom_layout.addWidget(self.zoom_in_btn)

        self.zoom_reset_btn = QPushButton("Reset")
        self.zoom_reset_btn.setStyleSheet(button_style)
        self.zoom_reset_btn.setToolTip("Reset to default zoom level")
        self.zoom_reset_btn.clicked.connect(self._zoom_reset)
        zoom_layout.addWidget(self.zoom_reset_btn)
        
        control_layout.addWidget(zoom_group)
        
        # Add control panel to main layout
        layout.addWidget(self.control_panel)
        
        # Timeline canvas area
        self.timeline_area = QFrame()
        self.timeline_area.setFrameShape(QFrame.Shape.StyledPanel)
        self.timeline_area.setMinimumHeight(80)
        self.timeline_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Make timeline area paintable (override the paintEvent method)
        class TimelineFrame(QFrame):
            def __init__(self, parent: 'TimelineVisualization'):
                super().__init__(parent)
                self.parent_widget = parent
            
            def paintEvent(self, event):
                # Standard QFrame painting
                opt = QStyleOption()
                opt.initFrom(self)
                painter = QPainter(self)
                # Check if style exists before calling drawPrimitive
                if style := self.style():
                    style.drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)
                
                # Delegate to parent's drawing method
                self.parent_widget._paint_timeline(painter)
            
            def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
                if event:
                    self.parent_widget._timeline_mouse_move(event)

            def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
                if event:
                    self.parent_widget._timeline_mouse_press(event)

            def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
                if event:
                    self.parent_widget._timeline_mouse_release(event)
        
        # Replace with custom frame
        self.timeline_area = TimelineFrame(self)
        layout.addWidget(self.timeline_area)
    
    def set_data(self, 
                missing_items: List[MissingTimestamp], 
                start_time: datetime, 
                end_time: datetime,
                interval_minutes: Optional[int] = None) -> None:
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
        self.expected_interval = interval_minutes
        
        # Extract timestamps
        self.missing_timestamps = [item.timestamp for item in missing_items 
                                  if not getattr(item, 'is_downloaded', False)]
        
        self.downloaded_timestamps = [item.timestamp for item in missing_items 
                                     if getattr(item, 'is_downloaded', False)]
        
        # If interval is provided, generate expected timestamps
        if interval_minutes is not None and interval_minutes > 0:
            all_expected = []
            current = start_time
            while current <= end_time:
                all_expected.append(current)
                current += timedelta(minutes=interval_minutes)
            
            # Calculate available timestamps as difference
            missing_set = set(self.missing_timestamps)
            downloaded_set = set(self.downloaded_timestamps)
            
            # Available are timestamps that are expected but not missing or downloaded
            self.available_timestamps = [ts for ts in all_expected 
                                        if ts not in missing_set and ts not in downloaded_set]
        
        # Reset view state
        self.zoom_level = 1.0
        self.viewport_start = 0.0
        self.hover_timestamp = None
        self.selection_start = None
        self.selection_end = None
        
        # Refresh the display
        self.update()
    
    def _set_view_mode(self, mode: str) -> None:
        """Set the view mode (both, missing, available)."""
        self.view_mode = mode
        self.update()
    
    def _zoom_in(self) -> None:
        """Zoom in the timeline view."""
        if self.zoom_level < 10.0:  # Limit maximum zoom
            self.zoom_level *= 1.5
            self.update()
    
    def _zoom_out(self) -> None:
        """Zoom out the timeline view."""
        if self.zoom_level > 0.5:  # Limit minimum zoom
            self.zoom_level /= 1.5
            if self.zoom_level < 1.0:
                self.zoom_level = 1.0  # Don't zoom out beyond showing all data
            self.update()
    
    def _zoom_reset(self) -> None:
        """Reset zoom to show all data."""
        self.zoom_level = 1.0
        self.viewport_start = 0.0
        self.update()
    
    def _paint_timeline(self, painter: QPainter) -> None:
        """
        Paint the timeline visualization.
        
        Args:
            painter: QPainter object to use for drawing
        """
        # Ensure we have data to visualize
        if (self.start_timestamp is None or 
            self.end_timestamp is None or 
            self.start_timestamp == self.end_timestamp):
            self._paint_empty_state(painter)
            return
        
        width = self.timeline_area.width()
        height = self.timeline_area.height()
        
        # Draw background
        painter.fillRect(0, 0, width, height, self.bg_color)
        
        # Calculate timeline area
        timeline_height = height * 0.6
        timeline_y = (height - timeline_height) // 2
        timeline_width = width - 40  # Leave margins
        timeline_x = 20
        
        # Draw timeline background
        painter.fillRect(
            QRect(int(timeline_x), int(timeline_y), int(timeline_width), int(timeline_height)),
            self.timeline_bg_color
        )
        
        # Draw timeline border
        painter.setPen(QPen(self.axis_color, 1))
        painter.drawRect(QRect(int(timeline_x), int(timeline_y), int(timeline_width), int(timeline_height)))
        
        # Convert all coordinate values to integers to avoid type errors
        int_x = int(timeline_x)
        int_y = int(timeline_y)
        int_width = int(timeline_width)
        int_height = int(timeline_height)

        # Draw time markers
        self._draw_time_markers(
            painter, int_x, int_y, int_width, int_height
        )

        # Draw data points based on view mode
        if self.view_mode in ['both', 'available']:
            self._draw_data_points(
                painter, self.available_timestamps, self.available_color,
                int_x, int_y, int_width, int_height
            )

        if self.view_mode in ['both', 'missing']:
            self._draw_data_points(
                painter, self.missing_timestamps, self.missing_color,
                int_x, int_y, int_width, int_height
            )

        # Always draw downloaded timestamps
        self._draw_data_points(
            painter, self.downloaded_timestamps, self.downloaded_color,
            int_x, int_y, int_width, int_height
        )

        # Draw selection if active
        if self.selection_start is not None and self.selection_end is not None:
            self._draw_selection(
                painter, int_x, int_y, int_width, int_height
            )

        # Draw hover indicator
        if self.hover_timestamp is not None:
            self._draw_hover_indicator(
                painter, int_x, int_y, int_width, int_height
            )
    
    def _paint_empty_state(self, painter: QPainter) -> None:
        """Paint an empty state when no data is available."""
        width = self.timeline_area.width()
        height = self.timeline_area.height()
        
        # Draw background
        painter.fillRect(0, 0, width, height, self.bg_color)
        
        # Draw message
        painter.setPen(QColor(200, 200, 200))  # Light gray for better visibility in dark mode
        font = painter.font()
        font.setPointSize(12)
        painter.setFont(font)
        
        text = "No data available for visualization"
        text_rect = painter.fontMetrics().boundingRect(0, 0, width, height, Qt.AlignmentFlag.AlignCenter, text)
        painter.drawText((width - text_rect.width()) // 2, height // 2, text)
    
    def _draw_time_markers(self,
                          painter: QPainter,
                          x: int, y: int,
                          width: int, height: int) -> None:
        """
        Draw time markers along the timeline.

        Args:
            painter: QPainter object to use for drawing
            x: X coordinate of timeline start
            y: Y coordinate of timeline top
            width: Width of timeline
            height: Height of timeline
        """
        # Ensure values are integers to avoid type errors
        x, y = int(x), int(y)
        width, height = int(width), int(height)
        """
        Draw time markers along the timeline.
        
        Args:
            painter: QPainter object to use for drawing
            x: X coordinate of timeline start
            y: Y coordinate of timeline top
            width: Width of timeline
            height: Height of timeline
        """
        if self.start_timestamp is None or self.end_timestamp is None:
            return
            
        # Calculate total duration in seconds
        total_duration = (self.end_timestamp - self.start_timestamp).total_seconds()
        
        # Don't try to draw if duration is zero
        if total_duration <= 0:
            return
        
        # Determine appropriate marker interval
        intervals = [  # (seconds, format)
            (60,              "%H:%M"),       # 1 minute
            (300,             "%H:%M"),       # 5 minutes
            (600,             "%H:%M"),       # 10 minutes
            (1800,            "%H:%M"),       # 30 minutes
            (3600,            "%H:%M"),       # 1 hour
            (7200,            "%H:%M"),       # 2 hours
            (14400,           "%H:%M"),       # 4 hours
            (21600,           "%H:%M"),       # 6 hours
            (43200,           "%b %d %H:%M"), # 12 hours
            (86400,           "%b %d"),       # 1 day
            (172800,          "%b %d"),       # 2 days
            (432000,          "%b %d"),       # 5 days
            (604800,          "%b %d"),       # 1 week
            (1209600,         "%b %d"),       # 2 weeks
            (2592000,         "%b %Y"),       # 1 month
            (5184000,         "%b %Y"),       # 2 months
            (15552000,        "%b %Y"),       # 6 months
            (31536000,        "%Y"),          # 1 year
        ]
        
        # Adjust for zoom level
        visible_duration = total_duration / self.zoom_level
        
        # Find appropriate interval
        marker_interval = intervals[-1]  # Default to largest
        for interval, format_str in intervals:
            # Aim for around 5-10 markers across the visible range
            if visible_duration / interval <= 10:
                marker_interval = (interval, format_str)
                break
        
        # Draw markers
        interval_seconds, format_str = marker_interval
        
        # Calculate visible range
        visible_start = self.start_timestamp + timedelta(
            seconds=total_duration * self.viewport_start
        )
        visible_end = visible_start + timedelta(seconds=visible_duration)
        
        # Round down to nearest interval
        marker_time = datetime.fromtimestamp(
            (visible_start.timestamp() // interval_seconds) * interval_seconds
        )
        
        # Set up font and pen - use brighter color for dark mode
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        
        while marker_time <= visible_end:
            # Skip if before visible range
            if marker_time < visible_start:
                marker_time += timedelta(seconds=interval_seconds)
                continue
            
            # Calculate position
            position_ratio = ((marker_time - self.start_timestamp).total_seconds() / total_duration - self.viewport_start) * self.zoom_level
            
            if 0 <= position_ratio <= 1:
                marker_x = x + position_ratio * width
                
                # Draw tick
                painter.drawLine(
                    int(marker_x), int(y + height),
                    int(marker_x), int(y + height + 5)
                )
                
                # Draw label
                marker_text = marker_time.strftime(format_str)
                text_width = painter.fontMetrics().horizontalAdvance(marker_text)
                painter.drawText(
                    int(marker_x - text_width // 2),
                    y + height + 18,
                    marker_text
                )
            
            marker_time += timedelta(seconds=interval_seconds)
    
    def _draw_data_points(self,
                         painter: QPainter,
                         timestamps: List[datetime],
                         color: QColor,
                         x: int, y: int,
                         width: int, height: int) -> None:
        # Ensure values are integers to avoid type errors
        x, y = int(x), int(y)
        width, height = int(width), int(height)
        """
        Draw data points on the timeline.

        Args:
            painter: QPainter object to use for drawing
            timestamps: List of timestamps to draw
            color: Color to use for drawing
            x: X coordinate of timeline start
            y: Y coordinate of timeline top
            width: Width of timeline
            height: Height of timeline
        """
        if not timestamps or self.start_timestamp is None or self.end_timestamp is None:
            return

        # Calculate total duration in seconds
        total_duration = (self.end_timestamp - self.start_timestamp).total_seconds()

        # Don't try to draw if duration is zero
        if total_duration <= 0:
            return

        # Set up pen with antialiasing for smoother appearance
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Create a slightly darker outline color for better definition
        outline_color = QColor(color)
        outline_color = outline_color.darker(120)

        painter.setPen(QPen(outline_color, 1))
        painter.setBrush(QBrush(color))

        # Calculate visible range
        visible_start = self.start_timestamp + timedelta(
            seconds=total_duration * self.viewport_start
        )
        visible_duration = total_duration / self.zoom_level
        visible_end = visible_start + timedelta(seconds=visible_duration)

        # Calculate point size based on density with a better minimum size
        point_base_size = min(10, max(3, int(width / (len(timestamps) + 1))))
        point_width = point_base_size

        # Special handling for intervals
        if self.expected_interval is not None and self.expected_interval > 0:
            expected_interval_seconds = self.expected_interval * 60
            pixels_per_interval = (expected_interval_seconds / total_duration) * width * self.zoom_level

            # Adjust point width to not overlap
            point_width = min(point_base_size, int(pixels_per_interval * 0.8))

        # Draw points
        for timestamp in timestamps:
            # Skip if outside visible range
            if timestamp < visible_start or timestamp > visible_end:
                continue

            # Calculate position
            position_ratio = ((timestamp - self.start_timestamp).total_seconds() / total_duration - self.viewport_start) * self.zoom_level

            if 0 <= position_ratio <= 1:
                point_x = x + position_ratio * width

                # Draw a rounded rectangle for better visual appeal
                # Determine if we should use rectangles or rounded shapes based on density
                if point_width > 4:
                    # Draw as rounded rectangle for larger points
                    painter.drawRoundedRect(
                        int(point_x - point_width / 2),
                        int(y + height / 4),  # Middle height
                        point_width,
                        int(height / 2),
                        2, 2  # Corner radius
                    )
                else:
                    # Use simple rectangle for smaller points to maintain visibility
                    painter.drawRect(
                        int(point_x - point_width / 2),
                        int(y + height / 4),  # Middle height
                        point_width,
                        int(height / 2)
                    )
    
    def _draw_selection(self,
                       painter: QPainter,
                       x: int, y: int,
                       width: int, height: int) -> None:
        # Ensure values are integers to avoid type errors
        x, y = int(x), int(y)
        width, height = int(width), int(height)
        """
        Draw the current selection on the timeline.

        Args:
            painter: QPainter object to use for drawing
            x: X coordinate of timeline start
            y: Y coordinate of timeline top
            width: Width of timeline
            height: Height of timeline
        """
        if self.selection_start is None or self.selection_end is None:
            return

        # Ensure start is before end
        start_pos = min(self.selection_start, self.selection_end)
        end_pos = max(self.selection_start, self.selection_end)

        # Enable antialiasing for smoother drawing
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Create a gradient for selection rectangle
        gradient = QLinearGradient(start_pos, y, end_pos, y)
        gradient.setColorAt(0, QColor(30, 110, 190, 160))    # Start with slightly darker, more transparent
        gradient.setColorAt(0.5, QColor(42, 130, 218, 180))  # Middle more vibrant
        gradient.setColorAt(1, QColor(30, 110, 190, 160))    # End with slightly darker, more transparent

        # Draw selection rectangle with rounded corners
        path = QPainterPath()
        # Add 1px padding on top and bottom for better visual appeal
        path.addRoundedRect(
            QRectF(start_pos, y - 1, end_pos - start_pos, height + 2),
            3, 3  # Subtle rounding of corners
        )

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawPath(path)

        # Draw more visible selection borders with subtle glow
        highlight_pen = QPen(QColor(80, 170, 255), 2)
        painter.setPen(highlight_pen)

        # Draw start handle with rounded cap for better appearance
        start_handle_path = QPainterPath()
        start_handle_path.moveTo(start_pos, y - 2)
        start_handle_path.lineTo(start_pos, y + height + 2)
        painter.drawPath(start_handle_path)

        # Draw end handle
        end_handle_path = QPainterPath()
        end_handle_path.moveTo(end_pos, y - 2)
        end_handle_path.lineTo(end_pos, y + height + 2)
        painter.drawPath(end_handle_path)

        # Add handle indicators at top and bottom
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawEllipse(start_pos - 3, y - 3, 6, 6)  # Top handle start
        painter.drawEllipse(start_pos - 3, y + height - 3, 6, 6)  # Bottom handle start
        painter.drawEllipse(end_pos - 3, y - 3, 6, 6)  # Top handle end
        painter.drawEllipse(end_pos - 3, y + height - 3, 6, 6)  # Bottom handle end
    
    def _draw_hover_indicator(self,
                             painter: QPainter,
                             x: int, y: int,
                             width: int, height: int) -> None:
        # Ensure values are integers to avoid type errors
        x, y = int(x), int(y)
        width, height = int(width), int(height)
        """
        Draw an indicator for the currently hovered timestamp.

        Args:
            painter: QPainter object to use for drawing
            x: X coordinate of timeline start
            y: Y coordinate of timeline top
            width: Width of timeline
            height: Height of timeline
        """
        if self.hover_timestamp is None or self.start_timestamp is None or self.end_timestamp is None:
            return

        # Calculate position
        total_duration = (self.end_timestamp - self.start_timestamp).total_seconds()
        position_ratio = ((self.hover_timestamp - self.start_timestamp).total_seconds() / total_duration - self.viewport_start) * self.zoom_level

        if 0 <= position_ratio <= 1:
            hover_x = x + position_ratio * width

            # Draw enhanced vertical line with animation-like gradient
            gradient = QLinearGradient(0, y, 0, y + height)
            gradient.setColorAt(0, QColor(120, 195, 255, 180))
            gradient.setColorAt(0.5, QColor(42, 130, 218, 230))
            gradient.setColorAt(1, QColor(120, 195, 255, 180))

            # Use a custom pen with gradient for the line
            gradient_pen = QPen()
            gradient_pen.setBrush(QBrush(gradient))
            gradient_pen.setWidth(2)
            gradient_pen.setStyle(Qt.PenStyle.DashLine)

            painter.setPen(gradient_pen)
            painter.drawLine(
                int(hover_x), y,
                int(hover_x), y + height
            )

            # Draw dot indicator at hover position for better visibility
            painter.setBrush(QBrush(QColor(120, 195, 255)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(hover_x) - 4, int(y + height/2) - 4, 8, 8)

            # Draw enhanced timestamp tooltip
            tooltip_text = self.hover_timestamp.strftime("%Y-%m-%d %H:%M:%S")
            text_width = painter.fontMetrics().horizontalAdvance(tooltip_text)
            text_height = painter.fontMetrics().height()

            tooltip_x = int(hover_x - text_width / 2)
            tooltip_y = y - text_height - 7  # Move a bit higher for cleaner look

            # Ensure tooltip stays within widget bounds
            if tooltip_x < 5:
                tooltip_x = 5
            elif tooltip_x + text_width > width - 5:
                tooltip_x = width - text_width - 5

            # Draw tooltip with rounded corners
            tooltip_bg = QColor(45, 45, 45, 240)  # Semi-transparent dark background
            tooltip_border = QColor(80, 160, 230)  # Bright blue border

            # Use path for rounded corners
            path = QPainterPath()
            path.addRoundedRect(
                QRectF(tooltip_x - 6, tooltip_y - 5, text_width + 12, text_height + 10),
                6, 6  # Corner radius
            )

            # Draw shadow first (slight offset)
            shadow_color = QColor(0, 0, 0, 80)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(shadow_color))
            painter.drawPath(path.translated(2, 2))  # Shadow offset

            # Draw tooltip background
            painter.setBrush(QBrush(tooltip_bg))
            painter.setPen(QPen(tooltip_border, 1.5))
            painter.drawPath(path)

            # Draw tooltip text with slight shadow for better readability
            painter.setPen(QPen(QColor(0, 0, 0, 100), 1))  # Text shadow
            painter.drawText(tooltip_x + 1, tooltip_y + text_height - 1, tooltip_text)
            painter.setPen(QPen(QColor(240, 240, 240), 1))  # Actual text
            painter.drawText(tooltip_x, tooltip_y + text_height - 2, tooltip_text)
    
    def _timeline_mouse_move(self, event: QMouseEvent) -> None:
        """
        Handle mouse move events on the timeline.
        
        Args:
            event: Mouse event object
        """
        if self.start_timestamp is None or self.end_timestamp is None:
            return
            
        # Update hover timestamp
        self.hover_timestamp = self._position_to_timestamp(event.position().x())
        
        # Update selection end if selecting
        if self.is_selecting and self.selection_start is not None:
            self.selection_end = int(event.position().x())
        
        # Update the display
        self.update()
    
    def _timeline_mouse_press(self, event: QMouseEvent) -> None:
        """
        Handle mouse press events on the timeline.
        
        Args:
            event: Mouse event object
        """
        if self.start_timestamp is None or self.end_timestamp is None:
            return
            
        # Start selection
        self.is_selecting = True
        self.selection_start = int(event.position().x())
        self.selection_end = self.selection_start
        
        # Update the display
        self.update()
    
    def _timeline_mouse_release(self, event: QMouseEvent) -> None:
        """
        Handle mouse release events on the timeline.
        
        Args:
            event: Mouse event object
        """
        if not self.is_selecting or self.selection_start is None:
            return
            
        self.is_selecting = False
        self.selection_end = int(event.position().x())
        
        # If it's just a click (no drag), emit timestamp selected
        if abs(self.selection_start - self.selection_end) < 5:
            # Single click - emit timestamp selected
            ts = self._position_to_timestamp(event.position().x())
            if ts is not None:
                self.timestampSelected.emit(ts)
                
            # Reset selection
            self.selection_start = None
            self.selection_end = None
        else:
            # Selection drag - emit range selected
            start_pos = min(self.selection_start, self.selection_end)
            end_pos = max(self.selection_start, self.selection_end)
            
            start_ts = self._position_to_timestamp(start_pos)
            end_ts = self._position_to_timestamp(end_pos)
            
            if start_ts is not None and end_ts is not None:
                self.rangeSelected.emit(start_ts, end_ts)
        
        # Update the display
        self.update()
    
    def _position_to_timestamp(self, position: float) -> Optional[datetime]:
        """
        Convert a pixel position to a timestamp.
        
        Args:
            position: X position in pixels
            
        Returns:
            Corresponding timestamp or None if invalid
        """
        if self.start_timestamp is None or self.end_timestamp is None:
            return None
            
        # Calculate timeline area
        timeline_x = 20
        timeline_width = self.timeline_area.width() - 40
        
        # Check if position is within timeline
        if position < timeline_x or position > timeline_x + timeline_width:
            return None
            
        # Calculate position as a ratio of the timeline
        position_ratio = (position - timeline_x) / timeline_width
        
        # Adjust for zoom and pan
        adjusted_ratio = position_ratio / self.zoom_level + self.viewport_start
        
        # Ensure within bounds
        if adjusted_ratio < 0:
            adjusted_ratio = 0
        elif adjusted_ratio > 1:
            adjusted_ratio = 1
            
        # Calculate timestamp
        total_duration = (self.end_timestamp - self.start_timestamp).total_seconds()
        seconds_offset = total_duration * adjusted_ratio
        
        return self.start_timestamp + timedelta(seconds=seconds_offset)


class MissingDataCalendarView(QWidget):
    """Calendar view showing data coverage by day and hour."""
    
    dateSelected = pyqtSignal(datetime)
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the calendar view widget."""
        super().__init__(parent)
        
        # Set up the UI
        self.setMinimumSize(300, 200)
        
        # Data for visualization
        self.start_date: Optional[datetime] = None
        self.end_date: Optional[datetime] = None
        self.data_by_day: Dict[str, Dict[int, int]] = {}  # day -> hour -> status
        
        # Statuses: 0 = missing, 1 = available, 2 = downloaded
        # Use slightly brighter colors for better visibility in dark mode
        self.status_colors = [
            QColor(255, 80, 90),    # Missing: Bright Red
            QColor(60, 200, 90),    # Available: Bright Green
            QColor(30, 150, 255)    # Downloaded: Bright Blue
        ]
        
        # UI state
        self.selected_day: Optional[str] = None  # YYYY-MM-DD
        self.selected_hour: Optional[int] = None
        
        # Set up timer for delayed repaints
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the calendar view UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Title - dark mode styling
        title_label = QLabel("Data Coverage by Day/Hour")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #f0f0f0;")
        layout.addWidget(title_label)
        
        # Calendar scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Calendar container
        self.calendar_container = QWidget()
        self.calendar_layout = QVBoxLayout(self.calendar_container)
        self.calendar_layout.setContentsMargins(0, 0, 0, 0)
        self.calendar_layout.setSpacing(1)
        
        self.scroll_area.setWidget(self.calendar_container)
        layout.addWidget(self.scroll_area)
        
        # Color legend - dark mode styling
        legend_frame = QFrame()
        legend_frame.setFrameShape(QFrame.Shape.StyledPanel)
        legend_frame.setStyleSheet("QFrame { background-color: #3a3a3a; border: 1px solid #545454; border-radius: 4px; }")
        legend_layout = QHBoxLayout(legend_frame)
        legend_layout.setContentsMargins(5, 5, 5, 5)

        # Create color boxes with labels
        status_names = ["Missing", "Available", "Downloaded"]

        for i, name in enumerate(status_names):
            # Color box
            color_box = QFrame()
            color_box.setFixedSize(16, 16)
            color_box.setStyleSheet(f"background-color: {self.status_colors[i].name()}; border: 1px solid #545454;")

            # Label - light text for dark mode
            label = QLabel(name)
            label.setStyleSheet("color: #f0f0f0;")

            # Add to layout with spacer
            color_layout = QHBoxLayout()
            color_layout.setContentsMargins(0, 0, 0, 0)
            color_layout.setSpacing(5)
            color_layout.addWidget(color_box)
            color_layout.addWidget(label)

            legend_layout.addLayout(color_layout)

            # Add spacer between items
            if i < len(status_names) - 1:
                legend_layout.addSpacing(10)

        legend_layout.addStretch()
        layout.addWidget(legend_frame)
    
    def set_data(self, 
                missing_items: List[MissingTimestamp], 
                start_date: datetime, 
                end_date: datetime,
                interval_minutes: Optional[int] = None) -> None:
        """
        Set data for the calendar view.
        
        Args:
            missing_items: List of missing timestamps
            start_date: Start of the time range
            end_date: End of the time range
            interval_minutes: Expected interval between timestamps (in minutes)
        """
        self.start_date = start_date
        self.end_date = end_date
        
        # Clear previous data
        self.data_by_day = {}
        
        # Process missing items
        for item in missing_items:
            day_key = item.timestamp.strftime("%Y-%m-%d")
            hour = item.timestamp.hour
            
            # Initialize day if needed
            if day_key not in self.data_by_day:
                self.data_by_day[day_key] = {}
            
            # Set status: 0 = missing, 2 = downloaded
            if getattr(item, 'is_downloaded', False):
                self.data_by_day[day_key][hour] = 2
            else:
                self.data_by_day[day_key][hour] = 0
        
        # Fill in expected timestamps if interval is provided
        if interval_minutes is not None and interval_minutes > 0:
            # Generate all expected timestamps
            current = start_date
            while current <= end_date:
                day_key = current.strftime("%Y-%m-%d")
                hour = current.hour
                
                # Initialize day if needed
                if day_key not in self.data_by_day:
                    self.data_by_day[day_key] = {}
                
                # If hour not already marked as missing or downloaded, mark as available
                if hour not in self.data_by_day[day_key]:
                    self.data_by_day[day_key][hour] = 1  # available
                
                current += timedelta(minutes=interval_minutes)
        
        # Create the calendar UI
        self._create_calendar_ui()
    
    def _create_calendar_ui(self) -> None:
        """Create the calendar UI based on current data."""
        # Clear previous UI
        while self.calendar_layout.count():
            item = self.calendar_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        
        if not self.data_by_day:
            # No data to display
            label = QLabel("No data to display")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.calendar_layout.addWidget(label)
            return
        
        # Sort days
        days = sorted(self.data_by_day.keys())
        
        # Create day rows
        for day in days:
            day_frame = self._create_day_row(day)
            self.calendar_layout.addWidget(day_frame)
        
        # Add stretch to bottom
        self.calendar_layout.addStretch()
    
    def _create_day_row(self, day: str) -> QFrame:
        """
        Create a row representing a day with hour cells.

        Args:
            day: Day string in YYYY-MM-DD format

        Returns:
            Frame containing the day row
        """
        # Create frame - dark mode styling
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("QFrame { background-color: #2d2d2d; border: 1px solid #454545; border-radius: 4px; }")

        # Create layout
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # Day label - styled for dark mode
        try:
            day_date = datetime.strptime(day, "%Y-%m-%d")
            day_label = QLabel(day_date.strftime("%a, %b %d, %Y"))
            day_label.setStyleSheet("font-weight: bold; color: #f0f0f0;")
        except ValueError:
            day_label = QLabel(day)
            day_label.setStyleSheet("color: #f0f0f0;")

        layout.addWidget(day_label)

        # Hours grid
        hours_widget = QWidget()
        hours_widget.setStyleSheet("background-color: transparent;")
        hours_layout = QGridLayout(hours_widget)
        hours_layout.setContentsMargins(0, 0, 0, 0)
        hours_layout.setSpacing(1)

        # Create hour cells
        for hour in range(24):
            col = hour % 12
            row = hour // 12

            # Create cell
            cell = self._create_hour_cell(day, hour)
            hours_layout.addWidget(cell, row, col)

        layout.addWidget(hours_widget)

        return frame
    
    def _create_hour_cell(self, day: str, hour: int) -> QFrame:
        """
        Create a cell representing an hour.

        Args:
            day: Day string in YYYY-MM-DD format
            hour: Hour (0-23)

        Returns:
            Frame representing the hour cell
        """
        # Create a custom cell class that directly paints its content
        # This ensures the hour text is always visible regardless of Qt's style system
        class HourCell(QFrame):
            def __init__(self, parent=None, hour=0, day="", bg_color=QColor(70, 70, 70),
                        text_color=QColor(240, 240, 240), is_selected=False):
                super().__init__(parent)
                self.hour = hour
                self.day = day
                self.bg_color = bg_color
                self.text_color = text_color
                self.is_selected = is_selected
                self.is_hovering = False
                self.time_text = f"{hour:02d}:00"

                # Enable mouse tracking for hover effects
                self.setMouseTracking(True)

            def paintEvent(self, event):
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)

                # Draw background
                if self.is_selected:
                    # Draw with selection border
                    painter.fillRect(1, 1, self.width()-2, self.height()-2, self.bg_color)
                    pen = QPen(QColor(255, 255, 255), 2)  # White border for selection
                    painter.setPen(pen)
                    painter.drawRect(1, 1, self.width()-3, self.height()-3)
                else:
                    # Draw normal cell
                    painter.fillRect(0, 0, self.width(), self.height(), self.bg_color)
                    pen = QPen(QColor(85, 85, 85), 1)  # Dark gray border
                    painter.setPen(pen)
                    painter.drawRect(0, 0, self.width()-1, self.height()-1)

                # Draw hover effect
                if self.is_hovering and not self.is_selected:
                    hover_brush = QBrush(QColor(255, 255, 255, 40))  # Semi-transparent white
                    painter.fillRect(1, 1, self.width()-2, self.height()-2, hover_brush)

                # Draw time text
                font = painter.font()
                font.setBold(True)
                font.setPointSize(12)  # Larger, more visible font
                painter.setFont(font)

                painter.setPen(self.text_color)
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.time_text)

            def enterEvent(self, event):
                self.is_hovering = True
                self.update()

            def leaveEvent(self, event):
                self.is_hovering = False
                self.update()

        # Determine colors based on status
        status = self.data_by_day.get(day, {}).get(hour, -1)

        # Default colors
        bg_color = QColor(70, 70, 70)  # Dark gray default
        text_color = QColor(240, 240, 240)  # White text

        if status >= 0 and status < len(self.status_colors):
            bg_color = self.status_colors[status]

            # For green (available) cells, use black text for better contrast
            if status == 1:  # Available (green)
                text_color = QColor(0, 0, 0)  # Black text

        # Create the custom cell
        is_selected = (day == self.selected_day and hour == self.selected_hour)
        cell = HourCell(hour=hour, day=day, bg_color=bg_color, text_color=text_color,
                       is_selected=is_selected)

        # Set fixed size - increased for better visibility
        cell.setFixedSize(65, 36)

        # Add tooltip for better UX
        cell.setToolTip(f"Day: {day}, Time: {hour:02d}:00")

        # Save references for click handler
        setattr(cell, '_cell_day', day)
        setattr(cell, '_cell_hour', hour)

        # Define click handler
        def cell_click_handler(cell_widget, event):
            if hasattr(cell_widget, '_cell_day') and hasattr(cell_widget, '_cell_hour'):
                self._cell_clicked(getattr(cell_widget, '_cell_day'), getattr(cell_widget, '_cell_hour'))

        # Set the method properly using descriptor protocol
        setattr(cell, 'mousePressEvent', cell_click_handler.__get__(cell, type(cell)))

        return cell
    
    def _cell_clicked(self, day: str, hour: int) -> None:
        """
        Handle cell click event.
        
        Args:
            day: Day string in YYYY-MM-DD format
            hour: Hour (0-23)
        """
        self.selected_day = day
        self.selected_hour = hour
        
        # Convert to datetime
        try:
            date = datetime.strptime(day, "%Y-%m-%d")
            selected_datetime = date.replace(hour=hour, minute=0, second=0, microsecond=0)
            
            # Emit signal
            self.dateSelected.emit(selected_datetime)
            
            # Refresh UI to show selection
            self._create_calendar_ui()
            
        except ValueError:
            pass