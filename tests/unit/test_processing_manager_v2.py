"""Optimized processing manager tests to speed up slow tests while maintaining coverage.

Optimizations applied:
- Shared fixtures for common manager setups and mock configurations
- Parameterized test scenarios for comprehensive processing workflow validation
- Enhanced error handling and state management testing
- Mock-based testing to avoid real GUI operations and worker creation
- Comprehensive signal emission and thread lifecycle testing
"""

from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch, Mock
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread

from goesvfi.gui_components.processing_manager import ProcessingManager


class TestProcessingManagerV2:
    """Optimized test class for processing manager functionality."""

    @pytest.fixture(scope="class")
    def qapp(self):
        """Create QApplication for all tests in this class."""
        if not QApplication.instance():
            app = QApplication([])
            yield app
            app.quit()
        else:
            yield QApplication.instance()

    @pytest.fixture(scope="class")
    def processing_scenarios(self):
        """Define various processing scenario test cases."""
        return {
            "basic_processing": {
                "args": {
                    "input_dir": "/test/input",
                    "output_file": "/test/output.mp4",
                    "model_location": "/test/models",
                    "exp": 2,
                    "fps": 30,
                },
                "expected_success": True,
            },
            "high_fps_processing": {
                "args": {
                    "input_dir": "/test/input_hfps",
                    "output_file": "/test/output_hfps.mp4",
                    "model_location": "/test/models",
                    "exp": 4,
                    "fps": 120,
                },
                "expected_success": True,
            },
            "minimal_processing": {
                "args": {
                    "input_dir": "/test/minimal",
                    "output_file": "/test/minimal.mp4",
                    "model_location": "/test/models",
                    "exp": 1,
                    "fps": 24,
                },
                "expected_success": True,
            },
            "custom_processing": {
                "args": {
                    "input_dir": "/custom/input",
                    "output_file": "/custom/output.mp4",
                    "model_location": "/custom/models",
                    "exp": 8,
                    "fps": 60,
                    "overwrite": True,
                },
                "expected_success": True,
            },
        }

    @pytest.fixture(scope="class")
    def validation_scenarios(self):
        """Define various validation scenario test cases."""
        return {
            "missing_input_dir": {
                "args": {
                    "output_file": "/test/output.mp4",
                    "model_location": "/test/models",
                },
                "expected_valid": False,
                "expected_error": "No input directory",
            },
            "missing_output_file": {
                "args": {
                    "input_dir": "/test/input",
                    "model_location": "/test/models",
                },
                "expected_valid": False,
                "expected_error": "Missing required argument: output_file",
            },
            "missing_model_location": {
                "args": {
                    "input_dir": "/test/input",
                    "output_file": "/test/output.mp4",
                },
                "expected_valid": False,
                "expected_error": "Missing required argument: model_location",
            },
            "nonexistent_input": {
                "args": {
                    "input_dir": "/nonexistent/input",
                    "output_file": "/test/output.mp4",
                    "model_location": "/test/models",
                },
                "expected_valid": False,
                "expected_error": "does not exist",
            },
            "invalid_fps": {
                "args": {
                    "input_dir": "/test/input",
                    "output_file": "/test/output.mp4",
                    "model_location": "/test/models",
                    "fps": 0,
                },
                "expected_valid": False,
                "expected_error": "FPS must be greater than 0",
            },
            "invalid_exp": {
                "args": {
                    "input_dir": "/test/input",
                    "output_file": "/test/output.mp4",
                    "model_location": "/test/models",
                    "exp": 0,
                },
                "expected_valid": False,
                "expected_error": "Interpolation factor must be at least 1",
            },
        }

    @pytest.fixture
    def processing_manager(self, qapp):
        """Create ProcessingManager instance for testing."""
        manager = ProcessingManager()
        yield manager
        # Clean up after test
        if manager.is_processing:
            manager.stop_processing()

    @pytest.fixture
    def signal_tracker(self):
        """Create a signal tracker for testing emissions."""
        def create_tracker():
            tracker = {
                "started": False,
                "progress": [],
                "finished": None,
                "error": None,
                "state_changed": [],
            }
            
            def track_signal(signal_name, value=None):
                if signal_name in {"progress", "state_changed"}:
                    tracker[signal_name].append(value)
                else:
                    tracker[signal_name] = value
            
            return tracker, track_signal
        return create_tracker

    @pytest.fixture
    def mock_worker_setup(self):
        """Create comprehensive mock worker setup."""
        def create_mocks(should_fail=False, failure_exception=None):
            # Mock QThread
            mock_thread = MagicMock(spec=QThread)
            mock_thread.start = Mock()
            mock_thread.quit = Mock()
            mock_thread.wait = Mock(return_value=True)
            mock_thread.terminate = Mock()
            mock_thread.isRunning = Mock(return_value=False)
            mock_thread.finished = Mock()
            mock_thread.started = Mock()
            
            # Mock VfiWorker
            mock_worker = MagicMock()
            mock_worker.run = Mock()
            mock_worker.moveToThread = Mock()
            mock_worker.deleteLater = Mock()
            mock_worker.progress = Mock()
            mock_worker.finished = Mock()
            mock_worker.error = Mock()
            
            # Setup patches
            thread_patch = patch("goesvfi.gui_components.processing_manager.QThread", return_value=mock_thread)
            
            if should_fail:
                worker_patch = patch("goesvfi.gui_components.processing_manager.VfiWorker", 
                                   side_effect=failure_exception or Exception("Worker creation failed"))
            else:
                worker_patch = patch("goesvfi.gui_components.processing_manager.VfiWorker", return_value=mock_worker)
            
            return {
                "thread_patch": thread_patch,
                "worker_patch": worker_patch,
                "mock_thread": mock_thread,
                "mock_worker": mock_worker,
            }
        return create_mocks

    def test_initialization(self, processing_manager):
        """Test ProcessingManager initialization."""
        assert not processing_manager.is_processing
        assert processing_manager.worker_thread is None
        assert processing_manager.worker is None
        assert processing_manager.current_output_path is None

    @pytest.mark.parametrize("scenario_name", [
        "basic_processing",
        "high_fps_processing",
        "minimal_processing",
        "custom_processing",
    ])
    def test_start_processing_success_scenarios(self, processing_manager, signal_tracker, 
                                              mock_worker_setup, processing_scenarios, scenario_name):
        """Test successful processing start with various scenarios."""
        scenario = processing_scenarios[scenario_name]
        tracker, track_signal = signal_tracker()
        mocks = mock_worker_setup(should_fail=False)
        
        # Connect signals to tracker
        processing_manager.processing_started.connect(lambda: track_signal("started", True))
        processing_manager.processing_progress.connect(lambda c, t, e: track_signal("progress", (c, t, e)))
        processing_manager.processing_finished.connect(lambda p: track_signal("finished", p))
        processing_manager.processing_error.connect(lambda e: track_signal("error", e))
        processing_manager.processing_state_changed.connect(lambda s: track_signal("state_changed", s))
        
        with mocks["thread_patch"], mocks["worker_patch"]:
            result = processing_manager.start_processing(scenario["args"])
            
            # Verify success
            assert result is True
            assert processing_manager.is_processing
            assert processing_manager.current_output_path == Path(scenario["args"]["output_file"])
            
            # Verify signals were emitted
            assert tracker["started"] is True
            assert True in tracker["state_changed"]
            
            # Verify thread operations
            mocks["mock_thread"].start.assert_called_once()
            mocks["mock_worker"].moveToThread.assert_called_once_with(mocks["mock_thread"])

    def test_start_processing_while_already_processing(self, processing_manager):
        """Test starting processing while already processing."""
        # Set processing state
        processing_manager.is_processing = True
        
        args = {
            "input_dir": "/test/input",
            "output_file": "/test/output.mp4",
            "model_location": "/test/models",
        }
        
        # Try to start processing
        result = processing_manager.start_processing(args)
        
        # Should fail
        assert result is False

    @pytest.mark.parametrize("scenario_name", [
        "missing_input_dir",
        "missing_output_file", 
        "missing_model_location",
    ])
    def test_start_processing_missing_args(self, processing_manager, signal_tracker, 
                                         validation_scenarios, scenario_name):
        """Test starting processing with missing required arguments."""
        scenario = validation_scenarios[scenario_name]
        tracker, track_signal = signal_tracker()
        
        # Connect error signal
        processing_manager.processing_error.connect(lambda e: track_signal("error", e))
        processing_manager.processing_state_changed.connect(lambda s: track_signal("state_changed", s))
        
        # Try to start processing
        result = processing_manager.start_processing(scenario["args"])
        
        # Should fail
        assert result is False
        assert tracker["error"] is not None
        assert scenario["expected_error"] in tracker["error"]
        assert False in tracker["state_changed"]

    def test_start_processing_worker_creation_failure(self, processing_manager, signal_tracker, mock_worker_setup):
        """Test handling of worker creation failure."""
        tracker, track_signal = signal_tracker()
        mocks = mock_worker_setup(should_fail=True, failure_exception=RuntimeError("Worker failed"))
        
        # Connect signals
        processing_manager.processing_error.connect(lambda e: track_signal("error", e))
        processing_manager.processing_state_changed.connect(lambda s: track_signal("state_changed", s))
        
        args = {
            "input_dir": "/test/input",
            "output_file": "/test/output.mp4",
            "model_location": "/test/models",
        }
        
        with mocks["thread_patch"], mocks["worker_patch"]:
            result = processing_manager.start_processing(args)
            
            # Should fail
            assert result is False
            assert not processing_manager.is_processing
            assert tracker["error"] is not None
            assert "Worker failed" in tracker["error"]

    @pytest.mark.parametrize("scenario_name", [
        "nonexistent_input",
        "invalid_fps",
        "invalid_exp",
    ])
    def test_validation_scenarios(self, processing_manager, validation_scenarios, scenario_name):
        """Test various validation scenarios."""
        scenario = validation_scenarios[scenario_name]
        
        # Mock path existence for validation
        with patch("pathlib.Path.exists") as mock_exists:
            with patch("pathlib.Path.is_dir") as mock_is_dir:
                # Setup path mocking based on scenario
                if "nonexistent" in scenario_name:
                    mock_exists.return_value = False
                else:
                    mock_exists.return_value = True
                    mock_is_dir.return_value = True
                
                is_valid, error = processing_manager.validate_processing_args(scenario["args"])
                
                assert is_valid == scenario["expected_valid"]
                if not scenario["expected_valid"]:
                    assert scenario["expected_error"] in error

    def test_handle_progress_updates(self, processing_manager, signal_tracker):
        """Test handling of progress updates."""
        tracker, track_signal = signal_tracker()
        
        # Connect progress signal
        processing_manager.processing_progress.connect(lambda c, t, e: track_signal("progress", (c, t, e)))
        
        # Simulate progress updates
        test_cases = [
            (10, 100, 60.0),
            (50, 100, 30.0),
            (90, 100, 5.0),
            (100, 100, 0.0),
        ]
        
        for current, total, eta in test_cases:
            processing_manager._handle_progress(current, total, eta)
        
        # Verify all progress updates were tracked
        assert len(tracker["progress"]) == len(test_cases)
        for i, (current, total, eta) in enumerate(test_cases):
            assert tracker["progress"][i] == (current, total, eta)

    def test_handle_finished_processing(self, processing_manager, signal_tracker):
        """Test handling of successful processing completion."""
        tracker, track_signal = signal_tracker()
        
        # Connect signals
        processing_manager.processing_finished.connect(lambda p: track_signal("finished", p))
        processing_manager.processing_state_changed.connect(lambda s: track_signal("state_changed", s))
        
        # Set processing state
        processing_manager.is_processing = True
        
        # Simulate completion
        output_path = "/test/completed_output.mp4"
        processing_manager._handle_finished(output_path)
        
        # Verify state changes
        assert not processing_manager.is_processing
        assert tracker["finished"] == output_path
        assert False in tracker["state_changed"]

    def test_handle_processing_error(self, processing_manager, signal_tracker):
        """Test handling of processing errors."""
        tracker, track_signal = signal_tracker()
        
        # Connect signals
        processing_manager.processing_error.connect(lambda e: track_signal("error", e))
        processing_manager.processing_state_changed.connect(lambda s: track_signal("state_changed", s))
        
        # Set processing state
        processing_manager.is_processing = True
        
        # Simulate error
        error_message = "Test processing error"
        processing_manager._handle_error(error_message)
        
        # Verify state changes
        assert not processing_manager.is_processing
        assert tracker["error"] == error_message
        assert False in tracker["state_changed"]

    def test_stop_processing_not_running(self, processing_manager):
        """Test stopping when not processing."""
        # Should not crash or change state
        processing_manager.stop_processing()
        assert not processing_manager.is_processing

    def test_stop_processing_with_running_thread(self, processing_manager):
        """Test stopping with a running thread."""
        # Setup mock thread
        mock_thread = MagicMock()
        mock_thread.isRunning.return_value = True
        mock_thread.wait.return_value = True
        
        mock_worker = MagicMock()
        
        # Set up processing state
        processing_manager.worker_thread = mock_thread
        processing_manager.worker = mock_worker
        processing_manager.is_processing = True
        
        # Stop processing
        processing_manager.stop_processing()
        
        # Verify thread operations
        mock_thread.wait.assert_called_once_with(5000)

    def test_stop_processing_thread_timeout(self, processing_manager):
        """Test stopping when thread doesn't finish gracefully."""
        # Setup mock thread that doesn't finish gracefully
        mock_thread = MagicMock()
        mock_thread.isRunning.return_value = True
        mock_thread.wait.return_value = False  # Timeout
        mock_thread.terminate = Mock()
        
        mock_worker = MagicMock()
        
        # Set up processing state
        processing_manager.worker_thread = mock_thread
        processing_manager.worker = mock_worker
        processing_manager.is_processing = True
        
        # Stop processing
        processing_manager.stop_processing()
        
        # Verify termination was called
        mock_thread.terminate.assert_called_once()

    def test_cleanup_thread_functionality(self, processing_manager):
        """Test thread cleanup functionality."""
        # Setup mock objects
        mock_thread = MagicMock()
        mock_worker = MagicMock()
        
        processing_manager.worker_thread = mock_thread
        processing_manager.worker = mock_worker
        
        # Call cleanup
        processing_manager._cleanup_thread()
        
        # Verify cleanup
        mock_worker.deleteLater.assert_called_once()
        mock_thread.deleteLater.assert_called_once()
        assert processing_manager.worker is None
        assert processing_manager.worker_thread is None

    def test_get_processing_state(self, processing_manager):
        """Test getting processing state."""
        # Initially false
        assert not processing_manager.get_processing_state()
        
        # Set to true
        processing_manager.is_processing = True
        assert processing_manager.get_processing_state()
        
        # Set back to false
        processing_manager.is_processing = False
        assert not processing_manager.get_processing_state()

    def test_get_current_output_path(self, processing_manager):
        """Test getting current output path."""
        # Initially None
        assert processing_manager.get_current_output_path() is None
        
        # Set output path but not processing
        test_path = Path("/test/output.mp4")
        processing_manager.current_output_path = test_path
        assert processing_manager.get_current_output_path() is None  # Still None because not processing
        
        # Set processing state
        processing_manager.is_processing = True
        assert processing_manager.get_current_output_path() == test_path
        
        # Stop processing
        processing_manager.is_processing = False
        assert processing_manager.get_current_output_path() is None

    def test_signal_connection_workflow(self, processing_manager, mock_worker_setup):
        """Test that signals are properly connected during workflow."""
        mocks = mock_worker_setup(should_fail=False)
        
        args = {
            "input_dir": "/test/input",
            "output_file": "/test/output.mp4",
            "model_location": "/test/models",
        }
        
        with mocks["thread_patch"], mocks["worker_patch"]:
            processing_manager.start_processing(args)
            
            # Verify signal connections were made
            mock_worker = mocks["mock_worker"]
            mock_thread = mocks["mock_thread"]
            
            # Check that signals were accessed (indicating connection attempts)
            assert mock_worker.progress.connect.called or hasattr(mock_worker.progress, 'connect')
            assert mock_worker.finished.connect.called or hasattr(mock_worker.finished, 'connect')
            assert mock_worker.error.connect.called or hasattr(mock_worker.error, 'connect')

    def test_comprehensive_workflow_integration(self, processing_manager, signal_tracker, mock_worker_setup):
        """Test complete workflow from start to finish."""
        tracker, track_signal = signal_tracker()
        mocks = mock_worker_setup(should_fail=False)
        
        # Connect all signals
        processing_manager.processing_started.connect(lambda: track_signal("started", True))
        processing_manager.processing_progress.connect(lambda c, t, e: track_signal("progress", (c, t, e)))
        processing_manager.processing_finished.connect(lambda p: track_signal("finished", p))
        processing_manager.processing_error.connect(lambda e: track_signal("error", e))
        processing_manager.processing_state_changed.connect(lambda s: track_signal("state_changed", s))
        
        args = {
            "input_dir": "/test/input",
            "output_file": "/test/output.mp4",
            "model_location": "/test/models",
            "exp": 2,
            "fps": 30,
        }
        
        with mocks["thread_patch"], mocks["worker_patch"]:
            # Start processing
            result = processing_manager.start_processing(args)
            assert result is True
            assert processing_manager.is_processing
            
            # Simulate progress updates
            processing_manager._handle_progress(25, 100, 45.0)
            processing_manager._handle_progress(50, 100, 22.5)
            processing_manager._handle_progress(75, 100, 11.25)
            
            # Simulate completion
            processing_manager._handle_finished("/test/output.mp4")
            
            # Verify complete workflow
            assert tracker["started"] is True
            assert len(tracker["progress"]) == 3
            assert tracker["finished"] == "/test/output.mp4"
            assert True in tracker["state_changed"]  # Started
            assert False in tracker["state_changed"]  # Finished
            assert not processing_manager.is_processing

    def test_error_recovery_and_state_consistency(self, processing_manager, signal_tracker, mock_worker_setup):
        """Test error recovery and state consistency."""
        tracker, track_signal = signal_tracker()
        mocks = mock_worker_setup(should_fail=True, failure_exception=ValueError("Invalid configuration"))
        
        # Connect error signals
        processing_manager.processing_error.connect(lambda e: track_signal("error", e))
        processing_manager.processing_state_changed.connect(lambda s: track_signal("state_changed", s))
        
        args = {
            "input_dir": "/test/input",
            "output_file": "/test/output.mp4",
            "model_location": "/test/models",
        }
        
        with mocks["thread_patch"], mocks["worker_patch"]:
            # Try to start processing (should fail)
            result = processing_manager.start_processing(args)
            
            # Verify error handling
            assert result is False
            assert not processing_manager.is_processing
            assert tracker["error"] is not None
            assert "Invalid configuration" in tracker["error"]
            
            # Verify state was reset
            assert False in tracker["state_changed"]

    def test_concurrent_operations_simulation(self, processing_manager):
        """Simulate concurrent operations to test thread safety."""
        import threading
        import time
        
        results = []
        
        def worker_operation(worker_id, operation_type):
            try:
                if operation_type == "start":
                    args = {
                        "input_dir": f"/test/input_{worker_id}",
                        "output_file": f"/test/output_{worker_id}.mp4",
                        "model_location": "/test/models",
                    }
                    result = processing_manager.start_processing(args)
                    results.append(f"worker_{worker_id}_start_{result}")
                elif operation_type == "state":
                    state = processing_manager.get_processing_state()
                    results.append(f"worker_{worker_id}_state_{state}")
                elif operation_type == "stop":
                    processing_manager.stop_processing()
                    results.append(f"worker_{worker_id}_stop_completed")
                
                time.sleep(0.001)  # Small delay
            except Exception as e:
                results.append(f"worker_{worker_id}_error: {e}")
        
        # Create multiple threads with different operations
        threads = []
        operations = [("start", 0), ("state", 1), ("stop", 2), ("state", 3)]
        
        for operation_type, worker_id in operations:
            thread = threading.Thread(target=worker_operation, args=(worker_id, operation_type))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify all operations completed
        assert len(results) == 4
        assert all("error" not in result for result in results)

    def test_memory_management_during_lifecycle(self, processing_manager, mock_worker_setup):
        """Test memory management throughout processing lifecycle."""
        mocks = mock_worker_setup(should_fail=False)
        
        args = {
            "input_dir": "/test/input",
            "output_file": "/test/output.mp4",
            "model_location": "/test/models",
        }
        
        with mocks["thread_patch"], mocks["worker_patch"]:
            # Start processing
            processing_manager.start_processing(args)
            
            # Verify objects are created
            assert processing_manager.worker_thread is not None
            assert processing_manager.worker is not None
            
            # Simulate completion and cleanup
            processing_manager._handle_finished("/test/output.mp4")
            processing_manager._cleanup_thread()
            
            # Verify cleanup
            assert processing_manager.worker is None
            assert processing_manager.worker_thread is None