"""Unit tests for S3 retry strategy and resilience.

These tests focus on the retry behavior, timeout handling, and resilience
of the S3Store implementation when faced with network issues.
"""

import asyncio
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import aioboto3
import botocore.exceptions
from botocore import UNSIGNED

from goesvfi.integrity_check.remote.base import (
    AuthenticationError,
    ConnectionError,
    RemoteStoreError,
    ResourceNotFoundError,
)
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.time_index import SatellitePattern


class TestS3RetryStrategy(unittest.IsolatedAsyncioTestCase):
    """Test cases for S3Store retry strategy and network resilience."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.store = S3Store(timeout=5)  # Short timeout for testing
        self.test_timestamp = datetime(2023, 6, 15, 12, 0, 0)
        self.test_satellite = SatellitePattern.GOES_18
        self.test_dest_path = Path("/tmp/test_download.nc")

        # Mock S3 client
        self.mock_s3_client = AsyncMock()

        # Patch the _get_s3_client method to return our mock
        patcher = patch.object(
            S3Store, "_get_s3_client", return_value=self.mock_s3_client
        )
        self.mock_get_s3_client = patcher.start()
        self.addAsyncCleanup(patcher.stop)

    async def test_client_connection_retry(self):
        """Test that client creation retries on timeout."""
        # Restore the original _get_s3_client method
        self.mock_get_s3_client.stop()

        # Create a session mock that fails with timeout, then succeeds
        mock_session = MagicMock()
        mock_client_context = MagicMock()
        mock_client = AsyncMock()

        # Setup mock client
        mock_client_context.__aenter__ = AsyncMock()
        # First call raises TimeoutError, second succeeds
        mock_client_context.__aenter__.side_effect = [
            asyncio.TimeoutError("Connection timed out"),
            mock_client,
        ]

        mock_session.client.return_value = mock_client_context

        with patch("aioboto3.Session", return_value=mock_session):
            # Call the method - should retry and succeed
            client = await self.store._get_s3_client()

            # Verify retry happened
            self.assertEqual(mock_client_context.__aenter__.call_count, 2)
            self.assertEqual(client, mock_client)

    async def test_client_connection_retry_fails_after_max_attempts(self):
        """Test that client creation gives up after max retries."""
        # Restore the original _get_s3_client method
        self.mock_get_s3_client.stop()

        # Create a session mock that always fails with timeout
        mock_session = MagicMock()
        mock_client_context = MagicMock()

        # Setup mock to always raise TimeoutError
        mock_client_context.__aenter__ = AsyncMock(
            side_effect=asyncio.TimeoutError("Connection timed out")
        )

        mock_session.client.return_value = mock_client_context

        with patch("aioboto3.Session", return_value=mock_session):
            # Call the method - should retry and eventually raise ConnectionError
            with self.assertRaises(ConnectionError) as context:
                await self.store._get_s3_client()

            # Verify retry happened max_retries times (default is 3)
            self.assertEqual(mock_client_context.__aenter__.call_count, 3)

            # Check error message
            error_msg = str(context.exception)
            self.assertIn("Connection to AWS S3 timed out", error_msg)

    async def test_download_retries_on_connection_error(self):
        """Test that download retries on connection errors."""
        # Configure head_object to succeed
        self.mock_s3_client.head_object.return_value = {"ContentLength": 1000}

        # First download attempt fails with connection error, second succeeds
        error_response = {
            "Error": {"Code": "ConnectionError", "Message": "Connection error"}
        }
        connection_error = botocore.exceptions.ClientError(error_response, "GetObject")

        # Setup download_file to fail first, then succeed
        self.mock_s3_client.download_file = AsyncMock()
        self.mock_s3_client.download_file.side_effect = [
            connection_error,
            None,  # Success on second attempt
        ]

        # Execute the download method
        with patch("goesvfi.integrity_check.remote.s3_store.update_download_stats"):
            result = await self.store.download(
                self.test_timestamp, self.test_satellite, self.test_dest_path
            )

        # Verify download_file was called twice (retry happened)
        self.assertEqual(self.mock_s3_client.download_file.call_count, 2)

        # Verify the result is the destination path
        self.assertEqual(result, self.test_dest_path)

    async def test_wildcard_matching_fallback(self):
        """Test fallback to wildcard matching when exact file not found."""
        # Setup head_object to fail with 404
        not_found_error = botocore.exceptions.ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
        )
        self.mock_s3_client.head_object.side_effect = not_found_error

        # Setup paginator for list_objects_v2
        mock_paginator = MagicMock()

        # Setup a mock page with one result
        test_page = {"Contents": [{"Key": "test_key.nc"}]}

        # Create an async generator for the paginator
        async def mock_paginate(*args, **kwargs):
            yield test_page

        mock_paginator.paginate = mock_paginate
        self.mock_s3_client.get_paginator.return_value = mock_paginator

        # Setup download to succeed
        self.mock_s3_client.download_file = AsyncMock()

        # Execute the download method
        with patch("goesvfi.integrity_check.remote.s3_store.update_download_stats"):
            result = await self.store.download(
                self.test_timestamp, self.test_satellite, self.test_dest_path
            )

        # Verify the paginator was used to find a wildcard match
        self.mock_s3_client.get_paginator.assert_called_with("list_objects_v2")

        # Verify download_file was called with the matched key
        args, kwargs = self.mock_s3_client.download_file.call_args
        self.assertEqual(kwargs["Key"], "test_key.nc")

        # Verify the result is the destination path
        self.assertEqual(result, self.test_dest_path)

    async def test_download_statistics_tracking(self):
        """Test that download statistics are properly tracked."""
        # Configure head_object to succeed
        self.mock_s3_client.head_object.return_value = {"ContentLength": 1000}

        # Make download_file succeed
        self.mock_s3_client.download_file = AsyncMock()

        # Path to a temporary file for better tracking test
        tmp_dest_path = self.test_dest_path

        # Create a spy for update_download_stats
        stats_updates = []

        def mock_update_stats(
            success, download_time=0, file_size=0, error_type=None, error_message=None
        ):
            stats_updates.append(
                {
                    "success": success,
                    "download_time": download_time,
                    "file_size": file_size,
                    "error_type": error_type,
                    "error_message": error_message,
                }
            )

        # Execute the download method
        with patch(
            "goesvfi.integrity_check.remote.s3_store.update_download_stats",
            side_effect=mock_update_stats,
        ) as mock_update:
            # Mock file existence check and size
            with (
                patch("pathlib.Path.exists", return_value=True),
                patch("pathlib.Path.stat", return_value=MagicMock(st_size=1024)),
            ):
                result = await self.store.download(
                    self.test_timestamp, self.test_satellite, tmp_dest_path
                )

        # Verify update_download_stats was called with success=True
        self.assertTrue(len(stats_updates) > 0)
        self.assertTrue(stats_updates[0]["success"])
        self.assertGreaterEqual(stats_updates[0]["download_time"], 0)
        self.assertEqual(stats_updates[0]["file_size"], 1024)
        self.assertIsNone(stats_updates[0]["error_type"])

        # Verify the result is the destination path
        self.assertEqual(result, tmp_dest_path)

    async def test_error_statistics_tracking(self):
        """Test that error statistics are properly tracked."""
        # Configure head_object to succeed
        self.mock_s3_client.head_object.return_value = {"ContentLength": 1000}

        # Make download_file fail with a timeout
        self.mock_s3_client.download_file.side_effect = asyncio.TimeoutError(
            "Download timed out"
        )

        # Create a spy for update_download_stats
        stats_updates = []

        def mock_update_stats(
            success, download_time=0, file_size=0, error_type=None, error_message=None
        ):
            stats_updates.append(
                {
                    "success": success,
                    "download_time": download_time,
                    "file_size": file_size,
                    "error_type": error_type,
                    "error_message": error_message,
                }
            )

        # Execute the download method, expect a ConnectionError
        with patch(
            "goesvfi.integrity_check.remote.s3_store.update_download_stats",
            side_effect=mock_update_stats,
        ):
            with self.assertRaises(ConnectionError):
                await self.store.download(
                    self.test_timestamp, self.test_satellite, self.test_dest_path
                )

        # Verify update_download_stats was called with success=False
        self.assertTrue(len(stats_updates) > 0)
        self.assertFalse(stats_updates[0]["success"])
        self.assertGreaterEqual(stats_updates[0]["download_time"], 0)
        self.assertEqual(stats_updates[0]["error_type"], "timeout")
        self.assertIsNotNone(stats_updates[0]["error_message"])

    async def test_concurrent_download_limits(self):
        """Test that concurrent downloads respect the semaphore limit."""
        # This test requires mocking the ReconcileManager
        from goesvfi.integrity_check.reconcile_manager import ReconcileManager

        # Create a mock cache_db
        mock_cache_db = AsyncMock()
        mock_cache_db.add_timestamp = AsyncMock(return_value=True)

        # Create the ReconcileManager with controlled concurrency
        max_concurrency = 2  # Only allow 2 concurrent downloads
        manager = ReconcileManager(
            cache_db=mock_cache_db,
            base_dir="/tmp",
            cdn_store=None,  # Will be mocked later
            s3_store=self.store,
            max_concurrency=max_concurrency,
        )

        # Create a delay tracker to measure concurrent execution
        delay_tracker = {"active_count": 0, "max_active": 0}

        # Make a replacement for S3Store.download that delays and tracks concurrency
        original_download = self.store.download

        async def tracking_download(ts, satellite, dest_path):
            # Increment active count
            delay_tracker["active_count"] += 1
            delay_tracker["max_active"] = max(
                delay_tracker["max_active"], delay_tracker["active_count"]
            )

            try:
                # Add a delay to ensure overlap
                await asyncio.sleep(0.1)
                # Return a fake path
                return dest_path
            finally:
                # Decrement active count
                delay_tracker["active_count"] -= 1

        # Replace download method with our tracking version
        self.store.download = tracking_download

        # Make exists always return True for this test
        self.store.exists = AsyncMock(return_value=True)

        try:
            # Create 5 timestamps to download simultaneously
            timestamps = {datetime(2023, 6, 15, 12, i * 10, 0) for i in range(5)}

            # Run the fetch_missing_files method
            await manager.fetch_missing_files(
                missing_timestamps=timestamps, satellite=self.test_satellite
            )

            # Verify the max active count never exceeded the concurrency limit
            self.assertLessEqual(delay_tracker["max_active"], max_concurrency)
        finally:
            # Restore original method
            self.store.download = original_download

    async def test_network_diagnostics_on_failure(self):
        """Test that network diagnostics are collected on failures."""
        # Configure head_object to succeed
        self.mock_s3_client.head_object.return_value = {"ContentLength": 1000}

        # Make download_file fail with a network error
        network_error = botocore.exceptions.ClientError(
            {"Error": {"Code": "NetworkError", "Message": "Network error"}}, "GetObject"
        )
        self.mock_s3_client.download_file.side_effect = network_error

        # Mock the diagnostics collector
        with patch(
            "goesvfi.integrity_check.remote.s3_store.get_system_network_info"
        ) as mock_diagnostics:
            # Execute the download method, expect a RemoteStoreError
            with self.assertRaises(RemoteStoreError):
                await self.store.download(
                    self.test_timestamp, self.test_satellite, self.test_dest_path
                )

            # Verify diagnostics were collected
            mock_diagnostics.assert_called_once()


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


# Apply async_test decorator to async test methods
for name in dir(TestS3RetryStrategy):
    if name.startswith("test_") and asyncio.iscoroutinefunction(
        getattr(TestS3RetryStrategy, name)
    ):
        setattr(
            TestS3RetryStrategy, name, async_test(getattr(TestS3RetryStrategy, name))
        )


if __name__ == "__main__":
    unittest.main()
