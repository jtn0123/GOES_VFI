from __future__ import annotations
import pathlib
import tempfile
import subprocess
import numpy as np
from PIL import Image
from typing import Iterable, List, Any # Adjusted imports
from numpy.typing import NDArray

# Define FloatNDArray alias if needed, or import if defined elsewhere
# Assuming FloatNDArray = NDArray[np.float32] for consistency
FloatNDArray = NDArray[np.float32]

# Renamed from write_mp4
def write_raw_mp4(frames: Iterable[FloatNDArray], raw_path: pathlib.Path, fps: int) -> pathlib.Path:
    """
    Writes intermediate MP4 with a lossless codec (FFV1).
    Returns the path to raw_path.
    """
    tmpdir = tempfile.TemporaryDirectory()
    pattern = pathlib.Path(tmpdir.name) / "%06d.png"

    # Ensure directory exists
    pattern.parent.mkdir(parents=True, exist_ok=True)

    print(f"Writing frames to temporary PNGs in {tmpdir.name}...")
    for i, frm in enumerate(frames):
        img8: NDArray[np.uint8] = (np.clip(frm, 0, 1) * 255).astype(np.uint8)
        Image.fromarray(img8).save(pattern.parent / f"{i:06d}.png")

    print(f"Encoding frames to lossless MP4: {raw_path}")
    # Use subprocess for ffmpeg command
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(pattern),          # Input pattern for PNGs
        "-c:v", "ffv1",            # Use FFV1 lossless codec
        str(raw_path)                 # Output raw MP4 path
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Lossless encoding successful.")
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg (raw) error:")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        # Clean up temp dir even on error
        tmpdir.cleanup()
        raise # Re-raise the exception
    except FileNotFoundError:
        print("Error: ffmpeg command not found. Is ffmpeg installed and in your PATH?")
        tmpdir.cleanup()
        raise

    # Clean up temporary directory
    tmpdir.cleanup()
    print(f"Temporary PNGs cleaned up. Raw MP4 created at: {raw_path}")
    return raw_path # Return the path 