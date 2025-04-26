import platform, subprocess, tarfile, zipfile
from pathlib import Path
from urllib.request import urlretrieve
import logging

LOGGER = logging.getLogger(__name__)

SAN_VERSION = "1.0.25"
BIN_DIR = Path(__file__).parent / "bin"

_LOOKUP = {                               #  << only the two targets you need
    ("Darwin",  "x86_64"): BIN_DIR / "osx-x64" / "Sanchez",
    ("Darwin",  "arm64"):  BIN_DIR / "osx-x64" / "Sanchez",
    ("Windows", "AMD64"):  BIN_DIR / "win-x64" / "Sanchez.exe",
}

def _bin() -> Path:
    key = (platform.system(), platform.machine())
    try:
        path = _LOOKUP[key]
    except KeyError:
        raise RuntimeError(f"Sanchez not packaged for {key}")
    if not path.exists():
        raise RuntimeError(f"Binary missing: {path}")
    return path

def colourise(ir_png: str | Path, out_png: str | Path, *, res_km: int = 4) -> Path:
    """Run the Sanchez binary to colourise an IR image.

    Args:
        ir_png: Path to the input IR PNG image.
        out_png: Path for the output colourised PNG image.
        res_km: Desired output resolution in km (default 4).

    Returns:
        Path to the output image.
    """
    bin_path = _bin()
    # Convert inputs to string paths for subprocess
    ir_png_str = str(ir_png)
    out_png_str = str(out_png)
    # Determine the directory containing the binary
    binary_dir = bin_path.parent
    cmd = [str(bin_path), "-s", ir_png_str, "-o", out_png_str,
           "-r", str(res_km)]
    LOGGER.info(f"Running Sanchez: {' '.join(cmd)} in directory {binary_dir}") # Log cwd
    try:
        # Use subprocess.run to capture output
        result = subprocess.run(
            cmd,
            check=True, # Still raise error on non-zero exit code
            capture_output=True,
            text=True, # Decode stdout/stderr as text
            encoding='utf-8', # Explicitly set encoding
            errors='replace', # Handle potential decoding errors
            cwd=binary_dir # <-- Set the current working directory
        )
        # Log stdout/stderr even on success if needed for debugging
        if result.stdout:
            LOGGER.debug(f"Sanchez stdout:\n{result.stdout}")
        if result.stderr:
            # Treat stderr as warning/info unless check=True fails
            LOGGER.info(f"Sanchez stderr:\n{result.stderr}")
        LOGGER.info(f"Sanchez completed successfully for {Path(ir_png).name}")

    except subprocess.CalledProcessError as e:
        # Log detailed error information if check=True fails
        LOGGER.error(f"Sanchez failed (Exit Code: {e.returncode}) for {Path(ir_png).name}")
        if e.stdout:
            LOGGER.error(f"--> Sanchez stdout:\n{e.stdout}")
        if e.stderr:
            LOGGER.error(f"--> Sanchez stderr:\n{e.stderr}")
        # Re-raise the original exception or a more specific one
        raise RuntimeError(f"Sanchez execution failed: {e}") from e
    except FileNotFoundError:
        LOGGER.error(f"Sanchez executable not found at: {bin_path}")
        raise # Re-raise
    except Exception as e:
        LOGGER.exception(f"An unexpected error occurred while running Sanchez for {Path(ir_png).name}")
        raise # Re-raise unexpected errors

    # Return the output path as a Path object
    return Path(out_png) 