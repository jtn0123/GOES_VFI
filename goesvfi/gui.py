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

# Correct import for find_rife_executable
from goesvfi.utils import config, log
from goesvfi.utils.gui_helpers import RifeCapabilityManager

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
                    false_colour=self.false_colour,
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
                try:
                    # Try importing run_ffmpeg_interpolation; handle missing module gracefully
                    from goesvfi.pipeline.run_ffmpeg import run_ffmpeg_interpolation
                except (ModuleNotFoundError, ImportError) as e:
                    LOGGER.error("FFmpeg pipeline (goesvfi.pipeline.run_ffmpeg) not found.")
                    self.error.emit("FFmpeg encoding module not found.")
                    return
                # --- Run FFmpeg pipeline ---
                # NOTE: run_ffmpeg_interpolation needs to be adapted
                # to handle Sanchez/cropping similarly to run_vfi if desired
                # For now, it assumes it works on original/cropped frames without Sanchez
                    LOGGER.warning("FFmpeg encoder path does not currently support Sanchez false colour.")
                    final_mp4_path = run_ffmpeg_interpolation(
                        input_dir=self.in_dir,
                        output_mp4_path=self.out_file_path,
                        fps=self.fps,
                        num_intermediate_frames=self.mid_count,
                        use_preset_optimal=False, # Allow manual settings
                        crop_rect=self.crop_rect,
                        debug_mode=self.debug_mode,
                        # Pass detailed settings
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
                        apply_unsharp=self.apply_unsharp,
                        unsharp_lx=self.unsharp_lx,
                        unsharp_ly=self.unsharp_ly,
                        unsharp_la=self.unsharp_la,
                        unsharp_cx=self.unsharp_cx,
                        unsharp_cy=self.unsharp_cy,
                        unsharp_ca=self.unsharp_ca,
                        crf=self.crf,
                        bitrate_kbps=self.bitrate_kbps,
                        bufsize_kb=self.bufsize_kb,
                        pix_fmt=self.pix_fmt
                    )
                    self.finished.emit(final_mp4_path)
                except ImportError:
                    LOGGER.error("FFmpeg pipeline (goesvfi.pipeline.run_ffmpeg) not found.")
                    self.error.emit("FFmpeg encoding module not found.")
                    return
                except NotImplementedError as nie:
                    LOGGER.error(f"FFmpeg encoding error: {nie}")
                    self.error.emit(str(nie))
                    return

            else:
                # This case should be caught by the initial check
                raise ValueError(f"Unsupported encoder reached run logic: {self.encoder}")

        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            LOGGER.error(f"Worker thread error:\n{tb_str}")
            self.error.emit(f"{type(e).__name__}: {e}")

# ──────────────────────────────── Main window ─────────────────────────────
class MainWindow(QWidget):
    # Signals
    request_previews_update = pyqtSignal() # Signal to trigger preview update

    def __init__(self, debug_mode: bool = False) -> None:
        super().__init__()
        self.debug_mode = debug_mode
        self.setWindowTitle("GOES Video Frame Interpolator")

        # Initialize RIFE capability manager
        self.rife_capability_manager = RifeCapabilityManager()

        # Load app icon
        try:
            icon_path = str(pkgres.files('goesvfi').joinpath('resources', 'app_icon.png'))
            self.setWindowIcon(QIcon(icon_path))
            LOGGER.info(f"Loaded icon from: {icon_path}")
        except Exception as e:
            LOGGER.warning(f"Could not load app icon: {e}")

        # Settings storage
        self.settings = QSettings("JustKay", "GOES_VFI")

        # UI State Variables
        self.worker: VfiWorker | None = None
        self.last_dir = pathlib.Path(self.settings.value("main/lastDir", str(pathlib.Path.home())))
        self.last_file = pathlib.Path(self.settings.value("main/lastFile", str(self.last_dir / "output.mp4")))
        saved_crop_str = self.settings.value("main/cropRect", None)
        crop_tuple: Optional[Tuple[int, int, int, int]] = None
        if isinstance(saved_crop_str, str):
            try:
                parts = list(map(int, saved_crop_str.split(',')))
                if len(parts) == 4:
                    crop_tuple = (parts[0], parts[1], parts[2], parts[3])
            except (ValueError, TypeError):
                LOGGER.warning(f"Could not parse cropRect from settings: {saved_crop_str}")
        self.crop_rect: Optional[Tuple[int, int, int, int]] = crop_tuple
        self._geometry_restored = False # Flag to track if geometry was loaded

        # --- Create Main Layout ---
        layout = QVBoxLayout(self)

        # --- Create Tab Widget ---
        self.tab_widget = QTabWidget() # Use self.tab_widget consistently
        layout.addWidget(self.tab_widget)

        # --- Add Tabs ---
        self.main_tab = self._makeMainTab()
        self.ffmpeg_tab = self._make_ffmpeg_settings_tab()
        self.model_tab = self._makeModelLibraryTab()

        self.tab_widget.addTab(self.main_tab, "Main")
        self.tab_widget.addTab(self.ffmpeg_tab, "FFmpeg Settings")
        self.tab_widget.addTab(self.model_tab, "Model Library")

        # Connect tab change signal
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # --- Create Status Bar --- #
        self.status_bar = QStatusBar()
        self.status_bar.setSizeGripEnabled(False) # Optional: hide the size grip
        layout.addWidget(self.status_bar)
        self.status_bar.showMessage("Ready") # Initial status message

        # --- Final Setup ---
        self.setLayout(layout)
        self._populate_models() # Populate model list before loading settings that might use it
        self.loadSettings() # Load settings AFTER UI elements are created
        self._connect_ffmpeg_settings_tab_signals() # Connect signals AFTER UI elements exist
        # Connect model combo signal
        if hasattr(self, 'model_combo'):
            self.model_combo.currentTextChanged.connect(self._on_model_changed)

        # Update UI elements based on RIFE capabilities
        self._update_rife_ui_elements()

        # Apply initial profile state after loading settings
        initial_profile = self.settings.value("ffmpeg/profile", "Default", type=str)
        if hasattr(self, 'ffmpeg_profile_combo'):
             if initial_profile in FFMPEG_PROFILES:
                 self.ffmpeg_profile_combo.setCurrentText(initial_profile)
                 # self._apply_ffmpeg_profile(initial_profile) # Apply might trigger unwanted changes, rely on loadSettings
             elif initial_profile == "Custom":
                 self.ffmpeg_profile_combo.setCurrentText("Custom")
             else:
                 # If saved profile is invalid, default to Default
                 self.ffmpeg_profile_combo.setCurrentText("Default")
                 # self._apply_ffmpeg_profile("Default")

        # Initial preview load might depend on loaded paths
        self._update_previews()

        # Adjust initial size if geometry wasn't restored
        if not self._geometry_restored:
            QTimer.singleShot(50, self._adjust_window_to_content)

        # Set initial start button state
        self._update_start_button_state()
        # Set initial crop button state
        self._update_crop_buttons_state()

    def _adjust_window_to_content(self) -> None:
        """Adjusts window size based on content size hint after tabs are populated."""
        # Calculate the required height considering the status bar
        content_height = self.tab_widget.sizeHint().height()
        status_bar_height = self.status_bar.sizeHint().height()
        # Add some padding
        total_height = content_height + status_bar_height + 20 # Adjust padding as needed

        # Get a reasonable width (e.g., from the main tab's hint or a fixed value)
        content_width = self.main_tab.sizeHint().width()
        total_width = content_width + 20 # Adjust padding

        self.resize(total_width, total_height)
        LOGGER.debug(f"Adjusted window size to: {total_width}x{total_height}")

    # --- UI Element Creation --- #

    def _pick_in_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select Input Folder", str(self.last_dir))
        if d:
            p = pathlib.Path(d)
            self.in_edit.setText(str(p))
            self.last_dir = p
            self._update_previews()

    def _pick_out_file(self) -> None:
        # Use last_file for default path
        f, _ = QFileDialog.getSaveFileName(self, "Select Output MP4", str(self.last_file), "MP4 Videos (*.mp4)")
        if f:
            p = pathlib.Path(f)
            self.out_edit.setText(str(p))
            self.last_file = p # Update last_file
            self.last_dir = p.parent # Update last_dir based on output selection

    def _on_crop_clicked(self) -> None:
        # Restore implementation from original file state (~line 1744)
        from pathlib import Path
        folder = Path(self.in_edit.text()).expanduser()
        imgs = sorted(folder.glob("*.png"))
        if not imgs:
            QMessageBox.warning(self, "No Images", "Select a folder with PNGs first")
            return

        pix = QPixmap(str(imgs[0]))
        crop_init = self.crop_rect
        dlg = CropDialog(pix, crop_init, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            rect = dlg.getRect()
            self.crop_rect = (rect.x(), rect.y(), rect.width(), rect.height())
            self.settings.setValue("main/cropRect", ",".join(map(str, self.crop_rect)))
            self._update_previews() # This method is now defined before _makeMainTab

    def _makeMainTab(self) -> QWidget:
        tab = QWidget()
        main_lay = QVBoxLayout(tab)

        # --- Top Row: Input / Output / Start / Progress --- #
        top_row_lay = QGridLayout()

        # Input
        top_row_lay.addWidget(QLabel("Input PNGs Folder:"), 0, 0)
        self.in_edit = QLineEdit()
        self.in_edit.textChanged.connect(self._update_start_button_state) # Connect signal
        self.in_edit.textChanged.connect(self._update_crop_buttons_state) # Connect signal
        top_row_lay.addWidget(self.in_edit, 0, 1)
        self.in_btn = QPushButton("Browse...")
        self.in_btn.clicked.connect(self._pick_in_dir)
        top_row_lay.addWidget(self.in_btn, 0, 2)
        # Crop Buttons (added to input row for better layout)
        self.crop_btn = QPushButton("Set Crop")
        self.crop_btn.clicked.connect(self._on_crop_clicked)
        top_row_lay.addWidget(self.crop_btn, 0, 3)
        self.clear_crop_btn = QPushButton("Clear Crop")
        self.clear_crop_btn.clicked.connect(self._on_clear_crop_clicked)
        top_row_lay.addWidget(self.clear_crop_btn, 0, 4)

        # Output
        top_row_lay.addWidget(QLabel("Output MP4 File:"), 1, 0)
        self.out_edit = QLineEdit()
        self.out_edit.textChanged.connect(self._update_start_button_state) # Connect signal
        top_row_lay.addWidget(self.out_edit, 1, 1)
        self.out_btn = QPushButton("Browse...")
        self.out_btn.clicked.connect(self._pick_out_file)
        top_row_lay.addWidget(self.out_btn, 1, 2)
        # +++ Add Open Output Button +++
        self.open_btn = QPushButton("Open Output")
        self.open_btn.setToolTip("Open the last generated MP4 file in VLC (if installed).")
        self.open_btn.clicked.connect(self._open_in_vlc)
        self.open_btn.setEnabled(False) # Start disabled
        top_row_lay.addWidget(self.open_btn, 1, 3) # Add to grid layout
        # --- End Add ---

        # Start Button
        self.start_btn = QPushButton("Start Interpolation")
        self.start_btn.clicked.connect(self._start)
        top_row_lay.addWidget(self.start_btn, 2, 0, 1, 5) # Span across 5 columns

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v/%m (%p%)")
        top_row_lay.addWidget(self.progress_bar, 3, 0, 1, 5) # Span across 5 columns

        # ETA Label
        self.eta_label = QLabel("ETA: --:--:--")
        self.eta_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row_lay.addWidget(self.eta_label, 4, 0, 1, 5) # Span across 5 columns

        main_lay.addLayout(top_row_lay)

        # --- Middle Row: Settings (FPS, Intermediates, Encoder, Skip) --- #
        settings_row_lay = QHBoxLayout()
        settings_row_lay.addWidget(QLabel("Output FPS:"))
        self.fps_spin = QSpinBox(); self.fps_spin.setRange(1, 120); self.fps_spin.setValue(30)
        settings_row_lay.addWidget(self.fps_spin)
        settings_row_lay.addWidget(QLabel("Interpolated Frames:"))
        self.inter_spin = QSpinBox(); self.inter_spin.setRange(1, 1); self.inter_spin.setValue(1)
        settings_row_lay.addWidget(self.inter_spin)
        settings_row_lay.addWidget(QLabel("Encoder:"))
        self.encoder_combo = QComboBox(); self.encoder_combo.addItems(["RIFE", "FFmpeg"])
        self.encoder_combo.setToolTip(
            "Select the encoder to use for frame interpolation:\n"
            "- RIFE: AI-based neural network interpolation (higher quality).\n"
            "- FFmpeg: Traditional algorithm-based interpolation (more configurable).\n"
            "Encoder selection affects which quality settings are used."
        )
        settings_row_lay.addWidget(self.encoder_combo)
        self.skip_model_cb = QCheckBox("Skip AI Model")
        self.skip_model_cb.setToolTip(
            "Skip the AI interpolation step and only perform direct encoding.\n"
            "This option is useful for debugging or when only using FFmpeg interpolation."
        )
        settings_row_lay.addWidget(self.skip_model_cb)
        settings_row_lay.addStretch()
        main_lay.addLayout(settings_row_lay)

        # --- RIFE Specific Options --- #
        rife_opts_group = QGroupBox("RIFE Options")
        self.rife_opts_group = rife_opts_group # Assign to self
        rife_opts_layout = QGridLayout(rife_opts_group)
        rife_opts_layout.addWidget(QLabel("Model:"), 0, 0)
        self.model_combo = QComboBox() # Populated later
        rife_opts_layout.addWidget(self.model_combo, 0, 1, 1, 3)
        
        # Add capability summary label
        self.rife_capability_label = QLabel(self.rife_capability_manager.get_capability_summary())
        self.rife_capability_label.setStyleSheet("color: #666; font-style: italic;")
        rife_opts_layout.addWidget(self.rife_capability_label, 0, 4)
        
        self.rife_tile_enable_cb = QCheckBox("Enable Tiling"); self.rife_tile_enable_cb.stateChanged.connect(self._toggle_tile_size_enabled)
        rife_opts_layout.addWidget(self.rife_tile_enable_cb, 1, 0)
        rife_opts_layout.addWidget(QLabel("Tile Size:"), 1, 1)
        self.rife_tile_size_spin = QSpinBox(); self.rife_tile_size_spin.setRange(64, 4096); self.rife_tile_size_spin.setSingleStep(64); self.rife_tile_size_spin.setValue(256); self.rife_tile_size_spin.setEnabled(False)
        rife_opts_layout.addWidget(self.rife_tile_size_spin, 1, 2)
        self.rife_uhd_mode_cb = QCheckBox("UHD Mode")
        rife_opts_layout.addWidget(self.rife_uhd_mode_cb, 2, 0)
        self.thread_spec_label = QLabel("Thread Spec (enc:dec:gpu):")
        rife_opts_layout.addWidget(self.thread_spec_label, 2, 1)
        self.rife_thread_spec_edit = QLineEdit("1:2:2"); self.rife_thread_spec_edit.textChanged.connect(self._validate_thread_spec)
        rife_opts_layout.addWidget(self.rife_thread_spec_edit, 2, 2)
        self.rife_tta_spatial_cb = QCheckBox("TTA Spatial")
        rife_opts_layout.addWidget(self.rife_tta_spatial_cb, 3, 0)
        self.rife_tta_temporal_cb = QCheckBox("TTA Temporal")
        rife_opts_layout.addWidget(self.rife_tta_temporal_cb, 3, 1)
        rife_opts_layout.setColumnStretch(3, 1)
        main_lay.addWidget(rife_opts_group)

        # --- Enhancements Group (Sanchez) --- #
        enhancements_group = QGroupBox("Enhancements")
        enhancements_layout = QGridLayout(enhancements_group)
        self.false_colour_check = QCheckBox("Apply False Colour (Sanchez)")
        enhancements_layout.addWidget(self.false_colour_check, 0, 0, 1, 2)
        self.sanchez_res_label = QLabel("Sanchez Resolution (km):")
        enhancements_layout.addWidget(self.sanchez_res_label, 1, 0)
        self.sanchez_res_spin = QSpinBox(); self.sanchez_res_spin.setRange(1, 16); self.sanchez_res_spin.setValue(4)
        enhancements_layout.addWidget(self.sanchez_res_spin, 1, 1)
        self.sanchez_res_label.setEnabled(False)
        self.sanchez_res_spin.setEnabled(False)
        enhancements_layout.setColumnStretch(2, 1)
        main_lay.addWidget(enhancements_group)

        # --- Bottom Row: Previews --- #
        preview_group = QGroupBox("Previews") # Renamed from Previews & Crop
        preview_layout = QGridLayout(preview_group)
        self.preview_first = ClickableLabel("First Frame"); self.preview_first.setAlignment(Qt.AlignmentFlag.AlignCenter); self.preview_first.setFixedSize(128, 128); self.preview_first.setToolTip("Click to zoom"); self.preview_first.clicked.connect(lambda: self._show_zoom(self.preview_first))
        preview_layout.addWidget(self.preview_first, 0, 0)
        self.preview_mid = ClickableLabel("Middle Frame"); self.preview_mid.setAlignment(Qt.AlignmentFlag.AlignCenter); self.preview_mid.setFixedSize(128, 128); self.preview_mid.setToolTip("Click to zoom"); self.preview_mid.clicked.connect(lambda: self._show_zoom(self.preview_mid))
        preview_layout.addWidget(self.preview_mid, 0, 1)
        self.preview_last = ClickableLabel("Last Frame"); self.preview_last.setAlignment(Qt.AlignmentFlag.AlignCenter); self.preview_last.setFixedSize(128, 128); self.preview_last.setToolTip("Click to zoom"); self.preview_last.clicked.connect(lambda: self._show_zoom(self.preview_last))
        preview_layout.addWidget(self.preview_last, 0, 2)
        # Crop buttons moved to input row
        main_lay.addWidget(preview_group)

        main_lay.addStretch()
        tab.setLayout(main_lay)
        return tab

    # --- FFmpeg Settings Tab --- #
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
        self.ffmpeg_profile_combo.setToolTip(
            "Select a predefined settings profile:\n"
            "- Default: Standard settings for good quality.\n"
            "- Optimal: Settings tuned for best quality-speed balance.\n"
            "- Optimal 2: Alternative optimization based on PowerShell script.\n"
            "- Custom: Your own custom settings configuration.\n"
            "Changing any individual setting will automatically switch to 'Custom'."
        )
        profile_row.addWidget(self.ffmpeg_profile_combo)
        profile_row.addStretch()
        layout.addLayout(profile_row)

        # --- Enable Checkbox ---
        interp_row = QHBoxLayout()
        self.ffmpeg_interp_cb = QCheckBox("Use FFmpeg motion interpolation")
        # Default checked state will be set by profile/loadSettings
        self.ffmpeg_interp_cb.setToolTip(
            "Apply FFmpeg's 'minterpolate' filter to enhance frame interpolation.\n"
            "When enabled, this allows fine-tuned control over the motion interpolation algorithm.\n"
            "When disabled, RIFE will handle all interpolation without FFmpeg processing."
        )
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
        self.preset_combo.setToolTip(
            "Selects the CRF value for software encoders (libx264, libx265).\n"
            "- Very High (CRF 16): Nearly visually lossless, best quality, larger files.\n"
            "- High (CRF 18): Excellent quality with good compression.\n"
            "- Medium (CRF 20): Good quality with better compression.\n"
            "Lower CRF = higher quality but larger file size.\n"
            "This setting is disabled when using hardware encoders."
        )
        quality_layout.addWidget(self.preset_combo)

        # Bitrate control (for hardware codecs)
        quality_layout.addWidget(QLabel("Hardware Encoder Target Bitrate (kbps):"))
        self.bitrate_spin = QSpinBox()
        self.bitrate_spin.setRange(1000, 20000) # 1-20 Mbps
        self.bitrate_spin.setSuffix(" kbps")
        self.bitrate_spin.setToolTip(
            "Target average bitrate for hardware encoders (VideoToolbox, NVENC, etc.).\n"
            "- Higher values produce better quality at larger file sizes.\n"
            "- For 1080p content, 8,000-12,000 kbps is typically good.\n"
            "- For 4K content, 15,000-20,000 kbps is recommended.\n"
            "This setting is enabled only when using hardware encoders."
        )
        quality_layout.addWidget(self.bitrate_spin)

        # Buffer size control (for hardware codecs)
        quality_layout.addWidget(QLabel("Hardware Encoder VBV Buffer Size (kb):"))
        self.bufsize_spin = QSpinBox()
        self.bufsize_spin.setRange(1000, 40000) # 1-40 Mbits
        self.bufsize_spin.setSuffix(" kb")
        self.bufsize_spin.setToolTip(
            "Video Buffer Verifier (VBV) size for hardware encoders.\n"
            "- Controls how much the bitrate can vary during encoding.\n"
            "- Larger values allow more variation for complex scenes.\n"
            "- Typically set to 1.5-2x the target bitrate.\n"
            "- Automatically adjusted when changing the target bitrate.\n"
            "This setting is enabled only when using hardware encoders."
        )
        # Connection for bitrate -> bufsize moved to _connect_ffmpeg_settings_tab_signals
        quality_layout.addWidget(self.bufsize_spin)

        # Pixel format selector
        quality_layout.addWidget(QLabel("Output Pixel Format:"))
        self.pixfmt_combo = QComboBox()
        self.pixfmt_combo.addItems(["yuv420p", "yuv444p"])
        self.pixfmt_combo.setToolTip(
            "Video pixel format for color subsampling:\n"
            "- yuv420p: Standard format with 4:2:0 chroma subsampling.\n"
            "  ✓ Better compatibility, smaller files\n"
            "  ✗ Some color detail loss\n"
            "- yuv444p: High-quality format with 4:4:4 chroma (no subsampling).\n"
            "  ✓ Preserves maximum color detail for scientific imagery\n"
            "  ✓ Better for false color processing\n"
            "  ✗ Larger file sizes\n"
            "For GOES satellite imagery, yuv444p is recommended."
        )
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

        # --- Connect encoder type to quality control enabling/disabling ---
        if hasattr(self, 'encoder_combo'):
            # Connect encoder selection to update quality controls
            self.encoder_combo.currentTextChanged.connect(self._update_quality_controls_state)

        if hasattr(self, 'ffmpeg_interp_cb'):
            self.ffmpeg_interp_cb.toggled.connect(self._update_ffmpeg_controls_state)
        if hasattr(self, 'bitrate_spin') and hasattr(self, 'bufsize_spin'):
            self.bitrate_spin.valueChanged.connect(
                 lambda val: self.bufsize_spin.setValue(min(self.bufsize_spin.maximum(), max(self.bufsize_spin.minimum(), int(val * 1.5))))
            )

        # --- Connect tab switching to resize window ---
        if hasattr(self, 'tab_widget'):
            self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # Initial state update after potential loading
        if hasattr(self, 'ffmpeg_interp_cb'):
             self._update_ffmpeg_controls_state(self.ffmpeg_interp_cb.isChecked())
        
        # Initialize quality control states based on current encoder selection
        if hasattr(self, 'encoder_combo'):
            self._update_quality_controls_state(self.encoder_combo.currentText())

    # +++ Inserted Methods (FFmpeg Settings Tab Logic) +++
    def _on_profile_selected(self, profile_name: str) -> None:
        """Applies the selected profile if it's not 'Custom'."""
        # Prevent recursive calls when applying profile programmatically
        if not hasattr(self, '_ffmpeg_setting_change_active') or not self._ffmpeg_setting_change_active: return
        if profile_name != "Custom" and profile_name in FFMPEG_PROFILES:
            LOGGER.info(f"Applying FFmpeg profile: {profile_name}")
            self._apply_ffmpeg_profile(profile_name)

    def _on_ffmpeg_setting_changed(self, *args: Any) -> None:
        """Switches the profile combo to 'Custom' if a setting is changed manually."""
        # Prevent switching to Custom when applying a profile or loading settings
        if not hasattr(self, '_ffmpeg_setting_change_active') or not self._ffmpeg_setting_change_active: return

        # Check if ffmpeg_profile_combo exists
        if not hasattr(self, 'ffmpeg_profile_combo'): return

        # Block signals temporarily to prevent immediate re-application of "Custom"
        self.ffmpeg_profile_combo.blockSignals(True)
        self.ffmpeg_profile_combo.setCurrentText("Custom")
        self.ffmpeg_profile_combo.blockSignals(False)

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
            # Need to handle unsharp group check state, not old checkbox
            if hasattr(self, 'unsharp_group'): self.unsharp_group.setChecked(cast(bool, profile.get("apply_unsharp", True)))
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

            # --- Ensure group boxes are expanded/checked correctly when applying a profile ---
            if hasattr(self, 'minterpolate_group'):
                self.minterpolate_group.setChecked(True) # Always expand interpolation
            if hasattr(self, 'unsharp_group'):
                self.unsharp_group.setChecked(cast(bool, profile.get("apply_unsharp", True)))

            # --- Update content visibility based on new groupbox check state ---
            if hasattr(self, 'minterpolate_group') and hasattr(self, '_toggle_minterpolate_content'):
                self._toggle_minterpolate_content(self.minterpolate_group.isChecked())
            if hasattr(self, 'unsharp_group') and hasattr(self, '_toggle_unsharp_content'):
                self._toggle_unsharp_content(self.unsharp_group.isChecked())

            # --- Update dependent control states ---
            if hasattr(self, 'ffmpeg_interp_cb'):
                self._update_ffmpeg_controls_state(self.ffmpeg_interp_cb.isChecked()) # Handles interp/unsharp groups

        finally:
            # --- Re-enable signals and flag ---
            if hasattr(self, 'ffmpeg_profile_combo'):
                 self.ffmpeg_profile_combo.blockSignals(False)
            self._ffmpeg_setting_change_active = True
            LOGGER.debug(f"Finished applying profile: {profile_name}")

    def _update_ffmpeg_controls_state(self, enable: bool) -> None:
        """Enables/disables all interpolation and sharpening controls based on the main checkbox."""
        # Find group boxes within the FFmpeg Settings tab
        ffmpeg_tab_index = -1
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "FFmpeg Settings":
                ffmpeg_tab_index = i
                break

        if ffmpeg_tab_index == -1:
            LOGGER.error("Could not find 'FFmpeg Settings' tab to update controls.")
            return

        ffmpeg_tab_widget = self.tab_widget.widget(ffmpeg_tab_index)
        if not ffmpeg_tab_widget:
            LOGGER.error("Widget for 'FFmpeg Settings' tab is invalid.")
            return

        minterpolate_group = ffmpeg_tab_widget.findChild(QGroupBox, "minterpolate_group")
        unsharp_group = ffmpeg_tab_widget.findChild(QGroupBox, "unsharp_group")
        quality_group = ffmpeg_tab_widget.findChild(QGroupBox, "quality_group")

        # Fallback to finding by title if object names aren't found
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

        # Quality group itself remains enabled/visible
        if quality_group:
            quality_group.setEnabled(True)
            quality_group.setVisible(True)

    def _update_scd_thresh_state(self, scd_mode: str) -> None:
        # Only enable threshold if scd_mode is fdiff
        enable = (scd_mode == "fdiff")
        if hasattr(self, 'scd_thresh_spin'):
            self.scd_thresh_spin.setEnabled(enable)

    def _update_unsharp_controls_state(self, checked: bool) -> None:
        # Only enable the unsharp group if main interp is enabled AND unsharp checkbox is checked
        # NOTE: This logic might be outdated if the unsharp group is directly toggled
        main_interp_enabled = hasattr(self, 'ffmpeg_interp_cb') and self.ffmpeg_interp_cb.isChecked()
        enable_group = main_interp_enabled and checked

        ffmpeg_tab_index = -1
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "FFmpeg Settings":
                ffmpeg_tab_index = i
                break
        if ffmpeg_tab_index == -1: return
        ffmpeg_tab_widget = self.tab_widget.widget(ffmpeg_tab_index)
        if not ffmpeg_tab_widget: return

        unsharp_group = ffmpeg_tab_widget.findChild(QGroupBox, "unsharp_group")
        if not unsharp_group:
            unsharp_group = ffmpeg_tab_widget.findChild(QGroupBox, "Sharpening (unsharp)")

        if unsharp_group:
            unsharp_group.setEnabled(enable_group)

    def _toggle_minterpolate_content(self, checked: bool) -> None:
        # Moved from ~line 1843
        """Show/hide the content widget within the minterpolate group box."""
        if hasattr(self, 'minterpolate_content_widget'):
            self.minterpolate_content_widget.setVisible(checked)
        else:
            LOGGER.warning("minterpolate_content_widget not found in _toggle_minterpolate_content")

    def _toggle_unsharp_content(self, checked: bool) -> None:
        # Moved from ~line 1852
        """Show/hide the content widget within the unsharp group box."""
        if hasattr(self, 'unsharp_content_widget'):
            self.unsharp_content_widget.setVisible(checked)
        else:
            LOGGER.warning("unsharp_content_widget not found in _toggle_unsharp_content")

    def _update_quality_controls_state(self, encoder_type: str) -> None:
        # Moved from ~line 2187
        """Enables/disables quality controls based on the selected encoder type."""
        if not hasattr(self, 'preset_combo') or not hasattr(self, 'bitrate_spin') or not hasattr(self, 'bufsize_spin'):
            return

        # Normalize encoder type string for comparison
        encoder_lower = encoder_type.lower()

        # Define keywords for hardware encoders (adjust if needed)
        hardware_keywords = ["hardware", "videotoolbox", "nvenc", "qsv", "vaapi", "vdpau"]
        # RIFE/FFmpeg are considered software for CRF control purposes
        is_software_crf = encoder_lower in ["rife", "ffmpeg"]
        is_hardware = any(keyword in encoder_lower for keyword in hardware_keywords)

        # Logic: CRF preset for software, Bitrate/Bufsize for hardware
        enable_crf_preset = is_software_crf
        enable_bitrate_bufsize = is_hardware

        # Apply enabling/disabling
        self.preset_combo.setEnabled(enable_crf_preset)
        self.bitrate_spin.setEnabled(enable_bitrate_bufsize)
        self.bufsize_spin.setEnabled(enable_bitrate_bufsize)

        # Update the UI to show visual indication of disabled state (optional styling)
        disabled_style = "color: #888888;"
        self.preset_combo.setStyleSheet(disabled_style if not enable_crf_preset else "")
        self.bitrate_spin.setStyleSheet(disabled_style if not enable_bitrate_bufsize else "")
        self.bufsize_spin.setStyleSheet(disabled_style if not enable_bitrate_bufsize else "")
    # --- End Inserted Methods ---

    def _start(self) -> None:
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Busy", "Interpolation is already running. Please wait for the current process to finish.")
            return

        in_dir = pathlib.Path(self.in_edit.text()).expanduser()
        out_file = pathlib.Path(self.out_edit.text()).expanduser()

        # Enhanced user error feedback for input validation
        if not in_dir.is_dir():
            self._show_error("Input folder not found:\n{}\n\nPlease select a valid folder containing PNG images.".format(in_dir), stage="Input Validation", user_error=True)
            return
        if not out_file.parent.exists():
            self._show_error("Output directory not found:\n{}\n\nPlease select a valid output directory.".format(out_file.parent), stage="Input Validation", user_error=True)
            return
        if not self.out_edit.text() or not out_file.name:
            self._show_error("Output filename cannot be empty.\n\nPlease specify a valid output filename.", stage="Input Validation", user_error=True)
            return

        # Ensure output directory exists (though parent check mostly covers this)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        # Check for input PNGs
        if not any(in_dir.glob("*.png")):
            self._show_error("No PNG images found in:\n{}\n\nPlease ensure the input folder contains PNG files.".format(in_dir), stage="Input Validation", user_error=True)
            return

        # Gather settings
        fps = self.fps_spin.value()
        mid_count = self.inter_spin.value()
        encoder = self.encoder_combo.currentText()
        skip_model = self.skip_model_cb.isChecked()
        model_key = self.model_combo.currentText()
        # RIFE settings
        rife_tile_enable = self.rife_tile_enable_cb.isChecked()
        rife_tile_size = self.rife_tile_size_spin.value()
        rife_uhd_mode = self.rife_uhd_mode_cb.isChecked()
        rife_thread_spec = self.rife_thread_spec_edit.text()
        rife_tta_spatial = self.rife_tta_spatial_cb.isChecked()
        rife_tta_temporal = self.rife_tta_temporal_cb.isChecked()
        # Sanchez settings
        false_colour = self.false_colour_check.isChecked()
        sanchez_res_km = self.sanchez_res_spin.value()
        # FFmpeg settings (Corrected retrieval from UI elements)
        use_ffmpeg_interp = self.ffmpeg_interp_cb.isChecked()
        filter_preset = self.filter_preset_combo.currentText()
        mi_mode = self.mi_combo.currentText()
        mc_mode = self.mc_combo.currentText()
        me_mode = self.me_combo.currentText()
        me_algo = self.me_algo_combo.currentText()
        search_param = self.search_param_spin.value()
        scd_mode = self.scd_combo.currentText()
        scd_threshold = self.scd_thresh_spin.value() if self.scd_thresh_spin.isEnabled() else None
        # Correctly check combo box text for mb_size
        mb_size_text = self.mbsize_combo.currentText()
        minter_mb_size = int(mb_size_text) if mb_size_text != "(default)" else None
        minter_vsbmc = 1 if self.vsbmc_cb.isChecked() else 0
        apply_unsharp = self.unsharp_group.isChecked() # Get state from groupbox
        unsharp_lx = self.luma_x_spin.value()
        unsharp_ly = self.luma_y_spin.value()
        unsharp_la = self.luma_amount_spin.value()
        unsharp_cx = self.chroma_x_spin.value()
        unsharp_cy = self.chroma_y_spin.value()
        unsharp_ca = self.chroma_amount_spin.value()
        # Get quality settings based on encoder type
        if self.preset_combo.isEnabled(): # Software encoder (RIFE/FFmpeg)
            preset_text = self.preset_combo.currentText()
            # Extract CRF value from preset text (e.g., "Very High (CRF 16)")
            crf_match = re.search(r'\(CRF (\d+)\)', preset_text)
            crf = int(crf_match.group(1)) if crf_match else 20 # Default to 20 if parsing fails
            bitrate_kbps = -1 # Indicate CRF mode to worker
            bufsize_kb = -1 # Indicate CRF mode to worker
        else: # Hardware encoder
            crf = -1 # Indicate bitrate mode to worker
            bitrate_kbps = self.bitrate_spin.value()
            bufsize_kb = self.bufsize_spin.value()
        pix_fmt = self.pixfmt_combo.currentText()

        # Reset progress and status
        self.progress_bar.setValue(0)

        # Use cast for crop_rect type hint consistency
        current_crop_rect = self.crop_rect

        # Start worker
        self.worker = VfiWorker(
            in_dir=in_dir,
            out_file_path=out_file,
            fps=fps,
            mid_count=mid_count,
            max_workers=4, # Placeholder for max_workers spinbox if added
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
            crf=crf,
            bitrate_kbps=bitrate_kbps,
            bufsize_kb=bufsize_kb,
            pix_fmt=pix_fmt,
            # RIFE settings
            model_key=model_key,
            rife_tile_enable=rife_tile_enable,
            rife_tile_size=rife_tile_size,
            rife_uhd_mode=rife_uhd_mode,
            rife_thread_spec=rife_thread_spec,
            rife_tta_spatial=rife_tta_spatial,
            rife_tta_temporal=rife_tta_temporal,
            # Sanchez settings
            false_colour=false_colour,
            res_km=sanchez_res_km,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(lambda msg: self._show_error(msg, stage="Processing"))
        self.worker.start()

        # Reset progress and status & Set Processing State
        self._set_processing_state(True)
        # Update status messages after setting processing state
        self.status_bar.showMessage("Preparing to start interpolation...", 3000)
        if hasattr(self, 'eta_label'): self.eta_label.setText("ETA: Starting...")

    def _on_progress(self, current: int, total: int, eta: float) -> None:
        """Update progress bar, ETA label, and status bar with detailed feedback."""
        try:
            LOGGER.debug(f"_on_progress called with: current={current}, total={total}, eta={eta}") # Add log
            if total > 0:
                LOGGER.debug(f"Updating progress bar: range(0, {total}), value({current})") # Add log
                self.progress_bar.setRange(0, total)
                self.progress_bar.setValue(current)
                percent = int((current / total) * 100) if total else 0
                # Format ETA nicely
                if eta > 0:
                    eta_seconds = int(eta)
                    minutes = eta_seconds // 60
                    seconds = eta_seconds % 60
                    eta_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
                    self.eta_label.setText(f"ETA: {eta_str}")
                else:
                    self.eta_label.setText("ETA: --")
                # Show progress in status bar with percent
                self.status_bar.showMessage(f"Processing frames: {current}/{total} ({percent}%) - ETA: {self.eta_label.text()[5:]}", 2000)
            else:
                self.progress_bar.setRange(0, 0)
                self.eta_label.setText("ETA: --")
                self.status_bar.showMessage("Processing...", 2000)
            LOGGER.debug("_on_progress finished successfully.")
        except Exception as e:
            LOGGER.exception(f"!!! EXCEPTION IN _on_progress !!!")
            # Optionally re-raise or handle differently
            # raise # Re-raising might make tests fail more obviously if an error occurs here

    def _on_finished(self, mp4: pathlib.Path) -> None:
        # Mark progress done and update UI for success
        self._set_processing_state(False) # Reset UI state first
        # Update status bar after UI is re-enabled
        self.status_bar.showMessage(f"Finished successfully: {mp4.name}")
        # Update progress/ETA labels (redundant if _set_processing_state resets them)
        # if hasattr(self, 'progress_bar'):
        #     self.progress_bar.setRange(0, 1)
        #     self.progress_bar.setValue(1)
        # if hasattr(self, 'eta_label'): self.eta_label.setText("ETA: Done")

        # Store the path for the Open button
        self._last_out = mp4
        # Ensure Open button state is correct after setting processing state
        if hasattr(self, 'open_btn'):
             self.open_btn.setEnabled(hasattr(self, '_last_out') and self._last_out.exists())

        # --- Load mid-frame preview --- #
        if self.worker and hasattr(self.worker, 'mid_frame_path'):
            mid_png_path_str = getattr(self.worker, 'mid_frame_path', None)
            if mid_png_path_str:
                mid_png = pathlib.Path(mid_png_path_str)
                if mid_png.exists():
                    try:
                        pixm = QPixmap(str(mid_png)).scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        self.preview_mid.setPixmap(pixm)
                        self.preview_mid.file_path = str(mid_png)
                        if not pixm.isNull():
                            self.preview_mid.setText("")
                    except Exception as e:
                        LOGGER.error(f"Error loading mid-frame preview '{mid_png}': {e}")
                        self.preview_mid.setText("Mid frame\n(Error)")
                else:
                    LOGGER.warning(f"Mid-frame path provided but file not found: {mid_png}")
                    self.preview_mid.setText("Mid frame\n(Not found)")
            else:
                LOGGER.info("No mid-frame path available after run.")
                self.preview_mid.setText("Mid frame")
        else:
            LOGGER.warning("Worker or mid_frame_path attribute not available in _on_finished")
        # --- End mid-frame preview logic ---

        self._show_info(f"Video saved to:\n{mp4}\n\nYou can now open the output file or start a new job.")

    def _show_error(self, msg: str, stage: str = "Error", user_error: bool = False) -> None:
        """
        Enhanced error dialog and feedback.
        - stage: Optional string indicating which stage failed.
        - user_error: If True, treat as user input error (friendlier wording).
        """
        LOGGER.error(f"{stage}: {msg}")
        self._set_processing_state(False) # Reset UI state first
        # Update status after UI is re-enabled
        self.status_bar.showMessage(f"Error: {stage}", 5000)

        # Friendlier error dialog
        if user_error:
            QMessageBox.warning(self, "Input Error", f"{msg}\n\nPlease check your input and try again.")
        else:
            QMessageBox.critical(self, "Processing Error", f"{stage} failed.\n\nDetails:\n{msg}")

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
                    x, y, w, h = self.crop_rect # Removed redundant cast
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
        """Enable/disable the tile size spinbox based on the tile checkbox and RIFE capability."""
        self._update_rife_ui_elements()
        # The following lines were removed as they were incorrectly indented and likely remnants of previous code:
        # # (This duplicate function definition is removed to resolve the lint error)
        #         LOGGER.warning("minterpolate_content_widget not found in _toggle_minterpolate_content")
        #         LOGGER.warning("minterpolate_content_widget not found in _toggle_minterpolate_content")
        #         LOGGER.warning("minterpolate_content_widget not found in _toggle_minterpolate_content")
        #         LOGGER.warning("minterpolate_content_widget not found in _toggle_minterpolate_content")
        #         LOGGER.warning("minterpolate_content_widget not found in _toggle_minterpolate_content")
            # QTimer.singleShot(0, self._adjust_window_to_content)
        if hasattr(self, 'unsharp_content_widget'):
            self.unsharp_content_widget.setVisible(checked)
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
        settings = self.settings # Use instance member
        self._geometry_restored = False # Flag to track if geometry was loaded

        # --- Window Geometry ---
        geom = settings.value("window/geometry")
        if isinstance(geom, QByteArray):
             if self.restoreGeometry(geom):
                 self._geometry_restored = True
                 LOGGER.debug("Restored window geometry.")
             else:
                 LOGGER.warning("Failed to restore window geometry from settings.")

        # --- Main Tab ---
        if hasattr(self, 'in_edit'):
            self.in_edit.setText(settings.value("main/inputDir", "", type=str))

        # --- Output Path --- #
        # Load last used full output path if available, otherwise derive default
        saved_output_path = settings.value("main/outputFile", "", type=str)
        if saved_output_path and pathlib.Path(saved_output_path).parent.exists():
            if hasattr(self, 'out_edit'): self.out_edit.setText(saved_output_path)
            LOGGER.info(f"Loaded output path: {saved_output_path}")
        else:
            # Derive default if saved path is missing or invalid
            input_dir_str = getattr(self, 'in_edit', QLineEdit()).text()
            out_dir = config.get_output_dir()
            out_dir.mkdir(parents=True, exist_ok=True)
            base_name = "goes_timelapse"
            # Try to use input dir name for default output name
            try:
                input_path = pathlib.Path(input_dir_str)
                if input_path.is_dir() and input_path.name:
                    base_name = f"{input_path.name}_timelapse"
            except Exception:
                pass # Keep default base name
            # Add timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"{base_name}_{timestamp}.mp4"
            default_path = out_dir / default_filename
            if hasattr(self, 'out_edit'): self.out_edit.setText(str(default_path))
            LOGGER.info(f"Derived default output path: {default_path}")

        # --- Load Last Directory (used for browsers) ---
        self.last_dir = pathlib.Path(settings.value("main/lastDir", str(pathlib.Path.home())))

        # --- Other Main Tab Settings ---
        if hasattr(self, 'fps_spin'): self.fps_spin.setValue(settings.value("main/fps", 30, type=int))
        if hasattr(self, 'encoder_combo'): self.encoder_combo.setCurrentText(settings.value("main/encoder", "RIFE", type=str))
        if hasattr(self, 'skip_model_cb'): self.skip_model_cb.setChecked(settings.value("main/skipModel", False, type=bool))
        # Load crop rect
        saved_crop_str = settings.value("main/cropRect", None)
        crop_tuple: Optional[Tuple[int, int, int, int]] = None
        if isinstance(saved_crop_str, str):
            try:
                parts = list(map(int, saved_crop_str.split(',')))
                if len(parts) == 4:
                    crop_tuple = (parts[0], parts[1], parts[2], parts[3])
            except (ValueError, TypeError):
                LOGGER.warning(f"Could not parse cropRect from settings: {saved_crop_str}")
        self.crop_rect = crop_tuple

        # --- RIFE v4.6 Settings ---
        if hasattr(self, 'inter_spin'): self.inter_spin.setValue(settings.value("rife/intermediateFrames", 1, type=int))
        if hasattr(self, 'model_combo'): self.model_combo.setCurrentText(settings.value("rife/modelName", "rife-v4.6", type=str))
        if hasattr(self, 'rife_tile_enable_cb'): self.rife_tile_enable_cb.setChecked(settings.value("rife/tilingEnabled", False, type=bool))
        if hasattr(self, 'rife_tile_size_spin'): self.rife_tile_size_spin.setValue(settings.value("rife/tileSize", 256, type=int))
        if hasattr(self, 'rife_uhd_mode_cb'): self.rife_uhd_mode_cb.setChecked(settings.value("rife/uhdMode", False, type=bool))
        if hasattr(self, 'rife_thread_spec_edit'): self.rife_thread_spec_edit.setText(settings.value("rife/threadSpec", "1:2:2", type=str))
        if hasattr(self, 'rife_tta_spatial_cb'): self.rife_tta_spatial_cb.setChecked(settings.value("rife/ttaSpatial", False, type=bool))
        if hasattr(self, 'rife_tta_temporal_cb'): self.rife_tta_temporal_cb.setChecked(settings.value("rife/ttaTemporal", False, type=bool))

        # --- Enhancements (Sanchez) ---
        if hasattr(self, 'false_colour_check'): self.false_colour_check.setChecked(settings.value("enhancements/falseColour", False, type=bool))
        if hasattr(self, 'sanchez_res_spin'): self.sanchez_res_spin.setValue(settings.value("enhancements/sanchezResKm", 4, type=int))

        # --- FFmpeg Settings Tab --- #
        # Load profile first, but don't apply it yet
        loaded_profile = settings.value("ffmpeg/profile", "Default", type=str)

        # Load individual FFmpeg settings
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
        if hasattr(self, 'unsharp_group'): self.unsharp_group.setChecked(settings.value("ffmpeg/unsharpChecked", True, type=bool))
        if hasattr(self, 'luma_x_spin'): self.luma_x_spin.setValue(settings.value("ffmpeg/unsharpLx", 7, type=int))
        if hasattr(self, 'luma_y_spin'): self.luma_y_spin.setValue(settings.value("ffmpeg/unsharpLy", 7, type=int))
        if hasattr(self, 'luma_amount_spin'): self.luma_amount_spin.setValue(settings.value("ffmpeg/unsharpLa", 1.0, type=float))
        if hasattr(self, 'chroma_x_spin'): self.chroma_x_spin.setValue(settings.value("ffmpeg/unsharpCx", 5, type=int))
        if hasattr(self, 'chroma_y_spin'): self.chroma_y_spin.setValue(settings.value("ffmpeg/unsharpCy", 5, type=int))
        if hasattr(self, 'chroma_amount_spin'): self.chroma_amount_spin.setValue(settings.value("ffmpeg/unsharpCa", 0.0, type=float))
        if hasattr(self, 'preset_combo'): self.preset_combo.setCurrentText(settings.value("ffmpeg/presetCRF", "Very High (CRF 16)", type=str))
        if hasattr(self, 'bitrate_spin'): self.bitrate_spin.setValue(settings.value("ffmpeg/bitrate", 15000, type=int))
        if hasattr(self, 'bufsize_spin'): self.bufsize_spin.setValue(settings.value("ffmpeg/bufsize", 22500, type=int))
        if hasattr(self, 'pixfmt_combo'): self.pixfmt_combo.setCurrentText(settings.value("ffmpeg/pixFmt", "yuv444p", type=str))
        if hasattr(self, 'minterpolate_group'): self.minterpolate_group.setChecked(settings.value("ffmpeg/minterpolateChecked", True, type=bool))

        # --- Set Profile ComboBox *after* loading individual settings ---
        if hasattr(self, 'ffmpeg_profile_combo'):
            self.ffmpeg_profile_combo.blockSignals(True)
            self.ffmpeg_profile_combo.setCurrentText(loaded_profile)
            self.ffmpeg_profile_combo.blockSignals(False)
            # If the loaded profile was NOT custom, re-apply it to ensure consistency
            if loaded_profile != "Custom" and loaded_profile in FFMPEG_PROFILES:
                self._apply_ffmpeg_profile(loaded_profile)
            else:
                 # Check if the loaded settings match any known profile, otherwise set to Custom
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

        # --- Update UI state after loading --- #
        # Manually trigger state updates for dependent controls
        if hasattr(self, 'rife_tile_enable_cb'): self._toggle_tile_size_enabled(self.rife_tile_enable_cb.isChecked())
        if hasattr(self, 'skip_model_cb') and hasattr(self, 'rife_opts_group'): # Assuming rife_opts_group exists
            self.rife_opts_group.setEnabled(not self.skip_model_cb.isChecked())
        if hasattr(self, 'false_colour_check'): self._toggle_sanchez_res_enabled(self.false_colour_check.checkState().value)
        if hasattr(self, 'ffmpeg_interp_cb'): self._update_ffmpeg_controls_state(self.ffmpeg_interp_cb.isChecked())
        if hasattr(self, 'scd_combo'): self._update_scd_thresh_state(self.scd_combo.currentText())
        # Update unsharp content visibility based on group check state
        if hasattr(self, 'unsharp_group'): self._toggle_unsharp_content(self.unsharp_group.isChecked())
        if hasattr(self, 'minterpolate_group'): self._toggle_minterpolate_content(self.minterpolate_group.isChecked())
        # Populate models after loading other settings
        self._populate_models()
        # Load RIFE model selection AFTER populating the combo box
        if hasattr(self, 'model_combo'):
            saved_model = settings.value("rife/modelName", "rife-v4.6", type=str)
            self.model_combo.setCurrentText(saved_model)
            # Ensure combo box is enabled correctly based on population
            if self.model_combo.count() > 0 and not self.model_combo.currentText().startswith(("Error", "No models")):
                self.model_combo.setEnabled(True)
            else:
                self.model_combo.setEnabled(False)

        self._update_previews() # Load previews based on loaded input dir
        self._ffmpeg_setting_change_active = True # Re-enable profile switching
        LOGGER.info("Settings loaded.")

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

    def _connect_model_combo(self) -> None: # Add -> None return type
        """Connect model selection change to update RIFE capabilities."""
        if hasattr(self, 'model_combo'):
            self.model_combo.currentTextChanged.connect(self._on_model_changed)

    def _toggle_sanchez_res_enabled(self, state: Qt.CheckState) -> None:
        # State is Qt.CheckState enum value (Unchecked=0, PartiallyChecked=1, Checked=2)
        enable = (state == Qt.CheckState.Checked) # Compare with enum member
        if hasattr(self, 'sanchez_res_label'): self.sanchez_res_label.setEnabled(enable)
        if hasattr(self, 'sanchez_res_spin'): self.sanchez_res_spin.setEnabled(enable)
        
    def _update_rife_ui_elements(self) -> None:
        """Update UI elements based on RIFE capabilities."""
        # Update UI elements using the capability manager
        self.rife_capability_manager.update_ui_elements(
            self.rife_tile_enable_cb,
            self.rife_tile_size_spin,
            self.rife_uhd_mode_cb,
            self.rife_thread_spec_edit,
            self.thread_spec_label,
            self.rife_tta_spatial_cb,
            self.rife_tta_temporal_cb
        )
        
        # Update capability summary label
        self.rife_capability_label.setText(self.rife_capability_manager.get_capability_summary())
        
    def _on_model_changed(self, model_key: str) -> None:
        """Handle model selection change."""
        # Update the capability manager with the new model
        self.rife_capability_manager = RifeCapabilityManager(model_key)
        
        # Update UI elements based on new capabilities
        self._update_rife_ui_elements()

    def closeEvent(self, event: QCloseEvent | None) -> None:
        LOGGER.info("Saving settings...")
        settings = self.settings # Use instance member

        # --- Window Geometry ---
        settings.setValue("window/geometry", self.saveGeometry())

        # --- Main Tab ---
        if hasattr(self, 'in_edit'): settings.setValue("main/inputDir", self.in_edit.text())
        if hasattr(self, 'out_edit'): settings.setValue("main/outputFile", self.out_edit.text()) # Save full path
        # Save parent dir of output if available
        if hasattr(self, 'out_edit'):
            try:
                out_path = pathlib.Path(self.out_edit.text())
                settings.setValue("main/lastDir", str(out_path.parent))
            except Exception:
                # Fallback to saving input dir's parent if output is invalid
                if hasattr(self, 'in_edit'):
                     try:
                        in_path = pathlib.Path(self.in_edit.text())
                        settings.setValue("main/lastDir", str(in_path.parent))
                     except Exception:
                         settings.setValue("main/lastDir", str(pathlib.Path.home())) # Absolute fallback
                else:
                    settings.setValue("main/lastDir", str(pathlib.Path.home()))

        if hasattr(self, 'fps_spin'): settings.setValue("main/fps", self.fps_spin.value())
        if hasattr(self, 'inter_spin'): settings.setValue("rife/intermediateFrames", self.inter_spin.value()) # Note: Moved to RIFE section
        if hasattr(self, 'encoder_combo'): settings.setValue("main/encoder", self.encoder_combo.currentText())
        if hasattr(self, 'skip_model_cb'): settings.setValue("main/skipModel", self.skip_model_cb.isChecked())
        # Save crop rect if it exists
        if self.crop_rect:
            settings.setValue("main/cropRect", ",".join(map(str, self.crop_rect)))
        else:
            settings.remove("main/cropRect") # Remove if cleared

        # --- RIFE v4.6 Settings --- #
        if hasattr(self, 'model_combo'): settings.setValue("rife/modelName", self.model_combo.currentText())
        if hasattr(self, 'rife_tile_enable_cb'): settings.setValue("rife/tilingEnabled", self.rife_tile_enable_cb.isChecked())
        if hasattr(self, 'rife_tile_size_spin'): settings.setValue("rife/tileSize", self.rife_tile_size_spin.value())
        if hasattr(self, 'rife_uhd_mode_cb'): settings.setValue("rife/uhdMode", self.rife_uhd_mode_cb.isChecked())
        if hasattr(self, 'rife_thread_spec_edit'): settings.setValue("rife/threadSpec", self.rife_thread_spec_edit.text())
        if hasattr(self, 'rife_tta_spatial_cb'): settings.setValue("rife/ttaSpatial", self.rife_tta_spatial_cb.isChecked())
        if hasattr(self, 'rife_tta_temporal_cb'): settings.setValue("rife/ttaTemporal", self.rife_tta_temporal_cb.isChecked())

        # --- Enhancements (Sanchez) ---
        if hasattr(self, 'false_colour_check'): settings.setValue("enhancements/falseColour", self.false_colour_check.isChecked())
        if hasattr(self, 'sanchez_res_spin'): settings.setValue("enhancements/sanchezResKm", self.sanchez_res_spin.value())

        # --- FFmpeg Settings Tab ---
        if hasattr(self, 'ffmpeg_profile_combo'): settings.setValue("ffmpeg/profile", self.ffmpeg_profile_combo.currentText())
        if hasattr(self, 'ffmpeg_interp_cb'): settings.setValue("ffmpeg/enabled", self.ffmpeg_interp_cb.isChecked())
        if hasattr(self, 'mi_combo'): settings.setValue("ffmpeg/miMode", self.mi_combo.currentText())
        if hasattr(self, 'mc_combo'): settings.setValue("ffmpeg/mcMode", self.mc_combo.currentText())
        if hasattr(self, 'me_combo'): settings.setValue("ffmpeg/meMode", self.me_combo.currentText())
        if hasattr(self, 'me_algo_combo'): settings.setValue("ffmpeg/meAlgo", self.me_algo_combo.currentText())
        if hasattr(self, 'search_param_spin'): settings.setValue("ffmpeg/searchParam", self.search_param_spin.value())
        if hasattr(self, 'scd_combo'): settings.setValue("ffmpeg/scdMode", self.scd_combo.currentText())
        if hasattr(self, 'scd_thresh_spin'): settings.setValue("ffmpeg/scdThreshold", self.scd_thresh_spin.value())
        if hasattr(self, 'filter_preset_combo'): settings.setValue("ffmpeg/filterPreset", self.filter_preset_combo.currentText())
        if hasattr(self, 'mbsize_combo'): settings.setValue("ffmpeg/mbSize", self.mbsize_combo.currentText())
        if hasattr(self, 'vsbmc_cb'): settings.setValue("ffmpeg/vsbmc", self.vsbmc_cb.isChecked())
        if hasattr(self, 'unsharp_group'): settings.setValue("ffmpeg/unsharpChecked", self.unsharp_group.isChecked())
        if hasattr(self, 'luma_x_spin'): settings.setValue("ffmpeg/unsharpLx", self.luma_x_spin.value())
        if hasattr(self, 'luma_y_spin'): settings.setValue("ffmpeg/unsharpLy", self.luma_y_spin.value())
        if hasattr(self, 'luma_amount_spin'): settings.setValue("ffmpeg/unsharpLa", self.luma_amount_spin.value())
        if hasattr(self, 'chroma_x_spin'): settings.setValue("ffmpeg/unsharpCx", self.chroma_x_spin.value())
        if hasattr(self, 'chroma_y_spin'): settings.setValue("ffmpeg/unsharpCy", self.chroma_y_spin.value())
        if hasattr(self, 'chroma_amount_spin'): settings.setValue("ffmpeg/unsharpCa", self.chroma_amount_spin.value())
        if hasattr(self, 'preset_combo'): settings.setValue("ffmpeg/presetCRF", self.preset_combo.currentText())
        if hasattr(self, 'bitrate_spin'): settings.setValue("ffmpeg/bitrate", self.bitrate_spin.value())
        if hasattr(self, 'bufsize_spin'): settings.setValue("ffmpeg/bufsize", self.bufsize_spin.value())
        if hasattr(self, 'pixfmt_combo'): settings.setValue("ffmpeg/pixFmt", self.pixfmt_combo.currentText())
        if hasattr(self, 'minterpolate_group'): settings.setValue("ffmpeg/minterpolateChecked", self.minterpolate_group.isChecked())
        # Note: unsharpChecked is already saved above

        LOGGER.info("Settings saved.")
        super().closeEvent(event) # Accept the close event

    # +++ Re-insert _update_previews method +++
    def _update_previews(self) -> None:
        # Moved from ~line 1762 / Restored after accidental deletion
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
                    x,y,w,h = self.crop_rect
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

    def _update_start_button_state(self) -> None:
        """Enables the start button only if both input and output paths are set."""
        # Ensure widgets exist before accessing text
        if hasattr(self, 'in_edit') and hasattr(self, 'out_edit') and hasattr(self, 'start_btn'):
            in_path = self.in_edit.text().strip()
            out_path = self.out_edit.text().strip()
            self.start_btn.setEnabled(bool(in_path and out_path))

    def _set_processing_state(self, processing: bool) -> None:
        """Sets the UI state for processing (True) or idle (False)."""
        enable_idle = not processing

        # Core Controls
        if hasattr(self, 'start_btn'): self.start_btn.setEnabled(enable_idle)
        if hasattr(self, 'tab_widget'): self.tab_widget.setEnabled(enable_idle)

        # Input/Output Controls
        if hasattr(self, 'in_edit'): self.in_edit.setEnabled(enable_idle)
        if hasattr(self, 'out_edit'): self.out_edit.setEnabled(enable_idle)
        if hasattr(self, 'in_btn'): self.in_btn.setEnabled(enable_idle)
        if hasattr(self, 'out_btn'): self.out_btn.setEnabled(enable_idle)
        if hasattr(self, 'crop_btn'): self.crop_btn.setEnabled(enable_idle)
        if hasattr(self, 'clear_crop_btn'): self.clear_crop_btn.setEnabled(enable_idle)
        if hasattr(self, 'open_btn'): self.open_btn.setEnabled(enable_idle and hasattr(self, '_last_out') and self._last_out.exists())

        # Main Tab Settings (Consider disabling these too)
        if hasattr(self, 'fps_spin'): self.fps_spin.setEnabled(enable_idle)
        if hasattr(self, 'inter_spin'): self.inter_spin.setEnabled(enable_idle)
        if hasattr(self, 'encoder_combo'): self.encoder_combo.setEnabled(enable_idle)
        if hasattr(self, 'skip_model_cb'): self.skip_model_cb.setEnabled(enable_idle)
        if hasattr(self, 'model_combo'): self.model_combo.setEnabled(enable_idle)
        # Add other main tab controls (RIFE group, Enhancements group) if needed

        # Reset progress bar if stopping processing
        if not processing:
            if hasattr(self, 'progress_bar'):
                 self.progress_bar.setRange(0, 1)
                 self.progress_bar.setValue(0)
            if hasattr(self, 'eta_label'): self.eta_label.setText("ETA: --")

    def _update_crop_buttons_state(self) -> None:
        """Enables crop buttons only if input path is set."""
        if hasattr(self, 'in_edit') and hasattr(self, 'crop_btn') and hasattr(self, 'clear_crop_btn'):
            in_path = self.in_edit.text().strip()
            enable = bool(in_path)
            self.crop_btn.setEnabled(enable)
            # Clear button enabled if input path is set OR if a crop is currently defined
            self.clear_crop_btn.setEnabled(enable or self.crop_rect is not None)

    # --- Update RIFE Options State --- #
    def _update_rife_options_state(self) -> None:
        """Enable/disable RIFE options group based on encoder and skip model settings."""
        is_rife_selected = self.encoder_combo.currentText() == "RIFE"
        is_skip_model = self.skip_model_cb.isChecked()
        self.rife_opts_group.setEnabled(is_rife_selected and not is_skip_model)
        # Optional: You might want to visually indicate why it's disabled,
        # e.g., by changing the group box title or adding a status message,
        # but for now, just enabling/disabling is standard.

# --- REMOVED DUPLICATE _on_profile_selected METHOD ---

# ────────────────────────── top‑level launcher ────────────────────────────
def main() -> None:
    # --- Add Argument Parsing --- #
    parser = argparse.ArgumentParser(description="GOES-VFI GUI")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    # --- Setup Logging Level ---
    log.set_level(args.debug) # Call set_level based on parsed arg

    app = QApplication(sys.argv)
    # Pass the parsed debug flag to the MainWindow
    win = MainWindow(debug_mode=args.debug)
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
