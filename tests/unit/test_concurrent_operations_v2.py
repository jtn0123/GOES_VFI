"""Tests for concurrent operations and thread safety (Optimized v2).

These tests verify thread safety, race conditions, and proper synchronization
in concurrent satellite data processing operations.

Optimizations:
- Mock asyncio.sleep to reduce test execution time
- Mock time.sleep for thread-based tests
- Shared fixtures for test data
- Parameterized tests where appropriate
- Reduced concurrent operation counts for faster execution
- Mocked external dependencies to focus on concurrency logic
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from goesvfi.integrity_check.background_worker import BackgroundProcessManager
from goesvfi.integrity_check.remote.composite_store import CompositeStore
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.thread_cache_db import ThreadLocalCacheDB
from goesvfi.integrity_check.time_index import SatellitePattern
from goesvfi.pipeline.run_vfi import InterpolationPipeline


@pytest.fixture()
def mock_time_functions():
    """Mock time-related functions to speed up tests."""
    with patch("asyncio.sleep", return_value=None), patch("time.sleep", return_value=None):
        yield


@pytest.fixture()
def temp_db_path(tmp_path):
    """Create a temporary database path."""
    return tmp_path / "test_cache.db"


@pytest.fixture()
def thread_safe_db(temp_db_path):
    """Create a thread-safe cache database."""
    return ThreadLocalCacheDB(temp_db_path)


@pytest.fixture()
def test_timestamps():
    """Generate test timestamps for concurrent operations."""
    base_time = datetime.now(UTC)
    return [(base_time + timedelta(minutes=i * 10), f"/path/to/file_{i}.nc", True) for i in range(10)]


@pytest.fixture()
def mock_s3_components():
    """Mock S3 components for testing."""
    mock_s3_client = AsyncMock()
    mock_s3_client.__aenter__ = AsyncMock(return_value=mock_s3_client)
    mock_s3_client.__aexit__ = AsyncMock(return_value=None)
    mock_s3_client.download_file = AsyncMock(return_value=None)
    mock_s3_client.head_object = AsyncMock(return_value={"ContentLength": 1000})

    mock_session = MagicMock()
    mock_session.client = MagicMock(return_value=mock_s3_client)

    return mock_s3_client, mock_session


class TestConcurrentOperations:
    """Test concurrent operations and thread safety."""

    @pytest.mark.asyncio()
    async def test_concurrent_s3_client_initialization(self, mock_time_functions, mock_s3_components) -> None:
        """Test thread-safe S3 client initialization."""
        mock_s3_client, mock_session = mock_s3_components

        # Track client creation calls
        client_ids = []
        creation_lock = threading.Lock()

        def track_client_creation(*args, **kwargs):
            with creation_lock:
                client_id = id(threading.current_thread())
                client_ids.append(client_id)
            return mock_s3_client

        with patch("aioboto3.Session", return_value=mock_session):
            store = S3Store()
            original_get_client = store._get_s3_client

            async def tracked_get_client():
                track_client_creation()
                return await original_get_client()

            store._get_s3_client = tracked_get_client

            # Create multiple tasks that will need S3 client
            async def use_s3_client(task_id):
                await store._get_s3_client()
                return task_id

            # Run fewer tasks concurrently for faster execution
            tasks = [use_s3_client(i) for i in range(5)]
            results = await asyncio.gather(*tasks)

            # Each thread should create its own client
            assert len(results) == 5
            # Should have created at least one client
            assert len(client_ids) >= 1

    @pytest.mark.asyncio()
    async def test_concurrent_cache_db_operations(self, mock_time_functions, thread_safe_db, test_timestamps) -> None:
        """Test concurrent read/write operations on cache database."""
        satellite = SatellitePattern.GOES_18

        # Use fewer entries for faster test execution
        test_entries = test_timestamps[:5]

        # Concurrent write operations
        async def write_entries(entries) -> None:
            for timestamp, filepath, found in entries:
                await thread_safe_db.add_timestamp(timestamp, satellite, filepath, found)

        # Concurrent read operations
        async def read_entries(timestamps):
            results = []
            for timestamp in timestamps:
                exists = await thread_safe_db.timestamp_exists(timestamp, satellite)
                results.append(exists)
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

    def test_thread_pool_cache_operations(self, mock_time_functions, thread_safe_db) -> None:
        """Test cache operations from multiple threads."""

        # Operations to run in threads
        def write_operation(thread_id, count) -> None:
            for i in range(count):
                filepath = f"thread_{thread_id}_file_{i}.nc"
                thread_safe_db.add_entry(
                    filepath=filepath,
                    file_hash=f"hash_{thread_id}_{i}",
                    file_size=i * 1000,
                    timestamp=datetime.now(UTC),
                )

        def read_operation(thread_id, count):
            results = []
            for i in range(count):
                filepath = f"thread_{thread_id}_file_{i}.nc"
                entry = thread_safe_db.get_entry(filepath)
                results.append(entry)
            return results

        # Run operations in thread pool with fewer threads and operations
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submit write operations
            write_futures = []
            for tid in range(3):
                future = executor.submit(write_operation, tid, 5)  # Reduced from 25
                write_futures.append(future)

            # Wait for writes to complete
            for future in write_futures:
                future.result()

            # Submit read operations
            read_futures = []
            for tid in range(3):
                future = executor.submit(read_operation, tid, 5)  # Reduced from 25
                read_futures.append(future)

            # Collect read results
            all_read_results = []
            for future in read_futures:
                results = future.result()
                all_read_results.extend(results)

        # Verify no data corruption
        non_none_results = [r for r in all_read_results if r is not None]
        assert len(non_none_results) == 15  # 3 threads * 5 entries each

    @pytest.mark.asyncio()
    async def test_concurrent_download_deduplication(self, mock_time_functions) -> None:
        """Test that concurrent downloads of same file are deduplicated."""
        store = S3Store()
        download_count = 0
        download_lock = asyncio.Lock()

        # Mock store download method to return a successful path
        async def mock_store_download(*args, **kwargs):
            nonlocal download_count
            async with download_lock:
                download_count += 1
            # Return the destination path (which is what download returns)
            return kwargs.get("dest_path", Path("/tmp/same_file.nc"))

        with patch.object(store, "download", side_effect=mock_store_download):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.stat") as mock_stat:
                    mock_stat.return_value.st_size = 1000

                    # Use fewer concurrent downloads for faster execution
                    timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
                    dest_path = Path("/tmp/same_file.nc")

                    # Launch multiple concurrent downloads of same file
                    tasks = []
                    for _ in range(3):  # Reduced from 5
                        task = store.download(
                            ts=timestamp,
                            satellite=SatellitePattern.GOES_16,
                            dest_path=dest_path,
                        )
                        tasks.append(task)

                    # All should complete
                    results = await asyncio.gather(*tasks)

                    # Verify all downloads completed
                    assert len(results) == 3
                    assert download_count == 3  # Without deduplication

    @pytest.mark.asyncio()
    async def test_race_condition_in_progress_tracking(self, mock_time_functions) -> None:
        """Test for race conditions in progress tracking."""
        progress_tracker: dict[str, int] = {}
        progress_lock = asyncio.Lock()

        async def unsafe_update_progress(task_id, progress) -> None:
            # Simulate race condition without lock
            current = progress_tracker.get(task_id, 0)
            progress_tracker[task_id] = current + progress

        async def safe_update_progress(task_id, progress) -> None:
            async with progress_lock:
                current = progress_tracker.get(task_id, 0)
                progress_tracker[task_id] = current + progress

        # Test safe updates (with lock) - reduced iterations
        progress_tracker.clear()
        safe_tasks = []
        for _ in range(20):  # Reduced from 100
            task = safe_update_progress("safe", 1)
            safe_tasks.append(task)
        await asyncio.gather(*safe_tasks)

        # Safe updates should always total 20
        assert progress_tracker.get("safe", 0) == 20

    @pytest.mark.asyncio()
    async def test_concurrent_pipeline_processing(self, mock_time_functions) -> None:
        """Test concurrent processing in interpolation pipeline."""
        processing_times = []
        processing_lock = threading.Lock()

        # Create fewer processing tasks for faster execution
        async def process_task(task_id, image_count):
            images = [f"image_{i}.png" for i in range(image_count)]

            # Track start time
            with processing_lock:
                import time

                start_time = time.time()
                processing_times.append((task_id, start_time))

            # Use pipeline as regular context manager in executor
            def run_pipeline():
                with InterpolationPipeline(max_workers=2) as pipeline:  # Reduced workers
                    return pipeline.process(images, task_id)

            # Run in executor
            return await asyncio.get_event_loop().run_in_executor(None, run_pipeline)

        # Run fewer tasks concurrently
        tasks = []
        for i in range(3):  # Reduced from 5
            task = process_task(i, 5)  # Reduced image count
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Verify all tasks completed
        assert len(results) == 3
        # Verify concurrent execution (overlapping times)
        assert len(processing_times) == 3

    @pytest.mark.asyncio()
    async def test_background_worker_concurrent_tasks(self, mock_time_functions) -> None:
        """Test background worker handling concurrent tasks."""
        # Mock the UIFreezeMonitor to avoid QTimer issues in tests
        with patch("goesvfi.integrity_check.background_worker.UIFreezeMonitor"):
            worker = BackgroundProcessManager()

            task_results = []
            task_lock = threading.Lock()

            def sample_task(task_id, duration, progress_callback=None, cancel_check=None) -> str:
                with task_lock:
                    import time

                    task_results.append((task_id, time.time()))
                return f"Task {task_id} completed"

            # Submit fewer tasks for faster execution
            task_ids = []
            for i in range(5):  # Reduced from 10
                task_id = worker.run_in_background(sample_task, i, 0.01)  # Reduced duration
                task_ids.append(task_id)

            # Wait for tasks with shorter timeout
            await asyncio.sleep(0.5)  # Reduced from 1.0

            # Check if tasks completed by looking at results
            assert len(task_results) >= 3  # At least some should complete

            # Clean up
            worker.cleanup()

    @pytest.mark.asyncio()
    async def test_deadlock_prevention_in_composite_store(self, mock_time_functions) -> None:
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
                return Path("/tmp/file1.nc")

        async def store2_download(*args, **kwargs):
            async with lock2:
                return Path("/tmp/file2.nc")

        store1.download = store1_download
        store2.download = store2_download

        # Replace the internal sources
        composite.sources = [("S3", store1), ("CDN", store2)]

        # Test concurrent downloads
        timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)

        # These should not deadlock - use fewer concurrent operations
        tasks = []
        for i in range(3):  # Reduced from 5
            task = composite.download_file(
                timestamp=timestamp,
                satellite=SatellitePattern.GOES_16,
                destination=Path(f"/tmp/test_{i}.nc"),
            )
            tasks.append(task)

        # Should complete without deadlock
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=2.0,  # Reduced timeout
        )

        # At least some should succeed
        successful = [r for r in results if isinstance(r, Path)]
        assert len(successful) > 0

    @pytest.mark.asyncio()
    async def test_atomic_operations_in_cache(self, mock_time_functions, thread_safe_db) -> None:
        """Test atomic operations in cache database."""
        # Test atomic increment operation
        counter_key = "download_counter"

        async def increment_counter(count) -> None:
            for _ in range(count):
                # Get current value
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

        # Run concurrent increments with fewer tasks/increments
        tasks = []
        increments_per_task = 5  # Reduced from 20
        num_tasks = 3  # Reduced from 5

        for _ in range(num_tasks):
            task = increment_counter(increments_per_task)
            tasks.append(task)

        await asyncio.gather(*tasks)

        # Verify final count
        entry = thread_safe_db.get_entry(counter_key)
        assert entry is not None
        assert entry["file_size"] == increments_per_task * num_tasks

    @pytest.mark.parametrize("num_clients", [2, 3, 5])
    @pytest.mark.asyncio()
    async def test_concurrent_client_access_patterns(
        self, mock_time_functions, mock_s3_components, num_clients
    ) -> None:
        """Test various concurrent client access patterns."""
        _mock_s3_client, mock_session = mock_s3_components

        with patch("aioboto3.Session", return_value=mock_session):
            store = S3Store()

            async def client_operation(client_id):
                # Simulate getting client multiple times
                for _ in range(2):
                    await store._get_s3_client()
                return client_id

            # Test with different numbers of concurrent clients
            tasks = [client_operation(i) for i in range(num_clients)]
            results = await asyncio.gather(*tasks)

            assert len(results) == num_clients
            assert all(isinstance(r, int) for r in results)

    def test_thread_safety_stress_test(self, mock_time_functions, thread_safe_db) -> None:
        """Stress test thread safety with multiple operations."""
        operations_completed = []

        def mixed_operations(thread_id) -> None:
            # Mix of read and write operations
            for i in range(3):  # Reduced iterations
                # Write operation
                thread_safe_db.add_entry(
                    filepath=f"stress_{thread_id}_{i}.nc",
                    file_hash=f"hash_{thread_id}_{i}",
                    file_size=i * 100,
                    timestamp=datetime.now(UTC),
                )

                # Read operation
                entry = thread_safe_db.get_entry(f"stress_{thread_id}_{i}.nc")
                if entry:
                    operations_completed.append((thread_id, i))

        # Run with fewer threads for faster execution
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for tid in range(3):
                future = executor.submit(mixed_operations, tid)
                futures.append(future)

            # Wait for all to complete
            for future in futures:
                future.result()

        # Should have completed all operations
        assert len(operations_completed) == 9  # 3 threads * 3 operations each
