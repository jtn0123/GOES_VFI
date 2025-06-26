import os  # For os.devnull
import pathlib
from unittest.mock import ANY, MagicMock, patch

import pytest

from goesvfi.pipeline import encode

# Import the mock utility
from tests.utils.mocks import create_mock_popen


@pytest.fixture
def temp_paths(tmp_path):
    intermediate = tmp_path / "input.mp4"
    intermediate.write_text("dummy input")
    final = tmp_path / "output.mp4"
    return intermediate, final


@patch("goesvfi.pipeline.encode.subprocess.Popen")  # Patch Popen directly
def test_stream_copy_success(mock_popen_patch, temp_paths):
    intermediate, final = temp_paths

    # Expected command for stream copy
    expected_cmd = ["ffmpeg", "-y", "-i", str(intermediate), "-c", "copy", str(final)]
    mock_popen_factory = create_mock_popen(expected_command=expected_cmd, output_file_to_create=final)
    mock_popen_patch.side_effect = mock_popen_factory

    # Act
    encode.encode_with_ffmpeg(
        intermediate_input=intermediate,
        final_output=final,
        encoder="None (copy original)",
        crf=0,
        bitrate_kbps=0,
        bufsize_kb=0,
        pix_fmt="yuv420p",
    )

    # Assert Popen called correctly and file created
    mock_popen_patch.assert_called_once()
    assert final.exists()


@patch("goesvfi.pipeline.encode.subprocess.Popen")  # Patch Popen directly
def test_stream_copy_fallback_rename(mock_popen_patch, temp_paths):
    intermediate, final = temp_paths

    # Expected command for stream copy
    expected_cmd = ["ffmpeg", "-y", "-i", str(intermediate), "-c", "copy", str(final)]
    # Configure mock Popen to fail (non-zero return code)
    mock_popen_factory = create_mock_popen(
        expected_command=expected_cmd,
        returncode=1,  # Simulate failure
        stderr=b"ffmpeg copy failed",
    )
    mock_popen_patch.side_effect = mock_popen_factory

    # Patch pathlib.Path.replace to track if called
    with patch.object(pathlib.Path, "replace", return_value=None) as mock_replace:
        # Act
        encode.encode_with_ffmpeg(
            intermediate_input=intermediate,
            final_output=final,
            encoder="None (copy original)",
            crf=0,
            bitrate_kbps=0,
            bufsize_kb=0,
            pix_fmt="yuv420p",
        )
        # Assert Popen was called (and failed)
        mock_popen_patch.assert_called_once()
        # Assert fallback rename was called
        mock_replace.assert_called_once_with(final)


@patch("goesvfi.pipeline.encode.subprocess.Popen")  # Patch Popen directly
@patch("tempfile.NamedTemporaryFile")  # Mock temp file for passlog
def test_2pass_x265_calls(mock_temp_file, mock_popen_patch, temp_paths):
    intermediate, final = temp_paths
    bitrate = 1000
    pix_fmt = "yuv420p"
    # Mock the temp file context manager
    mock_log_file = MagicMock()
    mock_log_file.name = str(temp_paths[0].parent / "ffmpeg_passlog")  # Predictable name
    mock_temp_file.return_value.__enter__.return_value = mock_log_file

    # Expected commands
    pass_log_prefix = mock_log_file.name
    cmd_pass1 = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "info",
        "-stats",
        "-y",
        "-i",
        str(intermediate),
        "-c:v",
        "libx265",
        "-preset",
        "slower",
        "-b:v",
        f"{bitrate}k",
        "-x265-params",
        "pass=1",
        "-passlogfile",
        pass_log_prefix,
        "-f",
        "null",
        os.devnull,
    ]
    cmd_pass2 = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "info",
        "-stats",
        "-y",
        "-i",
        str(intermediate),
        "-c:v",
        "libx265",
        "-preset",
        "slower",
        "-b:v",
        f"{bitrate}k",
        "-x265-params",
        ANY,  # Params string can be complex, use ANY
        "-passlogfile",
        pass_log_prefix,
        "-pix_fmt",
        pix_fmt,
        str(final),
    ]

    # Create two mock factories, one for each pass
    mock_popen_pass1 = create_mock_popen(expected_command=cmd_pass1)
    # Pass 2 creates the final output file
    mock_popen_pass2 = create_mock_popen(expected_command=cmd_pass2, output_file_to_create=final)

    # Define a side effect function to consume the factories
    factories = [mock_popen_pass1, mock_popen_pass2]

    def popen_side_effect(*args, **kwargs):
        if not factories:
            raise AssertionError("Popen called more times than expected")
        factory = factories.pop(0)
        return factory(*args, **kwargs)  # Call the factory and return its result

    mock_popen_patch.side_effect = popen_side_effect

    # Act
    encode.encode_with_ffmpeg(
        intermediate_input=intermediate,
        final_output=final,
        encoder="Software x265 (2-Pass)",
        crf=0,
        bitrate_kbps=bitrate,
        bufsize_kb=0,
        pix_fmt=pix_fmt,
    )

    # Assert Popen called twice with correct commands
    assert mock_popen_patch.call_count == 2
    # Check args of each call if needed via mock_popen_patch.call_args_list
    assert mock_popen_patch.call_args_list[0][0][0] == cmd_pass1
    assert mock_popen_patch.call_args_list[1][0][0] == cmd_pass2
    # Assert final file created
    assert final.exists()


@patch("goesvfi.pipeline.encode.subprocess.Popen")  # Patch Popen directly
@pytest.mark.parametrize(
    "encoder, expected_codec, use_crf",
    [
        ("Software x265", "libx265", True),
        ("Software x264", "libx264", True),
        ("Hardware HEVC (VideoToolbox)", "hevc_videotoolbox", False),
        ("Hardware H.264 (VideoToolbox)", "h264_videotoolbox", False),
    ],
)
def test_single_pass_encoders(mock_popen_patch, temp_paths, encoder, expected_codec, use_crf):
    intermediate, final = temp_paths
    crf = 23
    bitrate = 500
    bufsize = 1000
    pix_fmt = "yuv420p"

    # Base command part
    base_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "info",
        "-stats",
        "-y",
        "-i",
        str(intermediate),
    ]
    # Encoder specific part
    encoder_args = ["-c:v", expected_codec]
    if use_crf:
        # Correct order for software encoders: preset first, then crf
        if encoder == "Software x265":
            encoder_args.extend(["-preset", "slower"])  # Add preset first
            encoder_args.extend(["-crf", str(crf)])  # Then crf
            encoder_args.extend(["-x265-params", ANY])  # Then params
        elif encoder == "Software x264":
            encoder_args.extend(["-preset", "slow"])  # Add preset first
            encoder_args.extend(["-crf", str(crf)])  # Then crf
    else:  # Hardware encoders use bitrate
        # Adjust order to match Popen call: -tag:v first, then bitrate args
        if "hevc" in expected_codec:
            encoder_args.extend(["-tag:v", "hvc1"])  # Add tag for HEVC VT
        encoder_args.extend(["-b:v", f"{bitrate}k", "-maxrate", f"{bufsize}k"])

    # Final command
    expected_cmd = base_cmd + encoder_args + ["-pix_fmt", pix_fmt, str(final)]

    # Configure mock Popen
    mock_popen_factory = create_mock_popen(expected_command=expected_cmd, output_file_to_create=final)
    mock_popen_patch.side_effect = mock_popen_factory

    # Act
    encode.encode_with_ffmpeg(
        intermediate_input=intermediate,
        final_output=final,
        encoder=encoder,
        crf=crf,
        bitrate_kbps=bitrate,
        bufsize_kb=bufsize,
        pix_fmt=pix_fmt,
    )

    # Assert Popen called correctly and file created
    mock_popen_patch.assert_called_once()
    # Check command args more precisely if needed:
    # assert mock_popen_patch.call_args[0][0] == expected_cmd
    assert final.exists()


def test_unsupported_encoder_raises(temp_paths):
    intermediate, final = temp_paths
    with pytest.raises(ValueError):
        encode.encode_with_ffmpeg(
            intermediate_input=intermediate,
            final_output=final,
            encoder="Unsupported Encoder",
            crf=0,
            bitrate_kbps=0,
            bufsize_kb=0,
            pix_fmt="yuv420p",
        )
