# TODO: simple SHA‑256 → .npy cache

from __future__ import annotations
import hashlib
import pathlib
import numpy as np
# Import NDArray and Any for specific typing
from numpy.typing import NDArray
from typing import Any, List, Optional, cast

CACHE_DIR = pathlib.Path.home() / "Documents/goesvfi/cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Include num_intermediate_frames in the hash
def _hash_pair(path1: pathlib.Path, path2: pathlib.Path, model_id: str, num_intermediate_frames: int) -> str:
    h = hashlib.sha256()
    for p in (path1, path2):
        h.update(p.read_bytes())
    h.update(model_id.encode())
    h.update(str(num_intermediate_frames).encode())
    return h.hexdigest()

# Generate filename for a specific frame index
def _get_cache_filepath(base_key: str, index: int, total_frames: int) -> pathlib.Path:
    # Use zfill to ensure consistent sorting if needed, though direct indexing is used here
    max_digits = len(str(total_frames - 1))
    return CACHE_DIR / f"{base_key}_k{total_frames}_frame{index:0{max_digits}}.npy"

# Load a list of frames if all exist for the given count
def load_cached(path1: pathlib.Path, path2: pathlib.Path, model_id: str, num_intermediate_frames: int) -> Optional[List[NDArray[Any]]]:
    if num_intermediate_frames <= 0:
        return None # Cannot cache zero frames

    base_key = _hash_pair(path1, path2, model_id, num_intermediate_frames)
    frame_paths: List[pathlib.Path] = []
    all_exist = True

    # Check if all expected frame files exist
    for i in range(num_intermediate_frames):
        npy_path = _get_cache_filepath(base_key, i, num_intermediate_frames)
        if npy_path.exists():
            frame_paths.append(npy_path)
        else:
            all_exist = False
            break # No need to check further if one is missing

    if all_exist:
        # Load all frames if they all exist
        loaded_frames: List[NDArray[Any]] = []
        try:
            for npy_path in frame_paths:
                # Cast assumes loaded array is NDArray[Any]
                loaded_frames.append(cast(NDArray[Any], np.load(npy_path)))
            return loaded_frames
        except Exception as e:
            # Log error during loading? Handle potential corruption?
            print(f"Warning: Error loading cache files for key {base_key}: {e}")
            return None # Treat load error as cache miss
    else:
        return None # Cache miss if not all files were found

# Save a list of frames as separate files
def save_cache(path1: pathlib.Path, path2: pathlib.Path, model_id: str, num_intermediate_frames: int, frames: List[NDArray[Any]]) -> None:
    if not frames or num_intermediate_frames != len(frames):
        # Log error? Should not happen if called correctly
        print(f"Warning: Cache save called with mismatch: num_intermediate_frames={num_intermediate_frames}, len(frames)={len(frames)}")
        return

    base_key = _hash_pair(path1, path2, model_id, num_intermediate_frames)
    try:
        for i, frame in enumerate(frames):
            npy_path = _get_cache_filepath(base_key, i, num_intermediate_frames)
            np.save(npy_path, frame)
    except Exception as e:
        # Log error during saving? Clean up partial saves?
        print(f"Warning: Error saving cache files for key {base_key}: {e}")
