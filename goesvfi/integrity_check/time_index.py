"""Timestamp pattern recognition and utilities for satellite imagery.

This module provides functions for working with timestamp patterns in filenames,
generating expected timestamp sequences, and detecting time intervals.
It also provides utilities for working with GOES satellite imagery from various sources.

NOTE: This file now serves as a backward compatibility layer. The actual implementations
have been refactored into the time_utils package for better modularity.
"""

# Import everything from the new modules to maintain backward compatibility
from .time_utils import (  # Constants; Classes and enums; Functions
    BAND,
    CDN_RESOLUTIONS,
    DEFAULT_CDN_RESOLUTION,
    RADC_MINUTES,
    RADF_MINUTES,
    RADM_MINUTES,
    RECENT_WINDOW_DAYS,
    START_SECONDS,
    DirectoryScanner,
    S3KeyGenerator,
    SatellitePattern,
    TimeIndex,
    TimestampExtractor,
    TimestampFormatter,
    TimestampGenerator,
    filter_s3_keys_by_band,
    get_satellite_info,
)
from .time_utils.constants import _USE_EXACT_MATCH_IN_TEST
from .time_utils.patterns import (
    BAND_PATTERN,
    COMPILED_GOES_PATTERNS,
    COMPILED_PATTERNS,
    GOES_FILENAME_PATTERNS,
    PATTERN_MAPPING,
    S3_BUCKETS,
    SATELLITE_CODES,
    SATELLITE_NAMES,
    SATELLITE_SHORT_NAMES,
)

# Re-export all the legacy functions that were in the original file
# These are now wrappers around the new modular implementations

# Timestamp extraction functions
extract_timestamp = TimestampExtractor.extract_timestamp
extract_timestamp_and_satellite = TimestampExtractor.extract_timestamp_and_satellite
extract_timestamp_from_directory_name = (
    TimestampExtractor.extract_timestamp_from_directory_name
)

# Timestamp formatting functions
format_timestamp = TimestampFormatter.format_timestamp
get_filename_pattern = TimestampFormatter.get_filename_pattern
generate_expected_filename = TimestampFormatter.generate_expected_filename

# Timestamp generation functions
generate_timestamp_sequence = TimestampGenerator.generate_timestamp_sequence
detect_interval = TimestampGenerator.detect_interval
is_recent = TimestampGenerator.is_recent

# S3 key generation functions
to_cdn_url = S3KeyGenerator.to_cdn_url
to_s3_key = S3KeyGenerator.to_s3_key
get_s3_bucket = S3KeyGenerator.get_s3_bucket
generate_local_path = S3KeyGenerator.generate_local_path
to_local_path = S3KeyGenerator.to_local_path
find_nearest_goes_intervals = S3KeyGenerator.find_nearest_goes_intervals

# Directory scanning functions
scan_directory_for_timestamps = DirectoryScanner.scan_directory_for_timestamps
find_date_range_in_directory = DirectoryScanner.find_date_range_in_directory

# Re-export everything so imports work as before
__all__ = [
    # Constants
    "BAND",
    "CDN_RESOLUTIONS",
    "DEFAULT_CDN_RESOLUTION",
    "RADF_MINUTES",
    "RADC_MINUTES",
    "RADM_MINUTES",
    "RECENT_WINDOW_DAYS",
    "START_SECONDS",
    "_USE_EXACT_MATCH_IN_TEST",
    # Pattern dictionaries
    "PATTERN_MAPPING",
    "GOES_FILENAME_PATTERNS",
    "COMPILED_PATTERNS",
    "COMPILED_GOES_PATTERNS",
    "SATELLITE_NAMES",
    "SATELLITE_SHORT_NAMES",
    "S3_BUCKETS",
    "SATELLITE_CODES",
    "BAND_PATTERN",
    # Classes and enums
    "SatellitePattern",
    "TimeIndex",
    # Functions
    "extract_timestamp",
    "extract_timestamp_and_satellite",
    "generate_timestamp_sequence",
    "detect_interval",
    "get_filename_pattern",
    "format_timestamp",
    "generate_expected_filename",
    "extract_timestamp_from_directory_name",
    "scan_directory_for_timestamps",
    "find_date_range_in_directory",
    "to_cdn_url",
    "to_s3_key",
    "get_s3_bucket",
    "generate_local_path",
    "to_local_path",
    "is_recent",
    "filter_s3_keys_by_band",
    "find_nearest_goes_intervals",
    "get_satellite_info",
]
