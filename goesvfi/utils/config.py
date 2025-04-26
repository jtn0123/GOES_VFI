# TODO: path + TOML config
from __future__ import annotations
from typing import Dict
"""goesvfi.utils.config – user paths and TOML config loader"""

import os
import pathlib
import tomllib
from functools import lru_cache
import sys  # Add for platform check
import shutil  # Add for searching in PATH

CONFIG_DIR = pathlib.Path.home() / ".config/goesvfi"
CONFIG_FILE = CONFIG_DIR / "config.toml"

# Specify dict key/value types
DEFAULTS: Dict[str, str] = {
    "output_dir": str(pathlib.Path.home() / "Documents/goesvfi"),
    "cache_dir": str(pathlib.Path.home() / "Documents/goesvfi/cache"),
}

@lru_cache(maxsize=1)
# Specify dict return type
def _load_config() -> Dict[str, str]:
    data: Dict[str, str] = {} # Initialize data with type
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open("rb") as fp:
            try:
                # tomllib.load returns Dict[str, Any], we might need to validate/convert
                loaded_data = tomllib.load(fp)
                # Basic validation: ensure keys exist and values are strings
                # A more robust approach might use Pydantic or similar
                if isinstance(loaded_data.get("output_dir"), str):
                    data["output_dir"] = loaded_data["output_dir"]
                if isinstance(loaded_data.get("cache_dir"), str):
                    data["cache_dir"] = loaded_data["cache_dir"]
                # Add validation for any other expected keys
            except tomllib.TOMLDecodeError:
                pass # Keep data as empty dict

    # Merge defaults with loaded (and validated) data
    cfg: Dict[str, str] = {**DEFAULTS, **data}
    # ensure dirs exist
    pathlib.Path(cfg["output_dir"]).mkdir(parents=True, exist_ok=True)
    pathlib.Path(cfg["cache_dir"]).mkdir(parents=True, exist_ok=True)
    return cfg

# public helpers -----------------------------------------------------------

def get_output_dir() -> pathlib.Path:
    return pathlib.Path(_load_config()["output_dir"]).expanduser()

def get_cache_dir() -> pathlib.Path:
    return pathlib.Path(_load_config()["cache_dir"]).expanduser()

def find_rife_executable(model_key: str) -> pathlib.Path:
    """
    Locate the RIFE CLI executable.
    Searches in order:
    1. System PATH for 'rife-ncnn-vulkan' (or .exe)
    2. Project 'goesvfi/bin/' directory for 'rife-cli'
    3. Project 'goesvfi/models/<model_key>/' directory for 'rife-ncnn-vulkan' (or .exe)
    """
    # 1. Check PATH for standard name
    exe_name_std = "rife-ncnn-vulkan"
    if sys.platform == "win32":
        exe_name_std += ".exe"
    path_exe = shutil.which(exe_name_std)
    if path_exe:
        return pathlib.Path(path_exe)

    # Get project root (assuming this file is in goesvfi/utils/)
    project_root = pathlib.Path(__file__).parent.parent

    # 2. Check project bin directory for 'rife-cli'
    bin_dir = project_root / "bin"
    bin_fallback = bin_dir / "rife-cli"
    if bin_fallback.exists():
        return bin_fallback

    # 3. Check model-specific directory for standard name
    model_dir = project_root / "models" / model_key
    model_fallback = model_dir / exe_name_std
    if model_fallback.exists():
        return model_fallback

    # If none found, raise error
    raise FileNotFoundError(
        f"RIFE executable not found. Searched:\n"
        f"  - PATH for '{exe_name_std}'\n"
        f"  - '{bin_fallback}'\n"
        f"  - '{model_fallback}'"
    )
