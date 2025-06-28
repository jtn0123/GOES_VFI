"""Thread-safe SQLite database manager for integrity check.

This module provides a thread-local SQLite cache solution for the integrity check
system, solving the SQLite thread safety issues by creating per-thread database
connections.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import threading
from types import TracebackType
from typing import Any, Self

from goesvfi.integrity_check.cache_db import CacheDB
from goesvfi.integrity_check.time_index import SatellitePattern
from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class ThreadLocalCacheDB:
    """Thread-local SQLite cache for integrity check results.

    This class provides thread-safe access to CacheDB by creating
    separate CacheDB instances for each thread.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize the thread-local cache database.

        Args:
            db_path: Optional path to the database file
        """
        self.db_path = db_path
        self._lock = threading.Lock()
        self._local = threading.local()
        self._connections: dict[int, CacheDB] = {}

        # Create initial connection for the main thread
        self.get_db()

        LOGGER.info("ThreadLocalCacheDB initialized with path: %s", db_path)

    def __enter__(self) -> Self:
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager."""
        self.close_all()

    def get_db(self) -> CacheDB:
        """Get or create a thread-local database connection.

        Returns:
            CacheDB instance for the current thread
        """
        # Fast path: check if we already have a connection for this thread
        if hasattr(self._local, "db"):
            return self._local.db  # type: ignore

        # Slow path: create a new connection
        with self._lock:
            thread_id = threading.get_ident()
            if thread_id not in self._connections:
                self._connections[thread_id] = CacheDB(db_path=self.db_path)
            db_instance = self._connections[thread_id]
            self._local.db = db_instance
            return db_instance

    def _get_connection(self) -> CacheDB:
        """Alias for get_db for compatibility."""
        return self.get_db()

    def close_all(self) -> None:
        """Close all database connections."""
        with self._lock:
            for conn in self._connections.values():
                try:
                    conn.close()
                except Exception as e:
                    LOGGER.exception("Error closing connection: %s", e)
            self._connections.clear()

        # Also clear thread-local storage if present
        if hasattr(self._local, "db"):
            del self._local.db

    # Delegate methods to the thread-local CacheDB instance
    def set_cache_data(
        self,
        satellite: SatellitePattern,
        missing_timestamps: list[datetime],
        remote_files: list[str],
        local_files: set[str],
    ) -> None:
        """Set cache data."""
        db = self.get_db()
        db.set_cache_data(satellite, missing_timestamps, remote_files, local_files)

    def get_cache_data(self, satellite: SatellitePattern) -> dict[str, Any] | None:
        """Get cache data."""
        db = self.get_db()
        return db.get_cache_data(satellite)

    def clear_cache(self) -> None:
        """Clear all cache data."""
        db = self.get_db()
        db.clear_cache()

    def close_current_thread(self) -> None:
        """Close the database connection for the current thread only."""
        thread_id = threading.get_ident()
        with self._lock:
            if thread_id in self._connections:
                try:
                    self._connections[thread_id].close()
                    del self._connections[thread_id]
                except Exception as e:
                    LOGGER.exception("Error closing connection: %s", e)

        if hasattr(self._local, "db"):
            del self._local.db

    def close(self) -> None:
        """Close all database connections."""
        self.close_all()

    # Async methods for compatibility with tests
    async def add_timestamp(
        self,
        timestamp: datetime,
        satellite: SatellitePattern,
        file_path: str,
        found: bool,
    ) -> bool:
        """Add timestamp via thread-local connection."""
        db = self.get_db()
        return await db.add_timestamp(timestamp, satellite, file_path, found)

    async def get_timestamps(
        self,
        satellite: SatellitePattern,
        start_time: datetime,
        end_time: datetime,
    ) -> list[datetime]:
        """Get timestamps via thread-local connection."""
        db = self.get_db()
        result = await db.get_timestamps(satellite, start_time, end_time)
        return list(result)  # Convert set to list

    async def timestamp_exists(self, timestamp: datetime, satellite: SatellitePattern) -> bool:
        """Check if timestamp exists via thread-local connection."""
        db = self.get_db()
        return await db.timestamp_exists(timestamp, satellite)

    # General entry methods for thread-safe caching
    def add_entry(
        self,
        filepath: str,
        file_hash: str,
        file_size: int,
        timestamp: datetime,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a general cache entry via thread-local connection."""
        db = self.get_db()
        db.add_entry(filepath, file_hash, file_size, timestamp, metadata)

    def get_entry(self, filepath: str) -> dict[str, Any] | None:
        """Get a cache entry via thread-local connection."""
        db = self.get_db()
        return db.get_entry(filepath)

    def reset_database(self) -> None:
        """Reset the database via thread-local connection."""
        db = self.get_db()
        if hasattr(db, "reset_database"):
            db.reset_database()
        else:
            # Fallback to clear_cache if reset_database doesn't exist
            db.clear_cache()
