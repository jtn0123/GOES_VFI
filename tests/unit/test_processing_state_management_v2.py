"""Fast, optimized tests for processing state management - Optimized v2."""

import contextlib
import time
from typing import Any
from unittest.mock import MagicMock

from PyQt6.QtCore import QObject, pyqtSignal
import pytest


class MockProcessingViewModel(QObject):
    """Mock processing view model for testing state transitions."""

    # Signals
    state_changed = pyqtSignal(str)
    progress_updated = pyqtSignal(int, str)
    processing_finished = pyqtSignal(bool, str)

    def __init__(self) -> None:
        super().__init__()
        self.state = "idle"
        self.progress = 0
        self.is_processing = False
        self.current_operation = None

    def start_processing(self, operation_type: str = "video_interpolation") -> None:
        """Start processing operation.

        Raises:
            ValueError: If already processing.
        """
        if self.is_processing:
            msg = "Already processing"
            raise ValueError(msg)

        self.state = "processing"
        self.is_processing = True
        self.current_operation = operation_type
        self.progress = 0
        self.state_changed.emit(self.state)

    def update_progress(self, progress: int, message: str = "") -> None:
        """Update processing progress.

        Raises:
            ValueError: If not currently processing.
        """
        if not self.is_processing:
            msg = "Not currently processing"
            raise ValueError(msg)

        self.progress = max(0, min(100, progress))
        self.progress_updated.emit(self.progress, message)

    def finish_processing(self, *, success: bool = True, message: str = "") -> None:
        """Finish processing operation.

        Raises:
            ValueError: If not currently processing.
        """
        if not self.is_processing:
            msg = "Not currently processing"
            raise ValueError(msg)

        self.state = "idle"
        self.is_processing = False
        self.current_operation = None
        self.progress = 100 if success else 0

        self.state_changed.emit(self.state)
        self.processing_finished.emit(success, message)


# Shared fixtures and test data
@pytest.fixture(scope="session")
def operation_scenarios() -> dict[str, str]:
    """Pre-defined operation scenarios for testing.

    Returns:
        dict[str, str]: Operation scenarios.
    """
    return {
        "video_interpolation": "video_interpolation",
        "image_processing": "image_processing",
        "batch_operation": "batch_operation",
    }


@pytest.fixture(scope="session")
def progress_sequences() -> dict[str, list[tuple[int, str]]]:
    """Pre-defined progress sequences for testing.

    Returns:
        dict[str, list[tuple[int, str]]]: Progress sequences.
    """
    return {
        "normal": [(25, "Loading frames"), (50, "Interpolating"), (75, "Encoding")],
        "simple": [(50, "Processing")],
        "detailed": [(10, "Init"), (30, "Load"), (60, "Process"), (90, "Save")],
    }


@pytest.fixture()
def processing_vm() -> MockProcessingViewModel:
    """Create mock processing view model.

    Returns:
        MockProcessingViewModel: Mock processing view model.
    """
    return MockProcessingViewModel()


class TestProcessingStateManagement:
    """Test processing state management with optimized patterns."""

    def test_initial_state(self, processing_vm: MockProcessingViewModel) -> None:  # noqa: PLR6301
        """Test initial state of processing view model."""
        assert processing_vm.state == "idle"
        assert processing_vm.progress == 0
        assert not processing_vm.is_processing
        assert processing_vm.current_operation is None

    @pytest.mark.parametrize("operation_type", ["video_interpolation", "image_processing", "batch_operation"])
    def test_start_processing_state_transition(
        self, processing_vm: MockProcessingViewModel, operation_type: str
    ) -> None:
        """Test state transition when starting different types of processing."""
        state_changes = []
        processing_vm.state_changed.connect(state_changes.append)

        processing_vm.start_processing(operation_type)

        assert processing_vm.state == "processing"
        assert processing_vm.is_processing
        assert processing_vm.current_operation == operation_type
        assert state_changes == ["processing"]

    def test_prevent_concurrent_processing(self, processing_vm: MockProcessingViewModel) -> None:  # noqa: PLR6301
        """Test that concurrent processing is prevented."""
        processing_vm.start_processing("operation1")

        # Should raise error when trying to start another operation
        with pytest.raises(ValueError, match="Already processing"):
            processing_vm.start_processing("operation2")

    @pytest.mark.parametrize(
        "progress_sequence",
        [
            "normal",
            "simple",
            "detailed",
        ],
    )
    def test_progress_update_sequences(
        self, processing_vm: MockProcessingViewModel, progress_sequences: Any, progress_sequence: str
    ) -> None:
        """Test progress update with different sequences."""
        processing_vm.start_processing()

        progress_updates = []
        processing_vm.progress_updated.connect(lambda progress, msg: progress_updates.append((progress, msg)))

        sequence = progress_sequences[progress_sequence]
        for progress, message in sequence:
            processing_vm.update_progress(progress, message)

        assert processing_vm.progress == sequence[-1][0]  # Should be last progress value
        assert len(progress_updates) == len(sequence)

        # Verify all updates were recorded correctly
        for i, (expected_progress, expected_msg) in enumerate(sequence):
            assert progress_updates[i] == (expected_progress, expected_msg)

    @pytest.mark.parametrize(
        "progress_value,expected_clamped",
        [
            (-10, 0),  # Negative should clamp to 0
            (50, 50),  # Normal value should remain
            (150, 100),  # Over 100 should clamp to 100
            (0, 0),  # Zero should remain
            (100, 100),  # Max should remain
        ],
    )
    def test_progress_bounds_clamping(
        self, processing_vm: MockProcessingViewModel, progress_value: int, expected_clamped: int
    ) -> None:
        """Test progress values are clamped to valid range."""
        processing_vm.start_processing()

        processing_vm.update_progress(progress_value)
        assert processing_vm.progress == expected_clamped

    def test_progress_update_without_processing(self, processing_vm: MockProcessingViewModel) -> None:  # noqa: PLR6301
        """Test progress update fails when not processing."""
        # Should raise error when not processing
        with pytest.raises(ValueError, match="Not currently processing"):
            processing_vm.update_progress(50)

    @pytest.mark.parametrize(
        "success,expected_progress",
        [
            (True, 100),  # Successful completion sets progress to 100
            (False, 0),  # Failed completion resets progress to 0
        ],
    )
    def test_finish_processing_outcomes(
        self, processing_vm: MockProcessingViewModel, success: bool, expected_progress: int
    ) -> None:
        """Test processing completion with different outcomes."""
        processing_vm.start_processing()

        # Track completion signals
        completion_signals = []
        processing_vm.processing_finished.connect(lambda success, msg: completion_signals.append((success, msg)))

        state_changes = []
        processing_vm.state_changed.connect(state_changes.append)

        test_message = "Completed successfully" if success else "Processing failed"
        processing_vm.finish_processing(success=success, message=test_message)

        assert processing_vm.state == "idle"
        assert not processing_vm.is_processing
        assert processing_vm.current_operation is None
        assert processing_vm.progress == expected_progress

        assert len(completion_signals) == 1
        assert completion_signals[0] == (success, test_message)
        assert "idle" in state_changes

    def test_finish_without_processing(self, processing_vm: MockProcessingViewModel) -> None:  # noqa: PLR6301
        """Test finish fails when not processing."""
        with pytest.raises(ValueError, match="Not currently processing"):
            processing_vm.finish_processing()

    @pytest.mark.parametrize(
        "workflow_steps",
        [
            [
                ("start", "video_interpolation"),
                ("progress", 25, "Loading frames"),
                ("progress", 50, "Interpolating"),
                ("progress", 75, "Encoding"),
                ("finish", True, "Video saved"),
            ],
            [
                ("start", "image_processing"),
                ("progress", 100, "Complete"),
                ("finish", True, "Success"),
            ],
            [
                ("start", "batch_operation"),
                ("progress", 30, "Processing"),
                ("finish", False, "Error occurred"),
            ],
        ],
    )
    def test_complete_processing_workflows(
        self, processing_vm: MockProcessingViewModel, workflow_steps: list[tuple]
    ) -> None:
        """Test complete processing workflows from start to finish."""
        # Track all signals
        all_signals = []

        def track_state_change(state: str) -> None:
            all_signals.append(("state_changed", state))

        def track_progress(progress: int, msg: str) -> None:
            all_signals.append(("progress_updated", progress, msg))

        def track_finished(success: bool, msg: str) -> None:  # noqa: FBT001
            all_signals.append(("processing_finished", success, msg))

        processing_vm.state_changed.connect(track_state_change)
        processing_vm.progress_updated.connect(track_progress)
        processing_vm.processing_finished.connect(track_finished)

        # Execute workflow steps
        for step in workflow_steps:
            action = step[0]
            if action == "start":
                processing_vm.start_processing(step[1])
            elif action == "progress":
                processing_vm.update_progress(step[1], step[2])
            elif action == "finish":
                processing_vm.finish_processing(success=step[1], message=step[2])

        # Verify signals were emitted in correct sequence
        expected_signal_count = len([s for s in workflow_steps if s[0] != "start"]) + 2  # +2 for start signals
        assert len(all_signals) >= expected_signal_count

        # Should start and end with state changes
        assert all_signals[0][0] == "state_changed"
        assert all_signals[-2][0] == "state_changed"  # Second to last should be state change
        assert all_signals[-1][0] == "processing_finished"  # Last should be finish signal

    @pytest.mark.parametrize("cycle_count", [1, 3, 5])
    def test_multiple_processing_cycles(self, processing_vm: MockProcessingViewModel, cycle_count: int) -> None:  # noqa: PLR6301
        """Test multiple processing cycles work correctly."""
        for i in range(cycle_count):
            # Start processing
            processing_vm.start_processing(f"operation_{i}")
            assert processing_vm.is_processing
            assert processing_vm.current_operation == f"operation_{i}"

            # Update progress
            processing_vm.update_progress(50)
            assert processing_vm.progress == 50

            # Finish processing
            processing_vm.finish_processing(success=True)
            assert not processing_vm.is_processing
            assert processing_vm.state == "idle"

    def test_error_recovery_state(self, processing_vm: MockProcessingViewModel) -> None:  # noqa: PLR6301
        """Test state recovery after errors."""
        processing_vm.start_processing()

        # Simulate error during processing
        with contextlib.suppress(Exception):
            processing_vm.finish_processing(success=False, message="Simulated error")

        # Should be able to start new processing after error
        assert not processing_vm.is_processing
        processing_vm.start_processing("recovery_operation")
        assert processing_vm.is_processing
        assert processing_vm.current_operation == "recovery_operation"

    @pytest.mark.parametrize("handler_count", [10, 50, 100])
    def test_signal_connection_performance(self, processing_vm: MockProcessingViewModel, handler_count: int) -> None:  # noqa: PLR6301
        """Test performance with many signal connections."""
        # Connect many signal handlers
        handlers = []
        for _i in range(handler_count):
            handler = MagicMock()
            processing_vm.state_changed.connect(handler)
            processing_vm.progress_updated.connect(handler)
            processing_vm.processing_finished.connect(handler)
            handlers.append(handler)

        # Time a complete workflow
        start_time = time.time()

        processing_vm.start_processing()
        processing_vm.update_progress(50)
        processing_vm.finish_processing(success=True)

        end_time = time.time()

        # Should complete quickly even with many handlers
        assert (end_time - start_time) < 0.1  # Less than 100ms

        # Verify all handlers were called
        for handler in handlers:
            assert handler.call_count > 0

    @pytest.mark.parametrize(
        "stress_operations",
        [
            10,  # Light stress test
            25,  # Medium stress test
            50,  # Heavy stress test
        ],
    )
    def test_state_management_stress(self, processing_vm: MockProcessingViewModel, stress_operations: int) -> None:  # noqa: PLR6301
        """Test state management under stress conditions."""
        signal_counts = {"state": 0, "progress": 0, "finished": 0}

        def count_state(_: Any) -> None:
            signal_counts["state"] += 1

        def count_progress(_: Any, __: Any) -> None:
            signal_counts["progress"] += 1

        def count_finished(_: Any, __: Any) -> None:
            signal_counts["finished"] += 1

        processing_vm.state_changed.connect(count_state)
        processing_vm.progress_updated.connect(count_progress)
        processing_vm.processing_finished.connect(count_finished)

        # Perform many rapid operations
        for i in range(stress_operations):
            processing_vm.start_processing(f"stress_op_{i}")
            processing_vm.update_progress(i % 100)
            processing_vm.finish_processing(success=True)

        # Verify state remained consistent
        assert not processing_vm.is_processing
        assert processing_vm.state == "idle"

        # Verify signal counts
        assert signal_counts["state"] == stress_operations * 2  # start + finish for each
        assert signal_counts["progress"] == stress_operations
        assert signal_counts["finished"] == stress_operations
