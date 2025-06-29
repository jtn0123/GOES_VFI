"""Global process pool manager for coordinating CPU-bound operations.

This module provides a singleton process pool manager that ensures efficient
resource usage across the entire application by preventing multiple components
from creating their own process pools.
"""

import atexit
from collections.abc import Callable, Generator
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from contextlib import contextmanager
import os
import threading
from typing import Any, TypeVar

from goesvfi.core.base_manager import ConfigurableManager
from goesvfi.utils import log

LOGGER = log.get_logger(__name__)

T = TypeVar("T")


class GlobalProcessPool(ConfigurableManager):
    """Singleton process pool manager for application-wide coordination.

    This class ensures that only one process pool is active at a time,
    preventing resource exhaustion from multiple pools being created.
    """

    _instance: "GlobalProcessPool | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "GlobalProcessPool":
        """Ensure singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        """Initialize the global process pool manager."""
        # Skip if already initialized (singleton)
        if hasattr(self, "_initialized") and self._initialized:
            return

        # Default configuration
        default_config = {
            "max_workers": min(4, (os.cpu_count() or 1)),
            "max_tasks_per_child": 100,  # Restart workers periodically
            "initializer": None,
            "initargs": (),
            "auto_scale": True,
            "min_workers": 1,
            "scale_threshold": 0.8,  # Scale up when 80% busy
        }

        super().__init__("GlobalProcessPool", default_config=default_config)

        self._executor: ProcessPoolExecutor | None = None
        self._active_futures: set[Future] = set()
        self._usage_stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "current_workers": 0,
        }

        # Register cleanup on exit
        atexit.register(self._cleanup_on_exit)

        self._initialized = True
        self.log_info("Global process pool manager initialized")

    def _do_initialize(self) -> None:
        """Perform actual initialization."""
        if self._executor is None:
            max_workers = self.get_config("max_workers")
            max_tasks_per_child = self.get_config("max_tasks_per_child")

            # Create the process pool
            self._executor = ProcessPoolExecutor(
                max_workers=max_workers,
                max_tasks_per_child=max_tasks_per_child,
                initializer=self.get_config("initializer"),
                initargs=self.get_config("initargs"),
            )

            self._usage_stats["current_workers"] = max_workers
            self.log_info("Created process pool with %d workers", max_workers)

    def _do_cleanup(self) -> None:
        """Perform actual cleanup."""
        if self._executor:
            # Cancel pending futures
            for future in list(self._active_futures):
                if not future.done():
                    future.cancel()

            # Shutdown the executor
            self._executor.shutdown(wait=True, cancel_futures=True)
            self._executor = None

            self._active_futures.clear()
            self._usage_stats["current_workers"] = 0

            self.log_info("Process pool shut down")

    def _cleanup_on_exit(self) -> None:
        """Cleanup handler for program exit."""
        try:
            self.cleanup()
        except Exception:
            pass  # Suppress errors during exit

    def submit(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> Future[T]:
        """Submit a function to be executed in the process pool.

        Args:
            fn: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Future object representing the execution
        """
        if not self._is_initialized:
            self.initialize()

        if self._executor is None:
            msg = "Process pool not available"
            raise RuntimeError(msg)

        # Submit the task
        future = self._executor.submit(fn, *args, **kwargs)

        # Track the future
        self._active_futures.add(future)
        self._usage_stats["total_tasks"] += 1

        # Clean up completed futures
        self._cleanup_completed_futures()

        # Auto-scale if enabled
        if self.get_config("auto_scale"):
            self._check_scaling()

        # Add completion callback
        future.add_done_callback(self._on_task_complete)

        return future

    def map(
        self, fn: Callable[..., T], *iterables: Any, timeout: float | None = None, chunksize: int = 1
    ) -> Generator[T]:
        """Map a function across iterables using the process pool.

        Args:
            fn: Function to map
            *iterables: Iterables to map over
            timeout: Timeout for each result
            chunksize: Size of chunks for processing

        Yields:
            Results from the mapped function
        """
        if not self._is_initialized:
            self.initialize()

        if self._executor is None:
            msg = "Process pool not available"
            raise RuntimeError(msg)

        # Track task count
        iterable_len = len(list(zip(*iterables, strict=False)))
        self._usage_stats["total_tasks"] += iterable_len

        # Use executor.map
        try:
            for result in self._executor.map(fn, *iterables, timeout=timeout, chunksize=chunksize):
                self._usage_stats["completed_tasks"] += 1
                yield result
        except Exception:
            self._usage_stats["failed_tasks"] += 1
            raise

    def _on_task_complete(self, future: Future) -> None:
        """Callback when a task completes."""
        try:
            if future.exception() is not None:
                self._usage_stats["failed_tasks"] += 1
            else:
                self._usage_stats["completed_tasks"] += 1
        except Exception:
            self._usage_stats["failed_tasks"] += 1

        # Remove from active set
        self._active_futures.discard(future)

    def _cleanup_completed_futures(self) -> None:
        """Remove completed futures from tracking."""
        completed = {f for f in self._active_futures if f.done()}
        self._active_futures -= completed

    def _check_scaling(self) -> None:
        """Check if pool needs scaling (placeholder for future enhancement)."""
        # Calculate usage
        if self._executor and self._executor._max_workers:
            active_count = len(self._active_futures)
            max_workers = self._executor._max_workers
            usage_ratio = active_count / max_workers

            if usage_ratio > self.get_config("scale_threshold"):
                self.log_debug("High process pool usage: %.1f%%", usage_ratio * 100)
                # Future: Implement dynamic scaling

    def get_stats(self) -> dict[str, Any]:
        """Get usage statistics.

        Returns:
            Dictionary of usage statistics
        """
        stats = self._usage_stats.copy()
        stats["active_tasks"] = len(self._active_futures)
        stats["success_rate"] = (
            (stats["completed_tasks"] / stats["total_tasks"] * 100) if stats["total_tasks"] > 0 else 0
        )
        return stats

    def wait_for_all(self, timeout: float | None = None) -> None:
        """Wait for all active tasks to complete.

        Args:
            timeout: Maximum time to wait
        """
        if self._active_futures:
            self.log_info("Waiting for %d active tasks", len(self._active_futures))

            # Wait for completion
            _completed, pending = as_completed(self._active_futures, timeout=timeout)

            if pending:
                self.log_warning("Timed out waiting for %d tasks", len(pending))

    @contextmanager
    def batch_context(self, max_concurrent: int | None = None) -> Generator[None]:
        """Context manager for batch processing with concurrency control.

        Args:
            max_concurrent: Maximum concurrent tasks (None for no limit)

        Yields:
            None
        """
        if max_concurrent:
            # Store original max_workers
            original_max = self.get_config("max_workers")

            # Temporarily limit workers
            self.set_config("max_workers", min(max_concurrent, original_max))

            # Recreate pool with new size
            self.cleanup()
            self.initialize()

        try:
            yield
        finally:
            if max_concurrent:
                # Restore original configuration
                self.set_config("max_workers", original_max)
                self.cleanup()
                self.initialize()


# Module-level convenience functions

_global_pool: GlobalProcessPool | None = None


def get_global_process_pool() -> GlobalProcessPool:
    """Get the global process pool instance.

    Returns:
        GlobalProcessPool singleton instance
    """
    global _global_pool
    if _global_pool is None:
        _global_pool = GlobalProcessPool()
    return _global_pool


def submit_to_pool[T](fn: Callable[..., T], *args: Any, **kwargs: Any) -> Future[T]:
    """Submit a task to the global process pool.

    Args:
        fn: Function to execute
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Future for the task
    """
    pool = get_global_process_pool()
    return pool.submit(fn, *args, **kwargs)


def map_in_pool[T](fn: Callable[..., T], *iterables: Any, timeout: float | None = None, chunksize: int = 1) -> list[T]:
    """Map a function using the global process pool.

    Args:
        fn: Function to map
        *iterables: Iterables to map over
        timeout: Timeout for results
        chunksize: Chunk size for processing

    Returns:
        List of results
    """
    pool = get_global_process_pool()
    return list(pool.map(fn, *iterables, timeout=timeout, chunksize=chunksize))


@contextmanager
def process_pool_context(max_workers: int | None = None) -> Generator[GlobalProcessPool]:
    """Context manager for using the global process pool.

    Args:
        max_workers: Temporary worker limit

    Yields:
        GlobalProcessPool instance
    """
    pool = get_global_process_pool()

    if max_workers:
        with pool.batch_context(max_workers):
            yield pool
    else:
        yield pool
