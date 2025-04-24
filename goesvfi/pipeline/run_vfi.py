import pathlib
from PIL import Image
import numpy as np
from typing import Iterator, Union, Tuple, Any, cast, IO
import subprocess
import tempfile
import time
import math
import logging # Add logging
import io # Add io

LOGGER = logging.getLogger(__name__) # Setup logger for this module

# --- Helper function to encode frame to PNG bytes --- 
def _encode_frame_to_png_bytes(img: Image.Image) -> bytes:
    """Encodes a PIL Image into PNG bytes memory.

    Args:
        img: PIL Image object.

    Returns:
        PNG image data as bytes.
    """
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# Helper function for safe writing to ffmpeg stdin with detailed error logging
def _safe_write(proc: subprocess.Popen[bytes], data: bytes, frame_desc: str) -> None:
    """Writes data to process stdin, handles BrokenPipeError with stderr logging."""
    if proc.stdin is None:
        LOGGER.error(f"Cannot write {frame_desc}: ffmpeg stdin is None.")
        stderr_bytes = b""
        if proc.stderr:
            stderr_bytes = proc.stderr.read()
        raise IOError(f"ffmpeg stdin pipe not available. Stderr: {stderr_bytes.decode(errors='ignore')}")

    try:
        proc.stdin.write(data)
    except BrokenPipeError:
        stderr_bytes = b""
        if proc.stderr:
            stderr_bytes = proc.stderr.read()
        # Include byte length in log message
        LOGGER.error(f"Broken pipe while writing {frame_desc} ({len(data)} bytes) — FFmpeg log:\n{stderr_bytes.decode(errors='ignore')}")
        raise
# --- End Helper ---

# Function to run RIFE interpolation and write raw video stream via ffmpeg
def run_vfi(
    folder: pathlib.Path,
    output_mp4_path: pathlib.Path,
    rife_exe_path: pathlib.Path,
    fps: int,
    num_intermediate_frames: int, # Currently handles 1
    tile_enable: bool,
    max_workers: int, # Currently unused, runs sequentially
    **kwargs: Any
) -> Iterator[Union[Tuple[int, int, float], pathlib.Path]]:
    """
    Runs RIFE interpolation or copies original frames to a raw video file.

    Yields:
        Tuple[int, int, float]: Progress updates (current_pair, total_pairs, eta_seconds).
        pathlib.Path: The path to the generated raw video file.

    Raises:
        NotImplementedError: If num_intermediate_frames is not 1.
        ValueError: If no PNG images or fewer than 2 images are found.
        IOError: If image dimensions cannot be read or frame processing fails.
        RuntimeError: If RIFE or ffmpeg subprocess execution fails.
    """

    # --- Parameter Extraction ---
    crop_rect_xywh = kwargs.get("crop_rect")
    model_key = kwargs.get("model_key", "RIFE v4.6 (default)")
    skip_model = kwargs.get("skip_model", False)

    # --- Input Validation ---
    if num_intermediate_frames != 1 and not skip_model:
        # TODO: Implement recursive logic for num_intermediate_frames=3
        raise NotImplementedError("Currently only num_intermediate_frames=1 is supported when not skipping model.")

    paths = sorted(folder.glob("*.png"))
    if not paths:
        raise ValueError("No PNG images found in the input folder.")
    if len(paths) < 2 and not skip_model:
        raise ValueError("At least two PNG images are required for interpolation.")
    if len(paths) < 1 and skip_model:
        raise ValueError("At least one PNG image is required when skipping model.")

    LOGGER.info(f"Found {len(paths)} images. Skip AI model: {skip_model}")

    # --- Crop Setup ---
    crop_for_pil: Tuple[int, int, int, int] | None = None

    if crop_rect_xywh:
        try:
            x, y, w, h = cast(Tuple[int, int, int, int], crop_rect_xywh)
            if w <= 0 or h <= 0:
                raise ValueError("Crop width and height must be positive.")
            crop_for_pil = (x, y, x + w, y + h) # Convert to PIL format
            LOGGER.info(f"Applying crop rectangle (x,y,w,h): {crop_rect_xywh} -> PIL format: {crop_for_pil}")
        except (TypeError, ValueError) as e:
            LOGGER.error(f"Invalid crop rectangle format provided: {crop_rect_xywh}. Error: {e}. Cropping will be disabled.")
            crop_for_pil = None # Disable cropping if format is wrong
            crop_rect_xywh = None # Also clear the original tuple
    else:
        LOGGER.info("No crop rectangle provided.")
        crop_for_pil = None # Explicitly None if no tuple provided

    # --- Determine frame dimensions ---
    im0: Image.Image | None = None
    try:
        im0 = Image.open(paths[0])
        orig_width, orig_height = im0.size # Get original size first
        target_width, target_height = orig_width, orig_height # Start with original

        if crop_for_pil and crop_rect_xywh: # Check both converted and original tuples
            x, y, w_crop, h_crop = crop_rect_xywh # Use original (x,y,w,h) for validation logic
            left, upper, right, lower = crop_for_pil # Use PIL format for cropping

            # Check if crop rectangle is valid for the first image
            if right > orig_width or lower > orig_height:
                 raise ValueError(f"Crop rectangle {crop_for_pil} (from {crop_rect_xywh}) exceeds dimensions ({orig_width}x{orig_height}) of first image {paths[0].name}")

            # Perform the crop using the correct PIL format tuple
            im0 = im0.crop(crop_for_pil)
            # Final target dimensions are post-crop
            target_width, target_height = im0.size
        elif crop_for_pil is None and crop_rect_xywh is not None:
             # This case means the input tuple was invalid earlier
             LOGGER.warning("Cropping was requested but tuple was invalid. Using original dimensions.")
             # target_width, target_height remain original

        LOGGER.info(f"Target frame dimensions (post-crop): {target_width}x{target_height}")
    except Exception as e:
        LOGGER.exception(f"Failed to read first image {paths[0]} for dimensions.")
        raise IOError(f"Could not read image dimensions from {paths[0]}") from e

    # --- Pre-Validation Loop ---
    LOGGER.info("Validating dimensions for all input frames...")
    for i, p_path in enumerate(paths[1:], start=1):
        try:
            with Image.open(p_path) as img:
                img_to_validate = img
                orig_w, orig_h = img.size
                if crop_for_pil and crop_rect_xywh: # Check both
                    x, y, w_crop, h_crop = crop_rect_xywh # Use x,y,w,h for validation logic
                    left, upper, right, lower = crop_for_pil # Use PIL format for cropping

                    # Check if crop rectangle is valid for this image
                    if right > orig_w or lower > orig_h:
                        raise ValueError(f"Crop rectangle {crop_for_pil} (from {crop_rect_xywh}) exceeds dimensions ({orig_w}x{orig_h}) of image {p_path.name}")
                    # Perform crop for validation using PIL format
                    img_to_validate = img.crop(crop_for_pil)

                # Check final size after potential crop against target dimensions
                if img_to_validate.size != (target_width, target_height):
                    raise ValueError(f"Inconsistent dimensions for {p_path.name}! Got {img_to_validate.size} after crop, expected {(target_width, target_height)}.")
        except Exception as e:
            LOGGER.exception(f"Error during validation for {p_path.name}")
            # Re-raise with more context
            raise ValueError(f"Validation failed for {p_path.name}: {e}") from e
    LOGGER.info("All input frames passed dimension validation.")
    # --- End Pre-Validation ---

    # --- Prepare raw output path ---
    raw_path = output_mp4_path.with_suffix('.raw.mp4')
    LOGGER.info(f"Intermediate raw video path: {raw_path}")

    # --- Determine Effective FPS for Raw Stream ---
    # If interpolating, total frames = originals + intermediate per pair
    # If skipping, total frames = originals
    effective_input_fps = fps * (num_intermediate_frames + 1) if not skip_model else fps

    # --- FFmpeg command: image2pipe input, verbose logging ---
    ffmpeg_cmd = [
        'ffmpeg',
        '-hide_banner',
        '-loglevel', 'info',   # Start with info, maybe debug later
        '-stats',
        '-y',
        '-f', 'image2pipe',
        '-framerate', str(effective_input_fps),
        '-vcodec', 'png',
        '-i', '-',
        '-an',
        '-vcodec', 'libx264',
        '-preset', 'ultrafast',
        '-pix_fmt', 'yuv420p',
        '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', # Ensure dimensions are divisible by 2
        str(raw_path)
    ]

    ffmpeg_proc: subprocess.Popen[bytes] | None = None
    try:
        # Start ffmpeg process, redirect stderr to stdout, capture combined stdout/stderr
        ffmpeg_proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.PIPE,
            stderr=subprocess.STDOUT,   # Redirect stderr to stdout
            stdout=subprocess.PIPE,    # Capture combined stdout/stderr
        )
        if ffmpeg_proc.stdin is None:
            raise IOError("Failed to get ffmpeg stdin pipe.")

        # --- Write the very first frame ---
        assert im0 is not None
        try:
            png_data = _encode_frame_to_png_bytes(im0)
            _safe_write(ffmpeg_proc, png_data, f"initial frame {paths[0].name}")
        except (IOError, BrokenPipeError):
            raise
        except Exception as e:
            raise IOError(f"Failed processing {paths[0].name}") from e

        # --- Main Processing Logic ---
        if skip_model:
            LOGGER.info("Skipping AI model. Writing original frames directly as PNGs.")
            for idx, p_path in enumerate(paths[1:], start=1):
                try:
                    with Image.open(p_path) as img:
                        # Use crop_for_pil here
                        img_to_write = img.crop(crop_for_pil) if crop_for_pil else img
                        # Pre-validation ensures dimensions match target_width, target_height
                        if img_to_write.size != (target_width, target_height):
                             LOGGER.warning(f"Resizing frame {p_path.name} from {img_to_write.size} to {(target_width, target_height)} before write (skip_model).")
                             img_to_write = img_to_write.resize((target_width, target_height), Image.Resampling.LANCZOS)
                        png_data = _encode_frame_to_png_bytes(img_to_write)
                        _safe_write(ffmpeg_proc, png_data, f"original frame {idx} ({p_path.name})")
                    yield (idx + 1, len(paths), 0.0)
                except (IOError, BrokenPipeError):
                    raise
                except Exception as e:
                    raise IOError(f"Failed processing frame {p_path.name}: {e}") from e
            LOGGER.info(f"Finished writing {len(paths)} original frames.")

        else: # Perform RIFE interpolation
            LOGGER.info("Starting AI interpolation.")
            total_pairs = len(paths) - 1
            start_time = time.time()
            last_yield_time = start_time

            # Interpolation loop (first frame already written)
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = pathlib.Path(tmpdir)
                LOGGER.debug(f"Using temporary directory for RIFE frames: {tmp_path}")

                for idx, (p1_path, p2_path) in enumerate(zip(paths, paths[1:])):
                    pair_start_time = time.time()
                    interpolated_frame_path = tmp_path / f"interp_{idx:04d}.png"
                    temp_p1_path = tmp_path / f"p1_{idx:04d}.png"
                    temp_p2_path = tmp_path / f"p2_{idx:04d}.png"

                    # --- Load, Crop (if needed), Save Temp Input Frames ---
                    try:
                        with Image.open(p1_path) as img1, Image.open(p2_path) as img2:
                            # Use crop_for_pil here
                            img1_to_rife = img1.crop(crop_for_pil) if crop_for_pil else img1
                            img2_to_rife = img2.crop(crop_for_pil) if crop_for_pil else img2

                            # Double-check dimensions before saving temp (should match target)
                            if img1_to_rife.size != (target_width, target_height):
                                LOGGER.warning(f"Cropped p1 {p1_path.name} size {img1_to_rife.size} != target {(target_width, target_height)}. Resizing before RIFE.")
                                img1_to_rife = img1_to_rife.resize((target_width, target_height), Image.Resampling.LANCZOS)
                            if img2_to_rife.size != (target_width, target_height):
                                LOGGER.warning(f"Cropped p2 {p2_path.name} size {img2_to_rife.size} != target {(target_width, target_height)}. Resizing before RIFE.")
                                img2_to_rife = img2_to_rife.resize((target_width, target_height), Image.Resampling.LANCZOS)

                            img1_to_rife.save(temp_p1_path, format="PNG")
                            img2_to_rife.save(temp_p2_path, format="PNG")
                    except Exception as e:
                         LOGGER.exception(f"Failed to load/crop/save temporary inputs for RIFE pair {idx} ({p1_path.name}, {p2_path.name})")
                         raise IOError(f"Preprocessing failed for RIFE pair {idx}") from e
                    # --- End Temp Input Frame Handling ---


                    # Prepare RIFE command (model selection, timestep, etc.)
                    model_map = {
                        "RIFE v4.6 (default)": "rife-v4.6",
                        "RIFE v4": "rife-v4",
                    }
                    model_key_from_ui = kwargs.get("model_key")
                    if not isinstance(model_key_from_ui, str):
                        model_key_from_ui = "RIFE v4.6 (default)"
                    cli_model = model_map.get(model_key_from_ui, "rife-v4.6")

                    # --- RIFE command using TEMP paths ---
                    rife_cmd = [
                        str(rife_exe_path),
                        "-m", cli_model,
                        '-0', str(temp_p1_path), # Use temp cropped path
                        '-1', str(temp_p2_path), # Use temp cropped path
                        '-o', str(interpolated_frame_path),
                        '-n', str(num_intermediate_frames),
                        "-s", str(1/(num_intermediate_frames+1))
                    ]
                    LOGGER.debug(f"Running RIFE command: {' '.join(rife_cmd)}")

                    # Run RIFE
                    try:
                        rife_run = subprocess.run(rife_cmd, check=True, capture_output=True, text=True)
                        LOGGER.debug(f"RIFE ({p1_path.name} -> {p2_path.name}) output: {rife_run.stdout[-200:]}") # Log last bit of stdout
                        if rife_run.stderr:
                             LOGGER.warning(f"RIFE ({p1_path.name} -> {p2_path.name}) stderr: {rife_run.stderr[-200:]}")
                    except FileNotFoundError:
                        LOGGER.error(f"RIFE executable not found at: {rife_exe_path}")
                        raise
                    except subprocess.CalledProcessError as e:
                        LOGGER.error(f"RIFE execution failed (exit code {e.returncode}) for pair {p1_path.name}, {p2_path.name}")
                        LOGGER.error(f"RIFE stdout: {e.stdout}")
                        LOGGER.error(f"RIFE stderr: {e.stderr}")
                        raise RuntimeError(f"RIFE failed for pair {idx}") from e
                    except Exception as e:
                        LOGGER.exception(f"An unexpected error occurred running RIFE for pair {idx}")
                        raise
                    finally:
                        # Clean up temporary input files
                        try: temp_p1_path.unlink()
                        except OSError: pass
                        try: temp_p2_path.unlink()
                        except OSError: pass


                    # --- Load, convert, write INTERPOLATED frame ---
                    # (No cropping needed here anymore, RIFE used cropped inputs)
                    if not interpolated_frame_path.exists():
                        raise RuntimeError(f"RIFE output missing for pair {idx}")
                    try:
                        with Image.open(interpolated_frame_path) as im_interp:
                            im_interp_to_write = im_interp # Assign directly
                            # Dimension check/resize for interpolated frame (safety check)
                            if im_interp_to_write.size != (target_width, target_height):
                                LOGGER.warning(f"Resizing interpolated frame for pair {idx} from {im_interp_to_write.size} to {(target_width, target_height)} (Post-RIFE check).")
                                im_interp_to_write = im_interp_to_write.resize((target_width, target_height), Image.Resampling.LANCZOS)
                            # --- End Dimension Check/Resize ---
                            png_data = _encode_frame_to_png_bytes(im_interp_to_write)
                            _safe_write(ffmpeg_proc, png_data, f"interpolated frame {idx}")
                        interpolated_frame_path.unlink()
                    except (IOError, BrokenPipeError):
                        raise
                    except Exception as e:
                        raise IOError(f"Failed processing interpolated frame {idx}") from e

                    # --- Load, crop, convert, write SECOND frame (p2) ---
                    # (This part remains largely the same, still need to load/crop original p2)
                    try:
                        with Image.open(p2_path) as im_second:
                            # Use crop_for_pil here
                            im_second_to_write = im_second.crop(crop_for_pil) if crop_for_pil else im_second
                            # Add dimension check/resize for safety, although pre-validation should catch this
                            if im_second_to_write.size != (target_width, target_height):
                                LOGGER.warning(f"Resizing second frame {p2_path.name} from {im_second_to_write.size} to {(target_width, target_height)} before write.")
                                im_second_to_write = im_second_to_write.resize((target_width, target_height), Image.Resampling.LANCZOS)
                            png_data = _encode_frame_to_png_bytes(im_second_to_write)
                            _safe_write(ffmpeg_proc, png_data, f"second frame {idx} ({p2_path.name})")
                    except (IOError, BrokenPipeError):
                        raise
                    except Exception as e:
                        raise IOError(f"Failed processing {p2_path.name}") from e

                    # Yield Progress
                    current_time = time.time()
                    elapsed = current_time - start_time
                    pairs_processed = idx + 1
                    time_per_pair = elapsed / pairs_processed if pairs_processed > 0 else 0
                    pairs_remaining = total_pairs - pairs_processed
                    eta = pairs_remaining * time_per_pair if time_per_pair > 0 else 0.0
                    if current_time - last_yield_time > 1.0 or pairs_processed == total_pairs:
                        yield (pairs_processed, total_pairs, eta)
                        last_yield_time = current_time
                    LOGGER.debug(f"Pair {idx+1}/{total_pairs} processed in {time.time() - pair_start_time:.2f}s. ETA: {eta:.1f}s")

            LOGGER.info("Finished AI interpolation processing.")

        # --- Finish ffmpeg process --- 
        LOGGER.info("Closing ffmpeg stdin.")
        if ffmpeg_proc.stdin:
            ffmpeg_proc.stdin.close()

        # Read and log combined output/error stream
        if ffmpeg_proc.stdout:
            for line_bytes in ffmpeg_proc.stdout:
                LOGGER.info(f"[ffmpeg-raw] {line_bytes.decode(errors='replace').rstrip()}")

        ret = ffmpeg_proc.wait()
        if ret != 0:
            LOGGER.error(f"FFmpeg (raw video creation) failed (exit code {ret}). See logged output above.")
            raise RuntimeError(f"FFmpeg (raw video creation) failed (exit code {ret})")
        LOGGER.info("FFmpeg (raw video creation) completed successfully.")

        if not raw_path.exists() or raw_path.stat().st_size == 0:
             LOGGER.error(f"Raw output file {raw_path} not created or is empty.")
             raise RuntimeError("Raw video file creation failed.")

        # --- Yield final path ---
        LOGGER.info(f"Successfully created raw video: {raw_path}")
        yield raw_path

    except Exception as e:
        LOGGER.exception("Error during VFI processing.")
        if ffmpeg_proc and ffmpeg_proc.poll() is None:
            LOGGER.warning("Terminating ffmpeg process due to error.")
            ffmpeg_proc.terminate()
            try: ffmpeg_proc.wait(timeout=5)
            except subprocess.TimeoutExpired: ffmpeg_proc.kill()
        raise

    # Yield final (raw) output path
    raw_path = output_mp4_path.with_suffix('.raw.mp4')
    # Simulate creating the file
    try:
        raw_path.touch() # Create dummy file for worker check
    except OSError as e:
        print(f"Warning: Could not create dummy raw file {raw_path}: {e}")

    yield raw_path

    # ... rest of the function remains unchanged ... 