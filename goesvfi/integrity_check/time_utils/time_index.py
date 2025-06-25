"""Main TimeIndex class that provides a unified interface for GOES time utilities."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from .constants import BAND, DEFAULT_CDN_RESOLUTION, RADC_MINUTES, RADF_MINUTES, RADM_MINUTES, RECENT_WINDOW_DAYS
from .patterns import S3_BUCKETS, SATELLITE_CODES, SATELLITE_SHORT_NAMES, SatellitePattern
from .s3_utils import S3KeyGenerator, filter_s3_keys_by_band
from .scanner import DirectoryScanner
from .timestamp import TimestampExtractor, TimestampGenerator


class TimeIndex:
    """Enhanced utilities for GOES-16/18 Band 13 timestamp management.

    This class provides static methods for working with GOES satellite imagery
    from various sources including CDN and AWS S3.
    """

    # Constants
    BAND = BAND
    SATELLITE_CODES = SATELLITE_CODES
    SATELLITE_NAMES = SATELLITE_SHORT_NAMES
    S3_BUCKETS = S3_BUCKETS
    CDN_RES = DEFAULT_CDN_RESOLUTION
    RECENT_WINDOW_DAYS = RECENT_WINDOW_DAYS

    # Standard GOES imaging intervals (minutes past the hour) for each product type
    STANDARD_INTERVALS = {
        "RadF": RADF_MINUTES,  # Full Disk: [0, 10, 20, 30, 40, 50]
        "RadC": RADC_MINUTES,  # CONUS: [1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56]
        "RadM": RADM_MINUTES,  # Mesoscale: [0-59] (every minute)
    }

    @staticmethod
    def to_cdn_url(
        ts: datetime, satellite: SatellitePattern, resolution: Optional[str] = None
    ) -> str:
        """
        Generate a CDN URL for the given timestamp and satellite.

        Args:
            ts: Datetime object for the image
            satellite: Satellite pattern (GOES_16 or GOES_18)
            resolution: Optional override for resolution (default is CDN_RES)

        Returns:
            Full CDN URL string
        """
        return S3KeyGenerator.to_cdn_url(ts, satellite, resolution or TimeIndex.CDN_RES)

    @staticmethod
    def to_s3_key(
        ts: datetime,
        satellite: SatellitePattern,
        product_type: str = "RadC",
        band: int = 13,
        exact_match: bool = False,
    ) -> str:
        """
        Generate an S3 key for the given timestamp, satellite, and product type.

        Args:
            ts: Datetime object for the image
            satellite: Satellite pattern (GOES_16 or GOES_18)
            product_type: Product type ("RadF" for Full Disk, "RadC" for CONUS, "RadM" for Mesoscale)
            band: Band number (1-16, default 13 for Clean IR)
            exact_match: If True, return a concrete filename without wildcards
            (used for testing where wildcards cause issues)

        Returns:
            S3 key string (not including bucket name)
        """
        return S3KeyGenerator.to_s3_key(ts, satellite, product_type, band, exact_match)

    @staticmethod
    def get_s3_bucket(satellite: SatellitePattern) -> str:
        """
        Get the S3 bucket name for the given satellite.

        Args:
            satellite: Satellite pattern (GOES_16 or GOES_18)

        Returns:
            S3 bucket name
        """
        return S3KeyGenerator.get_s3_bucket(satellite)

    @staticmethod
    def generate_local_path(
        ts: datetime, satellite: SatellitePattern, base_dir: Path
    ) -> Path:
        """
        Generate a local path for storing the image.

        Args:
            ts: Datetime object for the image
            satellite: Satellite pattern (GOES_16 or GOES_18)
            base_dir: Base directory for storage

        Returns:
            Path object for the local file
        """
        return S3KeyGenerator.generate_local_path(ts, satellite, base_dir)

    @staticmethod
    def to_local_path(ts: datetime, satellite: SatellitePattern) -> Path:
        """
        Generate a simplified local path for storing the image.

        Args:
            ts: Datetime object for the image
            satellite: Satellite pattern (GOES_16 or GOES_18)

        Returns:
            Path object for the local file
        """
        return S3KeyGenerator.to_local_path(ts, satellite)

    @staticmethod
    def ts_from_filename(
        filename: str,
    ) -> Tuple[Optional[datetime], Optional[SatellitePattern]]:
        """
        Extract a timestamp and satellite from a filename.

        Args:
            filename: Filename to parse

        Returns:
            Tuple of (datetime object, satellite pattern) if successful, (None, None) otherwise
        """
        return TimestampExtractor.extract_timestamp_and_satellite(filename)

    @staticmethod
    def ts_from_directory_name(dirname: str) -> Optional[datetime]:
        """
        Extract a timestamp from a directory name with format YYYY-MM-DD_HH-MM-SS.

        Args:
            dirname: Directory name to parse (e.g., "2024-12-21_18-00-22")

        Returns:
            datetime object if extraction succeeded, None otherwise
        """
        return TimestampExtractor.extract_timestamp_from_directory_name(dirname)

    @staticmethod
    def is_cdn_available(ts: datetime) -> bool:
        """
        Check if a timestamp is within the recent window (for CDN).

        Args:
            ts: Datetime object to check

        Returns:
            True if within recent window, False otherwise
        """
        return TimestampGenerator.is_recent(ts)

    @staticmethod
    def find_nearest_intervals(
        ts: datetime, product_type: str = "RadF"
    ) -> List[datetime]:
        """
        Find the nearest standard GOES imagery intervals for a given timestamp and product type.

        GOES satellite imagery is typically available at fixed intervals, not at
        arbitrary timestamps. This function finds the nearest standard intervals
        for the given product type's scanning schedule.

        Args:
            ts: Input timestamp
            product_type: Product type ("RadF" for Full Disk, "RadC" for CONUS, "RadM" for Mesoscale)

        Returns:
            List of nearest standard interval timestamps (typically 2)
        """
        return S3KeyGenerator.find_nearest_goes_intervals(ts, product_type)

    @staticmethod
    def find_date_range_in_directory(
        directory: Path, satellite: SatellitePattern
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Find the earliest and latest timestamps in the directory.

        Args:
            directory: The directory to scan
            satellite: The satellite pattern to use for matching

        Returns:
            Tuple of (earliest datetime, latest datetime), or (None, None) if no matches
        """
        return DirectoryScanner.find_date_range_in_directory(directory, satellite)

    @staticmethod
    def scan_directory_for_timestamps(
        directory: Path,
        pattern: SatellitePattern,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[datetime]:
        """
        Scan a directory for files matching the timestamp pattern.

        Args:
            directory: The directory to scan
            pattern: The satellite pattern to use for matching
            start_time: Optional start time to filter results
            end_time: Optional end time to filter results

        Returns:
            A list of datetime objects extracted from filenames
        """
        return DirectoryScanner.scan_directory_for_timestamps(directory, pattern, start_time, end_time)

    @staticmethod
    def filter_s3_keys_by_band(keys: List[str], target_band: int = 13) -> List[str]:
        """
        Filter a list of S3 keys to include only those for the specified band.

        When using wildcards in S3 queries, we may get back files for multiple bands.
        This function helps filter the results to only include the band we want.

        Args:
            keys: List of S3 keys (filenames)
            target_band: The band number to filter for (1-16, default 13 for Clean IR)

        Returns:
            Filtered list of S3 keys
        """
        return filter_s3_keys_by_band(keys, target_band)