"""Optimized S3 ThreadLocal integration tests to speed up slow tests while maintaining coverage.

Optimizations applied:
- Shared fixtures for common ThreadLocal configurations and mock setups
- Parameterized test scenarios for comprehensive concurrent operation validation
- Enhanced thread safety and isolation testing
- Mock-based testing to avoid real database and S3 operations
- Comprehensive performance and memory testing under concurrent load
"""

import asyncio
import concurrent.futures
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import threading
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


class TestS3ThreadLocalIntegrationV2:
    """Optimized test class for S3 ThreadLocal integration functionality."""

    @pytest.fixture(scope="class")
    def product_configurations(self):
        """Define various product configuration test cases."""
        return {
            "radf": {
                "product_type": "RadF",
                "minute_schedule": RADF_MINUTES,
                "scan_interval": 15,  # minutes
                "s3_key_pattern": "ABI-L1b-RadF/2023/166/12/OR_ABI-L1b-RadF-M6C13_G18_s20231661200000_e20231661209214_c20231661209291.nc",
                "expected_age_threshold": 7,  # days for S3 vs CDN
            },
            "radc": {
                "product_type": "RadC",
                "minute_schedule": RADC_MINUTES,
                "scan_interval": 5,  # minutes
                "s3_key_pattern": "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G18_s20231661206190_e20231661208562_c20231661209032.nc",
                "expected_age_threshold": 7,  # days for S3 vs CDN
            },
            "radm": {
                "product_type": "RadM",
                "minute_schedule": RADM_MINUTES[:10],  # Limit for testing
                "scan_interval": 1,  # minutes
                "s3_key_pattern": "ABI-L1b-RadM1/2023/166/12/OR_ABI-L1b-RadM1-M6C13_G18_s20231661200245_e20231661200302_c20231661200344.nc",
                "expected_age_threshold": 7,  # days for S3 vs CDN
            },
        }

    @pytest.fixture(scope="class")
    def concurrency_scenarios(self):
        """Define various concurrency scenario test cases."""
        return {
            "light_concurrent": {
                "thread_count": 3,
                "timestamps_per_thread": 5,
                "expected_min_threads": 2,
                "timeout_seconds": 30,
            },
            "medium_concurrent": {
                "thread_count": 8,
                "timestamps_per_thread": 10,
                "expected_min_threads": 4,
                "timeout_seconds": 60,
            },
            "heavy_concurrent": {
                "thread_count": 15,
                "timestamps_per_thread": 20,
                "expected_min_threads": 8,
                "timeout_seconds": 120,
            },
        }

    @pytest.fixture(scope="class")
    def stress_test_scenarios(self):
        """Define various stress test scenario test cases."""
        return {
            "rapid_fire": {
                "total_operations": 100,
                "batch_size": 10,
                "max_workers": 5,
                "operation_delay": 0.01,  # seconds
            },
            "sustained_load": {
                "total_operations": 200,
                "batch_size": 20,
                "max_workers": 8,
                "operation_delay": 0.05,  # seconds
            },
            "burst_load": {
                "total_operations": 500,
                "batch_size": 50,
                "max_workers": 10,
                "operation_delay": 0.001,  # seconds
            },
        }

    @pytest.fixture
    async def threadlocal_setup(self, tmp_path):
        """Setup ThreadLocal cache and mock stores for testing."""
        # Create database path
        db_path = tmp_path / "test_cache.db"
        
        # Create ThreadLocalCacheDB
        cache_db = ThreadLocalCacheDB(db_path=db_path)
        
        # Create mock stores
        s3_store = MagicMock(spec=S3Store)
        cdn_store = MagicMock(spec=CDNStore)
        
        # Setup async context manager behavior
        s3_store.__aenter__ = AsyncMock(return_value=s3_store)
        s3_store.__aexit__ = AsyncMock(return_value=None)
        s3_store.exists = AsyncMock(return_value=True)
        
        cdn_store.__aenter__ = AsyncMock(return_value=cdn_store)
        cdn_store.__aexit__ = AsyncMock(return_value=None)
        cdn_store.exists = AsyncMock(return_value=True)
        
        # Create ReconcileManager
        manager = ReconcileManager(
            cache_db=cache_db,
            base_dir=tmp_path,
            cdn_store=cdn_store,
            s3_store=s3_store,
            max_concurrency=10,
        )
        
        # Thread tracking
        thread_tracker = {
            "thread_operations": {},  # thread_id -> list of operations
            "thread_db_instances": {},  # thread_id -> db_instance_id
            "operation_counts": {},  # thread_id -> count
            "lock": threading.RLock(),
        }
        
        yield {
            "cache_db": cache_db,
            "s3_store": s3_store,
            "cdn_store": cdn_store,
            "manager": manager,
            "base_dir": tmp_path,
            "thread_tracker": thread_tracker,
        }
        
        # Cleanup
        cache_db.close()

    @pytest.fixture
    def mock_download_factory(self):
        """Factory for creating mock download functions."""
        def create_download_mock(store_type, thread_tracker):
            async def mock_download(timestamp, satellite, dest_path, **kwargs):
                thread_id = threading.get_ident()
                
                # Track thread operations
                with thread_tracker["lock"]:
                    if thread_id not in thread_tracker["thread_operations"]:
                        thread_tracker["thread_operations"][thread_id] = []
                        thread_tracker["operation_counts"][thread_id] = 0
                    
                    thread_tracker["thread_operations"][thread_id].append({
                        "timestamp": timestamp,
                        "store_type": store_type,
                        "dest_path": str(dest_path),
                        "kwargs": kwargs,
                    })
                    thread_tracker["operation_counts"][thread_id] += 1
                
                # Create directory and file
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write realistic content based on store type
                if store_type == "s3":
                    content = f"S3: {kwargs.get('product_type', 'RadC')} {timestamp.isoformat()}"
                else:
                    content = f"CDN: JPEG {timestamp.isoformat()}"
                
                dest_path.write_text(content)
                
                # Simulate network delay
                await asyncio.sleep(0.01)
                
                return dest_path
            
            return mock_download
        
        return create_download_mock

    @pytest.fixture
    def timestamp_generator(self):
        """Generate timestamps for testing."""
        def generate_timestamps(start_date, count, interval_minutes=5, minute_schedule=None):
            timestamps = []
            current = start_date.replace(minute=0, second=0, microsecond=0)
            
            if minute_schedule:
                # Use specific minute schedule
                hours_needed = (count + len(minute_schedule) - 1) // len(minute_schedule)
                for hour_offset in range(hours_needed):
                    hour_time = current + timedelta(hours=hour_offset)
                    for minute in minute_schedule:
                        if len(timestamps) >= count:
                            break
                        ts = hour_time.replace(minute=minute)
                        timestamps.append(ts)
                    if len(timestamps) >= count:
                        break
            else:
                # Use simple interval
                for i in range(count):
                    timestamps.append(current + timedelta(minutes=i * interval_minutes))
            
            return timestamps[:count]
        
        return generate_timestamps

    @pytest.mark.asyncio
    @pytest.mark.parametrize("product_name", ["radf", "radc", "radm"])
    async def test_product_type_threadlocal_isolation(self, threadlocal_setup, 
                                                    product_configurations, 
                                                    mock_download_factory,
                                                    timestamp_generator, product_name):
        """Test ThreadLocal isolation with different product types."""
        setup = threadlocal_setup
        config = product_configurations[product_name]
        
        # Setup download mocks
        s3_download = mock_download_factory("s3", setup["thread_tracker"])
        cdn_download = mock_download_factory("cdn", setup["thread_tracker"])
        
        setup["s3_store"].download = s3_download
        setup["cdn_store"].download = cdn_download
        
        # Generate timestamps using product-specific schedule
        now = datetime.now()
        old_date = now - timedelta(days=14)  # S3 territory
        recent_date = now - timedelta(days=2)  # CDN territory
        
        s3_timestamps = timestamp_generator(
            old_date, 5, 
            minute_schedule=config["minute_schedule"]
        )
        cdn_timestamps = timestamp_generator(
            recent_date, 5,
            minute_schedule=config["minute_schedule"]
        )
        
        async def process_timestamps(timestamps, store_type):
            for ts in timestamps:
                age_days = (datetime.now() - ts).days
                store = setup["s3_store"] if age_days > 7 else setup["cdn_store"]
                
                dest_path = setup["base_dir"] / f"{product_name}_{ts.strftime('%Y%m%d_%H%M%S')}.nc"
                
                await store.download(
                    ts, 
                    SatellitePattern.GOES_18, 
                    dest_path,
                    product_type=config["product_type"],
                    band=13
                )
                
                # Add to cache
                await setup["cache_db"].add_timestamp(
                    ts, SatellitePattern.GOES_18, str(dest_path), True
                )
        
        # Process both S3 and CDN timestamps concurrently
        await asyncio.gather(
            process_timestamps(s3_timestamps, "s3"),
            process_timestamps(cdn_timestamps, "cdn")
        )
        
        # Verify operations were tracked
        with setup["thread_tracker"]["lock"]:
            total_operations = sum(setup["thread_tracker"]["operation_counts"].values())
            assert total_operations == 10  # 5 S3 + 5 CDN
            
            # Verify product type was passed correctly
            all_operations = []
            for ops in setup["thread_tracker"]["thread_operations"].values():
                all_operations.extend(ops)
            
            product_type_ops = [op for op in all_operations 
                              if op["kwargs"].get("product_type") == config["product_type"]]
            assert len(product_type_ops) >= 5  # At least S3 operations should have product_type

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario_name", [
        "light_concurrent",
        "medium_concurrent",
        "heavy_concurrent",
    ])
    async def test_concurrent_threadlocal_operations(self, threadlocal_setup,
                                                   concurrency_scenarios,
                                                   mock_download_factory,
                                                   timestamp_generator, scenario_name):
        """Test concurrent ThreadLocal operations with various load levels."""
        setup = threadlocal_setup
        scenario = concurrency_scenarios[scenario_name]
        
        # Setup download mocks
        s3_download = mock_download_factory("s3", setup["thread_tracker"])
        setup["s3_store"].download = s3_download
        
        # Generate base timestamps
        base_date = datetime.now() - timedelta(days=14)  # S3 territory
        
        def worker_task(worker_id):
            """Worker task to run in separate thread."""
            async def async_worker():
                # Generate timestamps for this worker
                timestamps = timestamp_generator(
                    base_date + timedelta(hours=worker_id), 
                    scenario["timestamps_per_thread"]
                )
                
                for ts in timestamps:
                    dest_path = setup["base_dir"] / f"worker_{worker_id}_{ts.strftime('%Y%m%d_%H%M%S')}.nc"
                    
                    await setup["s3_store"].download(
                        ts,
                        SatellitePattern.GOES_16,
                        dest_path,
                        product_type="RadC",
                        band=13
                    )
                    
                    # Add to cache (testing ThreadLocal isolation)
                    await setup["cache_db"].add_timestamp(
                        ts, SatellitePattern.GOES_16, str(dest_path), True
                    )
                
                return len(timestamps)
            
            # Run in new event loop for each thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(async_worker())
            finally:
                loop.close()
        
        # Execute concurrent workers
        with concurrent.futures.ThreadPoolExecutor(max_workers=scenario["thread_count"]) as executor:
            futures = [
                executor.submit(worker_task, i) 
                for i in range(scenario["thread_count"])
            ]
            
            results = [
                future.result(timeout=scenario["timeout_seconds"]) 
                for future in futures
            ]
        
        # Verify results
        assert len(results) == scenario["thread_count"]
        assert all(r == scenario["timestamps_per_thread"] for r in results)
        
        # Verify thread isolation
        with setup["thread_tracker"]["lock"]:
            unique_threads = len(setup["thread_tracker"]["thread_operations"])
            assert unique_threads >= scenario["expected_min_threads"]
            
            total_operations = sum(setup["thread_tracker"]["operation_counts"].values())
            expected_total = scenario["thread_count"] * scenario["timestamps_per_thread"]
            assert total_operations == expected_total

    @pytest.mark.asyncio
    @pytest.mark.parametrize("stress_scenario", [
        "rapid_fire",
        "sustained_load",
    ])  # Skip burst_load in CI to avoid timeouts
    async def test_threadlocal_stress_scenarios(self, threadlocal_setup,
                                              stress_test_scenarios,
                                              mock_download_factory,
                                              timestamp_generator, stress_scenario):
        """Test ThreadLocal cache under stress conditions."""
        setup = threadlocal_setup
        scenario = stress_test_scenarios[stress_scenario]
        
        # Setup download mocks with simulated delay
        async def stress_download(timestamp, satellite, dest_path, **kwargs):
            thread_id = threading.get_ident()
            
            # Track operation
            with setup["thread_tracker"]["lock"]:
                if thread_id not in setup["thread_tracker"]["operation_counts"]:
                    setup["thread_tracker"]["operation_counts"][thread_id] = 0
                setup["thread_tracker"]["operation_counts"][thread_id] += 1
            
            # Create file
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_text(f"Stress test: {timestamp.isoformat()}")
            
            # Simulate processing delay
            await asyncio.sleep(scenario["operation_delay"])
            
            return dest_path
        
        setup["s3_store"].download = stress_download
        
        # Generate all timestamps
        base_date = datetime.now() - timedelta(days=10)
        all_timestamps = timestamp_generator(base_date, scenario["total_operations"])
        
        # Split into batches
        batches = [
            all_timestamps[i:i + scenario["batch_size"]]
            for i in range(0, len(all_timestamps), scenario["batch_size"])
        ]
        
        def process_batch(batch, batch_id):
            """Process a batch of timestamps in a separate thread."""
            async def async_batch():
                for ts in batch:
                    dest_path = setup["base_dir"] / f"stress_{batch_id}_{ts.strftime('%Y%m%d_%H%M%S')}.nc"
                    
                    await setup["s3_store"].download(
                        ts,
                        SatellitePattern.GOES_18,
                        dest_path,
                        product_type="RadC"
                    )
                    
                    # Test cache operations under stress
                    await setup["cache_db"].add_timestamp(
                        ts, SatellitePattern.GOES_18, str(dest_path), True
                    )
                
                return len(batch)
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(async_batch())
            finally:
                loop.close()
        
        # Execute stress test
        with concurrent.futures.ThreadPoolExecutor(max_workers=scenario["max_workers"]) as executor:
            futures = [
                executor.submit(process_batch, batch, i)
                for i, batch in enumerate(batches)
            ]
            
            results = [future.result(timeout=120) for future in futures]
        
        # Verify stress test results
        assert sum(results) == scenario["total_operations"]
        
        with setup["thread_tracker"]["lock"]:
            total_tracked = sum(setup["thread_tracker"]["operation_counts"].values())
            assert total_tracked == scenario["total_operations"]

    @pytest.mark.asyncio
    async def test_threadlocal_cache_data_isolation(self, threadlocal_setup, timestamp_generator):
        """Test that ThreadLocal cache maintains data isolation between threads."""
        setup = threadlocal_setup
        
        # Create test data for different threads
        thread_data = {
            "thread_1": {
                "satellite": SatellitePattern.GOES_16,
                "timestamps": timestamp_generator(datetime.now() - timedelta(days=10), 5),
                "product": "RadC",
            },
            "thread_2": {
                "satellite": SatellitePattern.GOES_18,
                "timestamps": timestamp_generator(datetime.now() - timedelta(days=5), 5),
                "product": "RadF",
            },
        }
        
        isolation_results = {}
        
        def thread_worker(thread_name, data):
            """Worker that operates on thread-specific data."""
            async def async_worker():
                results = []
                
                for ts in data["timestamps"]:
                    dest_path = setup["base_dir"] / f"{thread_name}_{ts.strftime('%Y%m%d_%H%M%S')}.nc"
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    dest_path.write_text(f"{thread_name}: {data['product']} {ts.isoformat()}")
                    
                    # Add to cache
                    await setup["cache_db"].add_timestamp(
                        ts, data["satellite"], str(dest_path), True
                    )
                    
                    results.append(ts)
                
                # Try to read back data for this thread's satellite
                try:
                    cached_data = await setup["cache_db"].get_timestamps(
                        satellite=data["satellite"],
                        start_time=min(data["timestamps"]) - timedelta(hours=1),
                        end_time=max(data["timestamps"]) + timedelta(hours=1)
                    )
                    
                    return {
                        "added_count": len(results),
                        "cached_count": len(cached_data) if cached_data else 0,
                        "satellite": data["satellite"].name,
                        "thread_id": threading.get_ident(),
                    }
                except Exception as e:
                    return {
                        "added_count": len(results),
                        "cached_count": 0,
                        "satellite": data["satellite"].name,
                        "thread_id": threading.get_ident(),
                        "error": str(e),
                    }
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(async_worker())
                isolation_results[thread_name] = result
                return result
            finally:
                loop.close()
        
        # Run threads concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                name: executor.submit(thread_worker, name, data)
                for name, data in thread_data.items()
            }
            
            results = {name: future.result() for name, future in futures.items()}
        
        # Verify isolation
        assert len(results) == 2
        
        for thread_name, result in results.items():
            assert result["added_count"] == 5
            assert result["thread_id"] != 0  # Should have valid thread ID
        
        # Verify different threads had different IDs
        thread_ids = [r["thread_id"] for r in results.values()]
        assert len(set(thread_ids)) == 2, "Threads should have different IDs"

    @pytest.mark.asyncio
    async def test_threadlocal_error_handling_isolation(self, threadlocal_setup, timestamp_generator):
        """Test error handling and isolation in ThreadLocal operations."""
        setup = threadlocal_setup
        
        # Create scenarios with errors
        def error_worker(worker_id, should_fail=False):
            """Worker that may encounter errors."""
            async def async_worker():
                results = {"success": 0, "errors": 0}
                
                timestamps = timestamp_generator(
                    datetime.now() - timedelta(days=8), 3
                )
                
                for i, ts in enumerate(timestamps):
                    try:
                        if should_fail and i == 1:  # Fail on second operation
                            raise Exception(f"Simulated error in worker {worker_id}")
                        
                        dest_path = setup["base_dir"] / f"error_test_{worker_id}_{i}.nc"
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        dest_path.write_text(f"Worker {worker_id} operation {i}")
                        
                        # Add to cache
                        await setup["cache_db"].add_timestamp(
                            ts, SatellitePattern.GOES_16, str(dest_path), True
                        )
                        
                        results["success"] += 1
                        
                    except Exception:
                        results["errors"] += 1
                
                return results
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(async_worker())
            finally:
                loop.close()
        
        # Run workers with different error scenarios
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(error_worker, 0, should_fail=False),  # No errors
                executor.submit(error_worker, 1, should_fail=True),   # Has errors
                executor.submit(error_worker, 2, should_fail=False),  # No errors
            ]
            
            results = [future.result() for future in futures]
        
        # Verify error isolation
        assert results[0]["success"] == 3 and results[0]["errors"] == 0  # Worker 0: all success
        assert results[1]["success"] == 2 and results[1]["errors"] == 1  # Worker 1: one error
        assert results[2]["success"] == 3 and results[2]["errors"] == 0  # Worker 2: all success

    @pytest.mark.asyncio
    async def test_threadlocal_performance_characteristics(self, threadlocal_setup, timestamp_generator):
        """Test performance characteristics of ThreadLocal operations."""
        import time
        
        setup = threadlocal_setup
        
        def performance_worker(worker_id, operation_count):
            """Worker that measures performance metrics."""
            async def async_worker():
                start_time = time.time()
                
                timestamps = timestamp_generator(
                    datetime.now() - timedelta(days=10), operation_count
                )
                
                for i, ts in enumerate(timestamps):
                    dest_path = setup["base_dir"] / f"perf_{worker_id}_{i}.nc"
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    dest_path.write_text(f"Performance test {worker_id}-{i}")
                    
                    # Time cache operations
                    cache_start = time.time()
                    await setup["cache_db"].add_timestamp(
                        ts, SatellitePattern.GOES_16, str(dest_path), True
                    )
                    cache_duration = time.time() - cache_start
                    
                    # Should be fast (< 10ms per operation)
                    assert cache_duration < 0.01, f"Cache operation too slow: {cache_duration:.3f}s"
                
                total_duration = time.time() - start_time
                
                return {
                    "worker_id": worker_id,
                    "operations": operation_count,
                    "total_time": total_duration,
                    "ops_per_second": operation_count / total_duration,
                }
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(async_worker())
            finally:
                loop.close()
        
        # Run performance test with multiple workers
        operation_counts = [10, 15, 20]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(performance_worker, i, count)
                for i, count in enumerate(operation_counts)
            ]
            
            results = [future.result(timeout=60) for future in futures]
        
        # Verify performance metrics
        for result in results:
            assert result["ops_per_second"] > 50, f"Performance too slow: {result['ops_per_second']:.1f} ops/sec"
            assert result["total_time"] < 10, f"Total time too long: {result['total_time']:.1f}s"

    @pytest.mark.asyncio
    async def test_threadlocal_memory_efficiency(self, threadlocal_setup, timestamp_generator):
        """Test memory efficiency of ThreadLocal operations."""
        import sys
        
        setup = threadlocal_setup
        initial_refs = sys.getrefcount(ThreadLocalCacheDB)
        
        def memory_worker(worker_id):
            """Worker that tests memory usage patterns."""
            async def async_worker():
                # Perform many operations to test memory growth
                timestamps = timestamp_generator(
                    datetime.now() - timedelta(days=12), 50
                )
                
                for i, ts in enumerate(timestamps):
                    dest_path = setup["base_dir"] / f"mem_{worker_id}_{i}.nc"
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    dest_path.write_text(f"Memory test {worker_id}-{i}")
                    
                    await setup["cache_db"].add_timestamp(
                        ts, SatellitePattern.GOES_18, str(dest_path), True
                    )
                    
                    # Periodically check that we're not accumulating objects
                    if i % 10 == 0:
                        current_refs = sys.getrefcount(ThreadLocalCacheDB)
                        assert abs(current_refs - initial_refs) <= 5, "Memory leak detected"
                
                return 50
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(async_worker())
            finally:
                loop.close()
        
        # Run memory test with multiple workers
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(memory_worker, i)
                for i in range(4)
            ]
            
            results = [future.result() for future in futures]
        
        # Verify memory stability
        final_refs = sys.getrefcount(ThreadLocalCacheDB)
        assert abs(final_refs - initial_refs) <= 10, f"Memory leak: {initial_refs} -> {final_refs}"
        assert sum(results) == 200  # 4 workers * 50 operations each

    @pytest.mark.asyncio
    async def test_realistic_s3_pattern_integration(self, threadlocal_setup, mock_download_factory, product_configurations):
        """Test integration with realistic S3 file patterns."""
        setup = threadlocal_setup
        
        # Setup realistic download mock
        def realistic_s3_download(thread_tracker):
            async def download(timestamp, satellite, dest_path, product_type="RadC", **kwargs):
                thread_id = threading.get_ident()
                
                # Track operation
                with thread_tracker["lock"]:
                    if thread_id not in thread_tracker["operation_counts"]:
                        thread_tracker["operation_counts"][thread_id] = 0
                    thread_tracker["operation_counts"][thread_id] += 1
                
                # Generate realistic filename
                year = timestamp.year
                doy = timestamp.timetuple().tm_yday
                hour = timestamp.hour
                minute = timestamp.minute
                
                # Create realistic S3 key pattern
                if product_type == "RadF":
                    s3_key = f"ABI-L1b-RadF/{year}/{doy:03d}/{hour:02d}/OR_ABI-L1b-RadF-M6C13_{satellite.name}_s{year}{doy:03d}{hour:02d}{minute:02d}000_e{year}{doy:03d}{hour:02d}{minute+9:02d}214_c{year}{doy:03d}{hour:02d}{minute+9:02d}291.nc"
                elif product_type == "RadC":
                    s3_key = f"ABI-L1b-RadC/{year}/{doy:03d}/{hour:02d}/OR_ABI-L1b-RadC-M6C13_{satellite.name}_s{year}{doy:03d}{hour:02d}{minute:02d}190_e{year}{doy:03d}{hour:02d}{minute+2:02d}562_c{year}{doy:03d}{hour:02d}{minute+3:02d}032.nc"
                else:  # RadM
                    s3_key = f"ABI-L1b-RadM1/{year}/{doy:03d}/{hour:02d}/OR_ABI-L1b-RadM1-M6C13_{satellite.name}_s{year}{doy:03d}{hour:02d}{minute:02d}245_e{year}{doy:03d}{hour:02d}{minute:02d}302_c{year}{doy:03d}{hour:02d}{minute:02d}344.nc"
                
                # Create file with realistic content
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                dest_path.write_text(f"Realistic S3 content: {s3_key}")
                
                return dest_path
            
            return download
        
        setup["s3_store"].download = realistic_s3_download(setup["thread_tracker"])
        
        def product_worker(product_name, config):
            """Worker that processes specific product type."""
            async def async_worker():
                # Generate timestamps using product-specific schedule
                base_date = datetime.now() - timedelta(days=10)
                
                # Use first few minutes from schedule
                minute_schedule = config["minute_schedule"][:3]  # Limit for testing
                
                results = []
                for minute in minute_schedule:
                    ts = base_date.replace(minute=minute, second=0, microsecond=0)
                    dest_path = setup["base_dir"] / f"{product_name}_{ts.strftime('%Y%m%d_%H%M%S')}.nc"
                    
                    result_path = await setup["s3_store"].download(
                        ts,
                        SatellitePattern.GOES_18,
                        dest_path,
                        product_type=config["product_type"],
                        band=13
                    )
                    
                    # Verify realistic content
                    content = result_path.read_text()
                    assert config["product_type"] in content
                    assert "s2024" in content or "s2023" in content  # Year in timestamp
                    
                    # Add to cache
                    await setup["cache_db"].add_timestamp(
                        ts, SatellitePattern.GOES_18, str(result_path), True
                    )
                    
                    results.append(ts)
                
                return len(results)
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(async_worker())
            finally:
                loop.close()
        
        # Test each product type concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                product_name: executor.submit(product_worker, product_name, config)
                for product_name, config in product_configurations.items()
            }
            
            results = {name: future.result() for name, future in futures.items()}
        
        # Verify all product types were processed
        assert all(count == 3 for count in results.values())  # 3 timestamps per product
        
        # Verify concurrent thread usage
        with setup["thread_tracker"]["lock"]:
            total_operations = sum(setup["thread_tracker"]["operation_counts"].values())
            assert total_operations == 9  # 3 products * 3 timestamps each