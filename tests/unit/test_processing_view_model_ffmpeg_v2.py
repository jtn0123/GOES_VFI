"""
Optimized unit tests for ProcessingViewModel FFmpeg functionality with enhanced coverage.

Optimizations:
- Added more test cases for better coverage
- Parameterized tests for various scenarios
- Shared fixtures for common setup
- Added edge case testing
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from goesvfi.gui_components import PreviewManager, ProcessingManager
from goesvfi.view_models.processing_view_model import ProcessingViewModel


class TestProcessingViewModelFFmpegV2:
    """Optimized tests for ProcessingViewModel FFmpeg command building."""

    @pytest.fixture()
    def view_model(self) -> ProcessingViewModel:  # noqa: PLR6301
        """Create ProcessingViewModel instance with mocked dependencies.

        Returns:
            ProcessingViewModel: Instance with mocked dependencies.
        """
        preview_manager = MagicMock(spec=PreviewManager)
        processing_manager = MagicMock(spec=ProcessingManager)
        return ProcessingViewModel(preview_manager, processing_manager)

    @pytest.fixture()
    def test_paths(self, tmp_path: Any) -> dict[str, Any]:  # noqa: PLR6301
        """Create test paths.

        Returns:
            dict[str, Any]: Dictionary containing test file paths.
        """
        return {
            "output": tmp_path / "output.mp4",
            "output_mkv": tmp_path / "output.mkv",
            "output_avi": tmp_path / "output.avi",
            "output_mov": tmp_path / "output.mov",
        }

    def test_build_ffmpeg_command_with_crop(self, view_model: ProcessingViewModel, test_paths: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test building FFmpeg command with crop parameters."""
        output = test_paths["output"]
        settings = {"encoder": "Software x264", "crf": 20, "pix_fmt": "yuv420p"}
        crop = (10, 20, 100, 80)  # x, y, width, height

        cmd = view_model.build_ffmpeg_command(output, 30, crop, settings)

        # Verify crop filter is present
        idx = cmd.index("-filter:v")
        assert cmd[idx + 1].startswith("crop=100:80:10:20")
        assert str(output) in cmd

        # Verify other parameters
        assert "-framerate" in cmd
        assert "30" in cmd
        assert "-crf" in cmd
        assert "20" in cmd
        assert "-pix_fmt" in cmd
        assert "yuv420p" in cmd

    def test_build_ffmpeg_command_without_crop(  # noqa: PLR6301
        self, view_model: ProcessingViewModel, test_paths: dict[str, Any]
    ) -> None:
        """Test building FFmpeg command without crop parameters."""
        output = test_paths["output"]
        settings = {"encoder": "Software x264", "crf": 23}

        cmd = view_model.build_ffmpeg_command(output, 24, None, settings)

        # Verify no crop filter
        assert "-filter:v" not in cmd
        assert str(output) in cmd

        # Verify framerate
        assert "-framerate" in cmd
        assert "24" in cmd

    @pytest.mark.parametrize(
        "encoder,expected_codec",
        [
            ("Software x264", ["-c:v", "libx264"]),
            ("Software x265", ["-c:v", "libx265"]),
            ("Hardware H.264 (VideoToolbox)", ["-c:v", "h264_videotoolbox"]),
            ("Hardware HEVC (VideoToolbox)", ["-c:v", "hevc_videotoolbox"]),
            ("None (copy original)", ["-c", "copy"]),
        ],
    )
    def test_build_ffmpeg_command_encoders(  # noqa: PLR6301
        self, view_model: ProcessingViewModel, test_paths: dict[str, Any], encoder: str, expected_codec: str
    ) -> None:
        """Test building FFmpeg command with different encoders."""
        output = test_paths["output"]
        settings = {"encoder": encoder}
        
        # Add CRF for encoders that require it
        if encoder in ["Software x264", "Software x265"]:
            settings["crf"] = 23
        # Add bitrate for hardware encoders that require it
        elif "Hardware" in encoder:
            settings["bitrate_kbps"] = 5000
            settings["bufsize_kb"] = 10000

        cmd = view_model.build_ffmpeg_command(output, 30, None, settings)

        # Verify codec is set correctly
        for i, expected in enumerate(expected_codec):
            assert expected in cmd
            if i > 0:  # Check order for codec value
                idx = cmd.index(expected_codec[i - 1])
                assert cmd[idx + 1] == expected

    @pytest.mark.parametrize("fps", [24, 25, 30, 48, 50, 60, 120])
    def test_build_ffmpeg_command_various_fps(  # noqa: PLR6301
        self, view_model: ProcessingViewModel, test_paths: dict[str, Any], fps: int
    ) -> None:
        """Test building FFmpeg command with various frame rates."""
        output = test_paths["output"]
        settings = {"encoder": "Software x264", "crf": 23}

        cmd = view_model.build_ffmpeg_command(output, fps, None, settings)

        # Verify framerate is set
        assert "-framerate" in cmd
        idx = cmd.index("-framerate")
        assert cmd[idx + 1] == str(fps)

    @pytest.mark.parametrize("crf", [0, 15, 23, 28, 51])
    def test_build_ffmpeg_command_crf_values(  # noqa: PLR6301
        self, view_model: ProcessingViewModel, test_paths: dict[str, Any], crf: int
    ) -> None:
        """Test building FFmpeg command with various CRF values."""
        output = test_paths["output"]
        settings = {"encoder": "Software x264", "crf": crf}

        cmd = view_model.build_ffmpeg_command(output, 30, None, settings)

        # Verify CRF is set
        assert "-crf" in cmd
        idx = cmd.index("-crf")
        assert cmd[idx + 1] == str(crf)

    @pytest.mark.parametrize("pix_fmt", ["yuv420p", "yuv422p", "yuv444p", "rgb24"])
    def test_build_ffmpeg_command_pixel_formats(  # noqa: PLR6301
        self, view_model: ProcessingViewModel, test_paths: dict[str, Any], pix_fmt: str
    ) -> None:
        """Test building FFmpeg command with various pixel formats."""
        output = test_paths["output"]
        settings = {"encoder": "Software x264", "pix_fmt": pix_fmt, "crf": 23}

        cmd = view_model.build_ffmpeg_command(output, 30, None, settings)

        # Verify pixel format is set
        assert "-pix_fmt" in cmd
        idx = cmd.index("-pix_fmt")
        assert cmd[idx + 1] == pix_fmt

    def test_build_ffmpeg_command_with_all_settings(  # noqa: PLR6301
        self, view_model: ProcessingViewModel, test_paths: dict[str, Any]
    ) -> None:
        """Test building FFmpeg command with all possible settings."""
        output = test_paths["output"]
        settings = {
            "encoder": "Software x265",
            "crf": 28,
            "pix_fmt": "yuv420p10le",
            "preset": "medium",
            "tune": "animation",
            "profile": "main10",
        }
        crop = (50, 100, 1920, 1080)

        cmd = view_model.build_ffmpeg_command(output, 60, crop, settings)

        # Verify all parameters are present
        assert "-c:v" in cmd
        assert "libx265" in cmd
        assert "-crf" in cmd
        assert "28" in cmd
        assert "-pix_fmt" in cmd
        assert "yuv420p10le" in cmd
        assert "-preset" in cmd
        assert "medium" in cmd
        assert "-tune" in cmd
        assert "animation" in cmd
        assert "-profile:v" in cmd
        assert "main10" in cmd
        assert "-filter:v" in cmd
        assert "crop=1920:1080:50:100" in cmd[cmd.index("-filter:v") + 1]

    @pytest.mark.parametrize("output_ext", [".mp4", ".mkv", ".avi", ".mov", ".webm"])
    def test_build_ffmpeg_command_output_formats(  # noqa: PLR6301
        self, view_model: ProcessingViewModel, tmp_path: Any, output_ext: str
    ) -> None:
        """Test building FFmpeg command with different output formats."""
        output = tmp_path / f"output{output_ext}"
        settings = {"encoder": "Software x264", "crf": 23}

        cmd = view_model.build_ffmpeg_command(output, 30, None, settings)

        # Verify output path is included
        assert str(output) in cmd

        # Verify format-specific options if needed
        if output_ext == ".mp4":
            assert "-movflags" in cmd
            assert "+faststart" in cmd

    def test_build_ffmpeg_command_edge_cases(self, view_model: ProcessingViewModel, test_paths: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test edge cases for FFmpeg command building."""
        # Test with minimal settings
        output = test_paths["output"]
        cmd = view_model.build_ffmpeg_command(output, 30, None, {})

        # Should still produce valid command
        assert "ffmpeg" in cmd or cmd[0].endswith("ffmpeg")
        assert str(output) in cmd

        # Test with zero crop dimensions (should handle gracefully)
        crop = (0, 0, 0, 0)
        cmd = view_model.build_ffmpeg_command(output, 30, crop, {"encoder": "Software x264", "crf": 23})

        # Should either skip crop or handle it appropriately
        # Implementation dependent - just verify no crash
        assert isinstance(cmd, list)

    def test_build_ffmpeg_command_order_preservation(  # noqa: PLR6301
        self, view_model: ProcessingViewModel, test_paths: dict[str, Any]
    ) -> None:
        """Test that FFmpeg command maintains proper argument order."""
        output = test_paths["output"]
        settings = {
            "encoder": "Software x264",
            "crf": 23,
            "preset": "fast",
        }

        cmd = view_model.build_ffmpeg_command(output, 30, None, settings)

        # Verify critical order: input options -> input -> output options -> output
        # Output should be last
        assert cmd[-1] == str(output)

        # Codec should come before CRF
        if "-c:v" in cmd and "-crf" in cmd:
            assert cmd.index("-c:v") < cmd.index("-crf")
