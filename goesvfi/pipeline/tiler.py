# TODO: split/merge with overlap

from __future__ import annotations
import numpy as np  # type: ignore
from typing import List, Tuple


def tile_image(img: np.ndarray, tile_size: int = 2048, overlap: int = 32) -> List[Tuple[int,int,np.ndarray]]:
    """Split H×W×3 image into overlapping RGB float32 tiles."""
    h, w, _ = img.shape
    tiles: List[Tuple[int,int,np.ndarray]] = []
    y = 0
    while y < h:
        x = 0
        h_end = min(y + tile_size, h)
        while x < w:
            w_end = min(x + tile_size, w)
            tile = img[y:h_end, x:w_end, :].copy()
            tiles.append((x, y, tile))
            x += tile_size - overlap
        y += tile_size - overlap
    return tiles


def merge_tiles(tiles: List[Tuple[int,int,np.ndarray]], full_shape: Tuple[int,int], overlap: int = 32) -> np.ndarray:
    H, W = full_shape
    canvas = np.zeros((H, W, 3), dtype=np.float32)
    weight = np.zeros((H, W, 1), dtype=np.float32)
    for x, y, tile in tiles:
        h, w, _ = tile.shape
        alpha = np.ones((h, w, 1), dtype=np.float32)
        canvas[y:y+h, x:x+w] += tile * alpha
        weight[y:y+h, x:x+w] += alpha
    canvas /= np.maximum(weight, 1e-5)
    return canvas
