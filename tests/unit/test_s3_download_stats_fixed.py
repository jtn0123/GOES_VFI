"""Unit tests for enhanced S3 download statistics tracking.

These tests focus on the enhanced download statistics tracking functionality
in the S3Store implementation, verifying that statistics are properly
collected, updated, and reported.
"""

import asyncio
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from goesvfi.integrity_check.remote.s3_store import (
    format_error_message,
    log_download_statistics,
    update_download_stats,
)
from goesvfi.integrity_check.time_index import SatellitePattern


class TestS3DownloadStats(unittest.TestCase):
    """Test cases for enhanced S3 download statistics tracking."""

    def setUp(self):
        """Set up test fixtures."""
        # Reset tracking statistics between tests
        self.stats_data = {
            # Basic counters
            "total_attempts": 0,
            "successful": 0,
            "failed": 0,
            "retry_count": 0,
            # Error type counters
            "not_found": 0,
            "auth_errors": 0,
            "timeouts": 0,
            "network_errors": 0,
            # Performance metrics
            "download_times": [],
            "download_rates": [],  # New field for bytes per second
            "start_time": 1234567890,  # Fixed timestamp for testing
            "last_success_time": 0,
            "largest_file_size": 0,
            "smallest_file_size": float("inf"),
            "total_bytes": 0,
            # Recent history
            "errors": [],  # Track the last 20 errors
            "recent_attempts": [],  # New field for tracking recent attempts
            # Session information
            "session_id": "test-session-123",
            "hostname": "test-host",
            "start_timestamp": "2023-01-01T12:00:00",
        }
        self.stats_patcher = patch("goesvfi.integrity_check.remote.s3_store.DOWNLOAD_STATS", self.stats_data)
        self.mock_stats = self.stats_patcher.start()

    def tearDown(self):
        """Tear down test fixtures."""
        self.stats_patcher.stop()

    def test_update_stats_success(self):
        """Test updating stats for successful downloads."""
        # Call the function with success data
        update_download_stats(
            success=True,
            download_time=1.5,
            file_size=1024,
            satellite="GOES16",
            bucket="test-bucket",
            key="test/path/file.nc",
        )

        # Verify stats were updated correctly
        self.assertEqual(self.stats_data["total_attempts"], 1)
        self.assertEqual(self.stats_data["successful"], 1)
        self.assertEqual(self.stats_data["failed"], 0)
        self.assertEqual(len(self.stats_data["download_times"]), 1)
        self.assertEqual(self.stats_data["download_times"][0], 1.5)
        self.assertEqual(self.stats_data["total_bytes"], 1024)
        self.assertEqual(self.stats_data["largest_file_size"], 1024)
        self.assertEqual(self.stats_data["smallest_file_size"], 1024)

        # Verify download rate was calculated and stored
        self.assertEqual(len(self.stats_data["download_rates"]), 1)
        self.assertEqual(self.stats_data["download_rates"][0], 1024 / 1.5)

        # Verify recent attempts history was updated
        self.assertEqual(len(self.stats_data["recent_attempts"]), 1)
        self.assertEqual(self.stats_data["recent_attempts"][0]["success"], True)
        self.assertEqual(self.stats_data["recent_attempts"][0]["download_time"], 1.5)
        self.assertEqual(self.stats_data["recent_attempts"][0]["file_size"], 1024)
        self.assertEqual(self.stats_data["recent_attempts"][0]["satellite"], "GOES16")
        self.assertEqual(self.stats_data["recent_attempts"][0]["bucket"], "test-bucket")
        self.assertEqual(self.stats_data["recent_attempts"][0]["key"], "test/path/file.nc")

    def test_update_stats_failure(self):
        """Test updating stats for failed downloads."""
        # Call the function with failure data
        update_download_stats(
            success=False,
            error_type="timeout",
            error_message="Connection timed out",
            satellite="GOES16",
            bucket="test-bucket",
            key="test/path/file.nc",
        )

        # Verify stats were updated correctly
        self.assertEqual(self.stats_data["total_attempts"], 1)
        self.assertEqual(self.stats_data["successful"], 0)
        self.assertEqual(self.stats_data["failed"], 1)
        self.assertEqual(self.stats_data["timeouts"], 1)

        # Verify error was recorded with timestamp
        self.assertEqual(len(self.stats_data["errors"]), 1)
        self.assertTrue("timeout: Connection timed out" in self.stats_data["errors"][0])

        # Verify recent attempts history was updated
        self.assertEqual(len(self.stats_data["recent_attempts"]), 1)
        self.assertEqual(self.stats_data["recent_attempts"][0]["success"], False)
        self.assertEqual(self.stats_data["recent_attempts"][0]["error_type"], "timeout")
        self.assertEqual(self.stats_data["recent_attempts"][0]["satellite"], "GOES16")
        self.assertEqual(self.stats_data["recent_attempts"][0]["bucket"], "test-bucket")
        self.assertEqual(self.stats_data["recent_attempts"][0]["key"], "test/path/file.nc")

    def test_format_error_message(self):
        """Test the error message formatting with timestamps."""
        # Test normal formatting
        error_message = format_error_message("network", "Connection timed out")
        self.assertTrue("[" in error_message)  # Contains timestamp
        self.assertTrue("network: Connection timed out" in error_message)

        # Test when error_type is already in message
        error_message = format_error_message("timeout", "timeout: Operation took too long")
        self.assertTrue("[" in error_message)  # Contains timestamp
        # Should not duplicate the error type
        self.assertTrue("timeout: Operation took too long" in error_message)
        self.assertFalse("timeout: timeout: Operation took too long" in error_message)

    def test_error_categorization(self):
        """Test that different error types are categorized correctly."""
        # Test each error type
        error_types = {
            "not_found": "not_found",
            "auth": "auth_errors",
            "timeout": "timeouts",
            "network": "network_errors",
        }

        for i, (error_type, counter_name) in enumerate(error_types.items()):
            # Reset counter for this error type
            self.stats_data[counter_name] = 0

            # Update stats with this error type
            update_download_stats(
                success=False,
                error_type=error_type,
                error_message=f"Error of type {error_type}",
            )

            # Verify the counter was incremented
            self.assertEqual(
                self.stats_data[counter_name],
                1,
                f"Counter for {error_type} was not incremented",
            )

            # Verify failed count increases
            self.assertEqual(self.stats_data["failed"], i + 1)

    def test_file_size_tracking(self):
        """Test tracking of file sizes."""
        # Upload multiple files of different sizes
        file_sizes = [1024, 512, 2048]

        for size in file_sizes:
            update_download_stats(success=True, download_time=1.0, file_size=size)

        # Verify size tracking
        self.assertEqual(self.stats_data["largest_file_size"], max(file_sizes))
        self.assertEqual(self.stats_data["smallest_file_size"], min(file_sizes))
        self.assertEqual(self.stats_data["total_bytes"], sum(file_sizes))

    def test_error_history_limit(self):
        """Test that error history is limited to the most recent errors."""
        # Mock the log_download_statistics function to prevent the automatic logging
        with patch("goesvfi.integrity_check.remote.s3_store.log_download_statistics"):
            # Generate more than 20 errors
            for i in range(25):
                update_download_stats(success=False, error_type="network", error_message=f"Error {i}")

            # Verify only the most recent 20 are kept
            self.assertEqual(len(self.stats_data["errors"]), 20)

            # Verify the most recent errors are in the list (not all 25 can fit in 20 slots)
            # The oldest errors won't be in the list
            for i in range(20, 25):
                for error in self.stats_data["errors"]:
                    if f"Error {i}" in error:
                        break
                else:
                    self.fail(f"Error {i} not found in errors list")

            # The list should have 20 entries (not 25)
            self.assertEqual(len(self.stats_data["errors"]), 20)

    def test_recent_attempts_history_limit(self):
        """Test that recent attempts history is limited."""
        # Mock the log_download_statistics function to prevent the automatic logging
        with patch("goesvfi.integrity_check.remote.s3_store.log_download_statistics"):
            # Generate more than 50 attempts
            for i in range(60):
                update_download_stats(
                    success=i % 2 == 0,  # Alternate success/failure
                    download_time=1.0,
                    file_size=1024 if i % 2 == 0 else 0,
                    error_type="network" if i % 2 == 1 else None,
                    error_message=f"Error {i}" if i % 2 == 1 else None,
                    key=f"test/file_{i}.nc",  # Add a key to avoid None key issues
                )

            # Verify only the most recent 50 are kept
            self.assertEqual(len(self.stats_data["recent_attempts"]), 50)

            # Verify they have timestamps
            for attempt in self.stats_data["recent_attempts"]:
                self.assertIn("timestamp", attempt)

    def test_download_rate_calculation(self):
        """Test calculation of download rates."""
        # Add several downloads with different rates
        test_cases = [
            (1024, 1.0),  # 1024 B/s
            (2048, 1.0),  # 2048 B/s
            (512, 0.5),  # 1024 B/s
        ]

        for file_size, download_time in test_cases:
            update_download_stats(success=True, download_time=download_time, file_size=file_size)

        # Verify rates were calculated correctly
        expected_rates = [1024, 2048, 1024]
        self.assertEqual(len(self.stats_data["download_rates"]), 3)
        for i, rate in enumerate(expected_rates):
            self.assertEqual(self.stats_data["download_rates"][i], rate)

    @patch("goesvfi.integrity_check.remote.s3_store.LOGGER")
    def test_log_download_statistics(self, mock_logger):
        """Test enhanced logging of download statistics."""
        # Add comprehensive test data
        self.stats_data.update(
            {
                "total_attempts": 10,
                "successful": 7,
                "failed": 3,
                "retry_count": 2,
                "timeouts": 1,
                "network_errors": 2,
                "download_times": [1.0, 1.5, 2.0, 0.5, 1.0, 2.5, 1.2],
                "download_rates": [1024.0, 2048.0, 512.0, 1024.0],
                "total_bytes": 7168,
                "largest_file_size": 2048,
                "smallest_file_size": 512,
                "last_success_time": time.time() - 60,  # 60 seconds ago
                "errors": [
                    "[2023-01-01T12:00:00] timeout: Connection timed out",
                    "[2023-01-01T12:01:00] network: Connection reset",
                ],
                "recent_attempts": [
                    {
                        "timestamp": "2023-01-01T12:00:00",
                        "success": False,
                        "error_type": "timeout",
                        "satellite": "GOES16",
                        "key": "test-key-1",
                    },
                    {
                        "timestamp": "2023-01-01T12:01:00",
                        "success": True,
                        "download_time": 2.0,
                        "file_size": 1024,
                        "satellite": "GOES16",
                        "key": "test-key-2",
                    },
                    {
                        "timestamp": "2023-01-01T12:02:00",
                        "success": True,
                        "download_time": 2.5,
                        "file_size": 2048,
                        "satellite": "GOES16",
                        "key": "a/very/long/path/to/a/file/with/a/really/long/name.nc",
                    },
                ],
            }
        )

        # Call the function
        log_download_statistics()

        # Verify logger was called
        mock_logger.info.assert_called()

        # Get the log message
        log_message = mock_logger.info.call_args[0][0]

        # Check that the log message contains key stats
        self.assertIn("S3 Download Statistics", log_message)
        self.assertIn("Session ID: test-session-123", log_message)
        self.assertIn("Hostname: test-host", log_message)
        self.assertIn("Start time: 2023-01-01T12:00:00", log_message)
        self.assertIn("Total attempts: 10", log_message)
        self.assertIn("Successful: 7 (70.0%)", log_message)
        self.assertIn("Failed: 3", log_message)
        self.assertIn("Retries: 2", log_message)

        # Check that the enhanced metrics are included
        self.assertIn("Recent errors:", log_message)
        self.assertIn("Recent download attempts:", log_message)
        self.assertIn("Time since last successful download:", log_message)

        # Check that it shows the filename for keys
        self.assertIn("name.nc", log_message)


if __name__ == "__main__":
    unittest.main()
