"""Utility helpers for caching interpolated frames on disk.

Frames are saved as ``.npy`` files using a SHA-256 hash derived from the two
input frame paths, the RIFE model identifier and the number of interpolated
frames.  When the same inputs are processed again the cached ``.npy`` files are
loaded instead of recomputing the interpolation.
"""

from __future__ import annotations

import hashlib
import pathlib
from typing import Any, List, Optional, cast

import numpy as np

# Import NDArray and Any for specific typing
from numpy.typing import NDArray

from goesvfi.utils import config  # Import config module
from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)

# Get cache directory from config
CACHE_DIR = pathlib.Path(config.get_cache_dir())
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# Include num_intermediate_frames in the hash
def _hash_pair(
    path1: pathlib.Path,
    path2: pathlib.Path,
    model_id: str,
    num_intermediate_frames: int,
) -> str:
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
def load_cached(
    path1: pathlib.Path,
    path2: pathlib.Path,
    model_id: str,
    num_intermediate_frames: int,
) -> Optional[List[NDArray[Any]]]:
    """Load cached intermediate frames if all ``.npy`` files are present."""
    LOGGER.debug(
        "Attempting to load cache for %s, %s, model=%s, frames=%s",
        path1.name,
        path2.name,
        model_id,
        num_intermediate_frames,
    )
    if num_intermediate_frames <= 0:
        LOGGER.debug("num_intermediate_frames is 0 or less, returning None")
        return None  # Cannot cache zero frames

    base_key = _hash_pair(path1, path2, model_id, num_intermediate_frames)
    frame_paths: List[pathlib.Path] = []
    all_exist = True

    # Check if all expected frame files exist
    LOGGER.debug(
        "Checking for existence of %s cache files with base key %s",
        num_intermediate_frames,
        base_key,
    )
    for i in range(num_intermediate_frames):
        npy_path = _get_cache_filepath(base_key, i, num_intermediate_frames)
        LOGGER.debug("Checking if %s exists", npy_path)
        if npy_path.exists():
            frame_paths.append(npy_path)
        else:
            LOGGER.debug("Cache file %s missing", npy_path)
            all_exist = False
            break  # No need to check further if one is missing

    if all_exist:
        # Load all frames if they all exist
        LOGGER.debug("All cache files found, attempting to load %s files", len(frame_paths))
        loaded_frames: List[NDArray[Any]] = []
        try:
            for npy_path in frame_paths:
                LOGGER.debug("Loading cache file: %s", npy_path)
                loaded_frames.append(cast(NDArray[Any], np.load(npy_path)))
            LOGGER.debug("Successfully loaded all cache files")
            return loaded_frames
        except (OSError, KeyError, ValueError, RuntimeError) as e:
            LOGGER.warning("Error loading cache files for key %s: %s", base_key, e)
            LOGGER.debug("Exception details:", exc_info=True)
            return None
    else:
        LOGGER.debug("Not all cache files exist, cache miss")
        return None  # Cache miss if not all files were found


# Save a list of frames as separate files
def save_cache(
    path1: pathlib.Path,
    path2: pathlib.Path,
    model_id: str,
    num_intermediate_frames: int,
    frames: List[NDArray[Any]],
) -> None:
    """Persist interpolated frames to ``CACHE_DIR`` for later reuse."""
    LOGGER.debug(
        "Attempting to save cache for %s, %s, model=%s, frames=%s",
        path1.name,
        path2.name,
        model_id,
        num_intermediate_frames,
    )
    LOGGER.debug(
        "save_cache - num_intermediate_frames: %s (type: %s), len(frames): %s (type: %s)",
        num_intermediate_frames,
        type(num_intermediate_frames),
        len(frames),
        type(frames),
    )
    if not frames or num_intermediate_frames != len(frames):
        LOGGER.warning(
            "Cache save called with mismatch: num_intermediate_frames=%s, len(frames)=%s",
            num_intermediate_frames,
            len(frames),
        )
        LOGGER.debug("save_cache returning early due to mismatch")
        return

    base_key = _hash_pair(path1, path2, model_id, num_intermediate_frames)
    LOGGER.debug("Saving %s cache files with base key %s", len(frames), base_key)
    try:
        for i, frame in enumerate(frames):
            npy_path = _get_cache_filepath(base_key, i, num_intermediate_frames)
            LOGGER.debug("Saving cache file: %s", npy_path)
            np.save(npy_path, frame)
        LOGGER.debug("Successfully saved all cache files")
    except (KeyError, ValueError, RuntimeError) as e:
        LOGGER.warning("Error saving cache files for key %s: %s", base_key, e)
        LOGGER.debug("Exception details:", exc_info=True)
        raise IOError(f"Error saving cache files for key {base_key}: {e}") from e
