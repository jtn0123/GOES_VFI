"""Fast, optimized tests for processing state management - critical workflow coordination."""

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

    def start_processing(self, operation_type="video_interpolation") -> None:
        """Start processing operation."""
        if self.is_processing:
            msg = "Already processing"
            raise ValueError(msg)

        self.state = "processing"
        self.is_processing = True
        self.current_operation = operation_type
        self.progress = 0
        self.state_changed.emit(self.state)

    def update_progress(self, progress, message="") -> None:
        """Update processing progress."""
        if not self.is_processing:
            msg = "Not currently processing"
            raise ValueError(msg)

        self.progress = max(0, min(100, progress))
        self.progress_updated.emit(self.progress, message)

    def finish_processing(self, success=True, message="") -> None:
        """Finish processing operation."""
        if not self.is_processing:
            msg = "Not currently processing"
            raise ValueError(msg)

        self.state = "idle"
        self.is_processing = False
        self.current_operation = None
        self.progress = 100 if success else 0

        self.state_changed.emit(self.state)
        self.processing_finished.emit(success, message)


class TestProcessingStateManagement:
    """Test processing state management with fast, mocked operations."""

    @pytest.fixture()
    def processing_vm(self):
        """Create mock processing view model."""
        return MockProcessingViewModel()

    def test_initial_state(self, processing_vm) -> None:
        """Test initial state of processing view model."""
        assert processing_vm.state == "idle"
        assert processing_vm.progress == 0
        assert not processing_vm.is_processing
        assert processing_vm.current_operation is None

    def test_start_processing_state_transition(self, processing_vm) -> None:
        """Test state transition when starting processing."""
        # Track state changes
        state_changes = []
        processing_vm.state_changed.connect(state_changes.append)

        processing_vm.start_processing("video_interpolation")

        assert processing_vm.state == "processing"
        assert processing_vm.is_processing
        assert processing_vm.current_operation == "video_interpolation"
        assert state_changes == ["processing"]

    def test_prevent_concurrent_processing(self, processing_vm) -> None:
        """Test that concurrent processing is prevented."""
        processing_vm.start_processing("operation1")

        # Should raise error when trying to start another operation
        with pytest.raises(ValueError, match="Already processing"):
            processing_vm.start_processing("operation2")

    def test_progress_update_validation(self, processing_vm) -> None:
        """Test progress update validation and bounds checking."""
        processing_vm.start_processing()

        # Track progress updates
        progress_updates = []
        processing_vm.progress_updated.connect(lambda progress, msg: progress_updates.append((progress, msg)))

        # Test normal progress updates
        processing_vm.update_progress(25, "Processing frames")
        processing_vm.update_progress(50, "Interpolating")
        processing_vm.update_progress(75, "Encoding")

        assert processing_vm.progress == 75
        assert len(progress_updates) == 3
        assert progress_updates[0] == (25, "Processing frames")
        assert progress_updates[2] == (75, "Encoding")

    def test_progress_bounds_clamping(self, processing_vm) -> None:
        """Test progress values are clamped to valid range."""
        processing_vm.start_processing()

        # Test out-of-bounds values
        processing_vm.update_progress(-10)  # Should clamp to 0
        assert processing_vm.progress == 0

        processing_vm.update_progress(150)  # Should clamp to 100
        assert processing_vm.progress == 100

    def test_progress_update_without_processing(self, processing_vm) -> None:
        """Test progress update fails when not processing."""
        # Should raise error when not processing
        with pytest.raises(ValueError, match="Not currently processing"):
            processing_vm.update_progress(50)

    def test_finish_processing_success(self, processing_vm) -> None:
        """Test successful processing completion."""
        processing_vm.start_processing()

        # Track completion signals
        completion_signals = []
        processing_vm.processing_finished.connect(lambda success, msg: completion_signals.append((success, msg)))

        state_changes = []
        processing_vm.state_changed.connect(state_changes.append)

        processing_vm.finish_processing(success=True, message="Completed successfully")

        assert processing_vm.state == "idle"
        assert not processing_vm.is_processing
        assert processing_vm.current_operation is None
        assert processing_vm.progress == 100

        assert len(completion_signals) == 1
        assert completion_signals[0] == (True, "Completed successfully")
        assert "idle" in state_changes

    def test_finish_processing_failure(self, processing_vm) -> None:
        """Test failed processing completion."""
        processing_vm.start_processing()

        completion_signals = []
        processing_vm.processing_finished.connect(lambda success, msg: completion_signals.append((success, msg)))

        processing_vm.finish_processing(success=False, message="Processing failed")

        assert processing_vm.state == "idle"
        assert not processing_vm.is_processing
        assert processing_vm.progress == 0  # Reset on failure

        assert len(completion_signals) == 1
        assert completion_signals[0] == (False, "Processing failed")

    def test_finish_without_processing(self, processing_vm) -> None:
        """Test finish fails when not processing."""
        with pytest.raises(ValueError, match="Not currently processing"):
            processing_vm.finish_processing()

    def test_complete_processing_workflow(self, processing_vm) -> None:
        """Test complete processing workflow from start to finish."""
        # Track all signals
        all_signals = []

        def track_state_change(state) -> None:
            all_signals.append(("state_changed", state))

        def track_progress(progress, msg) -> None:
            all_signals.append(("progress_updated", progress, msg))

        def track_finished(success, msg) -> None:
            all_signals.append(("processing_finished", success, msg))

        processing_vm.state_changed.connect(track_state_change)
        processing_vm.progress_updated.connect(track_progress)
        processing_vm.processing_finished.connect(track_finished)

        # Complete workflow
        processing_vm.start_processing("video_interpolation")
        processing_vm.update_progress(25, "Loading frames")
        processing_vm.update_progress(50, "Interpolating")
        processing_vm.update_progress(75, "Encoding")
        processing_vm.finish_processing(True, "Video saved")

        # Verify signal sequence
        expected_signals = [
            ("state_changed", "processing"),
            ("progress_updated", 25, "Loading frames"),
            ("progress_updated", 50, "Interpolating"),
            ("progress_updated", 75, "Encoding"),
            ("state_changed", "idle"),
            ("processing_finished", True, "Video saved"),
        ]

        assert all_signals == expected_signals

    def test_multiple_processing_cycles(self, processing_vm) -> None:
        """Test multiple processing cycles work correctly."""
        for i in range(3):
            # Start processing
            processing_vm.start_processing(f"operation_{i}")
            assert processing_vm.is_processing
            assert processing_vm.current_operation == f"operation_{i}"

            # Update progress
            processing_vm.update_progress(50)
            assert processing_vm.progress == 50

            # Finish processing
            processing_vm.finish_processing(True)
            assert not processing_vm.is_processing
            assert processing_vm.state == "idle"

    def test_error_recovery_state(self, processing_vm) -> None:
        """Test state recovery after errors."""
        processing_vm.start_processing()

        # Simulate error during processing
        try:
            processing_vm.finish_processing(False, "Simulated error")
        except Exception:
            pass  # Ignore any exceptions

        # Should be able to start new processing after error
        assert not processing_vm.is_processing
        processing_vm.start_processing("recovery_operation")
        assert processing_vm.is_processing
        assert processing_vm.current_operation == "recovery_operation"

    def test_signal_connection_performance(self, processing_vm) -> None:
        """Test performance with many signal connections."""
        import time

        # Connect many signal handlers
        handlers = []
        for _i in range(100):
            handler = MagicMock()
            processing_vm.state_changed.connect(handler)
            processing_vm.progress_updated.connect(handler)
            processing_vm.processing_finished.connect(handler)
            handlers.append(handler)

        # Time a complete workflow
        start_time = time.time()

        processing_vm.start_processing()
        processing_vm.update_progress(50)
        processing_vm.finish_processing(True)

        end_time = time.time()

        # Should complete quickly even with many handlers
        assert (end_time - start_time) < 0.1  # Less than 100ms

        # Verify all handlers were called
        for handler in handlers:
            assert handler.call_count > 0
