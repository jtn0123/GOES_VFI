"""Memory management utilities for GOES_VFI.

This module provides memory monitoring, optimization, and management capabilities
to prevent out-of-memory errors and optimize performance.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import gc
import threading
import time
from typing import Any

import numpy as np

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)

# Try to import psutil for memory monitoring
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    LOGGER.warning("psutil not available - memory monitoring will be limited")


@dataclass
class MemoryStats:
    """Container for memory statistics."""

    total_mb: int = 0
    available_mb: int = 0
    used_mb: int = 0
    percent_used: float = 0.0
    process_mb: int = 0
    process_percent: float = 0.0

    @property
    def is_low_memory(self) -> bool:
        """Check if memory is running low."""
        return self.available_mb < 500 or self.percent_used > 85

    @property
    def is_critical_memory(self) -> bool:
        """Check if memory is critically low."""
        return self.available_mb < 200 or self.percent_used > 95


class MemoryMonitor:
    """Monitor system and process memory usage."""

    def __init__(self, warning_threshold_mb: int = 500, critical_threshold_mb: int = 200) -> None:
        """Initialize memory monitor.

        Args:
            warning_threshold_mb: Available memory threshold for warnings
            critical_threshold_mb: Available memory threshold for critical alerts
        """
        self.warning_threshold_mb = warning_threshold_mb
        self.critical_threshold_mb = critical_threshold_mb
        self._monitoring = False
        self._monitor_thread: threading.Thread | None = None
        self._callbacks: list[Callable[[MemoryStats], None]] = []

    @staticmethod
    def get_memory_stats() -> MemoryStats:
        """Get current memory statistics.

        Returns:
            MemoryStats object with current memory information
        """
        stats = MemoryStats()

        if PSUTIL_AVAILABLE:
            # System memory
            vm = psutil.virtual_memory()
            stats.total_mb = vm.total // (1024 * 1024)
            stats.available_mb = vm.available // (1024 * 1024)
            stats.used_mb = vm.used // (1024 * 1024)
            stats.percent_used = vm.percent

            # Process memory
            try:
                process = psutil.Process()
                process_info = process.memory_info()
                stats.process_mb = process_info.rss // (1024 * 1024)
                stats.process_percent = process.memory_percent()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        else:
            # Fallback - try to get basic info
            try:
                import resource

                usage = resource.getrusage(resource.RUSAGE_SELF)
                stats.process_mb = usage.ru_maxrss // 1024  # Convert KB to MB
            except ImportError:
                pass

        return stats

    def start_monitoring(self, interval: float = 5.0) -> None:
        """Start background memory monitoring.

        Args:
            interval: Check interval in seconds
        """
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, args=(interval,), daemon=True)
        self._monitor_thread.start()
        LOGGER.info("Started memory monitoring with %ss interval", interval)

    def stop_monitoring(self) -> None:
        """Stop background memory monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        LOGGER.info("Stopped memory monitoring")

    def add_callback(self, callback: Callable[[MemoryStats], None]) -> None:
        """Add a callback for memory status updates.

        Args:
            callback: Function to call with MemoryStats
        """
        self._callbacks.append(callback)

    def _monitor_loop(self, interval: float) -> None:
        """Background monitoring loop."""
        last_warning_time = 0.0

        while self._monitoring:
            try:
                stats = MemoryMonitor.get_memory_stats()

                # Check thresholds
                current_time = time.time()
                if stats.is_critical_memory:
                    if current_time - last_warning_time > 30:  # Warn every 30s max
                        LOGGER.critical(
                            "CRITICAL: Low memory! Available: %sMB (%s%% used)",
                            stats.available_mb,
                            round(stats.percent_used, 1),
                        )
                        last_warning_time = current_time
                elif stats.is_low_memory:
                    if current_time - last_warning_time > 60:  # Warn every 60s max
                        LOGGER.warning(
                            "Low memory warning: Available: %sMB (%s%% used)",
                            stats.available_mb,
                            round(stats.percent_used, 1),
                        )
                        last_warning_time = current_time

                # Call callbacks
                for callback in self._callbacks:
                    try:
                        callback(stats)
                    except Exception as e:
                        LOGGER.exception("Error in memory callback: %s", e)

                time.sleep(interval)

            except Exception as e:
                LOGGER.exception("Error in memory monitoring: %s", e)
                time.sleep(interval)


class MemoryOptimizer:
    """Optimize memory usage for large data processing."""

    def __init__(self) -> None:
        """Initialize memory optimizer."""
        self.monitor = MemoryMonitor()
        self._gc_threshold = 80  # Trigger GC when memory > 80%
        self._last_gc_time = 0.0
        self._gc_interval = 30.0  # Minimum seconds between GC runs

    @staticmethod
    def optimize_array_dtype(array: np.ndarray, preserve_range: bool = True) -> np.ndarray:
        """Optimize numpy array dtype to use less memory.

        Args:
            array: Input numpy array
            preserve_range: Whether to preserve the value range

        Returns:
            Optimized array with smaller dtype if possible
        """
        if array.dtype == np.float64:
            # Check if float32 is sufficient
            if preserve_range:
                min_val, max_val = array.min(), array.max()
                if min_val >= np.finfo(np.float32).min and max_val <= np.finfo(np.float32).max:
                    LOGGER.debug("Converting array from float64 to float32 (saves 50%% memory)")
                    return array.astype(np.float32)
            else:
                return array.astype(np.float32)

        if array.dtype == np.int64:
            # Check if smaller int type is sufficient
            min_val, max_val = array.min(), array.max()

            if min_val >= 0 and max_val <= 255:
                LOGGER.debug("Converting array from int64 to uint8 (saves 87.5%% memory)")
                return array.astype(np.uint8)
            if min_val >= -128 and max_val <= 127:
                LOGGER.debug("Converting array from int64 to int8 (saves 87.5%% memory)")
                return array.astype(np.int8)
            if min_val >= 0 and max_val <= 65535:
                LOGGER.debug("Converting array from int64 to uint16 (saves 75%% memory)")
                return array.astype(np.uint16)
            if min_val >= -32768 and max_val <= 32767:
                LOGGER.debug("Converting array from int64 to int16 (saves 75%% memory)")
                return array.astype(np.int16)
            if min_val >= -2147483648 and max_val <= 2147483647:
                LOGGER.debug("Converting array from int64 to int32 (saves 50%% memory)")
                return array.astype(np.int32)

        return array

    @staticmethod
    def chunk_large_array(array: np.ndarray, max_chunk_mb: int = 100) -> list[np.ndarray]:
        """Split large array into chunks for processing.

        Args:
            array: Large numpy array to chunk
            max_chunk_mb: Maximum chunk size in MB

        Returns:
            List of array chunks
        """
        array_mb = array.nbytes / (1024 * 1024)

        if array_mb <= max_chunk_mb:
            return [array]

        # Calculate number of chunks needed
        n_chunks = int(np.ceil(array_mb / max_chunk_mb))

        # Split along first axis
        chunk_size = len(array) // n_chunks
        chunks = []

        for i in range(n_chunks):
            start = i * chunk_size
            end = start + chunk_size if i < n_chunks - 1 else len(array)
            chunks.append(array[start:end])

        LOGGER.info(
            "Split %sMB array into %s chunks of ~%sMB each",
            round(array_mb, 1),
            n_chunks,
            max_chunk_mb,
        )

        return chunks

    def optimize_array_chunks(self, array: np.ndarray, max_chunk_mb: int = 100) -> Iterable[np.ndarray]:
        """Yield copies of array chunks to keep peak memory low.

        This method iterates over ``array`` in pieces and yields a copy of each
        chunk so the original array can be released after processing.  It also
        triggers garbage collection between chunks.

        Args:
            array: Large numpy array to process in chunks.
            max_chunk_mb: Maximum chunk size in megabytes.

        Yields:
            NumPy arrays containing contiguous chunks of ``array``.
        """
        chunk_size = max(1, max_chunk_mb * 1024 * 1024 // array.itemsize)
        for start in range(0, len(array), chunk_size):
            chunk = array[start : start + chunk_size].copy()
            yield chunk
            self.free_memory()

    def free_memory(self, force: bool = False) -> None:
        """Free memory by running garbage collection.

        Args:
            force: Force immediate GC regardless of thresholds
        """
        current_time = time.time()
        stats = MemoryMonitor.get_memory_stats()

        should_gc = (
            force or stats.percent_used > self._gc_threshold or (current_time - self._last_gc_time) > self._gc_interval
        )

        if should_gc:
            LOGGER.debug(
                "Running garbage collection (memory: %s%%)",
                round(stats.percent_used, 1),
            )
            gc.collect()
            self._last_gc_time = current_time

    def check_available_memory(self, required_mb: int) -> tuple[bool, str]:
        """Check if sufficient memory is available.

        Args:
            required_mb: Required memory in MB

        Returns:
            Tuple of (has_memory, message)
        """
        stats = MemoryMonitor.get_memory_stats()

        if stats.available_mb < required_mb:
            return False, (f"Insufficient memory: {stats.available_mb}MB available, {required_mb}MB required")

        if stats.available_mb < required_mb * 1.5:
            LOGGER.warning(
                "Low memory for operation: %sMB available, %sMB required",
                stats.available_mb,
                required_mb,
            )

        return True, "OK"


def estimate_memory_requirement(shape: tuple, dtype: np.dtype) -> int:
    """Estimate memory requirement for array.

    Args:
        shape: Array shape
        dtype: Array data type

    Returns:
        Estimated memory in MB
    """
    # Calculate number of elements
    n_elements = 1
    for dim in shape:
        n_elements *= dim

    # Get bytes per element
    if isinstance(dtype, type):
        dtype = np.dtype(dtype)
    bytes_per_element = dtype.itemsize

    # Calculate total bytes and convert to MB
    total_bytes = n_elements * bytes_per_element
    return int(np.ceil(total_bytes / (1024 * 1024)))


def log_memory_usage(context: str = "") -> None:
    """Log current memory usage.

    Args:
        context: Optional context string
    """
    monitor = MemoryMonitor()
    stats = MemoryMonitor.get_memory_stats()

    if context:
        LOGGER.info(
            "%s - Memory: %sMB used (%s%%), %sMB available",
            context,
            stats.used_mb,
            round(stats.percent_used, 1),
            stats.available_mb,
        )
    else:
        LOGGER.info(
            "Memory: %sMB used (%s%%), %sMB available",
            stats.used_mb,
            round(stats.percent_used, 1),
            stats.available_mb,
        )


# Global singleton monitor
_memory_monitor = None


def get_memory_monitor() -> MemoryMonitor:
    """Get the global memory monitor instance."""
    global _memory_monitor
    if _memory_monitor is None:
        _memory_monitor = MemoryMonitor()
    return _memory_monitor


class ObjectPool:
    """Object pool for reusing expensive objects."""

    def __init__(self, factory: Callable, max_size: int = 10) -> None:
        """Initialize object pool.

        Args:
            factory: Function to create new objects
            max_size: Maximum pool size
        """
        self.factory = factory
        self.max_size = max_size
        self.pool: list = []
        self._lock = threading.Lock()

    def acquire(self) -> Any:
        """Acquire an object from the pool."""
        with self._lock:
            if self.pool:
                return self.pool.pop()
            return self.factory()

    def release(self, obj: Any) -> None:
        """Release an object back to the pool."""
        with self._lock:
            if len(self.pool) < self.max_size:
                self.pool.append(obj)


class StreamingProcessor:
    """Process large data in streaming fashion."""

    def __init__(self, chunk_size_mb: int = 100) -> None:
        """Initialize streaming processor.

        Args:
            chunk_size_mb: Size of each chunk in MB
        """
        self.chunk_size_mb = chunk_size_mb
        self.optimizer = MemoryOptimizer()

    def process_array(self, array: np.ndarray, process_func: Callable) -> np.ndarray:
        """Process array in chunks.

        Args:
            array: Input array
            process_func: Function to process each chunk

        Returns:
            Processed array
        """
        results = []

        for chunk in self.optimizer.optimize_array_chunks(array, self.chunk_size_mb):
            result = process_func(chunk)
            results.append(result)

        del array
        self.optimizer.free_memory(force=True)

        return np.concatenate(results)

    @staticmethod
    def estimate_memory_usage(array_shape: tuple, dtype: np.dtype) -> MemoryStats:
        """Estimate memory usage for processing an array.

        Args:
            array_shape: Shape of the array
            dtype: Data type of the array

        Returns:
            MemoryStats with estimated usage
        """
        # Calculate array size
        num_elements = np.prod(array_shape)
        bytes_per_element = np.dtype(dtype).itemsize
        array_size_mb = (num_elements * bytes_per_element) / (1024 * 1024)

        # Get current memory stats
        monitor = get_memory_monitor()
        current_stats = MemoryMonitor.get_memory_stats()

        # Estimate if processing would fit in memory
        estimated_usage_mb = current_stats.used_mb + array_size_mb
        estimated_percent = (estimated_usage_mb / current_stats.total_mb) * 100

        return MemoryStats(
            total_mb=current_stats.total_mb,
            available_mb=current_stats.available_mb - array_size_mb,
            used_mb=estimated_usage_mb,
            percent_used=estimated_percent,
        )
