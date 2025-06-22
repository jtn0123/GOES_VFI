import os
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

# !/usr/bin/env python3


# --------------------------------------------------------------------------------
# Helper function: buffered file copy with mtime preservation
# --------------------------------------------------------------------------------
def copy_file_with_buffer(
    source_path: Path,
    dest_path: Path,
    source_mtime_utc: float,
    buffer_size: int = 1048576,
) -> None:
    """
    Copies a file in chunks (buffered) and preserves its last modified time (UTC).
    :param source_path: The full path to the source file.
    :param dest_path: The full path to the destination file.
    :param source_mtime_utc: The source file's mtime in epoch seconds (UTC).
    :param buffer_size: The size of the read/write buffer in bytes (default is 1 MB).
    """
    try:
        with open(source_path, "rb") as sf, open(dest_path, "wb") as df:
            while True:
                buffer = sf.read(buffer_size)
                if not buffer:
                    break
                df.write(buffer)
    except Exception as e:
        print(f"Error copying file {source_path!r} to {dest_path!r}: {e}")
        raise

    # Preserve the source file's modification time (in UTC).
    os.utime(dest_path, (source_mtime_utc, source_mtime_utc))


# --------------------------------------------------------------------------------
# New feature: Scan the converted folder for missing intervals
# --------------------------------------------------------------------------------
# 3. Extract repeated code patterns into utility functions
# 2. Consider using helper classes to group related functionality
# 1. Extract conditional blocks into separate helper functions
# Consider breaking into smaller helper functions for:
# TODO: This function has high cyclomatic complexity (15) and should be refactored.
def scan_for_missing_intervals(converted_folder: Path, interval_minutes: int = 30) -> None:
    """
    Scans the converted folder (recursively) for PNG files named like: baseName_YYYYMMDDThhmmssZ.png,

    extracts the datetime from each file, and finds any missing 30-minute intervals between
    """
    # Regex to capture the date/time from filenames of the form: baseName_YYYYMMDDThhmmssZ.png
    # Groups:
    #   1. The date/time portion: e.g. 20230501T073220
    #   2. Followed by "Z.png"
    datetime_pattern = re.compile(r"_(\d{8}T\d{6})Z\.png$")

    # 1) Gather all .png files in "converted" folder (recursively).
    all_png_files = list(converted_folder.rglob("*.png"))
    if not all_png_files:
        print("\nNo PNG files found in the 'converted' folder. Cannot scan for missing intervals.")
        return

    # 2) Parse out datetime from each filename (where it matches).
    datetimes = []
    for png_file in all_png_files:
        match = datetime_pattern.search(png_file.name)
        if match:
            # match.group(1) is "YYYYMMDDThhmmss"
            dt_str = match.group(1)  # e.g., 20230501T073220
            # Convert that to a Python datetime
            try:
                # strptime format: %Y%m%dT%H%M%S => 2023 05 01 T 07 32 20
                dt_obj = datetime.strptime(dt_str, "%Y%m%dT%H%M%S")
                datetimes.append(dt_obj)
            except ValueError:
                # If something is off, skip it
                pass

    if not datetimes:
        print("\nNo valid date/time-based files found (e.g., baseName_YYYYMMDDThhmmssZ.png).")
        return

    # Sort the list of datetimes
    datetimes.sort()

    # 3) Identify earliest and latest datetime
    earliest = datetimes[0]
    latest = datetimes[-1]

    # 4) Convert our list of existing datetimes to a set for O(1) membership checks
    date_set = set(datetimes)

    # 5) Walk from earliest to latest in 30-minute increments and record whether each interval is found
    current_dt = earliest
    missing_intervals = []

    # We'll create a data structure grouped by date: { date_string: [(time, present_boolean), ...], ... }
    daily_records: Dict[str, List[Tuple[str, bool]]] = {}

    while current_dt <= latest:
        # Chop off the date portion (YYYY-MM-DD) for grouping
        day_str = current_dt.strftime("%Y-%m-%d")
        time_str = current_dt.strftime("%H:%M")

        found = current_dt in date_set
        if not found:
            missing_intervals.append(current_dt)

        if day_str not in daily_records:
            daily_records[day_str] = []
        daily_records[day_str].append((time_str, found))

        # Move ahead by interval_minutes
        current_dt += timedelta(minutes=interval_minutes)

    # 6) Print a "calendar-like" view day by day
    print("\n=== Missing Interval Scan (every {} minutes) ===".format(interval_minutes))
    for day_str in sorted(daily_records.keys()):
        print(f"\nDate: {day_str}")
        for time_str, present in daily_records[day_str]:
            if present:
                # Green check mark
                print(f"  {time_str}  \033[32m✓\033[0m")
            else:
                # Red "X"
                print(f"  {time_str}  \033[31mX\033[0m")

    # 7) If any intervals are missing, you can also print a summary
    print("\nSummary of missing intervals:")
    if missing_intervals:
        for dt_obj in missing_intervals:
            print(f"  \033[31mMissing:\033[0m {dt_obj.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("  No missing intervals!")


def detect_interval(datetimes: List[datetime]) -> int:
    """Detect the most common interval between consecutive timestamps"""
    if len(datetimes) < 2:
        return 30  # Default to 30 minutes if not enough data

    # Calculate all intervals between consecutive timestamps
    intervals = []
    sorted_times = sorted(datetimes)
    for i in range(len(sorted_times) - 1):
        diff = sorted_times[i + 1] - sorted_times[i]
        minutes = diff.total_seconds() / 60
        if 1 <= minutes <= 60:  # Only consider reasonable intervals
            intervals.append(minutes)

    if not intervals:
        return 30  # Default if no valid intervals found

    # Find the most common interval
    from collections import Counter

    interval_counts = Counter(intervals)
    most_common = interval_counts.most_common(1)[0][0]

    # Round to nearest 5 minutes for cleaner intervals
    return round(most_common / 5) * 5


def format_calendar_output(daily_records: Dict[str, List[Tuple[str, bool]]], missing_intervals: List[datetime]) -> str:
    """Format the analysis results as a calendar-style output"""
    output_lines = []
    output_lines.append("\n=== Time Interval Analysis ===")

    # Group missing intervals by date
    missing_by_date: Dict[str, List[str]] = {}
    for dt in missing_intervals:
        date_str = dt.strftime("%Y-%m-%d")
        if date_str not in missing_by_date:
            missing_by_date[date_str] = []
        missing_by_date[date_str].append(dt.strftime("%H:%M"))

    # Print calendar view for each date
    for date_str in sorted(daily_records.keys()):
        output_lines.append(f"\n{date_str}")
        output_lines.append("Time  | Status")
        output_lines.append("------+--------")

        for time_str, present in daily_records[date_str]:
            status = "✓" if present else "X"
            output_lines.append(f"{time_str} | {status}")

        # Always print a "Missing times:" section
        output_lines.append("\nMissing times:")
        if date_str in missing_by_date:
            for time_entry in sorted(missing_by_date[date_str]):
                output_lines.append(f"  - {time_entry}")
        else:
            output_lines.append("  (none)")

    return "\n".join(output_lines)


class DateSorter:
    """
    Sorts files from a source directory into a destination directory
    """

    def sort_files(
        self,
        source: str,
        destination: str,
        date_format: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> None:
        """
        Sorts files from source to destination based on date in filename.

        :param source: Source directory path.
        :param destination: Destination directory path.
        :param date_format: Datetime format string to extract date from filename.
        :param progress_callback: Optional callback for progress updates (current, total).
        :param should_cancel: Optional callback to check if cancellation is requested.
        """
        source_path = Path(source)
        destination_path = Path(destination)

        if not source_path.is_dir():
            raise FileNotFoundError(f"Source directory not found: {source}")
        if not destination_path.exists():
            destination_path.mkdir(parents=True, exist_ok=True)

        all_files = list(source_path.rglob("*"))
        total_files = len(all_files)
        processed_count = 0

        for file_path in all_files:
            if should_cancel and should_cancel():
                print("Sorting cancelled.")
                return

            if file_path.is_file():
                try:
                    # Attempt to extract date from filename using the provided format
                    # This is a simplified approach; a more robust solution might be needed
                    # depending on the actual filename patterns.
                    # Assuming filename is something like 'prefix_YYYYMMDD_HHMMSS.ext'
                    # and date_format is '%Y%m%d_%H%M%S'
                    file_name = file_path.name
                    # Find the part of the filename that matches the date_format pattern
                    # This requires a more sophisticated regex based on the date_format
                    # For now, let's assume the date part is extractable.
                    # A simple approach: try to parse the whole filename or a known part
                    # This needs refinement based on actual file naming conventions.

                    # Placeholder for actual date extraction logic
                    # Example: if date_format is '%Y/%m/%d' and filename is 'data/2023/10/26/image.png'
                    # We need to extract '2023/10/26' and parse it.
                    # A more general approach would involve regex matching based on date_format components.

                    # For now, let's use a simplified example assuming a date string is part of the name
                    # like 'image_20231026120000.png' and format is '%Y%m%d%H%M%S'
                    # This part needs to be made robust based on real file patterns and date_format.

                    # Example: Extract date from filename like 'prefix_YYYYMMDDTHHMMSSZ.ext'
                    # This regex matches the pattern used in scan_for_missing_intervals
                    match = re.search(r"_(\d{8}T\d{6})Z", file_name)
                    if match:
                        date_str = match.group(1)  # YYYYMMDDTHHMMSS
                        # Parse the extracted date string
                        file_date = datetime.strptime(date_str, "%Y%m%dT%H%M%S")

                        # Create destination path based on date format
                        # Example: destination/YYYY/MM/DD/filename.ext
                        relative_dest_dir = file_date.strftime(date_format)
                        final_dest_dir = destination_path / relative_dest_dir
                        final_dest_dir.mkdir(parents=True, exist_ok=True)

                        dest_file_path = final_dest_dir / file_name

                        # Copy the file
                        shutil.copy2(file_path, dest_file_path)  # copy2 preserves metadata

                        processed_count += 1
                        if progress_callback:
                            progress_callback(processed_count, total_files)

                except ValueError as e:
                    print(f"Could not parse date from filename {file_name!r} " f"with format {date_format!r}: {e}")
                    # Optionally handle files that don't match the format
                    pass  # Skip files that don't match the expected date format
                except Exception as e:
                    print(f"Error processing file {file_path!r}: {e}")
                    # Handle other potential errors during file processing

        if progress_callback:
            progress_callback(total_files, total_files)  # Ensure 100% progress at the end


# The original main function is removed as the DateSorter class will handle sorting logic.
# The helper functions like scan_for_missing_intervals, detect_interval, format_calendar_output
# are kept as they might be useful utilities, potentially moved or refactored later.

if __name__ == "__main__":
    # Example usage (for testing the class directly)
    # sorter = DateSorter()
    # sorter.sort_files(source="/path/to/source", destination="/path/to/destination", date_format="%Y/%m/%d")
    print("DateSorter class is intended to be used as a module.")
