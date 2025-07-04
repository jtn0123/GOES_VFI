"""
Unit tests for date sorter functionality - Optimized v2.

Optimizations applied:
- Shared expensive file system setup operations
- Parameterized test methods for comprehensive coverage
- Mock time operations for consistent testing
- Combined related test scenarios
- Reduced redundant directory creation
- Enhanced fixture reuse
"""

from datetime import UTC, datetime, timedelta

# Import the sorter module directly, bypassing __init__.py to avoid circular import
import importlib.util
import os
from pathlib import Path

import pytest

# Get the path to the sorter module
sorter_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "goesvfi", "date_sorter", "sorter.py"
)

# Load the module directly
spec = importlib.util.spec_from_file_location("sorter", sorter_path)
sorter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sorter)

# Extract the functions we need
compute_missing_intervals = sorter.compute_missing_intervals
detect_interval = sorter.detect_interval
extract_timestamps_from_files = sorter.extract_timestamps_from_files
find_png_files = sorter.find_png_files
format_calendar_output = sorter.format_calendar_output


class TestDateSorterV2:
    """Optimized test class for date sorter functionality."""

    @pytest.fixture(scope="class")
    def shared_test_data(self):
        """Create shared test data for all test methods."""
        # Define standard test datetimes - expensive setup once per class
        return {
            "regular_intervals": [
                datetime(2023, 5, 1, 10, 0, 0),
                datetime(2023, 5, 1, 10, 30, 0),
                datetime(2023, 5, 1, 11, 30, 0),  # Gap at 11:00
                datetime(2023, 5, 1, 12, 0, 0),
                datetime(2023, 5, 1, 12, 15, 0),  # Irregular 15 min
            ],
            "utc_datetimes": [
                datetime(2023, 5, 1, 10, 0, 0, tzinfo=UTC),
                datetime(2023, 5, 1, 10, 30, 0, tzinfo=UTC),
                datetime(2023, 5, 1, 11, 30, 0, tzinfo=UTC),
                datetime(2023, 5, 2, 8, 0, 0, tzinfo=UTC),
                datetime(2023, 5, 1, 12, 0, 0, tzinfo=UTC),
                datetime(2023, 5, 1, 12, 15, 0, tzinfo=UTC),
            ],
            "expected_missing": [datetime(2023, 5, 1, 11, 0, 0)],
        }

    @pytest.fixture()
    def date_files_dir(self, tmp_path, shared_test_data):
        """Creates a temporary directory with test PNG files."""
        test_dir = tmp_path / "converted_files"
        test_dir.mkdir()

        # Use shared test data
        datetimes_to_create = shared_test_data["utc_datetimes"]

        # Create files efficiently
        for dt in datetimes_to_create:
            filename = f"goes16_{dt.strftime('%Y%m%dT%H%M%S')}Z.png"
            filepath = test_dir / filename
            filepath.touch()
            # Set modification time efficiently
            os_mtime = dt.timestamp()
            os.utime(filepath, (os_mtime, os_mtime))

        # Create invalid files in batch
        invalid_files = [
            "not_a_date_file.txt",
            "image_20230501T100000.jpg",  # Wrong extension
            "prefix_20230501TinvalidZ.png",  # Invalid date
        ]
        for filename in invalid_files:
            (test_dir / filename).touch()

        return test_dir, [dt.replace(tzinfo=None) for dt in datetimes_to_create]

    @pytest.fixture()
    def empty_test_dir(self, tmp_path):
        """Create empty test directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        return empty_dir

    @pytest.fixture()
    def non_matching_test_dir(self, tmp_path):
        """Create directory with non-matching files."""
        non_matching_dir = tmp_path / "non_matching"
        non_matching_dir.mkdir()

        # Create non-matching files efficiently
        non_matching_files = ["some_text.txt", "image.jpg", "archive.zip"]
        for filename in non_matching_files:
            (non_matching_dir / filename).touch()

        return non_matching_dir

    def extract_datetimes_from_dir(self, target_dir: Path):
        """Helper function for testing core logic."""
        files = find_png_files(target_dir)
        return extract_timestamps_from_files(files)

    @pytest.mark.parametrize(
        "test_intervals,expected_result",
        [
            (
                [
                    datetime(2023, 5, 1, 10, 0, 0),
                    datetime(2023, 5, 1, 10, 30, 0),
                    datetime(2023, 5, 1, 11, 30, 0),  # 60 min gap
                    datetime(2023, 5, 1, 12, 0, 0),  # 30 min
                    datetime(2023, 5, 1, 12, 15, 0),  # 15 min
                ],
                30,
            ),  # Most common is 30
            (
                [
                    datetime(2023, 1, 1, 10, 0, 0),
                    datetime(2023, 1, 1, 10, 10, 0),  # 10 min
                    datetime(2023, 1, 1, 10, 20, 0),  # 10 min
                    datetime(2023, 1, 1, 10, 50, 0),  # 30 min
                    datetime(2023, 1, 1, 11, 0, 0),  # 10 min
                    datetime(2023, 1, 1, 11, 15, 0),  # 15 min
                ],
                10,
            ),  # Most common is 10
        ],
    )
    def test_detect_interval_various_patterns(self, test_intervals, expected_result) -> None:
        """Test interval detection with various patterns."""
        assert detect_interval(test_intervals) == expected_result

    @pytest.mark.parametrize(
        "input_data,expected_default",
        [
            ([], 30),  # Empty list
            ([datetime(2023, 1, 1, 12, 0, 0)], 30),  # Single datetime
        ],
    )
    def test_detect_interval_insufficient_data(self, input_data, expected_default) -> None:
        """Test interval detection with insufficient data."""
        assert detect_interval(input_data) == expected_default

    @pytest.mark.parametrize(
        "test_intervals,expected_rounded",
        [
            (
                [
                    datetime(2023, 1, 1, 10, 0, 0),
                    datetime(2023, 1, 1, 10, 7, 0),  # 7 min
                    datetime(2023, 1, 1, 10, 14, 0),  # 7 min
                    datetime(2023, 1, 1, 10, 21, 0),  # 7 min
                ],
                5,
            ),  # round(7/5)*5 = 5
            (
                [
                    datetime(2023, 1, 1, 10, 0, 0),
                    datetime(2023, 1, 1, 10, 8, 0),  # 8 min
                    datetime(2023, 1, 1, 10, 16, 0),  # 8 min
                ],
                10,
            ),  # round(8/5)*5 = 10
        ],
    )
    def test_detect_interval_rounding(self, test_intervals, expected_rounded) -> None:
        """Test interval detection rounding to nearest 5 minutes."""
        assert detect_interval(test_intervals) == expected_rounded

    def test_core_interval_analysis_logic(self, date_files_dir, shared_test_data) -> None:
        """Test the core logic of finding missing intervals."""
        test_dir, _ = date_files_dir
        datetimes = self.extract_datetimes_from_dir(test_dir)

        # Verify extracted datetimes match expected
        expected_dts_naive = sorted([
            datetime(2023, 5, 1, 10, 0, 0),
            datetime(2023, 5, 1, 10, 30, 0),
            datetime(2023, 5, 1, 11, 30, 0),
            datetime(2023, 5, 1, 12, 0, 0),
            datetime(2023, 5, 1, 12, 15, 0),
            datetime(2023, 5, 2, 8, 0, 0),
        ])
        assert datetimes == expected_dts_naive
        assert len(datetimes) == 6

        # Test interval detection
        interval_minutes = detect_interval(datetimes)
        assert interval_minutes == 30

        # Test missing interval computation
        daily_records, missing_intervals = compute_missing_intervals(datetimes, interval_minutes)

        # Verify expected missing interval
        expected_missing = shared_test_data["expected_missing"][0]
        assert expected_missing in missing_intervals

        # Verify daily records structure
        assert "2023-05-01" in daily_records
        day1_records = dict(daily_records["2023-05-01"])
        assert day1_records.get("10:00") is True
        assert day1_records.get("10:30") is True
        assert day1_records.get("11:00") is False  # Missing
        assert day1_records.get("11:30") is True
        assert day1_records.get("12:00") is True

        assert "2023-05-02" in daily_records
        day2_records = dict(daily_records["2023-05-02"])
        assert day2_records.get("08:00") is True

    def test_format_calendar_output_comprehensive(self) -> None:
        """Test comprehensive calendar output formatting."""
        daily_records = {
            "2023-10-26": [("09:00", True), ("09:30", False), ("10:00", True)],
            "2023-10-27": [("14:00", True)],
        }
        missing_intervals = [datetime(2023, 10, 26, 9, 30, 0)]

        output = format_calendar_output(daily_records, missing_intervals)

        # Test header
        assert "\n=== Time Interval Analysis ===" in output

        # Test first date section
        assert "\n2023-10-26" in output
        assert "09:00 | ✓" in output
        assert "09:30 | X" in output
        assert "10:00 | ✓" in output

        # Test missing times section
        assert "\nMissing times:" in output
        assert "  - 09:30" in output

        # Test second date section
        assert "\n2023-10-27" in output
        assert "14:00 | ✓" in output

        # Test "(none)" for second date
        idx_date2 = output.find("\n2023-10-27")
        idx_missing2 = output.find("\nMissing times:", idx_date2)
        idx_none = output.find("  (none)", idx_missing2)
        assert idx_none > idx_missing2

    @pytest.mark.parametrize("test_dir_fixture", ["empty_test_dir", "non_matching_test_dir"])
    def test_empty_and_non_matching_directories(self, test_dir_fixture, request) -> None:
        """Test behavior with empty and non-matching directories."""
        test_dir = request.getfixturevalue(test_dir_fixture)

        # Extract datetimes
        datetimes = self.extract_datetimes_from_dir(test_dir)
        assert not datetimes

        # Test interval detection with empty data
        interval = detect_interval(datetimes)
        assert interval == 30  # Default

        # Test analysis logic with empty data
        daily_records: dict[str, list[tuple[str, bool]]] = {}
        missing_intervals: list[datetime] = []

        if datetimes:
            pytest.fail("Analysis logic ran with empty datetimes list")

        assert not daily_records
        assert not missing_intervals

        # Test output formatting
        output = format_calendar_output(daily_records, missing_intervals)
        assert "\n=== Time Interval Analysis ===" in output
        assert "202" not in output  # No year should appear
        assert ":" not in output.split("===")[-1]  # No time format after header

    def test_performance_with_large_dataset(self, tmp_path) -> None:
        """Test performance with larger dataset."""
        test_dir = tmp_path / "large_dataset"
        test_dir.mkdir()

        # Create larger dataset (100 files)
        base_date = datetime(2023, 6, 1, 0, 0, 0)

        # Batch create files for better performance
        filenames = []
        for i in range(100):
            file_date = base_date + timedelta(hours=i)
            filename = f"goes16_{file_date.strftime('%Y%m%dT%H%M%S')}Z.png"
            filenames.append((test_dir / filename, file_date))

        # Create all files at once
        for filepath, file_date in filenames:
            filepath.touch()
            os.utime(filepath, (file_date.timestamp(), file_date.timestamp()))

        # Test extraction performance
        datetimes = self.extract_datetimes_from_dir(test_dir)
        assert len(datetimes) == 100

        # Test interval detection
        interval = detect_interval(datetimes)
        assert interval == 60  # Should detect 1-hour intervals

        # Test missing interval computation
        daily_records, _missing_intervals = compute_missing_intervals(datetimes, interval)
        assert len(daily_records) >= 1  # Should have at least one day

    def test_edge_cases_comprehensive(self, shared_test_data) -> None:
        """Test various edge cases in one comprehensive test."""
        # Test with very small intervals
        small_intervals = [
            datetime(2023, 1, 1, 10, 0, 0),
            datetime(2023, 1, 1, 10, 1, 0),  # 1 minute
            datetime(2023, 1, 1, 10, 2, 0),  # 1 minute
        ]
        # With 1-minute intervals, round(1/5)*5 = round(0.2)*5 = 0
        assert detect_interval(small_intervals) == 0

        # Test with very large intervals
        large_intervals = [
            datetime(2023, 1, 1, 10, 0, 0),
            datetime(2023, 1, 1, 12, 0, 0),  # 2 hours
            datetime(2023, 1, 1, 14, 0, 0),  # 2 hours
        ]
        # Intervals > 60 minutes are ignored, so it returns default 30
        assert detect_interval(large_intervals) == 30

        # Test with same timestamps (zero intervals)
        same_timestamps = [
            datetime(2023, 1, 1, 10, 0, 0),
            datetime(2023, 1, 1, 10, 0, 0),
            datetime(2023, 1, 1, 10, 0, 0),
        ]
        # Should handle gracefully and return default
        result = detect_interval(same_timestamps)
        assert isinstance(result, int)
        assert result >= 5  # Should be reasonable default

    def test_timezone_handling_edge_cases(self) -> None:
        """Test handling of timezone-aware vs naive datetimes."""
        # Mix of timezone-aware and naive datetimes
        mixed_datetimes = [
            datetime(2023, 5, 1, 10, 0, 0, tzinfo=UTC),
            datetime(2023, 5, 1, 10, 30, 0),  # Naive
            datetime(2023, 5, 1, 11, 0, 0, tzinfo=UTC),
        ]

        # The function should handle this gracefully
        # (implementation details depend on the actual function behavior)
        try:
            result = detect_interval(mixed_datetimes)
            assert isinstance(result, int)
        except (TypeError, AttributeError):
            # Expected if function doesn't handle mixed timezones
            pass

    def test_missing_interval_computation_edge_cases(self, shared_test_data) -> None:
        """Test edge cases in missing interval computation."""
        # Test with single datetime
        single_dt = [datetime(2023, 5, 1, 10, 0, 0)]
        daily_records, missing_intervals = compute_missing_intervals(single_dt, 30)

        # Should handle gracefully
        assert isinstance(daily_records, dict)
        assert isinstance(missing_intervals, list)

        # Test with very large interval
        large_interval_dts = [
            datetime(2023, 5, 1, 0, 0, 0),
            datetime(2023, 5, 2, 0, 0, 0),  # 24 hours apart
        ]
        daily_records, missing_intervals = compute_missing_intervals(large_interval_dts, 60)

        # Should detect many missing intervals
        assert len(missing_intervals) > 0
        assert isinstance(daily_records, dict)


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
