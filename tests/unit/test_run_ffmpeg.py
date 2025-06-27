"""Tests for run_ffmpeg functionality."""

from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

from goesvfi.pipeline.run_ffmpeg import run_ffmpeg_interpolation


class TestRunFFmpegInterpolation:
    """Test run_ffmpeg_interpolation functionality."""

    @pytest.fixture()
    def temp_input_dir(self):
        """Create a temporary directory with PNG files for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir) / "input"
            input_dir.mkdir()

            # Create some test PNG files
            for i in range(5):
                png_file = input_dir / f"frame_{i:04d}.png"
                png_file.write_text("fake png content")  # Dummy content

            yield input_dir

    @pytest.fixture()
    def temp_output_file(self):
        """Create a temporary output file path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "output.mp4"
            yield output_path

    @pytest.fixture()
    def basic_params(self):
        """Basic parameters for FFmpeg interpolation."""
        return {
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
        }

    @patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command")
    def test_basic_interpolation(self, mock_run_command, temp_input_dir, temp_output_file, basic_params) -> None:
        """Test basic FFmpeg interpolation."""
        result = run_ffmpeg_interpolation(input_dir=temp_input_dir, output_mp4_path=temp_output_file, **basic_params)

        # Check that the function returns the output path
        assert result == temp_output_file

        # Check that _run_ffmpeg_command was called
        mock_run_command.assert_called_once()

        # Get the command that was executed
        call_args = mock_run_command.call_args
        cmd = call_args[0][0]
        desc = call_args[0][1]

        # Verify command structure
        assert cmd[0] == "ffmpeg"
        assert "-hide_banner" in cmd
        assert "-loglevel" in cmd
        assert "info" in cmd  # default log level
        assert "-y" in cmd
        assert "-framerate" in cmd
        assert "30" in cmd
        assert str(temp_input_dir / "*.png") in cmd
        assert str(temp_output_file) in cmd

        # Verify description
        assert desc == "FFmpeg interpolation"

    @patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command")
    def test_interpolation_with_debug_mode(
        self, mock_run_command, temp_input_dir, temp_output_file, basic_params
    ) -> None:
        """Test FFmpeg interpolation with debug mode enabled."""
        basic_params["debug_mode"] = True

        run_ffmpeg_interpolation(input_dir=temp_input_dir, output_mp4_path=temp_output_file, **basic_params)

        # Check that debug log level was used
        cmd = mock_run_command.call_args[0][0]
        loglevel_index = cmd.index("-loglevel")
        assert cmd[loglevel_index + 1] == "debug"

    @patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command")
    def test_interpolation_with_crop_rect(
        self, mock_run_command, temp_input_dir, temp_output_file, basic_params
    ) -> None:
        """Test FFmpeg interpolation with crop rectangle."""
        basic_params["crop_rect"] = (100, 50, 800, 600)

        run_ffmpeg_interpolation(input_dir=temp_input_dir, output_mp4_path=temp_output_file, **basic_params)

        # Check that crop filter was added
        cmd = mock_run_command.call_args[0][0]
        vf_index = cmd.index("-vf")
        filter_str = cmd[vf_index + 1]
        assert "crop=800:600:100:50" in filter_str

    @patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command")
    def test_interpolation_with_minterpolate(
        self, mock_run_command, temp_input_dir, temp_output_file, basic_params
    ) -> None:
        """Test FFmpeg interpolation with minterpolate filter."""
        basic_params["use_ffmpeg_interp"] = True
        basic_params["num_intermediate_frames"] = 2

        run_ffmpeg_interpolation(input_dir=temp_input_dir, output_mp4_path=temp_output_file, **basic_params)

        # Check that minterpolate filter was added
        cmd = mock_run_command.call_args[0][0]
        vf_index = cmd.index("-vf")
        filter_str = cmd[vf_index + 1]

        assert "minterpolate=" in filter_str
        assert "fps=90" in filter_str  # 30 * (2 + 1)
        assert "mi_mode=mci" in filter_str
        assert "mc_mode=obmc" in filter_str
        assert "me_mode=bidir" in filter_str
        assert "me=epzs" in filter_str
        assert "search_param=32" in filter_str
        assert "scd=fdi" in filter_str
        assert "scd_threshold=10.0" in filter_str
        assert "mb_size=16" in filter_str

    @patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command")
    def test_interpolation_without_minterpolate(
        self, mock_run_command, temp_input_dir, temp_output_file, basic_params
    ) -> None:
        """Test FFmpeg interpolation without minterpolate filter."""
        basic_params["use_ffmpeg_interp"] = False

        run_ffmpeg_interpolation(input_dir=temp_input_dir, output_mp4_path=temp_output_file, **basic_params)

        # Check that minterpolate filter was NOT added
        cmd = mock_run_command.call_args[0][0]
        vf_index = cmd.index("-vf")
        filter_str = cmd[vf_index + 1]

        assert "minterpolate=" not in filter_str

    @patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command")
    def test_interpolation_with_unsharp(self, mock_run_command, temp_input_dir, temp_output_file, basic_params) -> None:
        """Test FFmpeg interpolation with unsharp filter."""
        basic_params["apply_unsharp"] = True
        basic_params["unsharp_lx"] = 5
        basic_params["unsharp_ly"] = 5
        basic_params["unsharp_la"] = 1.2
        basic_params["unsharp_cx"] = 3
        basic_params["unsharp_cy"] = 3
        basic_params["unsharp_ca"] = 0.5

        run_ffmpeg_interpolation(input_dir=temp_input_dir, output_mp4_path=temp_output_file, **basic_params)

        # Check that unsharp filter was added
        cmd = mock_run_command.call_args[0][0]
        vf_index = cmd.index("-vf")
        filter_str = cmd[vf_index + 1]

        assert "unsharp=5:5:1.2:3:3:0.5" in filter_str

    @patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command")
    def test_interpolation_scale_filter_always_present(
        self, mock_run_command, temp_input_dir, temp_output_file, basic_params
    ) -> None:
        """Test that scale filter is always present."""
        run_ffmpeg_interpolation(input_dir=temp_input_dir, output_mp4_path=temp_output_file, **basic_params)

        # Check that scale filter was added
        cmd = mock_run_command.call_args[0][0]
        vf_index = cmd.index("-vf")
        filter_str = cmd[vf_index + 1]

        assert "scale=trunc(iw/2)*2:trunc(ih/2)*2" in filter_str

    @patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command")
    def test_interpolation_encoding_parameters(
        self, mock_run_command, temp_input_dir, temp_output_file, basic_params
    ) -> None:
        """Test encoding parameters in FFmpeg command."""
        run_ffmpeg_interpolation(input_dir=temp_input_dir, output_mp4_path=temp_output_file, **basic_params)

        cmd = mock_run_command.call_args[0][0]

        # Check encoding parameters
        assert "-an" in cmd  # no audio
        assert "-vcodec" in cmd
        assert "libx264" in cmd
        assert "-preset" in cmd
        assert "medium" in cmd
        assert "-crf" in cmd
        assert "18" in cmd
        assert "-b:v" in cmd
        assert "5000k" in cmd
        assert "-bufsize" in cmd
        assert "10000k" in cmd
        assert "-pix_fmt" in cmd
        assert "yuv420p" in cmd

    @patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command")
    def test_interpolation_without_bitrate(
        self, mock_run_command, temp_input_dir, temp_output_file, basic_params
    ) -> None:
        """Test interpolation without bitrate settings."""
        basic_params["bitrate_kbps"] = 0
        basic_params["bufsize_kb"] = 0

        run_ffmpeg_interpolation(input_dir=temp_input_dir, output_mp4_path=temp_output_file, **basic_params)

        cmd = mock_run_command.call_args[0][0]

        # Check that bitrate parameters are not included
        assert "-b:v" not in cmd
        assert "-bufsize" not in cmd

    @patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command")
    def test_minterpolate_optional_parameters(
        self, mock_run_command, temp_input_dir, temp_output_file, basic_params
    ) -> None:
        """Test minterpolate with optional parameters."""
        basic_params["use_ffmpeg_interp"] = True
        basic_params["me_algo"] = ""  # Empty should not be included
        basic_params["search_param"] = 0  # Zero should not be included
        basic_params["scd_mode"] = None  # None should not be included
        basic_params["scd_threshold"] = None
        basic_params["minter_mb_size"] = None
        basic_params["minter_vsbmc"] = 0  # Zero should not be included

        run_ffmpeg_interpolation(input_dir=temp_input_dir, output_mp4_path=temp_output_file, **basic_params)

        cmd = mock_run_command.call_args[0][0]
        vf_index = cmd.index("-vf")
        filter_str = cmd[vf_index + 1]

        # Check that optional parameters are not included when empty/zero/None
        assert "me=" not in filter_str
        assert "search_param=" not in filter_str
        assert "scd=" not in filter_str
        assert "scd_threshold=" not in filter_str
        assert "mb_size=" not in filter_str
        assert "vsbmc=" not in filter_str

    @patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command")
    def test_minterpolate_default_me_algo(
        self, mock_run_command, temp_input_dir, temp_output_file, basic_params
    ) -> None:
        """Test minterpolate with default me_algo."""
        basic_params["use_ffmpeg_interp"] = True
        basic_params["me_algo"] = "(default)"  # Should not be included

        run_ffmpeg_interpolation(input_dir=temp_input_dir, output_mp4_path=temp_output_file, **basic_params)

        cmd = mock_run_command.call_args[0][0]
        vf_index = cmd.index("-vf")
        filter_str = cmd[vf_index + 1]

        assert "me=" not in filter_str

    @patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command")
    def test_minterpolate_with_vsbmc(self, mock_run_command, temp_input_dir, temp_output_file, basic_params) -> None:
        """Test minterpolate with vsbmc enabled."""
        basic_params["use_ffmpeg_interp"] = True
        basic_params["minter_vsbmc"] = 1

        run_ffmpeg_interpolation(input_dir=temp_input_dir, output_mp4_path=temp_output_file, **basic_params)

        cmd = mock_run_command.call_args[0][0]
        vf_index = cmd.index("-vf")
        filter_str = cmd[vf_index + 1]

        assert "vsbmc=1" in filter_str

    @patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command")
    def test_complex_filter_chain(self, mock_run_command, temp_input_dir, temp_output_file, basic_params) -> None:
        """Test complex filter chain with all filters enabled."""
        basic_params["crop_rect"] = (50, 25, 1920, 1080)
        basic_params["use_ffmpeg_interp"] = True
        basic_params["apply_unsharp"] = True

        run_ffmpeg_interpolation(input_dir=temp_input_dir, output_mp4_path=temp_output_file, **basic_params)

        cmd = mock_run_command.call_args[0][0]
        vf_index = cmd.index("-vf")
        filter_str = cmd[vf_index + 1]

        # Check that all filters are present in correct order
        assert "crop=1920:1080:50:25" in filter_str
        assert "minterpolate=" in filter_str
        assert "unsharp=" in filter_str
        assert "scale=trunc(iw/2)*2:trunc(ih/2)*2" in filter_str

        # Check order using commas
        parts = filter_str.split(",")
        assert len(parts) == 4  # crop, minterpolate, unsharp, scale
        assert parts[0].startswith("crop=")
        assert parts[1].startswith("minterpolate=")
        assert parts[2].startswith("unsharp=")
        assert parts[3].startswith("scale=")

    def test_input_directory_not_exists(self, temp_output_file, basic_params) -> None:
        """Test error when input directory doesn't exist."""
        non_existent_dir = Path("/non/existent/directory")

        with pytest.raises(ValueError, match="Input directory .* does not exist"):
            run_ffmpeg_interpolation(input_dir=non_existent_dir, output_mp4_path=temp_output_file, **basic_params)

    def test_no_png_files(self, temp_output_file, basic_params) -> None:
        """Test error when no PNG files found in input directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            empty_dir = Path(temp_dir)

            with pytest.raises(ValueError, match="No PNG files found"):
                run_ffmpeg_interpolation(input_dir=empty_dir, output_mp4_path=temp_output_file, **basic_params)

    @patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command")
    def test_ffmpeg_command_exception(self, mock_run_command, temp_input_dir, temp_output_file, basic_params) -> None:
        """Test handling of FFmpeg command exceptions."""
        mock_run_command.side_effect = Exception("FFmpeg failed")

        with pytest.raises(Exception, match="FFmpeg failed"):
            run_ffmpeg_interpolation(input_dir=temp_input_dir, output_mp4_path=temp_output_file, **basic_params)

    @patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command")
    def test_logging_during_execution(self, mock_run_command, temp_input_dir, temp_output_file, basic_params) -> None:
        """Test that appropriate logging occurs."""
        with patch("goesvfi.pipeline.run_ffmpeg.LOGGER") as mock_logger:
            run_ffmpeg_interpolation(input_dir=temp_input_dir, output_mp4_path=temp_output_file, **basic_params)

            # Should log the command and completion
            assert mock_logger.info.call_count >= 2

            # Check specific log messages
            log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
            assert any("Running FFmpeg command" in msg for msg in log_calls)
            assert any("Interpolation completed" in msg for msg in log_calls)

    @patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command")
    def test_monitor_memory_parameter(self, mock_run_command, temp_input_dir, temp_output_file, basic_params) -> None:
        """Test that monitor_memory parameter is passed correctly."""
        run_ffmpeg_interpolation(input_dir=temp_input_dir, output_mp4_path=temp_output_file, **basic_params)

        # Check that monitor_memory=False was passed
        call_kwargs = mock_run_command.call_args[1]
        assert call_kwargs["monitor_memory"] is False

    @patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command")
    def test_fps_calculation(self, mock_run_command, temp_input_dir, temp_output_file, basic_params) -> None:
        """Test FPS calculation for different intermediate frame counts."""
        test_cases = [
            (30, 0, 30),  # 30 fps, 0 intermediate = 30 fps
            (30, 1, 60),  # 30 fps, 1 intermediate = 60 fps
            (24, 2, 72),  # 24 fps, 2 intermediate = 72 fps
            (60, 3, 240),  # 60 fps, 3 intermediate = 240 fps
        ]

        for input_fps, intermediate_frames, expected_fps in test_cases:
            basic_params["fps"] = input_fps
            basic_params["num_intermediate_frames"] = intermediate_frames
            basic_params["use_ffmpeg_interp"] = True

            run_ffmpeg_interpolation(input_dir=temp_input_dir, output_mp4_path=temp_output_file, **basic_params)

            cmd = mock_run_command.call_args[0][0]
            vf_index = cmd.index("-vf")
            filter_str = cmd[vf_index + 1]

            assert f"fps={expected_fps}" in filter_str

    @patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command")
    def test_path_conversion(self, mock_run_command, temp_input_dir, temp_output_file, basic_params) -> None:
        """Test that Path objects are properly converted to strings."""
        # Ensure we're passing Path objects
        assert isinstance(temp_input_dir, Path)
        assert isinstance(temp_output_file, Path)

        run_ffmpeg_interpolation(input_dir=temp_input_dir, output_mp4_path=temp_output_file, **basic_params)

        cmd = mock_run_command.call_args[0][0]

        # Check that paths were converted to strings in command
        assert str(temp_input_dir / "*.png") in cmd
        assert str(temp_output_file) in cmd
