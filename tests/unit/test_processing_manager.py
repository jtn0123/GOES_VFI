"""Unit tests for the ProcessingManager component."""

from pathlib import Path
from typing import Any, cast
import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication

from goesvfi.gui_components.processing_manager import ProcessingManager


class TestProcessingManager(unittest.TestCase):
    """Test cases for ProcessingManager."""

    app: QApplication

    @classmethod
    def setUpClass(cls) -> None:
        """Set up QApplication for all tests."""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = cast("QApplication", QApplication.instance())

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.processing_manager = ProcessingManager()

        # Track emitted signals
        self.emitted_signals: dict[str, bool | list[Any] | Any] = {
            "started": False,
            "progress": [],
            "finished": None,
            "error": None,
            "state_changed": [],
        }

        # Connect signals to track emissions
        self.processing_manager.processing_started.connect(lambda: self._signal_emitted("started", True))
        self.processing_manager.processing_progress.connect(lambda c, t, e: self._signal_emitted("progress", (c, t, e)))
        self.processing_manager.processing_finished.connect(lambda p: self._signal_emitted("finished", p))
        self.processing_manager.processing_error.connect(lambda e: self._signal_emitted("error", e))
        self.processing_manager.processing_state_changed.connect(lambda s: self._signal_emitted("state_changed", s))

    def _signal_emitted(self, signal_name: str, value: Any) -> None:
        """Helper to track signal emissions."""
        if signal_name in {"progress", "state_changed"}:
            signal_list = self.emitted_signals[signal_name]
            if isinstance(signal_list, list):
                signal_list.append(value)
        else:
            self.emitted_signals[signal_name] = value

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        # Stop any running processing
        if self.processing_manager.is_processing:
            self.processing_manager.stop_processing()

    def test_initialization(self) -> None:
        """Test ProcessingManager initialization."""
        assert not self.processing_manager.is_processing
        assert self.processing_manager.worker_thread is None
        assert self.processing_manager.worker is None
        assert self.processing_manager.current_output_path is None

    def test_validate_processing_args_valid(self) -> None:
        """Test validation with valid arguments."""
        args = {
            "input_dir": str(Path(__file__).parent),  # Use test directory
            "output_file": "/tmp/test_output.mp4",
            "model_location": str(Path(__file__).parent),  # Use test directory
            "exp": 2,
            "fps": 30,
        }

        is_valid, error = self.processing_manager.validate_processing_args(args)
        assert is_valid
        assert error == ""

    def test_validate_processing_args_missing_input(self) -> None:
        """Test validation with missing input directory."""
        args = {
            "output_file": "/tmp/test_output.mp4",
            "model_location": "/path/to/models",
        }

        is_valid, error = self.processing_manager.validate_processing_args(args)
        assert not is_valid
        assert "No input directory" in error

    def test_validate_processing_args_invalid_input(self) -> None:
        """Test validation with non-existent input directory."""
        args = {
            "input_dir": "/non/existent/directory",
            "output_file": "/tmp/test_output.mp4",
            "model_location": str(Path(__file__).parent),
        }

        is_valid, error = self.processing_manager.validate_processing_args(args)
        assert not is_valid
        assert "does not exist" in error

    def test_validate_processing_args_invalid_fps(self) -> None:
        """Test validation with invalid FPS."""
        args = {
            "input_dir": str(Path(__file__).parent),
            "output_file": "/tmp/test_output.mp4",
            "model_location": str(Path(__file__).parent),
            "fps": 0,  # Invalid
        }

        is_valid, error = self.processing_manager.validate_processing_args(args)
        assert not is_valid
        assert "FPS must be greater than 0" in error

    def test_validate_processing_args_invalid_exp(self) -> None:
        """Test validation with invalid interpolation factor."""
        args = {
            "input_dir": str(Path(__file__).parent),
            "output_file": "/tmp/test_output.mp4",
            "model_location": str(Path(__file__).parent),
            "exp": 0,  # Invalid
        }

        is_valid, error = self.processing_manager.validate_processing_args(args)
        assert not is_valid
        assert "Interpolation factor must be at least 1" in error

    @patch("goesvfi.gui_components.processing_manager.VfiWorker")
    @patch("goesvfi.gui_components.processing_manager.QThread")
    def test_start_processing_success(self, mock_qthread, mock_worker) -> None:
        """Test starting processing successfully."""
        # Setup mocks
        mock_thread_instance = MagicMock()
        mock_qthread.return_value = mock_thread_instance
        mock_worker_instance = MagicMock()
        mock_worker.return_value = mock_worker_instance

        args = {
            "input_dir": str(Path(__file__).parent),
            "output_file": "/tmp/test_output.mp4",
            "model_location": str(Path(__file__).parent),
        }

        # Start processing
        result = self.processing_manager.start_processing(args)

        # Verify
        assert result
        assert self.processing_manager.is_processing
        assert self.processing_manager.current_output_path == Path("/tmp/test_output.mp4")

        # Verify signals were emitted
        assert self.emitted_signals["started"]
        state_changes = cast("list[Any]", self.emitted_signals["state_changed"])
        assert isinstance(state_changes, list)
        assert True in state_changes

        # Verify thread was started
        mock_thread_instance.start.assert_called_once()

    def test_start_processing_while_processing(self) -> None:
        """Test starting processing while already processing."""
        # Set processing state
        self.processing_manager.is_processing = True

        args = {
            "input_dir": str(Path(__file__).parent),
            "output_file": "/tmp/test_output.mp4",
            "model_location": str(Path(__file__).parent),
        }

        # Try to start processing
        result = self.processing_manager.start_processing(args)

        # Should fail
        assert not result

    def test_start_processing_missing_required_arg(self) -> None:
        """Test starting processing with missing required argument."""
        args = {
            "input_dir": str(Path(__file__).parent),
            # Missing output_file
            "model_location": str(Path(__file__).parent),
        }

        # Try to start processing
        result = self.processing_manager.start_processing(args)

        # Should fail
        assert not result
        error_msg = self.emitted_signals["error"]
        assert error_msg is not None
        assert isinstance(error_msg, str)
        assert "Missing required argument" in error_msg

    def test_handle_progress(self) -> None:
        """Test handling progress updates."""
        # Simulate progress update
        self.processing_manager._handle_progress(50, 100, 60.0)

        # Verify signal was emitted
        progress_list = cast("list[Any]", self.emitted_signals["progress"])
        assert isinstance(progress_list, list)
        assert len(progress_list) == 1
        assert progress_list[0] == (50, 100, 60.0)

    def test_handle_finished(self) -> None:
        """Test handling processing completion."""
        # Set processing state
        self.processing_manager.is_processing = True

        # Simulate completion
        self.processing_manager._handle_finished("/tmp/output.mp4")

        # Verify state
        assert not self.processing_manager.is_processing
        assert self.emitted_signals["finished"] == "/tmp/output.mp4"
        state_changes = cast("list[Any]", self.emitted_signals["state_changed"])
        assert isinstance(state_changes, list)
        assert False in state_changes

    def test_handle_error(self) -> None:
        """Test handling processing error."""
        # Set processing state
        self.processing_manager.is_processing = True

        # Simulate error
        self.processing_manager._handle_error("Test error message")

        # Verify state
        assert not self.processing_manager.is_processing
        assert self.emitted_signals["error"] == "Test error message"
        state_changes = cast("list[Any]", self.emitted_signals["state_changed"])
        assert isinstance(state_changes, list)
        assert False in state_changes

    def test_stop_processing_not_running(self) -> None:
        """Test stopping when not processing."""
        # Should not crash
        self.processing_manager.stop_processing()

        # Verify nothing changed
        assert not self.processing_manager.is_processing

    @patch("goesvfi.gui_components.processing_manager.QThread")
    def test_stop_processing_running(self, mock_qthread) -> None:
        """Test stopping active processing."""
        # Setup mock thread
        mock_thread = MagicMock()
        mock_thread.isRunning.return_value = True
        mock_thread.wait.return_value = True

        # Set up processing state
        self.processing_manager.worker_thread = mock_thread
        self.processing_manager.worker = MagicMock()
        self.processing_manager.is_processing = True

        # Stop processing
        self.processing_manager.stop_processing()

        # Verify thread was waited on
        mock_thread.wait.assert_called_once_with(5000)

    def test_get_processing_state(self) -> None:
        """Test getting processing state."""
        # Initially false
        assert not self.processing_manager.get_processing_state()

        # Set to true
        self.processing_manager.is_processing = True
        assert self.processing_manager.get_processing_state()

    def test_get_current_output_path(self) -> None:
        """Test getting current output path."""
        # Initially None
        assert self.processing_manager.get_current_output_path() is None

        # Set output path and processing state
        test_path = Path("/tmp/test.mp4")
        self.processing_manager.current_output_path = test_path
        self.processing_manager.is_processing = True

        # Should return path when processing
        assert self.processing_manager.get_current_output_path() == test_path

        # Should return None when not processing
        self.processing_manager.is_processing = False
        assert self.processing_manager.get_current_output_path() is None


if __name__ == "__main__":
    unittest.main()
