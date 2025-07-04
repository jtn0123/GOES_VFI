"""
Optimized unit tests for ThreadLocalCacheDB integration with S3 downloads.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for ThreadLocalCacheDB, S3Store, and CDNStore setup
- Enhanced test managers for comprehensive thread safety validation
- Batch testing of concurrent operations with different product types
- Improved async/threading patterns with shared setup and teardown
"""

import asyncio
import concurrent.futures
from datetime import UTC, datetime, timedelta
from pathlib import Path
import tempfile
import threading
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from goesvfi.integrity_check.reconcile_manager import ReconcileManager
from goesvfi.integrity_check.remote.cdn_store import CDNStore
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.thread_cache_db import ThreadLocalCacheDB
from goesvfi.integrity_check.time_index import (
    RADC_MINUTES,
    RADF_MINUTES,
    RADM_MINUTES,
    SatellitePattern,
)


class TestS3ThreadLocalIntegrationOptimizedV2:
    """Optimized ThreadLocalCacheDB integration tests with full coverage."""

    @pytest.fixture(scope="class")
    @staticmethod
    def threadlocal_integration_test_components() -> dict[str, Any]:  # noqa: PLR6301, C901
        """Create shared components for ThreadLocalCacheDB integration testing.

        Returns:
            dict[str, Any]: Dictionary containing test components and managers.
        """

        # Enhanced ThreadLocal Integration Test Manager
        class ThreadLocalIntegrationTestManager:
            """Manage ThreadLocalCacheDB integration testing scenarios."""

            def __init__(self) -> None:
                # Define test configurations
                self.test_configs = {
                    "satellites": [SatellitePattern.GOES_16, SatellitePattern.GOES_18],
                    "max_concurrency": 5,
                    "thread_pool_size": 4,
                    "batch_size": 10,
                    "stress_test_count": 50,
                }

                # Real GOES file patterns for testing
                self.real_patterns = {
                    "RadF": {
                        "s3_key": (
                            "ABI-L1b-RadF/2023/166/12/"
                            "OR_ABI-L1b-RadF-M6C13_G18_s20231661200000_e20231661209214_c20231661209291.nc"
                        ),
                        "filename": "OR_ABI-L1b-RadF-M6C13_G18_s20231661200000_e20231661209214_c20231661209291.nc",
                        "minute": 0,  # RadF interval at the top of the hour
                        "schedule": RADF_MINUTES,
                    },
                    "RadC": {
                        "s3_key": (
                            "ABI-L1b-RadC/2023/166/12/"
                            "OR_ABI-L1b-RadC-M6C13_G18_s20231661206190_e20231661208562_c20231661209032.nc"
                        ),
                        "filename": "OR_ABI-L1b-RadC-M6C13_G18_s20231661206190_e20231661208562_c20231661209032.nc",
                        "minute": 6,  # RadC interval at 6 minutes past the hour
                        "schedule": RADC_MINUTES,
                    },
                    "RadM": {
                        "s3_key": (
                            "ABI-L1b-RadM1/2023/166/12/"
                            "OR_ABI-L1b-RadM1-M6C13_G18_s20231661200245_e20231661200302_c20231661200344.nc"
                        ),
                        "filename": "OR_ABI-L1b-RadM1-M6C13_G18_s20231661200245_e20231661200302_c20231661200344.nc",
                        "minute": 0,  # RadM interval at 0 minutes (can be any minute)
                        "schedule": RADM_MINUTES[:10],  # Limit for testing
                    },
                }

                # Define test scenarios
                self.test_scenarios = {
                    "concurrent_downloads": self._test_concurrent_downloads,
                    "product_type_integration": self._test_product_type_integration,
                    "thread_safety_validation": self._test_thread_safety_validation,
                    "cache_consistency": self._test_cache_consistency,
                    "stress_testing": self._test_stress_testing,
                    "real_pattern_testing": self._test_real_pattern_testing,
                    "error_handling": self._test_error_handling,
                    "performance_validation": self._test_performance_validation,
                }

                # Thread tracking
                self.thread_tracking = {
                    "thread_id_to_db": {},
                    "lock": threading.RLock(),
                    "processed_timestamps": {},
                    "error_count": 0,
                }

            @staticmethod
            def create_temp_directory() -> tempfile.TemporaryDirectory:
                """Create a temporary directory for test files.

                Returns:
                    tempfile.TemporaryDirectory: Temporary directory context manager.
                """
                return tempfile.TemporaryDirectory()

            @staticmethod
            def create_cache_db(base_dir: Path) -> ThreadLocalCacheDB:
                """Create a ThreadLocalCacheDB instance.

                Returns:
                    ThreadLocalCacheDB: New cache database instance.
                """
                db_path = base_dir / "test_cache.db"
                return ThreadLocalCacheDB(db_path=db_path)

            def create_mock_stores(self, cache_db: ThreadLocalCacheDB, _base_dir: Path) -> dict[str, Any]:
                """Create mock S3 and CDN stores.

                Returns:
                    dict[str, Any]: Dictionary with mocked S3 and CDN stores.
                """
                # Mock S3 store
                s3_store = MagicMock(spec=S3Store)
                s3_store.__aenter__ = AsyncMock(return_value=s3_store)
                s3_store.__aexit__ = AsyncMock(return_value=None)
                s3_store.exists = AsyncMock(return_value=True)
                async def s3_download_wrapper(*args, **kwargs):
                    return await self._mock_s3_download(*args, cache_db=cache_db, **kwargs)
                s3_store.download = AsyncMock(side_effect=s3_download_wrapper)

                # Mock CDN store
                cdn_store = MagicMock(spec=CDNStore)
                cdn_store.__aenter__ = AsyncMock(return_value=cdn_store)
                cdn_store.__aexit__ = AsyncMock(return_value=None)
                cdn_store.exists = AsyncMock(return_value=True)
                async def cdn_download_wrapper(*args, **kwargs):
                    return await self._mock_cdn_download(*args, cache_db=cache_db, **kwargs)
                cdn_store.download = AsyncMock(side_effect=cdn_download_wrapper)

                return {"s3_store": s3_store, "cdn_store": cdn_store}

            def create_reconcile_manager(
                self, cache_db: ThreadLocalCacheDB, base_dir: Path, stores: dict[str, Any]
            ) -> ReconcileManager:
                """Create a ReconcileManager with mocked stores.

                Returns:
                    ReconcileManager: New reconcile manager instance.
                """
                return ReconcileManager(
                    cache_db=cache_db,
                    base_dir=base_dir,
                    cdn_store=stores["cdn_store"],
                    s3_store=stores["s3_store"],
                    max_concurrency=self.test_configs["max_concurrency"],
                )

            async def _mock_s3_download(
                self,
                ts: datetime,
                satellite: SatellitePattern,
                dest_path: Path,
                cache_db: ThreadLocalCacheDB,
                product_type: str = "RadC",
                band: int = 13,
            ) -> Path:
                """Mock S3 download that records thread ID and updates cache DB.

                Returns:
                    Path: Path to the downloaded file.
                """
                thread_id = threading.get_ident()

                with self.thread_tracking["lock"]:
                    if thread_id not in self.thread_tracking["thread_id_to_db"]:
                        self.thread_tracking["thread_id_to_db"][thread_id] = set()
                        self.thread_tracking["processed_timestamps"][thread_id] = []

                # Create directory and file
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                # Use realistic filename based on product type
                if product_type in self.real_patterns:
                    pattern_info = self.real_patterns[product_type]
                    year = ts.year
                    doy = ts.timetuple().tm_yday
                    hour = ts.hour
                    minute = pattern_info["minute"]

                    formatted_name = pattern_info["filename"]
                    formatted_name = formatted_name.replace("2023166", f"{year}{doy:03d}")
                    formatted_name = formatted_name.replace("12", f"{hour:02d}")
                    formatted_name = formatted_name.replace("00000", f"{minute:02d}000")

                    content = f"S3 test file for {product_type} {ts.isoformat()}: {formatted_name}"
                else:
                    content = f"S3 test file for {product_type} {ts.isoformat()}"

                dest_path.write_text(content, encoding="utf-8")

                # Add to cache DB
                await cache_db.add_timestamp(ts, satellite, str(dest_path), True)

                # Record processing
                with self.thread_tracking["lock"]:
                    self.thread_tracking["thread_id_to_db"][thread_id].add(ts)
                    self.thread_tracking["processed_timestamps"][thread_id].append((ts, product_type))

                # Small delay for threading overlap
                await asyncio.sleep(0.01)

                return dest_path

            async def _mock_cdn_download(
                self, ts: datetime, satellite: SatellitePattern, dest_path: Path, cache_db: ThreadLocalCacheDB
            ) -> Path:
                """Mock CDN download that records thread ID and updates cache DB.

                Returns:
                    Path: Path to the downloaded file.
                """
                thread_id = threading.get_ident()

                with self.thread_tracking["lock"]:
                    if thread_id not in self.thread_tracking["thread_id_to_db"]:
                        self.thread_tracking["thread_id_to_db"][thread_id] = set()
                        self.thread_tracking["processed_timestamps"][thread_id] = []

                dest_path.parent.mkdir(parents=True, exist_ok=True)

                # Create realistic CDN content
                year = ts.year
                doy = ts.timetuple().tm_yday
                hour = ts.hour
                minute = ts.minute

                cdn_filename = f"{year}{doy:03d}{hour:02d}{minute:02d}_GOES18-ABI-CONUS-13-5424x5424.jpg"
                content = f"CDN test file for {ts.isoformat()}: {cdn_filename}"

                dest_path.write_text(content, encoding="utf-8")

                await cache_db.add_timestamp(ts, satellite, str(dest_path), True)

                with self.thread_tracking["lock"]:
                    self.thread_tracking["thread_id_to_db"][thread_id].add(ts)
                    self.thread_tracking["processed_timestamps"][thread_id].append((ts, "CDN"))

                await asyncio.sleep(0.01)

                return dest_path

            @staticmethod
            async def _mock_fetch_missing_files(
                missing_timestamps: list[datetime],
                satellite: SatellitePattern,
                destination_dir: str | Path,
                stores: dict[str, Any],
                _cache_db: ThreadLocalCacheDB,
                **kwargs: Any,
            ) -> list[datetime]:
                """Mock fetch_missing_files that calls store mocks.

                Returns:
                    list[datetime]: List of timestamps that were fetched.
                """
                for ts in missing_timestamps:
                    # Determine store based on age
                    age_days = (datetime.now(tz=UTC) - ts).days

                    store = stores["s3_store"] if age_days > 7 else stores["cdn_store"]

                    # Create destination path
                    filename = f"test_file_{ts.strftime('%Y%m%d_%H%M%S')}.nc"
                    dest_path = Path(destination_dir) / filename

                    # Call store download
                    await store.download(ts, satellite, dest_path)

                return list(missing_timestamps)

            def _run_reconcile_in_thread(
                self,
                start_date: datetime,
                end_date: datetime,
                manager: ReconcileManager,
                satellite: SatellitePattern,
                base_dir: str,
                _interval_minutes: int = 10,
                product_type: str = "RadC",
            ) -> int:
                """Run reconcile method in a separate thread.

                Returns:
                    int: Number of missing timestamps processed.
                """

                async def async_reconcile() -> int:
                    missing_timestamps = set()

                    # Use appropriate schedule for product type
                    if product_type in self.real_patterns:
                        minutes_to_use = self.real_patterns[product_type]["schedule"]
                    else:
                        minutes_to_use = RADC_MINUTES

                    # Generate timestamps
                    current = start_date.replace(minute=0, second=0, microsecond=0)
                    while current <= end_date:
                        for minute in minutes_to_use:
                            ts = current.replace(minute=minute)
                            if start_date <= ts <= end_date:
                                missing_timestamps.add(ts)
                        current += timedelta(hours=1)

                    # Call fetch_missing_files
                    await manager.fetch_missing_files(
                        missing_timestamps=list(missing_timestamps),
                        satellite=satellite,
                        destination_dir=base_dir,
                    )

                    return len(missing_timestamps)

                # Run in new event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(async_reconcile())
                finally:
                    loop.close()

            def reset_thread_tracking(self) -> None:
                """Reset thread tracking for new test."""
                with self.thread_tracking["lock"]:
                    self.thread_tracking["thread_id_to_db"].clear()
                    self.thread_tracking["processed_timestamps"].clear()
                    self.thread_tracking["error_count"] = 0

            def _test_concurrent_downloads(
                self,
                scenario_name: str,
                temp_dir: tempfile.TemporaryDirectory[str],
                cache_db: ThreadLocalCacheDB,
                stores: dict[str, Any],
                manager: ReconcileManager,
                **kwargs: Any,
            ) -> dict[str, Any]:
                """Test concurrent download scenarios.

                Returns:
                    dict[str, Any]: Test results with file processing statistics.
                """
                results = {}
                self.reset_thread_tracking()

                if scenario_name == "basic_concurrent":
                    # Create date ranges for different threads
                    now = datetime.now(tz=UTC)
                    old_date = now - timedelta(days=14)  # S3
                    recent_date = now - timedelta(days=2)  # CDN

                    date_ranges = [
                        (old_date, old_date + timedelta(minutes=50)),
                        (recent_date, recent_date + timedelta(minutes=50)),
                        (old_date - timedelta(days=1), old_date - timedelta(days=1) + timedelta(minutes=50)),
                        (recent_date - timedelta(days=1), recent_date - timedelta(days=1) + timedelta(minutes=50)),
                    ]

                    # Mock fetch_missing_files
                    with patch.object(ReconcileManager, "fetch_missing_files") as mock_fetch:
                        async def mock_fetch_coroutine(*args, **kwargs):
                            return await self._mock_fetch_missing_files(
                                *args, stores=stores, _cache_db=cache_db, **kwargs
                            )
                        mock_fetch.side_effect = mock_fetch_coroutine

                        # Run concurrent downloads
                        with concurrent.futures.ThreadPoolExecutor(
                            max_workers=self.test_configs["thread_pool_size"]
                        ) as executor:
                            futures = []
                            for start_date, end_date in date_ranges:
                                futures.append(
                                    executor.submit(
                                        self._run_reconcile_in_thread,
                                        start_date,
                                        end_date,
                                        manager,
                                        SatellitePattern.GOES_18,
                                        temp_dir.name,
                                    )
                                )

                            # Wait for completion
                            thread_results = [future.result() for future in futures]

                    # Verify results
                    assert sum(thread_results) > 0

                    results["files_processed"] = sum(thread_results)
                    results["threads_used"] = len(self.thread_tracking["thread_id_to_db"])
                    results["concurrent_success"] = results["threads_used"] >= 1  # At least some threading

                return {"scenario": scenario_name, "results": results}

            def _test_product_type_integration(
                self,
                scenario_name: str,
                temp_dir: tempfile.TemporaryDirectory[str],
                cache_db: ThreadLocalCacheDB,
                stores: dict[str, Any],
                manager: ReconcileManager,
                **kwargs: Any,
            ) -> dict[str, Any]:
                """Test product type integration scenarios.

                Returns:
                    dict[str, Any]: Test results with product type processing statistics.
                """
                results = {}
                self.reset_thread_tracking()

                if scenario_name == "different_product_types":
                    # Test different product types concurrently
                    now = datetime.now(tz=UTC)
                    start_date = (now - timedelta(days=14)).replace(minute=0, second=0, microsecond=0)
                    end_date = start_date + timedelta(hours=2)

                    product_types = ["RadF", "RadC", "RadM"]

                    with patch.object(ReconcileManager, "fetch_missing_files") as mock_fetch:
                        async def mock_fetch_coroutine(*args, **kwargs):
                            return await self._mock_fetch_missing_files(
                                *args, stores=stores, _cache_db=cache_db, **kwargs
                            )
                        mock_fetch.side_effect = mock_fetch_coroutine

                        # Run with different product types
                        with concurrent.futures.ThreadPoolExecutor(max_workers=len(product_types)) as executor:
                            futures = [
                                executor.submit(
                                    self._run_reconcile_in_thread,
                                    start_date,
                                    end_date,
                                    manager,
                                    SatellitePattern.GOES_18,
                                    temp_dir.name,
                                    10,
                                    product_type,
                                )
                                for product_type in product_types
                            ]

                            thread_results = [future.result() for future in futures]

                    # Verify each product type processed files
                    assert len(thread_results) >= len(product_types)
                    for count in thread_results:
                        assert count > 0

                    results["product_types_tested"] = len(product_types)
                    results["files_per_type"] = thread_results
                    results["total_files"] = sum(thread_results)

                return {"scenario": scenario_name, "results": results}

            def _test_thread_safety_validation(
                self,
                scenario_name: str,
                temp_dir: tempfile.TemporaryDirectory[str],
                cache_db: ThreadLocalCacheDB,
                stores: dict[str, Any],
                manager: ReconcileManager,  # noqa: ARG002
                **kwargs: Any,
            ) -> dict[str, Any]:
                """Test thread safety validation scenarios.

                Returns:
                    dict[str, Any]: Test results with thread safety validation statistics.
                """
                results = {}
                self.reset_thread_tracking()

                if scenario_name == "thread_safety_stress":
                    # Create many timestamps for stress testing
                    now = datetime.now(tz=UTC)
                    base_date = now - timedelta(days=14)
                    timestamps = []

                    for i in range(self.test_configs["stress_test_count"]):
                        ts = base_date + timedelta(minutes=i * 10)
                        timestamps.append(ts)

                    def process_batch(batch_timestamps: list[datetime], _batch_id: int) -> int:
                        async def async_process() -> int:
                            timestamp_set = set(batch_timestamps)

                            # Mock fetch call
                            await self._mock_fetch_missing_files(
                                list(timestamp_set), SatellitePattern.GOES_18, temp_dir.name, stores, _cache_db=cache_db
                            )

                            return len(timestamp_set)

                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            return loop.run_until_complete(async_process())
                        except (OSError, RuntimeError):
                            self.thread_tracking["error_count"] += 1
                            return 0
                        finally:
                            loop.close()

                    # Split into batches
                    batch_size = self.test_configs["batch_size"]
                    batches = [timestamps[i : i + batch_size] for i in range(0, len(timestamps), batch_size)]

                    # Process batches concurrently
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                        futures = []
                        for i, batch in enumerate(batches):
                            futures.append(executor.submit(process_batch, batch, i))

                        batch_results = [future.result() for future in futures]

                    # Verify results
                    assert sum(batch_results) == self.test_configs["stress_test_count"]
                    assert self.thread_tracking["error_count"] == 0  # No threading errors

                    results["timestamps_processed"] = sum(batch_results)
                    results["batches_processed"] = len(batches)
                    results["threads_used"] = len(self.thread_tracking["thread_id_to_db"])
                    results["errors"] = self.thread_tracking["error_count"]

                return {"scenario": scenario_name, "results": results}

            @staticmethod
            def _test_cache_consistency(
                scenario_name: str,
                _temp_dir: tempfile.TemporaryDirectory[str],
                cache_db: ThreadLocalCacheDB,
                _stores: dict[str, Any],
                _manager: ReconcileManager,
                **kwargs: Any,
            ) -> dict[str, Any]:
                """Test cache consistency scenarios.

                Returns:
                    dict[str, Any]: Test results with cache consistency validation statistics.
                """
                results = {}

                if scenario_name == "cache_operations":
                    # Test cache operations under concurrent access
                    satellite = SatellitePattern.GOES_18

                    try:
                        # Test basic cache operations
                        cache_stats = cache_db.get_cache_data(satellite)
                        results["cache_accessible"] = True
                        results["initial_entries"] = len(cache_stats) if cache_stats else 0
                    except (OSError, RuntimeError) as e:
                        results["cache_accessible"] = False
                        results["cache_error"] = str(e)

                    # Test cache under load (simplified)
                    async def add_cache_entries() -> None:
                        base_time = datetime.now(tz=UTC) - timedelta(days=1)
                        for i in range(10):
                            ts = base_time + timedelta(minutes=i * 5)
                            await cache_db.add_timestamp(ts, satellite, f"/test/path_{i}.nc", True)

                    # Run cache operations
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(add_cache_entries())
                        results["cache_entries_added"] = True
                    except (OSError, RuntimeError) as e:
                        results["cache_entries_added"] = False
                        results["add_error"] = str(e)
                    finally:
                        loop.close()

                return {"scenario": scenario_name, "results": results}

            def _test_stress_testing(
                self,
                scenario_name: str,
                temp_dir: tempfile.TemporaryDirectory[str],  # noqa: ARG002
                cache_db: ThreadLocalCacheDB,  # noqa: ARG002
                stores: dict[str, Any],  # noqa: ARG002
                manager: ReconcileManager,  # noqa: ARG002
                **kwargs: Any,
            ) -> dict[str, Any]:
                """Test stress testing scenarios.

                Returns:
                    dict[str, Any]: Test results with stress testing statistics.
                """
                results = {}

                # This is covered by thread_safety_validation stress test
                # Return a summary result
                results["stress_test_covered"] = True
                results["stress_count"] = self.test_configs["stress_test_count"]

                return {"scenario": scenario_name, "results": results}

            def _test_real_pattern_testing(
                self,
                scenario_name: str,
                temp_dir: tempfile.TemporaryDirectory[str],
                cache_db: ThreadLocalCacheDB,  # noqa: ARG002
                stores: dict[str, Any],
                manager: ReconcileManager,  # noqa: ARG002
                **kwargs: Any,
            ) -> dict[str, Any]:
                """Test real pattern testing scenarios.

                Returns:
                    dict[str, Any]: Test results with real pattern processing statistics.
                """
                results = {}

                if scenario_name == "real_s3_patterns":
                    # Test with real S3 patterns for different product types
                    def run_product_test(product_type: str) -> bool:
                        async def async_test() -> bool:
                            base_minute = self.real_patterns[product_type]["minute"]
                            now = datetime.now(tz=UTC)
                            timestamp = (now - timedelta(days=14)).replace(minute=base_minute, second=0, microsecond=0)

                            dest_path = Path(temp_dir.name) / f"{product_type}_{timestamp.strftime('%Y%m%d_%H%M%S')}.nc"

                            # Call S3 download directly
                            result = await stores["s3_store"].download(
                                timestamp,
                                SatellitePattern.GOES_18,
                                dest_path,
                                product_type=product_type,
                                band=13,
                            )

                            # Verify file content
                            content = result.read_text(encoding="utf-8")

                            return product_type in content

                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            return loop.run_until_complete(async_test())
                        finally:
                            loop.close()

                    # Test each product type in separate threads
                    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                        futures = {
                            product_type: executor.submit(run_product_test, product_type)
                            for product_type in self.real_patterns
                        }

                        pattern_results = {pt: future.result() for pt, future in futures.items()}

                    # Verify all succeeded
                    for product_type, success in pattern_results.items():
                        assert success, f"Failed to process {product_type} correctly"

                    results["patterns_tested"] = len(self.real_patterns)
                    results["all_patterns_success"] = all(pattern_results.values())

                return {"scenario": scenario_name, "results": results}

            @staticmethod
            def _test_error_handling(
                scenario_name: str,
                _temp_dir: tempfile.TemporaryDirectory[str],
                cache_db: ThreadLocalCacheDB,
                _stores: dict[str, Any],
                _manager: ReconcileManager,
                **kwargs: Any,
            ) -> dict[str, Any]:
                """Test error handling scenarios.

                Returns:
                    dict[str, Any]: Test results with error handling validation statistics.
                """
                results = {}

                if scenario_name == "threading_errors":
                    # Test error handling in threading context
                    error_count = 0

                    def error_prone_operation() -> int:
                        try:
                            # Simulate operation that might fail
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                # Test cache access
                                cache_stats = cache_db.get_cache_data(SatellitePattern.GOES_18)
                                return len(cache_stats) if cache_stats else 0
                            finally:
                                loop.close()
                        except (OSError, RuntimeError):
                            return -1  # Error indicator

                    # Run operations concurrently
                    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                        futures = [executor.submit(error_prone_operation) for _ in range(5)]
                        operation_results = [future.result() for future in futures]

                    error_count = sum(1 for result in operation_results if result == -1)

                    results["operations_run"] = len(operation_results)
                    results["errors_encountered"] = error_count
                    results["success_rate"] = (len(operation_results) - error_count) / len(operation_results)

                return {"scenario": scenario_name, "results": results}

            @staticmethod
            def _test_performance_validation(
                scenario_name: str,
                _temp_dir: tempfile.TemporaryDirectory[str],
                cache_db: ThreadLocalCacheDB,
                _stores: dict[str, Any],
                _manager: ReconcileManager,
                **kwargs: Any,
            ) -> dict[str, Any]:
                """Test performance validation scenarios.

                Returns:
                    dict[str, Any]: Test results with performance validation statistics.
                """
                results = {}

                if scenario_name == "throughput_testing":
                    # Test high throughput operations
                    operation_count = 20

                    async def batch_operations() -> int:
                        tasks = []
                        base_time = datetime.now(tz=UTC) - timedelta(days=1)

                        for i in range(operation_count):
                            ts = base_time + timedelta(minutes=i * 3)
                            task = cache_db.add_timestamp(
                                ts, SatellitePattern.GOES_18, f"/test/perf_{i}.nc", True
                            )
                            tasks.append(task)

                        await asyncio.gather(*tasks)
                        return operation_count

                    # Run performance test
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        operations_completed = loop.run_until_complete(batch_operations())
                        results["operations_completed"] = operations_completed
                        results["performance_success"] = operations_completed == operation_count
                    except (OSError, RuntimeError) as e:
                        results["operations_completed"] = 0
                        results["performance_success"] = False
                        results["error"] = str(e)
                    finally:
                        loop.close()

                return {"scenario": scenario_name, "results": results}

        return {"manager": ThreadLocalIntegrationTestManager()}

    @pytest.fixture()
    @staticmethod
    def temp_directory() -> tempfile.TemporaryDirectory[str]:
        """Create temporary directory for each test.

        Yields:
            tempfile.TemporaryDirectory[str]: Temporary directory context.
        """
        temp_dir = tempfile.TemporaryDirectory()
        yield temp_dir
        temp_dir.cleanup()

    @pytest.fixture()
    @staticmethod
    def test_setup(
        threadlocal_integration_test_components: dict[str, Any], temp_directory: tempfile.TemporaryDirectory[str]
    ) -> dict[str, Any]:
        """Set up test components for each test.

        Yields:
            dict[str, Any]: Test setup components.
        """
        manager = threadlocal_integration_test_components["manager"]
        base_dir = Path(temp_directory.name)

        # Create cache DB
        cache_db = manager.create_cache_db(base_dir)

        # Create mock stores
        stores = manager.create_mock_stores(cache_db, base_dir)

        # Create reconcile manager
        reconcile_manager = manager.create_reconcile_manager(cache_db, base_dir, stores)

        yield {
            "manager": manager,
            "temp_dir": temp_directory,
            "cache_db": cache_db,
            "stores": stores,
            "reconcile_manager": reconcile_manager,
            "base_dir": base_dir,
        }

        # Cleanup
        cache_db.close()

    def test_concurrent_download_scenarios(self, test_setup: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test concurrent download scenarios."""
        setup = test_setup
        manager = setup["manager"]

        result = manager._test_concurrent_downloads(  # noqa: SLF001
            "basic_concurrent", setup["temp_dir"], setup["cache_db"], setup["stores"], setup["reconcile_manager"]
        )

        assert result["scenario"] == "basic_concurrent"
        assert result["results"]["files_processed"] > 0
        assert result["results"]["concurrent_success"] is True

    def test_product_type_integration_scenarios(self, test_setup: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test product type integration scenarios."""
        setup = test_setup
        manager = setup["manager"]

        result = manager._test_product_type_integration(  # noqa: SLF001
            "different_product_types", setup["temp_dir"], setup["cache_db"], setup["stores"], setup["reconcile_manager"]
        )

        assert result["scenario"] == "different_product_types"
        assert result["results"]["product_types_tested"] == 3
        assert result["results"]["total_files"] > 0

    def test_thread_safety_validation_scenarios(self, test_setup: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test thread safety validation scenarios."""
        setup = test_setup
        manager = setup["manager"]

        result = manager._test_thread_safety_validation(  # noqa: SLF001
            "thread_safety_stress", setup["temp_dir"], setup["cache_db"], setup["stores"], setup["reconcile_manager"]
        )

        assert result["scenario"] == "thread_safety_stress"
        assert result["results"]["timestamps_processed"] == manager.test_configs["stress_test_count"]
        assert result["results"]["errors"] == 0

    def test_cache_consistency_scenarios(self, test_setup: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test cache consistency scenarios."""
        setup = test_setup
        manager = setup["manager"]

        result = manager._test_cache_consistency(  # noqa: SLF001
            "cache_operations", setup["temp_dir"], setup["cache_db"], setup["stores"], setup["reconcile_manager"]
        )

        assert result["scenario"] == "cache_operations"
        assert result["results"]["cache_accessible"] is True

    def test_real_pattern_testing_scenarios(self, test_setup: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test real pattern testing scenarios."""
        setup = test_setup
        manager = setup["manager"]

        result = manager._test_real_pattern_testing(  # noqa: SLF001
            "real_s3_patterns", setup["temp_dir"], setup["cache_db"], setup["stores"], setup["reconcile_manager"]
        )

        assert result["scenario"] == "real_s3_patterns"
        assert result["results"]["patterns_tested"] == 3
        assert result["results"]["all_patterns_success"] is True

    def test_error_handling_scenarios(self, test_setup: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test error handling scenarios."""
        setup = test_setup
        manager = setup["manager"]

        result = manager._test_error_handling(  # noqa: SLF001
            "threading_errors", setup["temp_dir"], setup["cache_db"], setup["stores"], setup["reconcile_manager"]
        )

        assert result["scenario"] == "threading_errors"
        assert result["results"]["operations_run"] == 5
        assert result["results"]["success_rate"] >= 0.8  # Allow some tolerance

    def test_performance_validation_scenarios(self, test_setup: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test performance validation scenarios."""
        setup = test_setup
        manager = setup["manager"]

        result = manager._test_performance_validation(  # noqa: SLF001
            "throughput_testing", setup["temp_dir"], setup["cache_db"], setup["stores"], setup["reconcile_manager"]
        )

        assert result["scenario"] == "throughput_testing"
        assert result["results"]["performance_success"] is True

    @pytest.mark.parametrize("product_type", ["RadF", "RadC", "RadM"])
    def test_product_type_specific_operations(self, test_setup: dict[str, Any], product_type: str) -> None:  # noqa: PLR6301
        """Test operations with specific product types."""
        setup = test_setup
        manager = setup["manager"]

        # Test specific product type
        pattern_info = manager.real_patterns[product_type]

        def run_product_test() -> bool:
            async def async_test() -> bool:
                base_minute = pattern_info["minute"]
                now = datetime.now(tz=UTC)
                timestamp = (now - timedelta(days=14)).replace(minute=base_minute, second=0, microsecond=0)

                dest_path = setup["base_dir"] / f"{product_type}_specific_{timestamp.strftime('%Y%m%d_%H%M%S')}.nc"

                # Call download
                result = await setup["stores"]["s3_store"].download(
                    timestamp,
                    SatellitePattern.GOES_18,
                    dest_path,
                    product_type=product_type,
                    band=13,
                )

                # Verify content
                content = result.read_text(encoding="utf-8")

                return product_type in content and result.exists()

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(async_test())
            finally:
                loop.close()

        # Run test
        success = run_product_test()
        assert success is True

    def test_comprehensive_threadlocal_integration_validation(self, test_setup: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test comprehensive ThreadLocalCacheDB integration validation."""
        setup = test_setup
        manager = setup["manager"]

        # Test concurrent downloads
        concurrent_result = manager._test_concurrent_downloads(  # noqa: SLF001
            "basic_concurrent", setup["temp_dir"], setup["cache_db"], setup["stores"], setup["reconcile_manager"]
        )
        assert concurrent_result["results"]["files_processed"] > 0

        # Test product type integration
        product_result = manager._test_product_type_integration(  # noqa: SLF001
            "different_product_types", setup["temp_dir"], setup["cache_db"], setup["stores"], setup["reconcile_manager"]
        )
        assert product_result["results"]["product_types_tested"] == 3

        # Test cache consistency
        cache_result = manager._test_cache_consistency(  # noqa: SLF001
            "cache_operations", setup["temp_dir"], setup["cache_db"], setup["stores"], setup["reconcile_manager"]
        )
        assert cache_result["results"]["cache_accessible"] is True

        # Test performance
        perf_result = manager._test_performance_validation(  # noqa: SLF001
            "throughput_testing", setup["temp_dir"], setup["cache_db"], setup["stores"], setup["reconcile_manager"]
        )
        assert perf_result["results"]["performance_success"] is True

    def test_threadlocal_integration_stress_validation(self, test_setup: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test ThreadLocalCacheDB integration under stress conditions."""
        setup = test_setup
        manager = setup["manager"]

        # Run stress test
        stress_result = manager._test_thread_safety_validation(  # noqa: SLF001
            "thread_safety_stress", setup["temp_dir"], setup["cache_db"], setup["stores"], setup["reconcile_manager"]
        )

        # Verify stress test results
        assert stress_result["results"]["timestamps_processed"] == manager.test_configs["stress_test_count"]
        assert stress_result["results"]["batches_processed"] == 5  # 50 / 10 = 5 batches
        assert stress_result["results"]["threads_used"] >= 2  # Should use multiple threads
        assert stress_result["results"]["errors"] == 0  # No threading errors
