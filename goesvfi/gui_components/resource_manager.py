"""Resource management system for proper cleanup and lifecycle management.

This module provides centralized resource management to prevent memory leaks
and ensure proper cleanup of widgets, threads, files, and other resources.
"""

import atexit
from collections.abc import Callable, Generator
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import tempfile
import threading
import weakref

from PyQt6.QtCore import QThread, QTimer
from PyQt6.QtWidgets import QWidget

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class ResourceTracker:
    """Tracks and manages application resources for proper cleanup."""

    def __init__(self) -> None:
        """Initialize the resource tracker."""
        self.temp_files: set[Path] = set()
        self.temp_dirs: set[Path] = set()
        self.worker_threads: dict[str, QThread] = {}
        self.timers: dict[str, QTimer] = {}
        self.widgets: weakref.WeakSet = weakref.WeakSet()
        self._cleanup_callbacks: list[Callable[[], None]] = []
        self._lock = threading.Lock()

        # Register cleanup at exit
        atexit.register(self.cleanup_all)

    def track_temp_file(self, file_path: Path) -> None:
        """Track a temporary file for cleanup.

        Args:
            file_path: Path to temporary file
        """
        with self._lock:
            self.temp_files.add(file_path)
        LOGGER.debug("Tracking temp file: %s", file_path)

    def track_temp_dir(self, dir_path: Path) -> None:
        """Track a temporary directory for cleanup.

        Args:
            dir_path: Path to temporary directory
        """
        with self._lock:
            self.temp_dirs.add(dir_path)
        LOGGER.debug("Tracking temp directory: %s", dir_path)

    def track_worker_thread(self, name: str, thread: QThread) -> None:
        """Track a worker thread for proper termination.

        Args:
            name: Unique name for the thread
            thread: QThread instance
        """
        with self._lock:
            if name in self.worker_threads:
                LOGGER.warning("Thread '%s' already tracked, replacing", name)
            self.worker_threads[name] = thread
        LOGGER.debug("Tracking worker thread: %s", name)

    def track_timer(self, name: str, timer: QTimer) -> None:
        """Track a timer for proper cleanup.

        Args:
            name: Unique name for the timer
            timer: QTimer instance
        """
        with self._lock:
            if name in self.timers:
                LOGGER.warning("Timer '%s' already tracked, replacing", name)
            self.timers[name] = timer
        LOGGER.debug("Tracking timer: %s", name)

    def track_widget(self, widget: QWidget) -> None:
        """Track a widget for cleanup monitoring.

        Args:
            widget: Widget to track
        """
        self.widgets.add(widget)
        LOGGER.debug("Tracking widget: %s", type(widget).__name__)

    def register_cleanup_callback(self, callback: Callable[[], None]) -> None:
        """Register a cleanup callback to be called during shutdown.

        Args:
            callback: Function to call during cleanup
        """
        with self._lock:
            self._cleanup_callbacks.append(callback)
        LOGGER.debug("Registered cleanup callback: %s", callback.__name__)

    def untrack_temp_file(self, file_path: Path) -> None:
        """Stop tracking a temporary file.

        Args:
            file_path: Path to temporary file
        """
        with self._lock:
            self.temp_files.discard(file_path)
        LOGGER.debug("Untracked temp file: %s", file_path)

    def untrack_worker_thread(self, name: str) -> None:
        """Stop tracking a worker thread.

        Args:
            name: Name of the thread
        """
        with self._lock:
            if name in self.worker_threads:
                del self.worker_threads[name]
        LOGGER.debug("Untracked worker thread: %s", name)

    def untrack_timer(self, name: str) -> None:
        """Stop tracking a timer.

        Args:
            name: Name of the timer
        """
        with self._lock:
            if name in self.timers:
                del self.timers[name]
        LOGGER.debug("Untracked timer: %s", name)

    def untrack_temp_dir(self, dir_path: Path) -> None:
        """Stop tracking a temporary directory.

        Args:
            dir_path: Path to temporary directory
        """
        with self._lock:
            self.temp_dirs.discard(dir_path)
        LOGGER.debug("Untracked temp directory: %s", dir_path)

    def cleanup_temp_files(self) -> None:
        """Clean up all tracked temporary files."""
        with self._lock:
            files_to_remove = list(self.temp_files)

        for file_path in files_to_remove:
            try:
                if file_path.exists():
                    file_path.unlink()
                    LOGGER.debug("Removed temp file: %s", file_path)
                self.temp_files.discard(file_path)
            except Exception:
                LOGGER.exception("Failed to remove temp file: %s", file_path)

    def cleanup_temp_dirs(self) -> None:
        """Clean up all tracked temporary directories."""
        with self._lock:
            dirs_to_remove = list(self.temp_dirs)

        for dir_path in dirs_to_remove:
            try:
                if dir_path.exists():
                    shutil.rmtree(dir_path)
                    LOGGER.debug("Removed temp directory: %s", dir_path)
                self.temp_dirs.discard(dir_path)
            except Exception:
                LOGGER.exception("Failed to remove temp directory: %s", dir_path)

    def cleanup_worker_threads(self) -> None:
        """Clean up all tracked worker threads."""
        with self._lock:
            threads_to_cleanup = dict(self.worker_threads)

        for name, thread in threads_to_cleanup.items():
            try:
                if thread.isRunning():
                    LOGGER.info("Terminating worker thread: %s", name)
                    thread.terminate()
                    if not thread.wait(3000):  # Wait 3 seconds
                        LOGGER.warning("Thread %s did not terminate gracefully", name)
                self.untrack_worker_thread(name)
            except Exception:
                LOGGER.exception("Failed to cleanup worker thread: %s", name)

    def cleanup_timers(self) -> None:
        """Clean up all tracked timers."""
        with self._lock:
            timers_to_cleanup = dict(self.timers)

        for name, timer in timers_to_cleanup.items():
            try:
                if timer.isActive():
                    timer.stop()
                    LOGGER.debug("Stopped timer: %s", name)
                self.untrack_timer(name)
            except Exception:
                LOGGER.exception("Failed to cleanup timer: %s", name)

    def cleanup_callbacks(self) -> None:
        """Execute all registered cleanup callbacks."""
        with self._lock:
            callbacks = list(self._cleanup_callbacks)

        for callback in callbacks:
            try:
                callback()
                LOGGER.debug("Executed cleanup callback: %s", callback.__name__)
            except Exception:
                LOGGER.exception("Error in cleanup callback: %s", callback.__name__)

    def cleanup_all(self) -> None:
        """Clean up all tracked resources."""
        LOGGER.info("Starting resource cleanup")

        # Clean up in order of importance
        self.cleanup_callbacks()
        self.cleanup_timers()
        self.cleanup_worker_threads()
        self.cleanup_temp_files()
        self.cleanup_temp_dirs()

        # Clear tracking collections
        with self._lock:
            self._cleanup_callbacks.clear()

        LOGGER.info("Resource cleanup complete")

    def get_stats(self) -> dict[str, int]:
        """Get statistics about tracked resources.

        Returns:
            Dictionary with resource counts
        """
        with self._lock:
            return {
                "temp_files": len(self.temp_files),
                "temp_dirs": len(self.temp_dirs),
                "worker_threads": len(self.worker_threads),
                "timers": len(self.timers),
                "widgets": len(self.widgets),
                "cleanup_callbacks": len(self._cleanup_callbacks),
            }


# Global resource tracker instance
_resource_tracker: ResourceTracker | None = None


def get_resource_tracker() -> ResourceTracker:
    """Get the global resource tracker instance.

    Returns:
        The global ResourceTracker instance
    """
    global _resource_tracker  # noqa: PLW0603
    if _resource_tracker is None:
        _resource_tracker = ResourceTracker()
    return _resource_tracker


# Context managers for automatic resource management
@contextmanager
def managed_temp_file(suffix: str = "", prefix: str = "goes_vfi_") -> Generator[Path]:
    """Context manager for temporary files with automatic cleanup.

    Args:
        suffix: File suffix
        prefix: File prefix

    Yields:
        Path to temporary file
    """
    temp_file = None
    try:
        # Create temporary file
        fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        os.close(fd)  # Close file descriptor

        temp_file = Path(temp_path)
        get_resource_tracker().track_temp_file(temp_file)

        yield temp_file

    finally:
        if temp_file:
            try:
                if temp_file.exists():
                    temp_file.unlink()
                get_resource_tracker().untrack_temp_file(temp_file)
            except Exception:
                LOGGER.exception("Failed to cleanup temp file: %s", temp_file)


@contextmanager
def managed_temp_dir(suffix: str = "", prefix: str = "goes_vfi_") -> Generator[Path]:
    """Context manager for temporary directories with automatic cleanup.

    Args:
        suffix: Directory suffix
        prefix: Directory prefix

    Yields:
        Path to temporary directory
    """
    temp_dir = None
    try:
        # Create temporary directory
        temp_dir = Path(tempfile.mkdtemp(suffix=suffix, prefix=prefix))
        get_resource_tracker().track_temp_dir(temp_dir)

        yield temp_dir

    finally:
        if temp_dir:
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                get_resource_tracker().untrack_temp_dir(temp_dir)
            except Exception:
                LOGGER.exception("Failed to cleanup temp directory: %s", temp_dir)


@contextmanager
def managed_worker_thread(name: str, thread: QThread) -> Generator[QThread]:
    """Context manager for worker threads with automatic cleanup.

    Args:
        name: Unique name for the thread
        thread: QThread instance

    Yields:
        The thread instance
    """
    try:
        get_resource_tracker().track_worker_thread(name, thread)
        yield thread

    finally:
        try:
            if thread.isRunning():
                thread.terminate()
                thread.wait(3000)
            get_resource_tracker().untrack_worker_thread(name)
        except Exception:
            LOGGER.exception("Failed to cleanup worker thread: %s", name)


# Convenience functions
def track_temp_file(file_path: Path) -> None:
    """Track a temporary file for cleanup."""
    get_resource_tracker().track_temp_file(file_path)


def track_temp_dir(dir_path: Path) -> None:
    """Track a temporary directory for cleanup."""
    get_resource_tracker().track_temp_dir(dir_path)


def track_worker_thread(name: str, thread: QThread) -> None:
    """Track a worker thread for cleanup."""
    get_resource_tracker().track_worker_thread(name, thread)


def track_timer(name: str, timer: QTimer) -> None:
    """Track a timer for cleanup."""
    get_resource_tracker().track_timer(name, timer)


def track_widget(widget: QWidget) -> None:
    """Track a widget for monitoring."""
    get_resource_tracker().track_widget(widget)


def register_cleanup_callback(callback: Callable[[], None]) -> None:
    """Register a cleanup callback."""
    get_resource_tracker().register_cleanup_callback(callback)
