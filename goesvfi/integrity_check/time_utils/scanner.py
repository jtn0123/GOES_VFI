"""Directory scanning utilities for timestamp extraction."""

from datetime import datetime
from pathlib import Path

from goesvfi.utils import log

from .patterns import COMPILED_PATTERNS, SatellitePattern
from .timestamp import TimestampExtractor

LOGGER = log.get_logger(__name__)


class DirectoryScanner:
    """Scan directories for GOES satellite imagery files and extract timestamps."""

    @classmethod
    def scan_directory_for_timestamps(
        cls,
        directory: Path,
        pattern: SatellitePattern,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[datetime]:
        """Scan a directory for files matching the timestamp pattern.
        Also checks directory names for timestamps in format YYYY-MM-DD_HH-MM-SS.

        Args:
            directory: The directory to scan
            pattern: The satellite pattern to use for matching
            start_time: Optional start time to filter results
            end_time: Optional end time to filter results

        Returns:
            A list of datetime objects extracted from filenames or directory names
        """
        if not directory.exists() or not directory.is_dir():
            LOGGER.error("Directory does not exist or is not a directory: %s", directory)
            return []

        # Compile regex pattern for files
        compiled_pattern = COMPILED_PATTERNS.get(pattern)
        if not compiled_pattern:
            LOGGER.error("Unknown satellite pattern: %s", pattern)
            return []

        # Extract timestamps from PNG files
        timestamps = cls._extract_timestamps_from_files(directory, pattern, start_time, end_time)

        # If no timestamps found, try subdirectories
        if not timestamps:
            timestamps = cls._extract_timestamps_from_subdirs(directory, start_time, end_time)

        LOGGER.info("Found %s timestamps in %s", len(timestamps), directory)
        return sorted(timestamps)

    @classmethod
    def _extract_timestamps_from_files(
        cls,
        directory: Path,
        pattern: SatellitePattern,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> list[datetime]:
        """Extract timestamps from PNG files in directory."""
        png_files = list(directory.glob("**/*.png"))
        LOGGER.info("Found %s PNG files in %s", len(png_files), directory)

        timestamps = []
        extractor = TimestampExtractor()

        for file_path in png_files:
            timestamp = cls._extract_timestamp_from_file(file_path, pattern, extractor)
            if timestamp and cls._is_in_time_range(timestamp, start_time, end_time):
                timestamps.append(timestamp)

        return timestamps

    @classmethod
    def _extract_timestamp_from_file(
        cls, file_path: Path, pattern: SatellitePattern, extractor: TimestampExtractor
    ) -> datetime | None:
        """Extract timestamp from a single file or its parent directory."""
        try:
            # First try to extract from filename
            timestamp = extractor.extract_timestamp(file_path.name, pattern)
            if not timestamp:
                # If that fails, try parent directory name
                parent_dir = file_path.parent.name
                timestamp = extractor.extract_timestamp_from_directory_name(parent_dir)
            return timestamp
        except ValueError:
            return None

    @classmethod
    def _extract_timestamps_from_subdirs(
        cls, directory: Path, start_time: datetime | None, end_time: datetime | None
    ) -> list[datetime]:
        """Extract timestamps from subdirectory names."""
        timestamps = []
        extractor = TimestampExtractor()

        subdirs = [p for p in directory.iterdir() if p.is_dir()]
        for subdir in subdirs:
            timestamp = extractor.extract_timestamp_from_directory_name(subdir.name)
            if timestamp and cls._is_in_time_range(timestamp, start_time, end_time):
                timestamps.append(timestamp)

        return timestamps

    @classmethod
    def _is_in_time_range(cls, timestamp: datetime, start_time: datetime | None, end_time: datetime | None) -> bool:
        """Check if timestamp is within the specified time range."""
        if start_time and timestamp < start_time:
            return False
        return not (end_time and timestamp > end_time)

    @staticmethod
    def find_date_range_in_directory(
        directory: Path, pattern: SatellitePattern
    ) -> tuple[datetime | None, datetime | None]:
        """Find the earliest and latest timestamps in the directory.

        Args:
            directory: The directory to scan
            pattern: The satellite pattern to use for matching

        Returns:
            Tuple of (earliest datetime, latest datetime), or (None, None) if no matches
        """
        timestamps = DirectoryScanner.scan_directory_for_timestamps(directory, pattern)

        if not timestamps:
            LOGGER.warning("No valid timestamps found in directory: %s", directory)
            return None, None

        return timestamps[0], timestamps[-1]
