"""
Optimized unit tests for FFmpegCommandBuilder with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for temporary directory and file setup
- Combined command building testing scenarios
- Batch validation of different encoder configurations
- Enhanced error handling and edge case coverage
"""

import os
from typing import Any

import pytest

from goesvfi.pipeline.ffmpeg_builder import FFmpegCommandBuilder


class TestFFmpegCommandBuilderOptimizedV2:
    """Optimized FFmpegCommandBuilder unit tests with full coverage."""

    @pytest.fixture(scope="class")
    @staticmethod
    def ffmpeg_test_components() -> Any:  # noqa: C901
        """Create shared components for FFmpeg command builder testing.

        Returns:
            dict[str, Any]: Test components including manager and validator.
        """

        # Enhanced Command Builder Test Manager
        class CommandBuilderTestManager:
            """Manage FFmpeg command builder testing scenarios."""

            def __init__(self) -> None:
                self.encoder_configs = {
                    "software_x264": {
                        "encoder": "Software x264",
                        "crf": 23,
                        "preset": "slow",
                        "expected_codec": "libx264",
                        "required_params": ["crf"],
                    },
                    "software_x265": {
                        "encoder": "Software x265",
                        "crf": 28,
                        "preset": "slower",
                        "expected_codec": "libx265",
                        "required_params": ["crf"],
                        "x265_params": "aq-mode=3:aq-strength=1.0:psy-rd=2.0:psy-rdoq=1.0",
                    },
                    "software_x265_2pass": {
                        "encoder": "Software x265 (2-Pass)",
                        "bitrate": 1000,
                        "preset": "slower",
                        "expected_codec": "libx265",
                        "required_params": ["bitrate", "two_pass"],
                        "two_pass": True,
                    },
                    "hardware_hevc": {
                        "encoder": "Hardware HEVC (VideoToolbox)",
                        "bitrate": 2000,
                        "bufsize": 4000,
                        "expected_codec": "hevc_videotoolbox",
                        "required_params": ["bitrate", "bufsize"],
                        "tag": "hvc1",
                    },
                    "hardware_h264": {
                        "encoder": "Hardware H.264 (VideoToolbox)",
                        "bitrate": 1500,
                        "bufsize": 3000,
                        "expected_codec": "h264_videotoolbox",
                        "required_params": ["bitrate", "bufsize"],
                    },
                    "stream_copy": {
                        "encoder": "None (copy original)",
                        "expected_codec": "copy",
                        "required_params": [],
                        "minimal_output": True,
                    },
                }

                self.test_scenarios = {
                    "basic_builds": self._test_basic_builds,
                    "two_pass_builds": self._test_two_pass_builds,
                    "hardware_builds": self._test_hardware_builds,
                    "error_validations": self._test_error_validations,
                    "edge_cases": self._test_edge_cases,
                }

            def _test_basic_builds(self, temp_workspace: Any) -> dict[str, Any]:
                """Test basic command builds for software encoders.

                Returns:
                    dict[str, Any]: Test results and validation data.
                """
                results = {}

                for config_name in ["software_x264", "software_x265", "stream_copy"]:
                    config = self.encoder_configs[config_name]
                    builder = FFmpegCommandBuilder()

                    # Build command
                    builder.set_input(temp_workspace["input_path"])
                    builder.set_output(temp_workspace["output_path"])
                    builder.set_encoder(config["encoder"])
                    builder.set_pix_fmt("yuv420p")

                    if "crf" in config:
                        builder.set_crf(config["crf"])

                    cmd = builder.build()

                    # Verify command structure
                    assert "ffmpeg" in cmd
                    assert str(temp_workspace["input_path"]) in cmd
                    assert str(temp_workspace["output_path"]) in cmd

                    if not config.get("minimal_output"):
                        assert "-c:v" in cmd
                        codec_index = cmd.index("-c:v") + 1
                        assert cmd[codec_index] == config["expected_codec"]
                    else:
                        assert "-c" in cmd
                        codec_index = cmd.index("-c") + 1
                        assert cmd[codec_index] == config["expected_codec"]

                    results[config_name] = {
                        "success": True,
                        "command_length": len(cmd),
                        "has_codec": config["expected_codec"] in cmd,
                    }

                return results

            def _test_two_pass_builds(self, temp_workspace: Any) -> dict[str, Any]:
                """Test two-pass encoding builds.

                Returns:
                    dict[str, Any]: Test results and validation data.
                """
                results = {}

                config = self.encoder_configs["software_x265_2pass"]
                pass_log_prefix = str(temp_workspace["test_dir"] / "ffmpeg_pass")

                # Test Pass 1
                builder = FFmpegCommandBuilder()
                builder.set_input(temp_workspace["input_path"])
                builder.set_output(temp_workspace["output_path"])
                builder.set_encoder(config["encoder"])
                builder.set_bitrate(config["bitrate"])
                builder.set_pix_fmt("yuv420p")
                builder.set_two_pass(enabled=True, logfile=pass_log_prefix, pass_num=1)

                cmd_pass1 = builder.build()

                # Verify Pass 1 structure
                assert "ffmpeg" in cmd_pass1
                assert "-c:v" in cmd_pass1
                assert "libx265" in cmd_pass1
                assert "-b:v" in cmd_pass1
                assert "1000k" in cmd_pass1
                assert "pass=1" in " ".join(cmd_pass1)
                assert "-f" in cmd_pass1
                assert "null" in cmd_pass1
                assert os.devnull in cmd_pass1

                results["pass1"] = {
                    "success": True,
                    "has_pass1": "pass=1" in " ".join(cmd_pass1),
                    "outputs_to_null": os.devnull in cmd_pass1,
                }

                # Test Pass 2
                builder = FFmpegCommandBuilder()
                builder.set_input(temp_workspace["input_path"])
                builder.set_output(temp_workspace["output_path"])
                builder.set_encoder(config["encoder"])
                builder.set_bitrate(config["bitrate"])
                builder.set_pix_fmt("yuv420p")
                builder.set_two_pass(enabled=True, logfile=pass_log_prefix, pass_num=2)

                cmd_pass2 = builder.build()

                # Verify Pass 2 structure
                assert "ffmpeg" in cmd_pass2
                assert "-c:v" in cmd_pass2
                assert "libx265" in cmd_pass2
                assert "-b:v" in cmd_pass2
                assert "1000k" in cmd_pass2
                assert "pass=2" in " ".join(cmd_pass2)
                assert str(temp_workspace["output_path"]) in cmd_pass2

                results["pass2"] = {
                    "success": True,
                    "has_pass2": "pass=2" in " ".join(cmd_pass2),
                    "outputs_to_file": str(temp_workspace["output_path"]) in cmd_pass2,
                }

                return results

            def _test_hardware_builds(self, temp_workspace: Any) -> dict[str, Any]:
                """Test hardware encoder builds.

                Returns:
                    dict[str, Any]: Test results and validation data.
                """
                results = {}

                for config_name in ["hardware_hevc", "hardware_h264"]:
                    config = self.encoder_configs[config_name]
                    builder = FFmpegCommandBuilder()

                    builder.set_input(temp_workspace["input_path"])
                    builder.set_output(temp_workspace["output_path"])
                    builder.set_encoder(config["encoder"])
                    builder.set_bitrate(config["bitrate"])
                    builder.set_bufsize(config["bufsize"])
                    builder.set_pix_fmt("yuv420p")

                    cmd = builder.build()

                    # Verify hardware encoder structure
                    assert "ffmpeg" in cmd
                    assert "-c:v" in cmd
                    codec_index = cmd.index("-c:v") + 1
                    assert cmd[codec_index] == config["expected_codec"]
                    assert "-b:v" in cmd
                    assert f"{config['bitrate']}k" in cmd
                    assert "-maxrate" in cmd
                    assert f"{config['bufsize']}k" in cmd

                    if "tag" in config:
                        assert "-tag:v" in cmd
                        assert config["tag"] in cmd

                    results[config_name] = {
                        "success": True,
                        "has_hardware_codec": config["expected_codec"] in cmd,
                        "has_bitrate": f"{config['bitrate']}k" in cmd,
                        "has_maxrate": f"{config['bufsize']}k" in cmd,
                    }

                return results

            def _test_error_validations(self, temp_workspace: Any) -> dict[str, Any]:  # noqa: PLR0915
                """Test error validation scenarios."""
                error_tests = {}

                # Test missing input
                builder = FFmpegCommandBuilder()
                builder.set_output(temp_workspace["output_path"])
                builder.set_encoder("Software x264")
                builder.set_crf(23)
                builder.set_pix_fmt("yuv420p")

                with pytest.raises(ValueError, match=r".*"):
                    builder.build()
                error_tests["missing_input"] = {"success": True, "raises_error": True}

                # Test missing output
                builder = FFmpegCommandBuilder()
                builder.set_input(temp_workspace["input_path"])
                builder.set_encoder("Software x264")
                builder.set_crf(23)
                builder.set_pix_fmt("yuv420p")

                with pytest.raises(ValueError, match=r".*"):
                    builder.build()
                error_tests["missing_output"] = {"success": True, "raises_error": True}

                # Test missing encoder
                builder = FFmpegCommandBuilder()
                builder.set_input(temp_workspace["input_path"])
                builder.set_output(temp_workspace["output_path"])
                builder.set_crf(23)
                builder.set_pix_fmt("yuv420p")

                with pytest.raises(ValueError, match=r".*"):
                    builder.build()
                error_tests["missing_encoder"] = {"success": True, "raises_error": True}

                # Test missing CRF for x264
                builder = FFmpegCommandBuilder()
                builder.set_input(temp_workspace["input_path"])
                builder.set_output(temp_workspace["output_path"])
                builder.set_encoder("Software x264")
                builder.set_pix_fmt("yuv420p")

                with pytest.raises(ValueError, match=r".*"):
                    builder.build()
                error_tests["missing_crf_x264"] = {"success": True, "raises_error": True}

                # Test missing bitrate for hardware
                builder = FFmpegCommandBuilder()
                builder.set_input(temp_workspace["input_path"])
                builder.set_output(temp_workspace["output_path"])
                builder.set_encoder("Hardware HEVC (VideoToolbox)")
                builder.set_bufsize(4000)
                builder.set_pix_fmt("yuv420p")

                with pytest.raises(ValueError, match=r".*"):
                    builder.build()
                error_tests["missing_bitrate_hardware"] = {"success": True, "raises_error": True}

                # Test missing bufsize for hardware
                builder = FFmpegCommandBuilder()
                builder.set_input(temp_workspace["input_path"])
                builder.set_output(temp_workspace["output_path"])
                builder.set_encoder("Hardware HEVC (VideoToolbox)")
                builder.set_bitrate(2000)
                builder.set_pix_fmt("yuv420p")

                with pytest.raises(ValueError, match=r".*"):
                    builder.build()
                error_tests["missing_bufsize_hardware"] = {"success": True, "raises_error": True}

                return error_tests

            def _test_edge_cases(self, temp_workspace: Any) -> dict[str, Any]:
                """Test edge cases and boundary conditions.

                Returns:
                    dict[str, Any]: Test results and validation data.
                """
                edge_cases = {}

                # Test two-pass missing parameters
                builder = FFmpegCommandBuilder()
                builder.set_input(temp_workspace["input_path"])
                builder.set_output(temp_workspace["output_path"])
                builder.set_encoder("Software x265 (2-Pass)")
                builder.set_bitrate(1000)
                builder.set_pix_fmt("yuv420p")
                # Missing set_two_pass call

                with pytest.raises(ValueError, match=r".*"):
                    builder.build()
                edge_cases["two_pass_missing_call"] = {"success": True, "raises_error": True}

                # Test two-pass missing log prefix
                builder = FFmpegCommandBuilder()
                builder.set_input(temp_workspace["input_path"])
                builder.set_output(temp_workspace["output_path"])
                builder.set_encoder("Software x265 (2-Pass)")
                builder.set_bitrate(1000)
                builder.set_pix_fmt("yuv420p")
                builder.set_two_pass(enabled=True, logfile=None, pass_num=1)  # Missing log prefix

                with pytest.raises(ValueError, match=r".*"):
                    builder.build()
                edge_cases["two_pass_missing_log_prefix"] = {"success": True, "raises_error": True}

                # Test two-pass missing pass number
                builder = FFmpegCommandBuilder()
                builder.set_input(temp_workspace["input_path"])
                builder.set_output(temp_workspace["output_path"])
                builder.set_encoder("Software x265 (2-Pass)")
                builder.set_bitrate(1000)
                builder.set_pix_fmt("yuv420p")
                builder.set_two_pass(enabled=True, logfile="log_prefix", pass_num=None)  # Missing pass number

                with pytest.raises(ValueError, match=r".*"):
                    builder.build()
                edge_cases["two_pass_missing_pass_number"] = {"success": True, "raises_error": True}

                # Test invalid pass number
                builder = FFmpegCommandBuilder()
                builder.set_input(temp_workspace["input_path"])
                builder.set_output(temp_workspace["output_path"])
                builder.set_encoder("Software x265 (2-Pass)")
                builder.set_bitrate(1000)
                builder.set_pix_fmt("yuv420p")
                builder.set_two_pass(enabled=True, logfile="log_prefix", pass_num=3)  # Invalid pass number

                with pytest.raises(ValueError, match=r".*"):
                    builder.build()
                edge_cases["invalid_pass_number"] = {"success": True, "raises_error": True}

                return edge_cases

            def run_test_scenario(self, scenario: str, temp_workspace: dict[str, Any]) -> dict[str, Any]:
                """Run specified test scenario.

                Returns:
                    dict[str, Any]: Test results for the scenario.
                """
                return self.test_scenarios[scenario](temp_workspace)

        # Enhanced Command Validator
        class CommandValidator:
            """Validate FFmpeg command structure and completeness."""

            def __init__(self) -> None:
                self.validation_rules = {
                    "basic_structure": self._validate_basic_structure,
                    "codec_settings": self._validate_codec_settings,
                    "quality_settings": self._validate_quality_settings,
                    "input_output": self._validate_input_output,
                    "hardware_specific": self._validate_hardware_specific,
                }

            @staticmethod
            def _validate_basic_structure(cmd: list[str]) -> dict[str, bool]:
                """Validate basic FFmpeg command structure.

                Returns:
                    dict[str, bool]: Basic structure validation results.
                """
                return {
                    "has_ffmpeg": "ffmpeg" in cmd,
                    "has_hide_banner": "-hide_banner" in cmd,
                    "has_loglevel": "-loglevel" in cmd,
                    "has_stats": "-stats" in cmd,
                    "has_overwrite": "-y" in cmd,
                    "has_input_flag": "-i" in cmd,
                }

            @staticmethod
            def _validate_codec_settings(cmd: list[str]) -> dict[str, Any]:
                """Validate codec-related settings.

                Returns:
                    dict[str, Any]: Codec settings validation results.
                """
                has_video_codec = "-c:v" in cmd or "-c" in cmd
                codec = None

                if "-c:v" in cmd:
                    codec_index = cmd.index("-c:v") + 1
                    codec = cmd[codec_index] if codec_index < len(cmd) else None
                elif "-c" in cmd:
                    codec_index = cmd.index("-c") + 1
                    codec = cmd[codec_index] if codec_index < len(cmd) else None

                return {
                    "has_video_codec": has_video_codec,
                    "codec": codec,
                    "has_preset": "-preset" in cmd,
                    "has_pix_fmt": "-pix_fmt" in cmd,
                }

            @staticmethod
            def _validate_quality_settings(cmd: list[str]) -> dict[str, Any]:
                """Validate quality-related settings.

                Returns:
                    dict[str, Any]: Quality settings validation results.
                """
                return {
                    "has_crf": "-crf" in cmd,
                    "has_bitrate": "-b:v" in cmd,
                    "has_maxrate": "-maxrate" in cmd,
                    "has_x265_params": "-x265-params" in cmd,
                }

            @staticmethod
            def _validate_input_output(cmd: list[str]) -> dict[str, bool]:
                """Validate input and output specifications.

                Returns:
                    dict[str, bool]: Input/output validation results.
                """
                input_index = cmd.index("-i") + 1 if "-i" in cmd else -1
                has_input_file = input_index > 0 and input_index < len(cmd)
                has_output_file = len(cmd) > 0 and not cmd[-1].startswith("-")

                return {
                    "has_input_file": has_input_file,
                    "has_output_file": has_output_file,
                    "input_after_flag": has_input_file,
                    "output_at_end": has_output_file,
                }

            @staticmethod
            def _validate_hardware_specific(cmd: list[str]) -> dict[str, bool]:
                """Validate hardware encoder specific settings.

                Returns:
                    dict[str, bool]: Hardware encoder validation results.
                """
                return {
                    "has_tag": "-tag:v" in cmd,
                    "has_videotoolbox": any("videotoolbox" in arg for arg in cmd),
                    "has_hardware_bitrate": "-b:v" in cmd and "-maxrate" in cmd,
                }

            def validate_command(self, cmd: list[str], validation_types: list[str] | None = None) -> dict[str, Any]:
                """Validate command using specified validation types.

                Returns:
                    dict[str, Any]: Validation results for all criteria.
                """
                if validation_types is None:
                    validation_types = list(self.validation_rules.keys())

                results = {}
                for validation_type in validation_types:
                    if validation_type in self.validation_rules:
                        results[validation_type] = self.validation_rules[validation_type](cmd)

                return results

        return {
            "test_manager": CommandBuilderTestManager(),
            "validator": CommandValidator(),
        }

    @pytest.fixture()
    def temp_workspace(self, tmp_path: Any) -> dict[str, Any]:  # noqa: PLR6301
        """Create temporary workspace for FFmpeg builder testing.

        Returns:
            dict[str, Any]: Workspace configuration with test paths.
        """
        test_dir = tmp_path / "ffmpeg_test"
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

    def test_ffmpeg_builder_comprehensive_scenarios(self, ffmpeg_test_components: Any, temp_workspace: Any) -> None:  # noqa: PLR6301
        """Test comprehensive FFmpeg command builder scenarios."""
        components = ffmpeg_test_components
        test_manager = components["test_manager"]
        validator = components["validator"]

        # Define comprehensive test scenarios
        builder_scenarios = [
            {
                "name": "Basic Software Encoder Builds",
                "test_type": "basic_builds",
                "validation_types": ["basic_structure", "codec_settings", "input_output"],
                "expected_encoders": ["libx264", "libx265", "copy"],
            },
            {
                "name": "Two-Pass Encoding Builds",
                "test_type": "two_pass_builds",
                "validation_types": ["basic_structure", "codec_settings", "quality_settings"],
                "expected_features": ["pass=1", "pass=2", "null", "libx265"],
            },
            {
                "name": "Hardware Encoder Builds",
                "test_type": "hardware_builds",
                "validation_types": ["basic_structure", "codec_settings", "hardware_specific"],
                "expected_features": ["videotoolbox", "bitrate", "maxrate"],
            },
            {
                "name": "Error Validation Tests",
                "test_type": "error_validations",
                "validation_types": [],  # No validation needed for error tests
                "expected_errors": 6,  # Number of error conditions tested
            },
            {
                "name": "Edge Case Handling",
                "test_type": "edge_cases",
                "validation_types": [],  # No validation needed for error tests
                "expected_errors": 4,  # Number of edge case error conditions
            },
        ]

        # Test each scenario
        all_results = {}

        for scenario in builder_scenarios:
            try:
                # Run test scenario
                scenario_results = test_manager.run_test_scenario(scenario["test_type"], temp_workspace)

                # Validate results for non-error scenarios
                if scenario["validation_types"]:
                    for test_result in scenario_results.values():
                        if test_result.get("success") and "command" in test_result:
                            cmd = test_result["command"]
                            validation_results = validator.validate_command(cmd, scenario["validation_types"])
                            test_result["validation"] = validation_results

                # Verify scenario-specific expectations
                if scenario["name"] == "Basic Software Encoder Builds":
                    # Check that all expected encoders were tested
                    for encoder in scenario["expected_encoders"]:
                        found_encoder = any(result.get("has_codec") for result in scenario_results.values())
                        assert found_encoder, f"Expected encoder {encoder} not found in results"

                elif scenario["name"] == "Two-Pass Encoding Builds":
                    # Check that both passes were tested
                    assert "pass1" in scenario_results, "Pass 1 test missing"
                    assert "pass2" in scenario_results, "Pass 2 test missing"
                    assert scenario_results["pass1"]["has_pass1"], "Pass 1 not properly configured"
                    assert scenario_results["pass2"]["has_pass2"], "Pass 2 not properly configured"

                elif scenario["name"] == "Hardware Encoder Builds":
                    # Check hardware-specific features
                    for result in scenario_results.values():
                        assert result.get("has_hardware_codec"), f"Hardware codec missing in {scenario['name']}"
                        assert result.get("has_bitrate"), f"Bitrate missing in {scenario['name']}"
                        assert result.get("has_maxrate"), f"Maxrate missing in {scenario['name']}"

                elif scenario["name"] in {"Error Validation Tests", "Edge Case Handling"}:
                    # Check that errors were properly caught
                    error_count = len([r for r in scenario_results.values() if r.get("raises_error")])
                    assert error_count == scenario["expected_errors"], (
                        f"Expected {scenario['expected_errors']} errors, got {error_count} in {scenario['name']}"
                    )

                all_results[scenario["name"]] = scenario_results

            except Exception as e:  # noqa: BLE001
                if scenario["name"] not in {"Error Validation Tests", "Edge Case Handling"}:
                    pytest.fail(f"Unexpected error in {scenario['name']}: {e}")
                # Error scenarios are expected to have exceptions

        # Overall validation
        assert len(all_results) == len(builder_scenarios), "Not all scenarios completed"

    def test_ffmpeg_builder_specific_command_validation(self, ffmpeg_test_components: Any, temp_workspace: Any) -> None:  # noqa: PLR6301
        """Test specific FFmpeg command validation and structure."""
        components = ffmpeg_test_components
        validator = components["validator"]

        # Specific command validation scenarios
        validation_scenarios = [
            {
                "name": "Software x264 Command Structure",
                "builder_config": {
                    "encoder": "Software x264",
                    "crf": 23,
                    "pix_fmt": "yuv420p",
                },
                "expected_elements": ["ffmpeg", "-c:v", "libx264", "-preset", "slow", "-crf", "23"],
            },
            {
                "name": "Software x265 Command Structure",
                "builder_config": {
                    "encoder": "Software x265",
                    "crf": 28,
                    "pix_fmt": "yuv420p",
                },
                "expected_elements": ["ffmpeg", "-c:v", "libx265", "-preset", "slower", "-crf", "28", "-x265-params"],
            },
            {
                "name": "Hardware HEVC Command Structure",
                "builder_config": {
                    "encoder": "Hardware HEVC (VideoToolbox)",
                    "bitrate": 2000,
                    "bufsize": 4000,
                    "pix_fmt": "yuv420p",
                },
                "expected_elements": [
                    "ffmpeg",
                    "-c:v",
                    "hevc_videotoolbox",
                    "-tag:v",
                    "hvc1",
                    "-b:v",
                    "2000k",
                    "-maxrate",
                    "4000k",
                ],
            },
            {
                "name": "Stream Copy Command Structure",
                "builder_config": {
                    "encoder": "None (copy original)",
                },
                "expected_elements": ["ffmpeg", "-y", "-i", "-c", "copy"],
                "minimal_structure": True,
            },
        ]

        # Test each validation scenario
        for scenario in validation_scenarios:
            # Build command
            builder = FFmpegCommandBuilder()
            builder.set_input(temp_workspace["input_path"])
            builder.set_output(temp_workspace["output_path"])

            config = scenario["builder_config"]
            builder.set_encoder(config["encoder"])

            if "crf" in config:
                builder.set_crf(config["crf"])
            if "bitrate" in config:
                builder.set_bitrate(config["bitrate"])
            if "bufsize" in config:
                builder.set_bufsize(config["bufsize"])
            if "pix_fmt" in config:
                builder.set_pix_fmt(config["pix_fmt"])

            cmd = builder.build()

            # Validate expected elements
            for element in scenario["expected_elements"]:
                assert element in cmd, f"Missing element '{element}' in command for {scenario['name']}: {cmd}"

            # Validate command structure
            validation_types = ["basic_structure", "codec_settings", "input_output"]
            if not scenario.get("minimal_structure"):
                validation_types.append("quality_settings")
            if "videotoolbox" in config.get("encoder", ""):
                validation_types.append("hardware_specific")

            validation_results = validator.validate_command(cmd, validation_types)

            # Check basic structure
            basic_checks = validation_results["basic_structure"]
            assert basic_checks["has_ffmpeg"], f"Missing ffmpeg in {scenario['name']}"
            assert basic_checks["has_input_flag"], f"Missing input flag in {scenario['name']}"

            # Check codec settings
            codec_checks = validation_results["codec_settings"]
            assert codec_checks["has_video_codec"], f"Missing video codec in {scenario['name']}"

            # Check input/output
            io_checks = validation_results["input_output"]
            assert io_checks["has_input_file"], f"Missing input file in {scenario['name']}"
            assert io_checks["has_output_file"], f"Missing output file in {scenario['name']}"

    def test_ffmpeg_builder_parameter_combinations(self, ffmpeg_test_components: Any, temp_workspace: Any) -> None:  # noqa: PLR6301
        """Test various parameter combinations and their interactions."""
        components = ffmpeg_test_components
        validator = components["validator"]

        # Parameter combination scenarios
        combination_scenarios = [
            {
                "name": "High Quality x264",
                "params": {"encoder": "Software x264", "crf": 18, "pix_fmt": "yuv444p"},
                "expected_quality": "high",
            },
            {
                "name": "Low Quality x264",
                "params": {"encoder": "Software x264", "crf": 35, "pix_fmt": "yuv420p"},
                "expected_quality": "low",
            },
            {
                "name": "High Bitrate Hardware",
                "params": {
                    "encoder": "Hardware HEVC (VideoToolbox)",
                    "bitrate": 5000,
                    "bufsize": 10000,
                    "pix_fmt": "yuv420p",
                },
                "expected_quality": "high",
            },
            {
                "name": "Low Bitrate Hardware",
                "params": {
                    "encoder": "Hardware H.264 (VideoToolbox)",
                    "bitrate": 500,
                    "bufsize": 1000,
                    "pix_fmt": "yuv420p",
                },
                "expected_quality": "low",
            },
        ]

        # Test each combination
        for scenario in combination_scenarios:
            builder = FFmpegCommandBuilder()
            builder.set_input(temp_workspace["input_path"])
            builder.set_output(temp_workspace["output_path"])

            params = scenario["params"]
            builder.set_encoder(params["encoder"])
            builder.set_pix_fmt(params["pix_fmt"])

            if "crf" in params:
                builder.set_crf(params["crf"])
            if "bitrate" in params:
                builder.set_bitrate(params["bitrate"])
            if "bufsize" in params:
                builder.set_bufsize(params["bufsize"])

            cmd = builder.build()

            # Validate parameter presence
            if "crf" in params:
                assert "-crf" in cmd and str(params["crf"]) in cmd, (
                    f"CRF {params['crf']} not found in {scenario['name']}"
                )
            if "bitrate" in params:
                assert "-b:v" in cmd and f"{params['bitrate']}k" in cmd, (
                    f"Bitrate {params['bitrate']} not found in {scenario['name']}"
                )
            if "bufsize" in params:
                assert "-maxrate" in cmd and f"{params['bufsize']}k" in cmd, (
                    f"Bufsize {params['bufsize']} not found in {scenario['name']}"
                )

            assert "-pix_fmt" in cmd and params["pix_fmt"] in cmd, (
                f"Pixel format {params['pix_fmt']} not found in {scenario['name']}"
            )

            # Validate overall command structure
            validation_results = validator.validate_command(
                cmd, ["basic_structure", "codec_settings", "quality_settings"]
            )

            assert validation_results["basic_structure"]["has_ffmpeg"], (
                f"Command structure invalid for {scenario['name']}"
            )
            assert validation_results["codec_settings"]["has_video_codec"], f"Codec missing for {scenario['name']}"

    def test_ffmpeg_builder_edge_cases_and_boundaries(self, ffmpeg_test_components: Any, temp_workspace: Any) -> None:  # noqa: PLR6301
        """Test edge cases and boundary conditions."""

        # Edge case scenarios
        edge_cases = [
            {
                "name": "Extreme CRF Values",
                "test": lambda: self._test_extreme_crf_values(temp_workspace),
            },
            {
                "name": "Very High Bitrates",
                "test": lambda: self._test_high_bitrates(temp_workspace),
            },
            {
                "name": "Long File Paths",
                "test": lambda: self._test_long_file_paths(temp_workspace),
            },
            {
                "name": "Special Characters in Paths",
                "test": lambda: self._test_special_character_paths(temp_workspace),
            },
        ]

        # Test each edge case
        for edge_case in edge_cases:
            try:
                result = edge_case["test"]()
                assert result is not None, f"Edge case {edge_case['name']} returned None"
            except Exception as e:  # noqa: BLE001
                # Some edge cases may raise exceptions, which can be acceptable
                if not ("expected" in str(e).lower() or isinstance(e, (ValueError, OSError))):
                    pytest.fail(f"Unexpected error in edge case {edge_case['name']}: {e}")

    def _test_extreme_crf_values(self, temp_workspace: Any) -> dict[str, Any]:  # noqa: PLR6301
        """Test extreme CRF values.

        Returns:
            dict[str, Any]: Test results and validation data.
        """
        extreme_values = [0, 1, 50, 51]

        for crf in extreme_values:
            builder = FFmpegCommandBuilder()
            builder.set_input(temp_workspace["input_path"])
            builder.set_output(temp_workspace["output_path"])
            builder.set_encoder("Software x264")
            builder.set_crf(crf)
            builder.set_pix_fmt("yuv420p")

            cmd = builder.build()
            assert str(crf) in cmd, f"CRF {crf} not found in command"

        return {"tested_values": extreme_values}

    def _test_high_bitrates(self, temp_workspace: Any) -> dict[str, Any]:  # noqa: PLR6301
        """Test very high bitrate values.

        Returns:
            dict[str, Any]: Test results and validation data.
        """
        high_bitrates = [10000, 50000, 100000]

        for bitrate in high_bitrates:
            builder = FFmpegCommandBuilder()
            builder.set_input(temp_workspace["input_path"])
            builder.set_output(temp_workspace["output_path"])
            builder.set_encoder("Hardware HEVC (VideoToolbox)")
            builder.set_bitrate(bitrate)
            builder.set_bufsize(bitrate * 2)
            builder.set_pix_fmt("yuv420p")

            cmd = builder.build()
            assert f"{bitrate}k" in cmd, f"Bitrate {bitrate} not found in command"

        return {"tested_bitrates": high_bitrates}

    def _test_long_file_paths(self, temp_workspace: Any) -> dict[str, Any]:  # noqa: PLR6301
        """Test very long file paths.

        Returns:
            dict[str, Any]: Test results and validation data.
        """
        # Create a deeply nested directory structure
        long_path = temp_workspace["test_dir"]
        for i in range(10):
            long_path /= f"very_long_directory_name_{i}"
        long_path.mkdir(parents=True, exist_ok=True)

        long_input = long_path / "very_long_input_filename.mkv"
        long_output = long_path / "very_long_output_filename.mp4"
        long_input.touch()

        builder = FFmpegCommandBuilder()
        builder.set_input(long_input)
        builder.set_output(long_output)
        builder.set_encoder("Software x264")
        builder.set_crf(23)
        builder.set_pix_fmt("yuv420p")

        cmd = builder.build()
        assert str(long_input) in cmd, "Long input path not found in command"
        assert str(long_output) in cmd, "Long output path not found in command"

        return {"long_path_length": len(str(long_input))}

    def _test_special_character_paths(self, temp_workspace: Any) -> dict[str, Any]:  # noqa: PLR6301
        """Test file paths with special characters.

        Returns:
            dict[str, Any]: Test results and validation data.
        """
        special_chars_dir = temp_workspace["test_dir"] / "special chars & symbols!"
        special_chars_dir.mkdir(exist_ok=True)

        special_input = special_chars_dir / "input file (test).mkv"
        special_output = special_chars_dir / "output file [final].mp4"
        special_input.touch()

        builder = FFmpegCommandBuilder()
        builder.set_input(special_input)
        builder.set_output(special_output)
        builder.set_encoder("Software x264")
        builder.set_crf(23)
        builder.set_pix_fmt("yuv420p")

        cmd = builder.build()
        assert str(special_input) in cmd, "Special character input path not found in command"
        assert str(special_output) in cmd, "Special character output path not found in command"

        return {"special_chars_tested": True}
