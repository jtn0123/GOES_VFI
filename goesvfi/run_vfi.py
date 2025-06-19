from __future__ import annotations

# Add imports for typing

# imageio unused ignore removed by previous step or not needed


# Standard temperature ranges for IR bands
TEMP_RANGES = {
    7: (200, 380),  # Fire detection
    8: (190, 258),  # Upper-level water vapor
    9: (190, 265),  # Mid-level water vapor
    10: (190, 280),  # Lower-level water vapor
    11: (190, 320),  # Cloud-top phase
    12: (210, 290),  # Ozone
    13: (190, 330),  # Clean IR longwave
    14: (190, 330),  # IR longwave
    15: (190, 320),  # Dirty IR longwave
    16: (190, 295),  # CO2 longwave
}
# from tqdm import tqdm # Unused ignore removed

# Define a type alias for float numpy arrays
FloatNDArray = NDArray[np.float32]

# Define ResultType at module level
ProcessPairResultType = Optional[Tuple[List[FloatNDArray], str]]

# Make TQDM_AVAILABLE global so worker can access it
TQDM_AVAILABLE = False
try:
    pass
    # Use optional tqdm dependency
except ImportError:
    pass

if error_count > 0:
    pass
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
