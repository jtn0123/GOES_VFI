"""Tests for the global process pool manager."""

from concurrent.futures import Future
import contextlib
import time
from typing import Any
import unittest
from unittest.mock import patch

import pytest

from goesvfi.core.global_process_pool import (
    GlobalProcessPool,
    get_global_process_pool,
    map_in_pool,
    process_pool_context,
    submit_to_pool,
)


def simple_task(x: int) -> int:
    """Simple test task.

    Returns:
        int: Input multiplied by 2.
    """
    return x * 2


def slow_task(x: int, delay: float = 0.1) -> int:
    """Task with delay for testing.

    Returns:
        int: Input multiplied by 2 after delay.
    """
    time.sleep(delay)
    return x * 2


def failing_task(x: int) -> int:
    """Task that always fails.

    Raises:
        ValueError: Always raised with input value.
    """
    msg = f"Task failed with input {x}"
    raise ValueError(msg)


class TestGlobalProcessPool(unittest.TestCase):
    """Test GlobalProcessPool functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Reset singleton
        GlobalProcessPool._instance = None  # noqa: SLF001
        self.pool = None

    def tearDown(self) -> None:
        """Clean up after tests."""
        # Ensure pool is cleaned up
        if self.pool:
            self.pool.cleanup()

        # Reset singleton
        GlobalProcessPool._instance = None  # noqa: SLF001

    def test_singleton_pattern(self) -> None:
        """Test that GlobalProcessPool is a singleton."""
        pool1 = GlobalProcessPool()
        pool2 = GlobalProcessPool()
        pool3 = get_global_process_pool()

        assert pool1 is pool2
        assert pool2 is pool3

        # Store for cleanup
        self.pool = pool1

    def test_inheritance_from_base_manager(self) -> None:
        """Test proper inheritance from ConfigurableManager."""
        pool = GlobalProcessPool()
        self.pool = pool

        # Check base class functionality
        assert pool.name == "GlobalProcessPool"
        assert pool._config is not None  # noqa: SLF001
        assert pool._logger is not None  # noqa: SLF001

        # Check default configuration
        assert pool.get_config("max_workers") >= 1
        assert pool.get_config("max_tasks_per_child") == 100
        assert pool.get_config("auto_scale")

    def test_initialization_lifecycle(self) -> None:
        """Test proper initialization and lifecycle."""
        pool = GlobalProcessPool()
        self.pool = pool

        # Should not have executor before initialization
        assert pool._executor is None  # noqa: SLF001

        # Initialize
        pool.initialize()
        assert pool._is_initialized  # noqa: SLF001
        assert pool._executor is not None  # noqa: SLF001

        # Double initialization should be safe
        pool.initialize()
        assert pool._is_initialized  # noqa: SLF001

    def test_submit_task(self) -> None:
        """Test submitting tasks to the pool."""
        pool = get_global_process_pool()
        self.pool = pool

        # Submit a simple task
        future = pool.submit(simple_task, 5)
        assert isinstance(future, Future)

        # Get result
        result = future.result(timeout=2)
        assert result == 10

        # Check stats
        stats = pool.get_stats()
        assert stats["total_tasks"] >= 1
        assert stats["completed_tasks"] >= 1

    def test_map_function(self) -> None:
        """Test mapping function over iterables."""
        pool = get_global_process_pool()
        self.pool = pool

        # Map over range
        inputs = range(5)
        results = list(pool.map(simple_task, inputs))

        assert results == [0, 2, 4, 6, 8]

        # Check stats
        stats = pool.get_stats()
        assert stats["total_tasks"] >= 5

    def test_error_handling(self) -> None:
        """Test error handling in tasks."""
        pool = get_global_process_pool()
        self.pool = pool

        # Submit failing task
        future = pool.submit(failing_task, 5)

        # Should raise exception
        with pytest.raises(ValueError, match="Task failed with input 42"):
            future.result(timeout=2)

        # Check stats
        stats = pool.get_stats()
        assert stats["failed_tasks"] >= 1

    def test_convenience_functions(self) -> None:
        """Test module-level convenience functions."""
        # Test submit_to_pool
        future = submit_to_pool(simple_task, 10)
        assert future.result(timeout=2) == 20

        # Test map_in_pool
        results = map_in_pool(simple_task, [1, 2, 3])
        assert results == [2, 4, 6]

        # Store pool for cleanup
        self.pool = get_global_process_pool()

    def test_batch_context(self) -> None:
        """Test batch context manager."""
        pool = get_global_process_pool()
        self.pool = pool

        # Original config
        original_max = pool.get_config("max_workers")

        # Use batch context with limited workers
        with pool.batch_context(max_concurrent=2):
            # Should have limited workers
            assert pool.get_config("max_workers") == min(2, original_max)

            # Submit tasks
            futures = [pool.submit(simple_task, i) for i in range(4)]
            results = [f.result(timeout=2) for f in futures]
            assert results == [0, 2, 4, 6]

        # Should restore original config
        assert pool.get_config("max_workers") == original_max

    def test_process_pool_context(self) -> None:
        """Test process pool context manager."""
        with process_pool_context() as pool:
            assert isinstance(pool, GlobalProcessPool)

            # Submit task
            future = pool.submit(simple_task, 7)
            assert future.result(timeout=2) == 14

        # Store for cleanup
        self.pool = pool

    def test_wait_for_all(self) -> None:
        """Test waiting for all tasks."""
        pool = get_global_process_pool()
        self.pool = pool

        # Submit multiple slow tasks
        futures = [pool.submit(slow_task, i, 0.1) for i in range(3)]

        # Wait for all
        pool.wait_for_all(timeout=2)

        # All should be done
        for future in futures:
            assert future.done()

    def test_cleanup(self) -> None:  # noqa: PLR6301
        """Test proper cleanup."""
        pool = GlobalProcessPool()
        pool.initialize()

        # Submit some tasks
        [pool.submit(simple_task, i) for i in range(3)]

        # Cleanup
        pool.cleanup()

        # Should not have executor
        assert pool._executor is None  # noqa: SLF001
        assert len(pool._active_futures) == 0  # noqa: SLF001
        assert not pool._is_initialized  # noqa: SLF001

    def test_stats_tracking(self) -> None:
        """Test statistics tracking."""
        pool = get_global_process_pool()
        self.pool = pool

        # Reset stats
        pool._usage_stats = {  # noqa: SLF001
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "current_workers": pool.get_config("max_workers"),
        }

        # Submit mix of tasks
        futures = []
        futures.extend((pool.submit(simple_task, 1), pool.submit(simple_task, 2), pool.submit(failing_task, 3)))

        # Wait for completion
        for future in futures:
            with contextlib.suppress(Exception):
                future.result(timeout=2)

        # Check stats
        stats = pool.get_stats()
        assert stats["total_tasks"] == 3
        assert stats["completed_tasks"] == 2
        assert stats["failed_tasks"] == 1
        assert abs(stats["success_rate"] - 66.67) < 0.1

    def test_configuration_update(self) -> None:
        """Test dynamic configuration updates."""
        pool = GlobalProcessPool()
        self.pool = pool

        # Update configuration
        pool.set_config("max_tasks_per_child", 50)
        pool.set_config("auto_scale", new=False)

        assert pool.get_config("max_tasks_per_child") == 50
        assert not pool.get_config("auto_scale")

    @patch("os.cpu_count")
    def test_default_worker_calculation(self, mock_cpu_count: Any) -> None:
        """Test default worker count calculation."""
        mock_cpu_count.return_value = 8

        pool = GlobalProcessPool()
        self.pool = pool

        # Should be min(4, cpu_count)
        assert pool.get_config("max_workers") == 4

    def test_chunksize_in_map(self) -> None:
        """Test chunksize parameter in map."""
        pool = get_global_process_pool()
        self.pool = pool

        # Large dataset
        inputs = range(100)

        # Map with larger chunksize
        results = list(pool.map(simple_task, inputs, chunksize=10))

        assert len(results) == 100
        assert results[0] == 0
        assert results[99] == 198


if __name__ == "__main__":
    unittest.main()
