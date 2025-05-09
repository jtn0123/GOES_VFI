"""
Reconciler Manager for hybrid CDN/S3 satellite imagery fetching.

This module provides the ReconcileManager class that coordinates scanning
directories, identifying missing files, and fetching them from remote sources
using the hybrid CDN/S3 strategy.
"""
import asyncio
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional, Union, Callable, Awaitable

from goesvfi.utils import log
from goesvfi.integrity_check.time_index import TimeIndex, SatellitePattern
from goesvfi.integrity_check.cache_db import CacheDB
from goesvfi.integrity_check.thread_cache_db import ThreadLocalCacheDB
from goesvfi.integrity_check.remote.base import (
    RemoteStore, RemoteStoreError, ResourceNotFoundError,
    AuthenticationError, ConnectionError
)
from goesvfi.integrity_check.remote.cdn_store import CDNStore
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.render.netcdf import render_png

LOGGER = log.get_logger(__name__)

# Type definitions
ProgressCallback = Callable[[int, int, str], None]
FileCallback = Callable[[Path, bool], None]
ErrorCallback = Callable[[str, Exception], None]


class ReconcileManager:
    """Manager for satellite imagery integrity reconciliation.
    
    This class coordinates scanning directories, identifying missing files,
    and fetching them from remote sources using the hybrid CDN/S3 strategy.
    """
    
    def __init__(
        self,
        cache_db: Union[CacheDB, ThreadLocalCacheDB],
        base_dir: Union[str, Path],
        cdn_store: Optional[CDNStore] = None,
        s3_store: Optional[S3Store] = None,
        cdn_resolution: Optional[str] = None,
        max_concurrency: int = 5,
    ):
        """Initialize the reconciler.
        
        Args:
            cache_db: Cache database instance (regular or thread-local)
            base_dir: Base directory for local files
            cdn_store: CDN store instance (optional, will create if None)
            s3_store: S3 store instance (optional, will create if None)
            cdn_resolution: CDN image resolution (default: TimeIndex.CDN_RES)
            max_concurrency: Maximum concurrent downloads
        """
        # Check if we need to wrap CacheDB in a ThreadLocalCacheDB
        if isinstance(cache_db, CacheDB) and not isinstance(cache_db, ThreadLocalCacheDB):
            LOGGER.info("Converting regular CacheDB to thread-local CacheDB for thread safety")
            self.cache_db = ThreadLocalCacheDB(db_path=cache_db.db_path)
            # Close the original connection since we won't use it
            cache_db.close()
        else:
            self.cache_db = cache_db
            
        LOGGER.debug(f"Using cache_db of type: {type(self.cache_db).__name__}")
        self.base_dir = Path(base_dir)
        self.cdn_store = cdn_store or CDNStore(resolution=cdn_resolution)
        self.s3_store = s3_store or S3Store()
        self.cdn_resolution = cdn_resolution or TimeIndex.CDN_RES
        self.max_concurrency = max_concurrency
        self.recent_window_days = TimeIndex.RECENT_WINDOW_DAYS
    
    def _get_local_path(self, ts: datetime, satellite: SatellitePattern) -> Path:
        """Get the local path for a timestamp and satellite.
        
        Args:
            ts: Timestamp
            satellite: Satellite pattern enum
            
        Returns:
            Path to the local file
        """
        return self.base_dir / TimeIndex.to_local_path(ts, satellite)
    
    async def _is_recent(self, ts: datetime) -> bool:
        """Check if a timestamp is within the recent window.
        
        Args:
            ts: Timestamp to check
            
        Returns:
            True if recent, False otherwise
        """
        cutoff = datetime.utcnow() - timedelta(days=self.recent_window_days)
        return ts >= cutoff
    
    async def _get_store_for_timestamp(self, ts: datetime) -> RemoteStore:
        """Get the appropriate store for a timestamp based on recency.
        
        Args:
            ts: Timestamp to check
            
        Returns:
            CDNStore for recent timestamps, S3Store for older ones
        """
        if await self._is_recent(ts):
            return self.cdn_store
        else:
            return self.s3_store
    
    async def scan_directory(
        self,
        directory: Union[str, Path],
        satellite: SatellitePattern,
        start_time: datetime,
        end_time: datetime,
        interval_minutes: int = 10,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Tuple[Set[datetime], Set[datetime]]:
        """Scan a directory for missing files.
        
        Args:
            directory: Directory to scan
            satellite: Satellite pattern enum
            start_time: Start timestamp
            end_time: End timestamp
            interval_minutes: Expected interval between timestamps in minutes
            progress_callback: Callback for progress updates
            
        Returns:
            Tuple of (existing_timestamps, missing_timestamps)
        """
        directory = Path(directory)
        if not directory.exists():
            LOGGER.warning(f"Directory does not exist: {directory}")
            directory.mkdir(parents=True, exist_ok=True)
        
        # Step 1: Generating expected timestamps
        LOGGER.debug(f"Starting scan step 1/5: Generating expected timestamps...")
        if progress_callback:
            progress_callback(0, 5, f"Step 1/5: Generating expected timestamps...")
        
        # Check if interval is 0, which could cause an infinite loop
        if interval_minutes <= 0:
            LOGGER.warning(f"Invalid interval minutes: {interval_minutes}, defaulting to 10")
            interval_minutes = 10
        
        LOGGER.debug(f"Using interval of {interval_minutes} minutes between timestamps")
        
        expected_timestamps = set()
        current = start_time
        timestamp_count = 0
        
        # Add a safety limit to prevent infinite loops
        max_iterations = 50000  # Set a reasonable max number of timestamps
        
        LOGGER.debug(f"Starting timestamp generation from {start_time} to {end_time}")
        while current <= end_time and timestamp_count < max_iterations:
            expected_timestamps.add(current)
            current += timedelta(minutes=interval_minutes)
            timestamp_count += 1
            
            # Log progress periodically
            if timestamp_count % 1000 == 0:
                LOGGER.debug(f"Generated {timestamp_count} timestamps so far, current: {current}")
                if progress_callback:
                    progress_callback(0, 5, f"Step 1/5: Generating timestamps ({timestamp_count} so far)...")
        
        if timestamp_count >= max_iterations:
            LOGGER.warning(f"Reached maximum timestamp limit ({max_iterations}), stopping generation")
        
        total_files = len(expected_timestamps)
        LOGGER.debug(f"Generated {total_files} expected timestamps from {start_time} to {end_time}")
        
        # Step 2: Checking cache for existing timestamps
        LOGGER.debug(f"Starting scan step 2/5: Checking cache for {total_files} timestamps...")
        if progress_callback:
            progress_callback(1, 5, f"Step 2/5: Checking cache for {total_files} timestamps...")
        
        existing_timestamps = set()
        
        # Check cache first
        cached_timestamps = await self.cache_db.get_timestamps(
            satellite=satellite,
            start_time=start_time,
            end_time=end_time
        )
        existing_timestamps.update(cached_timestamps)
        
        # Step 3: Determining which timestamps need filesystem check
        LOGGER.debug(f"Starting scan step 3/5: Found {len(existing_timestamps)}/{total_files} in cache, preparing filesystem check...")
        if progress_callback:
            progress_callback(2, 5, f"Step 3/5: Found {len(existing_timestamps)}/{total_files} in cache, preparing filesystem check...")
        
        # For timestamps not in cache, check filesystem
        unchecked_timestamps = expected_timestamps - existing_timestamps
        unchecked_count = len(unchecked_timestamps)
        
        LOGGER.debug(f"Starting scan step 4/5: Checking filesystem for {unchecked_count} timestamps...")
        if progress_callback:
            progress_callback(3, 5, f"Step 4/5: Checking filesystem for {unchecked_count} timestamps...")
        
        # Step 4: Checking filesystem for uncached timestamps
        filesystem_check_count = 0
        for i, ts in enumerate(sorted(unchecked_timestamps)):
            filesystem_check_count += 1
            if progress_callback:
                # Show both overall progress (step 4/5) and sub-step progress
                sub_progress = f"{i+1}/{unchecked_count}"
                if i % 10 == 0 or i == unchecked_count - 1:  # Update only every 10 items to reduce UI updates
                    progress_callback(3, 5, f"Step 4/5: Checking filesystem ({sub_progress}): {ts.isoformat()}")
            
            local_path = self._get_local_path(ts, satellite)
            if local_path.exists():
                existing_timestamps.add(ts)
                # Update cache
                await self.cache_db.add_timestamp(
                    timestamp=ts,
                    satellite=satellite,
                    file_path=str(local_path),
                    found=True
                )
        
        # Step 5: Finalizing results
        LOGGER.debug(f"Starting scan step 5/5: Finalizing scan results...")
        if progress_callback:
            progress_callback(4, 5, f"Step 5/5: Finalizing scan results...")
        
        # Calculate missing timestamps
        missing_timestamps = expected_timestamps - existing_timestamps
        
        LOGGER.info(
            f"Scan complete: {len(existing_timestamps)}/{total_files} files found, "
            f"{len(missing_timestamps)} missing (checked {filesystem_check_count} on filesystem)"
        )
        
        # Final step complete
        LOGGER.debug(f"Scan completed successfully: {len(missing_timestamps)} files missing out of {total_files}")
        if progress_callback:
            progress_callback(5, 5, f"Scan complete: {len(missing_timestamps)} files missing out of {total_files}")
        
        return existing_timestamps, missing_timestamps
    
    async def fetch_missing_files(
        self,
        missing_timestamps: Set[datetime],
        satellite: SatellitePattern,
        progress_callback: Optional[ProgressCallback] = None,
        file_callback: Optional[FileCallback] = None,
        error_callback: Optional[ErrorCallback] = None,
    ) -> Dict[datetime, Union[Path, Exception]]:
        """Fetch missing files from remote sources.
        
        Args:
            missing_timestamps: Set of missing timestamps to fetch
            satellite: Satellite pattern enum
            progress_callback: Callback for progress updates
            file_callback: Callback when a file is processed
            error_callback: Callback when an error occurs
            
        Returns:
            Dictionary mapping timestamps to downloaded paths or exceptions
        """
        results: Dict[datetime, Union[Path, Exception]] = {}
        total = len(missing_timestamps)
        
        if not missing_timestamps:
            if progress_callback:
                progress_callback(0, 1, "No missing files to fetch")
            LOGGER.info("No missing files to fetch")
            return results
        
        # Step 1: Analyze and group timestamps
        if progress_callback:
            progress_callback(0, 4, "Step 1/4: Analyzing missing files...")
        
        LOGGER.info(f"Fetching {total} missing files")
        
        # Group timestamps by recency for efficient store handling
        recent_timestamps = set()
        old_timestamps = set()
        
        for ts in missing_timestamps:
            if await self._is_recent(ts):
                recent_timestamps.add(ts)
            else:
                old_timestamps.add(ts)
        
        # Step 2: Preparing download strategy
        if progress_callback:
            progress_callback(1, 4, f"Step 2/4: Preparing download strategy ({len(recent_timestamps)} CDN, {len(old_timestamps)} S3)...")
        
        LOGGER.debug(
            f"Fetching strategy: {len(recent_timestamps)} recent files from CDN, "
            f"{len(old_timestamps)} older files from S3"
        )
        
        # Process each group with the appropriate store
        semaphore = asyncio.Semaphore(self.max_concurrency)
        
        async def fetch_single(ts: datetime, store: RemoteStore, is_recent: bool, source_name: str, idx: int, source_total: int) -> None:
            async with semaphore:
                overall_progress = len(results)
                if progress_callback:
                    if is_recent:
                        step_message = f"Step 3/4: Downloading from CDN ({idx+1}/{source_total}): {ts.isoformat()}"
                    else:
                        step_message = f"Step 4/4: Downloading from S3 ({idx+1}/{source_total}): {ts.isoformat()}"
                    progress_callback(2 if is_recent else 3, 4, step_message)
                
                local_path = self._get_local_path(ts, satellite)
                
                try:
                    # Check if file exists remotely
                    exists_message = f"Checking {source_name} for {ts.isoformat()}"
                    if progress_callback:
                        if is_recent:
                            progress_callback(2, 4, f"Step 3/4: {exists_message} ({idx+1}/{source_total})")
                        else:
                            progress_callback(3, 4, f"Step 4/4: {exists_message} ({idx+1}/{source_total})")
                    
                    if await store.exists(ts, satellite):
                        download_message = f"Downloading from {source_name}: {ts.isoformat()}"
                        if progress_callback:
                            if is_recent:
                                progress_callback(2, 4, f"Step 3/4: {download_message} ({idx+1}/{source_total})")
                            else:
                                progress_callback(3, 4, f"Step 4/4: {download_message} ({idx+1}/{source_total})")
                        
                        # Download the file
                        downloaded_path = await store.download(ts, satellite, local_path)
                        
                        # For S3 NetCDF files, render to PNG
                        if not is_recent and downloaded_path.suffix.lower() == '.nc':
                            render_message = f"Rendering NetCDF to PNG: {ts.isoformat()}"
                            if progress_callback:
                                progress_callback(3, 4, f"Step 4/4: {render_message} ({idx+1}/{source_total})")
                            
                            png_path = render_png(
                                netcdf_path=downloaded_path,
                                output_path=downloaded_path.with_suffix('.png')
                            )
                            
                            # Update the path to the rendered PNG
                            downloaded_path = png_path
                        
                        # Update cache
                        await self.cache_db.add_timestamp(
                            timestamp=ts,
                            satellite=satellite,
                            file_path=str(downloaded_path),
                            found=True
                        )
                        
                        if file_callback:
                            file_callback(downloaded_path, True)
                        
                        results[ts] = downloaded_path
                    else:
                        # File not found remotely
                        not_found_message = f"File not found on {source_name}: {ts.isoformat()}"
                        if progress_callback:
                            if is_recent:
                                progress_callback(2, 4, f"Step 3/4: {not_found_message} ({idx+1}/{source_total})")
                            else:
                                progress_callback(3, 4, f"Step 4/4: {not_found_message} ({idx+1}/{source_total})")
                        
                        await self.cache_db.add_timestamp(
                            timestamp=ts,
                            satellite=satellite,
                            file_path="",
                            found=False
                        )
                        
                        # Add DOY info to error message for clearer debugging
                        doy = ts.strftime("%j")  # Day of year as string
                        
                        if file_callback:
                            file_callback(local_path, False)
                        
                        msg = f"File not found remotely for {ts.isoformat()} (DOY={doy})"
                        
                        # Find nearest standard GOES imagery intervals for better error messaging
                        from goesvfi.integrity_check.time_index import TimeIndex
                        nearest_intervals = TimeIndex.find_nearest_intervals(ts)
                        nearest_intervals_str = ", ".join([dt.strftime("%Y-%m-%d %H:%M") for dt in nearest_intervals])
                        
                        # Add more helpful debugging information
                        LOGGER.warning(msg)
                        LOGGER.debug(f"Note: NOAA GOES imagery is available at specific time intervals")
                        LOGGER.debug(f"Input timestamp: year={ts.year}, doy={doy}, hour={ts.hour}, minute={ts.minute}")
                        LOGGER.debug(f"Standard GOES intervals: {TimeIndex.STANDARD_INTERVALS} minutes past the hour")
                        LOGGER.debug(f"Nearest standard timestamps: {nearest_intervals_str}")
                        
                        # Enhance error message with suggestions
                        msg = f"{msg} - Try timestamps at {TimeIndex.STANDARD_INTERVALS} minutes past the hour instead"
                        
                        error = FileNotFoundError(msg)
                        
                        if error_callback:
                            error_callback(str(local_path), error)
                        
                        results[ts] = error
                
                except (ResourceNotFoundError, AuthenticationError, ConnectionError, RemoteStoreError) as e:
                    # Handle our custom error types with better messages
                    error_message = f"Error fetching from {source_name}: {ts.isoformat()}"
                    if progress_callback:
                        if is_recent:
                            progress_callback(2, 4, f"Step 3/4: {error_message} ({idx+1}/{source_total})")
                        else:
                            progress_callback(3, 4, f"Step 4/4: {error_message} ({idx+1}/{source_total})")
                    
                    # Enhanced error logging
                    LOGGER.error(f"Error fetching {ts.isoformat()} from {source_name}: {e.get_user_message()}")
                    
                    if hasattr(e, 'technical_details') and e.technical_details:
                        LOGGER.debug(f"Technical details for {ts.isoformat()}: {e.technical_details}")
                    
                    # Log extra debug info
                    LOGGER.debug(f"Download error context - Satellite: {satellite}, Store: {store.__class__.__name__}, Remote exists check failed")
                    
                    if error_callback:
                        error_callback(str(local_path), e)
                    
                    results[ts] = e
                except Exception as e:
                    # Wrap generic exceptions in a user-friendly error
                    error_message = f"Unexpected error from {source_name}: {ts.isoformat()}"
                    if progress_callback:
                        if is_recent:
                            progress_callback(2, 4, f"Step 3/4: {error_message} ({idx+1}/{source_total})")
                        else:
                            progress_callback(3, 4, f"Step 4/4: {error_message} ({idx+1}/{source_total})")
                    
                    # Enhanced error logging
                    LOGGER.error(f"CRITICAL ERROR fetching {ts.isoformat()} from {source_name}: {str(e)}")
                    import traceback
                    LOGGER.error(f"Stacktrace for {ts.isoformat()}: {traceback.format_exc()}")
                    
                    # Log as much context as possible
                    LOGGER.debug(f"Download context - Satellite: {satellite}, Store type: {store.__class__.__name__}")
                    LOGGER.debug(f"Download context - Local path: {local_path}, TS: {ts.isoformat()}")
                    
                    try:
                        # Try to get more information about the store
                        store_info = "Unknown"
                        if hasattr(store, 'base_url'):
                            store_info = f"base_url={store.base_url}"
                        elif hasattr(store, 'bucket_name'):
                            store_info = f"bucket={store.bucket_name}"
                        LOGGER.debug(f"Store details: {store_info}")
                    except Exception as store_err:
                        LOGGER.debug(f"Unable to get store details: {store_err}")
                    
                    wrapped_error = RemoteStoreError(
                        message=f"Unexpected error downloading {satellite.name} data",
                        technical_details=f"Error during download for {ts.isoformat()}: {str(e)}",
                        original_exception=e
                    )
                    
                    if error_callback:
                        error_callback(str(local_path), wrapped_error)
                    
                    results[ts] = wrapped_error
        
        # Create tasks for each group
        cdn_tasks = []
        s3_tasks = []
        
        # Step 3: Download recent files from CDN
        if progress_callback and recent_timestamps:
            progress_callback(2, 4, f"Step 3/4: Downloading {len(recent_timestamps)} recent files from CDN...")
        
        # Recent files from CDN 
        async with self.cdn_store:
            for i, ts in enumerate(sorted(recent_timestamps)):
                cdn_tasks.append(fetch_single(ts, self.cdn_store, True, "CDN", i, len(recent_timestamps)))
            
            if cdn_tasks:
                await asyncio.gather(*cdn_tasks)
        
        # Step 4: Download older files from S3
        if progress_callback and old_timestamps:
            progress_callback(3, 4, f"Step 4/4: Downloading {len(old_timestamps)} older files from S3...")
        
        # Older files from S3
        async with self.s3_store:
            for i, ts in enumerate(sorted(old_timestamps)):
                s3_tasks.append(fetch_single(ts, self.s3_store, False, "S3", i, len(old_timestamps)))
            
            if s3_tasks:
                await asyncio.gather(*s3_tasks)
        
        # Final summary
        success_count = sum(1 for v in results.values() if isinstance(v, Path))
        success_message = f"Download complete: {success_count}/{total} files downloaded successfully"
        
        LOGGER.info(success_message)
        
        if progress_callback:
            progress_callback(4, 4, success_message)
        
        return results
    
    async def reconcile(
        self,
        directory: Union[str, Path],
        satellite: SatellitePattern,
        start_time: datetime,
        end_time: datetime,
        interval_minutes: int = 10,
        progress_callback: Optional[ProgressCallback] = None,
        file_callback: Optional[FileCallback] = None,
        error_callback: Optional[ErrorCallback] = None,
    ) -> Tuple[int, int, int]:
        """Reconcile missing files in a directory.
        
        Args:
            directory: Directory to scan
            satellite: Satellite pattern enum
            start_time: Start timestamp
            end_time: End timestamp
            interval_minutes: Expected interval between timestamps in minutes
            progress_callback: Callback for progress updates
            file_callback: Callback when a file is processed
            error_callback: Callback when an error occurs
            
        Returns:
            Tuple of (total_files, existing_files, fetched_files)
        """
        # Create a phase-based progress callback that shows both the overall progress and current phase
        def phase_progress_callback(current: int, total: int, message: str) -> None:
            if not progress_callback:
                return
            
            # Call the original callback with enhanced message
            phase = "Scanning"
            if "Step " in message:
                phase = "Scanning"
            elif "Download" in message:
                phase = "Downloading"
            
            # Pass along the original parameters
            progress_callback(current, total, message)
        
        # Phase 1: Scan directory for missing files
        if progress_callback:
            progress_callback(0, 2, f"Phase 1/2: Preparing to scan directory...")
        
        existing, missing = await self.scan_directory(
            directory=directory,
            satellite=satellite,
            start_time=start_time,
            end_time=end_time,
            interval_minutes=interval_minutes,
            progress_callback=phase_progress_callback
        )
        
        # Transition between phases
        if progress_callback:
            if len(missing) > 0:
                progress_callback(1, 2, f"Phase 2/2: Preparing to download {len(missing)} missing files...")
            else:
                progress_callback(1, 2, f"Phase 2/2: No missing files to download, completing the process...")
        
        # Phase 2: Fetch missing files (if any)
        results = await self.fetch_missing_files(
            missing_timestamps=missing,
            satellite=satellite,
            progress_callback=phase_progress_callback,
            file_callback=file_callback,
            error_callback=error_callback
        )
        
        # Count fetched files
        fetched = sum(1 for v in results.values() if isinstance(v, Path))
        
        total = len(existing) + len(missing)
        existing_count = len(existing)
        
        # Final completion notification
        if progress_callback:
            progress_callback(2, 2, f"Reconciliation complete: {existing_count} existing, {fetched} downloaded, {len(missing) - fetched} failed")
        
        return total, existing_count, fetched