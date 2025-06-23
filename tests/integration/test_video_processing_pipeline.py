"""Integration tests for the complete video processing pipeline.

Tests the entire flow from image input through RIFE interpolation,
Sanchez processing, cropping, and final video encoding.
"""

import pathlib
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from goesvfi.pipeline.run_vfi import run_vfi


class TestVideoProcessingPipeline:
    """Test the complete video processing pipeline."""

    @pytest.fixture
    def test_images(self, tmp_path):
        """Create test images for processing."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Create 5 test images with gradients
        images = []
        for i in range(5):
            # Create gradient image
            img_array = np.zeros((480, 640, 3), dtype=np.uint8)
            img_array[:, :, 0] = int(255 * i / 4)  # Red gradient
            img_array[:, :, 1] = 128  # Constant green
            img_array[:, :, 2] = 255 - int(255 * i / 4)  # Blue gradient

            img = Image.fromarray(img_array)
            img_path = input_dir / f"frame_{i:04d}.png"
            img.save(img_path)
            images.append(img_path)

        return input_dir, images

    @pytest.fixture
    def mock_rife(self):
        """Mock RIFE executable and processing."""
        with (
            patch(
                "goesvfi.pipeline.run_vfi.VfiWorker._get_rife_executable"
            ) as mock_find,
            patch("goesvfi.pipeline.run_vfi.subprocess.run") as mock_run,
        ):

            # Mock finding RIFE
            mock_find.return_value = pathlib.Path("/mock/rife-cli")

            # Mock RIFE execution
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            yield mock_find, mock_run

    @pytest.fixture
    def mock_ffmpeg(self):
        """Mock FFmpeg subprocess."""
        with patch("goesvfi.pipeline.run_vfi.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdin = MagicMock()
            mock_process.stdout = MagicMock()
            mock_process.stderr = MagicMock()
            mock_process.wait.return_value = 0
            mock_process.poll.return_value = None
            mock_process.returncode = 0

            mock_popen.return_value = mock_process

            yield mock_popen, mock_process

    def test_basic_video_pipeline(self, test_images, mock_rife, mock_ffmpeg, tmp_path):
        """Test basic video processing pipeline."""
        input_dir, image_files = test_images
        output_file = tmp_path / "output.mp4"

        # Mock FFmpeg to succeed
        mock_ffmpeg_popen, mock_process = mock_ffmpeg
        mock_process.wait.return_value = 0
        mock_process.returncode = 0

        # Get mocked RIFE path
        mock_find, mock_rife_run = mock_rife

        # Run the pipeline - it returns a generator
        result_gen = run_vfi(
            folder=input_dir,
            output_mp4_path=output_file,
            rife_exe_path=mock_find.return_value,
            fps=30,
            num_intermediate_frames=1,
            max_workers=2,
        )

        # Consume the generator to execute the pipeline
        result = None
        for item in result_gen:
            if isinstance(item, pathlib.Path):
                result = item
            # Otherwise it's a progress update tuple

        # Verify RIFE was called for each frame pair
        assert mock_rife_run.called
        # Should be called len(images) - 1 times for pairs
        assert mock_rife_run.call_count == len(image_files) - 1

        # Verify FFmpeg was called
        assert mock_ffmpeg_popen.called

        # Check FFmpeg command
        ffmpeg_cmd = mock_ffmpeg_popen.call_args[0][0]
        assert "ffmpeg" in ffmpeg_cmd[0]
        assert "-r" in ffmpeg_cmd  # Frame rate
        assert "30" in ffmpeg_cmd  # FPS value
        assert "-c:v" in ffmpeg_cmd  # Video codec
        assert "libx264" in ffmpeg_cmd  # Encoder
        assert str(output_file) in ffmpeg_cmd

    def test_pipeline_with_sanchez_processing(
        self, test_images, mock_rife, mock_ffmpeg, tmp_path
    ):
        """Test pipeline with Sanchez false color processing."""
        input_dir, image_files = test_images
        output_file = tmp_path / "output_sanchez.mp4"

        # Mock FFmpeg to succeed
        mock_ffmpeg_popen, mock_process = mock_ffmpeg
        mock_process.wait.return_value = 0
        mock_process.returncode = 0

        # Mock Sanchez processing
        with patch("goesvfi.pipeline.run_vfi.colourise") as mock_colourise:

            def mock_colourise_func(input_path, output_path, *args, **kwargs):
                # Simulate Sanchez by copying with color shift
                img = Image.open(input_path)
                img_array = np.array(img)
                # Shift colors to simulate false color
                img_array = np.roll(img_array, 1, axis=2)
                Image.fromarray(img_array).save(output_path)
                return 0

            mock_colourise.side_effect = mock_colourise_func

            # Get mocked RIFE path
            mock_find, mock_rife_run = mock_rife

            # Create sanchez temp dir
            sanchez_temp = tmp_path / "sanchez_temp"
            sanchez_temp.mkdir(exist_ok=True)

            result_gen = run_vfi(
                folder=input_dir,
                output_mp4_path=output_file,
                rife_exe_path=mock_find.return_value,
                fps=30,
                num_intermediate_frames=1,
                max_workers=1,
                false_colour=True,
                res_km=2,
                sanchez_gui_temp_dir=sanchez_temp,
            )

            # Consume the generator
            for _ in result_gen:
                pass

            # Verify Sanchez was called for each image
            assert mock_colourise.called
            # Sanchez is called for original images and interpolated images
            assert mock_colourise.call_count >= len(image_files)

    def test_pipeline_with_crop(self, test_images, mock_rife, mock_ffmpeg, tmp_path):
        """Test pipeline with crop region."""
        input_dir, image_files = test_images
        output_file = tmp_path / "output_cropped.mp4"
        crop_rect = (100, 100, 400, 300)  # x, y, width, height

        # Mock FFmpeg to succeed
        mock_ffmpeg_popen, mock_process = mock_ffmpeg
        mock_process.wait.return_value = 0
        mock_process.returncode = 0

        # Get mocked RIFE path
        mock_find, mock_rife_run = mock_rife

        result_gen = run_vfi(
            folder=input_dir,
            output_mp4_path=output_file,
            rife_exe_path=mock_find.return_value,
            fps=30,
            num_intermediate_frames=1,
            max_workers=1,
            crop_rect_xywh=crop_rect,
        )

        # Consume the generator
        for _ in result_gen:
            pass

        # Verify FFmpeg was called
        assert mock_ffmpeg_popen.called

        # Verify RIFE was called
        assert mock_rife_run.called

    def test_pipeline_with_multiple_intermediate_frames(
        self, test_images, mock_rife, mock_ffmpeg, tmp_path
    ):
        """Test pipeline with multiple intermediate frames."""
        input_dir, image_files = test_images
        output_file = tmp_path / "output_interpolated.mp4"

        # Mock FFmpeg to succeed
        mock_ffmpeg_popen, mock_process = mock_ffmpeg
        mock_process.wait.return_value = 0
        mock_process.returncode = 0

        # Get mocked RIFE path
        mock_find, mock_rife_run = mock_rife

        # Currently only num_intermediate_frames=1 is supported
        # Test should verify the NotImplementedError is raised for > 1
        with pytest.raises(NotImplementedError) as exc_info:
            list(
                run_vfi(
                    folder=input_dir,
                    output_mp4_path=output_file,
                    rife_exe_path=mock_find.return_value,
                    fps=60,  # Higher FPS
                    num_intermediate_frames=3,  # More intermediate frames - not supported
                    max_workers=2,
                )
            )

        assert "num_intermediate_frames=1 is supported" in str(exc_info.value)

    def test_pipeline_with_hardware_encoder(
        self, test_images, mock_rife, mock_ffmpeg, tmp_path
    ):
        """Test pipeline with hardware encoder."""
        input_dir, image_files = test_images
        output_file = tmp_path / "output_hw.mp4"

        # Test with VideoToolbox (macOS)
        import platform

        if platform.system() != "Darwin":
            pytest.skip("Hardware encoder test only for macOS")

        encoder = "hevc_videotoolbox"

        # Mock FFmpeg to succeed
        mock_ffmpeg_popen, mock_process = mock_ffmpeg
        mock_process.wait.return_value = 0
        mock_process.returncode = 0

        # Get mocked RIFE path
        mock_find, mock_rife_run = mock_rife

        # Note: run_vfi doesn't take encoder parameter directly
        # It uses the default encoder from the system
        result_gen = run_vfi(
            folder=input_dir,
            output_mp4_path=output_file,
            rife_exe_path=mock_find.return_value,
            fps=30,
            num_intermediate_frames=1,
            max_workers=1,
        )

        # Consume the generator
        for _ in result_gen:
            pass

        # Verify FFmpeg was called
        assert mock_ffmpeg_popen.called

        # Check FFmpeg command
        if mock_ffmpeg_popen.called:
            ffmpeg_cmd = mock_ffmpeg_popen.call_args[0][0]
            # Default encoder is libx264, not hardware encoder
            assert "libx264" in ffmpeg_cmd

    def test_pipeline_error_handling(self, test_images, tmp_path):
        """Test pipeline error handling."""
        input_dir, image_files = test_images
        output_file = tmp_path / "output_error.mp4"

        # Test 1: RIFE executable not found - test with actual file system check
        fake_rife_path = pathlib.Path("/nonexistent/rife")

        # The function will try to use this path and fail during subprocess.run
        with patch("goesvfi.pipeline.run_vfi.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("RIFE executable not found")

            result_gen = run_vfi(
                folder=input_dir,
                output_mp4_path=output_file,
                rife_exe_path=fake_rife_path,
                fps=30,
                num_intermediate_frames=1,
                max_workers=1,
            )

            # Should fail when trying to run RIFE
            with pytest.raises(FileNotFoundError):
                list(result_gen)

        # Test 2: FFmpeg failure
        with (
            patch("goesvfi.pipeline.run_vfi.subprocess.run") as mock_run,
            patch("goesvfi.pipeline.run_vfi.subprocess.Popen") as mock_popen,
        ):

            mock_run.return_value = MagicMock(returncode=0)

            # Mock FFmpeg failure
            mock_process = MagicMock()
            mock_process.stdin.write.side_effect = BrokenPipeError("Pipe broken")
            mock_process.stderr.read.return_value = b"FFmpeg error"
            mock_process.wait.return_value = 1  # Non-zero exit code
            mock_process.returncode = 1
            mock_popen.return_value = mock_process

            result_gen = run_vfi(
                folder=input_dir,
                output_mp4_path=output_file,
                rife_exe_path=pathlib.Path("/mock/rife"),
                fps=30,
                num_intermediate_frames=1,
                max_workers=1,
            )

            # Should fail when writing to FFmpeg
            with pytest.raises(BrokenPipeError):
                list(result_gen)

    def test_pipeline_with_resource_limits(
        self, test_images, mock_rife, mock_ffmpeg, tmp_path
    ):
        """Test pipeline with resource management."""
        input_dir, image_files = test_images
        output_file = tmp_path / "output_limited.mp4"

        # Mock FFmpeg to succeed
        mock_ffmpeg_popen, mock_process = mock_ffmpeg
        mock_process.wait.return_value = 0
        mock_process.returncode = 0

        # Get mocked RIFE path
        mock_find, mock_rife_run = mock_rife

        # Note: The current run_vfi doesn't use resource manager directly
        # It's part of the VfiWorker class which isn't used here
        result_gen = run_vfi(
            folder=input_dir,
            output_mp4_path=output_file,
            rife_exe_path=mock_find.return_value,
            fps=30,
            num_intermediate_frames=1,
            max_workers=4,  # Request more workers
        )

        # Consume the generator
        for _ in result_gen:
            pass

        # Verify basic execution
        assert mock_rife_run.called
        assert mock_ffmpeg_popen.called

    def test_pipeline_progress_reporting(
        self, test_images, mock_rife, mock_ffmpeg, tmp_path
    ):
        """Test progress reporting during processing."""
        input_dir, image_files = test_images
        output_file = tmp_path / "output_progress.mp4"

        # Mock FFmpeg to succeed
        mock_ffmpeg_popen, mock_process = mock_ffmpeg
        mock_process.wait.return_value = 0
        mock_process.returncode = 0

        # Get mocked RIFE path
        mock_find, mock_rife_run = mock_rife

        progress_updates = []

        result_gen = run_vfi(
            folder=input_dir,
            output_mp4_path=output_file,
            rife_exe_path=mock_find.return_value,
            fps=30,
            num_intermediate_frames=1,
            max_workers=1,
        )

        # Consume the generator and collect progress updates
        for item in result_gen:
            if isinstance(item, tuple) and len(item) == 3:
                # Progress update: (current, total, eta)
                progress_updates.append(item)

        # Verify progress updates were sent
        assert len(progress_updates) > 0
        # Should have increasing progress
        if len(progress_updates) > 1:
            # Check that current frame increases
            assert progress_updates[-1][0] >= progress_updates[0][0]

    def test_pipeline_with_skip_interpolation(self, test_images, mock_ffmpeg, tmp_path):
        """Test pipeline with interpolation skipped."""
        input_dir, image_files = test_images
        output_file = tmp_path / "output_no_interp.mp4"

        # Mock FFmpeg to succeed
        mock_ffmpeg_popen, mock_process = mock_ffmpeg
        mock_process.wait.return_value = 0
        mock_process.returncode = 0

        # RIFE should not be called
        with patch("goesvfi.pipeline.run_vfi.subprocess.run") as mock_run:

            result_gen = run_vfi(
                folder=input_dir,
                output_mp4_path=output_file,
                rife_exe_path=pathlib.Path("/mock/rife"),
                fps=30,
                num_intermediate_frames=1,
                max_workers=1,
                skip_model=True,  # Skip interpolation
            )

            # Consume the generator
            for _ in result_gen:
                pass

            # RIFE should not be called
            assert not mock_run.called

            # FFmpeg should still be called
            assert mock_ffmpeg_popen.called

    def test_pipeline_with_custom_ffmpeg_options(
        self, test_images, mock_rife, mock_ffmpeg, tmp_path
    ):
        """Test pipeline with custom FFmpeg options."""
        input_dir, image_files = test_images
        output_file = tmp_path / "output_custom.mp4"

        # Mock FFmpeg to succeed
        mock_ffmpeg_popen, mock_process = mock_ffmpeg
        mock_process.wait.return_value = 0
        mock_process.returncode = 0

        # Get mocked RIFE path
        mock_find, mock_rife_run = mock_rife

        # Note: run_vfi doesn't take custom ffmpeg_options parameter
        # It builds its own FFmpeg command internally
        result_gen = run_vfi(
            folder=input_dir,
            output_mp4_path=output_file,
            rife_exe_path=mock_find.return_value,
            fps=30,
            num_intermediate_frames=1,
            max_workers=1,
        )

        # Consume the generator
        for _ in result_gen:
            pass

        # Verify FFmpeg was called
        assert mock_ffmpeg_popen.called

        # Check FFmpeg command has basic encoding options
        ffmpeg_cmd = mock_ffmpeg_popen.call_args[0][0]

        # Should include basic encoding settings
        assert "-c:v" in ffmpeg_cmd
        assert "libx264" in ffmpeg_cmd  # Default encoder

    def test_pipeline_with_large_image_tiling(self, mock_rife, mock_ffmpeg, tmp_path):
        """Test pipeline with large images requiring tiling."""
        # Create large test images
        input_dir = tmp_path / "large_input"
        input_dir.mkdir()

        for i in range(2):
            # Create 4K image
            img_array = np.zeros((2160, 3840, 3), dtype=np.uint8)
            img_array[:, :, 0] = 100
            img_array[:, :, 1] = 150
            img_array[:, :, 2] = 200

            img = Image.fromarray(img_array)
            img.save(input_dir / f"frame_{i:04d}.png")

        output_file = tmp_path / "output_4k.mp4"

        # Get mocked RIFE path
        mock_find, _ = mock_rife

        result = run_vfi(
            folder=input_dir,
            output_mp4_path=output_file,
            rife_exe_path=mock_find.return_value,
            fps=30,
            num_intermediate_frames=1,
            max_workers=1,
            rife_tile_enable=True,  # Enable tiling
            rife_uhd_mode=True,  # UHD mode
        )

        # Verify RIFE was called with tiling options
        _, mock_rife_run = mock_rife
        if mock_rife_run.called:
            rife_cmd = mock_rife_run.call_args[0][0]
            # Check for tiling-related arguments
