"""
Unit tests for the background worker system.

Tests the background worker components including Task, TaskManager,
UIFreezeMonitor, and BackgroundProcessManager.
"""

import logging
import time
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QThreadPool

from goesvfi.integrity_check.background_worker import (
    BackgroundProcessManager,
    Task,
    TaskManager,
    TaskProgress,
    TaskResult,
    TaskSignals,
    TaskStatus,
    UIFreezeMonitor,
    cancel_background_task,
    get_freeze_monitor,
    get_task_manager,
)

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)


class TestTaskProgress:
    """Test TaskProgress dataclass."""

    def test_task_progress_creation(self):
        """Test creating TaskProgress instance."""
        progress = TaskProgress(
            current=5, total=10, eta_seconds=2.5, message="Processing..."
        )
        assert progress.current == 5
        assert progress.total == 10
        assert progress.eta_seconds == 2.5
        assert progress.message == "Processing..."

    def test_task_progress_defaults(self):
        """Test TaskProgress default values."""
        progress = TaskProgress(current=1, total=10)
        assert progress.eta_seconds == 0.0
        assert progress.message == ""


class TestTaskResult:
    """Test TaskResult dataclass."""

    def test_task_result_success(self):
        """Test creating successful TaskResult."""
        result = TaskResult(
            task_id="test_task", status=TaskStatus.COMPLETED, result="Success!"
        )
        assert result.task_id == "test_task"
        assert result.status == TaskStatus.COMPLETED
        assert result.result == "Success!"
        assert result.error is None
        assert result.error_traceback is None

    def test_task_result_failure(self):
        """Test creating failed TaskResult."""
        error = ValueError("Test error")
        result = TaskResult(
            task_id="test_task",
            status=TaskStatus.FAILED,
            error=error,
            error_traceback="Traceback...",
        )
        assert result.task_id == "test_task"
        assert result.status == TaskStatus.FAILED
        assert result.result is None
        assert result.error == error
        assert result.error_traceback == "Traceback..."


class TestTask:
    """Test Task class functionality."""

    def test_task_creation(self):
        """Test creating a Task instance."""

        def dummy_func(x, y):
            return x + y

        task = Task("test_task", dummy_func, 1, 2)
        assert task.task_id == "test_task"
        assert task.func == dummy_func
        assert task.args == (1, 2)
        assert task.kwargs == {}
        assert isinstance(task.signals, TaskSignals)
        assert not task._cancel_requested

    def test_task_successful_execution(self):
        """Test successful task execution."""

        def test_func(x, y, progress_callback=None, cancel_check=None):
            # Report progress
            if progress_callback:
                progress_callback(TaskProgress(current=1, total=2))

            # Check for cancellation
            if cancel_check and cancel_check():
                return None

            return x + y

        task = Task("test_task", test_func, 5, 3)

        # Track signals manually
        started_calls = []
        progress_calls = []
        completed_calls = []
        failed_calls = []

        task.signals.started.connect(lambda task_id: started_calls.append(task_id))
        task.signals.progress.connect(
            lambda task_id, p: progress_calls.append((task_id, p))
        )
        task.signals.completed.connect(
            lambda task_id, r: completed_calls.append((task_id, r))
        )
        task.signals.failed.connect(
            lambda task_id, e, t: failed_calls.append((task_id, e, t))
        )

        # Run the task
        task.run()

        # Check signals
        assert len(started_calls) == 1
        assert started_calls[0] == "test_task"

        assert len(progress_calls) == 1
        assert progress_calls[0][0] == "test_task"
        progress_info = progress_calls[0][1]
        assert progress_info.current == 1
        assert progress_info.total == 2

        assert len(completed_calls) == 1
        assert completed_calls[0][0] == "test_task"
        result = completed_calls[0][1]
        assert result.status == TaskStatus.COMPLETED
        assert result.result == 8

        assert len(failed_calls) == 0


class TestTaskStatus:
    """Test TaskStatus enum."""

    def test_task_status_values(self):
        """Test TaskStatus enum values."""
        assert TaskStatus.PENDING
        assert TaskStatus.RUNNING
        assert TaskStatus.COMPLETED
        assert TaskStatus.FAILED
        assert TaskStatus.CANCELLED
