import logging
import platform
import subprocess
from pathlib import Path

from goesvfi.utils import config  # Import config module

LOGGER = logging.getLogger(__name__)

# SAN_VERSION removed (not configurable)
# BIN_DIR removed (get from config)

_LOOKUP = {  # only the two targets you need
    ("Darwin", "x86_64"): config.get_sanchez_bin_dir() / "osx-x64" / "Sanchez",
    ("Darwin", "arm64"): config.get_sanchez_bin_dir() / "osx-x64" / "Sanchez",
    ("Windows", "AMD64"): config.get_sanchez_bin_dir() / "win-x64" / "Sanchez.exe",
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

    # Ensure the output directory exists
    out_dir = Path(out_png).parent
    import os

    os.makedirs(out_dir, exist_ok=True)
    LOGGER.info("Ensuring output directory exists: %s", out_dir)

    # Add the geostationary subcommand which is required for proper operation
    cmd = [
        str(bin_path),
        "geostationary",
        "-s",
        ir_png_str,
        "-o",
        out_png_str,
        "-r",
        str(res_km),
    ]

    # Add false color options (-c and -g) for geostationary processing
    gradient_path = binary_dir / "Resources" / "Gradients" / "Atmosphere.json"
    if gradient_path.exists():
        cmd.extend(["-c", "0.0-1.0", "-g", str(gradient_path)])
        LOGGER.info("Adding false color gradient: %s", gradient_path)
    else:
        LOGGER.warning(
            f"Gradient file not found at {gradient_path}, false color may not be applied"
        )

    LOGGER.info(
        f"Running Sanchez: {' '.join(map(str, cmd))} in directory {binary_dir}"
    )  # Log cwd with better formatting
    try:
        # Use subprocess.run to capture output
        result = subprocess.run(
            cmd,
            check=True,  # Still raise error on non-zero exit code
            capture_output=True,
            text=True,  # Decode stdout/stderr as text
            encoding="utf-8",  # Explicitly set encoding
            errors="replace",  # Handle potential decoding errors
            cwd=binary_dir,  # <-- Set the current working directory
            timeout=120,
        )
        # Log stdout/stderr even on success if needed for debugging
        if result.stdout:
            LOGGER.debug("Sanchez stdout:\n%s", result.stdout)
        if result.stderr:
            # Treat stderr as warning/info unless check=True fails
            LOGGER.info("Sanchez stderr:\n%s", result.stderr)
        LOGGER.info("Sanchez completed successfully for %s", Path(ir_png).name)

    except subprocess.CalledProcessError as e:
        # Log detailed error information if check=True fails
        LOGGER.error(
            f"Sanchez failed (Exit Code: {e.returncode}) for {Path(ir_png).name}"
        )
        if e.stdout:
            LOGGER.error("--> Sanchez stdout:\n%s", e.stdout)
        if e.stderr:
            LOGGER.error("--> Sanchez stderr:\n%s", e.stderr)
        # Re-raise the original exception or a more specific one
        raise RuntimeError(f"Sanchez execution failed: {e}") from e
    except FileNotFoundError:
        LOGGER.error("Sanchez executable not found at: %s", bin_path)
        raise  # Re-raise
    except (OSError, ValueError, KeyError) as e:
        LOGGER.exception(
            f"An unexpected error occurred while running Sanchez for {Path(ir_png).name}: {e}"
        )
        raise  # Re-raise unexpected errors

    # Return the output path as a Path object
    return Path(out_png)
