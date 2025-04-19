from __future__ import annotations
import pathlib
import numpy as np  # type: ignore
from PIL import Image  # type: ignore
from .pipeline.loader import discover_frames
from .pipeline.tiler import tile_image, merge_tiles
from .pipeline.interpolate import IFRNetSession
from .pipeline.cache import load_cached, save_cache
from .pipeline.encoder import write_mp4


def run_vfi(folder: pathlib.Path, model_path: pathlib.Path, fps: int = 60) -> pathlib.Path:
    """High-level helper called by GUI/CLI. Returns MP4 path."""
    paths = discover_frames(folder)
    if len(paths) < 2:
        raise ValueError("Need at least 2 frames")
    model_id = model_path.stem
    interp = IFRNetSession(model_path)

    output_frames: list[np.ndarray] = []
    for p1, p2 in zip(paths, paths[1:]):
        img1 = np.array(Image.open(p1)).astype(np.float32) / 255.0
        img2 = np.array(Image.open(p2)).astype(np.float32) / 255.0
        cached = load_cached(p1, p2, model_id)
        if cached is None:
            # tile if needed
            if max(img1.shape[0], img1.shape[1]) > 2048:
                tiles1 = tile_image(img1)
                tiles2 = tile_image(img2)
                inter_tiles: list[tuple[int,int,np.ndarray]] = []
                for (x, y, t1), (_, _, t2) in zip(tiles1, tiles2):
                    inter_tiles.append((x, y, interp.interpolate_pair(t1, t2)))
                inter_img = merge_tiles(inter_tiles, img1.shape[:2])
            else:
                inter_img = interp.interpolate_pair(img1, img2)
            save_cache(p1, p2, model_id, inter_img)
        else:
            inter_img = cached
        output_frames.extend([img1, inter_img])
    # append the last original frame
    output_frames.append(np.array(Image.open(paths[-1])).astype(np.float32) / 255.0)

    out_mp4 = folder / f"{folder.name}_vfi.mp4"
    write_mp4(output_frames, out_mp4, fps=fps)
    return out_mp4 