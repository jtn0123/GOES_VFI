# GOES-VFI (Video Frame Interpolation for GOES Imagery)

[![Version](https://img.shields.io/github/v/tag/jtn0123/GOES_VFI?label=version)](https://github.com/jtn0123/GOES_VFI/tags)
[![CI](https://github.com/jtn0123/GOES_VFI/workflows/CI/badge.svg)](https://github.com/jtn0123/GOES_VFI/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/jtn0123/GOES_VFI/branch/main/graph/badge.svg)](https://codecov.io/gh/jtn0123/GOES_VFI)
[![Code Quality](https://img.shields.io/badge/code%20quality-A-brightgreen)](https://github.com/jtn0123/GOES_VFI/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)

A PyQt6 GUI application for applying Video Frame Interpolation (VFI) using the RIFE model to sequences of satellite images (like GOES) or any PNG sequence, creating smooth timelapse videos.

## Screenshots & Demos

### User Interface
![Main application interface](docs/assets/UI.png)

### Sanchez Processing / False Color
![Sanchez false color processing example](docs/assets/Sanchez-FalseColorUI.png)

### Cropping Feature Demo
![Cropping tool in action](docs/assets/Cropping.gif)

## Features

*   **RIFE Interpolation:** Uses RIFE v4.6 (ncnn build) via the included `rife-cli` executable to generate 1 intermediate frame per original pair.
*   **RIFE Controls:** Fine-grained control over RIFE v4.6 parameters:
    *   Model selection (if multiple model folders exist).
    *   Tiling (enable/disable, tile size).
    *   UHD Mode (for >4K frames).
    *   Test-Time Augmentation (Spatial & Temporal).
    *   Thread specification (Load:Proc:Save).
*   **FFmpeg Integration:** Extensive options for processing and encoding:
    *   Motion Interpolation (`minterpolate`) via FFmpeg.
    *   Sharpening (`unsharp`) via FFmpeg.
    *   Detailed control over `minterpolate` and `unsharp` parameters.
    *   Software (libx265) and Hardware (VideoToolbox HEVC/H.264 on macOS) encoding.
    *   Quality/Bitrate/Preset controls.
    *   Pixel format selection.
    *   Option to skip FFmpeg interpolation.
*   **GUI:** Easy-to-use interface built with PyQt6.
    *   Input folder / Output file selection (output path is not saved between sessions).
    *   Image Cropping tool.
    *   "Skip AI Interpolation" option to only use original frames (can still use FFmpeg interpolation/encoding).
    *   Frame previews (first, middle, last) with clickable zoom (shows cropped view if active).
    *   FFmpeg settings profiles ("Default", "Optimal", "Optimal 2", "Custom").
    *   Progress bar and ETA display.
    *   "Open in VLC" button.
*   **Settings Persistence:** Saves UI state, input directory, crop selection, and FFmpeg settings between sessions (see Configuration section).
*   **Debug Mode:** Run with `--debug` to keep intermediate files.

## Architecture Overview

GOES-VFI is structured using modern software architecture patterns to maximize maintainability and extensibility:

* **MVVM (Model-View-ViewModel):** The GUI is organized using the Model-View-ViewModel pattern, which separates the user interface (View), presentation logic (ViewModel), and backend/data processing (Model). This decoupling makes the codebase easier to test and extend.
* **Decoupled Pipeline Components:** The core processing pipeline is modular:
    * **FFmpeg Command Builder:** Constructs and manages FFmpeg command invocations for encoding and filtering.
    * **ImageProcessor Interface:** Abstracts image processing steps, with concrete implementations such as `ImageLoader`, `SanchezProcessor`, and `ImageCropper`.
    * Each pipeline stage is independently testable and replaceable, supporting future enhancements.

## Requirements

* **Python:** 3.13+ required.
* **Packages:** See `requirements.txt` (mainly `PyQt6`, `numpy`, `Pillow`). Install with `pip install -r requirements.txt`.
* **FFmpeg:** Required for video processing/encoding. Must be installed and available in your system's PATH.
* **RIFE v4.6 ncnn:** The `rife-cli` executable and associated model files (`flownet.bin`, `flownet.param`) are expected.
    * The application looks for `rife-cli` in `goesvfi/bin/rife-cli` relative to the package installation.
    * The model files (`flownet.bin`, `flownet.param`) need to be placed within a model directory (e.g., `goesvfi/models/rife-v4.6/`). The GUI auto-detects folders named `rife-*` in `goesvfi/models/`.
    * *Ensure you have obtained the RIFE v4.6 ncnn executable and model files and placed them correctly.*
* **Development Tools:** For contributors, please install the following tools in your virtual environment:
    * [`black`](https://black.readthedocs.io/en/stable/) (code formatter)
    * [`flake8`](https://flake8.pycqa.org/en/latest/) (linter)
    * Install with: `pip install black flake8`

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/jtn0123/GOES_VFI.git
    cd GOES_VFI
    ```
2.  **Set up a virtual environment (recommended):**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    # For development (optional, but recommended):
    pip install black flake8
    ```
4.  **Place RIFE executable:** Put your downloaded/built `rife-cli` into the `goesvfi/bin/` directory.
5.  **Place RIFE models:** Create `goesvfi/models/rife-v4.6/` (or similar `rife-*` name) and place `flownet.bin` and `flownet.param` inside it.

## Usage

Ensure your virtual environment is activated.

Run the GUI application:

```bash
python -m goesvfi.gui [--debug]
```

**GUI Steps:**

1.  **Input folder:** Select the directory containing your sequence of PNG images.
2.  **Output MP4:** Select the desired base output file path (the application will suggest a default; a timestamp will be added automatically to the actual output file).
3.  **Crop (Optional):** Click "Crop..." to define a region on the first frame.
4.  **Adjust Settings:**
    *   Set Target FPS.
    *   Configure RIFE v4.6 settings (Tiling, UHD, TTA, etc.) or check "Skip AI Interpolation".
    *   Select Encoder.
    *   Go to the "FFmpeg Settings" tab to choose a profile or customize FFmpeg interpolation and sharpening parameters.
5.  **Start:** Click the "Start" button.
6.  **Monitor:** Watch the progress bar and status messages.
7.  **Open:** Once finished, click "Open in VLC" (if VLC is installed and in your PATH) or open the timestamped MP4 file manually.

## Configuration

GOES-VFI uses a standardized configuration mechanism for core settings:

* **Primary Configuration File:**
  The main configuration is stored in a TOML file located at `~/.config/goesvfi/config.toml` (on Linux/macOS) or the platform equivalent (e.g., `%APPDATA%\goesvfi\config.toml` on Windows).
* **Configuration Management:**
  The module `goesvfi/utils/config.py` is responsible for loading this TOML file and providing default values for all core settings, such as:
    * Cache directory
    * Logging level
    * Paths to RIFE/Sanchez executables and models
    * Other pipeline and application options
* **UI State Persistence:**
  Some user interface state (such as window geometry, last-used directories, and certain UI preferences) may still be saved using `QSettings` (platform-specific location).
  **Note:** Only UI state is managed by `QSettings`; all core configuration is handled by the TOML file.
* **Defaults:**
  If the TOML file does not exist, sensible defaults are used and a new file is created on first run.

## License

This project does not currently have a license. Consider adding one (e.g., MIT License).

## Project Structure

The GOES-VFI project is organized with a clean directory structure to make the codebase more maintainable and easier to navigate:

### Core Package
- `goesvfi/`: Main package containing the application code
  - `bin/`: Binary executables (e.g., `rife-cli`)
  - `gui_tabs/`: PyQt6 GUI tab implementations
  - `integrity_check/`: GOES data integrity checking module
  - `models/`: Model files for RIFE and other ML components
  - `pipeline/`: Processing pipeline components
  - `utils/`: Utility modules (logging, configuration, etc.)
  - `view_models/`: ViewModels for MVVM architecture

### Test Organization
- `tests/`: All test files are organized by test type
  - `unit/`: Unit tests for individual components
  - `integration/`: Integration tests for component interactions
  - `gui/`: Tests for the PyQt6 user interface
    - `imagery/`: Tests for imagery-related GUI components
    - `tabs/`: Tests for various tab components
  - `utils/`: Test utilities and helpers
- `legacy_tests/`: Contains potentially redundant or outdated tests for evaluation

### Example Scripts
- `examples/`: Example scripts demonstrating various features
  - `download/`: Examples for downloading GOES satellite data
  - `s3_access/`: Examples for interacting with NOAA S3 buckets
  - `imagery/`: Examples of processing and rendering satellite imagery
  - `processing/`: Examples of various processing techniques
  - `visualization/`: Examples of data visualization techniques
  - `debugging/`: Examples for debugging specific functionality
  - `utilities/`: Utility scripts for code maintenance

### Documentation
- `docs/`: Documentation files
  - `assets/`: Screenshots, diagrams, and other visual assets
  - `reports/`: Detailed reports on various components
  - `testing/`: Documentation related to testing

### Development Tools
- `scripts/`: Development and utility scripts
- `run_all_tests.py`, `run_working_tests.py`, etc.: Test runner scripts
- `cleanup.py`: Script to clean up temporary and cache files

## Examples and Testing

### Examples

The repository includes various example scripts showcasing different aspects of the GOES-VFI project. These examples are located in the `examples/` directory and are organized by functionality:

* **Download Examples:** Scripts for downloading GOES satellite imagery from NOAA S3 buckets
* **S3 Access Examples:** Examples demonstrating how to interact with NOAA S3 buckets directly
* **Imagery Examples:** Examples of processing and rendering satellite imagery
* **Processing Examples:** Demonstrations of various processing techniques
* **Visualization Examples:** Examples of data visualization techniques
* **Debugging Examples:** Scripts for debugging specific functionality
* **Utilities:** Utility scripts for code maintenance

Each example can be run directly from its directory. The examples are designed to be self-contained and include appropriate documentation.

```bash
python -m examples.download.download_band13
```

### Testing

The project uses pytest for unit testing, integration testing, and GUI testing. Tests are organized in the `tests/` directory with subdirectories for different types of tests:

* **Unit Tests:** Tests for individual components and modules
* **Integration Tests:** Tests for interactions between components
* **GUI Tests:** Tests for the PyQt6 user interface
  * **Imagery Tests:** Tests for imagery-related GUI components
  * **Tab Tests:** Tests for various tab components

To run the tests, use one of the test runner scripts:

```bash
# Run all working tests
./run_working_tests.py

# Run fixed GUI tests
./run_fixed_gui_tests.py

# Run all tests
./run_all_tests.py
```

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.

**Guidelines for Contributors:**

* **Architecture:**
  The project uses the MVVM (Model-View-ViewModel) pattern for the GUI and a modular, decoupled pipeline for processing. Please follow these patterns when adding new features or refactoring code.
* **Project Structure:**
  - Place new code in the appropriate module within the `goesvfi` package
  - Follow the established directory structure for tests and examples
  - When developing a new feature, consider creating it first as an example script in the appropriate examples directory
* **Utilities:**
  Use the centralized logging (`goesvfi.utils.log`) and configuration (`goesvfi.utils.config`) utilities for all logging and configuration access.
* **Examples and Tests:**
  - When adding new functionality, create appropriate examples in the corresponding `examples/` subdirectory
  - Add unit tests to `tests/unit/`, integration tests to `tests/integration/`, and GUI tests to `tests/gui/`
  - Follow existing patterns for both examples and tests
  - Use the test utilities in `tests/utils/` for common testing functionality
* **Code Style:**
  Before submitting changes, run the following commands to ensure code quality and consistency:
    ```bash
    black .
    flake8 .
    mypy .  # For type checking
    ```
* **Type Safety:**
  - Include type annotations for all function parameters and return values
  - Use mypy to check type correctness with `python -m run_mypy_checks`
* **Pull Requests:**
  Clearly describe your changes and reference any related issues or discussions
* **Data Files:**
  - Do not commit large data files (.nc files, large .png files, etc.)
  - Use the cleanup script (`cleanup.py`) to clean up temporary data files before committing
