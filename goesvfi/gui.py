# TODO: PyQt6 main window implementation
from __future__ import annotations
from goesvfi.pipeline.image_cropper import ImageCropper
from goesvfi.pipeline.sanchez_processor import SanchezProcessor
from goesvfi.pipeline.image_loader import ImageLoader
from goesvfi.pipeline.image_processing_interfaces import ImageData, ImageProcessor
from goesvfi.view_models.main_window_view_model import (
    MainWindowViewModel,
)  # <-- Add ViewModel import
from goesvfi.date_sorter.sorter import DateSorter  # <-- Add Model import
from goesvfi.file_sorter.sorter import FileSorter  # <-- Add Model import
from goesvfi.date_sorter.gui_tab import DateSorterTab
from goesvfi.file_sorter.gui_tab import FileSorterTab

"""
GOES‑VFI PyQt6 GUI – v0.1
Run with:  python -m goesvfi.gui
"""

import sys
import pathlib
import argparse  # <-- Import argparse
import importlib.resources as pkgres
import re  # <-- Import re for regex
import time  # <-- Import time for time.sleep
import tempfile  # Import tempfile for temporary files handling
import shutil  # Import shutil for file operations
from typing import (
    Optional,
    Any,
    cast,
    Union,
    Tuple,
    Iterator,
    Dict,
    List,
    TypedDict,
)  # Added Dict, List, cast, TypedDict
from datetime import datetime
from PyQt6.QtCore import (
    QThread,
    pyqtSignal,
    Qt,
    QSize,
    QPoint,
    QRect,
    QSettings,
    QByteArray,
    QTimer,
    QUrl,
)  # Added QTimer, QUrl
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QMessageBox,
    QComboBox,
    QCheckBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QStatusBar,
    QDialog,
    QDialogButtonBox,
    QRubberBand,
    QGridLayout,
    QDoubleSpinBox,
    QGroupBox,
    QSizePolicy,
    QSplitter,
    QScrollArea,  # Added GroupBox, SizePolicy, Splitter, ScrollArea
)
import pathlib
from PyQt6.QtGui import (
    QPixmap,
    QMouseEvent,
    QCloseEvent,
    QImage,
    QPainter,
    QPen,
    QColor,
    QIcon,
    QDesktopServices,
)  # Added Image, Painter, Pen, Color, Icon, DesktopServices
import json  # Import needed for pretty printing the dict
import logging
from pathlib import Path  # Ensure Path is explicitly imported
import os  # Import os for os.cpu_count()
import numpy as np
from PIL import Image

# Correct import for find_rife_executable
from goesvfi.utils import config, log
from goesvfi.utils.gui_helpers import RifeCapabilityManager

LOGGER = log.get_logger(__name__)

# from goesvfi.sanchez.runner import colourise # Import Sanchez colourise function - REMOVED


# Import the new image processor classes


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

# Commented out as it seems unused and might cause type issues if FfmpegProfile changes
# # OPTIMAL_FFMPEG_INTERP_SETTINGS = {
# #     "mi_mode": OPTIMAL_FFMPEG_PROFILE["mi_mode"],
# #     "mc_mode": OPTIMAL_FFMPEG_PROFILE["mc_mode"],
# #     "me_mode": OPTIMAL_FFMPEG_PROFILE["me_mode"],
# # #     "vsbmc": "1" if OPTIMAL_FFMPEG_PROFILE["vsbmc"] else "0",
# # #     "scd": OPTIMAL_FFMPEG_PROFILE["scd"]
# # }


# ─── Custom clickable label ────────────────────────────────────────────────
class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        LOGGER.debug("Entering ClickableLabel.__init__...")
        super().__init__(*args, **kwargs)
        self.file_path: str | None = None  # Original file path
        self.processed_image: QImage | None = None  # Store processed version
        # enable mouse tracking / events
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, ev: QMouseEvent | None) -> None:
        LOGGER.debug("Entering ClickableLabel.mouseReleaseEvent...")
        # Check if ev is not None before accessing attributes
        if ev is not None and ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        # Pass ev to super method (it handles None correctly)
        super().mouseReleaseEvent(ev)


# ─── ZoomDialog closes on any click ──────────────────────────────────────
class ZoomDialog(QDialog):
    def __init__(self, pixmap: QPixmap, parent: QWidget | None = None):
        LOGGER.debug(
            f"Entering ZoomDialog.__init__... pixmap.size={pixmap.size()}")
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog |
                            Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        lbl = QLabel(self)
        lbl.setPixmap(pixmap)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.addWidget(lbl)
        self.resize(pixmap.size())

    # Add type hint for event
    def mousePressEvent(self, ev: QMouseEvent | None) -> None:
        LOGGER.debug("Entering ZoomDialog.mousePressEvent...")
        self.close()


# ─── CropDialog class ─────────────────────────────────────────────
class CropDialog(QDialog):
    def __init__(
        self,
        pixmap: QPixmap,
        init: tuple[int, int, int, int] | None,
        parent: QWidget | None = None,
    ):
        LOGGER.debug(
            f"Entering CropDialog.__init__... pixmap.size={pixmap.size()}, init={init}")
        super().__init__(parent)
        self.setWindowTitle("Select Crop Region")

        self.original_pixmap = pixmap
        self.scale_factor = 1.0

        # --- Scale pixmap for display ---
        screen = QApplication.primaryScreen()
        if not screen:
            LOGGER.warning(
                "Could not get screen geometry, crop dialog might be too large."
            )
            max_size = QSize(1024, 768)  # Fallback size
        else:
            # Use 90% of available screen size
            max_size = screen.availableGeometry().size() * 0.9

        scaled_pix = pixmap.scaled(
            max_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.scale_factor = pixmap.width() / scaled_pix.width()
        # --- End scaling ---

        self.lbl = QLabel()
        self.lbl.setPixmap(scaled_pix)  # Display scaled pixmap
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.rubber = QRubberBand(QRubberBand.Shape.Rectangle, self.lbl)
        self.origin = QPoint()
        self.crop_rect_scaled = QRect()  # Store the rect drawn on the scaled pixmap

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
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(self.lbl)
        lay.addWidget(btns)

        # Adjust dialog size hint based on scaled content
        self.resize(lay.sizeHint())

    def mousePressEvent(self, ev: QMouseEvent | None) -> None:
        LOGGER.debug("Entering CropDialog.mousePressEvent...")
        if (
            ev is not None
            and ev.button() == Qt.MouseButton.LeftButton
            and self.lbl.geometry().contains(ev.pos())
        ):
            self.origin = self.lbl.mapFromParent(ev.pos())
            # Ensure origin is within scaled pixmap boundaries
            if not self.lbl.pixmap().rect().contains(self.origin):
                self.origin = QPoint()
                return
            self.rubber.setGeometry(QRect(self.origin, QSize()))
            self.rubber.show()

    def mouseMoveEvent(self, ev: QMouseEvent | None) -> None:
        LOGGER.debug("Entering CropDialog.mouseMoveEvent...")
        if ev is not None and not self.origin.isNull():
            cur = self.lbl.mapFromParent(ev.pos())
            # Clamp the current position to be within the scaled pixmap bounds
            scaled_pix_rect = self.lbl.pixmap().rect()
            cur.setX(max(0, min(cur.x(), scaled_pix_rect.width())))
            cur.setY(max(0, min(cur.y(), scaled_pix_rect.height())))
            self.rubber.setGeometry(QRect(self.origin, cur).normalized())

    def mouseReleaseEvent(self, ev: QMouseEvent | None) -> None:
        LOGGER.debug("Entering CropDialog.mouseReleaseEvent...")
        if (
            ev is not None
            and ev.button() == Qt.MouseButton.LeftButton
            and not self.origin.isNull()
        ):
            # Store the geometry relative to the scaled pixmap
            self.crop_rect_scaled = self.rubber.geometry()
            self.origin = QPoint()

    # Return the rectangle coordinates scaled UP to the original pixmap size
    def getRect(self) -> QRect:
        LOGGER.debug("Entering CropDialog.getRect...")
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
    error = pyqtSignal(str)

    def __init__(
        self,
        in_dir: pathlib.Path,
        out_file_path: pathlib.Path,
        fps: int,
        mid_count: int,
        max_workers: int,
        encoder: str,
        # FFmpeg settings passed directly
        use_preset_optimal: bool,
        use_ffmpeg_interp: bool,
        filter_preset: str,  # Intermediate filter preset
        mi_mode: str,
        mc_mode: str,
        me_mode: str,
        me_algo: str,
        search_param: int,
        scd_mode: str,
        scd_threshold: Optional[float],
        minter_mb_size: Optional[int],
        minter_vsbmc: int,  # Pass as 0 or 1
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
        LOGGER.debug(
            f"Entering VfiWorker.__init__... in_dir={in_dir}, out_file_path={out_file_path}, debug_mode={debug_mode}")
        super().__init__()
        self.in_dir = in_dir
        self.out_file_path = out_file_path
        self.fps = fps
        self.mid_count = mid_count
        self.max_workers = max_workers
        self.encoder = encoder
        # Store FFmpeg settings
        self.use_preset_optimal = use_preset_optimal
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
        # Other args
        self.skip_model = skip_model
        self.crop_rect = crop_rect
        self.debug_mode = debug_mode
        # RIFE v4.6 specific settings
        self.rife_tile_enable = rife_tile_enable
        self.rife_tile_size = rife_tile_size
        self.rife_uhd_mode = rife_uhd_mode
        self.rife_thread_spec = rife_thread_spec
        self.rife_tta_spatial = rife_tta_spatial
        self.rife_tta_temporal = rife_tta_temporal
        self.model_key = model_key
        # Sanchez Args
        self.false_colour = false_colour
        self.res_km = res_km

    def run(self) -> None:
        LOGGER.debug("Entering VfiWorker.run...")
        try:
            # Determine the image processor based on the selected encoder
            if self.encoder == "RIFE":
                # Use the RIFE image processor
                # The RIFE processor is expected to handle its own model loading
                # based on the model_key provided.
                # We need to pass the RIFE-specific settings to the processor.
                # Assuming RIFEProcessor exists and implements ImageProcessor
                # from goesvfi.pipeline.rife_processor import RIFEProcessor # Need to import this
                # processor: ImageProcessor = RIFEProcessor(
                #     model_key=self.model_key,
                #     tile_size=self.rife_tile_size if self.rife_tile_enable else None,
                #     uhd_mode=self.rife_uhd_mode,
                #     thread_spec=self.rife_thread_spec,
                #     tta_spatial=self.rife_tta_spatial,
                #     tta_temporal=self.rife_tta_temporal,
                # )
                # For now, using a placeholder or assuming the pipeline handles this
                # If the pipeline run_vfi handles processor instantiation, we don't need this here.
                # Let's assume run_vfi handles it for now based on the encoder type.
                processor = None # Placeholder, actual processor handled by run_vfi
            elif self.encoder == "Sanchez":
                # Use the Sanchez image processor
                # The Sanchez processor needs the false_colour and res_km settings
                # from goesvfi.pipeline.sanchez_processor import SanchezProcessor # Already imported at top
                # processor: ImageProcessor = SanchezProcessor(
                #     false_colour=self.false_colour,
                #     res_km=self.res_km,
                #     temp_dir=tempfile.gettempdir() # Sanchez needs a temp dir
                # )
                processor = None # Placeholder, actual processor handled by run_vfi
            elif self.encoder == "FFmpeg":
                 processor = None # Placeholder, actual processor handled by run_vfi
            else:
                raise ValueError(f"Unknown encoder type: {self.encoder}")

            # Find the RIFE executable path if RIFE is selected
            rife_exe = None
            if self.encoder == "RIFE":
                try:
                    rife_exe = config.find_rife_executable()
                    if rife_exe is None:
                        raise FileNotFoundError("RIFE executable not found.")
                    LOGGER.debug(f"Found RIFE executable at: {rife_exe}")
                except FileNotFoundError as e:
                    self.error.emit(f"RIFE executable not found: {e}")
                    LOGGER.error(f"RIFE executable not found: {e}")
                    return # Exit run method on error
                except Exception as e:
                    self.error.emit(f"Error finding RIFE executable: {e}")
                    LOGGER.exception(f"Error finding RIFE executable:")
                    return # Exit run method on error

            # Run the VFI pipeline
            # The run_vfi function is expected to yield progress updates
            # and return the path to the final MP4 file.
            # It should also handle the instantiation of the correct processor
            # based on the encoder type and pass the relevant settings.
            from goesvfi.pipeline.run_vfi import run_vfi # Need to import this

            LOGGER.debug("Calling run_vfi...")
            gen = run_vfi(
                in_dir=self.in_dir,
                out_file_path=self.out_file_path,
                fps=self.fps,
                mid_count=self.mid_count,
                max_workers=self.max_workers,
                encoder_type=self.encoder, # Pass encoder type
                # Pass all relevant settings for all encoders
                ffmpeg_settings={
                    "use_ffmpeg_interp": self.use_ffmpeg_interp,
                    "filter_preset": self.filter_preset,
                    "mi_mode": self.mi_mode,
                    "mc_mode": self.mc_mode,
                    "me_mode": self.me_mode,
                    "me_algo": self.me_algo,
                    "search_param": self.search_param,
                    "scd_mode": self.scd_mode,
                    "scd_threshold": self.scd_threshold,
                    "minter_mb_size": self.minter_mb_size,
                    "minter_vsbmc": self.minter_vsbmc,
                    "apply_unsharp": self.apply_unsharp,
                    "unsharp_lx": self.unsharp_lx,
                    "unsharp_ly": self.unsharp_ly,
                    "unsharp_la": self.unsharp_la,
                    "unsharp_cx": self.unsharp_cx,
                    "unsharp_cy": self.unsharp_cy,
                    "unsharp_ca": self.unsharp_ca,
                    "crf": self.crf,
                    "bitrate_kbps": self.bitrate_kbps,
                    "bufsize_kb": self.bufsize_kb,
                    "pix_fmt": self.pix_fmt,
                },
                rife_settings={
                    "model_key": self.model_key,
                    "tile_size": self.rife_tile_size if self.rife_tile_enable else None,
                    "uhd_mode": self.rife_uhd_mode,
                    "thread_spec": self.rife_thread_spec,
                    "tta_spatial": self.rife_tta_spatial,
                    "tta_temporal": self.rife_tta_temporal,
                    "rife_exe": rife_exe, # Pass the found executable path
                },
                sanchez_settings={
                    "false_colour": self.false_colour,
                    "res_km": self.res_km,
                    # SanchezProcessor needs a temp dir, pass the one created in MainWindow
                    "temp_dir": self._sanchez_gui_temp_dir,
                },
                skip_model=self.skip_model,
                crop_rect=self.crop_rect,
                debug_mode=self.debug_mode,
                # Pass the MainWindow instance to run_vfi so it can access image processors
                # This might not be the best design, consider passing processors directly
                # or making run_vfi responsible for their lifecycle.
                # For now, passing self to unblock.
                # main_window_instance=self # Removed passing self
            )

            final_mp4_path = None
            for progress_data in gen:
                if isinstance(progress_data, tuple) and len(progress_data) == 3:
                    # It's a progress update (current, total, eta)
                    current, total, eta = progress_data
                    self.progress.emit(current, total, eta)
                elif isinstance(progress_data, pathlib.Path):
                    # It's the final output path
                    final_mp4_path = progress_data
                elif isinstance(progress_data, str) and progress_data.startswith("ERROR:"):
                    # It's an error message
                    self.error.emit(progress_data[6:].strip()) # Emit error message
                    LOGGER.error(f"Error from run_vfi: {progress_data}")
                    return # Exit run method on error
                else:
                    LOGGER.warning(f"Unexpected data from run_vfi generator: {progress_data}")


            if final_mp4_path:
                LOGGER.debug(f"run_vfi finished, emitting finished signal with: {final_mp4_path}")
                self.finished.emit(final_mp4_path)
            else:
                # If gen completed without yielding a path, it means an error occurred
                # or the process was cancelled. An error should have been emitted already.
                LOGGER.warning("run_vfi generator finished without yielding a final path.")
                # If no error was emitted, emit a generic error
                # self.error.emit("Video processing failed or was cancelled.") # Avoid duplicate error if one was already emitted

        except Exception as e:
            LOGGER.exception("Unhandled exception in VfiWorker.run:")
            self.error.emit(f"An unexpected error occurred during processing: {e}")

# ────────────────────────────── Main Window ────────────────────────────────
class MainWindow(QWidget):
    request_previews_update = pyqtSignal()  # Signal to trigger preview update

    def __init__(self, debug_mode: bool = False) -> None:
        # Removed log level setting here, it's handled in main()
        LOGGER.debug(f"Entering MainWindow.__init__... debug_mode={debug_mode}")
        super().__init__()
        self.debug_mode = debug_mode
        self.setWindowTitle("GOES-VFI")
        self.setGeometry(100, 100, 800, 600)  # x, y, w, h

        # --- Models ---
        # Instantiate Models needed by ViewModels
        file_sorter_model = FileSorter()
        date_sorter_model = DateSorter()
        LOGGER.info("Models instantiated.")
        # --------------

        # --- ViewModels ---
        # Instantiate ViewModels here, passing required models
        self.main_view_model = MainWindowViewModel(
            file_sorter_model=file_sorter_model, date_sorter_model=date_sorter_model
        )  # <-- Instantiate ViewModel with models
        self.processing_view_model = (
            self.main_view_model.processing_vm
        )  # Get Processing VM from Main VM
        LOGGER.info("ViewModels instantiated.")
        # ------------------

        # --- Image Processor Instances ---
        # Instantiate processors here to be reused for previews
        self.image_loader = ImageLoader()
        # SanchezProcessor needs a temp directory, create one for the GUI lifetime
        self._sanchez_gui_temp_dir = (
            Path(tempfile.gettempdir()) / f"goes_vfi_sanchez_gui_{os.getpid()}"
        )
        os.makedirs(self._sanchez_gui_temp_dir, exist_ok=True)
        self.sanchez_processor = SanchezProcessor(self._sanchez_gui_temp_dir)
        self.image_cropper = ImageCropper()
        LOGGER.info("GUI Image processors instantiated.")
        # ---------------------------------

        # --- State Variables ---
        self.sanchez_preview_cache: dict[Path, np.ndarray[Any, Any]] = {} # Cache for Sanchez results
        self.in_dir: Path | None = None
        self.out_file_path: Path | None = None
        self.current_crop_rect: tuple[int, int, int, int] | None = (
            None  # Store crop rect as (x, y, w, h)
        )
        self.vfi_worker: VfiWorker | None = None
        self.is_processing = False
        self.current_encoder = "RIFE"  # Default encoder
        self.current_model_key = "rife-v4.6"  # Default RIFE model key
        # -----------------------

        # --- Layout ---
        main_layout = QVBoxLayout(self)

        # Tab Widget
        self.tab_widget = QTabWidget()
        self.main_tab = self._makeMainTab()
        self.ffmpeg_settings_tab = self._make_ffmpeg_settings_tab()
        self.model_library_tab = self._makeModelLibraryTab()  # Add Model Library tab
        # Pass ViewModels to Tabs
        self.file_sorter_tab = FileSorterTab(
            view_model=self.main_view_model.file_sorter_vm, parent=self
        )  # <-- Pass VM
        self.date_sorter_tab = DateSorterTab(
            view_model=self.main_view_model.date_sorter_vm, parent=self
        )  # <-- Pass VM

        self.tab_widget.addTab(self.main_tab, "Main")
        self.tab_widget.addTab(self.ffmpeg_settings_tab, "FFmpeg Settings")
        self.tab_widget.addTab(
            self.model_library_tab, "Model Library"
        )  # Add Model Library tab
        self.tab_widget.addTab(
            self.file_sorter_tab, "File Sorter"
        )  # Add File Sorter tab
        self.tab_widget.addTab(
            self.date_sorter_tab, "Date Sorter"
        )  # Add Date Sorter tab

        # self.loadSettings() # Moved lower

        main_layout.addWidget(self.tab_widget)
        # Status Bar
        self.status_bar = QStatusBar()

        # self.progress_label = QLabel("Idle") # <-- Remove direct label
        # self.status_bar.addWidget(self.progress_label) # <-- Remove direct label widget
        # self.progress_bar = QProgressBar() # <-- Progress bar likely managed by Processing VM later
        # self.progress_bar.setVisible(False) # Hide initially
        # self.status_bar.addPermanentWidget(self.progress_bar) # <-- Remove progress bar for now
        
        # Set up aliases for compatibility with inconsistent naming in the code
        self.model_combo = self.rife_model_combo  # Create alias for compatibility
        # self.sanchez_res_km_spinbox = self.sanchez_res_spinbox # Removed old alias
        self.sanchez_res_km_combo = self.sanchez_res_combo # Added new alias for ComboBox
        self.ffmpeg_interp_group = self.ffmpeg_settings_group  # Create alias for compatibility
        self.filter_preset_combo = self.ffmpeg_filter_preset_combo  # Create alias for compatibility
        self.mi_mode_combo = self.ffmpeg_mi_mode_combo  # Create alias for compatibility
        self.mc_mode_combo = self.ffmpeg_mc_mode_combo  # Create alias for compatibility
        self.me_mode_combo = self.ffmpeg_me_mode_combo  # Create alias for compatibility
        # These need special handling as they're QLineEdit but referenced as combo boxes
        self.me_algo_combo = self.ffmpeg_me_algo_edit  # Create alias for compatibility
        self.mb_size_combo = self.ffmpeg_mb_size_edit  # Create alias for compatibility
        
        self.search_param_spinbox = self.ffmpeg_search_param_spinbox  # Create alias for compatibility
        self.scd_mode_combo = self.ffmpeg_scd_combo  # Create alias for compatibility
        self.scd_threshold_spinbox = self.ffmpeg_scd_threshold_spinbox  # Create alias for compatibility
        self.vsbmc_checkbox = self.ffmpeg_vsbmc_checkbox  # Create alias for compatibility
        self.unsharp_group = self.ffmpeg_unsharp_group  # Create alias for compatibility
        self.unsharp_lx_spinbox = self.ffmpeg_unsharp_lx_spinbox  # Create alias for compatibility
        self.unsharp_ly_spinbox = self.ffmpeg_unsharp_ly_spinbox  # Create alias for compatibility
        self.unsharp_la_spinbox = self.ffmpeg_unsharp_la_spinbox  # Create alias for compatibility
        self.unsharp_cx_spinbox = self.ffmpeg_unsharp_cx_spinbox  # Create alias for compatibility
        self.unsharp_cy_spinbox = self.ffmpeg_unsharp_cy_spinbox  # Create alias for compatibility
        self.unsharp_ca_spinbox = self.ffmpeg_unsharp_ca_spinbox  # Create alias for compatibility
        self.crf_spinbox = self.ffmpeg_crf_spinbox  # Create alias for compatibility
        self.bitrate_spinbox = self.ffmpeg_bitrate_spinbox  # Create alias for compatibility
        self.bufsize_spinbox = self.ffmpeg_bufsize_spinbox  # Create alias for compatibility
        self.pix_fmt_combo = self.ffmpeg_pix_fmt_combo  # Create alias for compatibility
        self.profile_combo = self.ffmpeg_profile_combo  # Create alias for compatibility
        
        # Set up settings
        self.settings = QSettings("GOES_VFI", "gui")
        
        # Apply dark theme
        self.apply_dark_theme()
        
        # Load settings after main layout is constructed
        self.loadSettings()  # Using simplified version
        main_layout.addWidget(self.status_bar)

        # --- Load Settings and UI Connections ---
        # All settings loading, UI connections, and state updates are moved to _post_init_setup()
        # This prevents issues with Qt object lifetimes during testing
        # See _post_init_setup method below

        # Skip initialization steps that might cause Qt object lifetime issues
        # They will be called in _post_init_setup instead - see below

        # --- Moved Preview Update Setup from _post_init_setup ---
        logging.debug("Setting up preview update...")
        QTimer.singleShot(100, self.request_previews_update.emit)
        self.request_previews_update.connect(self._update_previews)
        logging.debug("request_previews_update connected to _update_previews")
        # -------------------------------------------------------

        LOGGER.info("MainWindow initialized.")

    def _post_init_setup(self) -> None:
        # LOGGER.debug("Entering _post_init_setup...") # Removed log
        """Perform UI setup and signal connections after initialization.

        This method should be called after the MainWindow is added to qtbot in tests,
        to ensure proper Qt object lifetime management.
        """
        # Connect signals
        # self.loadSettings() # Moved to __init__
        self._connect_ffmpeg_settings_tab_signals()
        self._connect_model_combo()
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self.main_view_model.status_updated.connect(self.status_bar.showMessage)
        self.file_sorter_tab.directory_selected.connect(self._set_in_dir_from_sorter)
        self.date_sorter_tab.directory_selected.connect(self._set_in_dir_from_sorter)

        # Populate initial data
        self._populate_models()

        # Update initial UI state
        self._update_rife_ui_elements()
        # self._update_ffmpeg_controls_state(self.encoder_combo.currentText()) # Removed - FFmpeg groups moved to own tab
        self._update_start_button_state()
        self._update_crop_buttons_state()
        self._update_rife_options_state(self.current_encoder)
        self._update_quality_controls_state(self.current_encoder) # Note: This likely needs adjustment if quality controls moved
        # self._update_ffmpeg_controls_state(self.current_encoder == "FFmpeg", update_group=False) # Removed - FFmpeg groups moved to own tab

        # Set up preview update (MOVED TO __init__)


        # Set initial status
        self.status_bar.showMessage(self.main_view_model.status)

        # LOGGER.debug("Exiting _post_init_setup...") # Removed log
        LOGGER.info("MainWindow post-initialization setup complete.")

    def _set_in_dir_from_sorter(self, directory: Path) -> None:
        LOGGER.debug(f"Entering _set_in_dir_from_sorter... directory={directory}")
        """Sets the input directory from a sorter tab."""
        self.in_dir = directory
        self.in_dir_edit.setText(str(directory))
        self._update_start_button_state()
        self.request_previews_update.emit()  # Request preview update

    def _pick_in_dir(self) -> None:
        LOGGER.debug("Entering _pick_in_dir...")
        """Open a directory dialog to select the input image folder."""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Input Image Folder")
        if dir_path:
            LOGGER.debug(f"Input directory selected: {dir_path}")
            self.in_dir = Path(dir_path)
            self.in_dir_edit.setText(dir_path)
            self._update_start_button_state()
            LOGGER.debug("Emitting request_previews_update from _pick_in_dir")
            self.request_previews_update.emit()  # Request preview update

    def _pick_out_file(self) -> None:
        LOGGER.debug("Entering _pick_out_file...")
        """Open a file dialog to select the output MP4 file path."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Output Video", "", "MP4 Files (*.mp4)"
        )
        if file_path:
            LOGGER.debug(f"Output file selected: {file_path}")
            self.out_file_path = Path(file_path)
            self.out_file_edit.setText(file_path)
            self._update_start_button_state()

    def _on_crop_clicked(self) -> None:
        LOGGER.debug("Entering _on_crop_clicked...")
        """Open the crop dialog with the first image."""
        if self.in_dir and self.in_dir.is_dir():
            image_files = sorted(
                [
                    f
                    for f in self.in_dir.iterdir()
                    if f.suffix.lower() in [".png", ".jpg", ".jpeg"]
                ]
            )
            LOGGER.debug(f"Found {len(image_files)} image files in {self.in_dir}")
            if image_files:
                first_image_path = image_files[0]
                try:
                    LOGGER.debug(f"Preparing image for crop dialog: {first_image_path}")

                    pixmap_for_dialog: QPixmap | None = None
                    sanchez_preview_enabled = self.sanchez_false_colour_checkbox.isChecked()

                    if sanchez_preview_enabled:
                        LOGGER.debug("Sanchez preview enabled. Attempting to get full-res processed_image from first_frame_label.")
                        # Try to get the stored full-res QImage from the label's attribute
                        full_res_image: QImage | None = None
                        if hasattr(self, 'first_frame_label') and self.first_frame_label is not None:
                            # Retrieve the QImage stored *before* scaling in _load_process_scale_preview
                            full_res_image = getattr(self.first_frame_label, 'processed_image', None)

                        if full_res_image is not None and isinstance(full_res_image, QImage) and not full_res_image.isNull():
                             LOGGER.debug("Successfully retrieved full-res processed_image from first_frame_label.")
                             pixmap_for_dialog = QPixmap.fromImage(full_res_image) # Create pixmap from the full-res QImage
                        else:
                             LOGGER.warning("processed_image not found or invalid on first_frame_label. Will fall back to original image.")
                             pixmap_for_dialog = None # Ensure fallback

                    # If Sanchez wasn't enabled OR getting the preview pixmap failed, load the original
                    if pixmap_for_dialog is None:
                        if sanchez_preview_enabled:
                             LOGGER.debug("Falling back to loading original image for crop dialog.")
                        else:
                             LOGGER.debug("Loading original image for crop dialog (Sanchez not enabled).")

                        original_image = QImage(str(first_image_path))
                        if original_image.isNull():
                            LOGGER.error(f"Failed to load original image for cropping: {first_image_path}")
                            QMessageBox.critical(self, "Error", f"Failed to load image for cropping: {first_image_path}")
                            return
                        pixmap_for_dialog = QPixmap.fromImage(original_image)
                        LOGGER.debug("Successfully loaded original image for crop dialog.")

                    # Final check if we have a valid pixmap
                    if pixmap_for_dialog is None or pixmap_for_dialog.isNull():
                         LOGGER.error(f"Failed to prepare any pixmap for crop dialog: {first_image_path}")
                         QMessageBox.critical(self, "Error", f"Could not load or process image for cropping: {first_image_path}")
                         return

                    # Now use the prepared pixmap (original or processed from preview label)
                    dialog = CropDialog(pixmap_for_dialog, self.current_crop_rect, self)
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        crop_rect = dialog.getRect()
                        # Store as (x, y, w, h) tuple
                        self.current_crop_rect = (
                            crop_rect.x(),
                            crop_rect.y(),
                            crop_rect.width(),
                            crop_rect.height(),
                        )
                        LOGGER.info(f"Crop rectangle set to: {self.current_crop_rect}")
                        self._update_crop_buttons_state()
                        self.request_previews_update.emit()  # Request preview update
                except Exception as e:
                    LOGGER.exception(
                        f"Error opening crop dialog for {first_image_path}:"
                    )
                    QMessageBox.critical(
                        self, "Error", f"Error opening crop dialog: {e}"
                    )
            else:
                LOGGER.debug("No images found in the input directory to crop.")
                QMessageBox.warning(
                    self, "Warning", "No images found in the input directory to crop."
                )
        else:
            LOGGER.debug("No input directory selected for cropping.")
            QMessageBox.warning(
                self, "Warning", "Please select an input directory first."
            )

    def _makeMainTab(self) -> QWidget:
        """Create and return the main tab widget with enhanced styling."""
        main_tab = QWidget()
        layout = QVBoxLayout(main_tab)
        layout.setContentsMargins(10, 10, 10, 10)  # Adjust margins
        layout.setSpacing(10)  # Adjust spacing between major groups

        # Input/Output Group with improved styling
        io_group = QGroupBox("Input/Output")
        io_layout = QGridLayout(io_group)
        io_layout.setContentsMargins(10, 15, 10, 10)  # Adjust internal margins
        io_layout.setSpacing(8)  # Adjust spacing between elements

        # Input directory row
        self.in_dir_edit = QLineEdit()
        self.in_dir_edit.setPlaceholderText("Select input image folder...")
        self.in_dir_edit.textChanged.connect(
            lambda text: self._update_start_button_state()
        )  # Connect text changed signal
        self.in_dir_edit.textChanged.connect(
            lambda text: setattr(self, "in_dir", Path(text) if text else None)
        )  # Update in_dir state
        self.in_dir_edit.textChanged.connect(
            self.request_previews_update.emit
        )  # Request preview update
        self.in_dir_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        in_dir_button = QPushButton("Browse...")
        in_dir_button.setObjectName("browse_button")
        in_dir_button.clicked.connect(self._pick_in_dir)

        io_layout.addWidget(QLabel("Input Directory:"), 0, 0)
        io_layout.addWidget(self.in_dir_edit, 0, 1)
        io_layout.addWidget(in_dir_button, 0, 2)

        # Output file row
        self.out_file_edit = QLineEdit()
        self.out_file_edit.setPlaceholderText("Select output MP4 file...")
        self.out_file_edit.textChanged.connect(
            lambda text: self._update_start_button_state()
        )  # Connect text changed signal
        self.out_file_edit.textChanged.connect(
            lambda text: setattr(self, "out_file_path", Path(text) if text else None)
        )  # Update out_file_path state
        self.out_file_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        out_file_button = QPushButton("Browse...")
        out_file_button.setObjectName("browse_button")
        out_file_button.clicked.connect(self._pick_out_file)

        io_layout.addWidget(QLabel("Output File (MP4):"), 1, 0)
        io_layout.addWidget(self.out_file_edit, 1, 1)
        io_layout.addWidget(out_file_button, 1, 2)

        # Create clickable labels for preview images
        self.first_frame_label = ClickableLabel()
        self.first_frame_label.clicked.connect(
            lambda: self._show_zoom(self.first_frame_label)
        )
        
        self.middle_frame_label = ClickableLabel()
        self.middle_frame_label.clicked.connect(
            lambda: self._show_zoom(self.middle_frame_label)
        )
        
        self.last_frame_label = ClickableLabel()
        self.last_frame_label.clicked.connect(
            lambda: self._show_zoom(self.last_frame_label)
        )

        # Create enhanced preview area (main focal point)
        previews_group = self._enhance_preview_area()
        
        # Create crop buttons with improved styling
        crop_buttons_layout = QHBoxLayout()
        crop_buttons_layout.setContentsMargins(10, 0, 10, 0)
        
        self.crop_button = QPushButton("Select Crop Region")
        self.crop_button.setObjectName("crop_button")
        self.crop_button.clicked.connect(self._on_crop_clicked)
        
        self.clear_crop_button = QPushButton("Clear Crop")
        self.clear_crop_button.setObjectName("clear_crop_button")
        self.clear_crop_button.clicked.connect(self._on_clear_crop_clicked)
        
        crop_buttons_layout.addWidget(self.crop_button)
        crop_buttons_layout.addWidget(self.clear_crop_button)
        crop_buttons_layout.addStretch(1)  # Add stretch to push buttons to the left

        # Create processing settings group with improved layout
        processing_group = self._create_processing_settings_group()

        # RIFE Options Group (Initially hidden/disabled)
        self.rife_options_group = QGroupBox("RIFE Options")
        self.rife_options_group.setCheckable(False) # Not checkable
        rife_layout = QGridLayout(self.rife_options_group)

        # RIFE Model Selection
        rife_layout.addWidget(QLabel("RIFE Model:"), 0, 0)
        self.rife_model_combo = QComboBox()
        # Populate this combo box later based on available models
        rife_layout.addWidget(self.rife_model_combo, 0, 1)

        # RIFE Tile Size
        self.rife_tile_checkbox = QCheckBox("Enable Tiling")
        self.rife_tile_checkbox.setChecked(False)
        self.rife_tile_checkbox.stateChanged.connect(self._toggle_tile_size_enabled)
        rife_layout.addWidget(self.rife_tile_checkbox, 1, 0)

        self.rife_tile_size_spinbox = QSpinBox()
        self.rife_tile_size_spinbox.setRange(32, 1024)
        self.rife_tile_size_spinbox.setValue(256)
        self.rife_tile_size_spinbox.setEnabled(False) # Initially disabled
        rife_layout.addWidget(self.rife_tile_size_spinbox, 1, 1)
        
        # Add backward compatibility alias for tile_size_spinbox
        self.tile_size_spinbox = self.rife_tile_size_spinbox

        # RIFE UHD Mode
        self.rife_uhd_checkbox = QCheckBox("UHD Mode")
        self.rife_uhd_checkbox.setChecked(False)
        rife_layout.addWidget(self.rife_uhd_checkbox, 2, 0, 1, 2) # Span 2 columns

        # RIFE Thread Specification
        rife_layout.addWidget(QLabel("Thread Spec:"), 3, 0)
        self.rife_thread_spec_edit = QLineEdit()
        self.rife_thread_spec_edit.setPlaceholderText("e.g., 1:2:2, 2:2:1")
        self.rife_thread_spec_edit.setToolTip("Specify thread distribution (encoder:decoder:processor)")
        self.rife_thread_spec_edit.textChanged.connect(self._validate_thread_spec) # Add validation
        rife_layout.addWidget(self.rife_thread_spec_edit, 3, 1)

        # RIFE TTA Options
        self.rife_tta_spatial_checkbox = QCheckBox("TTA Spatial")
        self.rife_tta_spatial_checkbox.setChecked(False)
        rife_layout.addWidget(self.rife_tta_spatial_checkbox, 4, 0, 1, 2)

        self.rife_tta_temporal_checkbox = QCheckBox("TTA Temporal")
        self.rife_tta_temporal_checkbox.setChecked(False)
        rife_layout.addWidget(self.rife_tta_temporal_checkbox, 5, 0, 1, 2)

        # Sanchez Options Group (Initially hidden/disabled)
        self.sanchez_options_group = QGroupBox("Sanchez Options")
        self.sanchez_options_group.setCheckable(False) # Not checkable
        sanchez_layout = QGridLayout(self.sanchez_options_group)

        # Sanchez False Colour
        self.sanchez_false_colour_checkbox = QCheckBox("False Colour")
        self.sanchez_false_colour_checkbox.setChecked(False)
        # Connect stateChanged to trigger preview update
        self.sanchez_false_colour_checkbox.stateChanged.connect(self.request_previews_update.emit)
        sanchez_layout.addWidget(self.sanchez_false_colour_checkbox, 0, 0, 1, 2)

        # Sanchez Resolution (km) - Changed to ComboBox
        sanchez_layout.addWidget(QLabel("Resolution (km):"), 1, 0)
        self.sanchez_res_combo = QComboBox() # Changed from QSpinBox
        self.sanchez_res_combo.addItems(["0.5", "1", "2", "4"]) # Valid values
        self.sanchez_res_combo.setCurrentText("4") # Set default to 4
        sanchez_layout.addWidget(self.sanchez_res_combo, 1, 1)

        # FFmpeg Settings Group (Initially hidden/disabled)
        self.ffmpeg_settings_group = QGroupBox("FFmpeg Interpolation Settings")
        self.ffmpeg_settings_group.setCheckable(False) # Not checkable
        ffmpeg_layout = QGridLayout(self.ffmpeg_settings_group)

        # FFmpeg Profile Selection
        ffmpeg_layout.addWidget(QLabel("Profile:"), 0, 0)
        self.ffmpeg_profile_combo = QComboBox()
        self.ffmpeg_profile_combo.addItems(list(FFMPEG_PROFILES.keys()) + ["Custom"])
        self.ffmpeg_profile_combo.setCurrentText("Default") # Set initial value
        self.ffmpeg_profile_combo.currentTextChanged.connect(self._on_profile_selected) # Connect signal
        ffmpeg_layout.addWidget(self.ffmpeg_profile_combo, 0, 1)

        # FFmpeg Interpolation Settings (mi_mode, mc_mode, me_mode, vsbmc, scd, me_algo, search_param, scd_threshold, mb_size)
        ffmpeg_layout.addWidget(QLabel("MI Mode:"), 1, 0)
        self.ffmpeg_mi_mode_combo = QComboBox()
        self.ffmpeg_mi_mode_combo.addItems(["mci", "simple", "scd"])
        ffmpeg_layout.addWidget(self.ffmpeg_mi_mode_combo, 1, 1)

        ffmpeg_layout.addWidget(QLabel("MC Mode:"), 2, 0)
        self.ffmpeg_mc_mode_combo = QComboBox()
        self.ffmpeg_mc_mode_combo.addItems(["obmc", "aobmc", "bilat"])
        ffmpeg_layout.addWidget(self.ffmpeg_mc_mode_combo, 2, 1)

        ffmpeg_layout.addWidget(QLabel("ME Mode:"), 3, 0)
        self.ffmpeg_me_mode_combo = QComboBox()
        self.ffmpeg_me_mode_combo.addItems(["bidir", "single"])
        ffmpeg_layout.addWidget(self.ffmpeg_me_mode_combo, 3, 1)

        self.ffmpeg_vsbmc_checkbox = QCheckBox("VSBMC")
        self.ffmpeg_vsbmc_checkbox.setChecked(False)
        ffmpeg_layout.addWidget(self.ffmpeg_vsbmc_checkbox, 4, 0, 1, 2)

        ffmpeg_layout.addWidget(QLabel("SCD Mode:"), 5, 0)
        self.ffmpeg_scd_combo = QComboBox()
        self.ffmpeg_scd_combo.addItems(["none", "fdiff", "sad"])
        self.ffmpeg_scd_combo.currentTextChanged.connect(self._update_scd_thresh_state) # Connect signal
        ffmpeg_layout.addWidget(self.ffmpeg_scd_combo, 5, 1)

        ffmpeg_layout.addWidget(QLabel("ME Algo:"), 6, 0)
        self.ffmpeg_me_algo_edit = QLineEdit()
        self.ffmpeg_me_algo_edit.setPlaceholderText("(default)")
        ffmpeg_layout.addWidget(self.ffmpeg_me_algo_edit, 6, 1)

        ffmpeg_layout.addWidget(QLabel("Search Param:"), 7, 0)
        self.ffmpeg_search_param_spinbox = QSpinBox()
        self.ffmpeg_search_param_spinbox.setRange(0, 256) # Example range
        self.ffmpeg_search_param_spinbox.setValue(96) # Example default
        ffmpeg_layout.addWidget(self.ffmpeg_search_param_spinbox, 7, 1)

        ffmpeg_layout.addWidget(QLabel("SCD Threshold:"), 8, 0)
        self.ffmpeg_scd_threshold_spinbox = QDoubleSpinBox()
        self.ffmpeg_scd_threshold_spinbox.setRange(0.0, 100.0) # Example range
        self.ffmpeg_scd_threshold_spinbox.setValue(10.0) # Example default
        self.ffmpeg_scd_threshold_spinbox.setSingleStep(0.1)
        ffmpeg_layout.addWidget(self.ffmpeg_scd_threshold_spinbox, 8, 1)

        ffmpeg_layout.addWidget(QLabel("MB Size:"), 9, 0)
        self.ffmpeg_mb_size_edit = QLineEdit()
        self.ffmpeg_mb_size_edit.setPlaceholderText("(default)")
        ffmpeg_layout.addWidget(self.ffmpeg_mb_size_edit, 9, 1)

        # FFmpeg Sharpening Settings Group
        self.ffmpeg_unsharp_group = QGroupBox("Unsharp Masking")
        self.ffmpeg_unsharp_group.setCheckable(True) # Make it checkable to enable/disable
        self.ffmpeg_unsharp_group.setChecked(True) # Initially checked
        self.ffmpeg_unsharp_group.toggled.connect(self._update_unsharp_controls_state) # Connect signal
        unsharp_layout = QGridLayout(self.ffmpeg_unsharp_group)

        unsharp_layout.addWidget(QLabel("Luma Matrix Width:"), 0, 0)
        self.ffmpeg_unsharp_lx_spinbox = QSpinBox()
        self.ffmpeg_unsharp_lx_spinbox.setRange(3, 23) # Odd numbers only
        self.ffmpeg_unsharp_lx_spinbox.setSingleStep(2)
        self.ffmpeg_unsharp_lx_spinbox.setValue(7)
        unsharp_layout.addWidget(self.ffmpeg_unsharp_lx_spinbox, 0, 1)

        unsharp_layout.addWidget(QLabel("Luma Matrix Height:"), 1, 0)
        self.ffmpeg_unsharp_ly_spinbox = QSpinBox()
        self.ffmpeg_unsharp_ly_spinbox.setRange(3, 23) # Odd numbers only
        self.ffmpeg_unsharp_ly_spinbox.setSingleStep(2)
        self.ffmpeg_unsharp_ly_spinbox.setValue(7)
        unsharp_layout.addWidget(self.ffmpeg_unsharp_ly_spinbox, 1, 1)

        unsharp_layout.addWidget(QLabel("Luma Amount:"), 2, 0)
        self.ffmpeg_unsharp_la_spinbox = QDoubleSpinBox()
        self.ffmpeg_unsharp_la_spinbox.setRange(-10.0, 10.0)
        self.ffmpeg_unsharp_la_spinbox.setSingleStep(0.1)
        self.ffmpeg_unsharp_la_spinbox.setValue(1.0)
        unsharp_layout.addWidget(self.ffmpeg_unsharp_la_spinbox, 2, 1)

        unsharp_layout.addWidget(QLabel("Chroma Matrix Width:"), 3, 0)
        self.ffmpeg_unsharp_cx_spinbox = QSpinBox()
        self.ffmpeg_unsharp_cx_spinbox.setRange(3, 23) # Odd numbers only
        self.ffmpeg_unsharp_cx_spinbox.setSingleStep(2)
        self.ffmpeg_unsharp_cx_spinbox.setValue(5)
        unsharp_layout.addWidget(self.ffmpeg_unsharp_cx_spinbox, 3, 1)

        unsharp_layout.addWidget(QLabel("Chroma Matrix Height:"), 4, 0)
        self.ffmpeg_unsharp_cy_spinbox = QSpinBox()
        self.ffmpeg_unsharp_cy_spinbox.setRange(3, 23) # Odd numbers only
        self.ffmpeg_unsharp_cy_spinbox.setSingleStep(2)
        self.ffmpeg_unsharp_cy_spinbox.setValue(5)
        unsharp_layout.addWidget(self.ffmpeg_unsharp_cy_spinbox, 4, 1)

        unsharp_layout.addWidget(QLabel("Chroma Amount:"), 5, 0)
        self.ffmpeg_unsharp_ca_spinbox = QDoubleSpinBox()
        self.ffmpeg_unsharp_ca_spinbox.setRange(-10.0, 10.0)
        self.ffmpeg_unsharp_ca_spinbox.setSingleStep(0.1)
        self.ffmpeg_unsharp_ca_spinbox.setValue(0.0)
        unsharp_layout.addWidget(self.ffmpeg_unsharp_ca_spinbox, 5, 1)

        # FFmpeg Quality Settings Group
        self.ffmpeg_quality_group = QGroupBox("Encoding Quality")
        self.ffmpeg_quality_group.setCheckable(False) # Not checkable
        quality_layout = QGridLayout(self.ffmpeg_quality_group)

        # Quality Preset (CRF/Bitrate)
        quality_layout.addWidget(QLabel("Quality Preset:"), 0, 0)
        self.ffmpeg_quality_combo = QComboBox()
        self.ffmpeg_quality_combo.addItems([
            "Very High (CRF 16)",
            "High (CRF 18)",
            "Medium (CRF 20)",
            "Low (CRF 23)",
            "Custom (CRF/Bitrate)"
        ])
        self.ffmpeg_quality_combo.setCurrentText("Very High (CRF 16)") # Set initial value
        self.ffmpeg_quality_combo.currentTextChanged.connect(self._update_quality_controls_state) # Connect signal
        quality_layout.addWidget(self.ffmpeg_quality_combo, 0, 1)

        # CRF (Constant Rate Factor)
        quality_layout.addWidget(QLabel("CRF:"), 1, 0)
        self.ffmpeg_crf_spinbox = QSpinBox()
        self.ffmpeg_crf_spinbox.setRange(0, 51) # 0 is lossless, higher is lower quality
        self.ffmpeg_crf_spinbox.setValue(16) # Default for very high quality
        self.ffmpeg_crf_spinbox.setEnabled(False) # Initially disabled for preset
        quality_layout.addWidget(self.ffmpeg_crf_spinbox, 1, 1)

        # Bitrate (kbps)
        quality_layout.addWidget(QLabel("Bitrate (kbps):"), 2, 0)
        self.ffmpeg_bitrate_spinbox = QSpinBox()
        self.ffmpeg_bitrate_spinbox.setRange(100, 100000) # Example range
        self.ffmpeg_bitrate_spinbox.setValue(15000) # Example default
        self.ffmpeg_bitrate_spinbox.setSingleStep(100)
        self.ffmpeg_bitrate_spinbox.setEnabled(False) # Initially disabled for preset
        quality_layout.addWidget(self.ffmpeg_bitrate_spinbox, 2, 1)

        # Bufsize (kb)
        quality_layout.addWidget(QLabel("Bufsize (kb):"), 3, 0)
        self.ffmpeg_bufsize_spinbox = QSpinBox()
        self.ffmpeg_bufsize_spinbox.setRange(100, 150000) # Example range (should be >= bitrate)
        self.ffmpeg_bufsize_spinbox.setValue(22500) # Example default (1.5 * bitrate)
        self.ffmpeg_bufsize_spinbox.setSingleStep(100)
        self.ffmpeg_bufsize_spinbox.setEnabled(False) # Initially disabled for preset
        quality_layout.addWidget(self.ffmpeg_bufsize_spinbox, 3, 1)

        # Pixel Format
        quality_layout.addWidget(QLabel("Pixel Format:"), 4, 0)
        self.ffmpeg_pix_fmt_combo = QComboBox()
        self.ffmpeg_pix_fmt_combo.addItems(["yuv420p", "yuv422p", "yuv444p"]) # Common formats
        self.ffmpeg_pix_fmt_combo.setCurrentText("yuv444p") # Default to high quality
        quality_layout.addWidget(self.ffmpeg_pix_fmt_combo, 4, 1)

        # FFmpeg Filter Preset
        quality_layout.addWidget(QLabel("Filter Preset:"), 5, 0)
        self.ffmpeg_filter_preset_combo = QComboBox()
        self.ffmpeg_filter_preset_combo.addItems(["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"])
        self.ffmpeg_filter_preset_combo.setCurrentText("slow") # Default to a good balance
        quality_layout.addWidget(self.ffmpeg_filter_preset_combo, 5, 1)


        # Style the Start button prominently
        self.start_button = QPushButton("Start Video Interpolation")
        self.start_button.setObjectName("start_button")
        self.start_button.setMinimumHeight(40)  # Make the button taller
        self.start_button.clicked.connect(self._start)
        self.start_button.setEnabled(False)  # Disabled initially

        # Create horizontal layout for processing settings and RIFE options
        settings_layout = QHBoxLayout()
        settings_layout.setSpacing(10)  # Add spacing between the columns
        
        # Adjust size policies for better proportions
        processing_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.rife_options_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        # Add groups to the horizontal layout
        settings_layout.addWidget(processing_group, 1)  # 1 is the stretch factor
        settings_layout.addWidget(self.rife_options_group, 1)  # Equal stretch factor
        
        # Add all components to main layout
        layout.addWidget(io_group)
        layout.addWidget(previews_group, 1)  # Give preview area more vertical space (stretch factor)
        layout.addLayout(crop_buttons_layout)  # Add crop buttons below the preview area
        layout.addLayout(settings_layout)  # Add the side-by-side settings layout
        layout.addWidget(self.sanchez_options_group)
        # FFmpeg groups moved to _make_ffmpeg_settings_tab
        layout.addWidget(self.start_button)

        # Set layout for the main tab
        main_tab.setLayout(layout)
        return main_tab

    def _make_ffmpeg_settings_tab(self) -> QWidget:
        """Create and return the FFmpeg settings tab widget."""
        ffmpeg_settings_tab = QWidget()
        layout = QVBoxLayout(ffmpeg_settings_tab)

        # This tab will contain the FFmpeg settings groups defined in _makeMainTab
        # We will move them here later if needed, for now they are in the main tab
        # and their visibility is controlled by the encoder selection.

        # Add the FFmpeg group boxes here
        layout.addWidget(self.ffmpeg_settings_group)
        layout.addWidget(self.ffmpeg_unsharp_group)
        layout.addWidget(self.ffmpeg_quality_group)
        layout.addStretch() # Add stretch to push groups to the top

        ffmpeg_settings_tab.setLayout(layout)
        return ffmpeg_settings_tab

    def _connect_ffmpeg_settings_tab_signals(self) -> None:
        """Connect signals for enabling/disabling controls and profile handling on the FFmpeg Settings tab."""
        # Connect signals for FFmpeg settings controls to update profile combo to "Custom"
        controls_to_monitor = [
            self.ffmpeg_mi_mode_combo,
            self.ffmpeg_mc_mode_combo,
            self.ffmpeg_me_mode_combo,
            self.ffmpeg_vsbmc_checkbox,
            self.ffmpeg_scd_combo,
            self.ffmpeg_me_algo_edit,
            self.ffmpeg_search_param_spinbox,
            self.ffmpeg_scd_threshold_spinbox,
            self.ffmpeg_mb_size_edit,
            self.ffmpeg_unsharp_group, # Monitor the group check state
            self.ffmpeg_unsharp_lx_spinbox,
            self.ffmpeg_unsharp_ly_spinbox,
            self.ffmpeg_unsharp_la_spinbox,
            self.ffmpeg_unsharp_cx_spinbox,
            self.ffmpeg_unsharp_cy_spinbox,
            self.ffmpeg_unsharp_ca_spinbox,
            self.ffmpeg_quality_combo, # Monitoring this will set Custom if user picks Custom
            self.ffmpeg_crf_spinbox,
            self.ffmpeg_bitrate_spinbox,
            self.ffmpeg_bufsize_spinbox,
            self.ffmpeg_pix_fmt_combo,
            self.ffmpeg_filter_preset_combo,
        ]

        for control in controls_to_monitor:
            if isinstance(control, (QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox)):
                if hasattr(control, 'currentTextChanged'):
                    control.currentTextChanged.connect(self._on_ffmpeg_setting_changed)
                elif hasattr(control, 'textChanged'):
                    control.textChanged.connect(self._on_ffmpeg_setting_changed)
                elif hasattr(control, 'valueChanged'):
                    control.valueChanged.connect(self._on_ffmpeg_setting_changed)
            elif isinstance(control, QCheckBox):
                 control.stateChanged.connect(self._on_ffmpeg_setting_changed)
            elif isinstance(control, QGroupBox):
                 control.toggled.connect(self._on_ffmpeg_setting_changed) # Connect toggled signal

        # Connect signals that should trigger a preview update when changed
        preview_update_controls = [
            self.in_dir_edit,
            self.mid_count_spinbox,
            self.encoder_combo,
            self.rife_model_combo, # Changing RIFE model affects preview
            self.sanchez_false_colour_checkbox, # Sanchez settings affect preview
            self.sanchez_res_spinbox, # Sanchez settings affect preview
            # FFmpeg interpolation settings also affect preview
            self.ffmpeg_mi_mode_combo,
            self.ffmpeg_mc_mode_combo,
            self.ffmpeg_me_mode_combo,
            self.ffmpeg_vsbmc_checkbox,
            self.ffmpeg_scd_combo,
            self.ffmpeg_me_algo_edit,
            self.ffmpeg_search_param_spinbox,
            self.ffmpeg_scd_threshold_spinbox,
            self.ffmpeg_mb_size_edit,
            self.ffmpeg_unsharp_group, # Unsharp affects preview
            self.ffmpeg_unsharp_lx_spinbox,
            self.ffmpeg_unsharp_ly_spinbox,
            self.ffmpeg_unsharp_la_spinbox,
            self.ffmpeg_unsharp_cx_spinbox,
            self.ffmpeg_unsharp_cy_spinbox,
            self.ffmpeg_unsharp_ca_spinbox,
        ]

        for control in preview_update_controls:
            if isinstance(control, (QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox)):
                if hasattr(control, 'currentTextChanged'):
                    control.currentTextChanged.connect(self.request_previews_update.emit)
                elif hasattr(control, 'textChanged'):
                    control.textChanged.connect(self.request_previews_update.emit)
                elif hasattr(control, 'valueChanged'):
                    control.valueChanged.connect(self.request_previews_update.emit)
            elif isinstance(control, QCheckBox):
                 control.stateChanged.connect(self.request_previews_update.emit)
            elif isinstance(control, QGroupBox):
                 control.toggled.connect(self.request_previews_update.emit)


    def _on_profile_selected(self, profile_name: str) -> None:
        LOGGER.debug(f"Entering _on_profile_selected... profile_name={profile_name}")
        """Load settings from the selected FFmpeg profile."""
        if profile_name == "Custom":
            # Do nothing, settings are already custom
            return

        profile_dict = FFMPEG_PROFILES.get(profile_name)
        if not profile_dict:
            LOGGER.warning(f"Unknown FFmpeg profile selected: {profile_name}")
            return

        # Block signals while updating widgets to prevent _on_ffmpeg_setting_changed from firing
        widgets_to_block = [
            self.ffmpeg_mi_mode_combo,
            self.ffmpeg_mc_mode_combo,
            self.ffmpeg_me_mode_combo,
            self.ffmpeg_vsbmc_checkbox,
            self.ffmpeg_scd_combo,
            self.ffmpeg_me_algo_edit,
            self.ffmpeg_search_param_spinbox,
            self.ffmpeg_scd_threshold_spinbox,
            self.ffmpeg_mb_size_edit,
            self.ffmpeg_unsharp_group,
            self.ffmpeg_unsharp_lx_spinbox,
            self.ffmpeg_unsharp_ly_spinbox,
            self.ffmpeg_unsharp_la_spinbox,
            self.ffmpeg_unsharp_cx_spinbox,
            self.ffmpeg_unsharp_cy_spinbox,
            self.ffmpeg_unsharp_ca_spinbox,
            self.ffmpeg_quality_combo,
            self.ffmpeg_crf_spinbox,
            self.ffmpeg_bitrate_spinbox,
            self.ffmpeg_bufsize_spinbox,
            self.ffmpeg_pix_fmt_combo,
            self.ffmpeg_filter_preset_combo,
        ]

        for widget in widgets_to_block:
            widget.blockSignals(True)

        try:
            # Update interpolation settings
            self.ffmpeg_mi_mode_combo.setCurrentText(profile_dict["mi_mode"])
            self.ffmpeg_mc_mode_combo.setCurrentText(profile_dict["mc_mode"])
            self.ffmpeg_me_mode_combo.setCurrentText(profile_dict["me_mode"])
            self.ffmpeg_vsbmc_checkbox.setChecked(profile_dict["vsbmc"])
            self.ffmpeg_scd_combo.setCurrentText(profile_dict["scd"])
            self.ffmpeg_me_algo_edit.setText(profile_dict["me_algo"])
            self.ffmpeg_search_param_spinbox.setValue(profile_dict["search_param"])
            self.ffmpeg_scd_threshold_spinbox.setValue(profile_dict["scd_threshold"])
            self.ffmpeg_mb_size_edit.setText(profile_dict["mb_size"])

            # Update unsharp settings
            self.ffmpeg_unsharp_group.setChecked(profile_dict["apply_unsharp"])
            self.ffmpeg_unsharp_lx_spinbox.setValue(profile_dict["unsharp_lx"])
            self.ffmpeg_unsharp_ly_spinbox.setValue(profile_dict["unsharp_ly"])
            self.ffmpeg_unsharp_la_spinbox.setValue(profile_dict["unsharp_la"])
            self.ffmpeg_unsharp_cx_spinbox.setValue(profile_dict["unsharp_cx"])
            self.ffmpeg_unsharp_cy_spinbox.setValue(profile_dict["unsharp_cy"])
            self.ffmpeg_unsharp_ca_spinbox.setValue(profile_dict["unsharp_ca"])

            # Update quality settings
            self.ffmpeg_quality_combo.setCurrentText(profile_dict["preset_text"])
            # Setting the quality combo text will trigger _update_quality_controls_state
            # which will handle setting CRF/Bitrate/Bufsize/PixFmt based on the preset text.
            # If the preset text is "Custom", it will enable the individual controls.
            # If it's a known preset, it will set the values and disable the controls.

            self.ffmpeg_filter_preset_combo.setCurrentText(profile_dict["filter_preset"])

        finally:
            # Unblock signals
            for widget in widgets_to_block:
                widget.blockSignals(False)

        # After loading a profile, check if the current settings still match the loaded profile
        # If they don't (e.g., due to manual edits before selecting the profile),
        # the profile combo should revert to "Custom".
        if not self._check_settings_match_profile(profile_dict):
             LOGGER.debug(f"Current settings do not match profile '{profile_name}', setting profile combo to 'Custom'.")
             self.ffmpeg_profile_combo.setCurrentText("Custom")
        else:
             LOGGER.debug(f"Current settings match profile '{profile_name}'.")


    def _on_ffmpeg_setting_changed(self, *args: Any) -> None:
        LOGGER.debug("Entering _on_ffmpeg_setting_changed...")
        """Handle changes to FFmpeg settings to set the profile combo to 'Custom'."""
        # Check if the current settings match any known profile
        current_settings = self._get_current_ffmpeg_settings()
        matching_profile_name = None
        for name, profile_dict in FFMPEG_PROFILES.items():
            if self._check_settings_match_profile(profile_dict):
                matching_profile_name = name
                break

        # If settings match a profile, set the combo box to that profile
        if matching_profile_name and self.ffmpeg_profile_combo.currentText() != matching_profile_name:
            LOGGER.debug(f"Settings match profile '{matching_profile_name}', setting profile combo.")
            self.ffmpeg_profile_combo.blockSignals(True) # Block to prevent re-triggering
            self.ffmpeg_profile_combo.setCurrentText(matching_profile_name)
            self.ffmpeg_profile_combo.blockSignals(False)
        # If settings don't match any profile and the current text is not already "Custom", set it to "Custom"
        elif not matching_profile_name and self.ffmpeg_profile_combo.currentText() != "Custom":
            LOGGER.debug("Settings do not match any profile, setting profile combo to 'Custom'.")


    def _makeModelLibraryTab(self) -> QWidget:
        """Create and return the Model Library tab widget."""
        model_library_tab = QWidget()
        layout = QVBoxLayout(model_library_tab)

        info_label = QLabel("Available RIFE Models:")
        layout.addWidget(info_label)

        self.model_table = QTableWidget()
        self.model_table.setColumnCount(2)
        self.model_table.setHorizontalHeaderLabels(["Model Key", "Path"])
        header = self.model_table.horizontalHeader()
        if header is not None: # Check if header is not None
            header.setStretchLastSection(True)
        self.model_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )  # Make table read-only
        layout.addWidget(self.model_table)

        layout.addStretch(1)  # Push table to the top

        self._populate_model_table()  # Populate the table with available models

        return model_library_tab

    def _populate_model_table(self) -> None:
        LOGGER.debug("Entering _populate_model_table...")
        """Populate the model table with available RIFE models."""
        available_models = config.get_available_rife_models() # Use correct function name
        self.model_table.setRowCount(len(available_models))

        for row, model_key in enumerate(available_models): # Iterate over list of keys
            model_path = f"goesvfi/models/{model_key}" # Construct path
            self.model_table.setItem(row, 0, QTableWidgetItem(model_key))
            self.model_table.setItem(row, 1, QTableWidgetItem(model_path)) # Use constructed path
    # Ensure exactly one blank line and correct indentation for the next method
    def _toggle_tile_size_enabled(self, state: int) -> None:
        """Enable/disable the tile size spinbox based on the checkbox state."""
        # Note: state is an int, compare with enum's value
        is_checked = (state == Qt.CheckState.Checked.value)
        LOGGER.debug(f"Entering _toggle_tile_size_enabled... state={state}, is_checked={is_checked}")
        if hasattr(self, 'tile_size_spinbox'):
            # Ensure consistent 8-space indentation within the method
            self.tile_size_spinbox.setEnabled(is_checked)
            LOGGER.debug(f"Set tile_size_spinbox enabled state to: {is_checked}")
        else:
            LOGGER.warning("tile_size_spinbox attribute not found in _toggle_tile_size_enabled.")
    def _on_clear_crop_clicked(self) -> None:
        """Clear the current crop rectangle and update previews."""
        self.current_crop_rect = None
        LOGGER.info("Crop rectangle cleared.")
        self._update_crop_buttons_state()
        self.request_previews_update.emit()  # Request preview update
    def _show_zoom(self, label: ClickableLabel) -> None:
        """Show a zoomed view of the processed image associated with the clicked label."""
        LOGGER.debug(f"Entering _show_zoom for label: {label.objectName()}") # Assuming labels have object names

        # Get the full resolution processed pixmap from the label
        # Ensure the label has the 'processed_image' attribute storing a QImage
        if not hasattr(label, 'processed_image') or label.processed_image is None:
            LOGGER.warning("Clicked label has no processed image attribute or it is None.")
            # Optionally show a message box to the user
            # QMessageBox.information(self, "Zoom", "No processed image available for this frame yet.")
            return
        if not isinstance(label.processed_image, QImage):
             LOGGER.warning(f"Label's processed_image is not a QImage: {type(label.processed_image)}")
             return

        full_res_processed_pixmap = QPixmap.fromImage(label.processed_image)
        if full_res_processed_pixmap.isNull():
            LOGGER.warning("Failed to create QPixmap from processed image for zoom.")
            # Optionally show a message box to the user
            # QMessageBox.warning(self, "Zoom Error", "Could not load the processed image for zooming.")
            return

        # --- Scale pixmap for display ---
        scaled_pix: QPixmap
        screen = QApplication.primaryScreen()
        if screen:
            # Use 90% of available screen size
            max_size = screen.availableGeometry().size() * 0.9
            # Check if scaling is needed
            if (
                full_res_processed_pixmap.size().width() > max_size.width()
                or full_res_processed_pixmap.size().height() > max_size.height()
            ):
                LOGGER.debug(f"Scaling zoom image from {full_res_processed_pixmap.size()} to fit {max_size}")
                scaled_pix = full_res_processed_pixmap.scaled(
                    max_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            else:
                LOGGER.debug("Using original size for zoom image as it fits screen.")
                scaled_pix = (
                    full_res_processed_pixmap  # Use original size if it fits
                )
        else:
            # Fallback if screen info is not available
            LOGGER.warning("Could not get screen geometry for zoom dialog scaling, using fallback size.")
            fallback_size = QSize(1024, 768) # Define a reasonable fallback size
            scaled_pix = full_res_processed_pixmap.scaled(
                fallback_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        # --- End scaling ---

        if scaled_pix.isNull():
             LOGGER.error("Failed to create scaled pixmap for zoom dialog.")
             # QMessageBox.critical(self, "Zoom Error", "Failed to prepare image for zooming.")
             return

        LOGGER.debug(f"Showing ZoomDialog with pixmap size: {scaled_pix.size()}")
        dialog = ZoomDialog(scaled_pix, self)
        dialog.exec()

    def _connect_model_combo(self) -> None:
        """Connect the model combo box signal."""
        self.model_combo.currentTextChanged.connect(self._on_model_changed)

    def _on_tab_changed(self, index: int) -> None:
        """Handle tab changes and update the ViewModel."""
        LOGGER.debug(f"Tab changed to index: {index}")
        self.main_view_model.active_tab_index = index  # <-- Update ViewModel state
        # Add any other logic needed when a tab changes, e.g., triggering updates
        if self.tab_widget.widget(index) == self.main_tab:
            self.request_previews_update.emit()

    def _check_settings_match_profile(self, profile_dict: FfmpegProfile) -> bool:
        """Checks if current FFmpeg settings match a given profile dictionary."""
        current_settings = {
            "use_ffmpeg_interp": self.ffmpeg_interp_group.isChecked(),
            "filter_preset": self.filter_preset_combo.currentText(),
            "mi_mode": self.mi_mode_combo.currentText(),
            "mc_mode": self.mc_mode_combo.currentText(),
            "me_mode": self.me_mode_combo.currentText(),
            "me_algo": self.me_algo_combo.text(),
            "search_param": self.search_param_spinbox.value(),
            "scd_mode": self.scd_mode_combo.currentText(),
            "scd_threshold": self.scd_threshold_spinbox.value(),
            "mb_size": self.mb_size_combo.text(),
            "vsbmc": self.vsbmc_checkbox.isChecked(),
            "apply_unsharp": self.unsharp_group.isChecked(),
            "unsharp_lx": self.unsharp_lx_spinbox.value(),
            "unsharp_ly": self.unsharp_ly_spinbox.value(),
            "unsharp_la": self.unsharp_la_spinbox.value(),
            "unsharp_cx": self.unsharp_cx_spinbox.value(),
            "unsharp_cy": self.unsharp_cy_spinbox.value(),
            "unsharp_ca": self.unsharp_ca_spinbox.value(),
            "crf": self.crf_spinbox.value(),
            "bitrate": self.bitrate_spinbox.value(),
            "bufsize": self.bufsize_spinbox.value(),
            "pix_fmt": self.pix_fmt_combo.currentText(),
        }

        # Compare current settings with the profile dictionary
        # Need to handle potential differences in data types (e.g., int vs float for threshold)
        # and optional values (like scd_threshold when scd is none)
        # Explicitly list keys to satisfy TypedDict literal requirement
        ffmpeg_profile_keys: List[str] = [
            "use_ffmpeg_interp", "mi_mode", "mc_mode", "me_mode", "vsbmc", "scd",
            "me_algo", "search_param", "scd_threshold", "mb_size", "apply_unsharp",
            "unsharp_lx", "unsharp_ly", "unsharp_la", "unsharp_cx", "unsharp_cy",
            "unsharp_ca", "preset_text", "crf", "bitrate", "bufsize", "pix_fmt",
            "filter_preset"
        ]

        for key in ffmpeg_profile_keys:
            # Ensure key exists in current_settings before accessing
            if key not in current_settings:
                 LOGGER.warning(f"Key '{key}' in profile but not in current settings.")
                 return False

            current_value = current_settings[key]
            profile_value = profile_dict[key]  # type: ignore[literal-required] # Access using literal key

            if key == "scd_threshold":
                # Special handling for scd_threshold: compare only if scd_mode is not "none"
                # Need to access scd_mode using literal key as well
                current_scd_mode = current_settings.get("scd_mode")
                profile_scd_mode = profile_dict.get("scd") # Access using literal key

                if (
                    current_scd_mode != "none"
                    and profile_scd_mode != "none"
                    and current_value is not None # Ensure values are not None before comparison
                    and profile_value is not None
                ):
                    if abs(current_value - profile_value) > 1e-9:  # Use tolerance for float comparison
                        return False
                elif (
                    current_scd_mode == "none"
                    and profile_scd_mode == "none"
                ):
                    pass  # Both are none, consider them matching for this setting
                else:
                    return False  # One is none, the other is not
            else:
                # Direct comparison for other keys
                if current_value != profile_value:
                    return False

        return True  # All settings match

    def loadSettings(self) -> None:
        """Load settings from QSettings."""
        # Simplified version for debugging - just set defaults
        LOGGER.debug("Using simplified loadSettings")
        self.in_dir = None
        self.out_file_path = None
        self.current_encoder = "RIFE"
        # Skip all other settings - they will use widget defaults
        # Ultra-defensive fps_spinbox handling - the primary crash point
        try:
            # Multiple layers of safety checks
            if hasattr(self, 'fps_spinbox') and self.fps_spinbox is not None:
                # Check if object is valid and is a QSpinBox
                if isinstance(self.fps_spinbox, QSpinBox):
                    try:
                        # Try a simple property access to check object validity
                        _ = self.fps_spinbox.objectName()
                        
                        fps_value = self.settings.value("fps", 30, type=int)
                        self.fps_spinbox.setValue(fps_value)
                        LOGGER.debug(f"Successfully set fps_spinbox value to {fps_value}")
                    except RuntimeError as e:
                        LOGGER.warning(f"RuntimeError setting fps_spinbox value: {e}")
                else:
                    LOGGER.warning(f"fps_spinbox is not a QSpinBox: {type(self.fps_spinbox)}")
            elif hasattr(self, 'fps_spinbox') and self.fps_spinbox is None:
                 LOGGER.warning("fps_spinbox attribute is None")
            else:
                LOGGER.warning("fps_spinbox attribute does not exist")
        except Exception as e:
            LOGGER.error(f"Unhandled exception accessing fps_spinbox: {e}")
    
            
        # For each widget, use separate try blocks to ensure independent error handling
        
        # mid_count_spinbox
        try:
            if hasattr(self, "mid_count_spinbox") and self.mid_count_spinbox is not None:
                try:
                    # Test widget validity
                    _ = self.mid_count_spinbox.objectName()
                    if isinstance(self.mid_count_spinbox, QSpinBox):
                        try:
                            value = self.settings.value("mid_count", 1, type=int)
                            self.mid_count_spinbox.setValue(value)
                            LOGGER.debug(f"Set mid_count_spinbox to {value}")
                        except RuntimeError as e:
                            LOGGER.warning(f"RuntimeError setting mid_count_spinbox: {e}")
                    else:
                        LOGGER.warning("mid_count_spinbox is not a QSpinBox")
                except RuntimeError:
                    LOGGER.warning("mid_count_spinbox exists but appears to be invalid")
            else:
                LOGGER.warning("mid_count_spinbox not available")
        except Exception as e:
            LOGGER.error(f"Unhandled exception with mid_count_spinbox: {e}")
        
        # max_workers_spinbox
        try:
            if hasattr(self, "max_workers_spinbox") and self.max_workers_spinbox is not None:
                try:
                    _ = self.max_workers_spinbox.objectName()
                    if isinstance(self.max_workers_spinbox, QSpinBox):
                        try:
                            value = self.settings.value("max_workers", os.cpu_count() or 1, type=int)
                            self.max_workers_spinbox.setValue(value)
                            LOGGER.debug(f"Set max_workers_spinbox to {value}")
                        except RuntimeError as e:
                            LOGGER.warning(f"RuntimeError setting max_workers_spinbox: {e}")
                    else:
                        LOGGER.warning("max_workers_spinbox is not a QSpinBox")
                except RuntimeError:
                    LOGGER.warning("max_workers_spinbox exists but appears to be invalid")
            else:
                LOGGER.warning("max_workers_spinbox not available")
        except Exception as e:
            LOGGER.error(f"Unhandled exception with max_workers_spinbox: {e}")
        
        # encoder_combo
        try:
            if hasattr(self, "encoder_combo") and self.encoder_combo is not None:
                try:
                    _ = self.encoder_combo.objectName()
                    try:
                        value = self.settings.value("encoder", "RIFE", type=str)
                        self.encoder_combo.setCurrentText(value)
                        self.current_encoder = self.encoder_combo.currentText()
                        LOGGER.debug(f"Set encoder_combo to {value}")
                    except RuntimeError as e:
                        LOGGER.warning(f"RuntimeError setting encoder_combo: {e}")
                        # Ensure state variable is set even if widget fails
                        self.current_encoder = value
                except RuntimeError:
                    LOGGER.warning("encoder_combo exists but appears to be invalid")
                    self.current_encoder = self.settings.value("encoder", "RIFE", type=str)
            else:
                LOGGER.warning("encoder_combo not available")
                self.current_encoder = self.settings.value("encoder", "RIFE", type=str)
        except Exception as e:
            LOGGER.error(f"Unhandled exception with encoder_combo: {e}")
            # Ensure current_encoder is always set
            self.current_encoder = "RIFE"  # Default fallback

        # Load RIFE v4.6 settings with defensive checks
        try:
            self.model_combo.setCurrentText(
                self.settings.value("rife_model_key", "rife-v4.6", type=str)
            )
            self.current_model_key = self.model_combo.currentText()  # Update state variable
            self.rife_tile_checkbox.setChecked(
                self.settings.value("rife_tile_enable", False, type=bool)
            )
            self.rife_tile_size_spinbox.setValue(
                self.settings.value("rife_tile_size", 256, type=int)
            )
            self.rife_uhd_checkbox.setChecked(
                self.settings.value("rife_uhd_mode", False, type=bool)
            )
            self.rife_thread_spec_edit.setText(
                self.settings.value("rife_thread_spec", "1:2:2", type=str)
            )
            self.rife_tta_spatial_checkbox.setChecked(
                self.settings.value("rife_tta_spatial", False, type=bool)
            )
            self.rife_tta_temporal_checkbox.setChecked(
                self.settings.value("rife_tta_temporal", False, type=bool)
            )
        except RuntimeError as e:
            # Catch Qt widget access errors for RIFE settings
            LOGGER.warning(f"Error accessing RIFE widgets during loadSettings: {e}")

        # Load Sanchez settings
        try:
            self.sanchez_false_colour_checkbox.setChecked(
                self.settings.value("sanchez_false_colour", False, type=bool)
            )
            # Use combo box for resolution
            res_km_value = self.settings.value("sanchez_res_km", "4", type=str) # Default to "4" string
            if hasattr(self, "sanchez_res_km_combo") and self.sanchez_res_km_combo is not None:
                if self.sanchez_res_km_combo.findText(res_km_value) != -1:
                     self.sanchez_res_km_combo.setCurrentText(res_km_value)
                else:
                     self.sanchez_res_km_combo.setCurrentText("4") # Fallback if saved value is invalid
            else:
                LOGGER.warning("sanchez_res_km_combo not found during loadSettings")
        except RuntimeError as e:
            # Catch Qt widget access errors for Sanchez settings
            LOGGER.warning(f"Error accessing Sanchez widgets during loadSettings: {e}")

        # Load crop rectangle
        crop_rect_str = self.settings.value("crop_rect", "", type=str)
        if crop_rect_str:
            try:
                x, y, w, h = map(int, crop_rect_str.split(","))
                self.current_crop_rect = (x, y, w, h)
            except ValueError:
                self.current_crop_rect = None
                LOGGER.warning(f"Invalid crop_rect setting: {crop_rect_str}")
        else:
            self.current_crop_rect = None

        # Load FFmpeg settings
        self.ffmpeg_interp_group.setChecked(
            self.settings.value("ffmpeg_use_interp", True, type=bool)
        )
        self.filter_preset_combo.setCurrentText(
            self.settings.value("ffmpeg_filter_preset", "slow", type=str)
        )
        self.mi_mode_combo.setCurrentText(
            self.settings.value("ffmpeg_mi_mode", "mci", type=str)
        )
        self.mc_mode_combo.setCurrentText(
            self.settings.value("ffmpeg_mc_mode", "obmc", type=str)
        )
        self.me_mode_combo.setCurrentText(
            self.settings.value("ffmpeg_me_mode", "bidir", type=str)
        )
        self.me_algo_combo.setText(
            self.settings.value("ffmpeg_me_algo", "(default)", type=str)
        )
        self.search_param_spinbox.setValue(
            self.settings.value("ffmpeg_search_param", 96, type=int)
        )
        self.scd_mode_combo.setCurrentText(
            self.settings.value("ffmpeg_scd_mode", "fdiff", type=str)
        )
        self.scd_threshold_spinbox.setValue(
            self.settings.value("ffmpeg_scd_threshold", 10.0, type=float)
        )
        self.mb_size_combo.setText(
            self.settings.value("ffmpeg_mb_size", "(default)", type=str)
        )
        self.vsbmc_checkbox.setChecked(
            self.settings.value("ffmpeg_vsbmc", False, type=bool)
        )
        self.unsharp_group.setChecked(
            self.settings.value("ffmpeg_apply_unsharp", True, type=bool)
        )
        self.unsharp_lx_spinbox.setValue(
            self.settings.value("ffmpeg_unsharp_lx", 7, type=int)
        )
        self.unsharp_ly_spinbox.setValue(
            self.settings.value("ffmpeg_unsharp_ly", 7, type=int)
        )
        self.unsharp_la_spinbox.setValue(
            self.settings.value("ffmpeg_unsharp_la", 1.0, type=float)
        )
        self.unsharp_cx_spinbox.setValue(
            self.settings.value("ffmpeg_unsharp_cx", 5, type=int)
        )
        self.unsharp_cy_spinbox.setValue(
            self.settings.value("ffmpeg_unsharp_cy", 5, type=int)
        )
        self.unsharp_ca_spinbox.setValue(
            self.settings.value("ffmpeg_unsharp_ca", 0.0, type=float)
        )
        self.crf_spinbox.setValue(self.settings.value("ffmpeg_crf", 16, type=int))
        self.bitrate_spinbox.setValue(
            self.settings.value("ffmpeg_bitrate", 15000, type=int)
        )
        self.bufsize_spinbox.setValue(
            self.settings.value("ffmpeg_bufsize", 22500, type=int)
        )
        self.pix_fmt_combo.setCurrentText(
            self.settings.value("ffmpeg_pix_fmt", "yuv444p", type=str)
        )

        # Update UI elements based on loaded settings
        if self.in_dir:
            self.in_dir_edit.setText(str(self.in_dir))
        if self.out_file_path:
            self.out_file_edit.setText(str(self.out_file_path))

        # Check if loaded settings match any predefined profile and set the combo box
        matched_profile = "Custom"
        for profile_name, profile_dict in FFMPEG_PROFILES.items():
            if self._check_settings_match_profile(profile_dict):
                matched_profile = profile_name
                break
        self.profile_combo.setCurrentText(matched_profile)

    def saveSettings(self) -> None:
        """Save settings to QSettings."""
        # Save basic settings that don't require widget access
        self.settings.setValue("in_dir", str(self.in_dir) if self.in_dir else "")
        self.settings.setValue(
            "out_file_path", str(self.out_file_path) if self.out_file_path else ""
        )
        
        # Add safety checks for all widget accesses to prevent "wrapped C/C++ object deleted" errors
        try:
            if hasattr(self, "fps_spinbox") and self.fps_spinbox is not None and isinstance(self.fps_spinbox, QSpinBox):
                self.settings.setValue("fps", self.fps_spinbox.value())
            
            if hasattr(self, "mid_count_spinbox") and self.mid_count_spinbox is not None:
                self.settings.setValue("mid_count", self.mid_count_spinbox.value())
                
            if hasattr(self, "max_workers_spinbox") and self.max_workers_spinbox is not None:
                self.settings.setValue("max_workers", self.max_workers_spinbox.value())
                
            if hasattr(self, "encoder_combo") and self.encoder_combo is not None:
                self.settings.setValue("encoder", self.encoder_combo.currentText())

            # Save RIFE v4.6 settings with safety checks
            if hasattr(self, "model_combo") and self.model_combo is not None:
                self.settings.setValue("rife_model_key", self.model_combo.currentText())
                
            if hasattr(self, "rife_tile_checkbox") and self.rife_tile_checkbox is not None:
                self.settings.setValue("rife_tile_enable", self.rife_tile_checkbox.isChecked())
                
            if hasattr(self, "rife_tile_size_spinbox") and self.rife_tile_size_spinbox is not None:
                self.settings.setValue("rife_tile_size", self.rife_tile_size_spinbox.value())
                
            if hasattr(self, "rife_uhd_checkbox") and self.rife_uhd_checkbox is not None:
                self.settings.setValue("rife_uhd_mode", self.rife_uhd_checkbox.isChecked())
                
            if hasattr(self, "rife_thread_spec_edit") and self.rife_thread_spec_edit is not None:
                self.settings.setValue("rife_thread_spec", self.rife_thread_spec_edit.text())
                
            if hasattr(self, "rife_tta_spatial_checkbox") and self.rife_tta_spatial_checkbox is not None:
                self.settings.setValue(
                    "rife_tta_spatial", self.rife_tta_spatial_checkbox.isChecked()
                )
                
            if hasattr(self, "rife_tta_temporal_checkbox") and self.rife_tta_temporal_checkbox is not None:
                self.settings.setValue(
                    "rife_tta_temporal", self.rife_tta_temporal_checkbox.isChecked()
                )
        except RuntimeError as e:
            LOGGER.warning(f"Error saving widget settings: {e}")
            return  # Exit early to avoid further widget access causing errors

        # Save Sanchez settings
        try:
            if hasattr(self, "sanchez_false_colour_checkbox") and self.sanchez_false_colour_checkbox is not None:
                self.settings.setValue(
                    "sanchez_false_colour", self.sanchez_false_colour_checkbox.isChecked()
                )

            # Use the new combo box alias
            if hasattr(self, "sanchez_res_km_combo") and self.sanchez_res_km_combo is not None:
                self.settings.setValue("sanchez_res_km", self.sanchez_res_km_combo.currentText())
        except RuntimeError as e:
            LOGGER.warning(f"Error saving Sanchez settings: {e}")

            # Save crop rectangle
            if self.current_crop_rect:
                x, y, w, h = self.current_crop_rect
                self.settings.setValue("crop_rect", f"{x},{y},{w},{h}")
            else:
                self.settings.setValue("crop_rect", "")

            # Save FFmpeg settings - with safety checks
            if hasattr(self, "ffmpeg_interp_group") and self.ffmpeg_interp_group is not None:
                self.settings.setValue(
                    "ffmpeg_use_interp", self.ffmpeg_interp_group.isChecked()
                )
            
            if hasattr(self, "filter_preset_combo") and self.filter_preset_combo is not None:
                self.settings.setValue(
                    "ffmpeg_filter_preset", self.filter_preset_combo.currentText()
                )
                
            if hasattr(self, "mi_mode_combo") and self.mi_mode_combo is not None:
                self.settings.setValue("ffmpeg_mi_mode", self.mi_mode_combo.currentText())
                
            if hasattr(self, "mc_mode_combo") and self.mc_mode_combo is not None:
                self.settings.setValue("ffmpeg_mc_mode", self.mc_mode_combo.currentText())
                
            if hasattr(self, "me_mode_combo") and self.me_mode_combo is not None:
                self.settings.setValue("ffmpeg_me_mode", self.me_mode_combo.currentText())
                
            if hasattr(self, "me_algo_combo") and self.me_algo_combo is not None:
                self.settings.setValue("ffmpeg_me_algo", self.me_algo_combo.text())
                
            if hasattr(self, "search_param_spinbox") and self.search_param_spinbox is not None:
                self.settings.setValue("ffmpeg_search_param", self.search_param_spinbox.value())
                
            if hasattr(self, "scd_mode_combo") and self.scd_mode_combo is not None:
                self.settings.setValue("ffmpeg_scd_mode", self.scd_mode_combo.currentText())
                
            if hasattr(self, "scd_threshold_spinbox") and self.scd_threshold_spinbox is not None:
                self.settings.setValue(
                    "ffmpeg_scd_threshold", self.scd_threshold_spinbox.value()
                )
                
            if hasattr(self, "mb_size_combo") and self.mb_size_combo is not None:
                self.settings.setValue("ffmpeg_mb_size", self.mb_size_combo.text())
                
            if hasattr(self, "vsbmc_checkbox") and self.vsbmc_checkbox is not None:
                self.settings.setValue("ffmpeg_vsbmc", self.vsbmc_checkbox.isChecked())
                
            if hasattr(self, "unsharp_group") and self.unsharp_group is not None:
                self.settings.setValue("ffmpeg_apply_unsharp", self.unsharp_group.isChecked())
                
            if hasattr(self, "unsharp_lx_spinbox") and self.unsharp_lx_spinbox is not None:
                self.settings.setValue("ffmpeg_unsharp_lx", self.unsharp_lx_spinbox.value())
                
            if hasattr(self, "unsharp_ly_spinbox") and self.unsharp_ly_spinbox is not None:
                self.settings.setValue("ffmpeg_unsharp_ly", self.unsharp_ly_spinbox.value())
                
            if hasattr(self, "unsharp_la_spinbox") and self.unsharp_la_spinbox is not None:
                self.settings.setValue("ffmpeg_unsharp_la", self.unsharp_la_spinbox.value())
                
            if hasattr(self, "unsharp_cx_spinbox") and self.unsharp_cx_spinbox is not None:
                self.settings.setValue("ffmpeg_unsharp_cx", self.unsharp_cx_spinbox.value())
                
            if hasattr(self, "unsharp_cy_spinbox") and self.unsharp_cy_spinbox is not None:
                self.settings.setValue("ffmpeg_unsharp_cy", self.unsharp_cy_spinbox.value())
                
            if hasattr(self, "unsharp_ca_spinbox") and self.unsharp_ca_spinbox is not None:
                self.settings.setValue("ffmpeg_ca", self.unsharp_ca_spinbox.value())
                
            if hasattr(self, "crf_spinbox") and self.crf_spinbox is not None:
                self.settings.setValue("ffmpeg_crf", self.crf_spinbox.value())
                
            if hasattr(self, "bitrate_spinbox") and self.bitrate_spinbox is not None:
                self.settings.setValue("ffmpeg_bitrate", self.bitrate_spinbox.value())
                
            if hasattr(self, "bufsize_spinbox") and self.bufsize_spinbox is not None:
                self.settings.setValue("ffmpeg_bufsize", self.bufsize_spinbox.value())
                
            if hasattr(self, "pix_fmt_combo") and self.pix_fmt_combo is not None:
                self.settings.setValue("ffmpeg_pix_fmt", self.pix_fmt_combo.currentText())

    def _validate_thread_spec(self, text: str) -> None:
        LOGGER.debug(f"Entering _validate_thread_spec... text={text}")
        """Validate the RIFE thread specification format."""
        # Simple regex check for format like "1:2:2"
        if not re.fullmatch(r"\d+:\d+:\d+", text):
            self.rife_thread_spec_edit.setStyleSheet("color: red;")
            self.start_button.setEnabled(False)  # Disable start button if invalid
            LOGGER.warning(f"Invalid RIFE thread specification format: {text}")
        else:
            self.rife_thread_spec_edit.setStyleSheet("")  # Reset style
            self._update_start_button_state()  # Re-check start button state

    def _populate_models(self) -> None:
        LOGGER.debug("Entering _populate_models...")
        """Populate the RIFE model combo box."""
        available_models = config.get_available_rife_models() # Use correct function name
        self.model_combo.clear()
        if available_models:
            self.model_combo.addItems(available_models) # Add list items directly
            # Set the current text to the loaded setting or default
            loaded_model = self.settings.value("rife_model_key", "rife-v4.6", type=str)
            if loaded_model in available_models: # Check membership in list
                self.model_combo.setCurrentText(loaded_model)
            else:
                self.model_combo.setCurrentIndex(0)  # Select the first available model
            self.current_model_key = (
                self.model_combo.currentText()
            )  # Update state variable
        else:
            self.model_combo.addItem("No RIFE models found")
            self.model_combo.setEnabled(False)
            self.current_model_key = ""  # Clear state variable
            LOGGER.warning("No RIFE models found.")

    def _toggle_sanchez_res_enabled(self, state: Qt.CheckState) -> None:
        """Enables or disables the Sanchez resolution spinbox based on the checkbox state."""
        self.sanchez_res_km_spinbox.setEnabled(state == Qt.CheckState.Checked.value)

    def _update_rife_ui_elements(self) -> None:
        LOGGER.debug("Entering _update_rife_ui_elements...")
        """Updates the visibility and state of RIFE-specific UI elements."""
        is_rife = self.current_encoder == "RIFE"

        # Toggle visibility of RIFE options group
        rife_options_parent = self.rife_options_layout.parentWidget()
        if rife_options_parent is not None: # Check if parent exists
            rife_options_parent.setVisible(is_rife)
        model_combo_parent = self.model_combo.parentWidget()
        if model_combo_parent is not None: # Check if parent exists
            model_combo_parent.setVisible(is_rife)  # Label and combo box

        # Update state of RIFE options based on capability
        if is_rife:
            rife_exe = None
            try:
                rife_exe = config.find_rife_executable(self.current_model_key) # Keep this to check for exe existence
                capability_detector = RifeCapabilityManager(model_key=self.current_model_key) # Instantiate with model_key

                self.rife_tile_checkbox.setEnabled(
                    capability_detector.capabilities.get("tiling", False)
                )
                # Tile size enabled state is handled by _toggle_tile_size_enabled signal
                self.rife_uhd_checkbox.setEnabled(capability_detector.capabilities.get("uhd", False))
                self.rife_thread_spec_edit.setEnabled(
                    capability_detector.capabilities.get("thread_spec", False)
                )
                self.rife_tta_spatial_checkbox.setEnabled(
                    capability_detector.capabilities.get("tta_spatial", False)
                )
                self.rife_tta_temporal_checkbox.setEnabled(
                    capability_detector.capabilities.get("tta_temporal", False)
                )

                # Warn if selected model doesn't support features
                if (
                    self.rife_tile_checkbox.isChecked()
                    and not capability_detector.capabilities.get("tiling", False) # Access capability from dict
                ):
                    LOGGER.warning(
                        f"Selected model '{self.current_model_key}' does not support tiling."
                    )
                if (
                    self.rife_uhd_checkbox.isChecked()
                    and not capability_detector.capabilities.get("uhd", False) # Access capability from dict
                ):
                    LOGGER.warning(
                        f"Selected model '{self.current_model_key}' does not support UHD mode."
                    )
                if (
                    self.rife_thread_spec_edit.text() != "1:2:2"
                    and not capability_detector.capabilities.get("thread_spec", False) # Access capability from dict
                ):
                    LOGGER.warning(
                        f"Selected model '{self.current_model_key}' does not support custom thread specification."
                    )
                if (
                    self.rife_tta_spatial_checkbox.isChecked()
                    and not capability_detector.capabilities.get("tta_spatial", False) # Access capability from dict
                ):
                    LOGGER.warning(
                        f"Selected model '{self.current_model_key}' does not support spatial TTA."
                    )
                if (
                    self.rife_tta_temporal_checkbox.isChecked()
                    and not capability_detector.capabilities.get("tta_temporal", False) # Access capability from dict
                 ):
                    LOGGER.warning(
                        f"Selected model '{self.current_model_key}' does not support temporal TTA."
                    )

            except FileNotFoundError:
                # If RIFE executable is not found for the selected model, disable all RIFE options
                self.rife_tile_checkbox.setEnabled(False)
                self.rife_tile_size_spinbox.setEnabled(False)
                self.rife_uhd_checkbox.setEnabled(False)
                self.rife_thread_spec_edit.setEnabled(False)
                self.rife_tta_spatial_checkbox.setEnabled(False)
                self.rife_tta_temporal_checkbox.setEnabled(False)
                LOGGER.warning(
                    f"RIFE executable not found for model '{self.current_model_key}'. RIFE options disabled."
                )
            except Exception as e:
                LOGGER.error(
                    f"Error checking RIFE capabilities for model '{self.current_model_key}': {e}"
                )
                # Disable options on error
                self.rife_tile_checkbox.setEnabled(False)
                self.rife_tile_size_spinbox.setEnabled(False)
                self.rife_uhd_checkbox.setEnabled(False)
                self.rife_thread_spec_edit.setEnabled(False)
                self.rife_tta_spatial_checkbox.setEnabled(False)
                self.rife_tta_temporal_checkbox.setEnabled(False)

    def _on_model_changed(self, model_key: str) -> None:
        LOGGER.debug(f"Entering _on_model_changed... model_key={model_key}")
        """Handle RIFE model selection change."""
        self.current_model_key = model_key
        self._update_rife_ui_elements()  # Update RIFE options based on new model
        self._update_start_button_state()  # Re-check start button state

    def closeEvent(self, event: QCloseEvent | None) -> None:
        LOGGER.debug("Entering closeEvent...")
        """Handle the window closing event."""
        if self.is_processing:
            reply = QMessageBox.question(
                self,
                "Processing in Progress",
                "Processing is still in progress. Do you want to cancel and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                if self.vfi_worker:
                    self.vfi_worker.terminate()  # Attempt to terminate the worker thread
                    self.vfi_worker.wait()  # Wait for the thread to finish
                # Clean up the GUI Sanchez temp directory
                if self._sanchez_gui_temp_dir.exists():
                    try:
                        shutil.rmtree(self._sanchez_gui_temp_dir)
                        LOGGER.info(
                            f"Cleaned up GUI Sanchez temp directory: {self._sanchez_gui_temp_dir}"
                        )
                    except Exception as cleanup_error:
                        LOGGER.warning(
                            f"Failed to clean up GUI Sanchez temp directory: {cleanup_error}"
                        )
                if event:
                    event.accept()
            else:
                if event:
                    event.ignore()
        else:
            # Clean up the GUI Sanchez temp directory on normal exit
            if self._sanchez_gui_temp_dir.exists():
                try:
                    shutil.rmtree(self._sanchez_gui_temp_dir)
                    LOGGER.info(
                        f"Cleaned up GUI Sanchez temp directory: {self._sanchez_gui_temp_dir}"
                    )
                except Exception as cleanup_error:
                    LOGGER.warning(
                        f"Failed to clean up GUI Sanchez temp directory: {cleanup_error}"
                    )
            # Settings are saved proactively or not saved on close to avoid widget deletion errors.
            # try:
            #     self.saveSettings()  # Save settings on exit - REMOVED
            # except RuntimeError as e:
            #     # This is likely a Qt object lifetime issue in tests; log and continue
            #     LOGGER.warning(f"Error saving settings during closeEvent: {e}")
                
            if event:
                event.accept()

    def _load_process_scale_preview(
        self,
        image_path: Path,
        target_label: ClickableLabel,
        image_loader: ImageLoader,
        sanchez_processor: SanchezProcessor,
        image_cropper: ImageCropper,
        # Add missing parameters
        apply_sanchez: bool,
        crop_rect: Optional[Tuple[int, int, int, int]],
    ) -> QPixmap | None:
        """Loads, processes (crop/sanchez), scales, and returns a preview pixmap
        using the provided ImageProcessor instances.
        """
        try:
            # 1. Load original image
            LOGGER.debug(f"Loading image: {image_path}")
            current_image_data_obj = image_loader.load(str(image_path))
            LOGGER.debug(f"Image loaded successfully. Original type: {type(current_image_data_obj.image_data)}")

            sanchez_processing_failed = False
            sanchez_error_message = ""

            # 2. Apply Sanchez if requested
            if apply_sanchez:
                processed_data_obj = None
                # Check cache first
                if image_path in self.sanchez_preview_cache:
                    LOGGER.debug(f"Using cached Sanchez result for: {image_path.name}")
                    cached_array = self.sanchez_preview_cache[image_path]
                    # Create a new ImageData object from the cached array
                    # Preserve metadata if possible, otherwise create minimal
                    metadata = current_image_data_obj.metadata if hasattr(current_image_data_obj, 'metadata') else {}
                    processed_data_obj = ImageData(image_data=cached_array, metadata=metadata)
                else:
                    LOGGER.debug(f"No cached Sanchez result for {image_path.name}, processing...")
                    try:
                        # Read resolution from ComboBox
                        res_km_str = "4"
                        if hasattr(self, 'sanchez_res_combo') and self.sanchez_res_combo is not None:
                            try: res_km_str = self.sanchez_res_combo.currentText()
                            except (RuntimeError, AttributeError) as e: LOGGER.warning(f"Could not get Sanchez resolution value: {e}")
                        else: LOGGER.warning("Sanchez resolution ComboBox not found")

                        try: res_km_val = float(res_km_str)
                        except ValueError: res_km_val = 4.0

                        LOGGER.debug(f"Applying Sanchez to preview for: {image_path.name} with res_km={res_km_val}")
                        sanchez_kwargs = {'res_km': res_km_val}
                        if 'filename' not in current_image_data_obj.metadata:
                             current_image_data_obj.metadata['filename'] = image_path.name
                             LOGGER.debug(f"Added filename to metadata for Sanchez: {image_path.name}")

                        # Run Sanchez Processor
                        processed_data_obj = sanchez_processor.process(current_image_data_obj, **sanchez_kwargs)
                        LOGGER.debug("Sanchez processing completed.")

                        # Cache the result (as NumPy array)
                        result_array: Optional[np.ndarray] = None
                        if isinstance(processed_data_obj.image_data, Image.Image):
                            result_array = np.array(processed_data_obj.image_data)
                        elif isinstance(processed_data_obj.image_data, np.ndarray):
                            result_array = processed_data_obj.image_data

                        if result_array is not None:
                            self.sanchez_preview_cache[image_path] = result_array.copy()
                            LOGGER.debug(f"Stored Sanchez result in cache for: {image_path.name}")
                        else:
                            LOGGER.warning("Sanchez processed data was not in expected format (PIL/NumPy) for caching.")

                    except Exception as e:
                        LOGGER.exception(f"Error during Sanchez processing for preview {image_path.name}: {e}")
                        sanchez_processing_failed = True
                        sanchez_error_message = str(e)
                        # Keep original image data if Sanchez fails
                        processed_data_obj = current_image_data_obj

                # Update the main object if Sanchez processing was successful (or retrieved from cache)
                if processed_data_obj is not None and not sanchez_processing_failed:
                    current_image_data_obj = processed_data_obj
                    LOGGER.debug("Updated current_image_data_obj with Sanchez result.")
                elif sanchez_processing_failed:
                     LOGGER.warning("Keeping original image data due to Sanchez failure.")
                else:
                     LOGGER.warning("Sanchez was requested but processed_data_obj is None and no failure recorded.")


            # 3. Apply Crop if requested
            # Use the passed crop_rect parameter, not self.current_crop_rect
            if crop_rect:
                LOGGER.debug("Cropping requested")
                try:
                    LOGGER.debug(f"Applying crop {crop_rect} to preview for {image_path.name}")
                    x, y, w, h = crop_rect
                    crop_rect_pil = (x, y, x + w, y + h)
                    # Crop the *current* image data object
                    current_image_data_obj = image_cropper.crop(current_image_data_obj, crop_rect_pil)
                    LOGGER.debug("Cropping completed successfully.")
                except Exception as e:
                    LOGGER.exception(f"Error during crop processing for preview {image_path.name}: {e}")
                    # If cropping fails, continue with the uncropped image data

            # 4. Convert the FINAL image data (original, sanchez, cropped, or sanchez+cropped) to QImage
            final_q_image: Optional[QImage] = None
            final_img_array: Optional[np.ndarray] = None

            if isinstance(current_image_data_obj.image_data, Image.Image):
                LOGGER.debug("Final image data is PIL Image, converting to NumPy array")
                final_img_array = np.array(current_image_data_obj.image_data)
            elif isinstance(current_image_data_obj.image_data, np.ndarray):
                LOGGER.debug("Final image data is NumPy array")
                final_img_array = current_image_data_obj.image_data
            else:
                LOGGER.error(f"Unsupported final image data type: {type(current_image_data_obj.image_data)}")
                return None # Cannot proceed

            LOGGER.debug("Converting final NumPy array to QImage")
            try:
                height, width, channel = final_img_array.shape
                bytes_per_line = channel * width
                if channel == 4: format = QImage.Format.Format_RGBA8888
                elif channel == 3: format = QImage.Format.Format_RGB888
                elif channel == 1:
                    format = QImage.Format.Format_Grayscale8
                    bytes_per_line = width
                else: raise ValueError(f"Unsupported number of channels: {channel}")

                # Ensure the array is C-contiguous for QImage
                contiguous_img_array = np.ascontiguousarray(final_img_array)
                final_q_image = QImage(
                    contiguous_img_array.data, width, height, bytes_per_line, format
                ).copy()
                LOGGER.debug("Successfully converted final NumPy array to QImage")
            except Exception as conversion_err:
                LOGGER.exception(f"Failed converting final NumPy array to QImage: {conversion_err}")
                return None

            # 5. Store original path and final processed QImage in the label
            target_label.file_path = str(image_path)
            target_label.processed_image = final_q_image.copy() # Store the full-res processed image

            # 6. Scale the final QImage for preview display
            LOGGER.debug("Scaling final QImage for preview display")
            target_size = QSize(100, 100) # Default size
            try:
                if hasattr(target_label, 'size') and target_label is not None:
                    target_size = target_label.size()
                if target_size.width() <= 0 or target_size.height() <= 0:
                    target_size = QSize(100, 100)
                LOGGER.debug(f"Target label size: {target_size}")
            except (RuntimeError, AttributeError) as e:
                 LOGGER.warning(f"Could not get target label size: {e}, using default.")

            scaled_img = final_q_image.scaled(
                target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            LOGGER.debug("Image scaled successfully")

            # 7. Create QPixmap and add Sanchez warning if needed
            pixmap = QPixmap.fromImage(scaled_img)
            LOGGER.debug("QPixmap created successfully")

            draw_sanchez_warning = False
            if sanchez_processing_failed and apply_sanchez: # Only show warning if Sanchez was requested
                 if hasattr(self, 'sanchez_false_colour_checkbox') and self.sanchez_false_colour_checkbox is not None:
                     try:
                         # Check current state, maybe user unchecked it while processing failed
                         if self.sanchez_false_colour_checkbox.isChecked():
                             draw_sanchez_warning = True
                     except (RuntimeError, AttributeError): pass # Ignore if checkbox gone

            if draw_sanchez_warning:
                LOGGER.debug("Drawing Sanchez failure warning on pixmap")
                try:
                    painter = QPainter(pixmap)
                    font = painter.font(); font.setBold(True); painter.setFont(font)
                    painter.fillRect(0, 0, pixmap.width(), 20, QColor(0, 0, 0, 150))
                    painter.setPen(Qt.GlobalColor.red)
                    painter.drawText(5, 15, f"Sanchez failed: {sanchez_error_message[:35]}...")
                    painter.end()
                    LOGGER.debug("Sanchez warning drawn")
                except Exception as paint_error:
                    LOGGER.error(f"Failed to draw Sanchez warning: {paint_error}")

            LOGGER.debug(f"Preview processing complete for {image_path}, returning pixmap.")
            return pixmap

        except Exception as e:
            LOGGER.exception(f"Unhandled error processing preview for {image_path}: {e}")
            try:
                if hasattr(target_label, 'file_path'): target_label.file_path = None
                if hasattr(target_label, 'processed_image'): target_label.processed_image = None
            except (RuntimeError, AttributeError): pass
            return None

    def _clear_preview_labels(self, message="First Frame"):
        """Helper method to clear all preview labels safely."""
        try:
            # Clear first frame
            if hasattr(self, 'first_frame_label') and self.first_frame_label is not None:
                try:
                    self.first_frame_label.clear()
                    self.first_frame_label.setText(message)
                    self.first_frame_label.file_path = None
                    self.first_frame_label.processed_image = None
                except (RuntimeError, AttributeError) as e:
                    LOGGER.warning(f"Error clearing first frame label: {e}")
                    
            # Clear middle frame
            if hasattr(self, 'middle_frame_label') and self.middle_frame_label is not None:
                try:
                    self.middle_frame_label.clear()
                    self.middle_frame_label.setText("Middle Frame")
                    self.middle_frame_label.file_path = None
                    self.middle_frame_label.processed_image = None
                except (RuntimeError, AttributeError) as e:
                    LOGGER.warning(f"Error clearing middle frame label: {e}")
                    
            # Clear last frame
            if hasattr(self, 'last_frame_label') and self.last_frame_label is not None:
                try:
                    self.last_frame_label.clear()
                    self.last_frame_label.setText("Last Frame")
                    self.last_frame_label.file_path = None
                    self.last_frame_label.processed_image = None
                except (RuntimeError, AttributeError) as e:
                    LOGGER.warning(f"Error clearing last frame label: {e}")
                    
        except Exception as e:
            LOGGER.warning(f"Error in _clear_preview_labels: {e}")
    
    def _update_previews(self) -> None:
        LOGGER.debug(f"Entering _update_previews. Current crop_rect: {self.current_crop_rect}, Sanchez enabled: {self.sanchez_false_colour_checkbox.isChecked()}")
        """Updates the preview images for first, middle, and last frames."""
        # Move log outside try block to ensure it's always printed if method is called
        LOGGER.debug("Entering _update_previews method")
        # Removed extra logging
        # NOTE: Removed self.sanchez_preview_cache.clear() - Cache should persist unless Sanchez settings change

        try:
            if not self.in_dir or not self.in_dir.is_dir():
                # Clear previews if no valid input directory
                LOGGER.debug("No valid input directory, clearing previews")
                self._clear_preview_labels()
                return
                
            LOGGER.debug(f"Input directory: {self.in_dir}")
            # Get sorted list of image files
            image_files = sorted(
                [
                    f
                    for f in self.in_dir.iterdir()
                    if f.is_file() and f.suffix.lower() in [".png", ".jpg", ".jpeg"]
                ]
            )

            if not image_files:
                # Clear previews if no images found
                LOGGER.debug("No image files found in directory")
                self._clear_preview_labels("No images found")
                return

            # Determine which frames to preview
            first_frame_path = image_files[0]
            last_frame_path = image_files[-1]
            middle_frame_path = None
            if len(image_files) > 2:
                middle_frame_path = image_files[len(image_files) // 2]

            # Load, process, and scale previews using the new processors
            try:
                LOGGER.debug(f"Loading first frame preview: {first_frame_path.name}")
                first_pixmap = self._load_process_scale_preview(
                    first_frame_path,
                    self.first_frame_label,
                    self.image_loader,
                    self.sanchez_processor,
                    self.image_cropper,
                    # Pass the required arguments
                    apply_sanchez=self.sanchez_false_colour_checkbox.isChecked(),
                    crop_rect=self.current_crop_rect,
                )
                if first_pixmap:
                    try:
                        self.first_frame_label.setPixmap(first_pixmap)
                        LOGGER.debug("Successfully set first frame preview")
                    except (RuntimeError, AttributeError) as e:
                        LOGGER.error(f"Error setting first frame pixmap: {e}")
                else:
                    LOGGER.warning("First frame preview generation failed")
                    try:
                        self.first_frame_label.clear()
                        self.first_frame_label.setText("Error loading preview")
                        self.first_frame_label.file_path = None
                        self.first_frame_label.processed_image = None
                    except (RuntimeError, AttributeError) as e:
                        LOGGER.error(f"Error clearing first frame: {e}")
            except Exception as e:
                LOGGER.error(f"Error processing first frame preview: {e}")

            # Handle middle frame if available
            if middle_frame_path:
                try:
                    LOGGER.debug(f"Loading middle frame preview: {middle_frame_path.name}")
                    middle_pixmap = self._load_process_scale_preview(
                        middle_frame_path,
                        self.middle_frame_label,
                        self.image_loader,
                        self.sanchez_processor,
                        self.image_cropper,
                        # Pass the required arguments
                        apply_sanchez=self.sanchez_false_colour_checkbox.isChecked(),
                        crop_rect=self.current_crop_rect,
                    )
                    if middle_pixmap:
                        try:
                            self.middle_frame_label.setPixmap(middle_pixmap)
                            LOGGER.debug("Successfully set middle frame preview")
                        except (RuntimeError, AttributeError) as e:
                            LOGGER.error(f"Error setting middle frame pixmap: {e}")
                    else:
                        LOGGER.warning("Middle frame preview generation failed")
                        try:
                            self.middle_frame_label.clear()
                            self.middle_frame_label.setText("Error loading preview")
                            self.middle_frame_label.file_path = None
                            self.middle_frame_label.processed_image = None
                        except (RuntimeError, AttributeError) as e:
                            LOGGER.error(f"Error clearing middle frame: {e}")
                except Exception as e:
                    LOGGER.error(f"Error processing middle frame preview: {e}")
            else:
                try:
                    LOGGER.debug("No middle frame available")
                    self.middle_frame_label.clear()
                    self.middle_frame_label.setText("Middle Frame (N/A)")
                    self.middle_frame_label.file_path = None
                    self.middle_frame_label.processed_image = None
                except (RuntimeError, AttributeError) as e:
                    LOGGER.error(f"Error clearing middle frame: {e}")

            # Process last frame
            try:
                LOGGER.debug(f"Loading last frame preview: {last_frame_path.name}")
                last_pixmap = self._load_process_scale_preview(
                    last_frame_path,
                    self.last_frame_label,
                    self.image_loader,
                    self.sanchez_processor,
                    self.image_cropper,
                    # Pass the required arguments
                    apply_sanchez=self.sanchez_false_colour_checkbox.isChecked(),
                    crop_rect=self.current_crop_rect,
                )
                if last_pixmap:
                    try:
                        self.last_frame_label.setPixmap(last_pixmap)
                        LOGGER.debug("Successfully set last frame preview")
                    except (RuntimeError, AttributeError) as e:
                        LOGGER.error(f"Error setting last frame pixmap: {e}")
                else:
                    LOGGER.warning("Last frame preview generation failed")
                    try:
                        self.last_frame_label.clear()
                        self.last_frame_label.setText("Error loading preview")
                        self.last_frame_label.file_path = None
                        self.last_frame_label.processed_image = None
                    except (RuntimeError, AttributeError) as e:
                        LOGGER.error(f"Error clearing last frame: {e}")
            except Exception as e:
                LOGGER.error(f"Error processing last frame preview: {e}")

        except Exception as e:
            LOGGER.exception(f"Error updating previews: {e}")
            
            # Use our safer method to clear labels
            self._clear_preview_labels("Error")
            
            # Show error message to user in a safe way
            try:
                QMessageBox.critical(
                    self, "Preview Error", f"Failed to update previews: {e}"
                )
            except Exception as dialog_error:
                # If even showing the dialog fails, just log it
                LOGGER.error(f"Failed to show error dialog: {dialog_error}")

    def _update_start_button_state(self) -> None:
        """Enable or disable the start button based on input/output paths and RIFE model availability."""
        # Use extremely defensive programming here - avoid accessing widget properties
        # that might trigger C++ object deleted errors
        
        # Default values in case we can't safely access widgets
        rife_model_selected = True
        thread_spec_valid = True
        
        try:
            # Check if using RIFE encoder
            is_rife = getattr(self, 'current_encoder', '') == "RIFE"
            
            if is_rife:
                # For RIFE encoder, check if model is selected and enabled
                # Don't access any widget methods (like isEnabled) directly
                if not (hasattr(self, 'current_model_key') and getattr(self, 'current_model_key', '') != ''):
                    rife_model_selected = False
            
        except Exception as e:
            LOGGER.warning(f"Error checking RIFE model selection: {e}")
            # Assume model is not valid if we can't safely check
            if is_rife:
                rife_model_selected = False
        # Check thread spec validity
        try:
            if is_rife:
                # Check if thread spec is valid without directly accessing widget methods
                thread_spec = ''
                if hasattr(self, 'rife_thread_spec_edit') and self.rife_thread_spec_edit is not None:
                    try:
                        thread_spec = self.rife_thread_spec_edit.text()
                    except (RuntimeError, AttributeError):
                        LOGGER.warning("Could not access thread_spec_edit text")
                
                if thread_spec and not re.fullmatch(r"\d+:\d+:\d+", thread_spec):
                    thread_spec_valid = False
        except Exception as e:
            LOGGER.warning(f"Error checking thread spec: {e}")
            if is_rife:
                thread_spec_valid = False

        # Safely check other conditions needed for start button
        try:
            # Explicit boolean calculation for can_start
            has_in_dir: bool = self.in_dir is not None and self.in_dir.is_dir()
            has_out_file: bool = self.out_file_path is not None
            is_idle: bool = not getattr(self, 'is_processing', True)  # Default to True (processing) if attribute missing
            
            # Explicitly define can_start as bool
            can_start: bool = (
                has_in_dir
                and has_out_file
                and rife_model_selected
                and thread_spec_valid
                and is_idle
            )
            
            # Safely enable/disable button
            if hasattr(self, 'start_button') and self.start_button is not None:
                try:
                    self.start_button.setEnabled(can_start)
                except (RuntimeError, AttributeError):
                    LOGGER.warning("Could not set start button enabled state")
        except Exception as e:
            LOGGER.warning(f"Error in final start button state calculation: {e}")

    def _set_processing_state(self, processing: bool) -> None:
        """Sets the processing state and updates UI elements accordingly."""
        self.is_processing = processing
        self.start_button.setEnabled(
            not processing
            and self.in_dir is not None
            and self.out_file_path is not None
        )
        self.in_dir_edit.setEnabled(not processing)
        self.out_file_edit.setEnabled(not processing)
        self.crop_button.setEnabled(not processing)
        self.clear_crop_button.setEnabled(
            not processing and self.current_crop_rect is not None
        )
        self.tab_widget.setEnabled(not processing)  # Disable tabs during processing
        self.open_in_vlc_button.setVisible(False)  # Hide VLC button while processing

        # Update progress bar visibility
        self.progress_bar.setVisible(processing)
        if not processing:
            self.progress_bar.setValue(0)  # Reset progress bar on finish/error

    def _update_crop_buttons_state(self) -> None:
        """Updates the enabled state of the crop and clear crop buttons."""
        has_in_dir = self.in_dir is not None and self.in_dir.is_dir()
        self.crop_button.setEnabled(has_in_dir and not self.is_processing)
        self.clear_crop_button.setEnabled(
            self.current_crop_rect is not None and not self.is_processing
        )

    def _update_rife_options_state(self, encoder_type: str) -> None:
        """Updates the visibility and enabled state of RIFE-specific options."""
        is_rife = encoder_type == "RIFE"

        # Toggle visibility of RIFE options group
        rife_options_parent = self.rife_options_layout.parentWidget()
        if rife_options_parent is not None: # Check if parent exists
            rife_options_parent.setVisible(is_rife)
            
    def _update_scd_thresh_state(self, scd_mode: str) -> None:
        """Updates the enabled state of the SCD threshold control based on the selected SCD mode."""
        # Enable SCD threshold only when SCD mode is not 'none'
        self.ffmpeg_scd_threshold_spinbox.setEnabled(scd_mode != "none")
        
    def _update_unsharp_controls_state(self, enabled: bool) -> None:
        """Updates the enabled state of the unsharp mask controls based on whether the group is checked."""
        # These controls should be enabled only when the unsharp group is checked
        if hasattr(self, "ffmpeg_unsharp_lx_spinbox"):
            self.ffmpeg_unsharp_lx_spinbox.setEnabled(enabled)
        if hasattr(self, "ffmpeg_unsharp_ly_spinbox"):
            self.ffmpeg_unsharp_ly_spinbox.setEnabled(enabled)
        if hasattr(self, "ffmpeg_unsharp_la_spinbox"):
            self.ffmpeg_unsharp_la_spinbox.setEnabled(enabled)
        if hasattr(self, "ffmpeg_unsharp_cx_spinbox"):
            self.ffmpeg_unsharp_cx_spinbox.setEnabled(enabled)
        if hasattr(self, "ffmpeg_unsharp_cy_spinbox"):
            self.ffmpeg_unsharp_cy_spinbox.setEnabled(enabled)
        if hasattr(self, "ffmpeg_unsharp_ca_spinbox"):
            self.ffmpeg_unsharp_ca_spinbox.setEnabled(enabled)
            
    def _update_quality_controls_state(self, preset_text: str) -> None:
        """Updates the state of quality controls based on the selected preset."""
        is_custom = preset_text == "Custom (CRF/Bitrate)"
        
        # Enable manual controls only in custom mode
        if hasattr(self, "ffmpeg_crf_spinbox"):
            self.ffmpeg_crf_spinbox.setEnabled(is_custom)
        if hasattr(self, "ffmpeg_bitrate_spinbox"):
            self.ffmpeg_bitrate_spinbox.setEnabled(is_custom)
        if hasattr(self, "ffmpeg_bufsize_spinbox"):
            self.ffmpeg_bufsize_spinbox.setEnabled(is_custom)
            
        # If not custom, set suitable values based on the preset
        if not is_custom and "CRF" in preset_text:
            try:
                # Extract CRF value from preset text (e.g., "Very High (CRF 16)" -> 16)
                crf_value = int(preset_text.split("CRF")[1].strip().split(")")[0])
                if hasattr(self, "ffmpeg_crf_spinbox"):
                    self.ffmpeg_crf_spinbox.setValue(crf_value)
                    
                # Set reasonable bitrate/bufsize based on quality level
                if "Very High" in preset_text:
                    bitrate = 15000
                elif "High" in preset_text:
                    bitrate = 10000
                elif "Medium" in preset_text:
                    bitrate = 5000
                else:  # Low
                    bitrate = 2500
                    
                if hasattr(self, "ffmpeg_bitrate_spinbox"):
                    self.ffmpeg_bitrate_spinbox.setValue(bitrate)
                if hasattr(self, "ffmpeg_bufsize_spinbox"):
                    self.ffmpeg_bufsize_spinbox.setValue(int(bitrate * 1.5))
            except (ValueError, IndexError):
                # If parsing fails, use defaults
                pass

    def _start(self) -> None:
        """Start the video interpolation process."""
        LOGGER.info("Starting video interpolation process...")
        
        # Update UI to processing state
        self._set_processing_state(True)
        
        # Create a worker
        self.vfi_worker = VfiWorker()
        
        # Set worker properties based on UI settings
        self.vfi_worker.in_dir = self.in_dir
        self.vfi_worker.out_file_path = self.out_file_path
        self.vfi_worker.fps = self.fps_spinbox.value()
        self.vfi_worker.mid_count = self.mid_count_spinbox.value()
        self.vfi_worker.max_workers = self.max_workers_spinbox.value()
        self.vfi_worker.crop_rect = self.current_crop_rect  # May be None
        self.vfi_worker.encoder = self.encoder_combo.currentText()
        self.vfi_worker.debug_mode = getattr(self, 'debug_mode', False)
        
        # Set encoder-specific settings
        if self.vfi_worker.encoder == "RIFE":
            # Set RIFE-specific settings
            self.vfi_worker.model_key = self.rife_model_combo.currentText()
            self.vfi_worker.rife_uhd = self.rife_uhd_checkbox.isChecked()
            self.vfi_worker.rife_sc = self.rife_sc_checkbox.isChecked()
            self.vfi_worker.ensemble = self.rife_ensemble_checkbox.isChecked()
            # Get thread spec if provided
            thread_spec = self.rife_thread_spec_edit.text().strip() if hasattr(self, "rife_thread_spec_edit") else None
            if thread_spec:
                self.vfi_worker.thread_spec = thread_spec
        elif self.vfi_worker.encoder == "Sanchez":
            # Set Sanchez-specific settings
            self.vfi_worker.false_colour = self.sanchez_false_colour_checkbox.isChecked()
            self.vfi_worker.res_km = self.sanchez_res_spinbox.value()
        elif self.vfi_worker.encoder == "FFmpeg":
            # Set FFmpeg-specific settings
            self.vfi_worker.mi_mode = self.ffmpeg_mi_mode_combo.currentText()
            self.vfi_worker.mc_mode = self.ffmpeg_mc_mode_combo.currentText()
            self.vfi_worker.me_mode = self.ffmpeg_me_mode_combo.currentText()
            self.vfi_worker.vsbmc = self.ffmpeg_vsbmc_checkbox.isChecked()
            self.vfi_worker.scd_mode = self.ffmpeg_scd_combo.currentText()
            self.vfi_worker.me_algo = self.ffmpeg_me_algo_edit.text()
            self.vfi_worker.search_param = self.ffmpeg_search_param_spinbox.value()
            self.vfi_worker.scd_threshold = self.ffmpeg_scd_threshold_spinbox.value()
            self.vfi_worker.mb_size = self.ffmpeg_mb_size_edit.text()
            
            # Unsharp settings
            self.vfi_worker.apply_unsharp = self.ffmpeg_unsharp_group.isChecked()
            if self.vfi_worker.apply_unsharp:
                self.vfi_worker.unsharp_lx = self.ffmpeg_unsharp_lx_spinbox.value()
                self.vfi_worker.unsharp_ly = self.ffmpeg_unsharp_ly_spinbox.value() if hasattr(self, "ffmpeg_unsharp_ly_spinbox") else 7
                self.vfi_worker.unsharp_la = self.ffmpeg_unsharp_la_spinbox.value() if hasattr(self, "ffmpeg_unsharp_la_spinbox") else 1.0
                self.vfi_worker.unsharp_cx = self.ffmpeg_unsharp_cx_spinbox.value() if hasattr(self, "ffmpeg_unsharp_cx_spinbox") else 7
                self.vfi_worker.unsharp_cy = self.ffmpeg_unsharp_cy_spinbox.value() if hasattr(self, "ffmpeg_unsharp_cy_spinbox") else 7
                self.vfi_worker.unsharp_ca = self.ffmpeg_unsharp_ca_spinbox.value() if hasattr(self, "ffmpeg_unsharp_ca_spinbox") else 0.0
        
        # Connect signals
        self.vfi_worker.progress.connect(self._update_progress)
        self.vfi_worker.finished.connect(self._handle_process_finished)
        self.vfi_worker.error.connect(self._handle_process_error)
        
        # Start worker
        self.vfi_worker.start()
        
    def _update_progress(self, progress_value: int, progress_text: str = "") -> None:
        """Update the progress bar with the current progress value and text."""
        try:
            if 0 <= progress_value <= 100:
                self.progress_bar.setValue(progress_value)
                
            if progress_text:
                self.status_label.setText(progress_text)
                
            # Process Qt events to update the UI
            QApplication.processEvents()
        except Exception as e:
            LOGGER.exception(f"Error updating progress: {e}")
            
    def _handle_process_finished(self, output_path: str) -> None:
        """Handle the successful completion of the video processing."""
        LOGGER.info(f"Process finished successfully. Output file: {output_path}")
        
        # Reset the processing state
        self._set_processing_state(False)
        
        # Update the status
        self.status_label.setText(f"Processing completed successfully!")
        
        # Show the "Open in VLC" button if VLC is available
        if shutil.which("vlc") is not None:
            self.open_in_vlc_button.setVisible(True)
            self.output_path = output_path
        
        # Show a success message
        QMessageBox.information(
            self,
            "Processing Complete",
            f"Video interpolation completed successfully!\n\nOutput saved to:\n{output_path}"
        )
        
    def _handle_process_error(self, error_message: str) -> None:
        """Handle an error during the video processing."""
        LOGGER.error(f"Process error: {error_message}")
        
        # Reset the processing state
        self._set_processing_state(False)
        
        # Update the status with the error message
        self.status_label.setText(f"Error: {error_message}")
        
        # Show an error message box
        QMessageBox.critical(
            self,
            "Processing Error",
            f"An error occurred during video interpolation:\n\n{error_message}"
        )
        # Determine if the current encoder is RIFE
        current_encoder_text = self.encoder_combo.currentText()
        is_rife = current_encoder_text.startswith("RIFE")
        LOGGER.debug(f"Current encoder: {current_encoder_text}, is_rife: {is_rife}")

        model_combo_parent = self.model_combo.parentWidget()
        if model_combo_parent is not None: # Check if parent exists
            model_combo_parent.setVisible(is_rife)  # Label and combo box

        # Update state of RIFE options based on capability
        if is_rife:
            rife_exe = None
            try:
                rife_exe = config.find_rife_executable(self.current_model_key) # Keep this to check for exe existence
                capability_detector = RifeCapabilityManager(model_key=self.current_model_key) # Instantiate with model_key

                self.rife_tile_checkbox.setEnabled(
                    capability_detector.capabilities.get("tiling", False)
                )
                # Tile size enabled state is handled by _toggle_tile_size_enabled signal
                self.rife_uhd_checkbox.setEnabled(capability_detector.capabilities.get("uhd", False))
                self.rife_thread_spec_edit.setEnabled(
                    capability_detector.capabilities.get("thread_spec", False)
                )
                self.rife_tta_spatial_checkbox.setEnabled(
                    capability_detector.capabilities.get("tta_spatial", False)
                )
                self.rife_tta_temporal_checkbox.setEnabled(
                    capability_detector.capabilities.get("tta_temporal", False)
                )

                # Warn if selected model doesn't support features
                if (
                    self.rife_tile_checkbox.isChecked()
                    and not capability_detector.capabilities.get("tiling", False) # Access capability from dict
                ):
                    LOGGER.warning(
                        f"Selected model '{self.current_model_key}' does not support tiling."
                    )
                if (
                    self.rife_uhd_checkbox.isChecked()
                    and not capability_detector.capabilities.get("uhd", False) # Access capability from dict
                ):
                    LOGGER.warning(
                        f"Selected model '{self.current_model_key}' does not support UHD mode."
                    )
                if (
                    self.rife_thread_spec_edit.text() != "1:2:2"
                    and not capability_detector.capabilities.get("thread_spec", False) # Access capability from dict
                ):
                    LOGGER.warning(
                        f"Selected model '{self.current_model_key}' does not support custom thread specification."
                    )
                if (
                    self.rife_tta_spatial_checkbox.isChecked()
                    and not capability_detector.capabilities.get("tta_spatial", False) # Access capability from dict
                ):
                    LOGGER.warning(
                        f"Selected model '{self.current_model_key}' does not support spatial TTA."
                    )
                if (
                    self.rife_tta_temporal_checkbox.isChecked()
                    and not capability_detector.capabilities.get("tta_temporal", False) # Access capability from dict
                ):
                    LOGGER.warning(
                        f"Selected model '{self.current_model_key}' does not support temporal TTA."
                    )

            except FileNotFoundError:
                # If RIFE executable is not found for the selected model, disable all RIFE options
                self.rife_tile_checkbox.setEnabled(False)
                self.rife_tile_size_spinbox.setEnabled(False)
                self.rife_uhd_checkbox.setEnabled(False)
                self.rife_thread_spec_edit.setEnabled(False)
                self.rife_tta_spatial_checkbox.setEnabled(False)
                self.rife_tta_temporal_checkbox.setEnabled(False)
                LOGGER.warning(
                    f"RIFE executable not found for model '{self.current_model_key}'. RIFE options disabled."
                )
            except Exception as e:
                LOGGER.error(
                    f"Error checking RIFE capabilities for model '{self.current_model_key}': {e}"
                )
                # Disable options on error
                self.rife_tile_checkbox.setEnabled(False)
                self.rife_tile_size_spinbox.setEnabled(False)
                self.rife_uhd_checkbox.setEnabled(False)
                self.rife_thread_spec_edit.setEnabled(False)
                self.rife_tta_spatial_checkbox.setEnabled(False)
                self.rife_tta_temporal_checkbox.setEnabled(False)

        self._update_start_button_state()  # Update start button state based on RIFE options
        
    def apply_dark_theme(self) -> None:
        """Apply dark theme styling to the application."""
        self.setStyleSheet("""
            /* Main Window and General Styling */
            QWidget {
                background-color: #2D2D2D;
                color: #EFEFEF;
                font-family: Arial, sans-serif;
            }
            
            /* Tab Widget Styling */
            QTabWidget::pane {
                border: 1px solid #444444;
                background-color: #2D2D2D;
            }
            
            QTabBar::tab {
                background-color: #3D3D3D;
                color: #EFEFEF;
                padding: 8px 12px;
                border: 1px solid #444444;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            
            QTabBar::tab:selected {
                background-color: #505050;
                border-bottom: none;
            }
            
            /* Group Box Styling */
            QGroupBox {
                border: 1px solid #444444;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 1.5ex;
                font-weight: bold;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
            }
            
            /* Input Field Styling */
            QLineEdit {
                background-color: #1A1A1A;
                color: #EFEFEF;
                border: 1px solid #444444;
                padding: 5px;
                border-radius: 3px;
            }
            
            /* Button Styling */
            QPushButton {
                background-color: #424242;
                color: #EFEFEF;
                border: 1px solid #555555;
                padding: 5px 10px;
                border-radius: 3px;
            }
            
            QPushButton:hover {
                background-color: #505050;
            }
            
            QPushButton:pressed {
                background-color: #333333;
            }
            
            /* Browse Buttons */
            QPushButton#browse_button {
                background-color: #4A4A4A;
            }
            
            /* Crop/Clear Buttons */
            QPushButton#crop_button, QPushButton#clear_crop_button {
                padding: 4px 8px;
            }
            
            /* Start Button - Special Styling */
            QPushButton#start_button {
                background-color: #424242;
                font-weight: bold;
                padding: 8px 15px;
            }
            
            /* Combo Box Styling */
            QComboBox {
                background-color: #1A1A1A;
                color: #EFEFEF;
                border: 1px solid #444444;
                padding: 5px;
                border-radius: 3px;
            }
            
            QComboBox:drop-down {
                width: 20px;
                border-left: 1px solid #444444;
            }
            
            QComboBox QAbstractItemView {
                background-color: #1A1A1A;
                color: #EFEFEF;
                selection-background-color: #505050;
            }
            
            /* Spin Box Styling */
            QSpinBox, QDoubleSpinBox {
                background-color: #1A1A1A;
                color: #EFEFEF;
                border: 1px solid #444444;
                padding: 5px;
                border-radius: 3px;
            }
            
            /* Check Box Styling */
            QCheckBox {
                spacing: 5px;
            }
            
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
            }
            
            QCheckBox::indicator:unchecked {
                background-color: #1A1A1A;
                border: 1px solid #444444;
            }
            
            QCheckBox::indicator:checked {
                background-color: #505050;
                border: 1px solid #EFEFEF;
            }
            
            /* Status Bar Styling */
            QStatusBar {
                background-color: #333333;
                color: #EFEFEF;
            }
            
            /* Preview Area Styling */
            QSplitter::handle {
                background-color: #444444;
            }
            
            QLabel#preview_title {
                color: #CCCCCC;
                font-weight: bold;
                font-size: 10pt;
                padding-bottom: 5px;
            }
            
            QLabel#preview_frame {
                background-color: #1A1A1A;
                border: 1px solid #444444;
                border-radius: 3px;
            }
            
            QWidget#preview_container {
                background-color: #2D2D2D;
                padding: 5px;
            }
        """)
        
    def _enhance_preview_area(self) -> QWidget:
        """Create an enhanced preview area with better spacing and styling."""
        # Create a container widget for previews with better styling
        previews_group = QGroupBox("Previews")
        previews_group.setObjectName("previews_group")
        previews_layout = QVBoxLayout(previews_group)
        previews_layout.setContentsMargins(10, 20, 10, 10)  # More top margin for title
        
        # Use QSplitter with custom styling for equal spacing
        preview_splitter = QSplitter(Qt.Orientation.Horizontal)
        preview_splitter.setHandleWidth(4)  # Thinner divider between previews
        preview_splitter.setChildrenCollapsible(False)  # Prevent collapsing
        
        # Create containers for each preview with identical styling
        for title, label_attr in [
            ("First Frame", "first_frame_label"),
            ("Middle Frame (Interpolated)", "middle_frame_label"),
            ("Last Frame", "last_frame_label")
        ]:
            container = QWidget()
            container.setObjectName("preview_container")
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(5, 5, 5, 5)
            
            # Create and style title label
            title_label = QLabel(title)
            title_label.setObjectName("preview_title")
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Get the frame label and set its properties
            frame_label = getattr(self, label_attr)
            frame_label.setObjectName("preview_frame")
            frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            frame_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            frame_label.setMinimumHeight(280)  # Make preview area taller
            
            # Add widgets to container layout
            container_layout.addWidget(title_label)
            container_layout.addWidget(frame_label, 1)  # Add stretch factor
            
            # Add container to splitter
            preview_splitter.addWidget(container)
        
        # Set equal sizes for all preview panels
        preview_splitter.setSizes([1, 1, 1])
        previews_layout.addWidget(preview_splitter)
        
        return previews_group
        
    def _create_processing_settings_group(self) -> QWidget:
        """Create processing settings group with improved layout."""
        processing_group = QGroupBox("Processing Settings")
        processing_layout = QGridLayout(processing_group)
        processing_layout.setContentsMargins(10, 15, 10, 10)  # Adjust internal margins
        processing_layout.setSpacing(8)  # Adjust spacing between elements
        
        # FPS control
        processing_layout.addWidget(QLabel("Output FPS:"), 0, 0)
        self.fps_spinbox = QSpinBox()
        self.fps_spinbox.setRange(1, 240)
        self.fps_spinbox.setValue(30)
        processing_layout.addWidget(self.fps_spinbox, 0, 1)
        
        # Mid frames control
        processing_layout.addWidget(QLabel("Mid Frames per Pair:"), 1, 0)
        self.mid_count_spinbox = QSpinBox()
        self.mid_count_spinbox.setRange(1, 10)
        self.mid_count_spinbox.setValue(1)
        processing_layout.addWidget(self.mid_count_spinbox, 1, 1)
        
        # Max workers control
        processing_layout.addWidget(QLabel("Max Workers:"), 2, 0)
        self.max_workers_spinbox = QSpinBox()
        self.max_workers_spinbox.setRange(1, os.cpu_count() or 1)
        self.max_workers_spinbox.setValue(os.cpu_count() or 1)
        processing_layout.addWidget(self.max_workers_spinbox, 2, 1)
        
        # Encoder selection
        processing_layout.addWidget(QLabel("Encoder:"), 3, 0)
        self.encoder_combo = QComboBox()
        self.encoder_combo.addItems(["RIFE", "FFmpeg", "Sanchez"])
        self.encoder_combo.setCurrentText(self.current_encoder)  # Set initial value
        self.encoder_combo.currentTextChanged.connect(
            self._update_rife_options_state
        )
        processing_layout.addWidget(self.encoder_combo, 3, 1)
        
        # Add extra columns for spacing
        processing_layout.setColumnMinimumWidth(2, 20)  # Add spacer column
        
        return processing_group


def main() -> None:
    """Main function to run the GOES-VFI GUI."""
    parser = argparse.ArgumentParser(description="GOES-VFI GUI")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    args = parser.parse_args()

    # Initialize logging with default settings
    if args.debug:
        log.set_global_log_level(logging.DEBUG)
        LOGGER.debug("Debug mode enabled via --debug flag.")

    app = QApplication(sys.argv)
    # Set application name for QSettings
    app.setApplicationName("GOES-VFI")
    app.setOrganizationName("YourOrganization")  # Replace with your organization name

    main_window = MainWindow(debug_mode=args.debug)
    main_window.show()
    # _post_init_setup() is primarily for test setup, not needed here now
    sys.exit(app.exec())



if __name__ == "__main__":
    main()

