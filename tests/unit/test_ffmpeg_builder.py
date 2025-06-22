import os
import pathlib
import unittest

from goesvfi.pipeline.ffmpeg_builder import FFmpegCommandBuilder


class TestFFmpegCommandBuilder(unittest.TestCase):
    def setUp(self):
        """Set up a temporary directory and file paths for testing."""
        self.test_dir = pathlib.Path("test_temp_dir")
        self.test_dir.mkdir(exist_ok=True)
        self.input_path = self.test_dir / "input.mkv"
        self.output_path = self.test_dir / "output.mp4"
        # Create dummy files so pathlib.exists() works if needed (though not strictly necessary for builder tests)
        self.input_path.touch()
        self.output_path.touch()

    def tearDown(self):
        """Clean up the temporary directory and files."""
        if self.test_dir.exists():
            for item in self.test_dir.iterdir():
                item.unlink()
            self.test_dir.rmdir()

    def test_single_pass_x264(self):
        builder = FFmpegCommandBuilder()
        cmd = (
            builder.set_input(self.input_path)
            .set_output(self.output_path)
            .set_encoder("Software x264")
            .set_crf(23)
            .set_pix_fmt("yuv420p")
            .build()
        )
        expected_cmd_parts = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "info",
            "-stats",
            "-y",
            "-i",
            str(self.input_path),
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            str(self.output_path),
        ]
        self.assertEqual(cmd, expected_cmd_parts)

    def test_single_pass_x265(self):
        builder = FFmpegCommandBuilder()
        cmd = (
            builder.set_input(self.input_path)
            .set_output(self.output_path)
            .set_encoder("Software x265")
            .set_crf(28)
            .set_pix_fmt("yuv420p")
            .build()
        )
        expected_cmd_parts = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "info",
            "-stats",
            "-y",
            "-i",
            str(self.input_path),
            "-c:v",
            "libx265",
            "-preset",
            "slower",
            "-crf",
            "28",
            "-x265-params",
            "aq-mode=3:aq-strength=1.0:psy-rd=2.0:psy-rdoq=1.0",
            "-pix_fmt",
            "yuv420p",
            str(self.output_path),
        ]
        self.assertEqual(cmd, expected_cmd_parts)

    def test_two_pass_x265_pass1(self):
        builder = FFmpegCommandBuilder()
        pass_log_prefix = str(self.test_dir / "ffmpeg_pass")
        cmd = (
            builder.set_input(self.input_path)
            .set_output(self.output_path)
            .set_encoder("Software x265 (2-Pass)")
            .set_bitrate(1000)
            .set_pix_fmt("yuv420p")
            .set_two_pass(True, pass_log_prefix, 1)
            .build()
        )
        expected_cmd_parts = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "info",
            "-stats",
            "-y",
            "-i",
            str(self.input_path),
            "-c:v",
            "libx265",
            "-preset",
            "slower",
            "-b:v",
            "1000k",
            "-x265-params",
            "pass=1",
            "-passlogfile",
            pass_log_prefix,
            "-f",
            "null",
            os.devnull,
        ]
        self.assertEqual(cmd, expected_cmd_parts)

    def test_two_pass_x265_pass2(self):
        builder = FFmpegCommandBuilder()
        pass_log_prefix = str(self.test_dir / "ffmpeg_pass")
        cmd = (
            builder.set_input(self.input_path)
            .set_output(self.output_path)
            .set_encoder("Software x265 (2-Pass)")
            .set_bitrate(1000)
            .set_pix_fmt("yuv420p")
            .set_two_pass(True, pass_log_prefix, 2)
            .build()
        )
        expected_cmd_parts = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "info",
            "-stats",
            "-y",
            "-i",
            str(self.input_path),
            "-c:v",
            "libx265",
            "-preset",
            "slower",
            "-b:v",
            "1000k",
            "-x265-params",
            "pass=2:aq-mode=3:aq-strength=1.0:psy-rd=2.0:psy-rdoq=1.0",
            "-passlogfile",
            pass_log_prefix,
            "-pix_fmt",
            "yuv420p",
            str(self.output_path),
        ]
        self.assertEqual(cmd, expected_cmd_parts)

    def test_hardware_hevc(self):
        builder = FFmpegCommandBuilder()
        cmd = (
            builder.set_input(self.input_path)
            .set_output(self.output_path)
            .set_encoder("Hardware HEVC (VideoToolbox)")
            .set_bitrate(2000)
            .set_bufsize(4000)
            .set_pix_fmt("yuv420p")
            .build()
        )
        expected_cmd_parts = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "info",
            "-stats",
            "-y",
            "-i",
            str(self.input_path),
            "-c:v",
            "hevc_videotoolbox",
            "-tag:v",
            "hvc1",
            "-b:v",
            "2000k",
            "-maxrate",
            "4000k",
            "-pix_fmt",
            "yuv420p",
            str(self.output_path),
        ]
        self.assertEqual(cmd, expected_cmd_parts)

    def test_hardware_h264(self):
        builder = FFmpegCommandBuilder()
        cmd = (
            builder.set_input(self.input_path)
            .set_output(self.output_path)
            .set_encoder("Hardware H.264 (VideoToolbox)")
            .set_bitrate(1500)
            .set_bufsize(3000)
            .set_pix_fmt("yuv420p")
            .build()
        )
        expected_cmd_parts = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "info",
            "-stats",
            "-y",
            "-i",
            str(self.input_path),
            "-c:v",
            "h264_videotoolbox",
            "-b:v",
            "1500k",
            "-maxrate",
            "3000k",
            "-pix_fmt",
            "yuv420p",
            str(self.output_path),
        ]
        self.assertEqual(cmd, expected_cmd_parts)

    def test_stream_copy(self):
        builder = FFmpegCommandBuilder()
        cmd = (
            builder.set_input(self.input_path)
            .set_output(self.output_path)
            .set_encoder("None (copy original)")
            .build()
        )
        expected_cmd_parts = [
            "ffmpeg",
            "-y",
            "-i",
            str(self.input_path),
            "-c",
            "copy",
            str(self.output_path),
        ]
        self.assertEqual(cmd, expected_cmd_parts)

    def test_missing_input(self):
        builder = FFmpegCommandBuilder()
        builder.set_output(self.output_path).set_encoder("Software x264").set_crf(
            23
        ).set_pix_fmt("yuv420p")
        with self.assertRaises(ValueError):
            builder.build()

    def test_missing_output(self):
        builder = FFmpegCommandBuilder()
        builder.set_input(self.input_path).set_encoder("Software x264").set_crf(
            23
        ).set_pix_fmt("yuv420p")
        with self.assertRaises(ValueError):
            builder.build()

    def test_missing_encoder(self):
        builder = FFmpegCommandBuilder()
        builder.set_input(self.input_path).set_output(self.output_path).set_crf(
            23
        ).set_pix_fmt("yuv420p")
        with self.assertRaises(ValueError):
            builder.build()

    def test_missing_crf_for_x264(self):
        builder = FFmpegCommandBuilder()
        builder.set_input(self.input_path).set_output(self.output_path).set_encoder(
            "Software x264"
        ).set_pix_fmt("yuv420p")
        with self.assertRaises(ValueError):
            builder.build()

    def test_missing_bitrate_for_hardware(self):
        builder = FFmpegCommandBuilder()
        builder.set_input(self.input_path).set_output(self.output_path).set_encoder(
            "Hardware HEVC (VideoToolbox)"
        ).set_bufsize(4000).set_pix_fmt("yuv420p")
        with self.assertRaises(ValueError):
            builder.build()

    def test_missing_bufsize_for_hardware(self):
        builder = FFmpegCommandBuilder()
        builder.set_input(self.input_path).set_output(self.output_path).set_encoder(
            "Hardware HEVC (VideoToolbox)"
        ).set_bitrate(2000).set_pix_fmt("yuv420p")
        with self.assertRaises(ValueError):
            builder.build()

    def test_two_pass_missing_params(self):
        builder = FFmpegCommandBuilder()
        builder.set_input(self.input_path).set_output(self.output_path).set_encoder(
            "Software x265 (2-Pass)"
        ).set_bitrate(1000).set_pix_fmt("yuv420p")
        # Missing set_two_pass call
        with self.assertRaises(ValueError):
            builder.build()

        builder = FFmpegCommandBuilder()
        builder.set_input(self.input_path).set_output(self.output_path).set_encoder(
            "Software x265 (2-Pass)"
        ).set_bitrate(1000).set_pix_fmt("yuv420p").set_two_pass(
            True, None, 1
        )  # Missing log prefix
        with self.assertRaises(ValueError):
            builder.build()

        builder = FFmpegCommandBuilder()
        builder.set_input(self.input_path).set_output(self.output_path).set_encoder(
            "Software x265 (2-Pass)"
        ).set_bitrate(1000).set_pix_fmt("yuv420p").set_two_pass(
            True, "log_prefix", None
        )  # Missing pass number
        with self.assertRaises(ValueError):
            builder.build()

    def test_two_pass_invalid_pass_number(self):
        builder = FFmpegCommandBuilder()
        builder.set_input(self.input_path).set_output(self.output_path).set_encoder(
            "Software x265 (2-Pass)"
        ).set_bitrate(1000).set_pix_fmt("yuv420p").set_two_pass(
            True, "log_prefix", 3
        )  # Invalid pass number
        with self.assertRaises(ValueError):
            builder.build()


if __name__ == "__main__":
    unittest.main()
