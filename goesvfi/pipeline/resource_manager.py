"""Resource management for pipeline processing.

This module provides resource monitoring and limiting capabilities
to prevent system overload during video processing operations.
"""

from collections.abc import Generator
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
import os
import threading
from typing import Any

from goesvfi.core.base_manager import ConfigurableManager
from goesvfi.core.global_process_pool import get_global_process_pool
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


class ResourceManager(ConfigurableManager):
    """Manages system resources for processing operations."""

    def __init__(self, limits: ResourceLimits | None = None) -> None:
        """Initialize resource manager.

        Args:
            limits: Resource limits configuration
        """
        self.limits = limits or ResourceLimits()

        # Convert limits to config dict for base class
        default_config = {
            "max_workers": self.limits.max_workers,
            "max_memory_mb": self.limits.max_memory_mb,
            "max_cpu_percent": self.limits.max_cpu_percent,
            "chunk_size_mb": self.limits.chunk_size_mb,
            "warn_memory_percent": self.limits.warn_memory_percent,
            "critical_memory_percent": self.limits.critical_memory_percent,
        }

        super().__init__("ResourceManager", default_config=default_config)

        self.memory_monitor = get_memory_monitor()
        self._executors: dict[str, ProcessPoolExecutor | ThreadPoolExecutor] = {}
        self._lock = threading.Lock()

        # Track resources for cleanup
        self._track_resource(self.memory_monitor)

    def _do_initialize(self) -> None:
        """Perform actual initialization."""
        # Start memory monitoring
        self.memory_monitor.start_monitoring(interval=2.0)
        self.memory_monitor.add_callback(self._memory_callback)
        self.log_info("Memory monitoring started")

    def _memory_callback(self, stats: Any) -> None:
        """Handle memory status updates."""
        critical_percent = float(self.get_config("critical_memory_percent", 90.0))
        warn_percent = float(self.get_config("warn_memory_percent", 75.0))

        if stats.percent_used > critical_percent:
            msg = f"Memory usage critical: {round(stats.percent_used, 1)}% (limit: {critical_percent}%)"
            self.log_error(msg)
            self.error_occurred.emit(msg)
        elif stats.percent_used > warn_percent:
            self.log_warning(
                "Memory usage high: %s%% (warning at: %s%%)",
                round(stats.percent_used, 1),
                warn_percent,
            )

    def check_resources(self, required_memory_mb: int | None = 0) -> None:
        """Check if resources are available for operation.

        Args:
            required_memory_mb: Required memory in MB

        Raises:
            ResourceError: If resources are insufficient
        """
        stats = self.memory_monitor.get_memory_stats()

        # Check memory availability
        if required_memory_mb is not None and required_memory_mb > 0 and stats.available_mb < required_memory_mb:
            msg = f"Insufficient memory: {stats.available_mb}MB available, {required_memory_mb}MB required"
            raise ResourceError(
                msg,
                resource_type="memory",
            )

        # Check if we're over the critical threshold
        critical_percent = float(self.get_config("critical_memory_percent", 90.0))
        if stats.percent_used > critical_percent:
            msg = f"Memory usage too high: {stats.percent_used:.1f}% (limit: {critical_percent}%)"
            raise ResourceError(
                msg,
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
        max_workers = int(self.get_config("max_workers", 2))
        optimal = min(max_workers, memory_based_workers, cpu_based_workers)

        self.log_info(
            "Optimal workers: %d (CPU: %d, Memory: %d, Limit: %d)",
            optimal,
            cpu_based_workers,
            memory_based_workers,
            max_workers,
        )

        return optimal

    @contextmanager
    def process_executor(
        self, max_workers: int | None = None, executor_id: str = "default"
    ) -> Generator[ProcessPoolExecutor]:
        """Context manager for ProcessPoolExecutor with resource limits.

        Args:
            max_workers: Maximum workers (None for optimal)
            executor_id: Unique ID for this executor

        Yields:
            ProcessPoolExecutor instance
        """
        max_workers_limit = int(self.get_config("max_workers", 2))
        max_workers = self.get_optimal_workers() if max_workers is None else min(max_workers, max_workers_limit)

        # Check resources before creating executor
        self.check_resources()

        executor = ProcessPoolExecutor(max_workers=max_workers)

        with self._lock:
            self._executors[executor_id] = executor

        try:
            self.log_info("Created ProcessPoolExecutor with %d workers", max_workers)
            yield executor
        finally:
            executor.shutdown(wait=True)
            with self._lock:
                self._executors.pop(executor_id, None)
            self.log_info("Shut down ProcessPoolExecutor")

    @contextmanager
    def thread_executor(
        self, max_workers: int | None = None, executor_id: str = "default"
    ) -> Generator[ThreadPoolExecutor]:
        """Context manager for ThreadPoolExecutor with resource limits.

        Args:
            max_workers: Maximum workers (None for optimal)
            executor_id: Unique ID for this executor

        Yields:
            ThreadPoolExecutor instance
        """
        max_workers_limit = int(self.get_config("max_workers", 2))
        max_workers = self.get_optimal_workers() if max_workers is None else min(max_workers, max_workers_limit)

        # Check resources before creating executor
        self.check_resources()

        executor = ThreadPoolExecutor(max_workers=max_workers)

        with self._lock:
            self._executors[executor_id] = executor

        try:
            self.log_info("Created ThreadPoolExecutor with %d workers", max_workers)
            yield executor
        finally:
            executor.shutdown(wait=True)
            with self._lock:
                self._executors.pop(executor_id, None)
            self.log_info("Shut down ThreadPoolExecutor")

    def _do_cleanup(self) -> None:
        """Perform actual cleanup."""
        # Shutdown all executors
        with self._lock:
            for executor_id, executor in list(self._executors.items()):
                self.log_info("Shutting down executor: %s", executor_id)
                executor.shutdown(wait=False)
            self._executors.clear()

        # Stop memory monitoring
        if self.memory_monitor:
            self.memory_monitor.stop_monitoring()
            self.log_info("Memory monitoring stopped")

    def shutdown_all(self) -> None:
        """Shutdown all active executors."""
        self.cleanup()

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
        chunk_size_mb = int(self.get_config("chunk_size_mb", 100))
        max_chunk = min(max_chunk, chunk_size_mb)

        # Ensure we have at least min_chunks
        chunk_size = min(max_chunk, total_size_mb // min_chunks)

        # But at least 10MB per chunk
        chunk_size = max(chunk_size, 10)

        self.log_debug(
            "Calculated chunk size: %dMB (total: %dMB, available: %dMB)",
            chunk_size,
            total_size_mb,
            stats.available_mb,
        )

        return chunk_size


# Global resource manager instance
_resource_manager: ResourceManager | None = None


def get_resource_manager(limits: ResourceLimits | None = None) -> ResourceManager:
    """Get the global resource manager instance.

    Args:
        limits: Resource limits (only used on first call)

    Returns:
        ResourceManager instance
    """
    global _resource_manager  # pylint: disable=global-statement
    if _resource_manager is None:
        _resource_manager = ResourceManager(limits)
    return _resource_manager


@contextmanager
def managed_executor(
    executor_type: str = "process",
    max_workers: int | None = None,
    check_resources: bool = True,
    use_global_pool: bool = True,
) -> Generator[ProcessPoolExecutor | ThreadPoolExecutor]:
    """Convenience context manager for resource-managed executors.

    Args:
        executor_type: "process" or "thread"
        max_workers: Maximum workers (None for optimal)
        check_resources: Whether to check resources first
        use_global_pool: Use global process pool for process executors

    Yields:
        Executor instance
    """
    manager = get_resource_manager()

    if check_resources:
        manager.check_resources()

    if executor_type == "process":
        if use_global_pool:
            # Use the global process pool instead of creating a new one
            global_pool = get_global_process_pool()
            global_pool.initialize()  # Ensure it's initialized
            with global_pool.batch_context(max_workers):
                # Return the global pool's executor
                if global_pool._executor is None:
                    msg = "Global process pool executor is not available"
                    raise RuntimeError(msg)
                yield global_pool._executor
        else:
            with manager.process_executor(max_workers) as executor:
                yield executor
    elif executor_type == "thread":
        with manager.thread_executor(max_workers) as executor:
            yield executor
    else:
        msg = f"Unknown executor type: {executor_type}"
        raise ValueError(msg)


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
    return int((total_bytes / (1024 * 1024)) * 1.2)
