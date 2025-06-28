"""Time utilities package for GOES satellite imagery processing.

This package provides modular components for handling timestamps, satellite patterns,
S3 operations, and file scanning for GOES satellite data.
"""

from .constants import (
    BAND,
    CDN_RESOLUTIONS,
    DEFAULT_CDN_RESOLUTION,
    RADC_MINUTES,
    RADF_MINUTES,
    RADM_MINUTES,
    RECENT_WINDOW_DAYS,
    START_SECONDS,
)
from .patterns import SatellitePattern, get_satellite_info
from .s3_utils import S3KeyGenerator, filter_s3_keys_by_band
from .scanner import DirectoryScanner
from .time_index import TimeIndex
from .timestamp import TimestampExtractor, TimestampFormatter, TimestampGenerator

__all__ = [
    # Constants
    "BAND",
    "CDN_RESOLUTIONS",
    "DEFAULT_CDN_RESOLUTION",
    "RADC_MINUTES",
    "RADF_MINUTES",
    "RADM_MINUTES",
    "RECENT_WINDOW_DAYS",
    "START_SECONDS",
    "DirectoryScanner",
    "S3KeyGenerator",
    # Classes and functions
    "SatellitePattern",
    "TimeIndex",
    "TimestampExtractor",
    "TimestampFormatter",
    "TimestampGenerator",
    "filter_s3_keys_by_band",
    "get_satellite_info",
]
