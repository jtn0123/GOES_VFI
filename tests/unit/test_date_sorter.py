import os  # Needed for os.utime
import re  # Need re for simulating file parsing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Functions to test from the sorter module
from goesvfi.date_sorter.sorter import (  # main as date_sorter_main,  # Removed as main function no longer exists
    detect_interval,
    format_calendar_output,
)

# --- Fixtures ---


@pytest.fixture
def date_files_dir(tmp_path):
    """Creates a temporary directory and populates it with test PNG files."""
    test_dir = tmp_path / "converted_files"
    test_dir.mkdir()

    # Define datetimes for test files
    # Regular 30 min interval
    dt1 = datetime(2023, 5, 1, 10, 0, 0, tzinfo=timezone.utc)
    dt2 = datetime(2023, 5, 1, 10, 30, 0, tzinfo=timezone.utc)
    # Gap here (11:00 missing)
    dt3 = datetime(2023, 5, 1, 11, 30, 0, tzinfo=timezone.utc)
    # Different day
    dt4 = datetime(2023, 5, 2, 8, 0, 0, tzinfo=timezone.utc)
    # Irregular interval (15 min) - should still detect 30 min as most common
    dt5 = datetime(2023, 5, 1, 12, 0, 0, tzinfo=timezone.utc)  # 30 min after dt3
    dt6 = datetime(2023, 5, 1, 12, 15, 0, tzinfo=timezone.utc)  # 15 min after dt5

    datetimes_to_create = [dt1, dt2, dt3, dt4, dt5, dt6]

    # Create files with the standard name format
    for i, dt in enumerate(datetimes_to_create):
        # Format: baseName_YYYYMMDDThhmmssZ.png
        filename = f"goes16_{dt.strftime('%Y%m%dT%H%M%S')}Z.png"
        filepath = test_dir / filename
        filepath.touch()
        # Set modification time (though the sorter uses filename)
        os_mtime = dt.timestamp()
        os.utime(filepath, (os_mtime, os_mtime))

    # Create some files that should be ignored
    (test_dir / "not_a_date_file.txt").touch()
    (test_dir / "image_20230501T100000.jpg").touch()  # Wrong extension
    (test_dir / "prefix_20230501TinvalidZ.png").touch()  # Invalid date part

    return (
        test_dir,
        datetimes_to_create,
    )  # Return the dir and the valid datetimes created


# --- Helper Function for Testing Core Logic ---
# This mimics the file scanning and date extraction part of the main/scan functions
def extract_datetimes_from_dir(target_dir: Path):
    datetime_pattern = re.compile(r"_(\d{8}T\d{6})Z\.png$")
    datetimes = []
    png_files = list(target_dir.rglob("*.png"))
    for file_path in png_files:
        match = datetime_pattern.search(file_path.name)
        if match:
            try:
                dt_str = match.group(1)
                # NOTE: The original code uses naive datetimes from strptime.
                # For consistency in testing, we'll stick to that, although UTC is implied by 'Z'.
                dt_obj = datetime.strptime(dt_str, "%Y%m%dT%H%M%S")
                datetimes.append(dt_obj)
            except ValueError:
                pass  # Ignore files with invalid date strings
    datetimes.sort()
    return datetimes


# --- Test Functions ---


def test_detect_interval_regular(date_files_dir):
    """Test interval detection with mostly regular intervals."""
    _, created_dts_utc = date_files_dir
    # Convert to naive datetimes as used in the sorter's parsing logic
    created_dts_naive = [dt.replace(tzinfo=None) for dt in created_dts_utc]

    # Manually select datetimes that form 30 min intervals mostly
    test_dts = [
        datetime(2023, 5, 1, 10, 0, 0),
        datetime(2023, 5, 1, 10, 30, 0),
        # 11:00 missing
        datetime(2023, 5, 1, 11, 30, 0),  # 60 min diff from previous
        datetime(2023, 5, 1, 12, 0, 0),  # 30 min diff
        datetime(2023, 5, 1, 12, 15, 0),  # 15 min diff
    ]
    # Intervals: 30, 60, 30, 15. Most common is 30.
    assert detect_interval(test_dts) == 30


def test_detect_interval_insufficient_data():
    """Test interval detection with less than 2 datetimes."""
    assert detect_interval([]) == 30  # Default
    assert detect_interval([datetime(2023, 1, 1, 12, 0, 0)]) == 30  # Default


def test_detect_interval_mixed():
    """Test interval detection with mixed intervals."""
    test_dts = [
        datetime(2023, 1, 1, 10, 0, 0),  # Start
        datetime(2023, 1, 1, 10, 10, 0),  # 10 min
        datetime(2023, 1, 1, 10, 20, 0),  # 10 min
        datetime(2023, 1, 1, 10, 50, 0),  # 30 min
        datetime(2023, 1, 1, 11, 0, 0),  # 10 min
        datetime(2023, 1, 1, 11, 15, 0),  # 15 min
    ]
    # Intervals: 10, 10, 30, 10, 15. Most common is 10. Rounded to nearest 5 is 10.
    assert detect_interval(test_dts) == 10


def test_detect_interval_rounds_correctly():
    """Test rounding to nearest 5 minutes."""
    test_dts = [
        datetime(2023, 1, 1, 10, 0, 0),
        datetime(2023, 1, 1, 10, 7, 0),  # 7 min -> rounds to 5? No, interval is 7.
        datetime(2023, 1, 1, 10, 14, 0),  # 7 min
        datetime(2023, 1, 1, 10, 21, 0),  # 7 min
    ]
    # Most common interval is 7. round(7 / 5) * 5 = round(1.4) * 5 = 1 * 5 = 5.
    assert detect_interval(test_dts) == 5

    test_dts_2 = [
        datetime(2023, 1, 1, 10, 0, 0),
        datetime(2023, 1, 1, 10, 8, 0),  # 8 min
        datetime(2023, 1, 1, 10, 16, 0),  # 8 min
    ]
    # Most common interval is 8. round(8 / 5) * 5 = round(1.6) * 5 = 2 * 5 = 10.
    assert detect_interval(test_dts_2) == 10


def test_core_interval_analysis_logic(date_files_dir):
    """Test the logic of finding missing intervals from extracted datetimes."""
    test_dir, _ = date_files_dir
    datetimes = extract_datetimes_from_dir(test_dir)

    # Manually verify extracted datetimes (naive as per sorter logic)
    expected_dts_naive = sorted(
        [
            datetime(2023, 5, 1, 10, 0, 0),
            datetime(2023, 5, 1, 10, 30, 0),
            datetime(2023, 5, 1, 11, 30, 0),
            datetime(2023, 5, 1, 12, 0, 0),
            datetime(
                2023, 5, 1, 12, 15, 0
            ),  # Note: This exists but might be skipped depending on detected interval
            datetime(2023, 5, 2, 8, 0, 0),
        ]
    )
    assert datetimes == expected_dts_naive
    assert len(datetimes) == 6  # Ensure only valid files were parsed

    # --- Simulate the analysis part of main() ---
    if not datetimes:
        pytest.fail("No datetimes extracted, cannot test analysis logic.")

    interval_minutes = detect_interval(datetimes)
    assert interval_minutes == 30  # Based on fixture data (10:00, 10:30, 11:30, 12:00)

    datetimes.sort()
    earliest = datetimes[0]
    latest = datetimes[-1]
    date_set = set(datetimes)

    daily_records = {}
    missing_intervals = []
    current_dt = earliest

    # Walk through the expected intervals
    while current_dt <= latest:
        day_str = current_dt.strftime("%Y-%m-%d")
        time_str = current_dt.strftime("%H:%M")

        if day_str not in daily_records:
            daily_records[day_str] = []

        # Check if this *exact* datetime exists in our set
        found = current_dt in date_set
        daily_records[day_str].append((time_str, found))

        if not found:
            missing_intervals.append(current_dt)

        current_dt += timedelta(
            minutes=interval_minutes
        )  # Advance by detected interval

    # --- Assertions ---
    # Expected missing intervals based on 30 min steps from 10:00 to 12:00 on day 1,
    # and then jumping to day 2.
    # Day 1: 10:00 (found), 10:30 (found), 11:00 (missing), 11:30 (found), 12:00 (found)
    # The 12:15 file exists but is not on a 30-min interval from 10:00, so it's ignored in this walk.
    # Day 2: Starts checking from 08:00 (found). The loop continues until latest (08:00).
    # The loop logic might need refinement if the range spans multiple days with large gaps.
    # Let's focus on the known gap:
    expected_missing = [
        datetime(2023, 5, 1, 11, 0, 0),
        # Potentially many others depending on how far the loop runs past the last item on day 1
        # before jumping to day 2. Let's check the first expected missing one.
    ]
    assert expected_missing[0] in missing_intervals

    # Check daily_records structure (example for day 1)
    assert "2023-05-01" in daily_records
    day1_records = dict(
        daily_records["2023-05-01"]
    )  # Convert list of tuples to dict for easier check
    assert day1_records.get("10:00") is True
    assert day1_records.get("10:30") is True
    assert day1_records.get("11:00") is False  # Missing
    assert day1_records.get("11:30") is True
    assert day1_records.get("12:00") is True
    # 12:15 is not checked because the step is 30 mins

    assert "2023-05-02" in daily_records
    day2_records = dict(daily_records["2023-05-02"])
    # The loop starts from earliest (day 1) and steps by 30 mins. It will eventually
    # generate checks for day 2, but the first *found* one should be 08:00.
    # Whether 00:00, 00:30 etc. on day 2 are marked missing depends on the exact loop end condition.
    # Let's check if 08:00 is correctly marked as found.
    assert day2_records.get("08:00") is True


def test_format_calendar_output():
    """Test the formatting of the calendar output string."""
    daily_records = {
        "2023-10-26": [("09:00", True), ("09:30", False), ("10:00", True)],
        "2023-10-27": [("14:00", True)],
    }
    missing_intervals = [datetime(2023, 10, 26, 9, 30, 0)]

    output = format_calendar_output(daily_records, missing_intervals)

    assert "\n=== Time Interval Analysis ===" in output
    assert "\n2023-10-26" in output
    assert "09:00 | ✓" in output
    assert "09:30 | X" in output
    assert "10:00 | ✓" in output
    assert "\nMissing times:" in output
    assert "  - 09:30" in output  # Missing time listed for the date

    assert "\n2023-10-27" in output
    assert "14:00 | ✓" in output
    # Check missing section for the second date
    # Find the index of the second date header
    idx_date2 = output.find("\n2023-10-27")
    # Find the index of "Missing times:" after the second date header
    idx_missing2 = output.find("\nMissing times:", idx_date2)
    # Find the index of "(none)" after that "Missing times:"
    idx_none = output.find("  (none)", idx_missing2)
    assert (
        idx_none > idx_missing2
    )  # Ensure "(none)" appears under the second date's missing section


def test_empty_directory(tmp_path):
    """Test analysis with an empty directory."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    datetimes = extract_datetimes_from_dir(empty_dir)
    assert not datetimes  # No datetimes should be extracted

    # Simulate main logic path for empty dir
    interval = detect_interval(datetimes)
    assert interval == 30  # Default

    # Analysis logic should handle empty list gracefully
    daily_records = {}
    missing_intervals = []
    if datetimes:
        # This block shouldn't run
        pytest.fail("Analysis logic ran with empty datetimes list")
    else:
        # Expected state for empty input
        pass

    assert not daily_records
    assert not missing_intervals

    output = format_calendar_output(daily_records, missing_intervals)
    assert "\n=== Time Interval Analysis ===" in output
    # Should not contain any date headers or time entries
    assert "202" not in output  # Check no year appears
    assert (
        ":" not in output.split("===")[-1]
    )  # Check no time format appears after header


def test_no_matching_files(tmp_path):
    """Test analysis with a directory containing no matching PNG files."""
    non_matching_dir = tmp_path / "non_matching"
    non_matching_dir.mkdir()
    (non_matching_dir / "some_text.txt").touch()
    (non_matching_dir / "image.jpg").touch()
    (non_matching_dir / "archive.zip").touch()

    datetimes = extract_datetimes_from_dir(non_matching_dir)
    assert not datetimes

    # Rest of the test is similar to test_empty_directory
    interval = detect_interval(datetimes)
    assert interval == 30
    daily_records = {}
    missing_intervals = []
    assert not daily_records
    assert not missing_intervals
    output = format_calendar_output(daily_records, missing_intervals)
    assert "\n=== Time Interval Analysis ===" in output
    assert "202" not in output
    assert ":" not in output.split("===")[-1]


# Note: Testing the `main` function directly is complex due to CWD reliance and callbacks.
# The tests above cover the core reusable logic components: `detect_interval`,
# the analysis algorithm (simulated via `extract_datetimes_from_dir` and manual steps),
# and `format_calendar_output`. This provides good coverage of the module's functionality.
# Testing `scan_for_missing_intervals` would largely duplicate the analysis logic test,
# adding complexity for capturing print output.
