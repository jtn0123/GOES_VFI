# TODO: simple SHA‑256 → .npy cache

from __future__ import annotations
import hashlib
import pathlib
import numpy as np  # type: ignore

CACHE_DIR = pathlib.Path.home() / "Documents/goesvfi/cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _hash_pair(path1: pathlib.Path, path2: pathlib.Path, model_id: str) -> str:
    h = hashlib.sha256()
    for p in (path1, path2):
        h.update(p.read_bytes())
    h.update(model_id.encode())
    return h.hexdigest()

def load_cached(path1: pathlib.Path, path2: pathlib.Path, model_id: str) -> np.ndarray | None:
    key = _hash_pair(path1, path2, model_id)
    npy = CACHE_DIR / f"{key}.npy"
    if npy.exists():
        return np.load(npy)  # type: ignore
    return None

def save_cache(path1: pathlib.Path, path2: pathlib.Path, model_id: str, frame: np.ndarray) -> None:
    key = _hash_pair(path1, path2, model_id)
    np.save(CACHE_DIR / f"{key}.npy", frame)  # type: ignore
