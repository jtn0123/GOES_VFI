from __future__ import annotations

import logging
import pathlib
import shutil
import subprocess
import tempfile
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from goesvfi.utils.rife_analyzer import RifeCommandBuilder

# Set up logging
logger = logging.getLogger(__name__)

# Import optimized backend (optional, falls back if not available)
try:
    from .optimized_interpolator import OptimizedRifeBackend
    OPTIMIZED_BACKEND_AVAILABLE = True
except ImportError:
    OPTIMIZED_BACKEND_AVAILABLE = False
    logger.debug("Optimized interpolator not available, using standard backend")


class RifeBackend:
    """Wraps an external RIFE command-line executable."""

    def __init__(self, exe_path: pathlib.Path) -> None:
        if not exe_path.is_file():
            msg = f"RIFE executable not found at: {exe_path}"
            raise FileNotFoundError(msg)
        if not shutil.which(str(exe_path)):
            # Check if it's executable or just if it exists
            # On Unix-like systems, check execute permission
            # On Windows, just check existence might be enough, but shutil.which checks PATHEXT
            # For simplicity, let's rely on FileNotFoundError for existence and assume user provides correct path
            # Or add more platform-specific checks if needed.
            logger.warning("RIFE executable may not be in PATH or executable")

        self.exe = exe_path
        # Create command builder for this executable
        self.command_builder = RifeCommandBuilder(exe_path)
        # Get capability detector for reference
        self.capability_detector = self.command_builder.detector

        # Log detected capabilities
        logger.info(
            "RIFE executable capabilities: tiling=%s, uhd=%s, tta_spatial=%s, tta_temporal=%s, thread_spec=%s",
            self.capability_detector.supports_tiling(),
            self.capability_detector.supports_uhd(),
            self.capability_detector.supports_tta_spatial(),
            self.capability_detector.supports_tta_temporal(),
            self.capability_detector.supports_thread_spec(),
        )

    def interpolate_pair(
        self,
        img1: NDArray[np.float32],
        img2: NDArray[np.float32],
        options: dict[str, Any] | None = None,
    ) -> NDArray[np.float32]:
        """Interpolate between two frames using the RIFE CLI.

        Args:
            img1: First input frame as float32 numpy array (0.0-1.0)
            img2: Second input frame as float32 numpy array (0.0-1.0)
            options: Optional dictionary of RIFE options

        Returns:
            Interpolated frame as float32 numpy array (0.0-1.0)
        """
        # Initialize options if None
        if options is None:
            options = {}

        tmp = pathlib.Path(tempfile.mkdtemp())
        f1, f2 = tmp / "1.png", tmp / "2.png"
        out_f = tmp / "out_frame.png"  # Single output file for midpoint

        try:
            # Convert and save input images
            img1_u8 = (np.clip(img1, 0, 1) * 255).astype(np.uint8)
            img2_u8 = (np.clip(img2, 0, 1) * 255).astype(np.uint8)
            Image.fromarray(img1_u8).save(f1)
            Image.fromarray(img2_u8).save(f2)

            # Set default options
            timestep = options.get("timestep", 0.5)  # Default to midpoint

            # Build command using the command builder
            cmd_options = {
                "timestep": timestep,
                "num_frames": 1,  # Always 1 for interpolate_pair
                "model_path": options.get("model_path", "goesvfi/models/rife-v4.6"),
                "tile_enable": options.get("tile_enable", False),
                "tile_size": options.get("tile_size", 256),
                "uhd_mode": options.get("uhd_mode", False),
                "tta_spatial": options.get("tta_spatial", False),
                "tta_temporal": options.get("tta_temporal", False),
                "thread_spec": options.get("thread_spec", "1:2:2"),
                "gpu_id": options.get("gpu_id", -1),  # Default to -1 (auto)
            }

            cmd = self.command_builder.build_command(f1, f2, out_f, cmd_options)
            logger.debug("Running RIFE command: %s", " ".join(cmd))

            # Run the command
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)

            # Log any output
            if result.stdout:
                logger.debug("RIFE stdout: %s", result.stdout)
            if result.stderr:
                logger.warning("RIFE stderr: %s", result.stderr)

            if not out_f.exists():
                msg = f"RIFE failed to generate frame at timestep {timestep}"
                raise RuntimeError(msg)

            # Load the generated frame
            with Image.open(out_f) as _img_temp:
                frame_arr = np.array(_img_temp).astype(np.float32) / 255.0

        except subprocess.CalledProcessError as e:
            logger.exception("RIFE CLI Error Output:\n%s", e.stderr)
            msg = f"RIFE executable failed (timestep {timestep}) with code {e.returncode}"
            raise RuntimeError(msg) from e
        except (KeyError, ValueError, RuntimeError) as e:
            logger.error("Error during RIFE CLI processing: %s", e, exc_info=True)
            msg = f"Error during RIFE CLI processing: {e}"
            raise OSError(msg) from e
        finally:
            shutil.rmtree(tmp)

        return frame_arr


def interpolate_three(
    img1: NDArray[np.float32],
    img2: NDArray[np.float32],
    backend: RifeBackend,
    options: dict[str, Any] | None = None,
) -> list[NDArray[np.float32]]:
    """Recursively interpolates three frames between img1 and img2.

    Args:
        img1: First input frame as float32 numpy array (0.0-1.0)
        img2: Second input frame as float32 numpy array (0.0-1.0)
        backend: RifeBackend instance
        options: Optional dictionary of RIFE options

    Returns:
        List of three interpolated frames as float32 numpy arrays (0.0-1.0)
    """
    # Initialize options if None
    if options is None:
        options = {}

    # Calculate the middle frame (t=0.5)
    mid_options = options.copy()
    mid_options["timestep"] = 0.5
    img_mid = backend.interpolate_pair(img1, img2, mid_options)

    # Calculate the frame between img1 and img_mid (t=0.25)
    left_options = options.copy()
    left_options["timestep"] = 0.5  # Always 0.5 for the pair, which is effectively 0.25 overall
    img_left = backend.interpolate_pair(img1, img_mid, left_options)

    # Calculate the frame between img_mid and img2 (t=0.75)
    right_options = options.copy()
    right_options["timestep"] = 0.5  # Always 0.5 for the pair, which is effectively 0.75 overall
    img_right = backend.interpolate_pair(img_mid, img2, right_options)

    return [img_left, img_mid, img_right]


def create_rife_backend(exe_path: pathlib.Path, optimized: bool = True, cache_size: int = 100) -> Any:
    """Create the best available RIFE backend.

    Args:
        exe_path: Path to RIFE executable
        optimized: Whether to use optimized backend if available
        cache_size: Cache size for optimized backend

    Returns:
        RifeBackend or OptimizedRifeBackend instance
    """
    if optimized and OPTIMIZED_BACKEND_AVAILABLE:
        logger.info("Creating optimized RIFE backend with cache_size=%d", cache_size)
        return OptimizedRifeBackend(exe_path, cache_size=cache_size)
    if optimized and not OPTIMIZED_BACKEND_AVAILABLE:
        logger.warning("Optimized backend requested but not available, using standard backend")
    else:
        logger.info("Creating standard RIFE backend")
    return RifeBackend(exe_path)


def get_backend_performance_info(backend: Any) -> dict[str, Any]:
    """Get performance information from a backend.

    Args:
        backend: RifeBackend or OptimizedRifeBackend instance

    Returns:
        Performance statistics dictionary
    """
    if hasattr(backend, "get_performance_stats"):
        return backend.get_performance_stats()
    return {
        "backend_type": "standard",
        "optimization_available": OPTIMIZED_BACKEND_AVAILABLE,
        "message": "Standard backend - no performance stats available"
    }


# Note about potential model differences can be kept or removed
# Note: The input/output layer names ("in0", "in1", "out0") and the exact
# pixel format/normalization expected/produced by the specific RIFE NCNN model
# might need adjustment based on the model's architecture.
