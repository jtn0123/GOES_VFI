import pathlib

from goesvfi.view_models.processing_view_model import ProcessingViewModel


def test_build_ffmpeg_command_with_crop():
    vm = ProcessingViewModel()
    output = pathlib.Path("/tmp/out.mp4")
    settings = {"encoder": "Software x264", "crf": 20, "pix_fmt": "yuv420p"}
    cmd = vm.build_ffmpeg_command(output, 30, (10, 20, 100, 80), settings)
    idx = cmd.index("-filter:v")
    assert cmd[idx + 1].startswith("crop=100:80:10:20")
    assert str(output) in cmd


def test_build_ffmpeg_command_without_crop():
    vm = ProcessingViewModel()
    output = pathlib.Path("/tmp/out.mp4")
    settings = {"encoder": "Software x264"}
    cmd = vm.build_ffmpeg_command(output, 24, None, settings)
    assert "-filter:v" not in cmd

