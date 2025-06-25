import subprocess  # Import subprocess for exceptions
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

import goesvfi.pipeline.interpolate as interpolate_mod

# Import the mock utility
from tests.utils.mocks import create_mock_subprocess_run


@pytest.fixture
def dummy_img():
    # 4x4 RGB float32 image
    return np.ones((4, 4, 3), dtype=np.float32)


@pytest.fixture
def dummy_backend():
    backend = MagicMock(spec=interpolate_mod.RifeBackend)
    return backend


def test_interpolate_pair_invokes_command_and_file_ops(tmp_path, dummy_img):
    # Patch all external dependencies in interpolate_pair
    with (
        patch.object(interpolate_mod, "RifeCommandBuilder") as mock_cmd_builder_cls,
        patch("goesvfi.pipeline.interpolate.subprocess.run") as mock_run_patch,
        patch("goesvfi.pipeline.interpolate.Image.fromarray") as mock_fromarray,
        patch("goesvfi.pipeline.interpolate.Image.open") as mock_image_open,
        patch("goesvfi.pipeline.interpolate.shutil.rmtree") as mock_rmtree,
        patch("goesvfi.pipeline.interpolate.pathlib.Path.exists", return_value=True) as mock_exists,
    ):  # Give exists a name
        # --- Setup Mocks ---
        # Mock Command Builder (as before)
        mock_cmd_builder = MagicMock()
        expected_rife_cmd = ["rife", "args"]  # Command returned by the mocked builder
        mock_cmd_builder.build_command.return_value = expected_rife_cmd
        # Set capabilities on the mock detector instance
        mock_cmd_builder.detector = MagicMock()
        mock_cmd_builder.detector.supports_tiling.return_value = True
        mock_cmd_builder.detector.supports_uhd.return_value = True
        mock_cmd_builder.detector.supports_tta_spatial.return_value = False
        mock_cmd_builder.detector.supports_tta_temporal.return_value = False
        mock_cmd_builder.detector.supports_thread_spec.return_value = True
        mock_cmd_builder_cls.return_value = mock_cmd_builder

        # Mock subprocess.run using the factory
        # Need to predict the output path: tmpdir / "out.png"
        # Since tmpdir is created inside, we can't know the exact path easily.
        # Let's assume the mock file creation isn't strictly needed here,
        # as the function reads the file back via mock_image_open.
        # We primarily care about the command being called correctly.
        mock_run_factory = create_mock_subprocess_run(
            expected_command=expected_rife_cmd,
            # output_file_to_create=... # Path is dynamic, skip for now
        )
        mock_run_patch.side_effect = mock_run_factory

        # Mock Image loading/saving (as before)
        mock_pil_image = MagicMock(spec=interpolate_mod.Image.Image)
        mock_pil_image.convert.return_value = mock_pil_image  # Return self for convert
        mock_pil_image.size = (4, 4)
        # Simulate Image.open returning a usable image mock that can be converted to numpy array
        mock_image_open.return_value.__enter__.return_value = mock_pil_image  # Handle context manager if used

        # Mock np.array to return a valid array when called on the mock PIL image
        with patch("numpy.array", return_value=np.ones((4, 4, 3), dtype=np.uint8)) as mock_np_array:
            # --- Setup Backend ---
            # Create dummy executable file before creating backend
            dummy_exe_path = tmp_path / "rife-cli"
            dummy_exe_path.touch()
            backend = interpolate_mod.RifeBackend(exe_path=dummy_exe_path)
            # Remove unnecessary mock of is_file, file actually exists now
            # backend.exe.is_file = MagicMock(return_value=True) # Ensure exe is seen as valid

            # --- Act ---
            result = backend.interpolate_pair(dummy_img, dummy_img, options={"timestep": 0.5, "tile_enable": True})

            # --- Assert ---
            # Check command builder was called
            mock_cmd_builder.build_command.assert_called_once()
            # Check subprocess.run was called with the expected command
            mock_run_patch.assert_called_once_with(
                expected_rife_cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            # Check output file was checked for existence (using the dynamic path)
            assert mock_exists.called  # Path.exists should have been called
            # Check Image.open was called (to load the result)
            mock_image_open.assert_called_once()
            # Check numpy.array was called (to convert PIL image)
            mock_np_array.assert_called_once()
            # Check rmtree was called to clean up
            mock_rmtree.assert_called_once()
            # Check result is a float32 numpy array
            assert isinstance(result, np.ndarray)
            assert result.dtype == np.float32


def test_interpolate_pair_raises_on_subprocess_error(tmp_path, dummy_img):
    # Mock Command Builder needs to be patched *within this test* scope
    with (
        patch.object(interpolate_mod, "RifeCommandBuilder") as mock_cmd_builder_cls,
        patch("goesvfi.pipeline.interpolate.subprocess.run") as mock_run_patch,
        patch("goesvfi.pipeline.interpolate.Image.fromarray"),
        patch("goesvfi.pipeline.interpolate.Image.open"),
        patch("goesvfi.pipeline.interpolate.shutil.rmtree") as mock_rmtree,
        patch("goesvfi.pipeline.interpolate.pathlib.Path.exists", return_value=True),
    ):  # Keep exists mock simple
        mock_cmd_builder = MagicMock()
        expected_rife_cmd = ["rife", "args"]
        mock_cmd_builder.build_command.return_value = expected_rife_cmd
        mock_cmd_builder.detector = MagicMock()  # Add detector mock
        mock_cmd_builder.detector.supports_tiling.return_value = True  # Example capability
        mock_cmd_builder_cls.return_value = mock_cmd_builder  # Now mock_cmd_builder_cls is defined

        # Use mock factory to raise CalledProcessError
        rife_error = subprocess.CalledProcessError(1, expected_rife_cmd, stderr="fail")
        mock_run_factory = create_mock_subprocess_run(expected_command=expected_rife_cmd, side_effect=rife_error)
        mock_run_patch.side_effect = mock_run_factory  # Assign side_effect to the correct mock

        # Create dummy executable
        dummy_exe_path = tmp_path / "rife-cli"
        dummy_exe_path.touch()
        backend = interpolate_mod.RifeBackend(exe_path=dummy_exe_path)
        # backend.exe.is_file = MagicMock(return_value=True) # Not needed

        # Act & Assert
        with pytest.raises(RuntimeError) as excinfo:
            backend.interpolate_pair(dummy_img, dummy_img)

        # Check the exception message and cause
        assert "RIFE executable failed" in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, subprocess.CalledProcessError)

        # Assert mock run was called
        mock_run_patch.assert_called_once()
        # Assert cleanup (rmtree) was still called
        mock_rmtree.assert_called_once()


def test_interpolate_three_calls_interpolate_pair_correctly(dummy_img, dummy_backend):
    # Setup: interpolate_pair returns dummy frames
    dummy_backend.interpolate_pair.side_effect = [
        np.full((4, 4, 3), 0.25, dtype=np.float32),  # left
        np.full((4, 4, 3), 0.5, dtype=np.float32),  # mid
        np.full((4, 4, 3), 0.75, dtype=np.float32),  # right
    ]
    options = {"tile_enable": True, "tile_size": 128}

    # Call interpolate_three
    result = interpolate_mod.interpolate_three(dummy_img, dummy_img, dummy_backend, options)

    # Should call interpolate_pair three times
    assert dummy_backend.interpolate_pair.call_count == 3

    # Check the arguments for each call
    calls = dummy_backend.interpolate_pair.call_args_list
    # 1st: img1, img2, timestep=0.5 (mid)
    np.testing.assert_array_equal(calls[0].args[0], dummy_img)
    np.testing.assert_array_equal(calls[0].args[1], dummy_img)
    # Check timestep within options dict (positional arg 2)
    assert calls[0].args[2]["timestep"] == 0.5
    assert calls[0].args[2]["tile_enable"] is True  # Check other options passed
    assert calls[0].kwargs == {}  # Should be no kwargs

    # 2nd: img1, img_mid, timestep=0.5 (left)
    # 3rd: img_mid, img2, timestep=0.5 (right)
    # (img_mid is the result of the first call)
    np.testing.assert_array_equal(calls[1].args[0], dummy_img)
    np.testing.assert_array_equal(calls[1].args[1], result[1])  # result[1] is img_mid
    assert calls[1].args[2]["timestep"] == 0.5  # Check options dict in positional arg

    np.testing.assert_array_equal(calls[2].args[0], result[1])  # result[1] is img_mid
    np.testing.assert_array_equal(calls[2].args[1], dummy_img)
    assert calls[2].args[2]["timestep"] == 0.5  # Check options dict in positional arg

    # Check result is a list of three float32 arrays
    assert isinstance(result, list)
    assert all(isinstance(arr, np.ndarray) and arr.dtype == np.float32 for arr in result)
    assert np.allclose(result[0], 0.5)  # img_left corresponds to second call
    assert np.allclose(result[1], 0.25)  # img_mid corresponds to first call
    assert np.allclose(result[2], 0.75)  # img_right corresponds to third call
