"""Resource management for pipeline processing.

This module provides resource monitoring and limiting capabilities
to prevent system overload during video processing operations.
"""

import os
import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Generator, Optional, Union

from goesvfi.pipeline.exceptions import ResourceError
from goesvfi.utils import log
from goesvfi.utils.memory_manager import get_memory_monitor

LOGGER = log.get_logger(__name__)


@dataclass
class ResourceLimits:
    """Configuration for resource limits."""

    max_workers: int = 2
    max_memory_mb: int = 4096  # 4GB default
    max_cpu_percent: float = 80.0
    chunk_size_mb: int = 100
    warn_memory_percent: float = 75.0
    critical_memory_percent: float = 90.0


class ResourceManager:
    """Manages system resources for processing operations."""

    def __init__(self, limits: Optional[ResourceLimits] = None) -> None:
        """Initialize resource manager.

        Args:
            limits: Resource limits configuration
        """
        self.limits = limits or ResourceLimits()
        self.memory_monitor = get_memory_monitor()
        self._executors: Dict[str, Union[ProcessPoolExecutor, ThreadPoolExecutor]] = {}
        self._lock = threading.Lock()

        # Start memory monitoring
        self.memory_monitor.start_monitoring(interval=2.0)
        self.memory_monitor.add_callback(self._memory_callback)

    def _memory_callback(self, stats: Any) -> None:
        """Handle memory status updates."""
        if stats.percent_used > self.limits.critical_memory_percent:
            LOGGER.critical(
                "Memory usage critical: %s%% (limit: %s%%)",
                round(stats.percent_used, 1),
                self.limits.critical_memory_percent,
            )
        elif stats.percent_used > self.limits.warn_memory_percent:
            LOGGER.warning(
                "Memory usage high: %s%% (warning at: %s%%)",
                round(stats.percent_used, 1),
                self.limits.warn_memory_percent,
            )

    def check_resources(self, required_memory_mb: int = 0) -> None:
        """Check if resources are available for operation.

        Args:
            required_memory_mb: Required memory in MB

        Raises:
            ResourceError: If resources are insufficient
        """
        stats = self.memory_monitor.get_memory_stats()

        # Check memory availability
        if required_memory_mb > 0:
            if stats.available_mb < required_memory_mb:
                raise ResourceError(
                    f"Insufficient memory: {stats.available_mb}MB available, "
                    f"{required_memory_mb}MB required",
                    resource_type="memory",
                )

        # Check if we're over the critical threshold
        if stats.percent_used > self.limits.critical_memory_percent:
            raise ResourceError(
                f"Memory usage too high: {stats.percent_used:.1f}% "
                f"(limit: {self.limits.critical_memory_percent}%)",
                resource_type="memory",
            )

    def get_optimal_workers(self) -> int:
        """Calculate optimal number of workers based on available resources.

        Returns:
            Optimal worker count
        """
        # Get CPU count
        cpu_count = os.cpu_count() or 1

        # Get memory stats
        stats = self.memory_monitor.get_memory_stats()

        # Calculate based on available memory (assume 500MB per worker)
        memory_based_workers = max(1, stats.available_mb // 500)

        # Calculate based on CPU (leave some for system)
        cpu_based_workers = max(1, int(cpu_count * 0.75))

        # Take minimum of all constraints
        optimal = min(self.limits.max_workers, memory_based_workers, cpu_based_workers)

        LOGGER.info(
            "Optimal workers: %d (CPU: %d, Memory: %d, Limit: %d)",
            optimal,
            cpu_based_workers,
            memory_based_workers,
            self.limits.max_workers,
        )

        return optimal

    @contextmanager
    def process_executor(
        self, max_workers: Optional[int] = None, executor_id: str = "default"
    ) -> Generator[ProcessPoolExecutor, None, None]:
        """Context manager for ProcessPoolExecutor with resource limits.

        Args:
            max_workers: Maximum workers (None for optimal)
            executor_id: Unique ID for this executor

        Yields:
            ProcessPoolExecutor instance
        """
        if max_workers is None:
            max_workers = self.get_optimal_workers()
        else:
            max_workers = min(max_workers, self.limits.max_workers)

        # Check resources before creating executor
        self.check_resources()

        executor = ProcessPoolExecutor(max_workers=max_workers)

        with self._lock:
            self._executors[executor_id] = executor

        try:
            LOGGER.info("Created ProcessPoolExecutor with %d workers", max_workers)
            yield executor
        finally:
            executor.shutdown(wait=True)
            with self._lock:
                self._executors.pop(executor_id, None)
            LOGGER.info("Shut down ProcessPoolExecutor")

    @contextmanager
    def thread_executor(
        self, max_workers: Optional[int] = None, executor_id: str = "default"
    ) -> Generator[ThreadPoolExecutor, None, None]:
        """Context manager for ThreadPoolExecutor with resource limits.

        Args:
            max_workers: Maximum workers (None for optimal)
            executor_id: Unique ID for this executor

        Yields:
            ThreadPoolExecutor instance
        """
        if max_workers is None:
            max_workers = self.get_optimal_workers()
        else:
            max_workers = min(max_workers, self.limits.max_workers)

        # Check resources before creating executor
        self.check_resources()

        executor = ThreadPoolExecutor(max_workers=max_workers)

        with self._lock:
            self._executors[executor_id] = executor

        try:
            LOGGER.info("Created ThreadPoolExecutor with %d workers", max_workers)
            yield executor
        finally:
            executor.shutdown(wait=True)
            with self._lock:
                self._executors.pop(executor_id, None)
            LOGGER.info("Shut down ThreadPoolExecutor")

    def shutdown_all(self) -> None:
        """Shutdown all active executors."""
        with self._lock:
            for executor_id, executor in list(self._executors.items()):
                LOGGER.info("Shutting down executor: %s", executor_id)
                executor.shutdown(wait=False)
            self._executors.clear()

        # Stop memory monitoring
        self.memory_monitor.stop_monitoring()

    def get_chunk_size(self, total_size_mb: int, min_chunks: int = 2) -> int:
        """Calculate optimal chunk size based on available memory.

        Args:
            total_size_mb: Total size to process in MB
            min_chunks: Minimum number of chunks

        Returns:
            Chunk size in MB
        """
        stats = self.memory_monitor.get_memory_stats()

        # Use at most 25% of available memory per chunk
        max_chunk = stats.available_mb // 4

        # Apply configured limit
        max_chunk = min(max_chunk, self.limits.chunk_size_mb)

        # Ensure we have at least min_chunks
        chunk_size = min(max_chunk, total_size_mb // min_chunks)

        # But at least 10MB per chunk
        chunk_size = max(chunk_size, 10)

        LOGGER.debug(
            "Calculated chunk size: %dMB (total: %dMB, available: %dMB)",
            chunk_size,
            total_size_mb,
            stats.available_mb,
        )

        return chunk_size


# Global resource manager instance
_resource_manager: Optional[ResourceManager] = None


def get_resource_manager(limits: Optional[ResourceLimits] = None) -> ResourceManager:
    """Get the global resource manager instance.

    Args:
        limits: Resource limits (only used on first call)

    Returns:
        ResourceManager instance
    """
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager(limits)
    return _resource_manager


@contextmanager
def managed_executor(
    executor_type: str = "process",
    max_workers: Optional[int] = None,
    check_resources: bool = True,
) -> Generator[Union[ProcessPoolExecutor, ThreadPoolExecutor], None, None]:
    """Convenience context manager for resource-managed executors.

    Args:
        executor_type: "process" or "thread"
        max_workers: Maximum workers (None for optimal)
        check_resources: Whether to check resources first

    Yields:
        Executor instance
    """
    manager = get_resource_manager()

    if check_resources:
        manager.check_resources()

    if executor_type == "process":
        with manager.process_executor(max_workers) as executor:
            yield executor
    elif executor_type == "thread":
        with manager.thread_executor(max_workers) as executor:
            yield executor
    else:
        raise ValueError(f"Unknown executor type: {executor_type}")


def estimate_processing_memory(
    num_frames: int,
    frame_width: int,
    frame_height: int,
    channels: int = 3,
    dtype_bytes: int = 1,
) -> int:
    """Estimate memory requirements for processing frames.

    Args:
        num_frames: Number of frames
        frame_width: Frame width in pixels
        frame_height: Frame height in pixels
        channels: Number of color channels
        dtype_bytes: Bytes per pixel value

    Returns:
        Estimated memory requirement in MB
    """
    # Single frame size
    frame_size = frame_width * frame_height * channels * dtype_bytes

    # Account for input, output, and working memory (3x)
    total_bytes = num_frames * frame_size * 3

    # Convert to MB and add 20% buffer
    total_mb = int((total_bytes / (1024 * 1024)) * 1.2)

    return total_mb
