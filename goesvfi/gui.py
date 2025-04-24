# TODO: PyQt6 main window implementation
from __future__ import annotations
"""
GOES‑VFI PyQt6 GUI – v0.1
Run with:  python -m goesvfi.gui
"""

import sys
import pathlib
import argparse # <-- Import argparse
import importlib.resources as pkgres
import re # <-- Import re for regex
from typing import Optional, Any, cast, Union, Tuple, Iterator, Dict, List # Added Dict, List
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QSize, QPoint, QRect, QSettings, QByteArray, QTimer, QUrl # Added QTimer, QUrl
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QProgressBar, QSpinBox, QVBoxLayout, QWidget,
    QMessageBox, QComboBox, QCheckBox, QTabWidget, QTableWidget, QTableWidgetItem, QStatusBar,
    QDialog, QDialogButtonBox, QRubberBand, QGridLayout, QDoubleSpinBox,
    QGroupBox, QSizePolicy, QSplitter, QScrollArea # Added GroupBox, SizePolicy, Splitter, ScrollArea
)
from PyQt6.QtGui import QPixmap, QMouseEvent, QCloseEvent, QImage, QPainter, QPen, QColor, QIcon, QDesktopServices # Added Image, Painter, Pen, Color, Icon, DesktopServices
import json # Import needed for pretty printing the dict

from goesvfi.utils import config, log

LOGGER = log.get_logger(__name__)

# Optimal FFmpeg interpolation settings profile
# (Values for quality settings are based on current defaults, adjust if needed)
OPTIMAL_FFMPEG_PROFILE = {
    # Interpolation
    "use_ffmpeg_interp": True,
    "mi_mode": "mci",
    "mc_mode": "aobmc",
    "me_mode": "bidir",
    "vsbmc": True, # Boolean representation for checkbox
    "scd": "none",
    "me_algo": "(default)", # Assuming default algo for optimal
    "search_param": 96,      # Assuming default search param
    "scd_threshold": 10.0,   # Default threshold (though scd is none)
    "mb_size": "(default)", # Assuming default mb_size
    # Sharpening
    "apply_unsharp": False, # <-- Key for groupbox check state
    "unsharp_lx": 7,
    "unsharp_ly": 7,
    "unsharp_la": 1.0,
    "unsharp_cx": 5,
    "unsharp_cy": 5,
    "unsharp_ca": 0.0,
    # Quality
    "preset_text": "Very High (CRF 16)",
    "bitrate": 15000,
    "bufsize": 22500, # Auto-calculated from bitrate
    "pix_fmt": "yuv444p",
    # Filter Preset
    "filter_preset": "slow",
}

# Optimal profile 2 - Based on PowerShell script defaults
OPTIMAL_FFMPEG_PROFILE_2 = {
    # Interpolation
    "use_ffmpeg_interp": True,
    "mi_mode": "mci",
    "mc_mode": "aobmc",
    "me_mode": "bidir",
    "vsbmc": True,
    "scd": "none",
    "me_algo": "epzs",          # Explicitly set based on PS default
    "search_param": 32,         # Set based on likely PS default
    "scd_threshold": 10.0,      # Value doesn't matter when scd="none"
    "mb_size": "(default)",     # Keep default
    # Sharpening (Disabled, mimicking lack of unsharp/presence of tmix in PS)
    "apply_unsharp": False,
    "unsharp_lx": 7,            # Values kept for structure, but unused
    "unsharp_ly": 7,
    "unsharp_la": 1.0,
    "unsharp_cx": 5,
    "unsharp_cy": 5,
    "unsharp_ca": 0.0,
    # Quality (Adjusted based on PS comparison)
    "preset_text": "Medium (CRF 20)", # Changed preset level example
    "bitrate": 10000,           # Lowered bitrate example
    "bufsize": 15000,           # Lowered bufsize (1.5*bitrate)
    "pix_fmt": "yuv444p",       # Keep high quality format
    # Filter Preset (Intermediate step)
    "filter_preset": "medium",      # Match final preset level choice
}

# Default profile based on initial GUI values
DEFAULT_FFMPEG_PROFILE = {
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
    "apply_unsharp": True, # <-- Key for groupbox check state
    "unsharp_lx": 7,
    "unsharp_ly": 7,
    "unsharp_la": 1.0,
    "unsharp_cx": 5,
    "unsharp_cy": 5,
    "unsharp_ca": 0.0,
    # Quality
    "preset_text": "Very High (CRF 16)",
    "bitrate": 15000,
    "bufsize": 22500,
    "pix_fmt": "yuv444p",
    # Filter Preset
    "filter_preset": "slow",
}

# Store profiles in a dictionary for easy access
FFMPEG_PROFILES = {
    "Default": DEFAULT_FFMPEG_PROFILE,
    "Optimal": OPTIMAL_FFMPEG_PROFILE,
    "Optimal 2": OPTIMAL_FFMPEG_PROFILE_2, # <-- Add new profile
    # "Custom" is handled implicitly when settings change
}

# Define OPTIMAL_FFMPEG_INTERP_SETTINGS for backward compatibility if needed elsewhere?
# For now, we rely on the full profiles.
OPTIMAL_FFMPEG_INTERP_SETTINGS = {
    "mi_mode": OPTIMAL_FFMPEG_PROFILE["mi_mode"],
    "mc_mode": OPTIMAL_FFMPEG_PROFILE["mc_mode"],
    "me_mode": OPTIMAL_FFMPEG_PROFILE["me_mode"],
    "vsbmc": "1" if OPTIMAL_FFMPEG_PROFILE["vsbmc"] else "0",
    "scd": OPTIMAL_FFMPEG_PROFILE["scd"]
}


# ─── Custom clickable label ────────────────────────────────────────────────
class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.file_path: str | None = None # Add file_path attribute
        # enable mouse tracking / events
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, ev: QMouseEvent | None) -> None:
        # Check if ev is not None before accessing attributes
        if ev is not None and ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        # Pass ev to super method (it handles None correctly)
        super().mouseReleaseEvent(ev)

# ─── ZoomDialog closes on any click ──────────────────────────────────────
class ZoomDialog(QDialog):
    def __init__(self, pixmap: QPixmap, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        lbl = QLabel(self)
        lbl.setPixmap(pixmap)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.addWidget(lbl)
        self.resize(pixmap.size())

    # Add type hint for event
    def mousePressEvent(self, ev: QMouseEvent | None) -> None:
        self.close()

# ─── CropDialog class ─────────────────────────────────────────────
class CropDialog(QDialog):
    def __init__(self, pixmap: QPixmap, init: tuple[int,int,int,int]|None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Select Crop Region")

        self.original_pixmap = pixmap
        self.scale_factor = 1.0

        # --- Scale pixmap for display ---
        screen = QApplication.primaryScreen()
        if not screen:
            LOGGER.warning("Could not get screen geometry, crop dialog might be too large.")
            max_size = QSize(1024, 768) # Fallback size
        else:
            # Use 90% of available screen size
            max_size = screen.availableGeometry().size() * 0.9

        scaled_pix = pixmap.scaled(
            max_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.scale_factor = pixmap.width() / scaled_pix.width()
        # --- End scaling ---

        self.lbl = QLabel()
        self.lbl.setPixmap(scaled_pix) # Display scaled pixmap
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.rubber = QRubberBand(QRubberBand.Shape.Rectangle, self.lbl)
        self.origin = QPoint()
        self.crop_rect_scaled = QRect() # Store the rect drawn on the scaled pixmap

        if init:
            # Scale the initial rect DOWN for display
            init_rect_orig = QRect(*init)
            scaled_x = int(init_rect_orig.x() / self.scale_factor)
            scaled_y = int(init_rect_orig.y() / self.scale_factor)
            scaled_w = int(init_rect_orig.width() / self.scale_factor)
            scaled_h = int(init_rect_orig.height() / self.scale_factor)
            scaled_init_rect = QRect(scaled_x, scaled_y, scaled_w, scaled_h)
            self.rubber.setGeometry(scaled_init_rect)
            self.crop_rect_scaled = scaled_init_rect
            self.rubber.show()
        else:
            # Ensure crop_rect_scaled is initialized if no init rect
            self.crop_rect_scaled = QRect()

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel,
            parent=self
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(self.lbl)
        lay.addWidget(btns)

        # Adjust dialog size hint based on scaled content
        self.resize(lay.sizeHint())

    def mousePressEvent(self, ev: QMouseEvent | None) -> None:
        if ev is not None and ev.button() == Qt.MouseButton.LeftButton and self.lbl.geometry().contains(ev.pos()):
            self.origin = self.lbl.mapFromParent(ev.pos())
            # Ensure origin is within scaled pixmap boundaries
            if not self.lbl.pixmap().rect().contains(self.origin):
                 self.origin = QPoint()
                 return
            self.rubber.setGeometry(QRect(self.origin, QSize()))
            self.rubber.show()

    def mouseMoveEvent(self, ev: QMouseEvent | None) -> None:
        if ev is not None and not self.origin.isNull():
            cur = self.lbl.mapFromParent(ev.pos())
            # Clamp the current position to be within the scaled pixmap bounds
            scaled_pix_rect = self.lbl.pixmap().rect()
            cur.setX(max(0, min(cur.x(), scaled_pix_rect.width())))
            cur.setY(max(0, min(cur.y(), scaled_pix_rect.height())))
            self.rubber.setGeometry(QRect(self.origin, cur).normalized())

    def mouseReleaseEvent(self, ev: QMouseEvent | None) -> None:
        if ev is not None and ev.button() == Qt.MouseButton.LeftButton and not self.origin.isNull():
            # Store the geometry relative to the scaled pixmap
            self.crop_rect_scaled = self.rubber.geometry()
            self.origin = QPoint()

    # Return the rectangle coordinates scaled UP to the original pixmap size
    def getRect(self) -> QRect:
        orig_x = int(self.crop_rect_scaled.x() * self.scale_factor)
        orig_y = int(self.crop_rect_scaled.y() * self.scale_factor)
        orig_w = int(self.crop_rect_scaled.width() * self.scale_factor)
        orig_h = int(self.crop_rect_scaled.height() * self.scale_factor)

        # Clamp to original image boundaries
        orig_w = max(0, min(orig_w, self.original_pixmap.width() - orig_x))
        orig_h = max(0, min(orig_h, self.original_pixmap.height() - orig_y))
        orig_x = max(0, min(orig_x, self.original_pixmap.width()))
        orig_y = max(0, min(orig_y, self.original_pixmap.height()))

        return QRect(orig_x, orig_y, orig_w, orig_h)

# ────────────────────────────── Worker thread ──────────────────────────────
class VfiWorker(QThread):
    progress = pyqtSignal(int, int, float)
    finished = pyqtSignal(pathlib.Path)
    error    = pyqtSignal(str)

    def __init__(
        self,
        in_dir: pathlib.Path,
        out_file_path: pathlib.Path,
        fps: int,
        mid_count: int,
        # model_key: str, # REMOVED
        # tile_enable: bool, # REMOVED
        max_workers: int,
        encoder: str,
        # FFmpeg settings passed directly
        use_ffmpeg_interp: bool,
        filter_preset: str, # Intermediate filter preset
        mi_mode: str,
        mc_mode: str,
        me_mode: str,
        me_algo: str,
        search_param: int,
        scd_mode: str,
        scd_threshold: Optional[float],
        minter_mb_size: Optional[int],
        minter_vsbmc: int, # Pass as 0 or 1
        # Unsharp settings
        apply_unsharp: bool,
        unsharp_lx: int,
        unsharp_ly: int,
        unsharp_la: float,
        unsharp_cx: int,
        unsharp_cy: int,
        unsharp_ca: float,
        # Final encoding quality settings
        crf: int,
        bitrate_kbps: int,
        bufsize_kb: int,
        pix_fmt: str,
        # Other args
        skip_model: bool,
        crop_rect: tuple[int, int, int, int] | None,
        debug_mode: bool,
        # RIFE v4.6 specific settings
        rife_tile_enable: bool,
        rife_tile_size: int,
        rife_uhd_mode: bool,
        rife_thread_spec: str,
        rife_tta_spatial: bool,
        rife_tta_temporal: bool,
        model_key: str, # ADD model_key back
    ) -> None:
        super().__init__()
        self.in_dir        = in_dir
        self.out_file_path = out_file_path
        self.fps           = fps
        self.mid_count     = mid_count
        # self.model_key     = model_key # REMOVED
        # self.tile_enable   = tile_enable # REMOVED
        self.max_workers   = max_workers
        self.encoder       = encoder
        self.skip_model = skip_model
        self.crop_rect     = crop_rect
        self.debug_mode = debug_mode

        # Store FFmpeg filter/quality settings directly
        self._do_ffmpeg_interp = use_ffmpeg_interp # Renamed internal variable
        self.filter_preset = filter_preset
        self.mi_mode = mi_mode
        self.mc_mode = mc_mode
        self.me_mode = me_mode
        self.me_algo = me_algo
        self.search_param = search_param
        self.scd_mode = scd_mode
        self.scd_threshold = scd_threshold
        self.minter_mb_size = minter_mb_size
        self.minter_vsbmc = minter_vsbmc
        self.apply_unsharp = apply_unsharp
        self.unsharp_lx = unsharp_lx
        self.unsharp_ly = unsharp_ly
        self.unsharp_la = unsharp_la
        self.unsharp_cx = unsharp_cx
        self.unsharp_cy = unsharp_cy
        self.unsharp_ca = unsharp_ca
        self.crf = crf
        self.bitrate_kbps = bitrate_kbps
        self.bufsize_kb = bufsize_kb
        self.pix_fmt = pix_fmt

        # Store RIFE v4.6 specific settings
        self.model_key = model_key # Store model key
        self.rife_tile_enable = rife_tile_enable
        self.rife_tile_size = rife_tile_size
        self.rife_uhd_mode = rife_uhd_mode
        self.rife_thread_spec = rife_thread_spec
        self.rife_tta_spatial = rife_tta_spatial
        self.rife_tta_temporal = rife_tta_temporal

        # placeholder for middle-frame preview
        self.mid_frame_path: str | None = None
        # Find the RIFE executable within the package data (e.g., in a 'bin' folder)
        # IMPORTANT: Place your RIFE executable (e.g., 'rife-cli') in goesvfi/bin/
        #            and ensure it's executable.
        try:
            # pkgres.files returns a Traversable, convert to Path
            # In Python 3.9+, can use pkgres.files('goesvfi').joinpath('bin', 'rife-cli')
            # For broader compatibility, resolve first.
            rife_exe_resource = pkgres.files('goesvfi').joinpath('bin', 'rife-cli')
            # Need to resolve the Traversable to an actual file system path
            with pkgres.as_file(rife_exe_resource) as exe_path:
                 self.rife_exe_path = exe_path
        except FileNotFoundError:
             # Provide a more informative error if the exe isn't found
             raise FileNotFoundError("RIFE executable not found in package data (expected goesvfi/bin/rife-cli)")


    def run(self) -> None:
        from goesvfi.pipeline.run_vfi import run_vfi
        from goesvfi.pipeline.encode import encode_with_ffmpeg, _run_ffmpeg_command # Import helper

        raw_intermediate_path: Optional[pathlib.Path] = None
        filtered_intermediate_path: Optional[pathlib.Path] = None
        input_for_final_encode: Optional[pathlib.Path] = None

        try:
            LOGGER.info("Starting VFI worker for %s -> %s", self.in_dir, self.out_file_path)
            # record the original middle input PNG for post‑processing preview
            all_pngs = sorted(self.in_dir.glob("*.png"))
            if all_pngs:
                mid_idx = len(all_pngs) // 2 # Use floor division
                # Ensure index is valid even for list with 1 element
                mid_idx = min(mid_idx, len(all_pngs) - 1)
                mid = all_pngs[mid_idx]
                self.mid_frame_path = str(mid)
                LOGGER.info(f"Recorded middle frame path for preview: {self.mid_frame_path}")
            else:
                LOGGER.warning("No PNGs found in input dir, cannot set mid_frame_path.")

            # --- Step A: Generating raw intermediate video --- #
            LOGGER.info("Step 1: Generating raw intermediate video (no FFmpeg interp here)...")

            # Run the VFI pipeline to get the raw intermediate - PASS ARGS DIRECTLY
            run_vfi_iterator: Iterator[Union[Tuple[int, int, float], pathlib.Path]] = run_vfi(
                folder=self.in_dir,
                output_mp4_path=self.out_file_path, # Base path for intermediates
                rife_exe_path=self.rife_exe_path,
                fps=self.fps,
                num_intermediate_frames=self.mid_count,
                max_workers=self.max_workers,
                # Pass arguments previously in kwargs directly
                crop_rect=self.crop_rect,
                model_key=self.model_key, # Pass stored model key
                skip_model=self.skip_model,
                rife_tile_enable=self.rife_tile_enable,
                rife_tile_size=self.rife_tile_size,
                rife_uhd_mode=self.rife_uhd_mode,
                rife_thread_spec=self.rife_thread_spec,
                rife_tta_spatial=self.rife_tta_spatial,
                rife_tta_temporal=self.rife_tta_temporal
            )
            for update in run_vfi_iterator:
                # --- This is the correct start of the loop body ---
                if isinstance(update, pathlib.Path):
                    raw_intermediate_path = update
                    LOGGER.info(f"Raw intermediate video created: {raw_intermediate_path}")
                elif isinstance(update, tuple):
                    idx, total, eta = update
                    self.progress.emit(idx, total, eta)
                else:
                    LOGGER.warning(f"Received unexpected update type from run_vfi: {type(update)}")

            # --- Code continues after the loop ---
            if not raw_intermediate_path or not raw_intermediate_path.exists():
                raise RuntimeError(f"Raw intermediate video path not received or file not found: {raw_intermediate_path}")

            # --- Step B: Optional FFmpeg Filtering Pass (Simplified) --- #
            if self._do_ffmpeg_interp:
                LOGGER.info("Step 1.5: Applying FFmpeg motion interpolation filter (based on GUI settings)...")
                filtered_intermediate_path = raw_intermediate_path.with_name(
                    f"{raw_intermediate_path.stem}.filtered{raw_intermediate_path.suffix}"
                )

                # --- Build filter strings directly from passed-in settings --- #
                filter_options = {
                    "mi_mode": self.mi_mode,
                    "mc_mode": self.mc_mode,
                    "me_mode": self.me_mode,
                    "search_param": str(self.search_param),
                    "fps": str(self.fps * 2), # Use the target FPS * 2
                    "scd": self.scd_mode,
                    # Add other options conditionally based on their values/defaults
                }
                if self.me_algo != "(default)":
                    filter_options["me"] = self.me_algo
                if self.scd_mode == "fdiff" and self.scd_threshold is not None:
                    filter_options["scd_threshold"] = f"{self.scd_threshold:.1f}"
                if self.minter_mb_size is not None:
                    filter_options["mb_size"] = str(self.minter_mb_size)
                # vsbmc is 0 or 1, convert to string
                filter_options["vsbmc"] = str(self.minter_vsbmc)

                minterpolate_str = "minterpolate=" + ":".join([f"{k}={v}" for k, v in filter_options.items()])

                # Combine with unsharp if enabled
                filter_vf_str = minterpolate_str
                if self.apply_unsharp:
                    unsharp_str = (
                        f"unsharp="
                        f"luma_msize_x={self.unsharp_lx}:luma_msize_y={self.unsharp_ly}:luma_amount={self.unsharp_la:.1f}:"
                        f"chroma_msize_x={self.unsharp_cx}:chroma_msize_y={self.unsharp_cy}:chroma_amount={self.unsharp_ca:.1f}"
                    )
                    filter_vf_str += f",{unsharp_str}"
                # --- End build filter strings --- #

                # --- Run the filtering command --- #
                filter_desc = "Filtering Pass (GUI Settings)"
                cmd_filter = [
                    "ffmpeg",
                    "-report",
                    "-hide_banner", "-loglevel", "debug", "-stats", "-y",
                    "-i", str(raw_intermediate_path),
                    "-vf", filter_vf_str, # Use the combined filter string
                    "-c:v", "libx264", "-preset", self.filter_preset, # Use the intermediate preset
                    "-an",
                    "-pix_fmt", self.pix_fmt, # Use the final target pixel format for intermediate too?
                    str(filtered_intermediate_path)
                ]

                try:
                    _run_ffmpeg_command(cmd_filter, filter_desc)
                    input_for_final_encode = filtered_intermediate_path
                    LOGGER.info(f"{filter_desc} created: {input_for_final_encode}")
                except RuntimeError as e:
                    # Handle error if filtering fails (no fallback here anymore)
                    LOGGER.error(f"{filter_desc} failed: {e}")
                    raise RuntimeError(f"FFmpeg filtering failed with current settings: {e}") from e

            else:
                # If not filtering, use the raw intermediate directly for the final encode
                input_for_final_encode = raw_intermediate_path
                LOGGER.info("Skipping FFmpeg motion interpolation filter pass.")

            # Check if the input for the next step exists
            if not input_for_final_encode or not input_for_final_encode.exists():
                raise RuntimeError(f"Input file for final encoding not found: {input_for_final_encode}")

            # --- Step C: Final Encoding Pass --- #
            LOGGER.info(f"Step 2: Final encoding from {input_for_final_encode} -> {self.out_file_path} using encoder '{self.encoder}'")

            encode_with_ffmpeg(
                intermediate_input=input_for_final_encode,
                final_output=self.out_file_path,
                encoder=self.encoder,
                # Pass the final quality settings
                crf=self.crf,
                bitrate_kbps=self.bitrate_kbps,
                bufsize_kb=self.bufsize_kb,
                pix_fmt=self.pix_fmt
            )

            LOGGER.info(f"Final output created: {self.out_file_path}")
            self.finished.emit(self.out_file_path)

        except Exception as exc:
            LOGGER.exception("Worker failed")
            self.error.emit(str(exc))

        finally:
            # --- Log debug status before cleanup --- #
            LOGGER.info(f"Worker finished. Debug mode is set to: {self.debug_mode}") # <-- Added log
            # --- Cleanup Intermediates --- #
            if not self.debug_mode: # <-- Check debug flag
                files_to_delete = [raw_intermediate_path, filtered_intermediate_path]
                for file_path in files_to_delete:
                    if file_path and file_path.exists() and file_path != self.out_file_path:
                        try:  # <-- Indent this block
                            LOGGER.info(f"Cleaning up intermediate file: {file_path}")
                            file_path.unlink()
                        except OSError as e:
                            LOGGER.error(f"Failed to delete intermediate file {file_path}: {e}")

# ──────────────────────────────── Main window ─────────────────────────────
class MainWindow(QWidget):
    def __init__(self, debug_mode: bool = False) -> None:
        super().__init__()
        self.setWindowTitle("GOES‑VFI")
        self.debug_mode = debug_mode
        self._ffmpeg_setting_change_active = True # Flag to prevent profile switching during load/apply

        self._base_output_path: pathlib.Path | None = None
        self.settings = QSettings("YourOrg", "GOESVFI")
        saved_crop = self.settings.value("main/cropRect", None)
        self.crop_rect = tuple(map(int, saved_crop.split(","))) if isinstance(saved_crop, str) else None

        self.tabs = QTabWidget()
        self.tabs.addTab(self._makeMainTab(), "Interpolate")
        self.tabs.addTab(self._make_ffmpeg_settings_tab(), "FFmpeg Settings") # New unified tab
        self.tabs.addTab(self._makeModelLibraryTab(), "Models")
        # Removed old filter/quality tabs

        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready")

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.tabs)
        main_layout.addWidget(self.status_bar)
        self.setLayout(main_layout)

        # Set initial fixed width
        self.setFixedWidth(600)

        self.worker: VfiWorker | None = None

        # --- Populate dynamic UI elements --- #
        self._populate_models() # Populate model list

        self._connect_ffmpeg_settings_tab_signals() # Connect signals for the new tab

        self.loadSettings() # <-- Load settings after UI is built

        # Apply the initially loaded or default profile after UI is built and settings possibly loaded
        initial_profile = self.settings.value("ffmpeg/profile", "Default", type=str)
        if initial_profile in FFMPEG_PROFILES:
            self._apply_ffmpeg_profile(initial_profile)
        else:
             self._apply_ffmpeg_profile("Default") # Fallback
             if initial_profile != "Custom": # Avoid setting Custom if it was loaded
                 # Check if ffmpeg_profile_combo exists before setting text
                 if hasattr(self, 'ffmpeg_profile_combo'):
                     self.ffmpeg_profile_combo.setCurrentText("Custom")

        # Initial resize after everything is loaded
        # self.adjustSize() # REMOVED - Replaced by conditional logic below

        # --- Final Size Adjustment ---
        if not self._geometry_restored:
            LOGGER.debug("No saved geometry found, calculating size based on content after delay.")
            # Call the adjustment method after a short delay
            QTimer.singleShot(50, self._adjust_window_to_content) # Changed delay to 50ms
        else:
            LOGGER.debug("Window size restored from saved geometry.")

    def _adjust_window_to_content(self) -> None:
        """Adjust window height to fit content of the current tab, clamped to screen height."""
        LOGGER.debug("Adjusting window height to fit current tab content...")

        current_tab_widget = self.tabs.currentWidget()
        if not isinstance(current_tab_widget, QScrollArea):
            LOGGER.warning("Current tab widget is not a QScrollArea, falling back to adjustSize().")
            self.adjustSize()
            return

        scroll_content = current_tab_widget.widget() # Get the widget inside the scroll area
        if not scroll_content:
            LOGGER.warning("Scroll area has no content widget, falling back to adjustSize().")
            self.adjustSize()
            return

        # Calculate ideal size based on the scroll area's content widget
        # content_hint = scroll_content.sizeHint()
        content_hint = scroll_content.minimumSizeHint() # TRY THIS INSTEAD

        # Add padding/margins for better spacing and account for window frame/decorations
        # These values might need tuning
        v_padding = 80 # Increased vertical padding

        ideal_height = content_hint.height() + v_padding

        # Add status bar height if it exists
        if hasattr(self, 'status_bar'):
            ideal_height += self.status_bar.height()

        # Get available screen size
        screen = QApplication.primaryScreen()
        if screen:
            screen_size = screen.availableGeometry().size()
            # Clamp ideal height to screen height
            final_height = min(ideal_height, screen_size.height())
            # Use current fixed width
            final_width = self.width() # Get current width (should be fixed)
            LOGGER.debug(f"Tab content hint H: {content_hint.height()}, Ideal H: {ideal_height}, Screen H: {screen_size.height()}, Final H: {final_height}")

            current_geom = self.geometry()
            # Check if resizing height is actually needed
            if abs(current_geom.height() - final_height) > 5:
                # Resize height only, keep current width
                self.resize(final_width, final_height)
            else:
                LOGGER.debug("Skipping height resize, current height is close enough.")
        else:
            # Fallback if screen size is unavailable
            LOGGER.warning("Could not get screen geometry, falling back to adjustSize().")
            self.adjustSize()

    def _pick_in_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if not folder:
            return
        self.in_edit.setText(folder)
        self._update_previews()

    def _pick_out_file(self) -> None:
        suggested_dir = self._base_output_path.parent if self._base_output_path else config.get_output_dir()
        suggested_name = self._base_output_path.name if self._base_output_path else "goes_animated.mp4"
        suggested = str(suggested_dir / suggested_name)
        path_str, _ = QFileDialog.getSaveFileName(self, "Save MP4", suggested, "MP4 files (*.mp4)")
        if path_str:
            path = pathlib.Path(path_str)
            self.out_edit.setText(str(path))
            self._base_output_path = path # Store the exact selected path

    def _makeMainTab(self) -> QWidget:
        """Builds the main 'Interpolate' tab UI."""
        # --- Create Content Widget and Layout ---
        # This widget will contain all controls and go *inside* the scroll area
        scroll_content_widget = QWidget()
        layout = QVBoxLayout(scroll_content_widget) # Layout FOR the content widget
        # layout.setAlignment(Qt.AlignmentFlag.AlignTop) # Keep content aligned top

        # Set vertical size policy for the content widget if needed (optional)
        # scroll_content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # --- Widgets (Initialize as before) ---
        self.in_edit   = QLineEdit()
        self.in_browse = QPushButton("Browse…")
        self.out_edit   = QLineEdit()
        self.out_browse = QPushButton("Save As…")
        self.fps_spin   = QSpinBox(); self.fps_spin.setRange(1, 240); self.fps_spin.setValue(10)
        self.mid_spin   = QSpinBox()
        self.mid_spin.setRange(1, 3)
        self.mid_spin.setSingleStep(2)
        self.mid_spin.setValue(1)
        self.mid_spin.setToolTip(
            "Number of in-between frames per original pair:\\n"
            "• 1 = single midpoint (fastest)\\n"
            "• 3 = recursive three-step (smoother)"
        )
        # --- RIFE v4.6 Settings Group ---
        self.rife_group = QGroupBox("RIFE v4.6 (ncnn) Settings")
        self.rife_group.setCheckable(False)
        rife_layout = QGridLayout(self.rife_group)

        # --- Model Selection (Data-driven) --- #
        rife_layout.addWidget(QLabel("Model:"), 0, 0)
        self.model_combo = QComboBox()
        self.model_combo.setToolTip("Select the RIFE model version to use.")
        # Items will be populated by _populate_models()
        rife_layout.addWidget(self.model_combo, 0, 1, 1, 2) # Span 2 columns

        # Intermediate frames (moved here)
        rife_layout.addWidget(QLabel("Intermediate frames:"), 1, 0) # Start at row 1 now
        rife_layout.addWidget(self.mid_spin, 1, 1, 1, 2) # Span 2 columns

        # Tiling
        self.tile_checkbox = QCheckBox("Enable tiling")
        self.tile_checkbox.setChecked(False) # Default OFF per user spec
        self.tile_checkbox.setToolTip(
            "Split large frames into tiles before interpolating.\\n"
            "Uses less RAM, potentially faster, but may show edge artifacts."
        )
        rife_layout.addWidget(self.tile_checkbox, 2, 0) # Start at row 2

        self.tile_size_spin = QSpinBox()
        self.tile_size_spin.setRange(128, 512)
        self.tile_size_spin.setValue(256)
        self.tile_size_spin.setSingleStep(64)
        self.tile_size_spin.setToolTip("Tile size in pixels. Requires tiling enabled.")
        self.tile_size_spin.setEnabled(False) # Disabled by default as checkbox is off
        rife_layout.addWidget(QLabel("Tile Size:"), 2, 1) # Row 2
        rife_layout.addWidget(self.tile_size_spin, 2, 2) # Row 2

        # UHD Mode
        self.uhd_checkbox = QCheckBox("UHD Mode")
        self.uhd_checkbox.setChecked(False) # Default OFF
        self.uhd_checkbox.setToolTip("Enable UHD mode for >4K frames. Selects HD model variant.")
        rife_layout.addWidget(self.uhd_checkbox, 3, 0) # Row 3

        # Thread Spec
        self.thread_edit = QLineEdit("1:2:2")
        self.thread_edit.setToolTip("Load:Proc:Save thread counts. E.g., '1:2:2'.")
        rife_layout.addWidget(QLabel("Thread Spec:"), 3, 1) # Row 3
        rife_layout.addWidget(self.thread_edit, 3, 2) # Row 3

        # TTA
        self.tta_spatial_cb = QCheckBox("Spatial TTA")
        self.tta_spatial_cb.setChecked(False)
        self.tta_spatial_cb.setToolTip("Enable spatial Test-Time Augmentation. Slower, may reduce artifacts.")
        rife_layout.addWidget(self.tta_spatial_cb, 4, 0) # Row 4

        self.tta_temporal_cb = QCheckBox("Temporal TTA")
        self.tta_temporal_cb.setChecked(False)
        self.tta_temporal_cb.setToolTip("Enable temporal Test-Time Augmentation. Slower, may reduce artifacts.")
        rife_layout.addWidget(self.tta_temporal_cb, 4, 1, 1, 2) # Row 4, Span 2 cols

        # --- End RIFE v4.6 Settings Group ---

        # --- Other Main Widgets ---
        self.start_btn  = QPushButton("Start")
        self.progress   = QProgressBar(); self.progress.setRange(0, 1)

        # ─── Encoder Selection ────────────────────────────────────────────
        self.encode_combo = QComboBox()
        self.encode_combo.addItems([
            "None (copy original)",
            "Software x265",
            "Software x265 (2-Pass)",
            "Hardware HEVC (VideoToolbox)",
            "Hardware H.264 (VideoToolbox)",
            # TODO: Add Windows/Linux hardware options if desired
        ])
        self.encode_combo.setToolTip(
            "Pick your output codec, or None to skip re-encoding."
        )
        # Update default setting logic: prioritize HEVC
        available_encoders = [self.encode_combo.itemText(i) for i in range(self.encode_combo.count())]
        if "Hardware HEVC (VideoToolbox)" in available_encoders:
            self.encode_combo.setCurrentText("Hardware HEVC (VideoToolbox)")
        elif "Hardware H.264 (VideoToolbox)" in available_encoders:
            self.encode_combo.setCurrentText("Hardware H.264 (VideoToolbox)")
        else:
            self.encode_combo.setCurrentText("Software x265") # Fallback

        # FFmpeg interpolation checkbox MOVED to FFmpeg Settings Tab

        # ─── Skip model interpolation toggle ─────────────────────
        self.skip_model_cb = QCheckBox("Skip AI interpolation (use originals only)")
        self.skip_model_cb.setChecked(False)
        self.skip_model_cb.setToolTip(
            "If checked, do not run the AI model; video will be assembled from\\n"
            "original frames (optionally with FFmpeg interpolation)."
        )

        # ─── Max parallel workers ─────────────────────────────────────────
        self.workers_spin = QSpinBox()
        # Get cpu_count safely for default value
        import os
        cpu_cores = os.cpu_count() or 1 # Default to 1 if None
        default_workers = max(1, cpu_cores - 1) # Leave one free if possible
        self.workers_spin.setRange(1, max(8, cpu_cores)) # Allow up to cpu_count or 8
        self.workers_spin.setValue(min(default_workers, 8)) # Default, capped at 8
        self.workers_spin.setToolTip(
            "Max number of parallel interpolation processes (CPU has " + str(cpu_cores) + ").\\n"
            "Reduce if you experience memory issues."
        )

        # ─── Tiling toggle ────────────────────────────────────────────────
        self.tile_checkbox = QCheckBox("Enable tiling for large frames (>2k)")
        self.tile_checkbox.setChecked(True) # Default to ON
        self.tile_checkbox.setToolTip(
            "Split large frames into tiles before interpolating.\\n"
            "Faster & uses less RAM, but may have edge artifacts.\\n"
            "Disable if RAM allows or edges look bad."
        )

        # ─── Preview thumbnails ───────────────────────────────────────────
        self.preview_first = ClickableLabel("First frame")
        self.preview_mid   = ClickableLabel("Mid frame")
        self.preview_last  = ClickableLabel("Last frame")
        for lbl in (self.preview_first, self.preview_mid, self.preview_last):
            lbl.setFixedSize(128,128)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("border: 1px solid gray; background-color: #eee;")
            # Connect click -> open dialog
            lbl.clicked.connect(lambda lb=lbl: self._show_zoom(lb))

        pv_row = QHBoxLayout()
        pv_row.addWidget(self.preview_first)
        pv_row.addWidget(self.preview_mid)
        pv_row.addWidget(self.preview_last)

        # Layout (Specific to this tab)
        in_row  = QHBoxLayout();  in_row.addWidget(QLabel("Input folder:"));  in_row.addWidget(self.in_edit);  in_row.addWidget(self.in_browse)
        out_row = QHBoxLayout(); out_row.addWidget(QLabel("Output MP4:"));  out_row.addWidget(self.out_edit); out_row.addWidget(self.out_browse)
        fps_row = QHBoxLayout(); fps_row.addWidget(QLabel("Target FPS:")); fps_row.addWidget(self.fps_spin); fps_row.addStretch()
        # mid_row = QHBoxLayout(); mid_row.addWidget(QLabel("Intermediate frames:")); mid_row.addWidget(self.mid_spin); mid_row.addStretch() # MOVED TO RIFE GROUP

        # Add new layout rows
        # tile_row = QHBoxLayout() # MOVED TO RIFE GROUP
        # tile_row.addWidget(self.tile_checkbox)
        # tile_row.addStretch()

        workers_row = QHBoxLayout()
        workers_row.addWidget(QLabel("Max workers (CPU):")) # Clarify this is likely CPU-bound GUI tasks
        workers_row.addWidget(self.workers_spin)
        workers_row.addStretch()

        # model_row = QHBoxLayout(); model_row.addWidget(QLabel("Model:")); model_row.addWidget(self.model_combo); model_row.addStretch() # REMOVED
        # Add layout row for encoder
        encode_row = QHBoxLayout(); encode_row.addWidget(QLabel("Encoder:")); encode_row.addWidget(self.encode_combo); encode_row.addStretch()

        # FFmpeg interpolation checkbox row REMOVED from here

        # Add skip_model checkbox row
        skip_row = QHBoxLayout()
        skip_row.addWidget(self.skip_model_cb)
        skip_row.addStretch()
        # layout.addLayout(skip_row) # Keep skip row separate from RIFE group for clarity

        # ─── Crop button ────────────────────────────────────────────────
        self.crop_btn = QPushButton("Crop…")
        self.crop_btn.setToolTip("Draw a rectangle on the first frame to crop all images")
        in_row.addWidget(self.crop_btn)
        self.crop_btn.clicked.connect(self._on_crop_clicked)

        # Add Clear Crop button (New)
        self.clear_crop_btn = QPushButton("Clear Crop")
        self.clear_crop_btn.setToolTip("Remove the current crop selection")
        in_row.addWidget(self.clear_crop_btn)
        self.clear_crop_btn.clicked.connect(self._on_clear_crop_clicked) # Connect new signal

        # --- Add Rows/Widgets to the main LAYOUT (which is on scroll_content_widget) ---
        layout.addLayout(in_row); layout.addLayout(out_row);
        # Update layout adding order
        layout.addLayout(fps_row)
        # layout.addLayout(mid_row) # MOVED
        layout.addLayout(skip_row)      # ADD SKIP ROW HERE (before RIFE settings)
        layout.addWidget(self.rife_group) # ADD RIFE GROUP BOX HERE
        layout.addLayout(workers_row)   # Add workers row after RIFE
        layout.addLayout(encode_row)    # Add encode row after RIFE
        layout.addWidget(QLabel("Frame Previews:")) # Add label for previews
        layout.addLayout(pv_row) # Add preview row
        layout.addWidget(self.start_btn); layout.addWidget(self.progress)

        # ─── Open in VLC button ───────────────────────────────────────────
        self.open_btn = QPushButton("Open in VLC")
        self.open_btn.setEnabled(False)
        self.open_btn.setToolTip("Launch the finished MP4 in VLC")
        layout.addWidget(self.open_btn) # Add button to layout

        # Add stretch to push content to the top *within the scrollable area*
        layout.addStretch()

        # --- Create Scroll Area and Set Content --- #
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff) # Usually not needed
        scroll_area.setWidget(scroll_content_widget) # Put the content widget inside the scroll area

        # --- Signals (Connect signals specific to this tab's widgets here) ---
        self.in_browse.clicked.connect(self._pick_in_dir)
        self.out_browse.clicked.connect(self._pick_out_file)
        self.start_btn.clicked.connect(self._start)
        self.open_btn.clicked.connect(self._open_in_vlc) # Connect new button
        self.in_edit.textChanged.connect(self._update_previews) # Connect input edit to preview update
        # Connect tile checkbox to enable/disable tile size spinbox
        if hasattr(self, 'tile_checkbox') and hasattr(self, 'tile_size_spin'):
            # Disconnect first to avoid duplicate connections if run multiple times (defensive)
            try: 
                self.tile_checkbox.toggled.disconnect()
            except TypeError: 
                pass # No connection existed
            # Reconnect the signal to the new slot
            self.tile_checkbox.toggled.connect(self._toggle_tile_size_enabled)
            LOGGER.debug("Connected tile_checkbox.toggled to _toggle_tile_size_enabled")
            # Ensure initial state is correct
            self._toggle_tile_size_enabled(self.tile_checkbox.isChecked()) # Call slot directly for initial state

        # TODO: Unresolved Issue - Tile Size spinbox does not visually enable/disable
        # when the 'Enable tiling' checkbox is toggled, even though the signal appears
        # connected initially and the internal slot logic seems correct. The slot
        # _toggle_tile_size_enabled is not being called on user interaction after load.
        # Needs further investigation into potential connection overriding or event issues.

        # Connect skip AI checkbox to enable/disable the RIFE group
        if hasattr(self, 'skip_model_cb') and hasattr(self, 'rife_group'):
            self.skip_model_cb.toggled.connect(lambda checked: self.rife_group.setEnabled(not checked))
            # Set initial state
            self.rife_group.setEnabled(not self.skip_model_cb.isChecked())

        # --- Connect thread spec validation ---
        if hasattr(self, 'thread_edit'):
            self.thread_edit.textChanged.connect(self._validate_thread_spec)
            # Initial validation
            self._validate_thread_spec(self.thread_edit.text())

        return scroll_area # Return the scroll area itself

    def _make_ffmpeg_settings_tab(self) -> QWidget:
        """Builds the consolidated FFmpeg Settings tab UI."""
        # --- Create Content Widget and Layout ---
        scroll_content_widget = QWidget()
        layout = QVBoxLayout(scroll_content_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Set vertical size policy (optional, layout alignment handles top alignment)
        # scroll_content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # --- Stylesheet for GroupBoxes ---
        groupbox_style = """
        QGroupBox::title {
            font-size: 13px; /* Adjust as needed */
        }
        QGroupBox::indicator {
            width: 13px;
            height: 13px;
        }
        """

        # --- Profile Selector ---
        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel("<b>FFmpeg Settings Profile:</b>"))
        self.ffmpeg_profile_combo = QComboBox()
        # Add standard profiles + Custom option
        self.ffmpeg_profile_combo.addItems(list(FFMPEG_PROFILES.keys()) + ["Custom"])
        self.ffmpeg_profile_combo.setToolTip("Select a predefined settings profile or use 'Custom'.")
        profile_row.addWidget(self.ffmpeg_profile_combo)
        profile_row.addStretch()
        layout.addLayout(profile_row)

        # --- Enable Checkbox ---
        interp_row = QHBoxLayout()
        self.ffmpeg_interp_cb = QCheckBox("Use FFmpeg motion interpolation")
        # Default checked state will be set by profile/loadSettings
        self.ffmpeg_interp_cb.setToolTip("Apply FFmpeg's 'minterpolate' filter before encoding.")
        interp_row.addWidget(self.ffmpeg_interp_cb)
        interp_row.addStretch()
        layout.addLayout(interp_row)

        layout.addSpacing(10)

        # --- Motion Interpolation Group ---
        minterpolate_group = QGroupBox("Motion Interpolation (minterpolate)") # <-- Title Updated
        minterpolate_group.setObjectName("minterpolate_group") # Set object name
        minterpolate_group.setCheckable(True) # <-- Make it checkable/collapsible
        minterpolate_group.setChecked(True)  # <-- Start expanded
        minterpolate_group.setStyleSheet(groupbox_style) # <-- Apply style (Re-apply)
        self.minterpolate_group = minterpolate_group # Assign group to self

        # --- Create Content Widget and Layout for Interpolation ---
        self.minterpolate_content_widget = QWidget()
        grid = QGridLayout(self.minterpolate_content_widget) # <-- Layout targets the content widget

        # --- Add controls to the content layout (grid) --- 
        # Interpolation Mode (mi_mode)
        mi_lbl = QLabel("Interpolation Mode:")
        self.mi_combo = QComboBox()
        self.mi_combo.addItems(["dup", "blend", "mci", "mc"])
        self.mi_combo.setToolTip(
            "Method for creating intermediate frames.\\n"
            "- dup: Duplicate frames (Fastest, no interpolation).\\n"
            "- blend: Simple frame averaging (Fast, blurry).\\n"
            "- mci: Motion Compensated Interpolation (Uses MC settings).\\n"
            "- mc: Motion Compensation (No interpolation).\\n"
            "Recommended: 'mci'."
        )
        grid.addWidget(mi_lbl, 0, 0)
        grid.addWidget(self.mi_combo, 0, 1)

        # Motion Compensation Mode (mc_mode)
        mc_lbl = QLabel("Motion Comp. Mode:")
        self.mc_combo = QComboBox()
        self.mc_combo.addItems(["obmc", "aobmc"])
        self.mc_combo.setToolTip(
            "Algorithm for applying motion vectors.\\n"
            "- obmc: Overlapped Block Motion Compensation (Standard).\\n"
            "- aobmc: Adaptive Overlapped Block MC (Higher quality, slower).\\n"
            "Recommended: 'obmc'."
        )
        grid.addWidget(mc_lbl, 1, 0)
        grid.addWidget(self.mc_combo, 1, 1)

        # Motion Estimation Mode (me_mode)
        me_lbl = QLabel("Motion Estimation Mode:")
        self.me_combo = QComboBox()
        self.me_combo.addItems(["bidir", "bilat"])
        self.me_combo.setToolTip(
            "Direction for motion vector search.\\n"
            "- bidir: Bidirectional (Uses past/future frames, best quality).\\n"
            "- bilat: Bilateral (Alternative bidirectional).\\n"
            "Recommended: 'bidir'."
        )
        grid.addWidget(me_lbl, 2, 0)
        grid.addWidget(self.me_combo, 2, 1)

        # Motion Estimation Algorithm (me_algo)
        me_algo_lbl = QLabel("ME Algorithm:")
        self.me_algo_combo = QComboBox()
        self.me_algo_combo.addItems(["(default)", "esa", "epzs", "hexbs", "umh"])
        self.me_algo_combo.setToolTip(
            "Algorithm for finding motion vectors.\\n"
            "- (default): FFmpeg's choice (often EPZS/HexBS).\\n"
            "- esa: Exhaustive Search (Slowest, highest quality).\\n"
            "- epzs: Enhanced Predictive Zonal Search (Good balance).\\n"
            "- hexbs/umh: Hexagon-based Search (Faster).\\n"
            "Recommended: Start with '(default)'."
        )
        grid.addWidget(me_algo_lbl, 3, 0)
        grid.addWidget(self.me_algo_combo, 3, 1)

        # Search parameter (search_param)
        search_param_lbl = QLabel("ME Search Parameter:")
        self.search_param_spin = QSpinBox()
        self.search_param_spin.setRange(4, 256)
        self.search_param_spin.setToolTip(
            "Max pixel distance to search for motion vectors.\\n"
            "Larger = Slower, better for fast motion.\\n"
            "Recommended: 64-128."
        )
        grid.addWidget(search_param_lbl, 4, 0)
        grid.addWidget(self.search_param_spin, 4, 1)

        # Scene change detection algorithm (scd)
        scd_lbl = QLabel("Scene Change Detection:")
        self.scd_combo = QComboBox()
        self.scd_combo.addItems(["none", "fdiff"])
        self.scd_combo.setToolTip(
            "Method to detect scene cuts.\\n"
            "- fdiff: Frame Difference (Recommended).\\n"
            "- none: No detection (Faster, artifacts at cuts)."
        )
        grid.addWidget(scd_lbl, 5, 0)
        grid.addWidget(self.scd_combo, 5, 1)

        # Scene change threshold (scd_threshold)
        scd_thresh_lbl = QLabel("Scene Change Threshold (%):")
        self.scd_thresh_spin = QDoubleSpinBox()
        self.scd_thresh_spin.setRange(0.0, 100.0)
        self.scd_thresh_spin.setSingleStep(0.1)
        self.scd_thresh_spin.setDecimals(1)
        self.scd_thresh_spin.setToolTip(
            "Sensitivity for 'fdiff' (0-100%).\\n"
            "Lower = More sensitive.\\n"
            "Recommended: Start with 8-12."
        )
        grid.addWidget(scd_thresh_lbl, 6, 0)
        grid.addWidget(self.scd_thresh_spin, 6, 1)

        # Filter Encoding Preset (filter_preset) - Now applies to intermediate step
        filter_preset_lbl = QLabel("Filter Encoding Preset:")
        self.filter_preset_combo = QComboBox()
        self.filter_preset_combo.addItems([
            "ultrafast", "superfast", "veryfast", "faster", "fast",
            "medium", "slow", "slower", "veryslow"
        ])
        self.filter_preset_combo.setToolTip(
            "x264 preset for the *intermediate* filtered video (if filtering enabled).\\n"
            "Slower presets might create slightly higher quality input for RIFE.\\n"
            "Does NOT affect final output encoding.\\n"
            "Recommended: 'medium' or 'slow'."
        )
        grid.addWidget(filter_preset_lbl, 7, 0)
        grid.addWidget(self.filter_preset_combo, 7, 1)

        # Macroblock size (mb_size)
        mbsize_lbl = QLabel("Macroblock Size:")
        self.mbsize_combo = QComboBox()
        self.mbsize_combo.addItems(["(default)", "16", "8", "4"])
        self.mbsize_combo.setToolTip(
            "Size of blocks for motion estimation.\\n"
            "- (default)/16: Standard, good balance.\\n"
            "- 8/4: Finer detail, *significantly* slower.\\n"
            "Recommended: '(default)' or '16'."
        )
        grid.addWidget(mbsize_lbl, 8, 0)
        grid.addWidget(self.mbsize_combo, 8, 1)

        # Variable-size block motion comp (vsbmc)
        vsbmc_lbl = QLabel("Variable Size Blocks:")
        self.vsbmc_cb = QCheckBox()
        self.vsbmc_cb.setToolTip(
            "Allow smaller block sizes within macroblock.\\n"
            "Improves detail on complex motion, increases processing time.\\n"
            "Recommended: Keep off unless necessary."
        )
        grid.addWidget(vsbmc_lbl, 9, 0)
        grid.addWidget(self.vsbmc_cb, 9, 1)

        # --- Add Content Widget to GroupBox Layout ---
        group_layout = QVBoxLayout(self.minterpolate_group) # Create layout for the groupbox itself
        group_layout.addWidget(self.minterpolate_content_widget)

        layout.addWidget(minterpolate_group)
        layout.addSpacing(10)

        # --- Sharpening Group ---
        unsharp_group = QGroupBox("Sharpening (unsharp)") # <-- Title Updated
        unsharp_group.setObjectName("unsharp_group") # Set object name
        unsharp_group.setCheckable(True) # <-- Make it checkable/collapsible
        unsharp_group.setChecked(True)  # <-- Start expanded
        self.unsharp_group = unsharp_group # <-- Assign to self
        unsharp_group.setStyleSheet(groupbox_style) # <-- Apply style (Re-apply)

        # --- Create Content Widget and Layout for Sharpening ---
        self.unsharp_content_widget = QWidget()
        unsharp_grid = QGridLayout(self.unsharp_content_widget) # <-- Layout targets the content widget

        # --- Add controls to the content layout (unsharp_grid) ---
        # Need to adjust row indices for subsequent widgets since row 0 was removed
        self.luma_x_label = QLabel("Luma Matrix X Size (lx):")
        unsharp_grid.addWidget(self.luma_x_label, 0, 0) # Start at row 0
        self.luma_x_spin = QSpinBox(); self.luma_x_spin.setRange(3, 23); self.luma_x_spin.setSingleStep(2);
        self.luma_x_spin.setToolTip("Horizontal size of luma sharpening mask (odd, 3-23). Larger = smoother. Recommended: 5 or 7.")
        unsharp_grid.addWidget(self.luma_x_spin, 0, 1) # Row 0

        self.luma_y_label = QLabel("Luma Matrix Y Size (ly):")
        unsharp_grid.addWidget(self.luma_y_label, 1, 0) # Row 1
        self.luma_y_spin = QSpinBox(); self.luma_y_spin.setRange(3, 23); self.luma_y_spin.setSingleStep(2);
        self.luma_y_spin.setToolTip("Vertical size of luma sharpening mask (odd, 3-23). Recommended: 5 or 7.")
        unsharp_grid.addWidget(self.luma_y_spin, 1, 1) # Row 1

        self.luma_amount_label = QLabel("Luma Amount (la):")
        unsharp_grid.addWidget(self.luma_amount_label, 2, 0) # Row 2
        self.luma_amount_spin = QDoubleSpinBox(); self.luma_amount_spin.setRange(-1.5, 5.0); self.luma_amount_spin.setDecimals(1); self.luma_amount_spin.setSingleStep(0.1);
        self.luma_amount_spin.setToolTip("Strength of luma sharpening (-1.5 to 5.0). >0 sharpens. Recommended: 0.5-1.0.")
        unsharp_grid.addWidget(self.luma_amount_spin, 2, 1) # Row 2

        self.chroma_x_label = QLabel("Chroma Matrix X Size (cx):")
        unsharp_grid.addWidget(self.chroma_x_label, 3, 0) # Row 3
        self.chroma_x_spin = QSpinBox(); self.chroma_x_spin.setRange(3, 23); self.chroma_x_spin.setSingleStep(2);
        self.chroma_x_spin.setToolTip("Horizontal size of chroma sharpening mask (odd, 3-23). Recommended: 3 or 5.")
        unsharp_grid.addWidget(self.chroma_x_spin, 3, 1) # Row 3

        self.chroma_y_label = QLabel("Chroma Matrix Y Size (cy):")
        unsharp_grid.addWidget(self.chroma_y_label, 4, 0) # Row 4
        self.chroma_y_spin = QSpinBox(); self.chroma_y_spin.setRange(3, 23); self.chroma_y_spin.setSingleStep(2);
        self.chroma_y_spin.setToolTip("Vertical size of chroma sharpening mask (odd, 3-23). Recommended: 3 or 5.")
        unsharp_grid.addWidget(self.chroma_y_spin, 4, 1) # Row 4

        self.chroma_amount_label = QLabel("Chroma Amount (ca):")
        unsharp_grid.addWidget(self.chroma_amount_label, 5, 0) # Row 5
        self.chroma_amount_spin = QDoubleSpinBox(); self.chroma_amount_spin.setRange(-1.5, 5.0); self.chroma_amount_spin.setDecimals(1); self.chroma_amount_spin.setSingleStep(0.1);
        self.chroma_amount_spin.setToolTip("Strength of chroma sharpening (-1.5 to 5.0). 0 = none (recommended).")
        unsharp_grid.addWidget(self.chroma_amount_spin, 5, 1) # Row 5

        # --- Add Content Widget to GroupBox Layout ---
        unsharp_group_layout = QVBoxLayout(self.unsharp_group) # Create layout for the groupbox itself
        unsharp_group_layout.addWidget(self.unsharp_content_widget)

        layout.addWidget(unsharp_group)
        layout.addSpacing(10)

        # --- Encoding Quality Group ---
        quality_group = QGroupBox("Encoding Quality (Final Output)")
        quality_group.setObjectName("quality_group") # Set object name
        quality_layout = QVBoxLayout(quality_group) # Use QVBoxLayout for this group

        # Preset selector (influences CRF for software codecs)
        quality_layout.addWidget(QLabel("Software Encoder Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["Very High (CRF 16)", "High (CRF 18)", "Medium (CRF 20)"])
        self.preset_combo.setToolTip("Selects the CRF value for software encoders (libx264, libx265). Lower = higher quality.")
        quality_layout.addWidget(self.preset_combo)

        # Bitrate control (for hardware codecs)
        quality_layout.addWidget(QLabel("Hardware Encoder Target Bitrate (kbps):"))
        self.bitrate_spin = QSpinBox()
        self.bitrate_spin.setRange(1000, 20000) # 1-20 Mbps
        self.bitrate_spin.setSuffix(" kbps")
        self.bitrate_spin.setToolTip("Target average bitrate for hardware encoders (VideoToolbox, etc.). Ignored by software.")
        quality_layout.addWidget(self.bitrate_spin)

        # Buffer size control (for hardware codecs)
        quality_layout.addWidget(QLabel("Hardware Encoder VBV Buffer Size (kb):"))
        self.bufsize_spin = QSpinBox()
        self.bufsize_spin.setRange(1000, 40000) # 1-40 Mbits
        self.bufsize_spin.setSuffix(" kb")
        self.bufsize_spin.setToolTip("Video Buffer Verifier size (controls max bitrate). ~1.5x bitrate is a good start. Ignored by software.")
        # Connection for bitrate -> bufsize moved to _connect_ffmpeg_settings_tab_signals
        quality_layout.addWidget(self.bufsize_spin)

        # Pixel format selector
        quality_layout.addWidget(QLabel("Output Pixel Format:"))
        self.pixfmt_combo = QComboBox()
        self.pixfmt_combo.addItems(["yuv420p", "yuv444p"])
        self.pixfmt_combo.setToolTip("Video pixel format. yuv420p is standard, yuv444p retains more color (larger file).")
        quality_layout.addWidget(self.pixfmt_combo)

        layout.addWidget(quality_group)

        # REMOVED layout.addStretch() from here - Add stretch inside scroll area if needed

        # --- Set initial content visibility based on groupbox state ---
        if hasattr(self, 'minterpolate_group') and hasattr(self, '_toggle_minterpolate_content'):
            self._toggle_minterpolate_content(self.minterpolate_group.isChecked())
        if hasattr(self, 'unsharp_group') and hasattr(self, '_toggle_unsharp_content'):
            self._toggle_unsharp_content(self.unsharp_group.isChecked())
        # --- End Initial Visibility ---

        # --- Create Scroll Area and Set Content --- #
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setWidget(scroll_content_widget)

        return scroll_area # Return the scroll area

    def _connect_ffmpeg_settings_tab_signals(self) -> None:
        """Connect signals for enabling/disabling controls and profile handling on the FFmpeg Settings tab."""
        # --- Profile Handling ---
        # Check if ffmpeg_profile_combo exists before connecting
        if hasattr(self, 'ffmpeg_profile_combo'):
            self.ffmpeg_profile_combo.currentTextChanged.connect(self._on_profile_selected)

        # --- Connect individual controls to switch profile to "Custom" ---
        controls_to_monitor = [
            # Group 1: Interpolation
            self.ffmpeg_interp_cb, self.mi_combo, self.mc_combo, self.me_combo,
            self.me_algo_combo, self.search_param_spin, self.scd_combo,
            self.scd_thresh_spin, self.filter_preset_combo, self.mbsize_combo,
            self.vsbmc_cb,
            # Group 2: Sharpening (Controls inside)
            # self.unsharp_cb, <-- REMOVED
            self.luma_x_spin, self.luma_y_spin,
            self.luma_amount_spin, self.chroma_x_spin, self.chroma_y_spin,
            self.chroma_amount_spin,
            # Group 3: Quality
            self.preset_combo, self.bitrate_spin,
            self.bufsize_spin, self.pixfmt_combo
        ]
        for control in controls_to_monitor:
             # Check if the control attribute exists on self before connecting
             if hasattr(self, control.objectName()):
                 actual_control = getattr(self, control.objectName())
                 if isinstance(actual_control, QComboBox):
                     actual_control.currentTextChanged.connect(self._on_ffmpeg_setting_changed)
                 elif isinstance(actual_control, QCheckBox):
                     actual_control.toggled.connect(self._on_ffmpeg_setting_changed)
                 elif isinstance(actual_control, (QSpinBox, QDoubleSpinBox)):
                     actual_control.valueChanged.connect(self._on_ffmpeg_setting_changed)

        # --- Control Enabling/Disabling ---
        # Check existence before connecting signals for dependent controls
        if hasattr(self, 'scd_combo'):
            self.scd_combo.currentTextChanged.connect(self._update_scd_thresh_state)
        # REMOVE OLD UNSHARP_CB CONNECTION
        # if hasattr(self, 'unsharp_cb'):
        #     self.unsharp_cb.toggled.connect(self._update_unsharp_controls_state)

        # Connect toggling the unsharp group itself to mark profile as custom
        if hasattr(self, 'unsharp_group'):
            self.unsharp_group.toggled.connect(self._on_ffmpeg_setting_changed)
            self.unsharp_group.toggled.connect(self._toggle_unsharp_content) # <-- Connect to hide/show content

        # --- Connect interpolation group toggle ---
        if hasattr(self, 'minterpolate_group'):
            # Also connect toggled signal to hide/show its content
            self.minterpolate_group.toggled.connect(self._toggle_minterpolate_content) # <-- Connect to hide/show content
            # Keep connection for profile change (optional, but good practice if group toggling should mark custom)
            # self.minterpolate_group.toggled.connect(self._on_ffmpeg_setting_changed) # Uncomment if needed


        if hasattr(self, 'ffmpeg_interp_cb'):
            self.ffmpeg_interp_cb.toggled.connect(self._update_ffmpeg_controls_state)
        if hasattr(self, 'bitrate_spin') and hasattr(self, 'bufsize_spin'):
            self.bitrate_spin.valueChanged.connect(
                 lambda val: self.bufsize_spin.setValue(min(self.bufsize_spin.maximum(), max(self.bufsize_spin.minimum(), int(val * 1.5))))
            )

        # --- Connect tab switching to resize window ---
        if hasattr(self, 'tabs'):
            self.tabs.currentChanged.connect(self._on_tab_changed)

        # Initial state update after potential loading
        if hasattr(self, 'ffmpeg_interp_cb'):
             self._update_ffmpeg_controls_state(self.ffmpeg_interp_cb.isChecked())


    def _on_profile_selected(self, profile_name: str) -> None:
        """Applies the selected profile if it's not 'Custom'."""
        # Prevent recursive calls when applying profile programmatically
        if not self._ffmpeg_setting_change_active: return
        if profile_name != "Custom" and profile_name in FFMPEG_PROFILES:
            LOGGER.info(f"Applying FFmpeg profile: {profile_name}")
            self._apply_ffmpeg_profile(profile_name)


    def _on_ffmpeg_setting_changed(self, *args: Any) -> None:
        """Switches the profile combo to 'Custom' if a setting is changed manually."""
        # Prevent switching to Custom when applying a profile or loading settings
        if not self._ffmpeg_setting_change_active: return

        # Check if ffmpeg_profile_combo exists
        if not hasattr(self, 'ffmpeg_profile_combo'): return

        # Block signals temporarily to prevent immediate re-application of "Custom"
        self.ffmpeg_profile_combo.blockSignals(True)
        self.ffmpeg_profile_combo.setCurrentText("Custom")
        self.ffmpeg_profile_combo.blockSignals(False)
        # LOGGER.debug("FFmpeg setting changed, profile set to Custom.")


    def _apply_ffmpeg_profile(self, profile_name: str) -> None:
        """Updates the UI controls based on the selected profile dictionary."""
        if profile_name not in FFMPEG_PROFILES:
            LOGGER.warning(f"Profile '{profile_name}' not found.")
            return

        profile = FFMPEG_PROFILES[profile_name]
        LOGGER.debug(f"Applying settings from profile: {profile_name}")

        # --- Block signals and disable change flag during update ---
        self._ffmpeg_setting_change_active = False
        # Check if ffmpeg_profile_combo exists before blocking/setting
        if hasattr(self, 'ffmpeg_profile_combo'):
            self.ffmpeg_profile_combo.blockSignals(True)

        try:
            # Set profile combo without triggering signal
            if hasattr(self, 'ffmpeg_profile_combo'):
                self.ffmpeg_profile_combo.setCurrentText(profile_name)

            # --- Apply settings from profile dict --- (Using cast for type safety)
            # Check existence of each control before setting its value
            if hasattr(self, 'ffmpeg_interp_cb'): self.ffmpeg_interp_cb.setChecked(cast(bool, profile.get("use_ffmpeg_interp", True)))
            if hasattr(self, 'mi_combo'): self.mi_combo.setCurrentText(cast(str, profile.get("mi_mode", "mci")))
            if hasattr(self, 'mc_combo'): self.mc_combo.setCurrentText(cast(str, profile.get("mc_mode", "obmc")))
            if hasattr(self, 'me_combo'): self.me_combo.setCurrentText(cast(str, profile.get("me_mode", "bidir")))
            if hasattr(self, 'me_algo_combo'): self.me_algo_combo.setCurrentText(cast(str, profile.get("me_algo", "(default)")))
            if hasattr(self, 'search_param_spin'): self.search_param_spin.setValue(cast(int, profile.get("search_param", 96)))
            if hasattr(self, 'scd_combo'): self.scd_combo.setCurrentText(cast(str, profile.get("scd", "fdiff")))
            if hasattr(self, 'scd_thresh_spin'): self.scd_thresh_spin.setValue(cast(float, profile.get("scd_threshold", 10.0)))
            if hasattr(self, 'filter_preset_combo'): self.filter_preset_combo.setCurrentText(cast(str, profile.get("filter_preset", "slow")))
            if hasattr(self, 'mbsize_combo'): self.mbsize_combo.setCurrentText(cast(str, profile.get("mb_size", "(default)")))
            if hasattr(self, 'vsbmc_cb'): self.vsbmc_cb.setChecked(cast(bool, profile.get("vsbmc", False)))
            if hasattr(self, 'unsharp_cb'): self.unsharp_cb.setChecked(cast(bool, profile.get("apply_unsharp", True)))
            if hasattr(self, 'luma_x_spin'): self.luma_x_spin.setValue(cast(int, profile.get("unsharp_lx", 7)))
            if hasattr(self, 'luma_y_spin'): self.luma_y_spin.setValue(cast(int, profile.get("unsharp_ly", 7)))
            if hasattr(self, 'luma_amount_spin'): self.luma_amount_spin.setValue(cast(float, profile.get("unsharp_la", 1.0)))
            if hasattr(self, 'chroma_x_spin'): self.chroma_x_spin.setValue(cast(int, profile.get("unsharp_cx", 5)))
            if hasattr(self, 'chroma_y_spin'): self.chroma_y_spin.setValue(cast(int, profile.get("unsharp_cy", 5)))
            if hasattr(self, 'chroma_amount_spin'): self.chroma_amount_spin.setValue(cast(float, profile.get("unsharp_ca", 0.0)))
            if hasattr(self, 'preset_combo'): self.preset_combo.setCurrentText(cast(str, profile.get("preset_text", "Very High (CRF 16)")))
            if hasattr(self, 'bitrate_spin'): self.bitrate_spin.setValue(cast(int, profile.get("bitrate", 15000)))
            if hasattr(self, 'bufsize_spin') and hasattr(self, 'bitrate_spin'):
                default_bufsize = int(self.bitrate_spin.value() * 1.5)
                self.bufsize_spin.setValue(cast(int, profile.get("bufsize", default_bufsize)))
            if hasattr(self, 'pixfmt_combo'): self.pixfmt_combo.setCurrentText(cast(str, profile.get("pix_fmt", "yuv444p")))

            # --- Ensure group boxes are expanded when applying a profile ---
            if hasattr(self, 'minterpolate_group'):
                self.minterpolate_group.setChecked(True)
            if hasattr(self, 'unsharp_group'):
                # Set checked state based on profile's apply_unsharp value
                self.unsharp_group.setChecked(cast(bool, profile.get("apply_unsharp", True)))

            # --- Update content visibility based on new groupbox check state ---
            if hasattr(self, 'minterpolate_group') and hasattr(self, '_toggle_minterpolate_content'):
                self._toggle_minterpolate_content(self.minterpolate_group.isChecked())
            if hasattr(self, 'unsharp_group') and hasattr(self, '_toggle_unsharp_content'):
                self._toggle_unsharp_content(self.unsharp_group.isChecked())
            # --- End Content Visibility Update ---

            # --- Update dependent control states ---\
            if hasattr(self, 'ffmpeg_interp_cb'):
                self._update_ffmpeg_controls_state(self.ffmpeg_interp_cb.isChecked()) # Handles interp/unsharp groups

        finally:
            # --- Re-enable signals and flag ---\
            if hasattr(self, 'ffmpeg_profile_combo'):
                 self.ffmpeg_profile_combo.blockSignals(False)
            self._ffmpeg_setting_change_active = True
            LOGGER.debug(f"Finished applying profile: {profile_name}")


    def _update_ffmpeg_controls_state(self, enable: bool) -> None:
        """Enables/disables all interpolation and sharpening controls based on the main checkbox."""
        # Find group boxes within the FFmpeg Settings tab
        # Get the index of the FFmpeg Settings tab
        ffmpeg_tab_index = -1
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == "FFmpeg Settings":
                ffmpeg_tab_index = i
                break

        if ffmpeg_tab_index == -1:
            LOGGER.error("Could not find 'FFmpeg Settings' tab to update controls.")
            return

        ffmpeg_tab_widget = self.tabs.widget(ffmpeg_tab_index)
        if not ffmpeg_tab_widget:
            LOGGER.error("Widget for 'FFmpeg Settings' tab is invalid.")
            return # Safety check

        # Find the specific group boxes within the correct tab widget
        # Use object names if they are set, otherwise rely on titles (less robust)
        minterpolate_group = ffmpeg_tab_widget.findChild(QGroupBox, "minterpolate_group")
        unsharp_group = ffmpeg_tab_widget.findChild(QGroupBox, "unsharp_group")
        quality_group = ffmpeg_tab_widget.findChild(QGroupBox, "quality_group")

        # Fallback to finding by title if object names aren't found (adjust titles if needed)
        if not minterpolate_group:
            minterpolate_group = ffmpeg_tab_widget.findChild(QGroupBox, "Motion Interpolation (minterpolate)")
        if not unsharp_group:
            unsharp_group = ffmpeg_tab_widget.findChild(QGroupBox, "Sharpening (unsharp)")
        if not quality_group:
            quality_group = ffmpeg_tab_widget.findChild(QGroupBox, "Encoding Quality (Final Output)")

        # --- Set Visibility based on main checkbox ---
        if minterpolate_group:
            minterpolate_group.setVisible(enable)
        else:
            LOGGER.warning("Could not find minterpolate_group to update visibility.")

        if unsharp_group:
            unsharp_group.setVisible(enable)
        else:
            LOGGER.warning("Could not find unsharp_group to update visibility.")
        # --- End Visibility Setting ---

        # Quality group itself remains enabled/visible
        if quality_group:
            quality_group.setEnabled(True) # Ensure quality group is always enabled
            quality_group.setVisible(True) # Ensure quality group is always visible

        # SCD threshold state is handled by its own signal connection, no need to call here.

    def _update_scd_thresh_state(self, scd_mode: str) -> None:
        # Only enable threshold if scd_mode is fdiff
        # Remove dependency on main ffmpeg checkbox state
        # main_interp_enabled = hasattr(self, 'ffmpeg_interp_cb') and self.ffmpeg_interp_cb.isChecked()
        enable = (scd_mode == "fdiff") # Enable ONLY based on scd_mode
        # Check if scd_thresh_spin exists
        if hasattr(self, 'scd_thresh_spin'):
            self.scd_thresh_spin.setEnabled(enable)

    def _update_unsharp_controls_state(self, checked: bool) -> None:
        # Only enable the unsharp group if main interp is enabled AND unsharp checkbox is checked
        main_interp_enabled = hasattr(self, 'ffmpeg_interp_cb') and self.ffmpeg_interp_cb.isChecked()
        enable_group = main_interp_enabled and checked

        # Find the unsharp group box again
        ffmpeg_tab_index = -1
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == "FFmpeg Settings":
                ffmpeg_tab_index = i
                break
        if ffmpeg_tab_index == -1: return # Should not happen
        ffmpeg_tab_widget = self.tabs.widget(ffmpeg_tab_index)
        if not ffmpeg_tab_widget: return

        unsharp_group = ffmpeg_tab_widget.findChild(QGroupBox, "unsharp_group")
        if not unsharp_group:
            unsharp_group = ffmpeg_tab_widget.findChild(QGroupBox, "Sharpening (unsharp)")

        if unsharp_group:
            unsharp_group.setEnabled(enable_group)
            # Ensure internal controls are enabled when the group is visible (they might have been disabled)
            # We no longer need to toggle individual controls here, just the group visibility.
            # unsharp_group.setEnabled(True) # Keep internal controls enabled, visibility controls the group <-- REMOVE THIS LINE
            unsharp_group.setEnabled(enable_group) # <-- USE THIS INSTEAD
        else:
            LOGGER.warning("Could not find unsharp_group to update visibility.")

    def _start(self) -> None:
        in_dir  = pathlib.Path(self.in_edit.text()).expanduser()

        # --- Ensure Base Output Path ---
        if not self._base_output_path:
            # Handle case where base path is somehow still None (e.g., first run, user cleared input)
            # Suggest a default name in the default output directory
            default_out_dir = config.get_output_dir()
            default_out_dir.mkdir(parents=True, exist_ok=True)
            self._base_output_path = default_out_dir / "goes_timelapse.mp4"
            LOGGER.warning(f"Base output path was not set, using default: {self._base_output_path}")
            # Update the UI field to reflect the default being used for this run
            self.out_edit.setText(str(self._base_output_path))

        base_out_path = self._base_output_path
        # Ensure stem/suffix are derived correctly, handling potential missing suffix
        stem = base_out_path.stem
        suf = base_out_path.suffix if base_out_path.suffix else ".mp4"
        # --- End stem/suf derivation ---

        # --- Generate timestamp and final path ---
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Use the parent from the base path and the derived stem/suf
        final_out_mp4 = base_out_path.with_name(f"{stem}_{ts}{suf}")

        # Reflect the ACTUAL timestamped path back into the UI for this run
        self.out_edit.setText(str(final_out_mp4))
        # --- End timestamp logic ---

        # Use the generated final_out_mp4 path from now on
        fps     = self.fps_spin.value()
        # Get RIFE v4.6 settings from the group box
        model_key = self.model_combo.currentText() if hasattr(self, 'model_combo') else "rife-v4.6" # Get selected model
        mid_count = self.mid_spin.value() if hasattr(self, 'mid_spin') else 1
        rife_tile_enable = self.tile_checkbox.isChecked() if hasattr(self, 'tile_checkbox') else False
        rife_tile_size = self.tile_size_spin.value() if hasattr(self, 'tile_size_spin') else 256
        rife_uhd_mode = self.uhd_checkbox.isChecked() if hasattr(self, 'uhd_checkbox') else False
        # Get and validate thread spec
        rife_thread_spec = "1:2:2" # Default
        if hasattr(self, 'thread_edit'):
            current_spec = self.thread_edit.text()
            # Check if the stylesheet indicates validity (empty means valid)
            if not self.thread_edit.styleSheet(): # Valid if style is empty
                rife_thread_spec = current_spec
            else:
                LOGGER.warning(f"Invalid thread spec '{current_spec}' in UI, using default '{rife_thread_spec}'.")
        # rife_thread_spec = self.thread_edit.text() if hasattr(self, 'thread_edit') else "1:2:2"
        rife_tta_spatial = self.tta_spatial_cb.isChecked() if hasattr(self, 'tta_spatial_cb') else False
        rife_tta_temporal = self.tta_temporal_cb.isChecked() if hasattr(self, 'tta_temporal_cb') else False

        # Get remaining general settings
        max_workers = self.workers_spin.value()
        encoder     = self.encode_combo.currentText()
        skip_model = self.skip_model_cb.isChecked()

        # --- Get settings from the consolidated FFmpeg Settings Tab ---\
        # Check existence of controls before accessing them
        use_ffmpeg_interp = self.ffmpeg_interp_cb.isChecked() if hasattr(self, 'ffmpeg_interp_cb') else False
        # Interpolation settings (with defaults if controls don't exist)
        mi_mode = self.mi_combo.currentText() if hasattr(self, 'mi_combo') else "mci"
        mc_mode = self.mc_combo.currentText() if hasattr(self, 'mc_combo') else "obmc"
        me_mode = self.me_combo.currentText() if hasattr(self, 'me_combo') else "bidir"
        me_algo = self.me_algo_combo.currentText() if hasattr(self, 'me_algo_combo') else "(default)"
        search_param = self.search_param_spin.value() if hasattr(self, 'search_param_spin') else 96
        scd_mode = self.scd_combo.currentText() if hasattr(self, 'scd_combo') else "fdiff"
        scd_threshold = self.scd_thresh_spin.value() if hasattr(self, 'scd_thresh_spin') and scd_mode == "fdiff" else None
        filter_preset = self.filter_preset_combo.currentText() if hasattr(self, 'filter_preset_combo') else "slow"
        mb_size_str = self.mbsize_combo.currentText() if hasattr(self, 'mbsize_combo') else "(default)"
        minter_mb_size = int(mb_size_str) if mb_size_str != "(default)" else None
        minter_vsbmc = 1 if hasattr(self, 'vsbmc_cb') and self.vsbmc_cb.isChecked() else 0
        # Sharpening settings
        apply_unsharp = self.unsharp_group.isChecked() if hasattr(self, 'unsharp_group') else False # <-- USE GROUP CHECK STATE
        unsharp_lx = self.luma_x_spin.value() if hasattr(self, 'luma_x_spin') else 7
        unsharp_ly = self.luma_y_spin.value() if hasattr(self, 'luma_y_spin') else 7
        unsharp_la = self.luma_amount_spin.value() if hasattr(self, 'luma_amount_spin') else 1.0
        unsharp_cx = self.chroma_x_spin.value() if hasattr(self, 'chroma_x_spin') else 5
        unsharp_cy = self.chroma_y_spin.value() if hasattr(self, 'chroma_y_spin') else 5
        unsharp_ca = self.chroma_amount_spin.value() if hasattr(self, 'chroma_amount_spin') else 0.0
        # Quality settings
        preset_text = self.preset_combo.currentText() if hasattr(self, 'preset_combo') else "Very High (CRF 16)"
        bitrate_kbps = self.bitrate_spin.value() if hasattr(self, 'bitrate_spin') else 15000
        bufsize_kb = self.bufsize_spin.value() if hasattr(self, 'bufsize_spin') else int(bitrate_kbps * 1.5)
        pix_fmt = self.pixfmt_combo.currentText() if hasattr(self, 'pixfmt_combo') else "yuv444p"
        # --- End Get FFmpeg Settings ---\

        # Calculate CRF from preset text (for final software encoding)
        try:
            crf_value = int(preset_text.split("CRF ")[-1].rstrip(")"))
        except (IndexError, ValueError):
            LOGGER.warning(f"Could not parse CRF from preset '{preset_text}', defaulting to 20.")
            crf_value = 20 # Default fallback

        # --- Log all settings before starting worker ---\
        settings_to_log = {
            "Input Directory": str(in_dir),
            "Output File": str(final_out_mp4),
            "FPS": fps,
            # "Intermediate Frames": mid_count, # Now under RIFE settings
            # "Model": model_key, # REMOVED
            # "Tiling Enabled": tile_enable, # Now under RIFE settings
            "Skip AI Model": skip_model,
            "Crop Rectangle": self.crop_rect,
            "Debug Mode": self.debug_mode,
            "RIFE v4.6 Settings": { # New section
                 "Intermediate Frames": mid_count,
                 "Tiling Enabled": rife_tile_enable,
                 "Tile Size": rife_tile_size if rife_tile_enable else "N/A",
                 "UHD Mode": rife_uhd_mode,
                 "Thread Spec": rife_thread_spec,
                 "Spatial TTA": rife_tta_spatial,
                 "Temporal TTA": rife_tta_temporal,
            },
            "Encoder": encoder, # Moved encoder log here
            "Max Workers (CPU)": max_workers, # Moved worker log here
            "FFmpeg Settings": {
                "Profile": self.ffmpeg_profile_combo.currentText() if hasattr(self, 'ffmpeg_profile_combo') else 'N/A', # Log selected profile
                "Enabled": use_ffmpeg_interp,
                # Interpolation
                "Intermediate Preset": filter_preset,
                "MI Mode": mi_mode,
                "MC Mode": mc_mode,
                "ME Mode": me_mode,
                "ME Algorithm": me_algo,
                "Search Param": search_param,
                "SCD Mode": scd_mode,
                "SCD Threshold": scd_threshold,
                "MB Size": minter_mb_size,
                "VSBMC": minter_vsbmc,
                # Sharpening
                "Apply Unsharp": apply_unsharp,
                "Unsharp Luma X": unsharp_lx,
                "Unsharp Luma Y": unsharp_ly,
                "Unsharp Luma Amount": unsharp_la,
                "Unsharp Chroma X": unsharp_cx,
                "Unsharp Chroma Y": unsharp_cy,
                "Unsharp Chroma Amount": unsharp_ca,
                # Quality
                "Software Preset (CRF)": f"{preset_text} ({crf_value})",
                "Hardware Bitrate (kbps)": bitrate_kbps,
                "Hardware Buffer (kb)": bufsize_kb,
                "Pixel Format": pix_fmt,
            },
        }
        LOGGER.info(f"Starting VFI process with settings:\\n{json.dumps(settings_to_log, indent=2)}")
        # --- End Logging ---\

        # disable the Open button until we finish
        self.open_btn.setEnabled(False)

        if not in_dir.is_dir():
            self._show_error("Input folder does not exist."); return
        # Ensure output directory exists, but use the full path for the worker
        final_out_mp4.parent.mkdir(parents=True, exist_ok=True)

        # Disable UI & launch worker
        self.start_btn.setEnabled(False); self.progress.setRange(0, 0)
        self.progress.setValue(0) # Explicitly reset progress value
        self.status_bar.showMessage("Starting interpolation...") # Update status bar

        # Ensure crop_rect type matches worker's expectation using cast
        current_crop_rect = cast(Optional[Tuple[int, int, int, int]], self.crop_rect)

        # Start worker - Pass all relevant FFmpeg settings
        self.worker = VfiWorker(
            # Standard args
            in_dir=in_dir,
            out_file_path=final_out_mp4,
            fps=fps,
            mid_count=mid_count,
            # model_key=model_key, # REMOVED - Worker no longer needs this directly
            # tile_enable=tile_enable, # REMOVED
            max_workers=max_workers,
            encoder=encoder,
            skip_model=skip_model,
            crop_rect=current_crop_rect,
            debug_mode=self.debug_mode,
             # FFmpeg settings
            use_ffmpeg_interp=use_ffmpeg_interp,
            filter_preset=filter_preset,
            mi_mode=mi_mode,
            mc_mode=mc_mode,
            me_mode=me_mode,
            me_algo=me_algo,
            search_param=search_param,
            scd_mode=scd_mode,
            scd_threshold=scd_threshold,
            minter_mb_size=minter_mb_size,
            minter_vsbmc=minter_vsbmc,
            apply_unsharp=apply_unsharp,
            unsharp_lx=unsharp_lx,
            unsharp_ly=unsharp_ly,
            unsharp_la=unsharp_la,
            unsharp_cx=unsharp_cx,
            unsharp_cy=unsharp_cy,
            unsharp_ca=unsharp_ca,
            # Quality args
            crf=crf_value,
            bitrate_kbps=bitrate_kbps,
            bufsize_kb=bufsize_kb,
            pix_fmt=pix_fmt,
            # Pass RIFE v4.6 specific settings
            model_key=model_key, # Pass selected model key
            rife_tile_enable=rife_tile_enable,
            rife_tile_size=rife_tile_size,
            rife_uhd_mode=rife_uhd_mode,
            rife_thread_spec=rife_thread_spec,
            rife_tta_spatial=rife_tta_spatial,
            rife_tta_temporal=rife_tta_temporal
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._show_error)
        self.worker.start()

    # ------------- callbacks --------------
    def _on_progress(self, current: int, total: int, eta: float) -> None:
        """Update progress bar and status bar with ETA."""
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(current)
            # Format ETA nicely
            eta_str = ""
            if eta > 0:
                eta_seconds = int(eta)
                minutes = eta_seconds // 60
                seconds = eta_seconds % 60
                eta_str = f" ETA: {minutes}m {seconds}s" if minutes > 0 else f" ETA: {seconds}s"
            else:
                # Handle zero or negative ETA (e.g., first frame or calculation issue)
                eta_str = "" # Don't show ETA yet or if invalid

            self.status_bar.showMessage(f"Processing {current}/{total}...{eta_str}")
        else: # Handle indeterminate case (shouldn't happen with new logic but safe)
            self.progress.setRange(0, 0)
            self.status_bar.showMessage("Processing...")

    def _on_finished(self, mp4: pathlib.Path) -> None:
        # mark progress done
        self.progress.setRange(0, 1); self.progress.setValue(1)
        self.start_btn.setEnabled(True)
        self.open_btn.setEnabled(True) # Enable Open button on success
        self.status_bar.showMessage(f"Finished: {mp4.name}") # Update status bar

        # Store the path for the Open button
        self._last_out = mp4

        # --- Load mid-frame preview --- #
        # NOTE: This assumes self.worker exists and has a populated 'mid_frame_path'
        #       which needs to be implemented in the worker/run_vfi logic separately.
        if self.worker and hasattr(self.worker, 'mid_frame_path'):
            mid_png_path_str = getattr(self.worker, 'mid_frame_path', None)
            if mid_png_path_str:
                mid_png = pathlib.Path(mid_png_path_str)
                if mid_png.exists():
                    try:
                        pixm = QPixmap(str(mid_png)).scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        self.preview_mid.setPixmap(pixm)
                        self.preview_mid.file_path = str(mid_png)
                        if not pixm.isNull(): self.preview_mid.setText("") # Clear text
                    except Exception as e:
                        LOGGER.error(f"Error loading mid-frame preview '{mid_png}': {e}")
                        self.preview_mid.setText("Mid frame\\n(Error)")
                else:
                     LOGGER.warning(f"Mid-frame path provided but file not found: {mid_png}")
                     self.preview_mid.setText("Mid frame\\n(Not found)")
            else:
                 LOGGER.info("No mid-frame path available after run.")
                 self.preview_mid.setText("Mid frame") # Reset text if no path
        else:
            LOGGER.warning("Worker or mid_frame_path attribute not available in _on_finished")
        # --- End mid-frame preview logic ---\

        self._show_info(f"Video saved to:\\n{mp4}")

    def _show_error(self, msg: str) -> None:
        LOGGER.error(msg)
        self.start_btn.setEnabled(True) # Re-enable start on error
        self.progress.setRange(0, 1); self.progress.setValue(0) # Reset progress visually
        self.status_bar.showMessage("Error occurred") # Update status bar
        QMessageBox.critical(self, "Error", msg)

    def _show_info(self, msg: str) -> None:
        QMessageBox.information(self, "Info", msg)

    # ------------- Add VLC opener method -----------\
    def _open_in_vlc(self) -> None:
        """Launch the last output MP4 in VLC (cross-platform)."""
        import sys, subprocess, pathlib # Keep imports local if preferred
        if not hasattr(self, "_last_out") or not self._last_out.exists():
             self._show_error("No valid output file found to open.")
             return
        path = str(self._last_out)
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-a", "VLC", path])
            elif sys.platform.startswith("win"):
                # Use 'start' command which should find VLC if in PATH
                # Providing full path to vlc.exe might be more robust if needed
                subprocess.Popen(["cmd", "/c", "start", "vlc", path], shell=True) # Use shell=True cautiously on Windows
            else:
                # Assume Linux/other Unix-like
                subprocess.Popen(["vlc", path])
        except FileNotFoundError:
             # Handle case where 'open', 'cmd', or 'vlc' command isn't found
            self._show_error(f"Could not find command to launch VLC. Is it installed and in your PATH?")
        except Exception as e:
             self._show_error(f"Failed to open file in VLC: {e}")

    # --- Zoom Dialog Method ---\
    def _show_zoom(self, label: ClickableLabel) -> None:
        """Pop up a frameless dialog showing the image from file_path, scaled to fit screen."""
        if not label.file_path or not pathlib.Path(label.file_path).exists():
            LOGGER.warning(f"Zoom requested but file_path is invalid: {label.file_path}")
            return # Do nothing if no valid file path

        try:
            pix = QPixmap(label.file_path)
            if pix.isNull():
                LOGGER.error(f"Failed to load pixmap for zoom: {label.file_path}")
                self._show_error(f"Could not load image:\\n{label.file_path}")
                return

            # --- Apply crop if it exists --- #
            if self.crop_rect:
                try:
                    x, y, w, h = cast(Tuple[int, int, int, int], self.crop_rect)
                    pix = pix.copy(x, y, w, h)
                    if pix.isNull(): # Check if copy resulted in an empty pixmap
                        LOGGER.error(f"Cropping resulted in null pixmap. Rect: {self.crop_rect}, Orig Size: {pix.size()}")
                        self._show_error("Error applying crop to image.")
                        return
                except Exception as crop_err:
                    LOGGER.exception(f"Error applying crop rect {self.crop_rect} during zoom")
                    self._show_error(f"Error applying crop:\\n{crop_err}")
                    return
            # --- End Apply crop --- #

            # scale to fit screen (80% of available geometry)
            target_size: QSize
            screen = self.screen()
            if screen:
                screen_geo = screen.availableGeometry()
                target_size = screen_geo.size() * 0.8 # Scale QSize directly
            else:
                LOGGER.warning("Could not get screen geometry, using default size for zoom.")
                target_size = QSize(1000, 1000) # Default fallback size

            scaled_pix = pix.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            dlg = ZoomDialog(scaled_pix, self)
            dlg.exec()

        except Exception as e:
            LOGGER.exception(f"Error showing zoom dialog for {label.file_path}")
            self._show_error(f"Error displaying image:\\n{e}")

    # +++ Restore Models Tab Method +++
    def _makeModelLibraryTab(self) -> QWidget:
        """Builds the Models tab with a simple table of available checkpoints."""
        # --- Create Content Widget and Layout ---
        scroll_content_widget = QWidget()
        layout = QVBoxLayout(scroll_content_widget)

        # Set vertical size policy for the content widget
        scroll_content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # --- Create the Table --- 
        tbl = QTableWidget(1, 4) # Parent removed, will be set by layout
        tbl.setHorizontalHeaderLabels(["Name", "Size", "Speed (FPS)", "ΔPSNR"])
        # Row 0: RIFE v4.6
        tbl.setItem(0, 0, QTableWidgetItem("RIFE v4.6 (ncnn)")) # Clarify it's ncnn
        tbl.setItem(0, 1, QTableWidgetItem("Uses included binary")) # Placeholder
        tbl.setItem(0, 2, QTableWidgetItem("Fast (GPU/Metal)")) # Placeholder
        tbl.setItem(0, 3, QTableWidgetItem("–")) # Placeholder for PSNR
        tbl.resizeColumnsToContents()

        # --- Add Table to Layout ---
        layout.addWidget(tbl)
        layout.addStretch() # Add stretch within the scrollable area

        # --- Create Scroll Area and Set Content --- #
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setWidget(scroll_content_widget)

        return scroll_area # Return the scroll area

    def _on_crop_clicked(self) -> None:
        from pathlib import Path
        folder = Path(self.in_edit.text()).expanduser()
        imgs = sorted(folder.glob("*.png"))
        if not imgs:
            QMessageBox.warning(self, "No Images", "Select a folder with PNGs first")
            return

        pix = QPixmap(str(imgs[0]))
        crop_init = cast(Optional[Tuple[int, int, int, int]], self.crop_rect)
        dlg = CropDialog(pix, crop_init, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            rect = dlg.getRect()
            self.crop_rect = (rect.x(), rect.y(), rect.width(), rect.height())
            self.settings.setValue("main/cropRect", ",".join(map(str, self.crop_rect)))
            self._update_previews()

    def _update_previews(self) -> None:
        LOGGER.info("Starting preview update...")
        start_time = datetime.now()
        from pathlib import Path
        folder = Path(self.in_edit.text()).expanduser()
        try:
            files = sorted(folder.glob("*.png"))
        except Exception as e:
            LOGGER.error(f"Error listing files in {folder}: {e}")
            files = [] # Ensure files is a list

        if not files:
            LOGGER.info("No PNG files found, clearing previews.")
            self.preview_first.clear(); self.preview_first.file_path = None
            self.preview_mid.clear(); self.preview_mid.file_path = None
            self.preview_last.clear(); self.preview_last.file_path = None
            return

        LOGGER.info(f"Found {len(files)} PNG files.")

        def crop_and_scale(path: Path) -> QPixmap:
            try:
                pix = QPixmap(str(path))
                if pix.isNull():
                    LOGGER.warning(f"Loaded null pixmap for {path.name}")
                    return QPixmap() # Return empty pixmap
                orig_size = pix.size()
                if self.crop_rect:
                    x,y,w,h = cast(Tuple[int, int, int, int], self.crop_rect)
                    pix = pix.copy(x,y,w,h)
                    if pix.isNull():
                        LOGGER.warning(f"Cropping {path.name} resulted in null pixmap. Rect: {(x,y,w,h)}, Orig: {orig_size}")
                        return QPixmap() # Return empty pixmap
                return pix.scaled(128,128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            except Exception as e:
                LOGGER.exception(f"Error cropping/scaling {path.name}")
                return QPixmap() # Return empty pixmap on error

        previews = [self.preview_first, self.preview_mid, self.preview_last]
        preview_names = ["First", "Mid", "Last"] # For logging
        indices = [0, len(files)//2, -1]

        if len(files) == 1:
            indices = [0, 0, 0]
        elif len(files) == 2:
            indices = [0, 0, 1]

        for i, (idx, lbl) in enumerate(zip(indices, previews)):
            p = files[idx]
            preview_name = preview_names[i]
            LOGGER.info(f"Updating preview '{preview_name}' with image index {idx}: {p.name}")
            pixmap = crop_and_scale(p)
            if not pixmap.isNull():
                lbl.setPixmap(pixmap)
                lbl.file_path = str(p)
            else:
                lbl.clear()
                lbl.setText(f"{preview_name}\\n(Error)") # Indicate error on label
                lbl.file_path = None

        end_time = datetime.now()
        LOGGER.info(f"Preview update finished in {(end_time - start_time).total_seconds():.3f} seconds.")

    def _on_clear_crop_clicked(self) -> None:
        """Clears the stored crop rectangle and updates previews."""
        if self.crop_rect is None:
            self.status_bar.showMessage("No crop is currently set.", 3000)
            return

        LOGGER.info("Clearing crop rectangle.")
        self.crop_rect = None
        self.settings.remove("main/cropRect") # Remove from persistent settings
        self._update_previews() # Refresh previews with full images
        self.status_bar.showMessage("Crop cleared.", 3000)

    # --- Slot to toggle tile size spinbox enabled state --- #
    def _toggle_tile_size_enabled(self, checked: bool) -> None:
        """Enable/disable the tile size spinbox based on the tile checkbox."""
        if hasattr(self, 'tile_size_spin'):
            LOGGER.debug(f"Setting tile_size_spin enabled state to: {checked}")
            self.tile_size_spin.setEnabled(checked)
            # --- Force visual change with style --- #
            if checked:
                self.tile_size_spin.setStyleSheet("background-color: yellow;")
            else:
                self.tile_size_spin.setStyleSheet("") # Reset to default style
            # --- End style change --- #
        else:
            LOGGER.warning("tile_size_spin attribute not found in _toggle_tile_size_enabled")
    # --- End Slot ---

    # --- Slot to toggle content visibility for group boxes --- #
    def _toggle_minterpolate_content(self, checked: bool) -> None:
        """Show/hide the content widget within the minterpolate group box."""
        if hasattr(self, 'minterpolate_content_widget'):
            self.minterpolate_content_widget.setVisible(checked)
            # Trigger a resize recalculation when visibility changes - REMOVED
            # QTimer.singleShot(0, self._adjust_window_to_content)
        else:
            LOGGER.warning("minterpolate_content_widget not found in _toggle_minterpolate_content")

    def _toggle_unsharp_content(self, checked: bool) -> None:
        """Show/hide the content widget within the unsharp group box."""
        if hasattr(self, 'unsharp_content_widget'):
            self.unsharp_content_widget.setVisible(checked)
            # Trigger a resize recalculation when visibility changes - REMOVED
        else:
            LOGGER.warning("unsharp_content_widget not found in _toggle_unsharp_content")
    # --- End Content Toggle Slots ---

    # --- Slot for tab changes --- #
    def _on_tab_changed(self, index: int) -> None:
        """Handle actions when the active tab changes, like resizing."""
        LOGGER.debug(f"Tab changed to index: {index}")
        # Trigger window adjustment after a minimal delay to allow layout to settle
        QTimer.singleShot(10, self._adjust_window_to_content)
    # --- End Tab Change Slot ---

    # --- Helper to check if UI settings match a profile --- #
    def _check_settings_match_profile(self, profile_dict: Dict[str, Any]) -> bool:
        """Helper to check if current UI settings match a given profile dictionary."""
        # Check existence of controls before comparing
        try:
            return (
                (not hasattr(self, 'ffmpeg_interp_cb') or self.ffmpeg_interp_cb.isChecked() == profile_dict.get("use_ffmpeg_interp", True)) and
                (not hasattr(self, 'mi_combo') or self.mi_combo.currentText() == profile_dict.get("mi_mode", "mci")) and
                (not hasattr(self, 'mc_combo') or self.mc_combo.currentText() == profile_dict.get("mc_mode", "obmc")) and
                (not hasattr(self, 'me_combo') or self.me_combo.currentText() == profile_dict.get("me_mode", "bidir")) and
                (not hasattr(self, 'me_algo_combo') or self.me_algo_combo.currentText() == profile_dict.get("me_algo", "(default)")) and
                (not hasattr(self, 'search_param_spin') or self.search_param_spin.value() == profile_dict.get("search_param", 96)) and
                (not hasattr(self, 'scd_combo') or self.scd_combo.currentText() == profile_dict.get("scd", "fdiff")) and
                (not hasattr(self, 'scd_thresh_spin') or self.scd_thresh_spin.value() == profile_dict.get("scd_threshold", 10.0)) and
                (not hasattr(self, 'filter_preset_combo') or self.filter_preset_combo.currentText() == profile_dict.get("filter_preset", "slow")) and
                (not hasattr(self, 'mbsize_combo') or self.mbsize_combo.currentText() == profile_dict.get("mb_size", "(default)")) and
                (not hasattr(self, 'vsbmc_cb') or self.vsbmc_cb.isChecked() == profile_dict.get("vsbmc", False)) and
                (not hasattr(self, 'unsharp_group') or self.unsharp_group.isChecked() == profile_dict.get("apply_unsharp", True)) and
                (not hasattr(self, 'luma_x_spin') or self.luma_x_spin.value() == profile_dict.get("unsharp_lx", 7)) and
                (not hasattr(self, 'luma_y_spin') or self.luma_y_spin.value() == profile_dict.get("unsharp_ly", 7)) and
                (not hasattr(self, 'luma_amount_spin') or self.luma_amount_spin.value() == profile_dict.get("unsharp_la", 1.0)) and
                (not hasattr(self, 'chroma_x_spin') or self.chroma_x_spin.value() == profile_dict.get("unsharp_cx", 5)) and
                (not hasattr(self, 'chroma_y_spin') or self.chroma_y_spin.value() == profile_dict.get("unsharp_cy", 5)) and
                (not hasattr(self, 'chroma_amount_spin') or self.chroma_amount_spin.value() == profile_dict.get("unsharp_ca", 0.0)) and
                (not hasattr(self, 'preset_combo') or self.preset_combo.currentText() == profile_dict.get("preset_text", "Very High (CRF 16)")) and
                (not hasattr(self, 'bitrate_spin') or self.bitrate_spin.value() == profile_dict.get("bitrate", 15000)) and
                # Bufsize check needs to be careful, might be auto-calculated
                # (not hasattr(self, 'bufsize_spin') or self.bufsize_spin.value() == profile_dict.get("bufsize", int(profile_dict.get("bitrate", 15000)*1.5))) and
                (not hasattr(self, 'pixfmt_combo') or self.pixfmt_combo.currentText() == profile_dict.get("pix_fmt", "yuv444p"))
            )
        except Exception as e:
            LOGGER.error(f"Error checking settings against profile: {e}")
            return False # Return False on error
    # --- End Profile Check Helper ---

    # +++ Settings Persistence Methods +++
    def loadSettings(self) -> None:
        """Load settings from QSettings and apply them to the UI."""
        LOGGER.info("Loading settings...")
        self._ffmpeg_setting_change_active = False # Disable profile switching during load
        settings = self.settings # Use the instance member
        self._geometry_restored = False # Flag to track if geometry was loaded

        # --- Window Geometry ---\
        geom = settings.value("window/geometry")
        if isinstance(geom, QByteArray): # QSettings might return QByteArray
             if self.restoreGeometry(geom): # restoreGeometry returns True on success
                 self._geometry_restored = True
                 LOGGER.debug("Restored window geometry.")
             else:
                 LOGGER.warning("Failed to restore window geometry from settings.")
        # REMOVED else block with fixed resize - will handle after loading if needed

        # --- Main Tab ---
        self.in_edit.setText(settings.value("main/inputDir", "", type=str))

        # --- Derive Default Output Path (DO NOT LOAD) ---
        input_dir_str = self.in_edit.text()
        # Use a fixed default name for simplicity, place in configured output dir
        out_dir = config.get_output_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        # Default base name (no timestamp)
        default_base_filename = "goes_timelapse.mp4"
        # Optionally, derive from input folder name if input_dir_str is valid
        # try:
        #     input_path = pathlib.Path(input_dir_str)
        #     if input_path.is_dir() and input_path.name:
        #         default_base_filename = f"{input_path.name}_timelapse.mp4"
        # except Exception:
        #     pass # Keep the fixed default if path is invalid

        default_path = out_dir / default_base_filename
        self.out_edit.setText(str(default_path)) # Set UI field to default
        self._base_output_path = default_path    # Set internal base path
        LOGGER.info(f"Derived default base output path: {self._base_output_path}")
        # --- End Derive Default Output Path ---

        self.fps_spin.setValue(settings.value("main/fps", 10, type=int))
        # self.mid_spin.setValue(settings.value("main/midFrames", 1, type=int)) # Moved to RIFE
        # self.model_combo.setCurrentText(settings.value("main/model", "RIFE v4.6 (default)", type=str)) # REMOVED
        # Ensure default encoder logic matches _makeMainTab if setting is missing/invalid
        default_encoder = "Software x265"
        available_encoders = [self.encode_combo.itemText(i) for i in range(self.encode_combo.count())]
        if "Hardware HEVC (VideoToolbox)" in available_encoders:
            default_encoder = "Hardware HEVC (VideoToolbox)"
        elif "Hardware H.264 (VideoToolbox)" in available_encoders:
            default_encoder = "Hardware H.264 (VideoToolbox)"
        self.encode_combo.setCurrentText(settings.value("main/encoder", default_encoder, type=str))
        # self.ffmpeg_interp_cb.setChecked(settings.value("main/useFFmpegInterp", True, type=bool)) # Moved to FFmpeg settings
        self.skip_model_cb.setChecked(settings.value("main/skipModel", False, type=bool))
        # Ensure default worker logic matches _makeMainTab if setting is missing
        import os
        cpu_cores = os.cpu_count() or 1
        default_workers = min(max(1, cpu_cores - 1), 8) # Default calc from _makeMainTab
        self.workers_spin.setValue(settings.value("main/maxWorkers", default_workers, type=int))
        # self.tile_checkbox.setChecked(settings.value("main/tilingEnabled", True, type=bool)) # Moved to RIFE

        # --- RIFE v4.6 Settings ---
        if hasattr(self, 'mid_spin'): self.mid_spin.setValue(settings.value("rife/intermediateFrames", 1, type=int))
        if hasattr(self, 'tile_checkbox'): self.tile_checkbox.setChecked(settings.value("rife/tilingEnabled", False, type=bool))
        if hasattr(self, 'tile_size_spin'): self.tile_size_spin.setValue(settings.value("rife/tileSize", 256, type=int))
        if hasattr(self, 'uhd_checkbox'): self.uhd_checkbox.setChecked(settings.value("rife/uhdMode", False, type=bool))
        if hasattr(self, 'thread_edit'): self.thread_edit.setText(settings.value("rife/threadSpec", "1:2:2", type=str))
        if hasattr(self, 'tta_spatial_cb'): self.tta_spatial_cb.setChecked(settings.value("rife/ttaSpatial", False, type=bool))
        if hasattr(self, 'tta_temporal_cb'): self.tta_temporal_cb.setChecked(settings.value("rife/ttaTemporal", False, type=bool))
        # Ensure tile size spinbox enabled state matches checkbox state after loading
        if hasattr(self, 'tile_checkbox') and hasattr(self, 'tile_size_spin'):
            self.tile_size_spin.setEnabled(self.tile_checkbox.isChecked())
        # Ensure RIFE group enabled state matches skip checkbox state
        if hasattr(self, 'skip_model_cb') and hasattr(self, 'rife_group'):
            self.rife_group.setEnabled(not self.skip_model_cb.isChecked())

        # --- FFmpeg Settings Tab ---
        # Load profile first, but don't apply it yet
        loaded_profile = settings.value("ffmpeg/profile", "Default", type=str)

        # Load individual settings (these will override profile defaults if profile is not "Custom")
        # Check existence of controls before loading into them
        if hasattr(self, 'ffmpeg_interp_cb'): self.ffmpeg_interp_cb.setChecked(settings.value("ffmpeg/enabled", True, type=bool))
        if hasattr(self, 'mi_combo'): self.mi_combo.setCurrentText(settings.value("ffmpeg/miMode", "mci", type=str))
        if hasattr(self, 'mc_combo'): self.mc_combo.setCurrentText(settings.value("ffmpeg/mcMode", "obmc", type=str))
        if hasattr(self, 'me_combo'): self.me_combo.setCurrentText(settings.value("ffmpeg/meMode", "bidir", type=str))
        if hasattr(self, 'me_algo_combo'): self.me_algo_combo.setCurrentText(settings.value("ffmpeg/meAlgo", "(default)", type=str))
        if hasattr(self, 'search_param_spin'): self.search_param_spin.setValue(settings.value("ffmpeg/searchParam", 96, type=int))
        if hasattr(self, 'scd_combo'): self.scd_combo.setCurrentText(settings.value("ffmpeg/scdMode", "fdiff", type=str))
        if hasattr(self, 'scd_thresh_spin'): self.scd_thresh_spin.setValue(settings.value("ffmpeg/scdThreshold", 10.0, type=float))
        if hasattr(self, 'filter_preset_combo'): self.filter_preset_combo.setCurrentText(settings.value("ffmpeg/filterPreset", "slow", type=str))
        if hasattr(self, 'mbsize_combo'): self.mbsize_combo.setCurrentText(settings.value("ffmpeg/mbSize", "(default)", type=str))
        if hasattr(self, 'vsbmc_cb'): self.vsbmc_cb.setChecked(settings.value("ffmpeg/vsbmc", False, type=bool))
        if hasattr(self, 'unsharp_cb'): self.unsharp_cb.setChecked(settings.value("ffmpeg/unsharpEnabled", True, type=bool))
        if hasattr(self, 'luma_x_spin'): self.luma_x_spin.setValue(settings.value("ffmpeg/unsharpLx", 7, type=int))
        if hasattr(self, 'luma_y_spin'): self.luma_y_spin.setValue(settings.value("ffmpeg/unsharpLy", 7, type=int))
        if hasattr(self, 'luma_amount_spin'): self.luma_amount_spin.setValue(settings.value("ffmpeg/unsharpLa", 1.0, type=float))
        if hasattr(self, 'chroma_x_spin'): self.chroma_x_spin.setValue(settings.value("ffmpeg/unsharpCx", 5, type=int))
        if hasattr(self, 'chroma_y_spin'): self.chroma_y_spin.setValue(settings.value("ffmpeg/unsharpCy", 5, type=int))
        if hasattr(self, 'chroma_amount_spin'): self.chroma_amount_spin.setValue(settings.value("ffmpeg/unsharpCa", 0.0, type=float))
        if hasattr(self, 'preset_combo'): self.preset_combo.setCurrentText(settings.value("ffmpeg/presetCRF", "Very High (CRF 16)", type=str))
        if hasattr(self, 'bitrate_spin'):
            default_bitrate = 15000
            saved_bitrate = settings.value("ffmpeg/bitrate", default_bitrate, type=int)
            self.bitrate_spin.setValue(saved_bitrate)
            if hasattr(self, 'bufsize_spin'):
                default_bufsize = int(saved_bitrate * 1.5)
                self.bufsize_spin.setValue(settings.value("ffmpeg/bufsize", default_bufsize, type=int))
        if hasattr(self, 'pixfmt_combo'): self.pixfmt_combo.setCurrentText(settings.value("ffmpeg/pixFmt", "yuv444p", type=str))

        # --- Load Collapsed State for Group Boxes ---
        if hasattr(self, 'minterpolate_group'):
            self.minterpolate_group.setChecked(settings.value("ffmpeg/minterpolateChecked", True, type=bool))
        if hasattr(self, 'unsharp_group'):
            self.unsharp_group.setChecked(settings.value("ffmpeg/unsharpChecked", True, type=bool))

        # --- Update content visibility based on loaded groupbox check state ---
        if hasattr(self, 'minterpolate_group') and hasattr(self, '_toggle_minterpolate_content'):
            self._toggle_minterpolate_content(self.minterpolate_group.isChecked())
        if hasattr(self, 'unsharp_group') and hasattr(self, '_toggle_unsharp_content'):
            self._toggle_unsharp_content(self.unsharp_group.isChecked())
        # --- End Content Visibility Update ---

        # --- Set Profile ComboBox *after* loading individual settings ---
        if hasattr(self, 'ffmpeg_profile_combo'):
            self.ffmpeg_profile_combo.blockSignals(True)
            self.ffmpeg_profile_combo.setCurrentText(loaded_profile)
            self.ffmpeg_profile_combo.blockSignals(False)

            # If the loaded profile was NOT custom, re-apply it to ensure consistency
            # Otherwise, check if current settings constitute "Custom"
            if loaded_profile != "Custom" and loaded_profile in FFMPEG_PROFILES:
                self._apply_ffmpeg_profile(loaded_profile) # Re-apply to make sure UI matches loaded profile
            else:
                 # Check if the loaded settings match any known profile
                 current_settings_match_profile = False
                 for name, prof_dict in FFMPEG_PROFILES.items():
                     if self._check_settings_match_profile(prof_dict):
                         self.ffmpeg_profile_combo.blockSignals(True)
                         self.ffmpeg_profile_combo.setCurrentText(name)
                         self.ffmpeg_profile_combo.blockSignals(False)
                         current_settings_match_profile = True
                         break
                 if not current_settings_match_profile:
                     self.ffmpeg_profile_combo.blockSignals(True)
                     self.ffmpeg_profile_combo.setCurrentText("Custom")
                     self.ffmpeg_profile_combo.blockSignals(False)

        # --- Load and Apply Collapsed State for Group Boxes (AFTER profile logic) ---
        if hasattr(self, 'minterpolate_group'):
            interp_checked = settings.value("ffmpeg/minterpolateChecked", True, type=bool)
            self.minterpolate_group.setChecked(interp_checked)
            if hasattr(self, '_toggle_minterpolate_content'):
                self._toggle_minterpolate_content(interp_checked)
        if hasattr(self, 'unsharp_group'):
            unsharp_checked = settings.value("ffmpeg/unsharpChecked", True, type=bool)
            self.unsharp_group.setChecked(unsharp_checked)
            if hasattr(self, '_toggle_unsharp_content'):
                self._toggle_unsharp_content(unsharp_checked)
        # --- End Group Box State Loading ---


        # --- Update UI state after loading ---\
        # Manually trigger state updates for dependent controls
        if hasattr(self, 'ffmpeg_interp_cb'):
            self._update_ffmpeg_controls_state(self.ffmpeg_interp_cb.isChecked()) # Handles interp/unsharp groups

        # --- Re-establish crucial UI connections AFTER loading all settings --- #
        LOGGER.debug("Re-establishing connections after loading settings...")
        # Tile Checkbox -> Tile Size Spinbox
        if hasattr(self, 'tile_checkbox') and hasattr(self, 'tile_size_spin'):
            LOGGER.debug("Reconnecting tile checkbox to toggle slot...")
            try: self.tile_checkbox.toggled.disconnect(self._toggle_tile_size_enabled)
            except TypeError: pass
            try: self.tile_checkbox.toggled.disconnect(self.tile_size_spin.setEnabled) # Old connection
            except TypeError: pass
            connection_success = self.tile_checkbox.toggled.connect(self._toggle_tile_size_enabled)
            LOGGER.debug(f"Tile checkbox reconnect success: {connection_success}")
            # Ensure state is correct *after* reconnecting
            self._toggle_tile_size_enabled(self.tile_checkbox.isChecked())

        # Skip AI Checkbox -> RIFE Group Enable
        if hasattr(self, 'skip_model_cb') and hasattr(self, 'rife_group'):
            LOGGER.debug("Reconnecting skip AI checkbox to RIFE group enable...")
            try: self.skip_model_cb.toggled.disconnect()
            except TypeError: pass # Disconnect all slots for this signal
            connection_success = self.skip_model_cb.toggled.connect(lambda checked: self.rife_group.setEnabled(not checked))
            LOGGER.debug(f"Skip AI checkbox reconnect success: {connection_success}")
            # Ensure state is correct *after* reconnecting
            self.rife_group.setEnabled(not self.skip_model_cb.isChecked())

        self._update_previews() # Load previews based on loaded input dir
        self._ffmpeg_setting_change_active = True # Re-enable profile switching
        LOGGER.info("Settings loaded.")

        # --- RIFE v4.6 Settings ---
        # Ensure RIFE group enabled state matches skip checkbox state
        if hasattr(self, 'skip_model_cb') and hasattr(self, 'rife_group'):
            self.rife_group.setEnabled(not self.skip_model_cb.isChecked())
        # Load Model Selection
        if hasattr(self, 'model_combo'):
            saved_model = settings.value("rife/modelName", "rife-v4.6", type=str)
            self.model_combo.setCurrentText(saved_model)
            # Ensure combo box is enabled if models were found
            if self.model_combo.count() > 0 and not self.model_combo.currentText().startswith("Error") and not self.model_combo.currentText().startswith("No models"):
                self.model_combo.setEnabled(True)
            else:
                self.model_combo.setEnabled(False)

        # --- FFmpeg Settings Tab ---
        # Load profile first, but don't apply it yet
        loaded_profile = settings.value("ffmpeg/profile", "Default", type=str)

        # Load individual settings (these will override profile defaults if profile is not "Custom")
        # Check existence of controls before loading into them
        if hasattr(self, 'ffmpeg_interp_cb'): self.ffmpeg_interp_cb.setChecked(settings.value("ffmpeg/enabled", True, type=bool))
        if hasattr(self, 'mi_combo'): self.mi_combo.setCurrentText(settings.value("ffmpeg/miMode", "mci", type=str))
        if hasattr(self, 'mc_combo'): self.mc_combo.setCurrentText(settings.value("ffmpeg/mcMode", "obmc", type=str))
        if hasattr(self, 'me_combo'): self.me_combo.setCurrentText(settings.value("ffmpeg/meMode", "bidir", type=str))
        if hasattr(self, 'me_algo_combo'): self.me_algo_combo.setCurrentText(settings.value("ffmpeg/meAlgo", "(default)", type=str))
        if hasattr(self, 'search_param_spin'): self.search_param_spin.setValue(settings.value("ffmpeg/searchParam", 96, type=int))
        if hasattr(self, 'scd_combo'): self.scd_combo.setCurrentText(settings.value("ffmpeg/scdMode", "fdiff", type=str))
        if hasattr(self, 'scd_thresh_spin'): self.scd_thresh_spin.setValue(settings.value("ffmpeg/scdThreshold", 10.0, type=float))
        if hasattr(self, 'filter_preset_combo'): self.filter_preset_combo.setCurrentText(settings.value("ffmpeg/filterPreset", "slow", type=str))
        if hasattr(self, 'mbsize_combo'): self.mbsize_combo.setCurrentText(settings.value("ffmpeg/mbSize", "(default)", type=str))
        if hasattr(self, 'vsbmc_cb'): self.vsbmc_cb.setChecked(settings.value("ffmpeg/vsbmc", False, type=bool))
        if hasattr(self, 'unsharp_cb'): self.unsharp_cb.setChecked(settings.value("ffmpeg/unsharpEnabled", True, type=bool))
        if hasattr(self, 'luma_x_spin'): self.luma_x_spin.setValue(settings.value("ffmpeg/unsharpLx", 7, type=int))
        if hasattr(self, 'luma_y_spin'): self.luma_y_spin.setValue(settings.value("ffmpeg/unsharpLy", 7, type=int))
        if hasattr(self, 'luma_amount_spin'): self.luma_amount_spin.setValue(settings.value("ffmpeg/unsharpLa", 1.0, type=float))
        if hasattr(self, 'chroma_x_spin'): self.chroma_x_spin.setValue(settings.value("ffmpeg/unsharpCx", 5, type=int))
        if hasattr(self, 'chroma_y_spin'): self.chroma_y_spin.setValue(settings.value("ffmpeg/unsharpCy", 5, type=int))
        if hasattr(self, 'chroma_amount_spin'): self.chroma_amount_spin.setValue(settings.value("ffmpeg/unsharpCa", 0.0, type=float))
        if hasattr(self, 'preset_combo'): self.preset_combo.setCurrentText(settings.value("ffmpeg/presetCRF", "Very High (CRF 16)", type=str))
        if hasattr(self, 'bitrate_spin'):
            default_bitrate = 15000
            saved_bitrate = settings.value("ffmpeg/bitrate", default_bitrate, type=int)
            self.bitrate_spin.setValue(saved_bitrate)
            if hasattr(self, 'bufsize_spin'):
                default_bufsize = int(saved_bitrate * 1.5)
                self.bufsize_spin.setValue(settings.value("ffmpeg/bufsize", default_bufsize, type=int))
        if hasattr(self, 'pixfmt_combo'): self.pixfmt_combo.setCurrentText(settings.value("ffmpeg/pixFmt", "yuv444p", type=str))

        # --- Load Collapsed State for Group Boxes ---
        if hasattr(self, 'minterpolate_group'):
            self.minterpolate_group.setChecked(settings.value("ffmpeg/minterpolateChecked", True, type=bool))
        if hasattr(self, 'unsharp_group'):
            self.unsharp_group.setChecked(settings.value("ffmpeg/unsharpChecked", True, type=bool))

        # --- Update content visibility based on loaded groupbox check state ---
        if hasattr(self, 'minterpolate_group') and hasattr(self, '_toggle_minterpolate_content'):
            self._toggle_minterpolate_content(self.minterpolate_group.isChecked())
        if hasattr(self, 'unsharp_group') and hasattr(self, '_toggle_unsharp_content'):
            self._toggle_unsharp_content(self.unsharp_group.isChecked())
        # --- End Content Visibility Update ---

        # --- Set Profile ComboBox *after* loading individual settings ---
        if hasattr(self, 'ffmpeg_profile_combo'):
            self.ffmpeg_profile_combo.blockSignals(True)
            self.ffmpeg_profile_combo.setCurrentText(loaded_profile)
            self.ffmpeg_profile_combo.blockSignals(False)

            # If the loaded profile was NOT custom, re-apply it to ensure consistency
            # Otherwise, check if current settings constitute "Custom"
            if loaded_profile != "Custom" and loaded_profile in FFMPEG_PROFILES:
                self._apply_ffmpeg_profile(loaded_profile) # Re-apply to make sure UI matches loaded profile
            else:
                 # Check if the loaded settings match any known profile
                 current_settings_match_profile = False
                 for name, prof_dict in FFMPEG_PROFILES.items():
                     if self._check_settings_match_profile(prof_dict):
                         self.ffmpeg_profile_combo.blockSignals(True)
                         self.ffmpeg_profile_combo.setCurrentText(name)
                         self.ffmpeg_profile_combo.blockSignals(False)
                         current_settings_match_profile = True
                         break
            self.tile_size_spin.setStyleSheet("") # Reset to default style
            # --- End style change --- #
        else:
            LOGGER.warning("tile_size_spin attribute not found in _toggle_tile_size_enabled")
    # --- End Slot ---

    # --- Slot to validate thread spec format ---
    def _validate_thread_spec(self, text: str) -> None:
        """Validate thread spec format using regex and update style."""
        if not hasattr(self, 'thread_edit'): return

        # Regex: 1+ digits, optionally followed by :digits up to two times
        valid_format = re.fullmatch(r'^\d+(?::\d+){0,2}$', text) # Added missing closing parenthesis
        if valid_format:
            self.thread_edit.setStyleSheet("") # Reset style
        else:
            # Indicate error with background color
            self.thread_edit.setStyleSheet("background-color: #ffdddd;") # Light red
    # --- End Slot ---

    # --- Populate Model Combo Box --- #
    def _populate_models(self) -> None:
        """Scan the models directory and populate the model combo box."""
        if not hasattr(self, 'model_combo'): return

        self.model_combo.clear() # Clear existing items
        models_dir = pathlib.Path("goesvfi/models")
        default_model = "rife-v4.6"
        models_found: List[str] = []

        if not models_dir.is_dir():
            LOGGER.error(f"Models directory not found: {models_dir}")
            self.model_combo.addItem(f"Error: Dir not found")
            self.model_combo.setEnabled(False)
            return

        try:
            for item in models_dir.iterdir():
                if item.is_dir() and item.name.startswith("rife-"):
                    # Add model name (e.g., "rife-v4.6")
                    models_found.append(item.name)

            if not models_found:
                LOGGER.warning(f"No RIFE models found in {models_dir}")
                self.model_combo.addItem("No models found")
                self.model_combo.setEnabled(False)
            else:
                models_found.sort() # Sort alphabetically
                self.model_combo.addItems(models_found)
                # Try to set default
                if default_model in models_found:
                    self.model_combo.setCurrentText(default_model)
                elif models_found: # Set first found as default otherwise
                    self.model_combo.setCurrentIndex(0)
                self.model_combo.setEnabled(True)

        except Exception as e:
            LOGGER.exception(f"Error scanning models directory: {models_dir}")
            self.model_combo.addItem(f"Error scanning models")
            self.model_combo.setEnabled(False)
    # --- End Populate --- #

# ────────────────────────── top‑level launcher ────────────────────────────
def main() -> None:
    # --- Add Argument Parsing --- #
    parser = argparse.ArgumentParser(description="GOES-VFI GUI")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    # Pass the parsed debug flag to the MainWindow
    win = MainWindow(debug_mode=args.debug)
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
