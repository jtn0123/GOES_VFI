"""Core reconciliation logic for integrity checking.

This module provides the main business logic for scanning directories,
finding missing timestamps, and reconciling local data with expectations.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable

from goesvfi.utils import log
from .time_index import (
    SatellitePattern,
    scan_directory_for_timestamps,
    generate_timestamp_sequence,
    detect_interval,
    generate_expected_filename
)
from .cache_db import CacheDB

LOGGER = log.get_logger(__name__)

# Type hints for callbacks
ProgressCallback = Callable[[int, int, float], None]
CancelCallback = Callable[[], bool]


class Reconciler:
    """
    Core business logic for scanning directories and identifying missing timestamps.

    This class handles the process of scanning a directory for satellite imagery,
    identifying missing timestamps within a date range, and providing detailed
    analysis of the findings.
    """
    def __init__(self, cache_db_path: Optional[Path] = None):
        """
        Initialize the Reconciler with optional cache database.

        Args:
            cache_db_path: Optional path to the cache database file
        """
        self.cache = CacheDB(cache_db_path) if cache_db_path else CacheDB()
    def scan_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        satellite_pattern: SatellitePattern,
        base_directory: Path,
        interval_minutes: int = 0,  # 0 means auto-detect
        progress_callback: Optional[ProgressCallback] = None,
        should_cancel: Optional[CancelCallback] = None,
        force_rescan: bool = False
    ) -> Dict[str, Any]:
        """
        Scan for missing timestamps within the date range.

        Args:
            start_date: Start date/time for the range
            end_date: End date/time for the range
            satellite_pattern: Satellite pattern to use for matching
            base_directory: Base directory to scan for files
            interval_minutes: Time interval in minutes (0 for auto-detect)
            progress_callback: Optional callback for progress updates
            should_cancel: Optional callback to check if scan should be cancelled
            force_rescan: Whether to force a rescan even if cached results exist

        Returns:
            Dict with scan results including missing timestamps
        """
        LOGGER.info(f"Starting scan for date range {start_date} to {end_date} "
                  f"with pattern {satellite_pattern.name}")
        scan_start_time = time.time()
        # Check cache first if not forcing a rescan
        if not force_rescan:
            options = {"interval_auto_detect": interval_minutes == 0}
            cached_result = self.cache.get_cached_scan(
                start_date, end_date, satellite_pattern,
                interval_minutes, base_directory, options
            )
            if cached_result:
                LOGGER.info(f"Using cached scan results from {cached_result['scan_time']}")
                # Report progress if callback provided
                if progress_callback:
                    progress_callback(100, 100, 0.0)  # Complete

                # Extract missing timestamps as datetime objects
                missing_timestamps = [item['timestamp'] for item in cached_result['missing']]

                # Return results
                return {
                    "status": "completed",
                    "source": "cache",
                    "missing": missing_timestamps,
                    "interval": interval_minutes,
                    "total_expected": cached_result['total_expected'],
                    "total_found": cached_result['total_found'],
                    "timestamp_details": cached_result['missing'],
                    "execution_time": 0.0
                }
        
        # Normalize dates - ensure start is before end
        if start_date > end_date:
            LOGGER.warning("Start date is after end date, swapping values")
            start_date, end_date = end_date, start_date

        # Validate directory exists
        if not base_directory.exists() or not base_directory.is_dir():
            error_msg = f"Base directory does not exist: {base_directory}"
            LOGGER.error(error_msg)
            return {
                "status": "error",
                "error": error_msg,
                "execution_time": time.time() - scan_start_time
            }
        
        # Report initial progress
        if progress_callback:
            progress_callback(0, 100, 0.0)
        
        # Check for cancellation
        if should_cancel and should_cancel():
            LOGGER.info("Scan cancelled before starting file scan")
            return {
                "status": "cancelled",
                "execution_time": time.time() - scan_start_time
            }
        
        # Step 1: Scan directory for existing files and extract timestamps
        LOGGER.info(f"Scanning directory {base_directory} for timestamps")

        # Start directory scan with filtering by date range
        found_timestamps = scan_directory_for_timestamps(
            base_directory, satellite_pattern, start_date, end_date
        )
        
        # Progress update
        if progress_callback:
            progress_callback(20, 100, 0.0)  # 20% progress after scanning
        
        # Check for cancellation
        if should_cancel and should_cancel():
            LOGGER.info("Scan cancelled after directory scan")
            return {
                "status": "cancelled",
                "execution_time": time.time() - scan_start_time
            }
        
        # Step 2: Determine interval if not provided
        if interval_minutes <= 0:
            LOGGER.info("Auto-detecting interval from existing timestamps")
            interval_minutes = detect_interval(found_timestamps)
            LOGGER.info(f"Detected interval: {interval_minutes} minutes")
        
        # Progress update
        if progress_callback:
            progress_callback(30, 100, 0.0)  # 30% progress after interval detection
        
        # Step 3: Generate expected timestamps for the range
        LOGGER.info(f"Generating expected timestamps at {interval_minutes}-minute intervals")
        expected_timestamps = generate_timestamp_sequence(
            start_date, end_date, interval_minutes
        )
        
        # Progress update
        if progress_callback:
            progress_callback(40, 100, 0.0)  # 40% progress after generating expected
        
        # Check for cancellation
        if should_cancel and should_cancel():
            LOGGER.info("Scan cancelled after generating expected timestamps")
            return {
                "status": "cancelled",
                "execution_time": time.time() - scan_start_time
            }
        
        # Step 4: Find missing timestamps
        LOGGER.info("Calculating missing timestamps")
        found_set = set(found_timestamps)
        expected_set = set(expected_timestamps)
        missing_set = expected_set - found_set
        missing_timestamps = sorted(missing_set)
        # Progress update
        if progress_callback:
            progress_callback(70, 100, 0.0)  # 70% progress after finding missing
        
        # Step 5: Generate missing file details
        LOGGER.info("Generating details for missing files")
        missing_details = []
        
        for dt in missing_timestamps:
            expected_filename = generate_expected_filename(dt, satellite_pattern)
            missing_details.append({
                'timestamp': dt,
                'expected_filename': expected_filename
            })
        
        # Progress update
        if progress_callback:
            progress_callback(90, 100, 0.0)  # 90% progress after details
        
        # Step 6: Store results in cache
        LOGGER.info("Storing scan results in cache")
        options = {"interval_auto_detect": interval_minutes == 0}
        self.cache.store_scan_results(
            start_date, end_date, satellite_pattern, interval_minutes,
            base_directory, missing_timestamps, len(expected_timestamps),
            len(found_timestamps), options
        )
        
        # Final progress update
        if progress_callback:
            progress_callback(100, 100, 0.0)  # 100% complete
        
        # Calculate execution time
        execution_time = time.time() - scan_start_time
        
        # Return results
        return {
            "status": "completed",
            "source": "scan",
            "missing": missing_timestamps,
            "interval": interval_minutes,
            "total_expected": len(expected_timestamps),
            "total_found": len(found_timestamps),
            "timestamp_details": missing_details,
            "execution_time": execution_time
        }
    
    def analyze_missing_intervals(self, missing_timestamps: List[datetime]) -> Dict[str, Any]:
        """
        Analyze patterns in missing timestamps to identify significant gaps.
        
        Args:
            missing_timestamps: List of missing timestamps
            
        Returns:
            A dictionary with analysis results
        """
        if not missing_timestamps:
            return {
                "status": "completed",
                "gaps": [],
                "isolated_missing": [],
                "total_gaps": 0,
                "max_gap_size": 0,
                "max_gap_start": None,
                "max_gap_end": None
            }
        
        # Sort timestamps
        sorted_timestamps = sorted(missing_timestamps)
        
        # Identify continuous gaps
        gaps = []
        current_gap = [sorted_timestamps[0]]
        
        for i in range(1, len(sorted_timestamps)):
            prev = sorted_timestamps[i - 1]
            curr = sorted_timestamps[i]
            
            # Check if consecutive (allowing for small variations)
            time_diff = (curr - prev).total_seconds() / 60  # diff in minutes
            
            # If within expected interval range, add to current gap
            if time_diff < 35:  # Allowing for some variation
                current_gap.append(curr)
            else:
                # End of gap, start a new one
                if len(current_gap) > 1:
                    gaps.append(current_gap)
                current_gap = [curr]
        
        # Add final gap if it exists
        if len(current_gap) > 1:
            gaps.append(current_gap)
        
        # Find isolated missing timestamps (not part of a gap)
        all_gap_timestamps = [ts for gap in gaps for ts in gap]
        isolated_missing = [ts for ts in sorted_timestamps if ts not in all_gap_timestamps]
        
        # Find the largest gap
        max_gap_size = 0
        max_gap_start = None
        max_gap_end = None
        
        for gap in gaps:
            if len(gap) > max_gap_size:
                max_gap_size = len(gap)
                max_gap_start = gap[0]
                max_gap_end = gap[-1]
        
        # Prepare analysis result
        return {
            "status": "completed",
            "gaps": gaps,
            "isolated_missing": isolated_missing,
            "total_gaps": len(gaps),
            "max_gap_size": max_gap_size,
            "max_gap_start": max_gap_start,
            "max_gap_end": max_gap_end
        }
    
    def close(self) -> None:
        """Close resources (like database connections)."""
        if hasattr(self, 'cache') and self.cache:
            self.cache.close()
