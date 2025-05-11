# goesvfi/pipeline/encode.py
import logging
import os
import pathlib
import subprocess
import tempfile

from .ffmpeg_builder import FFmpegCommandBuilder  # Import the builder

LOGGER = logging.getLogger(__name__)


# Define a helper function for running ffmpeg commands to simplify 2-pass
def _run_ffmpeg_command(cmd: list[str], desc: str) -> None:
    """Runs an FFmpeg command, logs output, raises error on failure."""
    LOGGER.info(f"Running ffmpeg command ({desc}): {' '.join(cmd)}")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            errors="replace",
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            LOGGER.info(f"[ffmpeg-{desc}] {line.rstrip()}")
        ret = proc.wait()
        if ret != 0:
            LOGGER.error(
                f"FFmpeg ({desc}) failed (exit code {ret}). See logged output above."
            )
            raise RuntimeError(f"FFmpeg ({desc}) failed (exit code {ret})")
        LOGGER.info(f"FFmpeg ({desc}) completed successfully.")
    except FileNotFoundError:
        LOGGER.error(f"ffmpeg command not found for {desc}.")
        raise
    except Exception as e:
        LOGGER.exception(f"Error during FFmpeg execution ({desc})]")
        raise RuntimeError(f"Error during FFmpeg execution ({desc})]") from e


def encode_with_ffmpeg(
    intermediate_input: pathlib.Path,
    final_output: pathlib.Path,
    encoder: str,
    crf: int,
    bitrate_kbps: int,
    bufsize_kb: int,
    pix_fmt: str,
) -> None:
    """
    Encodes intermediate_input into final_output using the chosen settings.
    Assumes any desired filtering (like minterpolate) has already been applied
    to the intermediate_input file.
    """

    # Handle "None" encoder case first (stream copy)
    if encoder == "None (copy original)":
        LOGGER.info(
            f"Encoder set to None. Copying streams from {intermediate_input} -> {final_output}"
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
            _run_ffmpeg_command(cmd_copy, "Stream Copy")
        except RuntimeError as e:
            LOGGER.warning(
                f"Stream copy failed ({e}). Attempting simple rename as fallback..."
            )
            try:
                intermediate_input.replace(final_output)
                LOGGER.info("Fallback rename successful.")
            except Exception as move_e:
                LOGGER.error(f"Fallback rename failed: {move_e}")
                raise e from move_e
        except FileNotFoundError:
            raise
        except Exception as e:
            LOGGER.exception("Unexpected error during stream copy fallback.")
            raise e
        return

    # --- Use FFmpegCommandBuilder ---
    if encoder == "Software x265 (2-Pass)":
        LOGGER.info(
            f"Starting 2-pass x265 encode. Target Bitrate: {bitrate_kbps}k (Preset: slower)"
        )
        pass_log_prefix = None
        try:
            with tempfile.NamedTemporaryFile(
                delete=True, suffix="_ffmpeg_passlog"
            ) as tmp_log:
                pass_log_prefix = tmp_log.name
            LOGGER.debug(f"Using pass log prefix: {pass_log_prefix}")

            # Pass 1
            builder_pass1 = FFmpegCommandBuilder()
            cmd_pass1 = (
                builder_pass1.set_input(intermediate_input)
                .set_output(final_output)
                .set_encoder(encoder)
                .set_bitrate(bitrate_kbps)
                .set_pix_fmt(pix_fmt)
                .set_two_pass(True, pass_log_prefix, 1)
                .build()
            )
            _run_ffmpeg_command(cmd_pass1, "Pass 1")

            # Pass 2
            builder_pass2 = FFmpegCommandBuilder()
            cmd_pass2 = (
                builder_pass2.set_input(intermediate_input)
                .set_output(final_output)
                .set_encoder(encoder)
                .set_bitrate(bitrate_kbps)
                .set_pix_fmt(pix_fmt)
                .set_two_pass(True, pass_log_prefix, 2)
                .build()
            )
            _run_ffmpeg_command(cmd_pass2, "Pass 2")

            LOGGER.info(f"2-pass x265 encoding successful: {final_output}")

        finally:
            # Cleanup pass log files
            if pass_log_prefix:
                for suffix in ["-0.log", "-0.log.mbtree"]:
                    try:
                        log_path = pathlib.Path(f"{pass_log_prefix}{suffix}")
                        if log_path.exists():
                            log_path.unlink()
                            LOGGER.debug(f"Deleted pass log file: {log_path}")
                    except OSError as e:
                        LOGGER.warning(
                            f"Could not delete pass log file {log_path}: {e}"
                        )
        return  # End of 2-pass logic

    # Single Pass Encoders
    builder_single_pass = FFmpegCommandBuilder()
    builder_single_pass.set_input(intermediate_input).set_output(
        final_output
    ).set_encoder(encoder).set_pix_fmt(pix_fmt)

    if encoder in ["Software x265", "Software x264"]:
        builder_single_pass.set_crf(crf)
        if encoder == "Software x265":
            LOGGER.info(
                f"Using x265 (slower) with CRF={crf}"
            )  # Specific x265 params are in builder
        elif encoder == "Software x264":
            LOGGER.info(f"Using x264 with CRF={crf}")

    elif encoder in ["Hardware HEVC (VideoToolbox)", "Hardware H.264 (VideoToolbox)"]:
        builder_single_pass.set_bitrate(bitrate_kbps).set_bufsize(bufsize_kb)
        if encoder == "Hardware HEVC (VideoToolbox)":
            safe_bitrate = max(1, bitrate_kbps)
            safe_bufsize = max(1, bufsize_kb)
            LOGGER.info(
                f"Using HEVC VideoToolbox with Bitrate={safe_bitrate}k, Maxrate={safe_bufsize}k"
            )
        elif encoder == "Hardware H.264 (VideoToolbox)":
            safe_bitrate = max(1, bitrate_kbps)
            safe_bufsize = max(1, bufsize_kb)
            LOGGER.info(
                f"Using H.264 VideoToolbox with Bitrate={safe_bitrate}k, Maxrate={safe_bufsize}k"
            )

    else:
        LOGGER.error(
            f"Encoder '{encoder}' is not recognized for re-encoding. Cannot proceed."
        )
        raise ValueError(f"Unsupported encoder selected: {encoder}")

    cmd_single_pass = builder_single_pass.build()
    _run_ffmpeg_command(cmd_single_pass, "Single Pass Encode")
