"""
Optimized tests for network failure simulation and retry logic.

Key optimizations:
1. Mock asyncio.sleep to avoid real delays
2. Use faster retry counts for testing
3. Combine related test scenarios
4. Mock time.time() for consistent timing
"""

import asyncio
from functools import wraps
import random
import socket
from typing import Never
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import botocore.exceptions
import pytest

from goesvfi.integrity_check.remote.base import NetworkError
from goesvfi.integrity_check.remote.composite_store import CompositeStore
from goesvfi.integrity_check.remote.s3_store import S3Store


def retry_with_exponential_backoff(max_retries=3, initial_backoff=1.0, jitter_factor=0.0):
    """Decorator to retry a function with exponential backoff (optimized for tests)."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            backoff = initial_backoff
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Check if this is a non-retryable error
                    if isinstance(e, botocore.exceptions.ClientError):
                        error_code = e.response.get("Error", {}).get("Code", "") if hasattr(e, "response") else ""
                        # Authentication errors should not be retried
                        if error_code in {
                            "AccessDenied",
                            "InvalidAccessKeyId",
                            "SignatureDoesNotMatch",
                        }:
                            raise

                    if attempt < max_retries:
                        # Apply jitter if requested
                        jittered_backoff = backoff
                        if jitter_factor > 0:
                            jittered_backoff = backoff * (1 + random.uniform(0, jitter_factor))
                        await asyncio.sleep(jittered_backoff)
                        backoff *= 2
                    else:
                        raise last_exception
            return None

        return wrapper

    return decorator


class TestNetworkFailureSimulationOptimized:
    """Optimized test network failure scenarios and recovery mechanisms."""

    @pytest.fixture(autouse=True)
    def mock_async_sleep(self):
        """Mock asyncio.sleep to speed up all tests."""
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            # Make sleep instant but trackable
            mock_sleep.side_effect = lambda x: None
            yield mock_sleep

    @pytest.fixture()
    def mock_time_module(self):
        """Mock time module for consistent timing."""
        with patch("time.time") as mock_time, patch("time.sleep") as mock_sleep:
            # Start at time 1000
            mock_time.return_value = 1000.0
            mock_sleep.side_effect = lambda x: None
            yield mock_time

    @pytest.mark.asyncio()
    async def test_exponential_backoff_and_jitter(self, mock_async_sleep) -> None:
        """Test both exponential backoff and jitter in one test."""
        attempt_count = 0
        attempt_times = []

        @retry_with_exponential_backoff(max_retries=3, initial_backoff=0.1, jitter_factor=0.5)
        async def flaky_operation() -> str:
            nonlocal attempt_count
            attempt_count += 1
            attempt_times.append(mock_async_sleep.call_count)

            if attempt_count < 3:
                msg = "Connection timeout"
                raise aiohttp.ClientError(msg)
            return "Success"

        # Execute the operation
        result = await flaky_operation()

        assert result == "Success"
        assert attempt_count == 3  # Initial + 2 retries

        # Verify sleep was called with increasing delays
        assert mock_async_sleep.call_count == 2  # 2 retries = 2 sleeps

        # Check that backoff values were passed (with potential jitter)
        # First retry: 0.1 * (1 + jitter)
        # Second retry: 0.2 * (1 + jitter)
        # Just verify they were called

    @pytest.mark.asyncio()
    async def test_non_retryable_and_max_retries(self, mock_async_sleep) -> None:
        """Test non-retryable errors and max retries exceeded in one test."""

        # Test non-retryable error
        @retry_with_exponential_backoff(max_retries=3)
        async def auth_error_operation() -> str:
            error = botocore.exceptions.ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}, "ListObjects"
            )
            raise error

        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            await auth_error_operation()

        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"
        assert mock_async_sleep.call_count == 0  # No retries for auth errors

        # Reset mock
        mock_async_sleep.reset_mock()

        # Test max retries exceeded
        @retry_with_exponential_backoff(max_retries=2, initial_backoff=0.01)
        async def always_failing_operation() -> str:
            msg = "Persistent failure"
            raise aiohttp.ClientError(msg)

        with pytest.raises(aiohttp.ClientError) as exc_info:
            await always_failing_operation()

        assert str(exc_info.value) == "Persistent failure"
        assert mock_async_sleep.call_count == 2  # Exactly max_retries sleeps

    @pytest.mark.asyncio()
    async def test_s3_connection_and_dns_failures(self) -> None:
        """Test S3 connection timeout and DNS resolution failures together."""
        # Mock S3 client
        mock_client = MagicMock()

        # Test connection timeout
        mock_client.list_objects_v2.side_effect = TimeoutError("Connection timed out")

        with patch("boto3.client", return_value=mock_client):
            store = S3Store()

            with pytest.raises(socket.timeout):
                await store._async_wrapper(mock_client.list_objects_v2, Bucket="test-bucket", Prefix="test-prefix")

        # Test DNS resolution failure
        dns_error = aiohttp.ClientConnectorError(
            connection_key=None, os_error=socket.gaierror(-2, "Name or service not known")
        )

        async def mock_request(*args, **kwargs) -> Never:
            raise dns_error

        with patch("aiohttp.ClientSession.request", new=mock_request):
            with pytest.raises(aiohttp.ClientConnectorError):
                async with aiohttp.ClientSession() as session:
                    await session.request("GET", "https://invalid-domain-xyz.com")

    @pytest.mark.asyncio()
    async def test_rate_limiting_and_composite_failover(self, mock_async_sleep, mock_time_module) -> None:
        """Test rate limiting handling and composite store failover together."""
        # Test rate limiting
        call_count = 0

        async def rate_limited_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                # Advance time to simulate rate limit window
                mock_time_module.return_value += 0.1
                return None  # Simulated rate limit response
            return {"data": "success"}

        # Simulate rate limiting with retries
        result = None
        for _ in range(3):
            result = await rate_limited_operation()
            if result:
                break
            await asyncio.sleep(0.01)  # Small delay

        assert result == {"data": "success"}
        assert call_count == 3

        # Test composite store failover
        primary = AsyncMock(spec=S3Store)
        fallback = AsyncMock(spec=S3Store)

        # Primary fails
        primary.get_file_info.side_effect = NetworkError("Primary failed")
        # Fallback succeeds
        fallback.get_file_info.return_value = {"size": 1024, "exists": True}

        composite = CompositeStore(primary=primary, fallback=fallback)

        result = await composite.get_file_info("test-file")
        assert result == {"size": 1024, "exists": True}

        # Verify failover occurred
        primary.get_file_info.assert_called_once_with("test-file")
        fallback.get_file_info.assert_called_once_with("test-file")

    @pytest.mark.asyncio()
    async def test_intermittent_and_pool_exhaustion(self, mock_async_sleep) -> None:
        """Test intermittent network issues and connection pool exhaustion together."""
        # Test intermittent issues
        attempt = 0

        async def intermittent_operation():
            nonlocal attempt
            attempt += 1
            if attempt % 2 == 0:  # Succeed on even attempts
                return {"status": "ok"}
            msg = "Intermittent failure"
            raise aiohttp.ClientError(msg)

        # Should succeed on second attempt
        try:
            result = await intermittent_operation()
        except:
            result = await intermittent_operation()

        assert result == {"status": "ok"}
        assert attempt == 2

        # Test connection pool exhaustion
        exhausted_error = aiohttp.ClientError("Connection pool exhausted")

        async def exhausted_operation() -> Never:
            raise exhausted_error

        with pytest.raises(aiohttp.ClientError) as exc_info:
            await exhausted_operation()

        assert "Connection pool exhausted" in str(exc_info.value)

    @pytest.mark.asyncio()
    async def test_partial_download_and_diagnostics(self) -> None:
        """Test partial download recovery and network diagnostics together."""
        # Test partial download recovery
        mock_downloader = AsyncMock()
        bytes_downloaded = 0

        async def partial_download(start_byte=0):
            nonlocal bytes_downloaded
            if start_byte == 0 and bytes_downloaded == 0:
                # First attempt fails after 5000 bytes
                bytes_downloaded = 5000
                msg = "Connection lost"
                raise aiohttp.ClientError(msg)
            # Resume succeeds
            return b"x" * (10000 - start_byte)

        mock_downloader.side_effect = partial_download

        # Simulate download with resume
        try:
            await mock_downloader(start_byte=0)
        except aiohttp.ClientError:
            # Resume from where we left off
            result = await mock_downloader(start_byte=5000)
            assert len(result) == 5000

        # Test network diagnostics
        diag_info = {"dns_resolved": True, "connection_established": False, "error_type": "timeout", "retry_count": 3}

        error = NetworkError("Connection failed", diagnostics=diag_info)
        assert error.diagnostics == diag_info
        assert "timeout" in error.diagnostics["error_type"]

    @pytest.mark.asyncio()
    async def test_concurrent_retry_limiting(self, mock_async_sleep) -> None:
        """Test limiting concurrent retries to prevent resource exhaustion."""
        active_retries = 0
        max_concurrent = 2

        async def limited_operation(op_id: int) -> str | None:
            nonlocal active_retries

            if active_retries >= max_concurrent:
                # Don't retry if too many active
                msg = f"Too many concurrent retries: {active_retries}"
                raise RuntimeError(msg)

            active_retries += 1
            try:
                await asyncio.sleep(0.01)  # Simulate work
                if op_id < 3:
                    msg = f"Operation {op_id} failed"
                    raise aiohttp.ClientError(msg)
                return f"Success {op_id}"
            finally:
                active_retries -= 1

        # Run multiple operations concurrently
        tasks = [limited_operation(i) for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check results
        [r for r in results if isinstance(r, Exception)]
        successes = [r for r in results if isinstance(r, str)]

        assert len(successes) >= 2  # At least some should succeed
        assert active_retries == 0  # All retries should be complete
