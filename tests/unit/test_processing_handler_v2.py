"""
Optimized unit tests for ProcessingHandler functionality with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for ProcessingHandler, mock window, and argument configurations
- Combined test scenarios for processing workflows and error handling
- Enhanced test managers for comprehensive validation and edge case coverage
- Batch testing of worker lifecycle and state management scenarios
"""

from typing import Any, Dict, List
from unittest.mock import Mock, patch

import pytest

from goesvfi.gui_components.processing_handler import ProcessingHandler


class TestProcessingHandlerOptimizedV2:
    """Optimized ProcessingHandler tests with full coverage."""

    @pytest.fixture(scope="class")
    def processing_test_components(self):
        """Create shared components for ProcessingHandler testing."""
        
        # Enhanced ProcessingHandler Test Manager
        class ProcessingHandlerTestManager:
            """Manage ProcessingHandler testing scenarios."""
            
            def __init__(self):
                self.handler = ProcessingHandler()
                
                # Define argument configurations for testing
                self.arg_configs = {
                    "valid": {
                        "in_dir": "/test/input",
                        "out_file": "/test/output.mp4",
                        "fps": 30,
                        "multiplier": 2,
                        "encoder": "libx264",
                        "max_workers": 4,
                    },
                    "minimal": {
                        "in_dir": "/test/input",
                        "out_file": "/test/output.mp4",
                    },
                    "complete": {
                        "in_dir": "/test/input",
                        "out_file": "/test/output.mp4",
                        "fps": 30,
                        "multiplier": 2,
                        "encoder": "libx264",
                        "max_workers": 4,
                        "debug": True,
                        "extra_param": "value"
                    },
                    "empty": {},
                    "none": None
                }
                
                # Define test scenarios
                self.test_scenarios = {
                    "successful_processing": self._test_successful_processing,
                    "processing_validation": self._test_processing_validation,
                    "error_handling": self._test_error_handling,
                    "worker_management": self._test_worker_management,
                    "state_consistency": self._test_state_consistency,
                    "logging_validation": self._test_logging_validation,
                    "integration_workflows": self._test_integration_workflows,
                    "edge_cases": self._test_edge_cases,
                    "performance_validation": self._test_performance_validation
                }
            
            def create_mock_main_window(self, **overrides) -> Mock:
                """Create a comprehensive mock main window."""
                main_window = Mock()
                
                # Default state
                main_window.is_processing = False
                main_window.debug_mode = False
                main_window.vfi_worker = None
                
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
                
                # Apply overrides
                for key, value in overrides.items():
                    setattr(main_window, key, value)
                
                return main_window
            
            def create_mock_worker(self, **config) -> Mock:
                """Create a mock worker with specified configuration."""
                worker = Mock()
                worker.start = Mock()
                worker.terminate = Mock()
                worker.wait = Mock()
                worker.isRunning = Mock(return_value=config.get("is_running", False))
                
                if config.get("start_exception"):
                    worker.start.side_effect = config["start_exception"]
                if config.get("terminate_exception"):
                    worker.terminate.side_effect = config["terminate_exception"]
                
                return worker
            
            def _test_successful_processing(self, scenario_name: str, args: Dict[str, Any], debug_mode: bool = False) -> Dict[str, Any]:
                """Test successful processing workflows."""
                main_window = self.create_mock_main_window(debug_mode=debug_mode)
                mock_worker = self.create_mock_worker()
                
                with patch("goesvfi.gui_components.processing_handler.WorkerFactory") as mock_worker_factory:
                    mock_worker_factory.create_worker.return_value = mock_worker
                    
                    self.handler.handle_processing(main_window, args)
                    
                    # Verify processing state was set
                    assert main_window.is_processing is True
                    main_window._set_processing_state.assert_called_with(True)
                    
                    # Verify worker creation and setup
                    mock_worker_factory.create_worker.assert_called_once_with(args, debug_mode)
                    main_window.signal_broker.setup_worker_connections.assert_called_once_with(main_window, mock_worker)
                    
                    # Verify worker was started
                    mock_worker.start.assert_called_once()
                    
                    # Verify view model was notified
                    main_window.main_view_model.processing_vm.start_processing.assert_called_once()
                    
                    # Verify worker was assigned
                    assert main_window.vfi_worker is mock_worker
                
                return {
                    "scenario": scenario_name,
                    "success": True,
                    "debug_mode": debug_mode,
                    "worker_created": True
                }
            
            def _test_processing_validation(self, scenario_name: str, args: Any, expected_warning: str) -> Dict[str, Any]:
                """Test processing validation scenarios."""
                main_window = self.create_mock_main_window()
                
                # Test already processing scenario
                if scenario_name == "already_processing":
                    main_window.is_processing = True
                
                with patch("goesvfi.gui_components.processing_handler.LOGGER") as mock_logger:
                    self.handler.handle_processing(main_window, args)
                    
                    # Should log warning and return early
                    mock_logger.warning.assert_called_once()
                    if expected_warning:
                        assert expected_warning in str(mock_logger.warning.call_args)
                    
                    # Should not change processing state (except for already_processing where it's already True)
                    if scenario_name != "already_processing":
                        main_window._set_processing_state.assert_not_called()
                
                return {
                    "scenario": scenario_name,
                    "validation_triggered": True,
                    "warning_logged": True
                }
            
            def _test_error_handling(self, scenario_name: str, error_type: Exception, args: Dict[str, Any]) -> Dict[str, Any]:
                """Test error handling scenarios."""
                main_window = self.create_mock_main_window()
                
                with patch("goesvfi.gui_components.processing_handler.WorkerFactory") as mock_worker_factory:
                    with patch("goesvfi.gui_components.processing_handler.QMessageBox") as mock_qmessage_box:
                        with patch("goesvfi.gui_components.processing_handler.LOGGER") as mock_logger:
                            # Mock worker creation failure
                            mock_worker_factory.create_worker.side_effect = error_type
                            
                            self.handler.handle_processing(main_window, args)
                            
                            # Should log exception
                            mock_logger.exception.assert_called_once()
                            
                            # Should reset processing state
                            assert main_window.is_processing is False
                            main_window._set_processing_state.assert_called_with(False)
                            
                            # Should show error dialog
                            mock_qmessage_box.critical.assert_called_once()
                            error_args = mock_qmessage_box.critical.call_args[0]
                            assert "Failed to initialize processing pipeline" in error_args[2]
                            
                            # Should reset start button
                            main_window.main_tab._reset_start_button.assert_called_once()
                
                return {
                    "scenario": scenario_name,
                    "error_type": type(error_type).__name__,
                    "error_handled": True,
                    "state_reset": True
                }
            
            def _test_worker_management(self, scenario_name: str, worker_config: Dict[str, Any]) -> Dict[str, Any]:
                """Test worker management scenarios."""
                main_window = self.create_mock_main_window()
                results = {}
                
                if scenario_name == "no_worker":
                    # Test terminating when no previous worker exists
                    main_window.vfi_worker = None
                    
                    # Should not raise exception
                    self.handler._terminate_previous_worker(main_window)
                    results["no_exception"] = True
                
                elif scenario_name == "worker_not_running":
                    # Test terminating when worker exists but not running
                    mock_worker = self.create_mock_worker(is_running=False)
                    main_window.vfi_worker = mock_worker
                    
                    self.handler._terminate_previous_worker(main_window)
                    
                    # Should check if running but not terminate
                    mock_worker.isRunning.assert_called_once()
                    mock_worker.terminate.assert_not_called()
                    results["checked_running"] = True
                
                elif scenario_name == "worker_running":
                    # Test terminating when worker is running
                    mock_worker = self.create_mock_worker(is_running=True)
                    main_window.vfi_worker = mock_worker
                    
                    with patch("goesvfi.gui_components.processing_handler.LOGGER") as mock_logger:
                        self.handler._terminate_previous_worker(main_window)
                        
                        # Should log warning
                        mock_logger.warning.assert_called_once()
                        
                        # Should terminate and wait
                        mock_worker.terminate.assert_called_once()
                        mock_worker.wait.assert_called_once_with(1000)
                        results["terminated"] = True
                
                elif scenario_name == "termination_exception":
                    # Test handling exception during worker termination
                    mock_worker = self.create_mock_worker(
                        is_running=True,
                        terminate_exception=Exception("Termination failed")
                    )
                    main_window.vfi_worker = mock_worker
                    
                    with patch("goesvfi.gui_components.processing_handler.LOGGER") as mock_logger:
                        # Should not raise exception
                        self.handler._terminate_previous_worker(main_window)
                        
                        # Should log exception
                        mock_logger.exception.assert_called_once()
                        results["exception_handled"] = True
                
                return {
                    "scenario": scenario_name,
                    "results": results
                }
            
            def _test_state_consistency(self, scenario_name: str) -> Dict[str, Any]:
                """Test state consistency scenarios."""
                main_window = self.create_mock_main_window()
                args = self.arg_configs["valid"]
                
                with patch("goesvfi.gui_components.processing_handler.WorkerFactory") as mock_worker_factory:
                    with patch("goesvfi.gui_components.processing_handler.QMessageBox"):
                        mock_worker_factory.create_worker.side_effect = Exception("Test error")
                        
                        self.handler.handle_processing(main_window, args)
                        
                        # Processing state should be reset to False
                        assert main_window.is_processing is False
                        
                        # UI state should be properly reset
                        main_window._set_processing_state.assert_called_with(False)
                        main_window.main_tab._reset_start_button.assert_called_once()
                
                return {
                    "scenario": scenario_name,
                    "state_consistent": True
                }
            
            def _test_logging_validation(self, scenario_name: str) -> Dict[str, Any]:
                """Test logging behavior validation."""
                main_window = self.create_mock_main_window()
                args = self.arg_configs["valid"]
                
                with patch("goesvfi.gui_components.processing_handler.LOGGER") as mock_logger:
                    with patch("goesvfi.gui_components.processing_handler.WorkerFactory") as mock_worker_factory:
                        mock_worker = self.create_mock_worker()
                        mock_worker_factory.create_worker.return_value = mock_worker
                        
                        self.handler.handle_processing(main_window, args)
                        
                        # Should log start of processing
                        info_calls = [str(call) for call in mock_logger.info.call_args_list]
                        assert any("Starting video interpolation" in call for call in info_calls)
                        
                        # Should log debug information
                        mock_logger.debug.assert_called_once()
                        
                        # Should log worker start
                        assert any("VfiWorker thread started" in call for call in info_calls)
                
                return {
                    "scenario": scenario_name,
                    "logging_validated": True
                }
            
            def _test_integration_workflows(self, scenario_name: str) -> Dict[str, Any]:
                """Test complete integration workflows."""
                main_window = self.create_mock_main_window()
                args = self.arg_configs["valid"]
                
                # Setup existing worker that's running
                existing_worker = self.create_mock_worker(is_running=True)
                main_window.vfi_worker = existing_worker
                
                # Setup new worker
                new_worker = self.create_mock_worker()
                
                with patch("goesvfi.gui_components.processing_handler.WorkerFactory") as mock_worker_factory:
                    mock_worker_factory.create_worker.return_value = new_worker
                    
                    self.handler.handle_processing(main_window, args)
                    
                    # Should terminate existing worker
                    existing_worker.terminate.assert_called_once()
                    existing_worker.wait.assert_called_once_with(1000)
                    
                    # Should create and start new worker
                    mock_worker_factory.create_worker.assert_called_once()
                    new_worker.start.assert_called_once()
                    
                    # Should setup all state correctly
                    assert main_window.is_processing is True
                    assert main_window.vfi_worker is new_worker
                    main_window._set_processing_state.assert_called_with(True)
                    main_window.main_view_model.processing_vm.start_processing.assert_called_once()
                
                return {
                    "scenario": scenario_name,
                    "integration_complete": True,
                    "worker_replaced": True
                }
            
            def _test_edge_cases(self, scenario_name: str) -> Dict[str, Any]:
                """Test edge cases and boundary conditions."""
                results = {}
                
                if scenario_name == "worker_assignment_timing":
                    main_window = self.create_mock_main_window()
                    args = self.arg_configs["valid"]
                    
                    with patch("goesvfi.gui_components.processing_handler.WorkerFactory") as mock_worker_factory:
                        mock_worker = self.create_mock_worker()
                        mock_worker_factory.create_worker.return_value = mock_worker
                        
                        # Worker should not be assigned yet
                        initial_worker = main_window.vfi_worker
                        
                        self.handler.handle_processing(main_window, args)
                        
                        # Worker should now be assigned
                        assert main_window.vfi_worker is mock_worker
                        assert main_window.vfi_worker is not initial_worker
                        results["timing_correct"] = True
                
                elif scenario_name == "error_dialog_content":
                    main_window = self.create_mock_main_window()
                    args = self.arg_configs["valid"]
                    
                    with patch("goesvfi.gui_components.processing_handler.WorkerFactory") as mock_worker_factory:
                        with patch("goesvfi.gui_components.processing_handler.QMessageBox") as mock_qmessage_box:
                            error_msg = "Specific error message"
                            mock_worker_factory.create_worker.side_effect = RuntimeError(error_msg)
                            
                            self.handler.handle_processing(main_window, args)
                            
                            # Check error dialog content
                            call_args = mock_qmessage_box.critical.call_args[0]
                            assert call_args[0] is main_window  # parent
                            assert call_args[1] == "Error"  # title
                            assert error_msg in call_args[2]  # message contains specific error
                            results["error_dialog_correct"] = True
                
                elif scenario_name == "create_and_start_worker_success":
                    main_window = self.create_mock_main_window()
                    args = self.arg_configs["valid"]
                    
                    with patch("goesvfi.gui_components.processing_handler.WorkerFactory") as mock_worker_factory:
                        mock_worker = self.create_mock_worker()
                        mock_worker_factory.create_worker.return_value = mock_worker
                        
                        result = self.handler._create_and_start_worker(main_window, args)
                        
                        # Should return True
                        assert result is True
                        
                        # Should create worker
                        mock_worker_factory.create_worker.assert_called_once_with(args, False)
                        
                        # Should setup connections
                        main_window.signal_broker.setup_worker_connections.assert_called_once_with(main_window, mock_worker)
                        
                        # Should start worker
                        mock_worker.start.assert_called_once()
                        
                        # Should assign worker
                        assert main_window.vfi_worker is mock_worker
                        results["worker_creation_success"] = True
                
                elif scenario_name == "create_and_start_worker_failure":
                    main_window = self.create_mock_main_window()
                    args = self.arg_configs["valid"]
                    
                    with patch("goesvfi.gui_components.processing_handler.WorkerFactory") as mock_worker_factory:
                        with patch("goesvfi.gui_components.processing_handler.QMessageBox") as mock_qmessage_box:
                            with patch("goesvfi.gui_components.processing_handler.LOGGER") as mock_logger:
                                mock_worker_factory.create_worker.side_effect = ValueError("Invalid arguments")
                                
                                result = self.handler._create_and_start_worker(main_window, args)
                                
                                # Should return False
                                assert result is False
                                
                                # Should log exception
                                mock_logger.exception.assert_called_once()
                                
                                # Should reset processing state
                                assert main_window.is_processing is False
                                main_window._set_processing_state.assert_called_with(False)
                                
                                # Should show error dialog
                                mock_qmessage_box.critical.assert_called_once()
                                error_args = mock_qmessage_box.critical.call_args[0]
                                assert "Failed to initialize processing pipeline" in error_args[2]
                                
                                # Should reset start button
                                main_window.main_tab._reset_start_button.assert_called_once()
                                results["worker_creation_failure"] = True
                
                return {
                    "scenario": scenario_name,
                    "results": results
                }
            
            def _test_performance_validation(self, scenario_name: str) -> Dict[str, Any]:
                """Test performance and batch processing scenarios."""
                results = {}
                
                if scenario_name == "multiple_processing_attempts":
                    # Test rapid processing attempts
                    main_window = self.create_mock_main_window()
                    args = self.arg_configs["valid"]
                    
                    with patch("goesvfi.gui_components.processing_handler.LOGGER") as mock_logger:
                        # First call should work
                        with patch("goesvfi.gui_components.processing_handler.WorkerFactory") as mock_worker_factory:
                            mock_worker = self.create_mock_worker()
                            mock_worker_factory.create_worker.return_value = mock_worker
                            
                            self.handler.handle_processing(main_window, args)
                            assert main_window.is_processing is True
                            
                            # Second call should be rejected
                            self.handler.handle_processing(main_window, args)
                            mock_logger.warning.assert_called()
                            
                    results["rapid_attempts_handled"] = True
                
                elif scenario_name == "argument_variations":
                    # Test processing with different argument configurations
                    main_window = self.create_mock_main_window()
                    successful_configs = 0
                    
                    for config_name, args in self.arg_configs.items():
                        if config_name in ["empty", "none"]:
                            continue  # Skip invalid configs
                        
                        main_window.is_processing = False  # Reset for each test
                        
                        with patch("goesvfi.gui_components.processing_handler.WorkerFactory") as mock_worker_factory:
                            mock_worker = self.create_mock_worker()
                            mock_worker_factory.create_worker.return_value = mock_worker
                            
                            self.handler.handle_processing(main_window, args)
                            
                            if main_window.is_processing:
                                successful_configs += 1
                    
                    results["successful_configs"] = successful_configs
                    results["total_configs"] = len([k for k in self.arg_configs.keys() if k not in ["empty", "none"]])
                
                return {
                    "scenario": scenario_name,
                    "results": results
                }
        
        return {
            "manager": ProcessingHandlerTestManager(),
            "handler": ProcessingHandlerTestManager().handler
        }

    def test_successful_processing_workflows(self, processing_test_components) -> None:
        """Test successful processing workflows."""
        manager = processing_test_components["manager"]
        
        # Test normal processing
        result = manager._test_successful_processing("normal", manager.arg_configs["valid"])
        assert result["success"] is True
        assert result["worker_created"] is True
        
        # Test debug mode processing
        result = manager._test_successful_processing("debug", manager.arg_configs["valid"], debug_mode=True)
        assert result["success"] is True
        assert result["debug_mode"] is True

    def test_processing_validation_scenarios(self, processing_test_components) -> None:
        """Test processing validation scenarios."""
        manager = processing_test_components["manager"]
        
        # Test already processing
        result = manager._test_processing_validation("already_processing", manager.arg_configs["valid"], None)
        assert result["validation_triggered"] is True
        
        # Test empty args
        result = manager._test_processing_validation("empty_args", manager.arg_configs["empty"], "Empty args dictionary")
        assert result["validation_triggered"] is True
        
        # Test none args
        result = manager._test_processing_validation("none_args", manager.arg_configs["none"], None)
        assert result["validation_triggered"] is True

    def test_error_handling_scenarios(self, processing_test_components) -> None:
        """Test error handling scenarios."""
        manager = processing_test_components["manager"]
        
        # Test different error types
        error_scenarios = [
            ("worker_creation_failure", Exception("Worker creation failed")),
            ("value_error", ValueError("Invalid arguments")),
            ("runtime_error", RuntimeError("Runtime failure")),
            ("type_error", TypeError("Type mismatch"))
        ]
        
        for scenario_name, error in error_scenarios:
            result = manager._test_error_handling(scenario_name, error, manager.arg_configs["valid"])
            assert result["error_handled"] is True
            assert result["state_reset"] is True

    def test_worker_management_scenarios(self, processing_test_components) -> None:
        """Test worker management scenarios."""
        manager = processing_test_components["manager"]
        
        worker_scenarios = [
            ("no_worker", {}),
            ("worker_not_running", {"is_running": False}),
            ("worker_running", {"is_running": True}),
            ("termination_exception", {"is_running": True, "terminate_exception": Exception("Termination failed")})
        ]
        
        for scenario_name, config in worker_scenarios:
            result = manager._test_worker_management(scenario_name, config)
            assert "scenario" in result
            assert result["scenario"] == scenario_name

    def test_state_consistency_validation(self, processing_test_components) -> None:
        """Test state consistency scenarios."""
        manager = processing_test_components["manager"]
        
        result = manager._test_state_consistency("error_state_reset")
        assert result["state_consistent"] is True

    def test_logging_behavior_validation(self, processing_test_components) -> None:
        """Test logging behavior validation."""
        manager = processing_test_components["manager"]
        
        result = manager._test_logging_validation("comprehensive_logging")
        assert result["logging_validated"] is True

    def test_integration_workflow_scenarios(self, processing_test_components) -> None:
        """Test complete integration workflows."""
        manager = processing_test_components["manager"]
        
        result = manager._test_integration_workflows("worker_replacement")
        assert result["integration_complete"] is True
        assert result["worker_replaced"] is True

    def test_edge_case_scenarios(self, processing_test_components) -> None:
        """Test edge cases and boundary conditions."""
        manager = processing_test_components["manager"]
        
        edge_case_scenarios = [
            "worker_assignment_timing",
            "error_dialog_content",
            "create_and_start_worker_success",
            "create_and_start_worker_failure"
        ]
        
        for scenario in edge_case_scenarios:
            result = manager._test_edge_cases(scenario)
            assert result["scenario"] == scenario
            assert len(result["results"]) > 0

    def test_performance_validation_scenarios(self, processing_test_components) -> None:
        """Test performance and batch processing scenarios."""
        manager = processing_test_components["manager"]
        
        performance_scenarios = [
            "multiple_processing_attempts",
            "argument_variations"
        ]
        
        for scenario in performance_scenarios:
            result = manager._test_performance_validation(scenario)
            assert result["scenario"] == scenario
            assert len(result["results"]) > 0

    @pytest.mark.parametrize("arg_config,debug_mode,expected_success", [
        ("valid", False, True),
        ("valid", True, True),
        ("minimal", False, True),
        ("complete", False, True),
        ("complete", True, True),
    ])
    def test_processing_argument_variations(self, processing_test_components, arg_config, debug_mode, expected_success) -> None:
        """Test processing with various argument configurations."""
        manager = processing_test_components["manager"]
        args = manager.arg_configs[arg_config]
        
        result = manager._test_successful_processing(f"args_{arg_config}", args, debug_mode)
        assert result["success"] == expected_success
        assert result["debug_mode"] == debug_mode

    def test_comprehensive_error_coverage(self, processing_test_components) -> None:
        """Test comprehensive error coverage scenarios."""
        manager = processing_test_components["manager"]
        
        # Test error scenarios with different combinations
        error_combinations = [
            (Exception("General error"), "General exception"),
            (ValueError("Invalid value"), "Value validation"),
            (RuntimeError("Runtime issue"), "Runtime failure"),
            (TypeError("Type issue"), "Type validation"),
            (OSError("System error"), "System failure")
        ]
        
        for error, description in error_combinations:
            result = manager._test_error_handling(description, error, manager.arg_configs["valid"])
            assert result["error_handled"] is True
            assert result["state_reset"] is True

    def test_processing_handler_edge_cases(self, processing_test_components) -> None:
        """Test ProcessingHandler edge cases and boundary conditions."""
        manager = processing_test_components["manager"]
        
        # Test with various worker states
        worker_states = [
            {"is_running": True, "name": "active_worker"},
            {"is_running": False, "name": "inactive_worker"},
            {"terminate_exception": Exception("Cannot terminate"), "name": "problematic_worker"}
        ]
        
        for state in worker_states:
            result = manager._test_worker_management(state["name"], state)
            assert result["scenario"] == state["name"]

    def test_processing_handler_integration_validation(self, processing_test_components) -> None:
        """Test complete ProcessingHandler integration scenarios."""
        manager = processing_test_components["manager"]
        
        # Test complete workflow
        result = manager._test_integration_workflows("complete_workflow")
        assert result["integration_complete"] is True
        
        # Test state consistency
        result = manager._test_state_consistency("complete_state_check")
        assert result["state_consistent"] is True
        
        # Test logging behavior
        result = manager._test_logging_validation("complete_logging_check")
        assert result["logging_validated"] is True

    def test_processing_handler_performance_scenarios(self, processing_test_components) -> None:
        """Test ProcessingHandler performance and efficiency scenarios."""
        manager = processing_test_components["manager"]
        
        # Test batch processing scenarios
        batch_results = []
        for i in range(10):
            result = manager._test_successful_processing(f"batch_{i}", manager.arg_configs["valid"])
            batch_results.append(result["success"])
        
        # All should succeed
        assert all(batch_results)
        assert len(batch_results) == 10
        
        # Test error recovery scenarios
        error_recovery_results = []
        for error_type in [ValueError, RuntimeError, TypeError]:
            result = manager._test_error_handling(f"recovery_{error_type.__name__}", error_type("Test"), manager.arg_configs["valid"])
            error_recovery_results.append(result["error_handled"])
        
        # All errors should be handled
        assert all(error_recovery_results)
        assert len(error_recovery_results) == 3