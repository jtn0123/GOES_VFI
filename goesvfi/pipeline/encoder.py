# TODO: FFmpeg H.265 writer

from __future__ import annotations
import tempfile
import pathlib
import subprocess
import numpy as np
from PIL import Image
from typing import Iterable, Any
from numpy.typing import NDArray

def write_mp4(frames: Iterable[NDArray[np.float32]], out_path: pathlib.Path, fps: int = 60) -> None:
    """Encode frames (float32 0‑1 RGB) to H.265 MP4 using ffmpeg."""
    tmpdir = tempfile.TemporaryDirectory()
    pattern = pathlib.Path(tmpdir.name) / "%06d.png"
    for i, frm in enumerate(frames):
        img8: NDArray[np.uint8] = (np.clip(frm, 0, 1) * 255).astype(np.uint8)
        Image.fromarray(img8).save(pattern.parent / f"{i:06d}.png")
    cmd = [
        "ffmpeg", "-y", "-framerate", str(fps), "-i", str(pattern),
        "-c:v", "libx265", "-pix_fmt", "yuv420p", "-crf", "18", str(out_path)
    ]
    subprocess.run(cmd, check=True)
    tmpdir.cleanup()
