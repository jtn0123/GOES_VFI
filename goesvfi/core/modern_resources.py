"""Modern resource management utilities for the GOES VFI codebase.

This module provides modern Python resource management patterns including
context managers, resource tracking, and automatic cleanup mechanisms.
"""

import asyncio
import atexit
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
import tempfile
import threading
from typing import Any, Protocol, TypeVar

from goesvfi.core.base_manager import BaseManager
from goesvfi.utils import log

LOGGER = log.get_logger(__name__)

T = TypeVar("T")


class ResourceProtocol(Protocol):
    """Protocol for resources that can be cleaned up."""

    def cleanup(self) -> None:
        """Clean up the resource."""
        ...


class AsyncResourceProtocol(Protocol):
    """Protocol for async resources that can be cleaned up."""

    async def cleanup(self) -> None:
        """Clean up the resource asynchronously."""
        ...


class ResourceTracker:
    """Thread-safe resource tracker for automatic cleanup."""

    def __init__(self, name: str = "default"):
        self.name = name
        self._resources: list[Any] = []
        self._lock = threading.Lock()
        self._cleanup_registered = False

    def track(self, resource: Any) -> None:
        """Track a resource for cleanup."""
        with self._lock:
            self._resources.append(resource)

            # Register cleanup on first resource
            if not self._cleanup_registered:
                atexit.register(self._cleanup_all)
                self._cleanup_registered = True

    def untrack(self, resource: Any) -> None:
        """Stop tracking a resource."""
        with self._lock:
            try:
                self._resources.remove(resource)
            except ValueError:
                pass  # Resource not tracked

    def cleanup_all(self) -> None:
        """Clean up all tracked resources."""
        with self._lock:
            for resource in list(self._resources):
                try:
                    if hasattr(resource, "cleanup"):
                        resource.cleanup()
                    elif hasattr(resource, "close"):
                        resource.close()
                    elif hasattr(resource, "__exit__"):
                        resource.__exit__(None, None, None)
                except Exception as e:
                    LOGGER.warning("Failed to cleanup resource %s in tracker %s: %s", resource, self.name, e)
            self._resources.clear()

    def _cleanup_all(self) -> None:
        """Cleanup handler for atexit."""
        try:
            self.cleanup_all()
        except Exception:
            pass  # Suppress errors during exit


# Global resource tracker
_global_tracker = ResourceTracker("global")


def track_resource(resource: Any) -> None:
    """Track a resource for automatic cleanup."""
    _global_tracker.track(resource)


def untrack_resource(resource: Any) -> None:
    """Stop tracking a resource."""
    _global_tracker.untrack(resource)


@contextmanager
def managed_resource(resource: Any, cleanup_fn: Any | None = None) -> Generator[Any]:
    """Context manager for automatic resource cleanup.

    Args:
        resource: Resource to manage
        cleanup_fn: Optional custom cleanup function

    Yields:
        The resource
    """
    track_resource(resource)
    try:
        yield resource
    finally:
        untrack_resource(resource)

        # Custom cleanup function
        if cleanup_fn:
            try:
                cleanup_fn(resource)
            except Exception as e:
                LOGGER.warning("Custom cleanup failed for %s: %s", resource, e)
        # Standard cleanup methods
        elif hasattr(resource, "cleanup"):
            resource.cleanup()
        elif hasattr(resource, "close"):
            resource.close()


@asynccontextmanager
async def managed_async_resource(resource: Any, cleanup_fn: Any | None = None) -> AsyncGenerator[Any]:
    """Async context manager for automatic resource cleanup.

    Args:
        resource: Resource to manage
        cleanup_fn: Optional custom cleanup function

    Yields:
        The resource
    """
    track_resource(resource)
    try:
        yield resource
    finally:
        untrack_resource(resource)

        # Custom cleanup function
        if cleanup_fn:
            try:
                if asyncio.iscoroutinefunction(cleanup_fn):
                    await cleanup_fn(resource)
                else:
                    cleanup_fn(resource)
            except Exception as e:
                LOGGER.warning("Custom async cleanup failed for %s: %s", resource, e)
        # Standard cleanup methods
        elif hasattr(resource, "cleanup"):
            if asyncio.iscoroutinefunction(resource.cleanup):
                await resource.cleanup()
            else:
                resource.cleanup()
        elif hasattr(resource, "close"):
            if asyncio.iscoroutinefunction(resource.close):
                await resource.close()
            else:
                resource.close()
        elif hasattr(resource, "__aexit__"):
            await resource.__aexit__(None, None, None)


@contextmanager
def temporary_directory(prefix: str = "goes_vfi_", suffix: str = "", cleanup: bool = True) -> Generator[Path]:
    """Context manager for temporary directories with automatic cleanup.

    Args:
        prefix: Directory name prefix
        suffix: Directory name suffix
        cleanup: Whether to cleanup on exit

    Yields:
        Path to temporary directory
    """
    temp_dir = None
    try:
        temp_dir = Path(tempfile.mkdtemp(prefix=prefix, suffix=suffix))
        LOGGER.debug("Created temporary directory: %s", temp_dir)
        yield temp_dir
    finally:
        if temp_dir and cleanup and temp_dir.exists():
            try:
                import shutil

                shutil.rmtree(temp_dir)
                LOGGER.debug("Cleaned up temporary directory: %s", temp_dir)
            except Exception as e:
                LOGGER.warning("Failed to cleanup temporary directory %s: %s", temp_dir, e)


@contextmanager
def temporary_file(
    suffix: str = "", prefix: str = "goes_vfi_", text: bool = False, cleanup: bool = True
) -> Generator[Path]:
    """Context manager for temporary files with automatic cleanup.

    Args:
        suffix: File name suffix
        prefix: File name prefix
        text: Whether file is text mode
        cleanup: Whether to cleanup on exit

    Yields:
        Path to temporary file
    """
    temp_file = None
    try:
        fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix, text=text)
        # Close the file descriptor since we only want the path
        import os

        os.close(fd)

        temp_file = Path(temp_path)
        LOGGER.debug("Created temporary file: %s", temp_file)
        yield temp_file
    finally:
        if temp_file and cleanup and temp_file.exists():
            try:
                temp_file.unlink()
                LOGGER.debug("Cleaned up temporary file: %s", temp_file)
            except Exception as e:
                LOGGER.warning("Failed to cleanup temporary file %s: %s", temp_file, e)


class ResourceManager(BaseManager):
    """Modern resource manager with automatic tracking and cleanup."""

    def __init__(self) -> None:
        super().__init__("ResourceManager")
        self._tracker = ResourceTracker("ResourceManager")

    def track(self, resource: Any) -> None:
        """Track a resource for cleanup."""
        self._tracker.track(resource)
        self.log_debug("Tracking resource: %s", type(resource).__name__)

    def untrack(self, resource: Any) -> None:
        """Stop tracking a resource."""
        self._tracker.untrack(resource)
        self.log_debug("Untracked resource: %s", type(resource).__name__)

    def _do_cleanup(self) -> None:
        """Perform cleanup of all tracked resources."""
        self._tracker.cleanup_all()
        self.log_info("Cleaned up all tracked resources")

    def managed(self, resource: Any, cleanup_fn: Any | None = None) -> Any:
        """Add a resource to be managed.

        Args:
            resource: Resource to manage
            cleanup_fn: Optional custom cleanup function

        Returns:
            The resource (for chaining)
        """
        self.track(resource)

        # Store custom cleanup function if provided
        if cleanup_fn and not hasattr(resource, "_custom_cleanup"):
            resource._custom_cleanup = cleanup_fn

        return resource

    @contextmanager
    def batch_context(self) -> Generator[None]:
        """Context manager for batch resource operations."""
        initial_count = len(self._tracker._resources)
        try:
            yield
        finally:
            # Cleanup any resources added during the batch
            current_count = len(self._tracker._resources)
            if current_count > initial_count:
                resources_to_cleanup = self._tracker._resources[initial_count:]
                for resource in resources_to_cleanup:
                    try:
                        if hasattr(resource, "_custom_cleanup"):
                            resource._custom_cleanup(resource)
                        elif hasattr(resource, "cleanup"):
                            resource.cleanup()
                        elif hasattr(resource, "close"):
                            resource.close()
                    except Exception as e:
                        self.log_warning("Failed to cleanup batch resource %s: %s", resource, e)


# Singleton resource manager
_resource_manager: ResourceManager | None = None


def get_resource_manager() -> ResourceManager:
    """Get the global resource manager instance."""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager


# Modern file operation utilities


@contextmanager
def atomic_write(path: Path, mode: str = "w", encoding: str = "utf-8", backup: bool = False) -> Generator[Any]:
    """Context manager for atomic file writing.

    Writes to a temporary file first, then moves to target location.

    Args:
        path: Target file path
        mode: File open mode
        encoding: Text encoding
        backup: Whether to create backup of existing file

    Yields:
        File object for writing
    """
    path = Path(path)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    backup_path = path.with_suffix(path.suffix + ".bak")

    try:
        # Create backup if requested and file exists
        if backup and path.exists():
            import shutil

            shutil.copy2(path, backup_path)
            LOGGER.debug("Created backup: %s", backup_path)

        # Write to temporary file
        with open(temp_path, mode, encoding=encoding) as f:
            yield f

        # Atomic move to target location
        temp_path.replace(path)
        LOGGER.debug("Atomically wrote file: %s", path)

    except Exception:
        # Clean up temporary file on error
        if temp_path.exists():
            temp_path.unlink()
        raise
    finally:
        # Clean up backup if write was successful
        if backup and backup_path.exists() and path.exists():
            try:
                backup_path.unlink()
            except Exception:
                pass  # Keep backup on cleanup failure


@contextmanager
def file_lock(path: Path, timeout: float = 10.0) -> Generator[None]:
    """Context manager for file locking.

    Args:
        path: Path to lock
        timeout: Timeout for acquiring lock

    Yields:
        None
    """
    import fcntl
    import time

    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_file = None

    try:
        # Create lock file
        lock_file = open(lock_path, "w", encoding="utf-8")

        # Try to acquire lock with timeout
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                LOGGER.debug("Acquired file lock: %s", lock_path)
                break
            except OSError:
                time.sleep(0.1)
        else:
            msg = f"Could not acquire file lock for {path} within {timeout}s"
            raise TimeoutError(msg)

        yield

    finally:
        if lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
                lock_path.unlink()
                LOGGER.debug("Released file lock: %s", lock_path)
            except Exception as e:
                LOGGER.warning("Failed to release file lock %s: %s", lock_path, e)


# Memory management utilities


class MemoryMonitor:
    """Monitor memory usage and provide warnings."""

    def __init__(self, warning_threshold: float = 0.8, critical_threshold: float = 0.9):
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    def get_memory_usage(self) -> dict[str, Any]:
        """Get current memory usage information."""
        try:
            import psutil

            memory = psutil.virtual_memory()
            return {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent,
                "used": memory.used,
                "free": memory.free,
            }
        except ImportError:
            # Fallback without psutil
            import sys

            if hasattr(sys, "getsizeof"):
                return {"available": "unknown", "percent": 0}
            return {}

    def check_memory(self) -> bool:
        """Check memory usage and log warnings.

        Returns:
            True if memory usage is acceptable
        """
        usage = self.get_memory_usage()
        percent = usage.get("percent", 0)

        if percent > self.critical_threshold * 100:
            LOGGER.critical("Critical memory usage: %.1f%%", percent)
            return False
        if percent > self.warning_threshold * 100:
            LOGGER.warning("High memory usage: %.1f%%", percent)

        return True

    @contextmanager
    def monitor_context(self) -> Generator[None]:
        """Context manager that monitors memory during execution."""
        initial_usage = self.get_memory_usage()
        LOGGER.debug("Initial memory usage: %.1f%%", initial_usage.get("percent", 0))

        try:
            yield
        finally:
            final_usage = self.get_memory_usage()
            LOGGER.debug("Final memory usage: %.1f%%", final_usage.get("percent", 0))

            # Calculate memory change
            initial_percent = initial_usage.get("percent", 0)
            final_percent = final_usage.get("percent", 0)

            if final_percent > initial_percent + 10:  # 10% increase
                LOGGER.warning("Significant memory increase: %.1f%% -> %.1f%%", initial_percent, final_percent)


# Global memory monitor
_memory_monitor = MemoryMonitor()


def get_memory_monitor() -> MemoryMonitor:
    """Get the global memory monitor instance."""
    return _memory_monitor


# Context manager for temporary environment variables
@contextmanager
def temporary_env(**env_vars: str) -> Generator[None]:
    """Context manager for temporary environment variables.

    Args:
        **env_vars: Environment variables to set temporarily

    Yields:
        None
    """
    import os

    original_values = {}

    try:
        # Set new values and store originals
        for key, value in env_vars.items():
            original_values[key] = os.environ.get(key)
            os.environ[key] = value
            LOGGER.debug("Set temporary env var: %s=%s", key, value)

        yield

    finally:
        # Restore original values
        for key, original_value in original_values.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value
            LOGGER.debug("Restored env var: %s", key)
