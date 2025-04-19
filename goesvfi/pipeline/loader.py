# TODO: discover + sort input frames
from __future__ import annotations
import pathlib
from typing import List

SUPPORTED_EXT = {".png", ".jpg", ".jpeg"}

def discover_frames(folder: pathlib.Path) -> List[pathlib.Path]:
    """Return frame paths sorted by timestamp (in filename)."""
    paths = [p for p in folder.iterdir() if p.suffix.lower() in SUPPORTED_EXT]
    # naive sort – filenames already embed time in lexicographic order
    return sorted(paths)
