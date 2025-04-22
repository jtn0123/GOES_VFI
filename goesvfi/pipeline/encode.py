# goesvfi/pipeline/encode.py
import subprocess
import pathlib
import logging
import tempfile
import os

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
            text=True,
            errors='replace'
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            LOGGER.info(f"[ffmpeg-{desc}] {line.rstrip()}")
        ret = proc.wait()
        if ret != 0:
            LOGGER.error(f"FFmpeg ({desc}) failed (exit code {ret}). See logged output above.")
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
    pix_fmt: str
) -> None:
    """
    Encodes intermediate_input into final_output using the chosen settings.
    Assumes any desired filtering (like minterpolate) has already been applied
    to the intermediate_input file.
    """

    # Handle "None" encoder case first (stream copy)
    if encoder == "None (copy original)":
        LOGGER.info(f"Encoder set to None. Copying streams from {intermediate_input} -> {final_output}")
        cmd_copy = [
            "ffmpeg", "-y",
            "-i", str(intermediate_input),
            "-c", "copy",
            str(final_output)
        ]
        try:
            _run_ffmpeg_command(cmd_copy, "Stream Copy")
        except RuntimeError as e:
            LOGGER.warning(f"Stream copy failed ({e}). Attempting simple rename as fallback...")
            try:
                intermediate_input.replace(final_output)
                LOGGER.info("Fallback rename successful.")
            except Exception as move_e:
                LOGGER.error(f"Fallback rename failed: {move_e}")
                raise e
        except FileNotFoundError:
            raise
        except Exception as e:
             LOGGER.exception("Unexpected error during stream copy fallback.")
             raise e
        return

    # --- Build Base Command Elements (Input Only) --- #
    base_cmd_elements = [
        "ffmpeg", "-hide_banner", "-loglevel", "info", "-stats", "-y",
        "-i", str(intermediate_input),
    ]

    # --- Encoder Specific Logic --- #

    # --- Software x265 (2-Pass) --- #
    if encoder == "Software x265 (2-Pass)":
        LOGGER.info(f"Starting 2-pass x265 encode. Target Bitrate: {bitrate_kbps}k (Preset: slower)")
        pass_log_prefix = None
        try:
            with tempfile.NamedTemporaryFile(delete=True, suffix='_ffmpeg_passlog') as tmp_log:
                pass_log_prefix = tmp_log.name
            LOGGER.debug(f"Using pass log prefix: {pass_log_prefix}")

            # Pass 1 command - NO filters applied here
            cmd_pass1 = base_cmd_elements + [
                "-c:v", "libx265",
                "-preset", "slower",
                "-b:v", f"{bitrate_kbps}k",
                "-x265-params", "pass=1",
                "-passlogfile", pass_log_prefix,
                "-f", "null",
                os.devnull
            ]
            _run_ffmpeg_command(cmd_pass1, "Pass 1")

            # Pass 2 command - NO filters applied here
            pass2_params = "pass=2:aq-mode=3:aq-strength=1.0:psy-rd=2.0:psy-rdoq=1.0"
            cmd_pass2 = base_cmd_elements + [
                "-c:v", "libx265",
                "-preset", "slower",
                "-b:v", f"{bitrate_kbps}k",
                "-x265-params", pass2_params,
                "-passlogfile", pass_log_prefix,
                "-pix_fmt", pix_fmt,
                str(final_output)
            ]
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
                        LOGGER.warning(f"Could not delete pass log file {log_path}: {e}")
        return # End of 2-pass logic

    # --- Single Pass Encoders --- #
    ffmpeg_args: list[str] = []

    if encoder == "Software x265":
        x265_params = "aq-mode=3:aq-strength=1.0:psy-rd=2.0:psy-rdoq=1.0"
        ffmpeg_args += ["-c:v", "libx265", "-preset", "slower", "-crf", str(crf)]
        ffmpeg_args += ["-x265-params", x265_params]
        LOGGER.info(f"Using x265 (slower) with CRF={crf} and PsyOpts={x265_params}")

    elif encoder == "Software x264":
        ffmpeg_args += ["-c:v", "libx264", "-preset", "slow", "-crf", str(crf)]
        LOGGER.info(f"Using x264 with CRF={crf}")

    elif encoder == "Hardware HEVC (VideoToolbox)":
        ffmpeg_args += ["-c:v", "hevc_videotoolbox", "-tag:v", "hvc1"]
        safe_bitrate = max(1, bitrate_kbps)
        safe_bufsize = max(1, bufsize_kb)
        ffmpeg_args += ["-b:v", f"{safe_bitrate}k", "-maxrate", f"{safe_bufsize}k"]
        LOGGER.info(f"Using HEVC VideoToolbox with Bitrate={safe_bitrate}k, Maxrate={safe_bufsize}k")

    elif encoder == "Hardware H.264 (VideoToolbox)":
        ffmpeg_args += ["-c:v", "h264_videotoolbox"]
        safe_bitrate = max(1, bitrate_kbps)
        safe_bufsize = max(1, bufsize_kb)
        ffmpeg_args += ["-b:v", f"{safe_bitrate}k", "-maxrate", f"{safe_bufsize}k"]
        LOGGER.info(f"Using H.264 VideoToolbox with Bitrate={safe_bitrate}k, Maxrate={safe_bufsize}k")

    # Add other hardware encoders here...

    else:
        LOGGER.error(f"Encoder '{encoder}' is not recognized for re-encoding. Cannot proceed.")
        raise ValueError(f"Unsupported encoder selected: {encoder}")

    # Combine command parts for single-pass execution (NO filters here)
    cmd_single_pass = base_cmd_elements + ffmpeg_args + ["-pix_fmt", pix_fmt, str(final_output)]

    # Execute the single-pass command
    _run_ffmpeg_command(cmd_single_pass, "Single Pass Encode")