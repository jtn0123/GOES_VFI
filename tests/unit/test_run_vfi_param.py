import pathlib
import subprocess
from unittest.mock import ANY, MagicMock, patch

import pytest

from goesvfi.pipeline import run_vfi as run_vfi_mod
from tests.utils.mocks import (
    create_mock_colourise,
    create_mock_popen,
    create_mock_subprocess_run,
)


def create_test_png(path: pathlib.Path, size: tuple = (4, 4)) -> pathlib.Path:
    """Create a tiny PNG image for testing."""
    import numpy as np
    from PIL import Image

    img_array = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    img = Image.fromarray(img_array)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")
    return path


def make_dummy_images(tmp_path: pathlib.Path, count: int) -> list[pathlib.Path]:
    paths = []
    for i in range(count):
        p = tmp_path / f"img{i}.png"
        create_test_png(p)
        paths.append(p)
    return paths


@pytest.fixture
def mock_capability_detector(mocker):
    from goesvfi.utils.rife_analyzer import RifeCapabilityDetector

    mock_detector = mocker.MagicMock(spec=RifeCapabilityDetector)
    mock_detector.supports_thread_spec.return_value = True
    return mocker.patch("goesvfi.pipeline.run_vfi.RifeCapabilityDetector", return_value=mock_detector)


@pytest.mark.parametrize(
    "scenario, expect_error",
    [
        ("skip", False),
        ("rife_fail", True),
        ("ffmpeg_fail", True),
        ("sanchez", False),
        ("sanchez_fail", False),
    ],
)
def test_run_vfi_scenarios(scenario, expect_error, tmp_path, mocker, mock_capability_detector):
    img_paths = make_dummy_images(tmp_path, 2)
    output_mp4 = tmp_path / "out.mp4"
    raw_output = output_mp4.with_suffix(".raw.mp4")
    rife_exe = tmp_path / "rife"

    with (
        patch("goesvfi.pipeline.run_vfi.subprocess.run") as mock_run,
        patch("goesvfi.pipeline.run_vfi.subprocess.Popen") as mock_popen,
        patch("goesvfi.pipeline.run_vfi.ProcessPoolExecutor") as mock_exec,
        patch("goesvfi.pipeline.run_vfi.Image.open") as mock_img_open,
        patch("goesvfi.pipeline.run_vfi.tempfile.TemporaryDirectory") as mock_tmpdir,
        patch.object(pathlib.Path, "glob", return_value=img_paths),
        patch("goesvfi.pipeline.run_vfi.pathlib.Path.exists", return_value=True),
        patch("goesvfi.pipeline.run_vfi.pathlib.Path.unlink", lambda *_a, **_k: None),
    ):
        mock_exec.return_value.__enter__.return_value = MagicMock(map=lambda fn, it: it)
        mock_img = MagicMock()
        mock_img.size = (4, 4)
        mock_img.__enter__.return_value = mock_img
        mock_img_open.return_value = mock_img
        mock_tmpdir.return_value.__enter__.return_value = tmp_path

        kwargs = {}
        if scenario == "skip":
            kwargs["skip_model"] = True
            mock_run.side_effect = None
            mock_popen.side_effect = create_mock_popen(output_file_to_create=raw_output)
        elif scenario == "rife_fail":
            mock_run.side_effect = create_mock_subprocess_run(side_effect=subprocess.CalledProcessError(1, "rife"))
            mock_popen.side_effect = create_mock_popen(output_file_to_create=raw_output)
        elif scenario == "ffmpeg_fail":
            mock_run.side_effect = create_mock_subprocess_run(output_file_to_create=tmp_path / "interp.png")
            mock_popen.side_effect = create_mock_popen(returncode=1, stderr=b"fail")
        elif scenario == "sanchez":
            kwargs.update({"false_colour": True, "res_km": 2})
            mock_run.side_effect = create_mock_subprocess_run(output_file_to_create=tmp_path / "interp.png")
            mock_popen.side_effect = create_mock_popen(output_file_to_create=raw_output)
            mocker.patch(
                "goesvfi.pipeline.run_vfi.colourise",
                create_mock_colourise(output_file_to_create=tmp_path / "fc.png"),
            )
        elif scenario == "sanchez_fail":
            kwargs.update({"false_colour": True, "res_km": 2})
            mock_run.side_effect = create_mock_subprocess_run(output_file_to_create=tmp_path / "interp.png")
            mock_popen.side_effect = create_mock_popen(output_file_to_create=raw_output)
            mocker.patch(
                "goesvfi.pipeline.run_vfi.colourise",
                create_mock_colourise(side_effect=RuntimeError("fail")),
            )

        def run():
            return list(
                run_vfi_mod.run_vfi(
                    folder=tmp_path,
                    output_mp4_path=output_mp4,
                    rife_exe_path=rife_exe,
                    fps=10,
                    num_intermediate_frames=1,
                    max_workers=1,
                    **kwargs,
                )
            )

        if expect_error:
            from goesvfi.pipeline.exceptions import (
                FFmpegError,
                ProcessingError,
                RIFEError,
            )

            with pytest.raises((RuntimeError, ProcessingError, RIFEError, FFmpegError)):
                run()
        else:
            results = run()
            assert any(isinstance(r, pathlib.Path) for r in results)
            assert raw_output.exists()
