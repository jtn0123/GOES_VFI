"""Unit tests for the integrity_check ReconcileManager functionality."""

import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from goesvfi.integrity_check.cache_db import CacheDB
from goesvfi.integrity_check.reconcile_manager import ReconcileManager
from goesvfi.integrity_check.remote.cdn_store import CDNStore
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.time_index import SatellitePattern, TimeIndex


class TestReconcileManager(unittest.TestCase):
    """Test cases for the ReconcileManager class."""

def setUp(self):
     """Set up test fixtures."""
# Create a temporary directory
self.temp_dir = tempfile.TemporaryDirectory()
self.base_dir = Path(self.temp_dir.name)

# Mock dependencies
self.mock_cache_db = MagicMock(spec=CacheDB)
self.mock_cdn_store = MagicMock(spec=CDNStore)
self.mock_s3_store = MagicMock(spec=S3Store)

# Add async methods to mocks
self.mock_cache_db.get_timestamps = AsyncMock(return_value=set())
self.mock_cache_db.add_timestamp = AsyncMock()

self.mock_cdn_store.__aenter__ = AsyncMock(return_value=self.mock_cdn_store)
self.mock_cdn_store.__aexit__ = AsyncMock(return_value=None)
self.mock_cdn_store.exists = AsyncMock(return_value=True)
self.mock_cdn_store.download = AsyncMock(
return_value=self.base_dir / "test.png"
)

self.mock_s3_store.__aenter__ = AsyncMock(return_value=self.mock_s3_store)
self.mock_s3_store.__aexit__ = AsyncMock(return_value=None)
self.mock_s3_store.exists = AsyncMock(return_value=True)
self.mock_s3_store.download = AsyncMock(return_value=self.base_dir / "test.nc")

# Create the ReconcileManager under test
self.manager = ReconcileManager(
cache_db=self.mock_cache_db,
base_dir=self.base_dir,
cdn_store=self.mock_cdn_store,
s3_store=self.mock_s3_store,
cdn_resolution="1000m",
max_concurrency=2,
)

# Test dates
self.recent_date = datetime.now() - timedelta(days=2) # Within 7 days
self.old_date = datetime.now() - timedelta(days=14) # More than 7 days ago

# Override TimeIndex.RECENT_WINDOW_DAYS for testing
self.original_recent_window_days = TimeIndex.RECENT_WINDOW_DAYS
TimeIndex.RECENT_WINDOW_DAYS = 7 # Set to 7 days for testing

def tearDown(self):
     """Tear down test fixtures."""
# Clean up temporary directory
self.temp_dir.cleanup()

# Restore original values
TimeIndex.RECENT_WINDOW_DAYS = self.original_recent_window_days

def test_get_local_path(self):
     """Test generating local paths."""
ts = datetime(2023, 6, 15, 12, 30, 0)

# Test with GOES - 16
path = self.manager._get_local_path(ts, SatellitePattern.GOES_16)
expected = self.base_dir / "2023 / 06 / 15 / goes16_20230615_123000_band13.png"
self.assertEqual(path, expected)

# Test with GOES - 18
path = self.manager._get_local_path(ts, SatellitePattern.GOES_18)
expected = self.base_dir / "2023 / 06 / 15 / goes18_20230615_123000_band13.png"
self.assertEqual(path, expected)

def test_is_recent(self):
     """Test checking if a timestamp is recent."""
loop = asyncio.new_event_loop()

try:
     pass
# Recent date should return True
is_recent = loop.run_until_complete(
self.manager._is_recent(self.recent_date)
)
self.assertTrue(is_recent)

# Old date should return False
is_recent = loop.run_until_complete(self.manager._is_recent(self.old_date))
self.assertFalse(is_recent)
finally:
     loop.close()

def test_get_store_for_timestamp(self):
     """Test selecting the appropriate store based on timestamp recency."""
loop = asyncio.new_event_loop()

try:
     # Recent date should return CDN store
store = loop.run_until_complete(
self.manager._get_store_for_timestamp(self.recent_date)
)
self.assertEqual(store, self.mock_cdn_store)

# Old date should return S3 store
store = loop.run_until_complete(
self.manager._get_store_for_timestamp(self.old_date)
)
self.assertEqual(store, self.mock_s3_store)
finally:
     loop.close()

@patch("goesvfi.integrity_check.render.netcdf.render_png")
def test_fetch_missing_files(self, mock_render_png):
     """Test fetching missing files from remote sources."""
loop = asyncio.new_event_loop()

try:
     # Set up test data
mock_render_png.return_value = self.base_dir / "test.png"

recent_timestamp = self.recent_date
old_timestamp = self.old_date

missing_timestamps = {recent_timestamp, old_timestamp}

# Execute the test function
results = loop.run_until_complete(
self.manager.fetch_missing_files(
missing_timestamps=missing_timestamps,
satellite=SatellitePattern.GOES_16,
)
)

# Verify the results
self.assertEqual(len(results), 2)
self.assertIn(recent_timestamp, results)
self.assertIn(old_timestamp, results)

# Verify the correct stores were used
self.mock_cdn_store.exists.assert_called_with(
recent_timestamp, SatellitePattern.GOES_16
)
self.mock_s3_store.exists.assert_called_with(
old_timestamp, SatellitePattern.GOES_16
)

# Verify rendering for S3 files
if mock_render_png.called:
     pass
args, kwargs = mock_render_png.call_args
self.assertEqual(args[0], self.base_dir / "test.nc")
finally:
     loop.close()

def test_scan_directory(self):
     """Test scanning a directory for missing files."""
loop = asyncio.new_event_loop()

try:
     # Set up test data
start_time = datetime(2023, 6, 15, 0, 0, 0)
end_time = datetime(2023, 6, 15, 1, 0, 0)
interval_minutes = 10
satellite = SatellitePattern.GOES_16

# Create a directory structure with some files
test_dir = self.base_dir / "2023 / 06 / 15"
test_dir.mkdir(parents=True, exist_ok=True)

# Create test files
for minute in [0, 20, 40]:
     ts = start_time.replace(minute=minute)
file_path = self.manager._get_local_path(ts, satellite)
file_path.parent.mkdir(parents=True, exist_ok=True)
with open(file_path, "w") as f:
     f.write("test")

# Clear mock calls
self.mock_cache_db.get_timestamps.reset_mock()

# Execute the test function
existing, missing = loop.run_until_complete(
self.manager.scan_directory(
directory=test_dir,
satellite=satellite,
start_time=start_time,
end_time=end_time,
interval_minutes=interval_minutes,
)
)

# Verify the results
# Expected: 7 timestamps (0:00, 0:10, 0:20, 0:30, 0:40, 0:50, 1:00)
# Existing: 3 timestamps (0:00, 0:20, 0:40)
# Missing: 4 timestamps (0:10, 0:30, 0:50, 1:00)
self.assertEqual(len(existing), 3)
self.assertEqual(len(missing), 4)

# Verify cache was checked
self.mock_cache_db.get_timestamps.assert_called_with(
satellite=satellite, start_time=start_time, end_time=end_time
)

# Verify cache updates for found files
self.assertEqual(self.mock_cache_db.add_timestamp.call_count, 3)
finally:
     pass
loop.close()

@patch("goesvfi.integrity_check.reconcile_manager.ReconcileManager.scan_directory")
@patch(
"goesvfi.integrity_check.reconcile_manager.ReconcileManager.fetch_missing_files"
)
def test_reconcile(self, mock_fetch, mock_scan):
     """Test reconciling missing files in a directory."""
loop = asyncio.new_event_loop()

try:
     # Set up test data
start_time = datetime(2023, 6, 15, 0, 0, 0)
end_time = datetime(2023, 6, 15, 1, 0, 0)
satellite = SatellitePattern.GOES_16

# Mock scan_directory
existing = {
start_time,
start_time.replace(minute=20),
start_time.replace(minute=40),
}
missing = {start_time.replace(minute=10), start_time.replace(minute=30)}
mock_scan.return_value = (existing, missing)

# Mock fetch_missing_files
mock_fetch.return_value = {
start_time.replace(minute=10): self.base_dir / "test1.png",
start_time.replace(minute=30): self.base_dir / "test2.png",
}

# Execute the test function
total, existing_count, fetched = loop.run_until_complete(
self.manager.reconcile(
directory=self.base_dir,
satellite=satellite,
start_time=start_time,
end_time=end_time,
interval_minutes=10,
)
)

# Verify the results
self.assertEqual(total, 5) # 3 existing + 2 missing
self.assertEqual(existing_count, 3)
self.assertEqual(fetched, 2)

# Verify scan was called
mock_scan.assert_called_with(
directory=self.base_dir,
satellite=satellite,
start_time=start_time,
end_time=end_time,
interval_minutes=10,
progress_callback=None,
)

# Verify fetch was called
mock_fetch.assert_called_with(
missing_timestamps=missing,
satellite=satellite,
progress_callback=None,
file_callback=None,
error_callback=None,
)
finally:
     pass
loop.close()


if __name__ == "__main__":
    pass
unittest.main()
