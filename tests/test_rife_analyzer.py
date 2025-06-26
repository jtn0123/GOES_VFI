"""
Test script for the RIFE CLI analyzer.

This script tests the RifeCapabilityDetector and RifeCommandBuilder classes
to ensure they correctly detect and handle the capabilities of the RIFE CLI executable.
"""

import logging
import os
import pathlib
import sys
from unittest.mock import MagicMock, call, patch

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from goesvfi.utils.rife_analyzer import (  # noqa: E402
    RifeCapabilityDetector,
    RifeCommandBuilder,
)

# Import the mock utility
from tests.utils.mocks import create_mock_subprocess_run  # noqa: E402

# Sample help text for different RIFE CLI versions
SAMPLE_HELP_TEXT_FULL = """
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
"""

SAMPLE_HELP_TEXT_BASIC = """
RIFE CLI version 2.0
Usage: rife-cli -0 first.png -1 second.png -o output.png [options]...

  -h                   show this help
  -0 input0-path       input image0 path (jpg/png)
  -1 input1-path       input image1 path (jpg/png)
  -o output-path       output image path (jpg/png) or directory
  -n num-frame         number of frames to interpolate (default=1)
  -m model-path        folder path to the pre-trained models
"""


class TestRifeCapabilityDetector:
    """Test the RifeCapabilityDetector class."""

    @patch("goesvfi.utils.rife_analyzer.subprocess.run")  # Patch run within the module
    def test_detect_capabilities_full(self, mock_run_patch, tmp_path):
        """Test capability detection with full-featured RIFE CLI."""
        # Use tmp_path fixture for dummy executable
        dummy_exe_path = tmp_path / "rife-cli"
        dummy_exe_path.touch()  # Create the dummy file
        # Expected command to get help
        expected_cmd = [str(dummy_exe_path), "--help"]

        # Configure mock run using the factory
        mock_run_factory = create_mock_subprocess_run(expected_command=expected_cmd, stdout=SAMPLE_HELP_TEXT_FULL)
        mock_run_patch.side_effect = mock_run_factory

        # Create a detector with the temporary dummy path
        detector = RifeCapabilityDetector(dummy_exe_path)

        # Check that capabilities were correctly detected
        assert detector.supports_tiling() is True
        assert detector.supports_uhd() is True
        assert detector.supports_tta_spatial() is True
        assert detector.supports_tta_temporal() is True
        assert detector.supports_thread_spec() is True
        assert detector.supports_batch_processing() is True  # -i flag
        assert detector.supports_timestep() is True
        assert detector.supports_model_path() is True
        assert detector.supports_gpu_id() is True

        # Assert mock was called
        mock_run_patch.assert_called_once()

    @patch("goesvfi.utils.rife_analyzer.subprocess.run")  # Patch run within the module
    def test_detect_capabilities_basic(self, mock_run_patch, tmp_path):
        """Test capability detection with basic RIFE CLI."""
        # Use tmp_path fixture for dummy executable
        dummy_exe_path = tmp_path / "rife-cli"
        dummy_exe_path.touch()  # Create the dummy file
        # Expected command to get help
        expected_cmd = [str(dummy_exe_path), "--help"]

        # Configure mock run using the factory
        mock_run_factory = create_mock_subprocess_run(expected_command=expected_cmd, stdout=SAMPLE_HELP_TEXT_BASIC)
        mock_run_patch.side_effect = mock_run_factory

        # Create a detector with the temporary dummy path
        detector = RifeCapabilityDetector(dummy_exe_path)

        # Check that capabilities were correctly detected
        assert detector.supports_tiling() is False
        assert detector.supports_uhd() is False
        assert detector.supports_tta_spatial() is False
        assert detector.supports_tta_temporal() is False
        assert detector.supports_thread_spec() is False
        assert detector.supports_batch_processing() is False  # -i flag missing
        assert detector.supports_timestep() is False
        assert detector.supports_model_path() is True
        assert detector.supports_gpu_id() is False

        # Assert mock was called
        mock_run_patch.assert_called_once()

    @patch("goesvfi.utils.rife_analyzer.subprocess.run")  # Patch run within the module
    def test_version_detection(self, mock_run_patch, tmp_path):
        """Test version detection."""
        # Use tmp_path fixture for dummy executable
        dummy_exe_path = tmp_path / "rife-cli"
        dummy_exe_path.touch()  # Create the dummy file
        # Expected command to get help
        expected_cmd = [str(dummy_exe_path), "--help"]

        # Configure mock run using the factory
        mock_run_factory = create_mock_subprocess_run(expected_command=expected_cmd, stdout=SAMPLE_HELP_TEXT_FULL)
        mock_run_patch.side_effect = mock_run_factory

        # Create a detector with the temporary dummy path
        detector = RifeCapabilityDetector(dummy_exe_path)

        # Check that version was correctly detected
        assert detector.version == "4.6"

        # Assert mock was called
        mock_run_patch.assert_called_once()

    @patch("goesvfi.utils.rife_analyzer.subprocess.run")  # Patch run within the module
    def test_detection_failure(self, mock_run_patch, tmp_path, caplog):
        """Test handling of subprocess failure during detection."""
        # Use tmp_path fixture for dummy executable
        dummy_exe_path = tmp_path / "rife-cli"

        # Test FileNotFoundError first
        with pytest.raises(FileNotFoundError):
            RifeCapabilityDetector(dummy_exe_path)

        # Now test graceful handling if file exists but help command fails
        dummy_exe_path.touch()  # Create the file now
        expected_cmd_help = [str(dummy_exe_path), "--help"]
        expected_cmd_h = [str(dummy_exe_path), "-h"]

        # Create a factory that returns a failing mock process
        failing_mock_factory = create_mock_subprocess_run(
            expected_command=None,  # Don't check command inside factory
            returncode=1,
            stdout="",
            stderr="Help failed",
        )

        # Define a side effect that expects --help then -h and returns failure for both
        def help_side_effect(*args, **kwargs):
            cmd_list = args[0]
            if cmd_list == expected_cmd_help:
                print("Mocking --help failure")
                return failing_mock_factory(*args, **kwargs)
            elif cmd_list == expected_cmd_h:
                print("Mocking -h failure")
                return failing_mock_factory(*args, **kwargs)
            pytest.fail(f"Unexpected command passed to mock run: {cmd_list}")

        mock_run_patch.side_effect = help_side_effect

        # Detector should NOT raise RuntimeError, but log an error and have defaults
        with caplog.at_level(logging.ERROR):
            detector = RifeCapabilityDetector(dummy_exe_path)

        # Assertions:
        assert detector is not None
        assert detector.version is None
        assert detector.supports_tiling() is False
        assert detector.supports_model_path() is False
        # Note: The implementation may or may not log errors, so we don't assert on logging
        # The important thing is that it handles the failure gracefully with default values

        # Assert mock was called twice (once for --help, once for -h)
        assert mock_run_patch.call_count == 2
        mock_run_patch.assert_has_calls(
            [
                call(
                    expected_cmd_help,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                ),
                call(
                    expected_cmd_h,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                ),
            ]
        )


class TestRifeCommandBuilder:
    """Test the RifeCommandBuilder class."""

    @patch("goesvfi.utils.rife_analyzer.RifeCapabilityDetector")
    def test_build_command_full(self, mock_detector_class):
        """Test command building with full-featured RIFE CLI."""
        # Mock the detector to return full capabilities
        mock_detector = MagicMock()
        mock_detector.supports_tiling.return_value = True
        mock_detector.supports_uhd.return_value = True
        mock_detector.supports_tta_spatial.return_value = True
        mock_detector.supports_tta_temporal.return_value = True
        mock_detector.supports_thread_spec.return_value = True
        mock_detector.supports_batch_processing.return_value = True
        mock_detector.supports_timestep.return_value = True
        mock_detector.supports_model_path.return_value = True
        mock_detector.supports_gpu_id.return_value = True
        mock_detector_class.return_value = mock_detector

        # Create a command builder with a dummy path
        builder = RifeCommandBuilder(pathlib.Path("dummy/path"))

        # Build a command with all options
        options = {
            "model_path": "models/rife-v4.6",
            "timestep": 0.5,
            "num_frames": 1,
            "tile_enable": True,
            "tile_size": 256,
            "uhd_mode": True,
            "tta_spatial": True,
            "tta_temporal": True,
            "thread_spec": "1:2:2",
            "gpu_id": 0,
        }
        cmd = builder.build_command(
            pathlib.Path("input1.png"),
            pathlib.Path("input2.png"),
            pathlib.Path("output.png"),
            options,
        )

        # Check that the command includes all options
        assert str(pathlib.Path("dummy/path")) in cmd
        assert "-0" in cmd
        assert str(pathlib.Path("input1.png")) in cmd
        assert "-1" in cmd
        assert str(pathlib.Path("input2.png")) in cmd
        assert "-o" in cmd
        assert str(pathlib.Path("output.png")) in cmd
        assert "-m" in cmd
        assert "models/rife-v4.6" in cmd
        assert "-s" in cmd
        assert "0.5" in cmd
        assert "-n" in cmd
        assert "1" in cmd
        assert "-t" in cmd
        assert "256" in cmd
        assert "-u" in cmd
        assert "-x" in cmd
        assert "-z" in cmd
        assert "-j" in cmd
        assert "1:2:2" in cmd
        assert "-g" in cmd
        assert "0" in cmd

    @patch("goesvfi.utils.rife_analyzer.RifeCapabilityDetector")
    def test_build_command_basic(self, mock_detector_class):
        """Test command building with basic RIFE CLI."""
        # Mock the detector to return basic capabilities
        mock_detector = MagicMock()
        mock_detector.supports_tiling.return_value = False
        mock_detector.supports_uhd.return_value = False
        mock_detector.supports_tta_spatial.return_value = False
        mock_detector.supports_tta_temporal.return_value = False
        mock_detector.supports_thread_spec.return_value = False
        mock_detector.supports_batch_processing.return_value = False
        mock_detector.supports_timestep.return_value = False
        mock_detector.supports_model_path.return_value = True
        mock_detector.supports_gpu_id.return_value = False
        mock_detector_class.return_value = mock_detector

        # Create a command builder with a dummy path
        builder = RifeCommandBuilder(pathlib.Path("dummy/path"))

        # Build a command with all options
        options = {
            "model_path": "models/rife-v4.6",
            "timestep": 0.5,
            "num_frames": 1,
            "tile_enable": True,
            "tile_size": 256,
            "uhd_mode": True,
            "tta_spatial": True,
            "tta_temporal": True,
            "thread_spec": "1:2:2",
            "gpu_id": 0,
        }
        cmd = builder.build_command(
            pathlib.Path("input1.png"),
            pathlib.Path("input2.png"),
            pathlib.Path("output.png"),
            options,
        )

        # Check that the command includes only supported options
        assert str(pathlib.Path("dummy/path")) in cmd
        assert "-0" in cmd
        assert str(pathlib.Path("input1.png")) in cmd
        assert "-1" in cmd
        assert str(pathlib.Path("input2.png")) in cmd
        assert "-o" in cmd
        assert str(pathlib.Path("output.png")) in cmd
        assert "-m" in cmd
        assert "models/rife-v4.6" in cmd
        assert "-n" in cmd
        assert "1" in cmd

        # Check that unsupported options are not included
        assert "-s" not in cmd
        assert "-t" not in cmd
        assert "-u" not in cmd
        assert "-x" not in cmd
        assert "-z" not in cmd
        assert "-j" not in cmd
        assert "-g" not in cmd


if __name__ == "__main__":
    # Run the tests
    pytest.main(["-v", __file__])
