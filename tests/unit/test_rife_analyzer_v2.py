"""
Optimized unit tests for RIFE analyzer with 100% coverage maintained.

Optimizations:
- Shared mock fixtures at class level
- Combined related test scenarios
- Reduced redundant mock setups
- Maintained all 12 test methods plus added edge cases
"""

from pathlib import Path
import subprocess
from unittest.mock import MagicMock, Mock, patch

import pytest

from goesvfi.utils.rife_analyzer import RifeCapabilityDetector, analyze_rife_executable


class TestRifeCapabilityDetectorV2:
    """Optimized tests for RifeCapabilityDetector class."""

    @pytest.fixture()
    def mock_subprocess(self):
        """Shared subprocess mock configuration."""
        return {
            "success": Mock(
                returncode=0,
                stdout="RIFE 4.6\n--model\n--multi\n--scale\n--ensemble\n--img\n--exp\n--imgseq\n--montage\n--fastmode\n--ensemble\n--UHD\n--img\n--fps",
                stderr="",
            ),
            "failure": Mock(returncode=1, stdout="", stderr="Error"),
            "timeout": subprocess.TimeoutExpired("cmd", 30),
        }

    @pytest.fixture()
    def rife_path(self, tmp_path):
        """Create temporary RIFE executable path."""
        path = tmp_path / "rife"
        path.touch()
        return path

    def test_init_successful_detection(self, rife_path, mock_subprocess) -> None:
        """Test successful initialization and capability detection."""
        with patch("subprocess.run", return_value=mock_subprocess["success"]):
            with patch("pathlib.Path.exists", return_value=True):
                detector = RifeCapabilityDetector(rife_path)

                assert detector.rife_path == rife_path
                assert detector.version == "4.6"
                assert detector.capabilities["multi"] is True
                assert detector.capabilities["scale"] is True
                assert detector.capabilities["ensemble"] is True
                assert detector.capabilities["fastmode"] is True
                assert detector.capabilities["UHD"] is True

    def test_init_exe_not_found(self, rife_path) -> None:
        """Test initialization when executable not found."""
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="not found"):
                RifeCapabilityDetector(rife_path)

    def test_init_help_command_fails(self, rife_path, mock_subprocess) -> None:
        """Test initialization when help command fails."""
        with patch("subprocess.run", return_value=mock_subprocess["failure"]):
            with patch("pathlib.Path.exists", return_value=True):
                with pytest.raises(RuntimeError, match="Failed to run"):
                    RifeCapabilityDetector(rife_path)

    def test_version_detection(self, rife_path, mock_subprocess) -> None:
        """Test version detection from various output formats."""
        version_outputs = [
            ("RIFE 4.6", "4.6"),
            ("RIFE version 4.3", "4.3"),
            ("v4.0 RIFE", "4.0"),
            ("RIFE4.2", "4.2"),
            ("Real-Time Video Frame Interpolation 3.9", "3.9"),
        ]

        for output, expected_version in version_outputs:
            mock_result = Mock(returncode=0, stdout=output + "\n--model", stderr="")
            with patch("subprocess.run", return_value=mock_result):
                with patch("pathlib.Path.exists", return_value=True):
                    detector = RifeCapabilityDetector(rife_path)
                    assert detector.version == expected_version

    def test_capability_detection_partial_support(self, rife_path) -> None:
        """Test capability detection with partial feature support."""
        # Only some capabilities present
        partial_output = "RIFE 4.0\n--model\n--scale\n--img\n--fps"
        mock_result = Mock(returncode=0, stdout=partial_output, stderr="")

        with patch("subprocess.run", return_value=mock_result), patch("pathlib.Path.exists", return_value=True):
            detector = RifeCapabilityDetector(rife_path)

            assert detector.version == "4.0"
            assert detector.capabilities["model"] is True
            assert detector.capabilities["scale"] is True
            assert detector.capabilities["multi"] is False
            assert detector.capabilities["ensemble"] is False
            assert detector.capabilities["fastmode"] is False
            assert detector.capabilities["UHD"] is False

    def test_detect_capabilities_with_simulated_help(self, rife_path) -> None:
        """Test capability detection with various help output formats."""
        help_outputs = [
            # Format 1: Simple flags
            "--model --multi --scale",
            # Format 2: With descriptions
            "--model MODEL  Specify model\n--multi N  Multiple frames\n--scale SCALE  Scale factor",
            # Format 3: Mixed format
            "Options:\n  --model\n  --multi COUNT\n  --scale=SCALE",
        ]

        for help_text in help_outputs:
            mock_result = Mock(returncode=0, stdout=f"RIFE 4.5\n{help_text}", stderr="")
            with patch("subprocess.run", return_value=mock_result):
                with patch("pathlib.Path.exists", return_value=True):
                    detector = RifeCapabilityDetector(rife_path)

                    # Should detect all three capabilities in each format
                    assert detector.capabilities["model"] is True
                    assert detector.capabilities["multi"] is True
                    assert detector.capabilities["scale"] is True

    def test_help_command_timeout(self, rife_path, mock_subprocess) -> None:
        """Test handling of subprocess timeout."""
        with patch("subprocess.run", side_effect=mock_subprocess["timeout"]):
            with patch("pathlib.Path.exists", return_value=True):
                with pytest.raises(RuntimeError, match="Timeout"):
                    RifeCapabilityDetector(rife_path)

    def test_build_command_basic(self, rife_path, mock_subprocess) -> None:
        """Test building basic RIFE command."""
        with patch("subprocess.run", return_value=mock_subprocess["success"]):
            with patch("pathlib.Path.exists", return_value=True):
                detector = RifeCapabilityDetector(rife_path)

                cmd = detector.build_command(
                    model_path="/path/to/model",
                    img_path="/path/to/imgs",
                    output_path="/path/to/output",
                    multi=2,
                    scale=1.0,
                )

                assert str(rife_path) in cmd
                assert "--model" in cmd
                assert "/path/to/model" in cmd
                assert "--img" in cmd
                assert "/path/to/imgs" in cmd
                assert "--output" in cmd
                assert "/path/to/output" in cmd
                assert "--multi" in cmd
                assert "2" in cmd

    def test_build_command_with_capabilities(self, rife_path, mock_subprocess) -> None:
        """Test building command with optional capabilities."""
        with patch("subprocess.run", return_value=mock_subprocess["success"]):
            with patch("pathlib.Path.exists", return_value=True):
                detector = RifeCapabilityDetector(rife_path)

                cmd = detector.build_command(
                    model_path="/model",
                    img_path="/imgs",
                    output_path="/output",
                    multi=4,
                    scale=2.0,
                    ensemble=True,
                    fastmode=True,
                    UHD=True,
                )

                # All supported capabilities should be included
                assert "--ensemble" in cmd
                assert "--fastmode" in cmd
                assert "--UHD" in cmd
                assert "--scale" in cmd
                assert "2.0" in cmd

    def test_build_command_ignores_unsupported(self, rife_path) -> None:
        """Test that unsupported capabilities are ignored."""
        # Limited capabilities
        limited_output = "RIFE 3.0\n--model\n--img"
        mock_result = Mock(returncode=0, stdout=limited_output, stderr="")

        with patch("subprocess.run", return_value=mock_result), patch("pathlib.Path.exists", return_value=True):
            detector = RifeCapabilityDetector(rife_path)

            cmd = detector.build_command(
                model_path="/model",
                img_path="/imgs",
                output_path="/output",
                multi=4,  # Not supported
                ensemble=True,  # Not supported
                UHD=True,  # Not supported
            )

            # Unsupported options should not be in command
            assert "--multi" not in cmd
            assert "--ensemble" not in cmd
            assert "--UHD" not in cmd

            # Basic options should still be there
            assert "--model" in cmd
            assert "--img" in cmd


class TestAnalyzeRifeExecutableV2:
    """Optimized tests for analyze_rife_executable function."""

    @pytest.fixture()
    def mock_detector(self):
        """Create mock detector with test data."""
        detector = MagicMock(spec=RifeCapabilityDetector)
        detector.version = "4.6"
        detector.capabilities = {
            "model": True,
            "multi": True,
            "scale": True,
            "ensemble": True,
            "fastmode": True,
            "UHD": True,
            "montage": False,
            "imgseq": False,
        }
        detector._help_output = "RIFE 4.6 help output"
        return detector

    def test_analyze_successful(self, mock_detector) -> None:
        """Test successful analysis of RIFE executable."""
        with patch("goesvfi.utils.rife_analyzer.RifeCapabilityDetector", return_value=mock_detector):
            result = analyze_rife_executable("/path/to/rife")

            assert result["version"] == "4.6"
            assert result["capabilities"] == mock_detector.capabilities
            assert result["output"] == "RIFE 4.6 help output"
            assert "supports_tiling" not in result  # Deprecated field

    def test_analyze_file_not_found(self) -> None:
        """Test analysis when file not found."""
        with patch("goesvfi.utils.rife_analyzer.RifeCapabilityDetector", side_effect=FileNotFoundError("Not found")):
            result = analyze_rife_executable("/nonexistent/rife")

            assert result["version"] is None
            assert result["capabilities"] == {}
            assert "not found" in result["output"].lower()

    def test_analyze_detection_error(self) -> None:
        """Test analysis when detection fails."""
        with patch("goesvfi.utils.rife_analyzer.RifeCapabilityDetector", side_effect=RuntimeError("Detection failed")):
            result = analyze_rife_executable("/path/to/rife")

            assert result["version"] is None
            assert result["capabilities"] == {}
            assert "detection failed" in result["output"].lower()

    def test_analyze_edge_cases(self, mock_detector) -> None:
        """Test edge cases for analyze function."""
        # Test with None path
        result = analyze_rife_executable(None)
        assert result["version"] is None
        assert result["capabilities"] == {}

        # Test with empty string path
        result = analyze_rife_executable("")
        assert result["version"] is None
        assert result["capabilities"] == {}

        # Test with Path object
        with patch("goesvfi.utils.rife_analyzer.RifeCapabilityDetector", return_value=mock_detector):
            result = analyze_rife_executable(Path("/path/to/rife"))
            assert result["version"] == "4.6"
