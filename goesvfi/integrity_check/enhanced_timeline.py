"""
Enhanced timeline visualization for GOES satellite data integrity.

This module provides an improved timeline visualization with better contrast,
interaction feedback, and visual appearance.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union, cast

from PyQt6.QtCore import (
    QEasingCurve,
    QPoint,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
    QResizeEvent,
)
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStyle,
    QStyleOption,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from goesvfi.integrity_check.timeline_visualization import TimelineVisualization
from goesvfi.integrity_check.view_model import MissingTimestamp


class EnhancedTimeline(TimelineVisualization):
    """
    Enhanced timeline visualization with improved visual appearance and interaction feedback.

    This class extends the base TimelineVisualization with:
    - Better visual contrast for data points
    - Enhanced selection and hover effects
    - Improved labeling and grid lines
    - Animation effects for user interactions
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the enhanced timeline visualization."""
        super().__init__(parent)

        # Enhanced colors with better contrast
        self.available_color = QColor(60, 180, 80)  # Brighter green
        self.missing_color = QColor(230, 70, 80)  # Brighter red
        self.downloaded_color = QColor(30, 140, 240)  # Brighter blue
        self.bg_color = QColor(40, 40, 40)  # Darker background for better contrast
        self.timeline_bg_color = QColor(
            55, 55, 55
        )  # Slightly lighter gray for timeline
        self.axis_color = QColor(200, 200, 200)  # Brighter axis color
        self.grid_color = QColor(80, 80, 80)  # Color for grid lines

        # Animation properties
        self.animation_active = False
        self.animation_progress = 0.0
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_timer.setInterval(16)  # ~60fps

        # Interactive feedback
        self.highlight_pulse = 0.0
        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self._update_pulse)
        self.pulse_timer.setInterval(50)
        self.pulse_timer.start()

        # Enhanced control panel
        self._enhance_control_panel()

    def _enhance_control_panel(self) -> None:
        """
        Apply enhancements to the control panel.

        Note: In the optimized UI, we hide the internal controls
        as they're duplicated in the main control panel.
        """
        # Set control panel color
        if hasattr(self, "control_panel"):
            # Hide the internal control panel since we now have the optimized
            # controls in the parent container
            self.control_panel.setVisible(False)

            # Apply styling for when it might be visible in other contexts
            self.control_panel.setStyleSheet(
                """
                background-color: #2d2d2d;
                border: 1px solid #454545;
                border-radius: 4px;
            """
            )

    def _paint_timeline(self, painter: QPainter) -> None:
        """
        Paint the enhanced timeline visualization.

        Args:
            painter: QPainter object to use for drawing
        """
        # Let the parent class handle the basic painting
        super()._paint_timeline(painter)

        # Add grid lines if we have data
        if (
            self.start_timestamp is not None
            and self.end_timestamp is not None
            and self.start_timestamp != self.end_timestamp
        ):
            self._draw_grid(painter)

            # If we have selection or hover, add highlight overlay
            if self.selection_start is not None or self.hover_timestamp is not None:
                self._draw_highlights(painter)

    def _draw_grid(self, painter: QPainter) -> None:
        """
        Draw grid lines for better visual reference.

        Args:
            painter: QPainter object to use for drawing
        """
        if self.start_timestamp is None or self.end_timestamp is None:
            return

        width = self.timeline_area.width()
        height = self.timeline_area.height()

        # Calculate timeline area
        timeline_height = height * 0.6
        timeline_y = (height - timeline_height) // 2
        timeline_width = width - 40  # Leave margins
        timeline_x = 20

        # Convert to integers
        x = int(timeline_x)
        y = int(timeline_y)
        w = int(timeline_width)
        h = int(timeline_height)

        # Calculate total duration in seconds
        total_duration = (self.end_timestamp - self.start_timestamp).total_seconds()

        # Don't try to draw if duration is zero
        if total_duration <= 0:
            return

        # Determine appropriate grid interval
        intervals = [  # (seconds, opacity)
            (60, 0.2),  # 1 minute
            (300, 0.3),  # 5 minutes
            (1800, 0.4),  # 30 minutes
            (3600, 0.5),  # 1 hour
            (86400, 0.6),  # 1 day
        ]

        # Adjust for zoom level
        visible_duration = total_duration / self.zoom_level

        # Find appropriate interval
        grid_interval = intervals[-1]  # Default to largest
        for interval, opacity in intervals:
            # Aim for a reasonable number of grid lines
            if visible_duration / interval <= 20:
                grid_interval = (interval, opacity)
                break

        # Draw grid lines
        interval_seconds, opacity = grid_interval

        # Calculate visible range
        visible_start = self.start_timestamp + timedelta(
            seconds=total_duration * self.viewport_start
        )
        visible_end = visible_start + timedelta(seconds=visible_duration)

        # Round down to nearest interval
        grid_time = datetime.fromtimestamp(
            (visible_start.timestamp() // interval_seconds) * interval_seconds
        )

        # Set up grid pen
        grid_pen = QPen(
            QColor(
                self.grid_color.red(),
                self.grid_color.green(),
                self.grid_color.blue(),
                int(255 * opacity),
            )
        )
        grid_pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(grid_pen)

        # Draw vertical grid lines
        while grid_time <= visible_end:
            # Skip if before visible range
            if grid_time < visible_start:
                grid_time += timedelta(seconds=interval_seconds)
                continue

            # Calculate position
            position_ratio = (
                (grid_time - self.start_timestamp).total_seconds() / total_duration
                - self.viewport_start
            ) * self.zoom_level

            if 0 <= position_ratio <= 1:
                grid_x = x + position_ratio * w

                # Draw vertical grid line
                painter.drawLine(int(grid_x), y, int(grid_x), y + h)

            grid_time += timedelta(seconds=interval_seconds)

    def _draw_highlights(self, painter: QPainter) -> None:
        """
        Draw highlights for the current selection or hover state.

        Args:
            painter: QPainter object to use for drawing
        """
        if self.start_timestamp is None or self.end_timestamp is None:
            return

        width = self.timeline_area.width()
        height = self.timeline_area.height()

        # Calculate timeline area
        timeline_height = height * 0.6
        timeline_y = (height - timeline_height) // 2
        timeline_width = width - 40  # Leave margins
        timeline_x = 20

        # Convert to integers
        x = int(timeline_x)
        y = int(timeline_y)
        w = int(timeline_width)
        h = int(timeline_height)

        # Draw pulsing hover indicator for a single hover timestamp
        if self.hover_timestamp is not None and self.selection_start is None:
            # Calculate position
            total_duration = (self.end_timestamp - self.start_timestamp).total_seconds()
            position_ratio = (
                (self.hover_timestamp - self.start_timestamp).total_seconds()
                / total_duration
                - self.viewport_start
            ) * self.zoom_level

            if 0 <= position_ratio <= 1:
                hover_x = x + position_ratio * w

                # Create pulsing glow
                pulse_factor = 0.5 + 0.5 * self.highlight_pulse  # 0.5 to 1.0

                # Gradient for glow
                glow = QRadialGradient(
                    int(hover_x),
                    int(y + h / 2),  # Center
                    int(h / 2 * pulse_factor),  # Radius
                )
                glow.setColorAt(0, QColor(80, 160, 255, 150))  # Center
                glow.setColorAt(0.7, QColor(80, 160, 255, 70))  # Mid
                glow.setColorAt(1, QColor(80, 160, 255, 0))  # Edge

                # Draw glow
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.setBrush(QBrush(glow))
                painter.setPen(Qt.PenStyle.NoPen)

                # Create bigger/smaller circle based on pulse
                glow_size = int(h / 2 * pulse_factor)
                painter.drawEllipse(
                    int(hover_x - glow_size),
                    int(y + h / 2 - glow_size),
                    glow_size * 2,
                    glow_size * 2,
                )

    def _update_animation(self) -> None:
        """Update animation progress and redraw the widget."""
        if not self.animation_active:
            self.animation_timer.stop()
            return

        # Update animation progress
        self.animation_progress += 0.05
        if self.animation_progress >= 1.0:
            self.animation_progress = 0.0
            self.animation_active = False
            self.animation_timer.stop()

        # Redraw
        self.update()

    def _update_pulse(self) -> None:
        """Update pulse effect for hover highlights."""
        # Update pulse value using sine wave for smooth oscillation
        import math

        self.highlight_pulse = (math.sin(self.pulse_timer.interval() * 0.002) + 1) / 2

        # Only trigger redraw if we have a hover point
        if self.hover_timestamp is not None:
            self.update()

    def _draw_data_points(
        self,
        painter: QPainter,
        timestamps: List[datetime],
        color: QColor,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> None:
        """
        Draw data points with enhanced visual style.

        Args:
            painter: QPainter object to use for drawing
            timestamps: List of timestamps to draw
            color: Color to use for drawing
            x: X coordinate of timeline start
            y: Y coordinate of timeline top
            width: Width of timeline
            height: Height of timeline
        """
        # Check conditions from parent method
        if not timestamps or self.start_timestamp is None or self.end_timestamp is None:
            return

        # Calculate total duration in seconds
        total_duration = (self.end_timestamp - self.start_timestamp).total_seconds()

        # Don't try to draw if duration is zero
        if total_duration <= 0:
            return

        # Set up pen with antialiasing for smoother appearance
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Create darker outline color for better definition
        outline_color = QColor(color)
        outline_color = outline_color.darker(120)

        # Set pen and brush
        painter.setPen(QPen(outline_color, 1))

        # Create a gradient brush for 3D effect
        point_gradient = QLinearGradient(0, y, 0, y + height)
        point_gradient.setColorAt(0, color.lighter(120))  # Lighter at top
        point_gradient.setColorAt(1, color.darker(120))  # Darker at bottom
        painter.setBrush(QBrush(point_gradient))

        # Calculate visible range
        visible_start = self.start_timestamp + timedelta(
            seconds=total_duration * self.viewport_start
        )
        visible_duration = total_duration / self.zoom_level
        visible_end = visible_start + timedelta(seconds=visible_duration)

        # Determine point size with extra size for legibility
        point_base_size = min(12, max(4, int(width / (len(timestamps) + 1))))
        point_width = point_base_size

        # Special handling for intervals
        if self.expected_interval is not None and self.expected_interval > 0:
            expected_interval_seconds = self.expected_interval * 60
            pixels_per_interval = (
                (expected_interval_seconds / total_duration) * width * self.zoom_level
            )

            # Adjust point width to not overlap
            point_width = min(point_base_size, int(pixels_per_interval * 0.8))

        # Draw points with enhanced visual style
        for timestamp in timestamps:
            # Skip if outside visible range
            if timestamp < visible_start or timestamp > visible_end:
                continue

            # Calculate position
            position_ratio = (
                (timestamp - self.start_timestamp).total_seconds() / total_duration
                - self.viewport_start
            ) * self.zoom_level

            if 0 <= position_ratio <= 1:
                point_x = x + position_ratio * width

                # Draw points with visual flair based on density
                if point_width > 6:
                    # Draw as rounded rectangle with shadow for larger points
                    # Shadow first
                    shadow_color = QColor(0, 0, 0, 80)
                    painter.setBrush(QBrush(shadow_color))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRoundedRect(
                        int(point_x - point_width / 2) + 2,
                        int(y + height / 4) + 2,
                        point_width,
                        int(height / 2),
                        3,
                        3,  # Corner radius
                    )

                    # Then actual point
                    painter.setBrush(QBrush(point_gradient))
                    painter.setPen(QPen(outline_color, 1))
                    painter.drawRoundedRect(
                        int(point_x - point_width / 2),
                        int(y + height / 4),
                        point_width,
                        int(height / 2),
                        3,
                        3,  # Corner radius
                    )
                elif point_width > 3:
                    # Medium-sized points with slight rounding
                    painter.setBrush(QBrush(color))
                    painter.drawRoundedRect(
                        int(point_x - point_width / 2),
                        int(y + height / 4),
                        point_width,
                        int(height / 2),
                        2,
                        2,  # Corner radius
                    )
                else:
                    # Very small points - use simple rectangles for clarity
                    painter.setBrush(QBrush(color))
                    painter.drawRect(
                        int(point_x - point_width / 2),
                        int(y + height / 4),
                        point_width,
                        int(height / 2),
                    )

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        """
        Handle mouse press with enhanced feedback.

        Args:
            event: Mouse event
        """
        # Let the parent class handle the event
        super().mousePressEvent(event)

        # Add visual feedback
        self.animation_active = True
        self.animation_progress = 0.0
        self.animation_timer.start()

    def resizeEvent(self, event: QResizeEvent | None) -> None:
        """
        Handle resize events with smooth animation.

        Args:
            event: Resize event
        """
        # Let the parent class handle the event
        super().resizeEvent(event)

        # Add smooth resize animation
        self.animation_active = True
        self.animation_progress = 0.0
        self.animation_timer.start()
