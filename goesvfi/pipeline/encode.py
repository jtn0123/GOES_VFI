"""Video encoding pipeline module for GOES VFI."""

import logging
import pathlib
import subprocess
import tempfile
from typing import List

from ..utils.memory_manager import MemoryMonitor, log_memory_usage
from .ffmpeg_builder import FFmpegCommandBuilder

LOGGER = logging.getLogger(__name__)


def _run_ffmpeg_command(
    cmd: List[str], desc: str, monitor_memory: bool = False
) -> None:
    """Run an FFmpeg command with logging and error handling.

    Args:
        cmd: FFmpeg command to run
        desc: Description of the operation
        monitor_memory: Whether to monitor memory during execution
    """
    LOGGER.info("Running ffmpeg command (%s): %s", desc, " ".join(cmd))

    if monitor_memory:
        log_memory_usage(f"Before {desc}")
        monitor = MemoryMonitor()

    try:
        with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            errors="replace",
        ) as proc:
            assert proc.stdout is not None
            line_count = 0
            for line in proc.stdout:
                LOGGER.info("[ffmpeg-%s] %s", desc, line.rstrip())
                line_count += 1

                # Check memory periodically
                if monitor_memory and line_count % 100 == 0:
                    stats = monitor.get_memory_stats()
                    if stats.is_critical_memory:
                        LOGGER.warning(
                            "Critical memory during %s: %sMB available",
                            desc,
                            stats.available_mb,
                        )

            ret = proc.wait()
            if ret != 0:
                LOGGER.error(
                    "FFmpeg (%s) failed (exit code %s). See logged output above.",
                    desc,
                    ret,
                )
                raise RuntimeError(f"FFmpeg ({desc}) failed (exit code {ret})")

        if monitor_memory:
            log_memory_usage(f"After {desc}")

        LOGGER.info("FFmpeg (%s) completed successfully.", desc)

    except FileNotFoundError:
        LOGGER.error("ffmpeg command not found for %s.", desc)
        raise
    except (KeyError, ValueError, RuntimeError) as e:
        LOGGER.exception("Error during FFmpeg execution (%s)", desc)
        raise IOError(f"Error during FFmpeg execution ({desc})") from e


def encode_with_ffmpeg(
    intermediate_input: pathlib.Path,
    final_output: pathlib.Path,
    encoder: str,
    *,
    crf: int,
    bitrate_kbps: int,
    bufsize_kb: int,
    pix_fmt: str,
    monitor_memory: bool = True,
) -> None:
    """Encode intermediate input into final output using the chosen settings.

    Args:
        intermediate_input: Path to input video
        final_output: Path to output video
        encoder: Encoder to use
        crf: Constant Rate Factor (for x264/x265)
        bitrate_kbps: Bitrate in kbps
        bufsize_kb: Buffer size in kb
        pix_fmt: Pixel format
        monitor_memory: Whether to monitor memory during encoding
    """
    if monitor_memory:
        log_memory_usage("Starting video encoding")

    # Handle "None" encoder case first (stream copy)
    if encoder == "None (copy original)":
        LOGGER.info(
            "Encoder set to None. Copying streams from %s -> %s",
            intermediate_input,
            final_output,
        )
        cmd_copy = [
            "ffmpeg",
            "-y",
            "-i",
            str(intermediate_input),
            "-c",
            "copy",
            str(final_output),
        ]
        try:
            _run_ffmpeg_command(cmd_copy, "Stream Copy", monitor_memory=monitor_memory)
        except RuntimeError as e:
            LOGGER.warning(
                "Stream copy failed (%s). Attempting simple rename as fallback...", e
            )
            try:
                intermediate_input.replace(final_output)
                LOGGER.info("Fallback rename successful.")
            except (KeyError, ValueError, OSError) as move_e:
                LOGGER.error("Fallback rename failed: %s", move_e)
                raise IOError("Stream copy fallback rename failed") from move_e
        except FileNotFoundError:
            raise
        except (KeyError, ValueError) as e:
            LOGGER.exception("Unexpected error during stream copy fallback.")
            raise ValueError(f"Unexpected error during stream copy: {e}") from e
        return

    # Use FFmpegCommandBuilder for other encoders
    if encoder == "Software x265 (2-Pass)":
        LOGGER.info(
            "Starting 2-pass x265 encode. Target Bitrate: %sk (Preset: slower)",
            bitrate_kbps,
        )

        pass_log_prefix = None
        try:
            with tempfile.NamedTemporaryFile(
                delete=True, suffix="_ffmpeg_passlog"
            ) as temp_file:
                pass_log_prefix = temp_file.name

                # Build commands using FFmpegCommandBuilder
                # Pass 1
                builder1 = FFmpegCommandBuilder()
                builder1.set_input(pathlib.Path(intermediate_input))
                builder1.set_output(pathlib.Path(final_output))
                builder1.set_encoder("Software x265 (2-Pass)")
                builder1.set_pix_fmt(pix_fmt)
                builder1.set_bitrate(bitrate_kbps)
                builder1.set_bufsize(bufsize_kb)
                builder1.set_two_pass(True, pass_log_prefix, 1)
                cmd_pass1 = builder1.build()
                _run_ffmpeg_command(cmd_pass1, "2-Pass x265 Pass 1", monitor_memory)

                # Pass 2
                builder2 = FFmpegCommandBuilder()
                builder2.set_input(pathlib.Path(intermediate_input))
                builder2.set_output(pathlib.Path(final_output))
                builder2.set_encoder("Software x265 (2-Pass)")
                builder2.set_pix_fmt(pix_fmt)
                builder2.set_bitrate(bitrate_kbps)
                builder2.set_bufsize(bufsize_kb)
                builder2.set_two_pass(True, pass_log_prefix, 2)
                cmd_pass2 = builder2.build()
                _run_ffmpeg_command(cmd_pass2, "2-Pass x265 Pass 2", monitor_memory)

        except (KeyError, ValueError, RuntimeError) as e:
            LOGGER.exception("Error during 2-pass x265 encoding")
            raise IOError("2-pass x265 encoding failed") from e

    else:
        # Single-pass encoding for other encoders
        builder = FFmpegCommandBuilder()
        builder.set_input(pathlib.Path(intermediate_input))
        builder.set_output(pathlib.Path(final_output))

        # Map encoder names to match FFmpegCommandBuilder expectations
        if "x264" in encoder:
            builder.set_encoder("Software x264")
        elif "x265" in encoder:
            builder.set_encoder("Software x265")
        else:
            # Pass through the encoder name as-is
            builder.set_encoder(encoder)

        builder.set_crf(crf)
        builder.set_pix_fmt(pix_fmt)

        # Set bitrate and bufsize if provided
        if bitrate_kbps:
            builder.set_bitrate(bitrate_kbps)
        if bufsize_kb:
            builder.set_bufsize(bufsize_kb)

        cmd = builder.build()
        _run_ffmpeg_command(cmd, f"Encoding with {encoder}", monitor_memory)

    if monitor_memory:
        log_memory_usage("Video encoding completed")
