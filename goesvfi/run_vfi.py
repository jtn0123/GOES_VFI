from __future__ import annotations
import pathlib
import os  # Added for cpu_count
import time  # Added for model_id timestamp
import concurrent.futures  # Added for ProcessPoolExecutor

# imageio unused ignore removed by previous step or not needed
# from PIL import Image # Unused ignore removed
# from tqdm import tqdm # Unused ignore removed
from .pipeline.loader import discover_frames
from .pipeline.tiler import tile_image, merge_tiles
from .pipeline.interpolate import RifeBackend, interpolate_three
from .pipeline.cache import load_cached, save_cache
from goesvfi.utils import log
from .pipeline.raw_encoder import write_raw_mp4

# Add imports for typing
from numpy.typing import NDArray
from typing import Any, List, Tuple, Iterable, Optional, Iterator, Union, cast
from PIL import Image  # Import PIL directly
import numpy as np  # Re-added missing numpy import
from goesvfi.utils import config  # Import config module

# Define a type alias for float numpy arrays
FloatNDArray = NDArray[np.float32]

# Define ResultType at module level
ProcessPairResultType = Optional[Tuple[List[FloatNDArray], str]]

# Make TQDM_AVAILABLE global so worker can access it
TQDM_AVAILABLE = False
try:
    # Use optional tqdm dependency
    from tqdm import tqdm

    TQDM_AVAILABLE = True
except ImportError:
    # Define a dummy tqdm if not available
    def tqdm(iterable: Iterable, **kwargs) -> Iterable:  # type: ignore
        print("Processing (tqdm not installed)...")
        yield from iterable


# --- Type Aliases ---
# Define complex type alias at module level for Pylance
TilePairIterable = Iterable[
    Tuple[Tuple[int, int, NDArray[np.float32]], Tuple[int, int, NDArray[np.float32]]]
]

LOGGER = log.get_logger(__name__)

# DEFAULT_TILE_SIZE removed, get from config

# Define a type alias for the yielded progress update
ProgressUpdate = Tuple[int, int, float]  # (current_idx, total_pairs, eta_seconds)


# --- Helper function for parallel processing ---
def _process_pair(
    p1: pathlib.Path,
    p2: pathlib.Path,
    rife_exe_path: pathlib.Path,
    model_id_base: str,  # Use a base model ID, add interp_count later
    num_intermediate_frames: int,  # Changed from interp_count
    tile_size: Optional[int] = None,  # Allow tiling settings to be passed
) -> Tuple[List[FloatNDArray], str]:
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
        backend = RifeBackend(exe_path=rife_exe_path)  # Instantiate backend in worker
        inter_imgs: List[FloatNDArray] = []

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
                    tile_iterable = tqdm(
                        zip(tiles1, tiles2),
                        total=len(tiles1),
                        desc="Interpolating tiles (1-step)",
                        leave=False,
                    )

                for (x, y, t1), (_, _, t2) in tile_iterable:
                    interpolated_tile: NDArray[np.float32] = backend.interpolate_pair(
                        t1, t2
                    )
                    inter_tiles.append((x, y, interpolated_tile))

                # Merge the single set of intermediate tiles
                h_orig, w_orig, _ = img1.shape
                merged_img = merge_tiles(inter_tiles, (h_orig, w_orig))
                inter_imgs = [merged_img]

            elif num_intermediate_frames == 3:
                # Implement tiled 3-frame interpolation
                LOGGER.debug(
                    "Performing tiled 3-frame interpolation for: %s, %s",
                    p1.name,
                    p2.name,
                )

                inter_tiles_left: List[Tuple[int, int, NDArray[np.float32]]] = []
                inter_tiles_mid: List[Tuple[int, int, NDArray[np.float32]]] = []
                inter_tiles_right: List[Tuple[int, int, NDArray[np.float32]]] = []

                # Use a different variable name here to avoid shadowing
                tile_iterable_3step: TilePairIterable = zip(tiles1, tiles2)
                if TQDM_AVAILABLE:
                    # Note: Total is number of tile PAIRS, but 3 interpolations happen per pair.
                    # Using total=len(tiles1) for the outer loop progress.
                    tile_iterable_3step = tqdm(
                        tile_iterable_3step,
                        total=len(tiles1),
                        desc="Interpolating tiles (3-step)",
                        leave=False,
                    )

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
                raise ValueError(
                    f"Unsupported num_intermediate_frames for tiling: {num_intermediate_frames}"
                )

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
                raise ValueError(
                    f"Unsupported num_intermediate_frames: {num_intermediate_frames}"
                )

        # --- 4. Save Cache ---
        # Pass num_intermediate_frames to save_cache
        save_cache(p1, p2, model_id, num_intermediate_frames, inter_imgs)

        return [img1] + inter_imgs, "processed"

    except Exception as e:
        LOGGER.error(
            "Error processing pair %s, %s: %s", p1.name, p2.name, e, exc_info=True
        )
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
    tile_enable: bool = True,  # Default to True as in GUI
    max_workers: int = 0,  # 0 means auto-detect based on cores
) -> Iterator[Union[ProgressUpdate, pathlib.Path]]:
    """High-level helper. Yields progress (idx, total, eta) and returns MP4 path."""
    LOGGER.info("Input folder: %s", folder)
    LOGGER.info("Output MP4: %s", output_mp4_path)
    LOGGER.info("Using RIFE Executable: %s", rife_exe_path)
    LOGGER.info(
        "Target FPS: %d, Intermediate frames per pair: %d", fps, num_intermediate_frames
    )
    # Log tiling status based on new flag
    if tile_enable:
        LOGGER.info(
            "Tiling enabled for frames larger than %d pixels",
            config.get_default_tile_size(),
        )
    else:
        LOGGER.info("Tiling disabled")

    paths = discover_frames(folder)
    if len(paths) < 2:
        raise ValueError("Need at least 2 input frames to interpolate.")

    # Use timestamp in model_id base to differentiate runs if executable changes etc.
    # Using filename + timestamp as a proxy for model identity here
    model_id_base = f"{rife_exe_path.name}_{int(time.time())}"

    # Determine effective tile size based on flag
    effective_tile_size = config.get_default_tile_size() if tile_enable else None

    # Prepare arguments for parallel processing
    tasks = [
        (
            paths[i],
            paths[i + 1],
            rife_exe_path,
            model_id_base,
            num_intermediate_frames,
            effective_tile_size,  # Pass calculated tile size
        )
        for i in range(len(paths) - 1)
    ]

    # Determine max workers safely handling os.cpu_count() == None and respecting GUI limit
    cpu_cores = os.cpu_count()
    # Calculate available workers (leaving one free if possible)
    available_workers = max(1, cpu_cores - 1) if cpu_cores is not None else 1
    # Use the minimum of the GUI limit (if specified > 0) and available cores
    if max_workers > 0:
        num_workers = max(1, min(max_workers, available_workers))
    else:  # If GUI sent 0 or less, use auto-detected available workers
        num_workers = available_workers

    LOGGER.info("Using up to %d worker processes.", num_workers)

    # Prepare timing list for ETA calculation
    pair_times: List[float] = []
    total_pairs = len(tasks)

    # Initialize counters
    processed_count = 0
    cache_hit_count = 0
    error_count = 0

    # Run tasks in parallel using calculated num_workers
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
        # Use submit for better control and future retrieval
        futures = {
            executor.submit(_process_pair, *task): i for i, task in enumerate(tasks)
        }

        # Wrap with tqdm if available (TQDM_AVAILABLE is now global)
        # Process futures as they complete for more responsive ETA
        # Remove local definition of ResultType
        # ResultType = Optional[Tuple[List[FloatNDArray], str]]
        # Use module-level ProcessPairResultType
        results_list: List[ProcessPairResultType] = [
            None
        ] * total_pairs  # Pre-allocate results list
        processed_indices = 0

        # Iterate using as_completed for better progress updates
        # Add type parameter to Future
        future_iterator: Iterable[
            concurrent.futures.Future[Tuple[List[FloatNDArray], str]]
        ] = concurrent.futures.as_completed(futures)
        if TQDM_AVAILABLE:
            # Remove unused type: ignore
            future_iterator = tqdm(
                future_iterator, total=total_pairs, desc="Processing frame pairs"
            )

        start_time = time.time()  # Start time for the first future completion
        for future in future_iterator:
            task_index = futures[future]  # Get original index
            try:
                frames_for_pair, status = future.result()
                results_list[task_index] = (
                    frames_for_pair,
                    status,
                )  # Store result in correct order
            except Exception as exc:
                LOGGER.error(
                    f"Task {task_index} generated an exception: {exc}", exc_info=True
                )
                # Fallback: create a placeholder result to maintain structure
                img1_fallback = (
                    np.array(Image.open(tasks[task_index][0])).astype(np.float32)
                    / 255.0
                )
                # Use FloatNDArray here
                fallback_result: Tuple[List[FloatNDArray], str] = (
                    [img1_fallback],
                    f"error: {exc}",
                )
                results_list[task_index] = (
                    fallback_result  # Store result in correct order
                )
                status = "error"

            processed_indices += 1
            end_time = time.time()
            duration = end_time - start_time  # Duration for this completed task
            pair_times.append(duration)
            start_time = end_time  # Reset start time for the next duration measurement

            # Calculate ETA
            if pair_times:
                avg_time_per_pair = sum(pair_times) / len(pair_times)
                remaining_pairs = total_pairs - processed_indices
                eta_seconds = avg_time_per_pair * remaining_pairs
            else:
                eta_seconds = 0.0  # Or some other indicator like -1

            # Yield progress update
            yield (processed_indices, total_pairs, eta_seconds)

            # Update local counts based on status
            if status == "processed":
                processed_count += 1
            elif status == "cache_hit":
                cache_hit_count += 1
            elif status.startswith("error"):
                error_count += 1

    # Assemble final frame list in order (using pre-allocated list)
    final_output_frames: List[FloatNDArray] = []
    for result in results_list:
        if result:
            frames_list, _ = result
            final_output_frames.extend(frames_list)

    # Add the very last original frame
    if paths:
        # Cast the result explicitly to FloatNDArray
        last_frame: FloatNDArray = (
            np.array(Image.open(paths[-1])).astype(np.float32) / 255.0
        )
        final_output_frames.append(last_frame)

    LOGGER.info(
        "Processing summary: %d pairs processed, %d cache hits, %d errors.",
        processed_count,
        cache_hit_count,
        error_count,
    )

    if not final_output_frames:
        raise RuntimeError(
            "No frames were successfully processed or retrieved from cache."
        )
    if error_count > 0:
        LOGGER.warning(
            "%d pairs failed during processing. Video may be incomplete or contain only original frames for failed pairs.",
            error_count,
        )

    # --- Encode Video --- (Changed: Now writes raw video)
    LOGGER.info("Encoding raw intermediate video...")
    # Define raw path based on final output path, using .mkv suffix
    raw_mkv_path = output_mp4_path.with_name(f"{output_mp4_path.stem}_raw.mkv")

    write_raw_mp4(final_output_frames, raw_mkv_path, fps=fps)
    LOGGER.info("Raw video saved successfully to %s", raw_mkv_path)

    # Yield the raw path as the final item
    yield raw_mkv_path
