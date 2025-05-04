# TODO: path + TOML config
from __future__ import annotations
from typing import Dict, Any, List, cast, TypedDict # Add Any, List, cast, and TypedDict

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
# Define default values for configuration settings
# Use Dict[str, Any] as values can be different types
DEFAULTS: Dict[str, Any] = {
    "output_dir": str(pathlib.Path.home() / "Documents/goesvfi"),
    "cache_dir": str(pathlib.Path.home() / "Documents/goesvfi/cache"),
    "pipeline": {
        "default_tile_size": 2048,
        "supported_extensions": [".png", ".jpg", ".jpeg"],
    },
    "sanchez": {
        "bin_dir": str(pathlib.Path(__file__).parent.parent / "sanchez" / "bin"),
    },
    "logging": {
        "level": "INFO",
    },
}

# Define TypedDict for profile structure first
class FfmpegProfile(TypedDict):
    use_ffmpeg_interp: bool
    mi_mode: str
    mc_mode: str
    me_mode: str
    vsbmc: bool
    scd: str
    me_algo: str
    search_param: int
    scd_threshold: float
    mb_size: str
    apply_unsharp: bool
    unsharp_lx: int
    unsharp_ly: int
    unsharp_la: float
    unsharp_cx: int
    unsharp_cy: int
    unsharp_ca: float
    preset_text: str
    crf: int  # Added crf
    bitrate: int
    bufsize: int
    pix_fmt: str
    filter_preset: str


# Optimal FFmpeg interpolation settings profile
# (Values for quality settings are based on current defaults, adjust if needed)
OPTIMAL_FFMPEG_PROFILE: FfmpegProfile = {
    # Interpolation
    "use_ffmpeg_interp": True,
    "mi_mode": "mci",
    "mc_mode": "aobmc",
    "me_mode": "bidir",
    "vsbmc": True,  # Boolean representation for checkbox
    "scd": "none",
    "me_algo": "(default)",  # Assuming default algo for optimal
    "search_param": 96,  # Assuming default search param
    "scd_threshold": 10.0,  # Default threshold (though scd is none)
    "mb_size": "(default)",  # Assuming default mb_size
    # Sharpening
    "apply_unsharp": False,  # <-- Key for groupbox check state
    "unsharp_lx": 7,
    "unsharp_ly": 7,
    "unsharp_la": 1.0,
    "unsharp_cx": 5,
    "unsharp_cy": 5,
    "unsharp_ca": 0.0,
    # Quality
    "preset_text": "Very High (CRF 16)",
    "crf": 16,  # Added CRF value
    "bitrate": 15000,
    "bufsize": 22500,  # Auto-calculated from bitrate
    "pix_fmt": "yuv444p",
    # Filter Preset
    "filter_preset": "slow",
}

# Optimal profile 2 - Based on PowerShell script defaults
OPTIMAL_FFMPEG_PROFILE_2: FfmpegProfile = {
    # Interpolation
    "use_ffmpeg_interp": True,
    "mi_mode": "mci",
    "mc_mode": "aobmc",
    "me_mode": "bidir",
    "vsbmc": True,
    "scd": "none",
    "me_algo": "epzs",  # Explicitly set based on PS default
    "search_param": 32,  # Set based on likely PS default
    "scd_threshold": 10.0,  # Value doesn't matter when scd="none"
    "mb_size": "(default)",  # Keep default
    # Sharpening (Disabled, mimicking lack of unsharp/presence of tmix in PS)
    "apply_unsharp": False,
    "unsharp_lx": 7,  # Values kept for structure, but unused
    "unsharp_ly": 7,
    "unsharp_la": 1.0,
    "unsharp_cx": 5,
    "unsharp_cy": 5,
    "unsharp_ca": 0.0,
    # Quality (Adjusted based on PS comparison)
    "preset_text": "Medium (CRF 20)",  # Changed preset level example
    "crf": 20,  # Added CRF value
    "bitrate": 10000,  # Lowered bitrate example
    "bufsize": 15000,  # Lowered bufsize (1.5*bitrate)
    "pix_fmt": "yuv444p",  # Keep high quality format
    # Filter Preset (Intermediate step)
    "filter_preset": "medium",  # Match final preset level choice
}

# Default profile based on initial GUI values
DEFAULT_FFMPEG_PROFILE: FfmpegProfile = {
    # Interpolation
    "use_ffmpeg_interp": True,
    "mi_mode": "mci",
    "mc_mode": "obmc",
    "me_mode": "bidir",
    "vsbmc": False,
    "scd": "fdiff",
    "me_algo": "(default)",
    "search_param": 96,
    "scd_threshold": 10.0,
    "mb_size": "(default)",
    # Sharpening
    "apply_unsharp": True,  # <-- Key for groupbox check state
    "unsharp_lx": 7,
    "unsharp_ly": 7,
    "unsharp_la": 1.0,
    "unsharp_cx": 5,
    "unsharp_cy": 5,
    "unsharp_ca": 0.0,
    # Quality
    "preset_text": "Very High (CRF 16)",
    "crf": 16,  # Added CRF value
    "bitrate": 15000,
    "bufsize": 22500,
    "pix_fmt": "yuv444p",
    # Filter Preset
    "filter_preset": "slow",
}

# Store profiles in a dictionary for easy access with type hint
FFMPEG_PROFILES: Dict[str, FfmpegProfile] = {
    "Default": DEFAULT_FFMPEG_PROFILE,
    "Optimal": OPTIMAL_FFMPEG_PROFILE,
    "Optimal 2": OPTIMAL_FFMPEG_PROFILE_2,
    # "Custom" is handled implicitly when settings change
}

@lru_cache(maxsize=1)
# Specify dict return type
def _load_config() -> Dict[str, Any]:
    # Initialize data with defaults
    data: Dict[str, Any] = DEFAULTS.copy()
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open("rb") as fp:
            try:
                loaded_data = tomllib.load(fp)
                # Merge loaded data with defaults. Loaded data overrides defaults.
                # This is a basic merge; for nested structures, a recursive merge would be needed.
                # For now, we assume top-level keys in TOML override corresponding keys in DEFAULTS.
                # A more robust approach might use Pydantic or similar for structured config.
                for key, value in loaded_data.items():
                    if (
                        key in data
                        and isinstance(data[key], dict)
                        and isinstance(value, dict)
                    ):
                        # Simple recursive merge for nested dictionaries (up to one level deep for now)
                        data[key].update(value)
                    else:
                        # Overwrite for non-dict values or if key not in defaults (new keys)
                        data[key] = value

            except tomllib.TOMLDecodeError:
                # If TOML is invalid, just use defaults
                pass

    # ensure dirs exist for known path configurations
    # Use .get() with a default to avoid KeyError if config is missing
    output_dir_str = data.get("output_dir")
    if isinstance(output_dir_str, str):
        pathlib.Path(output_dir_str).expanduser().mkdir(parents=True, exist_ok=True)

    cache_dir_str = data.get("cache_dir")
    if isinstance(cache_dir_str, str):
        pathlib.Path(cache_dir_str).expanduser().mkdir(parents=True, exist_ok=True)

    # Ensure sanchez bin dir exists if specified
    sanchez_config = data.get("sanchez", {})
    sanchez_bin_dir_str = sanchez_config.get("bin_dir")
    if isinstance(sanchez_bin_dir_str, str):
        pathlib.Path(sanchez_bin_dir_str).expanduser().mkdir(
            parents=True, exist_ok=True
        )

    return data


# public helpers -----------------------------------------------------------


def get_output_dir() -> pathlib.Path:
    # Use .get() with a default to handle potential missing key after loading
    output_dir_str = _load_config().get("output_dir", DEFAULTS["output_dir"])
    # Ensure it's a string before converting to Path
    if not isinstance(output_dir_str, str):
        output_dir_str = DEFAULTS["output_dir"]  # Fallback to default if type is wrong
    return pathlib.Path(output_dir_str).expanduser()


def get_cache_dir() -> pathlib.Path:
    # Use .get() with a default to handle potential missing key after loading
    cache_dir_str = _load_config().get("cache_dir", DEFAULTS["cache_dir"])
    # Ensure it's a string before converting to Path
    if not isinstance(cache_dir_str, str):
        cache_dir_str = DEFAULTS["cache_dir"]  # Fallback to default if type is wrong
    return pathlib.Path(cache_dir_str).expanduser()


def get_default_tile_size() -> int:
    # Access nested config using .get() for safety
    pipeline_config = _load_config().get("pipeline", {})
    tile_size = pipeline_config.get(
        "default_tile_size", DEFAULTS["pipeline"]["default_tile_size"]
    )
    # Ensure it's an int
    if not isinstance(tile_size, int):
        tile_size = DEFAULTS["pipeline"]["default_tile_size"]  # Fallback to default
    return cast(int, tile_size)


def get_sanchez_bin_dir() -> pathlib.Path:
    # Access nested config using .get() for safety
    sanchez_config = _load_config().get("sanchez", {})
    bin_dir_str = sanchez_config.get("bin_dir", DEFAULTS["sanchez"]["bin_dir"])
    # Ensure it's a string before converting to Path
    if not isinstance(bin_dir_str, str):
        bin_dir_str = DEFAULTS["sanchez"]["bin_dir"]  # Fallback to default
    return pathlib.Path(bin_dir_str).expanduser()


def get_logging_level() -> str:
    # Access nested config using .get() for safety
    logging_config = _load_config().get("logging", {})
    level = logging_config.get("level", DEFAULTS["logging"]["level"])
    # Ensure it's a string
    if not isinstance(level, str):
        level = DEFAULTS["logging"]["level"]  # Fallback to default
    return cast(str, level)


def get_supported_extensions() -> List[str]:
    # Access nested config using .get() for safety
    pipeline_config = _load_config().get("pipeline", {})
    extensions = pipeline_config.get(
        "supported_extensions", DEFAULTS["pipeline"]["supported_extensions"]
    )
    # Ensure it's a list of strings
    if not isinstance(extensions, list) or not all(
        isinstance(ext, str) for ext in extensions
    ):
        extensions = DEFAULTS["pipeline"]["supported_extensions"]  # Fallback to default
    return cast(List[str], extensions)


def get_project_root() -> pathlib.Path:
    """
    Returns the root directory of the project.
    Assumes this config.py file is located within a subdirectory of the project root
    (e.g., goesvfi/utils/).
    """
    # Navigate up two levels from this file's directory (utils -> goesvfi -> project_root)
    return pathlib.Path(__file__).resolve().parent.parent
def find_rife_executable(model_key: str) -> pathlib.Path:
    """
    Locate the RIFE CLI executable.
    Searches in order:
    1. System PATH for 'rife-ncnn-vulkan' (or .exe)
    2. Project 'goesvfi/bin/' directory for 'rife-cli' (or .exe)
    3. Project 'goesvfi/models/<model_key>/' directory for 'rife-cli' (or .exe)
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

    # 2. Check project 'bin' directory for 'rife-cli'
    exe_name_cli = "rife-cli"
    if sys.platform == "win32":
        exe_name_cli += ".exe"
    project_bin_dir = project_root / "bin"
    project_bin_exe = project_bin_dir / exe_name_cli
    if project_bin_exe.exists():
        return project_bin_exe

    # 3. Check model-specific directory for 'rife-cli'
    model_dir = project_root / "models" / model_key
    model_specific_exe = model_dir / exe_name_cli
    if model_specific_exe.exists():
        return model_specific_exe

    # If none found, raise error
    raise FileNotFoundError(
        f"RIFE executable not found. Searched:\n"
        f"  - PATH for '{exe_name_std}'\n"
        f"  - '{project_bin_exe}'\n"
        f"  - '{model_specific_exe}'"
    )


def get_available_rife_models() -> list[str]:
    """
    Scans the 'goesvfi/models/' directory for available RIFE models.

    Returns:
        A sorted list of model directory names found.
    """
    project_root = pathlib.Path(__file__).parent.parent
    models_dir = project_root / "models"
    available_models = []
    if models_dir.is_dir():
        for item in models_dir.iterdir():
            # Check if it's a directory and potentially contains model files
            # A simple check is just to see if it's a directory.
            # More robust checks could look for specific files like flownet.param
            if item.is_dir():
                available_models.append(item.name)
    return sorted(available_models)
