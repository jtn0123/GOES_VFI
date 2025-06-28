"""Unit tests for the thread-local cache database."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import os
from pathlib import Path
import tempfile
import threading
from typing import Any

import pytest

from goesvfi.integrity_check.thread_cache_db import ThreadLocalCacheDB
from goesvfi.integrity_check.time_index import SatellitePattern


class TestThreadLocalCacheDB:
    """Test cases for the ThreadLocalCacheDB class."""

    @pytest.fixture()
    def temp_db_path(self):
        """Create a temporary database file path."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            yield Path(f.name)
            # Clean up after the test
            try:
                os.unlink(f.name)
            except OSError:
                pass  # File might already be deleted

    def test_basic_creation(self, temp_db_path) -> None:
        """Test basic creation and initialization."""
        db = ThreadLocalCacheDB(db_path=temp_db_path)
        try:
            # Verify we can create the DB
            assert db is not None
            # Verify it creates a connection for the main thread
            assert hasattr(db, "_connections")
            assert len(db._connections) > 0
        finally:
            db.close()

    def test_multithread_access(self, temp_db_path) -> None:
        """Test accessing the database from multiple threads."""
        # Create the thread-local DB
        db = ThreadLocalCacheDB(db_path=temp_db_path)

        # Store references to thread IDs where each connection was created
        thread_references = {}
        test_result: dict[str, Any] = {"success": True, "errors": []}

        def worker_thread() -> None:
            """Function that runs in worker threads."""
            thread_id = threading.get_ident()
            try:
                # This should create a new connection for this thread
                conn = db._get_connection()
                # Store the thread ID
                thread_references[thread_id] = conn
                # Verify the connection is valid
                assert conn is not None
                # Verify this connection is stored in the connections dictionary
                assert thread_id in db._connections
            except Exception as e:
                test_result["success"] = False
                test_result["errors"].append(f"Thread {thread_id}: {e!s}")

        try:
            # Create and start several threads
            threads = []
            for _ in range(5):
                t = threading.Thread(target=worker_thread)
                t.start()
                threads.append(t)

            # Wait for all threads to finish
            for t in threads:
                t.join()

            # Verify that each thread got its own connection
            assert len(thread_references) == 5

            # Verify overall success
            assert test_result["success"], f"Thread errors: {test_result['errors']}"

            # Verify connections are stored in the database
            assert len(db._connections) >= 5
        finally:
            db.close()

    async def async_worker(self, db, satellite, timestamp, file_path, found):
        """Async worker that adds a timestamp to the database."""
        return await db.add_timestamp(timestamp, satellite, file_path, found)

    @pytest.mark.asyncio()
    async def test_async_thread_safe_operations(self, temp_db_path) -> None:
        """Test thread-safe operations with async functions."""
        # Create the thread-local DB
        db = ThreadLocalCacheDB(db_path=temp_db_path)

        # Create test data
        satellite = SatellitePattern.GOES_18
        base_timestamp = datetime.utcnow()

        try:
            # Use a thread pool to simulate multiple threads
            with ThreadPoolExecutor(max_workers=5) as executor:
                # Create tasks that will run in different threads
                tasks = []
                for i in range(10):
                    timestamp = base_timestamp + timedelta(minutes=i * 10)
                    file_path = f"/test/path/{i}.png"
                    # Use asyncio.wrap_future to convert concurrent.futures.Future to asyncio.Future
                    task = asyncio.wrap_future(
                        executor.submit(
                            asyncio.run,
                            self.async_worker(db, satellite, timestamp, file_path, True),
                        )
                    )
                    tasks.append(task)

                # Wait for all tasks to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Verify all operations succeeded
                for result in results:
                    assert result is True, f"Operation failed: {result}"

            # Now verify we can retrieve the timestamps from any thread
            async def verify_timestamps():
                start_time = base_timestamp
                end_time = base_timestamp + timedelta(minutes=100)
                timestamps = await db.get_timestamps(satellite, start_time, end_time)
                return len(timestamps)

            # Run in the main thread
            count = await verify_timestamps()
            assert count == 10, f"Expected 10 timestamps, got {count}"

            # Run in another thread
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, verify_timestamps())
                thread_count = future.result()
                assert thread_count == 10, f"Expected 10 timestamps from thread, got {thread_count}"

        finally:
            db.close()

    def test_close_all_connections(self, temp_db_path) -> None:
        """Test that close() properly closes all connections."""
        # Create the thread-local DB
        db = ThreadLocalCacheDB(db_path=temp_db_path)

        # Create connections from multiple threads
        def worker_thread() -> None:
            db._get_connection()  # Just get a connection

        # Start several threads to create connections
        threads = []
        for _ in range(5):
            t = threading.Thread(target=worker_thread)
            t.start()
            threads.append(t)

        # Wait for all threads to finish
        for t in threads:
            t.join()

        # Verify connections were created
        assert len(db._connections) >= 5

        # Close all connections
        db.close()

        # Verify connections dictionary is empty
        assert len(db._connections) == 0

    def test_close_current_thread(self, temp_db_path) -> None:
        """Test closing the connection for the current thread only."""
        # Create the thread-local DB
        db = ThreadLocalCacheDB(db_path=temp_db_path)

        # Get a connection for the main thread
        db._get_connection()
        main_thread_id = threading.get_ident()

        # Create connections from a worker thread
        worker_thread_id = None

        def worker_thread() -> None:
            nonlocal worker_thread_id
            worker_thread_id = threading.get_ident()
            db._get_connection()  # Get a connection for this thread

        # Start a worker thread
        t = threading.Thread(target=worker_thread)
        t.start()
        t.join()

        # Verify we have two connections
        assert len(db._connections) == 2
        assert main_thread_id in db._connections
        assert worker_thread_id in db._connections

        # Close the connection for the current (main) thread
        db.close_current_thread()

        # Verify only the worker thread's connection remains
        assert len(db._connections) == 1
        assert main_thread_id not in db._connections
        assert worker_thread_id in db._connections

        # Clean up
        db.close()
