from __future__ import annotations
import pathlib
import os # Added for cpu_count
import time # Added for model_id timestamp
import concurrent.futures # Added for ProcessPoolExecutor
# imageio unused ignore removed by previous step or not needed
# from PIL import Image # Unused ignore removed
# from tqdm import tqdm # Unused ignore removed
from .pipeline.loader import discover_frames
from .pipeline.tiler import tile_image, merge_tiles
from .pipeline.interpolate import RifeBackend, interpolate_three
from .pipeline.cache import load_cached, save_cache
from goesvfi.utils import log
from .pipeline.encoder import write_mp4
# Add imports for typing
from numpy.typing import NDArray
from typing import Any, List, Tuple, Iterable, Optional
from PIL import Image # Import PIL directly
import numpy as np # Re-added missing numpy import

# Make TQDM_AVAILABLE global so worker can access it
TQDM_AVAILABLE = False
try:
    # Use optional tqdm dependency
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    # Define a dummy tqdm if not available
    def tqdm(iterable: Iterable, **kwargs) -> Iterable: # type: ignore
        print("Processing (tqdm not installed)...")
        yield from iterable

# --- Type Aliases ---
# Define complex type alias at module level for Pylance
TilePairIterable = Iterable[Tuple[Tuple[int, int, NDArray[np.float32]], Tuple[int, int, NDArray[np.float32]]]]

LOGGER = log.get_logger(__name__)

DEFAULT_TILE_SIZE = 2048 # Define default tile size

# --- Helper function for parallel processing ---
def _process_pair(
    p1: pathlib.Path,
    p2: pathlib.Path,
    rife_exe_path: pathlib.Path,
    model_id_base: str, # Use a base model ID, add interp_count later
    num_intermediate_frames: int, # Changed from interp_count
    tile_size: Optional[int] = None, # Allow tiling settings to be passed
) -> Tuple[List[NDArray[np.float32]], str]:
    """Processes a single pair of images, returning frames and cache status."""
    try:
        # Generate model_id including num_intermediate_frames for caching
        model_id = f"{model_id_base}_k{num_intermediate_frames}"

        # --- 1. Check Cache ---
        # Pass num_intermediate_frames to cache functions
        cached_frames = load_cached(p1, p2, model_id, num_intermediate_frames)
        if cached_frames is not None:
            img1_arr = np.array(Image.open(p1)).astype(np.float32) / 255.0
            return [img1_arr] + cached_frames, "cache_hit"

        # --- 2. Load Images (if not cached) ---
        img1 = np.array(Image.open(p1)).astype(np.float32) / 255.0
        img2 = np.array(Image.open(p2)).astype(np.float32) / 255.0

        # --- 3. Interpolate ---
        backend = RifeBackend(exe_path=rife_exe_path) # Instantiate backend in worker
        inter_imgs: List[NDArray[np.float32]] = []

        # Tiling logic
        if tile_size and max(img1.shape[0], img1.shape[1]) > tile_size:
            LOGGER.debug("Tiling images for interpolation: %s, %s", p1.name, p2.name)
            tiles1 = tile_image(img1, tile_size=tile_size)
            tiles2 = tile_image(img2, tile_size=tile_size)

            # Interpolate tiles based on num_intermediate_frames
            if num_intermediate_frames == 1:
                # For 1 frame, interpolate each tile pair once
                inter_tiles: List[Tuple[int, int, NDArray[np.float32]]] = []
                tile_iterable: TilePairIterable = zip(tiles1, tiles2)
                if TQDM_AVAILABLE:
                    # Use specific desc for 1-step
                    tile_iterable = tqdm(zip(tiles1, tiles2), total=len(tiles1), desc="Interpolating tiles (1-step)", leave=False)

                for (x, y, t1), (_, _, t2) in tile_iterable:
                    interpolated_tile: NDArray[np.float32] = backend.interpolate_pair(t1, t2)
                    inter_tiles.append((x, y, interpolated_tile))

                # Merge the single set of intermediate tiles
                h_orig, w_orig, _ = img1.shape
                merged_img = merge_tiles(inter_tiles, (h_orig, w_orig))
                inter_imgs = [merged_img]

            elif num_intermediate_frames == 3:
                # Implement tiled 3-frame interpolation
                LOGGER.debug("Performing tiled 3-frame interpolation for: %s, %s", p1.name, p2.name)

                inter_tiles_left: List[Tuple[int, int, NDArray[np.float32]]] = []
                inter_tiles_mid: List[Tuple[int, int, NDArray[np.float32]]] = []
                inter_tiles_right: List[Tuple[int, int, NDArray[np.float32]]] = []

                # Use a different variable name here to avoid shadowing
                tile_iterable_3step: TilePairIterable = zip(tiles1, tiles2)
                if TQDM_AVAILABLE:
                    # Note: Total is number of tile PAIRS, but 3 interpolations happen per pair.
                    # Using total=len(tiles1) for the outer loop progress.
                    tile_iterable_3step = tqdm(tile_iterable_3step, total=len(tiles1), desc="Interpolating tiles (3-step)", leave=False)

                # Iterate using the new variable name
                for (x, y, t1), (_, _, t2) in tile_iterable_3step:
                    # Step 1: Interpolate midpoint tile (t=0.5)
                    t_mid = backend.interpolate_pair(t1, t2)
                    inter_tiles_mid.append((x, y, t_mid))

                    # Step 2: Interpolate left tile (t=0.25, between t1 and t_mid)
                    t_left = backend.interpolate_pair(t1, t_mid)
                    inter_tiles_left.append((x, y, t_left))

                    # Step 3: Interpolate right tile (t=0.75, between t_mid and t2)
                    t_right = backend.interpolate_pair(t_mid, t2)
                    inter_tiles_right.append((x, y, t_right))

                # Merge the three sets of intermediate tiles
                h_orig, w_orig, _ = img1.shape
                merged_img_left = merge_tiles(inter_tiles_left, (h_orig, w_orig))
                merged_img_mid = merge_tiles(inter_tiles_mid, (h_orig, w_orig))
                merged_img_right = merge_tiles(inter_tiles_right, (h_orig, w_orig))

                inter_imgs = [merged_img_left, merged_img_mid, merged_img_right]

            else:
                # This condition should ideally not be reached if GUI/caller restricts input
                raise ValueError(f"Unsupported num_intermediate_frames for tiling: {num_intermediate_frames}")

            # Tiled merging logic is now inside the if/elif blocks above

        else:
            # No tiling needed
            if num_intermediate_frames == 1:
                # Call interpolate_pair once, wrap result in list
                inter_imgs = [backend.interpolate_pair(img1, img2)]
            elif num_intermediate_frames == 3:
                # Call interpolate_three
                inter_imgs = interpolate_three(img1, img2, backend)
            else:
                raise ValueError(f"Unsupported num_intermediate_frames: {num_intermediate_frames}")

        # --- 4. Save Cache ---
        # Pass num_intermediate_frames to save_cache
        save_cache(p1, p2, model_id, num_intermediate_frames, inter_imgs)

        return [img1] + inter_imgs, "processed"

    except Exception as e:
        LOGGER.error("Error processing pair %s, %s: %s", p1.name, p2.name, e, exc_info=True)
        # Return the first frame only and indicate error, allows partial video generation
        img1_fallback = np.array(Image.open(p1)).astype(np.float32) / 255.0
        return [img1_fallback], f"error: {e}"


# --- Main function ---
def run_vfi(
    folder: pathlib.Path,
    output_mp4_path: pathlib.Path,
    rife_exe_path: pathlib.Path,
    fps: int = 60,
    num_intermediate_frames: int = 1,
    # Add new parameters, remove old tile_size
    tile_enable: bool = True,      # Default to True as in GUI
    max_workers: int = 0          # 0 means auto-detect based on cores
) -> pathlib.Path:
    """High-level helper called by GUI/CLI. Returns MP4 path."""
    LOGGER.info("Input folder: %s", folder)
    LOGGER.info("Output MP4: %s", output_mp4_path)
    LOGGER.info("Using RIFE Executable: %s", rife_exe_path)
    LOGGER.info("Target FPS: %d, Intermediate frames per pair: %d", fps, num_intermediate_frames)
    # Log tiling status based on new flag
    if tile_enable:
        LOGGER.info("Tiling enabled for frames larger than %d pixels", DEFAULT_TILE_SIZE)
    else:
        LOGGER.info("Tiling disabled")

    paths = discover_frames(folder)
    if len(paths) < 2:
        raise ValueError("Need at least 2 input frames to interpolate.")

    # Use timestamp in model_id base to differentiate runs if executable changes etc.
    # Using filename + timestamp as a proxy for model identity here
    model_id_base = f"{rife_exe_path.name}_{int(time.time())}"

    # Determine effective tile size based on flag
    effective_tile_size = DEFAULT_TILE_SIZE if tile_enable else None

    # Prepare arguments for parallel processing
    tasks = [
        (
            paths[i],
            paths[i+1],
            rife_exe_path,
            model_id_base,
            num_intermediate_frames,
            effective_tile_size # Pass calculated tile size
        )
        for i in range(len(paths) - 1)
    ]

    output_frames_lists: List[Tuple[List[NDArray[np.float32]], str]] = []
    processed_count = 0
    cache_hit_count = 0
    error_count = 0

    # Determine max workers safely handling os.cpu_count() == None and respecting GUI limit
    cpu_cores = os.cpu_count()
    # Calculate available workers (leaving one free if possible)
    available_workers = max(1, cpu_cores - 1) if cpu_cores is not None else 1
    # Use the minimum of the GUI limit (if specified > 0) and available cores
    if max_workers > 0:
        num_workers = max(1, min(max_workers, available_workers))
    else: # If GUI sent 0 or less, use auto-detected available workers
        num_workers = available_workers

    LOGGER.info("Using up to %d worker processes.", num_workers)

    # Run tasks in parallel using calculated num_workers
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
        results_iterator = executor.map(_process_pair, *zip(*tasks))

        # Wrap with tqdm if available (TQDM_AVAILABLE is now global)
        if TQDM_AVAILABLE:
            results_iterator = tqdm(results_iterator, total=len(tasks), desc="Processing frame pairs") # type: ignore

        for frames_for_pair, status in results_iterator:
            output_frames_lists.append((frames_for_pair, status))
            if status == "processed":
                processed_count += 1
            elif status == "cache_hit":
                cache_hit_count += 1
            elif status.startswith("error"):
                error_count += 1

    # Assemble final frame list in order
    final_output_frames: List[NDArray[np.float32]] = []
    for frames_list, _ in output_frames_lists:
        final_output_frames.extend(frames_list)

    # Add the very last original frame
    if paths:
         final_output_frames.append(np.array(Image.open(paths[-1])).astype(np.float32) / 255.0)

    LOGGER.info(
        "Processing summary: %d pairs processed, %d cache hits, %d errors.",
        processed_count, cache_hit_count, error_count
    )

    if not final_output_frames:
         raise RuntimeError("No frames were successfully processed or retrieved from cache.")
    if error_count > 0:
         LOGGER.warning("%d pairs failed during processing. Video may be incomplete or contain only original frames for failed pairs.", error_count)

    # --- Encode Video ---
    LOGGER.info("Encoding final video...")
    write_mp4(final_output_frames, output_mp4_path, fps=fps)
    LOGGER.info("Video saved successfully to %s", output_mp4_path)

    return output_mp4_path 