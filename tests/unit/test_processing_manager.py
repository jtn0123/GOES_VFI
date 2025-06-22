"""Unit tests for the ProcessingManager component."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QApplication

from goesvfi.gui_components.processing_manager import ProcessingManager


class TestProcessingManager(unittest.TestCase):
    """Test cases for ProcessingManager."""

    @classmethod
    def setUpClass(cls):
        """Set up QApplication for all tests."""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        """Set up test fixtures."""
        self.processing_manager = ProcessingManager()

        # Track emitted signals
        self.emitted_signals = {
            "started": False,
            "progress": [],
            "finished": None,
            "error": None,
            "state_changed": [],
        }

        # Connect signals to track emissions
        self.processing_manager.processing_started.connect(
            lambda: self._signal_emitted("started", True)
        )
        self.processing_manager.processing_progress.connect(
            lambda c, t, e: self._signal_emitted("progress", (c, t, e))
        )
        self.processing_manager.processing_finished.connect(
            lambda p: self._signal_emitted("finished", p)
        )
        self.processing_manager.processing_error.connect(
            lambda e: self._signal_emitted("error", e)
        )
        self.processing_manager.processing_state_changed.connect(
            lambda s: self._signal_emitted("state_changed", s)
        )

    def _signal_emitted(self, signal_name, value):
        """Helper to track signal emissions."""
        if signal_name in ["progress", "state_changed"]:
            self.emitted_signals[signal_name].append(value)
        else:
            self.emitted_signals[signal_name] = value

    def tearDown(self):
        """Clean up test fixtures."""
        # Stop any running processing
        if self.processing_manager.is_processing:
            self.processing_manager.stop_processing()

    def test_initialization(self):
        """Test ProcessingManager initialization."""
        self.assertFalse(self.processing_manager.is_processing)
        self.assertIsNone(self.processing_manager.worker_thread)
        self.assertIsNone(self.processing_manager.worker)
        self.assertIsNone(self.processing_manager.current_output_path)

    def test_validate_processing_args_valid(self):
        """Test validation with valid arguments."""
        args = {
            "input_dir": str(Path(__file__).parent),  # Use test directory
            "output_file": "/tmp/test_output.mp4",
            "model_location": str(Path(__file__).parent),  # Use test directory
            "exp": 2,
            "fps": 30,
        }

        is_valid, error = self.processing_manager.validate_processing_args(args)
        self.assertTrue(is_valid)
        self.assertEqual(error, "")

    def test_validate_processing_args_missing_input(self):
        """Test validation with missing input directory."""
        args = {
            "output_file": "/tmp/test_output.mp4",
            "model_location": "/path/to/models",
        }

        is_valid, error = self.processing_manager.validate_processing_args(args)
        self.assertFalse(is_valid)
        self.assertIn("No input directory", error)

    def test_validate_processing_args_invalid_input(self):
        """Test validation with non-existent input directory."""
        args = {
            "input_dir": "/non/existent/directory",
            "output_file": "/tmp/test_output.mp4",
            "model_location": str(Path(__file__).parent),
        }

        is_valid, error = self.processing_manager.validate_processing_args(args)
        self.assertFalse(is_valid)
        self.assertIn("does not exist", error)

    def test_validate_processing_args_invalid_fps(self):
        """Test validation with invalid FPS."""
        args = {
            "input_dir": str(Path(__file__).parent),
            "output_file": "/tmp/test_output.mp4",
            "model_location": str(Path(__file__).parent),
            "fps": 0,  # Invalid
        }

        is_valid, error = self.processing_manager.validate_processing_args(args)
        self.assertFalse(is_valid)
        self.assertIn("FPS must be greater than 0", error)

    def test_validate_processing_args_invalid_exp(self):
        """Test validation with invalid interpolation factor."""
        args = {
            "input_dir": str(Path(__file__).parent),
            "output_file": "/tmp/test_output.mp4",
            "model_location": str(Path(__file__).parent),
            "exp": 0,  # Invalid
        }

        is_valid, error = self.processing_manager.validate_processing_args(args)
        self.assertFalse(is_valid)
        self.assertIn("Interpolation factor must be at least 1", error)

    @patch("goesvfi.gui_components.processing_manager.VfiWorker")
    @patch("goesvfi.gui_components.processing_manager.QThread")
    def test_start_processing_success(self, mock_qthread, mock_worker):
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
        self.assertTrue(result)
        self.assertTrue(self.processing_manager.is_processing)
        self.assertEqual(
            self.processing_manager.current_output_path, Path("/tmp/test_output.mp4")
        )

        # Verify signals were emitted
        self.assertTrue(self.emitted_signals["started"])
        self.assertIn(True, self.emitted_signals["state_changed"])

        # Verify thread was started
        mock_thread_instance.start.assert_called_once()

    def test_start_processing_while_processing(self):
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
        self.assertFalse(result)

    def test_start_processing_missing_required_arg(self):
        """Test starting processing with missing required argument."""
        args = {
            "input_dir": str(Path(__file__).parent),
            # Missing output_file
            "model_location": str(Path(__file__).parent),
        }

        # Try to start processing
        result = self.processing_manager.start_processing(args)

        # Should fail
        self.assertFalse(result)
        self.assertIsNotNone(self.emitted_signals["error"])
        self.assertIn("Missing required argument", self.emitted_signals["error"])

    def test_handle_progress(self):
        """Test handling progress updates."""
        # Simulate progress update
        self.processing_manager._handle_progress(50, 100, 60.0)

        # Verify signal was emitted
        self.assertEqual(len(self.emitted_signals["progress"]), 1)
        self.assertEqual(self.emitted_signals["progress"][0], (50, 100, 60.0))

    def test_handle_finished(self):
        """Test handling processing completion."""
        # Set processing state
        self.processing_manager.is_processing = True

        # Simulate completion
        self.processing_manager._handle_finished("/tmp/output.mp4")

        # Verify state
        self.assertFalse(self.processing_manager.is_processing)
        self.assertEqual(self.emitted_signals["finished"], "/tmp/output.mp4")
        self.assertIn(False, self.emitted_signals["state_changed"])

    def test_handle_error(self):
        """Test handling processing error."""
        # Set processing state
        self.processing_manager.is_processing = True

        # Simulate error
        self.processing_manager._handle_error("Test error message")

        # Verify state
        self.assertFalse(self.processing_manager.is_processing)
        self.assertEqual(self.emitted_signals["error"], "Test error message")
        self.assertIn(False, self.emitted_signals["state_changed"])

    def test_stop_processing_not_running(self):
        """Test stopping when not processing."""
        # Should not crash
        self.processing_manager.stop_processing()

        # Verify nothing changed
        self.assertFalse(self.processing_manager.is_processing)

    @patch("goesvfi.gui_components.processing_manager.QThread")
    def test_stop_processing_running(self, mock_qthread):
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

    def test_get_processing_state(self):
        """Test getting processing state."""
        # Initially false
        self.assertFalse(self.processing_manager.get_processing_state())

        # Set to true
        self.processing_manager.is_processing = True
        self.assertTrue(self.processing_manager.get_processing_state())

    def test_get_current_output_path(self):
        """Test getting current output path."""
        # Initially None
        self.assertIsNone(self.processing_manager.get_current_output_path())

        # Set output path and processing state
        test_path = Path("/tmp/test.mp4")
        self.processing_manager.current_output_path = test_path
        self.processing_manager.is_processing = True

        # Should return path when processing
        self.assertEqual(self.processing_manager.get_current_output_path(), test_path)

        # Should return None when not processing
        self.processing_manager.is_processing = False
        self.assertIsNone(self.processing_manager.get_current_output_path())


if __name__ == "__main__":
    unittest.main()
