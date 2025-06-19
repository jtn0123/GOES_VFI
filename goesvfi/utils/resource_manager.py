"""Resource Management for GOES_VFI application.

This module provides resource monitoring and limiting capabilities
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Union
import os
import resource
import time

import platform
import psutil
import signal
import threading

from goesvfi.utils import log

to prevent excessive memory usage and long-running processes.
"""

LOGGER = log.get_logger(__name__)

@dataclass
class ResourceLimits:
    """Configuration for resource limits."""
    max_memory_mb: Optional[int] = None  # Maximum memory usage in MB
    max_cpu_percent: Optional[float] = None  # Maximum CPU usage percentage
    max_processing_time_sec: Optional[int] = None  # Maximum processing time in seconds
    max_disk_usage_mb: Optional[int] = None  # Maximum disk usage in MB
    max_open_files: Optional[int] = None  # Maximum number of open files
    enable_swap_limit: bool = True  # Whether to include swap in memory calculations

@dataclass
class ResourceUsage:
    """Current resource usage statistics."""
    memory_mb: float
    memory_percent: float
    cpu_percent: float
    disk_usage_mb: float
    open_files: int
    swap_mb: float = 0.0
    processing_time_sec: float = 0.0

class ResourceLimitExceeded(Exception):
    """Raised when a resource limit is exceeded."""
    def __init__(self, resource_type: str, current: float, limit: float):
        self.resource_type = resource_type
        self.current = current
        self.limit = limit
        super().__init__(f"{resource_type} limit exceeded: {current} > {limit}")

class ResourceMonitor:
    """Monitors system resource usage and enforces limits."""

    def __init__(self, limits: ResourceLimits, check_interval: float = 1.0):
        """Initialize the resource monitor.

        Args:
            limits: Resource limits configuration
            check_interval: How often to check resources (seconds)
        """
        self.limits = limits
        self.check_interval = check_interval
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.start_time = time.time()
        self.callbacks: Dict[str, Callable[[ResourceUsage], None]] = {}
        self.process = psutil.Process()

    def add_callback(self, event: str, callback: Callable[[ResourceUsage], None]) -> None:
        """Add a callback for resource monitoring events.

        Args:
            event: Event type ('usage_update', 'limit_warning', 'limit_exceeded')
            callback: Function to call when event occurs
        """
        self.callbacks[event] = callback

    def start_monitoring(self) -> None:
        """Start continuous resource monitoring."""
        if self.monitoring:
            pass
            return

        self.monitoring = True
        self.start_time = time.time()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)  # pylint: disable=attribute-defined-outside-init
        self.monitor_thread.start()
        LOGGER.info("Resource monitoring started")

    def stop_monitoring(self) -> None:
        """Stop resource monitoring."""
        self.monitoring = False
        if self.monitor_thread:
            pass
            self.monitor_thread.join(timeout=2.0)
        LOGGER.info("Resource monitoring stopped")

    def get_current_usage(self) -> ResourceUsage:
        """Get current resource usage statistics."""
        try:
            # Memory usage
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            memory_percent = self.process.memory_percent()

            # CPU usage
            cpu_percent = self.process.cpu_percent()

            # Disk usage (temp directory)
            temp_dir = os.environ.get('TMPDIR', '/tmp')
            disk_usage = psutil.disk_usage(temp_dir)
            disk_usage_mb = (disk_usage.total - disk_usage.free) / (1024 * 1024)

            # Open files
            try:
                open_files = len(self.process.open_files())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
                open_files = 0

            # Swap usage
            swap_mb = 0.0
            if self.limits.enable_swap_limit:
                pass
                try:
                    swap_info = psutil.swap_memory()
                    swap_mb = swap_info.used / (1024 * 1024)
                except Exception:
                    pass
                    pass

            # Processing time
            processing_time_sec = time.time() - self.start_time

            return ResourceUsage(
            memory_mb=memory_mb,
            memory_percent=memory_percent,
            cpu_percent=cpu_percent,
            disk_usage_mb=disk_usage_mb,
            open_files=open_files,
            swap_mb=swap_mb,
            processing_time_sec=processing_time_sec
            )
        except Exception as e:
            pass
            LOGGER.error("Error getting resource usage: %s", e)
            return ResourceUsage(0, 0, 0, 0, 0)

    def check_limits(self, usage: ResourceUsage) -> Optional[ResourceLimitExceeded]:
        """Check if any resource limits are exceeded.

        Args:
            pass
            usage: Current resource usage

        Returns:
            ResourceLimitExceeded if any limit is exceeded, None otherwise
        """
        # Check memory limit
        if self.limits.max_memory_mb is not None:
            pass
            total_memory = usage.memory_mb
            if self.limits.enable_swap_limit:
                pass
                total_memory += usage.swap_mb
            if total_memory > self.limits.max_memory_mb:
                pass
                return ResourceLimitExceeded("Memory", total_memory, self.limits.max_memory_mb)

        # Check CPU limit
        if self.limits.max_cpu_percent is not None:
            pass
            if usage.cpu_percent > self.limits.max_cpu_percent:
                pass
                return ResourceLimitExceeded("CPU", usage.cpu_percent, self.limits.max_cpu_percent)

        # Check processing time limit
        if self.limits.max_processing_time_sec is not None:
            pass
            if usage.processing_time_sec > self.limits.max_processing_time_sec:
                pass
                return ResourceLimitExceeded("Processing time",)
                usage.processing_time_sec,
                self.limits.max_processing_time_sec)

        # Check disk usage limit
        if self.limits.max_disk_usage_mb is not None:
            pass
            if usage.disk_usage_mb > self.limits.max_disk_usage_mb:
                pass
                return ResourceLimitExceeded("Disk usage",)
                usage.disk_usage_mb,
                self.limits.max_disk_usage_mb)

        # Check open files limit
        if self.limits.max_open_files is not None:
            pass
            if usage.open_files > self.limits.max_open_files:
                pass
                return ResourceLimitExceeded("Open files",)
                usage.open_files,
                self.limits.max_open_files)

        return None

    def _monitor_loop(self) -> None:
        """Main monitoring loop (runs in separate thread)."""
        warning_thresholds = {
        'memory': 0.8,
        'cpu': 0.8,
        'processing_time': 0.8,
        'disk': 0.8,
        'open_files': 0.8
        }

        while self.monitoring:
            try:
                usage = self.get_current_usage()

                # Call usage update callback
                if 'usage_update' in self.callbacks:
                    pass
                    self.callbacks['usage_update'](usage)

                # Check for warnings (80% of limit)
                self._check_warnings(usage, warning_thresholds)

                # Check for hard limits
                limit_exceeded = self.check_limits(usage)
                if limit_exceeded:
                    pass
                    LOGGER.error("Resource limit exceeded: %s", limit_exceeded)
                    if 'limit_exceeded' in self.callbacks:
                        pass
                        self.callbacks['limit_exceeded'](usage)
                    # Don't break the loop - let the callback handle the response

                time.sleep(self.check_interval)

            except Exception as e:
                pass
                LOGGER.error("Error in resource monitoring loop: %s", e)
                time.sleep(self.check_interval)

    def _check_warnings(self, usage: ResourceUsage, thresholds: Dict[str, float]) -> None:
        """Check for warning conditions (approaching limits)."""
        warnings = []

        # Memory warning
        if self.limits.max_memory_mb is not None:
            pass
            total_memory = usage.memory_mb
            if self.limits.enable_swap_limit:
                pass
                total_memory += usage.swap_mb
            if total_memory > self.limits.max_memory_mb * thresholds['memory']:
                pass
                warnings.append(f"Memory usage high: {total_memory:.1f}/{self.limits.max_memory_mb} MB")

        # CPU warning
        if self.limits.max_cpu_percent is not None:
            pass
            if usage.cpu_percent > self.limits.max_cpu_percent * thresholds['cpu']:
                pass
                warnings.append(f"CPU usage high: {usage.cpu_percent:.1f}/{self.limits.max_cpu_percent}%")

        # Processing time warning
        if self.limits.max_processing_time_sec is not None:
            pass
            if usage.processing_time_sec > self.limits.max_processing_time_sec * thresholds['processing_time']:
                pass
                warnings.append(f"Processing time high: {usage.processing_time_sec:.1f}/{self.limits.max_processing_time_sec}s")

        if warnings and 'limit_warning' in self.callbacks:
            pass
            self.callbacks['limit_warning'](usage)

def set_system_resource_limits(limits: ResourceLimits) -> None:
    """Set system-level resource limits using the resource module.

    Args:
        limits: Resource limits to apply
    """
    try:
        # Set memory limit (virtual memory)
        if limits.max_memory_mb is not None:
            pass
            memory_bytes = limits.max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
            LOGGER.info("Set virtual memory limit to %s MB", limits.max_memory_mb)

        # Set file descriptor limit
        if limits.max_open_files is not None:
            pass
            resource.setrlimit(resource.RLIMIT_NOFILE,)
            (limits.max_open_files,)
            limits.max_open_files))
            LOGGER.info("Set file descriptor limit to %s", limits.max_open_files)

        # Set CPU time limit (in seconds)
        if limits.max_processing_time_sec is not None:
            pass
            resource.setrlimit(resource.RLIMIT_CPU,)
            (limits.max_processing_time_sec,)
            limits.max_processing_time_sec))
            LOGGER.info("Set CPU time limit to %s seconds", limits.max_processing_time_sec)

    except Exception as e:
        pass
        LOGGER.warning("Could not set system resource limits: %s", e)

def get_system_resource_info() -> Dict[str, Any]:
    """Get information about system resources.

    Returns:
        Dictionary containing system resource information
    """
    try:
        # Memory info
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # CPU info
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()

        # Disk info
        disk = psutil.disk_usage('/')

        return {
        'memory': {
        'total_mb': memory.total / (1024 * 1024),
        'available_mb': memory.available / (1024 * 1024),
        'percent_used': memory.percent
        },
        'swap': {
        'total_mb': swap.total / (1024 * 1024),
        'used_mb': swap.used / (1024 * 1024),
        'percent_used': swap.percent
        },
        'cpu': {
        'count': cpu_count,
        'frequency_mhz': cpu_freq.current if cpu_freq else None,
        'max_frequency_mhz': cpu_freq.max if cpu_freq else None
        },
        'disk': {
        'total_gb': disk.total / (1024 * 1024 * 1024),
        'free_gb': disk.free / (1024 * 1024 * 1024),
        'percent_used': (disk.used / disk.total) * 100
        },
        'platform': {
        'system': platform.system(),
        'architecture': platform.architecture()[0],
        'processor': platform.processor()
        }
        }
    except Exception as e:
        pass
        LOGGER.error("Error getting system resource info: %s", e)
        return {}

class ResourceLimitedContext:
    """Context manager for applying resource limits during specific operations."""

    def __init__(self, limits: ResourceLimits, monitor: bool = True):
        """Initialize the context manager.

        Args:
            limits: Resource limits to apply
            monitor: Whether to start monitoring
        """
        self.limits = limits
        self.monitor_enabled = monitor
        self.monitor: Optional[ResourceMonitor] = None
        self.original_limits: Dict[int, tuple] = {}

    def __enter__(self) -> 'ResourceLimitedContext':
        """Enter the context and apply resource limits."""
        # Save original limits
        try:
            self.original_limits[resource.RLIMIT_AS] = resource.getrlimit(resource.RLIMIT_AS)
            self.original_limits[resource.RLIMIT_NOFILE] = resource.getrlimit(resource.RLIMIT_NOFILE)
            self.original_limits[resource.RLIMIT_CPU] = resource.getrlimit(resource.RLIMIT_CPU)
        except Exception as e:
            pass
            LOGGER.warning("Could not save original resource limits: %s", e)

        # Apply new limits
        set_system_resource_limits(self.limits)

        # Start monitoring if requested
        if self.monitor_enabled:
            pass
            self.monitor = ResourceMonitor(self.limits)
            self.monitor.start_monitoring()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context and restore original limits."""
        # Stop monitoring
        if self.monitor:
            pass
            self.monitor.stop_monitoring()

        # Restore original limits
        try:
            for limit_type, (soft, hard) in self.original_limits.items():
                resource.setrlimit(limit_type, (soft, hard))
        except Exception as e:
            pass
            LOGGER.warning("Could not restore original resource limits: %s", e)

    def get_monitor(self) -> Optional[ResourceMonitor]:
        """Get the resource monitor if monitoring is enabled."""
        return self.monitor
