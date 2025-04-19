# TODO: path + TOML config
from __future__ import annotations
"""goesvfi.utils.config – user paths and TOML config loader"""

import os
import pathlib
import tomllib
from functools import lru_cache

CONFIG_DIR = pathlib.Path.home() / ".config/goesvfi"
CONFIG_FILE = CONFIG_DIR / "config.toml"

DEFAULTS = {
    "output_dir": str(pathlib.Path.home() / "Documents/goesvfi"),
    "cache_dir": str(pathlib.Path.home() / "Documents/goesvfi/cache"),
}

@lru_cache(maxsize=1)
def _load_config() -> dict:
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open("rb") as fp:
            try:
                data = tomllib.load(fp)
            except tomllib.TOMLDecodeError:
                data = {}
    else:
        data = {}
    cfg = {**DEFAULTS, **data}
    # ensure dirs exist
    pathlib.Path(cfg["output_dir"]).mkdir(parents=True, exist_ok=True)
    pathlib.Path(cfg["cache_dir"]).mkdir(parents=True, exist_ok=True)
    return cfg

# public helpers -----------------------------------------------------------

def get_output_dir() -> pathlib.Path:
    return pathlib.Path(_load_config()["output_dir"]).expanduser()

def get_cache_dir() -> pathlib.Path:
    return pathlib.Path(_load_config()["cache_dir"]).expanduser()
