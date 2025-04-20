# goesvfi/pipeline/encode.py
import subprocess
import pathlib

ENCODER_MAP = {
    "None (copy original)": [],
    "Software x265": ["-c:v", "libx265", "-crf", "18", "-pix_fmt", "yuv420p"], # Added pix_fmt
    # Assuming macOS VideoToolbox encoders
    "Hardware HEVC (VideoToolbox)": ["-c:v", "hevc_videotoolbox", "-tag:v", "hvc1"], # Added tag for compatibility
    "Hardware H.264 (VideoToolbox)": ["-c:v", "h264_videotoolbox"],
    # TODO: Add options for NVENC (Windows/Linux), VAAPI (Linux), QSV (Intel)
}

def encode_with_ffmpeg(
    raw_input: pathlib.Path,
    final_output: pathlib.Path,
    encoder: str,
    fps: int,
    use_interp: bool = False
) -> None:
    """
    Re-encode raw_input -> final_output using encoder choice.
    If use_interp is True, apply motion interpolation via FFmpeg first.
    If encoder == "None...", just copy streams.
    """
    if encoder not in ENCODER_MAP:
        raise ValueError(f"Unknown encoder: {encoder!r}")

    args = ENCODER_MAP[encoder]

    if not args:
        # No re-encode args: Use ffmpeg to copy streams and change container
        print(f"Encoder set to None. Copying streams from {raw_input} -> {final_output}")
        cmd_copy = [
            "ffmpeg", "-y",
            "-i", str(raw_input),  # Input raw MKV
            "-c", "copy",           # Copy streams without re-encoding
            str(final_output)       # Final output MP4 path
        ]
        print(f"Running ffmpeg command: {' '.join(cmd_copy)}")
        try:
            subprocess.run(cmd_copy, check=True, capture_output=True, text=True)
            print("Stream copy successful.")
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg (stream copy) error:")
            print(f"STDOUT: {e.stdout}")
            print(f"STDERR: {e.stderr}")
            # Try the simple move/rename as a last resort, might fail on container change
            print("Attempting simple rename as fallback...")
            try:
                raw_input.replace(final_output)
                print("Fallback rename successful.")
            except Exception as move_e:
                print(f"Fallback rename failed: {move_e}")
                raise e # Re-raise the original ffmpeg error
        except FileNotFoundError:
            print("Error: ffmpeg command not found for stream copy. Is ffmpeg installed and in your PATH?")
            raise
        return

    # Build ffmpeg command arguments
    ffmpeg_args: list[str] = []

    # --- Add motion interpolation filter if requested --- #
    if use_interp:
        # Note: This doubles the effective FPS passed to the filter
        # We assume the input `fps` is the target *before* this filter.
        # The filter itself will output at the doubled rate.
        interp_fps = fps * 2
        filter_str = f"minterpolate=mi_mode=mci:mc_mode=aobmc:me_mode=bidir:fps={interp_fps}"
        ffmpeg_args += ["-vf", filter_str]
        print(f"Adding FFmpeg motion interpolation filter: {filter_str}")

    # --- Add selected encoder arguments --- #
    ffmpeg_args += args

    # --- Build the full command --- #
    cmd = [
        "ffmpeg", "-y",
        "-i", str(raw_input),  # Input raw MKV
        *ffmpeg_args,           # Combined filter and encoder args
        str(final_output)       # Final output path
    ]

    print(f"Running ffmpeg command: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Re-encoding successful.")
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg (re-encode) error:")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        raise # Re-raise the exception
    except FileNotFoundError:
        print("Error: ffmpeg command not found. Is ffmpeg installed and in your PATH?")
        raise 