"""Tests for VFI FFmpeg command building."""

import pytest

from goesvfi.pipeline.vfi_ffmpeg_builder import VFIFFmpegBuilder


class TestVFIFFmpegBuilder:
    """Test the VFIFFmpegBuilder class."""

    @pytest.fixture()
    def ffmpeg_builder(self):
        """Create an FFmpeg builder instance."""
        return VFIFFmpegBuilder()

    @pytest.fixture()
    def output_path(self, tmp_path):
        """Create a temporary output path."""
        return tmp_path / "output.mp4"

    @pytest.fixture()
    def input_path(self, tmp_path):
        """Create a temporary input path."""
        path = tmp_path / "input.mp4"
        path.touch()
        return path

    def test_ffmpeg_builder_initialization(self, ffmpeg_builder) -> None:
        """Test FFmpeg builder initializes with defaults."""
        assert ffmpeg_builder.default_encoder == "libx264"
        assert ffmpeg_builder.default_preset == "ultrafast"
        assert ffmpeg_builder.default_pix_fmt == "yuv420p"

    def test_build_raw_video_command_skip_model(self, ffmpeg_builder, output_path) -> None:
        """Test building raw video command with skip_model=True."""
        fps = 30
        num_intermediate_frames = 1
        skip_model = True

        cmd = ffmpeg_builder.build_raw_video_command(output_path, fps, num_intermediate_frames, skip_model)

        # Check basic structure
        assert cmd[0] == "ffmpeg"
        assert "-hide_banner" in cmd
        assert "-y" in cmd  # Overwrite
        assert str(output_path) == cmd[-1]

        # Check framerate (should be same as fps when skipping model)
        framerate_idx = cmd.index("-framerate")
        assert cmd[framerate_idx + 1] == "30"

        # Check input/output settings
        assert "-f" in cmd
        assert "image2pipe" in cmd
        assert "-i" in cmd
        assert "-" in cmd  # stdin
        assert "-vcodec" in cmd
        assert "libx264" in cmd

    def test_build_raw_video_command_with_interpolation(self, ffmpeg_builder, output_path) -> None:
        """Test building raw video command with interpolation."""
        fps = 30
        num_intermediate_frames = 1
        skip_model = False

        cmd = ffmpeg_builder.build_raw_video_command(output_path, fps, num_intermediate_frames, skip_model)

        # Check framerate (should be fps * (num_intermediate_frames + 1))
        framerate_idx = cmd.index("-framerate")
        assert cmd[framerate_idx + 1] == "60"  # 30 * (1 + 1)

    def test_build_raw_video_command_custom_encoder(self, ffmpeg_builder, output_path) -> None:
        """Test building raw video command with custom encoder."""
        cmd = ffmpeg_builder.build_raw_video_command(
            output_path, 30, 1, False, encoder="libx265", preset="slow", pix_fmt="yuv444p"
        )

        # Check custom values
        assert "libx265" in cmd
        assert "slow" in cmd
        assert "yuv444p" in cmd

    def test_build_raw_video_command_scale_filter(self, ffmpeg_builder, output_path) -> None:
        """Test that scale filter is included for even dimensions."""
        cmd = ffmpeg_builder.build_raw_video_command(output_path, 30, 1, False)

        # Check for scale filter
        assert "-vf" in cmd
        vf_idx = cmd.index("-vf")
        assert "scale=trunc(iw/2)*2:trunc(ih/2)*2" in cmd[vf_idx + 1]

    def test_build_final_video_command_basic(self, ffmpeg_builder, input_path, output_path) -> None:
        """Test building final video command with basic settings."""
        ffmpeg_args = {"crf": 23, "pix_fmt": "yuv420p", "encoder": "libx264"}

        cmd = ffmpeg_builder.build_final_video_command(input_path, output_path, 30, ffmpeg_args)

        # Check basic structure
        assert cmd[0] == "ffmpeg"
        assert str(input_path) in cmd
        assert str(output_path) == cmd[-1]

        # Check encoding settings
        assert "-crf" in cmd
        assert "23" in cmd
        assert "-r" in cmd
        assert "30" in cmd

    def test_build_final_video_command_with_bitrate(self, ffmpeg_builder, input_path, output_path) -> None:
        """Test building final video command with bitrate settings."""
        ffmpeg_args = {"crf": 23, "bitrate_kbps": 5000, "bufsize_kb": 10000}

        cmd = ffmpeg_builder.build_final_video_command(input_path, output_path, 30, ffmpeg_args)

        # Check bitrate settings
        assert "-b:v" in cmd
        assert "5000k" in cmd
        assert "-bufsize" in cmd
        assert "10000k" in cmd

    def test_build_final_video_command_with_unsharp(self, ffmpeg_builder, input_path, output_path) -> None:
        """Test building final video command with unsharp filter."""
        ffmpeg_args = {
            "apply_unsharp": True,
            "unsharp_lx": 5.0,
            "unsharp_ly": 5.0,
            "unsharp_la": 1.0,
            "unsharp_cx": 5.0,
            "unsharp_cy": 5.0,
            "unsharp_ca": 0.0,
        }

        cmd = ffmpeg_builder.build_final_video_command(input_path, output_path, 30, ffmpeg_args)

        # Check for unsharp filter
        assert "-vf" in cmd
        vf_idx = cmd.index("-vf")
        vf_value = cmd[vf_idx + 1]
        assert "unsharp=" in vf_value
        assert "lx=5.0" in vf_value
        assert "la=1.0" in vf_value

    def test_build_final_video_command_with_motion_interpolation(self, ffmpeg_builder, input_path, output_path) -> None:
        """Test building final video command with motion interpolation."""
        ffmpeg_args = {
            "use_ffmpeg_interp": True,
            "fps": 60,
            "filter_preset": "full",
            "mi_mode": "bidir",
            "mc_mode": "aobmc",
            "me_mode": "bidir",
            "me_algo": "epzs",
            "minter_mb_size": 16,
            "search_param": 64,
            "minter_vsbmc": 1,
            "scd_mode": "fdiff",
            "scd_threshold": 10.0,
        }

        cmd = ffmpeg_builder.build_final_video_command(input_path, output_path, 60, ffmpeg_args)

        # Check for motion interpolation filter
        assert "-vf" in cmd
        vf_idx = cmd.index("-vf")
        vf_value = cmd[vf_idx + 1]
        assert "minterpolate=" in vf_value
        assert "fps=60" in vf_value
        assert "mi_mode=bidir" in vf_value

    def test_build_final_video_command_combined_filters(self, ffmpeg_builder, input_path, output_path) -> None:
        """Test building final video command with multiple filters."""
        ffmpeg_args = {
            "apply_unsharp": True,
            "unsharp_lx": 3.0,
            "unsharp_ly": 3.0,
            "unsharp_la": 0.5,
            "use_ffmpeg_interp": True,
            "fps": 60,
            "filter_preset": "full",
        }

        cmd = ffmpeg_builder.build_final_video_command(input_path, output_path, 60, ffmpeg_args)

        # Check for combined filters (scale, unsharp, minterpolate)
        assert "-vf" in cmd
        vf_idx = cmd.index("-vf")
        vf_value = cmd[vf_idx + 1]

        # Should have all three filters separated by commas
        assert "scale=" in vf_value
        assert "unsharp=" in vf_value
        assert "minterpolate=" in vf_value
        assert vf_value.count(",") == 2  # Three filters = two commas

    def test_build_unsharp_filter_valid(self, ffmpeg_builder) -> None:
        """Test building unsharp filter with valid parameters."""
        ffmpeg_args = {
            "unsharp_lx": 7.0,
            "unsharp_ly": 7.0,
            "unsharp_la": 1.5,
            "unsharp_cx": 3.0,
            "unsharp_cy": 3.0,
            "unsharp_ca": 0.5,
        }

        result = ffmpeg_builder._build_unsharp_filter(ffmpeg_args)

        assert result == "unsharp=lx=7.0:ly=7.0:la=1.5:cx=3.0:cy=3.0:ca=0.5"

    def test_build_unsharp_filter_defaults(self, ffmpeg_builder) -> None:
        """Test building unsharp filter with default parameters."""
        ffmpeg_args = {}

        result = ffmpeg_builder._build_unsharp_filter(ffmpeg_args)

        # Should use defaults
        assert result == "unsharp=lx=5.0:ly=5.0:la=1.0:cx=5.0:cy=5.0:ca=0.0"

    def test_build_motion_interpolation_filter_valid(self, ffmpeg_builder) -> None:
        """Test building motion interpolation filter."""
        ffmpeg_args = {
            "fps": 60,
            "mi_mode": "blend",
            "mc_mode": "obmc",
            "me_mode": "bidir",
            "me_algo": "esa",
            "minter_mb_size": 8,
            "search_param": 32,
            "minter_vsbmc": 0,
            "scd_mode": "none",
            "scd_threshold": 5.0,
        }

        result = ffmpeg_builder._build_motion_interpolation_filter(ffmpeg_args)

        assert "minterpolate=" in result
        assert "fps=60" in result
        assert "mi_mode=blend" in result
        assert "search_param=32" in result

    def test_build_motion_interpolation_filter_disabled(self, ffmpeg_builder) -> None:
        """Test building motion interpolation filter when disabled."""
        ffmpeg_args = {"filter_preset": "none"}

        result = ffmpeg_builder._build_motion_interpolation_filter(ffmpeg_args)

        assert result is None

    def test_get_command_info_raw_video(self, ffmpeg_builder, output_path) -> None:
        """Test getting command info for raw video command."""
        cmd = ffmpeg_builder.build_raw_video_command(output_path, 30, 1, False)

        info = ffmpeg_builder.get_command_info(cmd)

        assert info["executable"] == "ffmpeg"
        assert info["input_type"] == "-"
        assert info["output_path"] == str(output_path)
        assert info["framerate"] == "60"
        assert info["encoder"] == "libx264"
        assert len(info["filters"]) == 1

    def test_get_command_info_final_video(self, ffmpeg_builder, input_path, output_path) -> None:
        """Test getting command info for final video command."""
        ffmpeg_args = {"encoder": "libx265", "apply_unsharp": True}

        cmd = ffmpeg_builder.build_final_video_command(input_path, output_path, 30, ffmpeg_args)

        info = ffmpeg_builder.get_command_info(cmd)

        assert info["executable"] == "ffmpeg"
        assert info["input_type"] == str(input_path)
        assert info["output_path"] == str(output_path)
        assert info["encoder"] == "libx265"
        assert len(info["filters"]) >= 2  # scale + unsharp

    def test_get_command_info_empty_command(self, ffmpeg_builder) -> None:
        """Test getting command info for empty command."""
        info = ffmpeg_builder.get_command_info([])

        assert info["executable"] is None
        assert info["input_type"] is None
        assert info["output_path"] is None
