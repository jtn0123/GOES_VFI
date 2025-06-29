"""
Optimized unit tests for ProcessingManager component with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for QApplication, ProcessingManager, and signal tracking
- Combined validation testing scenarios with parameterized arguments
- Enhanced test managers for comprehensive processing workflow coverage
- Batch testing of state management and error handling scenarios
"""

from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication
import pytest

from goesvfi.gui_components.processing_manager import ProcessingManager


class TestProcessingManagerOptimizedV2:
    """Optimized ProcessingManager tests with full coverage."""

    @pytest.fixture(scope="class")
    def processing_manager_test_components(self):
        """Create shared components for ProcessingManager testing."""

        # Ensure QApplication exists
        app = QApplication([]) if not QApplication.instance() else cast("QApplication", QApplication.instance())

        # Enhanced ProcessingManager Test Manager
        class ProcessingManagerTestManager:
            """Manage ProcessingManager testing scenarios."""

            def __init__(self) -> None:
                self.app = app

                # Define argument configurations for testing
                self.arg_configs = {
                    "valid_basic": {
                        "input_dir": str(Path(__file__).parent),
                        "output_file": "/tmp/test_output.mp4",
                        "model_location": str(Path(__file__).parent),
                    },
                    "valid_complete": {
                        "input_dir": str(Path(__file__).parent),
                        "output_file": "/tmp/test_output.mp4",
                        "model_location": str(Path(__file__).parent),
                        "exp": 2,
                        "fps": 30,
                    },
                    "missing_input": {
                        "output_file": "/tmp/test_output.mp4",
                        "model_location": "/path/to/models",
                    },
                    "invalid_input": {
                        "input_dir": "/non/existent/directory",
                        "output_file": "/tmp/test_output.mp4",
                        "model_location": str(Path(__file__).parent),
                    },
                    "invalid_fps": {
                        "input_dir": str(Path(__file__).parent),
                        "output_file": "/tmp/test_output.mp4",
                        "model_location": str(Path(__file__).parent),
                        "fps": 0,  # Invalid
                    },
                    "invalid_exp": {
                        "input_dir": str(Path(__file__).parent),
                        "output_file": "/tmp/test_output.mp4",
                        "model_location": str(Path(__file__).parent),
                        "exp": 0,  # Invalid
                    },
                    "missing_output": {
                        "input_dir": str(Path(__file__).parent),
                        "model_location": str(Path(__file__).parent),
                    },
                }

                # Define validation test scenarios
                self.validation_scenarios = [
                    ("valid_basic", True, ""),
                    ("valid_complete", True, ""),
                    ("missing_input", False, "No input directory"),
                    ("invalid_input", False, "does not exist"),
                    ("invalid_fps", False, "FPS must be greater than 0"),
                    ("invalid_exp", False, "Interpolation factor must be at least 1"),
                ]

                # Define test scenarios
                self.test_scenarios = {
                    "initialization": self._test_initialization,
                    "validation": self._test_validation,
                    "processing_lifecycle": self._test_processing_lifecycle,
                    "signal_handling": self._test_signal_handling,
                    "error_handling": self._test_error_handling,
                    "state_management": self._test_state_management,
                    "edge_cases": self._test_edge_cases,
                    "integration_workflows": self._test_integration_workflows,
                    "performance_validation": self._test_performance_validation,
                }

            def create_processing_manager(self) -> ProcessingManager:
                """Create a fresh ProcessingManager instance."""
                return ProcessingManager()

            def create_signal_tracker(self, processing_manager: ProcessingManager) -> dict[str, bool | list[Any] | Any]:
                """Create a signal tracker for the processing manager."""
                emitted_signals: dict[str, bool | list[Any] | Any] = {
                    "started": False,
                    "progress": [],
                    "finished": None,
                    "error": None,
                    "state_changed": [],
                }

                def signal_emitted(signal_name: str, value: Any) -> None:
                    """Helper to track signal emissions."""
                    if signal_name in {"progress", "state_changed"}:
                        signal_list = emitted_signals[signal_name]
                        if isinstance(signal_list, list):
                            signal_list.append(value)
                    else:
                        emitted_signals[signal_name] = value

                # Connect signals to track emissions
                processing_manager.processing_started.connect(lambda: signal_emitted("started", True))
                processing_manager.processing_progress.connect(lambda c, t, e: signal_emitted("progress", (c, t, e)))
                processing_manager.processing_finished.connect(lambda p: signal_emitted("finished", p))
                processing_manager.processing_error.connect(lambda e: signal_emitted("error", e))
                processing_manager.processing_state_changed.connect(lambda s: signal_emitted("state_changed", s))

                return emitted_signals

            def cleanup_processing_manager(self, processing_manager: ProcessingManager) -> None:
                """Clean up processing manager state."""
                if processing_manager.is_processing:
                    processing_manager.stop_processing()

            def _test_initialization(self, scenario_name: str) -> dict[str, Any]:
                """Test ProcessingManager initialization."""
                processing_manager = self.create_processing_manager()

                # Test initial state
                assert processing_manager.is_processing is False
                assert processing_manager.worker_thread is None
                assert processing_manager.worker is None
                assert processing_manager.current_output_path is None

                return {"scenario": scenario_name, "initialization_valid": True, "initial_state_correct": True}

            def _test_validation(
                self, scenario_name: str, config_name: str, expected_valid: bool, expected_error: str
            ) -> dict[str, Any]:
                """Test argument validation scenarios."""
                processing_manager = self.create_processing_manager()
                args = self.arg_configs[config_name]

                is_valid, error = processing_manager.validate_processing_args(args)

                assert is_valid == expected_valid
                if expected_error:
                    assert expected_error in error
                else:
                    assert error == ""

                self.cleanup_processing_manager(processing_manager)

                return {
                    "scenario": scenario_name,
                    "config": config_name,
                    "validation_correct": True,
                    "expected_valid": expected_valid,
                    "got_valid": is_valid,
                }

            def _test_processing_lifecycle(self, scenario_name: str, config_name: str) -> dict[str, Any]:
                """Test processing lifecycle scenarios."""
                processing_manager = self.create_processing_manager()
                signal_tracker = self.create_signal_tracker(processing_manager)
                args = self.arg_configs[config_name]

                results = {}

                if scenario_name == "start_success":
                    with patch("goesvfi.gui_components.processing_manager.VfiWorker") as mock_worker:
                        with patch("goesvfi.gui_components.processing_manager.QThread") as mock_qthread:
                            # Setup mocks
                            mock_thread_instance = MagicMock()
                            mock_qthread.return_value = mock_thread_instance
                            mock_worker_instance = MagicMock()
                            mock_worker.return_value = mock_worker_instance

                            # Start processing
                            result = processing_manager.start_processing(args)

                            # Verify
                            assert result is True
                            assert processing_manager.is_processing is True
                            assert processing_manager.current_output_path == Path(args["output_file"])

                            # Verify signals were emitted
                            assert signal_tracker["started"] is True
                            state_changes = cast("list[Any]", signal_tracker["state_changed"])
                            assert isinstance(state_changes, list)
                            assert True in state_changes

                            # Verify thread was started
                            mock_thread_instance.start.assert_called_once()

                            results["start_successful"] = True

                elif scenario_name == "start_while_processing":
                    # Set processing state
                    processing_manager.is_processing = True

                    # Try to start processing
                    result = processing_manager.start_processing(args)

                    # Should fail
                    assert result is False
                    results["rejected_when_processing"] = True

                elif scenario_name == "start_with_missing_arg":
                    args_missing = self.arg_configs["missing_output"]

                    # Try to start processing
                    result = processing_manager.start_processing(args_missing)

                    # Should fail
                    assert result is False
                    error_msg = signal_tracker["error"]
                    assert error_msg is not None
                    assert isinstance(error_msg, str)
                    assert "Missing required argument" in error_msg

                    results["missing_arg_handled"] = True

                self.cleanup_processing_manager(processing_manager)

                return {"scenario": scenario_name, "results": results}

            def _test_signal_handling(self, scenario_name: str) -> dict[str, Any]:
                """Test signal handling scenarios."""
                processing_manager = self.create_processing_manager()
                signal_tracker = self.create_signal_tracker(processing_manager)

                results = {}

                if scenario_name == "progress_handling":
                    # Simulate progress update
                    processing_manager._handle_progress(50, 100, 60.0)

                    # Verify signal was emitted
                    progress_list = cast("list[Any]", signal_tracker["progress"])
                    assert isinstance(progress_list, list)
                    assert len(progress_list) == 1
                    assert progress_list[0] == (50, 100, 60.0)

                    results["progress_tracked"] = True

                elif scenario_name == "finished_handling":
                    # Set processing state
                    processing_manager.is_processing = True

                    # Simulate completion
                    processing_manager._handle_finished("/tmp/output.mp4")

                    # Verify state
                    assert processing_manager.is_processing is False
                    assert signal_tracker["finished"] == "/tmp/output.mp4"
                    state_changes = cast("list[Any]", signal_tracker["state_changed"])
                    assert isinstance(state_changes, list)
                    assert False in state_changes

                    results["finished_handled"] = True

                elif scenario_name == "error_handling":
                    # Set processing state
                    processing_manager.is_processing = True

                    # Simulate error
                    processing_manager._handle_error("Test error message")

                    # Verify state
                    assert processing_manager.is_processing is False
                    assert signal_tracker["error"] == "Test error message"
                    state_changes = cast("list[Any]", signal_tracker["state_changed"])
                    assert isinstance(state_changes, list)
                    assert False in state_changes

                    results["error_handled"] = True

                self.cleanup_processing_manager(processing_manager)

                return {"scenario": scenario_name, "results": results}

            def _test_error_handling(self, scenario_name: str) -> dict[str, Any]:
                """Test error handling scenarios."""
                processing_manager = self.create_processing_manager()
                signal_tracker = self.create_signal_tracker(processing_manager)

                results = {}

                # Test various error scenarios
                error_scenarios = [
                    ("validation_error", "Invalid arguments"),
                    ("runtime_error", "Runtime failure"),
                    ("processing_error", "Processing failed"),
                    ("system_error", "System failure"),
                ]

                for error_type, error_message in error_scenarios:
                    processing_manager.is_processing = True
                    processing_manager._handle_error(error_message)

                    # Verify error was handled
                    assert processing_manager.is_processing is False
                    assert signal_tracker["error"] == error_message

                    # Reset for next test
                    signal_tracker["error"] = None
                    results[error_type] = True

                self.cleanup_processing_manager(processing_manager)

                return {"scenario": scenario_name, "results": results}

            def _test_state_management(self, scenario_name: str) -> dict[str, Any]:
                """Test state management scenarios."""
                processing_manager = self.create_processing_manager()

                results = {}

                if scenario_name == "processing_state":
                    # Initially false
                    assert processing_manager.get_processing_state() is False

                    # Set to true
                    processing_manager.is_processing = True
                    assert processing_manager.get_processing_state() is True

                    results["state_tracking"] = True

                elif scenario_name == "output_path_tracking":
                    # Initially None
                    assert processing_manager.get_current_output_path() is None

                    # Set output path and processing state
                    test_path = Path("/tmp/test.mp4")
                    processing_manager.current_output_path = test_path
                    processing_manager.is_processing = True

                    # Should return path when processing
                    assert processing_manager.get_current_output_path() == test_path

                    # Should return None when not processing
                    processing_manager.is_processing = False
                    assert processing_manager.get_current_output_path() is None

                    results["path_tracking"] = True

                elif scenario_name == "stop_not_running":
                    # Should not crash
                    processing_manager.stop_processing()

                    # Verify nothing changed
                    assert processing_manager.is_processing is False
                    results["stop_safe"] = True

                elif scenario_name == "stop_running":
                    with patch("goesvfi.gui_components.processing_manager.QThread"):
                        # Setup mock thread
                        mock_thread = MagicMock()
                        mock_thread.isRunning.return_value = True
                        mock_thread.wait.return_value = True

                        # Set up processing state
                        processing_manager.worker_thread = mock_thread
                        processing_manager.worker = MagicMock()
                        processing_manager.is_processing = True

                        # Stop processing
                        processing_manager.stop_processing()

                        # Verify thread was waited on
                        mock_thread.wait.assert_called_once_with(5000)
                        results["stop_with_thread"] = True

                self.cleanup_processing_manager(processing_manager)

                return {"scenario": scenario_name, "results": results}

            def _test_edge_cases(self, scenario_name: str) -> dict[str, Any]:
                """Test edge cases and boundary conditions."""
                processing_manager = self.create_processing_manager()

                results = {}

                if scenario_name == "multiple_progress_updates":
                    signal_tracker = self.create_signal_tracker(processing_manager)

                    # Send multiple progress updates
                    for i in range(10):
                        processing_manager._handle_progress(i * 10, 100, float(i * 10))

                    # Verify all were tracked
                    progress_list = cast("list[Any]", signal_tracker["progress"])
                    assert len(progress_list) == 10

                    results["multiple_progress"] = True

                elif scenario_name == "rapid_state_changes":
                    signal_tracker = self.create_signal_tracker(processing_manager)

                    # Rapid state changes
                    for i in range(5):
                        processing_manager.is_processing = True
                        processing_manager._handle_finished(f"/tmp/output_{i}.mp4")
                        processing_manager.is_processing = False

                    # Verify state changes were tracked
                    state_changes = cast("list[Any]", signal_tracker["state_changed"])
                    assert len(state_changes) >= 5

                    results["rapid_changes"] = True

                elif scenario_name == "error_recovery":
                    signal_tracker = self.create_signal_tracker(processing_manager)

                    # Set error state
                    processing_manager.is_processing = True
                    processing_manager._handle_error("Test error")

                    # Verify recovery
                    assert processing_manager.is_processing is False

                    # Try to start again
                    args = self.arg_configs["valid_basic"]
                    with patch("goesvfi.gui_components.processing_manager.VfiWorker"):
                        with patch("goesvfi.gui_components.processing_manager.QThread") as mock_qthread:
                            mock_thread = MagicMock()
                            mock_qthread.return_value = mock_thread

                            result = processing_manager.start_processing(args)
                            assert result is True  # Should be able to start again

                    results["error_recovery"] = True

                self.cleanup_processing_manager(processing_manager)

                return {"scenario": scenario_name, "results": results}

            def _test_integration_workflows(self, scenario_name: str) -> dict[str, Any]:
                """Test complete integration workflows."""
                processing_manager = self.create_processing_manager()
                signal_tracker = self.create_signal_tracker(processing_manager)

                results = {}

                if scenario_name == "complete_lifecycle":
                    args = self.arg_configs["valid_complete"]

                    with patch("goesvfi.gui_components.processing_manager.VfiWorker") as mock_worker:
                        with patch("goesvfi.gui_components.processing_manager.QThread") as mock_qthread:
                            # Setup mocks
                            mock_thread = MagicMock()
                            mock_qthread.return_value = mock_thread
                            mock_worker_instance = MagicMock()
                            mock_worker.return_value = mock_worker_instance

                            # Start processing
                            start_result = processing_manager.start_processing(args)
                            assert start_result is True

                            # Simulate progress
                            processing_manager._handle_progress(25, 100, 30.0)
                            processing_manager._handle_progress(50, 100, 60.0)
                            processing_manager._handle_progress(75, 100, 90.0)

                            # Simulate completion
                            processing_manager._handle_finished(args["output_file"])

                            # Verify complete workflow
                            assert signal_tracker["started"] is True
                            progress_list = cast("list[Any]", signal_tracker["progress"])
                            assert len(progress_list) == 3
                            assert signal_tracker["finished"] == args["output_file"]
                            assert processing_manager.is_processing is False

                            results["complete_workflow"] = True

                elif scenario_name == "workflow_with_error":
                    args = self.arg_configs["valid_basic"]

                    with patch("goesvfi.gui_components.processing_manager.VfiWorker") as mock_worker:
                        with patch("goesvfi.gui_components.processing_manager.QThread") as mock_qthread:
                            # Setup mocks
                            mock_thread = MagicMock()
                            mock_qthread.return_value = mock_thread
                            mock_worker_instance = MagicMock()
                            mock_worker.return_value = mock_worker_instance

                            # Start processing
                            start_result = processing_manager.start_processing(args)
                            assert start_result is True

                            # Simulate progress
                            processing_manager._handle_progress(30, 100, 45.0)

                            # Simulate error
                            processing_manager._handle_error("Processing failed")

                            # Verify error workflow
                            assert signal_tracker["started"] is True
                            assert signal_tracker["error"] == "Processing failed"
                            assert processing_manager.is_processing is False

                            results["error_workflow"] = True

                self.cleanup_processing_manager(processing_manager)

                return {"scenario": scenario_name, "results": results}

            def _test_performance_validation(self, scenario_name: str) -> dict[str, Any]:
                """Test performance and efficiency scenarios."""
                results = {}

                if scenario_name == "batch_validation":
                    # Test batch validation of arguments
                    validation_results = []

                    for config_name, expected_valid, _expected_error in self.validation_scenarios:
                        processing_manager = self.create_processing_manager()
                        args = self.arg_configs[config_name]

                        is_valid, error = processing_manager.validate_processing_args(args)
                        validation_results.append({
                            "config": config_name,
                            "valid": is_valid,
                            "expected": expected_valid,
                            "error": error,
                        })

                        self.cleanup_processing_manager(processing_manager)

                    # All validations should match expectations
                    all_correct = all(result["valid"] == result["expected"] for result in validation_results)

                    results["batch_validation"] = all_correct
                    results["validation_count"] = len(validation_results)

                elif scenario_name == "stress_testing":
                    processing_manager = self.create_processing_manager()
                    signal_tracker = self.create_signal_tracker(processing_manager)

                    # Stress test with many signal emissions
                    for i in range(100):
                        processing_manager._handle_progress(i, 100, float(i))

                    # Verify all signals were handled
                    progress_list = cast("list[Any]", signal_tracker["progress"])
                    assert len(progress_list) == 100

                    results["stress_test"] = True

                    self.cleanup_processing_manager(processing_manager)

                return {"scenario": scenario_name, "results": results}

        return {"manager": ProcessingManagerTestManager(), "app": app}

    def test_processing_manager_initialization(self, processing_manager_test_components) -> None:
        """Test ProcessingManager initialization."""
        manager = processing_manager_test_components["manager"]

        result = manager._test_initialization("basic_init")
        assert result["initialization_valid"] is True
        assert result["initial_state_correct"] is True

    @pytest.mark.parametrize(
        "config_name,expected_valid,expected_error",
        [
            ("valid_basic", True, ""),
            ("valid_complete", True, ""),
            ("missing_input", False, "No input directory"),
            ("invalid_input", False, "does not exist"),
            ("invalid_fps", False, "FPS must be greater than 0"),
            ("invalid_exp", False, "Interpolation factor must be at least 1"),
        ],
    )
    def test_argument_validation_scenarios(
        self, processing_manager_test_components, config_name, expected_valid, expected_error
    ) -> None:
        """Test argument validation scenarios."""
        manager = processing_manager_test_components["manager"]

        result = manager._test_validation("validation_test", config_name, expected_valid, expected_error)
        assert result["validation_correct"] is True
        assert result["expected_valid"] == expected_valid
        assert result["got_valid"] == expected_valid

    def test_processing_lifecycle_scenarios(self, processing_manager_test_components) -> None:
        """Test processing lifecycle scenarios."""
        manager = processing_manager_test_components["manager"]

        lifecycle_scenarios = [
            ("start_success", "valid_complete"),
            ("start_while_processing", "valid_basic"),
            ("start_with_missing_arg", "valid_basic"),
        ]

        for scenario_name, config_name in lifecycle_scenarios:
            result = manager._test_processing_lifecycle(scenario_name, config_name)
            assert result["scenario"] == scenario_name
            assert len(result["results"]) > 0

    def test_signal_handling_scenarios(self, processing_manager_test_components) -> None:
        """Test signal handling scenarios."""
        manager = processing_manager_test_components["manager"]

        signal_scenarios = ["progress_handling", "finished_handling", "error_handling"]

        for scenario in signal_scenarios:
            result = manager._test_signal_handling(scenario)
            assert result["scenario"] == scenario
            assert len(result["results"]) > 0

    def test_error_handling_comprehensive(self, processing_manager_test_components) -> None:
        """Test comprehensive error handling scenarios."""
        manager = processing_manager_test_components["manager"]

        result = manager._test_error_handling("comprehensive_errors")
        assert result["scenario"] == "comprehensive_errors"
        assert len(result["results"]) == 4  # Should test 4 error types

    def test_state_management_scenarios(self, processing_manager_test_components) -> None:
        """Test state management scenarios."""
        manager = processing_manager_test_components["manager"]

        state_scenarios = ["processing_state", "output_path_tracking", "stop_not_running", "stop_running"]

        for scenario in state_scenarios:
            result = manager._test_state_management(scenario)
            assert result["scenario"] == scenario
            assert len(result["results"]) > 0

    def test_edge_case_scenarios(self, processing_manager_test_components) -> None:
        """Test edge cases and boundary conditions."""
        manager = processing_manager_test_components["manager"]

        edge_cases = ["multiple_progress_updates", "rapid_state_changes", "error_recovery"]

        for scenario in edge_cases:
            result = manager._test_edge_cases(scenario)
            assert result["scenario"] == scenario
            assert len(result["results"]) > 0

    def test_integration_workflow_scenarios(self, processing_manager_test_components) -> None:
        """Test complete integration workflows."""
        manager = processing_manager_test_components["manager"]

        integration_scenarios = ["complete_lifecycle", "workflow_with_error"]

        for scenario in integration_scenarios:
            result = manager._test_integration_workflows(scenario)
            assert result["scenario"] == scenario
            assert len(result["results"]) > 0

    def test_performance_validation_scenarios(self, processing_manager_test_components) -> None:
        """Test performance and efficiency scenarios."""
        manager = processing_manager_test_components["manager"]

        performance_scenarios = ["batch_validation", "stress_testing"]

        for scenario in performance_scenarios:
            result = manager._test_performance_validation(scenario)
            assert result["scenario"] == scenario
            assert len(result["results"]) > 0

    def test_processing_manager_comprehensive_validation(self, processing_manager_test_components) -> None:
        """Test comprehensive ProcessingManager validation."""
        manager = processing_manager_test_components["manager"]

        # Test all validation scenarios in batch
        result = manager._test_performance_validation("batch_validation")
        assert result["results"]["batch_validation"] is True
        assert result["results"]["validation_count"] == len(manager.validation_scenarios)

    def test_processing_manager_signal_integration(self, processing_manager_test_components) -> None:
        """Test ProcessingManager signal integration."""
        manager = processing_manager_test_components["manager"]

        # Test comprehensive signal handling
        signal_types = ["progress_handling", "finished_handling", "error_handling"]

        all_results = []
        for signal_type in signal_types:
            result = manager._test_signal_handling(signal_type)
            all_results.append(result)

        # All signal types should be handled correctly
        assert len(all_results) == 3
        assert all(len(result["results"]) > 0 for result in all_results)

    def test_processing_manager_state_consistency(self, processing_manager_test_components) -> None:
        """Test ProcessingManager state consistency."""
        manager = processing_manager_test_components["manager"]

        # Test state consistency across scenarios
        state_scenarios = ["processing_state", "output_path_tracking", "stop_not_running", "stop_running"]

        state_results = []
        for scenario in state_scenarios:
            result = manager._test_state_management(scenario)
            state_results.append(result)

        # All state scenarios should be consistent
        assert len(state_results) == 4
        assert all(len(result["results"]) > 0 for result in state_results)

    def test_processing_manager_error_recovery_validation(self, processing_manager_test_components) -> None:
        """Test ProcessingManager error recovery validation."""
        manager = processing_manager_test_components["manager"]

        # Test error recovery workflow
        result = manager._test_edge_cases("error_recovery")
        assert result["scenario"] == "error_recovery"
        assert result["results"]["error_recovery"] is True

    def test_processing_manager_performance_stress(self, processing_manager_test_components) -> None:
        """Test ProcessingManager performance under stress."""
        manager = processing_manager_test_components["manager"]

        # Test stress scenario
        result = manager._test_performance_validation("stress_testing")
        assert result["scenario"] == "stress_testing"
        assert result["results"]["stress_test"] is True
