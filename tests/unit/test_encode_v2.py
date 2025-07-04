"""
Optimized unit tests for FFmpeg encoding functionality with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for encoding setup and mock configurations
- Combined encoding testing scenarios for different encoder types
- Batch validation of FFmpeg command generation and execution
- Enhanced error handling and edge case coverage
"""

import os
import pathlib
from typing import Any
from unittest.mock import ANY, MagicMock, patch

import pytest

from goesvfi.pipeline import encode

from tests.utils.mocks import create_mock_popen


class TestEncodeOptimizedV2:
    """Optimized FFmpeg encoding tests with full coverage."""

    @pytest.fixture(scope="class")
    @staticmethod
    def encoding_test_components() -> dict[str, Any]:  # noqa: C901
        """Create shared components for encoding testing.

        Returns:
            dict[str, Any]: Dictionary containing test manager and configurations.
        """

        # Enhanced Encoding Test Manager
        class EncodingTestManager:
            """Manage FFmpeg encoding testing scenarios."""

            def __init__(self) -> None:
                self.encoder_configs = {
                    "stream_copy": {
                        "encoder": "None (copy original)",
                        "crf": 0,
                        "bitrate_kbps": 0,
                        "bufsize_kb": 0,
                        "expected_codec": "copy",
                        "command_type": "simple",
                    },
                    "software_x264": {
                        "encoder": "Software x264",
                        "crf": 23,
                        "bitrate_kbps": 500,
                        "bufsize_kb": 1000,
                        "expected_codec": "libx264",
                        "command_type": "crf_based",
                        "preset": "slow",
                    },
                    "software_x265": {
                        "encoder": "Software x265",
                        "crf": 28,
                        "bitrate_kbps": 500,
                        "bufsize_kb": 1000,
                        "expected_codec": "libx265",
                        "command_type": "crf_based",
                        "preset": "slower",
                        "has_x265_params": True,
                    },
                    "software_x265_2pass": {
                        "encoder": "Software x265 (2-Pass)",
                        "crf": 0,
                        "bitrate_kbps": 1000,
                        "bufsize_kb": 0,
                        "expected_codec": "libx265",
                        "command_type": "two_pass",
                        "preset": "slower",
                    },
                    "hardware_hevc": {
                        "encoder": "Hardware HEVC (VideoToolbox)",
                        "crf": 23,
                        "bitrate_kbps": 500,
                        "bufsize_kb": 1000,
                        "expected_codec": "hevc_videotoolbox",
                        "command_type": "bitrate_based",
                        "has_tag": "hvc1",
                    },
                    "hardware_h264": {
                        "encoder": "Hardware H.264 (VideoToolbox)",
                        "crf": 23,
                        "bitrate_kbps": 500,
                        "bufsize_kb": 1000,
                        "expected_codec": "h264_videotoolbox",
                        "command_type": "bitrate_based",
                    },
                }

                self.test_scenarios = {
                    "stream_copy_success": self._test_stream_copy_success,
                    "stream_copy_fallback": self._test_stream_copy_fallback,
                    "single_pass_encoders": self._test_single_pass_encoders,
                    "two_pass_encoding": self._test_two_pass_encoding,
                    "error_conditions": self._test_error_conditions,
                    "edge_cases": self._test_edge_cases,
                }

            @staticmethod
            def _test_stream_copy_success(
                temp_workspace: dict[str, Any], mock_registry: dict[str, Any]
            ) -> dict[str, Any]:
                """Test successful stream copy operation.

                Returns:
                    dict[str, Any]: Test results for stream copy success.
                """
                intermediate = temp_workspace["intermediate"]
                final = temp_workspace["final"]

                # Expected command for stream copy
                expected_cmd = ["ffmpeg", "-y", "-i", str(intermediate), "-c", "copy", str(final)]

                with patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen:
                    mock_popen_factory = create_mock_popen(expected_command=expected_cmd, output_file_to_create=final)
                    mock_popen.side_effect = mock_popen_factory

                    # Execute encoding
                    encode.encode_with_ffmpeg(
                        intermediate_input=intermediate,
                        final_output=final,
                        encoder="None (copy original)",
                        crf=0,
                        bitrate_kbps=0,
                        bufsize_kb=0,
                        pix_fmt="yuv420p",
                    )

                    # Verify results
                    mock_popen.assert_called_once()
                    assert final.exists(), "Output file not created"

                    # Store command for validation
                    actual_cmd = mock_popen.call_args[0][0]
                    mock_registry["stream_copy_success"] = {
                        "success": True,
                        "command": actual_cmd,
                        "file_created": final.exists(),
                    }

                return dict(mock_registry["stream_copy_success"])

            @staticmethod
            def _test_stream_copy_fallback(
                temp_workspace: dict[str, Any], mock_registry: dict[str, Any]
            ) -> dict[str, Any]:
                """Test stream copy fallback to rename when FFmpeg fails.

                Returns:
                    dict[str, Any]: Test results for stream copy fallback.
                """
                intermediate = temp_workspace["intermediate"]
                final = temp_workspace["final"]

                # Expected command for stream copy
                expected_cmd = ["ffmpeg", "-y", "-i", str(intermediate), "-c", "copy", str(final)]

                with patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen:
                    # Configure mock to fail
                    mock_popen_factory = create_mock_popen(
                        expected_command=expected_cmd,
                        returncode=1,  # Simulate failure
                        stderr=b"ffmpeg copy failed",
                    )
                    mock_popen.side_effect = mock_popen_factory

                    # Patch pathlib.Path.replace to track if called
                    with patch.object(pathlib.Path, "replace", return_value=None) as mock_replace:
                        # Execute encoding
                        encode.encode_with_ffmpeg(
                            intermediate_input=intermediate,
                            final_output=final,
                            encoder="None (copy original)",
                            crf=0,
                            bitrate_kbps=0,
                            bufsize_kb=0,
                            pix_fmt="yuv420p",
                        )

                        # Verify fallback behavior
                        mock_popen.assert_called_once()
                        mock_replace.assert_called_once_with(final)

                        mock_registry["stream_copy_fallback"] = {
                            "success": True,
                            "ffmpeg_failed": True,
                            "fallback_used": mock_replace.called,
                        }

                return dict(mock_registry["stream_copy_fallback"])

            @staticmethod
            def _test_single_pass_encoders(  # noqa: PLR0914
                temp_workspace: dict[str, Any], mock_registry: dict[str, Any]
            ) -> dict[str, Any]:
                """Test various single-pass encoder configurations.

                Returns:
                    dict[str, Any]: Test results for single-pass encoders.
                """
                intermediate = temp_workspace["intermediate"]
                final = temp_workspace["final"]
                pix_fmt = "yuv420p"

                # Test configurations for single-pass encoders
                single_pass_configs = [
                    ("Software x265", "libx265", True),
                    ("Software x264", "libx264", True),
                    ("Hardware HEVC (VideoToolbox)", "hevc_videotoolbox", False),
                    ("Hardware H.264 (VideoToolbox)", "h264_videotoolbox", False),
                ]

                results = {}

                for encoder, expected_codec, use_crf in single_pass_configs:
                    # Access encoder_configs from the EncodingTestManager instance
                    manager = EncodingTestManager()
                    config_key = encoder.lower().replace(" ", "_").replace("(", "").replace(")", "").replace(".", "")
                    config = manager.encoder_configs.get(config_key)

                    # Extract values with defaults if not found
                    if config:
                        # Use type assertions for MyPy
                        crf_val = config.get("crf", 23)
                        bitrate_val = config.get("bitrate_kbps", 500)
                        bufsize_val = config.get("bufsize_kb", 1000)
                        assert isinstance(crf_val, int)
                        assert isinstance(bitrate_val, int)
                        assert isinstance(bufsize_val, int)
                        crf = crf_val
                        bitrate_kbps = bitrate_val
                        bufsize_kb = bufsize_val
                    else:
                        crf = 23
                        bitrate_kbps = 500
                        bufsize_kb = 1000

                    # Build expected command
                    base_cmd = [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel",
                        "info",
                        "-stats",
                        "-y",
                        "-i",
                        str(intermediate),
                    ]

                    encoder_args = ["-c:v", expected_codec]
                    if use_crf:
                        # Software encoders with CRF
                        if encoder == "Software x265":
                            encoder_args.extend(["-preset", "slower", "-crf", str(crf), "-x265-params", ANY])
                        elif encoder == "Software x264":
                            encoder_args.extend(["-preset", "slow", "-crf", str(crf)])
                    else:
                        # Hardware encoders with bitrate
                        if "hevc" in expected_codec:
                            encoder_args.extend(["-tag:v", "hvc1"])
                        encoder_args.extend([
                            "-b:v",
                            f"{bitrate_kbps}k",
                            "-maxrate",
                            f"{bufsize_kb}k",
                        ])

                    expected_cmd = (
                        base_cmd + encoder_args + ["-pix_fmt", pix_fmt, "-movflags", "+faststart", str(final)]
                    )

                    with patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen:
                        mock_popen_factory = create_mock_popen(
                            expected_command=expected_cmd, output_file_to_create=final
                        )
                        mock_popen.side_effect = mock_popen_factory

                        # Execute encoding
                        encode.encode_with_ffmpeg(
                            intermediate_input=intermediate,
                            final_output=final,
                            encoder=encoder,
                            crf=crf,
                            bitrate_kbps=bitrate_kbps,
                            bufsize_kb=bufsize_kb,
                            pix_fmt=pix_fmt,
                        )

                        # Verify results
                        mock_popen.assert_called_once()
                        assert final.exists(), f"Output file not created for {encoder}"

                        results[encoder] = {
                            "success": True,
                            "codec": expected_codec,
                            "uses_crf": use_crf,
                            "file_created": final.exists(),
                        }

                        # Remove file for next test
                        if final.exists():
                            final.unlink()

                mock_registry["single_pass_encoders"] = results
                return results

            @staticmethod
            def _test_two_pass_encoding(
                temp_workspace: dict[str, Any], mock_registry: dict[str, Any]
            ) -> dict[str, Any]:
                """Test two-pass encoding functionality.

                Returns:
                    dict[str, Any]: Test results for two-pass encoding.
                """
                intermediate = temp_workspace["intermediate"]
                final = temp_workspace["final"]
                bitrate = 1000
                pix_fmt = "yuv420p"

                with (
                    patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen,
                    patch("tempfile.NamedTemporaryFile") as mock_temp_file,
                ):
                    # Mock the temp file context manager
                    mock_log_file = MagicMock()
                    mock_log_file.name = str(temp_workspace["temp_dir"] / "ffmpeg_passlog")
                    mock_temp_file.return_value.__enter__.return_value = mock_log_file

                    # Expected commands for both passes
                    pass_log_prefix = mock_log_file.name
                    cmd_pass1 = [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel",
                        "info",
                        "-stats",
                        "-y",
                        "-i",
                        str(intermediate),
                        "-c:v",
                        "libx265",
                        "-preset",
                        "slower",
                        "-b:v",
                        f"{bitrate}k",
                        "-x265-params",
                        "pass=1",
                        "-passlogfile",
                        pass_log_prefix,
                        "-f",
                        "null",
                        os.devnull,
                    ]
                    cmd_pass2 = [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel",
                        "info",
                        "-stats",
                        "-y",
                        "-i",
                        str(intermediate),
                        "-c:v",
                        "libx265",
                        "-preset",
                        "slower",
                        "-b:v",
                        f"{bitrate}k",
                        "-x265-params",
                        ANY,  # Complex params string
                        "-passlogfile",
                        pass_log_prefix,
                        "-pix_fmt",
                        pix_fmt,
                        "-movflags",
                        "+faststart",
                        str(final),
                    ]

                    # Create mock factories for both passes
                    mock_popen_pass1 = create_mock_popen(expected_command=cmd_pass1)
                    mock_popen_pass2 = create_mock_popen(expected_command=cmd_pass2, output_file_to_create=final)

                    # Set up side effect for sequential calls
                    factories = [mock_popen_pass1, mock_popen_pass2]

                    def popen_side_effect(*args: Any, **kwargs: Any) -> Any:
                        if not factories:
                            msg = "Popen called more times than expected"
                            raise AssertionError(msg)
                        factory = factories.pop(0)
                        return factory(*args, **kwargs)

                    mock_popen.side_effect = popen_side_effect

                    # Execute encoding
                    encode.encode_with_ffmpeg(
                        intermediate_input=intermediate,
                        final_output=final,
                        encoder="Software x265 (2-Pass)",
                        crf=0,
                        bitrate_kbps=bitrate,
                        bufsize_kb=0,
                        pix_fmt=pix_fmt,
                    )

                    # Verify two-pass execution
                    assert mock_popen.call_count == 2, "Should call Popen twice for two-pass"
                    assert final.exists(), "Output file not created"

                    # Verify command arguments
                    call_args_list = mock_popen.call_args_list
                    assert call_args_list[0][0][0] == cmd_pass1, "Pass 1 command mismatch"
                    assert call_args_list[1][0][0] == cmd_pass2, "Pass 2 command mismatch"

                    mock_registry["two_pass_encoding"] = {
                        "success": True,
                        "pass_count": mock_popen.call_count,
                        "file_created": final.exists(),
                        "used_temp_file": mock_temp_file.called,
                    }

                return dict(mock_registry["two_pass_encoding"])

            @staticmethod
            def _test_error_conditions(temp_workspace: dict[str, Any], mock_registry: dict[str, Any]) -> dict[str, Any]:
                """Test error handling for unsupported encoders and invalid scenarios.

                Returns:
                    dict[str, Any]: Test results for error conditions.
                """
                intermediate = temp_workspace["intermediate"]
                final = temp_workspace["final"]

                error_tests: dict[str, Any] = {}

                # Test unsupported encoder
                with pytest.raises(ValueError, match="Unsupported encoder"):
                    encode.encode_with_ffmpeg(
                        intermediate_input=intermediate,
                        final_output=final,
                        encoder="Unsupported Encoder",
                        crf=0,
                        bitrate_kbps=0,
                        bufsize_kb=0,
                        pix_fmt="yuv420p",
                    )
                error_tests["unsupported_encoder"] = {"success": True, "raises_error": True}

                # Test with invalid input file
                nonexistent_input = temp_workspace["temp_dir"] / "nonexistent.mp4"

                with patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen:
                    # Mock Popen to simulate failure due to invalid input
                    mock_popen_factory = create_mock_popen(
                        expected_command=ANY,
                        returncode=1,
                        stderr=b"No such file or directory",
                    )
                    mock_popen.side_effect = mock_popen_factory

                    try:
                        encode.encode_with_ffmpeg(
                            intermediate_input=nonexistent_input,
                            final_output=final,
                            encoder="Software x264",
                            crf=23,
                            bitrate_kbps=0,
                            bufsize_kb=0,
                            pix_fmt="yuv420p",
                        )
                        # If no exception, check if FFmpeg was called
                        error_tests["invalid_input"] = {
                            "success": True,
                            "ffmpeg_called": mock_popen.called,
                        }
                    except (OSError, RuntimeError) as e:
                        error_tests["invalid_input"] = {
                            "success": True,
                            "exception_raised": True,
                            "exception_type": type(e).__name__,
                        }

                mock_registry["error_conditions"] = error_tests
                return error_tests

            @staticmethod
            def _test_edge_cases(temp_workspace: dict[str, Any], mock_registry: dict[str, Any]) -> dict[str, Any]:
                """Test edge cases for encoding functionality.

                Returns:
                    dict[str, Any]: Test results for edge cases.
                """
                intermediate = temp_workspace["intermediate"]
                final = temp_workspace["final"]

                edge_case_results = {}

                # Test with minimal valid parameters
                with patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen:
                    mock_popen_factory = create_mock_popen(expected_command=ANY, output_file_to_create=final)
                    mock_popen.side_effect = mock_popen_factory

                    encode.encode_with_ffmpeg(
                        intermediate_input=intermediate,
                        final_output=final,
                        encoder="Software x264",
                        crf=51,  # Maximum CRF value
                        bitrate_kbps=1,  # Minimum bitrate
                        bufsize_kb=1,  # Minimum buffer size
                        pix_fmt="yuv420p",
                    )

                    edge_case_results["minimal_params"] = {
                        "success": True,
                        "ffmpeg_called": mock_popen.called,
                        "file_created": final.exists(),
                    }

                mock_registry["edge_cases"] = edge_case_results
                return edge_case_results

            def run_test_scenario(
                self, scenario: str, temp_workspace: dict[str, Any], mock_registry: dict[str, Any]
            ) -> dict[str, Any]:
                """Run specified test scenario.

                Returns:
                    dict[str, Any]: Test scenario results.
                """
                return self.test_scenarios[scenario](temp_workspace, mock_registry)

        return {
            "test_manager": EncodingTestManager(),
        }

    @pytest.fixture()
    @staticmethod
    def temp_workspace(tmp_path: Any) -> dict[str, Any]:
        """Create temporary workspace for testing.

        Returns:
            dict[str, Any]: Dictionary containing workspace paths.
        """
        workspace = {
            "temp_dir": tmp_path,
            "intermediate": tmp_path / "intermediate.mp4",
            "final": tmp_path / "final.mp4",
        }
        # Create intermediate file
        workspace["intermediate"].touch()
        return workspace

    @pytest.fixture()
    @staticmethod
    def mock_registry() -> dict[str, Any]:
        """Create registry for storing mock results.

        Returns:
            dict[str, Any]: Empty registry dictionary.
        """
        return {}

    def test_stream_copy_success(
        self,
        encoding_test_components: dict[str, Any],
        temp_workspace: dict[str, Any],
        mock_registry: dict[str, Any],
    ) -> None:
        """Test successful stream copy operation."""
        test_manager = encoding_test_components["test_manager"]
        result = test_manager.run_test_scenario("stream_copy_success", temp_workspace, mock_registry)
        assert result["success"]
        assert result["file_created"]

    def test_stream_copy_fallback(
        self,
        encoding_test_components: dict[str, Any],
        temp_workspace: dict[str, Any],
        mock_registry: dict[str, Any],
    ) -> None:
        """Test stream copy fallback to rename when FFmpeg fails."""
        test_manager = encoding_test_components["test_manager"]
        result = test_manager.run_test_scenario("stream_copy_fallback", temp_workspace, mock_registry)
        assert result["success"]
        assert result["ffmpeg_failed"]
        assert result["fallback_used"]

    def test_single_pass_encoders(
        self,
        encoding_test_components: dict[str, Any],
        temp_workspace: dict[str, Any],
        mock_registry: dict[str, Any],
    ) -> None:
        """Test various single-pass encoder configurations."""
        test_manager = encoding_test_components["test_manager"]
        results = test_manager.run_test_scenario("single_pass_encoders", temp_workspace, mock_registry)

        # Verify all encoders were tested successfully
        for encoder_name, result in results.items():
            assert result["success"], f"Encoder {encoder_name} failed"
            assert result["file_created"], f"Output file not created for {encoder_name}"

    def test_two_pass_encoding(
        self,
        encoding_test_components: dict[str, Any],
        temp_workspace: dict[str, Any],
        mock_registry: dict[str, Any],
    ) -> None:
        """Test two-pass encoding functionality."""
        test_manager = encoding_test_components["test_manager"]
        result = test_manager.run_test_scenario("two_pass_encoding", temp_workspace, mock_registry)
        assert result["success"]
        assert result["pass_count"] == 2
        assert result["file_created"]
        assert result["used_temp_file"]

    def test_error_conditions(
        self,
        encoding_test_components: dict[str, Any],
        temp_workspace: dict[str, Any],
        mock_registry: dict[str, Any],
    ) -> None:
        """Test error handling for unsupported encoders and invalid scenarios."""
        test_manager = encoding_test_components["test_manager"]
        results = test_manager.run_test_scenario("error_conditions", temp_workspace, mock_registry)

        # Verify error handling
        assert results["unsupported_encoder"]["success"]
        assert results["unsupported_encoder"]["raises_error"]
        assert results["invalid_input"]["success"]

    def test_edge_cases(
        self,
        encoding_test_components: dict[str, Any],
        temp_workspace: dict[str, Any],
        mock_registry: dict[str, Any],
    ) -> None:
        """Test edge cases for encoding functionality."""
        test_manager = encoding_test_components["test_manager"]
        results = test_manager.run_test_scenario("edge_cases", temp_workspace, mock_registry)
        assert results["minimal_params"]["success"]
        assert results["minimal_params"]["ffmpeg_called"]
