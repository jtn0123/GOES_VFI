"""Tests for rife_analyzer utility functions."""

import pathlib
import subprocess
from unittest.mock import Mock, patch

import pytest

from goesvfi.utils.rife_analyzer import (
    RifeCapabilityDetector,
    RifeCommandBuilder,
    analyze_rife_executable,
)


class TestRifeCapabilityDetector:
    """Tests for the RifeCapabilityDetector class."""

    @patch("subprocess.run")
    def test_init_successful_detection(self, mock_run):
        """Test successful initialization and capability detection."""
        # Create a mock executable path
        exe_path = pathlib.Path("/path/to/rife")

        # Mock the help command output
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """
        RIFE CLI v4.6
        Usage: rife [options]

        Options:
          -i, --input         Input directory
          -o, --output        Output file
          -m, --model         Model path
          --uhd               Enable UHD mode
          --tile              Enable tiling
          --tile-size         Tile size (default: 256)
          --tta-spatial       Enable spatial TTA
          --tta-temporal      Enable temporal TTA
          --thread-spec       Thread specification (load:proc:save)
          --gpu-id            GPU device ID
        """
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Create detector
        with patch("pathlib.Path.exists", return_value=True):
            detector = RifeCapabilityDetector(exe_path)

        # Verify capabilities were detected
        assert detector.version == "4.6"
        assert detector.supports_tiling() is True
        assert detector.supports_uhd() is True
        assert detector.supports_tta_spatial() is True
        assert detector.supports_tta_temporal() is True
        assert detector.supports_thread_spec() is True
        assert detector.supports_gpu_id() is True

    def test_init_exe_not_found(self):
        """Test initialization with non-existent executable."""
        exe_path = pathlib.Path("/nonexistent/rife")

        with pytest.raises(FileNotFoundError):
            RifeCapabilityDetector(exe_path)

    @patch("subprocess.run")
    def test_init_help_command_fails(self, mock_run):
        """Test handling when help command fails."""
        exe_path = pathlib.Path("/path/to/rife")

        # Mock help command failure
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error running help"
        mock_run.return_value = mock_result

        with patch("pathlib.Path.exists", return_value=True):
            detector = RifeCapabilityDetector(exe_path)

        # Should handle gracefully with no capabilities
        assert detector.version is None
        assert detector.supports_tiling() is False
        assert detector.supports_uhd() is False

    @patch("subprocess.run")
    def test_version_detection(self, mock_run):
        """Test version detection from help output."""
        exe_path = pathlib.Path("/path/to/rife")

        # Test various version string formats
        test_cases = [
            ("RIFE v4.6 - Video Frame Interpolation", "4.6"),
            ("rife-ncnn-vulkan version 4.7.0", "4.7.0"),
            ("Version: 4.8", "4.8"),
            ("No version info here", None),
        ]

        for help_text, expected_version in test_cases:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = help_text
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            with patch("pathlib.Path.exists", return_value=True):
                detector = RifeCapabilityDetector(exe_path)

            assert detector.version == expected_version

    @patch("subprocess.run")
    def test_capability_detection_partial_support(self, mock_run):
        """Test detection when only some capabilities are supported."""
        exe_path = pathlib.Path("/path/to/rife")

        # Mock help output with only some options
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """
        RIFE CLI v3.0
        Options:
          -i, --input         Input directory
          -o, --output        Output file
          --uhd               Enable UHD mode
        """
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        with patch("pathlib.Path.exists", return_value=True):
            detector = RifeCapabilityDetector(exe_path)

        # Only UHD should be detected
        assert detector.supports_uhd() is True
        assert detector.supports_tiling() is False
        assert detector.supports_tta_spatial() is False
        assert detector.supports_thread_spec() is False

    def test_detect_capabilities_with_simulated_help(self, mocker):
        """Detect capabilities using a predefined help text."""
        exe_path = pathlib.Path("/path/to/rife")
        help_text = (
            "RIFE v4.6\n"
            "Options:\n"
            "  -u  enable uhd\n"
            "  -t  enable tiling\n"
            "  -x  spatial tta\n"
            "  -z  temporal tta\n"
            "  -j  thread spec\n"
            "  -g  gpu id\n"
            "  -m  model path\n"
        )

        mocker.patch("pathlib.Path.exists", return_value=True)
        mocker.patch.object(
            RifeCapabilityDetector,
            "_run_help_command",
            return_value=(help_text, True),
        )

        detector = RifeCapabilityDetector(exe_path)

        assert detector.version == "4.6"
        assert detector.supports_uhd() is True
        assert detector.supports_tiling() is True
        assert detector.supports_tta_spatial() is True
        assert detector.supports_tta_temporal() is True
        assert detector.supports_thread_spec() is True
        assert detector.supports_gpu_id() is True
        assert detector.supports_model_path() is True

    def test_help_command_timeout(self, mocker):
        """_run_help_command should handle subprocess timeouts."""
        exe_path = pathlib.Path("/path/to/rife")
        mocker.patch("pathlib.Path.exists", return_value=True)
        with patch.object(RifeCapabilityDetector, "_detect_capabilities"):
            detector = RifeCapabilityDetector(exe_path)

        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=[str(exe_path)], timeout=5),
        )

        text, success = detector._run_help_command()
        assert success is False
        assert "Timeout" in text

    def test_build_command_basic(self):
        """Test building basic command without optional features."""
        exe_path = pathlib.Path("/path/to/rife")

        # Mock the detector to return no capabilities
        with patch("pathlib.Path.exists", return_value=True):
            with patch.object(RifeCapabilityDetector, "_detect_capabilities"):
                # Create command builder
                builder = RifeCommandBuilder(exe_path)
                # Mock the detector inside builder
                builder.detector._capabilities = {}  # No capabilities
                builder.detector._supported_args = {"input", "output", "model"}

        # Build command with frame interpolation parameters
        cmd = builder.build_command(
            input_frame1=pathlib.Path("/frame1.png"),
            input_frame2=pathlib.Path("/frame2.png"),
            output_path=pathlib.Path("/output.png"),
            options={
                "model_path": pathlib.Path("/model"),
                "num_frames": 1,
            },
        )

        # Check basic command structure
        assert str(exe_path) in cmd
        assert "-0" in cmd
        assert "/frame1.png" in cmd
        assert "-1" in cmd
        assert "/frame2.png" in cmd
        assert "-o" in cmd
        assert "/output.png" in cmd
        # Model path is not added because model_path capability is False
        assert "-m" not in cmd

    def test_build_command_with_capabilities(self):
        """Test building command with optional features enabled."""
        exe_path = pathlib.Path("/path/to/rife")

        with patch("pathlib.Path.exists", return_value=True):
            with patch.object(RifeCapabilityDetector, "_detect_capabilities"):
                builder = RifeCommandBuilder(exe_path)
                builder.detector._capabilities = {
                    "uhd": True,
                    "tiling": True,
                    "tta_spatial": True,
                    "thread_spec": True,
                    "model_path": True,
                }
                builder.detector._supported_args = {
                    "input",
                    "output",
                    "model",
                    "uhd",
                    "tile",
                    "tile-size",
                    "tta-spatial",
                    "thread-spec",
                }

        cmd = builder.build_command(
            input_frame1=pathlib.Path("/frame1.png"),
            input_frame2=pathlib.Path("/frame2.png"),
            output_path=pathlib.Path("/output.png"),
            options={
                "model_path": pathlib.Path("/model"),
                "uhd_mode": True,
                "tile_enable": True,
                "tile_size": 512,
                "tta_spatial": True,
                "thread_spec": "2:4:2",
            },
        )

        assert "-u" in cmd  # UHD mode
        assert "-t" in cmd  # Tiling
        assert "512" in cmd  # Tile size
        assert "-x" in cmd  # TTA spatial
        assert "-j" in cmd  # Thread spec
        assert "2:4:2" in cmd
        assert "-m" in cmd  # Model path
        assert "/model" in cmd

    def test_build_command_ignores_unsupported(self):
        """Test that unsupported options are ignored in command."""
        exe_path = pathlib.Path("/path/to/rife")

        with patch("pathlib.Path.exists", return_value=True):
            with patch.object(RifeCapabilityDetector, "_detect_capabilities"):
                builder = RifeCommandBuilder(exe_path)
                builder.detector._capabilities = {"uhd": True}
                builder.detector._supported_args = {"input", "output", "model", "uhd"}

        cmd = builder.build_command(
            input_frame1=pathlib.Path("/frame1.png"),
            input_frame2=pathlib.Path("/frame2.png"),
            output_path=pathlib.Path("/output.png"),
            options={
                "uhd_mode": True,
                "tile_enable": True,  # Not supported
                "tta_spatial": True,  # Not supported
            },
        )

        assert "-u" in cmd  # UHD is supported
        assert "-t" not in cmd  # Tiling not supported
        assert "-x" not in cmd  # TTA spatial not supported


class TestAnalyzeRifeExecutable:
    """Tests for the analyze_rife_executable function."""

    @patch("goesvfi.utils.rife_analyzer.RifeCapabilityDetector")
    @patch("pathlib.Path.exists")
    def test_analyze_successful(self, mock_exists, mock_detector_class):
        """Test successful analysis of RIFE executable."""
        exe_path = pathlib.Path("/path/to/rife")

        # Mock the exists method to return True
        mock_exists.return_value = True

        # Mock detector instance
        mock_detector = Mock()
        mock_detector.version = "4.6"
        mock_detector.supports_tiling.return_value = True
        mock_detector.supports_uhd.return_value = True
        mock_detector.supports_tta_spatial.return_value = False
        mock_detector.supports_tta_temporal.return_value = False
        mock_detector.supports_thread_spec.return_value = True
        mock_detector.supports_batch_processing.return_value = True
        mock_detector.supports_timestep.return_value = False
        mock_detector.supports_model_path.return_value = True
        mock_detector.supports_gpu_id.return_value = False
        mock_detector.supported_args = {"-t", "-u", "--threads"}
        mock_detector.help_text = "RIFE help text"

        mock_detector_class.return_value = mock_detector

        result = analyze_rife_executable(exe_path)

        assert result["success"] is True
        assert result["exe_path"] == str(exe_path)
        assert result["version"] == "4.6"
        assert result["capabilities"]["tiling"] is True
        assert result["capabilities"]["uhd"] is True
        assert result["capabilities"]["tta_spatial"] is False
        assert len(result["capabilities"]) == 9

    def test_analyze_file_not_found(self):
        """Test analysis when executable doesn't exist."""
        exe_path = pathlib.Path("/nonexistent/rife")

        result = analyze_rife_executable(exe_path)

        assert result["success"] is False
        assert "not found" in result["error"]
        assert result["exe_path"] == str(exe_path)
        assert result["version"] is None
        assert result["capabilities"] == {}

    @patch("goesvfi.utils.rife_analyzer.RifeCapabilityDetector")
    def test_analyze_detection_error(self, mock_detector_class):
        """Test analysis when detection raises an error."""
        exe_path = pathlib.Path("/path/to/rife")

        # Make detector constructor raise an exception
        mock_detector_class.side_effect = Exception("Detection failed")

        with patch("pathlib.Path.exists", return_value=True):
            result = analyze_rife_executable(exe_path)

        assert result["success"] is False
        assert "Detection failed" in result["error"]
        assert result["capabilities"] == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
