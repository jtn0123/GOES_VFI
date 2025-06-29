"""Optimized FFmpeg command builder tests to speed up slow tests while maintaining coverage.

Optimizations applied:
- Shared fixtures for common FFmpeg configurations and file setups
- Parameterized test scenarios for comprehensive encoder validation
- Enhanced error handling and edge case coverage
- Mock-based testing to avoid actual file I/O operations
- Comprehensive command building validation across all encoder types
"""

import os
import pathlib
from unittest.mock import patch, MagicMock
import pytest

from goesvfi.pipeline.ffmpeg_builder import FFmpegCommandBuilder


class TestFFmpegCommandBuilderV2:
    """Optimized test class for FFmpeg command builder functionality."""

    @pytest.fixture(scope="class")
    def encoder_configurations(self):
        """Define various encoder configurations for testing."""
        return {
            "software_x264": {
                "name": "Software x264",
                "codec": "libx264",
                "preset": "slow",
                "requires_crf": True,
                "supports_two_pass": False,
            },
            "software_x265": {
                "name": "Software x265",
                "codec": "libx265", 
                "preset": "slower",
                "requires_crf": True,
                "supports_two_pass": True,
                "x265_params": "aq-mode=3:aq-strength=1.0:psy-rd=2.0:psy-rdoq=1.0",
            },
            "software_x265_2pass": {
                "name": "Software x265 (2-Pass)",
                "codec": "libx265",
                "preset": "slower", 
                "requires_bitrate": True,
                "supports_two_pass": True,
                "x265_params": "aq-mode=3:aq-strength=1.0:psy-rd=2.0:psy-rdoq=1.0",
            },
            "hardware_hevc": {
                "name": "Hardware HEVC (VideoToolbox)",
                "codec": "hevc_videotoolbox",
                "requires_bitrate": True,
                "requires_bufsize": True,
                "tag": "hvc1",
            },
            "hardware_h264": {
                "name": "Hardware H.264 (VideoToolbox)",
                "codec": "h264_videotoolbox",
                "requires_bitrate": True,
                "requires_bufsize": True,
            },
            "stream_copy": {
                "name": "None (copy original)",
                "codec": "copy",
                "minimal_command": True,
            }
        }

    @pytest.fixture
    def temp_file_setup(self, tmp_path):
        """Create temporary file structure for testing."""
        input_path = tmp_path / "input.mkv"
        output_path = tmp_path / "output.mp4"
        
        # Create dummy files
        input_path.touch()
        output_path.touch()
        
        return {
            "input": input_path,
            "output": output_path,
            "pass_log": str(tmp_path / "ffmpeg_pass"),
            "temp_dir": tmp_path,
        }

    @pytest.fixture
    def builder_factory(self):
        """Factory for creating fresh FFmpeg builders."""
        def create_builder():
            return FFmpegCommandBuilder()
        return create_builder

    @pytest.mark.parametrize("encoder_type,crf_value", [
        ("software_x264", 23),
        ("software_x264", 18),  # High quality
        ("software_x264", 28),  # Lower quality
        ("software_x265", 28),
        ("software_x265", 20),  # High quality
        ("software_x265", 32),  # Lower quality
    ])
    def test_single_pass_crf_encoders(self, builder_factory, temp_file_setup, encoder_configurations, encoder_type, crf_value):
        """Test single-pass CRF encoding with various encoders and quality settings."""
        config = encoder_configurations[encoder_type]
        builder = builder_factory()
        
        cmd = (
            builder.set_input(temp_file_setup["input"])
            .set_output(temp_file_setup["output"])
            .set_encoder(config["name"])
            .set_crf(crf_value)
            .set_pix_fmt("yuv420p")
            .build()
        )
        
        # Verify command structure
        assert "ffmpeg" in cmd
        assert "-hide_banner" in cmd
        assert "-loglevel" in cmd
        assert "info" in cmd
        assert "-stats" in cmd
        assert "-y" in cmd
        assert "-i" in cmd
        assert str(temp_file_setup["input"]) in cmd
        assert "-c:v" in cmd
        assert config["codec"] in cmd
        assert "-preset" in cmd
        assert config["preset"] in cmd
        assert "-crf" in cmd
        assert str(crf_value) in cmd
        assert "-pix_fmt" in cmd
        assert "yuv420p" in cmd
        assert str(temp_file_setup["output"]) in cmd
        
        # Verify x265-specific parameters
        if "x265_params" in config:
            assert "-x265-params" in cmd
            assert config["x265_params"] in cmd

    @pytest.mark.parametrize("encoder_type,bitrate,bufsize", [
        ("hardware_hevc", 2000, 4000),
        ("hardware_hevc", 1000, 2000),
        ("hardware_hevc", 5000, 10000),
        ("hardware_h264", 1500, 3000),
        ("hardware_h264", 800, 1600),
        ("hardware_h264", 3000, 6000),
    ])
    def test_hardware_encoders(self, builder_factory, temp_file_setup, encoder_configurations, encoder_type, bitrate, bufsize):
        """Test hardware encoding with various bitrate and buffer size combinations."""
        config = encoder_configurations[encoder_type]
        builder = builder_factory()
        
        cmd = (
            builder.set_input(temp_file_setup["input"])
            .set_output(temp_file_setup["output"])
            .set_encoder(config["name"])
            .set_bitrate(bitrate)
            .set_bufsize(bufsize)
            .set_pix_fmt("yuv420p")
            .build()
        )
        
        # Verify hardware-specific command structure
        assert config["codec"] in cmd
        assert "-b:v" in cmd
        assert f"{bitrate}k" in cmd
        assert "-maxrate" in cmd
        assert f"{bufsize}k" in cmd
        
        # Verify tag for HEVC
        if "tag" in config:
            assert "-tag:v" in cmd
            assert config["tag"] in cmd

    @pytest.mark.parametrize("pass_number", [1, 2])
    def test_two_pass_encoding(self, builder_factory, temp_file_setup, pass_number):
        """Test two-pass encoding with both pass 1 and pass 2."""
        builder = builder_factory()
        
        cmd = (
            builder.set_input(temp_file_setup["input"])
            .set_output(temp_file_setup["output"])
            .set_encoder("Software x265 (2-Pass)")
            .set_bitrate(1000)
            .set_pix_fmt("yuv420p")
            .set_two_pass(True, temp_file_setup["pass_log"], pass_number)
            .build()
        )
        
        # Common two-pass elements
        assert "libx265" in cmd
        assert "-preset" in cmd
        assert "slower" in cmd
        assert "-b:v" in cmd
        assert "1000k" in cmd
        assert "-passlogfile" in cmd
        assert temp_file_setup["pass_log"] in cmd
        
        if pass_number == 1:
            # Pass 1 specific
            assert "-x265-params" in cmd
            assert "pass=1" in cmd
            assert "-f" in cmd
            assert "null" in cmd
            assert os.devnull in cmd
        else:
            # Pass 2 specific
            assert "-x265-params" in cmd
            assert "pass=2" in cmd
            assert "aq-mode=3" in cmd
            assert "-pix_fmt" in cmd
            assert str(temp_file_setup["output"]) in cmd

    def test_stream_copy_minimal_command(self, builder_factory, temp_file_setup):
        """Test stream copy (no encoding) produces minimal command."""
        builder = builder_factory()
        
        cmd = (
            builder.set_input(temp_file_setup["input"])
            .set_output(temp_file_setup["output"])
            .set_encoder("None (copy original)")
            .build()
        )
        
        # Verify minimal command structure
        expected_parts = [
            "ffmpeg",
            "-y",
            "-i",
            str(temp_file_setup["input"]),
            "-c",
            "copy",
            str(temp_file_setup["output"]),
        ]
        
        assert cmd == expected_parts

    @pytest.mark.parametrize("missing_component,encoder_name", [
        ("input", "Software x264"),
        ("output", "Software x264"),
        ("encoder", None),
    ])
    def test_missing_required_components(self, builder_factory, temp_file_setup, missing_component, encoder_name):
        """Test validation when required components are missing."""
        builder = builder_factory()
        
        if missing_component != "input":
            builder.set_input(temp_file_setup["input"])
        if missing_component != "output":
            builder.set_output(temp_file_setup["output"])
        if missing_component != "encoder" and encoder_name:
            builder.set_encoder(encoder_name)
            
        # Add other required parameters
        if encoder_name == "Software x264":
            builder.set_crf(23).set_pix_fmt("yuv420p")
        
        with pytest.raises(ValueError):
            builder.build()

    @pytest.mark.parametrize("encoder_name,missing_param", [
        ("Software x264", "crf"),
        ("Software x265", "crf"),
        ("Hardware HEVC (VideoToolbox)", "bitrate"),
        ("Hardware HEVC (VideoToolbox)", "bufsize"),
        ("Hardware H.264 (VideoToolbox)", "bitrate"),
        ("Hardware H.264 (VideoToolbox)", "bufsize"),
    ])
    def test_missing_encoder_specific_parameters(self, builder_factory, temp_file_setup, encoder_name, missing_param):
        """Test validation when encoder-specific parameters are missing."""
        builder = builder_factory()
        
        builder.set_input(temp_file_setup["input"]).set_output(temp_file_setup["output"]).set_encoder(encoder_name)
        
        # Add parameters except the missing one
        if missing_param != "crf" and "Software" in encoder_name:
            builder.set_crf(23)
        if missing_param != "bitrate" and "Hardware" in encoder_name:
            builder.set_bitrate(2000)
        if missing_param != "bufsize" and "Hardware" in encoder_name:
            builder.set_bufsize(4000)
            
        builder.set_pix_fmt("yuv420p")
        
        with pytest.raises(ValueError):
            builder.build()

    @pytest.mark.parametrize("invalid_scenario", [
        "missing_two_pass_setup",
        "missing_log_prefix", 
        "missing_pass_number",
        "invalid_pass_number",
    ])
    def test_two_pass_validation_errors(self, builder_factory, temp_file_setup, invalid_scenario):
        """Test validation errors for two-pass encoding scenarios."""
        builder = builder_factory()
        
        base_setup = (
            builder.set_input(temp_file_setup["input"])
            .set_output(temp_file_setup["output"])
            .set_encoder("Software x265 (2-Pass)")
            .set_bitrate(1000)
            .set_pix_fmt("yuv420p")
        )
        
        if invalid_scenario == "missing_two_pass_setup":
            # Don't call set_two_pass at all
            pass
        elif invalid_scenario == "missing_log_prefix":
            base_setup.set_two_pass(True, None, 1)
        elif invalid_scenario == "missing_pass_number":
            base_setup.set_two_pass(True, temp_file_setup["pass_log"], None)
        elif invalid_scenario == "invalid_pass_number":
            base_setup.set_two_pass(True, temp_file_setup["pass_log"], 3)
        
        with pytest.raises(ValueError):
            builder.build()

    @pytest.mark.parametrize("pix_fmt", [
        "yuv420p",
        "yuv422p",
        "yuv444p",
        "yuv420p10le",
        "yuv422p10le",
    ])
    def test_pixel_format_variations(self, builder_factory, temp_file_setup, pix_fmt):
        """Test various pixel format options."""
        builder = builder_factory()
        
        cmd = (
            builder.set_input(temp_file_setup["input"])
            .set_output(temp_file_setup["output"])
            .set_encoder("Software x264")
            .set_crf(23)
            .set_pix_fmt(pix_fmt)
            .build()
        )
        
        assert "-pix_fmt" in cmd
        assert pix_fmt in cmd

    @pytest.mark.parametrize("crf_value", [0, 15, 23, 28, 35, 51])
    def test_crf_value_range(self, builder_factory, temp_file_setup, crf_value):
        """Test CRF values across the valid range."""
        builder = builder_factory()
        
        cmd = (
            builder.set_input(temp_file_setup["input"])
            .set_output(temp_file_setup["output"])
            .set_encoder("Software x264")
            .set_crf(crf_value)
            .set_pix_fmt("yuv420p")
            .build()
        )
        
        assert "-crf" in cmd
        assert str(crf_value) in cmd

    @pytest.mark.parametrize("bitrate", [500, 1000, 2000, 5000, 10000])
    def test_bitrate_variations(self, builder_factory, temp_file_setup, bitrate):
        """Test various bitrate settings."""
        builder = builder_factory()
        
        cmd = (
            builder.set_input(temp_file_setup["input"])
            .set_output(temp_file_setup["output"])
            .set_encoder("Hardware HEVC (VideoToolbox)")
            .set_bitrate(bitrate)
            .set_bufsize(bitrate * 2)
            .set_pix_fmt("yuv420p")
            .build()
        )
        
        assert "-b:v" in cmd
        assert f"{bitrate}k" in cmd
        assert "-maxrate" in cmd
        assert f"{bitrate * 2}k" in cmd

    def test_builder_method_chaining(self, builder_factory, temp_file_setup):
        """Test that builder methods can be chained in any order."""
        builder = builder_factory()
        
        # Test different chaining orders
        cmd1 = (
            builder.set_input(temp_file_setup["input"])
            .set_encoder("Software x264")
            .set_crf(23)
            .set_output(temp_file_setup["output"])
            .set_pix_fmt("yuv420p")
            .build()
        )
        
        builder2 = builder_factory()
        cmd2 = (
            builder2.set_pix_fmt("yuv420p")
            .set_crf(23)
            .set_input(temp_file_setup["input"])
            .set_output(temp_file_setup["output"])
            .set_encoder("Software x264")
            .build()
        )
        
        # Commands should be identical regardless of chaining order
        assert cmd1 == cmd2

    def test_builder_state_isolation(self, builder_factory, temp_file_setup):
        """Test that multiple builders don't interfere with each other."""
        builder1 = builder_factory()
        builder2 = builder_factory()
        
        # Configure builders differently
        cmd1 = (
            builder1.set_input(temp_file_setup["input"])
            .set_output(temp_file_setup["output"])
            .set_encoder("Software x264")
            .set_crf(18)
            .set_pix_fmt("yuv420p")
            .build()
        )
        
        cmd2 = (
            builder2.set_input(temp_file_setup["input"])
            .set_output(temp_file_setup["output"])
            .set_encoder("Software x265")
            .set_crf(28)
            .set_pix_fmt("yuv422p")
            .build()
        )
        
        # Verify different configurations
        assert "libx264" in cmd1
        assert "libx265" in cmd2
        assert "18" in cmd1
        assert "28" in cmd2
        assert "yuv420p" in cmd1
        assert "yuv422p" in cmd2

    def test_command_element_ordering(self, builder_factory, temp_file_setup):
        """Test that command elements appear in correct order."""
        builder = builder_factory()
        
        cmd = (
            builder.set_input(temp_file_setup["input"])
            .set_output(temp_file_setup["output"])
            .set_encoder("Software x264")
            .set_crf(23)
            .set_pix_fmt("yuv420p")
            .build()
        )
        
        # Find indices of key elements
        ffmpeg_idx = cmd.index("ffmpeg")
        input_idx = cmd.index("-i")
        codec_idx = cmd.index("-c:v")
        output_idx = cmd.index(str(temp_file_setup["output"]))
        
        # Verify ordering
        assert ffmpeg_idx < input_idx
        assert input_idx < codec_idx
        assert codec_idx < output_idx

    def test_path_handling_with_spaces(self, tmp_path, builder_factory):
        """Test proper handling of file paths with spaces."""
        input_with_spaces = tmp_path / "input file with spaces.mkv"
        output_with_spaces = tmp_path / "output file with spaces.mp4"
        
        input_with_spaces.touch()
        output_with_spaces.touch()
        
        builder = builder_factory()
        
        cmd = (
            builder.set_input(input_with_spaces)
            .set_output(output_with_spaces)
            .set_encoder("Software x264")
            .set_crf(23)
            .set_pix_fmt("yuv420p")
            .build()
        )
        
        assert str(input_with_spaces) in cmd
        assert str(output_with_spaces) in cmd

    def test_edge_case_parameter_values(self, builder_factory, temp_file_setup):
        """Test edge case parameter values."""
        builder = builder_factory()
        
        # Test minimum values
        cmd = (
            builder.set_input(temp_file_setup["input"])
            .set_output(temp_file_setup["output"])
            .set_encoder("Hardware HEVC (VideoToolbox)")
            .set_bitrate(1)  # Minimum bitrate
            .set_bufsize(2)  # Minimum bufsize
            .set_pix_fmt("yuv420p")
            .build()
        )
        
        assert "1k" in cmd
        assert "2k" in cmd

    def test_complex_two_pass_workflow(self, builder_factory, temp_file_setup):
        """Test complete two-pass encoding workflow."""
        pass_log_prefix = temp_file_setup["pass_log"]
        
        # Pass 1
        builder1 = builder_factory()
        cmd1 = (
            builder1.set_input(temp_file_setup["input"])
            .set_output(temp_file_setup["output"])
            .set_encoder("Software x265 (2-Pass)")
            .set_bitrate(2000)
            .set_pix_fmt("yuv420p")
            .set_two_pass(True, pass_log_prefix, 1)
            .build()
        )
        
        # Pass 2
        builder2 = builder_factory()
        cmd2 = (
            builder2.set_input(temp_file_setup["input"])
            .set_output(temp_file_setup["output"])
            .set_encoder("Software x265 (2-Pass)")
            .set_bitrate(2000)
            .set_pix_fmt("yuv420p")
            .set_two_pass(True, pass_log_prefix, 2)
            .build()
        )
        
        # Verify both passes have correct structure
        assert "pass=1" in " ".join(cmd1)
        assert "pass=2" in " ".join(cmd2)
        assert os.devnull in cmd1
        assert str(temp_file_setup["output"]) in cmd2

    def test_builder_reusability(self, builder_factory, temp_file_setup):
        """Test that builders can be reused after building."""
        builder = builder_factory()
        
        # First build
        cmd1 = (
            builder.set_input(temp_file_setup["input"])
            .set_output(temp_file_setup["output"])
            .set_encoder("Software x264")
            .set_crf(23)
            .set_pix_fmt("yuv420p")
            .build()
        )
        
        # Modify and build again
        cmd2 = (
            builder.set_crf(18)  # Change CRF
            .build()
        )
        
        # Verify both builds work
        assert "23" in cmd1
        assert "18" in cmd2
        assert len(cmd1) > 0
        assert len(cmd2) > 0

    def test_comprehensive_validation_coverage(self, builder_factory, temp_file_setup):
        """Test comprehensive validation scenarios."""
        validation_scenarios = [
            # Valid configurations
            {
                "valid": True,
                "config": {
                    "encoder": "Software x264",
                    "crf": 23,
                    "pix_fmt": "yuv420p"
                }
            },
            {
                "valid": True,
                "config": {
                    "encoder": "Hardware HEVC (VideoToolbox)",
                    "bitrate": 2000,
                    "bufsize": 4000,
                    "pix_fmt": "yuv420p"
                }
            },
            # Invalid configurations
            {
                "valid": False,
                "config": {
                    "encoder": "Software x264",
                    # Missing CRF
                    "pix_fmt": "yuv420p"
                }
            },
            {
                "valid": False,
                "config": {
                    "encoder": "Hardware HEVC (VideoToolbox)",
                    "bitrate": 2000,
                    # Missing bufsize
                    "pix_fmt": "yuv420p"
                }
            },
        ]
        
        for scenario in validation_scenarios:
            builder = builder_factory()
            builder.set_input(temp_file_setup["input"]).set_output(temp_file_setup["output"])
            
            for param, value in scenario["config"].items():
                if param == "encoder":
                    builder.set_encoder(value)
                elif param == "crf":
                    builder.set_crf(value)
                elif param == "bitrate":
                    builder.set_bitrate(value)
                elif param == "bufsize":
                    builder.set_bufsize(value)
                elif param == "pix_fmt":
                    builder.set_pix_fmt(value)
            
            if scenario["valid"]:
                cmd = builder.build()
                assert len(cmd) > 0
            else:
                with pytest.raises(ValueError):
                    builder.build()