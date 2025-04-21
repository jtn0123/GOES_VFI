# goesvfi/pipeline/encode.py
import subprocess
import pathlib
import logging

LOGGER = logging.getLogger(__name__)

# Remove PRESET_MAP and ENCODER_MAP as logic is now inline

# Update signature
def encode_with_ffmpeg(
    raw_input: pathlib.Path,
    final_output: pathlib.Path,
    encoder: str,
    fps: int,
    use_interp: bool,
    crf: int, # Added
    bitrate_kbps: int, # Added
    bufsize_kb: int, # Added
    pix_fmt: str # Added
) -> None:
    """
    Re-encode raw_input into final_output using the chosen settings.
    """

    # Handle "None" encoder case first (stream copy)
    if encoder == "None (copy original)":
        LOGGER.info(f"Encoder set to None. Copying streams from {raw_input} -> {final_output}")
        cmd_copy = [
            "ffmpeg", "-y",
            "-i", str(raw_input),
            "-c", "copy",
            str(final_output)
        ]
        try:
            subprocess.run(cmd_copy, check=True, capture_output=True, text=True)
            LOGGER.info("Stream copy successful.")
        except subprocess.CalledProcessError as e:
            LOGGER.error(f"FFmpeg (stream copy) error:\nSTDOUT: {e.stdout}\nSTDERR: {e.stderr}")
            LOGGER.warning("Attempting simple rename as fallback...")
            try:
                raw_input.replace(final_output)
                LOGGER.info("Fallback rename successful.")
            except Exception as move_e:
                LOGGER.error(f"Fallback rename failed: {move_e}")
                raise e
        except FileNotFoundError:
            LOGGER.error("ffmpeg command not found for stream copy.")
            raise
        return

    # --- Build base command with logging options ---
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "info",
        "-stats",
        "-y",
        "-i", str(raw_input),
    ]
    ffmpeg_args: list[str] = []

    # --- Add interpolation filter if requested ---
    if use_interp:
        filter_str = (
            "minterpolate="
            f"mi_mode=mci:"
            f"mc_mode=aobmc:"
            f"me_mode=bidir:"
            f"search_param=60:"
            f"scd=0:"
            f"fps={fps*2}"
        )
        ffmpeg_args += ["-vf", filter_str]
        LOGGER.info(f"Adding FFmpeg motion interpolation filter: {filter_str}")

    # --- Add encoder-specific arguments --- # 
    # This section replaces the ENCODER_MAP and preset lookup
    if encoder == "Software x265":
        ffmpeg_args += ["-c:v", "libx265", "-preset", "slow", "-crf", str(crf)]
        LOGGER.info(f"Using x265 with CRF={crf}")

    elif encoder == "Software x264": # Example, add if needed
        ffmpeg_args += ["-c:v", "libx264", "-preset", "slow", "-crf", str(crf)]
        LOGGER.info(f"Using x264 with CRF={crf}")

    elif encoder == "Hardware HEVC (VideoToolbox)":
        # Note: VideoToolbox might not strictly obey bufsize, acts more like maxrate
        ffmpeg_args += ["-c:v", "hevc_videotoolbox", "-tag:v", "hvc1"]
        ffmpeg_args += ["-b:v", f"{bitrate_kbps}k", "-maxrate", f"{bufsize_kb}k"]
        LOGGER.info(f"Using HEVC VideoToolbox with Bitrate={bitrate_kbps}k, Maxrate={bufsize_kb}k")

    elif encoder == "Hardware H.264 (VideoToolbox)":
        ffmpeg_args += ["-c:v", "h264_videotoolbox"]
        ffmpeg_args += ["-b:v", f"{bitrate_kbps}k", "-maxrate", f"{bufsize_kb}k"]
        LOGGER.info(f"Using H.264 VideoToolbox with Bitrate={bitrate_kbps}k, Maxrate={bufsize_kb}k")

    # Add other hardware encoders (NVENC, QSV, VAAPI) here with elif blocks
    # elif encoder == "Hardware HEVC (NVENC)":
    #    ffmpeg_args += ["-c:v", "hevc_nvenc", "-preset", "p6", "-b:v", f"{bitrate_kbps}k", "-bufsize", f"{bufsize_kb}k"]

    else:
        LOGGER.error(f"Encoder '{encoder}' is not recognized for re-encoding. Cannot proceed.")
        raise ValueError(f"Unsupported encoder selected: {encoder}")

    # --- Add Pixel Format --- #
    ffmpeg_args += ["-pix_fmt", pix_fmt]

    # --- Combine command parts and add output path --- #
    cmd += ffmpeg_args
    cmd.append(str(final_output))

    # --- Execute FFmpeg with real-time logging --- #
    LOGGER.info(f"Running ffmpeg command: {' '.join(cmd)}")
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
            LOGGER.info(f"[ffmpeg] {line.rstrip()}")
        ret = proc.wait()
        if ret != 0:
            LOGGER.error(f"FFmpeg failed (exit code {ret}). See logged output above.")
            raise RuntimeError(f"FFmpeg failed (exit code {ret})")
        LOGGER.info("Re-encoding successful.")
    except FileNotFoundError:
        LOGGER.error("ffmpeg command not found.")
        raise 