"""Date utilities for GOES VFI.

This module provides date conversion utilities for working with satellite imagery,
particularly for converting between calendar dates and day of year (DOY) formats.
"""

import datetime
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
    return (datetime.datetime(year, 1, 1) + datetime.timedelta(days=doy - 1)).date()


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


def _try_hyphenated_date_pattern(path_str: str) -> Optional[datetime.date]:
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


def extract_date_from_path(path: Union[str, Path]) -> Optional[datetime.date]:
    """
    Extract a date from a file or directory path using various patterns.

    This function tries multiple patterns to extract a date from a path:
    1. YYYY-MM-DD (hyphenated date)
    2. YYYY/DDD (year and day of year with slash)
    3. Satellite filename pattern (e.g., goes18_YYYYMMDD_HHMMSS)

    Args:
        path: File or directory path (string or Path object)

    Returns:
        datetime.date object if a valid date is found, None otherwise
    """
    # Convert to string if Path object
    path_str = str(path)

    # Try each pattern in order
    patterns = [
        _try_hyphenated_date_pattern,
        _try_year_doy_slash_pattern,
        _try_satellite_filename_pattern,
    ]

    for pattern_func in patterns:
        date = pattern_func(path_str)
        if date:
            return date

    # No valid date found
    LOGGER.debug("No valid date found in path: %s", path_str)
    return None


def format_satellite_path(date: datetime.date, format_type: str = "calendar") -> str:
    """
    Format a date for satellite data paths.

    Args:
        date: The date to format
        format_type: Type of format - "calendar", "doy", or "compact_doy"

    Returns:
        Formatted date string

    Raises:
        ValueError: If format_type is invalid
    """
    if format_type == "calendar":
        # YYYY-MM-DD format
        return date.strftime("%Y-%m-%d")
    elif format_type == "doy":
        # YYYY/DDD format
        doy = date_to_doy(date)
        return f"{date.year}/{doy:03d}"
    elif format_type == "compact_doy":
        # YYYYDDD format (no separator)
        doy = date_to_doy(date)
        return f"{date.year}{doy:03d}"
    else:
        raise ValueError(f"Invalid format_type: {format_type}")


def get_all_date_formats(date: datetime.date) -> Tuple[str, str, str]:
    """
    Get all common date formats for a given date.

    Args:
        date: The date to format

    Returns:
        Tuple of (calendar_format, doy_format, compact_doy_format)
    """
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


def parse_timestamp(timestamp_str: str) -> datetime.datetime:
    """
    Parse a timestamp string in various formats.

    Supported formats:
    - ISO format: YYYY-MM-DDTHH:MM:SS
    - Compact format: YYYYMMDDTHHMMSS
    - Space-separated: YYYY-MM-DD HH:MM:SS

    Args:
        timestamp_str: Timestamp string to parse

    Returns:
        Parsed datetime object

    Raises:
        ValueError: If the timestamp cannot be parsed
    """
    # Try different formats
    formats = [
        "%Y-%m-%dT%H:%M:%S",  # ISO format
        "%Y%m%dT%H%M%S",  # Compact format
        "%Y-%m-%d %H:%M:%S",  # Space-separated
        "%Y-%m-%d_%H-%M-%S",  # Underscore-separated
    ]

    for fmt in formats:
        try:
            return datetime.datetime.strptime(timestamp_str, fmt)
        except ValueError:
            continue

    # If none worked, raise an error
    raise ValueError(f"Could not parse timestamp: {timestamp_str}")


def format_timestamp(dt: datetime.datetime, compact: bool = False) -> str:
    """
    Format a datetime as a timestamp string.

    Args:
        dt: Datetime to format
        compact: If True, use compact format (no separators)

    Returns:
        Formatted timestamp string
    """
    if compact:
        return dt.strftime("%Y%m%dT%H%M%S")
    else:
        return dt.strftime("%Y-%m-%dT%H:%M:%S")


def get_satellite_path_components(
    path: Union[str, Path],
) -> Optional[Tuple[int, int, int]]:
    """
    Extract year, day of year, and hour from a satellite data path.

    Args:
        path: Path to analyze

    Returns:
        Tuple of (year, day_of_year, hour) if found, None otherwise
    """
    path_str = str(path)

    # Try YYYY/DDD/HH pattern
    match = re.search(r"(\d{4})[/\\](\d{3})[/\\](\d{2})", path_str)
    if match:
        year = int(match.group(1))
        doy = int(match.group(2))
        hour = int(match.group(3))
        return (year, doy, hour)

    # Try satellite filename pattern
    match = re.search(r"goes\d+_(\d{4})(\d{2})(\d{2})_(\d{2})\d{4}", path_str)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        hour = int(match.group(4))

        # Convert to day of year
        try:
            date = datetime.date(year, month, day)
            doy = date_to_doy(date)
            return (year, doy, hour)
        except ValueError:
            return None

    return None


def parse_satellite_path(path: Union[str, Path]) -> Optional[datetime.date]:
    """
    Parse a satellite data path to extract a date.

    Args:
        path: Path to parse

    Returns:
        Parsed date if successful, None otherwise
    """
    path_str = str(path)

    # Try satellite filename pattern with full timestamp
    match = re.search(r"goes\d+_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", path_str)
    if match:
        try:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            # Ignore hour, minute, second for date parsing
            return datetime.date(year, month, day)
        except ValueError:
            return None

    # Try various date patterns using existing helper functions
    # Order is important: more specific patterns first

    # Try YYYY-MM-DD pattern
    result = _try_calendar_pattern(path_str, r"(\d{4})-(\d{2})-(\d{2})", "YYYY-MM-DD")
    if result:
        return result

    # Try YYYY_MM_DD pattern
    result = _try_calendar_pattern(path_str, r"(\d{4})_(\d{2})_(\d{2})", "YYYY_MM_DD")
    if result:
        return result

    # Try YYYY/DDD pattern (with slash separator)
    result = _try_doy_pattern(path_str, r"(\d{4})/(\d{3})", "YYYY/DDD")
    if result:
        return result

    # Try ISO timestamp pattern (ignore time part)
    result = _try_timestamp_pattern(path_str, r"(\d{4})(\d{2})(\d{2})T\d{6}Z?", "ISO")
    if result:
        return result

    # Try YYYYMMDD pattern (8 digits for calendar date)
    result = _try_calendar_pattern(path_str, r"(\d{4})(\d{2})(\d{2})", "YYYYMMDD")
    if result:
        return result

    # Try YYYYDDD pattern (7 digits for day-of-year) - LAST because it can match YYYYMMDD incorrectly
    result = _try_doy_pattern(path_str, r"(\d{4})(\d{3})", "YYYYDDD")
    if result:
        return result

    return None


def _try_doy_pattern(
    path_str: str, pattern: str, pattern_name: str
) -> Optional[datetime.date]:
    """Try to parse using day-of-year pattern."""
    # For YYYYDDD pattern, check if this string was already rejected as invalid YYYYMMDD
    if pattern_name == "YYYYDDD":
        if (
            hasattr(_try_calendar_pattern, "_failed_yyyymmdd")
            and path_str in _try_calendar_pattern._failed_yyyymmdd
        ):
            LOGGER.debug(
                "Skipping %s as YYYYDDD because it failed as YYYYMMDD", path_str
            )
            return None

    match = re.search(pattern, path_str)
    if match:
        try:
            year = int(match.group(1))
            doy = int(match.group(2))
            result = doy_to_date(year, doy)
            LOGGER.debug("Found date %s using %s pattern", result, pattern_name)
            return result
        except ValueError as e:
            LOGGER.debug("Invalid date from %s pattern: %s", pattern_name, e)
    return None


def _try_calendar_pattern(
    path_str: str, pattern: str, pattern_name: str
) -> Optional[datetime.date]:
    """Try to parse using calendar date pattern."""
    match = re.search(pattern, path_str)
    if match:
        try:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            result = datetime.date(year, month, day)
            LOGGER.debug("Found date %s using %s pattern", result, pattern_name)
            return result
        except ValueError as e:
            LOGGER.debug("Invalid date from %s pattern: %s", pattern_name, e)
            # For YYYYMMDD pattern specifically, mark as invalid to prevent fallback to YYYYDDD
            if pattern_name == "YYYYMMDD":
                # Store the failed pattern to prevent YYYYDDD from trying it
                if not hasattr(_try_calendar_pattern, "_failed_yyyymmdd"):
                    _try_calendar_pattern._failed_yyyymmdd = set()
                _try_calendar_pattern._failed_yyyymmdd.add(path_str)
    return None


def _try_timestamp_pattern(
    path_str: str, pattern: str, pattern_name: str
) -> Optional[datetime.date]:
    """Try to parse using timestamp pattern (extract date part only)."""
    match = re.search(pattern, path_str)
    if match:
        try:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            result = datetime.date(year, month, day)
            LOGGER.debug("Found date %s using %s pattern", result, pattern_name)
            return result
        except ValueError as e:
            LOGGER.debug("Invalid date from %s pattern: %s", pattern_name, e)
    return None
