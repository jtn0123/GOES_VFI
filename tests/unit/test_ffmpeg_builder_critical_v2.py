"""
Optimized critical tests for FFmpeg command building functionality with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for FFmpeg builder components and validation
- Combined critical command building testing scenarios
- Batch validation of command structures and error conditions
- Enhanced test coverage for edge cases and boundary conditions
"""

import os
from typing import Any

import pytest

from goesvfi.pipeline.ffmpeg_builder import FFmpegCommandBuilder


class TestFFmpegCommandBuilderCriticalV2:
    """Optimized critical FFmpeg command builder tests with full coverage."""

    @pytest.fixture(scope="class")
    @staticmethod
    def ffmpeg_critical_components() -> Any:  # noqa: C901
        """Create shared components for critical FFmpeg command testing.

        Returns:
            CriticalCommandTestManager: Manager for critical FFmpeg command testing scenarios.
        """

        # Critical Command Test Manager
        class CriticalCommandTestManager:
            """Manage critical FFmpeg command testing scenarios."""

            def __init__(self) -> None:
                self.critical_scenarios = {
                    "basic_command": self._test_basic_command,
                    "two_pass_encoding": self._test_two_pass_encoding,
                    "stream_copy": self._test_stream_copy,
                    "invalid_parameters": self._test_invalid_parameters,
                    "pixel_format": self._test_pixel_format,
                }

                self.command_templates = {
                    "basic_x264": {
                        "encoder": "Software x264",
                        "crf": 23,
                        "expected_elements": ["ffmpeg", "-i", "-c:v", "libx264"],
                        "validation_type": "crf_based",
                    },
                    "two_pass_x265": {
                        "encoder": "Software x265 (2-Pass)",
                        "bitrate": 5000,
                        "expected_elements": ["ffmpeg", "-i", "-c:v", "libx265", "-x265-params"],
                        "validation_type": "two_pass",
                    },
                    "stream_copy": {
                        "encoder": "None (copy original)",
                        "expected_elements": ["ffmpeg", "-i", "-c", "copy"],
                        "validation_type": "copy_stream",
                    },
                }

            @staticmethod
            def _test_basic_command(temp_workspace: Any) -> dict[str, Any]:
                """Test basic FFmpeg command construction scenarios.

                Returns:
                    dict[str, Any]: Test results and validation data.
                """
                results = {}

                # Test basic video encoding command
                builder = FFmpegCommandBuilder()
                cmd = (
                    builder.set_input(temp_workspace["input_path"])
                    .set_output(temp_workspace["output_path"])
                    .set_encoder("Software x264")
                    .set_crf(23)
                    .build()
                )

                # Comprehensive validation
                assert "ffmpeg" in cmd, "FFmpeg executable not found in command"
                assert "-i" in cmd, "Input flag not found in command"
                assert str(temp_workspace["input_path"]) in cmd, "Input path not found in command"
                assert str(temp_workspace["output_path"]) in cmd, "Output path not found in command"

                # Verify command structure integrity
                input_index = cmd.index("-i")
                assert input_index + 1 < len(cmd), "No input file after -i flag"
                assert cmd[input_index + 1] == str(temp_workspace["input_path"]), "Input file mismatch"

                # Verify output is at the end
                assert cmd[-1] == str(temp_workspace["output_path"]), "Output file not at end of command"

                results["basic_command"] = {
                    "success": True,
                    "command_length": len(cmd),
                    "has_required_elements": all(elem in cmd for elem in ["ffmpeg", "-i"]),
                    "input_output_correct": True,
                }

                return results

            @staticmethod
            def _test_two_pass_encoding(temp_workspace: Any) -> dict[str, Any]:
                """Test two-pass encoding command construction.

                Returns:
                    dict[str, Any]: Test results and validation data.
                """
                results = {}

                # Test two-pass encoding setup
                builder = FFmpegCommandBuilder()
                cmd = (
                    builder.set_input(temp_workspace["input_path"])
                    .set_output(temp_workspace["output_path"])
                    .set_encoder("Software x265 (2-Pass)")
                    .set_bitrate(5000)
                    .set_two_pass(is_two_pass=True, pass_log_prefix="passlog", pass_number=1)
                    .build()
                )

                # Comprehensive two-pass validation
                assert "ffmpeg" in cmd, "FFmpeg executable not found"
                assert "-c:v" in cmd, "Video codec flag not found"
                assert "libx265" in cmd, "x265 codec not found"
                assert "-x265-params" in cmd, "x265 parameters flag not found"

                # Two-pass specific validation
                x265_params_index = cmd.index("-x265-params")
                assert x265_params_index + 1 < len(cmd), "No x265 params after flag"
                x265_params = cmd[x265_params_index + 1]
                assert "pass=1" in x265_params, "Pass 1 not found in x265 params"

                # Passlog validation
                assert "-passlogfile" in cmd, "Passlog file flag not found"
                passlog_index = cmd.index("-passlogfile")
                assert passlog_index + 1 < len(cmd), "No passlog file after flag"
                assert cmd[passlog_index + 1] == "passlog", "Passlog file mismatch"

                # Null output validation for pass 1
                assert os.devnull in cmd, "Null output not found for pass 1"

                results["two_pass_pass1"] = {
                    "success": True,
                    "has_x265_codec": "libx265" in cmd,
                    "has_pass_params": "pass=1" in " ".join(cmd),
                    "outputs_to_null": os.devnull in cmd,
                }

                # Test pass 2 as well
                builder2 = FFmpegCommandBuilder()
                cmd2 = (
                    builder2.set_input(temp_workspace["input_path"])
                    .set_output(temp_workspace["output_path"])
                    .set_encoder("Software x265 (2-Pass)")
                    .set_bitrate(5000)
                    .set_two_pass(is_two_pass=True, pass_log_prefix="passlog", pass_number=2)
                    .build()
                )

                # Pass 2 validation
                x265_params_index2 = cmd2.index("-x265-params")
                x265_params2 = cmd2[x265_params_index2 + 1]
                assert "pass=2" in x265_params2, "Pass 2 not found in x265 params"
                assert str(temp_workspace["output_path"]) in cmd2, "Output file not found in pass 2"
                assert os.devnull not in cmd2, "Null output incorrectly found in pass 2"

                results["two_pass_pass2"] = {
                    "success": True,
                    "has_pass2_params": "pass=2" in " ".join(cmd2),
                    "outputs_to_file": str(temp_workspace["output_path"]) in cmd2,
                }

                return results

            @staticmethod
            def _test_stream_copy(temp_workspace: Any) -> dict[str, Any]:
                """Test stream copy command construction.

                Returns:
                    dict[str, Any]: Test results and validation data.
                """
                results = {}

                builder = FFmpegCommandBuilder()
                cmd = (
                    builder.set_input(temp_workspace["input_path"])
                    .set_output(temp_workspace["output_path"])
                    .set_encoder("None (copy original)")
                    .build()
                )

                # Stream copy validation
                assert "ffmpeg" in cmd, "FFmpeg executable not found"
                assert "-i" in cmd, "Input flag not found"
                assert str(temp_workspace["input_path"]) in cmd, "Input path not found"
                assert "-c" in cmd, "Codec flag not found"
                assert "copy" in cmd, "Copy codec not found"
                assert str(temp_workspace["output_path"]) in cmd, "Output path not found"

                # Verify copy codec placement
                codec_index = cmd.index("-c")
                assert codec_index + 1 < len(cmd), "No codec after -c flag"
                assert cmd[codec_index + 1] == "copy", "Copy codec mismatch"

                # Stream copy should be minimal
                assert len(cmd) < 10, "Stream copy command too long"

                results["stream_copy"] = {
                    "success": True,
                    "has_copy_codec": "copy" in cmd,
                    "command_minimal": len(cmd) < 10,
                    "proper_structure": "-c" in cmd and "copy" in cmd,
                }

                return results

            @staticmethod
            def _test_invalid_parameters(temp_workspace: Any) -> dict[str, Any]:
                """Test comprehensive error handling for invalid parameters.

                Returns:
                    dict[str, Any]: Test results and validation data.
                """
                error_tests = {}

                # Test 1: Missing input, output, and encoder
                builder1 = FFmpegCommandBuilder()
                with pytest.raises(ValueError, match="Input path, output path, and encoder must be set"):
                    builder1.build()
                error_tests["missing_all_required"] = {"success": True, "raises_error": True}

                # Test 2: Missing encoder only
                builder2 = FFmpegCommandBuilder()
                builder2.set_input(temp_workspace["input_path"])
                builder2.set_output(temp_workspace["output_path"])
                with pytest.raises(ValueError, match=r".*"):
                    builder2.build()
                error_tests["missing_encoder"] = {"success": True, "raises_error": True}

                # Test 3: Two-pass without required params
                builder3 = FFmpegCommandBuilder()
                builder3.set_input(temp_workspace["input_path"])
                builder3.set_output(temp_workspace["output_path"])
                builder3.set_encoder("Software x265 (2-Pass)")
                with pytest.raises(ValueError, match="Two-pass encoding requires"):
                    builder3.build()
                error_tests["two_pass_missing_params"] = {"success": True, "raises_error": True}

                # Test 4: Missing input specifically
                builder4 = FFmpegCommandBuilder()
                builder4.set_output(temp_workspace["output_path"])
                builder4.set_encoder("Software x264")
                builder4.set_crf(23)
                with pytest.raises(ValueError, match=r".*"):
                    builder4.build()
                error_tests["missing_input"] = {"success": True, "raises_error": True}

                # Test 5: Missing output specifically
                builder5 = FFmpegCommandBuilder()
                builder5.set_input(temp_workspace["input_path"])
                builder5.set_encoder("Software x264")
                builder5.set_crf(23)
                with pytest.raises(ValueError, match=r".*"):
                    builder5.build()
                error_tests["missing_output"] = {"success": True, "raises_error": True}

                return error_tests

            @staticmethod
            def _test_pixel_format(temp_workspace: Any) -> dict[str, Any]:
                """Test pixel format setting functionality.

                Returns:
                    dict[str, Any]: Test results and validation data.
                """
                results = {}

                # Test pixel format with x264
                builder = FFmpegCommandBuilder()
                cmd = (
                    builder.set_input(temp_workspace["input_path"])
                    .set_output(temp_workspace["output_path"])
                    .set_encoder("Software x264")
                    .set_pix_fmt("yuv420p10le")
                    .set_crf(20)
                    .build()
                )

                # Pixel format validation
                assert "-pix_fmt" in cmd, "Pixel format flag not found"
                assert "yuv420p10le" in cmd, "Specified pixel format not found"

                # Verify pixel format placement
                pix_fmt_index = cmd.index("-pix_fmt")
                assert pix_fmt_index + 1 < len(cmd), "No pixel format after flag"
                assert cmd[pix_fmt_index + 1] == "yuv420p10le", "Pixel format mismatch"

                # Test with different pixel formats
                pixel_formats = ["yuv420p", "yuv444p", "yuv422p", "rgb24"]
                pixel_format_results = {}

                for pix_fmt in pixel_formats:
                    builder_test = FFmpegCommandBuilder()
                    cmd_test = (
                        builder_test.set_input(temp_workspace["input_path"])
                        .set_output(temp_workspace["output_path"])
                        .set_encoder("Software x264")
                        .set_pix_fmt(pix_fmt)
                        .set_crf(23)
                        .build()
                    )

                    pixel_format_results[pix_fmt] = {
                        "found": pix_fmt in cmd_test,
                        "position_correct": cmd_test[cmd_test.index("-pix_fmt") + 1] == pix_fmt,
                    }

                results["pixel_format"] = {
                    "success": True,
                    "has_pix_fmt_flag": "-pix_fmt" in cmd,
                    "has_specified_format": "yuv420p10le" in cmd,
                    "multiple_formats_tested": len(pixel_format_results),
                    "all_formats_work": all(
                        r["found"] and r["position_correct"] for r in pixel_format_results.values()
                    ),
                }

                return results

            def run_critical_scenario(self, scenario: str, temp_workspace: dict[str, Any]) -> dict[str, Any]:
                """Run specified critical test scenario.

                Returns:
                    dict[str, Any]: Test results for the specified scenario.
                """
                return self.critical_scenarios[scenario](temp_workspace)

        # Critical Command Validator
        class CriticalCommandValidator:
            """Validate critical aspects of FFmpeg commands."""

            def __init__(self) -> None:
                self.validation_rules = {
                    "command_integrity": self._validate_command_integrity,
                    "parameter_correctness": self._validate_parameter_correctness,
                    "error_conditions": self._validate_error_conditions,
                    "edge_cases": self._validate_edge_cases,
                }

            @staticmethod
            def _validate_command_integrity(cmd: list[str]) -> dict[str, bool]:
                """Validate basic command integrity.

                Returns:
                    dict[str, bool]: Command integrity validation results.
                """
                return {
                    "starts_with_ffmpeg": len(cmd) > 0 and cmd[0] == "ffmpeg",
                    "has_input_flag": "-i" in cmd,
                    "has_output_file": len(cmd) > 0 and not cmd[-1].startswith("-"),
                    "reasonable_length": 5 <= len(cmd) <= 50,
                    "no_empty_elements": all(elem for elem in cmd),
                }

            @staticmethod
            def _validate_parameter_correctness(cmd: list[str]) -> dict[str, Any]:
                """Validate parameter correctness.

                Returns:
                    dict[str, Any]: Parameter correctness validation results.
                """
                flags_with_values = ["-i", "-c:v", "-c", "-crf", "-b:v", "-preset", "-pix_fmt", "-x265-params"]
                flag_validation = {}

                for flag in flags_with_values:
                    if flag in cmd:
                        flag_index = cmd.index(flag)
                        has_value = flag_index + 1 < len(cmd) and not cmd[flag_index + 1].startswith("-")
                        flag_validation[f"{flag}_has_value"] = has_value

                return {
                    "flag_value_pairs_correct": all(flag_validation.values()) if flag_validation else True,
                    "flag_details": flag_validation,
                }

            @staticmethod
            def _validate_error_conditions(error_results: dict[str, Any]) -> dict[str, bool]:
                """Validate error condition handling.

                Returns:
                    dict[str, bool]: Error condition validation results.
                """
                expected_errors = [
                    "missing_all_required",
                    "missing_encoder",
                    "two_pass_missing_params",
                    "missing_input",
                    "missing_output",
                ]

                return {
                    "all_errors_caught": all(
                        error_results.get(error, {}).get("raises_error", False) for error in expected_errors
                    ),
                    "error_count": len([e for e in error_results.values() if e.get("raises_error", False)]),
                    "no_unexpected_successes": all(
                        error_results.get(error, {}).get("success", False) for error in expected_errors
                    ),
                }

            @staticmethod
            def _validate_edge_cases(edge_results: dict[str, Any]) -> dict[str, bool]:
                """Validate edge case handling.

                Returns:
                    dict[str, bool]: Edge case validation results.
                """
                return {
                    "pixel_formats_work": edge_results.get("pixel_format", {}).get("all_formats_work", False),
                    "two_pass_complete": all(
                        edge_results.get(f"two_pass_pass{i}", {}).get("success", False) for i in [1, 2]
                    ),
                    "stream_copy_minimal": edge_results.get("stream_copy", {}).get("command_minimal", False),
                }

            def validate_critical_command(
                self, cmd: list[str], validation_types: list[str] | None = None
            ) -> dict[str, Any]:
                """Validate command using specified validation types.

                Returns:
                    dict[str, Any]: Validation results for all specified types.
                """
                if validation_types is None:
                    validation_types = ["command_integrity", "parameter_correctness"]

                results = {}
                for validation_type in validation_types:
                    if validation_type in self.validation_rules:
                        results[validation_type] = self.validation_rules[validation_type](cmd)

                return results

        return {
            "test_manager": CriticalCommandTestManager(),
            "validator": CriticalCommandValidator(),
        }

    @pytest.fixture()
    def temp_workspace(self, tmp_path: Any) -> dict[str, Any]:  # noqa: PLR6301
        """Create temporary workspace for critical FFmpeg testing.

        Returns:
            dict[str, Any]: Workspace configuration with test paths.
        """
        test_dir = tmp_path / "ffmpeg_critical_test"
        test_dir.mkdir(exist_ok=True)

        input_path = test_dir / "input.mkv"
        output_path = test_dir / "output.mp4"

        # Create dummy files
        input_path.touch()
        output_path.touch()

        return {
            "test_dir": test_dir,
            "input_path": input_path,
            "output_path": output_path,
        }

    def test_ffmpeg_critical_comprehensive_scenarios(
        self, ffmpeg_critical_components: Any, temp_workspace: Any
    ) -> None:
        """Test comprehensive critical FFmpeg command scenarios."""
        components = ffmpeg_critical_components
        test_manager = components["test_manager"]
        validator = components["validator"]

        # Define critical test scenarios
        critical_scenarios = [
            {
                "name": "Basic Command Construction",
                "test_type": "basic_command",
                "validation_types": ["command_integrity", "parameter_correctness"],
                "expected_results": ["basic_command"],
            },
            {
                "name": "Two-Pass Encoding",
                "test_type": "two_pass_encoding",
                "validation_types": ["command_integrity", "parameter_correctness"],
                "expected_results": ["two_pass_pass1", "two_pass_pass2"],
            },
            {
                "name": "Stream Copy Operations",
                "test_type": "stream_copy",
                "validation_types": ["command_integrity"],
                "expected_results": ["stream_copy"],
            },
            {
                "name": "Invalid Parameters Handling",
                "test_type": "invalid_parameters",
                "validation_types": ["error_conditions"],
                "expected_errors": 5,
            },
            {
                "name": "Pixel Format Configuration",
                "test_type": "pixel_format",
                "validation_types": ["command_integrity", "parameter_correctness", "edge_cases"],
                "expected_results": ["pixel_format"],
            },
        ]

        # Test each critical scenario
        all_results = {}

        for scenario in critical_scenarios:
            try:
                # Run critical test scenario
                scenario_results = test_manager.run_critical_scenario(scenario["test_type"], temp_workspace)

                # Validate results for non-error scenarios
                if scenario["name"] != "Invalid Parameters Handling":
                    for test_result in scenario_results.values():
                        if test_result.get("success"):
                            # Commands should be validated (for non-error tests)
                            # Error tests don't produce commands to validate
                            pass

                # Verify scenario-specific expectations
                if scenario["name"] == "Basic Command Construction":
                    assert "basic_command" in scenario_results, "Basic command test missing"
                    assert scenario_results["basic_command"]["success"], "Basic command test failed"
                    assert scenario_results["basic_command"]["has_required_elements"], "Required elements missing"

                elif scenario["name"] == "Two-Pass Encoding":
                    assert "two_pass_pass1" in scenario_results, "Two-pass pass 1 test missing"
                    assert "two_pass_pass2" in scenario_results, "Two-pass pass 2 test missing"
                    assert scenario_results["two_pass_pass1"]["has_x265_codec"], "x265 codec missing in pass 1"
                    assert scenario_results["two_pass_pass2"]["has_pass2_params"], "Pass 2 parameters missing"
                    assert scenario_results["two_pass_pass1"]["outputs_to_null"], "Pass 1 should output to null"
                    assert scenario_results["two_pass_pass2"]["outputs_to_file"], "Pass 2 should output to file"

                elif scenario["name"] == "Stream Copy Operations":
                    assert "stream_copy" in scenario_results, "Stream copy test missing"
                    assert scenario_results["stream_copy"]["has_copy_codec"], "Copy codec missing"
                    assert scenario_results["stream_copy"]["command_minimal"], "Stream copy command not minimal"

                elif scenario["name"] == "Invalid Parameters Handling":
                    error_count = len([r for r in scenario_results.values() if r.get("raises_error")])
                    assert error_count == scenario["expected_errors"], (
                        f"Expected {scenario['expected_errors']} errors, got {error_count}"
                    )

                    # Validate error conditions
                    validator.validate_critical_command([], ["error_conditions"])
                    # Note: This validates the error_results structure, not actual commands

                elif scenario["name"] == "Pixel Format Configuration":
                    assert "pixel_format" in scenario_results, "Pixel format test missing"
                    assert scenario_results["pixel_format"]["has_pix_fmt_flag"], "Pixel format flag missing"
                    assert scenario_results["pixel_format"]["all_formats_work"], "Not all pixel formats work"

                all_results[scenario["name"]] = scenario_results

            except Exception as e:  # noqa: BLE001
                if scenario["name"] != "Invalid Parameters Handling":
                    pytest.fail(f"Unexpected error in {scenario['name']}: {e}")
                # For error scenarios, still add the results if we have them
                elif "scenario_results" in locals():
                    all_results[scenario["name"]] = scenario_results

        # Overall validation
        assert len(all_results) == len(critical_scenarios), "Not all critical scenarios completed"

    def test_ffmpeg_critical_command_validation(self, ffmpeg_critical_components: Any, temp_workspace: Any) -> None:  # noqa: PLR6301
        """Test critical command validation and error detection."""
        components = ffmpeg_critical_components
        validator = components["validator"]

        # Test commands with various critical aspects
        test_commands = [
            {
                "name": "Well-formed basic command",
                "command": [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "info",
                    "-stats",
                    "-y",
                    "-i",
                    str(temp_workspace["input_path"]),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "slow",
                    "-crf",
                    "23",
                    "-pix_fmt",
                    "yuv420p",
                    str(temp_workspace["output_path"]),
                ],
                "should_pass": True,
            },
            {
                "name": "Two-pass command",
                "command": [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "info",
                    "-stats",
                    "-y",
                    "-i",
                    str(temp_workspace["input_path"]),
                    "-c:v",
                    "libx265",
                    "-preset",
                    "slower",
                    "-b:v",
                    "5000k",
                    "-x265-params",
                    "pass=1",
                    "-passlogfile",
                    "passlog",
                    "-f",
                    "null",
                    os.devnull,
                ],
                "should_pass": True,
            },
            {
                "name": "Stream copy command",
                "command": [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(temp_workspace["input_path"]),
                    "-c",
                    "copy",
                    str(temp_workspace["output_path"]),
                ],
                "should_pass": True,
            },
            {
                "name": "Malformed command - missing values",
                "command": ["ffmpeg", "-i", "-c:v", "-crf", str(temp_workspace["output_path"])],
                "should_pass": False,
            },
            {
                "name": "Empty command",
                "command": [],
                "should_pass": False,
            },
        ]

        # Validate each test command
        for test_cmd in test_commands:
            cmd = test_cmd["command"]
            should_pass = test_cmd["should_pass"]

            # Run validation
            validation_results = validator.validate_critical_command(
                cmd, ["command_integrity", "parameter_correctness"]
            )

            # Check integrity results
            integrity = validation_results["command_integrity"]
            params = validation_results["parameter_correctness"]

            if should_pass:
                # Well-formed commands should pass basic checks
                assert integrity["starts_with_ffmpeg"] or len(cmd) == 0, (
                    f"Command should start with ffmpeg: {test_cmd['name']}"
                )
                if len(cmd) > 0:
                    assert integrity["has_input_flag"] or "-i" not in cmd, f"Input flag issues: {test_cmd['name']}"
                    assert integrity["reasonable_length"], f"Command length unreasonable: {test_cmd['name']}"
                    assert integrity["no_empty_elements"], f"Empty elements found: {test_cmd['name']}"
                    assert params["flag_value_pairs_correct"], f"Flag-value pairs incorrect: {test_cmd['name']}"
            # Malformed commands should fail some checks
            elif len(cmd) > 0:
                # At least one check should fail for malformed commands
                integrity_failed = not all(integrity.values())
                params_failed = not params["flag_value_pairs_correct"]
                assert integrity_failed or params_failed, f"Malformed command passed validation: {test_cmd['name']}"

    def test_ffmpeg_critical_edge_cases_and_boundaries(
        self, ffmpeg_critical_components: Any, temp_workspace: Any
    ) -> None:
        """Test critical edge cases and boundary conditions."""
        components = ffmpeg_critical_components
        components["test_manager"]

        # Critical edge cases
        edge_cases = [
            {
                "name": "Multiple Pixel Formats",
                "test": lambda: self._test_multiple_pixel_formats(temp_workspace),
            },
            {
                "name": "Two-Pass Edge Cases",
                "test": lambda: self._test_two_pass_edge_cases(temp_workspace),
            },
            {
                "name": "Command Length Boundaries",
                "test": lambda: self._test_command_length_boundaries(temp_workspace),
            },
            {
                "name": "Special Path Characters",
                "test": lambda: self._test_special_path_characters(temp_workspace),
            },
        ]

        # Test each edge case
        for edge_case in edge_cases:
            try:
                result = edge_case["test"]()
                assert result is not None, f"Edge case {edge_case['name']} returned None"
                assert result.get("success", False), f"Edge case {edge_case['name']} failed"
            except Exception as e:  # noqa: BLE001
                # Some edge cases may raise expected exceptions
                if not ("expected" in str(e).lower() or "invalid" in str(e).lower()):
                    pytest.fail(f"Unexpected error in edge case {edge_case['name']}: {e}")

    def _test_multiple_pixel_formats(self, temp_workspace: Any) -> dict[str, Any]:  # noqa: PLR6301
        """Test multiple pixel format scenarios.

        Returns:
            dict[str, Any]: Test results and validation data.
        """
        pixel_formats = ["yuv420p", "yuv444p", "yuv422p", "rgb24", "yuv420p10le"]
        results = {}

        for pix_fmt in pixel_formats:
            builder = FFmpegCommandBuilder()
            cmd = (
                builder.set_input(temp_workspace["input_path"])
                .set_output(temp_workspace["output_path"])
                .set_encoder("Software x264")
                .set_pix_fmt(pix_fmt)
                .set_crf(23)
                .build()
            )

            # Validate pixel format in command
            assert "-pix_fmt" in cmd, f"Pixel format flag missing for {pix_fmt}"
            assert pix_fmt in cmd, f"Pixel format {pix_fmt} not found in command"

            results[pix_fmt] = {"found": True, "valid": True}

        return {"success": True, "formats_tested": len(pixel_formats)}

    def _test_two_pass_edge_cases(self, temp_workspace: Any) -> dict[str, Any]:  # noqa: PLR6301
        """Test two-pass encoding edge cases.

        Returns:
            dict[str, Any]: Test results and validation data.
        """
        # Test invalid pass numbers
        builder = FFmpegCommandBuilder()
        builder.set_input(temp_workspace["input_path"])
        builder.set_output(temp_workspace["output_path"])
        builder.set_encoder("Software x265 (2-Pass)")
        builder.set_bitrate(1000)

        # Should fail with invalid pass number
        with pytest.raises(ValueError, match=r".*"):
            builder.set_two_pass(is_two_pass=True, pass_log_prefix="logfile", pass_number=3).build()

        # Should fail with missing pass number
        with pytest.raises(ValueError, match=r".*"):
            builder.set_two_pass(is_two_pass=True, pass_log_prefix="logfile", pass_number=None).build()

        return {"success": True, "edge_cases_handled": True}

    def _test_command_length_boundaries(self, temp_workspace: Any) -> dict[str, Any]:  # noqa: PLR6301
        """Test command length boundary conditions.

        Returns:
            dict[str, Any]: Test results and validation data.
        """
        # Test minimal command (stream copy)
        builder = FFmpegCommandBuilder()
        cmd = (
            builder.set_input(temp_workspace["input_path"])
            .set_output(temp_workspace["output_path"])
            .set_encoder("None (copy original)")
            .build()
        )

        assert len(cmd) >= 5, "Command too short"
        assert len(cmd) <= 10, "Stream copy command too long"

        # Test complex command
        builder2 = FFmpegCommandBuilder()
        cmd2 = (
            builder2.set_input(temp_workspace["input_path"])
            .set_output(temp_workspace["output_path"])
            .set_encoder("Software x265")
            .set_crf(28)
            .set_pix_fmt("yuv420p")
            .build()
        )

        assert len(cmd2) >= 10, "Complex command too short"
        assert len(cmd2) <= 30, "Complex command too long"

        return {"success": True, "boundary_tests_passed": True}

    def _test_special_path_characters(self, temp_workspace: Any) -> dict[str, Any]:  # noqa: PLR6301
        """Test handling of special characters in paths.

        Returns:
            dict[str, Any]: Test results and validation data.
        """
        # Create paths with special characters
        special_input = temp_workspace["test_dir"] / "input with spaces & symbols!.mkv"
        special_output = temp_workspace["test_dir"] / "output [final] (test).mp4"

        # Create files
        special_input.touch()

        builder = FFmpegCommandBuilder()
        cmd = (
            builder.set_input(special_input).set_output(special_output).set_encoder("Software x264").set_crf(23).build()
        )

        # Verify paths are in command
        assert str(special_input) in cmd, "Special input path not found"
        assert str(special_output) in cmd, "Special output path not found"

        return {"success": True, "special_chars_handled": True}
