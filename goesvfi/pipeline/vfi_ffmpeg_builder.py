"""FFmpeg command builder for VFI processing pipeline.

This module provides focused FFmpeg command construction functionality
extracted from VFIProcessor to improve maintainability and testability.
"""

import pathlib
from typing import Any

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class VFIFFmpegBuilder:
    """Builds FFmpeg commands for VFI video processing."""

    def __init__(self) -> None:
        """Initialize FFmpeg command builder."""
        self.default_encoder = "libx264"
        self.default_preset = "ultrafast"
        self.default_pix_fmt = "yuv420p"

    def build_raw_video_command(
        self,
        output_path: pathlib.Path,
        fps: int,
        num_intermediate_frames: int,
        skip_model: bool,
        encoder: str | None = None,
        preset: str | None = None,
        pix_fmt: str | None = None,
    ) -> list[str]:
        """Build FFmpeg command for creating raw video from image pipe.

        Args:
            output_path: Path for the output video file
            fps: Target frames per second
            num_intermediate_frames: Number of intermediate frames
            skip_model: Whether AI interpolation is being skipped
            encoder: Video encoder to use (default: libx264)
            preset: Encoding preset (default: ultrafast)
            pix_fmt: Pixel format (default: yuv420p)

        Returns:
            List of command arguments for FFmpeg
        """
        # Calculate effective input FPS based on interpolation
        effective_input_fps = fps if skip_model else fps * (num_intermediate_frames + 1)

        # Use provided values or defaults
        encoder = encoder or self.default_encoder
        preset = preset or self.default_preset
        pix_fmt = pix_fmt or self.default_pix_fmt

        cmd = [
            "ffmpeg",
            "-hide_banner",  # Hide FFmpeg banner
            "-loglevel",
            "verbose",  # Verbose logging
            "-stats",  # Show encoding progress
            "-y",  # Overwrite output file
            "-f",
            "image2pipe",  # Input format is piped images
            "-framerate",
            str(effective_input_fps),  # Input framerate
            "-vcodec",
            "png",  # Input codec is PNG
            "-i",
            "-",  # Read from stdin
            "-an",  # No audio
            "-vcodec",
            encoder,  # Output video codec
            "-preset",
            preset,  # Encoding preset
            "-pix_fmt",
            pix_fmt,  # Pixel format
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # Ensure even dimensions
            str(output_path),  # Output file
        ]

        LOGGER.info(
            "Built FFmpeg command: fps=%d, effective_fps=%d, encoder=%s, preset=%s",
            fps,
            effective_input_fps,
            encoder,
            preset,
        )

        return cmd

    def build_final_video_command(
        self, input_path: pathlib.Path, output_path: pathlib.Path, fps: int, ffmpeg_args: dict[str, Any]
    ) -> list[str]:
        """Build FFmpeg command for final video with all settings.

        Args:
            input_path: Path to the raw video file
            output_path: Path for the final output video
            fps: Target frames per second
            ffmpeg_args: Dictionary of FFmpeg arguments including:
                - crf: Constant rate factor
                - bitrate_kbps: Target bitrate in kbps
                - bufsize_kb: Buffer size in KB
                - pix_fmt: Pixel format
                - encoder: Video encoder
                - apply_unsharp: Whether to apply unsharp filter
                - unsharp_* : Unsharp filter parameters
                - use_ffmpeg_interp: Whether to use FFmpeg interpolation
                - filter_preset: FFmpeg filter preset
                - mi_mode, mc_mode, etc: Motion interpolation settings

        Returns:
            List of command arguments for FFmpeg
        """
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "verbose",
            "-stats",
            "-y",
            "-i",
            str(input_path),
            "-an",  # No audio
        ]

        # Add video filter chain if needed
        vf_filters = []

        # Always add scale filter to ensure even dimensions
        vf_filters.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")

        # Add unsharp filter if requested
        if ffmpeg_args.get("apply_unsharp"):
            unsharp_params = self._build_unsharp_filter(ffmpeg_args)
            if unsharp_params:
                vf_filters.append(unsharp_params)

        # Add motion interpolation if requested
        if ffmpeg_args.get("use_ffmpeg_interp"):
            mi_params = self._build_motion_interpolation_filter(ffmpeg_args)
            if mi_params:
                vf_filters.append(mi_params)

        # Apply video filters if any
        if vf_filters:
            cmd.extend(["-vf", ",".join(vf_filters)])

        # Add encoding parameters
        encoder = ffmpeg_args.get("encoder", self.default_encoder)
        cmd.extend(["-vcodec", encoder])

        # Add quality settings
        crf = ffmpeg_args.get("crf", 23)
        cmd.extend(["-crf", str(crf)])

        # Add bitrate settings if specified
        if ffmpeg_args.get("bitrate_kbps"):
            cmd.extend(["-b:v", f"{ffmpeg_args['bitrate_kbps']}k"])

            # Add buffer size if specified
            if ffmpeg_args.get("bufsize_kb"):
                cmd.extend(["-bufsize", f"{ffmpeg_args['bufsize_kb']}k"])

        # Add pixel format
        pix_fmt = ffmpeg_args.get("pix_fmt", self.default_pix_fmt)
        cmd.extend(["-pix_fmt", pix_fmt])

        # Add output framerate
        cmd.extend(["-r", str(fps)])

        # Add output path
        cmd.append(str(output_path))

        LOGGER.info("Built final FFmpeg command: encoder=%s, crf=%s, filters=%d", encoder, crf, len(vf_filters))

        return cmd

    def _build_unsharp_filter(self, ffmpeg_args: dict[str, Any]) -> str | None:
        """Build unsharp filter parameters.

        Args:
            ffmpeg_args: Dictionary containing unsharp parameters

        Returns:
            Unsharp filter string or None if not applicable
        """
        try:
            lx = ffmpeg_args.get("unsharp_lx", 5.0)
            ly = ffmpeg_args.get("unsharp_ly", 5.0)
            la = ffmpeg_args.get("unsharp_la", 1.0)
            cx = ffmpeg_args.get("unsharp_cx", 5.0)
            cy = ffmpeg_args.get("unsharp_cy", 5.0)
            ca = ffmpeg_args.get("unsharp_ca", 0.0)

            unsharp_filter = f"unsharp=lx={lx}:ly={ly}:la={la}:cx={cx}:cy={cy}:ca={ca}"

            LOGGER.debug("Built unsharp filter: %s", unsharp_filter)
            return unsharp_filter

        except (KeyError, ValueError) as e:
            LOGGER.warning("Failed to build unsharp filter: %s", e)
            return None

    def _build_motion_interpolation_filter(self, ffmpeg_args: dict[str, Any]) -> str | None:
        """Build motion interpolation filter parameters.

        Args:
            ffmpeg_args: Dictionary containing motion interpolation parameters

        Returns:
            Motion interpolation filter string or None if not applicable
        """
        try:
            # Get filter preset or build custom
            filter_preset = ffmpeg_args.get("filter_preset", "full")

            if filter_preset in {"none", "disabled"}:
                return None

            # Build minterpolate filter
            mi_mode = ffmpeg_args.get("mi_mode", "bidir")
            mc_mode = ffmpeg_args.get("mc_mode", "aobmc")
            me_mode = ffmpeg_args.get("me_mode", "bidir")
            me_algo = ffmpeg_args.get("me_algo", "epzs")
            mb_size = ffmpeg_args.get("minter_mb_size", 16)
            search_param = ffmpeg_args.get("search_param", 64)
            vsbmc = ffmpeg_args.get("minter_vsbmc", 1)

            # Scene change detection
            scd_mode = ffmpeg_args.get("scd_mode", "fdiff")
            scd_threshold = ffmpeg_args.get("scd_threshold", 10.0)

            mi_filter = (
                f"minterpolate=fps={ffmpeg_args.get('fps', 30)}:"
                f"mi_mode={mi_mode}:mc_mode={mc_mode}:me_mode={me_mode}:"
                f"me={me_algo}:mb_size={mb_size}:search_param={search_param}:"
                f"vsbmc={vsbmc}:scd={scd_mode}:scd_threshold={scd_threshold}"
            )

            LOGGER.debug("Built motion interpolation filter: %s", mi_filter)
            return mi_filter

        except (KeyError, ValueError) as e:
            LOGGER.warning("Failed to build motion interpolation filter: %s", e)
            return None

    def get_command_info(self, command: list[str]) -> dict[str, Any]:
        """Get information about an FFmpeg command.

        Args:
            command: FFmpeg command as list of arguments

        Returns:
            Dictionary with command information
        """
        info = {
            "executable": command[0] if command else None,
            "input_type": None,
            "output_path": None,
            "framerate": None,
            "encoder": None,
            "filters": [],
        }

        # Parse command arguments
        for i, arg in enumerate(command):
            if arg == "-i" and i + 1 < len(command):
                info["input_type"] = command[i + 1]
            elif arg == "-framerate" and i + 1 < len(command):
                info["framerate"] = command[i + 1]
            elif arg == "-vcodec" and i + 1 < len(command) and command[i - 1] != "-i":
                info["encoder"] = command[i + 1]
            elif arg == "-vf" and i + 1 < len(command):
                info["filters"] = command[i + 1].split(",")
            elif i == len(command) - 1 and not arg.startswith("-"):
                info["output_path"] = arg

        return info
