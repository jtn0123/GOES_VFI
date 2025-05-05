"""
Reconciler Manager for hybrid CDN/S3 satellite imagery fetching.

This module provides the ReconcileManager class that coordinates scanning
directories, identifying missing files, and fetching them from remote sources
using the hybrid CDN/S3 strategy.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional, Union, Callable, Awaitable

from goesvfi.utils import log
from goesvfi.integrity_check.time_index import TimeIndex, SatellitePattern
from goesvfi.integrity_check.cache_db import CacheDB
from goesvfi.integrity_check.remote.base import RemoteStore
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
        cache_db: CacheDB,
        base_dir: Union[str, Path],
        cdn_store: Optional[CDNStore] = None,
        s3_store: Optional[S3Store] = None,
        cdn_resolution: Optional[str] = None,
        max_concurrency: int = 5,
    ):
        """Initialize the reconciler.
        
        Args:
            cache_db: Cache database instance
            base_dir: Base directory for local files
            cdn_store: CDN store instance (optional, will create if None)
            s3_store: S3 store instance (optional, will create if None)
            cdn_resolution: CDN image resolution (default: TimeIndex.CDN_RES)
            max_concurrency: Maximum concurrent downloads
        """
        self.cache_db = cache_db
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
        
        # Generate expected timestamps
        expected_timestamps = set()
        current = start_time
        while current <= end_time:
            expected_timestamps.add(current)
            current += timedelta(minutes=interval_minutes)
        
        total_files = len(expected_timestamps)
        
        # Find existing files
        existing_timestamps = set()
        
        # Check cache first
        cached_timestamps = await self.cache_db.get_timestamps(
            satellite=satellite,
            start_time=start_time,
            end_time=end_time
        )
        existing_timestamps.update(cached_timestamps)
        
        # For timestamps not in cache, check filesystem
        unchecked_timestamps = expected_timestamps - existing_timestamps
        
        for i, ts in enumerate(sorted(unchecked_timestamps)):
            if progress_callback:
                progress_callback(i, len(unchecked_timestamps), f"Scanning for {ts.isoformat()}")
            
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
        
        # Calculate missing timestamps
        missing_timestamps = expected_timestamps - existing_timestamps
        
        LOGGER.info(
            f"Scan complete: {len(existing_timestamps)}/{total_files} files found, "
            f"{len(missing_timestamps)} missing"
        )
        
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
            LOGGER.info("No missing files to fetch")
            return results
        
        LOGGER.info(f"Fetching {total} missing files")
        
        # Group timestamps by recency for efficient store handling
        recent_timestamps = set()
        old_timestamps = set()
        
        for ts in missing_timestamps:
            if await self._is_recent(ts):
                recent_timestamps.add(ts)
            else:
                old_timestamps.add(ts)
        
        LOGGER.debug(
            f"Fetching strategy: {len(recent_timestamps)} recent files from CDN, "
            f"{len(old_timestamps)} older files from S3"
        )
        
        # Process each group with the appropriate store
        semaphore = asyncio.Semaphore(self.max_concurrency)
        
        async def fetch_single(ts: datetime, store: RemoteStore, is_recent: bool):
            async with semaphore:
                idx = len(results)
                if progress_callback:
                    progress_callback(idx, total, f"Checking {ts.isoformat()}")
                
                local_path = self._get_local_path(ts, satellite)
                
                try:
                    # Check if file exists remotely
                    if await store.exists(ts, satellite):
                        if progress_callback:
                            progress_callback(idx, total, f"Downloading {ts.isoformat()}")
                        
                        # Download the file
                        downloaded_path = await store.download(ts, satellite, local_path)
                        
                        # For S3 NetCDF files, render to PNG
                        if not is_recent and downloaded_path.suffix.lower() == '.nc':
                            if progress_callback:
                                progress_callback(idx, total, f"Rendering {ts.isoformat()}")
                            
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
                        await self.cache_db.add_timestamp(
                            timestamp=ts,
                            satellite=satellite,
                            file_path="",
                            found=False
                        )
                        
                        if file_callback:
                            file_callback(local_path, False)
                        
                        msg = f"File not found remotely for {ts.isoformat()}"
                        LOGGER.warning(msg)
                        error = FileNotFoundError(msg)
                        
                        if error_callback:
                            error_callback(str(local_path), error)
                        
                        results[ts] = error
                
                except Exception as e:
                    LOGGER.exception(f"Error fetching {ts.isoformat()}: {e}")
                    
                    if error_callback:
                        error_callback(str(local_path), e)
                    
                    results[ts] = e
        
        # Create tasks for each group
        tasks = []
        
        # Recent files from CDN
        async with self.cdn_store:
            for ts in recent_timestamps:
                tasks.append(fetch_single(ts, self.cdn_store, True))
            
            if tasks:
                await asyncio.gather(*tasks)
                tasks = []
        
        # Older files from S3
        async with self.s3_store:
            for ts in old_timestamps:
                tasks.append(fetch_single(ts, self.s3_store, False))
            
            if tasks:
                await asyncio.gather(*tasks)
        
        LOGGER.info(
            f"Fetch complete: {sum(1 for v in results.values() if isinstance(v, Path))}/{total} "
            f"files downloaded successfully"
        )
        
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
        # Scan directory for missing files
        existing, missing = await self.scan_directory(
            directory=directory,
            satellite=satellite,
            start_time=start_time,
            end_time=end_time,
            interval_minutes=interval_minutes,
            progress_callback=progress_callback
        )
        
        # Fetch missing files
        results = await self.fetch_missing_files(
            missing_timestamps=missing,
            satellite=satellite,
            progress_callback=progress_callback,
            file_callback=file_callback,
            error_callback=error_callback
        )
        
        # Count fetched files
        fetched = sum(1 for v in results.values() if isinstance(v, Path))
        
        total = len(existing) + len(missing)
        existing_count = len(existing)
        
        return total, existing_count, fetched