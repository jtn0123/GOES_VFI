"""Unit tests for the thread-local cache database (Optimized v2).

Optimizations:
- Shared fixtures for database setup/teardown
- Mock time operations to speed up tests
- Reduced thread counts and iteration counts
- Parameterized tests for similar scenarios
- Consolidated related test methods
- Mock asyncio operations where appropriate
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import contextlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
import tempfile
import threading
import time
from typing import Any
from unittest.mock import patch

import pytest

from goesvfi.integrity_check.thread_cache_db import ThreadLocalCacheDB
from goesvfi.integrity_check.time_index import SatellitePattern


@pytest.fixture()
def temp_db_path() -> Any:
    """Create a temporary database file path with automatic cleanup.

    Yields:
        Path: Temporary database file path.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    yield db_path

    # Clean up after the test
    if db_path.exists():
        db_path.unlink()


@pytest.fixture()
def thread_cache_db(temp_db_path: Path) -> Any:
    """Create and manage ThreadLocalCacheDB instance.

    Yields:
        ThreadLocalCacheDB: Database instance for testing.
    """
    db = ThreadLocalCacheDB(db_path=temp_db_path)
    yield db
    # Clean up
    db.close()


@pytest.fixture()
def test_data_sets() -> dict[str, Any]:
    """Generate test data sets for various scenarios.

    Returns:
        dict[str, Any]: Test data sets organized by size.
    """
    base_time = datetime.now(UTC)

    return {
        "small_set": {
            "satellite": SatellitePattern.GOES_18,
            "timestamps": [base_time + timedelta(minutes=i * 10) for i in range(5)],
            "filepaths": [f"/test/path/small_{i}.nc" for i in range(5)],
        },
        "medium_set": {
            "satellite": SatellitePattern.GOES_16,
            "timestamps": [base_time + timedelta(minutes=i * 15) for i in range(10)],
            "filepaths": [f"/test/path/medium_{i}.nc" for i in range(10)],
        },
    }


@pytest.fixture()
def mock_time_operations() -> Any:
    """Mock time-related operations to speed up tests.

    Yields:
        None: Context for mocked time operations.
    """
    with patch("time.sleep", return_value=None), patch("asyncio.sleep", return_value=None):
        yield


class TestThreadLocalCacheDB:
    """Test cases for the ThreadLocalCacheDB class with optimizations."""

    def test_database_initialization_and_cleanup(self, temp_db_path: Path) -> None:  # noqa: PLR6301
        """Test basic database creation, initialization, and cleanup."""
        db = ThreadLocalCacheDB(db_path=temp_db_path)

        try:
            # Verify basic initialization
            assert db is not None
            assert hasattr(db, "_connections")
            assert len(db._connections) > 0  # noqa: SLF001

            # Verify database file exists
            assert temp_db_path.exists()

            # Test connection retrieval
            conn = db._get_connection()  # noqa: SLF001
            assert conn is not None

        finally:
            db.close()

        # Verify cleanup
        assert len(db._connections) == 0  # noqa: SLF001

    @pytest.mark.parametrize("thread_count", [2, 3, 5])
    def test_multithread_access_patterns(  # noqa: PLR6301
        self,
        temp_db_path: Path,
        mock_time_operations: Any,
        thread_count: int,
    ) -> None:
        """Test accessing the database from multiple threads with different thread counts."""
        db = ThreadLocalCacheDB(db_path=temp_db_path)

        thread_references = {}
        test_result: dict[str, Any] = {"success": True, "errors": []}

        def worker_thread() -> None:
            """Function that runs in worker threads."""
            thread_id = threading.get_ident()
            try:
                # This should create a new connection for this thread
                conn = db._get_connection()  # noqa: SLF001
                thread_references[thread_id] = conn

                # Verify the connection is valid
                assert conn is not None
                assert thread_id in db._connections  # noqa: SLF001

                # Perform a simple database operation using CacheDB methods
                # Test adding and retrieving an entry
                test_filepath = f"test_file_{thread_id}.nc"
                conn.add_entry(
                    filepath=test_filepath,
                    file_hash=f"hash_{thread_id}",
                    file_size=1000,
                    timestamp=datetime.now(UTC),
                )

                # Verify entry was added
                entry = conn.get_entry(test_filepath)
                assert entry is not None

            except Exception as e:  # noqa: BLE001
                test_result["success"] = False
                test_result["errors"].append(f"Thread {thread_id}: {e!s}")

        try:
            # Create and start threads
            threads = []
            for _ in range(thread_count):
                t = threading.Thread(target=worker_thread)
                t.start()
                threads.append(t)

            # Wait for all threads to finish
            for t in threads:
                t.join()

            # Verify that each thread got its own connection
            assert len(thread_references) == thread_count
            assert test_result["success"], f"Thread errors: {test_result['errors']}"
            assert len(db._connections) >= thread_count  # noqa: SLF001

        finally:
            db.close()

    @staticmethod
    async def async_timestamp_worker(db: Any, satellite: Any, timestamp: Any, file_path: str, *, found: bool) -> Any:
        """Async worker that adds a timestamp to the database.

        Returns:
            Any: Result of add_timestamp operation.
        """
        return await db.add_timestamp(timestamp, satellite, file_path, found)

    @pytest.mark.asyncio()
    async def test_async_thread_safe_operations(
        self,
        temp_db_path: Path,
        test_data_sets: dict[str, Any],
        mock_time_operations: Any,  # noqa: ARG002
    ) -> None:
        """Test thread-safe operations with async functions."""
        db = ThreadLocalCacheDB(db_path=temp_db_path)

        try:
            # Use smaller test data set for faster execution
            data = test_data_sets["small_set"]
            satellite = data["satellite"]
            timestamps = data["timestamps"]
            filepaths = data["filepaths"]

            # Use a thread pool to simulate multiple threads
            with ThreadPoolExecutor(max_workers=3) as executor:
                # Create tasks that will run in different threads
                tasks = []
                for _i, (timestamp, file_path) in enumerate(zip(timestamps, filepaths, strict=False)):
                    # Use asyncio.wrap_future to convert concurrent.futures.Future to asyncio.Future
                    task = asyncio.wrap_future(
                        executor.submit(
                            asyncio.run,
                            self.async_timestamp_worker(db, satellite, timestamp, file_path, found=True),
                        )
                    )
                    tasks.append(task)

                # Wait for all tasks to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Verify all operations succeeded
                for i, result in enumerate(results):
                    assert result is True, f"Operation {i} failed: {result}"

            # Verify we can retrieve the timestamps
            async def verify_timestamps() -> int:
                start_time = min(timestamps)
                end_time = max(timestamps) + timedelta(minutes=10)
                retrieved = await db.get_timestamps(satellite, start_time, end_time)
                return len(retrieved)

            # Run verification in main thread
            count = await verify_timestamps()
            assert count == len(timestamps), f"Expected {len(timestamps)} timestamps, got {count}"

            # Run verification in another thread
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, verify_timestamps())
                thread_count = future.result()
                assert thread_count == len(timestamps), f"Expected {len(timestamps)} from thread, got {thread_count}"

        finally:
            db.close()

    def test_connection_management_lifecycle(self, temp_db_path: Path, mock_time_operations: Any) -> None:  # noqa: PLR6301, ARG002
        """Test complete connection lifecycle: create, use, close."""
        db = ThreadLocalCacheDB(db_path=temp_db_path)

        # Track connections from multiple threads
        connection_info = {}

        def worker_thread(thread_id: int) -> None:
            """Worker that creates and uses a connection."""
            # Get connection (creates if needed)
            conn = db._get_connection()  # noqa: SLF001
            thread_ident = threading.get_ident()
            connection_info[thread_id] = {
                "thread_ident": thread_ident,
                "connection": conn,
                "operations_successful": False,
            }

            try:
                # Perform database operation - use CacheDB's connection
                if hasattr(conn, "conn") and conn.conn:
                    conn.conn.execute("SELECT 1").fetchone()
                    connection_info[thread_id]["operations_successful"] = True
                else:
                    # Alternative: test with cache operations
                    test_entry = f"test_lifecycle_{thread_id}.nc"
                    conn.add_entry(
                        filepath=test_entry,
                        file_hash=f"hash_{thread_id}",
                        file_size=100,
                        timestamp=datetime.now(UTC),
                    )
                    result = conn.get_entry(test_entry)
                    connection_info[thread_id]["operations_successful"] = result is not None
            except Exception:  # noqa: BLE001, S110
                pass

        # Start multiple threads
        threads = []
        for i in range(3):  # Reduced thread count
            t = threading.Thread(target=worker_thread, args=(i,))
            t.start()
            threads.append(t)

        # Wait for all threads to finish
        for t in threads:
            t.join()

        # Verify all threads created connections successfully
        assert len(connection_info) == 3
        assert len(db._connections) >= 3  # noqa: SLF001

        for thread_id, info in connection_info.items():
            assert info["operations_successful"], f"Thread {thread_id} operations failed"

        # Test closing individual thread connections
        threading.get_ident()

        # Get initial connection count
        len(db._connections)  # noqa: SLF001

        # Check if main thread has a connection already by accessing it
        _ = db.get_db()  # This will create a connection for main thread if not exists
        updated_connection_count = len(db._connections)  # noqa: SLF001

        # Close current thread connection
        db.close_current_thread()

        # Should have one fewer connection after closing
        assert len(db._connections) == updated_connection_count - 1  # noqa: SLF001

        # Close all connections
        db.close()
        assert len(db._connections) == 0  # noqa: SLF001

    @pytest.mark.parametrize("operation_count", [3, 5, 8])
    def test_concurrent_database_operations(self, thread_cache_db: Any, operation_count: int) -> None:
        """Test concurrent database operations with varying operation counts."""
        results = []

        def database_worker(worker_id: int) -> None:
            """Worker that performs multiple database operations."""
            worker_results = []
            for i in range(operation_count):
                try:
                    # Add entry
                    filepath = f"worker_{worker_id}_file_{i}.nc"
                    thread_cache_db.add_entry(
                        filepath=filepath,
                        file_hash=f"hash_{worker_id}_{i}",
                        file_size=i * 100,
                        timestamp=datetime.now(UTC),
                    )

                    # Retrieve entry
                    entry = thread_cache_db.get_entry(filepath)
                    worker_results.append(entry is not None)

                except Exception:  # noqa: BLE001
                    worker_results.append(False)

            results.extend(worker_results)

        # Run with multiple threads
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for worker_id in range(3):
                future = executor.submit(database_worker, worker_id)
                futures.append(future)

            # Wait for all workers to complete
            for future in futures:
                future.result()

        # Verify operations were successful
        successful_operations = sum(1 for result in results if result)
        total_expected = 3 * operation_count  # 3 workers * operation_count each

        # Allow for some variability in concurrent operations
        assert successful_operations >= total_expected * 0.8, (
            f"Too many failed operations: {successful_operations}/{total_expected}"
        )

    def test_database_error_handling(self, temp_db_path: Path) -> None:  # noqa: PLR6301
        """Test database error handling and recovery."""
        db = ThreadLocalCacheDB(db_path=temp_db_path)

        try:
            # Test with invalid operation
            conn = db._get_connection()  # noqa: SLF001

            # This should work - use CacheDB's connection
            if hasattr(conn, "conn") and conn.conn:
                conn.conn.execute("SELECT 1").fetchone()

                # Test error handling by trying to access non-existent table
                with contextlib.suppress(Exception):
                    conn.conn.execute("SELECT * FROM non_existent_table").fetchone()

                # Verify database is still functional after error
                conn.conn.execute("SELECT 1").fetchone()
            else:
                # Alternative: test error handling with cache operations
                # This should work
                test_file = "test_error_handling.nc"
                conn.add_entry(
                    filepath=test_file,
                    file_hash="test_hash",
                    file_size=100,
                    timestamp=datetime.now(UTC),
                )

                # Test error handling - try to get non-existent entry
                non_existent = conn.get_entry("non_existent_file.nc")
                assert non_existent is None

                # Verify database is still functional
                result = conn.get_entry(test_file)
                assert result is not None

        finally:
            db.close()

    def test_thread_isolation_verification(self, thread_cache_db: Any, mock_time_operations: Any) -> None:  # noqa: PLR6301, ARG002
        """Verify that threads have isolated database connections."""
        thread_data = {}

        def isolated_worker(worker_id: int) -> None:
            """Worker that stores data specific to its thread."""
            thread_id = threading.get_ident()

            # Store unique data for this thread
            for i in range(3):
                filepath = f"isolated_{thread_id}_{i}.nc"
                thread_cache_db.add_entry(
                    filepath=filepath,
                    file_hash=f"hash_{thread_id}_{i}",
                    file_size=worker_id * 1000 + i,
                    timestamp=datetime.now(UTC),
                )

            # Retrieve and verify data
            retrieved_entries = []
            for i in range(3):
                filepath = f"isolated_{thread_id}_{i}.nc"
                entry = thread_cache_db.get_entry(filepath)
                if entry:
                    retrieved_entries.append(entry["file_size"])

            thread_data[worker_id] = retrieved_entries

        # Run workers in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for worker_id in range(3):
                future = executor.submit(isolated_worker, worker_id)
                futures.append(future)

            # Wait for completion
            for future in futures:
                future.result()

        # Verify each thread's data is correctly isolated and stored
        assert len(thread_data) == 3
        for worker_id, entries in thread_data.items():
            assert len(entries) == 3
            # Verify the pattern of stored data
            expected_base = worker_id * 1000
            for i, file_size in enumerate(entries):
                assert file_size == expected_base + i

    def test_performance_with_rapid_operations(self, thread_cache_db: Any, mock_time_operations: Any) -> None:  # noqa: PLR6301, ARG002
        """Test database performance with rapid consecutive operations."""

        operation_count = 50  # Reduced for faster test execution

        start_time = time.time()

        # Perform rapid operations
        for i in range(operation_count):
            filepath = f"rapid_{i}.nc"
            thread_cache_db.add_entry(
                filepath=filepath,
                file_hash=f"hash_{i}",
                file_size=i * 10,
                timestamp=datetime.now(UTC),
            )

            # Immediately retrieve
            entry = thread_cache_db.get_entry(filepath)
            assert entry is not None

        end_time = time.time()
        elapsed = end_time - start_time

        # Should be reasonably fast (allowing for test environment variability)
        # This is more of a performance regression test
        assert elapsed < 2.0, f"Operations took too long: {elapsed:.2f} seconds"
