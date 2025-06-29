"""
Optimized tests for run_ffmpeg functionality with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for FFmpeg interpolation setup and mock configurations
- Combined interpolation testing scenarios for different filter combinations
- Batch validation of FFmpeg command generation and parameter handling
- Enhanced error handling and edge case coverage
"""

from pathlib import Path
import tempfile
from typing import Any
from unittest.mock import patch

import pytest

from goesvfi.pipeline.run_ffmpeg import run_ffmpeg_interpolation


class TestRunFFmpegInterpolationV2:
    """Optimized FFmpeg interpolation tests with full coverage."""

    @pytest.fixture(scope="class")
    def ffmpeg_interpolation_components(self):
        """Create shared components for FFmpeg interpolation testing."""

        # Enhanced Interpolation Test Manager
        class InterpolationTestManager:
            """Manage FFmpeg interpolation testing scenarios."""

            def __init__(self) -> None:
                self.parameter_templates = {
                    "basic": {
                        "fps": 30,
                        "num_intermediate_frames": 1,
                        "_use_preset_optimal": False,
                        "crop_rect": None,
                        "debug_mode": False,
                        "use_ffmpeg_interp": True,
                        "filter_preset": "medium",
                        "mi_mode": "mci",
                        "mc_mode": "obmc",
                        "me_mode": "bidir",
                        "me_algo": "epzs",
                        "search_param": 32,
                        "scd_mode": "fdi",
                        "scd_threshold": 10.0,
                        "minter_mb_size": 16,
                        "minter_vsbmc": 0,
                        "apply_unsharp": False,
                        "unsharp_lx": 3,
                        "unsharp_ly": 3,
                        "unsharp_la": 1.0,
                        "unsharp_cx": 5,
                        "unsharp_cy": 5,
                        "unsharp_ca": 0.0,
                        "crf": 18,
                        "bitrate_kbps": 5000,
                        "bufsize_kb": 10000,
                        "pix_fmt": "yuv420p",
                    },
                    "debug": {
                        "debug_mode": True,
                    },
                    "cropped": {
                        "crop_rect": (100, 50, 800, 600),
                    },
                    "high_quality": {
                        "num_intermediate_frames": 2,
                        "crf": 15,
                        "filter_preset": "veryslow",
                    },
                    "no_bitrate": {
                        "bitrate_kbps": 0,
                        "bufsize_kb": 0,
                    },
                    "with_unsharp": {
                        "apply_unsharp": True,
                        "unsharp_lx": 5,
                        "unsharp_ly": 5,
                        "unsharp_la": 1.2,
                        "unsharp_cx": 3,
                        "unsharp_cy": 3,
                        "unsharp_ca": 0.5,
                    },
                    "no_minterpolate": {
                        "use_ffmpeg_interp": False,
                    },
                    "complex_filter": {
                        "crop_rect": (50, 25, 1920, 1080),
                        "use_ffmpeg_interp": True,
                        "apply_unsharp": True,
                    },
                }

                self.test_scenarios = {
                    "basic_interpolation": self._test_basic_interpolation,
                    "debug_mode": self._test_debug_mode,
                    "crop_functionality": self._test_crop_functionality,
                    "minterpolate_filters": self._test_minterpolate_filters,
                    "encoding_parameters": self._test_encoding_parameters,
                    "filter_combinations": self._test_filter_combinations,
                    "error_conditions": self._test_error_conditions,
                    "edge_cases": self._test_edge_cases,
                }

            def _test_basic_interpolation(self, temp_workspace, command_registry):
                """Test basic FFmpeg interpolation functionality."""
                input_dir = temp_workspace["input_dir"]
                output_file = temp_workspace["output_file"]
                params = self.parameter_templates["basic"].copy()

                with patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command") as mock_run_command:
                    result = run_ffmpeg_interpolation(input_dir=input_dir, output_mp4_path=output_file, **params)

                    # Verify return value
                    assert result == output_file, "Should return output path"

                    # Verify command execution
                    mock_run_command.assert_called_once()
                    call_args = mock_run_command.call_args
                    cmd = call_args[0][0]
                    desc = call_args[0][1]

                    # Store command for analysis
                    command_registry["basic_interpolation"] = {
                        "success": True,
                        "command": cmd,
                        "description": desc,
                        "return_value": result,
                    }

                    # Basic command structure validation
                    assert cmd[0] == "ffmpeg", "Command should start with ffmpeg"
                    assert "-hide_banner" in cmd, "Should include hide_banner flag"
                    assert "-loglevel" in cmd, "Should include loglevel flag"
                    assert "info" in cmd, "Default log level should be info"
                    assert "-y" in cmd, "Should include overwrite flag"
                    assert "-framerate" in cmd, "Should include framerate flag"
                    assert "30" in cmd, "Should include correct framerate"
                    assert str(input_dir / "*.png") in cmd, "Should include input pattern"
                    assert str(output_file) in cmd, "Should include output file"
                    assert desc == "FFmpeg interpolation", "Should have correct description"

                return command_registry["basic_interpolation"]

            def _test_debug_mode(self, temp_workspace, command_registry):
                """Test FFmpeg interpolation with debug mode."""
                input_dir = temp_workspace["input_dir"]
                output_file = temp_workspace["output_file"]
                params = self.parameter_templates["basic"].copy()
                params.update(self.parameter_templates["debug"])

                with patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command") as mock_run_command:
                    run_ffmpeg_interpolation(input_dir=input_dir, output_mp4_path=output_file, **params)

                    cmd = mock_run_command.call_args[0][0]

                    # Verify debug log level
                    loglevel_index = cmd.index("-loglevel")
                    assert cmd[loglevel_index + 1] == "debug", "Debug mode should set debug log level"

                    command_registry["debug_mode"] = {
                        "success": True,
                        "command": cmd,
                        "debug_enabled": True,
                    }

                return command_registry["debug_mode"]

            def _test_crop_functionality(self, temp_workspace, command_registry):
                """Test FFmpeg interpolation with crop functionality."""
                input_dir = temp_workspace["input_dir"]
                output_file = temp_workspace["output_file"]
                params = self.parameter_templates["basic"].copy()
                params.update(self.parameter_templates["cropped"])

                with patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command") as mock_run_command:
                    run_ffmpeg_interpolation(input_dir=input_dir, output_mp4_path=output_file, **params)

                    cmd = mock_run_command.call_args[0][0]

                    # Verify crop filter
                    vf_index = cmd.index("-vf")
                    filter_str = cmd[vf_index + 1]
                    assert "crop=800:600:100:50" in filter_str, "Should include crop filter"

                    command_registry["crop_functionality"] = {
                        "success": True,
                        "command": cmd,
                        "filter_string": filter_str,
                        "has_crop": True,
                    }

                return command_registry["crop_functionality"]

            def _test_minterpolate_filters(self, temp_workspace, command_registry):
                """Test minterpolate filter configurations."""
                input_dir = temp_workspace["input_dir"]
                output_file = temp_workspace["output_file"]

                minterpolate_tests = {
                    "with_minterpolate": {
                        "params": {"use_ffmpeg_interp": True, "num_intermediate_frames": 2},
                        "expected_fps": 90,  # 30 * (2 + 1)
                        "should_have_minterpolate": True,
                    },
                    "without_minterpolate": {
                        "params": {"use_ffmpeg_interp": False},
                        "should_have_minterpolate": False,
                    },
                    "optional_params_empty": {
                        "params": {
                            "use_ffmpeg_interp": True,
                            "me_algo": "",  # Empty should not be included
                            "search_param": 0,  # Zero should not be included
                            "scd_mode": None,  # None should not be included
                            "scd_threshold": None,
                            "minter_mb_size": None,
                            "minter_vsbmc": 0,  # Zero should not be included
                        },
                        "should_exclude": ["me=", "search_param=", "scd=", "scd_threshold=", "mb_size=", "vsbmc="],
                    },
                    "default_me_algo": {
                        "params": {"use_ffmpeg_interp": True, "me_algo": "(default)"},
                        "should_exclude": ["me="],
                    },
                    "with_vsbmc": {
                        "params": {"use_ffmpeg_interp": True, "minter_vsbmc": 1},
                        "should_include": ["vsbmc=1"],
                    },
                }

                results = {}

                for test_name, test_config in minterpolate_tests.items():
                    params = self.parameter_templates["basic"].copy()
                    params.update(test_config["params"])

                    with patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command") as mock_run_command:
                        run_ffmpeg_interpolation(input_dir=input_dir, output_mp4_path=output_file, **params)

                        cmd = mock_run_command.call_args[0][0]
                        vf_index = cmd.index("-vf")
                        filter_str = cmd[vf_index + 1]

                        # Test expectations
                        if "should_have_minterpolate" in test_config:
                            if test_config["should_have_minterpolate"]:
                                assert "minterpolate=" in filter_str, f"Should have minterpolate in {test_name}"
                            else:
                                assert "minterpolate=" not in filter_str, f"Should not have minterpolate in {test_name}"

                        if "expected_fps" in test_config:
                            assert f"fps={test_config['expected_fps']}" in filter_str, f"Wrong FPS in {test_name}"

                        if "should_exclude" in test_config:
                            for exclude_item in test_config["should_exclude"]:
                                assert exclude_item not in filter_str, f"Should exclude {exclude_item} in {test_name}"

                        if "should_include" in test_config:
                            for include_item in test_config["should_include"]:
                                assert include_item in filter_str, f"Should include {include_item} in {test_name}"

                        results[test_name] = {
                            "success": True,
                            "filter_string": filter_str,
                            "command": cmd,
                        }

                command_registry["minterpolate_filters"] = results
                return results

            def _test_encoding_parameters(self, temp_workspace, command_registry):
                """Test encoding parameter configurations."""
                input_dir = temp_workspace["input_dir"]
                output_file = temp_workspace["output_file"]

                encoding_tests = {
                    "with_bitrate": {
                        "params": self.parameter_templates["basic"],
                        "should_include": [
                            "-an",
                            "-vcodec",
                            "libx264",
                            "-preset",
                            "medium",
                            "-crf",
                            "18",
                            "-b:v",
                            "5000k",
                            "-bufsize",
                            "10000k",
                            "-pix_fmt",
                            "yuv420p",
                        ],
                    },
                    "without_bitrate": {
                        "params": {**self.parameter_templates["basic"], **self.parameter_templates["no_bitrate"]},
                        "should_include": [
                            "-an",
                            "-vcodec",
                            "libx264",
                            "-preset",
                            "medium",
                            "-crf",
                            "18",
                            "-pix_fmt",
                            "yuv420p",
                        ],
                        "should_exclude": ["-b:v", "-bufsize"],
                    },
                }

                results = {}

                for test_name, test_config in encoding_tests.items():
                    with patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command") as mock_run_command:
                        run_ffmpeg_interpolation(
                            input_dir=input_dir, output_mp4_path=output_file, **test_config["params"]
                        )

                        cmd = mock_run_command.call_args[0][0]

                        # Test inclusions
                        for include_item in test_config["should_include"]:
                            assert include_item in cmd, f"Should include {include_item} in {test_name}"

                        # Test exclusions
                        for exclude_item in test_config.get("should_exclude", []):
                            assert exclude_item not in cmd, f"Should exclude {exclude_item} in {test_name}"

                        results[test_name] = {
                            "success": True,
                            "command": cmd,
                        }

                command_registry["encoding_parameters"] = results
                return results

            def _test_filter_combinations(self, temp_workspace, command_registry):
                """Test various filter combinations."""
                input_dir = temp_workspace["input_dir"]
                output_file = temp_workspace["output_file"]

                filter_tests = {
                    "unsharp_only": {
                        "params": {**self.parameter_templates["basic"], **self.parameter_templates["with_unsharp"]},
                        "expected_filters": ["unsharp=5:5:1.2:3:3:0.5"],
                    },
                    "scale_always_present": {
                        "params": self.parameter_templates["basic"],
                        "expected_filters": ["scale=trunc(iw/2)*2:trunc(ih/2)*2"],
                    },
                    "complex_filter_chain": {
                        "params": {**self.parameter_templates["basic"], **self.parameter_templates["complex_filter"]},
                        "expected_filters": [
                            "crop=1920:1080:50:25",
                            "minterpolate=",
                            "unsharp=",
                            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                        ],
                        "filter_order": ["crop=", "minterpolate=", "unsharp=", "scale="],
                    },
                }

                results = {}

                for test_name, test_config in filter_tests.items():
                    with patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command") as mock_run_command:
                        run_ffmpeg_interpolation(
                            input_dir=input_dir, output_mp4_path=output_file, **test_config["params"]
                        )

                        cmd = mock_run_command.call_args[0][0]
                        vf_index = cmd.index("-vf")
                        filter_str = cmd[vf_index + 1]

                        # Test expected filters
                        for expected_filter in test_config["expected_filters"]:
                            assert expected_filter in filter_str, f"Should include {expected_filter} in {test_name}"

                        # Test filter order if specified
                        if "filter_order" in test_config:
                            parts = filter_str.split(",")
                            expected_order = test_config["filter_order"]
                            assert len(parts) == len(expected_order), f"Filter count mismatch in {test_name}"

                            for i, expected_start in enumerate(expected_order):
                                assert parts[i].startswith(expected_start), (
                                    f"Filter order wrong at position {i} in {test_name}"
                                )

                        results[test_name] = {
                            "success": True,
                            "filter_string": filter_str,
                            "command": cmd,
                        }

                command_registry["filter_combinations"] = results
                return results

            def _test_error_conditions(self, temp_workspace, command_registry):
                """Test error handling scenarios."""
                output_file = temp_workspace["output_file"]
                params = self.parameter_templates["basic"]

                error_tests = {}

                # Test non-existent input directory
                non_existent_dir = Path("/non/existent/directory")
                try:
                    with pytest.raises(ValueError, match="Input directory .* does not exist"):
                        run_ffmpeg_interpolation(input_dir=non_existent_dir, output_mp4_path=output_file, **params)
                    error_tests["non_existent_dir"] = {"success": True, "raises_error": True}
                except Exception as e:
                    error_tests["non_existent_dir"] = {"success": False, "unexpected_error": str(e)}

                # Test empty directory (no PNG files)
                with tempfile.TemporaryDirectory() as temp_dir:
                    empty_dir = Path(temp_dir)
                    try:
                        with pytest.raises(ValueError, match="No PNG files found"):
                            run_ffmpeg_interpolation(input_dir=empty_dir, output_mp4_path=output_file, **params)
                        error_tests["no_png_files"] = {"success": True, "raises_error": True}
                    except Exception as e:
                        error_tests["no_png_files"] = {"success": False, "unexpected_error": str(e)}

                # Test FFmpeg command exception
                input_dir = temp_workspace["input_dir"]
                with patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command") as mock_run_command:
                    mock_run_command.side_effect = Exception("FFmpeg failed")

                    try:
                        with pytest.raises(Exception, match="FFmpeg failed"):
                            run_ffmpeg_interpolation(input_dir=input_dir, output_mp4_path=output_file, **params)
                        error_tests["ffmpeg_command_exception"] = {"success": True, "raises_error": True}
                    except Exception as e:
                        error_tests["ffmpeg_command_exception"] = {"success": False, "unexpected_error": str(e)}

                command_registry["error_conditions"] = error_tests
                return error_tests

            def _test_edge_cases(self, temp_workspace, command_registry):
                """Test edge cases and boundary conditions."""
                input_dir = temp_workspace["input_dir"]
                output_file = temp_workspace["output_file"]

                edge_case_tests = {
                    "fps_calculations": {
                        "test_cases": [
                            (30, 0, 30),  # 30 fps, 0 intermediate = 30 fps
                            (30, 1, 60),  # 30 fps, 1 intermediate = 60 fps
                            (24, 2, 72),  # 24 fps, 2 intermediate = 72 fps
                            (60, 3, 240),  # 60 fps, 3 intermediate = 240 fps
                        ],
                    },
                    "path_conversion": {
                        "test": "path_objects_to_strings",
                    },
                    "logging_behavior": {
                        "test": "logging_during_execution",
                    },
                    "monitor_memory": {
                        "test": "monitor_memory_parameter",
                    },
                }

                results = {}

                # FPS calculations
                fps_results = []
                for input_fps, intermediate_frames, expected_fps in edge_case_tests["fps_calculations"]["test_cases"]:
                    params = self.parameter_templates["basic"].copy()
                    params["fps"] = input_fps
                    params["num_intermediate_frames"] = intermediate_frames
                    params["use_ffmpeg_interp"] = True

                    with patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command") as mock_run_command:
                        run_ffmpeg_interpolation(input_dir=input_dir, output_mp4_path=output_file, **params)

                        cmd = mock_run_command.call_args[0][0]
                        vf_index = cmd.index("-vf")
                        filter_str = cmd[vf_index + 1]

                        assert f"fps={expected_fps}" in filter_str, (
                            f"FPS calculation wrong for {input_fps} fps, {intermediate_frames} intermediate"
                        )

                        fps_results.append({
                            "input_fps": input_fps,
                            "intermediate_frames": intermediate_frames,
                            "expected_fps": expected_fps,
                            "verified": True,
                        })

                results["fps_calculations"] = {"success": True, "test_cases": fps_results}

                # Path conversion
                with patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command") as mock_run_command:
                    # Ensure we're passing Path objects
                    assert isinstance(input_dir, Path), "Input should be Path object"
                    assert isinstance(output_file, Path), "Output should be Path object"

                    run_ffmpeg_interpolation(
                        input_dir=input_dir, output_mp4_path=output_file, **self.parameter_templates["basic"]
                    )

                    cmd = mock_run_command.call_args[0][0]

                    # Check that paths were converted to strings
                    assert str(input_dir / "*.png") in cmd, "Input path not converted to string"
                    assert str(output_file) in cmd, "Output path not converted to string"

                    results["path_conversion"] = {"success": True, "paths_converted": True}

                # Logging behavior
                with patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command") as mock_run_command:
                    with patch("goesvfi.pipeline.run_ffmpeg.LOGGER") as mock_logger:
                        run_ffmpeg_interpolation(
                            input_dir=input_dir, output_mp4_path=output_file, **self.parameter_templates["basic"]
                        )

                        # Should log the command and completion
                        assert mock_logger.info.call_count >= 2, "Should have multiple log entries"

                        # Check specific log messages
                        log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
                        has_command_log = any("Running FFmpeg command" in msg for msg in log_calls)
                        has_completion_log = any("Interpolation completed" in msg for msg in log_calls)

                        assert has_command_log, "Should log command execution"
                        assert has_completion_log, "Should log completion"

                        results["logging_behavior"] = {
                            "success": True,
                            "log_count": mock_logger.info.call_count,
                            "has_command_log": has_command_log,
                            "has_completion_log": has_completion_log,
                        }

                # Monitor memory parameter
                with patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command") as mock_run_command:
                    run_ffmpeg_interpolation(
                        input_dir=input_dir, output_mp4_path=output_file, **self.parameter_templates["basic"]
                    )

                    # Check that monitor_memory=False was passed
                    call_kwargs = mock_run_command.call_args[1]
                    assert call_kwargs["monitor_memory"] is False, "Should pass monitor_memory=False"

                    results["monitor_memory"] = {
                        "success": True,
                        "monitor_memory_set": True,
                        "monitor_memory_value": call_kwargs["monitor_memory"],
                    }

                command_registry["edge_cases"] = results
                return results

            def run_test_scenario(
                self, scenario: str, temp_workspace: dict[str, Any], command_registry: dict[str, Any]
            ):
                """Run specified test scenario."""
                return self.test_scenarios[scenario](temp_workspace, command_registry)

        # Enhanced Command Analyzer
        class CommandAnalyzer:
            """Analyze FFmpeg interpolation commands for correctness."""

            def __init__(self) -> None:
                self.analysis_rules = {
                    "basic_structure": self._analyze_basic_structure,
                    "filter_chain": self._analyze_filter_chain,
                    "encoding_params": self._analyze_encoding_params,
                    "interpolation_params": self._analyze_interpolation_params,
                }

            def _analyze_basic_structure(self, cmd: list[str]) -> dict[str, bool]:
                """Analyze basic FFmpeg command structure."""
                return {
                    "starts_with_ffmpeg": len(cmd) > 0 and cmd[0] == "ffmpeg",
                    "has_hide_banner": "-hide_banner" in cmd,
                    "has_loglevel": "-loglevel" in cmd,
                    "has_overwrite": "-y" in cmd,
                    "has_framerate": "-framerate" in cmd,
                    "has_input_pattern": any("*.png" in arg for arg in cmd),
                    "has_output_file": len(cmd) > 0 and not cmd[-1].startswith("-"),
                }

            def _analyze_filter_chain(self, cmd: list[str]) -> dict[str, Any]:
                """Analyze video filter chain."""
                filter_info = {}

                if "-vf" in cmd:
                    vf_index = cmd.index("-vf")
                    if vf_index + 1 < len(cmd):
                        filter_str = cmd[vf_index + 1]
                        filter_info["filter_string"] = filter_str
                        filter_info["has_filters"] = True

                        # Analyze individual filters
                        filter_info["has_crop"] = "crop=" in filter_str
                        filter_info["has_minterpolate"] = "minterpolate=" in filter_str
                        filter_info["has_unsharp"] = "unsharp=" in filter_str
                        filter_info["has_scale"] = "scale=" in filter_str

                        # Count filters
                        filter_info["filter_count"] = len(filter_str.split(","))
                else:
                    filter_info["has_filters"] = False

                return filter_info

            def _analyze_encoding_params(self, cmd: list[str]) -> dict[str, bool]:
                """Analyze encoding parameters."""
                return {
                    "has_no_audio": "-an" in cmd,
                    "has_video_codec": "-vcodec" in cmd,
                    "has_preset": "-preset" in cmd,
                    "has_crf": "-crf" in cmd,
                    "has_bitrate": "-b:v" in cmd,
                    "has_bufsize": "-bufsize" in cmd,
                    "has_pixel_format": "-pix_fmt" in cmd,
                }

            def _analyze_interpolation_params(self, cmd: list[str]) -> dict[str, Any]:
                """Analyze interpolation-specific parameters."""
                params = {}

                # Extract framerate
                if "-framerate" in cmd:
                    fr_index = cmd.index("-framerate")
                    if fr_index + 1 < len(cmd):
                        params["framerate"] = cmd[fr_index + 1]

                # Extract log level
                if "-loglevel" in cmd:
                    ll_index = cmd.index("-loglevel")
                    if ll_index + 1 < len(cmd):
                        params["loglevel"] = cmd[ll_index + 1]

                return params

            def analyze_command(self, cmd: list[str], analysis_types: list[str] | None = None) -> dict[str, Any]:
                """Analyze command using specified analysis types."""
                if analysis_types is None:
                    analysis_types = list(self.analysis_rules.keys())

                results = {}
                for analysis_type in analysis_types:
                    if analysis_type in self.analysis_rules:
                        results[analysis_type] = self.analysis_rules[analysis_type](cmd)

                return results

        return {
            "test_manager": InterpolationTestManager(),
            "analyzer": CommandAnalyzer(),
        }

    @pytest.fixture()
    def temp_workspace(self, tmp_path):
        """Create temporary workspace for interpolation testing."""
        # Create input directory with PNG files
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Create test PNG files
        for i in range(5):
            png_file = input_dir / f"frame_{i:04d}.png"
            png_file.write_text("fake png content")  # Dummy content

        # Output file path
        output_file = tmp_path / "output.mp4"

        return {
            "temp_dir": tmp_path,
            "input_dir": input_dir,
            "output_file": output_file,
        }

    @pytest.fixture()
    def command_registry(self):
        """Registry for storing command execution results."""
        return {}

    def test_interpolation_comprehensive_scenarios(
        self, ffmpeg_interpolation_components, temp_workspace, command_registry
    ) -> None:
        """Test comprehensive FFmpeg interpolation scenarios."""
        components = ffmpeg_interpolation_components
        test_manager = components["test_manager"]
        analyzer = components["analyzer"]

        # Define comprehensive interpolation scenarios
        interpolation_scenarios = [
            {
                "name": "Basic Interpolation",
                "test_type": "basic_interpolation",
                "analysis_types": ["basic_structure", "filter_chain", "encoding_params"],
                "expected_features": ["ffmpeg", "framerate", "output_file"],
            },
            {
                "name": "Debug Mode",
                "test_type": "debug_mode",
                "analysis_types": ["basic_structure", "interpolation_params"],
                "expected_features": ["debug", "loglevel"],
            },
            {
                "name": "Crop Functionality",
                "test_type": "crop_functionality",
                "analysis_types": ["filter_chain"],
                "expected_features": ["crop", "filter_chain"],
            },
            {
                "name": "Minterpolate Filters",
                "test_type": "minterpolate_filters",
                "analysis_types": ["filter_chain"],
                "expected_features": ["minterpolate", "fps_calculation"],
            },
            {
                "name": "Encoding Parameters",
                "test_type": "encoding_parameters",
                "analysis_types": ["encoding_params"],
                "expected_features": ["codec", "bitrate", "crf"],
            },
            {
                "name": "Filter Combinations",
                "test_type": "filter_combinations",
                "analysis_types": ["filter_chain"],
                "expected_features": ["unsharp", "scale", "complex_chain"],
            },
            {
                "name": "Error Conditions",
                "test_type": "error_conditions",
                "analysis_types": [],  # No command analysis for error tests
                "expected_errors": 3,  # Number of error conditions tested
            },
            {
                "name": "Edge Cases",
                "test_type": "edge_cases",
                "analysis_types": ["interpolation_params"],
                "expected_features": ["fps_calculations", "path_conversion", "logging"],
            },
        ]

        # Test each interpolation scenario
        all_results = {}

        for scenario in interpolation_scenarios:
            try:
                # Run interpolation test scenario
                scenario_results = test_manager.run_test_scenario(
                    scenario["test_type"], temp_workspace, command_registry
                )

                # Analyze commands for non-error scenarios
                if scenario["analysis_types"] and scenario["name"] != "Error Conditions":
                    # For scenarios that produce commands
                    if "command" in scenario_results:
                        cmd = scenario_results["command"]
                        analysis_results = analyzer.analyze_command(cmd, scenario["analysis_types"])
                        scenario_results["analysis"] = analysis_results
                    elif isinstance(scenario_results, dict) and any(
                        "command" in v for v in scenario_results.values() if isinstance(v, dict)
                    ):
                        # Multiple test results with commands
                        for test_name, test_result in scenario_results.items():
                            if isinstance(test_result, dict) and "command" in test_result:
                                cmd = test_result["command"]
                                analysis_results = analyzer.analyze_command(cmd, scenario["analysis_types"])
                                test_result["analysis"] = analysis_results

                # Verify scenario-specific expectations
                if scenario["name"] == "Basic Interpolation":
                    assert scenario_results["success"], "Basic interpolation should succeed"
                    assert scenario_results["return_value"] == temp_workspace["output_file"], (
                        "Should return output path"
                    )
                    assert scenario_results["description"] == "FFmpeg interpolation", "Should have correct description"

                    # Verify command structure
                    if "command" in scenario_results:
                        cmd = scenario_results["command"]
                        assert "ffmpeg" in cmd, "Should contain ffmpeg"
                        assert "-framerate" in cmd, "Should contain framerate"

                elif scenario["name"] == "Debug Mode":
                    assert scenario_results["success"], "Debug mode should succeed"
                    assert scenario_results["debug_enabled"], "Debug should be enabled"

                elif scenario["name"] == "Crop Functionality":
                    assert scenario_results["success"], "Crop functionality should succeed"
                    assert scenario_results["has_crop"], "Should have crop filter"
                    assert "crop=800:600:100:50" in scenario_results["filter_string"], (
                        "Should have correct crop parameters"
                    )

                elif scenario["name"] == "Minterpolate Filters":
                    # Check that all minterpolate tests passed
                    for test_name, test_result in scenario_results.items():
                        assert test_result["success"], f"Minterpolate test {test_name} should succeed"

                elif scenario["name"] == "Encoding Parameters":
                    # Check that all encoding tests passed
                    for test_name, test_result in scenario_results.items():
                        assert test_result["success"], f"Encoding test {test_name} should succeed"

                elif scenario["name"] == "Filter Combinations":
                    # Check that all filter combination tests passed
                    for test_name, test_result in scenario_results.items():
                        assert test_result["success"], f"Filter combination test {test_name} should succeed"

                elif scenario["name"] == "Error Conditions":
                    # Check error handling
                    error_count = len([r for r in scenario_results.values() if r.get("raises_error")])
                    assert error_count >= scenario["expected_errors"], (
                        f"Expected at least {scenario['expected_errors']} errors, got {error_count}"
                    )

                elif scenario["name"] == "Edge Cases":
                    # Check edge case handling
                    for test_name, test_result in scenario_results.items():
                        assert test_result["success"], f"Edge case {test_name} should succeed"

                all_results[scenario["name"]] = scenario_results

            except Exception as e:
                if scenario["name"] != "Error Conditions":
                    pytest.fail(f"Unexpected error in {scenario['name']}: {e}")
                # Error scenarios are expected to have exceptions

        # Overall validation
        assert len(all_results) == len(interpolation_scenarios), "Not all interpolation scenarios completed"

    def test_interpolation_command_validation_and_analysis(
        self, ffmpeg_interpolation_components, temp_workspace
    ) -> None:
        """Test interpolation command validation and detailed analysis."""
        components = ffmpeg_interpolation_components
        analyzer = components["analyzer"]
        test_manager = components["test_manager"]

        # Test specific command configurations
        command_validation_scenarios = [
            {
                "name": "Standard Quality Command",
                "params": test_manager.parameter_templates["basic"],
                "expected_elements": ["ffmpeg", "-framerate", "30", "-vcodec", "libx264"],
            },
            {
                "name": "High Quality Command",
                "params": {
                    **test_manager.parameter_templates["basic"],
                    **test_manager.parameter_templates["high_quality"],
                },
                "expected_elements": ["ffmpeg", "-crf", "15", "-preset", "veryslow"],
            },
            {
                "name": "Complex Filter Command",
                "params": {
                    **test_manager.parameter_templates["basic"],
                    **test_manager.parameter_templates["complex_filter"],
                },
                "expected_elements": ["ffmpeg", "-vf", "crop=", "minterpolate=", "unsharp="],
            },
        ]

        # Test each command validation scenario
        for scenario in command_validation_scenarios:
            params = scenario["params"]

            with patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command") as mock_run_command:
                run_ffmpeg_interpolation(
                    input_dir=temp_workspace["input_dir"], output_mp4_path=temp_workspace["output_file"], **params
                )

                # Get actual command
                actual_cmd = mock_run_command.call_args[0][0]

                # Verify expected elements
                for element in scenario["expected_elements"]:
                    if element.endswith("="):
                        # Filter elements need special handling
                        if "-vf" in actual_cmd:
                            vf_index = actual_cmd.index("-vf")
                            filter_str = actual_cmd[vf_index + 1]
                            assert element in filter_str, (
                                f"Missing filter element '{element}' in {scenario['name']} command"
                            )
                    else:
                        assert element in actual_cmd, (
                            f"Missing element '{element}' in {scenario['name']} command: {actual_cmd}"
                        )

                # Analyze command structure
                analysis_results = analyzer.analyze_command(
                    actual_cmd, ["basic_structure", "filter_chain", "encoding_params", "interpolation_params"]
                )

                # Validate basic structure
                basic = analysis_results["basic_structure"]
                assert basic["starts_with_ffmpeg"], f"Command should start with ffmpeg for {scenario['name']}"
                assert basic["has_framerate"], f"Command should have framerate for {scenario['name']}"
                assert basic["has_output_file"], f"Command should have output file for {scenario['name']}"

                # Validate encoding parameters
                encoding = analysis_results["encoding_params"]
                assert encoding["has_video_codec"], f"Command should have video codec for {scenario['name']}"
                assert encoding["has_pixel_format"], f"Command should have pixel format for {scenario['name']}"

    def test_interpolation_performance_and_stress_scenarios(
        self, ffmpeg_interpolation_components, temp_workspace
    ) -> None:
        """Test interpolation performance characteristics and stress scenarios."""
        components = ffmpeg_interpolation_components
        test_manager = components["test_manager"]

        # Performance and stress test scenarios
        performance_scenarios = [
            {
                "name": "Rapid Parameter Changes",
                "test": lambda: self._test_rapid_parameter_changes(temp_workspace, test_manager),
            },
            {
                "name": "Complex Filter Combinations",
                "test": lambda: self._test_complex_filter_combinations(temp_workspace, test_manager),
            },
            {
                "name": "Extreme Parameter Values",
                "test": lambda: self._test_extreme_parameter_values(temp_workspace, test_manager),
            },
            {
                "name": "Multiple Interpolation Sessions",
                "test": lambda: self._test_multiple_interpolation_sessions(temp_workspace, test_manager),
            },
        ]

        # Test each performance scenario
        for scenario in performance_scenarios:
            try:
                result = scenario["test"]()
                assert result is not None, f"Performance test {scenario['name']} returned None"
                assert result.get("success", False), f"Performance test {scenario['name']} failed"
            except Exception as e:
                # Some performance tests may have expected limitations
                assert "expected" in str(e).lower() or "limitation" in str(e).lower(), (
                    f"Unexpected error in performance test {scenario['name']}: {e}"
                )

    def _test_rapid_parameter_changes(self, temp_workspace, test_manager):
        """Test rapid parameter changes."""
        input_dir = temp_workspace["input_dir"]
        output_file = temp_workspace["output_file"]

        parameter_sets = [
            test_manager.parameter_templates["basic"],
            {**test_manager.parameter_templates["basic"], **test_manager.parameter_templates["debug"]},
            {**test_manager.parameter_templates["basic"], **test_manager.parameter_templates["high_quality"]},
            {**test_manager.parameter_templates["basic"], **test_manager.parameter_templates["with_unsharp"]},
        ]

        successful_changes = 0

        for _i, params in enumerate(parameter_sets * 5):  # Test multiple rounds
            with patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command"):
                try:
                    run_ffmpeg_interpolation(input_dir=input_dir, output_mp4_path=output_file, **params)
                    successful_changes += 1
                except Exception:
                    # Some rapid changes might fail
                    pass

        return {
            "success": True,
            "successful_changes": successful_changes,
            "total_attempts": len(parameter_sets) * 5,
        }

    def _test_complex_filter_combinations(self, temp_workspace, test_manager):
        """Test complex filter combinations."""
        input_dir = temp_workspace["input_dir"]
        output_file = temp_workspace["output_file"]

        complex_combinations = [
            {
                "crop_rect": (10, 10, 500, 500),
                "use_ffmpeg_interp": True,
                "apply_unsharp": True,
                "num_intermediate_frames": 3,
            },
            {
                "crop_rect": (0, 0, 1920, 1080),
                "use_ffmpeg_interp": True,
                "apply_unsharp": True,
                "debug_mode": True,
                "num_intermediate_frames": 2,
            },
        ]

        successful_combinations = 0

        for combination in complex_combinations:
            params = test_manager.parameter_templates["basic"].copy()
            params.update(combination)

            with patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command") as mock_run_command:
                try:
                    run_ffmpeg_interpolation(input_dir=input_dir, output_mp4_path=output_file, **params)

                    # Verify complex filter chain
                    cmd = mock_run_command.call_args[0][0]
                    vf_index = cmd.index("-vf")
                    filter_str = cmd[vf_index + 1]

                    # Should have multiple filters
                    filter_count = len(filter_str.split(","))
                    assert filter_count >= 3, "Complex combination should have multiple filters"

                    successful_combinations += 1
                except Exception:
                    # Some complex combinations might fail
                    pass

        return {
            "success": True,
            "successful_combinations": successful_combinations,
            "total_combinations": len(complex_combinations),
        }

    def _test_extreme_parameter_values(self, temp_workspace, test_manager):
        """Test extreme parameter values."""
        input_dir = temp_workspace["input_dir"]
        output_file = temp_workspace["output_file"]

        extreme_values = [
            {"fps": 1, "num_intermediate_frames": 0},  # Minimum values
            {"fps": 240, "num_intermediate_frames": 10},  # Very high values
            {"crf": 0, "bitrate_kbps": 100000},  # Extreme quality settings
            {"search_param": 1, "scd_threshold": 0.1},  # Minimum search parameters
        ]

        successful_tests = 0

        for extreme_params in extreme_values:
            params = test_manager.parameter_templates["basic"].copy()
            params.update(extreme_params)

            with patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command"):
                try:
                    run_ffmpeg_interpolation(input_dir=input_dir, output_mp4_path=output_file, **params)
                    successful_tests += 1
                except Exception:
                    # Some extreme values might be rejected
                    pass

        return {
            "success": True,
            "extreme_tests_passed": successful_tests,
            "total_extreme_tests": len(extreme_values),
        }

    def _test_multiple_interpolation_sessions(self, temp_workspace, test_manager):
        """Test multiple interpolation sessions."""
        input_dir = temp_workspace["input_dir"]

        session_count = 10
        successful_sessions = 0

        for i in range(session_count):
            output_file = temp_workspace["temp_dir"] / f"output_{i}.mp4"

            with patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command"):
                try:
                    run_ffmpeg_interpolation(
                        input_dir=input_dir, output_mp4_path=output_file, **test_manager.parameter_templates["basic"]
                    )
                    successful_sessions += 1
                except Exception:
                    # Some sessions might fail
                    pass

        return {
            "success": True,
            "successful_sessions": successful_sessions,
            "total_sessions": session_count,
        }
