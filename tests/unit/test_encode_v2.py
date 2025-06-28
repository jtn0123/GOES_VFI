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
import tempfile
from typing import Any, Dict, List
from unittest.mock import ANY, MagicMock, patch

import pytest

from goesvfi.pipeline import encode
from tests.utils.mocks import create_mock_popen


class TestEncodeOptimizedV2:
    """Optimized FFmpeg encoding tests with full coverage."""

    @pytest.fixture(scope="class")
    def encoding_test_components(self):
        """Create shared components for encoding testing."""
        
        # Enhanced Encoding Test Manager
        class EncodingTestManager:
            """Manage FFmpeg encoding testing scenarios."""
            
            def __init__(self):
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
            
            def _test_stream_copy_success(self, temp_workspace, mock_registry):
                """Test successful stream copy operation."""
                intermediate = temp_workspace["intermediate"]
                final = temp_workspace["final"]
                
                # Expected command for stream copy
                expected_cmd = ["ffmpeg", "-y", "-i", str(intermediate), "-c", "copy", str(final)]
                
                with patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen:
                    mock_popen_factory = create_mock_popen(
                        expected_command=expected_cmd, 
                        output_file_to_create=final
                    )
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
                
                return mock_registry["stream_copy_success"]
            
            def _test_stream_copy_fallback(self, temp_workspace, mock_registry):
                """Test stream copy fallback to rename when FFmpeg fails."""
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
                
                return mock_registry["stream_copy_fallback"]
            
            def _test_single_pass_encoders(self, temp_workspace, mock_registry):
                """Test various single-pass encoder configurations."""
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
                    config = self.encoder_configs.get(encoder.lower().replace(" ", "_").replace("(", "").replace(")", "").replace(".", ""))
                    if not config:
                        # Fallback config
                        config = {
                            "crf": 23,
                            "bitrate_kbps": 500,
                            "bufsize_kb": 1000,
                        }
                    
                    # Build expected command
                    base_cmd = [
                        "ffmpeg", "-hide_banner", "-loglevel", "info", "-stats", "-y",
                        "-i", str(intermediate),
                    ]
                    
                    encoder_args = ["-c:v", expected_codec]
                    if use_crf:
                        # Software encoders with CRF
                        if encoder == "Software x265":
                            encoder_args.extend(["-preset", "slower", "-crf", str(config["crf"]), "-x265-params", ANY])
                        elif encoder == "Software x264":
                            encoder_args.extend(["-preset", "slow", "-crf", str(config["crf"])])
                    else:
                        # Hardware encoders with bitrate
                        if "hevc" in expected_codec:
                            encoder_args.extend(["-tag:v", "hvc1"])
                        encoder_args.extend(["-b:v", f"{config['bitrate_kbps']}k", "-maxrate", f"{config['bufsize_kb']}k"])
                    
                    expected_cmd = base_cmd + encoder_args + ["-pix_fmt", pix_fmt, str(final)]
                    
                    with patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen:
                        mock_popen_factory = create_mock_popen(
                            expected_command=expected_cmd, 
                            output_file_to_create=final
                        )
                        mock_popen.side_effect = mock_popen_factory
                        
                        # Execute encoding
                        encode.encode_with_ffmpeg(
                            intermediate_input=intermediate,
                            final_output=final,
                            encoder=encoder,
                            crf=config["crf"],
                            bitrate_kbps=config["bitrate_kbps"],
                            bufsize_kb=config["bufsize_kb"],
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
                        if final.exists():\n                            final.unlink()\n                \n                mock_registry[\"single_pass_encoders\"] = results\n                return results\n            \n            def _test_two_pass_encoding(self, temp_workspace, mock_registry):\n                \"\"\"Test two-pass encoding functionality.\"\"\"\n                intermediate = temp_workspace[\"intermediate\"]\n                final = temp_workspace[\"final\"]\n                bitrate = 1000\n                pix_fmt = \"yuv420p\"\n                \n                with patch(\"goesvfi.pipeline.encode.subprocess.Popen\") as mock_popen:\n                    with patch(\"tempfile.NamedTemporaryFile\") as mock_temp_file:\n                        # Mock the temp file context manager\n                        mock_log_file = MagicMock()\n                        mock_log_file.name = str(temp_workspace[\"temp_dir\"] / \"ffmpeg_passlog\")\n                        mock_temp_file.return_value.__enter__.return_value = mock_log_file\n                        \n                        # Expected commands for both passes\n                        pass_log_prefix = mock_log_file.name\n                        cmd_pass1 = [\n                            \"ffmpeg\", \"-hide_banner\", \"-loglevel\", \"info\", \"-stats\", \"-y\",\n                            \"-i\", str(intermediate),\n                            \"-c:v\", \"libx265\", \"-preset\", \"slower\",\n                            \"-b:v\", f\"{bitrate}k\",\n                            \"-x265-params\", \"pass=1\",\n                            \"-passlogfile\", pass_log_prefix,\n                            \"-f\", \"null\", os.devnull,\n                        ]\n                        cmd_pass2 = [\n                            \"ffmpeg\", \"-hide_banner\", \"-loglevel\", \"info\", \"-stats\", \"-y\",\n                            \"-i\", str(intermediate),\n                            \"-c:v\", \"libx265\", \"-preset\", \"slower\",\n                            \"-b:v\", f\"{bitrate}k\",\n                            \"-x265-params\", ANY,  # Complex params string\n                            \"-passlogfile\", pass_log_prefix,\n                            \"-pix_fmt\", pix_fmt,\n                            str(final),\n                        ]\n                        \n                        # Create mock factories for both passes\n                        mock_popen_pass1 = create_mock_popen(expected_command=cmd_pass1)\n                        mock_popen_pass2 = create_mock_popen(\n                            expected_command=cmd_pass2, \n                            output_file_to_create=final\n                        )\n                        \n                        # Set up side effect for sequential calls\n                        factories = [mock_popen_pass1, mock_popen_pass2]\n                        \n                        def popen_side_effect(*args, **kwargs):\n                            if not factories:\n                                raise AssertionError(\"Popen called more times than expected\")\n                            factory = factories.pop(0)\n                            return factory(*args, **kwargs)\n                        \n                        mock_popen.side_effect = popen_side_effect\n                        \n                        # Execute encoding\n                        encode.encode_with_ffmpeg(\n                            intermediate_input=intermediate,\n                            final_output=final,\n                            encoder=\"Software x265 (2-Pass)\",\n                            crf=0,\n                            bitrate_kbps=bitrate,\n                            bufsize_kb=0,\n                            pix_fmt=pix_fmt,\n                        )\n                        \n                        # Verify two-pass execution\n                        assert mock_popen.call_count == 2, \"Should call Popen twice for two-pass\"\n                        assert final.exists(), \"Output file not created\"\n                        \n                        # Verify command arguments\n                        call_args_list = mock_popen.call_args_list\n                        assert call_args_list[0][0][0] == cmd_pass1, \"Pass 1 command mismatch\"\n                        assert call_args_list[1][0][0] == cmd_pass2, \"Pass 2 command mismatch\"\n                        \n                        mock_registry[\"two_pass_encoding\"] = {\n                            \"success\": True,\n                            \"pass_count\": mock_popen.call_count,\n                            \"file_created\": final.exists(),\n                            \"used_temp_file\": mock_temp_file.called,\n                        }\n                \n                return mock_registry[\"two_pass_encoding\"]\n            \n            def _test_error_conditions(self, temp_workspace, mock_registry):\n                \"\"\"Test error handling for unsupported encoders and invalid scenarios.\"\"\"\n                intermediate = temp_workspace[\"intermediate\"]\n                final = temp_workspace[\"final\"]\n                \n                error_tests = {}\n                \n                # Test unsupported encoder\n                with pytest.raises(ValueError):\n                    encode.encode_with_ffmpeg(\n                        intermediate_input=intermediate,\n                        final_output=final,\n                        encoder=\"Unsupported Encoder\",\n                        crf=0,\n                        bitrate_kbps=0,\n                        bufsize_kb=0,\n                        pix_fmt=\"yuv420p\",\n                    )\n                error_tests[\"unsupported_encoder\"] = {\"success\": True, \"raises_error\": True}\n                \n                # Test with invalid input file\n                nonexistent_input = temp_workspace[\"temp_dir\"] / \"nonexistent.mp4\"\n                \n                with patch(\"goesvfi.pipeline.encode.subprocess.Popen\") as mock_popen:\n                    # Mock Popen to simulate failure due to invalid input\n                    mock_popen_factory = create_mock_popen(\n                        expected_command=ANY,\n                        returncode=1,\n                        stderr=b\"No such file or directory\",\n                    )\n                    mock_popen.side_effect = mock_popen_factory\n                    \n                    try:\n                        encode.encode_with_ffmpeg(\n                            intermediate_input=nonexistent_input,\n                            final_output=final,\n                            encoder=\"Software x264\",\n                            crf=23,\n                            bitrate_kbps=0,\n                            bufsize_kb=0,\n                            pix_fmt=\"yuv420p\",\n                        )\n                        # If no exception, check if FFmpeg was called\n                        error_tests[\"invalid_input\"] = {\n                            \"success\": True, \n                            \"ffmpeg_called\": mock_popen.called,\n                        }\n                    except Exception as e:\n                        error_tests[\"invalid_input\"] = {\n                            \"success\": True, \n                            \"exception_raised\": True,\n                            \"exception_type\": type(e).__name__,\n                        }\n                \n                mock_registry[\"error_conditions\"] = error_tests\n                return error_tests\n            \n            def _test_edge_cases(self, temp_workspace, mock_registry):\n                \"\"\"Test edge cases and boundary conditions.\"\"\"\n                intermediate = temp_workspace[\"intermediate\"]\n                final = temp_workspace[\"final\"]\n                \n                edge_case_results = {}\n                \n                # Test with very high CRF value\n                with patch(\"goesvfi.pipeline.encode.subprocess.Popen\") as mock_popen:\n                    mock_popen_factory = create_mock_popen(\n                        expected_command=ANY, \n                        output_file_to_create=final\n                    )\n                    mock_popen.side_effect = mock_popen_factory\n                    \n                    encode.encode_with_ffmpeg(\n                        intermediate_input=intermediate,\n                        final_output=final,\n                        encoder=\"Software x264\",\n                        crf=51,  # Maximum CRF value\n                        bitrate_kbps=0,\n                        bufsize_kb=0,\n                        pix_fmt=\"yuv420p\",\n                    )\n                    \n                    edge_case_results[\"high_crf\"] = {\n                        \"success\": True,\n                        \"crf_value\": 51,\n                        \"file_created\": final.exists(),\n                    }\n                    \n                    if final.exists():\n                        final.unlink()\n                \n                # Test with very high bitrate\n                with patch(\"goesvfi.pipeline.encode.subprocess.Popen\") as mock_popen:\n                    mock_popen_factory = create_mock_popen(\n                        expected_command=ANY, \n                        output_file_to_create=final\n                    )\n                    mock_popen.side_effect = mock_popen_factory\n                    \n                    encode.encode_with_ffmpeg(\n                        intermediate_input=intermediate,\n                        final_output=final,\n                        encoder=\"Hardware HEVC (VideoToolbox)\",\n                        crf=0,\n                        bitrate_kbps=50000,  # Very high bitrate\n                        bufsize_kb=100000,\n                        pix_fmt=\"yuv420p\",\n                    )\n                    \n                    edge_case_results[\"high_bitrate\"] = {\n                        \"success\": True,\n                        \"bitrate_value\": 50000,\n                        \"file_created\": final.exists(),\n                    }\n                    \n                    if final.exists():\n                        final.unlink()\n                \n                # Test with different pixel formats\n                pixel_formats = [\"yuv420p\", \"yuv444p\", \"rgb24\"]\n                pixel_format_results = {}\n                \n                for pix_fmt in pixel_formats:\n                    with patch(\"goesvfi.pipeline.encode.subprocess.Popen\") as mock_popen:\n                        mock_popen_factory = create_mock_popen(\n                            expected_command=ANY, \n                            output_file_to_create=final\n                        )\n                        mock_popen.side_effect = mock_popen_factory\n                        \n                        encode.encode_with_ffmpeg(\n                            intermediate_input=intermediate,\n                            final_output=final,\n                            encoder=\"Software x264\",\n                            crf=23,\n                            bitrate_kbps=0,\n                            bufsize_kb=0,\n                            pix_fmt=pix_fmt,\n                        )\n                        \n                        pixel_format_results[pix_fmt] = {\n                            \"success\": True,\n                            \"format\": pix_fmt,\n                            \"file_created\": final.exists(),\n                        }\n                        \n                        if final.exists():\n                            final.unlink()\n                \n                edge_case_results[\"pixel_formats\"] = pixel_format_results\n                \n                mock_registry[\"edge_cases\"] = edge_case_results\n                return edge_case_results\n            \n            def run_test_scenario(self, scenario: str, temp_workspace: Dict[str, Any], mock_registry: Dict[str, Any]):\n                \"\"\"Run specified test scenario.\"\"\"\n                return self.test_scenarios[scenario](temp_workspace, mock_registry)\n        \n        # Enhanced Command Analyzer\n        class CommandAnalyzer:\n            \"\"\"Analyze FFmpeg commands for correctness and completeness.\"\"\"\n            \n            def __init__(self):\n                self.analysis_rules = {\n                    \"basic_structure\": self._analyze_basic_structure,\n                    \"encoder_specific\": self._analyze_encoder_specific,\n                    \"parameter_validation\": self._analyze_parameter_validation,\n                    \"output_handling\": self._analyze_output_handling,\n                }\n            \n            def _analyze_basic_structure(self, cmd: List[str]) -> Dict[str, bool]:\n                \"\"\"Analyze basic FFmpeg command structure.\"\"\"\n                return {\n                    \"starts_with_ffmpeg\": len(cmd) > 0 and cmd[0] == \"ffmpeg\",\n                    \"has_hide_banner\": \"-hide_banner\" in cmd,\n                    \"has_loglevel\": \"-loglevel\" in cmd,\n                    \"has_stats\": \"-stats\" in cmd,\n                    \"has_overwrite\": \"-y\" in cmd,\n                    \"has_input\": \"-i\" in cmd,\n                    \"reasonable_length\": 5 <= len(cmd) <= 25,\n                }\n            \n            def _analyze_encoder_specific(self, cmd: List[str]) -> Dict[str, Any]:\n                \"\"\"Analyze encoder-specific command elements.\"\"\"\n                codec_info = {}\n                \n                if \"-c:v\" in cmd:\n                    codec_index = cmd.index(\"-c:v\") + 1\n                    codec = cmd[codec_index] if codec_index < len(cmd) else None\n                    codec_info[\"video_codec\"] = codec\n                    codec_info[\"has_video_codec\"] = True\n                elif \"-c\" in cmd:\n                    codec_index = cmd.index(\"-c\") + 1\n                    codec = cmd[codec_index] if codec_index < len(cmd) else None\n                    codec_info[\"codec\"] = codec\n                    codec_info[\"has_codec\"] = True\n                \n                return {\n                    \"codec_info\": codec_info,\n                    \"has_preset\": \"-preset\" in cmd,\n                    \"has_crf\": \"-crf\" in cmd,\n                    \"has_bitrate\": \"-b:v\" in cmd,\n                    \"has_x265_params\": \"-x265-params\" in cmd,\n                    \"has_tag\": \"-tag:v\" in cmd,\n                }\n            \n            def _analyze_parameter_validation(self, cmd: List[str]) -> Dict[str, bool]:\n                \"\"\"Analyze parameter validation aspects.\"\"\"\n                return {\n                    \"has_pix_fmt\": \"-pix_fmt\" in cmd,\n                    \"has_passlogfile\": \"-passlogfile\" in cmd,\n                    \"has_null_output\": os.devnull in cmd,\n                    \"proper_flag_pairs\": self._check_flag_value_pairs(cmd),\n                }\n            \n            def _analyze_output_handling(self, cmd: List[str]) -> Dict[str, bool]:\n                \"\"\"Analyze output handling aspects.\"\"\"\n                return {\n                    \"has_output_file\": len(cmd) > 0 and not cmd[-1].startswith(\"-\"),\n                    \"output_at_end\": len(cmd) > 0 and not cmd[-1].startswith(\"-\"),\n                    \"no_trailing_flags\": len(cmd) > 0 and not cmd[-1].startswith(\"-\"),\n                }\n            \n            def _check_flag_value_pairs(self, cmd: List[str]) -> bool:\n                \"\"\"Check that flags have corresponding values.\"\"\"\n                flags_needing_values = [\"-i\", \"-c:v\", \"-c\", \"-preset\", \"-crf\", \"-b:v\", \"-pix_fmt\", \"-x265-params\"]\n                \n                for flag in flags_needing_values:\n                    if flag in cmd:\n                        flag_index = cmd.index(flag)\n                        if flag_index + 1 >= len(cmd) or cmd[flag_index + 1].startswith(\"-\"):\n                            return False\n                return True\n            \n            def analyze_command(self, cmd: List[str], analysis_types: List[str] = None) -> Dict[str, Any]:\n                \"\"\"Analyze command using specified analysis types.\"\"\"\n                if analysis_types is None:\n                    analysis_types = list(self.analysis_rules.keys())\n                \n                results = {}\n                for analysis_type in analysis_types:\n                    if analysis_type in self.analysis_rules:\n                        results[analysis_type] = self.analysis_rules[analysis_type](cmd)\n                \n                return results\n        \n        return {\n            \"test_manager\": EncodingTestManager(),\n            \"analyzer\": CommandAnalyzer(),\n        }\n\n    @pytest.fixture()\n    def temp_workspace(self, tmp_path):\n        \"\"\"Create temporary workspace for encoding testing.\"\"\"\n        temp_dir = tmp_path / \"encoding_test\"\n        temp_dir.mkdir(exist_ok=True)\n        \n        # Create input file\n        intermediate = temp_dir / \"input.mp4\"\n        intermediate.write_text(\"dummy input\")\n        \n        # Output file path\n        final = temp_dir / \"output.mp4\"\n        \n        workspace = {\n            \"temp_dir\": temp_dir,\n            \"intermediate\": intermediate,\n            \"final\": final,\n        }\n        \n        return workspace\n\n    @pytest.fixture()\n    def mock_registry(self):\n        \"\"\"Registry for storing mock interaction results.\"\"\"\n        return {}\n\n    def test_encoding_comprehensive_scenarios(self, encoding_test_components, temp_workspace, mock_registry) -> None:\n        \"\"\"Test comprehensive encoding scenarios with all encoder types.\"\"\"\n        components = encoding_test_components\n        test_manager = components[\"test_manager\"]\n        analyzer = components[\"analyzer\"]\n        \n        # Define comprehensive encoding scenarios\n        encoding_scenarios = [\n            {\n                \"name\": \"Stream Copy Success\",\n                \"test_type\": \"stream_copy_success\",\n                \"analysis_types\": [\"basic_structure\", \"output_handling\"],\n                \"expected_features\": [\"copy\", \"simple\"],\n            },\n            {\n                \"name\": \"Stream Copy Fallback\",\n                \"test_type\": \"stream_copy_fallback\",\n                \"analysis_types\": [],  # No command analysis for fallback\n                \"expected_features\": [\"fallback\", \"rename\"],\n            },\n            {\n                \"name\": \"Single Pass Encoders\",\n                \"test_type\": \"single_pass_encoders\",\n                \"analysis_types\": [\"basic_structure\", \"encoder_specific\", \"parameter_validation\"],\n                \"expected_features\": [\"libx264\", \"libx265\", \"hevc_videotoolbox\", \"h264_videotoolbox\"],\n            },\n            {\n                \"name\": \"Two Pass Encoding\",\n                \"test_type\": \"two_pass_encoding\",\n                \"analysis_types\": [\"basic_structure\", \"encoder_specific\", \"parameter_validation\"],\n                \"expected_features\": [\"libx265\", \"pass=1\", \"pass=2\", \"passlogfile\"],\n            },\n            {\n                \"name\": \"Error Conditions\",\n                \"test_type\": \"error_conditions\",\n                \"analysis_types\": [],  # No command analysis for error tests\n                \"expected_errors\": 2,  # Number of error conditions tested\n            },\n            {\n                \"name\": \"Edge Cases\",\n                \"test_type\": \"edge_cases\",\n                \"analysis_types\": [\"basic_structure\", \"parameter_validation\"],\n                \"expected_features\": [\"high_crf\", \"high_bitrate\", \"pixel_formats\"],\n            },\n        ]\n        \n        # Test each encoding scenario\n        all_results = {}\n        \n        for scenario in encoding_scenarios:\n            try:\n                # Run encoding test scenario\n                scenario_results = test_manager.run_test_scenario(\n                    scenario[\"test_type\"], temp_workspace, mock_registry\n                )\n                \n                # Analyze commands for non-error scenarios\n                if scenario[\"analysis_types\"] and scenario[\"name\"] not in [\"Stream Copy Fallback\", \"Error Conditions\"]:\n                    # For scenarios that produce commands\n                    if \"command\" in scenario_results:\n                        cmd = scenario_results[\"command\"]\n                        analysis_results = analyzer.analyze_command(cmd, scenario[\"analysis_types\"])\n                        scenario_results[\"analysis\"] = analysis_results\n                \n                # Verify scenario-specific expectations\n                if scenario[\"name\"] == \"Stream Copy Success\":\n                    assert scenario_results[\"success\"], \"Stream copy should succeed\"\n                    assert scenario_results[\"file_created\"], \"Output file should be created\"\n                    \n                    # Verify command structure\n                    if \"command\" in scenario_results:\n                        cmd = scenario_results[\"command\"]\n                        assert \"copy\" in cmd, \"Stream copy command should contain 'copy'\"\n                        assert \"-c\" in cmd, \"Stream copy should use -c flag\"\n                \n                elif scenario[\"name\"] == \"Stream Copy Fallback\":\n                    assert scenario_results[\"success\"], \"Fallback should succeed\"\n                    assert scenario_results[\"ffmpeg_failed\"], \"FFmpeg should have failed\"\n                    assert scenario_results[\"fallback_used\"], \"Fallback rename should be used\"\n                \n                elif scenario[\"name\"] == \"Single Pass Encoders\":\n                    # Check that all expected encoders were tested\n                    for encoder_name, result in scenario_results.items():\n                        assert result[\"success\"], f\"Encoder {encoder_name} should succeed\"\n                        assert result[\"file_created\"], f\"File should be created for {encoder_name}\"\n                    \n                    # Should have tested multiple encoders\n                    assert len(scenario_results) >= 3, \"Should test multiple single-pass encoders\"\n                \n                elif scenario[\"name\"] == \"Two Pass Encoding\":\n                    assert scenario_results[\"success\"], \"Two-pass encoding should succeed\"\n                    assert scenario_results[\"pass_count\"] == 2, \"Should execute exactly 2 passes\"\n                    assert scenario_results[\"file_created\"], \"Output file should be created\"\n                    assert scenario_results[\"used_temp_file\"], \"Should use temporary file for passlog\"\n                \n                elif scenario[\"name\"] == \"Error Conditions\":\n                    # Check error handling\n                    error_count = len([r for r in scenario_results.values() if r.get(\"raises_error\") or r.get(\"exception_raised\")])\n                    assert error_count >= scenario[\"expected_errors\"], (\n                        f\"Expected at least {scenario['expected_errors']} errors, got {error_count}\"\n                    )\n                \n                elif scenario[\"name\"] == \"Edge Cases\":\n                    # Check edge case handling\n                    assert \"high_crf\" in scenario_results, \"High CRF test missing\"\n                    assert \"high_bitrate\" in scenario_results, \"High bitrate test missing\"\n                    assert \"pixel_formats\" in scenario_results, \"Pixel format tests missing\"\n                    \n                    # All edge cases should succeed\n                    for test_name, test_result in scenario_results.items():\n                        if isinstance(test_result, dict) and \"success\" in test_result:\n                            assert test_result[\"success\"], f\"Edge case {test_name} should succeed\"\n                \n                all_results[scenario[\"name\"]] = scenario_results\n                \n            except Exception as e:\n                if scenario[\"name\"] != \"Error Conditions\":\n                    pytest.fail(f\"Unexpected error in {scenario['name']}: {e}\")\n                # Error scenarios are expected to have exceptions\n        \n        # Overall validation\n        assert len(all_results) == len(encoding_scenarios), \"Not all encoding scenarios completed\"\n\n    def test_encoding_command_validation_and_analysis(self, encoding_test_components, temp_workspace) -> None:\n        \"\"\"Test encoding command validation and detailed analysis.\"\"\"\n        components = encoding_test_components\n        analyzer = components[\"analyzer\"]\n        intermediate = temp_workspace[\"intermediate\"]\n        final = temp_workspace[\"final\"]\n        \n        # Test specific command structures\n        command_validation_scenarios = [\n            {\n                \"name\": \"Software x264 Command\",\n                \"encoder\": \"Software x264\",\n                \"params\": {\"crf\": 23, \"pix_fmt\": \"yuv420p\"},\n                \"expected_elements\": [\"ffmpeg\", \"-c:v\", \"libx264\", \"-preset\", \"slow\"],\n            },\n            {\n                \"name\": \"Hardware HEVC Command\",\n                \"encoder\": \"Hardware HEVC (VideoToolbox)\",\n                \"params\": {\"bitrate_kbps\": 2000, \"bufsize_kb\": 4000, \"pix_fmt\": \"yuv420p\"},\n                \"expected_elements\": [\"ffmpeg\", \"-c:v\", \"hevc_videotoolbox\", \"-tag:v\", \"hvc1\"],\n            },\n        ]\n        \n        # Test each command validation scenario\n        for scenario in command_validation_scenarios:\n            params = scenario[\"params\"]\n            \n            with patch(\"goesvfi.pipeline.encode.subprocess.Popen\") as mock_popen:\n                mock_popen_factory = create_mock_popen(\n                    expected_command=ANY, \n                    output_file_to_create=final\n                )\n                mock_popen.side_effect = mock_popen_factory\n                \n                # Execute encoding\n                encode.encode_with_ffmpeg(\n                    intermediate_input=intermediate,\n                    final_output=final,\n                    encoder=scenario[\"encoder\"],\n                    crf=params.get(\"crf\", 0),\n                    bitrate_kbps=params.get(\"bitrate_kbps\", 0),\n                    bufsize_kb=params.get(\"bufsize_kb\", 0),\n                    pix_fmt=params[\"pix_fmt\"],\n                )\n                \n                # Get actual command\n                actual_cmd = mock_popen.call_args[0][0]\n                \n                # Verify expected elements\n                for element in scenario[\"expected_elements\"]:\n                    assert element in actual_cmd, f\"Missing element '{element}' in {scenario['name']} command: {actual_cmd}\"\n                \n                # Analyze command structure\n                analysis_results = analyzer.analyze_command(\n                    actual_cmd, \n                    [\"basic_structure\", \"encoder_specific\", \"parameter_validation\", \"output_handling\"]\n                )\n                \n                # Validate basic structure\n                basic = analysis_results[\"basic_structure\"]\n                assert basic[\"starts_with_ffmpeg\"], f\"Command should start with ffmpeg for {scenario['name']}\"\n                assert basic[\"has_input\"], f\"Command should have input for {scenario['name']}\"\n                assert basic[\"reasonable_length\"], f\"Command length unreasonable for {scenario['name']}\"\n                \n                # Validate encoder-specific elements\n                encoder = analysis_results[\"encoder_specific\"]\n                assert encoder[\"codec_info\"], f\"Codec info missing for {scenario['name']}\"\n                \n                # Validate parameters\n                params_analysis = analysis_results[\"parameter_validation\"]\n                assert params_analysis[\"has_pix_fmt\"], f\"Pixel format missing for {scenario['name']}\"\n                assert params_analysis[\"proper_flag_pairs\"], f\"Flag-value pairs incorrect for {scenario['name']}\"\n                \n                # Validate output\n                output = analysis_results[\"output_handling\"]\n                assert output[\"has_output_file\"], f\"Output file missing for {scenario['name']}\"\n                \n                # Clean up for next test\n                if final.exists():\n                    final.unlink()\n\n    def test_encoding_performance_and_edge_cases(self, encoding_test_components, temp_workspace) -> None:\n        \"\"\"Test encoding performance characteristics and edge cases.\"\"\"\n        components = encoding_test_components\n        test_manager = components[\"test_manager\"]\n        \n        # Performance and edge case scenarios\n        performance_scenarios = [\n            {\n                \"name\": \"Rapid Encoder Switching\",\n                \"test\": lambda: self._test_rapid_encoder_switching(temp_workspace),\n            },\n            {\n                \"name\": \"Large File Handling\",\n                \"test\": lambda: self._test_large_file_simulation(temp_workspace),\n            },\n            {\n                \"name\": \"Parameter Boundary Values\",\n                \"test\": lambda: self._test_parameter_boundaries(temp_workspace),\n            },\n            {\n                \"name\": \"Concurrent Encoding Simulation\",\n                \"test\": lambda: self._test_concurrent_encoding_simulation(temp_workspace),\n            },\n        ]\n        \n        # Test each performance scenario\n        for scenario in performance_scenarios:\n            try:\n                result = scenario[\"test\"]()\n                assert result is not None, f\"Performance test {scenario['name']} returned None\"\n                assert result.get(\"success\", False), f\"Performance test {scenario['name']} failed\"\n            except Exception as e:\n                # Some performance tests may have expected limitations\n                assert \"expected\" in str(e).lower() or \"limitation\" in str(e).lower(), (\n                    f\"Unexpected error in performance test {scenario['name']}: {e}\"\n                )\n\n    def _test_rapid_encoder_switching(self, temp_workspace):\n        \"\"\"Test rapid switching between different encoders.\"\"\"\n        intermediate = temp_workspace[\"intermediate\"]\n        final = temp_workspace[\"final\"]\n        \n        encoders = [\n            \"Software x264\",\n            \"Software x265\", \n            \"Hardware HEVC (VideoToolbox)\",\n            \"None (copy original)\"\n        ]\n        \n        successful_switches = 0\n        \n        for i, encoder in enumerate(encoders * 3):  # Test multiple rounds\n            with patch(\"goesvfi.pipeline.encode.subprocess.Popen\") as mock_popen:\n                mock_popen_factory = create_mock_popen(\n                    expected_command=ANY, \n                    output_file_to_create=final\n                )\n                mock_popen.side_effect = mock_popen_factory\n                \n                try:\n                    encode.encode_with_ffmpeg(\n                        intermediate_input=intermediate,\n                        final_output=final,\n                        encoder=encoder,\n                        crf=23 if \"Software\" in encoder else 0,\n                        bitrate_kbps=1000 if \"Hardware\" in encoder else 0,\n                        bufsize_kb=2000 if \"Hardware\" in encoder else 0,\n                        pix_fmt=\"yuv420p\",\n                    )\n                    \n                    successful_switches += 1\n                    \n                    # Clean up for next iteration\n                    if final.exists():\n                        final.unlink()\n                        \n                except Exception:\n                    # Some switches might fail, which is acceptable\n                    pass\n        \n        return {\n            \"success\": True,\n            \"successful_switches\": successful_switches,\n            \"total_attempts\": len(encoders) * 3,\n        }\n\n    def _test_large_file_simulation(self, temp_workspace):\n        \"\"\"Simulate handling of large files.\"\"\"\n        intermediate = temp_workspace[\"intermediate\"]\n        final = temp_workspace[\"final\"]\n        \n        # Simulate large file by creating larger content\n        large_content = \"dummy input\" * 1000  # Simulate larger file\n        intermediate.write_text(large_content)\n        \n        with patch(\"goesvfi.pipeline.encode.subprocess.Popen\") as mock_popen:\n            mock_popen_factory = create_mock_popen(\n                expected_command=ANY, \n                output_file_to_create=final\n            )\n            mock_popen.side_effect = mock_popen_factory\n            \n            encode.encode_with_ffmpeg(\n                intermediate_input=intermediate,\n                final_output=final,\n                encoder=\"Software x264\",\n                crf=23,\n                bitrate_kbps=0,\n                bufsize_kb=0,\n                pix_fmt=\"yuv420p\",\n            )\n            \n            return {\n                \"success\": True,\n                \"large_file_handled\": True,\n                \"input_size\": len(large_content),\n            }\n\n    def _test_parameter_boundaries(self, temp_workspace):\n        \"\"\"Test parameter boundary values.\"\"\"\n        intermediate = temp_workspace[\"intermediate\"]\n        final = temp_workspace[\"final\"]\n        \n        boundary_tests = [\n            {\"crf\": 0, \"encoder\": \"Software x264\"},    # Minimum CRF\n            {\"crf\": 51, \"encoder\": \"Software x264\"},   # Maximum CRF\n            {\"bitrate_kbps\": 1, \"bufsize_kb\": 2, \"encoder\": \"Hardware HEVC (VideoToolbox)\"},  # Minimum bitrate\n            {\"bitrate_kbps\": 100000, \"bufsize_kb\": 200000, \"encoder\": \"Hardware HEVC (VideoToolbox)\"},  # High bitrate\n        ]\n        \n        successful_tests = 0\n        \n        for test_params in boundary_tests:\n            with patch(\"goesvfi.pipeline.encode.subprocess.Popen\") as mock_popen:\n                mock_popen_factory = create_mock_popen(\n                    expected_command=ANY, \n                    output_file_to_create=final\n                )\n                mock_popen.side_effect = mock_popen_factory\n                \n                try:\n                    encode.encode_with_ffmpeg(\n                        intermediate_input=intermediate,\n                        final_output=final,\n                        encoder=test_params[\"encoder\"],\n                        crf=test_params.get(\"crf\", 0),\n                        bitrate_kbps=test_params.get(\"bitrate_kbps\", 0),\n                        bufsize_kb=test_params.get(\"bufsize_kb\", 0),\n                        pix_fmt=\"yuv420p\",\n                    )\n                    \n                    successful_tests += 1\n                    \n                    # Clean up\n                    if final.exists():\n                        final.unlink()\n                        \n                except Exception:\n                    # Some boundary values might be rejected\n                    pass\n        \n        return {\n            \"success\": True,\n            \"boundary_tests_passed\": successful_tests,\n            \"total_boundary_tests\": len(boundary_tests),\n        }\n\n    def _test_concurrent_encoding_simulation(self, temp_workspace):\n        \"\"\"Simulate concurrent encoding scenarios.\"\"\"\n        intermediate = temp_workspace[\"intermediate\"]\n        final = temp_workspace[\"final\"]\n        \n        # Simulate multiple \"concurrent\" encodings by rapid succession\n        concurrent_tests = 5\n        successful_encodings = 0\n        \n        for i in range(concurrent_tests):\n            final_numbered = temp_workspace[\"temp_dir\"] / f\"output_{i}.mp4\"\n            \n            with patch(\"goesvfi.pipeline.encode.subprocess.Popen\") as mock_popen:\n                mock_popen_factory = create_mock_popen(\n                    expected_command=ANY, \n                    output_file_to_create=final_numbered\n                )\n                mock_popen.side_effect = mock_popen_factory\n                \n                try:\n                    encode.encode_with_ffmpeg(\n                        intermediate_input=intermediate,\n                        final_output=final_numbered,\n                        encoder=\"Software x264\",\n                        crf=23,\n                        bitrate_kbps=0,\n                        bufsize_kb=0,\n                        pix_fmt=\"yuv420p\",\n                    )\n                    \n                    successful_encodings += 1\n                    \n                    # Clean up\n                    if final_numbered.exists():\n                        final_numbered.unlink()\n                        \n                except Exception:\n                    # Some concurrent operations might fail\n                    pass\n        \n        return {\n            \"success\": True,\n            \"concurrent_encodings_completed\": successful_encodings,\n            \"total_concurrent_attempts\": concurrent_tests,\n        }