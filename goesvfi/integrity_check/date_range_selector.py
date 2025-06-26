"""
Unified date range selector component for the GOES Integrity Check UI.

This module provides a standardized date range selector component that can be
used across all tabs in the integrity check system, ensuring consistent UI
and behavior for date selection.
"""

from datetime import datetime, timedelta
from typing import Callable, Optional, Tuple

from PyQt6.QtCore import QDate, QDateTime, Qt, QTime, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from goesvfi.integrity_check.visual_date_picker import VisualDateRangePicker


# pylint: disable=too-few-public-methods
class DateRangePreset:
    """Represents a date range preset."""

    def __init__(
        self,
        name: str,
        description: str,
        start_date_func: Callable[[], datetime],
        end_date_func: Callable[[], datetime],
    ) -> None:
        """
        Initialize a date range preset.

        Args:
            name: The preset name (e.g., "Today", "Last Week")
            description: A short description of the preset
            start_date_func: Function that returns the start date
            end_date_func: Function that returns the end date
        """
        self.name = name
        self.description = description
        self._start_date_func = start_date_func  # pylint: disable=attribute-defined-outside-init
        self._end_date_func = end_date_func  # pylint: disable=attribute-defined-outside-init

    def get_date_range(self) -> Tuple[datetime, datetime]:
        """Get the date range for this preset."""
        return self._start_date_func(), self._end_date_func()


class UnifiedDateRangeSelector(QWidget):
    """
    A standardized date range selector component for use across all tabs.

    This component provides a consistent interface for selecting date ranges
    with support for presets, manual date entry, and visual date picking.
    """

    # Signal when date range changes
    dateRangeSelected = pyqtSignal(datetime, datetime)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        include_visual_picker: bool = True,
        include_presets: bool = True,
        layout_direction: Qt.Orientation = Qt.Orientation.Horizontal,
    ) -> None:
        """
        Initialize the date range selector.

        Args:
            parent: The parent widget
            include_visual_picker: Whether to include the visual date picker button
            include_presets: Whether to include preset buttons
            layout_direction: The layout direction (horizontal or vertical)
        """
        super().__init__(parent)

        # Store settings
        self._include_visual_picker = include_visual_picker  # pylint: disable=attribute-defined-outside-init
        self._include_presets = include_presets  # pylint: disable=attribute-defined-outside-init
        self._layout_direction = layout_direction  # pylint: disable=attribute-defined-outside-init

        # Initialize date range with defaults
        yesterday = datetime.now() - timedelta(days=1)
        self._start_date = yesterday.replace(
            hour=0, minute=0, second=0, microsecond=0
        )  # pylint: disable=attribute-defined-outside-init
        self._end_date = yesterday.replace(
            hour=23, minute=59, second=59, microsecond=0
        )  # pylint: disable=attribute-defined-outside-init

        # Create UI components
        self._setup_ui()

        # Initialize with current date range
        self._update_date_controls()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        # Create main layout based on orientation
        if self._layout_direction == Qt.Orientation.Horizontal:
            main_layout = QHBoxLayout(self)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(10)
        else:
            # Need to cast to avoid type error since we're assigning to same variable
            main_layout = QVBoxLayout(self)  # type: ignore[assignment]
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(10)

        # Date range group
        date_group = QGroupBox(self.tr("Date Range"))
        date_layout = QFormLayout()

        # Start date
        self.start_date_edit = QDateTimeEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.start_date_edit.dateTimeChanged.connect(self._handle_manual_date_change)
        date_layout.addRow(self.tr("From:"), self.start_date_edit)

        # End date
        self.end_date_edit = QDateTimeEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.end_date_edit.dateTimeChanged.connect(self._handle_manual_date_change)
        date_layout.addRow(self.tr("To:"), self.end_date_edit)

        # Visual date picker button
        if self._include_visual_picker:
            visual_picker_btn = QPushButton(self.tr("Visual Picker"))
            visual_picker_btn.setToolTip(self.tr("Open visual date picker"))
            visual_picker_btn.clicked.connect(self._open_visual_date_picker)
            date_layout.addRow("", visual_picker_btn)

        date_group.setLayout(date_layout)
        main_layout.addWidget(date_group)

        # Presets group if enabled
        if self._include_presets:
            presets_group = QGroupBox(self.tr("Quick Select"))
            presets_layout = QVBoxLayout()

            # Create preset buttons layout (always horizontal)
            buttons_layout = QHBoxLayout()
            buttons_layout.setSpacing(5)

            # Add preset buttons
            today_btn = QPushButton(self.tr("Today"))
            today_btn.clicked.connect(lambda: self._apply_preset("today"))
            buttons_layout.addWidget(today_btn)

            yesterday_btn = QPushButton(self.tr("Yesterday"))
            yesterday_btn.clicked.connect(lambda: self._apply_preset("yesterday"))
            buttons_layout.addWidget(yesterday_btn)

            last_week_btn = QPushButton(self.tr("Last 7 Days"))
            last_week_btn.clicked.connect(lambda: self._apply_preset("last_week"))
            buttons_layout.addWidget(last_week_btn)

            last_month_btn = QPushButton(self.tr("Last 30 Days"))
            last_month_btn.clicked.connect(lambda: self._apply_preset("last_month"))
            buttons_layout.addWidget(last_month_btn)

            presets_layout.addLayout(buttons_layout)

            # Add a second row of buttons for other common presets
            more_buttons_layout = QHBoxLayout()
            more_buttons_layout.setSpacing(5)

            this_month_btn = QPushButton(self.tr("This Month"))
            this_month_btn.clicked.connect(lambda: self._apply_preset("this_month"))
            more_buttons_layout.addWidget(this_month_btn)

            last_cal_month_btn = QPushButton(self.tr("Last Month"))
            last_cal_month_btn.clicked.connect(lambda: self._apply_preset("last_cal_month"))
            more_buttons_layout.addWidget(last_cal_month_btn)

            this_year_btn = QPushButton(self.tr("This Year"))
            this_year_btn.clicked.connect(lambda: self._apply_preset("this_year"))
            more_buttons_layout.addWidget(this_year_btn)

            custom_btn = QPushButton(self.tr("Custom"))
            custom_btn.clicked.connect(self._open_visual_date_picker)
            more_buttons_layout.addWidget(custom_btn)

            presets_layout.addLayout(more_buttons_layout)

            presets_group.setLayout(presets_layout)
            main_layout.addWidget(presets_group)

    def _update_date_controls(self) -> None:
        """Update the date controls with the current date range."""
        # Block signals to prevent recursion
        self.start_date_edit.blockSignals(True)
        self.end_date_edit.blockSignals(True)

        # Update start date
        self.start_date_edit.setDateTime(
            QDateTime(
                QDate(self._start_date.year, self._start_date.month, self._start_date.day),
                QTime(self._start_date.hour, self._start_date.minute),
            )
        )

        # Update end date
        self.end_date_edit.setDateTime(
            QDateTime(
                QDate(self._end_date.year, self._end_date.month, self._end_date.day),
                QTime(self._end_date.hour, self._end_date.minute),
            )
        )

        # Unblock signals
        self.start_date_edit.blockSignals(False)
        self.end_date_edit.blockSignals(False)

    def _handle_manual_date_change(self) -> None:
        """Handle date change from manual date edit controls."""
        # Get date from controls
        start_dt = self.start_date_edit.dateTime().toPyDateTime()
        end_dt = self.end_date_edit.dateTime().toPyDateTime()

        # Ensure start date is before end date
        if start_dt > end_dt:
            # If start is after end, adjust the one that didn't trigger this change
            if self.sender() == self.start_date_edit:
                self.end_date_edit.setDateTime(
                    QDateTime(
                        QDate(start_dt.year, start_dt.month, start_dt.day),
                        QTime(start_dt.hour, start_dt.minute),
                    )
                )
                end_dt = start_dt
            else:
                self.start_date_edit.setDateTime(
                    QDateTime(
                        QDate(end_dt.year, end_dt.month, end_dt.day),
                        QTime(end_dt.hour, end_dt.minute),
                    )
                )
                start_dt = end_dt

        # Update internal state
        self._start_date = start_dt  # pylint: disable=attribute-defined-outside-init
        self._end_date = end_dt  # pylint: disable=attribute-defined-outside-init

        # Emit signal
        self.dateRangeSelected.emit(self._start_date, self._end_date)

    def _open_visual_date_picker(self) -> None:
        """Open the visual date picker dialog."""
        dialog = VisualDateRangePicker(self, self._start_date, self._end_date)
        dialog.dateRangeSelected.connect(self._handle_visual_date_selection)
        dialog.exec()

    def _handle_visual_date_selection(self, start: datetime, end: datetime) -> None:
        """
        Handle date selection from visual date picker.

        Args:
            start: Start date
            end: End date
        """
        # Update internal state
        self._start_date = start  # pylint: disable=attribute-defined-outside-init
        self._end_date = end  # pylint: disable=attribute-defined-outside-init

        # Update controls
        self._update_date_controls()

        # Emit signal
        self.dateRangeSelected.emit(start, end)

    def _apply_preset(self, preset_name: str) -> None:
        """
        Apply a preset date range.

        Args:
            preset_name: Name of the preset to apply
        """
        # Get current date and time for reference
        now = datetime.now()

        if preset_name == "today":
            # Today (midnight to current time)
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now

        elif preset_name == "yesterday":
            # Yesterday (full day)
            yesterday = now - timedelta(days=1)
            start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end = yesterday.replace(hour=23, minute=59, second=59, microsecond=0)

        elif preset_name == "last_week":
            # Last 7 days
            start = now - timedelta(days=7)
            end = now

        elif preset_name == "last_month":
            # Last 30 days
            start = now - timedelta(days=30)
            end = now

        elif preset_name == "this_month":
            # Current calendar month
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # Calculate the end of month
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=1)
            else:
                next_month = now.replace(month=now.month + 1, day=1)

            end = (next_month - timedelta(days=1)).replace(hour=23, minute=59, second=59)

        elif preset_name == "last_cal_month":
            # Previous calendar month
            # Get the first day of the current month
            first_of_month = now.replace(day=1)

            # Get the last day of the previous month
            last_of_prev_month = first_of_month - timedelta(days=1)

            # Get the first day of the previous month
            start = last_of_prev_month.replace(day=1, hour=0, minute=0, second=0)

            # End of the previous month
            end = last_of_prev_month.replace(hour=23, minute=59, second=59)

        elif preset_name == "this_year":
            # Current year
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=0)

        else:
            # Unknown preset, use last 24 hours as fallback
            start = now - timedelta(days=1)
            end = now

        # Update internal state
        self._start_date = start  # pylint: disable=attribute-defined-outside-init
        self._end_date = end  # pylint: disable=attribute-defined-outside-init

        # Update controls
        self._update_date_controls()

        # Emit signal
        self.dateRangeSelected.emit(start, end)

    def get_date_range(self) -> Tuple[datetime, datetime]:
        """Get the current date range."""
        return self._start_date, self._end_date

    def set_date_range(self, start: datetime, end: datetime) -> None:
        """
        Set the date range.

        Args:
            start: Start date
            end: End date
        """
        # Update internal state
        self._start_date = start  # pylint: disable=attribute-defined-outside-init
        self._end_date = end  # pylint: disable=attribute-defined-outside-init

        # Update controls
        self._update_date_controls()


class CompactDateRangeSelector(QWidget):
    """
    A compact date range selector for use in space-constrained UIs.

    This component provides a simplified version of the date selector with
    a dropdown for common presets and a compact date display.
    """

    # Signal when date range changes
    dateRangeSelected = pyqtSignal(datetime, datetime)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the compact date range selector."""
        super().__init__(parent)

        # Initialize date range with defaults (last 7 days)
        now = datetime.now()
        self._start_date = now - timedelta(days=7)
        self._end_date = now

        # Create UI components
        self._setup_ui()

        # Initialize display
        self._update_display()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)

        # Label
        main_layout.addWidget(QLabel(self.tr("Date Range:")))

        # Preset dropdown
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(
            [
                self.tr("Last 7 Days"),
                self.tr("Last 24 Hours"),
                self.tr("Today"),
                self.tr("Yesterday"),
                self.tr("Last 30 Days"),
                self.tr("This Month"),
                self.tr("Last Month"),
                self.tr("This Year"),
                self.tr("Custom..."),
            ]
        )
        self.preset_combo.currentTextChanged.connect(self._handle_preset_change)
        main_layout.addWidget(self.preset_combo)

        # Date display
        self.date_display = QLabel()
        self.date_display.setProperty("class", "DateRangeDisplay")
        main_layout.addWidget(self.date_display)

        # Edit button (opens visual date picker)
        self.edit_button = QPushButton(self.tr("Edit"))
        self.edit_button.setMaximumWidth(50)
        self.edit_button.clicked.connect(self._open_visual_date_picker)
        main_layout.addWidget(self.edit_button)

    def _update_display(self) -> None:
        """Update the date display."""
        # Format for display
        if self._start_date.date() == self._end_date.date():
            # Same day
            display_text = f"{self._start_date.strftime('%Y-%m-%d')}"
        else:
            # Different days
            if self._start_date.year == self._end_date.year:
                # Same year
                if self._start_date.month == self._end_date.month:
                    # Same month
                    display_text = f"{self._start_date.strftime('%b %d')} - " f"{self._end_date.strftime('%d, %Y')}"
                else:
                    # Different months
                    display_text = f"{self._start_date.strftime('%b %d')} - " f"{self._end_date.strftime('%b %d, %Y')}"
            else:
                # Different years
                display_text = f"{self._start_date.strftime('%Y-%m-%d')} - " f"{self._end_date.strftime('%Y-%m-%d')}"

        self.date_display.setText(display_text)

    def _handle_preset_change(self, preset_text: str) -> None:
        """
        Handle preset change from the dropdown.

        Args:
            preset_text: The selected preset text
        """
        # Current date/time for reference
        now = datetime.now()

        if preset_text == "Last 7 Days":
            start = now - timedelta(days=7)
            end = now

        elif preset_text == "Last 24 Hours":
            start = now - timedelta(days=1)
            end = now

        elif preset_text == "Today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now

        elif preset_text == "Yesterday":
            yesterday = now - timedelta(days=1)
            start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end = yesterday.replace(hour=23, minute=59, second=59, microsecond=0)

        elif preset_text == "Last 30 Days":
            start = now - timedelta(days=30)
            end = now

        elif preset_text == "This Month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=1)
            else:
                next_month = now.replace(month=now.month + 1, day=1)
            end = (next_month - timedelta(days=1)).replace(hour=23, minute=59, second=59)

        elif preset_text == "Last Month":
            first_of_month = now.replace(day=1)
            last_of_prev_month = first_of_month - timedelta(days=1)
            start = last_of_prev_month.replace(day=1, hour=0, minute=0, second=0)
            end = last_of_prev_month.replace(hour=23, minute=59, second=59)

        elif preset_text == "This Year":
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=0)

        elif preset_text == "Custom...":
            # Open visual date picker without changing dates
            self._open_visual_date_picker()
            return

        # Update internal state
        self._start_date = start  # pylint: disable=attribute-defined-outside-init
        self._end_date = end  # pylint: disable=attribute-defined-outside-init

        # Update display
        self._update_display()

        # Emit signal
        self.dateRangeSelected.emit(start, end)

    def _open_visual_date_picker(self) -> None:
        """Open the visual date picker dialog."""
        dialog = VisualDateRangePicker(self, self._start_date, self._end_date)
        dialog.dateRangeSelected.connect(self._handle_visual_date_selection)
        if dialog.exec():
            # If dialog was accepted, set preset combo to "Custom"
            self.preset_combo.blockSignals(True)
            self.preset_combo.setCurrentText("Custom...")
            self.preset_combo.blockSignals(False)

    def _handle_visual_date_selection(self, start: datetime, end: datetime) -> None:
        """
        Handle date selection from visual date picker.

        Args:
            start: Start date
            end: End date
        """
        # Update internal state
        self._start_date = start  # pylint: disable=attribute-defined-outside-init
        self._end_date = end  # pylint: disable=attribute-defined-outside-init

        # Update display
        self._update_display()

        # Emit signal
        self.dateRangeSelected.emit(start, end)

    def get_date_range(self) -> Tuple[datetime, datetime]:
        """Get the current date range."""
        return self._start_date, self._end_date

    def set_date_range(self, start: datetime, end: datetime) -> None:
        """
        Set the date range.

        Args:
            start: Start date
            end: End date
        """
        # Update internal state
        self._start_date = start  # pylint: disable=attribute-defined-outside-init
        self._end_date = end  # pylint: disable=attribute-defined-outside-init

        # Update display
        self._update_display()

        # Reset preset combo to "Custom"
        self.preset_combo.blockSignals(True)
        self.preset_combo.setCurrentText("Custom...")
        self.preset_combo.blockSignals(False)


# Alias for compatibility with existing code
DateRangeSelector = UnifiedDateRangeSelector
