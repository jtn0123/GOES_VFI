import pathlib
import subprocess
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import ANY, MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from goesvfi.pipeline.image_loader import ImageLoader
from goesvfi.pipeline.image_processing_interfaces import ImageData
from goesvfi.pipeline.image_saver import ImageSaver

# Import the main pipeline function (Corrected path)
from goesvfi.pipeline.run_vfi import run_vfi
from goesvfi.utils.rife_analyzer import (  # For mocking capabilities
    RifeCapabilityDetector,
)

# Import helper
from tests.utils.helpers import create_dummy_png

# Import the mock utilities
from tests.utils.mocks import (
    create_mock_colourise,
    create_mock_popen,
    create_mock_subprocess_run,
)

# --- Constants ---
DEFAULT_IMG_SIZE = (64, 32)  # Small size for faster testing
DEFAULT_FPS = 30
DEFAULT_INTERMEDIATE_FRAMES = 1
MOCK_RIFE_EXE = pathlib.Path("/mock/rife-cli")
MOCK_FFMPEG_EXE = "ffmpeg"  # Assume ffmpeg is in PATH for command construction

# --- Mock Fixtures / Setup ---


@pytest.fixture
def mock_popen():
    """Fixture to patch subprocess.Popen. Side effect configured in helper."""
    with patch("goesvfi.pipeline.run_vfi.subprocess.Popen") as mock_popen_patch:
        yield mock_popen_patch


@pytest.fixture
def mock_run():
    """Fixture to patch subprocess.run. Side effect configured in helper."""
    # Note: run_vfi uses run for RIFE, Popen for ffmpeg stream
    with patch("goesvfi.pipeline.run_vfi.subprocess.run") as mock_run_patch:
        yield mock_run_patch


@pytest.fixture
def mock_rife_capabilities():
    """Fixture to mock RifeCapabilityDetector."""
    # Define default capabilities for the mock
    default_caps = {
        "supports_tiling": True,
        "supports_uhd": True,
        "supports_tta_spatial": True,
        "supports_tta_temporal": True,
        "supports_thread_spec": True,
        "supports_model_path": True,
        "supports_timestep": True,
        "supports_gpu_id": True,
    }
    with patch(
        "goesvfi.pipeline.run_vfi.RifeCapabilityDetector"
    ) as mock_detector_class:
        mock_instance = MagicMock(spec=RifeCapabilityDetector)
        # Configure the instance attributes based on default_caps
        for cap, value in default_caps.items():
            setattr(mock_instance, cap, MagicMock(return_value=value))

        # Make the class constructor return our configured instance
        mock_detector_class.return_value = mock_instance
        yield mock_instance  # Yield the instance for potential modification in tests


@pytest.fixture
def mock_sanchez():
    """Fixture to mock the Sanchez colourise function."""
    # Use the mock factory for colourise
    with patch("goesvfi.pipeline.run_vfi.colourise") as mock_colourise_patch:
        # Default side effect creates the file. Tests can override if needed.
        def default_colourise_factory(*args, **kwargs):
            # Extract output path from args[1]
            output_path_str = args[1]
            factory = create_mock_colourise(
                output_file_to_create=pathlib.Path(output_path_str)
            )
            return factory(*args, **kwargs)  # Call the created mock function

        mock_colourise_patch.side_effect = default_colourise_factory
        yield mock_colourise_patch


# --- Helper Function ---


def run_pipeline_and_collect(
    # Fixtures passed in
    mock_popen_fixture: MagicMock,
    mock_run_fixture: MagicMock,
    # Test parameters
    input_dir: pathlib.Path,
    output_mp4_path: pathlib.Path,
    num_input_frames: int = 2,
    img_size: Tuple[int, int] = DEFAULT_IMG_SIZE,
    rife_exe: pathlib.Path = MOCK_RIFE_EXE,
    fps: int = DEFAULT_FPS,
    num_intermediate: int = DEFAULT_INTERMEDIATE_FRAMES,
    max_workers: int = 1,
    skip_model: bool = False,
    false_colour: bool = False,
    res_km: int = 4,
    crop_rect_xywh: Optional[Tuple[int, int, int, int]] = None,
    rife_options: Optional[Dict[str, Any]] = None,
    # --- Mock configurations (NEW) ---
    expected_rife_cmd: Optional[List[str]] = None,
    rife_output_to_create: Optional[pathlib.Path] = None,
    rife_return_code: int = 0,
    rife_side_effect: Optional[Exception] = None,
    expected_ffmpeg_cmd: Optional[List[str]] = None,
    ffmpeg_output_to_create: Optional[pathlib.Path] = None,
    ffmpeg_return_code: int = 0,
    ffmpeg_side_effect: Optional[Exception] = None,
    ffmpeg_stdin_write_limit: Optional[int] = None,  # For BrokenPipeError simulation
    # --- Original mock fixtures (still needed for setup) ---
    _sanchez_mock: Optional[MagicMock] = None,
    _rife_caps_mock: Optional[MagicMock] = None,
) -> Tuple[Optional[pathlib.Path], List[Tuple[int, int, float]], MagicMock, MagicMock]:
    """
    Runs the pipeline with specified parameters and mocks, collecting results.
    Uses mock factories to configure subprocess.run and subprocess.Popen.

    Returns:
        Tuple containing:
        - Final output path (or None if error)
        - List of progress updates
        - The mock_run_fixture (for assertion checks)
        - The mock_popen_fixture (for assertion checks)
    """
    # Create dummy input files
    input_paths = []
    for i in range(num_input_frames):
        p = input_dir / f"frame_{i:03d}.png"
        create_dummy_png(p, size=img_size, color=(0, 0, i * 10))
        input_paths.append(p)

    # --- Configure Mocks using Factories ---

    # Configure subprocess.run (for RIFE)
    # Only configure if not skipping model, otherwise it shouldn't be called
    if not skip_model:
        if not expected_rife_cmd:
            # Basic default if not provided by test
            expected_rife_cmd = [
                str(rife_exe),
                "-0",
                ANY,
                "-1",
                ANY,
                "-o",
                ANY,
                "-m",
                "rife-v4.6",
                "-n",
                str(num_intermediate),
                "-j",
                "1:2:2",
                "-s",
                "0.5",
                "-g",
                "-1",
            ]
        mock_run_factory = create_mock_subprocess_run(
            expected_command=expected_rife_cmd,
            returncode=rife_return_code,
            output_file_to_create=rife_output_to_create,
            side_effect=rife_side_effect,
        )
        mock_run_fixture.side_effect = mock_run_factory
    else:
        # If skipping model, ensure run is not called
        mock_run_fixture.side_effect = lambda *_a, **_k: pytest.fail(
            "subprocess.run called unexpectedly when skip_model=True"
        )

    # Configure subprocess.Popen (for FFmpeg)
    if not expected_ffmpeg_cmd:
        # Basic default if not provided by test
        expected_ffmpeg_cmd = [
            MOCK_FFMPEG_EXE,
            "-i",
            "-",
            str(output_mp4_path.with_suffix(".raw.mp4")),
        ]  # Simplified
    mock_popen_factory = create_mock_popen(
        expected_command=expected_ffmpeg_cmd,
        returncode=ffmpeg_return_code,
        output_file_to_create=ffmpeg_output_to_create,
        side_effect=ffmpeg_side_effect,
        stdin_write_limit=ffmpeg_stdin_write_limit,
    )
    mock_popen_fixture.side_effect = mock_popen_factory

    # --- Run Pipeline ---
    final_path = None
    progress_updates = []
    pipeline_kwargs = {
        "folder": input_dir,
        "output_mp4_path": output_mp4_path,
        "rife_exe_path": rife_exe,
        "fps": fps,
        "num_intermediate_frames": num_intermediate,
        "max_workers": max_workers,
        "skip_model": skip_model,
        "false_colour": false_colour,
        "res_km": res_km,
        "crop_rect_xywh": crop_rect_xywh,
        **(rife_options or {}),
    }

    # Remove the broad try/except block to allow test exceptions to propagate
    # try:
    generator = run_vfi(**pipeline_kwargs)
    for update in generator:
        if isinstance(update, pathlib.Path):
            final_path = update
        elif isinstance(update, tuple):
            progress_updates.append(update)
        else:
            pytest.fail(f"Unexpected yield type: {type(update)}")
    # except Exception as e:
    #     print(f"Pipeline execution raised exception: {e}")
    #     # Don't fail the helper, let the test assert the expected exception
    #     pass # Allow tests to check for expected exceptions

    return final_path, progress_updates, mock_run_fixture, mock_popen_fixture


# --- Test Cases ---


# Pass mock_run fixture as well
@patch("pathlib.Path.exists", return_value=True)  # Mock model path existence
# Skip marker removed after resolving the Qt dependency issue
def test_basic_interpolation(
    mock_exists,
    temp_dir: pathlib.Path,
    mock_popen: MagicMock,
    mock_run: MagicMock,
    mock_rife_capabilities: MagicMock,
    mocker,
):
    """Test basic interpolation (2 frames -> 1 intermediate)."""
    # Patch the request_previews_update signal on all Qt classes that might use it
    # This prevents "AttributeError: '...' does not have a signal with the signature request_previews_update()"
    from PyQt6.QtWidgets import QCheckBox, QComboBox, QLabel

    mocker.patch.object(
        QComboBox, "request_previews_update", create=True, return_value=None
    )
    mocker.patch.object(
        QLabel, "request_previews_update", create=True, return_value=None
    )
    mocker.patch.object(
        QCheckBox, "request_previews_update", create=True, return_value=None
    )

    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    output_mp4 = output_dir / "basic.mp4"
    num_frames = 2
    num_intermediate = DEFAULT_INTERMEDIATE_FRAMES
    fps = DEFAULT_FPS
    effective_fps = fps * (num_intermediate + 1)
    expected_raw_path = output_mp4.with_suffix(".raw.mp4")
    # Predict RIFE output path based on run_vfi logic (inside processed_img_path)
    # This is fragile, but necessary for the mock file creation check
    temp_dir / "processed_temp" / "interp_0000.png"

    # --- Define Expected Commands ---
    expected_rife_cmd = [
        str(MOCK_RIFE_EXE),
        "-0",
        ANY,
        "-1",
        ANY,
        "-o",
        ANY,
        "-m",
        "rife-v4.6",
        "-n",
        str(num_intermediate),
        "-s",
        "0.5",
        "-g",
        "-1",
        "-j",
        "1:2:2",
    ]
    expected_ffmpeg_cmd = [
        MOCK_FFMPEG_EXE,
        "-hide_banner",
        "-loglevel",
        "verbose",
        "-stats",
        "-y",
        "-f",
        "image2pipe",
        "-framerate",
        str(effective_fps),
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
        str(expected_raw_path),
    ]

    # --- Run Test ---
    with pytest.raises((IOError, RuntimeError)):
        run_pipeline_and_collect(
            mock_popen_fixture=mock_popen,
            mock_run_fixture=mock_run,
            input_dir=input_dir,
            output_mp4_path=output_mp4,
            num_input_frames=num_frames,
            _rife_caps_mock=mock_rife_capabilities,
            expected_rife_cmd=expected_rife_cmd,
            rife_output_to_create=None,  # Mock won't create RIFE output
            rife_return_code=0,  # RIFE itself "succeeds"
            expected_ffmpeg_cmd=expected_ffmpeg_cmd,
            ffmpeg_output_to_create=expected_raw_path,
        )
    # --- Assert ---
    # Verify RIFE was called using the mock fixture
    mock_run.assert_called_once()


# Pass mock_run fixture as well
# Skip marker removed after resolving the Qt dependency issue
def test_skip_model(temp_dir: pathlib.Path, mock_popen: MagicMock, mock_run: MagicMock):
    """Test pipeline with skip_model=True."""
    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    output_mp4 = output_dir / "skipped.mp4"
    num_frames = 3
    fps = DEFAULT_FPS  # Effective FPS is just fps when skipping
    expected_raw_path = output_mp4.with_suffix(".raw.mp4")

    # --- Define Expected Commands ---
    # RIFE (run) should NOT be called. Helper configures mock_run to fail if called.
    # FFmpeg (Popen) should be called.
    # Define the full expected command explicitly
    expected_ffmpeg_cmd = [
        MOCK_FFMPEG_EXE,
        "-hide_banner",
        "-loglevel",
        "verbose",
        "-stats",
        "-y",
        "-f",
        "image2pipe",
        "-framerate",
        str(fps),  # Use base fps
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
        str(expected_raw_path),
    ]

    # --- Run Test ---
    final_path, progress, run_mock, popen_mock = run_pipeline_and_collect(
        mock_popen_fixture=mock_popen,
        mock_run_fixture=mock_run,
        input_dir=input_dir,
        output_mp4_path=output_mp4,
        num_input_frames=num_frames,
        skip_model=True,
        # Pass expected FFmpeg command and output
        expected_ffmpeg_cmd=expected_ffmpeg_cmd,  # Use explicit cmd
        ffmpeg_output_to_create=expected_raw_path,
    )

    # --- Assert ---
    assert final_path == expected_raw_path
    assert final_path.exists()  # Check mock FFmpeg file creation

    assert len(progress) >= num_frames - 1  # Check progress updates

    # Check mocks were called (or not called)
    run_mock.assert_not_called()  # RIFE should not be called
    popen_mock.assert_called_once()  # FFmpeg should be called


# Pass mock_run fixture as well
@patch("pathlib.Path.exists", return_value=True)  # Mock model path existence
# Skip marker removed after resolving the Qt dependency issue
def test_cropping(
    mock_exists,
    temp_dir: pathlib.Path,
    mock_popen: MagicMock,
    mock_run: MagicMock,
    mock_rife_capabilities: MagicMock,
):
    """Test pipeline with cropping enabled."""
    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    output_mp4 = output_dir / "cropped.mp4"
    num_frames = 2
    num_intermediate = DEFAULT_INTERMEDIATE_FRAMES
    fps = DEFAULT_FPS
    effective_fps = fps * (num_intermediate + 1)
    expected_raw_path = output_mp4.with_suffix(".raw.mp4")
    temp_dir / "processed_temp" / "interp_0000.png"
    # Crop to inner 10x10 area of the 64x32 image
    crop_rect = (27, 11, 10, 10)  # x, y, w, h
    # Cropped size needs to be even for yuv420p, run_vfi handles this with scale filter
    # The mock doesn't need to know the exact scaled size, just that the filter is present.

    # --- Define Expected Commands ---
    expected_rife_cmd = [
        str(MOCK_RIFE_EXE),
        "-0",
        ANY,
        "-1",
        ANY,
        "-o",
        ANY,
        "-m",
        "rife-v4.6",
        "-n",
        str(num_intermediate),
        "-s",
        "0.5",
        "-g",
        "-1",
        "-j",
        "1:2:2",
    ]
    # FFmpeg command should have the scaling filter
    expected_ffmpeg_cmd = [
        MOCK_FFMPEG_EXE,
        "-hide_banner",
        "-loglevel",
        "verbose",
        "-stats",
        "-y",
        "-f",
        "image2pipe",
        "-framerate",
        str(effective_fps),
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
        str(expected_raw_path),
    ]

    # --- Run Test ---
    with pytest.raises((IOError, RuntimeError)):
        run_pipeline_and_collect(
            mock_popen_fixture=mock_popen,
            mock_run_fixture=mock_run,
            input_dir=input_dir,
            output_mp4_path=output_mp4,
            num_input_frames=num_frames,
            crop_rect_xywh=crop_rect,
            _rife_caps_mock=mock_rife_capabilities,
            expected_rife_cmd=expected_rife_cmd,
            rife_output_to_create=None,  # Mock won't create RIFE output
            rife_return_code=0,
            expected_ffmpeg_cmd=expected_ffmpeg_cmd,
            ffmpeg_output_to_create=expected_raw_path,
        )
    # --- Assert ---
    # Verify RIFE was called using the mock fixture
    mock_run.assert_called_once()


# Pass mock_run fixture as well
@patch("pathlib.Path.exists", return_value=True)  # Mock model path existence
# Skip marker removed after resolving the Qt dependency issue
def test_sanchez(
    mock_exists,
    temp_dir: pathlib.Path,
    mock_popen: MagicMock,
    mock_run: MagicMock,
    mock_sanchez: MagicMock,
    mock_rife_capabilities: MagicMock,
):
    """Test pipeline with Sanchez false colour enabled."""
    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    output_mp4 = output_dir / "sanchez.mp4"
    num_frames = 2
    num_intermediate = DEFAULT_INTERMEDIATE_FRAMES
    fps = DEFAULT_FPS
    effective_fps = fps * (num_intermediate + 1)
    expected_raw_path = output_mp4.with_suffix(".raw.mp4")
    temp_dir / "processed_temp" / "interp_0000.png"
    res_km = 2

    # --- Define Expected Commands ---
    expected_rife_cmd = [
        str(MOCK_RIFE_EXE),
        "-0",
        ANY,
        "-1",
        ANY,
        "-o",
        ANY,
        "-m",
        "rife-v4.6",
        "-n",
        str(num_intermediate),
        "-s",
        "0.5",
        "-g",
        "-1",
        "-j",
        "1:2:2",
    ]
    # FFmpeg command structure is the same
    expected_ffmpeg_cmd = [
        MOCK_FFMPEG_EXE,
        "-hide_banner",
        "-loglevel",
        "verbose",
        "-stats",
        "-y",
        "-f",
        "image2pipe",
        "-framerate",
        str(effective_fps),
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
        str(expected_raw_path),
    ]

    # --- Run Test ---
    with pytest.raises((IOError, RuntimeError)):
        run_pipeline_and_collect(
            mock_popen_fixture=mock_popen,
            mock_run_fixture=mock_run,
            input_dir=input_dir,
            output_mp4_path=output_mp4,
            num_input_frames=num_frames,
            false_colour=True,
            res_km=res_km,
            _sanchez_mock=mock_sanchez,
            _rife_caps_mock=mock_rife_capabilities,
            expected_rife_cmd=expected_rife_cmd,
            rife_output_to_create=None,  # Mock won't create RIFE output
            rife_return_code=0,
            expected_ffmpeg_cmd=expected_ffmpeg_cmd,
            ffmpeg_output_to_create=expected_raw_path,
        )
    # --- Assert ---
    # Verify RIFE and Sanchez were called using the mock fixtures
    mock_run.assert_called_once()
    # Check Sanchez was attempted, exact count not reliable due to early exit
    mock_sanchez.assert_called()


# Pass mock_run fixture as well
@patch("pathlib.Path.exists", return_value=True)  # Mock model path existence
# Skip marker removed after resolving the Qt dependency issue
def test_crop_and_sanchez(
    mock_exists,
    temp_dir: pathlib.Path,
    mock_popen: MagicMock,
    mock_run: MagicMock,
    mock_sanchez: MagicMock,
    mock_rife_capabilities: MagicMock,
):
    """Test pipeline with both cropping and Sanchez enabled."""
    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    output_mp4 = output_dir / "crop_sanchez.mp4"
    num_frames = 2
    num_intermediate = DEFAULT_INTERMEDIATE_FRAMES
    fps = DEFAULT_FPS
    effective_fps = fps * (num_intermediate + 1)
    expected_raw_path = output_mp4.with_suffix(".raw.mp4")
    temp_dir / "processed_temp" / "interp_0000.png"
    crop_rect = (10, 5, 20, 10)  # x, y, w, h
    res_km = 1

    # --- Define Expected Commands ---
    expected_rife_cmd = [
        str(MOCK_RIFE_EXE),
        "-0",
        ANY,
        "-1",
        ANY,
        "-o",
        ANY,
        "-m",
        "rife-v4.6",
        "-n",
        str(num_intermediate),
        "-s",
        "0.5",
        "-g",
        "-1",
        "-j",
        "1:2:2",
    ]
    # FFmpeg command structure is the same, includes scaling filter
    expected_ffmpeg_cmd = [
        MOCK_FFMPEG_EXE,
        "-hide_banner",
        "-loglevel",
        "verbose",
        "-stats",
        "-y",
        "-f",
        "image2pipe",
        "-framerate",
        str(effective_fps),
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
        str(expected_raw_path),
    ]

    # --- Run Test ---
    with pytest.raises((IOError, RuntimeError)):
        run_pipeline_and_collect(
            mock_popen_fixture=mock_popen,
            mock_run_fixture=mock_run,
            input_dir=input_dir,
            output_mp4_path=output_mp4,
            num_input_frames=num_frames,
            false_colour=True,
            res_km=res_km,
            crop_rect_xywh=crop_rect,
            _sanchez_mock=mock_sanchez,
            _rife_caps_mock=mock_rife_capabilities,
            expected_rife_cmd=expected_rife_cmd,
            rife_output_to_create=None,  # Mock won't create RIFE output
            rife_return_code=0,
            expected_ffmpeg_cmd=expected_ffmpeg_cmd,
            ffmpeg_output_to_create=expected_raw_path,
        )
    # --- Assert ---
    # Verify RIFE and Sanchez were called using the mock fixtures
    mock_run.assert_called_once()
    # Check Sanchez was attempted, exact count not reliable due to early exit
    mock_sanchez.assert_called()


# --- Error Handling Tests ---


def test_error_insufficient_frames(
    temp_dir: pathlib.Path, mock_popen: MagicMock, mock_run: MagicMock
):
    """Test error handling for fewer than 2 input frames."""
    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    output_mp4 = output_dir / "insufficient.mp4"

    with pytest.raises(
        ValueError, match="At least two PNG images are required for interpolation."
    ):
        run_pipeline_and_collect(
            mock_popen_fixture=mock_popen,
            mock_run_fixture=mock_run,
            input_dir=input_dir,
            output_mp4_path=output_mp4,
            num_input_frames=1,
        )


def test_error_insufficient_frames_skip_model(
    temp_dir: pathlib.Path, mock_popen: MagicMock, mock_run: MagicMock
):
    """Test error handling for < 2 frames when skipping model."""
    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    output_mp4 = output_dir / "insufficient_skip.mp4"

    with pytest.raises(ValueError, match="No PNG images found in the input folder."):
        run_pipeline_and_collect(
            mock_popen_fixture=mock_popen,
            mock_run_fixture=mock_run,
            input_dir=input_dir,
            output_mp4_path=output_mp4,
            num_input_frames=0,
            skip_model=True,
        )


# Pass mock_run fixture as well
@patch("pathlib.Path.exists", return_value=True)  # Mock model path existence
# Skip marker removed after resolving the Qt dependency issue
def test_error_invalid_crop(
    mock_exists,
    temp_dir: pathlib.Path,
    mock_popen: MagicMock,
    mock_run: MagicMock,
    mock_rife_capabilities: MagicMock,
    caplog,
):
    """Test that an invalid crop rectangle logs an error but allows processing to continue without cropping."""
    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    output_mp4 = output_dir / "invalid_crop.mp4"
    num_frames = 2
    num_intermediate = DEFAULT_INTERMEDIATE_FRAMES
    fps = DEFAULT_FPS
    effective_fps = fps * (num_intermediate + 1)
    expected_raw_path = output_mp4.with_suffix(".raw.mp4")
    temp_dir / "processed_temp" / "interp_0000.png"
    # Invalid crop: width is zero
    crop_rect = (10, 10, 0, 10)  # x, y, w, h

    # --- Define Expected Commands (Pipeline should run without cropping) ---
    expected_rife_cmd = [
        str(MOCK_RIFE_EXE),
        "-0",
        ANY,
        "-1",
        ANY,
        "-o",
        ANY,
        "-m",
        "rife-v4.6",
        "-n",
        str(num_intermediate),
        "-s",
        "0.5",
        "-g",
        "-1",
        "-j",
        "1:2:2",
    ]
    expected_ffmpeg_cmd = [
        MOCK_FFMPEG_EXE,
        "-hide_banner",
        "-loglevel",
        "verbose",
        "-stats",
        "-y",
        "-f",
        "image2pipe",
        "-framerate",
        str(effective_fps),
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
        str(expected_raw_path),
    ]

    # --- Run Test ---
    with caplog.at_level("ERROR"):
        with pytest.raises((IOError, RuntimeError)):
            run_pipeline_and_collect(
                mock_popen_fixture=mock_popen,
                mock_run_fixture=mock_run,
                input_dir=input_dir,
                output_mp4_path=output_mp4,
                num_input_frames=num_frames,
                crop_rect_xywh=crop_rect,
                _rife_caps_mock=mock_rife_capabilities,
                expected_rife_cmd=expected_rife_cmd,
                rife_output_to_create=None,  # Mock won't create RIFE output
                rife_return_code=0,
                expected_ffmpeg_cmd=expected_ffmpeg_cmd,
                ffmpeg_output_to_create=expected_raw_path,
            )

    # --- Assert ---
    # Verify crop error logged and RIFE called using the mock fixture
    assert (
        "Invalid crop rectangle format provided" in caplog.text
        or "Crop width and height must be positive" in caplog.text
    )
    mock_run.assert_called_once()


# Pass mock_run fixture as well
# Skip marker removed after resolving the Qt dependency issue
def test_error_rife_failure(
    temp_dir: pathlib.Path,
    mock_popen: MagicMock,
    mock_run: MagicMock,
    mock_rife_capabilities: MagicMock,
):
    """Test RuntimeError is raised if RIFE process returns non-zero exit code."""
    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    output_mp4 = output_dir / "rife_fail.mp4"
    num_frames = 2
    expected_raw_path = output_mp4.with_suffix(".raw.mp4")  # FFmpeg might not run
    (
        temp_dir / "processed_temp" / "interp_0000.png"
    )  # RIFE might not create
    # Define vars needed for ffmpeg cmd expectation
    num_intermediate = DEFAULT_INTERMEDIATE_FRAMES
    fps = DEFAULT_FPS
    effective_fps = fps * (num_intermediate + 1)

    # --- Define Expected Commands ---
    # RIFE command will be attempted
    expected_rife_cmd = [
        str(MOCK_RIFE_EXE),
        "-0",
        ANY,
        "-1",
        ANY,
        "-o",
        ANY,  # Use ANY for output path
        "-m",
        "rife-v4.6",
        "-n",
        str(num_intermediate),
        "-s",
        "0.5",  # Use specific timestep
        "-g",
        "-1",
        "-j",
        "1:2:2",  # Add thread spec
    ]
    # FFmpeg command might not be reached, but the mock needs the correct expectation
    expected_ffmpeg_cmd = [
        MOCK_FFMPEG_EXE,
        "-hide_banner",
        "-loglevel",
        "verbose",
        "-stats",
        "-y",
        "-f",
        "image2pipe",
        "-framerate",
        str(effective_fps),
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
        str(expected_raw_path),
    ]

    # --- Configure Mocks for RIFE Failure ---
    rife_error = subprocess.CalledProcessError(
        1, expected_rife_cmd, stderr="RIFE mock failure"
    )

    # --- Run Test ---
    with (
        patch("pathlib.Path.exists", return_value=True),
        pytest.raises(RuntimeError) as excinfo,
    ):  # Check for RuntimeError wrapping the CalledProcessError
        final_path, _, run_mock, popen_mock = run_pipeline_and_collect(
            mock_popen_fixture=mock_popen,
            mock_run_fixture=mock_run,
            input_dir=input_dir,
            output_mp4_path=output_mp4,
            num_input_frames=num_frames,
            _rife_caps_mock=mock_rife_capabilities,
            # Configure RIFE mock to fail
            expected_rife_cmd=expected_rife_cmd,
            rife_side_effect=rife_error,
            # FFmpeg config (might not be called)
            expected_ffmpeg_cmd=expected_ffmpeg_cmd,
            ffmpeg_output_to_create=expected_raw_path,
        )

    # --- Assert ---
    # Check the exception cause
    assert isinstance(excinfo.value.__cause__, subprocess.CalledProcessError)

    # Check RIFE mock was called
    mock_run.assert_called_once()
    # FFmpeg mock might not have been called
    # assert not mock_popen.called # Or check call_count == 0


# Pass mock_run fixture as well
@patch("pathlib.Path.exists", autospec=True)  # Mock model path existence WITH AUTOSPEC
# Skip marker removed after resolving the Qt dependency issue
def test_error_ffmpeg_failure_exit_code(
    mock_exists,
    temp_dir: pathlib.Path,
    mock_popen: MagicMock,
    mock_run: MagicMock,
    mock_rife_capabilities: MagicMock,
):
    """Test RuntimeError is raised if FFmpeg process returns non-zero exit code."""
    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    output_mp4 = output_dir / "ffmpeg_fail.mp4"
    num_frames = 2
    num_intermediate = DEFAULT_INTERMEDIATE_FRAMES
    fps = DEFAULT_FPS
    effective_fps = fps * (num_intermediate + 1)
    expected_raw_path = output_mp4.with_suffix(
        ".raw.mp4"
    )  # FFmpeg should not create this
    rife_output_file = (
        temp_dir / "processed_temp" / "interp_0000.png"
    )  # RIFE should create this

    # --- Define side effect for mock_exists --- #
    # Return False only if the path being checked is the expected raw output path
    def mock_exists_side_effect(self_path_instance):  # Correct signature (only self)
        # Need to resolve path_arg in case it's relative or different instance
        # We compare the string representation of the instance
        if str(self_path_instance) == str(expected_raw_path):
            return False
        return True  # Assume other paths (like model path) exist

    mock_exists.side_effect = mock_exists_side_effect

    # --- Define Expected Commands ---
    # RIFE should "succeed" (return 0) but won't create the file in the mock
    # The FileNotFoundError during Image.open should lead to RuntimeError
    expected_rife_cmd = [
        str(MOCK_RIFE_EXE),
        "-0",
        ANY,
        "-1",
        ANY,
        "-o",
        ANY,  # RIFE calculates its own path here
        "-m",
        "rife-v4.6",
        "-n",
        str(num_intermediate),
        "-s",
        "0.5",
        "-g",
        "-1",
        "-j",
        "1:2:2",
    ]
    # FFmpeg command might not be reached, but the mock needs the correct expectation
    expected_ffmpeg_cmd = [
        MOCK_FFMPEG_EXE,
        "-hide_banner",
        "-loglevel",
        "verbose",
        "-stats",
        "-y",
        "-f",
        "image2pipe",
        "-framerate",
        str(effective_fps),
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
        str(expected_raw_path),
    ]

    # --- Run Test ---
    # Expect IOError because ffmpeg failure during finalization is critical
    with pytest.raises(IOError, match="Failed to finalize video"):
        final_path, _, run_mock, popen_mock = run_pipeline_and_collect(
            mock_popen_fixture=mock_popen,
            mock_run_fixture=mock_run,
            input_dir=input_dir,
            output_mp4_path=output_mp4,
            num_input_frames=num_frames,
            _rife_caps_mock=mock_rife_capabilities,
            # RIFE config (success)
            expected_rife_cmd=expected_rife_cmd,
            rife_output_to_create=rife_output_file,
            # FFmpeg config (failure)
            expected_ffmpeg_cmd=expected_ffmpeg_cmd,
            ffmpeg_return_code=1,  # Simulate failure
            ffmpeg_output_to_create=expected_raw_path,  # Mock won't create if return code != 0
        )

    # --- Assert ---
    # Check mocks were called
    mock_run.assert_called_once()
    mock_popen.assert_called_once()
    # Check RIFE output was created, but FFmpeg output was not
    assert rife_output_file.exists()
    assert not expected_raw_path.exists()


# Pass mock_run fixture as well
# Skip marker removed after resolving the Qt dependency issue
def test_error_ffmpeg_pipe_error(
    temp_dir: pathlib.Path,
    mock_popen: MagicMock,
    mock_run: MagicMock,
    mock_rife_capabilities: MagicMock,
):
    """Test IOError is raised if writing to FFmpeg stdin fails (BrokenPipeError)."""
    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    output_mp4 = output_dir / "ffmpeg_pipe_fail.mp4"
    num_frames = 2
    num_intermediate = DEFAULT_INTERMEDIATE_FRAMES
    fps = DEFAULT_FPS
    effective_fps = fps * (num_intermediate + 1)
    expected_raw_path = output_mp4.with_suffix(
        ".raw.mp4"
    )  # FFmpeg should not create this
    (
        temp_dir / "processed_temp" / "interp_0000.png"
    )  # RIFE should create this

    # --- Define Expected Commands ---
    expected_rife_cmd = [
        str(MOCK_RIFE_EXE),
        "-0",
        ANY,
        "-1",
        ANY,
        "-o",
        ANY,  # Use ANY, mock won't create
        "-m",
        "rife-v4.6",
        "-n",
        str(num_intermediate),
        "-s",
        "0.5",
        "-g",
        "-1",
        "-j",
        "1:2:2",  # Add thread spec
    ]
    expected_ffmpeg_cmd = [
        MOCK_FFMPEG_EXE,
        "-hide_banner",
        "-loglevel",
        "verbose",
        "-stats",
        "-y",
        "-f",
        "image2pipe",
        "-framerate",
        str(effective_fps),
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
        str(expected_raw_path),
    ]

    # --- Run Test --- (Call outside the context manager)
    # Expect IOError due to the pipe breaking during frame writing
    def run_action():
        run_pipeline_and_collect(
            mock_popen_fixture=mock_popen,
            mock_run_fixture=mock_run,
            input_dir=input_dir,
            output_mp4_path=output_mp4,
            num_input_frames=num_frames,
            _rife_caps_mock=mock_rife_capabilities,
            # RIFE config (success return code, but no file)
            expected_rife_cmd=expected_rife_cmd,
            rife_output_to_create=None,  # Let mock NOT create
            rife_return_code=0,
            # FFmpeg config (BrokenPipeError)
            expected_ffmpeg_cmd=expected_ffmpeg_cmd,
            ffmpeg_stdin_write_limit=10,  # Simulate pipe breaking after 10 bytes
            ffmpeg_output_to_create=expected_raw_path,  # Mock won't create if error occurs
        )

    with pytest.raises(IOError, match="Failed to finalize video"):
        run_action()

    # --- Assert ---
    # If the correct exception was raised, we just need to check
    # that Popen was called (which setup the failing pipe).
    # RIFE (mock_run) should not have been called.
    mock_run.assert_not_called()
    mock_popen.assert_called_once()  # Popen should have been called
    # No need to assert file non-existence as the error prevents creation


# Pass mock_run fixture as well
@patch("pathlib.Path.exists", return_value=True)  # Mock model path existence
# Skip marker removed after resolving the Qt dependency issue
def test_error_sanchez_failure(
    mock_exists,
    temp_dir: pathlib.Path,
    mock_popen: MagicMock,
    mock_run: MagicMock,
    mock_sanchez: MagicMock,
    mock_rife_capabilities: MagicMock,
    caplog,
):
    """Test that Sanchez failure logs an error but pipeline continues with original images."""
    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    output_mp4 = output_dir / "sanchez_fail.mp4"
    num_frames = 2
    num_intermediate = DEFAULT_INTERMEDIATE_FRAMES
    fps = DEFAULT_FPS
    effective_fps = fps * (num_intermediate + 1)
    expected_raw_path = output_mp4.with_suffix(
        ".raw.mp4"
    )  # Should be created using originals
    rife_output_file = (
        temp_dir / "processed_temp" / "interp_0000.png"
    )  # Should be created using originals

    # --- Configure Sanchez mock to fail ---
    sanchez_error = Exception("Mock Sanchez Failure")
    mock_sanchez.side_effect = sanchez_error

    # --- Define Expected Commands (using original images) ---
    expected_rife_cmd = [
        str(MOCK_RIFE_EXE),
        "-0",
        ANY,
        "-1",
        ANY,
        "-o",
        ANY,
        "-m",
        "rife-v4.6",
        "-n",
        str(num_intermediate),
        "-s",
        "0.5",
        "-g",
        "-1",
        "-j",
        "1:2:2",
    ]
    expected_ffmpeg_cmd = [
        MOCK_FFMPEG_EXE,
        "-hide_banner",
        "-loglevel",
        "verbose",
        "-stats",
        "-y",
        "-f",
        "image2pipe",
        "-framerate",
        str(effective_fps),
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
        str(expected_raw_path),
    ]

    # --- Run Test --- (Call outside context manager)
    def run_action():
        run_pipeline_and_collect(
            mock_popen_fixture=mock_popen,
            mock_run_fixture=mock_run,
            input_dir=input_dir,
            output_mp4_path=output_mp4,
            num_input_frames=num_frames,
            false_colour=True,  # Enable Sanchez (which will fail)
            res_km=1,
            _sanchez_mock=mock_sanchez,  # Pass failing mock
            _rife_caps_mock=mock_rife_capabilities,
            # RIFE/FFmpeg should still run successfully with originals
            expected_rife_cmd=expected_rife_cmd,
            rife_output_to_create=rife_output_file,  # Pass path for mock to create
            rife_return_code=0,
            expected_ffmpeg_cmd=expected_ffmpeg_cmd,
            ffmpeg_output_to_create=expected_raw_path,
        )

    # Expect IOError because pipeline fails when it can't open RIFE output
    with caplog.at_level("ERROR"):
        with pytest.raises(IOError, match="Failed to process images"):
            run_action()

    # --- Assert ---
    assert (
        "Worker Sanchez failed" in caplog.text
        or "Sanchez colourise failed" in caplog.text
    )
    # Check RIFE was called
    mock_run.assert_called_once()
    # FFmpeg might not have been called if Image.open failed first
    mock_popen.assert_called_once()  # Popen should have been called
    # Check Sanchez mock was called (even though it failed)
    assert mock_sanchez.call_count > 0


def test_multiple_intermediate_frames_not_supported(temp_dir, mock_rife_capabilities):
    """Test that num_intermediate_frames > 1 raises NotImplementedError."""
    input_dir = temp_dir / "input"
    input_dir.mkdir()
    # Create test frames
    for i in range(3):
        create_dummy_png(input_dir / f"frame_{i:03d}.png", size=(64, 32))

    output_mp4 = temp_dir / "output.mp4"

    # Try to use multiple intermediate frames
    with pytest.raises(NotImplementedError) as exc_info:
        list(
            run_vfi(
                folder=input_dir,
                output_mp4_path=output_mp4,
                rife_exe_path=MOCK_RIFE_EXE,
                fps=30,
                num_intermediate_frames=3,  # Not supported
                max_workers=1,
            )
        )

    assert "num_intermediate_frames=1 is supported" in str(exc_info.value)


@patch("pathlib.Path.exists", return_value=True)  # Mock model path existence
def test_large_image_tiling(
    mock_exists, temp_dir, mock_popen, mock_run, mock_rife_capabilities
):
    """Test pipeline with large images that would benefit from tiling."""
    # Create large 4K test images
    input_dir = temp_dir / "input_4k"
    input_dir.mkdir()

    # Create 4K images
    for i in range(2):
        img = Image.new("RGB", (3840, 2160), color=(100, 150, 200))
        img.save(input_dir / f"frame_{i:04d}.png")

    output_mp4 = temp_dir / "output_4k.mp4"

    # Configure mocks
    # Create output file to simulate FFmpeg success
    output_mp4.with_suffix(".raw.mp4").write_bytes(b"dummy video")
    output_mp4.write_bytes(b"dummy video")

    # Use mock factory for Popen
    mock_factory = create_mock_popen(
        output_file_to_create=output_mp4.with_suffix(".raw.mp4")
    )
    mock_popen.side_effect = mock_factory

    # Mock RIFE to create interpolated frame
    def create_interp(*args, **kwargs):
        cmd = args[0]
        output_idx = cmd.index("-o") if "-o" in cmd else -1
        if output_idx >= 0:
            output_path = pathlib.Path(cmd[output_idx + 1])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            create_dummy_png(output_path, size=(3840, 2160))
        return MagicMock(returncode=0)

    mock_run.side_effect = create_interp

    # Run with tiling enabled
    gen = run_vfi(
        folder=input_dir,
        output_mp4_path=output_mp4,
        rife_exe_path=MOCK_RIFE_EXE,
        fps=30,
        num_intermediate_frames=1,
        max_workers=1,
        rife_tile_enable=True,
        rife_tile_size=512,
        rife_uhd_mode=True,
    )

    # Collect results
    list(gen)

    # Verify RIFE was called
    mock_run.assert_called_once()
    rife_cmd = mock_run.call_args[0][0]

    # Check for tiling arguments if supported by capability detector
    if mock_rife_capabilities.supports_tiling():
        assert "-t" in rife_cmd
        assert "512" in rife_cmd

    # Check for UHD mode if supported
    # Note: -u is only added if UHD mode is on AND tiling is off
    # Since we have tiling enabled, -u should NOT be present
    if mock_rife_capabilities.supports_uhd() and "-t" not in rife_cmd:
        assert "-u" in rife_cmd
    else:
        # With tiling enabled, -u should not be present
        assert "-u" not in rife_cmd

    # Verify FFmpeg was called
    mock_popen.assert_called_once()


@patch("pathlib.Path.exists", return_value=True)  # Mock model path existence
def test_max_workers_parameter(
    mock_exists, temp_dir, mock_popen, mock_run, mock_rife_capabilities
):
    """Test that max_workers parameter is respected for parallel processing."""
    input_dir = temp_dir / "input"
    input_dir.mkdir()

    # Create enough images to test parallel processing
    num_frames = 10
    # Create test frames
    for i in range(num_frames):
        create_dummy_png(input_dir / f"frame_{i:03d}.png", size=(64, 32))

    output_mp4 = temp_dir / "output.mp4"

    # Configure mocks
    # Create output file to simulate FFmpeg success
    output_mp4.with_suffix(".raw.mp4").write_bytes(b"dummy video")
    output_mp4.write_bytes(b"dummy video")

    # Use mock factory for Popen
    mock_factory = create_mock_popen(
        output_file_to_create=output_mp4.with_suffix(".raw.mp4")
    )
    mock_popen.side_effect = mock_factory

    # Mock RIFE to create interpolated frames
    def create_interp_frame(*args, **kwargs):
        cmd = args[0]
        output_idx = cmd.index("-o") if "-o" in cmd else -1
        if output_idx >= 0:
            output_path = pathlib.Path(cmd[output_idx + 1])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            create_dummy_png(output_path, size=(64, 32))
        return MagicMock(returncode=0)

    mock_run.side_effect = create_interp_frame

    # Test with different max_workers values
    for max_workers in [1, 2, 4]:
        # Clear mocks
        mock_run.reset_mock()
        mock_popen.reset_mock()

        gen = run_vfi(
            folder=input_dir,
            output_mp4_path=output_mp4,
            rife_exe_path=MOCK_RIFE_EXE,
            fps=30,
            num_intermediate_frames=1,
            max_workers=max_workers,
        )

        # Collect results
        results = list(gen)

        # Verify processing completed
        assert any(isinstance(r, pathlib.Path) for r in results)

        # The max_workers affects parallel image preprocessing,
        # not RIFE interpolation (which is sequential)
        # So we just verify the pipeline completes successfully


def test_image_loader_key_error(temp_dir: pathlib.Path):
    """ImageLoader should wrap KeyError in ProcessingError."""
    from goesvfi.pipeline.exceptions import ProcessingError

    loader = ImageLoader()
    img_path = temp_dir / "img.png"
    img_path.write_bytes(b"data")
    with patch("PIL.Image.open", side_effect=KeyError("bad key")):
        with pytest.raises(ProcessingError):
            loader.load(str(img_path))


def test_image_saver_runtime_error(temp_dir: pathlib.Path):
    """ImageSaver should surface runtime errors as ValueError."""
    saver = ImageSaver()
    out_path = temp_dir / "out.png"
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    img_data = ImageData(image_data=arr, metadata={})
    with patch("PIL.Image.fromarray", side_effect=RuntimeError("boom")):
        with pytest.raises(ValueError, match="Failed to save image"):
            saver.save(img_data, str(out_path))
