#!/usr/bin/env python3
"""
Example script demonstrating date format conversion for satellite imagery.

This script shows how to use the date_utils module to convert between calendar dates
and day of year (DOY) formats for satellite imagery directories.
"""

import os
import sys
from datetime import date, datetime
from pathlib import Path

# Add the project root to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from goesvfi.integrity_check.time_index import (
    SatellitePattern,
    extract_timestamp_and_satellite,
    extract_timestamp_from_directory_name,
    to_cdn_url,
    to_s3_key,
)
from goesvfi.utils import date_utils


def demonstrate_date_conversion():
    """Demonstrate conversion between calendar dates and DOY format."""
    print("Date Conversion Examples")
    print("=======================")

    # Calendar date to DOY
    today = date.today()
    doy = date_utils.date_to_doy(today)
    print(f"Today ({today.strftime('%Y-%m-%d')}) is day {doy} of the year")

    # DOY to calendar date
    test_year = 2023
    test_doy = 300  # Example: day 300 of 2023
    calendar_date = date_utils.doy_to_date(test_year, test_doy)
    print(f"Day {test_doy} of {test_year} is {calendar_date.strftime('%Y-%m-%d')}")

    # Format as different path styles
    print("\nPath Formatting Examples")
    print("=======================")
    print(
        f"Calendar format: {date_utils.format_satellite_path(calendar_date, 'calendar')}"
    )
    print(f"DOY format:      {date_utils.format_satellite_path(calendar_date, 'doy')}")
    print(
        f"Compact DOY:     {date_utils.format_satellite_path(calendar_date, 'compact_doy')}"
    )

    # Parse satellite paths
    print("\nParsing Satellite Paths")
    print("======================")
    paths = [
        "2023/300/image.png",  # Year/DOY
        "2023300/image.png",  # Compact DOY
        "2023-10-27/image.png",  # Calendar
        "GOES18/FD/13/2023/300/image.png",  # GOES directory structure with DOY
        "goes18_20231027_120000_band13.png",  # GOES filename with calendar date
    ]

    # Special debug for the satellite path
    satellite_path = "goes18_20231027_120000_band13.png"
    print(f"Special debugging for satellite path: {satellite_path}")
    import re

    sat_pattern = re.compile(r"goes\d+_(\d{4})(\d{2})(\d{2})_\d{6}")
    match = sat_pattern.search(satellite_path)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        try:
            date_obj = date(year, month, day)
            print(f"  Raw match: year={year}, month={month}, day={day}")
            print(f"  Valid date: {date_obj.isoformat()}")
            print(f"  Day of year: {date_utils.date_to_doy(date_obj)}")
        except ValueError as e:
            print(f"  Error creating date: {e}")
    else:
        print("  No match")

    for path in paths:
        date_obj = date_utils.parse_satellite_path(path)
        if date_obj:
            print(f"Path: {path}")
            print(f"  Parsed date: {date_obj.strftime('%Y-%m-%d')}")
            print(f"  Day of year: {date_utils.date_to_doy(date_obj)}")
            print(
                f"  Calendar format: {date_utils.format_satellite_path(date_obj, 'calendar')}"
            )
            print(f"  DOY format: {date_utils.format_satellite_path(date_obj, 'doy')}")
            print()


def demonstrate_time_index_integration():
    """Demonstrate integration with time_index module."""
    print("\nTime Index Integration")
    print("=====================")

    # Extract timestamp from directory name
    dir_name = "GOES18/FD/13/2023/300"
    timestamp = extract_timestamp_from_directory_name(dir_name)
    if timestamp:
        print(f"Directory: {dir_name}")
        print(f"  Extracted timestamp: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Day of year: {date_utils.date_to_doy(timestamp.date())}")

        # Generate S3 key
        s3_key = to_s3_key(timestamp, SatellitePattern.GOES_18, exact_match=True)
        print(f"  S3 key: {s3_key}")

        # Generate CDN URL
        cdn_url = to_cdn_url(timestamp, SatellitePattern.GOES_18)
        print(f"  CDN URL: {cdn_url}")

    # Extract timestamp and satellite from filename
    filename = "2023300120000_GOES18-ABI-FD-13-5424x5424.jpg"
    ts, satellite = extract_timestamp_and_satellite(filename)
    if ts and satellite:
        print(f"\nFilename: {filename}")
        print(f"  Extracted timestamp: {ts.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Satellite: {satellite}")
        print(f"  Day of year: {date_utils.date_to_doy(ts.date())}")


if __name__ == "__main__":
    demonstrate_date_conversion()
    demonstrate_time_index_integration()
