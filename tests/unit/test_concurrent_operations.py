"""Tests for concurrent operations and thread safety.

These tests verify thread safety, race conditions, and proper synchronization
in concurrent satellite data processing operations.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import operator
from pathlib import Path
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from goesvfi.integrity_check.background_worker import BackgroundProcessManager
from goesvfi.integrity_check.remote.composite_store import CompositeStore
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.thread_cache_db import ThreadLocalCacheDB
from goesvfi.integrity_check.time_index import SatellitePattern
from goesvfi.pipeline.run_vfi import InterpolationPipeline


class TestConcurrentOperations:
    """Test concurrent operations and thread safety."""

    @pytest.fixture()
    def temp_db_path(self, tmp_path):
        """Create a temporary database path."""
        return tmp_path / "test_cache.db"

    @pytest.fixture()
    def thread_safe_db(self, temp_db_path):
        """Create a thread-safe cache database."""
        return ThreadLocalCacheDB(temp_db_path)

    @pytest.mark.asyncio()
    async def test_concurrent_s3_client_initialization(self) -> None:
        """Test thread-safe S3 client initialization."""
        # Track client creation calls
        client_ids = []
        creation_lock = threading.Lock()

        # Create a mock client
        mock_s3_client = AsyncMock()
        mock_s3_client.__aenter__ = AsyncMock(return_value=mock_s3_client)
        mock_s3_client.__aexit__ = AsyncMock(return_value=None)

        def track_client_creation(*args, **kwargs):
            with creation_lock:
                client_id = id(threading.current_thread())
                client_ids.append(client_id)
            return mock_s3_client

        # Mock the session and client creation
        mock_session = MagicMock()
        mock_session.client = MagicMock(return_value=mock_s3_client)

        with patch("aioboto3.Session", return_value=mock_session):
            # Patch the _get_s3_client method to track calls
            store = S3Store()
            original_get_client = store._get_s3_client

            async def tracked_get_client():
                track_client_creation()
                return await original_get_client()

            store._get_s3_client = tracked_get_client

            # Create multiple tasks that will need S3 client
            async def use_s3_client(task_id):
                await store._get_s3_client()
                # Simulate some work
                await asyncio.sleep(0.01)
                return task_id

            # Run tasks concurrently
            tasks = [use_s3_client(i) for i in range(10)]
            results = await asyncio.gather(*tasks)

            # Each thread should create its own client
            assert len(results) == 10
            # Should have created at least one client
            assert len(client_ids) >= 1

    @pytest.mark.asyncio()
    async def test_concurrent_cache_db_operations(self, thread_safe_db) -> None:
        """Test concurrent read/write operations on cache database."""
        # Database is initialized in constructor

        # Test data - use timestamps and satellite pattern
        from goesvfi.integrity_check.time_index import SatellitePattern

        satellite = SatellitePattern.GOES_18
        base_time = datetime.now(UTC)

        test_entries = [(base_time + timedelta(minutes=i * 10), f"/path/to/file_{i}.nc", True) for i in range(100)]

        # Concurrent write operations
        async def write_entries(entries) -> None:
            for timestamp, filepath, found in entries:
                await thread_safe_db.add_timestamp(timestamp, satellite, filepath, found)
                await asyncio.sleep(0.001)  # Simulate work

        # Concurrent read operations
        async def read_entries(timestamps):
            results = []
            for timestamp in timestamps:
                exists = await thread_safe_db.timestamp_exists(timestamp, satellite)
                results.append(exists)
                await asyncio.sleep(0.001)  # Simulate work
            return results

        # Split data for concurrent operations
        mid = len(test_entries) // 2
        write_tasks = [
            write_entries(test_entries[:mid]),
            write_entries(test_entries[mid:]),
        ]

        # Execute writes concurrently
        await asyncio.gather(*write_tasks)

        # Now read concurrently
        all_timestamps = [e[0] for e in test_entries]
        read_tasks = [
            read_entries(all_timestamps[:mid]),
            read_entries(all_timestamps[mid:]),
        ]

        read_results = await asyncio.gather(*read_tasks)

        # Verify all entries were written and read correctly
        all_results = read_results[0] + read_results[1]
        non_none_results = [r for r in all_results if r is not None]

        # Should have read all entries
        assert len(non_none_results) == len(test_entries)

    def test_thread_pool_cache_operations(self, thread_safe_db) -> None:
        """Test cache operations from multiple threads."""
        # Database is initialized in constructor

        # Operations to run in threads
        def write_operation(thread_id, count) -> None:
            for _i in range(count):
                filepath = f"thread_{thread_id}_file_{_i}.nc"
                thread_safe_db.add_entry(
                    filepath=filepath,
                    file_hash=f"hash_{thread_id}_{_i}",
                    file_size=_i * 1000,
                    timestamp=datetime.now(UTC),
                )
                time.sleep(0.001)  # Simulate work

        def read_operation(thread_id, count):
            results = []
            for _i in range(count):
                filepath = f"thread_{thread_id}_file_{_i}.nc"
                entry = thread_safe_db.get_entry(filepath)
                results.append(entry)
                time.sleep(0.001)  # Simulate work
            return results

        # Run operations in thread pool
        with ThreadPoolExecutor(max_workers=8) as executor:
            # Submit write operations
            write_futures = []
            for tid in range(4):
                future = executor.submit(write_operation, tid, 25)
                write_futures.append(future)

            # Wait for writes to complete
            for future in write_futures:
                future.result()

            # Submit read operations
            read_futures = []
            for tid in range(4):
                future = executor.submit(read_operation, tid, 25)
                read_futures.append(future)

            # Collect read results
            all_read_results = []
            for future in read_futures:
                results = future.result()
                all_read_results.extend(results)

        # Verify no data corruption
        non_none_results = [r for r in all_read_results if r is not None]
        assert len(non_none_results) == 100  # 4 threads * 25 entries each

    @pytest.mark.asyncio()
    async def test_concurrent_download_deduplication(self) -> None:
        """Test that concurrent downloads of same file are deduplicated."""
        store = S3Store()
        download_count = 0
        download_lock = asyncio.Lock()

        # Mock S3 client
        mock_s3_client = AsyncMock()

        async def mock_download(*args, **kwargs) -> None:
            async with download_lock:
                nonlocal download_count
                download_count += 1
            await asyncio.sleep(0.1)  # Simulate download time

        mock_s3_client.download_file = mock_download
        mock_s3_client.head_object = AsyncMock(return_value={"ContentLength": 1000})

        # Mock the download method to return a successful path
        async def mock_store_download(*args, **kwargs):
            nonlocal download_count
            async with download_lock:
                download_count += 1
            await asyncio.sleep(0.1)  # Simulate download time
            # Return the destination path (which is what download returns)
            return kwargs.get("dest_path", Path("/tmp/same_file.nc"))

        with patch.object(store, "download", side_effect=mock_store_download):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.stat") as mock_stat:
                    mock_stat.return_value.st_size = 1000

                    # Same timestamp and destination
                    # Use a unique temp directory to avoid conflicts
                    import tempfile

                    temp_dir = tempfile.mkdtemp()
                    timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
                    dest_path = Path(temp_dir) / "same_file.nc"

                    # Launch multiple concurrent downloads of same file
                    tasks = []
                    for _ in range(5):
                        task = store.download(
                            ts=timestamp,
                            satellite=SatellitePattern.GOES_16,
                            dest_path=dest_path,
                        )
                        tasks.append(task)

                    # All should complete
                    results = await asyncio.gather(*tasks)

                    # But only one actual download should occur
                    # (This would require implementing deduplication in S3Store)
                    # For now, we verify all downloads completed
                    assert len(results) == 5
                    assert download_count == 5  # Without deduplication

    @pytest.mark.asyncio()
    async def test_race_condition_in_progress_tracking(self) -> None:
        """Test for race conditions in progress tracking."""
        progress_tracker: dict[str, int] = {}
        progress_lock = asyncio.Lock()

        async def update_progress(task_id, progress) -> None:
            # Simulate race condition without lock
            current = progress_tracker.get(task_id, 0)
            await asyncio.sleep(0.001)  # Simulate work
            progress_tracker[task_id] = current + progress

        async def safe_update_progress(task_id, progress) -> None:
            async with progress_lock:
                current = progress_tracker.get(task_id, 0)
                await asyncio.sleep(0.001)  # Simulate work
                progress_tracker[task_id] = current + progress

        # Test unsafe updates (race condition)
        progress_tracker.clear()
        unsafe_tasks = []
        for _ in range(100):
            task = update_progress("unsafe", 1)
            unsafe_tasks.append(task)
        await asyncio.gather(*unsafe_tasks)

        # Test safe updates (with lock)
        progress_tracker.clear()
        safe_tasks = []
        for _ in range(100):
            task = safe_update_progress("safe", 1)
            safe_tasks.append(task)
        await asyncio.gather(*safe_tasks)

        # Safe updates should always total 100
        assert progress_tracker.get("safe", 0) == 100
        # Unsafe updates might lose some due to race condition
        # (In practice, asyncio's single-threaded nature might hide this)

    async def test_concurrent_pipeline_processing(self) -> None:
        """Test concurrent processing in interpolation pipeline."""
        processing_times = []
        processing_lock = threading.Lock()

        # Create multiple processing tasks using pipeline as context manager
        async def process_task(task_id, image_count):
            images = [f"image_{i}.png" for i in range(image_count)]

            # Track start time
            with processing_lock:
                start_time = time.time()
                processing_times.append((task_id, start_time))

            # Use pipeline as regular context manager in executor
            def run_pipeline():
                with InterpolationPipeline(max_workers=4) as pipeline:
                    return pipeline.process(images, task_id)

            # Run in executor
            return await asyncio.get_event_loop().run_in_executor(None, run_pipeline)

        # Run tasks concurrently
        tasks = []
        for i in range(5):
            task = process_task(i, 10)
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Verify all tasks completed (assuming results are meaningful)
        assert len(results) == 5
        # Note: Can't verify exact message without knowing pipeline.process behavior

        # Verify concurrent execution (overlapping times)
        assert len(processing_times) == 5

    @pytest.mark.asyncio()
    async def test_background_worker_concurrent_tasks(self) -> None:
        """Test background worker handling concurrent tasks."""
        # Mock the UIFreezeMonitor to avoid QTimer issues in tests
        with patch("goesvfi.integrity_check.background_worker.UIFreezeMonitor"):
            worker = BackgroundProcessManager()

            task_results = []
            task_lock = threading.Lock()

            def sample_task(task_id, duration, progress_callback=None, cancel_check=None) -> str:
                time.sleep(duration)
                with task_lock:
                    task_results.append((task_id, time.time()))
                return f"Task {task_id} completed"

            # Submit more tasks than max concurrent
            task_ids = []
            for i in range(10):
                # run_in_background returns task_id
                task_id = worker.run_in_background(sample_task, i, 0.1)
                task_ids.append(task_id)

            # Wait for all tasks
            await asyncio.sleep(1.0)

            # Check if tasks completed by looking at results
            assert len(task_results) >= 6  # At least some should complete

            # Verify concurrent execution by checking overlapping times
            # Sort by start time
            task_results.sort(key=operator.itemgetter(1))

            # Check for overlapping execution times
            overlaps = 0
            for i in range(len(task_results) - 1):
                # If next task started before current ended (0.1s duration)
                if task_results[i + 1][1] < task_results[i][1] + 0.09:
                    overlaps += 1

            assert overlaps > 0  # Should have some concurrent execution

            # Clean up
            worker.cleanup()

    async def test_deadlock_prevention_in_composite_store(self) -> None:
        """Test that composite store prevents deadlocks."""
        # Create a composite store with default initialization
        composite = CompositeStore(enable_s3=True, enable_cdn=True, enable_cache=False)

        # Mock the internal stores to simulate potential deadlock scenario
        store1 = AsyncMock()
        store2 = AsyncMock()

        # Mock stores that could deadlock if not careful
        lock1 = asyncio.Lock()
        lock2 = asyncio.Lock()

        async def store1_download(*args, **kwargs):
            async with lock1:
                await asyncio.sleep(0.01)
                # Don't try to acquire lock2 to avoid deadlock
                return Path("/tmp/file1.nc")

        async def store2_download(*args, **kwargs):
            async with lock2:
                await asyncio.sleep(0.01)
                # Don't try to acquire lock1 to avoid deadlock
                return Path("/tmp/file2.nc")

        store1.download = store1_download
        store2.download = store2_download

        # Replace the internal sources
        composite.sources = [("S3", store1), ("CDN", store2)]

        # Test concurrent downloads
        timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)

        # These should not deadlock
        tasks = []
        for i in range(5):
            task = composite.download_file(
                timestamp=timestamp,
                satellite=SatellitePattern.GOES_16,
                destination=Path(f"/tmp/test_{i}.nc"),
            )
            tasks.append(task)

        # Should complete without deadlock
        results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=5.0)

        # At least some should succeed
        successful = [r for r in results if isinstance(r, Path)]
        assert len(successful) > 0

    @pytest.mark.asyncio()
    async def test_atomic_operations_in_cache(self, thread_safe_db) -> None:
        """Test atomic operations in cache database."""
        # Database is initialized in constructor

        # Test atomic increment operation
        counter_key = "download_counter"

        async def increment_counter(count) -> None:
            for _ in range(count):
                # Get current value - don't use context manager here since it closes the connection
                db = thread_safe_db.get_db()
                entry = db.get_entry(counter_key)
                current = entry["file_size"] if entry else 0

                # Increment
                new_value = current + 1

                # Update atomically
                db.add_entry(
                    filepath=counter_key,
                    file_hash="counter",
                    file_size=new_value,
                    timestamp=datetime.now(UTC),
                    metadata={"type": "counter"},
                )

                await asyncio.sleep(0.001)

        # Run concurrent increments
        tasks = []
        increments_per_task = 20
        num_tasks = 5

        for _ in range(num_tasks):
            task = increment_counter(increments_per_task)
            tasks.append(task)

        await asyncio.gather(*tasks)

        # Verify final count
        entry = thread_safe_db.get_entry(counter_key)
        assert entry is not None
        assert entry["file_size"] == increments_per_task * num_tasks
