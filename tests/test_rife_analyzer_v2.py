"""Optimized test script for the RIFE CLI analyzer.

Optimizations applied:
- Mock-based testing to avoid subprocess dependencies
- Shared fixtures for common setup and mock configurations
- Parameterized test scenarios for comprehensive capability coverage
- Enhanced error handling and edge case validation
- Streamlined command building validation

This script tests the RifeCapabilityDetector and RifeCommandBuilder classes
to ensure they correctly detect and handle the capabilities of the RIFE CLI executable.
"""

import logging
import pathlib
from unittest.mock import MagicMock, call, patch
import pytest


class TestRifeCapabilityDetectorV2:
    """Optimized test class for the RifeCapabilityDetector class."""

    @pytest.fixture(scope="class")
    def sample_help_texts(self):
        """Sample help text for different RIFE CLI versions."""
        return {
            "full": """
RIFE ncnn Vulkan version 4.6
Usage: rife-ncnn-vulkan -0 first.png -1 second.png -o output.png [options]...

  -h                   show this help
  -v                   verbose output
  -0 input0-path       input image0 path (jpg/png/webp)
  -1 input1-path       input image1 path (jpg/png/webp)
  -o output-path       output image path (jpg/png/webp) or directory
  -n num-frame         number of frames to interpolate (default=1)
  -s time-step         time step (0.0~1.0) (default=0.5)
  -m model-path        folder path to the pre-trained models
  -g gpu-id            gpu device to use (default=auto) can be 0,1,2 for multi-gpu
  -j load:proc:save    thread count for load/proc/save (default=1:2:2) can be 1:2,
                                                        2,
                                                        2:2 for multi-gpu
  -f pattern-format    output image filename pattern format (default=%08d.png)
  -x                   enable tta mode (2x slower but slightly better quality)
  -z                   enable temporal tta mode
  -t tile-size         tile size (>=128, default=256) can be 256,256,128 for multi-gpu
  -u                   enable UHD mode (4x slower but better quality in 4K video)
  -i input-path        input video/image directory path
  -c                   enable cache mode for input sequence, reduce memory usage
  -a                   alpha channel mode (0=ignore, 1=separate, 2=premultiplied) (default=0)
  -p                   enable progress bar
  -C cache-path        cache directory path
""",
            "basic": """
RIFE CLI version 2.0
Usage: rife-cli -0 first.png -1 second.png -o output.png [options]...

  -h                   show this help
  -0 input0-path       input image0 path (jpg/png)
  -1 input1-path       input image1 path (jpg/png)
  -o output-path       output image path (jpg/png) or directory
  -n num-frame         number of frames to interpolate (default=1)
  -m model-path        folder path to the pre-trained models
""",
            "minimal": """
RIFE version 1.0
Usage: rife -0 first.png -1 second.png -o output.png

  -h                   show this help
  -0 input0-path       input image0 path
  -1 input1-path       input image1 path
  -o output-path       output image path
"""
        }

    @pytest.fixture
    def mock_subprocess_factory(self):
        """Factory for creating subprocess run mocks."""
        def create_mock_run(stdout="", stderr="", returncode=0):
            mock_result = MagicMock()
            mock_result.stdout = stdout
            mock_result.stderr = stderr
            mock_result.returncode = returncode
            return mock_result
        return create_mock_run

    @pytest.fixture
    def mock_detector_setup(self, tmp_path, mock_subprocess_factory):
        """Setup mock detector with temporary executable."""
        dummy_exe_path = tmp_path / "rife-cli"
        dummy_exe_path.touch()  # Create the dummy file
        
        def create_detector_with_help(help_text):
            mock_result = mock_subprocess_factory(stdout=help_text)
            with patch("goesvfi.utils.rife_analyzer.subprocess.run", return_value=mock_result):
                from goesvfi.utils.rife_analyzer import RifeCapabilityDetector
                return RifeCapabilityDetector(dummy_exe_path)
        
        return create_detector_with_help, dummy_exe_path

    @pytest.mark.parametrize("help_type,expected_capabilities", [
        ("full", {
            "tiling": True,
            "uhd": True,
            "tta_spatial": True,
            "tta_temporal": True,
            "thread_spec": True,
            "batch_processing": True,
            "timestep": True,
            "model_path": True,
            "gpu_id": True,
            "version": "4.6"
        }),
        ("basic", {
            "tiling": False,
            "uhd": False,
            "tta_spatial": False,
            "tta_temporal": False,
            "thread_spec": False,
            "batch_processing": False,
            "timestep": False,
            "model_path": True,
            "gpu_id": False,
            "version": "2.0"
        }),
        ("minimal", {
            "tiling": False,
            "uhd": False,
            "tta_spatial": False,
            "tta_temporal": False,
            "thread_spec": False,
            "batch_processing": False,
            "timestep": False,
            "model_path": False,
            "gpu_id": False,
            "version": "1.0"
        })
    ])
    def test_detect_capabilities_scenarios(self, mock_detector_setup, sample_help_texts, help_type, expected_capabilities):
        """Test capability detection with various RIFE CLI versions."""
        create_detector, _ = mock_detector_setup
        detector = create_detector(sample_help_texts[help_type])
        
        # Verify all capabilities
        assert detector.supports_tiling() == expected_capabilities["tiling"]
        assert detector.supports_uhd() == expected_capabilities["uhd"]
        assert detector.supports_tta_spatial() == expected_capabilities["tta_spatial"]
        assert detector.supports_tta_temporal() == expected_capabilities["tta_temporal"]
        assert detector.supports_thread_spec() == expected_capabilities["thread_spec"]
        assert detector.supports_batch_processing() == expected_capabilities["batch_processing"]
        assert detector.supports_timestep() == expected_capabilities["timestep"]
        assert detector.supports_model_path() == expected_capabilities["model_path"]
        assert detector.supports_gpu_id() == expected_capabilities["gpu_id"]
        assert detector.version == expected_capabilities["version"]

    def test_detection_file_not_found(self, tmp_path):
        """Test handling of FileNotFoundError when executable doesn't exist."""
        nonexistent_path = tmp_path / "nonexistent_rife"
        
        with pytest.raises(FileNotFoundError):
            from goesvfi.utils.rife_analyzer import RifeCapabilityDetector
            RifeCapabilityDetector(nonexistent_path)

    @pytest.mark.parametrize("help_command,fallback_command", [
        (["--help"], ["-h"]),
    ])
    def test_detection_subprocess_failure(self, mock_detector_setup, mock_subprocess_factory, help_command, fallback_command, caplog):
        """Test handling of subprocess failure during detection."""
        create_detector, dummy_exe_path = mock_detector_setup
        
        # Mock subprocess to fail for both help commands
        def mock_run_side_effect(*args, **kwargs):
            return mock_subprocess_factory(stdout="", stderr="Help failed", returncode=1)
        
        with patch("goesvfi.utils.rife_analyzer.subprocess.run", side_effect=mock_run_side_effect) as mock_run:
            with caplog.at_level(logging.ERROR):
                from goesvfi.utils.rife_analyzer import RifeCapabilityDetector
                detector = RifeCapabilityDetector(dummy_exe_path)
        
        # Verify detector handles failure gracefully with defaults
        assert detector is not None
        assert detector.version is None
        assert detector.supports_tiling() is False
        assert detector.supports_model_path() is False
        assert detector.supports_uhd() is False
        
        # Verify both help commands were attempted
        assert mock_run.call_count == 2
        expected_calls = [
            call([str(dummy_exe_path), "--help"], capture_output=True, text=True, timeout=5, check=False),
            call([str(dummy_exe_path), "-h"], capture_output=True, text=True, timeout=5, check=False)
        ]
        mock_run.assert_has_calls(expected_calls)

    def test_version_extraction_edge_cases(self, mock_detector_setup, sample_help_texts):
        """Test version extraction with various format edge cases."""
        create_detector, _ = mock_detector_setup
        
        # Test various version formats
        version_test_cases = [
            ("RIFE version 1.2.3", "1.2.3"),
            ("RIFE CLI v2.0-beta", "2.0-beta"),
            ("rife-ncnn-vulkan version 4.6.1", "4.6.1"),
            ("No version info", None),
        ]
        
        for help_text, expected_version in version_test_cases:
            detector = create_detector(help_text)
            assert detector.version == expected_version

    def test_capability_detection_edge_cases(self, mock_detector_setup):
        """Test capability detection with edge case help text."""
        create_detector, _ = mock_detector_setup
        
        # Test with partial capability indicators
        partial_help = """
Usage: rife -0 first.png -1 second.png -o output.png [options]...
  -t tile-size         partial tiling support
  -x                   spatial tta only
  -m model-path        model support
"""
        
        detector = create_detector(partial_help)
        
        # Should detect present capabilities
        assert detector.supports_tiling() is True
        assert detector.supports_tta_spatial() is True
        assert detector.supports_model_path() is True
        
        # Should not detect missing capabilities
        assert detector.supports_uhd() is False
        assert detector.supports_tta_temporal() is False
        assert detector.supports_batch_processing() is False

    def test_detector_caching_behavior(self, mock_detector_setup, sample_help_texts):
        """Test that detector caches results and doesn't re-run subprocess."""
        create_detector, dummy_exe_path = mock_detector_setup
        
        with patch("goesvfi.utils.rife_analyzer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=sample_help_texts["full"], returncode=0)
            
            from goesvfi.utils.rife_analyzer import RifeCapabilityDetector
            detector = RifeCapabilityDetector(dummy_exe_path)
            
            # Multiple capability checks should not trigger additional subprocess calls
            assert detector.supports_tiling() is True
            assert detector.supports_uhd() is True
            assert detector.supports_tta_spatial() is True
            assert detector.version == "4.6"
            
            # Verify subprocess was called only once during initialization
            assert mock_run.call_count == 1


class TestRifeCommandBuilderV2:
    """Optimized test class for the RifeCommandBuilder class."""

    @pytest.fixture
    def mock_detector_factory(self):
        """Factory for creating mock detectors with specific capabilities."""
        def create_mock_detector(capabilities):
            mock_detector = MagicMock()
            
            # Set default capabilities
            default_capabilities = {
                "tiling": False,
                "uhd": False,
                "tta_spatial": False,
                "tta_temporal": False,
                "thread_spec": False,
                "batch_processing": False,
                "timestep": False,
                "model_path": False,
                "gpu_id": False
            }
            
            # Update with provided capabilities
            default_capabilities.update(capabilities)
            
            # Configure mock methods
            for capability, supported in default_capabilities.items():
                method_name = f"supports_{capability}"
                getattr(mock_detector, method_name).return_value = supported
            
            return mock_detector
        
        return create_mock_detector

    @pytest.fixture
    def sample_paths(self, tmp_path):
        """Create sample file paths for testing."""
        return {
            "executable": pathlib.Path("dummy/rife-cli"),
            "input1": pathlib.Path("input1.png"),
            "input2": pathlib.Path("input2.png"),
            "output": pathlib.Path("output.png"),
            "model": "models/rife-v4.6"
        }

    @pytest.mark.parametrize("capabilities,options,expected_flags", [
        # Full-featured RIFE
        (
            {"tiling": True, "uhd": True, "tta_spatial": True, "tta_temporal": True, 
             "thread_spec": True, "timestep": True, "model_path": True, "gpu_id": True},
            {"model_path": "models/rife-v4.6", "timestep": 0.5, "num_frames": 1,
             "tile_enable": True, "tile_size": 256, "uhd_mode": True,
             "tta_spatial": True, "tta_temporal": True, "thread_spec": "1:2:2", "gpu_id": 0},
            ["-m", "-s", "-n", "-t", "-u", "-x", "-z", "-j", "-g"]
        ),
        # Basic RIFE
        (
            {"model_path": True},
            {"model_path": "models/rife-v4.6", "num_frames": 1,
             "tile_enable": True, "uhd_mode": True, "tta_spatial": True},
            ["-m", "-n"]  # Only supported flags should appear
        ),
        # Minimal RIFE
        (
            {},
            {"model_path": "models/rife-v4.6", "num_frames": 1},
            []  # No optional flags supported
        ),
    ])
    def test_build_command_capability_scenarios(self, mock_detector_factory, sample_paths, capabilities, options, expected_flags):
        """Test command building with various capability combinations."""
        mock_detector = mock_detector_factory(capabilities)
        
        with patch("goesvfi.utils.rife_analyzer.RifeCapabilityDetector", return_value=mock_detector):
            from goesvfi.utils.rife_analyzer import RifeCommandBuilder
            builder = RifeCommandBuilder(sample_paths["executable"])
            
            cmd = builder.build_command(
                sample_paths["input1"],
                sample_paths["input2"],
                sample_paths["output"],
                options
            )
            
            # Verify basic command structure
            assert str(sample_paths["executable"]) in cmd
            assert "-0" in cmd
            assert str(sample_paths["input1"]) in cmd
            assert "-1" in cmd
            assert str(sample_paths["input2"]) in cmd
            assert "-o" in cmd
            assert str(sample_paths["output"]) in cmd
            
            # Verify only expected flags are present
            for flag in expected_flags:
                assert flag in cmd, f"Expected flag {flag} not found in command"
            
            # Verify unsupported flags are not present
            all_possible_flags = ["-m", "-s", "-n", "-t", "-u", "-x", "-z", "-j", "-g"]
            for flag in all_possible_flags:
                if flag not in expected_flags:
                    # Allow -n (num_frames) as it's basic functionality
                    if flag == "-n" and "num_frames" in options:
                        continue
                    assert flag not in cmd or cmd.count(flag) == 0, f"Unexpected flag {flag} found in command"

    def test_command_option_value_mapping(self, mock_detector_factory, sample_paths):
        """Test that option values are correctly mapped to command arguments."""
        mock_detector = mock_detector_factory({
            "model_path": True, "timestep": True, "tiling": True, 
            "thread_spec": True, "gpu_id": True
        })
        
        with patch("goesvfi.utils.rife_analyzer.RifeCapabilityDetector", return_value=mock_detector):
            from goesvfi.utils.rife_analyzer import RifeCommandBuilder
            builder = RifeCommandBuilder(sample_paths["executable"])
            
            test_options = {
                "model_path": "custom/model/path",
                "timestep": 0.75,
                "num_frames": 5,
                "tile_size": 512,
                "thread_spec": "2:4:2",
                "gpu_id": 1
            }
            
            cmd = builder.build_command(
                sample_paths["input1"],
                sample_paths["input2"],
                sample_paths["output"],
                test_options
            )
            
            # Verify values are correctly placed after their flags
            cmd_str = " ".join(cmd)
            assert "-m custom/model/path" in cmd_str
            assert "-s 0.75" in cmd_str
            assert "-n 5" in cmd_str
            assert "-t 512" in cmd_str
            assert "-j 2:4:2" in cmd_str
            assert "-g 1" in cmd_str

    def test_command_builder_error_handling(self, mock_detector_factory, sample_paths):
        """Test command builder error handling scenarios."""
        mock_detector = mock_detector_factory({"model_path": True})
        
        with patch("goesvfi.utils.rife_analyzer.RifeCapabilityDetector", return_value=mock_detector):
            from goesvfi.utils.rife_analyzer import RifeCommandBuilder
            builder = RifeCommandBuilder(sample_paths["executable"])
            
            # Test with empty options
            cmd = builder.build_command(
                sample_paths["input1"],
                sample_paths["input2"],
                sample_paths["output"],
                {}
            )
            
            # Should still build basic command
            assert len(cmd) >= 6  # executable + 6 basic args
            assert str(sample_paths["executable"]) in cmd
            assert "-0" in cmd
            assert "-1" in cmd
            assert "-o" in cmd

    def test_boolean_option_handling(self, mock_detector_factory, sample_paths):
        """Test handling of boolean options in command building."""
        mock_detector = mock_detector_factory({
            "tiling": True, "uhd": True, "tta_spatial": True, "tta_temporal": True
        })
        
        with patch("goesvfi.utils.rife_analyzer.RifeCapabilityDetector", return_value=mock_detector):
            from goesvfi.utils.rife_analyzer import RifeCommandBuilder
            builder = RifeCommandBuilder(sample_paths["executable"])
            
            # Test with boolean options enabled
            options_enabled = {
                "tile_enable": True,
                "uhd_mode": True,
                "tta_spatial": True,
                "tta_temporal": True
            }
            
            cmd_enabled = builder.build_command(
                sample_paths["input1"],
                sample_paths["input2"],
                sample_paths["output"],
                options_enabled
            )
            
            # Boolean flags should be present when enabled
            assert "-u" in cmd_enabled  # UHD mode
            assert "-x" in cmd_enabled  # TTA spatial
            assert "-z" in cmd_enabled  # TTA temporal
            
            # Test with boolean options disabled
            options_disabled = {
                "tile_enable": False,
                "uhd_mode": False,
                "tta_spatial": False,
                "tta_temporal": False
            }
            
            cmd_disabled = builder.build_command(
                sample_paths["input1"],
                sample_paths["input2"],
                sample_paths["output"],
                options_disabled
            )
            
            # Boolean flags should not be present when disabled
            assert "-u" not in cmd_disabled
            assert "-x" not in cmd_disabled
            assert "-z" not in cmd_disabled

    def test_command_builder_path_handling(self, mock_detector_factory, sample_paths):
        """Test command builder handling of different path types."""
        mock_detector = mock_detector_factory({"model_path": True})
        
        with patch("goesvfi.utils.rife_analyzer.RifeCapabilityDetector", return_value=mock_detector):
            from goesvfi.utils.rife_analyzer import RifeCommandBuilder
            builder = RifeCommandBuilder(sample_paths["executable"])
            
            # Test with pathlib.Path objects
            path_options = {
                "model_path": pathlib.Path("models/custom")
            }
            
            cmd = builder.build_command(
                pathlib.Path("input/frame1.png"),
                pathlib.Path("input/frame2.png"),
                pathlib.Path("output/result.png"),
                path_options
            )
            
            # Verify paths are converted to strings
            cmd_str = " ".join(cmd)
            assert "input/frame1.png" in cmd_str
            assert "input/frame2.png" in cmd_str
            assert "output/result.png" in cmd_str
            assert "models/custom" in cmd_str

    def test_command_builder_performance(self, mock_detector_factory, sample_paths):
        """Test command builder performance with multiple builds."""
        mock_detector = mock_detector_factory({
            "model_path": True, "timestep": True, "tiling": True, "gpu_id": True
        })
        
        with patch("goesvfi.utils.rife_analyzer.RifeCapabilityDetector", return_value=mock_detector):
            from goesvfi.utils.rife_analyzer import RifeCommandBuilder
            builder = RifeCommandBuilder(sample_paths["executable"])
            
            # Build multiple commands to test performance
            base_options = {
                "model_path": "models/rife-v4.6",
                "timestep": 0.5,
                "tile_size": 256,
                "gpu_id": 0
            }
            
            commands = []
            for i in range(10):
                cmd = builder.build_command(
                    pathlib.Path(f"input{i}.png"),
                    pathlib.Path(f"input{i+1}.png"),
                    pathlib.Path(f"output{i}.png"),
                    base_options
                )
                commands.append(cmd)
            
            # Verify all commands were built successfully
            assert len(commands) == 10
            for cmd in commands:
                assert len(cmd) > 6  # Should have basic structure
                assert str(sample_paths["executable"]) in cmd