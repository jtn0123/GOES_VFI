# TODO: path + TOML config
from __future__ import annotations
from typing import Dict
"""goesvfi.utils.config – user paths and TOML config loader"""

import os
import pathlib
import tomllib
from functools import lru_cache

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
