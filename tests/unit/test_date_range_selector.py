"""
Unit tests for the unified date range selector component.
"""

from datetime import datetime, timedelta
from pathlib import Path
import sys

from PyQt6.QtCore import QDateTime
from PyQt6.QtWidgets import QApplication
import pytest

from goesvfi.integrity_check.date_range_selector import (
    CompactDateRangeSelector,
    UnifiedDateRangeSelector,
)

from tests.utils.pyqt_async_test import PyQtAsyncTestCase

# Add repository root to Python path
repo_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, repo_root)


class TestUnifiedDateRangeSelector(PyQtAsyncTestCase):
    """Tests for the UnifiedDateRangeSelector widget."""

    def setUp(self) -> None:
        """Set up the test case."""
        super().setUp()
        self.selector = UnifiedDateRangeSelector()

        # Track emitted signals
        self.emitted_ranges: list[tuple[datetime, datetime]] = []
        self.selector.dateRangeSelected.connect(self._store_date_range)

    def _store_date_range(self, start: datetime, end: datetime) -> None:
        """Store emitted date ranges for verification."""
        self.emitted_ranges.append((start, end))

    def test_initial_state(self) -> None:
        """Test the initial state of the selector."""
        # Get current date range
        start, end = self.selector.get_date_range()

        # Should be yesterday (full day) by default
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_end = yesterday.replace(hour=23, minute=59, second=59, microsecond=0)

        # Check dates (only compare date parts and hour/minute)
        assert start.date() == yesterday_start.date()
        assert start.hour == yesterday_start.hour
        assert start.minute == yesterday_start.minute

        assert end.date() == yesterday_end.date()
        assert end.hour == yesterday_end.hour
        assert end.minute == yesterday_end.minute

    def test_manual_date_change(self) -> None:
        """Test manual date change through date edit controls."""
        # Set a new start date
        now = datetime.now()
        new_start = now - timedelta(days=3)
        new_end = now

        # Convert to QDateTime
        q_start = QDateTime(
            new_start.year,
            new_start.month,
            new_start.day,
            new_start.hour,
            new_start.minute,
        )
        q_end = QDateTime(new_end.year, new_end.month, new_end.day, new_end.hour, new_end.minute)

        # Set dates
        self.selector.start_date_edit.setDateTime(q_start)

        # Process events to allow signal emission
        QApplication.processEvents()

        self.selector.end_date_edit.setDateTime(q_end)

        # Process events to allow signal emission
        QApplication.processEvents()

        # Verify internal state updated
        start, end = self.selector.get_date_range()
        assert start.date() == new_start.date()
        assert end.date() == new_end.date()

        # Verify signal was emitted
        assert len(self.emitted_ranges) == 2  # Two changes should emit two signals

    def test_preset_applications(self) -> None:
        """Test applying date presets."""
        # Apply "today" preset
        self.selector._apply_preset("today")

        # Verify "today" preset
        start, _end = self.selector.get_date_range()
        today = datetime.now()
        assert start.date() == today.date()
        assert start.hour == 0
        assert start.minute == 0

        # Apply "last_week" preset
        self.selector._apply_preset("last_week")

        # Verify "last_week" preset
        start, _end = self.selector.get_date_range()
        today = datetime.now()
        week_ago = today - timedelta(days=7)
        assert start.date() == week_ago.date()

        # Verify signal emission for both preset applications
        assert len(self.emitted_ranges) == 2

    def test_set_date_range(self) -> None:
        """Test the set_date_range method."""
        # Define custom date range
        start = datetime(2023, 5, 1, 10, 30)
        end = datetime(2023, 5, 15, 16, 45)

        # Set date range
        self.selector.set_date_range(start, end)

        # Verify date controls were updated
        start_dt = self.selector.start_date_edit.dateTime().toPyDateTime()
        start_dt = start_dt.replace(second=0, microsecond=0)
        assert start_dt == start
        end_dt = self.selector.end_date_edit.dateTime().toPyDateTime()
        end_dt = end_dt.replace(second=0, microsecond=0)
        assert end_dt == end

        # Verify internal state
        current_start, current_end = self.selector.get_date_range()
        assert current_start == start
        assert current_end == end

        # No signal should be emitted when using set_date_range
        assert len(self.emitted_ranges) == 0


class TestCompactDateRangeSelector(PyQtAsyncTestCase):
    """Tests for the CompactDateRangeSelector widget."""

    def setUp(self) -> None:
        """Set up the test case."""
        super().setUp()
        self.selector = CompactDateRangeSelector()

        # Track emitted signals
        self.emitted_ranges: list[tuple[datetime, datetime]] = []
        self.selector.dateRangeSelected.connect(self._store_date_range)

    def _store_date_range(self, start: datetime, end: datetime) -> None:
        """Store emitted date ranges for verification."""
        self.emitted_ranges.append((start, end))

    def test_initial_state(self) -> None:
        """Test the initial state of the selector."""
        # Default should be "Last 7 Days"
        assert self.selector.preset_combo.currentText() == "Last 7 Days"

        # Get current date range
        start, end = self.selector.get_date_range()

        # Should be last 7 days
        now = datetime.now()
        week_ago = now - timedelta(days=7)

        # Check dates (only compare date parts)
        assert start.date() == week_ago.date()
        assert end.date() == now.date()

    def test_preset_change(self) -> None:
        """Test changing presets via dropdown."""
        # Change to "Today"
        self.selector.preset_combo.setCurrentText("Today")

        # Process events to allow signal emission
        QApplication.processEvents()

        # Verify date range updated
        start, _end = self.selector.get_date_range()
        today = datetime.now()
        assert start.date() == today.date()
        assert start.hour == 0
        assert start.minute == 0

        # Change to "Yesterday"
        self.selector.preset_combo.setCurrentText("Yesterday")

        # Process events to allow signal emission
        QApplication.processEvents()

        # Verify date range updated
        start, _end = self.selector.get_date_range()
        yesterday = datetime.now() - timedelta(days=1)
        assert start.date() == yesterday.date()
        assert start.hour == 0
        assert start.minute == 0

        # Verify signals were emitted
        assert len(self.emitted_ranges) == 2

    def test_set_date_range(self) -> None:
        """Test the set_date_range method."""
        # Define custom date range
        start = datetime(2023, 5, 1, 10, 30)
        end = datetime(2023, 5, 15, 16, 45)

        # Set date range
        self.selector.set_date_range(start, end)

        # Verify internal state
        current_start, current_end = self.selector.get_date_range()
        assert current_start == start
        assert current_end == end

        # Verify preset combo set to "Custom..."
        assert self.selector.preset_combo.currentText() == "Custom..."

        # Verify date display updated
        display_text = self.selector.date_display.text()
        # Simply check that month and year are included, since the format might vary
        assert "May" in display_text, f"Month 'May' not found in: {display_text}"
        assert "2023" in display_text, f"Year '2023' not found in: {display_text}"
        # Check that both day numbers appear (either as '1' or '01' and '15')
        assert "1" in display_text or "01" in display_text, f"Day '1' or '01' not found in: {display_text}"
        assert "15" in display_text, f"Day '15' not found in: {display_text}"

        # No signal should be emitted when using set_date_range
        assert len(self.emitted_ranges) == 0


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
