# TODO: IFRNet‑S via ONNX Runtime (CoreML/DirectML)

from __future__ import annotations
import tempfile
import subprocess
import pathlib
import shutil
import numpy as np  # type: ignore
from PIL import Image  # type: ignore


class RifeCliBackend:
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

    def interpolate_pair(self, img1: np.ndarray, img2: np.ndarray) -> np.ndarray:
        # RIFE CLI often works with PNGs in 0-255 range
        img1_u8 = (np.clip(img1, 0, 1) * 255).astype(np.uint8)
        img2_u8 = (np.clip(img2, 0, 1) * 255).astype(np.uint8)

        # Create a temp dir
        d = pathlib.Path(tempfile.mkdtemp())
        f1, f2, out_f = d / "1.png", d / "2.png", d / "out.png"

        try:
            Image.fromarray(img1_u8).save(f1)
            Image.fromarray(img2_u8).save(f2)

            # Call the RIFE binary: expecting one interpolated frame (-n 1)
            # Adapt command based on the specific CLI flags your RIFE exe uses
            # Example flags shown below might need adjustment.
            cmd = [
                str(self.exe),
                "-0", str(f1), # Use -0 for first input file
                "-1", str(f2), # Use -1 for second input file
                "-o", str(out_f),
                "-n", "1",    # Number of intermediate frames (1 = single middle frame)
                "-m", "goesvfi/models/rife-v4.6" # Explicitly set model path
            ]
            subprocess.run(cmd, check=True, capture_output=True, text=True)

            if not out_f.exists():
                 raise RuntimeError(f"RIFE executable did not produce expected output file: {out_f}")

            arr = np.array(Image.open(out_f)).astype(np.float32) / 255.0
        except subprocess.CalledProcessError as e:
            print(f"RIFE CLI Error Output:\n{e.stderr}")
            raise RuntimeError(f"RIFE executable failed with code {e.returncode}") from e
        except Exception as e:
            # Catch other potential errors during image processing or file handling
            raise RuntimeError(f"Error during RIFE CLI processing: {e}") from e
        finally:
            # Ensure temporary directory is always cleaned up
            shutil.rmtree(d)

        return arr

# Note: The input/output layer names ("in0", "in1", "out0") and the exact
# pixel format/normalization expected/produced by the specific RIFE NCNN model
# might need adjustment based on the model's architecture.
# The provided `RifeNcnnVulkan` class from the prompt was simplified and likely
# missed pixel format conversions and normalization steps.
