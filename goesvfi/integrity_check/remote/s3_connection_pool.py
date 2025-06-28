"""S3 connection pooling for improved performance and resource management.

This module provides a connection pool for S3 clients to reduce the overhead
of creating new connections and improve performance for concurrent operations.
"""

import asyncio
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import time
from typing import Any

import aioboto3
from botocore import UNSIGNED
from botocore.config import Config

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)

# Type alias for S3 client
S3ClientType = Any  # aioboto3 doesn't expose concrete types


class S3ConnectionPool:
    """Connection pool for S3 clients with automatic lifecycle management."""

    def __init__(
        self,
        max_connections: int = 10,
        region: str = "us-east-1",
        connect_timeout: int = 10,
        read_timeout: int = 60,
        session_kwargs: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the S3 connection pool.

        Args:
            max_connections: Maximum number of connections in the pool
            region: AWS region for S3 buckets
            connect_timeout: Connection timeout in seconds
            read_timeout: Read timeout in seconds
            session_kwargs: Additional kwargs for aioboto3.Session
        """
        self.max_connections = max_connections
        self.region = region
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.session_kwargs = session_kwargs or {}

        # Pool data structures
        self._available_connections: deque[tuple[S3ClientType, float]] = deque()
        self._in_use_connections: set[S3ClientType] = set()
        self._lock = asyncio.Lock()

        # Statistics
        self._stats = {
            "connections_created": 0,
            "connections_reused": 0,
            "connections_closed": 0,
            "wait_time_total": 0.0,
            "pool_hits": 0,
            "pool_misses": 0,
        }

        # Connection configuration
        self._s3_config = Config(
            signature_version=UNSIGNED,  # Public NOAA buckets
            connect_timeout=self.connect_timeout,
            read_timeout=self.read_timeout,
            retries={"max_attempts": 2},
            region_name=self.region,
        )

        LOGGER.info(
            "Initialized S3 connection pool: max_connections=%d, region=%s",
            self.max_connections, self.region
        )

    async def _create_connection(self) -> S3ClientType:
        """Create a new S3 client connection.

        Returns:
            New S3 client instance

        Raises:
            Exception: If connection creation fails
        """
        try:
            session = aioboto3.Session(**self.session_kwargs)
            client_context = session.client("s3", config=self._s3_config)
            client = await client_context.__aenter__()

            self._stats["connections_created"] += 1
            LOGGER.debug(
                "Created new S3 connection (total created: %d)",
                self._stats["connections_created"]
            )

            return client

        except Exception as e:
            LOGGER.exception("Failed to create S3 connection: %s", e)
            raise

    async def _close_connection(self, client: S3ClientType) -> None:
        """Close an S3 client connection.

        Args:
            client: S3 client to close
        """
        try:
            if hasattr(client, "__aexit__"):
                await client.__aexit__(None, None, None)
            elif hasattr(client, "close"):
                await client.close()

            self._stats["connections_closed"] += 1
            LOGGER.debug(
                "Closed S3 connection (total closed: %d)",
                self._stats["connections_closed"]
            )

        except Exception as e:
            LOGGER.warning("Error closing S3 connection: %s", e)

    async def _check_connection_health(self, client: S3ClientType) -> bool:
        """Check if a connection is still healthy.

        Args:
            client: S3 client to check

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Simple health check - list buckets with max 1 result
            # This is a lightweight operation that verifies connectivity
            await client.list_buckets(MaxBuckets=1)
            return True
        except Exception as e:
            LOGGER.debug("Connection health check failed: %s", e)
            return False

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[S3ClientType]:
        """Acquire a connection from the pool.

        Yields:
            S3 client instance

        Raises:
            Exception: If unable to acquire a connection
        """
        start_time = time.time()
        client = None

        try:
            async with self._lock:
                # Try to get an available connection
                while self._available_connections:
                    client, created_time = self._available_connections.popleft()

                    # Check connection age (reuse connections for up to 5 minutes)
                    age = time.time() - created_time
                    if age < 300:  # 5 minutes
                        # Connection is fresh enough
                        self._in_use_connections.add(client)
                        self._stats["connections_reused"] += 1
                        self._stats["pool_hits"] += 1

                        LOGGER.debug(
                            "Reused connection from pool (age: %.1fs, pool size: %d)",
                            age, len(self._available_connections)
                        )
                        break
                    else:
                        # Connection too old, close it
                        await self._close_connection(client)
                        client = None

                # If no connection available and we can create more
                if client is None:
                    current_total = len(self._available_connections) + len(self._in_use_connections)
                    if current_total < self.max_connections:
                        client = await self._create_connection()
                        self._in_use_connections.add(client)
                        self._stats["pool_misses"] += 1
                    else:
                        # Pool is full, need to wait
                        LOGGER.warning(
                            "Connection pool full (%d connections), waiting...",
                            self.max_connections
                        )
                        # In a real implementation, we'd wait for a connection
                        # For now, create a new one anyway
                        client = await self._create_connection()
                        self._in_use_connections.add(client)

            # Track wait time
            wait_time = time.time() - start_time
            self._stats["wait_time_total"] += wait_time

            # Yield the connection
            yield client

        finally:
            # Return connection to pool
            if client is not None:
                async with self._lock:
                    self._in_use_connections.discard(client)

                    # Check if connection is still healthy before returning to pool
                    if await self._check_connection_health(client):
                        self._available_connections.append((client, time.time()))
                        LOGGER.debug(
                            "Returned connection to pool (pool size: %d)",
                            len(self._available_connections)
                        )
                    else:
                        # Connection unhealthy, close it
                        await self._close_connection(client)
                        LOGGER.debug("Closed unhealthy connection instead of returning to pool")

    async def close_all(self) -> None:
        """Close all connections in the pool."""
        async with self._lock:
            # Close available connections
            while self._available_connections:
                client, _ = self._available_connections.popleft()
                await self._close_connection(client)

            # Note: in-use connections should be closed by their users
            if self._in_use_connections:
                LOGGER.warning(
                    "Closing pool with %d connections still in use",
                    len(self._in_use_connections)
                )

        LOGGER.info("Closed all connections in pool")

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics.

        Returns:
            Dictionary of pool statistics
        """
        stats = self._stats.copy()
        stats.update({
            "available_connections": len(self._available_connections),
            "in_use_connections": len(self._in_use_connections),
            "total_connections": len(self._available_connections) + len(self._in_use_connections),
            "max_connections": self.max_connections,
        })

        # Calculate derived stats
        total_requests = stats["pool_hits"] + stats["pool_misses"]
        if total_requests > 0:
            stats["hit_rate"] = stats["pool_hits"] / total_requests
            stats["avg_wait_time"] = stats["wait_time_total"] / total_requests
        else:
            stats["hit_rate"] = 0.0
            stats["avg_wait_time"] = 0.0

        return stats

    def log_stats(self) -> None:
        """Log current pool statistics."""
        stats = self.get_stats()
        LOGGER.info(
            "S3 Pool Stats: %d/%d connections (%.1f%% hit rate, %.3fs avg wait)",
            stats["total_connections"],
            stats["max_connections"],
            stats["hit_rate"] * 100,
            stats["avg_wait_time"]
        )


# Global connection pool instance
_global_pool: S3ConnectionPool | None = None


def get_global_pool(**kwargs: Any) -> S3ConnectionPool:
    """Get or create the global S3 connection pool.

    Args:
        **kwargs: Arguments for S3ConnectionPool if creating new instance

    Returns:
        Global S3ConnectionPool instance
    """
    global _global_pool
    if _global_pool is None:
        _global_pool = S3ConnectionPool(**kwargs)
    return _global_pool


def reset_global_pool() -> None:
    """Reset the global connection pool (mainly for testing)."""
    global _global_pool
    _global_pool = None
