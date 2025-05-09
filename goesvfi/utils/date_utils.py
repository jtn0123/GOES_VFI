"""Date utilities for GOES VFI.

This module provides date conversion utilities for working with satellite imagery,
particularly for converting between calendar dates and day of year (DOY) formats.
"""

import datetime
import re
from pathlib import Path
from typing import Optional, Tuple, Union


def date_to_doy(date: datetime.date) -> int:
    """Convert a date to day of year.

    Args:
        date: The date to convert.

    Returns:
        int: The day of year (1-366).
    """
    return date.timetuple().tm_yday


def doy_to_date(year: int, doy: int) -> datetime.date:
    """Convert a year and day of year to a date.

    Args:
        year: The year.
        doy: The day of year (1-366).

    Returns:
        datetime.date: The corresponding date.

    Raises:
        ValueError: If the day of year is invalid for the given year.
    """
    if doy < 1 or doy > 366:
        raise ValueError(f"Day of year must be between 1 and 366, got {doy}")
    
    # Check if it's a leap year and doy is 366
    is_leap_year = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
    if doy == 366 and not is_leap_year:
        raise ValueError(f"Day of year 366 is invalid for non-leap year {year}")
    
    # Create the date
    return datetime.datetime(year, 1, 1) + datetime.timedelta(days=doy - 1)


def parse_satellite_path(path: Union[str, Path]) -> Optional[datetime.date]:
    """Extract date from a satellite imagery path.

    This function attempts to parse various common satellite imagery path formats
    including both calendar date formats (YYYY-MM-DD) and day of year formats (YYYYDDD).

    Args:
        path: The path to parse.

    Returns:
        Optional[datetime.date]: The extracted date, or None if no date could be parsed.
    """
    path_str = str(path)
    
    # Order of patterns is important - more specific patterns should come first
    
    # 1. Specific pattern for satellite file formats like goes18_20231027_120000_band13.png
    sat_pattern = re.search(r'goes\d+_(\d{4})(\d{2})(\d{2})_\d{6}', path_str)
    if sat_pattern:
        year = int(sat_pattern.group(1))
        month = int(sat_pattern.group(2))
        day = int(sat_pattern.group(3))
        try:
            return datetime.date(year, month, day)
        except ValueError:
            pass
    
    # 2. Try YYYY/DDD format (year/day of year)
    doy_match = re.search(r'(\d{4})[/\\](\d{3})', path_str)
    if doy_match:
        year = int(doy_match.group(1))
        doy = int(doy_match.group(2))
        try:
            return doy_to_date(year, doy)
        except ValueError:
            pass
    
    # 3. Try YYYYDDD format (year + day of year)
    doy_match = re.search(r'(\d{4})(\d{3})', path_str)
    if doy_match:
        year = int(doy_match.group(1))
        doy = int(doy_match.group(2))
        try:
            return doy_to_date(year, doy)
        except ValueError:
            pass
    
    # 4. Try YYYY-MM-DD format
    date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', path_str)
    if date_match:
        year = int(date_match.group(1))
        month = int(date_match.group(2))
        day = int(date_match.group(3))
        try:
            return datetime.date(year, month, day)
        except ValueError:
            pass
    
    # 5. Try YYYY_MM_DD format
    date_match = re.search(r'(\d{4})_(\d{2})_(\d{2})', path_str)
    if date_match:
        year = int(date_match.group(1))
        month = int(date_match.group(2))
        day = int(date_match.group(3))
        try:
            return datetime.date(year, month, day)
        except ValueError:
            pass
    
    # 6. Try date in timestamp format (YYYYMMDDTHHMMSSZ)
    date_match = re.search(r'(\d{4})(\d{2})(\d{2})T', path_str)
    if date_match:
        year = int(date_match.group(1))
        month = int(date_match.group(2))
        day = int(date_match.group(3))
        try:
            return datetime.date(year, month, day)
        except ValueError:
            pass
    
    # 7. Try YYYYMMDD format (most general, so it comes last to avoid mismatches)
    date_match = re.search(r'(\d{4})(\d{2})(\d{2})', path_str)
    if date_match and len(date_match.group(0)) == 8:  # Ensure we matched an 8-digit number
        year = int(date_match.group(1))
        month = int(date_match.group(2))
        day = int(date_match.group(3))
        try:
            return datetime.date(year, month, day)
        except ValueError:
            pass
    
    return None


def format_satellite_path(date: datetime.date, format_type: str = "calendar") -> str:
    """Format a date for use in satellite imagery paths.

    Args:
        date: The date to format.
        format_type: The type of format to use:
            - "calendar": YYYY-MM-DD
            - "doy": YYYY/DDD (year/day of year)
            - "compact_doy": YYYYDDD (year + day of year)

    Returns:
        str: The formatted date.

    Raises:
        ValueError: If an invalid format_type is specified.
    """
    if format_type == "calendar":
        return date.strftime("%Y-%m-%d")
    elif format_type == "doy":
        doy = date_to_doy(date)
        return f"{date.year}/{doy:03d}"
    elif format_type == "compact_doy":
        doy = date_to_doy(date)
        return f"{date.year}{doy:03d}"
    else:
        raise ValueError(f"Invalid format_type: {format_type}")


def get_satellite_path_components(date: datetime.date) -> Tuple[str, str, str]:
    """Get all common satellite path formats for a date.

    Args:
        date: The date to format.

    Returns:
        Tuple[str, str, str]: The formatted date in (calendar, doy, compact_doy) formats.
    """
    return (
        format_satellite_path(date, "calendar"),
        format_satellite_path(date, "doy"),
        format_satellite_path(date, "compact_doy")
    )