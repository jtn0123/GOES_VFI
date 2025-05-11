"""Date utilities for GOES VFI.

This module provides date conversion utilities for working with satellite imagery,
particularly for converting between calendar dates and day of year (DOY) formats.
"""

import datetime
import logging
import re
from pathlib import Path
from typing import Optional, Tuple, Union

from goesvfi.utils.log import get_logger

# Set up module logger
LOGGER = get_logger(__name__)


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


# Helper functions for date parsing


def _try_create_date_from_year_month_day(
    year: int, month: int, day: int, pattern_name: str
) -> Optional[datetime.date]:
    """
    Try to create a date from year, month, and day components.

    Args:
        year: Year value
        month: Month value
        day: Day value
        pattern_name: Name of the pattern (for logging)

    Returns:
        datetime.date if valid, None otherwise
    """
    try:
        date = datetime.date(year, month, day)
        LOGGER.debug("Found date %s using %s pattern", date, pattern_name)
        return date
    except ValueError as e:
        LOGGER.debug(
            "Invalid date from %s pattern: %s-%s-%s (%s)",
            pattern_name,
            year,
            month,
            day,
            e,
        )
        return None


def _try_create_date_from_year_doy(
    year: int, doy: int, pattern_name: str
) -> Optional[datetime.date]:
    """
    Try to create a date from year and day-of-year components.

    Args:
        year: Year value
        doy: Day of year value
        pattern_name: Name of the pattern (for logging)

    Returns:
        datetime.date if valid, None otherwise
    """
    try:
        date = doy_to_date(year, doy)
        LOGGER.debug("Found date %s using %s pattern", date, pattern_name)
        return date
    except ValueError as e:
        LOGGER.debug(
            "Invalid date from %s pattern: %s/%s (%s)", pattern_name, year, doy, e
        )
        return None


def _try_satellite_filename_pattern(path_str: str) -> Optional[datetime.date]:
    """
    Try to parse a date using the satellite filename pattern.
    Example: goes18_20231027_120000_band13.png

    Args:
        path_str: Path string to parse

    Returns:
        datetime.date if pattern matches and date is valid, None otherwise
    """
    sat_pattern = re.search(r"goes\d+_(\d{4})(\d{2})(\d{2})_\d{6}", path_str)
    if not sat_pattern:
        return None

    year = int(sat_pattern.group(1))
    month = int(sat_pattern.group(2))
    day = int(sat_pattern.group(3))
    return _try_create_date_from_year_month_day(year, month, day, "satellite filename")


def _try_year_doy_slash_pattern(path_str: str) -> Optional[datetime.date]:
    """
    Try to parse a date using the YYYY/DDD pattern.
    Example: 2023/123

    Args:
        path_str: Path string to parse

    Returns:
        datetime.date if pattern matches and date is valid, None otherwise
    """
    doy_match = re.search(r"(\d{4})[/\\](\d{3})", path_str)
    if not doy_match:
        return None

    year = int(doy_match.group(1))
    doy = int(doy_match.group(2))
    return _try_create_date_from_year_doy(year, doy, "YYYY/DDD")


def _try_compact_doy_pattern(path_str: str) -> Optional[datetime.date]:
    """
    Try to parse a date using the YYYYDDD pattern.
    Example: 2023123

    Args:
        path_str: Path string to parse

    Returns:
        datetime.date if pattern matches and date is valid, None otherwise
    """
    doy_match = re.search(r"(\d{4})(\d{3})", path_str)
    if not doy_match:
        return None

    year = int(doy_match.group(1))
    doy = int(doy_match.group(2))
    return _try_create_date_from_year_doy(year, doy, "YYYYDDD")


def _try_hyphen_date_pattern(path_str: str) -> Optional[datetime.date]:
    """
    Try to parse a date using the YYYY-MM-DD pattern.
    Example: 2023-10-27

    Args:
        path_str: Path string to parse

    Returns:
        datetime.date if pattern matches and date is valid, None otherwise
    """
    date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", path_str)
    if not date_match:
        return None

    year = int(date_match.group(1))
    month = int(date_match.group(2))
    day = int(date_match.group(3))
    return _try_create_date_from_year_month_day(year, month, day, "YYYY-MM-DD")


def _try_underscore_date_pattern(path_str: str) -> Optional[datetime.date]:
    """
    Try to parse a date using the YYYY_MM_DD pattern.
    Example: 2023_10_27

    Args:
        path_str: Path string to parse

    Returns:
        datetime.date if pattern matches and date is valid, None otherwise
    """
    date_match = re.search(r"(\d{4})_(\d{2})_(\d{2})", path_str)
    if not date_match:
        return None

    year = int(date_match.group(1))
    month = int(date_match.group(2))
    day = int(date_match.group(3))
    return _try_create_date_from_year_month_day(year, month, day, "YYYY_MM_DD")


def _try_timestamp_pattern(path_str: str) -> Optional[datetime.date]:
    """
    Try to parse a date using the timestamp pattern (YYYYMMDDTHHMMSSZ).
    Example: 20231027T120000Z

    Args:
        path_str: Path string to parse

    Returns:
        datetime.date if pattern matches and date is valid, None otherwise
    """
    date_match = re.search(r"(\d{4})(\d{2})(\d{2})T", path_str)
    if not date_match:
        return None

    year = int(date_match.group(1))
    month = int(date_match.group(2))
    day = int(date_match.group(3))
    return _try_create_date_from_year_month_day(year, month, day, "timestamp")


def _try_compact_date_pattern(path_str: str) -> Optional[datetime.date]:
    """
    Try to parse a date using the YYYYMMDD pattern.
    Example: 20231027

    Args:
        path_str: Path string to parse

    Returns:
        datetime.date if pattern matches and date is valid, None otherwise
    """
    date_match = re.search(r"(\d{4})(\d{2})(\d{2})", path_str)
    if not date_match or len(date_match.group(0)) != 8:
        # Ensure we matched an 8-digit number exactly
        return None

    year = int(date_match.group(1))
    month = int(date_match.group(2))
    day = int(date_match.group(3))
    return _try_create_date_from_year_month_day(year, month, day, "YYYYMMDD")


def parse_satellite_path(path: Union[str, Path]) -> Optional[datetime.date]:
    """Extract date from a satellite imagery path.

    This function attempts to parse various common satellite imagery path formats
    including both calendar date formats (YYYY-MM-DD) and day of year formats (YYYYDDD).

    The function tries different date patterns in order from most specific to most general.

    Args:
        path: The path to parse.

    Returns:
        Optional[datetime.date]: The extracted date, or None if no date could be parsed.
    """
    path_str = str(path)
    LOGGER.debug("Attempting to parse date from path: %s", path_str)

    # Try all patterns in order from most specific to most general
    parsers = [
        _try_satellite_filename_pattern,  # goes18_20231027_120000
        _try_year_doy_slash_pattern,  # 2023/123
        _try_compact_doy_pattern,  # 2023123
        _try_hyphen_date_pattern,  # 2023-10-27
        _try_underscore_date_pattern,  # 2023_10_27
        _try_timestamp_pattern,  # 20231027T120000Z
        _try_compact_date_pattern,  # 20231027 (most general, comes last)
    ]

    for parser in parsers:
        date = parser(path_str)
        if date is not None:
            return date

    LOGGER.debug("No valid date pattern found in path: %s", path_str)
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
    LOGGER.debug("Formatting date %s with format type '%s'", date, format_type)

    if format_type == "calendar":
        result = date.strftime("%Y-%m-%d")
        LOGGER.debug("Formatted as calendar date: %s", result)
        return result
    elif format_type == "doy":
        doy = date_to_doy(date)
        result = f"{date.year}/{doy:03d}"
        LOGGER.debug("Formatted as DOY date: %s", result)
        return result
    elif format_type == "compact_doy":
        doy = date_to_doy(date)
        result = f"{date.year}{doy:03d}"
        LOGGER.debug("Formatted as compact DOY date: %s", result)
        return result
    else:
        LOGGER.error("Invalid format_type: %s", format_type)
        raise ValueError(f"Invalid format_type: {format_type}")


def get_satellite_path_components(date: datetime.date) -> Tuple[str, str, str]:
    """Get all common satellite path formats for a date.

    Args:
        date: The date to format.

    Returns:
        Tuple[str, str, str]: The formatted date in (calendar, doy, compact_doy) formats.
    """
    LOGGER.debug("Getting all satellite path components for date: %s", date)

    calendar_format = format_satellite_path(date, "calendar")
    doy_format = format_satellite_path(date, "doy")
    compact_doy_format = format_satellite_path(date, "compact_doy")

    LOGGER.debug(
        "Generated all formats: calendar=%s, doy=%s, compact_doy=%s",
        calendar_format,
        doy_format,
        compact_doy_format,
    )

    return (calendar_format, doy_format, compact_doy_format)
