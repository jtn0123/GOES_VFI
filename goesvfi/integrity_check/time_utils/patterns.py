"""Satellite pattern definitions and utilities."""

import re
from enum import Enum, auto
from typing import Dict, Optional, Pattern

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class SatellitePattern(Enum):
    """Enumeration of supported satellite name and timestamp patterns."""

    GOES_16 = auto()  # GOES-16 (GOES-East)
    GOES_17 = auto()  # GOES-17 (GOES-West)
    GOES_18 = auto()  # GOES-18 (New GOES-West)
    GENERIC = auto()  # Generic timestamp pattern


# Mapping of satellite patterns to regex patterns for extraction
PATTERN_MAPPING: Dict[SatellitePattern, str] = {
    SatellitePattern.GOES_16: r"(?:_G16_|G16_13_)(\d{8}T\d{6})Z\.png$",
    SatellitePattern.GOES_17: r"(?:_G17_|G17_13_)(\d{8}T\d{6})Z\.png$",
    SatellitePattern.GOES_18: r"(?:_G18_|G18_13_)(\d{8}T\d{6})Z\.png$",
    SatellitePattern.GENERIC: r"_(\d{8}T\d{6})Z\.png$",
}

# Additional patterns for GOES ABI filenames (CDN/S3)
GOES_FILENAME_PATTERNS: Dict[SatellitePattern, str] = {
    SatellitePattern.GOES_16: r"(\d{4})(\d{3})(\d{2})(\d{2})(?:\d{2})?_GOES16-ABI-FD-13",
    SatellitePattern.GOES_18: r"(\d{4})(\d{3})(\d{2})(\d{2})(?:\d{2})?_GOES18-ABI-FD-13",
}

# Compiled regex patterns for faster matching
COMPILED_PATTERNS: Dict[SatellitePattern, Pattern[str]] = {
    sat: re.compile(pattern) for sat, pattern in PATTERN_MAPPING.items()
}

COMPILED_GOES_PATTERNS: Dict[SatellitePattern, Pattern[str]] = {
    sat: re.compile(pattern) for sat, pattern in GOES_FILENAME_PATTERNS.items()
}

# Mapping of satellites to their friendly names for UI display
SATELLITE_NAMES: Dict[SatellitePattern, str] = {
    SatellitePattern.GOES_16: "GOES-16 (East)",
    SatellitePattern.GOES_17: "GOES-17 (West)",
    SatellitePattern.GOES_18: "GOES-18 (West)",
    SatellitePattern.GENERIC: "Generic Pattern",
}

# Mapping of satellites to their short names
SATELLITE_SHORT_NAMES: Dict[SatellitePattern, str] = {
    SatellitePattern.GOES_16: "GOES16",
    SatellitePattern.GOES_17: "GOES17",
    SatellitePattern.GOES_18: "GOES18",
}

# Mapping of satellites to their AWS S3 bucket names
S3_BUCKETS: Dict[SatellitePattern, str] = {
    SatellitePattern.GOES_16: "noaa-goes16",
    SatellitePattern.GOES_18: "noaa-goes18",
}

# Mapping of satellites to their S3 file pattern codes
SATELLITE_CODES: Dict[SatellitePattern, str] = {
    SatellitePattern.GOES_16: "G16",
    SatellitePattern.GOES_18: "G18",
}

# Regular expression for extracting band number from filenames
BAND_PATTERN: re.Pattern[str] = re.compile(r"ABI-L1b-(?:RadF|RadC|RadM)-M\d+C(\d+)_")


def get_satellite_info(satellite: SatellitePattern) -> Dict[str, Optional[str]]:
    """Get all information for a satellite pattern.

    Args:
        satellite: The satellite pattern

    Returns:
        Dictionary with keys: name, short_name, s3_bucket, code
    """
    return {
        "name": SATELLITE_NAMES.get(satellite),
        "short_name": SATELLITE_SHORT_NAMES.get(satellite),
        "s3_bucket": S3_BUCKETS.get(satellite),
        "code": SATELLITE_CODES.get(satellite),
    }
