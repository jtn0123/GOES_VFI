# GOES-VFI (Video Frame Interpolation for GOES Imagery)

[![Version](https://img.shields.io/github/v/tag/jtn0123/GOES_VFI?label=version)](https://github.com/jtn0123/GOES_VFI/tags)

A PyQt6 GUI application for applying Video Frame Interpolation (VFI) using the RIFE (Real-Time Intermediate Flow Estimation) model to sequences of GOES satellite images, creating smooth timelapse videos.

## Features

*   **RIFE Interpolation:** Uses the RIFE v4.6 model (via `rife-cli`) to generate intermediate frames.
*   **Frame Counts:** Supports generating 1 or 3 intermediate frames per original pair.
*   **Tiling:** Optional tiling for large frames (>2k pixels) to improve performance and reduce memory usage.
*   **GUI:** Easy-to-use interface built with PyQt6.
    *   Input/Output selection.
    *   Controls for FPS, intermediate frame count, tiling, max workers.
    *   Encoder selection (including hardware acceleration via VideoToolbox on macOS, and no-reencode option).
    *   Optional FFmpeg motion interpolation (`minterpolate`) for further frame doubling.
    *   Preview thumbnails (first, middle, last) with clickable zoom.
    *   Progress bar and ETA display during processing.
    *   "Open in VLC" button for quick viewing.
    *   Timestamped output filenames to prevent overwrites.
*   **Caching:** Caches generated intermediate frames to speed up subsequent runs.
*   **Parallel Processing:** Uses multiple processes to speed up frame interpolation.

## Requirements

*   **Python:** 3.9+ recommended.
*   **Packages:** See `requirements.txt` (mainly `PyQt6`, `numpy`, `Pillow`). Install with `pip install -r requirements.txt`.
*   **FFmpeg:** Required for video encoding. Must be installed and available in your system's PATH.
*   **RIFE CLI:** The RIFE command-line executable (`rife-cli`).
    *   Download or build the RIFE CLI suitable for your OS.
    *   **Crucially:** Place the executable file named `rife-cli` inside the `goesvfi/bin/` directory within this project before running.

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
    ```
4.  **Place RIFE CLI:** Download/build `rife-cli` and place it in the `goesvfi/bin/` directory.

## Usage

Ensure your virtual environment is activated.

Run the GUI application:

```bash
python -m goesvfi.gui
```

**GUI Steps:**

1.  **Input folder:** Select the directory containing your sequence of GOES PNG images.
2.  **Output MP4:** Select the desired output file path (a timestamp will be added automatically).
3.  **Adjust Settings:** Configure FPS, intermediate frames (1 or 3), tiling, max workers, encoder, and FFmpeg interpolation as needed.
4.  **Start:** Click the "Start" button.
5.  **Monitor:** Watch the progress bar and status messages.
6.  **Open:** Once finished, click "Open in VLC" (if VLC is installed and in your PATH) or open the timestamped MP4 file manually.

## Configuration

*   **RIFE Executable:** Must be placed as `goesvfi/bin/rife-cli`.
*   **Cache/Output Directories:** Default locations are managed by `goesvfi/utils/config.py` (using platform-specific cache/data directories), but the output path can be selected freely in the GUI.

## License

This project does not currently have a license. Consider adding one (e.g., MIT License).

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.
