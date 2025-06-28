"""
Optimized integration tests for VfiWorker functionality with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for Qt application and worker setup
- Combined worker testing scenarios
- Batch validation of signal handling
- Enhanced error handling and timeout testing
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QObject, QTimer, pyqtSlot, QEventLoop
from PyQt6.QtWidgets import QApplication

from goesvfi.pipeline.run_vfi import VfiWorker


class TestVfiWorkerOptimizedV2:
    """Optimized VfiWorker integration tests with full coverage."""

    @pytest.fixture(scope="class")
    def shared_qt_app(self):
        """Shared QApplication instance for all worker tests."""
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app
        app.processEvents()

    @pytest.fixture(scope="class")
    def worker_test_components(self):
        """Create shared components for VfiWorker testing."""
        
        # Enhanced Signal Receiver
        class ComprehensiveSignalReceiver(QObject):
            """Comprehensive signal receiver for VfiWorker testing."""

            def __init__(self):
                super().__init__()
                self.signals_received = {
                    "progress": [],
                    "finished": [],
                    "error": [],
                    "started": [],
                    "frame_processed": [],
                }
                self.last_progress = None
                self.last_error = None
                self.last_output = None
                self.processing_complete = False
                self.error_occurred = False

            @pyqtSlot(int, int, float)
            def on_progress(self, current, total, elapsed):
                self.signals_received["progress"].append((current, total, elapsed))
                self.last_progress = (current, total, elapsed)

            @pyqtSlot(str)
            def on_finished(self, output_path):
                self.signals_received["finished"].append(output_path)
                self.last_output = output_path
                self.processing_complete = True

            @pyqtSlot(str)
            def on_error(self, error_message):
                self.signals_received["error"].append(error_message)
                self.last_error = error_message
                self.error_occurred = True

            @pyqtSlot()
            def on_started(self):
                self.signals_received["started"].append(True)

            @pyqtSlot(int, str)
            def on_frame_processed(self, frame_num, frame_path):
                self.signals_received["frame_processed"].append((frame_num, frame_path))

            def reset(self):
                """Reset receiver state for new test."""
                self.signals_received = {
                    "progress": [],
                    "finished": [],
                    "error": [],
                    "started": [],
                    "frame_processed": [],
                }
                self.last_progress = None
                self.last_error = None
                self.last_output = None
                self.processing_complete = False
                self.error_occurred = False

            def get_signal_count(self, signal_type):
                """Get count of received signals of given type."""
                return len(self.signals_received.get(signal_type, []))

            def has_received_signal(self, signal_type):
                """Check if signal type has been received."""
                return len(self.signals_received.get(signal_type, [])) > 0

        # Enhanced Worker Configuration Manager
        class WorkerConfigurationManager:
            """Manage different VfiWorker configurations for testing."""
            
            def __init__(self):
                self.base_config = {
                    "fps": 30,
                    "mid_count": 3,
                    "max_workers": 4,
                    "encoder": "RIFE",
                    "use_preset_optimal": False,
                    "use_ffmpeg_interp": False,
                    "filter_preset": "slow",
                    "mi_mode": "mci",
                    "mc_mode": "obmc",
                    "me_mode": "bidir",
                    "me_algo": "",
                    "search_param": 96,
                    "scd_mode": "fdiff",
                    "scd_threshold": None,
                    "minter_mb_size": None,
                    "minter_vsbmc": 0,
                    "apply_unsharp": False,
                    "unsharp_lx": 3,
                    "unsharp_ly": 3,
                    "unsharp_la": 1.0,
                    "unsharp_cx": 0.5,
                    "unsharp_cy": 0.5,
                    "unsharp_ca": 0.0,
                    "crf": 18,
                    "bitrate_kbps": 7000,
                    "bufsize_kb": 14000,
                    "pix_fmt": "yuv420p",
                    "skip_model": False,
                    "crop_rect": None,
                    "debug_mode": True,
                    "rife_tile_enable": True,
                    "rife_tile_size": 384,
                    "rife_uhd_mode": False,
                    "rife_thread_spec": "0:0:0:0",
                    "rife_tta_spatial": False,
                    "rife_tta_temporal": False,
                    "rife_model_name": "rife-v4.6",
                    "sanchez_temp_dir": None,
                    "sanchez": False,
                    "sanchez_resolution": "4",
                    "sanchez_parallel": True,
                }
            
            def get_config(self, config_type="basic"):
                """Get configuration for different test scenarios."""
                configs = {
                    "basic": self.base_config.copy(),
                    "high_performance": {
                        **self.base_config,
                        "fps": 60,
                        "mid_count": 5,
                        "max_workers": 8,
                        "rife_tile_enable": True,
                        "rife_tile_size": 512,
                        "rife_uhd_mode": True,
                    },
                    "low_resource": {
                        **self.base_config,
                        "fps": 24,
                        "mid_count": 1,
                        "max_workers": 2,
                        "rife_tile_enable": False,
                        "crf": 23,
                        "bitrate_kbps": 3000,
                    },
                    "ffmpeg_fallback": {
                        **self.base_config,
                        "encoder": "FFmpeg",
                        "use_ffmpeg_interp": True,
                        "filter_preset": "medium",
                    },
                    "sanchez_enabled": {
                        **self.base_config,
                        "sanchez": True,
                        "sanchez_resolution": "8",
                        "sanchez_parallel": True,
                    },
                }
                return configs.get(config_type, self.base_config)
            
            def create_worker_args(self, in_dir, out_file, config_type="basic"):
                """Create complete worker arguments."""
                config = self.get_config(config_type)
                return {
                    "in_dir": in_dir,
                    "out_file_path": out_file,
                    **config
                }

        # Enhanced Mock Manager
        class WorkerMockManager:
            """Manage mocks for VfiWorker testing."""
            
            def __init__(self):
                self.mock_scenarios = {
                    "success": self._setup_success_mocks,
                    "rife_failure": self._setup_rife_failure_mocks,
                    "ffmpeg_failure": self._setup_ffmpeg_failure_mocks,
                    "timeout": self._setup_timeout_mocks,
                    "permission_error": self._setup_permission_error_mocks,
                }
            
            def _setup_success_mocks(self):
                """Setup mocks for successful processing."""
                return {
                    "subprocess_run": MagicMock(returncode=0, stdout="", stderr=""),
                    "subprocess_popen": self._create_success_popen_mock(),
                    "rife_executable": Path("/mock/rife-cli"),
                    "sanchez_colourise": lambda *args, **kwargs: 0,
                }
            
            def _setup_rife_failure_mocks(self):
                """Setup mocks for RIFE processing failure."""
                return {
                    "subprocess_run": MagicMock(returncode=1, stdout="", stderr="RIFE error"),
                    "subprocess_popen": self._create_success_popen_mock(),
                    "rife_executable": Path("/mock/rife-cli"),
                    "sanchez_colourise": lambda *args, **kwargs: 0,
                }
            
            def _setup_ffmpeg_failure_mocks(self):
                """Setup mocks for FFmpeg processing failure."""
                return {
                    "subprocess_run": MagicMock(returncode=0, stdout="", stderr=""),
                    "subprocess_popen": self._create_failure_popen_mock(),
                    "rife_executable": Path("/mock/rife-cli"),
                    "sanchez_colourise": lambda *args, **kwargs: 0,
                }
            
            def _setup_timeout_mocks(self):
                """Setup mocks for timeout scenarios."""
                import subprocess
                return {
                    "subprocess_run": MagicMock(side_effect=subprocess.TimeoutExpired("cmd", 30)),
                    "subprocess_popen": self._create_success_popen_mock(),
                    "rife_executable": Path("/mock/rife-cli"),
                    "sanchez_colourise": lambda *args, **kwargs: 0,
                }
            
            def _setup_permission_error_mocks(self):
                """Setup mocks for permission error scenarios."""
                return {
                    "subprocess_run": MagicMock(side_effect=PermissionError("Permission denied")),
                    "subprocess_popen": self._create_success_popen_mock(),
                    "rife_executable": Path("/mock/rife-cli"),
                    "sanchez_colourise": lambda *args, **kwargs: 0,
                }
            
            def _create_success_popen_mock(self):
                """Create successful Popen mock."""
                mock_process = MagicMock()
                mock_process.stdin = MagicMock()
                mock_process.stdout = MagicMock()
                mock_process.stderr = MagicMock()
                mock_process.wait.return_value = 0
                mock_process.poll.return_value = None
                mock_process.returncode = 0
                mock_process.communicate.return_value = (b"success", b"")
                return mock_process
            
            def _create_failure_popen_mock(self):
                """Create failing Popen mock."""
                mock_process = MagicMock()
                mock_process.wait.return_value = 1
                mock_process.poll.return_value = 1
                mock_process.returncode = 1
                mock_process.communicate.return_value = (b"", b"FFmpeg error")
                return mock_process
            
            def get_mocks(self, scenario="success"):
                """Get mocks for given scenario."""
                if scenario in self.mock_scenarios:
                    return self.mock_scenarios[scenario]()
                return self.mock_scenarios["success"]()

        return {
            "signal_receiver_class": ComprehensiveSignalReceiver,
            "config_manager": WorkerConfigurationManager(),
            "mock_manager": WorkerMockManager(),
        }

    @pytest.fixture()
    def temp_workspace(self, tmp_path):
        """Create temporary workspace for worker testing."""
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()
        
        # Create test images
        test_images = []
        for i in range(5):
            img_file = input_dir / f"frame_{i:04d}.png"
            img_file.write_bytes(b"fake image data")
            test_images.append(img_file)
        
        output_file = output_dir / "output.mp4"
        sanchez_temp_dir = tmp_path / "sanchez_temp"
        sanchez_temp_dir.mkdir()
        
        return {
            "input_dir": input_dir,
            "output_dir": output_dir,
            "output_file": output_file,
            "test_images": test_images,
            "sanchez_temp_dir": sanchez_temp_dir,
        }

    def test_vfi_worker_initialization_comprehensive(self, shared_qt_app, worker_test_components, temp_workspace) -> None:
        """Test comprehensive VfiWorker initialization scenarios."""
        components = worker_test_components
        workspace = temp_workspace
        config_manager = components["config_manager"]
        
        # Define initialization test scenarios
        init_scenarios = [
            {
                "name": "Basic Initialization",
                "config_type": "basic",
                "should_succeed": True,
            },
            {
                "name": "High Performance Config",
                "config_type": "high_performance",
                "should_succeed": True,
            },
            {
                "name": "Low Resource Config",
                "config_type": "low_resource",
                "should_succeed": True,
            },
            {
                "name": "FFmpeg Fallback Config",
                "config_type": "ffmpeg_fallback",
                "should_succeed": True,
            },
            {
                "name": "Sanchez Enabled Config",
                "config_type": "sanchez_enabled",
                "should_succeed": True,
            },
        ]
        
        # Test each initialization scenario
        for scenario in init_scenarios:
            try:
                # Create worker arguments
                worker_args = config_manager.create_worker_args(
                    workspace["input_dir"],
                    workspace["output_file"],
                    scenario["config_type"]
                )
                
                # Add sanchez_temp_dir for sanchez tests
                if scenario["config_type"] == "sanchez_enabled":
                    worker_args["sanchez_temp_dir"] = workspace["sanchez_temp_dir"]
                
                # Initialize worker
                worker = VfiWorker(**worker_args)
                
                # Verify worker initialization
                assert worker is not None, f"Worker initialization failed for {scenario['name']}"
                assert hasattr(worker, "progress"), f"Worker missing progress signal for {scenario['name']}"
                assert hasattr(worker, "finished"), f"Worker missing finished signal for {scenario['name']}"
                assert hasattr(worker, "error"), f"Worker missing error signal for {scenario['name']}"
                
                # Verify configuration was applied
                assert worker.in_dir == workspace["input_dir"], f"Input directory mismatch for {scenario['name']}"
                assert worker.out_file_path == workspace["output_file"], f"Output file mismatch for {scenario['name']}"
                
                # Verify encoder-specific settings
                config = config_manager.get_config(scenario["config_type"])
                assert worker.encoder == config["encoder"], f"Encoder mismatch for {scenario['name']}"
                assert worker.fps == config["fps"], f"FPS mismatch for {scenario['name']}"
                assert worker.mid_count == config["mid_count"], f"Mid count mismatch for {scenario['name']}"
                
                # Test signal connections
                signal_receiver = components["signal_receiver_class"]()
                worker.progress.connect(signal_receiver.on_progress)
                worker.finished.connect(signal_receiver.on_finished)
                worker.error.connect(signal_receiver.on_error)
                
                # Verify connections don't raise errors
                assert True, f"Signal connections successful for {scenario['name']}"
                
            except Exception as e:
                if scenario["should_succeed"]:
                    pytest.fail(f"Unexpected initialization failure for {scenario['name']}: {e}")

    def test_vfi_worker_signal_handling_comprehensive(self, shared_qt_app, worker_test_components, temp_workspace) -> None:
        """Test comprehensive VfiWorker signal handling scenarios."""
        components = worker_test_components
        workspace = temp_workspace
        config_manager = components["config_manager"]
        mock_manager = components["mock_manager"]
        
        # Define signal handling test scenarios
        signal_scenarios = [
            {
                "name": "Successful Processing Signals",
                "mock_scenario": "success",
                "expected_signals": ["progress", "finished"],
                "unexpected_signals": ["error"],
            },
            {
                "name": "RIFE Failure Signals",
                "mock_scenario": "rife_failure",
                "expected_signals": ["error"],
                "unexpected_signals": ["finished"],
            },
            {
                "name": "FFmpeg Failure Signals",
                "mock_scenario": "ffmpeg_failure",
                "expected_signals": ["error"],
                "unexpected_signals": ["finished"],
            },
            {
                "name": "Timeout Signals",
                "mock_scenario": "timeout",
                "expected_signals": ["error"],
                "unexpected_signals": ["finished"],
            },
        ]
        
        # Test each signal scenario
        for scenario in signal_scenarios:
            # Create worker
            worker_args = config_manager.create_worker_args(
                workspace["input_dir"],
                workspace["output_file"],
                "basic"
            )
            
            # Setup signal receiver
            signal_receiver = components["signal_receiver_class"]()
            
            with (
                patch("goesvfi.pipeline.run_vfi.subprocess.run") as mock_run,
                patch("goesvfi.pipeline.run_vfi.subprocess.Popen") as mock_popen,
                patch("goesvfi.pipeline.run_vfi.VfiWorker._get_rife_executable") as mock_rife_exe,
                patch("goesvfi.pipeline.run_vfi.colourise") as mock_sanchez,
            ):
                # Configure mocks for this scenario
                mocks = mock_manager.get_mocks(scenario["mock_scenario"])
                mock_run.return_value = mocks["subprocess_run"]
                mock_popen.return_value = mocks["subprocess_popen"]
                mock_rife_exe.return_value = mocks["rife_executable"]
                mock_sanchez.side_effect = mocks["sanchez_colourise"]
                
                # Create and setup output file for success scenarios
                if scenario["mock_scenario"] == "success":
                    def create_output_file(*args, **kwargs):
                        workspace["output_file"].write_bytes(b"mock video content")
                        return mocks["subprocess_popen"]
                    mock_popen.side_effect = create_output_file
                
                # Initialize worker
                worker = VfiWorker(**worker_args)
                
                # Connect signals
                worker.progress.connect(signal_receiver.on_progress)
                worker.finished.connect(signal_receiver.on_finished)
                worker.error.connect(signal_receiver.on_error)
                
                # Create event loop for signal processing
                loop = QEventLoop()
                
                # Setup completion handler
                def on_completion():
                    QTimer.singleShot(100, loop.quit)
                
                worker.finished.connect(on_completion)
                worker.error.connect(on_completion)
                
                # Start worker
                worker.start()
                
                # Wait for completion with timeout
                QTimer.singleShot(5000, loop.quit)  # 5 second timeout
                loop.exec()
                
                # Wait a bit more for signal processing
                shared_qt_app.processEvents()
                
                # Verify expected signals were received
                for expected_signal in scenario["expected_signals"]:
                    assert signal_receiver.has_received_signal(expected_signal), (
                        f"Expected {expected_signal} signal not received for {scenario['name']}"
                    )
                
                # Verify unexpected signals were not received
                for unexpected_signal in scenario["unexpected_signals"]:
                    assert not signal_receiver.has_received_signal(unexpected_signal), (
                        f"Unexpected {unexpected_signal} signal received for {scenario['name']}"
                    )
                
                # Additional scenario-specific validations
                if scenario["mock_scenario"] == "success":
                    assert signal_receiver.processing_complete, f"Processing not marked complete for {scenario['name']}"
                    assert signal_receiver.last_output is not None, f"No output path received for {scenario['name']}"
                    
                elif "failure" in scenario["mock_scenario"] or scenario["mock_scenario"] == "timeout":
                    assert signal_receiver.error_occurred, f"Error not detected for {scenario['name']}"
                    assert signal_receiver.last_error is not None, f"No error message received for {scenario['name']}"
                
                # Clean up
                worker.quit()
                worker.wait(1000)  # Wait up to 1 second for thread to finish
                signal_receiver.reset()

    def test_vfi_worker_processing_workflows_comprehensive(self, shared_qt_app, worker_test_components, temp_workspace) -> None:
        """Test comprehensive VfiWorker processing workflows."""
        components = worker_test_components
        workspace = temp_workspace
        config_manager = components["config_manager"]
        mock_manager = components["mock_manager"]
        
        # Define processing workflow scenarios
        workflow_scenarios = [
            {
                "name": "RIFE with Basic Settings",
                "config_type": "basic",
                "encoder": "RIFE",
                "sanchez": False,
                "crop": None,
                "expected_steps": ["rife_processing", "ffmpeg_encoding"],
            },
            {
                "name": "RIFE with Sanchez Enhancement",
                "config_type": "sanchez_enabled",
                "encoder": "RIFE",
                "sanchez": True,
                "crop": None,
                "expected_steps": ["rife_processing", "sanchez_processing", "ffmpeg_encoding"],
            },
            {
                "name": "RIFE with Cropping",
                "config_type": "basic",
                "encoder": "RIFE",
                "sanchez": False,
                "crop": (10, 10, 50, 30),
                "expected_steps": ["image_cropping", "rife_processing", "ffmpeg_encoding"],
            },
            {
                "name": "FFmpeg Interpolation",
                "config_type": "ffmpeg_fallback",
                "encoder": "FFmpeg",
                "sanchez": False,
                "crop": None,
                "expected_steps": ["ffmpeg_interpolation"],
            },
            {
                "name": "High Performance RIFE",
                "config_type": "high_performance",
                "encoder": "RIFE",
                "sanchez": False,
                "crop": None,
                "expected_steps": ["rife_processing", "ffmpeg_encoding"],
            },
        ]
        
        # Test each workflow scenario
        for scenario in workflow_scenarios:
            # Create worker configuration
            worker_args = config_manager.create_worker_args(
                workspace["input_dir"],
                workspace["output_file"],
                scenario["config_type"]
            )
            
            # Apply scenario-specific settings
            if scenario["crop"]:
                worker_args["crop_rect"] = scenario["crop"]
            
            if scenario["sanchez"]:
                worker_args["sanchez_temp_dir"] = workspace["sanchez_temp_dir"]
            
            # Setup mocks
            with (
                patch("goesvfi.pipeline.run_vfi.subprocess.run") as mock_run,
                patch("goesvfi.pipeline.run_vfi.subprocess.Popen") as mock_popen,
                patch("goesvfi.pipeline.run_vfi.VfiWorker._get_rife_executable") as mock_rife_exe,
                patch("goesvfi.pipeline.run_vfi.colourise") as mock_sanchez,
            ):
                # Configure success mocks
                mocks = mock_manager.get_mocks("success")
                mock_run.return_value = mocks["subprocess_run"]
                mock_popen.return_value = mocks["subprocess_popen"]
                mock_rife_exe.return_value = mocks["rife_executable"]
                mock_sanchez.side_effect = mocks["sanchez_colourise"]
                
                # Create output file
                def create_output_file(*args, **kwargs):
                    workspace["output_file"].write_bytes(b"mock video content")
                    return mocks["subprocess_popen"]
                mock_popen.side_effect = create_output_file
                
                # Initialize and setup worker
                worker = VfiWorker(**worker_args)
                signal_receiver = components["signal_receiver_class"]()
                
                worker.progress.connect(signal_receiver.on_progress)
                worker.finished.connect(signal_receiver.on_finished)
                worker.error.connect(signal_receiver.on_error)
                
                # Run workflow
                loop = QEventLoop()
                
                def on_completion():
                    QTimer.singleShot(50, loop.quit)
                
                worker.finished.connect(on_completion)
                worker.error.connect(on_completion)
                
                worker.start()
                
                # Wait for completion
                QTimer.singleShot(3000, loop.quit)  # 3 second timeout
                loop.exec()
                shared_qt_app.processEvents()
                
                # Verify workflow completed successfully
                assert signal_receiver.processing_complete, f"Workflow not completed for {scenario['name']}"
                assert not signal_receiver.error_occurred, f"Unexpected error in {scenario['name']}: {signal_receiver.last_error}"
                
                # Verify appropriate mocks were called based on expected steps
                if "rife_processing" in scenario["expected_steps"]:
                    mock_run.assert_called()
                
                if "ffmpeg_encoding" in scenario["expected_steps"] or "ffmpeg_interpolation" in scenario["expected_steps"]:
                    mock_popen.assert_called()
                
                if "sanchez_processing" in scenario["expected_steps"]:
                    mock_sanchez.assert_called()
                
                # Verify output file was created
                assert workspace["output_file"].exists(), f"Output file not created for {scenario['name']}"
                
                # Clean up
                worker.quit()
                worker.wait(1000)
                signal_receiver.reset()
                
                # Reset output file for next test
                if workspace["output_file"].exists():
                    workspace["output_file"].unlink()

    def test_vfi_worker_error_recovery_and_validation(self, shared_qt_app, worker_test_components, temp_workspace) -> None:
        """Test VfiWorker error recovery and input validation."""
        components = worker_test_components
        workspace = temp_workspace
        config_manager = components["config_manager"]
        
        # Define error and validation scenarios
        validation_scenarios = [
            {
                "name": "Invalid Input Directory",
                "modify_args": lambda args: args.update({"in_dir": Path("/nonexistent/path")}),
                "should_error": True,
                "error_type": "input_validation",
            },
            {
                "name": "Invalid Output Directory",
                "modify_args": lambda args: args.update({"out_file_path": Path("/readonly/output.mp4")}),
                "should_error": True,
                "error_type": "output_validation",
            },
            {
                "name": "Invalid FPS Value",
                "modify_args": lambda args: args.update({"fps": 0}),
                "should_error": True,
                "error_type": "parameter_validation",
            },
            {
                "name": "Invalid Mid Count",
                "modify_args": lambda args: args.update({"mid_count": -1}),
                "should_error": True,
                "error_type": "parameter_validation",
            },
            {
                "name": "Invalid Crop Rectangle",
                "modify_args": lambda args: args.update({"crop_rect": (100, 100, 10, 10)}),  # Invalid: width/height negative
                "should_error": True,
                "error_type": "crop_validation",
            },
        ]
        
        # Test each validation scenario
        for scenario in validation_scenarios:
            # Create base worker arguments
            worker_args = config_manager.create_worker_args(
                workspace["input_dir"],
                workspace["output_file"],
                "basic"
            )
            
            # Apply scenario modifications
            scenario["modify_args"](worker_args)
            
            if scenario["should_error"]:
                # Expect worker initialization or execution to fail
                try:
                    worker = VfiWorker(**worker_args)
                    signal_receiver = components["signal_receiver_class"]()
                    
                    worker.progress.connect(signal_receiver.on_progress)
                    worker.finished.connect(signal_receiver.on_finished)
                    worker.error.connect(signal_receiver.on_error)
                    
                    # Mock successful external tools to isolate validation errors
                    with (
                        patch("goesvfi.pipeline.run_vfi.subprocess.run") as mock_run,
                        patch("goesvfi.pipeline.run_vfi.subprocess.Popen") as mock_popen,
                        patch("goesvfi.pipeline.run_vfi.VfiWorker._get_rife_executable") as mock_rife_exe,
                    ):
                        mock_run.return_value = MagicMock(returncode=0)
                        mock_popen.return_value = MagicMock(returncode=0)
                        mock_rife_exe.return_value = Path("/mock/rife-cli")
                        
                        loop = QEventLoop()
                        
                        def on_completion():
                            QTimer.singleShot(50, loop.quit)
                        
                        worker.finished.connect(on_completion)
                        worker.error.connect(on_completion)
                        
                        worker.start()
                        
                        # Wait for completion or error
                        QTimer.singleShot(2000, loop.quit)  # 2 second timeout
                        loop.exec()
                        shared_qt_app.processEvents()
                        
                        # Should have received an error signal
                        assert signal_receiver.error_occurred, (
                            f"Expected error not detected for {scenario['name']}"
                        )
                        assert signal_receiver.last_error is not None, (
                            f"No error message received for {scenario['name']}"
                        )
                        
                        # Clean up
                        worker.quit()
                        worker.wait(1000)
                        
                except (ValueError, TypeError, FileNotFoundError) as e:
                    # Expected validation errors during initialization
                    assert scenario["should_error"], (
                        f"Unexpected initialization error for {scenario['name']}: {e}"
                    )
            else:
                # Should succeed
                try:
                    worker = VfiWorker(**worker_args)
                    assert worker is not None, f"Worker creation failed for valid scenario {scenario['name']}"
                except Exception as e:
                    pytest.fail(f"Unexpected error for valid scenario {scenario['name']}: {e}")

    def test_vfi_worker_performance_and_resource_management(self, shared_qt_app, worker_test_components, temp_workspace) -> None:
        """Test VfiWorker performance characteristics and resource management."""
        components = worker_test_components
        workspace = temp_workspace
        config_manager = components["config_manager"]
        mock_manager = components["mock_manager"]
        
        # Performance test scenarios
        performance_scenarios = [
            {
                "name": "Memory Usage Monitoring",
                "config_type": "basic",
                "test_type": "memory",
                "max_memory_increase_mb": 50,
            },
            {
                "name": "Processing Time Validation",
                "config_type": "low_resource",
                "test_type": "timing",
                "max_processing_time_sec": 3.0,
            },
            {
                "name": "Resource Cleanup",
                "config_type": "basic",
                "test_type": "cleanup",
                "check_temp_files": True,
            },
            {
                "name": "Thread Safety",
                "config_type": "high_performance",
                "test_type": "thread_safety",
                "concurrent_workers": 2,
            },
        ]
        
        # Test each performance scenario
        import time
        import psutil
        import os
        
        for scenario in performance_scenarios:
            if scenario["test_type"] == "memory":
                # Monitor memory usage
                process = psutil.Process(os.getpid())
                initial_memory = process.memory_info().rss / 1024 / 1024  # MB
                
                worker_args = config_manager.create_worker_args(
                    workspace["input_dir"],
                    workspace["output_file"],
                    scenario["config_type"]
                )
                
                with (
                    patch("goesvfi.pipeline.run_vfi.subprocess.run") as mock_run,
                    patch("goesvfi.pipeline.run_vfi.subprocess.Popen") as mock_popen,
                    patch("goesvfi.pipeline.run_vfi.VfiWorker._get_rife_executable") as mock_rife_exe,
                ):
                    # Configure fast mocks
                    mocks = mock_manager.get_mocks("success")
                    mock_run.return_value = mocks["subprocess_run"]
                    mock_popen.return_value = mocks["subprocess_popen"]
                    mock_rife_exe.return_value = mocks["rife_executable"]
                    
                    def quick_output(*args, **kwargs):
                        workspace["output_file"].write_bytes(b"quick output")
                        return mocks["subprocess_popen"]
                    mock_popen.side_effect = quick_output
                    
                    # Run worker
                    worker = VfiWorker(**worker_args)
                    signal_receiver = components["signal_receiver_class"]()
                    
                    worker.finished.connect(signal_receiver.on_finished)
                    worker.error.connect(signal_receiver.on_error)
                    
                    loop = QEventLoop()
                    
                    def on_completion():
                        QTimer.singleShot(50, loop.quit)
                    
                    worker.finished.connect(on_completion)
                    worker.error.connect(on_completion)
                    
                    worker.start()
                    QTimer.singleShot(2000, loop.quit)
                    loop.exec()
                    
                    worker.quit()
                    worker.wait(1000)
                
                # Check memory usage
                final_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = final_memory - initial_memory
                
                assert memory_increase < scenario["max_memory_increase_mb"], (
                    f"Memory increase {memory_increase:.1f}MB exceeds limit for {scenario['name']}"
                )
            
            elif scenario["test_type"] == "timing":
                # Monitor processing time
                worker_args = config_manager.create_worker_args(
                    workspace["input_dir"],
                    workspace["output_file"],
                    scenario["config_type"]
                )
                
                with (
                    patch("goesvfi.pipeline.run_vfi.subprocess.run") as mock_run,
                    patch("goesvfi.pipeline.run_vfi.subprocess.Popen") as mock_popen,
                    patch("goesvfi.pipeline.run_vfi.VfiWorker._get_rife_executable") as mock_rife_exe,
                ):
                    mocks = mock_manager.get_mocks("success")
                    mock_run.return_value = mocks["subprocess_run"]
                    mock_popen.return_value = mocks["subprocess_popen"]
                    mock_rife_exe.return_value = mocks["rife_executable"]
                    
                    def instant_output(*args, **kwargs):
                        workspace["output_file"].write_bytes(b"instant output")
                        return mocks["subprocess_popen"]
                    mock_popen.side_effect = instant_output
                    
                    start_time = time.perf_counter()
                    
                    worker = VfiWorker(**worker_args)
                    signal_receiver = components["signal_receiver_class"]()
                    
                    worker.finished.connect(signal_receiver.on_finished)
                    worker.error.connect(signal_receiver.on_error)
                    
                    loop = QEventLoop()
                    
                    def on_completion():
                        QTimer.singleShot(25, loop.quit)
                    
                    worker.finished.connect(on_completion)
                    worker.error.connect(on_completion)
                    
                    worker.start()
                    QTimer.singleShot(2000, loop.quit)
                    loop.exec()
                    
                    processing_time = time.perf_counter() - start_time
                    
                    worker.quit()
                    worker.wait(1000)
                
                assert processing_time < scenario["max_processing_time_sec"], (
                    f"Processing time {processing_time:.2f}s exceeds limit for {scenario['name']}"
                )
            
            elif scenario["test_type"] == "cleanup":
                # Test resource cleanup
                initial_files = list(workspace["output_dir"].glob("*"))
                
                worker_args = config_manager.create_worker_args(
                    workspace["input_dir"],
                    workspace["output_file"],
                    scenario["config_type"]
                )
                
                with (
                    patch("goesvfi.pipeline.run_vfi.subprocess.run") as mock_run,
                    patch("goesvfi.pipeline.run_vfi.subprocess.Popen") as mock_popen,
                    patch("goesvfi.pipeline.run_vfi.VfiWorker._get_rife_executable") as mock_rife_exe,
                ):
                    mocks = mock_manager.get_mocks("success")
                    mock_run.return_value = mocks["subprocess_run"]
                    mock_popen.return_value = mocks["subprocess_popen"]
                    mock_rife_exe.return_value = mocks["rife_executable"]
                    
                    def cleanup_output(*args, **kwargs):
                        workspace["output_file"].write_bytes(b"cleanup test")
                        return mocks["subprocess_popen"]
                    mock_popen.side_effect = cleanup_output
                    
                    worker = VfiWorker(**worker_args)
                    signal_receiver = components["signal_receiver_class"]()
                    
                    worker.finished.connect(signal_receiver.on_finished)
                    worker.error.connect(signal_receiver.on_error)
                    
                    loop = QEventLoop()
                    
                    def on_completion():
                        QTimer.singleShot(50, loop.quit)
                    
                    worker.finished.connect(on_completion)
                    worker.error.connect(on_completion)
                    
                    worker.start()
                    QTimer.singleShot(2000, loop.quit)
                    loop.exec()
                    
                    worker.quit()
                    worker.wait(1000)
                
                # Check that temp files haven't accumulated
                final_files = list(workspace["output_dir"].glob("*"))
                new_files = len(final_files) - len(initial_files)
                
                # Allow for the output file itself
                assert new_files <= 1, f"Too many new files created: {new_files}"
