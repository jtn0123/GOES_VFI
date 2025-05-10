"""
Background worker system for UI-responsive operations.

This module provides a background worker system for running heavy operations
without freezing the UI, with support for progress reporting, cancellation,
and error handling.
"""

import logging
import traceback
import time
from typing import Dict, Any, Optional, Callable, TypeVar, Generic
from dataclasses import dataclass
from enum import Enum, auto
# Concurrent futures for thread management

from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QRunnable, QThreadPool
# PyQt widgets for UI integration

# Configure logging
LOGGER = logging.getLogger(__name__)


# Define types for generic task handling
T = TypeVar('T')  # Task result type
P = TypeVar('P')  # Task progress type


class TaskStatus(Enum):
    """Status of a background task."""
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass
class TaskProgress:
    """Progress information for a background task."""
    current: int
    total: int
    eta_seconds: float = 0.0
    message: str = ""


@dataclass
class TaskResult(Generic[T]):
    """Result of a background task."""
    task_id: str
    status: TaskStatus
    result: Optional[T] = None
    error: Optional[Exception] = None
    error_traceback: Optional[str] = None


class TaskSignals(QObject):
    """Signals for task communication."""
    started = pyqtSignal(str)  # task_id
    progress = pyqtSignal(str, object)  # task_id, progress_info
    completed = pyqtSignal(str, object)  # task_id, result
    failed = pyqtSignal(str, object, object)  # task_id, error, traceback
    cancelled = pyqtSignal(str)  # task_id


class Task(QRunnable, Generic[T, P]):
    """
    Background task that runs in a separate thread.
    
    This class provides a way to run a function in a background thread
    with support for progress reporting, cancellation, and error handling.
    """
    
    def __init__(self, task_id: str, func: Callable[..., T],
                 *args, **kwargs) -> None:
        """
        Initialize the task.
        
        Args:
            task_id: Unique identifier for the task
            func: Function to run in the background
            *args: Positional arguments to pass to func
            **kwargs: Keyword arguments to pass to func
        """
        super().__init__()
        
        self.task_id = task_id
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.signals = TaskSignals()
        self._cancel_requested = False
        
        # Set thread priority
        self.setAutoDelete(True)
    
    def run(self) -> None:
        """Execute the task in the background thread."""
        try:
            # Emit started signal
            self.signals.started.emit(self.task_id)
            
            # Add progress_callback and cancel_check to kwargs
            self.kwargs["progress_callback"] = self._progress_callback
            self.kwargs["cancel_check"] = self._cancel_check
            
            # Run the function
            result = self.func(*self.args, **self.kwargs)
            
            # Check if cancelled after execution
            if self._cancel_requested:
                self.signals.cancelled.emit(self.task_id)
                return
            
            # Emit completed signal with result
            task_result = TaskResult(
                task_id=self.task_id,
                status=TaskStatus.COMPLETED,
                result=result
            )
            self.signals.completed.emit(self.task_id, task_result)
            
        except Exception as e:
            # Get traceback
            error_traceback = traceback.format_exc()
            
            # Emit failed signal with error info
            task_result = TaskResult(
                task_id=self.task_id,
                status=TaskStatus.FAILED,
                error=e,
                error_traceback=error_traceback
            )
            self.signals.failed.emit(self.task_id, e, error_traceback)
            
            # Log error
            LOGGER.error("Task %s failed: %s\n%s", self.task_id, e, error_traceback)
    
    def _progress_callback(self, progress_info: P) -> None:
        """
        Report progress from the task.
        
        Args:
            progress_info: Progress information to report
        """
        self.signals.progress.emit(self.task_id, progress_info)
    
    def _cancel_check(self) -> bool:
        """
        Check if the task should be cancelled.
        
        Returns:
            True if the task should be cancelled, False otherwise
        """
        return self._cancel_requested
    
    def cancel(self) -> None:
        """Request cancellation of the task."""
        self._cancel_requested = True
        LOGGER.debug("Cancellation requested for task %s", self.task_id)


class TaskManager(QObject):
    """
    Manager for background tasks.
    
    This class provides a centralized way to manage background tasks,
    with support for progress reporting, cancellation, and error handling.
    """
    
    # Signals for task events
    task_started = pyqtSignal(str)  # task_id
    task_progress = pyqtSignal(str, object)  # task_id, progress_info
    task_completed = pyqtSignal(str, object)  # task_id, result
    task_failed = pyqtSignal(str, object, object)  # task_id, error, traceback
    task_cancelled = pyqtSignal(str)  # task_id
    
    def __init__(self) -> None:
        """Initialize the task manager."""
        super().__init__()
        
        # Create thread pool
        self.thread_pool = QThreadPool.globalInstance()
        
        # Set thread pool maximum thread count
        max_threads = min(16, QThreadPool.globalInstance().maxThreadCount())
        self.thread_pool.setMaxThreadCount(max_threads)
        
        # Store active tasks
        self._tasks: Dict[str, Task] = {}
        
        # Configure logging
        LOGGER.info("Task manager initialized with %d threads", max_threads)
    
    def submit_task(self, task_id: str, func: Callable[..., T],
                   *args, **kwargs) -> None:
        """
        Submit a task for execution in the background.
        
        Args:
            task_id: Unique identifier for the task
            func: Function to run in the background
            *args: Positional arguments to pass to func
            **kwargs: Keyword arguments to pass to func
        """
        # Create task
        task = Task(task_id, func, *args, **kwargs)
        
        # Store task
        self._tasks[task_id] = task
        
        # Connect signals
        task.signals.started.connect(self._on_task_started)
        task.signals.progress.connect(self._on_task_progress)
        task.signals.completed.connect(self._on_task_completed)
        task.signals.failed.connect(self._on_task_failed)
        task.signals.cancelled.connect(self._on_task_cancelled)
        
        # Submit task to thread pool
        self.thread_pool.start(task)
        
        LOGGER.debug("Task %s submitted", task_id)
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Request cancellation of a task.
        
        Args:
            task_id: Identifier of the task to cancel
            
        Returns:
            True if the task was found and cancellation was requested,
            False if the task wasn't found
        """
        if task_id in self._tasks:
            self._tasks[task_id].cancel()
            LOGGER.debug("Cancellation requested for task %s", task_id)
            return True
        
        LOGGER.warning("Cannot cancel task %s: not found", task_id)
        return False
    
    def cancel_all_tasks(self) -> None:
        """Request cancellation of all active tasks."""
        for task_id in list(self._tasks.keys()):
            self.cancel_task(task_id)
        
        LOGGER.info("Cancellation requested for all %d tasks", len(self._tasks))
    
    def is_task_active(self, task_id: str) -> bool:
        """
        Check if a task is active.
        
        Args:
            task_id: Identifier of the task to check
            
        Returns:
            True if the task is active, False if it has completed or wasn't found
        """
        return task_id in self._tasks
    
    def get_active_task_count(self) -> int:
        """
        Get the number of active tasks.
        
        Returns:
            Number of active tasks
        """
        return len(self._tasks)
    
    def _on_task_started(self, task_id: str) -> None:
        """
        Handle task started event.
        
        Args:
            task_id: Identifier of the started task
        """
        # Emit started signal
        self.task_started.emit(task_id)
        
        LOGGER.debug("Task %s started", task_id)
    
    def _on_task_progress(self, task_id: str, progress_info: Any) -> None:
        """
        Handle task progress event.
        
        Args:
            task_id: Identifier of the task reporting progress
            progress_info: Progress information from the task
        """
        # Emit progress signal
        self.task_progress.emit(task_id, progress_info)
    
    def _on_task_completed(self, task_id: str, result: TaskResult) -> None:
        """
        Handle task completed event.
        
        Args:
            task_id: Identifier of the completed task
            result: Result of the task
        """
        # Remove task from active tasks
        if task_id in self._tasks:
            del self._tasks[task_id]
        
        # Emit completed signal
        self.task_completed.emit(task_id, result)
        
        LOGGER.debug("Task %s completed", task_id)
    
    def _on_task_failed(self, task_id: str, error: Exception,
                        error_traceback: str) -> None:
        """
        Handle task failed event.
        
        Args:
            task_id: Identifier of the failed task
            error: Exception that caused the failure
            error_traceback: Traceback of the exception
        """
        # Remove task from active tasks
        if task_id in self._tasks:
            del self._tasks[task_id]
        
        # Emit failed signal
        self.task_failed.emit(task_id, error, error_traceback)
        
        LOGGER.error("Task %s failed: %s\n%s", task_id, error, error_traceback)
    
    def _on_task_cancelled(self, task_id: str) -> None:
        """
        Handle task cancelled event.
        
        Args:
            task_id: Identifier of the cancelled task
        """
        # Remove task from active tasks
        if task_id in self._tasks:
            del self._tasks[task_id]
        
        # Emit cancelled signal
        self.task_cancelled.emit(task_id)
        
        LOGGER.debug("Task %s cancelled", task_id)
    
    def cleanup(self) -> None:
        """Clean up resources used by the task manager."""
        # Cancel all tasks
        self.cancel_all_tasks()
        
        # Wait for all tasks to complete
        self.thread_pool.waitForDone()
        
        LOGGER.info("Task manager cleaned up")


class UIFreezeMonitor(QObject):
    """
    Monitor for detecting UI freezes.
    
    This class monitors the application's event loop to detect UI freezes,
    and emits signals when freezes are detected and resolved.
    """
    
    # Signals for freeze events
    freeze_detected = pyqtSignal(float)  # duration_ms
    freeze_resolved = pyqtSignal(float)  # total_duration_ms
    
    def __init__(self, parent: Optional[QObject] = None,
                 check_interval_ms: int = 100,
                 freeze_threshold_ms: int = 500) -> None:
        """
        Initialize the freeze monitor.
        
        Args:
            parent: Optional parent object
            check_interval_ms: Interval between checks, in milliseconds
            freeze_threshold_ms: Threshold for detecting freezes, in milliseconds
        """
        super().__init__(parent)
        
        self.check_interval_ms = check_interval_ms
        self.freeze_threshold_ms = freeze_threshold_ms
        
        # State variables
        self._is_frozen = False
        self._freeze_start_time = 0.0
        self._last_check_time = 0.0
        
        # Create timer for checks
        self._timer = QTimer(self)
        self._timer.setInterval(check_interval_ms)
        self._timer.timeout.connect(self._check_responsiveness)
    
    def start_monitoring(self) -> None:
        """Start monitoring for UI freezes."""
        self._last_check_time = time.time() * 1000
        self._timer.start()
        LOGGER.debug("UI freeze monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop monitoring for UI freezes."""
        self._timer.stop()
        self._is_frozen = False
        LOGGER.debug("UI freeze monitoring stopped")
    
    def is_frozen(self) -> bool:
        """
        Check if the UI is currently frozen.
        
        Returns:
            True if the UI is frozen, False otherwise
        """
        return self._is_frozen
    
    def get_freeze_duration(self) -> float:
        """
        Get the duration of the current freeze, in milliseconds.
        
        Returns:
            Duration of the current freeze, or 0.0 if not frozen
        """
        if not self._is_frozen:
            return 0.0
        
        return (time.time() * 1000) - self._freeze_start_time
    
    def _check_responsiveness(self) -> None:
        """Check for UI freezes based on event loop responsiveness."""
        # Get current time in milliseconds
        current_time = time.time() * 1000
        
        # Calculate time since last check
        elapsed = current_time - self._last_check_time
        
        # Check if we're experiencing a freeze
        if elapsed > self.freeze_threshold_ms:
            # We have a freeze
            if not self._is_frozen:
                # This is a new freeze
                self._is_frozen = True
                self._freeze_start_time = self._last_check_time
                self.freeze_detected.emit(elapsed)
                LOGGER.warning("UI freeze detected: %.1fms", elapsed)
        elif self._is_frozen:
            # Freeze has resolved
            total_duration = current_time - self._freeze_start_time
            self._is_frozen = False
            self.freeze_resolved.emit(total_duration)
            LOGGER.info("UI freeze resolved after %.1fms", total_duration)
        
        # Update last check time
        self._last_check_time = current_time


class BackgroundProcessManager:
    """
    Manager for background processes to optimize UI responsiveness.
    
    This class combines the TaskManager and UIFreezeMonitor to provide
    a comprehensive solution for running background tasks while maintaining
    UI responsiveness.
    """
    
    def __init__(self) -> None:
        """Initialize the background process manager."""
        # Create task manager
        self.task_manager = TaskManager()
        
        # Create freeze monitor
        self.freeze_monitor = UIFreezeMonitor()
        
        # Start freeze monitoring
        self.freeze_monitor.start_monitoring()
        
        # Connect freeze signals to logging
        self.freeze_monitor.freeze_detected.connect(self._on_freeze_detected)
        self.freeze_monitor.freeze_resolved.connect(self._on_freeze_resolved)
        
        LOGGER.info("Background process manager initialized")
    
    def submit_task(self, task_id: str, func: Callable[..., T],
                   *args, **kwargs) -> None:
        """
        Submit a task for execution in the background.
        
        Args:
            task_id: Unique identifier for the task
            func: Function to run in the background
            *args: Positional arguments to pass to func
            **kwargs: Keyword arguments to pass to func
        """
        self.task_manager.submit_task(task_id, func, *args, **kwargs)
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Request cancellation of a task.
        
        Args:
            task_id: Identifier of the task to cancel
            
        Returns:
            True if the task was found and cancellation was requested,
            False if the task wasn't found
        """
        return self.task_manager.cancel_task(task_id)
    
    def _on_freeze_detected(self, duration_ms: float) -> None:
        """
        Handle UI freeze detected event.
        
        Args:
            duration_ms: Duration of the freeze, in milliseconds
        """
        # Log the freeze
        LOGGER.warning("UI freeze detected: %.1fms", duration_ms)
    
    def _on_freeze_resolved(self, total_duration_ms: float) -> None:
        """
        Handle UI freeze resolved event.
        
        Args:
            total_duration_ms: Total duration of the freeze, in milliseconds
        """
        # Log the resolution
        LOGGER.info("UI freeze resolved after %.1fms", total_duration_ms)
    
    def cleanup(self) -> None:
        """Clean up resources used by the background process manager."""
        # Stop freeze monitoring
        self.freeze_monitor.stop_monitoring()
        
        # Clean up task manager
        self.task_manager.cleanup()
        
        LOGGER.info("Background process manager cleaned up")


# Create a global instance of the background process manager
background_manager = BackgroundProcessManager()


def run_in_background(task_id: str, func: Callable[..., T],
                      *args, **kwargs) -> None:
    """
    Run a function in the background without freezing the UI.
    
    Args:
        task_id: Unique identifier for the task
        func: Function to run in the background
        *args: Positional arguments to pass to func
        **kwargs: Keyword arguments to pass to func
    """
    background_manager.submit_task(task_id, func, *args, **kwargs)


def cancel_background_task(task_id: str) -> bool:
    """
    Request cancellation of a background task.
    
    Args:
        task_id: Identifier of the task to cancel
        
    Returns:
        True if the task was found and cancellation was requested,
        False if the task wasn't found
    """
    return background_manager.cancel_task(task_id)


def get_task_manager() -> TaskManager:
    """
    Get the global task manager instance.
    
    Returns:
        Global task manager instance
    """
    return background_manager.task_manager


def get_freeze_monitor() -> UIFreezeMonitor:
    """
    Get the global UI freeze monitor instance.
    
    Returns:
        Global UI freeze monitor instance
    """
    return background_manager.freeze_monitor
