#!/usr/bin/env python3

import os
import re
import shutil
import time
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Set, Callable

# --------------------------------------------------------------------------------
# Helper function: buffered file copy with mtime preservation
# --------------------------------------------------------------------------------
def copy_file_with_buffer(source_path: Path, dest_path: Path, source_mtime_utc: float, buffer_size: int = 1048576) -> None:
    """
    Copies a file in chunks (buffered) and preserves its last modified time (UTC).
    :param source_path: The full path to the source file.
    :param dest_path: The full path to the destination file.
    :param source_mtime_utc: The source file's mtime in epoch seconds (UTC).
    :param buffer_size: The size of the read/write buffer in bytes (default is 1 MB).
    """
    try:
        with open(source_path, 'rb') as sf, open(dest_path, 'wb') as df:
            while True:
                buffer = sf.read(buffer_size)
                if not buffer:
                    break
                df.write(buffer)
    except Exception as e:
        print(f"Error copying file '{source_path}' to '{dest_path}': {e}")
        raise

    # Preserve the source file's modification time (in UTC).
    os.utime(dest_path, (source_mtime_utc, source_mtime_utc))


# --------------------------------------------------------------------------------
# New feature: Scan the converted folder for missing intervals
# --------------------------------------------------------------------------------
def scan_for_missing_intervals(converted_folder: Path, interval_minutes: int = 30) -> None:
    """
    Scans the converted folder (recursively) for PNG files named like: baseName_YYYYMMDDThhmmssZ.png,
    extracts the datetime from each file, and finds any missing 30-minute intervals between
    the earliest and latest file times. Prints a text-based "calendar" of found/missing intervals.
    """
    # Regex to capture the date/time from filenames of the form: baseName_YYYYMMDDThhmmssZ.png
    # Groups:
    #   1. The date/time portion: e.g. 20230501T073220
    #   2. Followed by "Z.png"
    datetime_pattern = re.compile(r'_(\d{8}T\d{6})Z\.png$')

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

        found = (current_dt in date_set)
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
        for (time_str, present) in daily_records[day_str]:
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
            for time in sorted(missing_by_date[date_str]):
                output_lines.append(f"  - {time}")
        else:
            output_lines.append("  (none)")
    
    return "\n".join(output_lines)

def main(interactive: bool = True, progress_callback: Callable[[int], None] | None = None, status_callback: Callable[[str], None] | None = None, log_callback: Callable[[str], None] | None = None) -> None:
    """Main function that analyzes files for date/time consistency."""
    def update_status(msg: str) -> None:
        if status_callback:
            status_callback(msg)
        elif interactive:
            print(msg)

    try:
        # Initial setup and file scanning
        root_dir = Path.cwd()
        png_files = list(root_dir.rglob("*.png"))
        
        if not png_files:
            update_status("No PNG files found in selected folder.")
            if progress_callback:
                progress_callback(100)
            return
        
        total_files = len(png_files)
        update_status(f"Found {total_files} PNG files to analyze")
        if progress_callback:
            progress_callback(10)
            
        # Extract dates from filenames
        update_status("Analyzing file dates...")
        datetime_pattern = re.compile(r'_(\d{8}T\d{6})Z\.png$')
        datetimes = []
        invalid_files = []
        
        # Process files in smaller batches
        batch_size = max(1, total_files // 10)  # Update progress every 10%
        for idx, file_path in enumerate(png_files):
            if progress_callback and idx % batch_size == 0:
                progress = int((idx / total_files) * 50)
                progress_callback(progress)
                
            match = datetime_pattern.search(file_path.name)
            if match:
                try:
                    dt_str = match.group(1)
                    dt_obj = datetime.strptime(dt_str, "%Y%m%dT%H%M%S")
                    datetimes.append(dt_obj)
                except ValueError:
                    update_status(f"Warning: Invalid date format in {file_path.name}")
                    invalid_files.append(file_path.name)
            else:
                update_status(f"Warning: Invalid date format in {file_path.name}")
                invalid_files.append(file_path.name)

        if invalid_files:
            update_status("\nFiles with invalid date formats:")
            for fname in invalid_files:
                update_status(f"  - {fname}")
            update_status("")

        if not datetimes:
            update_status("No files with valid dates found. Cannot continue analysis.")
            if progress_callback:
                progress_callback(100)  # Set progress to 100% since we're done
            return

        # Ensure progress updates continue
        if progress_callback:
            progress_callback(75)  # Show substantial progress

        # After collecting datetimes, detect interval
        interval_minutes = detect_interval(datetimes)
        update_status(f"\nDetected interval: {interval_minutes} minutes")
        
        # Sort and analyze
        datetimes.sort()
        earliest = datetimes[0]
        latest = datetimes[-1]
        date_set = set(datetimes)
        
        # Group by date
        daily_records: Dict[str, List[Tuple[str, bool]]] = {}
        missing_intervals = []
        current_dt = earliest
        
        while current_dt <= latest:
            day_str = current_dt.strftime("%Y-%m-%d")
            time_str = current_dt.strftime("%H:%M")
            
            if day_str not in daily_records:
                daily_records[day_str] = []
            
            found = current_dt in date_set
            daily_records[day_str].append((time_str, found))
            
            if not found:
                missing_intervals.append(current_dt)
                
            current_dt += timedelta(minutes=interval_minutes)
            
            if progress_callback:
                progress = min(100, 50 + int(((current_dt - earliest).total_seconds() / 
                                            (latest - earliest).total_seconds()) * 50))
                progress_callback(progress)
        
        # Generate calendar view
        calendar_output = format_calendar_output(daily_records, missing_intervals)
        update_status(calendar_output)
        
        # Generate summary
        total_intervals = len(missing_intervals) + len(datetimes)
        completion_rate = (len(datetimes) / total_intervals * 100) if total_intervals > 0 else 0
        
        summary = [
            f"\nAnalysis Summary:",
            f"Total files analyzed: {len(datetimes)}",
            f"Detected interval: {interval_minutes} minutes",
            f"Date range: {earliest.strftime('%Y-%m-%d %H:%M')} to {latest.strftime('%Y-%m-%d %H:%M')}",
            f"Missing intervals: {len(missing_intervals)}",
            f"Completion rate: {completion_rate:.1f}%"
        ]
        
        for line in summary:
            update_status(line)
            
        update_status("\nAnalysis complete!")
        
    except Exception as e:
        update_status(f"Error during analysis: {str(e)}")
        raise

    if interactive:
        input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
