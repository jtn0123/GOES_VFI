# TODO: IFRNet‑S via ONNX Runtime (CoreML/DirectML)

from __future__ import annotations
import tempfile
import subprocess
import pathlib
import shutil
import numpy as np
import logging
from PIL import Image
from numpy.typing import NDArray
from typing import Any, List, Dict, Optional

# Import the new RIFE analyzer utilities
from goesvfi.utils.rife_analyzer import RifeCommandBuilder, RifeCapabilityDetector

# Set up logging
logger = logging.getLogger(__name__)


class RifeBackend:
    """Wraps an external RIFE command-line executable."""

    def __init__(self, exe_path: pathlib.Path):
        if not exe_path.is_file():
            raise FileNotFoundError(f"RIFE executable not found at: {exe_path}")
        if not shutil.which(str(exe_path)):
             # Check if it's executable or just if it exists
             # On Unix-like systems, check execute permission
             # On Windows, just check existence might be enough, but shutil.which checks PATHEXT
             # For simplicity, let's rely on FileNotFoundError for existence and assume user provides correct path
             # Or add more platform-specific checks if needed.
             pass # Basic existence checked above

        self.exe = exe_path
        # Create command builder for this executable
        self.command_builder = RifeCommandBuilder(exe_path)
        # Get capability detector for reference
        self.capability_detector = self.command_builder.detector
        
        # Log detected capabilities
        logger.info(f"RIFE executable capabilities: tiling={self.capability_detector.supports_tiling()}, "
                   f"uhd={self.capability_detector.supports_uhd()}, "
                   f"tta_spatial={self.capability_detector.supports_tta_spatial()}, "
                   f"tta_temporal={self.capability_detector.supports_tta_temporal()}, "
                   f"thread_spec={self.capability_detector.supports_thread_spec()}")

    def interpolate_pair(self,
                         img1: NDArray[np.float32],
                         img2: NDArray[np.float32],
                         options: Optional[Dict[str, Any]] = None
                        ) -> NDArray[np.float32]:
        """
        Interpolate between two frames using the RIFE CLI.
        
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
        f1, f2 = tmp/"1.png", tmp/"2.png"
        out_f = tmp / "out_frame.png" # Single output file for midpoint

        try:
            # Convert and save input images
            img1_u8 = (np.clip(img1, 0, 1) * 255).astype(np.uint8)
            img2_u8 = (np.clip(img2, 0, 1) * 255).astype(np.uint8)
            Image.fromarray(img1_u8).save(f1)
            Image.fromarray(img2_u8).save(f2)

            # Set default options
            timestep = options.get('timestep', 0.5)  # Default to midpoint
            
            # Build command using the command builder
            cmd_options = {
                'timestep': timestep,
                'num_frames': 1,  # Always 1 for interpolate_pair
                'model_path': options.get('model_path', "goesvfi/models/rife-v4.6"),
                'tile_enable': options.get('tile_enable', False),
                'tile_size': options.get('tile_size', 256),
                'uhd_mode': options.get('uhd_mode', False),
                'tta_spatial': options.get('tta_spatial', False),
                'tta_temporal': options.get('tta_temporal', False),
                'thread_spec': options.get('thread_spec', "1:2:2"),
                'gpu_id': options.get('gpu_id', -1),  # Default to -1 (auto)
            }
            
            cmd = self.command_builder.build_command(f1, f2, out_f, cmd_options)
            logger.debug(f"Running RIFE command: {' '.join(cmd)}")
            
            # Run the command
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # Log any output
            if result.stdout:
                logger.debug(f"RIFE stdout: {result.stdout}")
            if result.stderr:
                logger.warning(f"RIFE stderr: {result.stderr}")

            if not out_f.exists():
                raise RuntimeError(f"RIFE failed to generate frame at timestep {timestep}")

            # Load the generated frame
            frame_arr = np.array(Image.open(out_f)).astype(np.float32) / 255.0

        except subprocess.CalledProcessError as e:
            logger.error(f"RIFE CLI Error Output:\n{e.stderr}")
            raise RuntimeError(f"RIFE executable failed (timestep {timestep}) with code {e.returncode}") from e
        except Exception as e:
            logger.error(f"Error during RIFE CLI processing: {e}", exc_info=True)
            raise RuntimeError(f"Error during RIFE CLI processing: {e}") from e
        finally:
            shutil.rmtree(tmp)

        return frame_arr

def interpolate_three(img1: NDArray[np.float32], img2: NDArray[np.float32], backend: RifeBackend, options: Optional[Dict[str, Any]] = None) -> List[NDArray[np.float32]]:
    """
    Recursively interpolates three frames between img1 and img2.
    
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
    mid_options['timestep'] = 0.5
    img_mid = backend.interpolate_pair(img1, img2, mid_options)

    # Calculate the frame between img1 and img_mid (t=0.25)
    left_options = options.copy()
    left_options['timestep'] = 0.5  # Always 0.5 for the pair, which is effectively 0.25 overall
    img_left = backend.interpolate_pair(img1, img_mid, left_options)

    # Calculate the frame between img_mid and img2 (t=0.75)
    right_options = options.copy()
    right_options['timestep'] = 0.5  # Always 0.5 for the pair, which is effectively 0.75 overall
    img_right = backend.interpolate_pair(img_mid, img2, right_options)

    return [img_left, img_mid, img_right]

# Note about potential model differences can be kept or removed
# Note: The input/output layer names ("in0", "in1", "out0") and the exact
# pixel format/normalization expected/produced by the specific RIFE NCNN model
# might need adjustment based on the model's architecture.
