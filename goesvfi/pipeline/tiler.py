from __future__ import annotations

from typing import List, Tuple

import numpy as np
from numpy.typing import NDArray


def tile_image(
    img: NDArray[np.float32], tile_size: int = 2048, overlap: int = 32
) -> List[Tuple[int, int, NDArray[np.float32]]]:
    """Split H×W×3 image into overlapping RGB float32 tiles.

    Parameters
    ----------
    img:
        Full image to tile in H×W×3 format.
    tile_size:
        Size of the square tile. The actual tile may be smaller at the image
        edges.
    overlap:
        Amount of overlap in pixels between tiles. Set to 0 for no overlap.
    """

    h, w, _ = img.shape
    step = tile_size - overlap if overlap < tile_size else tile_size
    tiles: List[Tuple[int, int, NDArray[np.float32]]] = []
    y = 0
    while y < h:
        x = 0
        h_end = min(y + tile_size, h)
        while x < w:
            w_end = min(x + tile_size, w)
            tile = img[y:h_end, x:w_end, :].copy()
            tiles.append((x, y, tile))
            x += step
        y += step
    return tiles


def merge_tiles(
    tiles: List[Tuple[int, int, NDArray[np.float32]]],
    full_shape: Tuple[int, int],
    overlap: int = 32,
) -> NDArray[np.float32]:
    """Merge tiles back into a single image with optional edge blending."""
    H, W = full_shape
    canvas = np.zeros((H, W, 3), dtype=np.float32)
    weight = np.zeros((H, W, 1), dtype=np.float32)

    for x, y, tile in tiles:
        h, w, _ = tile.shape
        mask_y = np.ones(h, dtype=np.float32)
        mask_x = np.ones(w, dtype=np.float32)

        if overlap > 0:
            if y > 0:
                o = min(overlap, h)
                mask_y[:o] = np.linspace(0, 1, o, endpoint=False)
            if y + h < H:
                o = min(overlap, h)
                mask_y[h - o :] = np.linspace(1, 0, o, endpoint=False)
            if x > 0:
                o = min(overlap, w)
                mask_x[:o] = np.linspace(0, 1, o, endpoint=False)
            if x + w < W:
                o = min(overlap, w)
                mask_x[w - o :] = np.linspace(1, 0, o, endpoint=False)

        mask = mask_y[:, None] * mask_x[None, :]
        mask = mask[..., None]

        canvas[y : y + h, x : x + w] += tile * mask
        weight[y : y + h, x : x + w] += mask

    canvas /= np.maximum(weight, 1e-5)
    return canvas
