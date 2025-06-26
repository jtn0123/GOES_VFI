"""Constants for GOES satellite time utilities."""

from typing import Dict, List

# Constants for GOES imagery
BAND: int = 13  # Hard-coded for Band 13 (Clean IR)
CDN_RESOLUTIONS: List[str] = [
    "339x339",
    "678x678",
    "1808x1808",
    "5424x5424",
    "10848x10848",
]
DEFAULT_CDN_RESOLUTION: str = "5424x5424"
RECENT_WINDOW_DAYS: int = 7  # Window for CDN vs S3 decision

# GOES ABI Scanning schedules (Mode 6) - minutes of the hour when scans start
# These are the actual scanning schedules based on NOAA documentation
RADF_MINUTES: List[int] = [0, 10, 20, 30, 40, 50]  # Full Disk scans, start sec ≈ 0.3
RADC_MINUTES: List[int] = [
    1,
    6,
    11,
    16,
    21,
    26,
    31,
    36,
    41,
    46,
    51,
    56,
]  # CONUS scans, start sec ≈ 19.1
RADM_MINUTES: List[int] = list(range(60))  # Mesoscale scans, every minute, start sec ≈ 24.4

# Approximate start seconds for each product type
START_SECONDS: Dict[str, int] = {"RadF": 0, "RadC": 19, "RadM": 24}

# Control variable for testing wildcard behavior in time_index.to_s3_key()
# Set to False in tests to allow testing wildcard key functionality
_USE_EXACT_MATCH_IN_TEST: bool = True
