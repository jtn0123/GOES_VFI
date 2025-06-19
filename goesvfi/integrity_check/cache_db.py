"""Cache database for integrity check results.

This module provides SQLite-based caching for scan results to improve performance.
"""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from goesvfi.utils import config, log

LOGGER = log.get_logger(__name__)

# Default cache location
DEFAULT_CACHE_PATH = Path(config.get_user_config_dir()) / "integrity_cache.db"


class CacheDB:
    """SQLite cache for integrity check results.

    Provides caching of scan results to improve performance and avoid
    redundant scanning operations.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the cache database."""
        self.db_path = Path(db_path) if db_path else DEFAULT_CACHE_PATH

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Connect to database
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        # Create tables
        self._create_schema()

        LOGGER.info(f"CacheDB initialized at {self.db_path}")

    def _create_schema(self) -> None:
        """Create the database schema."""
        cursor = self.conn.cursor()

        # Scan results table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS scan_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                satellite TEXT NOT NULL,
                interval_minutes INTEGER NOT NULL,
                base_dir TEXT NOT NULL,
                expected_count INTEGER,
                found_count INTEGER,
                missing_count INTEGER,
                scan_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                options TEXT,
                UNIQUE(start_date, end_date, satellite, interval_minutes, base_dir)
            )
        """
        )

        # Missing timestamps table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS missing_timestamps (
                scan_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                expected_filename TEXT,
                FOREIGN KEY (scan_id) REFERENCES scan_results(id) ON DELETE CASCADE
            )
        """
        )

        # Found timestamps table for tracking what exists
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS timestamps (
                satellite TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                file_path TEXT,
                found BOOLEAN DEFAULT 0,
                last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (satellite, timestamp)
            )
        """
        )

        # Create indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_scan_results_dates ON scan_results(start_date, end_date)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_missing_timestamps_scan ON missing_timestamps(scan_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_timestamps_satellite ON timestamps(satellite)"
        )

        self.conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def store_scan_results(
        self,
        start_date: datetime,
        end_date: datetime,
        satellite: Any,
        interval_minutes: int,
        base_dir: Path,
        missing_timestamps: List[datetime],
        expected_count: int,
        found_count: int,
        options: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Store scan results in cache.

        Returns:
            The scan_id of the stored result
        """
        cursor = self.conn.cursor()

        # Convert satellite to string if needed
        sat_str = satellite.name if hasattr(satellite, "name") else str(satellite)

        # Delete any existing scan with same parameters
        cursor.execute(
            """
            DELETE FROM scan_results
            WHERE start_date = ? AND end_date = ?
            AND satellite = ? AND interval_minutes = ? AND base_dir = ?
        """,
            (
                start_date.isoformat(),
                end_date.isoformat(),
                sat_str,
                interval_minutes,
                str(base_dir),
            ),
        )

        # Insert new scan result
        cursor.execute(
            """
            INSERT INTO scan_results
            (start_date, end_date, satellite, interval_minutes, base_dir,
             expected_count, found_count, missing_count, options)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                start_date.isoformat(),
                end_date.isoformat(),
                sat_str,
                interval_minutes,
                str(base_dir),
                expected_count,
                found_count,
                len(missing_timestamps),
                json.dumps(options) if options else None,
            ),
        )

        scan_id = cursor.lastrowid

        # Store missing timestamps
        for ts in missing_timestamps:
            # Generate expected filename based on timestamp
            expected_filename = f"{ts.strftime('%Y%m%dT%H%M%S')}.png"
            cursor.execute(
                """
                INSERT INTO missing_timestamps (scan_id, timestamp, expected_filename)
                VALUES (?, ?, ?)
            """,
                (scan_id, ts.isoformat(), expected_filename),
            )

        self.conn.commit()
        LOGGER.debug(f"Stored scan results with ID {scan_id}")
        return scan_id

    def get_cached_scan(
        self,
        start_date: datetime,
        end_date: datetime,
        satellite: Any,
        interval_minutes: int,
        base_dir: Path,
        options: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get cached scan results.

        Returns:
            Dictionary with scan results or None if not found
        """
        cursor = self.conn.cursor()

        # Convert satellite to string if needed
        sat_str = satellite.name if hasattr(satellite, "name") else str(satellite)

        # Look for matching scan
        cursor.execute(
            """
            SELECT * FROM scan_results
            WHERE start_date = ? AND end_date = ?
            AND satellite = ? AND interval_minutes = ? AND base_dir = ?
        """,
            (
                start_date.isoformat(),
                end_date.isoformat(),
                sat_str,
                interval_minutes,
                str(base_dir),
            ),
        )

        row = cursor.fetchone()
        if not row:
            return None

        # Get missing timestamps
        cursor.execute(
            """
            SELECT timestamp FROM missing_timestamps
            WHERE scan_id = ?
        """,
            (row["id"],),
        )

        missing_timestamps = [
            datetime.fromisoformat(r["timestamp"]) for r in cursor.fetchall()
        ]

        return {
            "id": row["id"],
            "start_date": datetime.fromisoformat(row["start_date"]),
            "end_date": datetime.fromisoformat(row["end_date"]),
            "satellite": sat_str,
            "interval_minutes": row["interval_minutes"],
            "base_dir": Path(row["base_dir"]),
            "expected_count": row["expected_count"],
            "found_count": row["found_count"],
            "missing_count": row["missing_count"],
            "missing_timestamps": missing_timestamps,
            "scan_timestamp": row["scan_timestamp"],
            "options": json.loads(row["options"]) if row["options"] else None,
        }

    def clear_cache(self) -> bool:
        """Clear all cached data.

        Returns:
            True if successful
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM scan_results")
            cursor.execute("DELETE FROM missing_timestamps")
            cursor.execute("DELETE FROM timestamps")
            self.conn.commit()
            LOGGER.info("Cache cleared successfully")
            return True
        except Exception as e:
            LOGGER.error(f"Error clearing cache: {e}")
            return False

    async def add_timestamp(
        self,
        timestamp: datetime,
        satellite: Any,
        file_path: str,
        found: bool,
    ) -> bool:
        """Add or update a timestamp entry in the cache.

        Returns:
            True if successful
        """
        try:
            cursor = self.conn.cursor()
            sat_str = satellite.name if hasattr(satellite, "name") else str(satellite)

            cursor.execute(
                """
                INSERT OR REPLACE INTO timestamps
                (satellite, timestamp, file_path, found, last_checked)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (sat_str, timestamp.isoformat(), file_path, int(found)),
            )

            self.conn.commit()
            return True
        except Exception as e:
            LOGGER.error(f"Error adding timestamp: {e}")
            return False

    async def timestamp_exists(self, timestamp: datetime, satellite: Any) -> bool:
        """Check if a timestamp exists in the cache.

        Returns:
            True if the timestamp exists and was found
        """
        cursor = self.conn.cursor()
        sat_str = satellite.name if hasattr(satellite, "name") else str(satellite)

        cursor.execute(
            """
            SELECT found FROM timestamps
            WHERE satellite = ? AND timestamp = ?
        """,
            (sat_str, timestamp.isoformat()),
        )

        row = cursor.fetchone()
        return bool(row and row["found"])

    async def get_timestamps(
        self, satellite: Any, start_time: datetime, end_time: datetime
    ) -> Set[datetime]:
        """Get all timestamps in a time range that were found.

        Returns:
            Set of timestamps that exist
        """
        cursor = self.conn.cursor()
        sat_str = satellite.name if hasattr(satellite, "name") else str(satellite)

        cursor.execute(
            """
            SELECT timestamp FROM timestamps
            WHERE satellite = ? AND timestamp >= ? AND timestamp <= ? AND found = 1
        """,
            (sat_str, start_time.isoformat(), end_time.isoformat()),
        )

        return {datetime.fromisoformat(row["timestamp"]) for row in cursor.fetchall()}

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache.

        Returns:
            Dictionary with cache statistics
        """
        cursor = self.conn.cursor()

        # Get scan count
        cursor.execute("SELECT COUNT(*) as count FROM scan_results")
        scan_count = cursor.fetchone()["count"]

        # Get missing count
        cursor.execute("SELECT COUNT(*) as count FROM missing_timestamps")
        missing_count = cursor.fetchone()["count"]

        # Get timestamp counts
        cursor.execute("SELECT COUNT(*) as count FROM timestamps")
        timestamp_count = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM timestamps WHERE found = 1")
        found_count = cursor.fetchone()["count"]

        # Get last scan time
        cursor.execute("SELECT MAX(scan_timestamp) as last FROM scan_results")
        last_scan = cursor.fetchone()["last"]

        # Get database size
        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

        return {
            "scan_count": scan_count,
            "missing_count": missing_count,
            "timestamp_count": timestamp_count,
            "found_count": found_count,
            "db_size_bytes": db_size,
            "schema_version": "1",
            "last_scan": last_scan,
            "last_cleanup": None,
            "last_checked": datetime.now().isoformat(),
        }

    # Methods for ThreadLocalCacheDB compatibility
    def set_cache_data(
        self,
        satellite: Any,
        missing_timestamps: List[datetime],
        remote_files: List[str],
        local_files: Set[str],
    ) -> None:
        """Set cache data for a satellite (ThreadLocalCacheDB compatibility)."""
        # For now, just store the missing timestamps
        sat_str = satellite.name if hasattr(satellite, "name") else str(satellite)
        cursor = self.conn.cursor()

        for ts in missing_timestamps:
            cursor.execute(
                """
                INSERT OR REPLACE INTO timestamps
                (satellite, timestamp, found)
                VALUES (?, ?, 0)
            """,
                (sat_str, ts.isoformat()),
            )

        self.conn.commit()

    def get_cache_data(self, satellite: Any) -> Optional[Dict[str, Any]]:
        """Get cache data for a satellite (ThreadLocalCacheDB compatibility)."""
        sat_str = satellite.name if hasattr(satellite, "name") else str(satellite)
        cursor = self.conn.cursor()

        # Get missing timestamps
        cursor.execute(
            """
            SELECT timestamp FROM timestamps
            WHERE satellite = ? AND found = 0
        """,
            (sat_str,),
        )

        missing = [
            datetime.fromisoformat(row["timestamp"]) for row in cursor.fetchall()
        ]

        if not missing:
            return None

        return {
            "missing_timestamps": missing,
            "last_scan": datetime.now(),
            "metadata": {"source": "cache"},
        }

    def reset_database(self) -> None:
        """Reset the database by clearing all tables."""
        self.clear_cache()
        LOGGER.info("Database reset completed")
