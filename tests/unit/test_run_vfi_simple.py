import pathlib
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from goesvfi.pipeline import run_vfi as run_vfi_mod


@pytest.fixture
def mock_capability_detector(mocker):
    """Fixture to provide a mock RifeCapabilityDetector."""
    mock_detector = mocker.MagicMock()
    mock_detector.supports_thread_spec.return_value = True
    return mocker.patch(
        "goesvfi.pipeline.run_vfi.RifeCapabilityDetector", return_value=mock_detector
    )


def create_test_png(path: pathlib.Path, size: tuple = (10, 10)):
    """Create a minimal valid PNG file at the given path."""
    img_array = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    img = Image.fromarray(img_array)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")
    return path


def make_dummy_images(tmp_path, n, size=(4, 4)):
    paths = []
    for i in range(n):
        img_path = tmp_path / f"img{i}.png"
        create_test_png(img_path, size=size)
        paths.append(img_path)
    return paths


def test_run_vfi_skip_model_basic(tmp_path, mock_capability_detector):
    """Test that skip_model=True bypasses RIFE and writes frames directly."""
    # Arrange: create 3 dummy images
    img_paths = make_dummy_images(tmp_path, 3)
    output_mp4 = tmp_path / "output.mp4"
    rife_exe = tmp_path / "rife"
    fps = 10

    with (
        patch("goesvfi.pipeline.run_vfi.subprocess.run") as mock_run_patch,
        patch("goesvfi.pipeline.run_vfi.subprocess.Popen") as mock_popen_patch,
        patch.object(pathlib.Path, "glob", return_value=img_paths),
    ):
        # Mock ffmpeg Popen to succeed
        mock_popen = MagicMock()
        mock_popen.returncode = 0
        mock_popen.wait.return_value = 0
        mock_popen.stdin = MagicMock()
        mock_popen.stdout = MagicMock()
        mock_popen.stdout.readline.return_value = b""
        mock_popen_patch.return_value = mock_popen

        # Act: run with skip_model=True
        gen = run_vfi_mod.run_vfi(
            folder=tmp_path,
            output_mp4_path=output_mp4,
            rife_exe_path=rife_exe,
            fps=fps,
            num_intermediate_frames=1,
            max_workers=1,
            skip_model=True,
        )
        results = list(gen)

        # Assert
        # 1. FFmpeg was called via Popen (for encoding)
        mock_popen_patch.assert_called_once()

        # 2. RIFE (subprocess.run) was NOT called
        mock_run_patch.assert_not_called()

        # 3. FFmpeg stdin received frame data
        assert mock_popen.stdin.write.call_count >= 1

        # 4. Results contain progress updates and final path
        assert any(isinstance(r, tuple) for r in results)  # Progress updates
        assert any(isinstance(r, pathlib.Path) for r in results)  # Final path
