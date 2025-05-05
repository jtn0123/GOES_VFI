"""SQLite cache for integrity check results.

This module provides a simple SQLite-based cache for storing and retrieving
scan results, avoiding redundant scanning of the same directories.
"""

import os
import sqlite3
import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set, Union

from goesvfi.utils import log
from goesvfi.utils import config
from .time_index import SatellitePattern

LOGGER = log.get_logger(__name__)

# Default cache file location (in user config directory)
DEFAULT_CACHE_PATH = Path(config.get_user_config_dir()) / "integrity_cache.db"

# SQL Schema Definitions
SCHEMA_VERSION = 1

CREATE_TABLES_SQL = """
-- Scans table: Stores metadata about each scan operation
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_date TEXT NOT NULL,  -- ISO format date
    end_date TEXT NOT NULL,    -- ISO format date
    satellite TEXT NOT NULL,   -- Satellite pattern name
    interval_minutes INTEGER NOT NULL,
    base_dir TEXT NOT NULL,    -- Base directory that was scanned
    total_expected INTEGER NOT NULL,
    total_found INTEGER NOT NULL,
    scan_time TEXT NOT NULL,   -- ISO format date of when scan was performed
    options TEXT               -- JSON string of additional options
);

-- Missing timestamps table: Stores individual missing timestamps
CREATE TABLE IF NOT EXISTS missing_timestamps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,   -- ISO format timestamp
    expected_filename TEXT NOT NULL,
    FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
);

-- Cache metadata table: Stores cache version and settings
CREATE TABLE IF NOT EXISTS cache_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Timestamps table: Stores information about individual timestamps
CREATE TABLE IF NOT EXISTS timestamps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,   -- ISO format timestamp
    satellite TEXT NOT NULL,   -- Satellite pattern name
    file_path TEXT,           -- Path to the file if found, empty if not found
    found INTEGER NOT NULL,    -- 1 if found, 0 if not found
    last_checked TEXT NOT NULL, -- ISO format date of when it was last checked
    UNIQUE(timestamp, satellite)
);
"""

# Initialize metadata with schema version - separate for execute() calls
INIT_SCHEMA_VERSION_SQL = "INSERT OR REPLACE INTO cache_metadata (key, value) VALUES ('schema_version', ?)"
INIT_LAST_CLEANUP_SQL = "INSERT OR REPLACE INTO cache_metadata (key, value) VALUES ('last_cleanup', ?)"


class CacheDB:
    """SQLite cache for integrity check results."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the cache database.
        
        Args:
            db_path: Path to the SQLite database file, or None to use default
        """
        self.db_path = db_path or DEFAULT_CACHE_PATH
        self.conn: Optional[sqlite3.Connection] = None
        
        # Ensure parent directory exists
        os.makedirs(self.db_path.parent, exist_ok=True)
        
        # Initialize the database
        self._connect()
        self._init_schema()
    
    def _connect(self) -> None:
        """Connect to the SQLite database."""
        try:
            self.conn = sqlite3.connect(str(self.db_path))
            # Enable foreign keys support
            self.conn.execute("PRAGMA foreign_keys = ON")
            # Configure connection to return rows as dictionaries
            self.conn.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            LOGGER.error(f"Error connecting to cache database: {e}")
            raise
    
    def _init_schema(self) -> None:
        """Initialize the database schema if needed."""
        if not self.conn:
            LOGGER.error("Cannot initialize schema: No database connection")
            return
            
        try:
            # Create tables
            self.conn.executescript(CREATE_TABLES_SQL)
            
            # Initialize metadata using separate statements
            now_iso = datetime.now().isoformat()
            self.conn.execute(INIT_SCHEMA_VERSION_SQL, (SCHEMA_VERSION,))
            self.conn.execute(INIT_LAST_CLEANUP_SQL, (now_iso,))
            
            self.conn.commit()
            LOGGER.info(f"Cache database initialized at {self.db_path}")
        except sqlite3.Error as e:
            LOGGER.error(f"Error initializing cache database schema: {e}")
            raise
    
    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def store_scan_results(self,
                          start_date: datetime,
                          end_date: datetime,
                          satellite: SatellitePattern,
                          interval_minutes: int,
                          base_dir: Path,
                          missing_timestamps: List[datetime],
                          expected_count: int,
                          found_count: int,
                          options: Optional[Dict[str, Any]] = None) -> int:
        """
        Store scan results in the cache.
        
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
        if not self.conn:
            LOGGER.error("Cannot store results: No database connection")
            return -1
            
        try:
            # Convert options to JSON if present
            options_json = json.dumps(options) if options else "{}"
            
            # Insert scan record
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO scans 
                (start_date, end_date, satellite, interval_minutes, base_dir, 
                 total_expected, total_found, scan_time, options)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                start_date.isoformat(),
                end_date.isoformat(),
                satellite.name,
                interval_minutes,
                str(base_dir),
                expected_count,
                found_count,
                datetime.now().isoformat(),
                options_json
            ))
            
            scan_id = cursor.lastrowid
            
            # Insert missing timestamps
            for dt in missing_timestamps:
                expected_filename = f"{dt.strftime('%Y%m%dT%H%M%S')}.png"  # Simplified
                cursor.execute("""
                    INSERT INTO missing_timestamps 
                    (scan_id, timestamp, expected_filename)
                    VALUES (?, ?, ?)
                """, (
                    scan_id,
                    dt.isoformat(),
                    expected_filename
                ))
            
            self.conn.commit()
            LOGGER.info(f"Stored scan results with ID {scan_id}, {len(missing_timestamps)} missing timestamps")
            return scan_id
            
        except sqlite3.Error as e:
            LOGGER.error(f"Error storing scan results: {e}")
            if self.conn:
                self.conn.rollback()
            return -1
    
    def get_cached_scan(self,
                       start_date: datetime,
                       end_date: datetime,
                       satellite: SatellitePattern,
                       interval_minutes: int,
                       base_dir: Path,
                       options: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Check if a scan with the given parameters exists in the cache.
        
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
        if not self.conn:
            LOGGER.error("Cannot query cache: No database connection")
            return None
            
        try:
            # Convert options to JSON if present
            options_json = json.dumps(options) if options else "{}"
            
            # Look for a matching scan
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT id, scan_time, total_expected, total_found
                FROM scans
                WHERE start_date = ? 
                AND end_date = ?
                AND satellite = ?
                AND interval_minutes = ?
                AND base_dir = ?
                AND options = ?
                ORDER BY scan_time DESC
                LIMIT 1
            """, (
                start_date.isoformat(),
                end_date.isoformat(),
                satellite.name,
                interval_minutes,
                str(base_dir),
                options_json
            ))
            
            row = cursor.fetchone()
            if not row:
                return None
                
            scan_id = row['id']
            
            # Get missing timestamps for this scan
            cursor.execute("""
                SELECT timestamp, expected_filename
                FROM missing_timestamps
                WHERE scan_id = ?
                ORDER BY timestamp
            """, (scan_id,))
            
            missing = []
            for missing_row in cursor.fetchall():
                missing.append({
                    'timestamp': datetime.fromisoformat(missing_row['timestamp']),
                    'expected_filename': missing_row['expected_filename']
                })
            
            # Prepare result dictionary
            result = {
                'id': scan_id,
                'scan_time': datetime.fromisoformat(row['scan_time']),
                'total_expected': row['total_expected'],
                'total_found': row['total_found'],
                'missing': missing
            }
            
            LOGGER.info(f"Found cached scan results with ID {scan_id}, {len(missing)} missing timestamps")
            return result
            
        except sqlite3.Error as e:
            LOGGER.error(f"Error querying cache: {e}")
            return None
    
    def clear_cache(self) -> bool:
        """
        Clear all data from the cache.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.conn:
            LOGGER.error("Cannot clear cache: No database connection")
            return False
            
        try:
            self.conn.execute("DELETE FROM missing_timestamps")
            self.conn.execute("DELETE FROM scans")
            now_iso = datetime.now().isoformat()
            self.conn.execute(
                "INSERT OR REPLACE INTO cache_metadata (key, value) VALUES ('last_cleanup', ?)",
                (now_iso,)
            )
            self.conn.commit()
            LOGGER.info("Cache cleared successfully")
            return True
        except sqlite3.Error as e:
            LOGGER.error(f"Error clearing cache: {e}")
            if self.conn:
                self.conn.rollback()
            return False
    
    async def add_timestamp(
        self,
        timestamp: datetime,
        satellite: SatellitePattern,
        file_path: str,
        found: bool
    ) -> bool:
        """
        Add or update a timestamp entry in the cache.
        
        Args:
            timestamp: The timestamp to add
            satellite: The satellite pattern enum
            file_path: Path to the file (or empty if not found)
            found: True if the file was found, False otherwise
            
        Returns:
            True if successful, False otherwise
        """
        if not self.conn:
            LOGGER.error("Cannot add timestamp: No database connection")
            return False
            
        try:
            now_iso = datetime.now().isoformat()
            found_int = 1 if found else 0
            
            self.conn.execute("""
                INSERT OR REPLACE INTO timestamps 
                (timestamp, satellite, file_path, found, last_checked)
                VALUES (?, ?, ?, ?, ?)
            """, (
                timestamp.isoformat(),
                satellite.name,
                file_path,
                found_int,
                now_iso
            ))
            
            self.conn.commit()
            return True
            
        except sqlite3.Error as e:
            LOGGER.error(f"Error adding timestamp to cache: {e}")
            if self.conn:
                self.conn.rollback()
            return False
    
    async def timestamp_exists(
        self,
        timestamp: datetime,
        satellite: SatellitePattern
    ) -> bool:
        """
        Check if a timestamp exists in the cache and was found.
        
        Args:
            timestamp: The timestamp to check
            satellite: The satellite pattern enum
            
        Returns:
            True if the timestamp exists and was found, False otherwise
        """
        if not self.conn:
            LOGGER.error("Cannot check timestamp: No database connection")
            return False
            
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT found FROM timestamps
                WHERE timestamp = ? AND satellite = ?
            """, (
                timestamp.isoformat(),
                satellite.name
            ))
            
            row = cursor.fetchone()
            if not row:
                return False
                
            return row['found'] == 1
            
        except sqlite3.Error as e:
            LOGGER.error(f"Error checking timestamp in cache: {e}")
            return False
    
    async def get_timestamps(
        self,
        satellite: SatellitePattern,
        start_time: datetime,
        end_time: datetime
    ) -> Set[datetime]:
        """
        Get all timestamps in a time range that were found.
        
        Args:
            satellite: The satellite pattern enum
            start_time: Start of the time range
            end_time: End of the time range
            
        Returns:
            Set of timestamps that were found in the cache
        """
        if not self.conn:
            LOGGER.error("Cannot get timestamps: No database connection")
            return set()
            
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT timestamp FROM timestamps
                WHERE satellite = ? AND found = 1
                AND timestamp >= ? AND timestamp <= ?
            """, (
                satellite.name,
                start_time.isoformat(),
                end_time.isoformat()
            ))
            
            timestamps = set()
            for row in cursor.fetchall():
                timestamps.add(datetime.fromisoformat(row['timestamp']))
                
            return timestamps
            
        except sqlite3.Error as e:
            LOGGER.error(f"Error getting timestamps from cache: {e}")
            return set()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the cache.
        
        Returns:
            A dictionary with cache statistics
        """
        if not self.conn:
            LOGGER.error("Cannot get cache stats: No database connection")
            return {'error': 'No database connection'}
            
        try:
            cursor = self.conn.cursor()
            
            # Get scan count
            cursor.execute("SELECT COUNT(*) as count FROM scans")
            scan_count = cursor.fetchone()['count']
            
            # Get missing timestamp count
            cursor.execute("SELECT COUNT(*) as count FROM missing_timestamps")
            missing_count = cursor.fetchone()['count']
            
            # Get timestamp count
            cursor.execute("SELECT COUNT(*) as count FROM timestamps")
            timestamp_count = cursor.fetchone()['count']
            
            # Get found timestamp count
            cursor.execute("SELECT COUNT(*) as count FROM timestamps WHERE found = 1")
            found_count = cursor.fetchone()['count']
            
            # Get database file size
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            
            # Get last scan time
            cursor.execute("SELECT MAX(scan_time) as last_scan FROM scans")
            last_scan = cursor.fetchone()['last_scan']
            last_scan_dt = datetime.fromisoformat(last_scan) if last_scan else None
            
            # Get schema version
            cursor.execute("SELECT value FROM cache_metadata WHERE key = 'schema_version'")
            schema_version = cursor.fetchone()['value']
            
            # Get last cleanup time
            cursor.execute("SELECT value FROM cache_metadata WHERE key = 'last_cleanup'")
            last_cleanup = cursor.fetchone()['value']
            last_cleanup_dt = datetime.fromisoformat(last_cleanup) if last_cleanup else None
            
            # Get last checked timestamp
            cursor.execute("SELECT MAX(last_checked) as last_checked FROM timestamps")
            last_checked = cursor.fetchone()['last_checked']
            last_checked_dt = datetime.fromisoformat(last_checked) if last_checked else None
            
            return {
                'scan_count': scan_count,
                'missing_count': missing_count,
                'timestamp_count': timestamp_count,
                'found_count': found_count,
                'db_size_bytes': db_size,
                'db_size_mb': round(db_size / (1024 * 1024), 2),
                'last_scan': last_scan_dt,
                'last_checked': last_checked_dt,
                'schema_version': schema_version,
                'last_cleanup': last_cleanup_dt,
                'db_path': str(self.db_path)
            }
            
        except sqlite3.Error as e:
            LOGGER.error(f"Error getting cache stats: {e}")
            return {'error': str(e)}
    
    def __enter__(self):
        """Enter context manager."""
        return self
        
    def __exit__(self, exc_type, exc_value, traceback):
        """Exit context manager and close connection."""
        self.close()