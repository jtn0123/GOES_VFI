"""Optimized critical FFmpeg builder tests to speed up slow tests while maintaining coverage.

Optimizations applied:
- Shared fixtures for common builder setups and command configurations
- Parameterized test scenarios for comprehensive FFmpeg command validation
- Enhanced error handling and edge case testing
- Mock-based testing to avoid actual FFmpeg execution
- Comprehensive encoder configuration and parameter testing
"""

from pathlib import Path
from unittest.mock import patch, Mock
import pytest

from goesvfi.pipeline.ffmpeg_builder import FFmpegCommandBuilder


class TestFFmpegBuilderCriticalV2:
    """Optimized test class for critical FFmpeg builder functionality."""

    @pytest.fixture(scope="class")
    def encoder_configurations(self):
        """Define various encoder configuration test cases."""
        return {
            "software_x264": {
                "encoder": "Software x264",
                "expected_codec": "libx264",
                "supports_crf": True,
                "supports_two_pass": False,
                "quality_range": (0, 51),
            },
            "software_x265": {
                "encoder": "Software x265",
                "expected_codec": "libx265",
                "supports_crf": True,
                "supports_two_pass": False,
                "quality_range": (0, 51),
            },
            "software_x265_two_pass": {
                "encoder": "Software x265 (2-Pass)",
                "expected_codec": "libx265",
                "supports_crf": False,
                "supports_two_pass": True,
                "quality_range": None,
            },
            "hardware_nvenc": {
                "encoder": "NVIDIA NVENC H.264",
                "expected_codec": "h264_nvenc",
                "supports_crf": True,
                "supports_two_pass": False,
                "quality_range": (0, 51),
            },
            "hardware_videotoolbox": {
                "encoder": "Apple VideoToolbox H.264",
                "expected_codec": "h264_videotoolbox",
                "supports_crf": True,
                "supports_two_pass": False,
                "quality_range": (0, 100),
            },
            "copy_stream": {
                "encoder": "None (copy original)",
                "expected_codec": "copy",
                "supports_crf": False,
                "supports_two_pass": False,
                "quality_range": None,
            },
        }

    @pytest.fixture(scope="class")
    def command_scenarios(self):
        """Define various command building scenario test cases."""
        return {
            "basic_encoding": {
                "input": Path("/test/frames/frame_%04d.png"),
                "output": Path("/test/output.mp4"),
                "encoder": "Software x264",
                "crf": 23,
                "expected_elements": ["ffmpeg", "-i", "/test/frames/frame_%04d.png", "-c:v", "libx264", "-crf", "23"],
            },
            "high_quality_encoding": {
                "input": Path("/test/input.mp4"),
                "output": Path("/test/high_quality.mp4"),
                "encoder": "Software x265",
                "crf": 18,
                "pix_fmt": "yuv420p10le",
                "expected_elements": ["ffmpeg", "-i", "/test/input.mp4", "-c:v", "libx265", "-crf", "18", "-pix_fmt", "yuv420p10le"],
            },
            "two_pass_encoding": {
                "input": Path("/test/input.mp4"),
                "output": Path("/test/two_pass.mp4"),
                "encoder": "Software x265 (2-Pass)",
                "bitrate": 5000,
                "two_pass": {"enabled": True, "passlog": "test_passlog", "pass_num": 1},
                "expected_elements": ["ffmpeg", "-i", "/test/input.mp4", "-c:v", "libx265", "-b:v", "5000k", "-x265-params", "pass=1", "-passlogfile", "test_passlog"],
            },
            "copy_stream": {
                "input": Path("/test/input.mp4"),
                "output": Path("/test/copy.mp4"),
                "encoder": "None (copy original)",
                "expected_elements": ["ffmpeg", "-i", "/test/input.mp4", "-c", "copy"],
            },
            "nvenc_encoding": {
                "input": Path("/test/input.mp4"),
                "output": Path("/test/nvenc.mp4"),
                "encoder": "NVIDIA NVENC H.264",
                "crf": 20,
                "preset": "p4",
                "expected_elements": ["ffmpeg", "-i", "/test/input.mp4", "-c:v", "h264_nvenc", "-crf", "20", "-preset", "p4"],
            },
        }

    @pytest.fixture(scope="class")
    def validation_scenarios(self):
        """Define various validation scenario test cases."""
        return {
            "missing_input": {
                "setup": {"output": Path("/test/output.mp4"), "encoder": "Software x264"},
                "expected_error": "Input path, output path, and encoder must be set",
            },
            "missing_output": {
                "setup": {"input": Path("/test/input.mp4"), "encoder": "Software x264"},
                "expected_error": "Input path, output path, and encoder must be set",
            },
            "missing_encoder": {
                "setup": {"input": Path("/test/input.mp4"), "output": Path("/test/output.mp4")},
                "expected_error": "Input path, output path, and encoder must be set",
            },
            "two_pass_missing_bitrate": {
                "setup": {
                    "input": Path("/test/input.mp4"),
                    "output": Path("/test/output.mp4"),
                    "encoder": "Software x265 (2-Pass)",
                    "two_pass": {"enabled": True, "passlog": "test", "pass_num": 1},
                },
                "expected_error": "Two-pass encoding requires",
            },
            "two_pass_missing_passlog": {
                "setup": {
                    "input": Path("/test/input.mp4"),
                    "output": Path("/test/output.mp4"),
                    "encoder": "Software x265 (2-Pass)",
                    "bitrate": 5000,
                    "two_pass": {"enabled": True, "pass_num": 1},
                },
                "expected_error": "Two-pass encoding requires",
            },
            "invalid_crf_negative": {
                "setup": {
                    "input": Path("/test/input.mp4"),
                    "output": Path("/test/output.mp4"),
                    "encoder": "Software x264",
                    "crf": -5,
                },
                "expected_error": "CRF value must be between",
            },
            "invalid_crf_too_high": {
                "setup": {
                    "input": Path("/test/input.mp4"),
                    "output": Path("/test/output.mp4"),
                    "encoder": "Software x264",
                    "crf": 100,
                },
                "expected_error": "CRF value must be between",
            },
        }

    @pytest.fixture
    def ffmpeg_builder(self):
        """Create FFmpegCommandBuilder instance for testing."""
        return FFmpegCommandBuilder()

    @pytest.fixture
    def mock_path_operations(self):
        """Mock path operations to avoid filesystem interactions."""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.is_file", return_value=True):
                with patch("pathlib.Path.is_dir", return_value=True):
                    yield

    @pytest.mark.parametrize("encoder_name", [
        "software_x264",
        "software_x265", 
        "software_x265_two_pass",
        "hardware_nvenc",
        "hardware_videotoolbox",
        "copy_stream",
    ])
    def test_encoder_configuration_scenarios(self, ffmpeg_builder, encoder_configurations, 
                                           mock_path_operations, encoder_name):
        """Test various encoder configuration scenarios."""
        config = encoder_configurations[encoder_name]
        
        builder = (ffmpeg_builder
                  .set_input(Path("/test/input.mp4"))
                  .set_output(Path("/test/output.mp4"))
                  .set_encoder(config["encoder"]))
        
        if config["supports_crf"] and config["quality_range"]:
            # Test with middle quality value
            mid_quality = config["quality_range"][0] + (config["quality_range"][1] - config["quality_range"][0]) // 2
            builder.set_crf(mid_quality)
        
        if config["supports_two_pass"]:
            builder.set_bitrate(5000).set_two_pass(True, "test_passlog", 1)
        
        # Build command
        cmd = builder.build()
        
        # Verify basic structure
        assert isinstance(cmd, str)
        assert "ffmpeg" in cmd
        assert "-i" in cmd
        assert "/test/input.mp4" in cmd
        
        # Verify codec selection
        if config["expected_codec"] == "copy":
            assert "-c copy" in cmd or "-c:v copy" in cmd
        else:
            assert f"-c:v {config['expected_codec']}" in cmd

    @pytest.mark.parametrize("scenario_name", [
        "basic_encoding",
        "high_quality_encoding",
        "two_pass_encoding",
        "copy_stream",
        "nvenc_encoding",
    ])
    def test_command_building_scenarios(self, ffmpeg_builder, command_scenarios, 
                                      mock_path_operations, scenario_name):
        """Test comprehensive command building scenarios."""
        scenario = command_scenarios[scenario_name]
        
        builder = (ffmpeg_builder
                  .set_input(scenario["input"])
                  .set_output(scenario["output"])
                  .set_encoder(scenario["encoder"]))
        
        # Apply optional parameters
        if "crf" in scenario:
            builder.set_crf(scenario["crf"])
        if "pix_fmt" in scenario:
            builder.set_pix_fmt(scenario["pix_fmt"])
        if "bitrate" in scenario:
            builder.set_bitrate(scenario["bitrate"])
        if "preset" in scenario:
            builder.set_preset(scenario["preset"])
        if "two_pass" in scenario:
            tp = scenario["two_pass"]
            builder.set_two_pass(tp["enabled"], tp["passlog"], tp["pass_num"])
        
        # Build and verify command
        cmd = builder.build()
        
        # Check all expected elements are present
        for element in scenario["expected_elements"]:
            assert str(element) in cmd

    @pytest.mark.parametrize("validation_case", [
        "missing_input",
        "missing_output",
        "missing_encoder",
        "two_pass_missing_bitrate",
        "two_pass_missing_passlog",
        "invalid_crf_negative",
        "invalid_crf_too_high",
    ])
    def test_validation_error_scenarios(self, ffmpeg_builder, validation_scenarios, 
                                      mock_path_operations, validation_case):
        """Test various validation error scenarios."""
        scenario = validation_scenarios[validation_case]
        setup = scenario["setup"]
        
        # Apply setup parameters
        if "input" in setup:
            ffmpeg_builder.set_input(setup["input"])
        if "output" in setup:
            ffmpeg_builder.set_output(setup["output"])
        if "encoder" in setup:
            ffmpeg_builder.set_encoder(setup["encoder"])
        if "crf" in setup:
            ffmpeg_builder.set_crf(setup["crf"])
        if "bitrate" in setup:
            ffmpeg_builder.set_bitrate(setup["bitrate"])
        if "two_pass" in setup:
            tp = setup["two_pass"]
            ffmpeg_builder.set_two_pass(
                tp["enabled"], 
                tp.get("passlog"), 
                tp["pass_num"]
            )
        
        # Verify expected error is raised
        with pytest.raises(ValueError, match=scenario["expected_error"]):
            ffmpeg_builder.build()

    def test_builder_method_chaining(self, ffmpeg_builder, mock_path_operations):
        """Test that all builder methods support chaining."""
        # Test comprehensive method chaining
        cmd = (ffmpeg_builder
               .set_input(Path("/test/input.mp4"))
               .set_output(Path("/test/output.mp4"))
               .set_encoder("Software x264")
               .set_crf(23)
               .set_pix_fmt("yuv420p")
               .set_preset("medium")
               .set_tune("film")
               .build())
        
        # Verify all parameters are included
        assert "ffmpeg" in cmd
        assert "-i /test/input.mp4" in cmd
        assert "-c:v libx264" in cmd
        assert "-crf 23" in cmd
        assert "-pix_fmt yuv420p" in cmd
        assert "-preset medium" in cmd
        assert "-tune film" in cmd
        assert "/test/output.mp4" in cmd

    @pytest.mark.parametrize("crf_value,encoder", [
        (0, "Software x264"),
        (18, "Software x264"),
        (23, "Software x264"),
        (51, "Software x264"),
        (0, "Software x265"),
        (28, "Software x265"),
        (51, "Software x265"),
        (0, "NVIDIA NVENC H.264"),
        (25, "NVIDIA NVENC H.264"),
        (51, "NVIDIA NVENC H.264"),
    ])
    def test_crf_value_boundaries(self, ffmpeg_builder, mock_path_operations, crf_value, encoder):
        """Test CRF value boundaries for different encoders."""
        cmd = (ffmpeg_builder
               .set_input(Path("/test/input.mp4"))
               .set_output(Path("/test/output.mp4"))
               .set_encoder(encoder)
               .set_crf(crf_value)
               .build())
        
        assert f"-crf {crf_value}" in cmd

    def test_two_pass_encoding_both_passes(self, ffmpeg_builder, mock_path_operations):
        """Test two-pass encoding for both passes."""
        base_setup = (ffmpeg_builder
                     .set_input(Path("/test/input.mp4"))
                     .set_output(Path("/test/output.mp4"))
                     .set_encoder("Software x265 (2-Pass)")
                     .set_bitrate(5000))
        
        # Test first pass
        first_pass_cmd = base_setup.set_two_pass(True, "test_passlog", 1).build()
        assert "-x265-params pass=1" in first_pass_cmd
        assert "-passlogfile test_passlog" in first_pass_cmd
        assert "-b:v 5000k" in first_pass_cmd
        
        # Test second pass
        second_pass_cmd = (FFmpegCommandBuilder()
                          .set_input(Path("/test/input.mp4"))
                          .set_output(Path("/test/output.mp4"))
                          .set_encoder("Software x265 (2-Pass)")
                          .set_bitrate(5000)
                          .set_two_pass(True, "test_passlog", 2)
                          .build())
        assert "-x265-params pass=2" in second_pass_cmd
        assert "-passlogfile test_passlog" in second_pass_cmd
        assert "-b:v 5000k" in second_pass_cmd

    @pytest.mark.parametrize("pixel_format", [
        "yuv420p",
        "yuv422p",
        "yuv444p",
        "yuv420p10le",
        "yuv422p10le",
        "yuv444p10le",
        "rgb24",
        "rgba",
    ])
    def test_pixel_format_options(self, ffmpeg_builder, mock_path_operations, pixel_format):
        """Test various pixel format options."""
        cmd = (ffmpeg_builder
               .set_input(Path("/test/input.mp4"))
               .set_output(Path("/test/output.mp4"))
               .set_encoder("Software x264")
               .set_pix_fmt(pixel_format)
               .set_crf(23)
               .build())
        
        assert f"-pix_fmt {pixel_format}" in cmd

    @pytest.mark.parametrize("preset", [
        "ultrafast",
        "superfast", 
        "veryfast",
        "faster",
        "fast",
        "medium",
        "slow",
        "slower",
        "veryslow",
    ])
    def test_preset_options(self, ffmpeg_builder, mock_path_operations, preset):
        """Test various preset options."""
        cmd = (ffmpeg_builder
               .set_input(Path("/test/input.mp4"))
               .set_output(Path("/test/output.mp4"))
               .set_encoder("Software x264")
               .set_preset(preset)
               .set_crf(23)
               .build())
        
        assert f"-preset {preset}" in cmd

    @pytest.mark.parametrize("tune", [
        "film",
        "animation",
        "grain",
        "stillimage",
        "psnr",
        "ssim",
        "fastdecode",
        "zerolatency",
    ])
    def test_tune_options(self, ffmpeg_builder, mock_path_operations, tune):
        """Test various tune options."""
        cmd = (ffmpeg_builder
               .set_input(Path("/test/input.mp4"))
               .set_output(Path("/test/output.mp4"))
               .set_encoder("Software x264")
               .set_tune(tune)
               .set_crf(23)
               .build())
        
        assert f"-tune {tune}" in cmd

    def test_bitrate_settings(self, ffmpeg_builder, mock_path_operations):
        """Test bitrate settings for different scenarios."""
        scenarios = [
            {"bitrate": 1000, "expected": "-b:v 1000k"},
            {"bitrate": 5000, "expected": "-b:v 5000k"},
            {"bitrate": 10000, "expected": "-b:v 10000k"},
        ]
        
        for scenario in scenarios:
            cmd = (ffmpeg_builder
                   .set_input(Path("/test/input.mp4"))
                   .set_output(Path("/test/output.mp4"))
                   .set_encoder("Software x265 (2-Pass)")
                   .set_bitrate(scenario["bitrate"])
                   .set_two_pass(True, "test_passlog", 1)
                   .build())
            
            assert scenario["expected"] in cmd
            
            # Reset builder for next iteration
            ffmpeg_builder = FFmpegCommandBuilder()

    def test_complex_command_integration(self, ffmpeg_builder, mock_path_operations):
        """Test complex command with all parameters."""
        cmd = (ffmpeg_builder
               .set_input(Path("/test/complex/input.mp4"))
               .set_output(Path("/test/complex/output.mp4"))
               .set_encoder("Software x264")
               .set_crf(20)
               .set_pix_fmt("yuv420p10le")
               .set_preset("slow")
               .set_tune("film")
               .build())
        
        # Verify all components are present and properly formatted
        expected_components = [
            "ffmpeg",
            "-i", "/test/complex/input.mp4",
            "-c:v", "libx264",
            "-crf", "20",
            "-pix_fmt", "yuv420p10le", 
            "-preset", "slow",
            "-tune", "film",
            "/test/complex/output.mp4"
        ]
        
        for component in expected_components:
            assert str(component) in cmd

    def test_builder_state_isolation(self):
        """Test that builders maintain isolated state."""
        builder1 = FFmpegCommandBuilder()
        builder2 = FFmpegCommandBuilder()
        
        # Configure builder1
        builder1.set_input(Path("/test1/input.mp4"))
        builder1.set_encoder("Software x264")
        builder1.set_crf(18)
        
        # Configure builder2 differently
        builder2.set_input(Path("/test2/input.mp4")) 
        builder2.set_encoder("Software x265")
        builder2.set_crf(25)
        
        # Verify builders are independent
        with patch("pathlib.Path.exists", return_value=True):
            builder1.set_output(Path("/test1/output.mp4"))
            builder2.set_output(Path("/test2/output.mp4"))
            
            cmd1 = builder1.build()
            cmd2 = builder2.build()
            
            # Verify each has its own settings
            assert "/test1/" in cmd1 and "/test1/" not in cmd2
            assert "/test2/" in cmd2 and "/test2/" not in cmd1
            assert "libx264" in cmd1 and "libx264" not in cmd2
            assert "libx265" in cmd2 and "libx265" not in cmd1
            assert "-crf 18" in cmd1
            assert "-crf 25" in cmd2

    def test_error_message_clarity(self, ffmpeg_builder):
        """Test that error messages are clear and helpful."""
        error_scenarios = [
            {
                "action": lambda: ffmpeg_builder.build(),
                "expected_message": "Input path, output path, and encoder must be set",
            },
            {
                "action": lambda: ffmpeg_builder.set_input(Path("test")).set_output(Path("test")).set_crf(-1).build(),
                "expected_message": "CRF value must be between",
            },
        ]
        
        for scenario in error_scenarios:
            with pytest.raises(ValueError) as exc_info:
                scenario["action"]()
            assert scenario["expected_message"] in str(exc_info.value)

    def test_command_string_format_consistency(self, ffmpeg_builder, mock_path_operations):
        """Test that command strings are consistently formatted."""
        cmd = (ffmpeg_builder
               .set_input(Path("/test/input.mp4"))
               .set_output(Path("/test/output.mp4"))  
               .set_encoder("Software x264")
               .set_crf(23)
               .build())
        
        # Verify command structure
        parts = cmd.split()
        assert parts[0] == "ffmpeg"
        assert "-i" in parts
        assert "-c:v" in parts
        assert "libx264" in parts
        assert "-crf" in parts
        assert "23" in parts
        
        # Verify no extra spaces or formatting issues
        assert "  " not in cmd  # No double spaces
        assert cmd.strip() == cmd  # No leading/trailing whitespace

    def test_performance_command_building(self, ffmpeg_builder, mock_path_operations):
        """Test performance of command building operations."""
        import time
        
        # Build multiple commands to test performance
        start_time = time.time()
        
        for i in range(100):
            builder = FFmpegCommandBuilder()
            cmd = (builder
                   .set_input(Path(f"/test/input_{i}.mp4"))
                   .set_output(Path(f"/test/output_{i}.mp4"))
                   .set_encoder("Software x264")
                   .set_crf(23)
                   .build())
            assert "ffmpeg" in cmd
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete 100 builds in reasonable time (less than 1 second)
        assert duration < 1.0, f"Command building took too long: {duration:.3f}s"

    def test_memory_usage_consistency(self, mock_path_operations):
        """Test that builders don't accumulate memory over multiple uses."""
        import sys
        
        initial_refs = sys.getrefcount(FFmpegCommandBuilder)
        
        # Create and use multiple builders
        for i in range(50):
            builder = FFmpegCommandBuilder()
            cmd = (builder
                   .set_input(Path(f"/test/input_{i}.mp4"))
                   .set_output(Path(f"/test/output_{i}.mp4"))
                   .set_encoder("Software x264")
                   .set_crf(23)
                   .build())
            assert "ffmpeg" in cmd
            del builder
        
        final_refs = sys.getrefcount(FFmpegCommandBuilder)
        
        # Reference count should be similar (within reasonable bounds)
        assert abs(final_refs - initial_refs) <= 2, f"Memory leak detected: {initial_refs} -> {final_refs}"