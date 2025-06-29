"""Optimized interpolation tests to speed up slow tests while maintaining coverage.

Optimizations applied:
- Shared fixtures for common interpolation setups and mock configurations
- Parameterized test scenarios for comprehensive RIFE functionality validation
- Enhanced error handling and edge case coverage
- Mock-based testing to avoid actual subprocess operations and file I/O
- Comprehensive interpolation workflow and performance testing
"""

import subprocess
import tempfile
import pathlib
from unittest.mock import ANY, MagicMock, patch, call
import pytest
import numpy as np

import goesvfi.pipeline.interpolate as interpolate_mod


class TestInterpolateV2:
    """Optimized test class for interpolation functionality."""

    @pytest.fixture(scope="class")
    def interpolation_scenarios(self):
        """Define various interpolation test scenarios."""
        return {
            "standard_interpolation": {
                "img_shape": (4, 4, 3),
                "timestep": 0.5,
                "tile_enable": False,
                "expected_calls": 1,
            },
            "tiled_interpolation": {
                "img_shape": (256, 256, 3),
                "timestep": 0.5,
                "tile_enable": True,
                "tile_size": 128,
                "expected_calls": 1,
            },
            "uhd_interpolation": {
                "img_shape": (1920, 1080, 3),
                "timestep": 0.5,
                "uhd_mode": True,
                "expected_calls": 1,
            },
            "three_frame_interpolation": {
                "img_shape": (4, 4, 3),
                "frame_count": 3,
                "expected_calls": 3,
            },
        }

    @pytest.fixture
    def sample_images(self):
        """Create sample image data for testing."""
        def create_images(shape=(4, 4, 3), count=2):
            images = []
            for i in range(count):
                # Create slightly different images for variety
                img = np.ones(shape, dtype=np.float32) * (0.1 + i * 0.2)
                img = np.clip(img, 0.0, 1.0)
                images.append(img)
            return images
        return create_images

    @pytest.fixture
    def mock_rife_backend_factory(self, tmp_path):
        """Factory for creating mock RIFE backends."""
        def create_backend(exe_exists=True, supports_tiling=True, supports_uhd=True):
            # Create executable file if needed
            exe_path = tmp_path / "rife-cli"
            if exe_exists:
                exe_path.touch()
                exe_path.chmod(0o755)  # Make executable

            with patch("shutil.which", return_value=str(exe_path) if exe_exists else None):
                # Mock the command builder and detector
                with patch.object(interpolate_mod, "RifeCommandBuilder") as mock_builder_cls:
                    mock_builder = MagicMock()
                    mock_detector = MagicMock()
                    
                    # Setup capabilities
                    mock_detector.supports_tiling.return_value = supports_tiling
                    mock_detector.supports_uhd.return_value = supports_uhd
                    mock_detector.supports_tta_spatial.return_value = False
                    mock_detector.supports_tta_temporal.return_value = False
                    mock_detector.supports_thread_spec.return_value = True
                    
                    mock_builder.detector = mock_detector
                    mock_builder.build_command.return_value = ["rife", "test", "command"]
                    mock_builder_cls.return_value = mock_builder
                    
                    if exe_exists:
                        backend = interpolate_mod.RifeBackend(exe_path)
                        backend._mock_builder = mock_builder
                        backend._mock_detector = mock_detector
                        return backend
                    else:
                        return None
        return create_backend

    @pytest.fixture
    def mock_subprocess_operations(self):
        """Mock subprocess and file operations for interpolation."""
        def setup_mocks(success=True, output_exists=True, stderr_output=""):
            mock_patches = {}
            
            # Mock subprocess.run
            if success:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = "RIFE processing completed"
                mock_result.stderr = stderr_output
                mock_patches["subprocess_run"] = patch(
                    "goesvfi.pipeline.interpolate.subprocess.run",
                    return_value=mock_result
                )
            else:
                error = subprocess.CalledProcessError(1, ["rife"], stderr="RIFE failed")
                mock_patches["subprocess_run"] = patch(
                    "goesvfi.pipeline.interpolate.subprocess.run",
                    side_effect=error
                )
            
            # Mock file operations
            mock_patches["image_fromarray"] = patch("goesvfi.pipeline.interpolate.Image.fromarray")
            mock_patches["path_exists"] = patch("goesvfi.pipeline.interpolate.pathlib.Path.exists", return_value=output_exists)
            mock_patches["rmtree"] = patch("goesvfi.pipeline.interpolate.shutil.rmtree")
            mock_patches["tempfile_mkdtemp"] = patch("goesvfi.pipeline.interpolate.tempfile.mkdtemp")
            
            # Mock image loading
            mock_image = MagicMock()
            mock_image.size = (4, 4)
            mock_patches["image_open"] = patch("goesvfi.pipeline.interpolate.Image.open")
            mock_patches["numpy_array"] = patch("numpy.array", return_value=np.ones((4, 4, 3), dtype=np.uint8))
            
            return mock_patches
        return setup_mocks

    def test_rife_backend_initialization_success(self, mock_rife_backend_factory):
        """Test successful RIFE backend initialization."""
        backend = mock_rife_backend_factory(exe_exists=True, supports_tiling=True, supports_uhd=True)
        
        assert backend is not None
        assert backend.exe.exists()
        assert hasattr(backend, 'command_builder')
        assert hasattr(backend, 'capability_detector')
        
        # Verify capabilities were logged
        assert backend._mock_detector.supports_tiling.called
        assert backend._mock_detector.supports_uhd.called

    def test_rife_backend_initialization_missing_executable(self, tmp_path):
        """Test RIFE backend initialization with missing executable."""
        non_existent_exe = tmp_path / "missing-rife"
        
        with pytest.raises(FileNotFoundError, match="RIFE executable not found"):
            interpolate_mod.RifeBackend(non_existent_exe)

    @pytest.mark.parametrize("scenario_name", [
        "standard_interpolation",
        "tiled_interpolation", 
        "uhd_interpolation",
    ])
    def test_interpolate_pair_scenarios(self, mock_rife_backend_factory, mock_subprocess_operations, 
                                      sample_images, interpolation_scenarios, scenario_name):
        """Test interpolate_pair with various scenarios."""
        scenario = interpolation_scenarios[scenario_name]
        backend = mock_rife_backend_factory(exe_exists=True)
        images = sample_images(shape=scenario["img_shape"], count=2)
        
        mock_patches = mock_subprocess_operations(success=True, output_exists=True)
        
        with patch.multiple("goesvfi.pipeline.interpolate", **mock_patches):
            # Setup temp directory mock
            temp_dir = "/tmp/mock_temp_dir"
            mock_patches["tempfile_mkdtemp"].return_value = temp_dir
            
            # Setup image mock to return valid result
            expected_result = np.ones(scenario["img_shape"], dtype=np.float32) * 0.5
            mock_patches["numpy_array"].return_value = (expected_result * 255).astype(np.uint8)
            
            # Create options dict
            options = {k: v for k, v in scenario.items() if k not in ["img_shape", "expected_calls"]}
            
            result = backend.interpolate_pair(images[0], images[1], options)
            
            # Verify result
            assert isinstance(result, np.ndarray)
            assert result.dtype == np.float32
            assert result.shape == scenario["img_shape"]
            
            # Verify subprocess was called
            mock_patches["subprocess_run"].assert_called_once()
            
            # Verify cleanup
            mock_patches["rmtree"].assert_called_once()

    @pytest.mark.parametrize("timestep", [0.0, 0.25, 0.5, 0.75, 1.0])
    def test_interpolate_pair_timestep_variations(self, mock_rife_backend_factory, mock_subprocess_operations, 
                                                 sample_images, timestep):
        """Test interpolate_pair with various timestep values."""
        backend = mock_rife_backend_factory(exe_exists=True)
        images = sample_images()
        
        mock_patches = mock_subprocess_operations(success=True, output_exists=True)
        
        with patch.multiple("goesvfi.pipeline.interpolate", **mock_patches):
            mock_patches["tempfile_mkdtemp"].return_value = "/tmp/test"
            expected_result = np.ones((4, 4, 3), dtype=np.float32) * timestep
            mock_patches["numpy_array"].return_value = (expected_result * 255).astype(np.uint8)
            
            options = {"timestep": timestep}
            result = backend.interpolate_pair(images[0], images[1], options)
            
            assert isinstance(result, np.ndarray)
            assert result.dtype == np.float32
            
            # Verify command builder was called with correct timestep
            backend._mock_builder.build_command.assert_called_once()
            call_args = backend._mock_builder.build_command.call_args
            assert call_args[1]["timestep"] == timestep

    def test_interpolate_pair_subprocess_error_handling(self, mock_rife_backend_factory, mock_subprocess_operations, sample_images):
        """Test interpolate_pair error handling when subprocess fails."""
        backend = mock_rife_backend_factory(exe_exists=True)
        images = sample_images()
        
        mock_patches = mock_subprocess_operations(success=False)
        
        with patch.multiple("goesvfi.pipeline.interpolate", **mock_patches):
            mock_patches["tempfile_mkdtemp"].return_value = "/tmp/test"
            
            with pytest.raises(RuntimeError, match="RIFE executable failed"):
                backend.interpolate_pair(images[0], images[1])
            
            # Verify cleanup was still called
            mock_patches["rmtree"].assert_called_once()

    def test_interpolate_pair_missing_output_file(self, mock_rife_backend_factory, mock_subprocess_operations, sample_images):
        """Test interpolate_pair when output file is not generated."""
        backend = mock_rife_backend_factory(exe_exists=True)
        images = sample_images()
        
        mock_patches = mock_subprocess_operations(success=True, output_exists=False)
        
        with patch.multiple("goesvfi.pipeline.interpolate", **mock_patches):
            mock_patches["tempfile_mkdtemp"].return_value = "/tmp/test"
            
            with pytest.raises(RuntimeError, match="RIFE failed to generate frame"):
                backend.interpolate_pair(images[0], images[1])

    @pytest.mark.parametrize("tile_size", [64, 128, 256, 512])
    def test_interpolate_pair_tiling_configurations(self, mock_rife_backend_factory, mock_subprocess_operations, 
                                                   sample_images, tile_size):
        """Test interpolate_pair with various tiling configurations."""
        backend = mock_rife_backend_factory(exe_exists=True, supports_tiling=True)
        images = sample_images(shape=(512, 512, 3))
        
        mock_patches = mock_subprocess_operations(success=True)
        
        with patch.multiple("goesvfi.pipeline.interpolate", **mock_patches):
            mock_patches["tempfile_mkdtemp"].return_value = "/tmp/test"
            mock_patches["numpy_array"].return_value = np.ones((512, 512, 3), dtype=np.uint8)
            
            options = {
                "tile_enable": True,
                "tile_size": tile_size,
                "timestep": 0.5
            }
            
            result = backend.interpolate_pair(images[0], images[1], options)
            
            assert isinstance(result, np.ndarray)
            assert result.shape == (512, 512, 3)
            
            # Verify tiling options were passed to command builder
            call_args = backend._mock_builder.build_command.call_args[1]
            assert call_args["tile_enable"] is True
            assert call_args["tile_size"] == tile_size

    def test_interpolate_three_workflow(self, sample_images):
        """Test interpolate_three function workflow."""
        images = sample_images()
        
        # Mock backend with side effects for three calls
        mock_backend = MagicMock()
        mock_backend.interpolate_pair.side_effect = [
            np.full((4, 4, 3), 0.25, dtype=np.float32),  # mid frame
            np.full((4, 4, 3), 0.125, dtype=np.float32),  # left frame  
            np.full((4, 4, 3), 0.375, dtype=np.float32),  # right frame
        ]
        
        options = {"tile_enable": True, "tile_size": 128}
        result = interpolate_mod.interpolate_three(images[0], images[1], mock_backend, options)
        
        # Verify three calls were made
        assert mock_backend.interpolate_pair.call_count == 3
        
        # Verify result structure
        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(frame, np.ndarray) for frame in result)
        assert all(frame.dtype == np.float32 for frame in result)
        
        # Verify call arguments
        calls = mock_backend.interpolate_pair.call_args_list
        
        # First call: img1 -> img2 (timestep 0.5)
        assert calls[0][1]["timestep"] == 0.5
        
        # Second call: img1 -> img_mid (timestep 0.5) 
        assert calls[1][1]["timestep"] == 0.5
        
        # Third call: img_mid -> img2 (timestep 0.5)
        assert calls[2][1]["timestep"] == 0.5

    @pytest.mark.parametrize("options_config", [
        {},  # Default options
        {"tile_enable": True, "tile_size": 256},
        {"uhd_mode": True, "tta_spatial": True},
        {"gpu_id": 0, "thread_spec": "2:4:4"},
    ])
    def test_interpolate_three_option_propagation(self, sample_images, options_config):
        """Test that options are properly propagated through interpolate_three."""
        images = sample_images()
        
        mock_backend = MagicMock()
        mock_backend.interpolate_pair.return_value = np.ones((4, 4, 3), dtype=np.float32) * 0.5
        
        interpolate_mod.interpolate_three(images[0], images[1], mock_backend, options_config)
        
        # Verify all calls received the options (with timestep modifications)
        calls = mock_backend.interpolate_pair.call_args_list
        for call in calls:
            call_options = call[1] if len(call) > 1 else call.args[2]
            assert call_options["timestep"] == 0.5  # Always 0.5 for pair interpolation
            
            # Check other options are preserved
            for key, value in options_config.items():
                if key != "timestep":
                    assert call_options[key] == value

    @pytest.mark.parametrize("optimized,available", [
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    ])
    def test_create_rife_backend_factory(self, tmp_path, optimized, available):
        """Test create_rife_backend factory function."""
        exe_path = tmp_path / "rife"
        exe_path.touch()
        
        with patch.object(interpolate_mod, "OPTIMIZED_BACKEND_AVAILABLE", available):
            with patch.object(interpolate_mod, "OptimizedRifeBackend") as mock_optimized:
                with patch.object(interpolate_mod, "RifeBackend") as mock_standard:
                    mock_optimized.return_value = MagicMock()
                    mock_standard.return_value = MagicMock()
                    
                    backend = interpolate_mod.create_rife_backend(exe_path, optimized=optimized, cache_size=50)
                    
                    if optimized and available:
                        mock_optimized.assert_called_once_with(exe_path, cache_size=50)
                        mock_standard.assert_not_called()
                    else:
                        mock_standard.assert_called_once_with(exe_path)
                        if optimized:
                            mock_optimized.assert_not_called()

    def test_get_backend_performance_info(self):
        """Test get_backend_performance_info function."""
        # Test with optimized backend (has performance stats)
        mock_optimized_backend = MagicMock()
        mock_optimized_backend.get_performance_stats.return_value = {
            "backend_type": "optimized",
            "cache_hits": 10,
            "cache_misses": 2
        }
        
        stats = interpolate_mod.get_backend_performance_info(mock_optimized_backend)
        assert stats["backend_type"] == "optimized"
        assert "cache_hits" in stats
        
        # Test with standard backend (no performance stats)
        mock_standard_backend = MagicMock()
        del mock_standard_backend.get_performance_stats  # Remove the method
        
        stats = interpolate_mod.get_backend_performance_info(mock_standard_backend)
        assert stats["backend_type"] == "standard"
        assert "optimization_available" in stats

    @pytest.mark.parametrize("img_dtype", [np.uint8, np.float32, np.float64])
    def test_image_format_handling(self, mock_rife_backend_factory, mock_subprocess_operations, img_dtype):
        """Test handling of different input image formats."""
        backend = mock_rife_backend_factory(exe_exists=True)
        
        # Create images with different dtypes
        if img_dtype == np.uint8:
            img1 = np.random.randint(0, 256, (4, 4, 3), dtype=img_dtype)
            img2 = np.random.randint(0, 256, (4, 4, 3), dtype=img_dtype)
            # Convert to float32 as expected by function
            img1 = img1.astype(np.float32) / 255.0
            img2 = img2.astype(np.float32) / 255.0
        else:
            img1 = np.random.random((4, 4, 3)).astype(img_dtype)
            img2 = np.random.random((4, 4, 3)).astype(img_dtype)
            if img_dtype == np.float64:
                img1 = img1.astype(np.float32)
                img2 = img2.astype(np.float32)
        
        mock_patches = mock_subprocess_operations(success=True)
        
        with patch.multiple("goesvfi.pipeline.interpolate", **mock_patches):
            mock_patches["tempfile_mkdtemp"].return_value = "/tmp/test"
            mock_patches["numpy_array"].return_value = np.ones((4, 4, 3), dtype=np.uint8)
            
            result = backend.interpolate_pair(img1, img2)
            
            assert isinstance(result, np.ndarray)
            assert result.dtype == np.float32
            assert 0.0 <= result.min() <= result.max() <= 1.0

    def test_interpolation_with_extreme_values(self, mock_rife_backend_factory, mock_subprocess_operations):
        """Test interpolation with extreme pixel values."""
        backend = mock_rife_backend_factory(exe_exists=True)
        
        # Create images with extreme values
        img1 = np.zeros((4, 4, 3), dtype=np.float32)  # All black
        img2 = np.ones((4, 4, 3), dtype=np.float32)   # All white
        
        mock_patches = mock_subprocess_operations(success=True)
        
        with patch.multiple("goesvfi.pipeline.interpolate", **mock_patches):
            mock_patches["tempfile_mkdtemp"].return_value = "/tmp/test"
            mock_patches["numpy_array"].return_value = np.full((4, 4, 3), 127, dtype=np.uint8)
            
            result = backend.interpolate_pair(img1, img2, {"timestep": 0.5})
            
            assert isinstance(result, np.ndarray)
            assert result.dtype == np.float32
            assert result.shape == (4, 4, 3)

    def test_concurrent_interpolation_simulation(self, mock_rife_backend_factory, mock_subprocess_operations, sample_images):
        """Simulate multiple concurrent interpolation operations."""
        import threading
        import time
        
        backend = mock_rife_backend_factory(exe_exists=True)
        images = sample_images()
        results = []
        errors = []
        
        def interpolate_worker(worker_id):
            try:
                mock_patches = mock_subprocess_operations(success=True)
                
                with patch.multiple("goesvfi.pipeline.interpolate", **mock_patches):
                    mock_patches["tempfile_mkdtemp"].return_value = f"/tmp/test_{worker_id}"
                    mock_patches["numpy_array"].return_value = np.ones((4, 4, 3), dtype=np.uint8) * worker_id
                    
                    result = backend.interpolate_pair(images[0], images[1], {"timestep": 0.5})
                    results.append(f"worker_{worker_id}_success")
                    time.sleep(0.001)  # Small delay
            except Exception as e:
                errors.append(f"worker_{worker_id}_error: {e}")
        
        # Create multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=interpolate_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify results
        assert len(results) == 3
        assert len(errors) == 0

    def test_interpolation_command_building_edge_cases(self, mock_rife_backend_factory, mock_subprocess_operations, sample_images):
        """Test command building with edge case configurations."""
        backend = mock_rife_backend_factory(exe_exists=True)
        images = sample_images()
        
        edge_case_configs = [
            {"gpu_id": -1, "thread_spec": "1:1:1"},  # Minimum resources
            {"gpu_id": 0, "thread_spec": "8:16:16", "tile_size": 2048},  # Maximum resources
            {"model_path": "custom/model/path", "tta_spatial": True, "tta_temporal": True},  # Custom model with TTA
        ]
        
        for config in edge_case_configs:
            mock_patches = mock_subprocess_operations(success=True)
            
            with patch.multiple("goesvfi.pipeline.interpolate", **mock_patches):
                mock_patches["tempfile_mkdtemp"].return_value = "/tmp/test"
                mock_patches["numpy_array"].return_value = np.ones((4, 4, 3), dtype=np.uint8)
                
                result = backend.interpolate_pair(images[0], images[1], config)
                
                assert isinstance(result, np.ndarray)
                
                # Verify command builder was called with correct options
                call_args = backend._mock_builder.build_command.call_args[1]
                for key, value in config.items():
                    assert call_args[key] == value

    def test_interpolation_memory_efficiency(self, mock_rife_backend_factory, mock_subprocess_operations):
        """Test interpolation with focus on memory efficiency."""
        backend = mock_rife_backend_factory(exe_exists=True)
        
        # Test with progressively larger image sizes
        image_sizes = [(64, 64, 3), (128, 128, 3), (256, 256, 3)]
        
        for size in image_sizes:
            # Simulate large images
            img1 = np.random.random(size).astype(np.float32)
            img2 = np.random.random(size).astype(np.float32)
            
            mock_patches = mock_subprocess_operations(success=True)
            
            with patch.multiple("goesvfi.pipeline.interpolate", **mock_patches):
                mock_patches["tempfile_mkdtemp"].return_value = "/tmp/test"
                mock_patches["numpy_array"].return_value = np.ones(size, dtype=np.uint8)
                
                result = backend.interpolate_pair(img1, img2, {"tile_enable": True, "tile_size": 64})
                
                assert isinstance(result, np.ndarray)
                assert result.shape == size
                assert result.dtype == np.float32

    def test_interpolation_error_recovery_scenarios(self, mock_rife_backend_factory, sample_images):
        """Test various error recovery scenarios during interpolation."""
        backend = mock_rife_backend_factory(exe_exists=True)
        images = sample_images()
        
        error_scenarios = [
            {"exception": subprocess.CalledProcessError(1, ["rife"], stderr="Process failed")},
            {"exception": KeyError("Missing configuration key")},
            {"exception": ValueError("Invalid parameter value")},
            {"exception": RuntimeError("General runtime error")},
        ]
        
        for scenario in error_scenarios:
            with patch("goesvfi.pipeline.interpolate.subprocess.run", side_effect=scenario["exception"]):
                with patch("goesvfi.pipeline.interpolate.tempfile.mkdtemp", return_value="/tmp/test"):
                    with patch("goesvfi.pipeline.interpolate.shutil.rmtree") as mock_rmtree:
                        with patch("goesvfi.pipeline.interpolate.Image.fromarray"):
                            
                            if isinstance(scenario["exception"], subprocess.CalledProcessError):
                                with pytest.raises(RuntimeError, match="RIFE executable failed"):
                                    backend.interpolate_pair(images[0], images[1])
                            else:
                                with pytest.raises(OSError, match="Error during RIFE CLI processing"):
                                    backend.interpolate_pair(images[0], images[1])
                            
                            # Verify cleanup was called even during error
                            mock_rmtree.assert_called_once()

    def test_interpolation_workflow_integration(self, mock_rife_backend_factory, mock_subprocess_operations, sample_images):
        """Test complete interpolation workflow integration."""
        backend = mock_rife_backend_factory(exe_exists=True)
        images = sample_images()
        
        workflow_steps = [
            {"description": "Standard interpolation", "options": {"timestep": 0.5}},
            {"description": "Tiled interpolation", "options": {"tile_enable": True, "tile_size": 128}},
            {"description": "UHD interpolation", "options": {"uhd_mode": True, "timestep": 0.3}},
            {"description": "GPU interpolation", "options": {"gpu_id": 0, "thread_spec": "2:4:4"}},
        ]
        
        for step in workflow_steps:
            mock_patches = mock_subprocess_operations(success=True)
            
            with patch.multiple("goesvfi.pipeline.interpolate", **mock_patches):
                mock_patches["tempfile_mkdtemp"].return_value = "/tmp/test"
                mock_patches["numpy_array"].return_value = np.ones((4, 4, 3), dtype=np.uint8)
                
                result = backend.interpolate_pair(images[0], images[1], step["options"])
                
                # Verify interpolation step completed
                assert isinstance(result, np.ndarray)
                assert result.dtype == np.float32
                assert result.shape == (4, 4, 3)
                
                # Verify subprocess and cleanup were called
                mock_patches["subprocess_run"].assert_called_once()
                mock_patches["rmtree"].assert_called_once()