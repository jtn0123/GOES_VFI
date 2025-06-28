"""Core reconciliation logic for integrity checking.

This module provides the main business logic for scanning directories,
finding missing timestamps, and reconciling local data with expectations.
"""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
import time
from typing import Any

from goesvfi.utils import log

from .cache_db import CacheDB
from .time_index import (
    SatellitePattern,
    detect_interval,
    generate_timestamp_sequence,
    scan_directory_for_timestamps,
)

LOGGER = log.get_logger(__name__)

# Type hints for callbacks
ProgressCallback = Callable[[int, int, float], None]
CancelCallback = Callable[[], bool]


class Reconciler:
    """Core business logic for scanning directories and identifying missing timestamps.

    This class handles the reconciliation between expected timestamps based on
    satellite schedules and actual files found in local directories.
    """

    def __init__(self, cache_db_path: Path | None = None) -> None:
        """Initialize the Reconciler with optional cache database."""
        self.cache = CacheDB(cache_db_path) if cache_db_path else CacheDB()
        LOGGER.info("Reconciler initialized with cache at %s", cache_db_path)

    def scan_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        satellite_pattern: SatellitePattern,
        base_directory: Path,
        interval_minutes: int = 0,
        progress_callback: ProgressCallback | None = None,
        should_cancel: CancelCallback | None = None,
        force_rescan: bool = False,
    ) -> dict[str, Any]:
        """Scan for missing timestamps within the date range.

        Args:
            start_date: Start of scan range
            end_date: End of scan range
            satellite_pattern: Satellite to scan for
            base_directory: Directory to scan
            interval_minutes: Expected interval between files (0 = auto-detect)
            progress_callback: Callback for progress updates
            should_cancel: Callback to check for cancellation
            force_rescan: Force rescan even if cached

        Returns:
            Dictionary with scan results
        """
        start_time = time.time()

        # Check cache unless forced to rescan
        if not force_rescan:
            cached = self.cache.get_cached_scan(
                start_date,
                end_date,
                satellite_pattern,
                interval_minutes,
                base_directory,
            )
            if cached:
                LOGGER.info("Using cached scan results")
                return {
                    "status": "completed",
                    "source": "cache",
                    "missing": cached["missing_timestamps"],
                    "interval": cached["interval_minutes"],
                    "total_expected": cached["expected_count"],
                    "total_found": cached["found_count"],
                    "timestamp_details": [],
                    "execution_time": 0.0,
                }

        # Scan directory for existing files
        LOGGER.info("Scanning directory: %s", base_directory)
        found_timestamps = scan_directory_for_timestamps(base_directory, satellite_pattern)

        # Auto-detect interval if not specified
        if interval_minutes == 0:
            interval_minutes = detect_interval(found_timestamps) or 30
            LOGGER.info("Auto-detected interval: %s minutes", interval_minutes)

        # Generate expected timestamps
        expected_timestamps = list(generate_timestamp_sequence(start_date, end_date, interval_minutes))

        # Find missing timestamps
        found_set = set(found_timestamps)
        missing_timestamps = [ts for ts in expected_timestamps if ts not in found_set]

        # Update progress
        total_expected = len(expected_timestamps)
        total_found = len(found_timestamps)

        if progress_callback:
            progress_callback(total_expected, total_found, 1.0)

        # Store in cache
        self.cache.store_scan_results(
            start_date,
            end_date,
            satellite_pattern,
            interval_minutes,
            base_directory,
            missing_timestamps,
            total_expected,
            total_found,
        )

        execution_time = time.time() - start_time

        return {
            "status": "completed",
            "source": "scan",
            "missing": missing_timestamps,
            "interval": interval_minutes,
            "total_expected": total_expected,
            "total_found": total_found,
            "timestamp_details": [],
            "execution_time": execution_time,
        }

    def get_missing_timestamps(
        self,
        start_date: datetime,
        end_date: datetime,
        satellite_pattern: SatellitePattern,
        base_directory: Path,
        interval_minutes: int = 0,
    ) -> list[datetime]:
        """Get a list of missing timestamps.

        Args:
            start_date: Start of scan range
            end_date: End of scan range
            satellite_pattern: Satellite to scan for
            base_directory: Directory to scan
            interval_minutes: Expected interval between files (0 = auto-detect)

        Returns:
            List of missing timestamps
        """
        scan_result = self.scan_date_range(start_date, end_date, satellite_pattern, base_directory, interval_minutes)
        missing = scan_result.get("missing", [])
        return list(missing) if missing else []
