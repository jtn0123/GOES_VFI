from __future__ import annotations
import pathlib
import numpy as np  # type: ignore
import imageio.v2 as imageio # type: ignore
from PIL import Image  # type: ignore
from tqdm import tqdm # type: ignore
from .pipeline.loader import discover_frames
from .pipeline.tiler import tile_image, merge_tiles
from .pipeline.interpolate import RifeCliBackend
from .pipeline.cache import load_cached, save_cache
from goesvfi.utils import log
from .pipeline.encoder import write_mp4

LOGGER = log.get_logger(__name__)

def run_vfi(
    folder: pathlib.Path,
    rife_exe_path: pathlib.Path,
    fps: int = 60,
    tile_size: int | None = 256,
    cache_capacity: int = 500,
) -> pathlib.Path:
    """
    Perform Video Frame Interpolation (VFI) on a folder of images.

    Args:
        folder: Path to the folder containing input image frames.
        rife_exe_path: Path to the RIFE command-line executable.
        fps: Target frames per second for the output video.
        tile_size: Maximum dimension for image tiles (e.g., 256). If None, tiling is disabled.
            Reduces memory usage for large images but may introduce minor artifacts.
        cache_capacity: Maximum number of interpolated frames to keep in the cache.

    Returns:
        Path to the generated MP4 file.
    """
    in_dir = pathlib.Path(folder).expanduser()
    out_mp4 = in_dir.parent / f"{in_dir.name}_interpolated_{fps}fps.mp4"

    LOGGER.info("Input folder: %s", in_dir)
    LOGGER.info("Output MP4: %s", out_mp4)
    LOGGER.info("Using RIFE Executable: %s", rife_exe_path)
    backend = RifeCliBackend(exe_path=rife_exe_path)

    paths = discover_frames(folder)
    if len(paths) < 2:
        raise ValueError("Need at least 2 frames for interpolation.")
    # Use the executable path stem for cache key (or a fixed string if preferred)
    model_id = rife_exe_path.stem

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
                    inter_tiles.append((x, y, backend.interpolate_pair(t1, t2)))
                h, w, _ = img1.shape
                inter_img = merge_tiles(inter_tiles, (h, w))
            else:
                inter_img = backend.interpolate_pair(img1, img2)
            save_cache(p1, p2, model_id, inter_img)
        else:
            inter_img = cached
        output_frames.extend([img1, inter_img])
    # append the last original frame
    output_frames.append(np.array(Image.open(paths[-1])).astype(np.float32) / 255.0)

    out_mp4 = folder / f"{folder.name}_vfi.mp4"
    write_mp4(output_frames, out_mp4, fps=fps)
    return out_mp4 