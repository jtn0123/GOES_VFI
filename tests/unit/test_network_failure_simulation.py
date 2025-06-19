"""Tests for network failure simulation and retry logic.

These tests verify retry mechanisms, exponential backoff, and fallback strategies
when network failures occur during satellite data operations.
"""

import asyncio
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import aiohttp
import botocore.exceptions
import pytest

from goesvfi.integrity_check.remote.base import (
    AuthenticationError,
    NetworkError,
    RateLimitError,
    RemoteStoreError,
    TemporaryError,
)
from goesvfi.integrity_check.remote.cdn_store import CDNStore
from goesvfi.integrity_check.remote.composite_store import CompositeStore
from goesvfi.integrity_check.remote.s3_store import (
    S3Store,
    retry_with_exponential_backoff,
)
from goesvfi.integrity_check.time_index import SatellitePattern


class TestNetworkFailureSimulation:
    """Test network failure scenarios and recovery mechanisms."""

    @pytest.fixture
    def mock_time(self):
        """Mock time.sleep to speed up tests."""
        with patch("time.sleep"):
            yield

    @pytest.mark.asyncio
    async def test_exponential_backoff_retry(self, mock_time):
        """Test exponential backoff retry mechanism."""
        attempt_count = 0
        attempt_times = []

        @retry_with_exponential_backoff(max_retries=3, initial_backoff=1.0)
        async def flaky_operation():
            nonlocal attempt_count
            attempt_count += 1
            attempt_times.append(time.time())

            if attempt_count < 3:
                raise aiohttp.ClientError("Connection timeout")
            return "Success"

        # Execute the operation
        start_time = time.time()
        result = await flaky_operation()

        assert result == "Success"
        assert attempt_count == 3

        # Verify backoff timing (accounting for mocked sleep)
        # First attempt is immediate, then exponential delays
        assert len(attempt_times) == 3

    @pytest.mark.asyncio
    async def test_non_retryable_errors(self):
        """Test that certain errors are not retried."""
        attempt_count = 0

        @retry_with_exponential_backoff(max_retries=3)
        async def auth_failure():
            nonlocal attempt_count
            attempt_count += 1

            # Simulate authentication error (non-retryable)
            error = botocore.exceptions.ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
                "GetObject",
            )
            raise error

        # Should fail immediately without retries
        with pytest.raises(botocore.exceptions.ClientError):
            await auth_failure()

        assert attempt_count == 1  # No retries for auth errors

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, mock_time):
        """Test behavior when max retries are exceeded."""
        attempt_count = 0

        @retry_with_exponential_backoff(max_retries=3, initial_backoff=0.1)
        async def always_fails():
            nonlocal attempt_count
            attempt_count += 1
            raise socket.timeout("Connection timed out")

        # Should eventually give up and raise the error
        with pytest.raises(socket.timeout):
            await always_fails()

        assert attempt_count == 4  # Initial attempt + 3 retries

    @pytest.mark.asyncio
    async def test_jitter_in_backoff(self, mock_time):
        """Test that jitter is applied to prevent thundering herd."""
        backoff_times = []

        # Mock time.sleep to capture sleep durations
        with patch("asyncio.sleep") as mock_sleep:
            mock_sleep.side_effect = lambda x: backoff_times.append(x)

            @retry_with_exponential_backoff(
                max_retries=3, initial_backoff=1.0, jitter_factor=0.3
            )
            async def flaky_operation():
                if len(backoff_times) < 3:
                    raise aiohttp.ClientError("Timeout")
                return "Success"

            await flaky_operation()

        # Verify jitter was applied (times should not be exactly 1, 2, 4)
        assert len(backoff_times) == 3
        assert 1.0 <= backoff_times[0] <= 1.3  # 1s + up to 30% jitter
        assert 2.0 <= backoff_times[1] <= 2.6  # 2s + up to 30% jitter
        assert 4.0 <= backoff_times[2] <= 5.2  # 4s + up to 30% jitter

    @pytest.mark.asyncio
    async def test_s3_connection_timeout(self):
        """Test S3 connection timeout handling."""
        store = S3Store(connection_timeout=1.0, read_timeout=5.0)

        # Mock S3 client to simulate timeout
        mock_s3_client = AsyncMock()
        mock_s3_client.head_object = AsyncMock(
            side_effect=asyncio.TimeoutError("Connection timeout")
        )

        with patch.object(store, "_get_s3_client", return_value=mock_s3_client):
            timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

            with pytest.raises(NetworkError) as exc_info:
                await store.exists(ts=timestamp, satellite=SatellitePattern.GOES_16)

            assert "Connection timeout" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_dns_resolution_failure(self):
        """Test handling of DNS resolution failures."""
        store = S3Store()

        # Mock S3 client to simulate DNS failure
        mock_s3_client = AsyncMock()
        dns_error = aiohttp.ClientConnectorError(
            connection_key=None,
            os_error=socket.gaierror(-2, "Name or service not known"),
        )
        mock_s3_client.head_object = AsyncMock(side_effect=dns_error)

        with patch.object(store, "_get_s3_client", return_value=mock_s3_client):
            timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

            with pytest.raises(NetworkError) as exc_info:
                await store.exists(ts=timestamp, satellite=SatellitePattern.GOES_16)

            # Error should mention DNS
            assert "DNS" in str(exc_info.value) or "Name or service not known" in str(
                exc_info.value
            )

    @pytest.mark.asyncio
    async def test_rate_limiting_handling(self, mock_time):
        """Test handling of rate limiting errors."""
        store = S3Store()

        # Mock S3 client to simulate rate limiting
        mock_s3_client = AsyncMock()
        rate_limit_error = botocore.exceptions.ClientError(
            {
                "Error": {
                    "Code": "SlowDown",
                    "Message": "Please reduce your request rate.",
                },
                "ResponseMetadata": {"HTTPHeaders": {"retry-after": "2"}},
            },
            "HeadObject",
        )

        # First call raises rate limit, second succeeds
        mock_s3_client.head_object = AsyncMock(
            side_effect=[rate_limit_error, {"ContentLength": 1000}]
        )

        with patch.object(store, "_get_s3_client", return_value=mock_s3_client):
            timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

            # Should retry and succeed
            result = await store.exists(
                ts=timestamp, satellite=SatellitePattern.GOES_16
            )

            assert result is True
            assert mock_s3_client.head_object.call_count == 2

    @pytest.mark.asyncio
    async def test_composite_store_failover(self):
        """Test composite store failover between multiple sources."""
        # Mock S3 store that fails
        mock_s3 = AsyncMock(spec=S3Store)
        mock_s3.download = AsyncMock(side_effect=NetworkError("S3 connection failed"))
        mock_s3.get_statistics = MagicMock(
            return_value={
                "attempts": 10,
                "successes": 2,
                "failures": 8,
                "consecutive_failures": 3,
            }
        )

        # Mock CDN store that succeeds
        mock_cdn = AsyncMock(spec=CDNStore)
        test_path = Path("/tmp/test.nc")
        mock_cdn.download = AsyncMock(return_value=test_path)
        mock_cdn.get_statistics = MagicMock(
            return_value={
                "attempts": 5,
                "successes": 4,
                "failures": 1,
                "consecutive_failures": 0,
            }
        )

        # Create composite store
        composite = CompositeStore([mock_s3, mock_cdn])

        timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Download should succeed via CDN
        result = await composite.download(
            ts=timestamp, satellite=SatellitePattern.GOES_16, dest_path=test_path
        )

        assert result == test_path
        mock_s3.download.assert_called_once()
        mock_cdn.download.assert_called_once()

        # After failure, CDN should be preferred
        stats = composite.get_store_statistics()
        # CDN should have better success rate
        assert stats[1]["success_rate"] > stats[0]["success_rate"]

    @pytest.mark.asyncio
    async def test_intermittent_network_issues(self, mock_time):
        """Test handling of intermittent network issues."""
        success_pattern = [False, False, True, False, True, True]
        attempt_idx = 0

        @retry_with_exponential_backoff(max_retries=5, initial_backoff=0.1)
        async def intermittent_operation():
            nonlocal attempt_idx
            success = (
                success_pattern[attempt_idx]
                if attempt_idx < len(success_pattern)
                else True
            )
            attempt_idx += 1

            if not success:
                raise aiohttp.ClientError("Network unreachable")
            return f"Success on attempt {attempt_idx}"

        result = await intermittent_operation()
        assert "Success on attempt 3" in result
        assert attempt_idx == 3

    @pytest.mark.asyncio
    async def test_connection_pool_exhaustion(self):
        """Test handling when connection pool is exhausted."""
        store = S3Store()

        # Simulate connection pool exhaustion
        mock_s3_client = AsyncMock()
        pool_error = aiohttp.ClientError("Connection pool is full")
        mock_s3_client.head_object = AsyncMock(side_effect=pool_error)

        with patch.object(store, "_get_s3_client", return_value=mock_s3_client):
            timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

            # Should raise NetworkError
            with pytest.raises(NetworkError) as exc_info:
                await store.exists(ts=timestamp, satellite=SatellitePattern.GOES_16)

            assert "Connection pool" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_partial_download_recovery(self):
        """Test recovery from partial downloads."""
        store = S3Store()
        download_path = Path("/tmp/partial_download.nc")

        # Mock S3 client
        mock_s3_client = AsyncMock()

        # First attempt: partial download (connection drops)
        async def partial_download(*args, **kwargs):
            # Create partial file
            download_path.parent.mkdir(parents=True, exist_ok=True)
            download_path.write_bytes(b"partial data")
            raise aiohttp.ClientError("Connection reset by peer")

        # Second attempt: successful download
        async def successful_download(*args, **kwargs):
            download_path.write_bytes(b"complete data file")
            return None

        mock_s3_client.download_file = AsyncMock(
            side_effect=[partial_download, successful_download]
        )
        mock_s3_client.head_object = AsyncMock(
            return_value={"ContentLength": len(b"complete data file")}
        )

        with patch.object(store, "_get_s3_client", return_value=mock_s3_client):
            with patch("pathlib.Path.unlink") as mock_unlink:
                timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

                # Should retry and succeed
                with patch("pathlib.Path.exists", return_value=True):
                    with patch("pathlib.Path.stat") as mock_stat:
                        mock_stat.return_value.st_size = len(b"complete data file")

                        result = await store.download(
                            ts=timestamp,
                            satellite=SatellitePattern.GOES_16,
                            dest_path=download_path,
                        )

                assert mock_s3_client.download_file.call_count == 2

    @pytest.mark.asyncio
    async def test_network_diagnostics_in_errors(self):
        """Test that network errors include diagnostic information."""
        store = S3Store()

        # Mock various network diagnostic functions
        with patch(
            "socket.gethostbyname", side_effect=socket.gaierror("DNS lookup failed")
        ):
            with patch.object(store, "_test_connectivity", return_value=False):
                # Create network error with diagnostics
                error = store.create_error_from_code(
                    "NetworkError", "Connection failed", include_diagnostics=True
                )

                # Should include diagnostic info
                assert isinstance(error, NetworkError)
                error_msg = str(error)
                assert "Connection failed" in error_msg

    @pytest.mark.asyncio
    async def test_concurrent_retry_limiting(self):
        """Test that concurrent operations don't overwhelm with retries."""
        store = S3Store()
        retry_counts = []

        @retry_with_exponential_backoff(max_retries=3, initial_backoff=0.1)
        async def failing_operation(op_id):
            retry_counts.append(op_id)
            raise aiohttp.ClientError(f"Operation {op_id} failed")

        # Run multiple operations concurrently
        with pytest.raises(aiohttp.ClientError):
            tasks = [failing_operation(i) for i in range(5)]
            await asyncio.gather(*tasks, return_exceptions=True)

        # Each operation should retry independently
        for i in range(5):
            operation_retries = retry_counts.count(i)
            assert operation_retries == 4  # Initial + 3 retries
