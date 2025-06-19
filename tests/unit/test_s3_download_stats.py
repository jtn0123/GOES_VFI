"""Unit tests for S3 download statistics tracking.

These tests focus on the download statistics tracking functionality
in the S3Store implementation, verifying that statistics are properly
collected and reported.
"""

import asyncio
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import botocore.exceptions

from goesvfi.integrity_check.remote.s3_store import (
    DOWNLOAD_STATS,
    S3Store,
    log_download_statistics,
    update_download_stats,
)
from goesvfi.integrity_check.time_index import SatellitePattern


class TestS3DownloadStats(unittest.TestCase):
    """Test cases for S3 download statistics tracking."""

    def setUp(self):
        """Set up test fixtures."""
        # Reset download stats before each test
        self._reset_download_stats()

        # Create temp directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

        # Create test timestamp and satellite
        self.test_timestamp = datetime(2023, 6, 15, 12, 0, 0)
        self.test_satellite = SatellitePattern.GOES_18

    def tearDown(self):
        """Tear down test fixtures."""
        # Clean up temp directory
        self.temp_dir.cleanup()

        # Reset download stats after test
        self._reset_download_stats()

    def _reset_download_stats(self):
        """Reset download statistics to initial state."""
        global DOWNLOAD_STATS
        DOWNLOAD_STATS = {
            "total_attempts": 0,
            "successful": 0,
            "failed": 0,
            "retry_count": 0,
            "not_found": 0,
            "auth_errors": 0,
            "timeouts": 0,
            "network_errors": 0,
            "download_times": [],
            "start_time": 0,
            "last_success_time": 0,
            "largest_file_size": 0,
            "smallest_file_size": float("inf"),
            "total_bytes": 0,
            "errors": [],
        }

    def test_update_download_stats_success(self):
        """Test updating download statistics for successful downloads."""
        # Initial state check
        self.assertEqual(DOWNLOAD_STATS["total_attempts"], 0)
        self.assertEqual(DOWNLOAD_STATS["successful"], 0)
        self.assertEqual(len(DOWNLOAD_STATS["download_times"]), 0)

        # Update with a successful download
        download_time = 1.5
        file_size = 1024
        update_download_stats(
            success=True, download_time=download_time, file_size=file_size
        )

        # Check updated state
        self.assertEqual(DOWNLOAD_STATS["total_attempts"], 1)
        self.assertEqual(DOWNLOAD_STATS["successful"], 1)
        self.assertEqual(DOWNLOAD_STATS["failed"], 0)
        self.assertEqual(len(DOWNLOAD_STATS["download_times"]), 1)
        self.assertEqual(DOWNLOAD_STATS["download_times"][0], download_time)
        self.assertEqual(DOWNLOAD_STATS["total_bytes"], file_size)
        self.assertEqual(DOWNLOAD_STATS["largest_file_size"], file_size)
        self.assertEqual(DOWNLOAD_STATS["smallest_file_size"], file_size)

    def test_update_download_stats_failure(self):
        """Test updating download statistics for failed downloads."""
        # Initial state check
        self.assertEqual(DOWNLOAD_STATS["total_attempts"], 0)
        self.assertEqual(DOWNLOAD_STATS["failed"], 0)
        self.assertEqual(len(DOWNLOAD_STATS["errors"]), 0)

        # Update with a failed download
        error_type = "timeout"
        error_message = "Connection timed out"
        update_download_stats(
            success=False, error_type=error_type, error_message=error_message
        )

        # Check updated state
        self.assertEqual(DOWNLOAD_STATS["total_attempts"], 1)
        self.assertEqual(DOWNLOAD_STATS["successful"], 0)
        self.assertEqual(DOWNLOAD_STATS["failed"], 1)
        self.assertEqual(DOWNLOAD_STATS["timeouts"], 1)
        self.assertEqual(len(DOWNLOAD_STATS["errors"]), 1)
        self.assertEqual(DOWNLOAD_STATS["errors"][0], f"timeout: Connection timed out")

    def test_update_download_stats_multiple_error_types(self):
        """Test updating download statistics for different error types."""
        # Test each error type
        error_types = {
            "not_found": "not_found",
            "auth": "auth_errors",
            "timeout": "timeouts",
            "network": "network_errors",
        }

        for error_type, counter_key in error_types.items():
            # Update with the current error type
            update_download_stats(
                success=False,
                error_type=error_type,
                error_message=f"Error of type {error_type}",
            )

            # Check that the counter for this error type was incremented
            self.assertEqual(
                DOWNLOAD_STATS[counter_key],
                1,
                f"Counter for {error_type} ({counter_key}) was not incremented",
            )

        # Check overall stats
        self.assertEqual(DOWNLOAD_STATS["total_attempts"], 4)
        self.assertEqual(DOWNLOAD_STATS["failed"], 4)
        self.assertEqual(len(DOWNLOAD_STATS["errors"]), 4)

    def test_file_size_tracking(self):
        """Test tracking of file sizes in download statistics."""
        # Upload multiple files of different sizes
        file_sizes = [1024, 512, 2048]

        for size in file_sizes:
            update_download_stats(success=True, download_time=1.0, file_size=size)

        # Check tracked sizes
        self.assertEqual(DOWNLOAD_STATS["largest_file_size"], max(file_sizes))
        self.assertEqual(DOWNLOAD_STATS["smallest_file_size"], min(file_sizes))
        self.assertEqual(DOWNLOAD_STATS["total_bytes"], sum(file_sizes))

    def test_error_history_limit(self):
        """Test that error history is limited to the most recent errors."""
        # Generate more than 20 errors (the default limit)
        for i in range(25):
            update_download_stats(
                success=False, error_type="network", error_message=f"Error {i}"
            )

        # Verify only the most recent 20 are kept
        self.assertEqual(len(DOWNLOAD_STATS["errors"]), 20)

        # Verify the oldest errors were removed (errors 0-4 should be gone)
        for i in range(5):
            self.assertNotIn(f"network: Error {i}", DOWNLOAD_STATS["errors"])

        # Verify the newest errors are still there (errors 5-24)
        for i in range(5, 25):
            expected_msg = f"network: Error {i}"
            # Only the first 100 chars are kept if message is longer
            if len(expected_msg) > 100:
                expected_msg = expected_msg[:100] + "..."
            self.assertIn(expected_msg, DOWNLOAD_STATS["errors"])

    @patch("goesvfi.integrity_check.remote.s3_store.LOGGER")
    def test_log_download_statistics(self, mock_logger):
        """Test the log_download_statistics function."""
        # Add some test data
        update_download_stats(success=True, download_time=1.0, file_size=1024)
        update_download_stats(success=True, download_time=2.0, file_size=2048)
        update_download_stats(
            success=False, error_type="timeout", error_message="Timeout error"
        )

        # Call the function
        log_download_statistics()

        # Verify logger was called
        mock_logger.info.assert_called()

        # Get the log message
        log_message = mock_logger.info.call_args[0][0]

        # Check for key statistics in the log message
        self.assertIn("S3 Download Statistics", log_message)
        self.assertIn("Total attempts: 3", log_message)
        self.assertIn("Successful: 2", log_message)
        self.assertIn("Failed: 1", log_message)
        self.assertIn("Timeouts: 1", log_message)
        self.assertIn("Average download time:", log_message)
        self.assertIn("Total bytes: 3072", log_message)

    @patch("goesvfi.integrity_check.remote.s3_store.get_system_network_info")
    def test_network_diagnostics_on_repeated_failures(self, mock_get_info):
        """Test that network diagnostics are collected after repeated failures."""
        # Generate 5 failures
        for i in range(5):
            update_download_stats(
                success=False, error_type="network", error_message=f"Network error {i}"
            )

        # Verify network diagnostics were collected on the 5th failure
        mock_get_info.assert_called_once()

        # Reset the mock
        mock_get_info.reset_mock()

        # Generate 4 more failures (total: 9)
        for i in range(5, 9):
            update_download_stats(
                success=False, error_type="network", error_message=f"Network error {i}"
            )

        # Verify network diagnostics were not collected again
        mock_get_info.assert_not_called()

        # Generate one more failure (total: 10)
        update_download_stats(
            success=False, error_type="network", error_message="Network error 10"
        )

        # Verify network diagnostics were collected on the 10th failure
        mock_get_info.assert_called_once()


class TestS3DownloadStatsIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for S3 download statistics in the S3Store class."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        # Reset download stats
        global DOWNLOAD_STATS
        DOWNLOAD_STATS = {
            "total_attempts": 0,
            "successful": 0,
            "failed": 0,
            "retry_count": 0,
            "not_found": 0,
            "auth_errors": 0,
            "timeouts": 0,
            "network_errors": 0,
            "download_times": [],
            "start_time": 0,
            "last_success_time": 0,
            "largest_file_size": 0,
            "smallest_file_size": float("inf"),
            "total_bytes": 0,
            "errors": [],
        }

        # Create temp directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

        # Create test timestamp and satellite
        self.test_timestamp = datetime(2023, 6, 15, 12, 0, 0)
        self.test_satellite = SatellitePattern.GOES_18
        self.test_dest_path = self.base_dir / "test_download.nc"

        # Create the S3Store instance
        self.store = S3Store()

        # Mock S3 client
        self.mock_s3_client = AsyncMock()

        # Patch the _get_s3_client method to return our mock
        patcher = patch.object(
            S3Store, "_get_s3_client", return_value=self.mock_s3_client
        )
        self.mock_get_s3_client = patcher.start()
        self.addAsyncCleanup(patcher.stop)

    async def asyncTearDown(self):
        """Tear down test fixtures."""
        # Clean up temp directory
        self.temp_dir.cleanup()

    async def test_stats_updated_on_successful_download(self):
        """Test that statistics are updated on successful download."""
        # Configure head_object to succeed
        self.mock_s3_client.head_object.return_value = {"ContentLength": 1000}

        # Configure download_file to succeed
        self.mock_s3_client.download_file = AsyncMock()

        # Create the destination directory
        self.test_dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Create a test file at the destination to simulate a successful download
        with open(self.test_dest_path, "w") as f:
            f.write("Test content")

        # Get the file size
        file_size = self.test_dest_path.stat().st_size

        # Reset statistics for clean test
        self._reset_download_stats()

        # Execute the download
        await self.store.download_file(
            self.test_timestamp, self.test_satellite, self.test_dest_path
        )

        # Verify statistics were updated
        self.assertEqual(DOWNLOAD_STATS["total_attempts"], 1)
        self.assertEqual(DOWNLOAD_STATS["successful"], 1)
        self.assertEqual(len(DOWNLOAD_STATS["download_times"]), 1)
        self.assertEqual(DOWNLOAD_STATS["total_bytes"], file_size)

    async def test_stats_updated_on_download_failure(self):
        """Test that statistics are updated on download failure."""
        # Configure head_object to succeed
        self.mock_s3_client.head_object.return_value = {"ContentLength": 1000}

        # Configure download_file to fail with a timeout error
        self.mock_s3_client.download_file.side_effect = asyncio.TimeoutError(
            "Download timed out"
        )

        # Reset statistics for clean test
        self._reset_download_stats()

        # Execute the download, expect ConnectionError
        with self.assertRaises(ConnectionError):
            await self.store.download_file(
                self.test_timestamp, self.test_satellite, self.test_dest_path
            )

        # Verify statistics were updated
        self.assertEqual(DOWNLOAD_STATS["total_attempts"], 1)
        self.assertEqual(DOWNLOAD_STATS["successful"], 0)
        self.assertEqual(DOWNLOAD_STATS["failed"], 1)
        self.assertEqual(DOWNLOAD_STATS["timeouts"], 1)
        self.assertEqual(len(DOWNLOAD_STATS["errors"]), 1)

    async def test_stats_updated_on_not_found_error(self):
        """Test that statistics are updated on not found error."""
        # Configure head_object to return 404
        error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
        client_error = botocore.exceptions.ClientError(error_response, "HeadObject")
        self.mock_s3_client.head_object.side_effect = client_error

        # Configure paginator for list_objects_v2 to return empty results
        paginator_mock = MagicMock()

        # Make the paginator.paginate method return an empty async iterator
        async def empty_paginate(*args, **kwargs):
            # Return an empty async generator
            if False:
                yield  # This is never reached, so nothing is yielded

        paginator_mock.paginate = empty_paginate
        self.mock_s3_client.get_paginator.return_value = paginator_mock

        # Reset statistics for clean test
        self._reset_download_stats()

        # Execute the download, expect ResourceNotFoundError
        with self.assertRaises(ResourceNotFoundError):
            await self.store.download_file(
                self.test_timestamp, self.test_satellite, self.test_dest_path
            )

        # Verify statistics were updated
        self.assertEqual(DOWNLOAD_STATS["total_attempts"], 1)
        self.assertEqual(DOWNLOAD_STATS["successful"], 0)
        self.assertEqual(DOWNLOAD_STATS["failed"], 1)
        self.assertEqual(DOWNLOAD_STATS["not_found"], 1)
        self.assertEqual(len(DOWNLOAD_STATS["errors"]), 1)

    def _reset_download_stats(self):
        """Reset download statistics to initial state."""
        global DOWNLOAD_STATS
        DOWNLOAD_STATS = {
            "total_attempts": 0,
            "successful": 0,
            "failed": 0,
            "retry_count": 0,
            "not_found": 0,
            "auth_errors": 0,
            "timeouts": 0,
            "network_errors": 0,
            "download_times": [],
            "start_time": 0,
            "last_success_time": 0,
            "largest_file_size": 0,
            "smallest_file_size": float("inf"),
            "total_bytes": 0,
            "errors": [],
        }


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
for name in dir(TestS3DownloadStatsIntegration):
    if name.startswith("test_") and asyncio.iscoroutinefunction(
        getattr(TestS3DownloadStatsIntegration, name)
    ):
        setattr(
            TestS3DownloadStatsIntegration,
            name,
            async_test(getattr(TestS3DownloadStatsIntegration, name)),
        )


if __name__ == "__main__":
    unittest.main()
