import subprocess  # Import subprocess for exceptions
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from goesvfi.pipeline import raw_encoder

# Import the mock utility
from tests.utils.mocks import create_mock_subprocess_run


@pytest.fixture
def dummy_frames():
    # Create 3 dummy float32 RGB frames (4x4)
    return [np.ones((4, 4, 3), dtype=np.float32) * i for i in range(3)]


def test_write_raw_mp4_success(tmp_path, dummy_frames):
    raw_path = tmp_path / "output.mp4"
    temp_dir_path = tmp_path / "tempdir"
    temp_dir_path.mkdir()

    # Define expected command using ANY for the temp path part
    fps = 30
    expected_pattern = str(temp_dir_path / "%06d.png")
    expected_cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(fps),
        "-i",
        expected_pattern,
        "-c:v",
        "ffv1",
        str(raw_path),
    ]

    # Use the mock factory
    mock_run_factory = create_mock_subprocess_run(
        expected_command=expected_cmd,
        output_file_to_create=raw_path,  # Simulate file creation on success
    )

    with (
        patch(
            "goesvfi.pipeline.raw_encoder.tempfile.TemporaryDirectory"
        ) as mock_tempdir,
        patch("goesvfi.pipeline.raw_encoder.Image.fromarray") as mock_fromarray,
        patch(
            "goesvfi.pipeline.raw_encoder.subprocess.run", side_effect=mock_run_factory
        ) as mock_run_patch,
    ):  # Apply factory
        # Setup tempdir context manager mock (still needed)
        mock_tempdir.return_value = MagicMock(name="TemporaryDirectory")
        mock_tempdir.return_value.__enter__.return_value = mock_tempdir.return_value
        mock_tempdir.return_value.__exit__.return_value = None
        mock_tempdir.return_value.name = str(
            temp_dir_path
        )  # Ensure the mock uses the correct path

        # Mock save (still needed)
        mock_img = MagicMock()
        mock_fromarray.return_value = mock_img

        # Act
        result = raw_encoder.write_raw_mp4(dummy_frames, raw_path, fps=fps)

        # Assert
        # assert mock_fromarray.call_count == len(dummy_frames) # Fails (4 == 3), reason unclear
        assert mock_fromarray.call_count >= len(
            dummy_frames
        )  # Check it's called at least enough times
        # FIX: Assert count is 3 again now that mock interference is fixed
        # Add debug print
        # print(f"DEBUG: mock_fromarray call count: {mock_fromarray.call_count}")
        # print(f"DEBUG: mock_fromarray call args list: {mock_fromarray.call_args_list}")
        assert mock_fromarray.call_count == len(dummy_frames)
        # assert mock_fromarray.call_count == 4
        # assert mock_fromarray.call_count == len(dummy_frames)
        # assert mock_img.save.call_count == len(dummy_frames) # Save is called correct number of times
        mock_run_patch.assert_called_once()  # Check ffmpeg was called
        assert result == raw_path
        assert raw_path.exists()  # Check mock file creation


def test_write_raw_mp4_ffmpeg_error(tmp_path, dummy_frames):
    raw_path = tmp_path / "output.mp4"
    temp_dir_path = tmp_path / "tempdir"
    temp_dir_path.mkdir()

    # Define expected command (it will still be called even if it fails)
    fps = 30
    expected_pattern = str(temp_dir_path / "%06d.png")
    expected_cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(fps),
        "-i",
        expected_pattern,
        "-c:v",
        "ffv1",
        str(raw_path),
    ]

    # Use the mock factory to raise CalledProcessError
    ffmpeg_error = subprocess.CalledProcessError(1, expected_cmd, stderr="fail")
    mock_run_factory = create_mock_subprocess_run(
        expected_command=expected_cmd, side_effect=ffmpeg_error
    )

    with (
        patch(
            "goesvfi.pipeline.raw_encoder.tempfile.TemporaryDirectory"
        ) as mock_tempdir,
        patch("goesvfi.pipeline.raw_encoder.Image.fromarray") as mock_fromarray,
        patch(
            "goesvfi.pipeline.raw_encoder.subprocess.run", side_effect=mock_run_factory
        ) as mock_run_patch,
    ):
        mock_tempdir.return_value = MagicMock(name="TemporaryDirectory")
        mock_tempdir.return_value.__enter__.return_value = mock_tempdir.return_value
        mock_tempdir.return_value.__exit__.return_value = None
        mock_tempdir.return_value.name = str(temp_dir_path)

        mock_img = MagicMock()
        mock_fromarray.return_value = mock_img

        # Act & Assert
        with pytest.raises(subprocess.CalledProcessError):
            raw_encoder.write_raw_mp4(dummy_frames, raw_path, fps=fps)

        mock_run_patch.assert_called_once()  # Check mock was called


def test_write_raw_mp4_ffmpeg_not_found(tmp_path, dummy_frames):
    raw_path = tmp_path / "output.mp4"
    temp_dir_path = tmp_path / "tempdir"
    temp_dir_path.mkdir()

    # Define expected command (it will still be attempted)
    fps = 30
    expected_pattern = str(temp_dir_path / "%06d.png")
    expected_cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(fps),
        "-i",
        expected_pattern,
        "-c:v",
        "ffv1",
        str(raw_path),
    ]

    # Use the mock factory to raise FileNotFoundError
    not_found_error = FileNotFoundError("ffmpeg not found")
    mock_run_factory = create_mock_subprocess_run(
        expected_command=expected_cmd, side_effect=not_found_error
    )

    with (
        patch(
            "goesvfi.pipeline.raw_encoder.tempfile.TemporaryDirectory"
        ) as mock_tempdir,
        patch("goesvfi.pipeline.raw_encoder.Image.fromarray") as mock_fromarray,
        patch(
            "goesvfi.pipeline.raw_encoder.subprocess.run", side_effect=mock_run_factory
        ) as mock_run_patch,
    ):
        mock_tempdir.return_value = MagicMock(name="TemporaryDirectory")
        mock_tempdir.return_value.__enter__.return_value = mock_tempdir.return_value
        mock_tempdir.return_value.__exit__.return_value = None
        mock_tempdir.return_value.name = str(temp_dir_path)

        mock_img = MagicMock()
        mock_fromarray.return_value = mock_img

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            raw_encoder.write_raw_mp4(dummy_frames, raw_path, fps=fps)

        mock_run_patch.assert_called_once()  # Check mock was called
