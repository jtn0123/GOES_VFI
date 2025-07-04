"""Tests for S3 connection pooling."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import the module directly to avoid circular imports
sys.path.insert(0, "goesvfi/integrity_check/remote")
from s3_connection_pool import (
    S3ConnectionPool,
    get_global_pool,
    reset_global_pool,
)


class TestS3ConnectionPool:
    """Test the S3ConnectionPool class."""

    @pytest.fixture()
    def mock_s3_client(self):
        """Create a mock S3 client."""
        client = AsyncMock()
        # Add required attributes/methods
        client.list_buckets = AsyncMock(return_value={"Buckets": []})
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        return client

    @pytest.fixture()
    def mock_session(self, mock_s3_client):
        """Create a mock aioboto3 session."""
        session = MagicMock()
        client_context = MagicMock()
        client_context.__aenter__ = AsyncMock(return_value=mock_s3_client)
        session.client.return_value = client_context
        return session

    @pytest.fixture()
    async def connection_pool(self):
        """Create a connection pool instance."""
        pool = S3ConnectionPool(max_connections=3, region="us-east-1")
        yield pool
        await pool.close_all()

    def test_pool_initialization(self) -> None:
        """Test connection pool initializes correctly."""
        pool = S3ConnectionPool(max_connections=5, region="us-west-2", connect_timeout=20, read_timeout=120)

        assert pool.max_connections == 5
        assert pool.region == "us-west-2"
        assert pool.connect_timeout == 20
        assert pool.read_timeout == 120
        assert len(pool._available_connections) == 0
        assert len(pool._in_use_connections) == 0

    @pytest.mark.asyncio()
    async def test_create_connection(self, connection_pool, mock_session) -> None:
        """Test creating a new connection."""
        with patch("s3_connection_pool.aioboto3.Session", return_value=mock_session):
            client = await connection_pool._create_connection()

            assert client is not None
            assert connection_pool._stats["connections_created"] == 1

    @pytest.mark.asyncio()
    async def test_acquire_new_connection(self, connection_pool, mock_session, mock_s3_client) -> None:
        """Test acquiring a new connection when pool is empty."""
        with patch("s3_connection_pool.aioboto3.Session", return_value=mock_session):
            async with connection_pool.acquire() as client:
                assert client == mock_s3_client
                assert len(connection_pool._in_use_connections) == 1
                assert connection_pool._stats["pool_misses"] == 1
                assert connection_pool._stats["pool_hits"] == 0

    @pytest.mark.asyncio()
    async def test_connection_reuse(self, connection_pool, mock_session, mock_s3_client) -> None:
        """Test connection reuse from pool."""
        with patch("s3_connection_pool.aioboto3.Session", return_value=mock_session):
            # First acquisition creates new connection
            async with connection_pool.acquire() as client1:
                assert connection_pool._stats["pool_misses"] == 1

            # Connection should be returned to pool
            assert len(connection_pool._available_connections) == 1
            assert len(connection_pool._in_use_connections) == 0

            # Second acquisition should reuse connection
            async with connection_pool.acquire() as client2:
                assert client2 == client1  # Same client instance
                assert connection_pool._stats["pool_hits"] == 1
                assert connection_pool._stats["connections_reused"] == 1

    @pytest.mark.asyncio()
    async def test_connection_health_check(self, connection_pool, mock_s3_client) -> None:
        """Test connection health checking."""
        # Healthy connection
        mock_s3_client.list_buckets.return_value = {"Buckets": []}
        assert await connection_pool._check_connection_health(mock_s3_client) is True

        # Unhealthy connection
        mock_s3_client.list_buckets.side_effect = Exception("Connection error")
        assert await connection_pool._check_connection_health(mock_s3_client) is False

    @pytest.mark.asyncio()
    async def test_unhealthy_connection_closed(self, connection_pool, mock_session, mock_s3_client) -> None:
        """Test that unhealthy connections are closed instead of returned to pool."""
        with patch("s3_connection_pool.aioboto3.Session", return_value=mock_session):
            # Acquire connection
            async with connection_pool.acquire():
                # Make connection unhealthy for when it's returned
                mock_s3_client.list_buckets.side_effect = Exception("Connection lost")

            # Connection should be closed, not returned to pool
            assert len(connection_pool._available_connections) == 0
            assert connection_pool._stats["connections_closed"] == 1

    @pytest.mark.asyncio()
    async def test_max_connections_limit(self) -> None:
        """Test that pool respects max connections limit."""
        pool = S3ConnectionPool(max_connections=2)

        # Create separate mock clients
        mock_client1 = AsyncMock()
        mock_client1.__aenter__ = AsyncMock(return_value=mock_client1)
        mock_client1.__aexit__ = AsyncMock(return_value=None)
        mock_client1.list_buckets = AsyncMock(return_value={"Buckets": []})

        mock_client2 = AsyncMock()
        mock_client2.__aenter__ = AsyncMock(return_value=mock_client2)
        mock_client2.__aexit__ = AsyncMock(return_value=None)
        mock_client2.list_buckets = AsyncMock(return_value={"Buckets": []})

        mock_client3 = AsyncMock()
        mock_client3.__aenter__ = AsyncMock(return_value=mock_client3)
        mock_client3.__aexit__ = AsyncMock(return_value=None)
        mock_client3.list_buckets = AsyncMock(return_value={"Buckets": []})

        mock_session = MagicMock()
        client_context = MagicMock()
        
        # Return different clients on each call
        client_context.__aenter__ = AsyncMock(side_effect=[mock_client1, mock_client2, mock_client3])
        mock_session.client.return_value = client_context

        with patch("s3_connection_pool.aioboto3.Session", return_value=mock_session):
            # Acquire max connections
            async with pool.acquire() as client1:
                async with pool.acquire() as client2:
                    # Both connections in use
                    assert len(pool._in_use_connections) == 2
                    assert client1 is not None
                    assert client2 is not None

                    # Try to acquire third (should still work but log warning)
                    async with pool.acquire() as client3:
                        assert client3 is not None
        
        # Cleanup
        await pool.close_all()

    @pytest.mark.asyncio()
    async def test_connection_age_limit(self, connection_pool, mock_session, mock_s3_client) -> None:
        """Test that old connections are not reused."""
        import time

        with patch("s3_connection_pool.aioboto3.Session", return_value=mock_session):
            # Acquire and release connection
            async with connection_pool.acquire():
                pass

            # Manually age the connection
            if connection_pool._available_connections:
                client, _ = connection_pool._available_connections.popleft()
                # Add back with old timestamp (6 minutes ago)
                connection_pool._available_connections.append((client, time.time() - 360))

            # Next acquisition should create new connection
            async with connection_pool.acquire():
                assert connection_pool._stats["connections_closed"] >= 1
                assert connection_pool._stats["connections_created"] >= 2

    @pytest.mark.asyncio()
    async def test_close_all_connections(self, connection_pool, mock_session, mock_s3_client) -> None:
        """Test closing all connections in pool."""
        with patch("s3_connection_pool.aioboto3.Session", return_value=mock_session):
            # Create some connections and let them return to pool
            async with connection_pool.acquire():
                pass
            async with connection_pool.acquire():
                pass

            # Should have connections in pool (they return when released)
            assert len(connection_pool._available_connections) >= 1

            # Close all
            await connection_pool.close_all()

            # Pool should be empty
            assert len(connection_pool._available_connections) == 0
            assert connection_pool._stats["connections_closed"] >= 1

    def test_get_stats(self, connection_pool) -> None:
        """Test getting pool statistics."""
        # Set some stats
        connection_pool._stats["pool_hits"] = 10
        connection_pool._stats["pool_misses"] = 5
        connection_pool._stats["wait_time_total"] = 1.5

        stats = connection_pool.get_stats()

        assert stats["pool_hits"] == 10
        assert stats["pool_misses"] == 5
        assert stats["hit_rate"] == 10 / 15  # 10 hits / 15 total
        assert stats["avg_wait_time"] == 1.5 / 15  # 1.5s / 15 requests
        assert stats["max_connections"] == connection_pool.max_connections

    def test_get_stats_no_requests(self, connection_pool) -> None:
        """Test getting stats when no requests have been made."""
        stats = connection_pool.get_stats()

        assert stats["hit_rate"] == 0.0
        assert stats["avg_wait_time"] == 0.0

    def test_global_pool_singleton(self) -> None:
        """Test that global pool is a singleton."""
        reset_global_pool()  # Ensure clean state

        pool1 = get_global_pool(max_connections=5)
        pool2 = get_global_pool(max_connections=10)  # Different args ignored

        assert pool1 is pool2
        assert pool1.max_connections == 5  # First initialization wins

        reset_global_pool()  # Clean up

    def test_reset_global_pool(self) -> None:
        """Test resetting the global pool."""
        pool1 = get_global_pool(max_connections=5)
        reset_global_pool()
        pool2 = get_global_pool(max_connections=10)

        assert pool1 is not pool2
        assert pool2.max_connections == 10
