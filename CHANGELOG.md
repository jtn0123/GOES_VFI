# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2025-04-28

### Added
- **GUI:** Added logging to the `_on_progress` method for better debugging and tracking of progress updates (`gui.py`).
- **Testing:** Added comprehensive unit tests for the `FileSorter` class (`tests/unit/test_file_sorter.py`).
- **Processing:** Added Sanchez (false color) support for Windows and OSX.
- **Utilities:** Preliminary addition of File Sorter and Date Sorter codebases (`goesvfi/file_sorter/`, `goesvfi/date_sorter/`).

### Changed
- **GUI:** Assigned the RIFE options group to `self` for improved access within the class (`gui.py`). Improved preview options to work with Sanchez enabled. Updated tests to ensure proper UI updates and status messages during progress tracking (`tests/gui/test_main_window.py`, `tests/integration/test_pipeline.py`).
- **Dependencies:** Removed obsolete RIFE v4 and v4.6 binary and parameter files from the repository (`goesvfi/bin/rife-v4.6/flownet.bin`, `goesvfi/bin/rife-v4.6/flownet.param`, `goesvfi/bin/rife-v4/flownet.bin`, `goesvfi/bin/rife-v4/flownet.param`).
- **Documentation:** Updated README.md to reflect enhancements in the VFI application, including clarified support for any PNG sequence, expanded features, updated installation and usage instructions, and notes on settings persistence (`README.md`). Updated TODO list to include investigation of integration test failures (`docs/TODO.md`). Updated improvement plan to include details on FileSorter and DateSorter integration (`docs/improvement_plan.md`).

### Fixed
- **GUI:** Removed duplicate `_on_profile_selected` method (`gui.py`).
## [0.6.0] - 2025-04-24

### Added
- **GUI & Settings:**
    - Consolidated FFmpeg filter and quality settings into a single "FFmpeg Settings" tab (`gui.py`).
    - Added FFmpeg settings profiles ("Default", "Optimal", "Optimal 2", "Custom") selector (`gui.py`).
    - Added group boxes for FFmpeg "Motion Interpolation" and "Sharpening" settings, which can be collapsed (`gui.py`).
    - Added specific RIFE v4.6 ncnn controls: Model selection (auto-populated), UHD Mode, Thread Spec, Spatial TTA, Temporal TTA (`gui.py`).
    - Implemented dynamic window resizing based on current tab content (`gui.py`).
    - Added validation for RIFE thread spec input format (`gui.py`).
    - Added helper methods to check if current UI settings match a profile (`gui.py`).
- **Processing:**
    - Added support for passing new RIFE v4.6 arguments (UHD, TTA, thread spec, model dir) to the `rife-cli` executable (`run_vfi.py`).
    - Added validation of RIFE output file existence and size (`run_vfi.py`).
    - Redirected ffmpeg `stderr` to `stdout` and captured the combined stream for better error logging (`run_vfi.py`, `encode.py`).
    - Passed `stdin=subprocess.DEVNULL` to FFmpeg encode command to prevent potential hangs (`encode.py`).

### Changed
- **GUI & Settings:**
    - Output file path is no longer saved in settings; a default is derived on load, preventing timestamp accumulation (`gui.py`).
    - RIFE intermediate frame count and tiling controls moved into the RIFE v4.6 settings group (`gui.py`).
    - FFmpeg filter tab split/merged into the consolidated "FFmpeg Settings" tab (`gui.py`).
    - Improved clarity in Models tab description (`gui.py`).
    - Changed "FFmpeg Quality" tab name to "Encoding Quality (Final Output)" group box (`gui.py`).
- **Processing:**
    - Removed old fallback logic for "Safe HQ" FFmpeg filter in `VfiWorker` (`gui.py`).
    - FFmpeg loglevel increased to `verbose` for raw video creation (`run_vfi.py`).
    - Refined ETA calculation and yield frequency (`run_vfi.py`).
    - Improved `_safe_write` helper to capture more context on `BrokenPipeError` (`run_vfi.py`).
    - Updated RIFE command construction to pass model directory instead of model name (`run_vfi.py`).

### Fixed
- Resolved Mypy `attr-defined` errors by adding missing/renamed methods (`_toggle_tile_size_enabled`, `_toggle_minterpolate_content`, `_toggle_unsharp_content`, `_on_tab_changed`, `_check_settings_match_profile`, etc.) in `gui.py`.
- Corrected `FileNotFoundError` in `run_vfi.py` caused by an unnecessary sanity check for `flownet.pkl` when using the RIFE executable.
- Prevented "File name too long" errors by correcting output path saving/loading logic in `gui.py`.
- Reduced log spam related to window resizing by removing automatic resize triggers from FFmpeg group box toggle methods in `gui.py`.
- Fixed incorrect `stderr` handling in `_run_ffmpeg_command` which could miss errors (`encode.py`).
- Corrected `closeEvent` superclass call (`gui.py`).
- Fixed various UI update/state issues after loading settings, particularly for tile size checkbox and RIFE group enabled state (`gui.py`).
- Fixed potential issues with `rife_exe_path` discovery by using `pkgres.files` correctly (`gui.py`).
- Fixed `BrokenPipeError` handling in `_safe_write` to provide more useful ffmpeg log context (`run_vfi.py`).
- Corrected escaping of newline characters (`\\n`) in error/info messages (`gui.py`).

## [0.5.0] - 2025-04-21

### Added
- **GUI & Settings:**
    - Added "Interpolation Filters" tab with detailed controls for FFmpeg `minterpolate` filter (`mi_mode`, `mc_mode`, `me_mode`, `me_algo`, `search_param`, `scd_mode`, `scd_threshold`, `mb_size`, `vsbmc`) and `unsharp` filter (`lx`, `ly`, `la`, `cx`, `cy`, `ca`).
    - Added "FFmpeg Quality" tab for controlling software preset (CRF), hardware bitrate/buffer, and pixel format.
    - Added "Skip AI interpolation" checkbox to only use original frames (optionally with FFmpeg interpolation).
    - Added interactive image cropping functionality with a dedicated dialog (`CropDialog`) and "Clear Crop" button.
    - Implemented settings persistence using `QSettings` to save and load UI state, including window geometry and crop selection.
    - Added `--debug` command-line flag to prevent cleanup of intermediate files.
    - Added `.gitignore` file to exclude common Python artifacts, cache files, editor files, and FFmpeg/x265 logs.
    - Added `cleanup.py` script to remove cache directories and log files.
- **Processing:**
    - `VfiWorker` now accepts and utilizes all new filter and quality settings from the GUI.
    - Implemented fallback logic in `VfiWorker`: if the custom "Safe HQ" FFmpeg filter fails, it attempts a simpler `minterpolate` configuration.
    - Intermediate files generated during FFmpeg filtering are now cleaned up unless debug mode is active.

### Changed
- Default software encoder preset changed to "Very High (CRF 16)".
- Default hardware encoder bitrate increased to 15000 kbps.
- Default output pixel format changed to `yuv444p`.
- Improved logging during the VFI process, including dumping all settings used.
- Refined preview update logic, including applying the current crop to thumbnails.

### Fixed
- Corrected indentation issue in `VfiWorker`'s cleanup logic.

## [0.4.0] - 2025-04-20

### Fixed
- Corrected handling of crop rectangle coordinates passed to the image processing pipeline (`run_vfi`). The input tuple format `(x, y, width, height)` is now correctly converted to the `(left, upper, right, lower)` format required by the Pillow library, resolving `ValueError: Coordinate 'right' is less than 'left'` errors when cropping was enabled.

## [0.3.0] - 2025-04-19

### Added
- GUI:
    - Added "Models" tab (placeholder). (`goesvfi/gui.py`)
    - Added preview thumbnails for first/middle/last frames in input folder. (`goesvfi/gui.py`)
    - Made preview thumbnails clickable to show a larger zoom dialog. (`goesvfi/gui.py`)
    - Added status bar for messages and ETA display. (`goesvfi/gui.py`)
    - Added encoder selection dropdown, including "None (copy original)". (`goesvfi/gui.py`)
    - Added checkbox to enable FFmpeg motion interpolation (`minterpolate`) during encoding. (`goesvfi/gui.py`)
- Processing:
    - Added ETA calculation during frame processing. (`goesvfi/run_vfi.py`)
    - Refactored encoding to use a lossless intermediate file (`_raw.mkv`) and a separate final encoding step. (`goesvfi/pipeline/raw_encoder.py`, `goesvfi/pipeline/encode.py`, `goesvfi/run_vfi.py`, `goesvfi/gui.py`)
    - Added support for FFmpeg `minterpolate` filter in the final encoding step. (`goesvfi/pipeline/encode.py`, `goesvfi/gui.py`)

### Changed
- GUI:
    - Output filename now includes a timestamp by default to prevent overwrites. (`goesvfi/gui.py`)
- Processing:
    - `run_vfi` now yields progress updates and the path to the intermediate raw file. (`goesvfi/run_vfi.py`)
    - `VfiWorker` handles the two-step process (raw generation + final encoding/copy). (`goesvfi/gui.py`)

### Fixed
- Fixed Mypy strict type checking errors. (`goesvfi/gui.py`, `goesvfi/run_vfi.py`)
- Fixed issue where "Open in VLC" button didn't work due to missing output path storage. (`goesvfi/gui.py`)
- Fixed compounding timestamp issue when re-running processing. (`goesvfi/gui.py`)
- Fixed FFmpeg error when creating raw intermediate file by switching from MP4+ffv1 to MKV+ffv1. (`goesvfi/run_vfi.py`, `goesvfi/pipeline/raw_encoder.py`)
- Fixed FFmpeg stream copy issue when "None" encoder was selected with MKV input. (`goesvfi/pipeline/encode.py`)

## [0.2.0] - 2025-04-19

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

## [0.1.0] - 2024-04-18

- Initial release. 