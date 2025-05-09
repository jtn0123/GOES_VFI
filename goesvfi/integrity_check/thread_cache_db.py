from __future__ import annotations

"""Thread-safe SQLite database manager for integrity check.

This module provides a thread-local SQLite cache solution for the integrity check
system, solving the SQLite thread safety issues by creating per-thread database
connections.
"""

import os
import threading
import logging
from pathlib import Path
from typing import Dict, Optional, Set, List, Any, Tuple, Union, Callable, Type, TypeVar, cast
from types import TracebackType

from goesvfi.utils import log
from goesvfi.integrity_check.cache_db import CacheDB
from goesvfi.integrity_check.time_index import SatellitePattern
from datetime import datetime

LOGGER = log.get_logger(__name__)

class ThreadLocalCacheDB:
    """Thread-local SQLite cache for integrity check results.
    
    This class manages thread-local CacheDB instances, ensuring that
    each thread uses its own SQLite connection. This solves the SQLite
    thread safety issue where connections must be used only from the
    thread where they were created.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the thread-local cache manager.
        
        Args:
            db_path: Path to the SQLite database file, or None to use default
        """
        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.RLock()
        self._main_thread_id = threading.get_ident()
        self._connections: Dict[int, CacheDB] = {}
        
        # Create the main thread connection immediately
        self._get_connection()
        
        LOGGER.info(f"Initialized thread-local cache DB manager with path: {db_path}")
    
    def _get_connection(self) -> CacheDB:
        """Get or create a thread-local CacheDB instance.
        
        Returns:
            A CacheDB instance for the current thread
        """
        thread_id = threading.get_ident()
        
        # Fast path: check if we already have a connection for this thread
        if hasattr(self._local, 'db'):
            # Explicitly cast to CacheDB to fix mypy no-any-return error
            return self._local.db if isinstance(self._local.db, CacheDB) else CacheDB(db_path=self.db_path)
        
        # Slow path: create a new connection with thread safety
        with self._lock:
            # Double-check inside the lock
            if hasattr(self._local, 'db'):
                # Explicitly cast to CacheDB to fix mypy no-any-return error
                return self._local.db if isinstance(self._local.db, CacheDB) else CacheDB(db_path=self.db_path)
                
            LOGGER.debug(f"Creating new CacheDB connection for thread ID: {thread_id}")
            
            # Create and store a new connection for this thread
            self._local.db = CacheDB(db_path=self.db_path)
            self._connections[thread_id] = self._local.db
            
            return self._local.db
    
    def close(self) -> None:
        """Close all database connections.
        
        Note: This will only safely close the current thread's connection. 
        Other thread connections will be noted but not attempted to be closed
        from this thread as that would cause a SQLite thread safety error.
        """
        with self._lock:
            LOGGER.debug(f"Closing all CacheDB connections ({len(self._connections)} connections)")
            
            current_thread_id = threading.get_ident()
            
            # Close the connection for the current thread if it exists
            if current_thread_id in self._connections:
                try:
                    LOGGER.debug(f"Closing connection for current thread ID: {current_thread_id}")
                    self._connections[current_thread_id].close()
                    del self._connections[current_thread_id]
                except Exception as e:
                    LOGGER.error(f"Error closing connection for current thread ID {current_thread_id}: {e}")
            
            # Log information about other thread connections but don't try to close them
            other_threads = [tid for tid in self._connections.keys() if tid != current_thread_id]
            if other_threads:
                LOGGER.debug(f"Note: {len(other_threads)} connections from other threads will be abandoned")
                for tid in other_threads:
                    LOGGER.debug(f"Thread {tid} connection will be abandoned (cannot be closed from thread {current_thread_id})")
            
            # Clear the connection cache - connections will be closed by the garbage collector
            self._connections.clear()
            
            # Clear thread-local for the current thread
            if hasattr(self._local, 'db'):
                delattr(self._local, 'db')
    
    def close_current_thread(self) -> None:
        """Close the database connection for the current thread only."""
        thread_id = threading.get_ident()
        
        with self._lock:
            if thread_id in self._connections:
                try:
                    LOGGER.debug(f"Closing connection for current thread ID: {thread_id}")
                    self._connections[thread_id].close()
                    del self._connections[thread_id]
                except Exception as e:
                    LOGGER.error(f"Error closing connection for thread ID {thread_id}: {e}")
            
            # Clear thread-local for the current thread
            if hasattr(self._local, 'db'):
                delattr(self._local, 'db')
    
    # Delegate all CacheDB methods to the thread-local instance
    
    async def add_timestamp(self, timestamp: datetime, satellite: SatellitePattern, 
                         file_path: str, found: bool) -> bool:
        """Add or update a timestamp entry in the cache.
        
        Thread-safe: This method delegates to a thread-local CacheDB instance.
        
        Args:
            timestamp: The timestamp to add
            satellite: The satellite pattern enum
            file_path: Path to the file (or empty if not found)
            found: True if the file was found, False otherwise
            
        Returns:
            True if successful, False otherwise
        """
        return await self._get_connection().add_timestamp(
            timestamp=timestamp,
            satellite=satellite,
            file_path=file_path,
            found=found
        )
    
    async def timestamp_exists(self, timestamp: datetime, satellite: SatellitePattern) -> bool:
        """Check if a timestamp exists in the cache and was found.
        
        Thread-safe: This method delegates to a thread-local CacheDB instance.
        
        Args:
            timestamp: The timestamp to check
            satellite: The satellite pattern enum
            
        Returns:
            True if the timestamp exists and was found, False otherwise
        """
        return await self._get_connection().timestamp_exists(
            timestamp=timestamp,
            satellite=satellite
        )
    
    async def get_timestamps(self, satellite: SatellitePattern, 
                          start_time: datetime, end_time: datetime) -> Set[datetime]:
        """Get all timestamps in a time range that were found.
        
        Thread-safe: This method delegates to a thread-local CacheDB instance.
        
        Args:
            satellite: The satellite pattern enum
            start_time: Start of the time range
            end_time: End of the time range
            
        Returns:
            Set of timestamps that were found in the cache
        """
        return await self._get_connection().get_timestamps(
            satellite=satellite,
            start_time=start_time,
            end_time=end_time
        )
    
    def store_scan_results(self, start_date: datetime, end_date: datetime,
                         satellite: SatellitePattern, interval_minutes: int,
                         base_dir: Path, missing_timestamps: List[datetime],
                         expected_count: int, found_count: int,
                         options: Optional[Dict[str, Any]] = None) -> int:
        """Store scan results in the cache.
        
        Thread-safe: This method delegates to a thread-local CacheDB instance.
        
        Args:
            start_date: Start date of the scan
            end_date: End date of the scan
            satellite: Satellite pattern used
            interval_minutes: Time interval in minutes
            base_dir: Base directory that was scanned
            missing_timestamps: List of missing timestamps
            expected_count: Total expected timestamps
            found_count: Total found timestamps
            options: Additional scan options as a dictionary
            
        Returns:
            The ID of the inserted scan record
        """
        return self._get_connection().store_scan_results(
            start_date=start_date,
            end_date=end_date,
            satellite=satellite,
            interval_minutes=interval_minutes,
            base_dir=base_dir,
            missing_timestamps=missing_timestamps,
            expected_count=expected_count,
            found_count=found_count,
            options=options
        )
    
    def get_cached_scan(self, start_date: datetime, end_date: datetime,
                      satellite: SatellitePattern, interval_minutes: int,
                      base_dir: Path, options: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Check if a scan with the given parameters exists in the cache.
        
        Thread-safe: This method delegates to a thread-local CacheDB instance.
        
        Args:
            start_date: Start date of the scan
            end_date: End date of the scan
            satellite: Satellite pattern used
            interval_minutes: Time interval in minutes
            base_dir: Base directory that was scanned
            options: Additional scan options as a dictionary
            
        Returns:
            A dictionary of scan results if found, None otherwise
        """
        return self._get_connection().get_cached_scan(
            start_date=start_date,
            end_date=end_date,
            satellite=satellite,
            interval_minutes=interval_minutes,
            base_dir=base_dir,
            options=options
        )
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache.
        
        Thread-safe: This method delegates to a thread-local CacheDB instance.
        
        Returns:
            A dictionary with cache statistics
        """
        return self._get_connection().get_cache_stats()
    
    def clear_cache(self) -> bool:
        """Clear all data from the cache.
        
        Thread-safe: This method delegates to a thread-local CacheDB instance.
        
        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            main_conn = self._get_connection()
            result = main_conn.clear_cache()
            
            # After clearing cache, close and recreate all connections to ensure fresh state
            self.close()
            self._get_connection()  # Recreate main thread connection
            
            return result
    
    def __enter__(self) -> Any:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]],
                 exc_val: Optional[BaseException],
                 exc_tb: Optional[TracebackType]) -> None:
        """Context manager exit."""
        self.close()