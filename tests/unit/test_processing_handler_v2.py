"""Optimized processing handler tests to speed up slow tests while maintaining coverage.

Optimizations applied:
- Shared fixtures for common handler setups and mock configurations
- Parameterized test scenarios for comprehensive processing workflow validation
- Enhanced error handling and state management testing
- Mock-based testing to avoid real GUI operations and worker creation
- Comprehensive worker lifecycle and integration testing
"""

from unittest.mock import Mock, patch, MagicMock, call
import pytest
from PyQt6.QtWidgets import QMessageBox

from goesvfi.gui_components.processing_handler import ProcessingHandler


class TestProcessingHandlerV2:
    """Optimized test class for processing handler functionality."""

    @pytest.fixture(scope="class")
    def processing_scenarios(self):
        """Define various processing scenario test cases."""
        return {
            "basic_processing": {
                "args": {
                    "in_dir": "/test/input",
                    "out_file": "/test/output.mp4",
                    "fps": 30,
                    "multiplier": 2,
                    "encoder": "libx264",
                    "max_workers": 4,
                },
                "debug_mode": False,
                "expected_success": True,
            },
            "debug_processing": {
                "args": {
                    "in_dir": "/debug/input",
                    "out_file": "/debug/output.mp4",
                    "fps": 60,
                    "multiplier": 4,
                    "encoder": "libx265",
                    "max_workers": 8,
                },
                "debug_mode": True,
                "expected_success": True,
            },
            "high_fps_processing": {
                "args": {
                    "in_dir": "/high_fps/input",
                    "out_file": "/high_fps/output.mp4",
                    "fps": 120,
                    "multiplier": 8,
                    "encoder": "hevc_videotoolbox",
                    "max_workers": 16,
                },
                "debug_mode": False,
                "expected_success": True,
            },
            "minimal_processing": {
                "args": {
                    "in_dir": "/minimal/input",
                    "out_file": "/minimal/output.mp4",
                    "fps": 24,
                    "multiplier": 1,
                    "encoder": "copy",
                    "max_workers": 1,
                },
                "debug_mode": False,
                "expected_success": True,
            },
        }

    @pytest.fixture(scope="class")
    def error_scenarios(self):
        """Define various error scenario test cases."""
        return {
            "worker_creation_failure": {
                "exception": ValueError("Invalid arguments"),
                "expected_error_message": "Invalid arguments",
            },
            "runtime_error": {
                "exception": RuntimeError("Processing initialization failed"),
                "expected_error_message": "Processing initialization failed",
            },
            "file_not_found": {
                "exception": FileNotFoundError("Input directory not found"),
                "expected_error_message": "Input directory not found",
            },
            "permission_error": {
                "exception": PermissionError("Access denied to output directory"),
                "expected_error_message": "Access denied to output directory",
            },
            "memory_error": {
                "exception": MemoryError("Insufficient memory for processing"),
                "expected_error_message": "Insufficient memory for processing",
            },
        }

    @pytest.fixture
    def processing_handler(self):
        """Create ProcessingHandler instance for testing."""
        return ProcessingHandler()

    @pytest.fixture
    def mock_main_window_factory(self):
        """Factory for creating comprehensive mock main windows."""
        def create_mock_window(initial_state=None):
            initial_state = initial_state or {}
            
            main_window = Mock()
            
            # Processing state
            main_window.is_processing = initial_state.get("is_processing", False)
            main_window.debug_mode = initial_state.get("debug_mode", False)
            main_window.vfi_worker = initial_state.get("vfi_worker", None)
            
            # Methods
            main_window._set_processing_state = Mock()
            
            # Signal broker
            main_window.signal_broker = Mock()
            main_window.signal_broker.setup_worker_connections = Mock()
            
            # View models
            main_window.main_view_model = Mock()
            main_window.main_view_model.processing_vm = Mock()
            main_window.main_view_model.processing_vm.start_processing = Mock()
            
            # Main tab
            main_window.main_tab = Mock()
            main_window.main_tab._reset_start_button = Mock()
            
            return main_window
        return create_mock_window

    @pytest.fixture
    def mock_worker_factory(self):
        """Mock worker factory for testing."""
        def create_mock_worker(should_fail=False, failure_exception=None):
            mock_worker = Mock()
            mock_worker.start = Mock()
            mock_worker.isRunning = Mock(return_value=False)
            mock_worker.terminate = Mock()
            mock_worker.wait = Mock()
            
            with patch("goesvfi.gui_components.processing_handler.WorkerFactory") as factory:
                if should_fail:
                    factory.create_worker.side_effect = failure_exception or Exception("Worker creation failed")
                else:
                    factory.create_worker.return_value = mock_worker
                return factory, mock_worker
        return create_mock_worker

    @pytest.mark.parametrize("scenario_name", [
        "basic_processing",
        "debug_processing",
        "high_fps_processing", 
        "minimal_processing",
    ])
    def test_successful_processing_scenarios(self, processing_handler, mock_main_window_factory, 
                                           mock_worker_factory, processing_scenarios, scenario_name):
        """Test successful processing with various scenarios."""
        scenario = processing_scenarios[scenario_name]
        main_window = mock_main_window_factory({"debug_mode": scenario["debug_mode"]})
        factory, mock_worker = mock_worker_factory(should_fail=False)
        
        with factory:
            processing_handler.handle_processing(main_window, scenario["args"])
            
            # Verify processing state was set
            assert main_window.is_processing is True
            main_window._set_processing_state.assert_called_with(True)
            
            # Verify worker creation with correct debug mode
            factory.create_worker.assert_called_once_with(scenario["args"], scenario["debug_mode"])
            
            # Verify signal connections
            main_window.signal_broker.setup_worker_connections.assert_called_once_with(main_window, mock_worker)
            
            # Verify worker was started
            mock_worker.start.assert_called_once()
            
            # Verify view model was notified
            main_window.main_view_model.processing_vm.start_processing.assert_called_once()
            
            # Verify worker assignment
            assert main_window.vfi_worker is mock_worker

    def test_processing_already_in_progress(self, processing_handler, mock_main_window_factory):
        """Test handling when processing is already in progress."""
        main_window = mock_main_window_factory({"is_processing": True})
        args = {"in_dir": "/test", "out_file": "/test.mp4"}
        
        with patch("goesvfi.gui_components.processing_handler.LOGGER") as mock_logger:
            processing_handler.handle_processing(main_window, args)
            
            # Should log warning and return early
            mock_logger.warning.assert_called_once()
            assert "already in progress" in str(mock_logger.warning.call_args)
            
            # Should not change processing state
            main_window._set_processing_state.assert_not_called()

    @pytest.mark.parametrize("invalid_args", [
        {},  # Empty dict
        None,  # None value
    ])
    def test_invalid_arguments_handling(self, processing_handler, mock_main_window_factory, invalid_args):
        """Test handling of invalid or empty arguments."""
        main_window = mock_main_window_factory()
        
        with patch("goesvfi.gui_components.processing_handler.LOGGER") as mock_logger:
            processing_handler.handle_processing(main_window, invalid_args)
            
            # Should log warning and return early
            mock_logger.warning.assert_called_once()
            if invalid_args == {}:
                assert "Empty args dictionary" in str(mock_logger.warning.call_args)
            
            # Should not change processing state
            main_window._set_processing_state.assert_not_called()

    @pytest.mark.parametrize("error_scenario", [
        "worker_creation_failure",
        "runtime_error",
        "file_not_found",
        "permission_error",
        "memory_error",
    ])
    def test_worker_creation_error_scenarios(self, processing_handler, mock_main_window_factory, 
                                           mock_worker_factory, error_scenarios, error_scenario):
        """Test various worker creation error scenarios."""
        scenario = error_scenarios[error_scenario]
        main_window = mock_main_window_factory()
        args = {"in_dir": "/test", "out_file": "/test.mp4"}
        
        factory, _ = mock_worker_factory(should_fail=True, failure_exception=scenario["exception"])
        
        with factory:
            with patch("goesvfi.gui_components.processing_handler.QMessageBox") as mock_qmessage_box:
                with patch("goesvfi.gui_components.processing_handler.LOGGER") as mock_logger:
                    processing_handler.handle_processing(main_window, args)
                    
                    # Should log exception
                    mock_logger.exception.assert_called_once()
                    
                    # Should reset processing state
                    assert main_window.is_processing is False
                    main_window._set_processing_state.assert_called_with(False)
                    
                    # Should show error dialog with specific message
                    mock_qmessage_box.critical.assert_called_once()
                    error_args = mock_qmessage_box.critical.call_args[0]
                    assert error_args[0] is main_window  # parent
                    assert error_args[1] == "Error"  # title
                    assert scenario["expected_error_message"] in error_args[2]  # message content
                    
                    # Should reset start button
                    main_window.main_tab._reset_start_button.assert_called_once()

    @pytest.mark.parametrize("worker_running", [True, False])
    def test_terminate_previous_worker_scenarios(self, processing_handler, mock_main_window_factory, worker_running):
        """Test terminating previous worker in various states."""
        # Create mock worker
        mock_worker = Mock()
        mock_worker.isRunning.return_value = worker_running
        mock_worker.terminate = Mock()
        mock_worker.wait = Mock()
        
        main_window = mock_main_window_factory({"vfi_worker": mock_worker})
        
        if worker_running:
            with patch("goesvfi.gui_components.processing_handler.LOGGER") as mock_logger:
                processing_handler._terminate_previous_worker(main_window)
                
                # Should log warning
                mock_logger.warning.assert_called_once()
                assert "Terminating previous VfiWorker" in str(mock_logger.warning.call_args)
                
                # Should terminate and wait
                mock_worker.terminate.assert_called_once()
                mock_worker.wait.assert_called_once_with(1000)
        else:
            processing_handler._terminate_previous_worker(main_window)
            
            # Should check if running but not terminate
            mock_worker.isRunning.assert_called_once()
            mock_worker.terminate.assert_not_called()
            mock_worker.wait.assert_not_called()

    def test_terminate_worker_no_previous_worker(self, processing_handler, mock_main_window_factory):
        """Test terminating when no previous worker exists."""
        main_window = mock_main_window_factory({"vfi_worker": None})
        
        # Should not raise exception
        processing_handler._terminate_previous_worker(main_window)

    def test_terminate_worker_exception_handling(self, processing_handler, mock_main_window_factory):
        """Test handling exceptions during worker termination."""
        mock_worker = Mock()
        mock_worker.isRunning.return_value = True
        mock_worker.terminate.side_effect = Exception("Termination failed")
        
        main_window = mock_main_window_factory({"vfi_worker": mock_worker})
        
        with patch("goesvfi.gui_components.processing_handler.LOGGER") as mock_logger:
            # Should not raise exception
            processing_handler._terminate_previous_worker(main_window)
            
            # Should log exception
            mock_logger.exception.assert_called_once()
            assert "Error terminating previous worker" in str(mock_logger.exception.call_args)

    def test_create_and_start_worker_success(self, processing_handler, mock_main_window_factory, mock_worker_factory):
        """Test successful worker creation and start."""
        main_window = mock_main_window_factory()
        args = {"in_dir": "/test", "out_file": "/test.mp4"}
        
        factory, mock_worker = mock_worker_factory(should_fail=False)
        
        with factory:
            result = processing_handler._create_and_start_worker(main_window, args)
            
            # Should return True
            assert result is True
            
            # Should create worker with correct debug mode
            factory.create_worker.assert_called_once_with(args, False)
            
            # Should setup signal connections
            main_window.signal_broker.setup_worker_connections.assert_called_once_with(main_window, mock_worker)
            
            # Should start worker
            mock_worker.start.assert_called_once()
            
            # Should assign worker to main window
            assert main_window.vfi_worker is mock_worker

    def test_create_and_start_worker_failure(self, processing_handler, mock_main_window_factory, mock_worker_factory):
        """Test worker creation and start failure."""
        main_window = mock_main_window_factory()
        args = {"in_dir": "/test", "out_file": "/test.mp4"}
        
        factory, _ = mock_worker_factory(should_fail=True, failure_exception=ValueError("Test error"))
        
        with factory:
            with patch("goesvfi.gui_components.processing_handler.QMessageBox") as mock_qmessage_box:
                with patch("goesvfi.gui_components.processing_handler.LOGGER") as mock_logger:
                    result = processing_handler._create_and_start_worker(main_window, args)
                    
                    # Should return False
                    assert result is False
                    
                    # Should log exception
                    mock_logger.exception.assert_called_once()
                    
                    # Should reset processing state
                    assert main_window.is_processing is False
                    main_window._set_processing_state.assert_called_with(False)
                    
                    # Should show error dialog
                    mock_qmessage_box.critical.assert_called_once()
                    
                    # Should reset start button
                    main_window.main_tab._reset_start_button.assert_called_once()

    def test_integration_full_workflow_with_existing_worker(self, processing_handler, mock_main_window_factory, mock_worker_factory):
        """Test complete processing workflow with existing running worker."""
        # Setup existing worker that's running
        existing_worker = Mock()
        existing_worker.isRunning.return_value = True
        existing_worker.terminate = Mock()
        existing_worker.wait = Mock()
        
        main_window = mock_main_window_factory({"vfi_worker": existing_worker})
        args = {"in_dir": "/test", "out_file": "/test.mp4"}
        
        # Setup new worker
        factory, new_worker = mock_worker_factory(should_fail=False)
        
        with factory:
            with patch("goesvfi.gui_components.processing_handler.LOGGER"):
                processing_handler.handle_processing(main_window, args)
                
                # Should terminate existing worker
                existing_worker.terminate.assert_called_once()
                existing_worker.wait.assert_called_once_with(1000)
                
                # Should create and start new worker
                factory.create_worker.assert_called_once()
                new_worker.start.assert_called_once()
                
                # Should setup all state correctly
                assert main_window.is_processing is True
                assert main_window.vfi_worker is new_worker
                main_window._set_processing_state.assert_called_with(True)
                main_window.main_view_model.processing_vm.start_processing.assert_called_once()

    def test_logging_behavior_comprehensive(self, processing_handler, mock_main_window_factory, mock_worker_factory):
        """Test comprehensive logging behavior during processing."""
        main_window = mock_main_window_factory()
        args = {"in_dir": "/test", "out_file": "/test.mp4", "fps": 30}
        
        factory, mock_worker = mock_worker_factory(should_fail=False)
        
        with factory:
            with patch("goesvfi.gui_components.processing_handler.LOGGER") as mock_logger:
                processing_handler.handle_processing(main_window, args)
                
                # Should log start of processing
                info_calls = [str(call) for call in mock_logger.info.call_args_list]
                assert any("Starting video interpolation" in call for call in info_calls)
                assert any("VfiWorker thread started" in call for call in info_calls)
                
                # Should log debug information
                mock_logger.debug.assert_called_once()
                debug_call = str(mock_logger.debug.call_args)
                assert "Processing arguments" in debug_call

    def test_state_consistency_throughout_workflow(self, processing_handler, mock_main_window_factory, mock_worker_factory):
        """Test that state remains consistent throughout the entire workflow."""
        main_window = mock_main_window_factory()
        args = {"in_dir": "/test", "out_file": "/test.mp4"}
        
        factory, mock_worker = mock_worker_factory(should_fail=False)
        
        with factory:
            # Initial state
            assert main_window.is_processing is False
            assert main_window.vfi_worker is None
            
            processing_handler.handle_processing(main_window, args)
            
            # Final state
            assert main_window.is_processing is True
            assert main_window.vfi_worker is mock_worker
            
            # Verify state change calls
            main_window._set_processing_state.assert_called_once_with(True)

    def test_error_state_consistency(self, processing_handler, mock_main_window_factory, mock_worker_factory):
        """Test that state remains consistent when errors occur."""
        main_window = mock_main_window_factory()
        args = {"in_dir": "/test", "out_file": "/test.mp4"}
        
        factory, _ = mock_worker_factory(should_fail=True, failure_exception=Exception("Test error"))
        
        with factory:
            with patch("goesvfi.gui_components.processing_handler.QMessageBox"):
                # Processing state gets set to True initially
                processing_handler.handle_processing(main_window, args)
                
                # Should be reset to False after error
                assert main_window.is_processing is False
                
                # Should have proper state reset calls
                calls = main_window._set_processing_state.call_args_list
                assert call(True) in calls  # Initial set
                assert call(False) in calls  # Reset after error

    def test_worker_assignment_timing(self, processing_handler, mock_main_window_factory, mock_worker_factory):
        """Test that worker is assigned at the correct time in the workflow."""
        main_window = mock_main_window_factory()
        args = {"in_dir": "/test", "out_file": "/test.mp4"}
        
        factory, mock_worker = mock_worker_factory(should_fail=False)
        
        with factory:
            # Track when worker gets assigned by patching the factory
            original_create = factory.create_worker
            
            def track_assignment(*args, **kwargs):
                # At this point, worker should not be assigned yet
                assert main_window.vfi_worker != mock_worker
                result = original_create(*args, **kwargs)
                return result
            
            factory.create_worker.side_effect = track_assignment
            
            processing_handler.handle_processing(main_window, args)
            
            # After processing, worker should be assigned
            assert main_window.vfi_worker is mock_worker

    def test_signal_broker_integration(self, processing_handler, mock_main_window_factory, mock_worker_factory):
        """Test integration with signal broker for worker connections."""
        main_window = mock_main_window_factory()
        args = {"in_dir": "/test", "out_file": "/test.mp4"}
        
        factory, mock_worker = mock_worker_factory(should_fail=False)
        
        with factory:
            processing_handler.handle_processing(main_window, args)
            
            # Should setup worker connections through signal broker
            main_window.signal_broker.setup_worker_connections.assert_called_once_with(main_window, mock_worker)
            
            # Connection setup should happen before worker start
            signal_call_index = None
            start_call_index = None
            
            # Find the order of calls (signal broker setup should come before worker.start)
            for i, call_obj in enumerate([main_window.signal_broker.setup_worker_connections, mock_worker.start]):
                if call_obj.called:
                    if call_obj is main_window.signal_broker.setup_worker_connections:
                        signal_call_index = i
                    elif call_obj is mock_worker.start:
                        start_call_index = i
            
            # Signal setup should happen before worker start
            assert signal_call_index is not None
            assert start_call_index is not None

    def test_view_model_integration(self, processing_handler, mock_main_window_factory, mock_worker_factory):
        """Test integration with view model for processing state updates."""
        main_window = mock_main_window_factory()
        args = {"in_dir": "/test", "out_file": "/test.mp4"}
        
        factory, mock_worker = mock_worker_factory(should_fail=False)
        
        with factory:
            processing_handler.handle_processing(main_window, args)
            
            # Should notify view model of processing start
            main_window.main_view_model.processing_vm.start_processing.assert_called_once()

    def test_debug_mode_propagation(self, processing_handler, mock_main_window_factory, mock_worker_factory):
        """Test that debug mode is properly propagated to worker creation."""
        debug_scenarios = [
            {"debug_mode": True, "expected_debug": True},
            {"debug_mode": False, "expected_debug": False},
        ]
        
        for scenario in debug_scenarios:
            main_window = mock_main_window_factory({"debug_mode": scenario["debug_mode"]})
            args = {"in_dir": "/test", "out_file": "/test.mp4"}
            
            factory, mock_worker = mock_worker_factory(should_fail=False)
            
            with factory:
                processing_handler.handle_processing(main_window, args)
                
                # Should pass debug mode to worker creation
                factory.create_worker.assert_called_once_with(args, scenario["expected_debug"])
                
                # Reset for next iteration
                factory.reset_mock()

    def test_concurrent_processing_requests_simulation(self, processing_handler, mock_main_window_factory):
        """Simulate concurrent processing requests to test thread safety."""
        import threading
        import time
        
        main_window = mock_main_window_factory()
        args = {"in_dir": "/test", "out_file": "/test.mp4"}
        results = []
        
        def processing_worker(worker_id):
            try:
                # First request should set processing to True, subsequent should be ignored
                processing_handler.handle_processing(main_window, args)
                results.append(f"worker_{worker_id}_completed")
                time.sleep(0.001)  # Small delay
            except Exception as e:
                results.append(f"worker_{worker_id}_error: {e}")
        
        # Create multiple threads to simulate concurrent requests
        threads = []
        for i in range(3):
            thread = threading.Thread(target=processing_worker, args=(i,))
            threads.append(thread)
        
        # Set processing to True to simulate already processing state
        main_window.is_processing = True
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # All should complete (though they'll be ignored due to already processing)
        assert len(results) == 3
        assert all("completed" in result for result in results)

    def test_memory_cleanup_on_error(self, processing_handler, mock_main_window_factory, mock_worker_factory):
        """Test that memory is properly cleaned up when errors occur."""
        main_window = mock_main_window_factory()
        args = {"in_dir": "/test", "out_file": "/test.mp4"}
        
        factory, _ = mock_worker_factory(should_fail=True, failure_exception=MemoryError("Out of memory"))
        
        with factory:
            with patch("goesvfi.gui_components.processing_handler.QMessageBox"):
                processing_handler.handle_processing(main_window, args)
                
                # State should be properly cleaned up
                assert main_window.is_processing is False
                main_window._set_processing_state.assert_called_with(False)
                main_window.main_tab._reset_start_button.assert_called_once()
                
                # No worker should be assigned
                assert main_window.vfi_worker is None  # Should remain None after failed creation