from __future__ import annotations

import pathlib
import subprocess
import tempfile
from typing import Iterable

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)

# Define FloatNDArray alias if needed, or import if defined elsewhere
# Assuming FloatNDArray = NDArray[np.float32] for consistency
FloatNDArray = NDArray[np.float32]


# Renamed from write_mp4
def write_raw_mp4(frames: Iterable[FloatNDArray], raw_path: pathlib.Path, fps: int) -> pathlib.Path:
    """
    Writes intermediate MP4 with a lossless codec (FFV1).
    Returns the path to raw_path.
    """
    with tempfile.TemporaryDirectory() as tmpdir_name:
        pattern = pathlib.Path(tmpdir_name) / "%06d.png"

        # Ensure directory exists
        pattern.parent.mkdir(parents=True, exist_ok=True)

        LOGGER.info("Writing frames to temporary PNGs in %s...", tmpdir_name)
        for i, frm in enumerate(frames):
            img8: NDArray[np.uint8] = (np.clip(frm, 0, 1) * 255).astype(np.uint8)
            Image.fromarray(img8).save(pattern.parent / f"{i:06d}.png")

        LOGGER.info("Encoding frames to lossless MP4: %s", raw_path)
        # Use subprocess for ffmpeg command
        cmd = [
            "ffmpeg",
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(pattern),  # Input pattern for PNGs
            "-c:v",
            "ffv1",  # Use FFV1 lossless codec
            str(raw_path),  # Output raw MP4 path
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
            LOGGER.info("Lossless encoding successful.")
        except subprocess.CalledProcessError as e:
            LOGGER.exception("FFmpeg (raw) error:")
            LOGGER.exception("STDOUT: %s", e.stdout)
            LOGGER.exception("STDERR: %s", e.stderr)
            raise  # Re-raise the exception
        except FileNotFoundError:
            LOGGER.exception("Error: ffmpeg command not found. Is ffmpeg installed and in your PATH?")
            raise

        LOGGER.info("Temporary PNGs cleaned up. Raw MP4 created at: %s", raw_path)
        return raw_path  # Return the path
