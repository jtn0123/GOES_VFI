"""ffmpeg_builder.py.

Provides the FFmpegCommandBuilder class for constructing FFmpeg command-line
arguments in a flexible and modular way, supporting various encoding options
and hardware/software backends for the GOES_VFI pipeline.
"""

from __future__ import annotations

import os
import pathlib


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
        self._command: list[str] = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "info",
            "-stats",
            "-y",
        ]
        self._input_path: pathlib.Path | None = None
        self._output_path: pathlib.Path | None = None
        self._encoder: str | None = None
        self._crf: int | None = None
        self._bitrate_kbps: int | None = None
        self._bufsize_kb: int | None = None
        self._pix_fmt: str | None = None
        self._preset: str | None = None
        self._tune: str | None = None
        self._profile: str | None = None
        self._is_two_pass: bool = False
        self._pass_log_prefix: str | None = None
        self._pass_number: int | None = None

    def set_input(self, input_path: pathlib.Path) -> FFmpegCommandBuilder:
        """Set the input file path for the FFmpeg command.

        Args:
            input_path (pathlib.Path): Path to the input video file.

        Returns:
            FFmpegCommandBuilder: The builder instance (for chaining).
        """
        self._input_path = input_path  # pylint: disable=attribute-defined-outside-init
        self._command.extend(["-i", str(input_path)])
        return self

    def set_output(self, output_path: pathlib.Path) -> FFmpegCommandBuilder:
        """Set the output file path for the FFmpeg command.

        Args:
            output_path (pathlib.Path): Path to the output video file.

        Returns:
            FFmpegCommandBuilder: The builder instance (for chaining).
        """
        self._output_path = output_path  # pylint: disable=attribute-defined-outside-init
        return self  # Output path is added during build based on pass

    def set_encoder(self, encoder: str) -> FFmpegCommandBuilder:
        """Set the video encoder to use.

        Args:
            encoder (str): Encoder name (e.g., "Software x265", "Hardware HEVC (VideoToolbox)").

        Returns:
            FFmpegCommandBuilder: The builder instance (for chaining).
        """
        self._encoder = encoder  # pylint: disable=attribute-defined-outside-init
        # Encoder-specific args will be added in build()
        return self

    def set_crf(self, crf: int) -> FFmpegCommandBuilder:
        """Set the Constant Rate Factor (CRF) for quality-based encoding.

        Args:
            crf (int): CRF value (lower is higher quality).

        Returns:
            FFmpegCommandBuilder: The builder instance (for chaining).
        """
        self._crf = crf  # pylint: disable=attribute-defined-outside-init
        return self

    def set_bitrate(self, bitrate_kbps: int) -> FFmpegCommandBuilder:
        """Set the target bitrate in kbps for bitrate-based encoding.

        Args:
            bitrate_kbps (int): Target bitrate in kilobits per second.

        Returns:
            FFmpegCommandBuilder: The builder instance (for chaining).
        """
        self._bitrate_kbps = bitrate_kbps  # pylint: disable=attribute-defined-outside-init
        return self

    def set_bufsize(self, bufsize_kb: int) -> FFmpegCommandBuilder:
        """Set the buffer size in kb for bitrate-based encoding.

        Args:
            bufsize_kb (int): Buffer size in kilobytes.

        Returns:
            FFmpegCommandBuilder: The builder instance (for chaining).
        """
        self._bufsize_kb = bufsize_kb  # pylint: disable=attribute-defined-outside-init
        return self

    def set_pix_fmt(self, pix_fmt: str) -> FFmpegCommandBuilder:
        """Set the pixel format for the output video.

        Args:
            pix_fmt (str): Pixel format string (e.g., "yuv420p10le").

        Returns:
            FFmpegCommandBuilder: The builder instance (for chaining).
        """
        self._pix_fmt = pix_fmt  # pylint: disable=attribute-defined-outside-init
        return self

    def set_preset(self, preset: str) -> FFmpegCommandBuilder:
        """Set the encoding preset for the output video.

        Args:
            preset (str): Encoding preset (e.g., "slow", "medium", "fast").

        Returns:
            FFmpegCommandBuilder: The builder instance (for chaining).
        """
        self._preset = preset  # pylint: disable=attribute-defined-outside-init
        return self

    def set_tune(self, tune: str) -> FFmpegCommandBuilder:
        """Set the encoding tune for the output video.

        Args:
            tune (str): Encoding tune (e.g., "animation", "film", "grain").

        Returns:
            FFmpegCommandBuilder: The builder instance (for chaining).
        """
        self._tune = tune  # pylint: disable=attribute-defined-outside-init
        return self

    def set_profile(self, profile: str) -> FFmpegCommandBuilder:
        """Set the encoding profile for the output video.

        Args:
            profile (str): Encoding profile (e.g., "main", "main10", "high").

        Returns:
            FFmpegCommandBuilder: The builder instance (for chaining).
        """
        self._profile = profile  # pylint: disable=attribute-defined-outside-init
        return self

    def set_two_pass(self, is_two_pass: bool, pass_log_prefix: str, pass_number: int) -> FFmpegCommandBuilder:
        """Configure two-pass encoding parameters.

        Args:
            is_two_pass (bool): Whether to use two-pass encoding.
            pass_log_prefix (str): Prefix for the two-pass log file.
            pass_number (int): Pass number (1 or 2).

        Returns:
            FFmpegCommandBuilder: The builder instance (for chaining).
        """
        self._is_two_pass = is_two_pass  # pylint: disable=attribute-defined-outside-init
        self._pass_log_prefix = pass_log_prefix  # pylint: disable=attribute-defined-outside-init
        self._pass_number = pass_number  # pylint: disable=attribute-defined-outside-init
        return self

    def build(self) -> list[str]:
        """Build and return the FFmpeg command as a list of arguments.

        Returns:
            List[str]: The FFmpeg command suitable for subprocess execution.

        Raises:
            ValueError: If required parameters are missing or invalid.
        """
        self._validate_required_parameters()

        # Handle special case of copy encoder
        if self._encoder == "None (copy original)":
            return self._build_copy_command()

        # Build command with encoder-specific arguments
        cmd = list(self._command)
        self._add_encoder_specific_args(cmd)

        return cmd

    def _validate_required_parameters(self) -> None:
        """Validate that all required parameters are set."""
        if not self._input_path or not self._output_path or not self._encoder:
            msg = "Input path, output path, and encoder must be set."
            raise ValueError(msg)

    def _build_copy_command(self) -> list[str]:
        """Build command for stream copy (no re-encoding)."""
        return [
            "ffmpeg",
            "-y",
            "-i",
            str(self._input_path),
            "-c",
            "copy",
            str(self._output_path),
        ]

    def _get_preset(self, default: str) -> str:
        """Get the preset to use, with fallback to default.
        
        Args:
            default (str): Default preset to use if none specified.
            
        Returns:
            str: The preset to use.
        """
        return self._preset if self._preset is not None else default

    def _add_tune_and_profile_args(self, cmd: list[str]) -> None:
        """Add tune and profile arguments if set.
        
        Args:
            cmd (list[str]): Command list to append to.
        """
        if self._tune is not None:
            cmd.extend(["-tune", self._tune])
        if self._profile is not None:
            cmd.extend(["-profile:v", self._profile])

    def _add_encoder_specific_args(self, cmd: list[str]) -> None:
        """Add encoder-specific arguments to the command."""
        if self._encoder == "Software x265 (2-Pass)":
            self._add_x265_two_pass_args(cmd)
        elif self._encoder == "Software x265":
            self._add_x265_single_pass_args(cmd)
        elif self._encoder == "Software x264":
            self._add_x264_args(cmd)
        elif self._encoder == "Hardware HEVC (VideoToolbox)":
            self._add_hardware_hevc_args(cmd)
        elif self._encoder == "Hardware H.264 (VideoToolbox)":
            self._add_hardware_h264_args(cmd)
        else:
            msg = f"Unsupported encoder selected: {self._encoder}"
            raise ValueError(msg)

    def _add_x265_two_pass_args(self, cmd: list[str]) -> None:
        """Add arguments for x265 two-pass encoding."""
        self._validate_two_pass_parameters()

        cmd.extend(["-c:v", "libx265", "-preset", self._get_preset("slower")])

        if self._pass_number == 1:
            self._add_x265_pass1_args(cmd)
        elif self._pass_number == 2:
            self._add_x265_pass2_args(cmd)
        else:
            msg = f"Invalid pass number for two-pass x265: {self._pass_number}"
            raise ValueError(msg)

    def _validate_two_pass_parameters(self) -> None:
        """Validate parameters required for two-pass encoding."""
        if not self._is_two_pass or self._pass_log_prefix is None or self._pass_number is None:
            msg = "Two-pass encoding requires two_pass flag, log prefix, and pass number."
            raise ValueError(msg)

    def _add_x265_pass1_args(self, cmd: list[str]) -> None:
        """Add arguments for x265 pass 1."""
        # Type narrowing: we know _pass_log_prefix is not None here due to validation
        assert self._pass_log_prefix is not None
        cmd.extend([
            "-b:v",
            f"{self._bitrate_kbps}k",
            "-x265-params",
            "pass=1",
            "-passlogfile",
            self._pass_log_prefix,
            "-f",
            "null",
            os.devnull,
        ])

    def _add_x265_pass2_args(self, cmd: list[str]) -> None:
        """Add arguments for x265 pass 2."""
        # Type narrowing: we know _pass_log_prefix is not None here due to validation
        assert self._pass_log_prefix is not None
        pass2_params = "pass=2:aq-mode=3:aq-strength=1.0:psy-rd=2.0:psy-rdoq=1.0"
        args = [
            "-b:v",
            f"{self._bitrate_kbps}k",
            "-x265-params",
            pass2_params,
            "-passlogfile",
            self._pass_log_prefix,
        ]
        self._add_common_output_args(args)
        cmd.extend(args)

    def _add_x265_single_pass_args(self, cmd: list[str]) -> None:
        """Add arguments for single-pass x265 encoding."""
        if self._crf is None:
            msg = "CRF must be set for single-pass x265."
            raise ValueError(msg)

        x265_params = "aq-mode=3:aq-strength=1.0:psy-rd=2.0:psy-rdoq=1.0"
        cmd.extend(["-c:v", "libx265", "-preset", self._get_preset("slower"), "-crf", str(self._crf)])
        self._add_tune_and_profile_args(cmd)
        cmd.extend(["-x265-params", x265_params])

        args: list[str] = []
        self._add_common_output_args(args)
        cmd.extend(args)

    def _add_x264_args(self, cmd: list[str]) -> None:
        """Add arguments for x264 encoding."""
        if self._crf is None:
            msg = "CRF must be set for x264."
            raise ValueError(msg)

        cmd.extend(["-c:v", "libx264", "-preset", self._get_preset("slow"), "-crf", str(self._crf)])
        self._add_tune_and_profile_args(cmd)

        args: list[str] = []
        self._add_common_output_args(args)
        cmd.extend(args)

    def _add_hardware_hevc_args(self, cmd: list[str]) -> None:
        """Add arguments for hardware HEVC encoding."""
        self._validate_hardware_parameters("Hardware HEVC")

        safe_bitrate, safe_bufsize = self._get_safe_hardware_rates()
        cmd.extend(["-c:v", "hevc_videotoolbox", "-tag:v", "hvc1"])
        cmd.extend(["-b:v", f"{safe_bitrate}k", "-maxrate", f"{safe_bufsize}k"])

        args: list[str] = []
        self._add_common_output_args(args)
        cmd.extend(args)

    def _add_hardware_h264_args(self, cmd: list[str]) -> None:
        """Add arguments for hardware H.264 encoding."""
        self._validate_hardware_parameters("Hardware H.264")

        safe_bitrate, safe_bufsize = self._get_safe_hardware_rates()
        cmd.extend(["-c:v", "h264_videotoolbox"])
        cmd.extend(["-b:v", f"{safe_bitrate}k", "-maxrate", f"{safe_bufsize}k"])

        args: list[str] = []
        self._add_common_output_args(args)
        cmd.extend(args)

    def _validate_hardware_parameters(self, encoder_name: str) -> None:
        """Validate parameters required for hardware encoding."""
        if self._bitrate_kbps is None or self._bufsize_kb is None:
            msg = f"Bitrate and bufsize must be set for {encoder_name}."
            raise ValueError(msg)

    def _get_safe_hardware_rates(self) -> tuple[int, int]:
        """Get safe bitrate and bufsize values for hardware encoding."""
        # These should have been validated before calling this method
        assert self._bitrate_kbps is not None
        assert self._bufsize_kb is not None
        safe_bitrate = max(1, self._bitrate_kbps)
        safe_bufsize = max(1, self._bufsize_kb)
        return safe_bitrate, safe_bufsize

    def _add_format_specific_args(self, args: list[str]) -> None:
        """Add format-specific arguments based on output file extension."""
        if self._output_path is not None:
            output_ext = self._output_path.suffix.lower()
            if output_ext == ".mp4":
                args.extend(["-movflags", "+faststart"])

    def _add_common_output_args(self, args: list[str]) -> None:
        """Add common output arguments (pixel format, format-specific options, and output path)."""
        if self._pix_fmt is not None:
            args.extend(["-pix_fmt", self._pix_fmt])
        self._add_format_specific_args(args)
        if self._output_path is not None:
            args.append(str(self._output_path))
