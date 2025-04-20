# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - YYYY-MM-DD

### Added
- Support for generating 3 intermediate frames using recursive 3-step interpolation (`interpolate_three`).
- Tiled interpolation implementation for the 3-intermediate-frame case, improving performance and memory usage for large frames.
- GUI control (SpinBox) to select the number of intermediate frames (1 or 3).
- GUI control (CheckBox) to enable/disable tiled interpolation.
- GUI control (SpinBox) to set the maximum number of parallel worker processes, with a sensible default based on CPU cores.
- GUI button ("Open in VLC") to quickly open the generated video file.

### Changed
- Core processing logic (`run_vfi`) updated to handle selection between 1 and 3 intermediate frames.
- Caching logic (`pipeline/cache.py`) updated to store and retrieve varying numbers of intermediate frames correctly based on parameters.
- Parallel processing task setup (`run_vfi`) updated to pass tiling and worker settings.

### Fixed
- Resolved Mypy type checking errors related to new function arguments and missing return type hints (`gui.py`, `run_vfi.py`).
- Prevented variable shadowing in `_process_pair` function (`run_vfi.py`).

## [0.1.0] - YYYY-MM-DD

- Initial release. 