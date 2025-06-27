import pathlib
from typing import Never
from unittest.mock import patch

import pytest

from goesvfi.pipeline.run_ffmpeg import run_ffmpeg_interpolation

from tests.utils.helpers import create_dummy_png


def _create_inputs(tmp_path: pathlib.Path, count: int = 2) -> pathlib.Path:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    for i in range(count):
        create_dummy_png(input_dir / f"frame_{i}.png", size=(8, 8))
    return input_dir


def test_ffmpeg_interpolation_success(tmp_path: pathlib.Path) -> None:
    input_dir = _create_inputs(tmp_path)
    output_file = tmp_path / "out.mp4"
    captured = {}

    def fake_run(cmd, desc, monitor_memory=False) -> None:
        captured["cmd"] = cmd
        output_file.write_text("done")

    with patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command", side_effect=fake_run) as mock_run:
        result = run_ffmpeg_interpolation(
            input_dir=input_dir,
            output_mp4_path=output_file,
            fps=30,
            num_intermediate_frames=1,
            _use_preset_optimal=False,
            crop_rect=(0, 0, 4, 4),
            debug_mode=False,
            use_ffmpeg_interp=True,
            filter_preset="fast",
            mi_mode="mci",
            mc_mode="obmc",
            me_mode="bidir",
            me_algo="",
            search_param=32,
            scd_mode="fdiff",
            scd_threshold=10.0,
            minter_mb_size=None,
            minter_vsbmc=0,
            apply_unsharp=False,
            unsharp_lx=5,
            unsharp_ly=5,
            unsharp_la=1.0,
            unsharp_cx=5,
            unsharp_cy=5,
            unsharp_ca=0.0,
            crf=18,
            bitrate_kbps=1000,
            bufsize_kb=1500,
            pix_fmt="yuv420p",
        )

    assert result == output_file
    assert output_file.exists()
    cmd_str = " ".join(captured["cmd"])
    assert "minterpolate" in cmd_str
    assert "crop=4:4:0:0" in cmd_str
    mock_run.assert_called_once()


def test_ffmpeg_interpolation_failure(tmp_path: pathlib.Path) -> None:
    input_dir = _create_inputs(tmp_path)
    output_file = tmp_path / "out.mp4"

    def fail_run(*_a, **_k) -> Never:
        msg = "ffmpeg failed"
        raise RuntimeError(msg)

    with patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command", side_effect=fail_run):
        with pytest.raises(RuntimeError):
            run_ffmpeg_interpolation(
                input_dir=input_dir,
                output_mp4_path=output_file,
                fps=30,
                num_intermediate_frames=1,
                _use_preset_optimal=False,
                crop_rect=None,
                debug_mode=False,
                use_ffmpeg_interp=True,
                filter_preset="fast",
                mi_mode="mci",
                mc_mode="obmc",
                me_mode="bidir",
                me_algo="",
                search_param=32,
                scd_mode="fdiff",
                scd_threshold=10.0,
                minter_mb_size=None,
                minter_vsbmc=0,
                apply_unsharp=False,
                unsharp_lx=5,
                unsharp_ly=5,
                unsharp_la=1.0,
                unsharp_cx=5,
                unsharp_cy=5,
                unsharp_ca=0.0,
                crf=18,
                bitrate_kbps=1000,
                bufsize_kb=1500,
                pix_fmt="yuv420p",
            )
