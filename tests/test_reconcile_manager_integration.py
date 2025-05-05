"""Integration tests for the ReconcileManager with real filesystem operations."""

import unittest
import asyncio
import tempfile
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from goesvfi.integrity_check.time_index import TimeIndex, SatellitePattern
from goesvfi.integrity_check.cache_db import CacheDB
from goesvfi.integrity_check.reconcile_manager import ReconcileManager
from goesvfi.integrity_check.remote.cdn_store import CDNStore
from goesvfi.integrity_check.remote.s3_store import S3Store


class TestReconcileManagerIntegration(unittest.TestCase):
    """Integration tests for ReconcileManager that actually create files."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for testing
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        
        # Create cache DB in temp directory
        self.cache_db_path = self.base_dir / "test_cache.db"
        self.cache_db = CacheDB(self.cache_db_path)
        
        # Create mock CDN and S3 stores
        self.cdn_store = MagicMock(spec=CDNStore)
        self.s3_store = MagicMock(spec=S3Store)
        
        # Set up async methods for mocks
        self.cdn_store.__aenter__ = AsyncMock(return_value=self.cdn_store)
        self.cdn_store.__aexit__ = AsyncMock(return_value=None)
        self.cdn_store.exists = AsyncMock(return_value=True)
        self.cdn_store.download = AsyncMock(side_effect=self._mock_cdn_download)
        
        self.s3_store.__aenter__ = AsyncMock(return_value=self.s3_store)
        self.s3_store.__aexit__ = AsyncMock(return_value=None)
        self.s3_store.exists = AsyncMock(return_value=True)
        self.s3_store.download = AsyncMock(side_effect=self._mock_s3_download)
        
        # Create the ReconcileManager under test
        self.manager = ReconcileManager(
            cache_db=self.cache_db,
            base_dir=self.base_dir,
            cdn_store=self.cdn_store,
            s3_store=self.s3_store,
            max_concurrency=2
        )
        
        # Set up test dates
        self.now = datetime.now()
        self.recent_date = self.now - timedelta(days=2)  # Within window
        self.old_date = self.now - timedelta(days=14)  # Outside window
        
        # Test satellite
        self.satellite = SatellitePattern.GOES_16
        
        # Override TimeIndex.RECENT_WINDOW_DAYS for testing
        self.original_window_days = TimeIndex.RECENT_WINDOW_DAYS
        TimeIndex.RECENT_WINDOW_DAYS = 7

    def tearDown(self):
        """Tear down test fixtures."""
        # Clean up temporary directory
        self.temp_dir.cleanup()
        
        # Restore original TimeIndex values
        TimeIndex.RECENT_WINDOW_DAYS = self.original_window_days

    async def _mock_cdn_download(self, ts, satellite, dest_path):
        """Mock CDN download by creating a fake image file."""
        # Ensure parent directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create a small test file
        with open(dest_path, 'w') as f:
            f.write(f"CDN test file for {ts.isoformat()} satellite {satellite.name}")
        
        return dest_path

    async def _mock_s3_download(self, ts, satellite, dest_path):
        """Mock S3 download by creating a fake NetCDF file."""
        # Ensure parent directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create a small test file with .nc extension
        dest_path = dest_path.with_suffix('.nc')
        with open(dest_path, 'w') as f:
            f.write(f"S3 NetCDF test file for {ts.isoformat()} satellite {satellite.name}")
        
        return dest_path

    def _create_test_files(self, timestamps, satellite):
        """Create test files in the filesystem."""
        for ts in timestamps:
            # Get path
            path = self.manager._get_local_path(ts, satellite)
            # Create directory
            path.parent.mkdir(parents=True, exist_ok=True)
            # Create empty file
            with open(path, 'w') as f:
                f.write(f"Test file for {ts.isoformat()}")

    async def test_scan_directory_with_real_files(self):
        """Test scanning a directory with real files."""
        # Create a sequence of timestamps
        interval = 10  # 10-minute intervals
        start_time = datetime(2023, 1, 1, 0, 0, 0)
        end_time = datetime(2023, 1, 1, 1, 0, 0)
        
        # Generate timestamps for files to create
        # Create only files at 0:00, 0:20, and 0:40 to create gaps
        timestamps_to_create = [
            start_time,
            start_time + timedelta(minutes=20),
            start_time + timedelta(minutes=40)
        ]
        
        # Create test files
        self._create_test_files(timestamps_to_create, self.satellite)
        
        # Scan the directory
        existing, missing = await self.manager.scan_directory(
            directory=self.base_dir,
            satellite=self.satellite,
            start_time=start_time,
            end_time=end_time,
            interval_minutes=interval
        )
        
        # Expected missing timestamps: 0:10, 0:30, 0:50, 1:00
        expected_missing = {
            start_time + timedelta(minutes=10),
            start_time + timedelta(minutes=30),
            start_time + timedelta(minutes=50),
            end_time
        }
        
        # Verify results
        self.assertEqual(set(timestamps_to_create), existing)
        self.assertEqual(expected_missing, missing)
        
        # Verify cache was updated
        for ts in timestamps_to_create:
            path = self.manager._get_local_path(ts, self.satellite)
            # Query the cache for this timestamp
            timestamp_exists = await self.cache_db.timestamp_exists(
                timestamp=ts,
                satellite=self.satellite
            )
            self.assertTrue(timestamp_exists)

    @patch('goesvfi.integrity_check.reconcile_manager.render_png', autospec=True)
    async def test_fetch_missing_files(self, mock_render_png):
        """Test fetching missing files."""
        # Setup mock render_png function to immediately return a PNG path
        def fake_render(netcdf_path, output_path=None, **kwargs):
            # Just create the PNG file so tests pass
            png_path = netcdf_path.with_suffix('.png')
            png_path.parent.mkdir(parents=True, exist_ok=True)
            with open(png_path, 'w') as f:
                f.write(f"Fake rendered PNG for {netcdf_path}")
            return png_path
            
        mock_render_png.side_effect = fake_render
        
        # Create missing timestamps
        missing_timestamps = {
            self.recent_date,  # Should use CDN
            self.old_date      # Should use S3
        }
        
        # Define callbacks for testing
        progress_updates = []
        def progress_callback(current, total, message):
            progress_updates.append((current, total, message))
        
        file_callbacks = []
        def file_callback(path, success):
            file_callbacks.append((path, success))
        
        # Fetch missing files
        results = await self.manager.fetch_missing_files(
            missing_timestamps=missing_timestamps,
            satellite=self.satellite,
            progress_callback=progress_callback,
            file_callback=file_callback
        )
        
        # Verify results
        self.assertEqual(len(results), 2)
        self.assertIn(self.recent_date, results)
        self.assertIn(self.old_date, results)
        
        # Verify appropriate stores were used
        self.cdn_store.exists.assert_called_with(self.recent_date, self.satellite)
        self.s3_store.exists.assert_called_with(self.old_date, self.satellite)
        
        self.cdn_store.download.assert_called_once()
        self.s3_store.download.assert_called_once()
        
        # Verify callbacks were called
        self.assertGreater(len(progress_updates), 0)
        self.assertEqual(len(file_callbacks), 2)
        
        # Verify render_png was called for S3 file
        mock_render_png.assert_called_once()
        
        # Check that the cache was updated
        for ts in missing_timestamps:
            timestamp_exists = await self.cache_db.timestamp_exists(
                timestamp=ts,
                satellite=self.satellite
            )
            self.assertTrue(timestamp_exists)

    @patch('goesvfi.integrity_check.reconcile_manager.render_png', autospec=True)
    async def test_reconcile(self, mock_render_png):
        """Test the full reconcile process."""
        # Setup mock render_png function to immediately return a PNG path
        def fake_render(netcdf_path, output_path=None, **kwargs):
            # Just create the PNG file so tests pass
            png_path = netcdf_path.with_suffix('.png')
            png_path.parent.mkdir(parents=True, exist_ok=True)
            with open(png_path, 'w') as f:
                f.write(f"Fake rendered PNG for {netcdf_path}")
            return png_path
            
        mock_render_png.side_effect = fake_render
        
        # Create a sequence of timestamps
        interval = 10  # 10-minute intervals
        start_time = datetime(2023, 1, 1, 0, 0, 0)
        end_time = datetime(2023, 1, 1, 1, 0, 0)
        
        # Generate timestamps for files to create
        # Create only files at 0:00, 0:20, and 0:40 to create gaps
        timestamps_to_create = [
            start_time,
            start_time + timedelta(minutes=20),
            start_time + timedelta(minutes=40)
        ]
        
        # Create test files
        self._create_test_files(timestamps_to_create, self.satellite)
        
        # Define callbacks for testing
        progress_updates = []
        def progress_callback(current, total, message):
            progress_updates.append((current, total, message))
        
        file_callbacks = []
        def file_callback(path, success):
            file_callbacks.append((path, success))
        
        # Run reconcile
        total, existing_count, fetched = await self.manager.reconcile(
            directory=self.base_dir,
            satellite=self.satellite,
            start_time=start_time,
            end_time=end_time,
            interval_minutes=interval,
            progress_callback=progress_callback,
            file_callback=file_callback
        )
        
        # Expected counts
        expected_total = 7  # 0:00, 0:10, 0:20, 0:30, 0:40, 0:50, 1:00
        expected_existing = 3  # 0:00, 0:20, 0:40
        expected_fetched = 4  # 0:10, 0:30, 0:50, 1:00
        
        # Verify counts
        self.assertEqual(total, expected_total)
        self.assertEqual(existing_count, expected_existing)
        self.assertEqual(fetched, expected_fetched)
        
        # Verify callbacks were called
        self.assertGreater(len(progress_updates), 0)
        self.assertEqual(len(file_callbacks), expected_fetched)
        
        # Check that files were created for all timestamps
        for i in range(7):
            ts = start_time + timedelta(minutes=i*10)
            path = self.manager._get_local_path(ts, self.satellite)
            self.assertTrue(path.exists() or Path(str(path).replace('.png', '.nc')).exists(),
                           f"File doesn't exist for timestamp {ts}")


def async_test(coro):
    """Decorator for running async tests."""
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro(*args, **kwargs))
    return wrapper


# Apply async_test decorator to async test methods
for attr in dir(TestReconcileManagerIntegration):
    if attr.startswith('test_') and asyncio.iscoroutinefunction(getattr(TestReconcileManagerIntegration, attr)):
        setattr(TestReconcileManagerIntegration, attr, 
                async_test(getattr(TestReconcileManagerIntegration, attr)))


if __name__ == '__main__':
    unittest.main()