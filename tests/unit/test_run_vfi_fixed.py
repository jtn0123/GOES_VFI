import pathlib
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from goesvfi.pipeline import run_vfi as run_vfi_mod
from tests.utils.mocks import MockPopen


@pytest.fixture
def mock_capability_detector(mocker):
    """Fixture to provide a mock RifeCapabilityDetector."""
    # Import the actual class/object being mocked here
    from goesvfi.utils.rife_analyzer import RifeCapabilityDetector

    mock_detector = mocker.MagicMock(spec=RifeCapabilityDetector)
    mock_detector.supports_thread_spec.return_value = True  # Default to True
    # Configure other default mock behaviors if needed
    # mock_detector.version = "mock-4.x"

    # Patch where it's used in run_vfi
    return mocker.patch(
        "goesvfi.pipeline.run_vfi.RifeCapabilityDetector", return_value=mock_detector
    )


@pytest.fixture
def mock_colourise(mocker):
    """Fixture to provide a mock colourise function."""
    # Patch where it's used in run_vfi
    return mocker.patch("goesvfi.pipeline.run_vfi.colourise")


@pytest.fixture
def minimal_image(tmp_path):
    """Create a minimal PNG image and return its path."""
    img_path = tmp_path / "img.png"
    img = Image.new("RGB", (4, 4), color="red")
    img.save(img_path)
    return img_path


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


def test_run_vfi_skip_model_writes_all_frames(tmp_path, mock_capability_detector):
    # Arrange: create 3 dummy images
    img_paths = make_dummy_images(tmp_path, 3)
    output_mp4 = tmp_path / "output.mp4"
    raw_output = output_mp4.with_suffix(".raw.mp4")
    rife_exe = tmp_path / "rife"
    fps = 10

    # Setup processed paths - only the first one is used by the worker
    processed_path = tmp_path / "processed_img0.png"
    create_test_png(processed_path, size=(4, 4))

    # Mock Image.open to return a mock image with size attribute
    mock_img = MagicMock()
    mock_img.size = (4, 4)  # Match the size of our test PNG
    mock_img.width = 4
    mock_img.height = 4
    mock_img.mode = "RGB"  # Set image mode to RGB
    mock_img.__enter__.return_value = mock_img  # For context manager usage
    mock_img.close = MagicMock()  # Mock close method
    mock_img.save = MagicMock()

    # Configure mock Popen for ffmpeg
    expected_ffmpeg_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "verbose",
        "-stats",
        "-y",
        "-f",
        "image2pipe",
        "-framerate",
        str(fps),  # Effective FPS is just fps when skipping
        "-vcodec",
        "png",
        "-i",
        "-",
        "-an",
        "-vcodec",
        "libx264",
        "-preset",
        "ultrafast",
        "-pix_fmt",
        "yuv420p",
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        str(raw_output),
    ]
    # FIX: Create the MockPopen instance directly and assign to return_value
    mock_popen_instance = MockPopen(
        args=expected_ffmpeg_cmd,  # Provide expected args for potential internal checks
        returncode=0,  # Success
        stdout=b"ffmpeg success",
        stderr=b"",
        stdin_write_limit=None,
    )
    # Simulate file creation upon successful wait
    original_wait = mock_popen_instance.wait

    def wait_with_file_creation(*wait_args, **wait_kwargs):
        res = original_wait(*wait_args, **wait_kwargs)
        if res == 0:
            try:
                # Create the raw output file that the code expects
                raw_output.parent.mkdir(parents=True, exist_ok=True)
                with open(raw_output, "wb") as f:
                    f.write(b"dummy ffmpeg output")
                print(f"Mock Popen created file: {raw_output}")
            except Exception as e:
                print(f"Mock Popen failed to create file: {e}")
        return res

    mock_popen_instance.wait = wait_with_file_creation  # type: ignore[method-assign]

    with (
        patch("goesvfi.pipeline.run_vfi.subprocess.run") as mock_run_patch,
        patch("goesvfi.pipeline.run_vfi.subprocess.Popen") as mock_popen_patch,
        patch("goesvfi.pipeline.run_vfi.Image.open") as mock_image_open,
        patch("goesvfi.pipeline.run_vfi.ProcessPoolExecutor") as mock_executor,
        patch("goesvfi.pipeline.run_vfi.ImageLoader") as mock_loader_class,
        patch("goesvfi.pipeline.run_vfi.ImageSaver") as mock_saver_class,
        patch("goesvfi.pipeline.run_vfi.SanchezProcessor") as mock_sanchez_class,
        patch("goesvfi.pipeline.run_vfi.ImageCropper") as mock_cropper_class,
        patch.object(pathlib.Path, "glob", return_value=img_paths),
    ):
        # Setup a mock executor that doesn't actually use multiprocessing
        mock_executor_instance = MagicMock()
        mock_executor.return_value.__enter__.return_value = mock_executor_instance

        mock_image_open.return_value = mock_img
        mock_popen_patch.return_value = mock_popen_instance

        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader

        # Create mock ImageData with required attributes
        mock_image_data = MagicMock()
        mock_image_data.width = 4
        mock_image_data.height = 4
        mock_image_data.image = mock_img  # The PIL image
        mock_loader.load.return_value = mock_image_data

        # Mock SanchezProcessor to return same image data
        mock_sanchez = MagicMock()
        mock_sanchez_class.return_value = mock_sanchez
        mock_sanchez.process.return_value = mock_image_data

        # Mock ImageCropper to return same image data
        mock_cropper = MagicMock()
        mock_cropper_class.return_value = mock_cropper
        mock_cropper.crop.return_value = mock_image_data

        # Mock ImageSaver to just pretend to save
        mock_saver = MagicMock()
        mock_saver_class.return_value = mock_saver
        mock_saver.save.return_value = None

        # Configure map to return expected paths
        mock_executor_instance.map.return_value = img_paths

        # Act: run with skip_model=True
        gen = run_vfi_mod.run_vfi(
            folder=tmp_path,
            output_mp4_path=output_mp4,
            rife_exe_path=rife_exe,
            fps=fps,
            num_intermediate_frames=1,  # This is ignored when skip_model=True for ffmpeg fps
            max_workers=1,
            skip_model=True,
        )
        results = list(gen)

        # Assert: ffmpeg Popen called, subprocess.run not called
        mock_popen_patch.assert_called_once()
        mock_run_patch.assert_not_called()

        # In skip_model=True mode, Image.open is called multiple times
        assert mock_image_open.call_count >= 1

        # Check mock Popen instance (the one returned) for stdin writes
        assert mock_popen_instance.stdin.write.call_count >= 1

        # Check results and file creation
        assert any(isinstance(r, tuple) for r in results)  # Progress updates

        # Find the path result
        path_results = [r for r in results if isinstance(r, pathlib.Path)]
        assert len(path_results) > 0, f"No path results found. All results: {results}"

        # The returned path should have a timestamp in the name
        final_path = path_results[-1]
        assert final_path.parent == raw_output.parent
        assert final_path.suffix == ".mp4"
        assert final_path.exists()  # Check mock file creation
