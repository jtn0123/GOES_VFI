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
import time # <-- Import time for time.sleep
import tempfile # Import tempfile for temporary files handling
import shutil # Import shutil for file operations
from typing import Optional, Any, cast, Union, Tuple, Iterator, Dict, List, TypedDict # Added Dict, List, cast, TypedDict
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QSize, QPoint, QRect, QSettings, QByteArray, QTimer, QUrl # Added QTimer, QUrl
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QProgressBar, QSpinBox, QVBoxLayout, QWidget,
    QMessageBox, QComboBox, QCheckBox, QTabWidget, QTableWidget, QTableWidgetItem, QStatusBar,
    QDialog, QDialogButtonBox, QRubberBand, QGridLayout, QDoubleSpinBox,
    QGroupBox, QSizePolicy, QSplitter, QScrollArea # Added GroupBox, SizePolicy, Splitter, ScrollArea
)
import pathlib
from PyQt6.QtGui import QPixmap, QMouseEvent, QCloseEvent, QImage, QPainter, QPen, QColor, QIcon, QDesktopServices # Added Image, Painter, Pen, Color, Icon, DesktopServices
import json # Import needed for pretty printing the dict
import logging
from pathlib import Path # Ensure Path is explicitly imported
import os # Import os for os.cpu_count()

# Correct import for find_rife_executable
from goesvfi.utils import config, log
from goesvfi.utils.gui_helpers import RifeCapabilityManager
from goesvfi.file_sorter.gui_tab import FileSorterTab
from goesvfi.date_sorter.gui_tab import DateSorterTab
from goesvfi.sanchez.runner import colourise # Import Sanchez colourise function

LOGGER = log.get_logger(__name__)

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
    crf: int # Added crf
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
    "crf": 16, # Added CRF value
    "bitrate": 15000,
    "bufsize": 22500, # Auto-calculated from bitrate
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
    "crf": 20, # Added CRF value
    "bitrate": 10000,           # Lowered bitrate example
    "bufsize": 15000,           # Lowered bufsize (1.5*bitrate)
    "pix_fmt": "yuv444p",       # Keep high quality format
    # Filter Preset (Intermediate step)
    "filter_preset": "medium",      # Match final preset level choice
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
    "apply_unsharp": True, # <-- Key for groupbox check state
    "unsharp_lx": 7,
    "unsharp_ly": 7,
    "unsharp_la": 1.0,
    "unsharp_cx": 5,
    "unsharp_cy": 5,
    "unsharp_ca": 0.0,
    # Quality
    "preset_text": "Very High (CRF 16)",
    "crf": 16, # Added CRF value
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

# Commented out as it seems unused and might cause type issues if FfmpegProfile changes
# OPTIMAL_FFMPEG_INTERP_SETTINGS = {
#     "mi_mode": OPTIMAL_FFMPEG_PROFILE["mi_mode"],
#     "mc_mode": OPTIMAL_FFMPEG_PROFILE["mc_mode"],
#     "me_mode": OPTIMAL_FFMPEG_PROFILE["me_mode"],
#     "vsbmc": "1" if OPTIMAL_FFMPEG_PROFILE["vsbmc"] else "0",
#     "scd": OPTIMAL_FFMPEG_PROFILE["scd"]
# }


# ─── Custom clickable label ────────────────────────────────────────────────
class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.file_path: str | None = None # Original file path
        self.processed_image: QImage | None = None # Store processed version
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
        model_key: str,
        # --- Add Sanchez Args ---
        false_colour: bool,
        res_km: int,
        # -----------------------
    ) -> None:
        super().__init__()
        self.in_dir = in_dir
        self.out_file_path = out_file_path
        self.fps = fps
        self.mid_count = mid_count
        self.max_workers = max_workers
        self.encoder = encoder
        # Store FFmpeg settings
        self.use_ffmpeg_interp = use_ffmpeg_interp
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
        # Unsharp
        self.apply_unsharp = apply_unsharp
        self.unsharp_lx = unsharp_lx
        self.unsharp_ly = unsharp_ly
        self.unsharp_la = unsharp_la
        self.unsharp_cx = unsharp_cx
        self.unsharp_cy = unsharp_cy
        self.unsharp_ca = unsharp_ca
        # Quality
        self.crf = crf
        self.bitrate_kbps = bitrate_kbps
        self.bufsize_kb = bufsize_kb
        self.pix_fmt = pix_fmt
        # Other
        self.skip_model = skip_model
        self.crop_rect = crop_rect
        self.debug_mode = debug_mode
        # Store RIFE v4.6 settings
        self.model_key = model_key
        self.rife_tile_enable = rife_tile_enable
        self.rife_tile_size = rife_tile_size
        self.rife_uhd_mode = rife_uhd_mode
        self.rife_thread_spec = rife_thread_spec
        self.rife_tta_spatial = rife_tta_spatial
        self.rife_tta_temporal = rife_tta_temporal
        # --- Store Sanchez Args ---
        self.false_colour = false_colour
        self.res_km = res_km
        # ------------------------

    def run(self) -> None:
        try:
            # Define rife_exe variable with potential None type first
            rife_exe: Optional[pathlib.Path] = None

            # Determine RIFE executable path
            if self.encoder == 'RIFE':
                # Locate RIFE CLI executable using config helper
                try:
                    rife_exe = config.find_rife_executable(self.model_key)
                except FileNotFoundError as e:
                    LOGGER.error(f"RIFE executable not found: {e}")
                    self.error.emit(str(e))
                    return
            elif self.encoder == 'FFmpeg':
                pass # rife_exe remains None
            else:
                raise ValueError(f"Unsupported encoder selected: {self.encoder}")

            # --- Proceed based on encoder ---

            if self.encoder == 'RIFE':
                # Type check: Ensure rife_exe is not None before calling run_vfi
                if rife_exe is None:
                    # This should theoretically not happen if logic above is correct
                    err_msg = "RIFE encoder selected, but executable path is None."
                    LOGGER.critical(err_msg)
                    self.error.emit(err_msg)
                    return

                from goesvfi.pipeline.run_vfi import run_vfi
                # --- Run RIFE pipeline ---
                gen = run_vfi(
                    folder=self.in_dir,
                    output_mp4_path=self.out_file_path,
                    rife_exe_path=rife_exe, # Pass the found path
                    fps=self.fps,
                    num_intermediate_frames=self.mid_count,
                    max_workers=self.max_workers,
                    skip_model=self.skip_model,
                    crop_rect_xywh=self.crop_rect,
                    # Pass RIFE v4.6 settings
                    rife_tile_enable=self.rife_tile_enable,
                    rife_tile_size=self.rife_tile_size,
                    rife_uhd_mode=self.rife_uhd_mode,
                    rife_thread_spec=self.rife_thread_spec,
                    rife_tta_spatial=self.rife_tta_spatial,
                    rife_tta_temporal=self.rife_tta_temporal,
                    model_key=self.model_key,
                    # --- Pass Sanchez Args ---
                    false_colour=self.false_colour, # Correct attribute name
                    res_km=self.res_km,
                    # ------------------------
                )
                raw_video_path: pathlib.Path | None = None
                for item in gen:
                    if isinstance(item, pathlib.Path):
                        raw_video_path = item
                    elif isinstance(item, tuple):
                        current, total, eta = item
                        self.progress.emit(current, total, eta)
                    else:
                        LOGGER.warning(f"Unexpected item yielded from run_vfi: {item}")

                if not raw_video_path or not raw_video_path.exists():
                     raise RuntimeError("RIFE pipeline finished but did not produce a raw video file.")

                # Rename raw output to final requested name
                if raw_video_path.exists() and raw_video_path != self.out_file_path:
                     LOGGER.info(f"Renaming raw output {raw_video_path.name} to {self.out_file_path.name}")
                     try:
                         raw_video_path.rename(self.out_file_path)
                         self.finished.emit(self.out_file_path)
                     except OSError as e:
                         raise RuntimeError(f"Failed to rename {raw_video_path} to {self.out_file_path}: {e}") from e
                elif raw_video_path == self.out_file_path:
                    self.finished.emit(self.out_file_path)
                else:
                    raise RuntimeError("Raw video file missing after RIFE pipeline completion.")

            elif self.encoder == 'FFmpeg':
                from goesvfi.pipeline.run_ffmpeg import run_ffmpeg_interpolation
                # --- Run FFmpeg pipeline ---
                try:
                    final_mp4_path = run_ffmpeg_interpolation(
                        input_dir=self.in_dir,
                        output_mp4_path=self.out_file_path,
                        fps=self.fps,
                        num_intermediate_frames=self.mid_count,
                        crop_rect=self.crop_rect,
                        # Pass FFmpeg settings
                        use_ffmpeg_interp=self.use_ffmpeg_interp,
                        filter_preset=self.filter_preset,
                        mi_mode=self.mi_mode,
                        mc_mode=self.mc_mode,
                        me_mode=self.me_mode,
                        me_algo=self.me_algo,
                        search_param=self.search_param,
                        scd_mode=self.scd_mode,
                        scd_threshold=self.scd_threshold,
                        minter_mb_size=self.minter_mb_size,
                        minter_vsbmc=self.minter_vsbmc,
                        # Unsharp
                        apply_unsharp=self.apply_unsharp,
                        unsharp_lx=self.unsharp_lx,
                        unsharp_ly=self.unsharp_ly,
                        unsharp_la=self.unsharp_la,
                        unsharp_cx=self.unsharp_cx,
                        unsharp_cy=self.unsharp_cy,
                        unsharp_ca=self.unsharp_ca,
                        # Quality
                        crf=self.crf,
                        bitrate_kbps=self.bitrate_kbps,
                        bufsize_kb=self.bufsize_kb,
                        pix_fmt=self.pix_fmt,
                        # Missing args from function definition:
                        use_preset_optimal=False, # Assuming False as default
                        debug_mode=self.debug_mode
                    )
                    self.finished.emit(final_mp4_path)
                except Exception as e:
                    LOGGER.exception(f"FFmpeg interpolation failed: {e}")
                    self.error.emit(f"FFmpeg interpolation failed: {e}")
                    return

        except Exception as e:
            LOGGER.exception(f"VFI process failed: {e}") # Log full traceback
            self.error.emit(f"VFI process failed: {e}")

# ────────────────────────────── Main Window ──────────────────────────────
class MainWindow(QWidget):
    request_previews_update = pyqtSignal() # Signal to trigger preview update

    def __init__(self, debug_mode: bool = False) -> None:
        """Initializes the main application window."""
        super().__init__()
        self.debug_mode = debug_mode
        self.setWindowTitle("GOES-VFI GUI")
        self.setGeometry(100, 100, 800, 600) # Initial window size

        self.settings = QSettings("GOES-VFI", "GUI")

        self.worker: Optional[VfiWorker] = None
        self.is_processing = False
        self.current_crop_rect: tuple[int, int, int, int] | None = None # Store crop rect as (x, y, w, h)

        # Instantiate capability manager
        self.rife_capability_manager = RifeCapabilityManager()

        # Instantiate File Sorter Tab
        self.file_sorter_tab = FileSorterTab()

        # Instantiate Date Sorter Tab
        self.date_sorter_tab = DateSorterTab()

        # Create the main tab widget
        self.main_tabs = QTabWidget()

        # Create the "VFI Process" tab (existing controls)
        vfi_process_tab = QWidget()
        vfi_process_layout = QVBoxLayout(vfi_process_tab)

        # --- UI Elements (Moved from original __init__) ---
        # Input/Output
        self.in_dir_label = QLabel("Input Directory:")
        self.in_dir_edit = QLineEdit()
        self.in_dir_button = QPushButton("Browse...")

        self.out_file_label = QLabel("Output File (MP4):")
        self.out_file_edit = QLineEdit()
        self.out_file_button = QPushButton("Browse...")

        # Interpolation Settings
        self.fps_label = QLabel("Output FPS:")
        self.fps_spinbox = QSpinBox()
        self.fps_spinbox.setRange(1, 120)
        self.fps_spinbox.setValue(30)

        self.mid_count_label = QLabel("Intermediate Frames:")
        self.mid_count_spinbox = QSpinBox()
        self.mid_count_spinbox.setRange(0, 100)
        self.mid_count_spinbox.setValue(7) # Default for 8x interpolation

        # Add Max Workers Spinbox
        self.max_workers_label = QLabel("Max Workers:")
        self.max_workers_spinbox = QSpinBox()
        self.max_workers_spinbox.setRange(1, os.cpu_count() or 4) # Range from 1 to num CPUs
        self.max_workers_spinbox.setValue(4) # Default value

        # Encoder Selection
        self.encoder_label = QLabel("Encoder:")
        self.encoder_combo = QComboBox()
        self.encoder_combo.addItems(["RIFE", "FFmpeg"]) # Add FFmpeg option

        # RIFE Model Selection (Only visible if RIFE is selected)
        self.model_label = QLabel("RIFE Model:")
        self.model_combo = QComboBox()
        self.model_combo.setEnabled(False) # Disabled until models are populated

        # RIFE v4.6 Specific Options GroupBox
        self.rife_options_groupbox = QGroupBox("RIFE v4.6 Options")
        self.rife_options_groupbox.setCheckable(False) # Not checkable
        rife_options_layout = QGridLayout(self.rife_options_groupbox)

        self.rife_tile_enable_checkbox = QCheckBox("Enable Tiling")
        self.rife_tile_enable_checkbox.setChecked(True) # Default to enabled
        self.rife_tile_size_label = QLabel("Tile Size:")
        self.rife_tile_size_spinbox = QSpinBox()
        self.rife_tile_size_spinbox.setRange(32, 2048)
        self.rife_tile_size_spinbox.setSingleStep(32)
        self.rife_tile_size_spinbox.setValue(384) # Default tile size
        self.rife_tile_size_spinbox.setEnabled(True) # Enabled by default

        self.rife_uhd_mode_checkbox = QCheckBox("UHD Mode (for > 4K)")
        self.rife_uhd_mode_checkbox.setChecked(False) # Default to disabled

        self.rife_thread_spec_label = QLabel("Thread Spec:")
        self.rife_thread_spec_edit = QLineEdit("0:0:0:0") # Default thread spec
        self.rife_thread_spec_edit.setPlaceholderText("e.g., 0:0:0:0 or 1:1:1:1")
        self.rife_thread_spec_edit.setToolTip("Specify threads for [encoder]:[decoder]:[pre]:[post]. 0 means auto.")

        self.rife_tta_spatial_checkbox = QCheckBox("TTA Spatial")
        self.rife_tta_spatial_checkbox.setChecked(False)

        self.rife_tta_temporal_checkbox = QCheckBox("TTA Temporal")
        self.rife_tta_temporal_checkbox.setChecked(False)

        rife_options_layout.addWidget(self.rife_tile_enable_checkbox, 0, 0)
        rife_options_layout.addWidget(self.rife_tile_size_label, 0, 1)
        rife_options_layout.addWidget(self.rife_tile_size_spinbox, 0, 2)
        rife_options_layout.addWidget(self.rife_uhd_mode_checkbox, 1, 0)
        rife_options_layout.addWidget(self.rife_thread_spec_label, 2, 0)
        rife_options_layout.addWidget(self.rife_thread_spec_edit, 2, 1, 1, 2) # Span 2 columns
        rife_options_layout.addWidget(self.rife_tta_spatial_checkbox, 3, 0)
        rife_options_layout.addWidget(self.rife_tta_temporal_checkbox, 3, 1)
        rife_options_layout.setColumnStretch(2, 1) # Give the last column stretch

        self.model_combo = QComboBox()
        self.model_combo.setEnabled(False) # Disabled until models are populated

        # Sanchez Options GroupBox
        self.sanchez_options_groupbox = QGroupBox("Sanchez Options")
        self.sanchez_options_groupbox.setCheckable(False) # Not checkable
        sanchez_options_layout = QGridLayout(self.sanchez_options_groupbox)

        self.sanchez_false_colour_checkbox = QCheckBox("Apply False Colour")
        self.sanchez_false_colour_checkbox.setChecked(False) # Default to disabled

        self.sanchez_res_km_label = QLabel("Resolution (km):")
        self.sanchez_res_km_spinbox = QSpinBox()
        self.sanchez_res_km_spinbox.setRange(1, 1000) # Example range
        self.sanchez_res_km_spinbox.setValue(500) # Example default
        self.sanchez_res_km_spinbox.setEnabled(False) # Disabled by default

        sanchez_options_layout.addWidget(self.sanchez_false_colour_checkbox, 0, 0)
        sanchez_options_layout.addWidget(self.sanchez_res_km_label, 0, 1)
        sanchez_options_layout.addWidget(self.sanchez_res_km_spinbox, 0, 2)
        sanchez_options_layout.setColumnStretch(2, 1)

        # FFmpeg Settings Tab (Moved from _make_ffmpeg_settings_tab)
        # Create and assign the FFmpeg tab attribute
        self.ffmpeg_settings_tab = self._make_ffmpeg_settings_tab()

        # Previews
        self.preview_label_1 = ClickableLabel("Preview 1 (First)")
        self.preview_label_mid = ClickableLabel("Preview 2 (Middle)") # Added middle label
        self.preview_label_2 = ClickableLabel("Preview 3 (Last)") # Renamed last label
        
        # Set consistent alignment for all labels
        self.preview_label_1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label_mid.setAlignment(Qt.AlignmentFlag.AlignCenter) # Align middle
        self.preview_label_2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Set expanding size policy for all labels
        policy = QSizePolicy.Policy.Expanding # Use Expanding policy
        self.preview_label_1.setSizePolicy(policy, policy)
        self.preview_label_mid.setSizePolicy(policy, policy) # Set policy for middle
        self.preview_label_2.setSizePolicy(policy, policy)
        
        # Set minimum and fixed sizes to ensure consistency
        min_size = 200
        # Set minimum sizes to ensure labels don't collapse
        self.preview_label_1.setMinimumSize(min_size, min_size)
        self.preview_label_mid.setMinimumSize(min_size, min_size)
        self.preview_label_2.setMinimumSize(min_size, min_size)

        # Crop Button
        self.crop_button = QPushButton("Select Crop Region")
        self.clear_crop_button = QPushButton("Clear Crop")
        self.clear_crop_button.setEnabled(False) # Disabled initially

        # Start Button
        self.start_button = QPushButton("Start VFI")
        self.start_button.setEnabled(False) # Disabled initially

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)

        # Status Bar (using QLabel for simplicity in QWidget)
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Open in VLC Button
        self.open_vlc_button = QPushButton("Open Output in VLC")
        self.open_vlc_button.setEnabled(False) # Disabled initially

        # --- Layouts (Moved from original __init__) ---
        # Input/Output Layout
        io_layout = QGridLayout()
        io_layout.addWidget(self.in_dir_label, 0, 0)
        io_layout.addWidget(self.in_dir_edit, 0, 1)
        io_layout.addWidget(self.in_dir_button, 0, 2)
        io_layout.addWidget(self.out_file_label, 1, 0)
        io_layout.addWidget(self.out_file_edit, 1, 1)
        io_layout.addWidget(self.out_file_button, 1, 2)
        io_layout.setColumnStretch(1, 1) # Give the line edits stretch

        # Interpolation Settings Layout
        interp_layout = QHBoxLayout()
        interp_layout.addWidget(self.fps_label)
        interp_layout.addWidget(self.fps_spinbox)
        interp_layout.addStretch(1) # Add stretch to push elements left
        interp_layout.addWidget(self.mid_count_label)
        interp_layout.addWidget(self.mid_count_spinbox)
        interp_layout.addStretch(1)
        interp_layout.addWidget(self.encoder_label)
        interp_layout.addWidget(self.encoder_combo)
        interp_layout.addStretch(1)
        interp_layout.addWidget(self.model_label)
        interp_layout.addWidget(self.model_combo)
        interp_layout.addStretch(1)
        interp_layout.addWidget(self.max_workers_label) # Add Max Workers
        interp_layout.addWidget(self.max_workers_spinbox)
        interp_layout.addStretch(1)

        # Options Layout (RIFE and Sanchez GroupBoxes)
        options_layout = QHBoxLayout()
        options_layout.addWidget(self.rife_options_groupbox)
        options_layout.addWidget(self.sanchez_options_groupbox)
        options_layout.addStretch(1)

        # Previews Layout (using QSplitter for resizable previews)
        preview_splitter = QSplitter(Qt.Orientation.Horizontal)
        preview_splitter.addWidget(self.preview_label_1)
        preview_splitter.addWidget(self.preview_label_mid) # Add middle label to splitter
        preview_splitter.addWidget(self.preview_label_2)
        
        # Set equal stretch factors for all labels
        preview_splitter.setStretchFactor(0, 1) # Give all equal stretch
        preview_splitter.setStretchFactor(1, 1)
        preview_splitter.setStretchFactor(2, 1) # Stretch for middle label
        
        # Set uniform sizes to force equal distribution at startup
        # Calculate available width (estimate based on window size)
        screen_width = 800  # Reasonable default
        screen = QApplication.primaryScreen()
        if screen:
            screen_width = int(screen.availableGeometry().width() * 0.8)  # 80% of screen width
        
        # Calculate size per widget (accounting for some margin/padding)
        widget_width = (screen_width - 100) // 3
        
        # Set sizes explicitly to ensure uniformity
        sizes = [widget_width, widget_width, widget_width]
        preview_splitter.setSizes(sizes)
        
        # Disable handle movement to prevent user from resizing
        preview_splitter.setHandleWidth(1) # Minimum handle width

        # Crop Buttons Layout
        crop_buttons_layout = QHBoxLayout()
        crop_buttons_layout.addWidget(self.crop_button)
        crop_buttons_layout.addWidget(self.clear_crop_button)
        crop_buttons_layout.addStretch(1)

        # Start Button Layout
        start_button_layout = QHBoxLayout()
        start_button_layout.addWidget(self.start_button)
        start_button_layout.addStretch(1)

        # VLC Button Layout
        vlc_button_layout = QHBoxLayout()
        vlc_button_layout.addWidget(self.open_vlc_button)
        vlc_button_layout.addStretch(1)

        # Add widgets to the VFI Process tab layout
        vfi_process_layout.addLayout(io_layout)
        vfi_process_layout.addLayout(interp_layout)
        vfi_process_layout.addLayout(options_layout)
        vfi_process_layout.addWidget(preview_splitter, 1) # Give the splitter a stretch factor
        vfi_process_layout.addLayout(crop_buttons_layout)
        vfi_process_layout.addLayout(start_button_layout)
        vfi_process_layout.addWidget(self.progress_bar)
        vfi_process_layout.addWidget(self.status_label)
        vfi_process_layout.addLayout(vlc_button_layout)

        # Add the VFI Process tab and FFmpeg Settings tab to the main tab widget
        self.main_tabs.addTab(vfi_process_tab, "VFI Process")
        self.main_tabs.addTab(self.ffmpeg_settings_tab, "FFmpeg Settings")

        # Add the "File Sorter" tab
        # self.file_sorter_tab was instantiated earlier
        # TEMP: Comment out adding extra tabs for testing
        # self.main_tabs.addTab(self.file_sorter_tab, "File Sorter")
        self.main_tabs.addTab(self.file_sorter_tab, "File Sorter")

        # Add the "Date Sorter" tab
        # self.date_sorter_tab was instantiated earlier
        self.main_tabs.addTab(self.date_sorter_tab, "Date Sorter")

        # Create and add the Model Library tab
        self.model_library_tab = self._makeModelLibraryTab() # Create the tab first
        self.main_tabs.addTab(self.model_library_tab, "Model Library")


        # Set the main layout of the MainWindow to the tab widget
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.main_tabs)

        # Populate models *after* all UI elements are created
        self._populate_models()

        # --- Connections ---
        self.in_dir_button.clicked.connect(self._pick_in_dir)
        self.out_file_button.clicked.connect(self._pick_out_file)
        self.start_button.clicked.connect(self._start)
        self.open_vlc_button.clicked.connect(self._open_in_vlc)
        self.crop_button.clicked.connect(self._on_crop_clicked)
        self.clear_crop_button.clicked.connect(self._on_clear_crop_clicked)

        # Connect signals for preview updates to the new intermediate slot
        self.in_dir_edit.textChanged.connect(self._trigger_preview_update)
        self.sanchez_false_colour_checkbox.stateChanged.connect(self._trigger_preview_update)
        self.sanchez_res_km_spinbox.valueChanged.connect(lambda: self._trigger_preview_update())

        # Connect signals for preview zooming
        self.preview_label_1.clicked.connect(lambda: self._show_zoom(self.preview_label_1))
        self.preview_label_mid.clicked.connect(lambda: self._show_zoom(self.preview_label_mid)) # Connect middle label
        self.preview_label_2.clicked.connect(lambda: self._show_zoom(self.preview_label_2))

        # Connect signals for updating start button state
        self.in_dir_edit.textChanged.connect(self._update_start_button_state)
        self.out_file_edit.textChanged.connect(self._update_start_button_state)
        self.encoder_combo.currentTextChanged.connect(self._update_start_button_state)
        self.model_combo.currentTextChanged.connect(self._update_start_button_state)

        # Connect signals for updating crop buttons state
        self.in_dir_edit.textChanged.connect(self._update_crop_buttons_state)

        # Connect signals for updating RIFE options state based on encoder
        self.encoder_combo.currentTextChanged.connect(self._update_rife_options_state)

        # Connect signals for RIFE v4.6 options
        self.rife_tile_enable_checkbox.stateChanged.connect(self._toggle_tile_size_enabled)
        self.rife_thread_spec_edit.textChanged.connect(self._validate_thread_spec)

        # Connect signals for Sanchez options
        self.sanchez_false_colour_checkbox.stateChanged.connect(self._toggle_sanchez_res_enabled)

        # Connect signals for FFmpeg settings tab (moved to a separate method)
        self._connect_ffmpeg_settings_tab_signals()

        # Connect signal for tab changes to potentially update UI elements
        self.main_tabs.currentChanged.connect(self._on_tab_changed)

        # Connect signal for model combo box changes
        self._connect_model_combo()

        # Load saved settings
        self.loadSettings()

        # Initial state updates AFTER loading settings
        self._update_rife_options_state(self.encoder_combo.currentText()) # Update based on initial/loaded encoder
        # _update_rife_options_state now calls _toggle_sanchez_res_enabled and _update_ffmpeg_controls_state
        # self._toggle_sanchez_res_enabled(self.sanchez_false_colour_checkbox.checkState()) # Called by _update_rife_options_state
        # self._update_ffmpeg_controls_state(self.encoder_combo.currentText() == 'FFmpeg') # Called by _update_rife_options_state
        self._update_unsharp_controls_state(self.unsharp_groupbox.isChecked()) # Update unsharp controls state
        self._update_scd_thresh_state(self.ffmpeg_scd_combo.currentText()) # Update scd threshold state
        self._update_quality_controls_state("FFmpeg", self.ffmpeg_quality_preset_combo.currentText()) # Update quality controls state
        self._update_start_button_state() # Explicitly update start/VLC button state
        self._update_crop_buttons_state() # Explicitly update crop button state

        # Set up a timer to trigger preview updates periodically or when requested
        self.preview_timer = QTimer(self)
        self.preview_timer.setInterval(5000) # Update every 5 seconds (adjust as needed)
        self.preview_timer.timeout.connect(self._update_previews)
        # Connect the signal itself to the actual update method
        self.request_previews_update.connect(self._update_previews)
        # REMOVED redundant check before connecting the signal
        # self.preview_timer.start() # Don't start timer initially, rely on signals

        # Trigger initial preview update after UI is shown and sized
        QTimer.singleShot(100, self.request_previews_update.emit)

    def _trigger_preview_update(self, *args: Any) -> None: # Accept arbitrary args from signals
        """Slot to emit the request_previews_update signal."""
        self.request_previews_update.emit()

    def _adjust_window_to_content(self) -> None:
        """Adjusts the window size to fit its content."""
        self.adjustSize()

    def _pick_in_dir(self) -> None:
        """Opens a dialog to select the input directory."""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Input Directory")
        if dir_path:
            self.in_dir_edit.setText(dir_path)

    def _pick_out_file(self) -> None:
        """Opens a dialog to select the output file path."""
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Output File", "", "MP4 Files (*.mp4);;All Files (*)")
        if file_path:
            self.out_file_edit.setText(file_path)

    def _on_crop_clicked(self) -> None:
        """Opens the crop dialog to select a region."""
        # Use the first preview label's file path to load the original image
        if not self.preview_label_1.file_path:
            QMessageBox.warning(self, "Crop Error", "Load input images first to select a crop region (ensure Preview 1 is loaded).")
            return

        try:
            # Load the original, unprocessed image for cropping
            pixmap_to_crop = QPixmap(self.preview_label_1.file_path)
            if pixmap_to_crop.isNull():
                 QMessageBox.warning(self, "Crop Error", f"Failed to load image for cropping:\n{self.preview_label_1.file_path}")
                 return
        except Exception as e:
            LOGGER.error(f"Error loading image for crop dialog: {e}")
            QMessageBox.critical(self, "Crop Error", f"Could not load image for cropping:\n{e}")
            return

        dialog = CropDialog(pixmap_to_crop, self.current_crop_rect, self) # Pass QPixmap directly
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_rect = dialog.getRect()
            if selected_rect.width() > 0 and selected_rect.height() > 0:
                self.current_crop_rect = (
                    selected_rect.x(),
                    selected_rect.y(),
                    selected_rect.width(),
                    selected_rect.height()
                )
                LOGGER.info(f"Crop region selected: {self.current_crop_rect}")
                self.clear_crop_button.setEnabled(True) # Enable clear button
                self.request_previews_update.emit() # Update previews with crop
            else:
                # If an invalid (empty) rect was selected, clear the crop
                self._on_clear_crop_clicked()

    def _makeMainTab(self) -> QWidget:
        """Creates the main VFI processing tab."""
        # This method is likely a remnant and not used for the primary layout anymore
        # The main layout is built directly in __init__ now.
        # Keeping it for now in case it's referenced elsewhere, but it's not
        # where the main UI is constructed in the current version.
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("This is a placeholder tab."))
        return tab

    def _make_ffmpeg_settings_tab(self) -> QWidget:
        """Creates the FFmpeg settings tab."""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)

        # --- Profile Selection ---
        profile_layout = QHBoxLayout()
        profile_layout.addWidget(QLabel("FFmpeg Settings Profile:"))
        self.ffmpeg_profile_combo = QComboBox()
        self.ffmpeg_profile_combo.addItems(list(FFMPEG_PROFILES.keys()))
        self.ffmpeg_profile_combo.addItem("Custom") # Add Custom option
        profile_layout.addWidget(self.ffmpeg_profile_combo)
        profile_layout.addStretch(1)
        main_layout.addLayout(profile_layout)

        # --- Interpolation Group ---
        interp_group = QGroupBox("Interpolation (minterpolate)")
        interp_group.setCheckable(True) # Make it checkable
        self.ffmpeg_interp_group = interp_group # Store reference
        interp_layout = QGridLayout(interp_group)

        self.ffmpeg_mi_mode_label = QLabel("MI Mode:")
        self.ffmpeg_mi_mode_combo = QComboBox()
        self.ffmpeg_mi_mode_combo.addItems(["dup", "blend", "mci"])
        interp_layout.addWidget(self.ffmpeg_mi_mode_label, 0, 0)
        interp_layout.addWidget(self.ffmpeg_mi_mode_combo, 0, 1)

        self.ffmpeg_mc_mode_label = QLabel("MC Mode:")
        self.ffmpeg_mc_mode_combo = QComboBox()
        self.ffmpeg_mc_mode_combo.addItems(["obmc", "aobmc"])
        interp_layout.addWidget(self.ffmpeg_mc_mode_label, 1, 0)
        interp_layout.addWidget(self.ffmpeg_mc_mode_combo, 1, 1)

        self.ffmpeg_me_mode_label = QLabel("ME Mode:")
        self.ffmpeg_me_mode_combo = QComboBox()
        self.ffmpeg_me_mode_combo.addItems(["bidir", "bilat"])
        interp_layout.addWidget(self.ffmpeg_me_mode_label, 2, 0)
        interp_layout.addWidget(self.ffmpeg_me_mode_combo, 2, 1)

        self.ffmpeg_me_algo_label = QLabel("ME Algorithm:")
        self.ffmpeg_me_algo_combo = QComboBox()
        self.ffmpeg_me_algo_combo.addItems(["(default)", "esa", "tss", "tdls", "ntss", "fss", "ds", "hexbs", "epzs", "umh"])
        interp_layout.addWidget(self.ffmpeg_me_algo_label, 0, 2)
        interp_layout.addWidget(self.ffmpeg_me_algo_combo, 0, 3)

        self.ffmpeg_search_param_label = QLabel("Search Param:")
        self.ffmpeg_search_param_spinbox = QSpinBox()
        self.ffmpeg_search_param_spinbox.setRange(4, 128) # Example range
        interp_layout.addWidget(self.ffmpeg_search_param_label, 1, 2)
        interp_layout.addWidget(self.ffmpeg_search_param_spinbox, 1, 3)

        self.ffmpeg_vsbmc_checkbox = QCheckBox("VSBMC")
        interp_layout.addWidget(self.ffmpeg_vsbmc_checkbox, 2, 2)

        self.ffmpeg_scd_label = QLabel("Scene Change Detection:")
        self.ffmpeg_scd_combo = QComboBox()
        self.ffmpeg_scd_combo.addItems(["none", "fdiff"])
        interp_layout.addWidget(self.ffmpeg_scd_label, 3, 0)
        interp_layout.addWidget(self.ffmpeg_scd_combo, 3, 1)

        self.ffmpeg_scd_thresh_label = QLabel("SCD Threshold (%):")
        self.ffmpeg_scd_thresh_spinbox = QDoubleSpinBox()
        self.ffmpeg_scd_thresh_spinbox.setRange(0.0, 100.0)
        self.ffmpeg_scd_thresh_spinbox.setDecimals(1)
        self.ffmpeg_scd_thresh_spinbox.setSingleStep(0.5)
        interp_layout.addWidget(self.ffmpeg_scd_thresh_label, 3, 2)
        interp_layout.addWidget(self.ffmpeg_scd_thresh_spinbox, 3, 3)

        self.ffmpeg_mb_size_label = QLabel("Macroblock Size:")
        self.ffmpeg_mb_size_combo = QComboBox()
        self.ffmpeg_mb_size_combo.addItems(["(default)", "8", "16"]) # Common values
        interp_layout.addWidget(self.ffmpeg_mb_size_label, 4, 0)
        interp_layout.addWidget(self.ffmpeg_mb_size_combo, 4, 1)

        interp_layout.setColumnStretch(1, 1)
        interp_layout.setColumnStretch(3, 1)
        main_layout.addWidget(interp_group)

        # --- Unsharp Filter Group ---
        unsharp_group = QGroupBox("Sharpening (unsharp)")
        unsharp_group.setCheckable(True)
        self.unsharp_groupbox = unsharp_group # Store reference
        unsharp_layout = QGridLayout(unsharp_group)

        unsharp_layout.addWidget(QLabel("Luma X:"), 0, 0)
        self.unsharp_lx_spinbox = QSpinBox()
        self.unsharp_lx_spinbox.setRange(3, 23)
        self.unsharp_lx_spinbox.setSingleStep(2)
        unsharp_layout.addWidget(self.unsharp_lx_spinbox, 0, 1)

        unsharp_layout.addWidget(QLabel("Luma Y:"), 0, 2)
        self.unsharp_ly_spinbox = QSpinBox()
        self.unsharp_ly_spinbox.setRange(3, 23)
        self.unsharp_ly_spinbox.setSingleStep(2)
        unsharp_layout.addWidget(self.unsharp_ly_spinbox, 0, 3)

        unsharp_layout.addWidget(QLabel("Luma Amount:"), 0, 4)
        self.unsharp_la_spinbox = QDoubleSpinBox()
        self.unsharp_la_spinbox.setRange(-1.5, 5.0)
        self.unsharp_la_spinbox.setDecimals(2)
        self.unsharp_la_spinbox.setSingleStep(0.1)
        unsharp_layout.addWidget(self.unsharp_la_spinbox, 0, 5)

        unsharp_layout.addWidget(QLabel("Chroma X:"), 1, 0)
        self.unsharp_cx_spinbox = QSpinBox()
        self.unsharp_cx_spinbox.setRange(3, 23)
        self.unsharp_cx_spinbox.setSingleStep(2)
        unsharp_layout.addWidget(self.unsharp_cx_spinbox, 1, 1)

        unsharp_layout.addWidget(QLabel("Chroma Y:"), 1, 2)
        self.unsharp_cy_spinbox = QSpinBox()
        self.unsharp_cy_spinbox.setRange(3, 23)
        self.unsharp_cy_spinbox.setSingleStep(2)
        unsharp_layout.addWidget(self.unsharp_cy_spinbox, 1, 3)

        unsharp_layout.addWidget(QLabel("Chroma Amount:"), 1, 4)
        self.unsharp_ca_spinbox = QDoubleSpinBox()
        self.unsharp_ca_spinbox.setRange(-1.5, 5.0)
        self.unsharp_ca_spinbox.setDecimals(2)
        self.unsharp_ca_spinbox.setSingleStep(0.1)
        unsharp_layout.addWidget(self.unsharp_ca_spinbox, 1, 5)

        unsharp_layout.setColumnStretch(1, 1)
        unsharp_layout.setColumnStretch(3, 1)
        unsharp_layout.setColumnStretch(5, 1)
        main_layout.addWidget(unsharp_group)

        # --- Quality Settings Group ---
        quality_group = QGroupBox("Encoding Quality (libx264)")
        quality_layout = QGridLayout(quality_group)

        self.ffmpeg_quality_preset_label = QLabel("Preset:")
        self.ffmpeg_quality_preset_combo = QComboBox()
        # Example presets - map these to CRF/bitrate values
        self.ffmpeg_quality_preset_combo.addItems([
            "Very High (CRF 16)",
            "High (CRF 18)",
            "Medium (CRF 20)",
            "Low (CRF 23)",
            "Very Low (CRF 26)",
            "Custom CRF",
            "Custom Bitrate"
        ])
        quality_layout.addWidget(self.ffmpeg_quality_preset_label, 0, 0)
        quality_layout.addWidget(self.ffmpeg_quality_preset_combo, 0, 1, 1, 3) # Span columns

        self.ffmpeg_crf_label = QLabel("CRF:")
        self.ffmpeg_crf_spinbox = QSpinBox()
        self.ffmpeg_crf_spinbox.setRange(0, 51) # x264 CRF range
        quality_layout.addWidget(self.ffmpeg_crf_label, 1, 0)
        quality_layout.addWidget(self.ffmpeg_crf_spinbox, 1, 1)

        self.ffmpeg_bitrate_label = QLabel("Bitrate (kbps):")
        self.ffmpeg_bitrate_spinbox = QSpinBox()
        self.ffmpeg_bitrate_spinbox.setRange(100, 100000) # Example range
        self.ffmpeg_bitrate_spinbox.setSingleStep(100)
        quality_layout.addWidget(self.ffmpeg_bitrate_label, 1, 2)
        quality_layout.addWidget(self.ffmpeg_bitrate_spinbox, 1, 3)

        self.ffmpeg_bufsize_label = QLabel("Buffer Size (kbps):")
        self.ffmpeg_bufsize_spinbox = QSpinBox()
        self.ffmpeg_bufsize_spinbox.setRange(100, 200000) # Example range
        self.ffmpeg_bufsize_spinbox.setSingleStep(100)
        self.ffmpeg_bufsize_spinbox.setEnabled(False) # Auto-calculated
        quality_layout.addWidget(self.ffmpeg_bufsize_label, 2, 2)
        quality_layout.addWidget(self.ffmpeg_bufsize_spinbox, 2, 3)

        self.ffmpeg_pix_fmt_label = QLabel("Pixel Format:")
        self.ffmpeg_pix_fmt_combo = QComboBox()
        self.ffmpeg_pix_fmt_combo.addItems(["yuv444p", "yuv420p", "yuv422p"]) # Common options
        quality_layout.addWidget(self.ffmpeg_pix_fmt_label, 3, 0)
        quality_layout.addWidget(self.ffmpeg_pix_fmt_combo, 3, 1)

        self.ffmpeg_filter_preset_label = QLabel("Filter Preset:")
        self.ffmpeg_filter_preset_combo = QComboBox()
        self.ffmpeg_filter_preset_combo.addItems([
            "ultrafast", "superfast", "veryfast", "faster", "fast",
            "medium", "slow", "slower", "veryslow"
        ])
        quality_layout.addWidget(self.ffmpeg_filter_preset_label, 3, 2)
        quality_layout.addWidget(self.ffmpeg_filter_preset_combo, 3, 3)


        quality_layout.setColumnStretch(1, 1)
        quality_layout.setColumnStretch(3, 1)
        main_layout.addWidget(quality_group)

        main_layout.addStretch(1) # Push everything up

        return tab

    def _connect_ffmpeg_settings_tab_signals(self) -> None:
        """Connect signals for enabling/disabling controls and profile handling on the FFmpeg Settings tab."""
        # Profile selection
        self.ffmpeg_profile_combo.currentTextChanged.connect(self._on_profile_selected)

        # Monitor changes in individual controls to switch profile to "Custom"
        controls_to_monitor = [
            self.ffmpeg_interp_group, # Checkbox state of the groupbox
            self.ffmpeg_mi_mode_combo,
            self.ffmpeg_mc_mode_combo,
            self.ffmpeg_me_mode_combo,
            self.ffmpeg_me_algo_combo,
            self.ffmpeg_search_param_spinbox,
            self.ffmpeg_vsbmc_checkbox,
            self.ffmpeg_scd_combo,
            self.ffmpeg_scd_thresh_spinbox,
            self.ffmpeg_mb_size_combo,
            self.unsharp_groupbox, # Checkbox state of the groupbox
            self.unsharp_lx_spinbox,
            self.unsharp_ly_spinbox,
            self.unsharp_la_spinbox,
            self.unsharp_cx_spinbox,
            self.unsharp_cy_spinbox,
            self.unsharp_ca_spinbox,
            self.ffmpeg_quality_preset_combo, # Changes here trigger updates
            self.ffmpeg_crf_spinbox,
            self.ffmpeg_bitrate_spinbox,
            # self.ffmpeg_bufsize_spinbox, # Bufsize is auto-calculated
            self.ffmpeg_pix_fmt_combo,
            self.ffmpeg_filter_preset_combo,
        ]

        for control in controls_to_monitor:
            if isinstance(control, (QComboBox, QGroupBox)):
                # QGroupBox uses stateChanged for its checkable state
                # QComboBox uses currentTextChanged
                signal = control.toggled if isinstance(control, QGroupBox) else control.currentTextChanged
                signal.connect(self._on_ffmpeg_setting_changed)
            elif isinstance(control, (QSpinBox, QDoubleSpinBox)):
                control.valueChanged.connect(self._on_ffmpeg_setting_changed)
            elif isinstance(control, QCheckBox):
                control.stateChanged.connect(self._on_ffmpeg_setting_changed)

        # Enable/disable interpolation group based on encoder
        # self.encoder_combo.currentTextChanged.connect(lambda enc: self._update_ffmpeg_controls_state(enc == 'FFmpeg')) # Handled in _update_rife_options_state

        # Enable/disable unsharp group based on its own checkbox
        self.unsharp_groupbox.toggled.connect(self._update_unsharp_controls_state)

        # Enable/disable SCD threshold based on SCD mode
        self.ffmpeg_scd_combo.currentTextChanged.connect(self._update_scd_thresh_state)

        # Update quality controls based on preset selection
        self.ffmpeg_quality_preset_combo.currentTextChanged.connect(
            lambda preset: self._update_quality_controls_state("FFmpeg", preset)
        )
        # Auto-calculate bufsize when bitrate changes
        self.ffmpeg_bitrate_spinbox.valueChanged.connect(
            lambda val: self.ffmpeg_bufsize_spinbox.setValue(int(val * 1.5))
        )

    def _on_profile_selected(self, profile_name: str) -> None:
        """Applies the selected FFmpeg profile settings."""
        if profile_name == "Custom":
            # Don't change settings if "Custom" is selected, just update combo
            return

        if profile_name not in FFMPEG_PROFILES:
            LOGGER.warning(f"Selected profile '{profile_name}' not found in FFMPEG_PROFILES.")
            return

        profile = FFMPEG_PROFILES[profile_name]

        # Block signals temporarily to prevent recursive updates
        widgets_to_block = [
            self.ffmpeg_profile_combo, self.ffmpeg_interp_group, self.ffmpeg_mi_mode_combo,
            self.ffmpeg_mc_mode_combo, self.ffmpeg_me_mode_combo, self.ffmpeg_me_algo_combo,
            self.ffmpeg_search_param_spinbox, self.ffmpeg_vsbmc_checkbox, self.ffmpeg_scd_combo,
            self.ffmpeg_scd_thresh_spinbox, self.ffmpeg_mb_size_combo, self.unsharp_groupbox,
            self.unsharp_lx_spinbox, self.unsharp_ly_spinbox, self.unsharp_la_spinbox,
            self.unsharp_cx_spinbox, self.unsharp_cy_spinbox, self.unsharp_ca_spinbox,
            self.ffmpeg_quality_preset_combo, self.ffmpeg_crf_spinbox, self.ffmpeg_bitrate_spinbox,
            self.ffmpeg_pix_fmt_combo, self.ffmpeg_filter_preset_combo
        ]
        blocked_states = {widget: widget.signalsBlocked() for widget in widgets_to_block}
        for widget in widgets_to_block:
            widget.blockSignals(True)

        try:
            # Apply Interpolation settings
            self.ffmpeg_interp_group.setChecked(profile["use_ffmpeg_interp"])
            self.ffmpeg_mi_mode_combo.setCurrentText(profile["mi_mode"])
            self.ffmpeg_mc_mode_combo.setCurrentText(profile["mc_mode"])
            self.ffmpeg_me_mode_combo.setCurrentText(profile["me_mode"])
            self.ffmpeg_me_algo_combo.setCurrentText(profile["me_algo"])
            self.ffmpeg_search_param_spinbox.setValue(profile["search_param"])
            self.ffmpeg_vsbmc_checkbox.setChecked(profile["vsbmc"])
            self.ffmpeg_scd_combo.setCurrentText(profile["scd"])
            self.ffmpeg_scd_thresh_spinbox.setValue(profile["scd_threshold"])
            self.ffmpeg_mb_size_combo.setCurrentText(profile["mb_size"])

            # Apply Unsharp settings
            self.unsharp_groupbox.setChecked(profile["apply_unsharp"])
            self.unsharp_lx_spinbox.setValue(profile["unsharp_lx"])
            self.unsharp_ly_spinbox.setValue(profile["unsharp_ly"])
            self.unsharp_la_spinbox.setValue(profile["unsharp_la"])
            self.unsharp_cx_spinbox.setValue(profile["unsharp_cx"])
            self.unsharp_cy_spinbox.setValue(profile["unsharp_cy"])
            self.unsharp_ca_spinbox.setValue(profile["unsharp_ca"])

            # Apply Quality settings
            self.ffmpeg_quality_preset_combo.setCurrentText(profile["preset_text"])
            self.ffmpeg_crf_spinbox.setValue(profile["crf"])
            self.ffmpeg_bitrate_spinbox.setValue(profile["bitrate"])
            self.ffmpeg_bufsize_spinbox.setValue(profile["bufsize"]) # Also set bufsize
            self.ffmpeg_pix_fmt_combo.setCurrentText(profile["pix_fmt"])
            self.ffmpeg_filter_preset_combo.setCurrentText(profile["filter_preset"])

            # Update dependent control states AFTER setting values
            self._update_unsharp_controls_state(profile["apply_unsharp"])
            self._update_scd_thresh_state(profile["scd"])
            self._update_quality_controls_state("FFmpeg", profile["preset_text"])

        finally:
            # Restore signal blocking states
            for widget, was_blocked in blocked_states.items():
                widget.blockSignals(was_blocked)

        LOGGER.info(f"Applied FFmpeg profile: {profile_name}")

    def _on_ffmpeg_setting_changed(self, *args: Any) -> None:
        """Switches the profile combo to 'Custom' if settings deviate from the selected profile."""
        current_profile_name = self.ffmpeg_profile_combo.currentText()
        if current_profile_name == "Custom":
            return # Already custom

        if current_profile_name in FFMPEG_PROFILES:
            profile_dict = FFMPEG_PROFILES[current_profile_name]
            if not self._check_settings_match_profile(profile_dict):
                # Block signals on the profile combo ONLY to prevent recursion
                was_blocked = self.ffmpeg_profile_combo.signalsBlocked()
                self.ffmpeg_profile_combo.blockSignals(True)
                self.ffmpeg_profile_combo.setCurrentText("Custom")
                self.ffmpeg_profile_combo.blockSignals(was_blocked)
                LOGGER.info("FFmpeg settings changed, switched profile to Custom.")

    def _update_ffmpeg_controls_state(self, enable: bool, update_group: bool = True) -> None:
        """Enables or disables all FFmpeg settings controls."""
        # Only enable/disable the tab content if the attribute exists
        if hasattr(self, 'ffmpeg_settings_tab'):
            # Find the main layout of the ffmpeg_settings_tab
            layout = self.ffmpeg_settings_tab.layout()
            if layout:
                 # Iterate through items in the layout (widgets and sub-layouts)
                 for i in range(layout.count()):
                     item = layout.itemAt(i)
                     # Check item before accessing widget
                     if item is not None:
                         widget = item.widget()
                         if widget:
                             # Don't disable labels
                             if not isinstance(widget, QLabel):
                                 widget.setEnabled(enable)
                         else:
                             # Handle sub-layouts (like the profile layout)
                             sub_layout = item.layout()
                             if sub_layout:
                                 for j in range(sub_layout.count()):
                                     sub_item = sub_layout.itemAt(j)
                                     # Check sub_item before accessing widget
                                     if sub_item is not None:
                                         sub_widget = sub_item.widget()
                                         if sub_widget:
                                             # Don't disable labels
                                             if not isinstance(sub_widget, QLabel):
                                                 sub_widget.setEnabled(enable)

            # Special handling for group boxes if update_group is True
            if update_group:
                self.ffmpeg_interp_group.setEnabled(enable and self.ffmpeg_interp_group.isChecked())
                self.unsharp_groupbox.setEnabled(enable and self.unsharp_groupbox.isChecked())
                # Update controls within the groups based on their check state
                self._update_unsharp_controls_state(self.unsharp_groupbox.isChecked() if enable else False)
                self._update_scd_thresh_state(self.ffmpeg_scd_combo.currentText() if enable else "none")
                self._update_quality_controls_state("FFmpeg", self.ffmpeg_quality_preset_combo.currentText() if enable else None)

        else:
             LOGGER.warning("Attempted to update FFmpeg controls state, but ffmpeg_settings_tab not found.")


    def _toggle_tile_size_enabled(self, state: int) -> None:
        """Enables/disables the tile size spinbox based on the tile enable checkbox."""
        self.rife_tile_size_spinbox.setEnabled(state == Qt.CheckState.Checked.value)
        self.rife_tile_size_label.setEnabled(state == Qt.CheckState.Checked.value)

    def _update_scd_thresh_state(self, scd_mode: str) -> None:
        """Enables/disables the SCD threshold spinbox based on the SCD mode."""
        enable = (scd_mode == "fdiff")
        self.ffmpeg_scd_thresh_label.setEnabled(enable)
        self.ffmpeg_scd_thresh_spinbox.setEnabled(enable)

    def _update_unsharp_controls_state(self, checked: bool) -> None:
        """Enables or disables controls within the Unsharp group based on the group's check state."""
        # Iterate through children of the unsharp_groupbox layout
        layout = self.unsharp_groupbox.layout()
        if layout:
            for i in range(layout.count()):
                item = layout.itemAt(i)
                # Check if item and widget exist before accessing
                if item is not None:
                    widget = item.widget()
                    if widget and widget != self.unsharp_groupbox: # Don't disable the groupbox itself
                        # Only enable if the groupbox is checked AND the main FFmpeg controls are enabled
                        is_ffmpeg_enabled = self.encoder_combo.currentText() == 'FFmpeg'
                        widget.setEnabled(checked and is_ffmpeg_enabled)

    def _update_quality_controls_state(self, encoder_type: str, preset_text: Optional[str] = None) -> None:
        """Updates CRF/Bitrate controls based on the selected quality preset."""
        is_ffmpeg = (encoder_type == "FFmpeg")
        enable_crf = False
        enable_bitrate = False

        if is_ffmpeg and preset_text:
            if "Custom CRF" in preset_text:
                enable_crf = True
                enable_bitrate = False
            elif "Custom Bitrate" in preset_text:
                enable_crf = False
                enable_bitrate = True
            elif "CRF" in preset_text: # Preset with CRF value
                enable_crf = False # Disabled, value comes from preset
                enable_bitrate = False
                # Extract CRF value from preset text, e.g., "Very High (CRF 16)"
                match = re.search(r"\(CRF (\d+)\)", preset_text)
                if match:
                    crf_value = int(match.group(1))
                    # Block signals temporarily to avoid triggering _on_ffmpeg_setting_changed
                    was_blocked = self.ffmpeg_crf_spinbox.signalsBlocked()
                    self.ffmpeg_crf_spinbox.blockSignals(True)
                    self.ffmpeg_crf_spinbox.setValue(crf_value)
                    self.ffmpeg_crf_spinbox.blockSignals(was_blocked)
            else: # Default case or unknown preset
                enable_crf = False
                enable_bitrate = False
        else: # Not FFmpeg encoder or no preset text
             enable_crf = False
             enable_bitrate = False


        # Enable/disable controls based on flags and whether FFmpeg is selected
        self.ffmpeg_crf_label.setEnabled(enable_crf and is_ffmpeg)
        self.ffmpeg_crf_spinbox.setEnabled(enable_crf and is_ffmpeg)
        self.ffmpeg_bitrate_label.setEnabled(enable_bitrate and is_ffmpeg)
        self.ffmpeg_bitrate_spinbox.setEnabled(enable_bitrate and is_ffmpeg)
        self.ffmpeg_bufsize_label.setEnabled(enable_bitrate and is_ffmpeg) # Bufsize tied to bitrate
        self.ffmpeg_bufsize_spinbox.setEnabled(enable_bitrate and is_ffmpeg)


    def _start(self) -> None:
        """Starts the VFI process in a worker thread."""
        if self.is_processing:
            LOGGER.warning("Processing is already in progress.")
            return

        in_dir = pathlib.Path(self.in_dir_edit.text())
        out_file = pathlib.Path(self.out_file_edit.text())

        if not in_dir.is_dir():
            self._show_error("Input directory is not valid.", user_error=True)
            return
        if not out_file.parent.is_dir():
            self._show_error("Output file directory is not valid.", user_error=True)
            return
        if out_file.suffix.lower() != ".mp4":
             self._show_error("Output file must have a .mp4 extension.", user_error=True)
             return

        # --- Get common settings ---
        fps = self.fps_spinbox.value()
        mid_count = self.mid_count_spinbox.value()
        max_workers = self.max_workers_spinbox.value()
        encoder = self.encoder_combo.currentText()

        # --- Get RIFE specific settings ---
        model_key = self.model_combo.currentData() # Get the key (e.g., "rife-v4.6")
        rife_tile_enable = self.rife_tile_enable_checkbox.isChecked()
        rife_tile_size = self.rife_tile_size_spinbox.value()
        rife_uhd_mode = self.rife_uhd_mode_checkbox.isChecked()
        rife_thread_spec = self.rife_thread_spec_edit.text()
        rife_tta_spatial = self.rife_tta_spatial_checkbox.isChecked()
        rife_tta_temporal = self.rife_tta_temporal_checkbox.isChecked()

        # --- Get Sanchez specific settings ---
        false_colour = self.sanchez_false_colour_checkbox.isChecked()
        res_km = self.sanchez_res_km_spinbox.value()

        # --- Get FFmpeg specific settings ---
        use_ffmpeg_interp = self.ffmpeg_interp_group.isChecked()
        filter_preset = self.ffmpeg_filter_preset_combo.currentText()
        mi_mode = self.ffmpeg_mi_mode_combo.currentText()
        mc_mode = self.ffmpeg_mc_mode_combo.currentText()
        me_mode = self.ffmpeg_me_mode_combo.currentText()
        me_algo = self.ffmpeg_me_algo_combo.currentText()
        search_param = self.ffmpeg_search_param_spinbox.value()
        scd_mode = self.ffmpeg_scd_combo.currentText()
        scd_threshold = self.ffmpeg_scd_thresh_spinbox.value() if scd_mode == "fdiff" else None
        mb_size_str = self.ffmpeg_mb_size_combo.currentText()
        minter_mb_size = int(mb_size_str) if mb_size_str != "(default)" else None
        minter_vsbmc = 1 if self.ffmpeg_vsbmc_checkbox.isChecked() else 0

        # Unsharp
        apply_unsharp = self.unsharp_groupbox.isChecked()
        unsharp_lx = self.unsharp_lx_spinbox.value()
        unsharp_ly = self.unsharp_ly_spinbox.value()
        unsharp_la = self.unsharp_la_spinbox.value()
        unsharp_cx = self.unsharp_cx_spinbox.value()
        unsharp_cy = self.unsharp_cy_spinbox.value()
        unsharp_ca = self.unsharp_ca_spinbox.value()

        # Quality
        crf = self.ffmpeg_crf_spinbox.value()
        bitrate_kbps = self.ffmpeg_bitrate_spinbox.value()
        bufsize_kb = self.ffmpeg_bufsize_spinbox.value()
        pix_fmt = self.ffmpeg_pix_fmt_combo.currentText()
        quality_preset = self.ffmpeg_quality_preset_combo.currentText()

        # Determine final CRF/bitrate based on preset
        final_crf = crf
        final_bitrate = bitrate_kbps
        if "Custom CRF" not in quality_preset and "Custom Bitrate" not in quality_preset:
             # Use CRF from preset text if available
             match = re.search(r"\(CRF (\d+)\)", quality_preset)
             if match:
                 final_crf = int(match.group(1))
                 final_bitrate = 0 # Indicate CRF mode is used
             else:
                 # Fallback if preset text doesn't contain CRF (shouldn't happen with current setup)
                 LOGGER.warning(f"Could not extract CRF from preset '{quality_preset}', using spinbox value.")
                 final_bitrate = 0 # Default to CRF mode

        elif "Custom Bitrate" in quality_preset:
             final_crf = 0 # Indicate bitrate mode is used
             final_bitrate = bitrate_kbps # Use bitrate spinbox value
        # else "Custom CRF" uses final_crf = crf and final_bitrate = 0


        # --- Validate RIFE settings if RIFE is selected ---
        if encoder == 'RIFE':
            if not model_key:
                 self._show_error("No RIFE model selected.", user_error=True)
                 return
            # Validate thread spec format
            if not re.fullmatch(r"\d+:\d+:\d+:\d+", rife_thread_spec):
                 self._show_error("Invalid RIFE thread spec format. Use N:N:N:N (e.g., 0:0:0:0).", user_error=True)
                 return

        # --- Create and start worker ---
        self._set_processing_state(True)
        self.status_label.setText("Starting VFI process...")
        self.progress_bar.setValue(0)

        self.worker = VfiWorker(
            in_dir=in_dir,
            out_file_path=out_file,
            fps=fps,
            mid_count=mid_count,
            max_workers=max_workers,
            encoder=encoder,
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
            crf=final_crf, # Pass final determined CRF
            bitrate_kbps=final_bitrate, # Pass final determined bitrate
            bufsize_kb=bufsize_kb,
            pix_fmt=pix_fmt,
            # Other
            skip_model=False, # Add skip_model option later if needed
            crop_rect=self.current_crop_rect,
            debug_mode=self.debug_mode,
            # RIFE v4.6 settings
            model_key=model_key or "", # Pass empty string if None
            rife_tile_enable=rife_tile_enable,
            rife_tile_size=rife_tile_size,
            rife_uhd_mode=rife_uhd_mode,
            rife_thread_spec=rife_thread_spec,
            rife_tta_spatial=rife_tta_spatial,
            rife_tta_temporal=rife_tta_temporal,
            # Sanchez settings
            false_colour=false_colour,
            res_km=res_km,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(lambda msg: self._show_error(msg, stage="Processing")) # Specify stage
        self.worker.start()

    def _on_progress(self, current: int, total: int, eta: float) -> None:
        """Updates the progress bar and status label."""
        progress_percent = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(progress_percent)
        eta_str = f"{eta:.1f}s" if eta > 0 else "N/A"
        self.status_label.setText(f"Processing frame {current}/{total}... ETA: {eta_str}")

    def _on_finished(self, mp4: pathlib.Path) -> None:
        """Handles the completion of the VFI process."""
        self._set_processing_state(False)
        self.status_label.setText(f"Finished! Output saved to: {mp4.name}")
        self.progress_bar.setValue(100)
        QMessageBox.information(self, "VFI Complete", f"Video saved to:\n{mp4}")
        self._update_start_button_state() # Re-enable VLC button if file exists

    def _show_error(self, msg: str, stage: str = "Error", user_error: bool = False) -> None:
        """Displays an error message in a dialog and updates the status label."""
        LOGGER.error(f"{stage}: {msg}")
        self.status_label.setText(f"{stage}: {msg}")
        if self.is_processing: # Ensure state is reset if error occurs during processing
             self._set_processing_state(False)
        # Use warning icon for user errors, critical for system errors
        icon = QMessageBox.Icon.Warning if user_error else QMessageBox.Icon.Critical
        QMessageBox.critical(self, stage, msg) # Use critical for all errors for now
        self._update_start_button_state() # Update button states after error

    def _open_in_vlc(self) -> None:
        """Attempts to open the output file in VLC."""
        file_path = self.out_file_edit.text()
        if file_path and Path(file_path).exists():
            url = QUrl.fromLocalFile(file_path)
            if not QDesktopServices.openUrl(url):
                QMessageBox.warning(self, "Open Failed", f"Could not automatically open the file:\n{file_path}\n\nPlease open it manually.")
        else:
            QMessageBox.warning(self, "Open Failed", "Output file does not exist or path is not set.")

    # Modified _show_zoom function
    def _show_zoom(self, label: ClickableLabel) -> None:
        """Shows a zoomable dialog for the preview image, loading the original processed file."""
        if not label.file_path:
            LOGGER.warning("Zoom requested, but label has no file_path set.")
            # Optionally show a small warning to the user?
            # QMessageBox.information(label, "Zoom", "Preview image path not available.")
            return

        try:
            # Check if we have a processed image stored
            if hasattr(label, 'processed_image') and label.processed_image is not None:
                # Use the already-processed image (with Sanchez and any other processing already applied)
                LOGGER.info("Using stored processed image for zoom dialog")
                img = label.processed_image
            else:
                # Fall back to loading from file
                LOGGER.info("No stored processed image, loading from file")
                img = QImage(label.file_path)
                
            if img.isNull():
                LOGGER.error(f"Zoom: Failed to load image from {label.file_path}")
                QMessageBox.warning(label, "Zoom Error", f"Could not load image:\n{label.file_path}")
                return
                
            # We're using the already processed image, which has both Sanchez and cropping applied
            # No need to re-apply any processing here

            # Convert processed full-res image to QPixmap
            full_res_processed_pixmap = QPixmap.fromImage(img)

            # Scale the *processed full-resolution* pixmap for the zoom dialog
            screen = QApplication.primaryScreen()
            if screen:
                max_size = screen.availableGeometry().size() * 0.95 # Use 95% of screen
                scaled_pix = full_res_processed_pixmap.scaled(
                    max_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                dialog = ZoomDialog(scaled_pix, self)
                dialog.exec()
            else:
                 LOGGER.warning("Zoom: Could not get screen geometry, showing unscaled image.")
                 dialog = ZoomDialog(full_res_processed_pixmap, self) # Show unscaled if no screen info
                 dialog.exec()

        except Exception as e:
            LOGGER.error(f"Error showing zoom for {label.file_path}: {e}")
            QMessageBox.critical(label, "Zoom Error", f"Could not display zoomed image:\n{e}")


    def _makeModelLibraryTab(self) -> QWidget:
        """Creates the Model Library management tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        layout.addWidget(QLabel("Installed RIFE Models:"))

        self.model_table = QTableWidget()
        self.model_table.setColumnCount(4) # Name, Type, Path, Capabilities
        self.model_table.setHorizontalHeaderLabels(["Name", "Type", "Path", "Capabilities"])
        self.model_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers) # Read-only
        v_header = self.model_table.verticalHeader()
        if v_header:
            v_header.setVisible(False)
        h_header = self.model_table.horizontalHeader()
        if h_header:
            h_header.setStretchLastSection(True)
        layout.addWidget(self.model_table)

        # Add button or mechanism to refresh/scan for models later if needed
        # refresh_button = QPushButton("Refresh Models")
        # layout.addWidget(refresh_button)

        self._populate_model_table() # Populate the table initially

        return tab

    def _populate_model_table(self) -> None:
        """Populates the model library table with discovered models."""
        self.model_table.setRowCount(0) # Clear existing rows
        models = config.get_available_rife_models() # Assumes this returns list[str] or similar

        # Base path for models
        project_root = pathlib.Path(__file__).parent.parent # Go up one level from gui.py to project root
        models_base_dir = project_root / "models"

        # Iterate directly if models is a list of names
        # If models is a dict {key: {name: ..., path: ...}}, adjust accordingly
        for i, model_name in enumerate(models): # Assuming models is a list of names
            self.model_table.insertRow(i)
            # Construct path based on the name if needed, or retrieve from models if it's a dict
            model_path = models_base_dir / model_name
            model_type = "RIFE" # Assuming all discovered models are RIFE for now

            self.model_table.setItem(i, 0, QTableWidgetItem(model_name)) # Use model_name as name
            self.model_table.setItem(i, 1, QTableWidgetItem(model_type)) # Set type
            self.model_table.setItem(i, 2, QTableWidgetItem(str(model_path))) # Set path

            # Get capabilities from the manager
            caps_dict = self.rife_capability_manager.capabilities
            supported_caps = [k for k, v in caps_dict.items() if v]
            caps_str = ", ".join(supported_caps) if supported_caps else "None"
            self.model_table.setItem(i, 3, QTableWidgetItem(caps_str))

        self.model_table.resizeColumnsToContents()
        h_header = self.model_table.horizontalHeader()
        if h_header:
            h_header.setStretchLastSection(True)


    def _on_clear_crop_clicked(self) -> None:
        """Clears the current crop selection."""
        if self.current_crop_rect:
            self.current_crop_rect = None
            LOGGER.info("Crop region cleared.")
            self.clear_crop_button.setEnabled(False)
            self.request_previews_update.emit() # Update previews without crop


    def _connect_model_combo(self) -> None:
        """Connects the model combo box signal if it exists."""
        if hasattr(self, 'model_combo'):
            self.model_combo.currentTextChanged.connect(self._on_model_changed)
        else:
            LOGGER.warning("model_combo not found during connection setup.")


    def _on_tab_changed(self, index: int) -> None:
        """Handles actions when the selected tab changes."""
        # Example: Refresh model library tab if selected
        tab_text = self.main_tabs.tabText(index)
        if tab_text == "Model Library":
            self._populate_model_table()

    def _check_settings_match_profile(self, profile_dict: FfmpegProfile) -> bool:
        """Checks if current FFmpeg settings match a given profile dictionary."""
        try:
            current_settings = {
                "use_ffmpeg_interp": self.ffmpeg_interp_group.isChecked(),
                "mi_mode": self.ffmpeg_mi_mode_combo.currentText(),
                "mc_mode": self.ffmpeg_mc_mode_combo.currentText(),
                "me_mode": self.ffmpeg_me_mode_combo.currentText(),
                "me_algo": self.ffmpeg_me_algo_combo.currentText(),
                "search_param": self.ffmpeg_search_param_spinbox.value(),
                "vsbmc": self.ffmpeg_vsbmc_checkbox.isChecked(),
                "scd": self.ffmpeg_scd_combo.currentText(),
                "scd_threshold": self.ffmpeg_scd_thresh_spinbox.value(),
                "mb_size": self.ffmpeg_mb_size_combo.currentText(),
                "apply_unsharp": self.unsharp_groupbox.isChecked(),
                "unsharp_lx": self.unsharp_lx_spinbox.value(),
                "unsharp_ly": self.unsharp_ly_spinbox.value(),
                "unsharp_la": self.unsharp_la_spinbox.value(),
                "unsharp_cx": self.unsharp_cx_spinbox.value(),
                "unsharp_cy": self.unsharp_cy_spinbox.value(),
                "unsharp_ca": self.unsharp_ca_spinbox.value(),
                "preset_text": self.ffmpeg_quality_preset_combo.currentText(),
                "crf": self.ffmpeg_crf_spinbox.value(),
                "bitrate": self.ffmpeg_bitrate_spinbox.value(),
                "bufsize": self.ffmpeg_bufsize_spinbox.value(),
                "pix_fmt": self.ffmpeg_pix_fmt_combo.currentText(),
                "filter_preset": self.ffmpeg_filter_preset_combo.currentText(),
            }

            # Compare relevant fields, considering disabled states might affect comparison
            for key, profile_value in profile_dict.items():
                current_value = current_settings.get(key)

                # Special handling for SCD threshold (only compare if scd is 'fdiff')
                if key == "scd_threshold" and profile_dict.get("scd") != "fdiff":
                    continue # Don't compare threshold if SCD is off

                # Special handling for unsharp values (only compare if apply_unsharp is True)
                if key.startswith("unsharp_") and key != "apply_unsharp" and not profile_dict.get("apply_unsharp"):
                     continue # Don't compare specific unsharp values if group is off

                # Special handling for CRF/Bitrate based on preset_text
                preset = profile_dict.get("preset_text", "")
                if "Custom CRF" in preset:
                     if key == "bitrate" or key == "bufsize": continue # Don't compare bitrate/bufsize
                elif "Custom Bitrate" in preset:
                     if key == "crf": continue # Don't compare CRF
                elif "CRF" in preset: # Preset defines CRF
                     if key == "bitrate" or key == "bufsize": continue # Don't compare bitrate/bufsize
                     # CRF value is derived from preset_text, so comparing preset_text is sufficient

                # General comparison
                if current_value != profile_value:
                    # LOGGER.debug(f"Profile mismatch: Key='{key}', Current='{current_value}', Profile='{profile_value}'")
                    return False
            return True
        except Exception as e:
            LOGGER.error(f"Error checking profile match: {e}")
            return False # Assume mismatch on error

    def loadSettings(self) -> None:
        """Loads settings from QSettings."""
        LOGGER.info("Loading settings...")
        # Input/Output
        self.in_dir_edit.setText(self.settings.value("paths/inputDirectory", "", type=str))
        self.out_file_edit.setText(self.settings.value("paths/outputFile", "", type=str))

        # Interpolation
        self.fps_spinbox.setValue(self.settings.value("interpolation/fps", 30, type=int))
        self.mid_count_spinbox.setValue(self.settings.value("interpolation/midCount", 7, type=int))
        self.max_workers_spinbox.setValue(self.settings.value("interpolation/maxWorkers", 4, type=int))
        self.encoder_combo.setCurrentText(self.settings.value("interpolation/encoder", "RIFE", type=str))
        self.model_combo.setCurrentText(self.settings.value("interpolation/rifeModel", "", type=str)) # Load model name

        # RIFE Options
        self.rife_tile_enable_checkbox.setChecked(self.settings.value("rife/tileEnable", True, type=bool))
        self.rife_tile_size_spinbox.setValue(self.settings.value("rife/tileSize", 384, type=int))
        self.rife_uhd_mode_checkbox.setChecked(self.settings.value("rife/uhdMode", False, type=bool))
        self.rife_thread_spec_edit.setText(self.settings.value("rife/threadSpec", "0:0:0:0", type=str))
        self.rife_tta_spatial_checkbox.setChecked(self.settings.value("rife/ttaSpatial", False, type=bool))
        self.rife_tta_temporal_checkbox.setChecked(self.settings.value("rife/ttaTemporal", False, type=bool))

        # Sanchez Options
        self.sanchez_false_colour_checkbox.setChecked(self.settings.value("sanchez/falseColour", False, type=bool))
        self.sanchez_res_km_spinbox.setValue(self.settings.value("sanchez/resKm", 500, type=int))

        # FFmpeg Profile and Settings
        # Load profile first, then individual settings which might override profile if saved as "Custom"
        saved_profile_name = self.settings.value("ffmpeg/profileName", "Default", type=str)

        # Load individual FFmpeg settings (use profile defaults if key missing)
        default_prof = FFMPEG_PROFILES.get(saved_profile_name, DEFAULT_FFMPEG_PROFILE) # Fallback to Default

        self.ffmpeg_interp_group.setChecked(self.settings.value("ffmpeg/use_ffmpeg_interp", default_prof["use_ffmpeg_interp"], type=bool))
        self.ffmpeg_mi_mode_combo.setCurrentText(self.settings.value("ffmpeg/mi_mode", default_prof["mi_mode"], type=str))
        self.ffmpeg_mc_mode_combo.setCurrentText(self.settings.value("ffmpeg/mc_mode", default_prof["mc_mode"], type=str))
        self.ffmpeg_me_mode_combo.setCurrentText(self.settings.value("ffmpeg/me_mode", default_prof["me_mode"], type=str))
        self.ffmpeg_me_algo_combo.setCurrentText(self.settings.value("ffmpeg/me_algo", default_prof["me_algo"], type=str))
        self.ffmpeg_search_param_spinbox.setValue(self.settings.value("ffmpeg/search_param", default_prof["search_param"], type=int))
        self.ffmpeg_vsbmc_checkbox.setChecked(self.settings.value("ffmpeg/vsbmc", default_prof["vsbmc"], type=bool))
        self.ffmpeg_scd_combo.setCurrentText(self.settings.value("ffmpeg/scd", default_prof["scd"], type=str))
        self.ffmpeg_scd_thresh_spinbox.setValue(self.settings.value("ffmpeg/scd_threshold", default_prof["scd_threshold"], type=float))
        self.ffmpeg_mb_size_combo.setCurrentText(self.settings.value("ffmpeg/mb_size", default_prof["mb_size"], type=str))

        self.unsharp_groupbox.setChecked(self.settings.value("ffmpeg/apply_unsharp", default_prof["apply_unsharp"], type=bool))
        self.unsharp_lx_spinbox.setValue(self.settings.value("ffmpeg/unsharp_lx", default_prof["unsharp_lx"], type=int))
        self.unsharp_ly_spinbox.setValue(self.settings.value("ffmpeg/unsharp_ly", default_prof["unsharp_ly"], type=int))
        self.unsharp_la_spinbox.setValue(self.settings.value("ffmpeg/unsharp_la", default_prof["unsharp_la"], type=float))
        self.unsharp_cx_spinbox.setValue(self.settings.value("ffmpeg/unsharp_cx", default_prof["unsharp_cx"], type=int))
        self.unsharp_cy_spinbox.setValue(self.settings.value("ffmpeg/unsharp_cy", default_prof["unsharp_cy"], type=int))
        self.unsharp_ca_spinbox.setValue(self.settings.value("ffmpeg/unsharp_ca", default_prof["unsharp_ca"], type=float))

        # Load quality preset text first, as it determines which other controls are relevant
        quality_preset_text = self.settings.value("ffmpeg/preset_text", default_prof["preset_text"], type=str)
        self.ffmpeg_quality_preset_combo.setCurrentText(quality_preset_text)

        self.ffmpeg_crf_spinbox.setValue(self.settings.value("ffmpeg/crf", default_prof["crf"], type=int))
        self.ffmpeg_bitrate_spinbox.setValue(self.settings.value("ffmpeg/bitrate", default_prof["bitrate"], type=int))
        self.ffmpeg_bufsize_spinbox.setValue(self.settings.value("ffmpeg/bufsize", default_prof["bufsize"], type=int)) # Load bufsize
        self.ffmpeg_pix_fmt_combo.setCurrentText(self.settings.value("ffmpeg/pix_fmt", default_prof["pix_fmt"], type=str))
        self.ffmpeg_filter_preset_combo.setCurrentText(self.settings.value("ffmpeg/filter_preset", default_prof["filter_preset"], type=str))

        # After loading individual settings, check if they still match the saved profile name
        if saved_profile_name != "Custom" and saved_profile_name in FFMPEG_PROFILES:
             if self._check_settings_match_profile(FFMPEG_PROFILES[saved_profile_name]):
                  self.ffmpeg_profile_combo.setCurrentText(saved_profile_name)
             else:
                  self.ffmpeg_profile_combo.setCurrentText("Custom")
        else:
             # If saved profile was "Custom" or invalid, set combo to "Custom"
             self.ffmpeg_profile_combo.setCurrentText("Custom")


        # Window Geometry
        geom = self.settings.value("window/geometry")
        if isinstance(geom, QByteArray):
            self.restoreGeometry(geom)

        LOGGER.info("Settings loaded.")


    def saveSettings(self) -> None:
        """Saves settings to QSettings."""
        LOGGER.info("Saving settings...")
        # Paths
        self.settings.setValue("paths/inputDirectory", self.in_dir_edit.text())
        self.settings.setValue("paths/outputFile", self.out_file_edit.text())

        # Interpolation
        self.settings.setValue("interpolation/fps", self.fps_spinbox.value())
        self.settings.setValue("interpolation/midCount", self.mid_count_spinbox.value())
        self.settings.setValue("interpolation/maxWorkers", self.max_workers_spinbox.value())
        self.settings.setValue("interpolation/encoder", self.encoder_combo.currentText())
        self.settings.setValue("interpolation/rifeModel", self.model_combo.currentText()) # Save model name

        # RIFE Options
        self.settings.setValue("rife/tileEnable", self.rife_tile_enable_checkbox.isChecked())
        self.settings.setValue("rife/tileSize", self.rife_tile_size_spinbox.value())
        self.settings.setValue("rife/uhdMode", self.rife_uhd_mode_checkbox.isChecked())
        self.settings.setValue("rife/threadSpec", self.rife_thread_spec_edit.text())
        self.settings.setValue("rife/ttaSpatial", self.rife_tta_spatial_checkbox.isChecked())
        self.settings.setValue("rife/ttaTemporal", self.rife_tta_temporal_checkbox.isChecked())

        # Sanchez Options
        self.settings.setValue("sanchez/falseColour", self.sanchez_false_colour_checkbox.isChecked())
        self.settings.setValue("sanchez/resKm", self.sanchez_res_km_spinbox.value())

        # FFmpeg Profile and Settings
        self.settings.setValue("ffmpeg/profileName", self.ffmpeg_profile_combo.currentText())
        # Save all individual FFmpeg settings regardless of profile
        self.settings.setValue("ffmpeg/use_ffmpeg_interp", self.ffmpeg_interp_group.isChecked())
        self.settings.setValue("ffmpeg/mi_mode", self.ffmpeg_mi_mode_combo.currentText())
        self.settings.setValue("ffmpeg/mc_mode", self.ffmpeg_mc_mode_combo.currentText())
        self.settings.setValue("ffmpeg/me_mode", self.ffmpeg_me_mode_combo.currentText())
        self.settings.setValue("ffmpeg/me_algo", self.ffmpeg_me_algo_combo.currentText())
        self.settings.setValue("ffmpeg/search_param", self.ffmpeg_search_param_spinbox.value())
        self.settings.setValue("ffmpeg/vsbmc", self.ffmpeg_vsbmc_checkbox.isChecked())
        self.settings.setValue("ffmpeg/scd", self.ffmpeg_scd_combo.currentText())
        self.settings.setValue("ffmpeg/scd_threshold", self.ffmpeg_scd_thresh_spinbox.value())
        self.settings.setValue("ffmpeg/mb_size", self.ffmpeg_mb_size_combo.currentText())
        self.settings.setValue("ffmpeg/apply_unsharp", self.unsharp_groupbox.isChecked())
        self.settings.setValue("ffmpeg/unsharp_lx", self.unsharp_lx_spinbox.value())
        self.settings.setValue("ffmpeg/unsharp_ly", self.unsharp_ly_spinbox.value())
        self.settings.setValue("ffmpeg/unsharp_la", self.unsharp_la_spinbox.value())
        self.settings.setValue("ffmpeg/unsharp_cx", self.unsharp_cx_spinbox.value())
        self.settings.setValue("ffmpeg/unsharp_cy", self.unsharp_cy_spinbox.value())
        self.settings.setValue("ffmpeg/unsharp_ca", self.unsharp_ca_spinbox.value())
        self.settings.setValue("ffmpeg/preset_text", self.ffmpeg_quality_preset_combo.currentText())
        self.settings.setValue("ffmpeg/crf", self.ffmpeg_crf_spinbox.value())
        self.settings.setValue("ffmpeg/bitrate", self.ffmpeg_bitrate_spinbox.value())
        self.settings.setValue("ffmpeg/bufsize", self.ffmpeg_bufsize_spinbox.value()) # Save bufsize
        self.settings.setValue("ffmpeg/pix_fmt", self.ffmpeg_pix_fmt_combo.currentText())
        self.settings.setValue("ffmpeg/filter_preset", self.ffmpeg_filter_preset_combo.currentText())


        # Window Geometry
        self.settings.setValue("window/geometry", self.saveGeometry())

        self.settings.sync()
        LOGGER.info("Settings saved.")


    def _validate_thread_spec(self, text: str) -> None:
        """Validates the RIFE thread spec input."""
        edit = self.rife_thread_spec_edit
        valid_format = re.fullmatch(r"\d+:\d+:\d+:\d+", text) is not None
        # Change background color to indicate validity (subtle)
        palette = edit.palette()
        if valid_format or not text: # Allow empty string during typing
            palette.setColor(palette.ColorRole.Base, QColor("white"))
        else:
            palette.setColor(palette.ColorRole.Base, QColor("#fff0f0")) # Light red background for invalid
        edit.setPalette(palette)
        # Update start button state as validity affects it
        self._update_start_button_state()


    def _populate_models(self) -> None:
        """Populates the RIFE model combo box."""
        self.model_combo.clear()
        self.model_combo.addItem("Scanning for models...", None) # Placeholder
        self.model_combo.setEnabled(False)

        try:
            models = config.get_available_rife_models() # Returns list[str]
            self.model_combo.clear() # Clear placeholder/previous items
            if models:
                # Iterate over the list of model keys/names
                for model_key in models:
                    # For now, add the key as both text and data.
                    # TODO: Fetch model display name if needed separately.
                    self.model_combo.addItem(model_key, model_key)
                self.model_combo.setEnabled(True)
                LOGGER.info(f"Found {len(models)} RIFE models.")
                # Try to restore last selected model
                last_model_name = self.settings.value("interpolation/rifeModel", "", type=str)
                if last_model_name:
                     index = self.model_combo.findText(last_model_name)
                     if index != -1:
                          self.model_combo.setCurrentIndex(index)
                     else:
                          LOGGER.warning(f"Previously selected model '{last_model_name}' not found.")
                          self.model_combo.setCurrentIndex(0) # Select first available
                else:
                     self.model_combo.setCurrentIndex(0) # Select first available if none saved

            else:
                self.model_combo.addItem("No RIFE models found", None)
                self.model_combo.setEnabled(False)
                LOGGER.warning("No RIFE models found in expected locations.")

        except Exception as e:
            LOGGER.exception(f"Error populating RIFE models: {e}")
            self.model_combo.clear()
            self.model_combo.addItem("Error finding models", None)
            self.model_combo.setEnabled(False)
            self._show_error(f"Could not find RIFE models: {e}", stage="Initialization")

        # Update UI elements that depend on model availability/selection
        self._update_rife_ui_elements()
        self._update_start_button_state()


    def _toggle_sanchez_res_enabled(self, state: Qt.CheckState) -> None:
        """Enables or disables the Sanchez resolution spinbox based on the false colour checkbox state."""
        # Revert: Just enable/disable based on checkbox state. Groupbox enable state handles the rest.
        is_checked = (state == Qt.CheckState.Checked)
        is_rife_enabled = (self.encoder_combo.currentText() == "RIFE")
        self.sanchez_res_km_spinbox.setEnabled(is_checked and is_rife_enabled)
        self.sanchez_res_km_label.setEnabled(is_checked and is_rife_enabled) # Also enable/disable label

    def _update_rife_ui_elements(self) -> None:
        """Updates the visibility and state of RIFE-specific UI elements."""
        # NOTE: Visibility is primarily handled by _update_rife_options_state based on encoder.
        # This method ensures consistency after model population.
        is_rife_encoder = (self.encoder_combo.currentText() == "RIFE")
        self.rife_options_groupbox.setVisible(is_rife_encoder)
        self.model_label.setVisible(is_rife_encoder)
        self.model_combo.setVisible(is_rife_encoder)
        # The enabled state of model_combo is handled in _populate_models and _set_processing_state
        pass # Keep method structure for now, might need further review

    def _on_model_changed(self, model_key: str) -> None:
        """Handles actions when the selected RIFE model changes."""
        # Currently no specific actions needed on model change, but this is a placeholder
        LOGGER.info(f"Selected RIFE model: {model_key}")
        self._update_start_button_state() # Update start button state as model selection affects it


    def closeEvent(self, event: QCloseEvent | None) -> None:
        """Handles the window close event."""
        if self.is_processing:
            reply = QMessageBox.question(
                self,
                "Quit GOES-VFI",
                "A VFI process is currently running. Are you sure you want to quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                # Attempt to terminate the worker thread gracefully
                if self.worker and self.worker.isRunning():
                    LOGGER.info("Attempting to terminate worker thread...")
                    self.worker.terminate()
                    self.worker.wait() # Wait for the thread to finish
                    LOGGER.info("Worker thread terminated.")
                self.saveSettings() # Save settings before closing
                if event:
                    event.accept()
            else:
                if event:
                    event.ignore()
        else:
            self.saveSettings() # Save settings before closing
            if event:
                event.accept()

    # Corrected indentation and removed stray else blocks
    def _load_process_scale_preview(self, image_path: Path, target_label: ClickableLabel) -> QPixmap | None:
        """Loads, processes (crop/sanchez), scales, and returns a preview pixmap."""
        try:
            img = QImage(str(image_path))
            if img.isNull():
                LOGGER.error(f"Failed to load image: {image_path}")
                return None

            # --- Apply Sanchez Processing ---
            sanchez_processing_failed = False
            sanchez_error_message = ""
            
            # Import _bin from Sanchez runner to get binary path
            try:
                from goesvfi.sanchez.runner import _bin
            except ImportError as e:
                LOGGER.error(f"Could not import _bin function from Sanchez runner: {e}")
                sanchez_processing_failed = True
                sanchez_error_message = f"Sanchez import error: {e}"
            
            if self.sanchez_false_colour_checkbox.isChecked():
                temp_input_path = None
                temp_output_path = None
                
                try:
                    LOGGER.debug(f"Starting Sanchez processing for: {image_path.name}")
                    
                    # First verify that Sanchez binary exists and is executable
                    try:
                        sanchez_binary = _bin()
                        if not sanchez_binary.exists():
                            LOGGER.error(f"Sanchez binary not found at: {sanchez_binary}")
                            raise FileNotFoundError(f"Sanchez binary not found: {sanchez_binary}")
                        
                        # Check if the binary has execute permissions
                        if not os.access(sanchez_binary, os.X_OK):
                            LOGGER.error(f"Sanchez binary exists but is not executable: {sanchez_binary}")
                            # Try to make it executable
                            try:
                                os.chmod(sanchez_binary, 0o755)  # rwx for owner, rx for group and others
                                LOGGER.info(f"Added execute permission to Sanchez binary: {sanchez_binary}")
                            except Exception as chmod_error:
                                LOGGER.error(f"Failed to add execute permission to Sanchez binary: {chmod_error}")
                                raise RuntimeError(f"Sanchez binary is not executable: {sanchez_binary}")
                    except Exception as bin_error:
                        LOGGER.error(f"Error accessing Sanchez binary: {bin_error}")
                        raise RuntimeError(f"Sanchez binary access failed: {bin_error}")
                    
                    LOGGER.debug(f"Using Sanchez binary: {sanchez_binary}")
                    
                    # Create a more distinctive temp directory to avoid issues with permissions
                    temp_dir = Path(tempfile.gettempdir()) / "goes_vfi_sanchez"
                    os.makedirs(temp_dir, exist_ok=True)
                    
                    # Preserve original filename exactly - Sanchez parser depends on it!
                    original_name = image_path.name
                    temp_input_path = temp_dir / original_name
                    # Create output path with same name but add "_processed" suffix
                    output_name = image_path.stem + "_processed" + image_path.suffix
                    temp_output_path = temp_dir / output_name
                    
                    # Save the image with highest quality for processing
                    LOGGER.debug(f"Saving image to: {temp_input_path}")
                    save_result = img.save(str(temp_input_path), "PNG", 100)
                    
                    if not save_result:
                        LOGGER.error(f"Failed to save temporary image for processing: {temp_input_path}")
                        raise IOError(f"Failed to save temporary image to {temp_input_path}")
                        
                    # Verify the file was created
                    if not temp_input_path.exists() or temp_input_path.stat().st_size == 0:
                        LOGGER.error(f"Temporary file is empty or not created: {temp_input_path}")
                        raise IOError(f"Temporary file creation failed: {temp_input_path}")
                        
                    # Get the resolution setting
                    res_km = self.sanchez_res_km_spinbox.value()
                    LOGGER.debug(f"Applying Sanchez processing with resolution {res_km}km")
                    
                    try:
                        # Get binary path
                        bin_path = _bin()
                        binary_dir = bin_path.parent
                        
                        # Build command directly for debugging
                        cmd = [str(bin_path), "-s", str(temp_input_path), "-o", str(temp_output_path),
                               "-r", str(res_km)]
                               
                        LOGGER.info(f"Running Sanchez command: {' '.join(cmd)}")
                        LOGGER.info(f"In directory: {binary_dir}")
                        
                        # Make sure the binary exists and has execute permissions
                        if not os.path.exists(bin_path):
                            LOGGER.error(f"Sanchez binary not found at runtime: {bin_path}")
                            raise FileNotFoundError(f"Sanchez binary not found at runtime: {bin_path}")
                            
                        if not os.access(bin_path, os.X_OK):
                            LOGGER.error(f"Sanchez binary not executable at runtime: {bin_path}")
                            # Try to make it executable
                            try:
                                os.chmod(bin_path, 0o755)
                                LOGGER.info(f"Added execute permission to Sanchez binary at runtime: {bin_path}")
                            except Exception as chmod_error:
                                LOGGER.error(f"Failed to add execute permission: {chmod_error}")
                                raise RuntimeError(f"Cannot execute Sanchez binary: {bin_path}")
                        
                        # Run process manually for maximum control and debugging
                        import subprocess
                        LOGGER.debug(f"Starting subprocess for Sanchez")
                        
                        # Set full path for output explicitly to debug permission issues
                        full_output_path = os.path.abspath(str(temp_output_path))
                        # Use directly the same command that works in our test script
                        full_input_path = os.path.abspath(str(temp_input_path))
                        # Use the 'geostationary' verb explicitly
                        cmd = [str(bin_path), "geostationary", "-s", full_input_path,
                               "-o", full_output_path, "-r", str(res_km), "-v"]
                        LOGGER.info(f"Using absolute paths: input={full_input_path}, output={full_output_path}")
                        LOGGER.info("Using the command that works from our standalone test")
                        
                        # We now know that Sanchez strictly depends on the original filename format,
                        # so we don't need to create alternative filenames with different extensions
                        LOGGER.info(f"Using original filename: {temp_input_path.name}")
                        
                        result = subprocess.run(
                            cmd,
                            check=False,  # Don't raise exception, we'll handle errors
                            capture_output=True,
                            text=True,
                            encoding='utf-8',
                            errors='replace',
                            cwd=binary_dir
                        )
                        
                        # Log full output for debugging
                        LOGGER.info(f"Sanchez command completed with return code: {result.returncode}")
                        if result.stdout:
                            LOGGER.info(f"Sanchez stdout: {result.stdout}")
                        else:
                            LOGGER.info("No stdout output from Sanchez")
                            
                        if result.stderr:
                            LOGGER.info(f"Sanchez stderr: {result.stderr}")
                        else:
                            LOGGER.info("No stderr output from Sanchez")
                            
                        # Check return code
                        if result.returncode != 0:
                            LOGGER.error(f"Sanchez process failed with code {result.returncode}")
                            raise RuntimeError(f"Sanchez process failed with code {result.returncode}")
                            
                        # Check if the output directory exists and is writable
                        output_dir = os.path.dirname(full_output_path)
                        if not os.path.exists(output_dir):
                            LOGGER.error(f"Output directory does not exist: {output_dir}")
                            raise FileNotFoundError(f"Output directory does not exist: {output_dir}")
                            
                        if not os.access(output_dir, os.W_OK):
                            LOGGER.error(f"Output directory is not writable: {output_dir}")
                            raise PermissionError(f"Output directory is not writable: {output_dir}")
                    
                    except Exception as sanchez_error:
                        LOGGER.error(f"Sanchez processing failed: {sanchez_error}")
                        raise
                        
                    # Check if the output file was created
                    if not temp_output_path.exists():
                        LOGGER.error(f"Sanchez output file was not created: {temp_output_path}")
                        
                        # Try to create a simple test file in the same directory to check permissions
                        try:
                            test_file_path = Path(temp_output_path.parent) / "test_write_permission.txt"
                            with open(test_file_path, 'w') as f:
                                f.write("Test write permission")
                            LOGGER.info(f"Successfully created test file at {test_file_path}")
                            os.remove(test_file_path)
                            LOGGER.info(f"Successfully removed test file")
                        except Exception as perm_error:
                            LOGGER.error(f"Permission test failed: {perm_error}")
                            
                        # Try fallback with different options before giving up
                        LOGGER.info("Attempting fallback with different Sanchez options...")
                        
                        fallback_succeeded = False
                        
                        try:
                            # Try with help flag first to see available options
                            help_cmd = [str(bin_path), "--help"]
                            help_result = subprocess.run(
                                help_cmd,
                                check=False,
                                capture_output=True,
                                text=True,
                                cwd=binary_dir
                            )
                            if help_result.stdout:
                                LOGGER.info(f"Sanchez help: {help_result.stdout}")
                            if help_result.stderr:
                                LOGGER.info(f"Sanchez help stderr: {help_result.stderr}")
                                
                            # Try with debug flag
                            debug_cmd = [str(bin_path), "-s", str(temp_input_path), "-o", full_output_path, "-r", str(res_km), "--debug"]
                            LOGGER.info(f"Trying with debug flag: {' '.join(debug_cmd)}")
                            debug_result = subprocess.run(
                                debug_cmd,
                                check=False,
                                capture_output=True,
                                text=True,
                                cwd=binary_dir
                            )
                            
                            if temp_output_path.exists() and temp_output_path.stat().st_size > 0:
                                LOGGER.info("Success! Debug flag worked!")
                                fallback_succeeded = True
                                
                            # Try explicitly without the geostationary verb (as used in colourise function)
                            if not fallback_succeeded:
                                no_verb_cmd = [str(bin_path), "-s", full_input_path,
                                              "-o", full_output_path, "-r", str(res_km)]
                                LOGGER.info(f"Trying without verb: {' '.join(no_verb_cmd)}")
                                no_verb_result = subprocess.run(
                                    no_verb_cmd,
                                    check=False,
                                    capture_output=True,
                                    text=True,
                                    cwd=binary_dir
                                )
                                
                                if temp_output_path.exists() and temp_output_path.stat().st_size > 0:
                                    LOGGER.info("Success! No-verb command worked!")
                                    fallback_succeeded = True
                                    
                            # We no longer need the IR PNG fallback since we preserve the original filename
                            # Try with another approach: attempt directly using the original file
                            if not fallback_succeeded:
                                # Get the original image path from our function parameter
                                orig_cmd = [str(bin_path), "geostationary", "-s", str(image_path),
                                         "-o", full_output_path, "-r", str(res_km), "-v"]
                                LOGGER.info(f"Trying with direct original file: {' '.join(orig_cmd)}")
                                orig_result = subprocess.run(
                                    orig_cmd,
                                    check=False,
                                    capture_output=True,
                                    text=True,
                                    cwd=binary_dir
                                )
                                
                                if temp_output_path.exists() and temp_output_path.stat().st_size > 0:
                                    LOGGER.info("Success! Direct original file worked!")
                                    fallback_succeeded = True
                        except Exception as fallback_error:
                            LOGGER.error(f"Error during fallback attempts: {fallback_error}")
                        
                        # If a fallback succeeded, continue with the existing code path
                        if fallback_succeeded:
                            LOGGER.info("Using successfully generated output file from fallback")
                        else:
                            # If we got here, all fallbacks failed
                            # Since the Sanchez command completed but no output was created
                            # this might be an issue with the input image format or Sanchez itself
                            sanchez_error_message = "Sanchez failed to process the image (no output file created)"
                            raise FileNotFoundError(f"Sanchez output file not found: {temp_output_path}")
                        
                    # Check output file size
                    if temp_output_path.stat().st_size == 0:
                        LOGGER.error(f"Sanchez output file is empty: {temp_output_path}")
                        raise IOError(f"Sanchez output file is empty: {temp_output_path}")
                    
                    LOGGER.debug(f"Loading processed image from: {temp_output_path}")
                    processed_img = QImage(str(temp_output_path))
                    
                    if not processed_img.isNull():
                        LOGGER.debug(f"Successfully applied Sanchez processing to {image_path.name}")
                        img = processed_img
                    else:
                        LOGGER.error(f"Sanchez processing resulted in null image for {image_path.name}")
                        raise IOError(f"Processed image is null: {temp_output_path}")
                        
                except Exception as e:
                    LOGGER.error(f"Error during Sanchez processing for {image_path.name}: {e}")
                    sanchez_processing_failed = True
                    sanchez_error_message = str(e)
                    # Continue with the original image if Sanchez fails
                finally:
                    # Clean up temporary files
                    try:
                        if temp_input_path and temp_input_path.exists():
                            os.remove(temp_input_path)
                        if temp_output_path and temp_output_path.exists():
                            os.remove(temp_output_path)
                    except Exception as cleanup_error:
                        LOGGER.warning(f"Failed to clean up temporary files: {cleanup_error}")
            # --- End Sanchez Processing ---

            # --- Apply Crop ---
            if self.current_crop_rect:
                x, y, w, h = self.current_crop_rect
                # Ensure crop rect is within image bounds
                img_w, img_h = img.width(), img.height()
                if x < img_w and y < img_h: # Use < directly
                    crop_w = min(w, img_w - x)
                    crop_h = min(h, img_h - y)
                    if crop_w > 0 and crop_h > 0:
                        img = img.copy(x, y, crop_w, crop_h)
                    else:
                        LOGGER.warning(f"Invalid crop rect {self.current_crop_rect} for image size {img_w}x{img_h}")
                else:
                     LOGGER.warning(f"Crop start point {x},{y} outside image bounds {img_w}x{img_h}")
            # --- End Crop ---

            # Store original path for zoom function and the processed image itself
            target_label.file_path = str(image_path) # Store the *original* path
            target_label.processed_image = img.copy() # Store the processed image for zoom

            # Scale for preview display
            target_size = target_label.size()
            # Ensure target size is valid before scaling
            if target_size.width() <= 0 or target_size.height() <= 0:
                 # If label size isn't determined yet, use a reasonable default or skip scaling
                 LOGGER.warning(f"Target label '{target_label.objectName()}' has invalid size {target_size}, cannot scale preview.")
                 # Let's try scaling to a fixed size if label size is invalid
                 target_size = QSize(100, 100) # Fallback size

            scaled_img = img.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # If Sanchez processing was attempted but failed, draw an indicator
            pixmap = QPixmap.fromImage(scaled_img)
            
            if sanchez_processing_failed and self.sanchez_false_colour_checkbox.isChecked():
                # Paint warning indicator on the image
                painter = QPainter(pixmap)
                font = painter.font()
                font.setBold(True)
                painter.setFont(font)
                
                # Draw semi-transparent background for text
                painter.fillRect(0, 0, pixmap.width(), 20, QColor(0, 0, 0, 150))
                
                # Draw warning text
                painter.setPen(Qt.GlobalColor.red)
                painter.drawText(5, 15, f"Sanchez failed: {sanchez_error_message[:35]}...")
                painter.end()
            
            return pixmap

        except Exception as e:
            LOGGER.error(f"Error processing preview for {image_path}: {e}")
            target_label.file_path = None # Clear path on error
            return None
        # Stray else blocks removed

    # Rewritten _update_previews function
    def _update_previews(self) -> None:
        """Updates the preview images for first, middle, and last frames."""
        in_dir_path = pathlib.Path(self.in_dir_edit.text())

        # Define labels and default texts
        labels = [self.preview_label_1, self.preview_label_mid, self.preview_label_2]
        default_texts = ["Preview 1 (First)", "Preview 2 (Middle)", "Preview 3 (Last)"]

        # --- Clear previews and reset state ---
        def clear_all_previews(message: str = "") -> None:
            for i, label in enumerate(labels):
                label.setPixmap(QPixmap())
                label.setText(default_texts[i] if not message else message if i == 0 else "")
                label.file_path = None
            self._update_crop_buttons_state()

        # --- Handle invalid input directory ---
        if not in_dir_path.is_dir():
            clear_all_previews()
            # Optionally add a specific message if the path is not empty but invalid
            if self.in_dir_edit.text():
                 labels[0].setText("Invalid Directory")
            return

        # --- Find image files ---
        try:
            image_files = sorted([
                f for f in in_dir_path.iterdir()
                if f.is_file() and f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.tif', '.tiff']
            ])
        except Exception as e:
            LOGGER.error(f"Error listing image files in {in_dir_path}: {e}")
            clear_all_previews("Error listing files")
            return

        num_images = len(image_files)

        # --- Handle case: No images found ---
        if num_images == 0:
            clear_all_previews("No images found")
            return

        # --- Determine paths for first, middle, and last images ---
        first_image_path = image_files[0]
        middle_image_path: Path | None = None
        last_image_path: Path | None = None

        if num_images > 2:
            middle_index = num_images // 2
            middle_image_path = image_files[middle_index]
            last_image_path = image_files[-1]
        elif num_images == 2:
            # If exactly two images, show first and second (last)
            last_image_path = image_files[1]
            # Middle remains None
        # If num_images == 1, only first_image_path is set

        # --- Create list of (path, label) pairs to process ---
        preview_tasks = [(first_image_path, self.preview_label_1)]
        if middle_image_path:
            preview_tasks.append((middle_image_path, self.preview_label_mid))
        if last_image_path:
            preview_tasks.append((last_image_path, self.preview_label_2))

        # --- Clear existing previews before loading new ones ---
        for label in labels:
             label.setPixmap(QPixmap())
             label.setText("Loading...") # Indicate loading state
             label.file_path = None

        # --- Load, process, and display previews using the helper ---
        processed_indices = set()
        for i, (path, label) in enumerate(preview_tasks):
            # Assign object name for better logging
            label.setObjectName(f"preview_label_{labels.index(label)+1}")
            pixmap = self._load_process_scale_preview(path, label)
            if pixmap:
                label.setPixmap(pixmap)
                label.setText("")
                processed_indices.add(labels.index(label)) # Mark as processed
            else:
                label.setPixmap(QPixmap())
                label.setText("Error")
                label.file_path = None # Ensure path is cleared

        # --- Clear any labels that didn't have a task ---
        for i, label in enumerate(labels):
            if i not in processed_indices:
                label.setPixmap(QPixmap())
                label.setText("") # Clear text (e.g., middle/last if only 1 or 2 images)
                label.file_path = None

        self._update_crop_buttons_state() # Update crop button state


    def _update_start_button_state(self) -> None:
        """Updates the enabled state of the start button."""
        in_dir_ok = pathlib.Path(self.in_dir_edit.text()).is_dir()
        out_file_path_str = self.out_file_edit.text()
        out_file_ok = bool(out_file_path_str) and pathlib.Path(out_file_path_str).parent.is_dir() and out_file_path_str.lower().endswith(".mp4")
        encoder = self.encoder_combo.currentText()
        model_selected = (encoder == 'FFmpeg') or (encoder == 'RIFE' and self.model_combo.currentData() is not None)

        # Check RIFE thread spec validity if RIFE is selected
        rife_spec_ok = True
        if encoder == 'RIFE':
             rife_spec_ok = re.fullmatch(r"\d+:\d+:\d+:\d+", self.rife_thread_spec_edit.text()) is not None

        self.start_button.setEnabled(in_dir_ok and out_file_ok and model_selected and rife_spec_ok and not self.is_processing)

        # Also update the state of the Open in VLC button
        out_file_exists = bool(out_file_path_str) and pathlib.Path(out_file_path_str).exists() # Check non-empty path first
        self.open_vlc_button.setEnabled(out_file_exists and not self.is_processing)


    def _set_processing_state(self, processing: bool) -> None:
        """Sets the processing state and updates UI elements accordingly."""
        self.is_processing = processing
        is_rife_encoder = self.encoder_combo.currentText() == 'RIFE' # Check current encoder
        model_available = self.model_combo.count() > 0 and self.model_combo.currentData() is not None

        can_start = (
            pathlib.Path(self.in_dir_edit.text()).is_dir() and
            pathlib.Path(self.out_file_edit.text()).parent.is_dir() and
            self.out_file_edit.text().lower().endswith(".mp4") and
            (is_rife_encoder and model_available) or (not is_rife_encoder)
        )
        # Check RIFE thread spec validity if RIFE is selected
        rife_spec_ok = True
        if is_rife_encoder:
             rife_spec_ok = re.fullmatch(r"\d+:\d+:\d+:\d+", self.rife_thread_spec_edit.text()) is not None


        self.start_button.setEnabled(can_start and rife_spec_ok and not processing)
        self.open_vlc_button.setEnabled(not processing and pathlib.Path(self.out_file_edit.text()).exists())
        # Disable other controls while processing
        self.in_dir_edit.setEnabled(not processing)
        self.in_dir_button.setEnabled(not processing)
        self.out_file_edit.setEnabled(not processing)
        self.out_file_button.setEnabled(not processing)
        self.fps_spinbox.setEnabled(not processing)
        self.mid_count_spinbox.setEnabled(not processing)
        self.max_workers_spinbox.setEnabled(not processing)
        self.encoder_combo.setEnabled(not processing)
        # Explicitly disable model_combo if not RIFE or if processing
        self.model_combo.setEnabled(not processing and is_rife_encoder and self.model_combo.count() > 0)
        self.crop_button.setEnabled(not processing and pathlib.Path(self.in_dir_edit.text()).is_dir()) # Crop button enabled if not processing and input dir is set
        self.clear_crop_button.setEnabled(not processing and self.current_crop_rect is not None) # Clear crop button enabled if not processing and crop is set
        self.main_tabs.setEnabled(not processing) # Disable the entire tab widget while processing

    def _update_crop_buttons_state(self) -> None:
        """Updates the enabled state of the crop buttons."""
        in_dir_path_str = self.in_dir_edit.text()
        # Enable crop button only if the input directory path is non-empty AND it's a directory
        in_dir_ok = bool(in_dir_path_str) and pathlib.Path(in_dir_path_str).is_dir()
        # Also check if there are any images loaded in preview 1 (using file_path as proxy)
        preview_loaded = bool(self.preview_label_1.file_path)
        self.crop_button.setEnabled(in_dir_ok and preview_loaded and not self.is_processing)
        self.clear_crop_button.setEnabled(self.current_crop_rect is not None and not self.is_processing)


    def _update_rife_options_state(self, encoder_type: str) -> None:
        """Updates the enabled state of RIFE/FFmpeg options based on the selected encoder."""
        is_rife = (encoder_type == "RIFE")
        is_ffmpeg = (encoder_type == "FFmpeg")

        # RIFE controls
        self.rife_options_groupbox.setEnabled(is_rife)
        self.model_label.setEnabled(is_rife)
        self.model_combo.setEnabled(is_rife and self.model_combo.count() > 0 and self.model_combo.currentData() is not None) # Check data too
        self.sanchez_options_groupbox.setEnabled(is_rife)

        # Explicitly update Sanchez spinbox state *after* groupbox state is set
        if is_rife:
            self._toggle_sanchez_res_enabled(self.sanchez_false_colour_checkbox.checkState())
        else:
            # Ensure spinbox is disabled if not RIFE
            self.sanchez_res_km_spinbox.setEnabled(False)
            self.sanchez_res_km_label.setEnabled(False) # Also disable label

        # FFmpeg controls
        if hasattr(self, 'ffmpeg_settings_tab'):
             self._update_ffmpeg_controls_state(is_ffmpeg, update_group=True)
        else:
             LOGGER.warning("ffmpeg_settings_tab not found during _update_rife_options_state")

        # Update other states dependent on encoder change
        self._update_start_button_state()

# ────────────────────────────── Entry Point ──────────────────────────────
def main() -> None:
    """Main function to run the GUI application."""
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="GOES-VFI GUI")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level (default: INFO)",
    )
    parser.add_argument(
         "--debug",
         action="store_true",
         help="Enable debug mode (sets log level to DEBUG and potentially other debug features)"
    )
    args = parser.parse_args()

    log_level = args.log_level # Keep this line for potential future use
    if args.debug:
         log_level = "DEBUG" # Override log level if --debug is set

    # --- Logging Setup ---
    log.set_level(debug_mode=args.debug) # Use the correct function and argument

    LOGGER.info("Starting GOES-VFI GUI...")
    if args.debug:
         LOGGER.info("Debug mode enabled.")

    # --- Application Setup ---
    app = QApplication(sys.argv)

    # Set application icon (optional)
    try:
        # Assuming icon.png is in the same directory as gui.py or accessible via package resources
        # If using package resources:
        # icon_path = pkgres.files('goesvfi').joinpath('icon.png')
        # If relative to script:
        icon_path = Path(__file__).parent / 'icon.png'
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
        else:
            LOGGER.warning("Application icon not found.")
    except Exception as e:
        LOGGER.warning(f"Could not set application icon: {e}")


    window = MainWindow(debug_mode=args.debug) # Pass debug mode flag
    window.show()
    # window._adjust_window_to_content() # Adjust size after showing

    sys.exit(app.exec())


if __name__ == "__main__":
    main()