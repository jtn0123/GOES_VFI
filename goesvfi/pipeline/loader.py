from __future__ import annotations

import pathlib

from goesvfi.utils import config

# TODO: discover + sort input frames

SUPPORTED_EXT = set(config.get_supported_extensions())  # Get from config and convert to set


def discover_frames(folder: pathlib.Path | str) -> list[pathlib.Path]:
    """Return frame paths sorted by timestamp (in filename)."""
    # Convert string to Path object if needed
    folder_path = pathlib.Path(folder) if isinstance(folder, str) else folder

    # Handle case where directory doesn't exist
    if not folder_path.exists():
        return []

    # Handle case where path is not a directory
    if not folder_path.is_dir():
        return []

    paths = [p for p in folder_path.iterdir() if p.suffix.lower() in SUPPORTED_EXT]
    # naive sort - filenames already embed time in lexicographic order
    return sorted(paths)
