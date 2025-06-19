# \!/usr/bin/env python3
"""Fix all docstring issues in time_index_refactored.py"""


def fix_all_docstrings():
    """Fix all the malformed docstrings."""
    file_path = "goesvfi/integrity_check/time_index_refactored.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Fix _try_primary_datetime_patterns
    content = content.replace(
        '''def _try_primary_datetime_patterns(dirname: str) -> Optional[datetime]:
        """Try to parse directory name using the primary datetime patterns.

    Args:
        dirname: Directory name to parse
    """

    Returns:
        datetime object if successful, None otherwise''',
        '''def _try_primary_datetime_patterns(dirname: str) -> Optional[datetime]:
    """Try to parse directory name using the primary datetime patterns.

    Args:
        dirname: Directory name to parse

    Returns:
        datetime object if successful, None otherwise
    """''',
    )

    # Fix _try_satellite_specific_patterns
    content = content.replace(
        '''def _try_satellite_specific_patterns(dirname: str) -> Optional[datetime]:
        """Try to parse directory name using satellite-specific patterns.

    Args:
        dirname: Directory name to parse
    """

    Returns:
        datetime object if successful, None otherwise''',
        '''def _try_satellite_specific_patterns(dirname: str) -> Optional[datetime]:
    """Try to parse directory name using satellite-specific patterns.

    Args:
        dirname: Directory name to parse

    Returns:
        datetime object if successful, None otherwise
    """''',
    )

    # Fix extract_timestamp_from_directory_name
    content = content.replace(
        '''def extract_timestamp_from_directory_name(dirname: str) -> Optional[datetime]:
        """Extract a timestamp from a directory name with various formats.

    Supported formats:
    - YYYY-MM-DD_HH-MM-SS (primary format)
    - YYYYMMDD_HHMMSS
    - YYYYMMDDTHHMMSS
    - GOES18/FD/13/YYYY/DDD (where DDD is day of year)
    - SATNAME_YYYYMMDD_HHMMSS
    - YYYY/DDD (year and day of year)
    - YYYYDDD (compact year and day of year)
    """

    Args:
        dirname: Directory name to parse (e.g., "2024-12-21_18-00-22")

    Returns:
        datetime object if extraction succeeded, None otherwise''',
        '''def extract_timestamp_from_directory_name(dirname: str) -> Optional[datetime]:
    """Extract a timestamp from a directory name with various formats.

    Supported formats:
    - YYYY-MM-DD_HH-MM-SS (primary format)
    - YYYYMMDD_HHMMSS
    - YYYYMMDDTHHMMSS
    - GOES18/FD/13/YYYY/DDD (where DDD is day of year)
    - SATNAME_YYYYMMDD_HHMMSS
    - YYYY/DDD (year and day of year)
    - YYYYDDD (compact year and day of year)

    Args:
        dirname: Directory name to parse (e.g., "2024-12-21_18-00-22")

    Returns:
        datetime object if extraction succeeded, None otherwise
    """''',
    )

    # Fix _validate_directory_and_pattern
    content = content.replace(
        """) -> Tuple[bool, Optional[re.Pattern]]:
    Validate directory exists and pattern is valid.

    Args:
        directory: Directory to validate
        pattern: Satellite pattern to validate

    Returns:
        Tuple of (is_valid, compiled_pattern)""",
        ''') -> Tuple[bool, Optional[re.Pattern]]:
    """Validate directory exists and pattern is valid.

    Args:
        directory: Directory to validate
        pattern: Satellite pattern to validate

    Returns:
        Tuple of (is_valid, compiled_pattern)
    """''',
    )

    # Fix _extract_timestamp_from_file
    content = content.replace(
        """) -> Optional[datetime]:
    Extract timestamp from a file using various methods.

    Args:
        file_path: Path to the file
        pattern: Satellite pattern to use for extraction

    Returns:
        Extracted timestamp or None if not found""",
        ''') -> Optional[datetime]:
    """Extract timestamp from a file using various methods.

    Args:
        file_path: Path to the file
        pattern: Satellite pattern to use for extraction

    Returns:
        Extracted timestamp or None if not found
    """''',
    )

    # Fix _filter_timestamp_by_range
    content = content.replace(
        """) -> bool:
    Check if timestamp is within the specified time range.

    Args:
        timestamp: Timestamp to check
        start_time: Optional start of time range
        end_time: Optional end of time range

    Returns:
        True if timestamp is within range, False otherwise""",
        ''') -> bool:
    """Check if timestamp is within the specified time range.

    Args:
        timestamp: Timestamp to check
        start_time: Optional start of time range
        end_time: Optional end of time range

    Returns:
        True if timestamp is within range, False otherwise
    """''',
    )

    # Fix _scan_files_for_timestamps
    content = content.replace(
        """) -> List[datetime]:
    Scan PNG files in a directory for timestamps.

    Args:
        directory: Directory to scan
        pattern: Satellite pattern to use for matching
        start_time: Optional start time to filter results
        end_time: Optional end time to filter results

    Returns:
        List of timestamps extracted from files""",
        ''') -> List[datetime]:
    """Scan PNG files in a directory for timestamps.

    Args:
        directory: Directory to scan
        pattern: Satellite pattern to use for matching
        start_time: Optional start time to filter results
        end_time: Optional end time to filter results

    Returns:
        List of timestamps extracted from files
    """''',
    )

    # Fix _scan_subdirectories_for_timestamps
    content = content.replace(
        """) -> List[datetime]:
    Scan subdirectories for timestamps in their names.

    Args:
        directory: Directory to scan
        start_time: Optional start time to filter results
        end_time: Optional end time to filter results

    Returns:
        List of timestamps extracted from subdirectory names""",
        ''') -> List[datetime]:
    """Scan subdirectories for timestamps in their names.

    Args:
        directory: Directory to scan
        start_time: Optional start time to filter results
        end_time: Optional end time to filter results

    Returns:
        List of timestamps extracted from subdirectory names
    """''',
    )

    # Fix scan_directory_for_timestamps
    content = content.replace(
        """) -> List[datetime]:
    Scan a directory for files matching the timestamp pattern.
    Also checks directory names for timestamps in format YYYY-MM-DD_HH-MM-SS.

    Args:
        directory: The directory to scan
        pattern: The satellite pattern to use for matching
        start_time: Optional start time to filter results
        end_time: Optional end time to filter results

    Returns:
        A list of datetime objects extracted from filenames or directory names""",
        ''') -> List[datetime]:
    """Scan a directory for files matching the timestamp pattern.
    Also checks directory names for timestamps in format YYYY-MM-DD_HH-MM-SS.

    Args:
        directory: The directory to scan
        pattern: The satellite pattern to use for matching
        start_time: Optional start time to filter results
        end_time: Optional end time to filter results

    Returns:
        A list of datetime objects extracted from filenames or directory names
    """''',
    )

    # Fix _detect_test_environment
    content = content.replace(
        '''def _detect_test_environment() -> Tuple[bool, bool, bool]:
        """Detect if code is running in a test environment and which test file is calling.

    Returns:
        Tuple of (is_test_env, is_basic_test, is_remote_test)
    """''',
        '''def _detect_test_environment() -> Tuple[bool, bool, bool]:
    """Detect if code is running in a test environment and which test file is calling.

    Returns:
        Tuple of (is_test_env, is_basic_test, is_remote_test)
    """''',
    )

    # Fix _validate_product_type_and_band
    content = content.replace(
        '''def _validate_product_type_and_band(product_type: str, band: int) -> None:
        """Validate product type and band number.

    Args:
        product_type: Product type ("RadF", "RadC", "RadM")
        band: Band number (1-16)
    """

    Raises:
        ValueError: If product type or band is invalid''',
        '''def _validate_product_type_and_band(product_type: str, band: int) -> None:
    """Validate product type and band number.

    Args:
        product_type: Product type ("RadF", "RadC", "RadM")
        band: Band number (1-16)

    Raises:
        ValueError: If product type or band is invalid
    """''',
    )

    # Fix _find_nearest_valid_scan_minute
    content = content.replace(
        """) -> int:
    Find the nearest valid scan minute for the given product type.

    Args:
        original_minute: The original minute value
        scan_minutes: List of valid scan minutes for the product

    Returns:
        The nearest valid scan minute""",
        ''') -> int:
    """Find the nearest valid scan minute for the given product type.

    Args:
        original_minute: The original minute value
        scan_minutes: List of valid scan minutes for the product

    Returns:
        The nearest valid scan minute
    """''',
    )

    # Fix _get_s3_filename_pattern
    content = content.replace(
        """) -> str:
    Generate the appropriate S3 filename pattern based on test environment and match requirements.

    Args:
        satellite_code: The satellite code (e.g., "G16", "G18")
        product_type: Product type ("RadF", "RadC", "RadM")
        band_str: Formatted band number (e.g., "13")
        timestamp_components: Dictionary with year, doy, hour, minute, start_sec components
        use_exact_match: Whether to use exact matching for filename
        is_basic_test: Whether this is being called from a basic test

    Returns:
        The appropriate S3 filename pattern""",
        ''') -> str:
    """Generate the appropriate S3 filename pattern based on test environment and match requirements.

    Args:
        satellite_code: The satellite code (e.g., "G16", "G18")
        product_type: Product type ("RadF", "RadC", "RadM")
        band_str: Formatted band number (e.g., "13")
        timestamp_components: Dictionary with year, doy, hour, minute, start_sec components
        use_exact_match: Whether to use exact matching for filename
        is_basic_test: Whether this is being called from a basic test

    Returns:
        The appropriate S3 filename pattern
    """''',
    )

    # Fix to_s3_key
    content = content.replace(
        """) -> str:
    Generate an S3 key for the given timestamp, satellite, and product type.

    Args:
        ts: Datetime object for the image
        satellite: Satellite pattern (GOES_16 or GOES_18)
        product_type: Product type ("RadF" for Full Disk, "RadC" for CONUS, "RadM" for Mesoscale)
        band: Band number (1-16, default 13 for Clean IR)
        exact_match: If True, return a concrete filename without wildcards
                     (used for testing where wildcards cause issues)

    Returns:
        S3 key string (not including bucket name)""",
        ''') -> str:
    """Generate an S3 key for the given timestamp, satellite, and product type.

    Args:
        ts: Datetime object for the image
        satellite: Satellite pattern (GOES_16 or GOES_18)
        product_type: Product type ("RadF" for Full Disk, "RadC" for CONUS, "RadM" for Mesoscale)
        band: Band number (1-16, default 13 for Clean IR)
        exact_match: If True, return a concrete filename without wildcards
                     (used for testing where wildcards cause issues)

    Returns:
        S3 key string (not including bucket name)
    """''',
    )

    # Fix find_date_range_in_directory
    content = content.replace(
        """) -> Tuple[Optional[datetime], Optional[datetime]]:
    Find the earliest and latest timestamps in the directory.

    Args:
        directory: The directory to scan
        pattern: The satellite pattern to use for matching

    Returns:
        Tuple of (earliest datetime, latest datetime), or (None, None) if no matches""",
        ''') -> Tuple[Optional[datetime], Optional[datetime]]:
    """Find the earliest and latest timestamps in the directory.

    Args:
        directory: The directory to scan
        pattern: The satellite pattern to use for matching

    Returns:
        Tuple of (earliest datetime, latest datetime), or (None, None) if no matches
    """''',
    )

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed all docstrings in {file_path}")


if __name__ == "__main__":
    fix_all_docstrings()
