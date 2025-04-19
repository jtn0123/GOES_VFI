# TODO: IFRNet‑S via ONNX Runtime (CoreML/DirectML)

from __future__ import annotations
import tempfile
import subprocess
import pathlib
import shutil
import numpy as np
from PIL import Image
from numpy.typing import NDArray
from typing import Any, List


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

    def interpolate_pair(self,
                         img1: NDArray[np.float32],
                         img2: NDArray[np.float32],
                        ) -> NDArray[np.float32]:
        tmp = pathlib.Path(tempfile.mkdtemp())
        f1, f2 = tmp/"1.png", tmp/"2.png"

        out_f = tmp / "out_frame.png" # Single output file for midpoint

        try:
            img1_u8 = (np.clip(img1, 0, 1) * 255).astype(np.uint8)
            img2_u8 = (np.clip(img2, 0, 1) * 255).astype(np.uint8)
            Image.fromarray(img1_u8).save(f1)
            Image.fromarray(img2_u8).save(f2)

            timestep = 0.5 # Always interpolate the midpoint
            cmd = [
                str(self.exe),
                "-0", str(f1),
                "-1", str(f2),
                "-o", str(out_f), # Output single file
                "-s", f"{timestep:.6f}", # Set timestep
                "-n", "1", # Explicitly ask for 1 frame (may be default)
                "-m", "goesvfi/models/rife-v4.6"
                # No -f needed for single file output
            ]
            subprocess.run(cmd, check=True, capture_output=True, text=True)

            if not out_f.exists():
                raise RuntimeError(f"RIFE failed to generate frame at timestep {timestep}")

            # Load the generated frame
            frame_arr = np.array(Image.open(out_f)).astype(np.float32) / 255.0

        except subprocess.CalledProcessError as e:
            print(f"RIFE CLI Error Output:\n{e.stderr}")
            raise RuntimeError(f"RIFE executable failed (timestep {timestep}) with code {e.returncode}") from e
        except Exception as e:
            raise RuntimeError(f"Error during RIFE CLI processing: {e}") from e
        finally:
            shutil.rmtree(tmp)

        return frame_arr

def interpolate_three(img1: NDArray[np.float32], img2: NDArray[np.float32], backend: RifeBackend) -> List[NDArray[np.float32]]:
    """Recursively interpolates three frames between img1 and img2."""
    # Calculate the middle frame (t=0.5)
    img_mid = backend.interpolate_pair(img1, img2)

    # Calculate the frame between img1 and img_mid (t=0.25)
    img_left = backend.interpolate_pair(img1, img_mid)

    # Calculate the frame between img_mid and img2 (t=0.75)
    img_right = backend.interpolate_pair(img_mid, img2)

    return [img_left, img_mid, img_right]

# Note about potential model differences can be kept or removed
# Note: The input/output layer names ("in0", "in1", "out0") and the exact
# pixel format/normalization expected/produced by the specific RIFE NCNN model
# might need adjustment based on the model's architecture.
