"""Directory scanning utilities for timestamp extraction."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from goesvfi.utils import log

from .patterns import COMPILED_PATTERNS, SatellitePattern
from .timestamp import TimestampExtractor

LOGGER = log.get_logger(__name__)


class DirectoryScanner:
    """Scan directories for GOES satellite imagery files and extract timestamps."""

    @staticmethod
    def scan_directory_for_timestamps(
        directory: Path,
        pattern: SatellitePattern,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[datetime]:
        """
        Scan a directory for files matching the timestamp pattern.
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
            LOGGER.error(
                "Directory does not exist or is not a directory: %s", directory
            )
            return []

        # Compile regex pattern for files
        compiled_pattern = COMPILED_PATTERNS.get(pattern)
        if not compiled_pattern:
            LOGGER.error("Unknown satellite pattern: %s", pattern)
            return []

        # Find all PNG files
        png_files = list(directory.glob("**/*.png"))
        LOGGER.info("Found %s PNG files in %s", len(png_files), directory)

        # Extract timestamps from filenames
        timestamps = []
        extractor = TimestampExtractor()

        for file_path in png_files:
            try:
                # First try to extract from filename
                timestamp = extractor.extract_timestamp(file_path.name, pattern)
                if not timestamp:
                    # If that fails, try to extract from parent directory name
                    parent_dir = file_path.parent.name
                    extracted_ts = extractor.extract_timestamp_from_directory_name(
                        parent_dir
                    )
                    if extracted_ts is not None:
                        timestamp = extracted_ts

                if timestamp:
                    # Apply time range filtering if provided
                    if start_time and timestamp < start_time:
                        continue
                    if end_time and timestamp > end_time:
                        continue
                    timestamps.append(timestamp)
            except ValueError:
                # Skip files that don't match the pattern
                continue

        # If we didn't find any timestamps in files, look at subdirectories themselves
        if not timestamps:
            # Find all subdirectories that might contain timestamp information
            subdirs = [p for p in directory.iterdir() if p.is_dir()]
            for subdir in subdirs:
                # Initialize timestamp as None
                extracted_ts = extractor.extract_timestamp_from_directory_name(
                    subdir.name
                )
                # Skip iterations where we can't extract a timestamp
                if extracted_ts is None:
                    continue

                # Now timestamp is guaranteed to be a valid datetime
                timestamp = extracted_ts
                if timestamp:
                    # Apply time range filtering if provided
                    if start_time and timestamp < start_time:
                        continue
                    if end_time and timestamp > end_time:
                        continue
                    timestamps.append(timestamp)

        LOGGER.info("Found %s timestamps in %s", len(timestamps), directory)
        return sorted(timestamps)

    @staticmethod
    def find_date_range_in_directory(
        directory: Path, pattern: SatellitePattern
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Find the earliest and latest timestamps in the directory.

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
