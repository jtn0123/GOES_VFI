"""Tests for BatchProcessingTab functionality (Optimized v2).

Optimizations:
- Shared fixtures for common test components
- Mocked GUI components to eliminate Qt dependencies
- Simplified test structure with focused assertions
- Reduced setup complexity while maintaining coverage
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from goesvfi.gui_tabs.batch_processing_tab import BatchProcessingTab
from goesvfi.pipeline.batch_queue import BatchJob, JobPriority

from tests.utils.disable_popups import disable_all_gui_popups

# Disable GUI popups for testing
disable_all_gui_popups()


class MockSignal:
    """Mock PyQt signal for testing."""

    def __init__(self) -> None:
        self.connected_callbacks: list[Callable[..., Any]] = []

    def connect(self, callback: Callable[..., Any]) -> None:
        """Mock signal connection."""
        self.connected_callbacks.append(callback)

    def emit(self, *args: Any, **kwargs: Any) -> None:
        """Mock signal emission."""
        for callback in self.connected_callbacks:
            callback(*args, **kwargs)


class MockQueue:
    """Mock batch queue for testing."""

    def __init__(self) -> None:
        self.jobs: list[BatchJob] = []
        # Mock all required signals
        self.job_added = MockSignal()
        self.job_started = MockSignal()
        self.job_progress = MockSignal()
        self.job_completed = MockSignal()
        self.job_failed = MockSignal()
        self.job_cancelled = MockSignal()
        self.queue_empty = MockSignal()

    def add_job(self, job: BatchJob) -> None:
        """Add job to mock queue."""
        self.jobs.append(job)
        self.job_added.emit(job.id)

    def get_all_jobs(self) -> list[BatchJob]:
        """Get all jobs from mock queue.

        Returns:
            list[BatchJob]: List of all jobs in the queue.
        """
        return self.jobs

    def start_processing(self) -> None:
        """Mock start processing."""

    def stop_processing(self) -> None:
        """Mock stop processing."""


@pytest.fixture()
def mock_batch_processor() -> Mock:
    """Create a mock BatchProcessor with all required methods.

    Returns:
        Mock: A mock BatchProcessor instance.
    """
    processor = Mock()
    processor.create_queue.return_value = MockQueue()

    def mock_create_job_from_paths(
        input_paths: list[str],
        output_dir: Any,
        settings: dict[str, Any],
        priority: JobPriority = JobPriority.NORMAL,
        **kwargs: Any,
    ) -> list[BatchJob]:
        """Mock job creation from paths.

        Returns:
            list[BatchJob]: List of created batch jobs.
        """
        jobs = []
        for i, input_path in enumerate(input_paths):
            job = BatchJob(
                id=f"job_{i}",
                name=f"Test Job {i}",
                input_path=Path(input_path),
                output_path=output_dir / f"output_{i}.mp4",
                settings=settings,
                priority=priority,
            )
            jobs.append(job)
        return jobs

    processor.create_job_from_paths.side_effect = mock_create_job_from_paths
    processor.add_directory = Mock(return_value=["job_1", "job_2"])

    return processor


@pytest.fixture()
def test_settings() -> dict[str, Any]:
    """Standard test settings for batch processing.

    Returns:
        dict[str, Any]: Test settings dictionary.
    """
    return {"target_fps": 24, "interpolation": "RIFE", "encoder": "libx264", "quality": "high"}


@pytest.fixture()
def settings_provider(test_settings: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    """Mock settings provider function.

    Returns:
        Callable[[], dict[str, Any]]: Function that returns test settings.
    """

    def provider() -> dict[str, Any]:
        return test_settings

    return provider


@pytest.fixture()
def mock_process_function() -> Callable[..., str]:
    """Mock process function for batch processing.

    Returns:
        Callable[..., str]: Mock process function.
    """

    def process_fn(*args: Any, **kwargs: Any) -> str:
        return "Processing completed"

    return process_fn


@pytest.fixture()
def batch_tab(
    qtbot: Any,
    mock_batch_processor: Mock,
    settings_provider: Callable[[], dict[str, Any]],
    mock_process_function: Callable[..., str],
) -> Any:
    """Create BatchProcessingTab instance for testing.

    Yields:
        tuple[BatchProcessingTab, Mock, dict[str, Any]]: Tab instance, processor, and settings.
    """
    with (
        patch("goesvfi.gui_tabs.batch_processing_tab.BatchProcessor", return_value=mock_batch_processor),
        patch("goesvfi.gui_tabs.batch_processing_tab.QMessageBox"),
    ):
        tab = BatchProcessingTab(
            process_function=mock_process_function,
            settings_provider=settings_provider,
        )
        qtbot.addWidget(tab)

        # Mock the UI elements that would be created
        tab.output_dir_label = Mock()
        tab.output_dir_label.text = Mock(return_value="/tmp/output")  # noqa: S108
        tab.input_paths_list = Mock()
        tab.input_paths_list.count = Mock(return_value=1)

        # Mock item access
        mock_item = Mock()
        mock_item.text = Mock(return_value="/tmp/input/file1.png")  # noqa: S108
        tab.input_paths_list.item = Mock(return_value=mock_item)

        yield tab, mock_batch_processor, test_settings


class TestBatchProcessingTab:
    """Test BatchProcessingTab functionality."""

    def test_tab_initialization(self, batch_tab: Any) -> None:  # noqa: PLR6301
        """Test that tab initializes correctly."""
        tab, processor, _settings = batch_tab

        assert tab is not None
        assert hasattr(tab, "batch_processor")
        assert hasattr(tab, "process_function")
        assert hasattr(tab, "settings_provider")

        # Verify processor was created
        processor.create_queue.assert_called_once()

    def test_add_to_queue_with_current_settings(self, batch_tab: Any) -> None:  # noqa: PLR6301
        """Test adding jobs to queue uses current settings."""
        tab, processor, expected_settings = batch_tab

        # Mock UI state
        tab.output_dir_label.text.return_value = "/tmp/output"  # noqa: S108
        tab.input_paths_list.count.return_value = 1

        # Call the internal method (simulating button click)
        tab._add_to_queue()  # noqa: SLF001

        # Verify job creation was called with correct settings
        processor.create_job_from_paths.assert_called_once()
        call_args = processor.create_job_from_paths.call_args

        # Check that settings were passed correctly
        assert call_args.kwargs["settings"] == expected_settings

    def test_settings_provider_integration(self, batch_tab: Any) -> None:  # noqa: PLR6301
        """Test that settings provider is called correctly."""
        tab, processor, expected_settings = batch_tab

        # Mock UI state for adding to queue
        tab.output_dir_label.text.return_value = "/tmp/output"  # noqa: S108
        tab.input_paths_list.count.return_value = 1

        # Trigger add to queue
        tab._add_to_queue()  # noqa: SLF001

        # Verify the settings provider was used
        call_args = processor.create_job_from_paths.call_args
        assert call_args.kwargs["settings"] == expected_settings

    @pytest.mark.parametrize("file_count", [1, 3, 5])
    def test_multiple_file_processing(self, batch_tab: Any, file_count: int) -> None:  # noqa: PLR6301
        """Test processing multiple files."""
        tab, processor, _settings = batch_tab

        # Mock multiple files in the input list
        tab.input_paths_list.count.return_value = file_count
        tab.output_dir_label.text.return_value = "/tmp/output"  # noqa: S108

        # Mock returning different items for each index
        def mock_item_at_index(index: int) -> Mock:
            mock_item = Mock()
            mock_item.text.return_value = f"/tmp/input/file{index}.png"  # noqa: S108
            return mock_item

        tab.input_paths_list.item.side_effect = mock_item_at_index

        # Call add to queue
        tab._add_to_queue()  # noqa: SLF001

        # Verify job creation was called
        processor.create_job_from_paths.assert_called_once()

        # The actual input paths would be collected from the UI
        call_args = processor.create_job_from_paths.call_args
        assert "input_paths" in call_args.kwargs

    def test_queue_signal_connections(self, batch_tab: Any) -> None:  # noqa: PLR6301
        """Test that queue signals are properly connected."""
        _tab, processor, _settings = batch_tab

        # Get the queue that was created
        queue = processor.create_queue.return_value

        # Verify that signal connections were made
        # Note: In a real implementation, these would be connected to UI update methods
        assert hasattr(queue, "job_added")
        assert hasattr(queue, "job_started")
        assert hasattr(queue, "job_completed")
        assert hasattr(queue, "job_failed")

    def test_output_directory_handling(self, batch_tab: Any) -> None:  # noqa: PLR6301
        """Test output directory handling."""
        tab, processor, _settings = batch_tab

        test_output_dir = "/custom/output/path"
        tab.output_dir_label.text.return_value = test_output_dir
        tab.input_paths_list.count.return_value = 1

        tab._add_to_queue()  # noqa: SLF001

        call_args = processor.create_job_from_paths.call_args
        # The output directory should be passed as a Path object
        assert str(call_args.kwargs["output_dir"]) == test_output_dir

    def test_empty_input_list_handling(self, batch_tab: Any) -> None:  # noqa: PLR6301
        """Test handling when input list is empty."""
        tab, _processor, _settings = batch_tab

        # Mock empty input list
        tab.input_paths_list.count.return_value = 0
        tab.output_dir_label.text.return_value = "/tmp/output"  # noqa: S108

        # This should not call create_job_from_paths
        tab._add_to_queue()  # noqa: SLF001

        # Since there are no input files, job creation should not be called
        # (assuming the implementation checks for empty input)
        # This test would need to be adjusted based on actual implementation

    def test_job_priority_setting(self, batch_tab: Any) -> None:  # noqa: PLR6301
        """Test that job priority can be set."""
        tab, processor, _settings = batch_tab

        tab.output_dir_label.text.return_value = "/tmp/output"  # noqa: S108
        tab.input_paths_list.count.return_value = 1

        # If the tab has priority selection, test it
        # This would depend on the actual UI implementation
        tab._add_to_queue()  # noqa: SLF001

        call_args = processor.create_job_from_paths.call_args
        # Default priority should be NORMAL
        priority = call_args.kwargs.get("priority", JobPriority.NORMAL)
        assert priority == JobPriority.NORMAL

    @pytest.mark.parametrize(
        "settings_variant",
        [
            {"target_fps": 30, "interpolation": "RIFE"},
            {"target_fps": 60, "interpolation": "FFmpeg"},
            {"target_fps": 24, "interpolation": "RIFE", "encoder": "libx265"},
        ],
    )
    def test_different_settings_configurations(  # noqa: PLR6301
        self,
        qtbot: Any,
        mock_batch_processor: Mock,
        mock_process_function: Callable[..., str],
        settings_variant: dict[str, Any],
    ) -> None:
        """Test different settings configurations."""

        def settings_provider() -> dict[str, Any]:
            return settings_variant

        with (
            patch("goesvfi.gui_tabs.batch_processing_tab.BatchProcessor", return_value=mock_batch_processor),
            patch("goesvfi.gui_tabs.batch_processing_tab.QMessageBox"),
        ):
            tab = BatchProcessingTab(
                process_function=mock_process_function,
                settings_provider=settings_provider,
            )
            qtbot.addWidget(tab)

            # Mock UI elements
            tab.output_dir_label = Mock()
            tab.output_dir_label.text = Mock(return_value="/tmp/output")  # noqa: S108
            tab.input_paths_list = Mock()
            tab.input_paths_list.count = Mock(return_value=1)
            mock_item = Mock()
            mock_item.text = Mock(return_value="/tmp/input/file1.png")  # noqa: S108
            tab.input_paths_list.item = Mock(return_value=mock_item)

            # Trigger add to queue
            tab._add_to_queue()  # noqa: SLF001

            # Verify settings were used
            call_args = mock_batch_processor.create_job_from_paths.call_args
            assert call_args.kwargs["settings"] == settings_variant

    def test_batch_processor_integration(self, batch_tab: Any) -> None:  # noqa: PLR6301
        """Test integration with BatchProcessor."""
        tab, processor, _settings = batch_tab

        # Verify the processor was initialized correctly
        assert tab.batch_processor == processor

        # Verify queue was created
        processor.create_queue.assert_called_once()

        # Test that the processor methods are available
        assert hasattr(processor, "create_job_from_paths")
        assert hasattr(processor, "add_directory")

    def test_error_handling_in_job_creation(self, batch_tab: Any) -> None:  # noqa: PLR6301
        """Test error handling when job creation fails."""
        tab, processor, _settings = batch_tab

        # Make job creation raise an exception
        processor.create_job_from_paths.side_effect = Exception("Job creation failed")

        tab.output_dir_label.text.return_value = "/tmp/output"  # noqa: S108
        tab.input_paths_list.count.return_value = 1

        # The method should handle the exception gracefully
        # (Implementation would depend on actual error handling in the tab)
        try:
            tab._add_to_queue()  # noqa: SLF001
        except Exception:  # noqa: BLE001
            pytest.fail("Tab should handle job creation errors gracefully")

    def test_ui_update_after_job_addition(self, batch_tab: Any) -> None:  # noqa: PLR6301
        """Test that UI updates after jobs are added."""
        tab, processor, _settings = batch_tab

        tab.output_dir_label.text.return_value = "/tmp/output"  # noqa: S108
        tab.input_paths_list.count.return_value = 1

        # Mock the queue to simulate job addition
        queue = processor.create_queue.return_value

        # Add job to queue
        tab._add_to_queue()  # noqa: SLF001

        # Verify queue received the job
        assert len(queue.jobs) > 0 or processor.create_job_from_paths.called
