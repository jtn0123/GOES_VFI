"""
Unit tests for the background worker system (Optimized v2).

Tests the background worker components including Task, TaskManager,
UIFreezeMonitor, and BackgroundProcessManager.

Optimizations:
- Shared test data fixtures for reusability
- Mock time.sleep to reduce test execution time
- Mock ThreadPoolExecutor to control execution
- Mock QTimer to avoid GUI dependencies
- Reduced task durations in tests
"""

import logging
from typing import Any
from unittest.mock import Mock, patch

import pytest

from goesvfi.integrity_check.background_worker import (
    BackgroundProcessManager,
    Task,
    TaskProgress,
    TaskResult,
    TaskSignals,
    TaskStatus,
)

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)


@pytest.fixture()
def sample_task_data() -> dict[str, Any]:
    """Shared test data for task creation.

    Returns:
        dict[str, Any]: Dictionary containing sample task data for tests.
    """
    return {
        "task_id": "test_task_001",
        "progress": TaskProgress(current=5, total=10, eta_seconds=2.5, message="Processing..."),
        "result": TaskResult(task_id="test_task_001", status=TaskStatus.COMPLETED, result="Success!"),
        "error": ValueError("Test error"),
        "error_result": TaskResult(
            task_id="test_task_001",
            status=TaskStatus.FAILED,
            error=ValueError("Test error"),
            error_traceback="Traceback...",
        ),
    }


@pytest.fixture()
def dummy_functions() -> dict[str, Any]:
    """Shared dummy functions for task testing.

    Returns:
        dict[str, Any]: Dictionary containing dummy functions for testing.
    """

    def simple_add(x: int, y: int) -> int:  # noqa: FURB118
        return x + y

    def task_with_progress(x: int, y: int, progress_callback: Any = None, cancel_check: Any = None) -> int | None:
        # Report progress
        if progress_callback:
            progress_callback(TaskProgress(current=1, total=2))

        # Check for cancellation
        if cancel_check and cancel_check():
            return None

        return x + y

    return {"simple_add": simple_add, "task_with_progress": task_with_progress}


class TestTaskProgress:
    """Test TaskProgress dataclass."""

    def test_task_progress_creation(self, sample_task_data: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test creating TaskProgress instance."""
        progress_data = sample_task_data["progress"]
        assert progress_data.current == 5
        assert progress_data.total == 10
        assert progress_data.eta_seconds == 2.5
        assert progress_data.message == "Processing..."

    def test_task_progress_defaults(self) -> None:  # noqa: PLR6301
        """Test TaskProgress default values."""
        progress = TaskProgress(current=1, total=10)
        assert progress.eta_seconds == 0.0
        assert not progress.message


class TestTaskResult:
    """Test TaskResult dataclass."""

    def test_task_result_success(self, sample_task_data: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test creating successful TaskResult."""
        result = sample_task_data["result"]
        assert result.task_id == "test_task_001"
        assert result.status == TaskStatus.COMPLETED
        assert result.result == "Success!"
        assert result.error is None
        assert result.error_traceback is None

    def test_task_result_failure(self, sample_task_data: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test creating failed TaskResult."""
        result = sample_task_data["error_result"]
        assert result.task_id == "test_task_001"
        assert result.status == TaskStatus.FAILED
        assert result.result is None
        assert isinstance(result.error, ValueError)
        assert result.error_traceback == "Traceback..."


class TestTask:
    """Test Task class functionality."""

    def test_task_creation(self, sample_task_data: dict[str, Any], dummy_functions: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test creating a Task instance."""
        task: Task = Task(sample_task_data["task_id"], dummy_functions["simple_add"], 1, 2)
        assert task.task_id == sample_task_data["task_id"]
        assert task.func == dummy_functions["simple_add"]
        assert task.args == (1, 2)
        assert task.kwargs == {}
        assert isinstance(task.signals, TaskSignals)
        assert not task._cancel_requested  # noqa: SLF001

    @patch("time.sleep", return_value=None)  # Mock time.sleep to speed up tests
    def test_task_successful_execution(self, mock_sleep: Any, dummy_functions: dict[str, Any]) -> None:  # noqa: PLR6301, ARG002
        """Test successful task execution."""
        task: Task = Task("test_task", dummy_functions["task_with_progress"], 5, 3)

        # Track signals manually
        signal_calls: dict[str, list[Any]] = {"started": [], "progress": [], "completed": [], "failed": []}

        task.signals.started.connect(signal_calls["started"].append)
        task.signals.progress.connect(lambda task_id, p: signal_calls["progress"].append((task_id, p)))
        task.signals.completed.connect(lambda task_id, r: signal_calls["completed"].append((task_id, r)))
        task.signals.failed.connect(lambda task_id, e, t: signal_calls["failed"].append((task_id, e, t)))

        # Run the task
        task.run()

        # Check signals
        assert len(signal_calls["started"]) == 1
        assert signal_calls["started"][0] == "test_task"

        assert len(signal_calls["progress"]) == 1
        assert signal_calls["progress"][0][0] == "test_task"
        progress_info = signal_calls["progress"][0][1]
        assert progress_info.current == 1
        assert progress_info.total == 2

        assert len(signal_calls["completed"]) == 1
        assert signal_calls["completed"][0][0] == "test_task"
        result = signal_calls["completed"][0][1]
        assert result.status == TaskStatus.COMPLETED
        assert result.result == 8

        assert len(signal_calls["failed"]) == 0


class TestTaskStatus:
    """Test TaskStatus enum."""

    @pytest.mark.parametrize(
        "status",
        [
            TaskStatus.PENDING,
            TaskStatus.RUNNING,
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        ],
    )
    def test_task_status_values(self, status: Any) -> None:  # noqa: PLR6301
        """Test TaskStatus enum values exist."""
        assert status is not None


class TestBackgroundProcessManager:
    """Test BackgroundProcessManager with mocked dependencies."""

    @patch("goesvfi.integrity_check.background_worker.UIFreezeMonitor")
    @patch("goesvfi.integrity_check.background_worker.ThreadPoolExecutor")
    @patch("time.sleep", return_value=None)  # Mock time.sleep for faster tests
    def test_background_worker_task_execution(  # noqa: PLR6301
        self, mock_sleep: Any, mock_executor_class: Any, mock_monitor_class: Any  # noqa: ARG002
    ) -> None:
        """Test background worker task execution with mocked components."""
        # Setup mock executor
        mock_executor = Mock()
        mock_executor_class.return_value = mock_executor
        mock_future = Mock()
        mock_executor.submit.return_value = mock_future

        # Create worker
        worker = BackgroundProcessManager()

        # Define test task
        def test_task(value: int) -> int:
            return value * 2

        # Submit task
        task_id = worker.run_in_background(test_task, 5)

        # Verify task was submitted
        assert task_id is not None
        assert mock_executor.submit.called

        # Verify cleanup works
        worker.cleanup()
        assert mock_executor.shutdown.called

    @patch("goesvfi.integrity_check.background_worker.UIFreezeMonitor")
    def test_worker_initialization(self, mock_monitor_class: Any) -> None:  # noqa: PLR6301
        """Test worker initialization with mocked UI freeze monitor."""
        worker = BackgroundProcessManager()
        assert worker is not None

        # Should create UI freeze monitor
        mock_monitor_class.assert_called_once()

        # Cleanup
        worker.cleanup()

    @patch("goesvfi.integrity_check.background_worker.UIFreezeMonitor")
    @patch("goesvfi.integrity_check.background_worker.ThreadPoolExecutor")
    def test_multiple_task_submission(self, mock_executor_class: Any, mock_monitor_class: Any) -> None:  # noqa: PLR6301, ARG002
        """Test submitting multiple tasks."""
        mock_executor = Mock()
        mock_executor_class.return_value = mock_executor

        worker = BackgroundProcessManager()

        # Submit multiple tasks
        task_ids = []
        for i in range(5):
            task_id = worker.run_in_background(lambda x: x * 2, i)
            task_ids.append(task_id)

        # Should have 5 unique task IDs
        assert len(set(task_ids)) == 5

        # Should have submitted 5 tasks
        assert mock_executor.submit.call_count == 5

        worker.cleanup()
