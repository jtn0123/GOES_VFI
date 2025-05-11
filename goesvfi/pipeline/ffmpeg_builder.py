from __future__ import annotations

"""ffmpeg_builder.py

Provides the FFmpegCommandBuilder class for constructing FFmpeg command-line
arguments in a flexible and modular way, supporting various encoding options
and hardware/software backends for the GOES_VFI pipeline.
"""

import os
import pathlib
from typing import List, Optional


class FFmpegCommandBuilder:
    """Builder for FFmpeg command-line arguments for video encoding.

    This class provides a fluent interface for specifying input/output files,
    encoder options, quality/bitrate settings, pixel format, and two-pass
    encoding parameters. It generates a command list suitable for subprocess
    execution.

    Typical usage:
        builder = FFmpegCommandBuilder()
        cmd = (
            builder.set_input(input_path)
                   .set_output(output_path)
                   .set_encoder("Software x265")
                   .set_crf(20)
                   .set_pix_fmt("yuv420p10le")
                   .build()
        )
    """

    def __init__(self) -> None:
        """Initialize a new FFmpegCommandBuilder with default settings."""
        self._command: List[str] = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "info",
            "-stats",
            "-y",
        ]
        self._input_path: Optional[pathlib.Path] = None
        self._output_path: Optional[pathlib.Path] = None
        self._encoder: Optional[str] = None
        self._crf: Optional[int] = None
        self._bitrate_kbps: Optional[int] = None
        self._bufsize_kb: Optional[int] = None
        self._pix_fmt: Optional[str] = None
        self._is_two_pass: bool = False
        self._pass_log_prefix: Optional[str] = None
        self._pass_number: Optional[int] = None

    def set_input(self, input_path: pathlib.Path) -> "FFmpegCommandBuilder":
        """Set the input file path for the FFmpeg command.

        Args:
            input_path (pathlib.Path): Path to the input video file.

        Returns:
            FFmpegCommandBuilder: The builder instance (for chaining).
        """
        self._input_path = input_path
        self._command.extend(["-i", str(input_path)])
        return self

    def set_output(self, output_path: pathlib.Path) -> "FFmpegCommandBuilder":
        """Set the output file path for the FFmpeg command.

        Args:
            output_path (pathlib.Path): Path to the output video file.

        Returns:
            FFmpegCommandBuilder: The builder instance (for chaining).
        """
        self._output_path = output_path
        return self  # Output path is added during build based on pass

    def set_encoder(self, encoder: str) -> "FFmpegCommandBuilder":
        """Set the video encoder to use.

        Args:
            encoder (str): Encoder name (e.g., "Software x265", "Hardware HEVC (VideoToolbox)").

        Returns:
            FFmpegCommandBuilder: The builder instance (for chaining).
        """
        self._encoder = encoder
        # Encoder-specific args will be added in build()
        return self

    def set_crf(self, crf: int) -> "FFmpegCommandBuilder":
        """Set the Constant Rate Factor (CRF) for quality-based encoding.

        Args:
            crf (int): CRF value (lower is higher quality).

        Returns:
            FFmpegCommandBuilder: The builder instance (for chaining).
        """
        self._crf = crf
        return self

    def set_bitrate(self, bitrate_kbps: int) -> "FFmpegCommandBuilder":
        """Set the target bitrate in kbps for bitrate-based encoding.

        Args:
            bitrate_kbps (int): Target bitrate in kilobits per second.

        Returns:
            FFmpegCommandBuilder: The builder instance (for chaining).
        """
        self._bitrate_kbps = bitrate_kbps
        return self

    def set_bufsize(self, bufsize_kb: int) -> "FFmpegCommandBuilder":
        """Set the buffer size in kb for bitrate-based encoding.

        Args:
            bufsize_kb (int): Buffer size in kilobytes.

        Returns:
            FFmpegCommandBuilder: The builder instance (for chaining).
        """
        self._bufsize_kb = bufsize_kb
        return self

    def set_pix_fmt(self, pix_fmt: str) -> "FFmpegCommandBuilder":
        """Set the pixel format for the output video.

        Args:
            pix_fmt (str): Pixel format string (e.g., "yuv420p10le").

        Returns:
            FFmpegCommandBuilder: The builder instance (for chaining).
        """
        self._pix_fmt = pix_fmt
        return self

    def set_two_pass(
        self, is_two_pass: bool, pass_log_prefix: str, pass_number: int
    ) -> "FFmpegCommandBuilder":
        """Configure two-pass encoding parameters.

        Args:
            is_two_pass (bool): Whether to use two-pass encoding.
            pass_log_prefix (str): Prefix for the two-pass log file.
            pass_number (int): Pass number (1 or 2).

        Returns:
            FFmpegCommandBuilder: The builder instance (for chaining).
        """
        self._is_two_pass = is_two_pass
        self._pass_log_prefix = pass_log_prefix
        self._pass_number = pass_number
        return self

    def build(self) -> List[str]:
        """Build and return the FFmpeg command as a list of arguments.

        Returns:
            List[str]: The FFmpeg command suitable for subprocess execution.

        Raises:
            ValueError: If required parameters are missing or invalid.
        """
        if not self._input_path or not self._output_path or not self._encoder:
            raise ValueError("Input path, output path, and encoder must be set.")

        # Creating a new list to avoid modifying the original command template
        cmd = list(self._command)  # Start with base command elements

        # Handle "None" encoder (stream copy)
        if self._encoder == "None (copy original)":
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(self._input_path),
                "-c",
                "copy",
                str(self._output_path),
            ]
            return cmd

        # Add encoder-specific arguments
        if self._encoder == "Software x265 (2-Pass)":
            if (
                not self._is_two_pass
                or self._pass_log_prefix is None
                or self._pass_number is None
            ):
                raise ValueError(
                    "Two-pass encoding requires two_pass flag, log prefix, and pass number."
                )

            cmd.extend(["-c:v", "libx265", "-preset", "slower"])

            if self._pass_number == 1:
                cmd.extend(
                    [
                        "-b:v",
                        f"{self._bitrate_kbps}k",
                        "-x265-params",
                        "pass=1",
                        "-passlogfile",
                        self._pass_log_prefix,
                        "-f",
                        "null",
                        os.devnull,  # Use os.devnull for null output in pass 1
                    ]
                )
            elif self._pass_number == 2:
                pass2_params = (
                    "pass=2:aq-mode=3:aq-strength=1.0:psy-rd=2.0:psy-rdoq=1.0"
                )
                args = [
                    "-b:v",
                    f"{self._bitrate_kbps}k",
                    "-x265-params",
                    pass2_params,
                    "-passlogfile",
                    self._pass_log_prefix,
                ]
                if self._pix_fmt is not None:
                    args.extend(["-pix_fmt", self._pix_fmt])
                if self._output_path is not None:
                    args.append(str(self._output_path))
                cmd.extend(args)
            else:
                raise ValueError(
                    f"Invalid pass number for two-pass x265: {self._pass_number}"
                )

        elif self._encoder == "Software x265":
            if self._crf is None:
                raise ValueError("CRF must be set for single-pass x265.")
            x265_params = "aq-mode=3:aq-strength=1.0:psy-rd=2.0:psy-rdoq=1.0"
            cmd.extend(["-c:v", "libx265", "-preset", "slower", "-crf", str(self._crf)])
            cmd.extend(["-x265-params", x265_params])
            args = []
            if self._pix_fmt is not None:
                args.extend(["-pix_fmt", self._pix_fmt])
            if self._output_path is not None:
                args.append(str(self._output_path))
            cmd.extend(args)

        elif self._encoder == "Software x264":
            if self._crf is None:
                raise ValueError("CRF must be set for x264.")
            cmd.extend(["-c:v", "libx264", "-preset", "slow", "-crf", str(self._crf)])
            args = []
            if self._pix_fmt is not None:
                args.extend(["-pix_fmt", self._pix_fmt])
            if self._output_path is not None:
                args.append(str(self._output_path))
            cmd.extend(args)

        elif self._encoder == "Hardware HEVC (VideoToolbox)":
            if self._bitrate_kbps is None or self._bufsize_kb is None:
                raise ValueError("Bitrate and bufsize must be set for Hardware HEVC.")
            safe_bitrate = max(1, self._bitrate_kbps)
            safe_bufsize = max(1, self._bufsize_kb)
            cmd.extend(["-c:v", "hevc_videotoolbox", "-tag:v", "hvc1"])
            cmd.extend(["-b:v", f"{safe_bitrate}k", "-maxrate", f"{safe_bufsize}k"])
            args = []
            if self._pix_fmt is not None:
                args.extend(["-pix_fmt", self._pix_fmt])
            if self._output_path is not None:
                args.append(str(self._output_path))
            cmd.extend(args)

        elif self._encoder == "Hardware H.264 (VideoToolbox)":
            if self._bitrate_kbps is None or self._bufsize_kb is None:
                raise ValueError("Bitrate and bufsize must be set for Hardware H.264.")
            safe_bitrate = max(1, self._bitrate_kbps)
            safe_bufsize = max(1, self._bufsize_kb)
            cmd.extend(["-c:v", "h264_videotoolbox"])
            cmd.extend(["-b:v", f"{safe_bitrate}k", "-maxrate", f"{safe_bufsize}k"])
            args = []
            if self._pix_fmt is not None:
                args.extend(["-pix_fmt", self._pix_fmt])
            if self._output_path is not None:
                args.append(str(self._output_path))
            cmd.extend(args)

        else:
            raise ValueError(f"Unsupported encoder selected: {self._encoder}")

        return cmd
