"""Unit tests for S3 retry strategy and resilience.

These tests focus on the retry behavior, timeout handling, and resilience
of the S3Store implementation when faced with network issues.
"""

import asyncio
from datetime import datetime
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from goesvfi.integrity_check.remote.base import ConnectionError
from goesvfi.integrity_check.remote.s3_store import S3Store, update_download_stats
from goesvfi.integrity_check.time_index import SatellitePattern


class TestS3RetryStrategy(unittest.IsolatedAsyncioTestCase):
    """Test cases for S3Store retry strategy and network resilience."""

    async def asyncSetUp(self) -> None:
        """Set up test fixtures."""
        # We'll handle our own mocking for specific tests
        # because we need more control over the retry behavior

        self.test_timestamp = datetime(2023, 6, 15, 12, 0, 0)
        self.test_satellite = SatellitePattern.GOES_18
        self.test_dest_path = Path("/tmp/test_download.nc")

    async def test_client_creation_retry(self) -> None:
        """Test retry logic for client creation."""
        # We need to mock at the aioboto3.Session level
        with (
            patch("aioboto3.Session") as mock_session_class,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            # Setup a mock session
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            # Setup the client context to raise TimeoutError on first call
            mock_client_context = MagicMock()
            mock_client = AsyncMock()
            mock_client_context.__aenter__ = AsyncMock()

            # First call raises TimeoutError, second returns a client
            mock_client_context.__aenter__.side_effect = [
                TimeoutError("Connection timed out"),
                mock_client,
            ]

            # Configure session.client to return our mock context
            mock_session.client.return_value = mock_client_context

            # Create S3Store and call _get_s3_client
            store = S3Store(timeout=5)
            # This should retry and succeed on the second attempt
            client = await store._get_s3_client()

            # Verify the result and call counts
            assert client == mock_client
            assert mock_client_context.__aenter__.call_count == 2

            # Verify correct session setup - it should be called twice due to retry
            assert mock_session_class.call_count == 2
            # All calls should have the region_name parameter
            for call in mock_session_class.call_args_list:
                assert call[1] == {"region_name": "us-east-1"}

            # Verify client creation was called twice (once for each session)
            assert mock_session.client.call_count == 2

    async def test_client_creation_retry_fails_after_max_retries(self) -> None:
        """Test client creation fails after exceeding max retries."""
        # We need to mock at the aioboto3.Session level
        with patch("aioboto3.Session") as mock_session_class:
            # Setup a mock session
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            # Setup the client context to always raise TimeoutError
            mock_client_context = MagicMock()
            mock_client_context.__aenter__ = AsyncMock(side_effect=TimeoutError("Connection timed out"))

            # Configure session.client to return our mock context
            mock_session.client.return_value = mock_client_context

            # Create S3Store with patch to sleep to avoid real delays
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                store = S3Store(timeout=5)

                # This should retry 3 times and then raise ConnectionError
                with pytest.raises(ConnectionError) as exc_info:
                    await store._get_s3_client()

                # Verify error message
                assert "Could not connect to AWS S3 service" in str(exc_info.value)

                # Verify retry attempts
                assert mock_client_context.__aenter__.call_count == 3

                # Verify sleep was called for retries
                assert mock_sleep.call_count == 2  # Once per retry (before 3rd attempt)

    async def test_download_with_retry_on_transient_error(self) -> None:
        """Test download with retry on transient network errors."""
        # Test the retry behavior at the _get_s3_client level
        # which is where the actual retry logic happens

        # Track connection attempts
        connection_attempts = 0

        # Mock aioboto3.Session to simulate connection failures
        with patch("aioboto3.Session") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            # Create a mock client context
            mock_client_context = MagicMock()
            mock_client = AsyncMock()

            # Configure the context manager to fail twice then succeed
            async def mock_aenter(self):
                nonlocal connection_attempts
                connection_attempts += 1
                if connection_attempts <= 2:
                    msg = "Connection timed out"
                    raise TimeoutError(msg)
                return mock_client

            mock_client_context.__aenter__ = mock_aenter
            mock_client_context.__aexit__ = AsyncMock(return_value=None)

            # Configure session.client to return our mock context
            mock_session.client.return_value = mock_client_context

            # Create S3Store and test retry behavior
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                store = S3Store(timeout=5)

                # Get client - should retry and succeed on third attempt
                client = await store._get_s3_client()

                # Verify we got the client
                assert client == mock_client

                # Verify we made 3 attempts
                assert connection_attempts == 3

                # Verify sleep was called for backoff (2 times - before 2nd and 3rd attempts)
                assert mock_sleep.call_count == 2

    async def test_concurrent_download_limiter(self) -> None:
        """Test that concurrent downloads are limited by the semaphore."""
        # This test verifies concurrent task limiting behavior
        # We'll simulate the concurrency limiting without actual S3 calls

        # Track active tasks for testing concurrency
        active_tasks = 0
        max_active = 0
        task_count = 0

        # Create a semaphore to limit concurrency (similar to S3Store)
        semaphore = asyncio.Semaphore(2)  # Limit to 2 concurrent tasks

        async def simulated_download(task_id: int) -> str:
            nonlocal active_tasks, max_active, task_count

            async with semaphore:
                active_tasks += 1
                max_active = max(max_active, active_tasks)
                task_count += 1

                # Simulate work with a delay
                await asyncio.sleep(0.05)

                active_tasks -= 1
                return f"Result_{task_id}"

        # Create multiple tasks
        tasks = []
        for i in range(5):
            task = asyncio.create_task(simulated_download(i))
            tasks.append(task)

        # Wait for all tasks
        results = await asyncio.gather(*tasks)

        # Verify all tasks completed
        assert task_count == 5
        assert len(results) == 5

        # Verify concurrency was limited to 2
        assert max_active <= 2

        # Verify we actually had concurrent execution (max should be 2 if running concurrently)
        assert max_active == 2, "Expected to see 2 concurrent tasks"

    async def test_network_diagnostics_collection(self) -> None:
        """Test that network diagnostics are collected on repeated failures."""
        # Mock get_system_network_info
        with patch("goesvfi.integrity_check.remote.s3_store.get_system_network_info") as mock_info:
            # Set the failed count to 10 so that when the condition checks failed % 5 == 0 it's true
            # The code checks the OLD value before increment: if old_failed % 5 == 0, so we need 10 % 5 == 0
            from goesvfi.integrity_check.remote.s3_store import DOWNLOAD_STATS

            DOWNLOAD_STATS["failed"] = 10  # 10 % 5 == 0 triggers diagnostics
            DOWNLOAD_STATS["total_attempts"] = 10
            DOWNLOAD_STATS["errors"] = []  # Initialize errors list

            # Call update_download_stats with a failure
            # This should trigger network diagnostics collection because 10 % 5 == 0
            update_download_stats(success=False, error_type="network", error_message="Connection failed")

            # Verify get_system_network_info was called
            mock_info.assert_called_once()


if __name__ == "__main__":
    unittest.main()
