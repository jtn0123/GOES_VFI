"""Optimized VFI parameter tests to speed up slow tests while maintaining coverage.

Optimizations applied:
- Shared fixtures for common VFI setups and mock configurations
- Parameterized test scenarios for comprehensive VFI pipeline validation
- Enhanced error handling and edge case coverage
- Mock-based testing to avoid real subprocess operations and file I/O
- Comprehensive VFI workflow and failure scenario testing
"""

import pathlib
import subprocess
import tempfile
from unittest.mock import ANY, MagicMock, patch, call
import pytest
import numpy as np
from PIL import Image

from goesvfi.pipeline import run_vfi as run_vfi_mod
from goesvfi.pipeline.exceptions import (
    FFmpegError,
    ProcessingError,
    RIFEError,
    SanchezError,
)


class TestRunVFIParamV2:
    """Optimized test class for VFI parameter functionality."""

    @pytest.fixture(scope="class")
    def vfi_scenarios(self):
        """Define various VFI processing scenarios."""
        return {
            "minimal_processing": {
                "fps": 10,
                "num_intermediate_frames": 1,
                "max_workers": 1,
                "skip_model": True,
                "expected_success": True,
            },
            "standard_processing": {
                "fps": 30,
                "num_intermediate_frames": 3,
                "max_workers": 2,
                "skip_model": False,
                "expected_success": True,
            },
            "high_performance": {
                "fps": 60,
                "num_intermediate_frames": 7,
                "max_workers": 4,
                "skip_model": False,
                "expected_success": True,
            },
            "sanchez_processing": {
                "fps": 10,
                "num_intermediate_frames": 1,
                "max_workers": 1,
                "false_colour": True,
                "res_km": 2,
                "expected_success": True,
            },
            "rife_failure": {
                "fps": 10,
                "num_intermediate_frames": 1,
                "max_workers": 1,
                "skip_model": False,
                "simulate_rife_failure": True,
                "expected_success": False,
            },
            "ffmpeg_failure": {
                "fps": 10,
                "num_intermediate_frames": 1,
                "max_workers": 1,
                "skip_model": False,
                "simulate_ffmpeg_failure": True,
                "expected_success": False,
            },
        }

    @pytest.fixture
    def sample_images_factory(self, tmp_path):
        """Factory for creating test images."""
        def create_images(count=2, size=(64, 64)):
            paths = []
            for i in range(count):
                img_path = tmp_path / f"img{i:04d}.png"
                
                # Create test image with different patterns
                img_array = np.zeros((size[1], size[0], 3), dtype=np.uint8)
                # Add some pattern for variety
                img_array[:, :, i % 3] = (i * 50) % 256
                
                img = Image.fromarray(img_array)
                img_path.parent.mkdir(parents=True, exist_ok=True)
                img.save(img_path, format="PNG")
                paths.append(img_path)
            return paths
        return create_images

    @pytest.fixture
    def mock_vfi_environment(self, tmp_path):
        """Create comprehensive mock environment for VFI processing."""
        def setup_environment(scenario_config):
            mock_patches = {}
            
            # Setup paths
            output_mp4 = tmp_path / "output.mp4"
            raw_output = tmp_path / "output.raw.mp4"
            rife_exe = tmp_path / "rife-cli"
            rife_exe.touch()
            
            # Mock capability detector
            mock_detector = MagicMock()
            mock_detector.supports_thread_spec.return_value = True
            mock_detector.supports_tiling.return_value = True
            mock_detector.supports_uhd.return_value = True
            mock_patches["capability_detector"] = patch(
                "goesvfi.pipeline.run_vfi.RifeCapabilityDetector",
                return_value=mock_detector
            )
            
            # Mock subprocess operations
            if scenario_config.get("simulate_rife_failure"):
                rife_error = subprocess.CalledProcessError(1, ["rife"], stderr="RIFE failed")
                mock_patches["subprocess_run"] = patch(
                    "goesvfi.pipeline.run_vfi.subprocess.run",
                    side_effect=rife_error
                )
            elif scenario_config.get("simulate_ffmpeg_failure"):
                # RIFE succeeds, FFmpeg fails
                mock_run_result = MagicMock()
                mock_run_result.returncode = 0
                mock_patches["subprocess_run"] = patch(
                    "goesvfi.pipeline.run_vfi.subprocess.run",
                    return_value=mock_run_result
                )
                mock_patches["subprocess_popen"] = patch(
                    "goesvfi.pipeline.run_vfi.subprocess.Popen",
                    return_value=self._create_failing_popen()
                )
            else:
                # Success case
                mock_run_result = MagicMock()
                mock_run_result.returncode = 0
                mock_patches["subprocess_run"] = patch(
                    "goesvfi.pipeline.run_vfi.subprocess.run",
                    return_value=mock_run_result
                )
                mock_patches["subprocess_popen"] = patch(
                    "goesvfi.pipeline.run_vfi.subprocess.Popen",
                    return_value=self._create_successful_popen(raw_output)
                )
            
            # Mock file operations
            mock_patches["path_glob"] = patch.object(pathlib.Path, "glob")
            mock_patches["path_exists"] = patch("goesvfi.pipeline.run_vfi.pathlib.Path.exists", return_value=True)
            mock_patches["path_unlink"] = patch("goesvfi.pipeline.run_vfi.pathlib.Path.unlink")
            
            # Mock image operations
            mock_img = MagicMock()
            mock_img.size = (64, 64)
            mock_img.__enter__.return_value = mock_img
            mock_patches["image_open"] = patch("goesvfi.pipeline.run_vfi.Image.open", return_value=mock_img)
            
            # Mock temporary directory
            mock_patches["temp_directory"] = patch(
                "goesvfi.pipeline.run_vfi.tempfile.TemporaryDirectory"
            )
            
            # Mock process pool executor
            mock_executor = MagicMock()
            mock_executor.__enter__.return_value.map = lambda fn, it: list(it)
            mock_patches["process_pool"] = patch(
                "goesvfi.pipeline.run_vfi.ProcessPoolExecutor",
                return_value=mock_executor
            )
            
            # Mock Sanchez if needed
            if scenario_config.get("false_colour"):
                if scenario_config.get("simulate_sanchez_failure"):
                    mock_patches["colourise"] = patch(
                        "goesvfi.pipeline.run_vfi.colourise",
                        side_effect=RuntimeError("Sanchez failed")
                    )
                else:
                    mock_patches["colourise"] = patch(
                        "goesvfi.pipeline.run_vfi.colourise",
                        return_value=tmp_path / "coloured.png"
                    )
            
            return {
                "patches": mock_patches,
                "paths": {
                    "output_mp4": output_mp4,
                    "raw_output": raw_output,
                    "rife_exe": rife_exe,
                }
            }
        return setup_environment

    def _create_successful_popen(self, output_file):
        """Create a mock Popen that simulates successful execution."""
        mock_popen = MagicMock()
        mock_popen.returncode = 0
        mock_popen.communicate.return_value = (b"", b"")
        mock_popen.wait.return_value = 0
        
        # Simulate file creation
        def create_output(*args, **kwargs):
            output_file.touch()
            return mock_popen
        
        return create_output()

    def _create_failing_popen(self):
        """Create a mock Popen that simulates failed execution."""
        mock_popen = MagicMock()
        mock_popen.returncode = 1
        mock_popen.communicate.return_value = (b"", b"FFmpeg failed")
        mock_popen.wait.return_value = 1
        return mock_popen

    @pytest.mark.parametrize("scenario_name", [
        "minimal_processing",
        "standard_processing",
        "high_performance",
    ])
    def test_run_vfi_success_scenarios(self, sample_images_factory, mock_vfi_environment, 
                                     vfi_scenarios, scenario_name):
        """Test successful VFI processing scenarios."""
        scenario = vfi_scenarios[scenario_name]
        img_paths = sample_images_factory(count=5)
        environment = mock_vfi_environment(scenario)
        
        # Apply all patches
        active_patches = []
        for patch_obj in environment["patches"].values():
            active_patches.append(patch_obj.start())
        
        try:
            # Setup path globbing to return our test images
            environment["patches"]["path_glob"].start().return_value = img_paths
            environment["patches"]["temp_directory"].start().__enter__.return_value = img_paths[0].parent
            
            # Execute VFI processing
            kwargs = {k: v for k, v in scenario.items() if k not in ["expected_success", "simulate_rife_failure", "simulate_ffmpeg_failure"]}
            
            results = list(run_vfi_mod.run_vfi(
                folder=img_paths[0].parent,
                output_mp4_path=environment["paths"]["output_mp4"],
                rife_exe_path=environment["paths"]["rife_exe"],
                **kwargs
            ))
            
            # Verify results
            assert len(results) > 0
            assert any(isinstance(r, pathlib.Path) for r in results)
            
        finally:
            # Clean up patches
            for patch_obj in environment["patches"].values():
                patch_obj.stop()

    @pytest.mark.parametrize("scenario_name", [
        "rife_failure",
        "ffmpeg_failure",
    ])
    def test_run_vfi_failure_scenarios(self, sample_images_factory, mock_vfi_environment, 
                                     vfi_scenarios, scenario_name):
        """Test VFI processing failure scenarios."""
        scenario = vfi_scenarios[scenario_name]
        img_paths = sample_images_factory(count=3)
        environment = mock_vfi_environment(scenario)
        
        # Apply all patches
        active_patches = []
        for patch_obj in environment["patches"].values():
            active_patches.append(patch_obj.start())
        
        try:
            # Setup path globbing
            environment["patches"]["path_glob"].start().return_value = img_paths
            environment["patches"]["temp_directory"].start().__enter__.return_value = img_paths[0].parent
            
            # Execute VFI processing and expect failure
            kwargs = {k: v for k, v in scenario.items() if k not in ["expected_success", "simulate_rife_failure", "simulate_ffmpeg_failure"]}
            
            with pytest.raises((RuntimeError, ProcessingError, RIFEError, FFmpegError)):
                list(run_vfi_mod.run_vfi(
                    folder=img_paths[0].parent,
                    output_mp4_path=environment["paths"]["output_mp4"],
                    rife_exe_path=environment["paths"]["rife_exe"],
                    **kwargs
                ))
                
        finally:
            # Clean up patches
            for patch_obj in environment["patches"].values():
                patch_obj.stop()

    def test_run_vfi_sanchez_integration(self, sample_images_factory, mock_vfi_environment, vfi_scenarios):
        """Test VFI processing with Sanchez false colour integration."""
        scenario = vfi_scenarios["sanchez_processing"]
        img_paths = sample_images_factory(count=2)
        environment = mock_vfi_environment(scenario)
        
        active_patches = []
        for patch_obj in environment["patches"].values():
            active_patches.append(patch_obj.start())
        
        try:
            environment["patches"]["path_glob"].start().return_value = img_paths
            environment["patches"]["temp_directory"].start().__enter__.return_value = img_paths[0].parent
            
            # Create coloured output file
            coloured_path = img_paths[0].parent / "coloured.png"
            coloured_path.touch()
            environment["patches"]["colourise"].start().return_value = coloured_path
            
            kwargs = {k: v for k, v in scenario.items() if k not in ["expected_success"]}
            
            results = list(run_vfi_mod.run_vfi(
                folder=img_paths[0].parent,
                output_mp4_path=environment["paths"]["output_mp4"],
                rife_exe_path=environment["paths"]["rife_exe"],
                **kwargs
            ))
            
            # Verify Sanchez was called
            environment["patches"]["colourise"].start().assert_called()
            assert len(results) > 0
            
        finally:
            for patch_obj in environment["patches"].values():
                patch_obj.stop()

    @pytest.mark.parametrize("fps,num_frames,max_workers", [
        (10, 1, 1),
        (30, 3, 2),
        (60, 7, 4),
        (120, 15, 8),
    ])
    def test_run_vfi_parameter_variations(self, sample_images_factory, mock_vfi_environment, 
                                        fps, num_frames, max_workers):
        """Test VFI processing with various parameter combinations."""
        scenario_config = {
            "fps": fps,
            "num_intermediate_frames": num_frames,
            "max_workers": max_workers,
            "skip_model": True,
        }
        
        img_paths = sample_images_factory(count=3)
        environment = mock_vfi_environment(scenario_config)
        
        active_patches = []
        for patch_obj in environment["patches"].values():
            active_patches.append(patch_obj.start())
        
        try:
            environment["patches"]["path_glob"].start().return_value = img_paths
            environment["patches"]["temp_directory"].start().__enter__.return_value = img_paths[0].parent
            
            results = list(run_vfi_mod.run_vfi(
                folder=img_paths[0].parent,
                output_mp4_path=environment["paths"]["output_mp4"],
                rife_exe_path=environment["paths"]["rife_exe"],
                fps=fps,
                num_intermediate_frames=num_frames,
                max_workers=max_workers,
                skip_model=True,
            ))
            
            assert len(results) > 0
            
        finally:
            for patch_obj in environment["patches"].values():
                patch_obj.stop()

    def test_run_vfi_crop_functionality(self, sample_images_factory, mock_vfi_environment):
        """Test VFI processing with cropping functionality."""
        scenario_config = {"fps": 10, "num_intermediate_frames": 1, "max_workers": 1}
        img_paths = sample_images_factory(count=2, size=(128, 128))
        environment = mock_vfi_environment(scenario_config)
        
        active_patches = []
        for patch_obj in environment["patches"].values():
            active_patches.append(patch_obj.start())
        
        try:
            environment["patches"]["path_glob"].start().return_value = img_paths
            environment["patches"]["temp_directory"].start().__enter__.return_value = img_paths[0].parent
            
            # Test with crop parameters
            crop_rect = (10, 10, 100, 100)  # x, y, width, height
            
            results = list(run_vfi_mod.run_vfi(
                folder=img_paths[0].parent,
                output_mp4_path=environment["paths"]["output_mp4"],
                rife_exe_path=environment["paths"]["rife_exe"],
                fps=10,
                num_intermediate_frames=1,
                max_workers=1,
                skip_model=True,
                crop_rect_xywh=crop_rect,
            ))
            
            assert len(results) > 0
            
        finally:
            for patch_obj in environment["patches"].values():
                patch_obj.stop()

    def test_run_vfi_rife_configuration_options(self, sample_images_factory, mock_vfi_environment):
        """Test VFI processing with various RIFE configuration options."""
        rife_configs = [
            {"tile_enable": True, "tile_size": 256},
            {"uhd_mode": True, "gpu_id": 0},
            {"tta_spatial": True, "tta_temporal": True},
            {"thread_spec": "2:4:4", "gpu_id": -1},
        ]
        
        for rife_config in rife_configs:
            img_paths = sample_images_factory(count=2)
            scenario_config = {"fps": 10, "num_intermediate_frames": 1, "max_workers": 1}
            environment = mock_vfi_environment(scenario_config)
            
            active_patches = []
            for patch_obj in environment["patches"].values():
                active_patches.append(patch_obj.start())
            
            try:
                environment["patches"]["path_glob"].start().return_value = img_paths
                environment["patches"]["temp_directory"].start().__enter__.return_value = img_paths[0].parent
                
                results = list(run_vfi_mod.run_vfi(
                    folder=img_paths[0].parent,
                    output_mp4_path=environment["paths"]["output_mp4"],
                    rife_exe_path=environment["paths"]["rife_exe"],
                    fps=10,
                    num_intermediate_frames=1,
                    max_workers=1,
                    skip_model=True,
                    **rife_config
                ))
                
                assert len(results) > 0
                
            finally:
                for patch_obj in environment["patches"].values():
                    patch_obj.stop()

    def test_run_vfi_resource_management(self, sample_images_factory, mock_vfi_environment):
        """Test VFI processing with resource management."""
        scenario_config = {"fps": 30, "num_intermediate_frames": 3, "max_workers": 4}
        img_paths = sample_images_factory(count=10)  # More images to test resource management
        environment = mock_vfi_environment(scenario_config)
        
        active_patches = []
        for patch_obj in environment["patches"].values():
            active_patches.append(patch_obj.start())
        
        # Mock resource manager
        mock_resource_manager = MagicMock()
        mock_resource_manager.get_optimal_workers.return_value = 4
        mock_resource_manager.get_memory_usage.return_value = {"used": "1GB", "available": "8GB"}
        
        with patch("goesvfi.pipeline.run_vfi.get_resource_manager", return_value=mock_resource_manager):
            try:
                environment["patches"]["path_glob"].start().return_value = img_paths
                environment["patches"]["temp_directory"].start().__enter__.return_value = img_paths[0].parent
                
                results = list(run_vfi_mod.run_vfi(
                    folder=img_paths[0].parent,
                    output_mp4_path=environment["paths"]["output_mp4"],
                    rife_exe_path=environment["paths"]["rife_exe"],
                    fps=30,
                    num_intermediate_frames=3,
                    max_workers=4,
                    skip_model=True,
                ))
                
                assert len(results) > 0
                
            finally:
                for patch_obj in environment["patches"].values():
                    patch_obj.stop()

    def test_run_vfi_input_validation_edge_cases(self, tmp_path, mock_vfi_environment):
        """Test VFI input validation with edge cases."""
        scenario_config = {"fps": 10, "num_intermediate_frames": 1, "max_workers": 1}
        environment = mock_vfi_environment(scenario_config)
        
        edge_cases = [
            {"folder": tmp_path / "nonexistent", "should_fail": True},
            {"fps": 0, "should_fail": True},
            {"fps": -1, "should_fail": True},
            {"num_intermediate_frames": -1, "should_fail": True},
            {"max_workers": 0, "should_fail": True},
        ]
        
        for case in edge_cases:
            active_patches = []
            for patch_obj in environment["patches"].values():
                active_patches.append(patch_obj.start())
            
            try:
                # Create minimal valid setup
                valid_folder = tmp_path / "valid"
                valid_folder.mkdir(exist_ok=True)
                test_img = valid_folder / "test.png"
                test_img.touch()
                
                environment["patches"]["path_glob"].start().return_value = [test_img]
                environment["patches"]["temp_directory"].start().__enter__.return_value = valid_folder
                
                kwargs = {
                    "folder": case.get("folder", valid_folder),
                    "output_mp4_path": environment["paths"]["output_mp4"],
                    "rife_exe_path": environment["paths"]["rife_exe"],
                    "fps": case.get("fps", 10),
                    "num_intermediate_frames": case.get("num_intermediate_frames", 1),
                    "max_workers": case.get("max_workers", 1),
                    "skip_model": True,
                }
                
                if case.get("should_fail"):
                    with pytest.raises((ValueError, FileNotFoundError, ProcessingError)):
                        list(run_vfi_mod.run_vfi(**kwargs))
                else:
                    results = list(run_vfi_mod.run_vfi(**kwargs))
                    assert len(results) > 0
                    
            finally:
                for patch_obj in environment["patches"].values():
                    patch_obj.stop()

    def test_run_vfi_memory_efficiency_simulation(self, sample_images_factory, mock_vfi_environment):
        """Test VFI processing with memory efficiency considerations."""
        # Simulate processing of different batch sizes
        batch_sizes = [2, 5, 10, 20]
        
        for batch_size in batch_sizes:
            scenario_config = {"fps": 10, "num_intermediate_frames": 1, "max_workers": 2}
            img_paths = sample_images_factory(count=batch_size)
            environment = mock_vfi_environment(scenario_config)
            
            active_patches = []
            for patch_obj in environment["patches"].values():
                active_patches.append(patch_obj.start())
            
            try:
                environment["patches"]["path_glob"].start().return_value = img_paths
                environment["patches"]["temp_directory"].start().__enter__.return_value = img_paths[0].parent
                
                results = list(run_vfi_mod.run_vfi(
                    folder=img_paths[0].parent,
                    output_mp4_path=environment["paths"]["output_mp4"],
                    rife_exe_path=environment["paths"]["rife_exe"],
                    fps=10,
                    num_intermediate_frames=1,
                    max_workers=2,
                    skip_model=True,
                ))
                
                # Verify processing completed regardless of batch size
                assert len(results) > 0
                
            finally:
                for patch_obj in environment["patches"].values():
                    patch_obj.stop()

    def test_run_vfi_concurrent_processing_simulation(self, sample_images_factory, mock_vfi_environment):
        """Simulate concurrent VFI processing operations."""
        import threading
        import time
        
        scenario_config = {"fps": 10, "num_intermediate_frames": 1, "max_workers": 1}
        results = []
        errors = []
        
        def vfi_worker(worker_id):
            try:
                img_paths = sample_images_factory(count=3)
                environment = mock_vfi_environment(scenario_config)
                
                active_patches = []
                for patch_obj in environment["patches"].values():
                    active_patches.append(patch_obj.start())
                
                try:
                    environment["patches"]["path_glob"].start().return_value = img_paths
                    environment["patches"]["temp_directory"].start().__enter__.return_value = img_paths[0].parent
                    
                    worker_results = list(run_vfi_mod.run_vfi(
                        folder=img_paths[0].parent,
                        output_mp4_path=environment["paths"]["output_mp4"],
                        rife_exe_path=environment["paths"]["rife_exe"],
                        fps=10,
                        num_intermediate_frames=1,
                        max_workers=1,
                        skip_model=True,
                    ))
                    
                    results.append(f"worker_{worker_id}_success")
                    time.sleep(0.001)  # Small delay
                    
                finally:
                    for patch_obj in environment["patches"].values():
                        patch_obj.stop()
                        
            except Exception as e:
                errors.append(f"worker_{worker_id}_error: {e}")
        
        # Create multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=vfi_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify results
        assert len(results) == 3
        assert len(errors) == 0

    def test_run_vfi_comprehensive_workflow_integration(self, sample_images_factory, mock_vfi_environment):
        """Test comprehensive VFI workflow integration."""
        workflow_scenarios = [
            {
                "name": "basic_workflow",
                "config": {"fps": 10, "num_intermediate_frames": 1, "skip_model": True}
            },
            {
                "name": "advanced_workflow", 
                "config": {"fps": 30, "num_intermediate_frames": 3, "tile_enable": True, "uhd_mode": True}
            },
            {
                "name": "sanchez_workflow",
                "config": {"fps": 10, "num_intermediate_frames": 1, "false_colour": True, "res_km": 2}
            },
        ]
        
        for scenario in workflow_scenarios:
            img_paths = sample_images_factory(count=4)
            environment = mock_vfi_environment(scenario["config"])
            
            active_patches = []
            for patch_obj in environment["patches"].values():
                active_patches.append(patch_obj.start())
            
            try:
                environment["patches"]["path_glob"].start().return_value = img_paths
                environment["patches"]["temp_directory"].start().__enter__.return_value = img_paths[0].parent
                
                # Add Sanchez mock if needed
                if scenario["config"].get("false_colour"):
                    coloured_path = img_paths[0].parent / "coloured.png"
                    coloured_path.touch()
                    environment["patches"]["colourise"].start().return_value = coloured_path
                
                results = list(run_vfi_mod.run_vfi(
                    folder=img_paths[0].parent,
                    output_mp4_path=environment["paths"]["output_mp4"],
                    rife_exe_path=environment["paths"]["rife_exe"],
                    max_workers=1,
                    **scenario["config"]
                ))
                
                # Verify workflow completed
                assert len(results) > 0
                assert any(isinstance(r, pathlib.Path) for r in results)
                
            finally:
                for patch_obj in environment["patches"].values():
                    patch_obj.stop()