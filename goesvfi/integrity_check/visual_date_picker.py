"""Visual date picker with quick presets for the GOES Integrity Check UI.

This module provides an enhanced date picker with visual calendar and quick presets
for common date ranges used in satellite data processing.
"""

from datetime import datetime, timedelta
from typing import Any, Callable, List, Optional

from PyQt6.QtCore import QDate, QPoint, Qt, QTime, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QCalendarWidget,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)


class VisualDateRangePicker(QDialog):
    """
    Enhanced date picker dialog with visual calendar and quick preset options.
    Provides a more intuitive interface for selecting date ranges common in
    satellite data processing workflows.
    """

    dateRangeSelected = pyqtSignal(datetime, datetime)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> None:
        """
        Initialize the visual date picker dialog.

        Args:
            parent: Parent widget
            start_date: Initial start date
            end_date: Initial end date
        """
        super().__init__(parent)

        # Apply material theme dialog class
        self.setProperty("class", "CropSelectionDialog")

        self.setWindowTitle(self.tr("Select Date Range"))
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        # Store the initial dates
        self.start_date = start_date or (datetime.now() - timedelta(days=1))
        self.end_date = end_date or datetime.now()

        # Set up the UI
        self._setup_ui()

        # Initialize with values
        self._initialize_with_dates(self.start_date, self.end_date)

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # Create quick presets section
        self._setup_quick_presets(main_layout)

        # Create custom selection section
        self._setup_custom_selection(main_layout)

        # Create preview section
        self._setup_preview_section(main_layout)

        # Create buttons section
        self._setup_buttons(main_layout)

    def _setup_quick_presets(self, parent_layout: QVBoxLayout) -> None:
        """Set up the quick presets section."""
        preset_group = QFrame()
        preset_group.setFrameShape(QFrame.Shape.StyledPanel)
        preset_group.setProperty("class", "DatePickerGroup")

        preset_layout = QVBoxLayout(preset_group)
        preset_layout.setContentsMargins(10, 10, 10, 10)

        # Title
        preset_title = QLabel(self.tr("Quick Select"))
        preset_title.setProperty("class", "DatePickerTitle")
        preset_layout.addWidget(preset_title)

        # Buttons grid
        buttons_layout = QGridLayout()
        buttons_layout.setSpacing(8)

        # Create preset buttons
        self.preset_buttons = [
            (self._create_preset_button("Today", self._set_today), 0, 0),
            (self._create_preset_button("Yesterday", self._set_yesterday), 0, 1),
            (self._create_preset_button("Last 7 Days", self._set_last_week), 0, 2),
            (self._create_preset_button("Last 30 Days", self._set_last_month), 0, 3),
            (self._create_preset_button("This Month", self._set_this_month), 1, 0),
            (
                self._create_preset_button("Last Month", self._set_last_calendar_month),
                1,
                1,
            ),
            (self._create_preset_button("This Year", self._set_this_year), 1, 2),
            (self._create_preset_button("Custom Range", self._set_custom), 1, 3),
        ]

        # Add buttons to layout
        for button, row, col in self.preset_buttons:
            buttons_layout.addWidget(button, row, col)

        preset_layout.addLayout(buttons_layout)
        parent_layout.addWidget(preset_group)

    def _create_preset_button(self, text: str, slot: Callable[[], None]) -> QPushButton:
        """Create a stylized preset button."""
        button = QPushButton(text)
        button.setMinimumHeight(40)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setProperty("class", "DatePickerButton")
        button.clicked.connect(slot)
        return button

    def _setup_custom_selection(self, parent_layout: QVBoxLayout) -> None:
        """Set up the custom date selection section."""
        # Create main custom selection container
        custom_container = QWidget()
        custom_layout = QHBoxLayout(custom_container)
        custom_layout.setContentsMargins(0, 0, 0, 0)

        # --- Start Date Section ---
        start_group = QFrame()
        start_group.setFrameShape(QFrame.Shape.StyledPanel)
        start_group.setProperty("class", "DatePickerGroup")
        start_layout = QVBoxLayout(start_group)

        # Start date label
        start_label = QLabel(self.tr("Start Date"))
        start_label.setProperty("class", "DatePickerTitle")
        start_layout.addWidget(start_label)

        # Start date calendar
        self.start_calendar = QCalendarWidget()
        self.start_calendar.setGridVisible(True)
        self.start_calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.start_calendar.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.SingleLetterDayNames)
        self.start_calendar.selectionChanged.connect(self._update_preview)

        # Use material theme styling
        self.start_calendar.setProperty("class", "DatePickerCalendar")
        start_layout.addWidget(self.start_calendar)

        # Start time
        start_time_layout = QHBoxLayout()
        time_label = QLabel(self.tr("Time:"))
        # Use default material theme styling
        start_time_layout.addWidget(time_label)
        self.start_time_edit = QTimeEdit()
        self.start_time_edit.setDisplayFormat("HH:mm")
        self.start_time_edit.timeChanged.connect(self._update_preview)
        # Use material theme styling
        self.start_time_edit.setProperty("class", "DatePickerTime")
        start_time_layout.addWidget(self.start_time_edit)
        start_layout.addLayout(start_time_layout)

        custom_layout.addWidget(start_group)

        # --- End Date Section ---
        end_group = QFrame()
        end_group.setFrameShape(QFrame.Shape.StyledPanel)
        end_group.setProperty("class", "DatePickerGroup")
        end_layout = QVBoxLayout(end_group)

        # End date label
        end_label = QLabel(self.tr("End Date"))
        end_label.setProperty("class", "DatePickerTitle")
        end_layout.addWidget(end_label)

        # End date calendar
        self.end_calendar = QCalendarWidget()
        self.end_calendar.setGridVisible(True)
        self.end_calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.end_calendar.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.SingleLetterDayNames)
        self.end_calendar.selectionChanged.connect(self._update_preview)

        # Use material theme styling
        self.end_calendar.setProperty("class", "DatePickerCalendar")
        end_layout.addWidget(self.end_calendar)

        # End time
        end_time_layout = QHBoxLayout()
        end_time_label = QLabel(self.tr("Time:"))
        # Use default material theme styling
        end_time_layout.addWidget(end_time_label)
        self.end_time_edit = QTimeEdit()
        self.end_time_edit.setDisplayFormat("HH:mm")
        self.end_time_edit.timeChanged.connect(self._update_preview)
        # Use material theme styling
        self.end_time_edit.setProperty("class", "DatePickerTime")
        end_time_layout.addWidget(self.end_time_edit)
        end_layout.addLayout(end_time_layout)

        custom_layout.addWidget(end_group)

        parent_layout.addWidget(custom_container)

    def _setup_preview_section(self, parent_layout: QVBoxLayout) -> None:
        """Set up the date range preview section."""
        preview_group = QFrame()
        preview_group.setFrameShape(QFrame.Shape.StyledPanel)
        preview_group.setProperty("class", "DatePickerPreview")

        preview_layout = QHBoxLayout(preview_group)
        preview_layout.setContentsMargins(15, 10, 15, 10)

        # Preview label
        preview_label = QLabel(self.tr("Selected Range:"))
        preview_label.setProperty("class", "DatePickerTitle")
        preview_layout.addWidget(preview_label)

        # Preview text
        self.preview_text = QLabel(self.tr(""))
        self.preview_text.setProperty("class", "DatePickerMonospace")
        preview_layout.addWidget(self.preview_text, 1)  # Give stretch priority

        # Time span
        self.timespan_label = QLabel(self.tr(""))
        # Use default material theme styling
        preview_layout.addWidget(self.timespan_label)

        parent_layout.addWidget(preview_group)

    def _setup_buttons(self, parent_layout: QVBoxLayout) -> None:
        """Set up the bottom buttons."""
        buttons_layout = QHBoxLayout()

        # Cancel button - dark mode styling
        self.cancel_button = QPushButton(self.tr("Cancel"))
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setProperty("class", "DatePickerButton")

        # Apply button
        self.apply_button = QPushButton(self.tr("Apply"))
        self.apply_button.setDefault(True)
        self.apply_button.clicked.connect(self._apply_selection)
        self.apply_button.setProperty("class", "DatePickerPrimary")

        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.apply_button)

        parent_layout.addLayout(buttons_layout)

    def _initialize_with_dates(self, start_date: datetime, end_date: datetime) -> None:
        """Initialize the UI with the specified dates."""
        # Set start date calendar
        self.start_calendar.setSelectedDate(QDate(start_date.year, start_date.month, start_date.day))
        self.start_time_edit.setTime(QTime(start_date.hour, start_date.minute))

        # Set end date calendar
        self.end_calendar.setSelectedDate(QDate(end_date.year, end_date.month, end_date.day))
        self.end_time_edit.setTime(QTime(end_date.hour, end_date.minute))

        # Update the preview
        self._update_preview()

    def _update_preview(self) -> None:
        pass
        """Update the date range preview text."""
        start_date = self._get_start_datetime()
        end_date = self._get_end_datetime()

        # Format dates for preview
        if start_date.date() == end_date.date():
            pass
            # Same day
            date_str = start_date.strftime("%Y-%m-%d")
            time_str = f"{start_date.strftime('%H:%M')} - {end_date.strftime('%H:%M')}"
            self.preview_text.setText(f"{date_str} ({time_str})")
        else:
            # Different days
            start_str = start_date.strftime("%Y-%m-%d %H:%M")
            end_str = end_date.strftime("%Y-%m-%d %H:%M")
            self.preview_text.setText(f"{start_str} → {end_str}")

        # Calculate and show time span
        duration = end_date - start_date
        days = duration.days
        hours, remainder = divmod(duration.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        timespan_text = ""
        if days > 0:
            pass
            timespan_text += f"{days} day{'s' if days != 1 else ''} "
        if hours > 0:
            pass
            timespan_text += f"{hours} hour{'s' if hours != 1 else ''} "
        if minutes > 0 and days == 0:  # Only show minutes if less than a day
            timespan_text += f"{minutes} minute{'s' if minutes != 1 else ''}"

        self.timespan_label.setText(f"({timespan_text.strip()})")

    def _get_start_datetime(self) -> datetime:
        pass
        """Get the selected start datetime."""
        selected_date = self.start_calendar.selectedDate()
        selected_time = self.start_time_edit.time()

        return datetime(
            selected_date.year(),
            selected_date.month(),
            selected_date.day(),
            selected_time.hour(),
            selected_time.minute(),
            0,  # seconds
        )

    def _get_end_datetime(self) -> datetime:
        """Get the selected end datetime."""
        selected_date = self.end_calendar.selectedDate()
        selected_time = self.end_time_edit.time()

        return datetime(
            selected_date.year(),
            selected_date.month(),
            selected_date.day(),
            selected_time.hour(),
            selected_time.minute(),
            59,  # seconds (end of the minute)
        )

    def _apply_selection(self) -> None:
        """Apply the selected date range and emit signal."""
        start_date = self._get_start_datetime()
        end_date = self._get_end_datetime()

        # Ensure start date is before end date
        if start_date > end_date:
            pass
            start_date, end_date = end_date, start_date

        # Update stored dates
        self.start_date = start_date
        self.end_date = end_date

        # Emit signal with the selected range
        self.dateRangeSelected.emit(start_date, end_date)

        # Accept dialog
        self.accept()

    # --- Preset handlers ---

    def _set_today(self) -> None:
        """Set the date range to today."""
        today = datetime.now()
        today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today.replace(hour=23, minute=59, second=59, microsecond=0)

        self._initialize_with_dates(today_start, today_end)

    def _set_yesterday(self) -> None:
        """Set the date range to yesterday."""
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_end = yesterday.replace(hour=23, minute=59, second=59, microsecond=0)

        self._initialize_with_dates(yesterday_start, yesterday_end)

    def _set_last_week(self) -> None:
        """Set the date range to the last 7 days."""
        today = datetime.now()
        last_week = today - timedelta(days=7)

        last_week_start = last_week.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today.replace(hour=23, minute=59, second=59, microsecond=0)

        self._initialize_with_dates(last_week_start, today_end)

    def _set_last_month(self) -> None:
        """Set the date range to the last 30 days."""
        today = datetime.now()
        last_month = today - timedelta(days=30)

        last_month_start = last_month.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today.replace(hour=23, minute=59, second=59, microsecond=0)

        self._initialize_with_dates(last_month_start, today_end)

    def _set_this_month(self) -> None:
        """Set the date range to the current calendar month."""
        today = datetime.now()

        month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Calculate the end of month
        if today.month == 12:
            pass
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)

        month_end = (next_month - timedelta(days=1)).replace(hour=23, minute=59, second=59)

        self._initialize_with_dates(month_start, month_end)

    def _set_last_calendar_month(self) -> None:
        """Set the date range to the previous calendar month."""
        today = datetime.now()

        # Get the first day of the current month
        first_of_month = today.replace(day=1)

        # Get the last day of the previous month
        last_of_prev_month = first_of_month - timedelta(days=1)

        # Get the first day of the previous month
        first_of_prev_month = last_of_prev_month.replace(day=1, hour=0, minute=0, second=0)

        # End of the previous month
        end_of_prev_month = last_of_prev_month.replace(hour=23, minute=59, second=59)

        self._initialize_with_dates(first_of_prev_month, end_of_prev_month)

    def _set_this_year(self) -> None:
        """Set the date range to the current calendar year."""
        today = datetime.now()

        year_start = today.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        year_end = today.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=0)

        self._initialize_with_dates(year_start, year_end)

    def _set_custom(self) -> None:
        """Reset to the original dates."""
        self._initialize_with_dates(self.start_date, self.end_date)


class TimelinePickerWidget(QWidget):
    """A widget showing a timeline with data availability indicator."""

    dateRangeSelected = pyqtSignal(datetime, datetime)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the timeline picker widget."""
        super().__init__(parent)

        self.setMinimumWidth(400)
        self.setMinimumHeight(80)

        # Initialize data
        self.start_date = datetime.now() - timedelta(days=7)
        self.end_date = datetime.now()

        # For drawing selection
        self.selection_start: Optional[datetime] = None
        self.selection_end: Optional[datetime] = None
        self.is_selecting = False

        # Mock data availability (in a real app, this would come from the model)
        self.data_points = self._generate_mock_data()  # pylint: disable=attribute-defined-outside-init

    def _generate_mock_data(self) -> List[Any]:
        """Generate mock data points for demonstration."""
        data_points = []
        current = self.start_date
        while current <= self.end_date:
            # Add data point with 80% probability
            if datetime.now().microsecond % (100 // 80) == 0:
                pass
                data_points.append(current)
            current += timedelta(hours=1)
        return data_points

    def _update_calendar_style(self) -> None:
        """Override paint event to draw the timeline."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # Draw background - dark mode colors
        painter.fillRect(0, 0, width, height, QColor(45, 45, 45))

        # Define timeline area
        timeline_height = 20
        timeline_y = height // 2 - timeline_height // 2

        # Draw timeline - dark mode colors
        painter.fillRect(10, timeline_y, width - 20, timeline_height, QColor(70, 70, 70))

        # Draw data points
        if self.data_points:
            pass
            total_duration = (self.end_date - self.start_date).total_seconds()
            for point in self.data_points:
                point_offset = (point - self.start_date).total_seconds() / total_duration
                point_x = 10 + point_offset * (width - 20)
                # Convert coordinates to integers for fillRect
                painter.fillRect(
                    int(point_x - 1),
                    timeline_y - 2,
                    2,
                    timeline_height + 4,
                    QColor(40, 167, 69),
                )

        # Draw selection if active
        if self.selection_start is not None and self.selection_end is not None:
            pass
            start_offset = (self.selection_start - self.start_date).total_seconds() / total_duration
            end_offset = (self.selection_end - self.start_date).total_seconds() / total_duration

            start_x = 10 + start_offset * (width - 20)
            end_x = 10 + end_offset * (width - 20)

            # Draw selection rectangle - brighter blue for better visibility in dark mode
            selection_rect = QColor(42, 130, 218, 180)  # Semi-transparent blue
            # Convert coordinates to integers for fillRect
            painter.fillRect(
                int(start_x),
                timeline_y - 5,
                int(end_x - start_x),
                timeline_height + 10,
                selection_rect,
            )

            # Draw start and end markers - brighter for dark mode
            painter.setPen(QPen(QColor(80, 170, 255), 2))
            # Convert coordinates to integers for drawLine
            painter.drawLine(
                int(start_x),
                timeline_y - 5,
                int(start_x),
                timeline_y + timeline_height + 5,
            )
            painter.drawLine(int(end_x), timeline_y - 5, int(end_x), timeline_y + timeline_height + 5)

    def _on_preset_clicked(self, days: int) -> None:
        """Handle mouse press events for selection."""
        self.is_selecting = True
        date = self._pixel_to_date(QPoint(0, 0).x())
        # Initialize both with the same date to avoid None issues
        if date is not None:
            pass
            self.selection_start = date
            self.selection_end = date
        self.update()

    def _on_today_clicked(self) -> None:
        """Handle mouse move events for selection."""
        if self.is_selecting and self.selection_start is not None:
            pass
            date = self._pixel_to_date(QPoint(0, 0).x())
            if date is not None:
                pass
                self.selection_end = date
            self.update()

    def _on_custom_clicked(self) -> None:
        """Handle mouse release events to finalize selection."""
        if self.is_selecting and self.selection_start is not None:
            pass
            self.is_selecting = False
            date = self._pixel_to_date(QPoint(0, 0).x())
            if date is not None:
                pass
                self.selection_end = date

            # Ensure start is before end (only if both are valid)
            if self.selection_start is not None and self.selection_end is not None:
                pass
                if self.selection_start > self.selection_end:
                    pass
                    self.selection_start, self.selection_end = (
                        self.selection_end,
                        self.selection_start,
                    )

            # Emit signal with selection
            self.dateRangeSelected.emit(self.selection_start, self.selection_end)

            self.update()

    def _pixel_to_date(self, x_position: int) -> datetime:
        """Convert a pixel position to a date."""
        width = self.width()
        if x_position <= 10:
            pass
            return self.start_date
        if x_position >= width - 10:
            pass
            return self.end_date

        # Calculate position as a fraction of the timeline
        position_ratio = (x_position - 10) / (width - 20)

        # Calculate the corresponding date
        total_duration = (self.end_date - self.start_date).total_seconds()
        seconds_offset = total_duration * position_ratio

        return self.start_date + timedelta(seconds=seconds_offset)

    def set_date_range(self, start_date: datetime, end_date: datetime) -> None:
        """Set the date range for the timeline."""
        self.start_date = start_date
        self.end_date = end_date

        # Reset selection
        self.selection_start = None
        self.selection_end = None

        # Regenerate mock data
        self.data_points = self._generate_mock_data()  # pylint: disable=attribute-defined-outside-init

        self.update()
