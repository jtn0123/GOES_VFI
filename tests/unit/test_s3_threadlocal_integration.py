"""Unit tests for ThreadLocalCacheDB integration with S3 downloads.

These tests focus on the integration between the ThreadLocalCacheDB and
S3Store classes to ensure thread safety during download operations and
proper handling of real GOES satellite file patterns.
"""

import asyncio
import concurrent.futures
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from goesvfi.integrity_check.reconcile_manager import ReconcileManager
from goesvfi.integrity_check.remote.cdn_store import CDNStore
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.thread_cache_db import ThreadLocalCacheDB
from goesvfi.integrity_check.time_index import (
    RADC_MINUTES,
    RADF_MINUTES,
    RADM_MINUTES,
    SatellitePattern,
    TimeIndex,
)


class TestS3ThreadLocalIntegration(unittest.TestCase):
    """Test cases for ThreadLocalCacheDB integration with S3 downloads."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

        # Create a temporary database file
        self.db_path = self.base_dir / "test_cache.db"

        # Create a ThreadLocalCacheDB
        self.cache_db = ThreadLocalCacheDB(db_path=self.db_path)

        # Create mock S3 and CDN stores
        self.s3_store = MagicMock(spec=S3Store)
        self.cdn_store = MagicMock(spec=CDNStore)

        # Set up async methods for mocks
        self.s3_store.__aenter__ = AsyncMock(return_value=self.s3_store)
        self.s3_store.__aexit__ = AsyncMock(return_value=None)
        self.s3_store.exists = AsyncMock(return_value=True)
        self.s3_store.download = AsyncMock(side_effect=self._mock_s3_download)

        self.cdn_store.__aenter__ = AsyncMock(return_value=self.cdn_store)
        self.cdn_store.__aexit__ = AsyncMock(return_value=None)
        self.cdn_store.exists = AsyncMock(return_value=True)
        self.cdn_store.download = AsyncMock(side_effect=self._mock_cdn_download)

        # Create a ReconcileManager with thread-local cache
        self.manager = ReconcileManager(
            cache_db=self.cache_db,
            base_dir=self.base_dir,
            cdn_store=self.cdn_store,
            s3_store=self.s3_store,
            max_concurrency=5,  # Allow multiple concurrent downloads
        )

        # Test dates and satellite
        self.now = datetime.now()
        self.old_date = self.now - timedelta(days=14)  # Use S3
        self.recent_date = self.now - timedelta(days=2)  # Use CDN
        self.satellite = SatellitePattern.GOES_18

        # Thread tracking
        self.thread_id_to_db = {}
        self.lock = threading.RLock()

        # Create sample real GOES file patterns for testing
        self.real_patterns = {
            "RadF": {
                "s3_key": "ABI-L1b-RadF/2023/166/12/OR_ABI-L1b-RadF-M6C13_G18_s20231661200000_e20231661209214_c20231661209291.nc",
                "filename": "OR_ABI-L1b-RadF-M6C13_G18_s20231661200000_e20231661209214_c20231661209291.nc",
                "minute": 0,  # RadF interval at the top of the hour
            },
            "RadC": {
                "s3_key": "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G18_s20231661206190_e20231661208562_c20231661209032.nc",
                "filename": "OR_ABI-L1b-RadC-M6C13_G18_s20231661206190_e20231661208562_c20231661209032.nc",
                "minute": 6,  # RadC interval at 6 minutes past the hour
            },
            "RadM": {
                "s3_key": "ABI-L1b-RadM1/2023/166/12/OR_ABI-L1b-RadM1-M6C13_G18_s20231661200245_e20231661200302_c20231661200344.nc",
                "filename": "OR_ABI-L1b-RadM1-M6C13_G18_s20231661200245_e20231661200302_c20231661200344.nc",
                "minute": 0,  # RadM interval at 0 minutes (can be any minute)
            },
        }

    def tearDown(self):
        """Tear down test fixtures."""
        # Close the cache DB
        self.cache_db.close()

        # Clean up temporary directory
        self.temp_dir.cleanup()

    async def _mock_s3_download(
        self, ts, satellite, dest_path, product_type="RadC", band=13
    ):
        """Mock S3 download that records the thread ID and updates the cache DB.

        This version uses realistic filenames based on the product type.
        """
        # Record thread ID
        thread_id = threading.get_ident()
        with self.lock:
            if thread_id not in self.thread_id_to_db:
                self.thread_id_to_db[thread_id] = set()

        # Create directory for the file
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Use a realistic filename based on the product type
        if product_type in self.real_patterns:
            # Get the real filename and update with correct timestamp components
            year = ts.year
            doy = ts.timetuple().tm_yday
            hour = ts.hour
            minute = self.real_patterns[product_type]["minute"]

            # Format for s3 key structure with appropriate timestamps
            formatted_name = self.real_patterns[product_type]["filename"]
            formatted_name = formatted_name.replace("2023166", f"{year}{doy:03d}")
            formatted_name = formatted_name.replace("12", f"{hour:02d}")
            formatted_name = formatted_name.replace("00000", f"{minute:02d}000")

            # Write with formatted name as content
            with open(dest_path, "w") as f:
                f.write(
                    f"S3 test file for {product_type} {ts.isoformat()}: {formatted_name}"
                )
        else:
            # Generic content
            with open(dest_path, "w") as f:
                f.write(f"S3 test file for {product_type} {ts.isoformat()}")

        # Add to cache DB
        await self.cache_db.add_timestamp(ts, satellite, str(dest_path), True)

        # Record the timestamp this thread has processed
        with self.lock:
            self.thread_id_to_db[thread_id].add(ts)

        # Add a small delay to ensure overlap in multi-threading
        await asyncio.sleep(0.05)

        return dest_path

    async def _mock_cdn_download(self, ts, satellite, dest_path):
        """Mock CDN download that records the thread ID and updates the cache DB."""
        # Similar to _mock_s3_download but for CDN
        thread_id = threading.get_ident()
        with self.lock:
            if thread_id not in self.thread_id_to_db:
                self.thread_id_to_db[thread_id] = set()

        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Create more realistic CDN content with proper filename format
        year = ts.year
        doy = ts.timetuple().tm_yday
        hour = ts.hour
        minute = ts.minute

        # Use the GOES16 CDN format
        cdn_filename = (
            f"{year}{doy:03d}{hour:02d}{minute:02d}_GOES18-ABI-CONUS-13-5424x5424.jpg"
        )

        with open(dest_path, "w") as f:
            f.write(f"CDN test file for {ts.isoformat()}: {cdn_filename}")

        await self.cache_db.add_timestamp(ts, satellite, str(dest_path), True)

        with self.lock:
            self.thread_id_to_db[thread_id].add(ts)

        await asyncio.sleep(0.05)

        return dest_path

    def _run_reconcile_in_thread(
        self, start_date, end_date, interval_minutes=10, product_type="RadC"
    ):
        """Run the reconcile method in a separate thread."""

        async def async_reconcile():
            # Simulate a scan that finds missing files
            missing_timestamps = set()

            # Use specific scanning schedule based on product type
            minutes_to_use = RADC_MINUTES  # Default
            if product_type == "RadF":
                minutes_to_use = RADF_MINUTES
            elif product_type == "RadM":
                minutes_to_use = RADM_MINUTES[
                    :10
                ]  # Just use first 10 minutes to limit test duration

            # Generate timestamps at appropriate minutes
            current = start_date.replace(minute=0, second=0, microsecond=0)
            while current <= end_date:
                for minute in minutes_to_use:
                    ts = current.replace(minute=minute)
                    if start_date <= ts <= end_date:
                        missing_timestamps.add(ts)
                current += timedelta(hours=1)

            # Call fetch_missing_files directly with the product type
            await self.manager.fetch_missing_files(
                missing_timestamps=missing_timestamps,
                satellite=self.satellite,
                product_type=product_type,
                band=13,
            )

            return len(missing_timestamps)

        # Run the async function in the current thread's event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(async_reconcile())
        finally:
            loop.close()

    def test_concurrent_downloads_with_threadlocal_cache(self):
        """Test concurrent downloads with ThreadLocalCacheDB."""
        # Create multiple date ranges for different threads
        date_ranges = [
            (self.old_date, self.old_date + timedelta(minutes=50)),  # S3 range
            (self.recent_date, self.recent_date + timedelta(minutes=50)),  # CDN range
            (
                self.old_date - timedelta(days=1),
                self.old_date - timedelta(days=1) + timedelta(minutes=50),
            ),  # S3 range
            (
                self.recent_date - timedelta(days=1),
                self.recent_date - timedelta(days=1) + timedelta(minutes=50),
            ),  # CDN range
        ]

        # Run concurrent downloads in multiple threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for start_date, end_date in date_ranges:
                futures.append(
                    executor.submit(self._run_reconcile_in_thread, start_date, end_date)
                )

            # Wait for all to complete
            results = [future.result() for future in futures]

        # Verify at least some files were processed
        self.assertGreater(sum(results), 0)

        # Verify multiple thread IDs were used
        self.assertGreater(
            len(self.thread_id_to_db),
            1,
            "Only one thread was used for concurrent downloads",
        )

        # Verify each thread had its own timestamps
        thread_timestamps = {}
        for thread_id, timestamps in self.thread_id_to_db.items():
            thread_timestamps[thread_id] = len(timestamps)

        total_timestamps = sum(thread_timestamps.values())
        self.assertGreater(
            total_timestamps, 0, f"Expected timestamps, got {total_timestamps}"
        )

        # Verify cache entries were created
        cache_stats = self.cache_db.get_cache_stats()
        self.assertGreater(cache_stats.get("timestamp_count", 0), 0)

    def test_different_product_types_with_threadlocal_cache(self):
        """Test concurrent downloads with different product types."""
        # Create date range
        start_date = self.old_date
        end_date = self.old_date + timedelta(minutes=50)

        # Test different product types concurrently
        product_types = ["RadF", "RadC", "RadM"]

        # Run concurrent downloads in multiple threads
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(product_types)
        ) as executor:
            futures = []
            for product_type in product_types:
                futures.append(
                    executor.submit(
                        self._run_reconcile_in_thread,
                        start_date,
                        end_date,
                        interval_minutes=10,
                        product_type=product_type,
                    )
                )

            # Wait for all to complete
            results = [future.result() for future in futures]

        # Verify each product type processed files
        self.assertGreaterEqual(len(results), len(product_types))
        for count in results:
            self.assertGreater(count, 0, "Expected files to be processed")

        # Verify multiple thread IDs were used
        self.assertGreaterEqual(
            len(self.thread_id_to_db),
            len(product_types),
            f"Expected at least {len(product_types)} threads, got {len(self.thread_id_to_db)}",
        )

        # Verify SQLite thread safety by checking for errors
        # If there were thread safety issues, the test would crash with SQLite exceptions

        # Verify cache has entries
        cache_stats = self.cache_db.get_cache_stats()
        self.assertGreater(cache_stats.get("timestamp_count", 0), 0)

    def test_threadlocal_cache_stress_test(self):
        """Stress test the ThreadLocalCacheDB with many concurrent downloads."""
        # Create a large number of timestamps
        timestamps = []
        base_date = self.old_date
        for i in range(50):  # 50 timestamps
            ts = base_date + timedelta(minutes=i * 10)
            timestamps.append(ts)

        # Function to process a batch of timestamps
        def process_batch(batch_timestamps, product_type):
            async def async_process():
                # Convert list to set
                timestamp_set = set(batch_timestamps)

                # Call fetch_missing_files
                results = await self.manager.fetch_missing_files(
                    missing_timestamps=timestamp_set,
                    satellite=self.satellite,
                    product_type=product_type,
                )

                return len(results)

            # Run the async function
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(async_process())
            finally:
                loop.close()

        # Split timestamps into 5 batches
        batch_size = 10
        batches = [
            timestamps[i : i + batch_size]
            for i in range(0, len(timestamps), batch_size)
        ]

        # Add product types for each batch - rotate between RadF, RadC, RadM
        product_types = ["RadF", "RadC", "RadM", "RadF", "RadC"]

        # Process batches concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i, batch in enumerate(batches):
                product_type = product_types[i % len(product_types)]
                futures.append(executor.submit(process_batch, batch, product_type))

            # Wait for all to complete
            results = [future.result() for future in futures]

        # Verify all timestamps were processed
        self.assertEqual(sum(results), 50)

        # Verify multiple threads were used
        self.assertGreaterEqual(
            len(self.thread_id_to_db),
            2,
            "Too few threads were used for concurrent downloads",
        )

        # Verify each thread processed some timestamps
        for thread_id, timestamps in self.thread_id_to_db.items():
            self.assertGreater(
                len(timestamps), 0, f"Thread {thread_id} processed 0 timestamps"
            )

        # Check no SQLite thread errors occurred by verifying the cache contains entries
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            all_timestamps = loop.run_until_complete(self._get_all_cache_entries())
            self.assertGreaterEqual(
                len(all_timestamps),
                50,
                f"Expected at least 50 timestamps in cache, got {len(all_timestamps)}",
            )
        finally:
            loop.close()

    def test_real_s3_patterns(self):
        """Test with real S3 file patterns for different product types."""

        # Create a thread-specific function for each product type
        def run_product_test(product_type):
            async def async_test():
                # Create timestamps at the correct minute for this product
                base_minute = self.real_patterns[product_type]["minute"]
                timestamp = self.old_date.replace(
                    minute=base_minute, second=0, microsecond=0
                )

                # Create destination path
                dest_path = (
                    self.base_dir
                    / f"{product_type}_{timestamp.strftime('%Y%m%d_%H%M%S')}.nc"
                )

                # Directly call download to test real patterns
                result = await self.s3_store.download(
                    timestamp,
                    self.satellite,
                    dest_path,
                    product_type=product_type,
                    band=13,
                )

                # Verify file was created with the correct content
                with open(result, "r") as f:
                    content = f.read()

                # File content should contain the product type
                return product_type in content

            # Run in this thread's event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(async_test())
            finally:
                loop.close()

        # Test each product type in a separate thread
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                product_type: executor.submit(run_product_test, product_type)
                for product_type in self.real_patterns.keys()
            }

            # Wait for all to complete
            results = {pt: future.result() for pt, future in futures.items()}

        # Verify each product type was processed correctly
        for product_type, success in results.items():
            self.assertTrue(success, f"Failed to process {product_type} correctly")

    async def _get_all_cache_entries(self):
        """Helper method to get all entries from the cache."""
        # Get earliest and latest timestamps
        now = datetime.now()
        earliest = now - timedelta(days=30)

        # Get all timestamps for our test satellite
        return await self.cache_db.get_timestamps(
            satellite=self.satellite, start_time=earliest, end_time=now
        )


# Helper function to run async tests with an event loop
def async_test(coro):
    """Decorator for running async tests."""

    def wrapper(*args, **kwargs):
        # Create event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Run the test
            return loop.run_until_complete(coro(*args, **kwargs))
        finally:
            # Clean up
            loop.close()

    return wrapper


# Apply async_test decorator to async methods that need it
for name in dir(TestS3ThreadLocalIntegration):
    if name.startswith("_get_") and asyncio.iscoroutinefunction(
        getattr(TestS3ThreadLocalIntegration, name)
    ):
        setattr(
            TestS3ThreadLocalIntegration,
            name,
            async_test(getattr(TestS3ThreadLocalIntegration, name)),
        )


if __name__ == "__main__":
    unittest.main()
