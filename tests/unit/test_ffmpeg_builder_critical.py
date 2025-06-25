"""Critical tests for FFmpeg command building functionality."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from goesvfi.pipeline.ffmpeg_builder import FFmpegCommandBuilder


class TestFFmpegCommandBuilder:
    """Test FFmpeg command building logic."""

    def test_basic_ffmpeg_command(self):
        """Test basic FFmpeg command construction."""
        builder = FFmpegCommandBuilder()

        # Test basic video encoding command
        cmd = (
            builder.set_input(Path("/tmp/frames/frame_%04d.png"))
            .set_output(Path("/tmp/output.mp4"))
            .set_encoder("Software x264")
            .set_crf(23)
            .build()
        )

        assert "ffmpeg" in cmd
        assert "-i" in cmd
        assert "/tmp/frames/frame_%04d.png" in cmd
        assert str(Path("/tmp/output.mp4")) in cmd

    def test_ffmpeg_with_two_pass(self):
        """Test FFmpeg command with two-pass encoding."""
        builder = FFmpegCommandBuilder()

        # Test first pass
        cmd = (
            builder.set_input(Path("/tmp/input.mp4"))
            .set_output(Path("/tmp/output.mp4"))
            .set_encoder("Software x265 (2-Pass)")
            .set_bitrate(5000)
            .set_two_pass(True, "passlog", 1)
            .build()
        )

        assert "-c:v" in cmd
        assert "libx265" in cmd
        assert "-x265-params" in cmd
        assert "pass=1" in cmd
        assert "-passlogfile" in cmd
        assert "passlog" in cmd

    def test_ffmpeg_copy_stream(self):
        """Test FFmpeg command for stream copy."""
        builder = FFmpegCommandBuilder()

        cmd = (
            builder.set_input(Path("/tmp/input.mp4"))
            .set_output(Path("/tmp/output.mp4"))
            .set_encoder("None (copy original)")
            .build()
        )

        assert "ffmpeg" in cmd
        assert "-i" in cmd
        assert "/tmp/input.mp4" in cmd
        assert "-c" in cmd
        assert "copy" in cmd
        assert "/tmp/output.mp4" in cmd

    def test_invalid_parameters(self):
        """Test error handling for invalid parameters."""
        builder = FFmpegCommandBuilder()

        # Test missing required parameters
        with pytest.raises(ValueError, match="Input path, output path, and encoder must be set"):
            builder.build()

        # Test missing encoder
        builder.set_input(Path("/tmp/input.mp4"))
        builder.set_output(Path("/tmp/output.mp4"))
        with pytest.raises(ValueError):
            builder.build()

        # Test two-pass without required params
        builder.set_encoder("Software x265 (2-Pass)")
        with pytest.raises(ValueError, match="Two-pass encoding requires"):
            builder.build()

    def test_pixel_format_setting(self):
        """Test FFmpeg command with pixel format."""
        builder = FFmpegCommandBuilder()

        cmd = (
            builder.set_input(Path("/tmp/input.mp4"))
            .set_output(Path("/tmp/output.mp4"))
            .set_encoder("Software x264")
            .set_pix_fmt("yuv420p10le")
            .set_crf(20)
            .build()
        )

        assert "-pix_fmt" in cmd
        assert "yuv420p10le" in cmd
