"""
Unit tests for the unified date range selector component - Optimized Version 2.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
from unittest.mock import patch

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


class TestUnifiedDateRangeSelectorV2(PyQtAsyncTestCase):
    """Tests for the UnifiedDateRangeSelector widget - Enhanced with shared fixtures and optimization."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up class-level fixtures shared across all test methods."""
        # Pre-computed test dates for efficiency
        cls.reference_date = datetime.now(UTC)
        cls.test_dates = {
            "yesterday": cls.reference_date - timedelta(days=1),
            "three_days_ago": cls.reference_date - timedelta(days=3),
            "week_ago": cls.reference_date - timedelta(days=7),
            "custom_start": datetime(2023, 5, 1, 10, 30, tzinfo=UTC),
            "custom_end": datetime(2023, 5, 15, 16, 45, tzinfo=UTC),
        }

        # Pre-computed expected ranges for validation
        cls.expected_ranges = {
            "yesterday_start": cls.test_dates["yesterday"].replace(hour=0, minute=0, second=0, microsecond=0),
            "yesterday_end": cls.test_dates["yesterday"].replace(hour=23, minute=59, second=59, microsecond=0),
            "today_start": cls.reference_date.replace(hour=0, minute=0, second=0, microsecond=0),
            "week_ago_start": cls.test_dates["week_ago"].replace(hour=0, minute=0, second=0, microsecond=0),
        }

    def setUp(self) -> None:
        """Set up the test case with shared signal tracking."""
        super().setUp()
        self.selector = UnifiedDateRangeSelector()

        # Shared signal tracking setup - used across multiple test methods
        self.emitted_ranges: list[tuple[datetime, datetime]] = []
        self.selector.dateRangeSelected.connect(self._store_date_range)

    def _store_date_range(self, start: datetime, end: datetime) -> None:
        """Store emitted date ranges for verification."""
        self.emitted_ranges.append((start, end))

    def test_initial_state(self) -> None:
        """Test the initial state of the selector using pre-computed values."""
        # Get current date range
        start, end = self.selector.get_date_range()

        # Use pre-computed expected values for efficiency
        expected_start = self.expected_ranges["yesterday_start"]
        expected_end = self.expected_ranges["yesterday_end"]

        # Check dates (only compare date parts and hour/minute)
        assert start.date() == expected_start.date()
        assert start.hour == expected_start.hour
        assert start.minute == expected_start.minute

        assert end.date() == expected_end.date()
        assert end.hour == expected_end.hour
        assert end.minute == expected_end.minute

    def _convert_datetime_to_qdatetime(self, dt: datetime) -> QDateTime:  # noqa: PLR6301
        """Helper method to convert datetime to QDateTime - reduces code duplication.

        Returns:
            QDateTime: The converted QDateTime object.
        """
        return QDateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute)

    def _process_events_and_verify_dates(self, expected_start: datetime, expected_end: datetime) -> None:
        """Helper method to process events and verify date ranges - reduces duplication."""
        QApplication.processEvents()

        # Verify internal state updated
        start, end = self.selector.get_date_range()
        assert start.date() == expected_start.date()
        assert end.date() == expected_end.date()

    def test_manual_date_change(self) -> None:
        """Test manual date change through date edit controls using optimized helpers."""
        # Use pre-computed test dates
        new_start = self.test_dates["three_days_ago"]
        new_end = self.reference_date

        # Convert to QDateTime using helper
        q_start = self._convert_datetime_to_qdatetime(new_start)
        q_end = self._convert_datetime_to_qdatetime(new_end)

        # Set dates and verify using helper
        self.selector.start_date_edit.setDateTime(q_start)
        QApplication.processEvents()

        self.selector.end_date_edit.setDateTime(q_end)
        self._process_events_and_verify_dates(new_start, new_end)

        # Verify signal was emitted
        assert len(self.emitted_ranges) == 2  # Two changes should emit two signals

    def test_preset_applications_parametrized(self) -> None:
        """Test applying different date presets using parametrization."""
        test_cases = [
            ("today", "today_start"),
            ("last_week", "week_ago_start"),
        ]

        for preset, expected_start_key in test_cases:
            with self.subTest(preset=preset, expected_start_key=expected_start_key):
                initial_signal_count = len(self.emitted_ranges)

                # Apply preset
                self.selector._apply_preset(preset)  # noqa: SLF001

                # Verify preset was applied
                start, _end = self.selector.get_date_range()

                if preset == "today":
                    expected_start = self.expected_ranges["today_start"]
                    assert start.date() == expected_start.date()
                    assert start.hour == 0
                    assert start.minute == 0
                elif preset == "last_week":
                    expected_start = self.expected_ranges["week_ago_start"]
                    assert start.date() == expected_start.date()

                # Verify signal emission
                assert len(self.emitted_ranges) == initial_signal_count + 1

    def test_set_date_range_comprehensive(self) -> None:
        """Test the set_date_range method with comprehensive validation."""
        # Use pre-computed custom date range
        start = self.test_dates["custom_start"]
        end = self.test_dates["custom_end"]

        # Set date range
        self.selector.set_date_range(start, end)

        # Verify date controls were updated using helper validation
        start_dt = self.selector.start_date_edit.dateTime().toPyDateTime()
        start_dt = start_dt.replace(second=0, microsecond=0)
        # If start has timezone info but start_dt doesn't, convert for comparison
        if start.tzinfo is not None and start_dt.tzinfo is None:
            start_naive = start.replace(tzinfo=None)
            assert start_dt == start_naive
        else:
            assert start_dt == start

        end_dt = self.selector.end_date_edit.dateTime().toPyDateTime()
        end_dt = end_dt.replace(second=0, microsecond=0)
        # If end has timezone info but end_dt doesn't, convert for comparison
        if end.tzinfo is not None and end_dt.tzinfo is None:
            end_naive = end.replace(tzinfo=None)
            assert end_dt == end_naive
        else:
            assert end_dt == end

        # Verify internal state
        current_start, current_end = self.selector.get_date_range()
        assert current_start == start
        assert current_end == end

        # No signal should be emitted when using set_date_range
        assert len(self.emitted_ranges) == 0

    def test_multiple_preset_changes(self) -> None:
        """Test rapid preset changes to verify signal handling."""
        presets_to_test = ["today", "yesterday", "last_week"]
        initial_count = len(self.emitted_ranges)

        for i, preset in enumerate(presets_to_test):
            self.selector._apply_preset(preset)  # noqa: SLF001
            # Each preset change should emit exactly one signal
            expected_count = initial_count + i + 1
            assert len(self.emitted_ranges) == expected_count

    def test_date_range_validation(self) -> None:
        """Test date range validation and boundary conditions."""
        # Test with start date after end date (edge case)
        future_start = self.reference_date + timedelta(days=1)
        past_end = self.reference_date - timedelta(days=1)

        # This should be handled gracefully by the widget
        self.selector.set_date_range(future_start, past_end)

        # Widget should maintain the set values even if logically inconsistent
        current_start, current_end = self.selector.get_date_range()
        assert current_start == future_start
        assert current_end == past_end


class TestCompactDateRangeSelectorV2(PyQtAsyncTestCase):
    """Tests for the CompactDateRangeSelector widget - Enhanced with optimization."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up class-level fixtures shared across all test methods."""
        # Pre-computed dates for efficiency
        cls.reference_date = datetime.now(UTC)
        cls.test_dates = {
            "week_ago": cls.reference_date - timedelta(days=7),
            "yesterday": cls.reference_date - timedelta(days=1),
            "custom_start": datetime(2023, 5, 1, 10, 30, tzinfo=UTC),
            "custom_end": datetime(2023, 5, 15, 16, 45, tzinfo=UTC),
        }

    def setUp(self) -> None:
        """Set up the test case with shared signal tracking."""
        super().setUp()
        self.selector = CompactDateRangeSelector()

        # Shared signal tracking setup
        self.emitted_ranges: list[tuple[datetime, datetime]] = []
        self.selector.dateRangeSelected.connect(self._store_date_range)

    def _store_date_range(self, start: datetime, end: datetime) -> None:
        """Store emitted date ranges for verification."""
        self.emitted_ranges.append((start, end))

    def test_initial_state_optimized(self) -> None:
        """Test the initial state using pre-computed values."""
        # Default should be "Last 7 Days"
        assert self.selector.preset_combo.currentText() == "Last 7 Days"

        # Get current date range
        start, end = self.selector.get_date_range()

        # Use pre-computed values for verification
        expected_start = self.test_dates["week_ago"]
        expected_end = self.reference_date

        # Check dates (only compare date parts)
        assert start.date() == expected_start.date()
        assert end.date() == expected_end.date()

    def test_preset_change_parametrized(self) -> None:
        """Test changing presets via dropdown using parametrization."""
        test_cases = [
            ("Today", 0),
            ("Yesterday", 0),
        ]

        for preset_text, expected_hour in test_cases:
            with self.subTest(preset_text=preset_text, expected_hour=expected_hour):
                initial_count = len(self.emitted_ranges)

                # Change to specified preset
                self.selector.preset_combo.setCurrentText(preset_text)
                QApplication.processEvents()

                # Verify date range updated
                start, _ = self.selector.get_date_range()
                assert start.hour == expected_hour
                assert start.minute == 0

                # Verify signal was emitted
                assert len(self.emitted_ranges) == initial_count + 1

    def test_custom_date_range_display(self) -> None:
        """Test custom date range display formatting."""
        # Use pre-computed custom date range
        start = self.test_dates["custom_start"]
        end = self.test_dates["custom_end"]

        # Set date range
        self.selector.set_date_range(start, end)

        # Verify preset combo set to "Custom..."
        assert self.selector.preset_combo.currentText() == "Custom..."

        # Verify date display updated with expected content
        display_text = self.selector.date_display.text()

        # Pre-computed expected components for efficiency
        expected_components = ["May", "2023", "1", "15"]

        for component in expected_components:
            assert component in display_text, f"Component '{component}' not found in: {display_text}"

        # No signal should be emitted when using set_date_range
        assert len(self.emitted_ranges) == 0

    def test_preset_combo_population(self) -> None:
        """Test that preset combo is properly populated with expected options."""
        combo_items = [self.selector.preset_combo.itemText(i) for i in range(self.selector.preset_combo.count())]

        # Verify expected presets are available
        expected_presets = ["Today", "Yesterday", "Last 7 Days", "Last 30 Days", "Custom..."]

        for preset in expected_presets:
            assert preset in combo_items, f"Missing preset: {preset}"

    def test_rapid_preset_switching(self) -> None:
        """Test rapid switching between presets."""
        presets_to_test = ["Today", "Yesterday", "Last 7 Days"]
        initial_count = len(self.emitted_ranges)

        for i, preset in enumerate(presets_to_test):
            self.selector.preset_combo.setCurrentText(preset)
            QApplication.processEvents()

            # Verify each change emits a signal
            expected_count = initial_count + i + 1
            assert len(self.emitted_ranges) == expected_count

    @patch("goesvfi.integrity_check.date_range_selector.datetime")
    def test_date_calculations_with_mocked_time(self, mock_datetime) -> None:  # noqa: ANN001, PLR6301
        """Test date calculations with mocked current time for consistency."""
        # Set up a fixed reference time
        fixed_time = datetime(2023, 6, 15, 12, 0, 0, tzinfo=UTC)
        mock_datetime.now.return_value = fixed_time
        mock_datetime.side_effect = datetime  # Allow normal datetime construction

        # Create new selector with mocked time
        selector = CompactDateRangeSelector()

        # Test "Today" preset with fixed time
        selector.preset_combo.setCurrentText("Today")
        QApplication.processEvents()

        start, _end = selector.get_date_range()

        # With fixed time, results should be predictable
        assert start.date() == fixed_time.date()
        assert start.hour == 0


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
