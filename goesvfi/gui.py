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
from goesvfi.gui_tabs.main_tab import MainTab  # <-- Add new tab import
from goesvfi.gui_tabs.ffmpeg_settings_tab import FFmpegSettingsTab # <-- Add new tab import
from goesvfi.gui_tabs.model_library_tab import ModelLibraryTab # <-- Add new tab import


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
from goesvfi.utils.gui_helpers import ClickableLabel, ZoomDialog, CropDialog # Import moved classes
from goesvfi.pipeline.run_vfi import VfiWorker # <-- ADDED IMPORT


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


# Classes ClickableLabel, ZoomDialog, CropDialog moved to goesvfi.utils.gui_helpers


# ────────────────────────────── Worker thread ──────────────────────────────
# VfiWorker class removed, now imported from goesvfi.pipeline.run_vfi

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

# --- Settings ---
        self.settings = QSettings("GoesVFI", "GoesVFI") # Initialize QSettings
        # ----------------
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
        # Instantiate new tab classes, passing necessary arguments (e.g., view models, config)
        # Assuming MainTab needs main_view_model and processing_view_model
        self.main_tab = MainTab(
            main_view_model=self.main_view_model,
            image_loader=self.image_loader,
            sanchez_processor=self.sanchez_processor,
            image_cropper=self.image_cropper,
            settings=self.settings,
            request_previews_update_signal=self.request_previews_update, # Pass the signal
            main_window_ref=self, # Pass the MainWindow instance itself
            parent=self,
        )
# --- Create FFmpeg Widgets (to be passed to FFmpegSettingsTab) ---
        # These widgets are logically part of the FFmpeg settings but need to be owned by MainWindow
        # to be passed correctly during instantiation. FFmpegSettingsTab will then manage their layout.
        self.ffmpeg_settings_group = QGroupBox("FFmpeg Interpolation Settings")
        self.ffmpeg_settings_group.setCheckable(True) # Assuming it should be checkable like in profiles
        self.ffmpeg_unsharp_group = QGroupBox("Unsharp Mask")
        self.ffmpeg_unsharp_group.setCheckable(True)
        self.ffmpeg_quality_group = QGroupBox("Encoding Quality")
        # Profile Combo
        self.ffmpeg_profile_combo = QComboBox()
        self.ffmpeg_profile_combo.addItems(["Custom"] + list(FFMPEG_PROFILES.keys()))
        # Interpolation Widgets
        self.ffmpeg_mi_mode_combo = QComboBox()
        self.ffmpeg_mi_mode_combo.addItems(["dup", "blend", "mci"])
        self.ffmpeg_mc_mode_combo = QComboBox()
        self.ffmpeg_mc_mode_combo.addItems(["obmc", "aobmc"])
        self.ffmpeg_me_mode_combo = QComboBox()
        self.ffmpeg_me_mode_combo.addItems(["bidir", "bilat"])
        self.ffmpeg_vsbmc_checkbox = QCheckBox("VSBMC")
        self.ffmpeg_scd_combo = QComboBox()
        self.ffmpeg_scd_combo.addItems(["none", "fdiff"])
        self.ffmpeg_me_algo_edit = QLineEdit("(default)") # QLineEdit, not combo
        self.ffmpeg_search_param_spinbox = QSpinBox()
        self.ffmpeg_search_param_spinbox.setRange(4, 1024) # Example range
        self.ffmpeg_scd_threshold_spinbox = QDoubleSpinBox()
        self.ffmpeg_scd_threshold_spinbox.setRange(0.0, 100.0)
        self.ffmpeg_scd_threshold_spinbox.setDecimals(1)
        self.ffmpeg_mb_size_edit = QLineEdit("(default)") # QLineEdit, not combo
        # Unsharp Widgets
        self.ffmpeg_unsharp_lx_spinbox = QSpinBox()
        self.ffmpeg_unsharp_lx_spinbox.setRange(3, 63)
        self.ffmpeg_unsharp_ly_spinbox = QSpinBox()
        self.ffmpeg_unsharp_ly_spinbox.setRange(3, 63)
        self.ffmpeg_unsharp_la_spinbox = QDoubleSpinBox()
        self.ffmpeg_unsharp_la_spinbox.setRange(-1.5, 1.5)
        self.ffmpeg_unsharp_la_spinbox.setDecimals(1)
        self.ffmpeg_unsharp_cx_spinbox = QSpinBox()
        self.ffmpeg_unsharp_cx_spinbox.setRange(3, 63)
        self.ffmpeg_unsharp_cy_spinbox = QSpinBox()
        self.ffmpeg_unsharp_cy_spinbox.setRange(3, 63)
        self.ffmpeg_unsharp_ca_spinbox = QDoubleSpinBox()
        self.ffmpeg_unsharp_ca_spinbox.setRange(-1.5, 1.5)
        self.ffmpeg_unsharp_ca_spinbox.setDecimals(1)
        # Quality Widgets
        self.ffmpeg_quality_combo = QComboBox()
        self.ffmpeg_quality_combo.addItems([
            "Very High (CRF 16)", "High (CRF 18)", "Medium (CRF 20)",
            "Low (CRF 23)", "Very Low (CRF 26)", "Custom Quality"
        ])
        self.ffmpeg_crf_spinbox = QSpinBox()
        self.ffmpeg_crf_spinbox.setRange(0, 51)
        self.ffmpeg_bitrate_spinbox = QSpinBox()
        self.ffmpeg_bitrate_spinbox.setRange(100, 100000) # KBit/s
        self.ffmpeg_bitrate_spinbox.setSuffix(" kbit/s")
        self.ffmpeg_bufsize_spinbox = QSpinBox()
        self.ffmpeg_bufsize_spinbox.setRange(150, 150000) # KBit
        self.ffmpeg_bufsize_spinbox.setSuffix(" kbit")
        self.ffmpeg_pix_fmt_combo = QComboBox()
        self.ffmpeg_pix_fmt_combo.addItems(["yuv420p", "yuv444p"]) # Common options
        self.ffmpeg_filter_preset_combo = QComboBox()
        self.ffmpeg_filter_preset_combo.addItems(["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"])
        # -----------------------------------------------------------------
        # Instantiate FFmpegSettingsTab, passing required widgets and signals
        self.ffmpeg_settings_tab: FFmpegSettingsTab # <-- ADDED TYPE HINT
        self.ffmpeg_settings_tab = FFmpegSettingsTab(
            # Pass the widgets created above in MainWindow
            ffmpeg_settings_group=self.ffmpeg_settings_group,
            ffmpeg_unsharp_group=self.ffmpeg_unsharp_group,
            ffmpeg_quality_group=self.ffmpeg_quality_group,
            ffmpeg_profile_combo=self.ffmpeg_profile_combo,
            ffmpeg_mi_mode_combo=self.ffmpeg_mi_mode_combo,
            ffmpeg_mc_mode_combo=self.ffmpeg_mc_mode_combo,
            ffmpeg_me_mode_combo=self.ffmpeg_me_mode_combo,
            ffmpeg_vsbmc_checkbox=self.ffmpeg_vsbmc_checkbox,
            ffmpeg_scd_combo=self.ffmpeg_scd_combo,
            ffmpeg_me_algo_edit=self.ffmpeg_me_algo_edit,
            ffmpeg_search_param_spinbox=self.ffmpeg_search_param_spinbox,
            ffmpeg_scd_threshold_spinbox=self.ffmpeg_scd_threshold_spinbox,
            ffmpeg_mb_size_edit=self.ffmpeg_mb_size_edit,
            ffmpeg_unsharp_lx_spinbox=self.ffmpeg_unsharp_lx_spinbox,
            ffmpeg_unsharp_ly_spinbox=self.ffmpeg_unsharp_ly_spinbox,
            ffmpeg_unsharp_la_spinbox=self.ffmpeg_unsharp_la_spinbox,
            ffmpeg_unsharp_cx_spinbox=self.ffmpeg_unsharp_cx_spinbox,
            ffmpeg_unsharp_cy_spinbox=self.ffmpeg_unsharp_cy_spinbox,
            ffmpeg_unsharp_ca_spinbox=self.ffmpeg_unsharp_ca_spinbox,
            ffmpeg_quality_combo=self.ffmpeg_quality_combo,
            ffmpeg_crf_spinbox=self.ffmpeg_crf_spinbox,
            ffmpeg_bitrate_spinbox=self.ffmpeg_bitrate_spinbox,
            ffmpeg_bufsize_spinbox=self.ffmpeg_bufsize_spinbox,
            ffmpeg_pix_fmt_combo=self.ffmpeg_pix_fmt_combo,
            ffmpeg_filter_preset_combo=self.ffmpeg_filter_preset_combo,
            # Pass widgets from MainTab needed for preview updates
            in_dir_edit=self.main_tab.in_dir_edit,
            mid_count_spinbox=self.main_tab.multiplier_spinbox, # Corrected reference
            encoder_combo=self.main_tab.encoder_combo,
            rife_model_combo=self.main_tab.rife_model_combo,
            sanchez_false_colour_checkbox=self.main_tab.sanchez_false_colour_checkbox,
            sanchez_res_combo=self.main_tab.sanchez_res_combo,
            # Pass the signal
            request_previews_update=self.request_previews_update,
            parent=self
        )
        # Assuming ModelLibraryTab needs main_view_model
        self.model_library_tab = ModelLibraryTab(parent=self)
        # Pass ViewModels to Existing Tabs
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
        # Access main_tab widgets for aliases
        self.model_combo = self.main_tab.rife_model_combo  # Create alias for compatibility
        # self.sanchez_res_km_spinbox = self.sanchez_res_spinbox # Removed old alias
        self.sanchez_res_km_combo = self.main_tab.sanchez_res_combo # Added new alias for ComboBox
        # FFmpeg aliases point to FFmpegSettingsTab widgets (passed during init), not MainTab
        self.ffmpeg_interp_group = self.ffmpeg_settings_group  # Alias points to self
        self.filter_preset_combo = self.ffmpeg_filter_preset_combo  # Alias points to self
        self.mi_mode_combo = self.ffmpeg_mi_mode_combo  # Alias points to self
        self.mc_mode_combo = self.ffmpeg_mc_mode_combo  # Alias points to self
        self.me_mode_combo = self.ffmpeg_me_mode_combo  # Alias points to self
        # These need special handling as they're QLineEdit but referenced as combo boxes
        self.me_algo_combo = self.ffmpeg_me_algo_edit  # Alias points to self
        self.mb_size_combo = self.ffmpeg_mb_size_edit  # Alias points to self

        self.search_param_spinbox = self.ffmpeg_search_param_spinbox  # Alias points to self
        self.scd_mode_combo = self.ffmpeg_scd_combo  # Alias points to self
        self.scd_threshold_spinbox = self.ffmpeg_scd_threshold_spinbox  # Alias points to self
        self.vsbmc_checkbox = self.ffmpeg_vsbmc_checkbox  # Alias points to self
        self.unsharp_group = self.ffmpeg_unsharp_group  # Alias points to self
        self.unsharp_lx_spinbox = self.ffmpeg_unsharp_lx_spinbox  # Alias points to self
        self.unsharp_ly_spinbox = self.ffmpeg_unsharp_ly_spinbox  # Alias points to self
        self.unsharp_la_spinbox = self.ffmpeg_unsharp_la_spinbox  # Alias points to self
        self.unsharp_cx_spinbox = self.ffmpeg_unsharp_cx_spinbox  # Alias points to self
        self.unsharp_cy_spinbox = self.ffmpeg_unsharp_cy_spinbox  # Alias points to self
        self.unsharp_ca_spinbox = self.ffmpeg_unsharp_ca_spinbox  # Alias points to self
        self.crf_spinbox = self.ffmpeg_crf_spinbox  # Alias points to self
        self.bitrate_spinbox = self.ffmpeg_bitrate_spinbox  # Alias points to self
        self.bufsize_spinbox = self.ffmpeg_bufsize_spinbox  # Alias points to self
        self.pix_fmt_combo = self.ffmpeg_pix_fmt_combo  # Alias points to self
        self.profile_combo = self.ffmpeg_profile_combo  # Alias points to self
        
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
        # self._connect_ffmpeg_settings_tab_signals() # Removed - logic moved to FFmpegSettingsTab
        self._connect_model_combo() # Assuming this connects main tab's model combo - verify if moved
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

    # --- State Setters for Child Tabs ---
    def set_in_dir(self, path: Path | None) -> None:
        """Set the input directory state and clear Sanchez cache."""
        if self.in_dir != path:
            LOGGER.debug(f"MainWindow setting in_dir to: {path}")
            self.in_dir = path
            self.sanchez_preview_cache.clear() # Clear cache when dir changes
            # Preview update will be triggered separately by the caller via signal
        self.main_tab._update_crop_buttons_state() # ADDED: Explicitly update crop buttons

    def set_crop_rect(self, rect: tuple[int, int, int, int] | None) -> None:
        """Set the current crop rectangle state."""
        if self.current_crop_rect != rect:
            LOGGER.debug(f"MainWindow setting crop_rect to: {rect}")
            self.current_crop_rect = rect
            # Explicitly trigger preview and button state updates when crop changes
            self.request_previews_update.emit()
            if hasattr(self, 'main_tab') and hasattr(self.main_tab, '_update_crop_buttons_state'):
                 self.main_tab._update_crop_buttons_state()
            else:
                 LOGGER.warning("Could not call main_tab._update_crop_buttons_state() from set_crop_rect")
    # ------------------------------------
    def _set_in_dir_from_sorter(self, directory: Path) -> None:
        LOGGER.debug(f"Entering _set_in_dir_from_sorter... directory={directory}")
        """Sets the input directory from a sorter tab."""
        self.in_dir = directory
        self.main_tab.in_dir_edit.setText(str(directory))
        self._update_start_button_state()
        self.request_previews_update.emit()  # Request preview update

    def _pick_in_dir(self) -> None:
        LOGGER.debug("Entering _pick_in_dir...")
        """Open a directory dialog to select the input image folder."""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Input Image Folder")
        if dir_path:
            LOGGER.debug(f"Input directory selected: {dir_path}")
            self.in_dir = Path(dir_path)
            self.main_tab.in_dir_edit.setText(dir_path)
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
            self.main_tab.out_file_edit.setText(file_path)
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
                    sanchez_preview_enabled = self.main_tab.sanchez_false_colour_checkbox.isChecked()

                    if sanchez_preview_enabled:
                        LOGGER.debug("Sanchez preview enabled. Attempting to get full-res processed_image from first_frame_label.")
                        # Try to get the stored full-res QImage from the label's attribute
                        full_res_image: QImage | None = None
                        if hasattr(self.main_tab, 'first_frame_label') and self.main_tab.first_frame_label is not None:
                            # Retrieve the QImage stored *before* scaling in _load_process_scale_preview
                            full_res_image = getattr(self.main_tab.first_frame_label, 'processed_image', None)

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

    # --- Removed methods previously here ---
    # _makeMainTab
    # _make_ffmpeg_settings_tab
    # _connect_ffmpeg_settings_tab_signals
    # _on_profile_selected
    # _on_ffmpeg_setting_changed
    # _makeModelLibraryTab
    # _populate_model_table
    # _toggle_tile_size_enabled
    # --- Their logic is now encapsulated in the respective tab classes ---

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
            if hasattr(self.main_tab, 'fps_spinbox') and self.main_tab.fps_spinbox is not None:
                # Check if object is valid and is a QSpinBox
                if isinstance(self.main_tab.fps_spinbox, QSpinBox):
                    try:
                        # Try a simple property access to check object validity
                        _ = self.main_tab.fps_spinbox.objectName()

                        fps_value = self.settings.value("fps", 30, type=int)
                        self.main_tab.fps_spinbox.setValue(fps_value)
                        LOGGER.debug(f"Successfully set fps_spinbox value to {fps_value}")
                    except RuntimeError as e:
                        LOGGER.warning(f"RuntimeError setting fps_spinbox value: {e}")
                else:
                    LOGGER.warning(f"fps_spinbox is not a QSpinBox: {type(self.main_tab.fps_spinbox)}")
            elif hasattr(self.main_tab, 'fps_spinbox') and self.main_tab.fps_spinbox is None:
                 LOGGER.warning("fps_spinbox attribute is None")
            else:
                LOGGER.warning("fps_spinbox attribute does not exist")
        except Exception as e:
            LOGGER.error(f"Unhandled exception accessing fps_spinbox: {e}")
    
            
        # For each widget, use separate try blocks to ensure independent error handling
        
        # multiplier_spinbox (was mid_count_spinbox)
        try:
            if hasattr(self.main_tab, "multiplier_spinbox") and self.main_tab.multiplier_spinbox is not None:
                try:
                    # Test widget validity
                    _ = self.main_tab.multiplier_spinbox.objectName()
                    if isinstance(self.main_tab.multiplier_spinbox, QSpinBox):
                        try:
                            # Load setting using "mid_count" key for backward compatibility? Or change key? Assuming key stays "mid_count".
                            value = self.settings.value("mid_count", 1, type=int)
                            # VfiWorker expects num_intermediate_frames (multiplier - 1), but GUI shows multiplier.
                            # Load the multiplier value (setting value + 1)
                            self.main_tab.multiplier_spinbox.setValue(value + 1)
                            LOGGER.debug(f"Set multiplier_spinbox to {value + 1} (loaded mid_count={value})")
                        except RuntimeError as e:
                            LOGGER.warning(f"RuntimeError setting multiplier_spinbox: {e}")
                    else:
                        LOGGER.warning("multiplier_spinbox is not a QSpinBox")
                except RuntimeError:
                    LOGGER.warning("multiplier_spinbox exists but appears to be invalid")
            else:
                LOGGER.warning("multiplier_spinbox not available")
        except Exception as e:
            LOGGER.error(f"Unhandled exception with multiplier_spinbox: {e}")

        # max_workers_spinbox (Commented out as widget doesn't exist on MainTab)
        # try:
        #     if hasattr(self.main_tab, "max_workers_spinbox") and self.main_tab.max_workers_spinbox is not None:
        #         try:
        #             _ = self.main_tab.max_workers_spinbox.objectName()
        #             if isinstance(self.main_tab.max_workers_spinbox, QSpinBox):
        #                 try:
        #                     value = self.settings.value("max_workers", os.cpu_count() or 1, type=int)
        #                     self.main_tab.max_workers_spinbox.setValue(value)
        #                     LOGGER.debug(f"Set max_workers_spinbox to {value}")
        #                 except RuntimeError as e:
        #                     LOGGER.warning(f"RuntimeError setting max_workers_spinbox: {e}")
        #             else:
        #                 LOGGER.warning("max_workers_spinbox is not a QSpinBox")
        #         except RuntimeError:
        #             LOGGER.warning("max_workers_spinbox exists but appears to be invalid")
        #     else:
        #         LOGGER.warning("max_workers_spinbox not available")
        # except Exception as e:
        #     LOGGER.error(f"Unhandled exception with max_workers_spinbox: {e}")
        
        # encoder_combo
        try:
            if hasattr(self.main_tab, "encoder_combo") and self.main_tab.encoder_combo is not None:
                try:
                    _ = self.main_tab.encoder_combo.objectName()
                    try:
                        value = self.settings.value("encoder", "RIFE", type=str)
                        self.main_tab.encoder_combo.setCurrentText(value)
                        self.current_encoder = self.main_tab.encoder_combo.currentText()
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
            # Use alias self.model_combo which now points to self.main_tab.rife_model_combo
            self.model_combo.setCurrentText(
                self.settings.value("rife_model_key", "rife-v4.6", type=str)
            )
            self.current_model_key = self.model_combo.currentText()  # Update state variable using alias
            self.main_tab.rife_tile_checkbox.setChecked(
                self.settings.value("rife_tile_enable", False, type=bool)
            )
            self.main_tab.rife_tile_size_spinbox.setValue(
                self.settings.value("rife_tile_size", 256, type=int)
            )
            self.main_tab.rife_uhd_checkbox.setChecked(
                self.settings.value("rife_uhd_mode", False, type=bool)
            )
            self.main_tab.rife_thread_spec_edit.setText(
                self.settings.value("rife_thread_spec", "1:2:2", type=str)
            )
            self.main_tab.rife_tta_spatial_checkbox.setChecked(
                self.settings.value("rife_tta_spatial", False, type=bool)
            )
            self.main_tab.rife_tta_temporal_checkbox.setChecked(
                self.settings.value("rife_tta_temporal", False, type=bool)
            )
        except RuntimeError as e:
            # Catch Qt widget access errors for RIFE settings
            LOGGER.warning(f"Error accessing RIFE widgets during loadSettings: {e}")

        # Load Sanchez settings
        try:
            self.main_tab.sanchez_false_colour_checkbox.setChecked(
                self.settings.value("sanchez_false_colour", False, type=bool)
            )
            # Use combo box for resolution
            res_km_value = self.settings.value("sanchez_res_km", "4", type=str) # Default to "4" string
            # Use alias self.sanchez_res_km_combo which now points to self.main_tab.sanchez_res_combo
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

        # Load FFmpeg settings (accessing widgets directly from self)
        # Note: Assuming 'use_ffmpeg_interp_checkbox' doesn't exist, using the groupbox check state
        self.ffmpeg_settings_group.setChecked(
            self.settings.value("ffmpeg_use_interp", True, type=bool)
        )
        self.ffmpeg_filter_preset_combo.setCurrentText(
            self.settings.value("ffmpeg_filter_preset", "slow", type=str)
        )
        self.ffmpeg_mi_mode_combo.setCurrentText(
            self.settings.value("ffmpeg_mi_mode", "mci", type=str)
        )
        self.ffmpeg_mc_mode_combo.setCurrentText(
            self.settings.value("ffmpeg_mc_mode", "obmc", type=str)
        )
        self.ffmpeg_me_mode_combo.setCurrentText(
            self.settings.value("ffmpeg_me_mode", "bidir", type=str)
        )
        self.ffmpeg_me_algo_edit.setText( # Use setText for QLineEdit
            self.settings.value("ffmpeg_me_algo", "(default)", type=str)
        )
        self.ffmpeg_search_param_spinbox.setValue(
            self.settings.value("ffmpeg_search_param", 96, type=int)
        )
        self.ffmpeg_scd_combo.setCurrentText(
            self.settings.value("ffmpeg_scd_mode", "fdiff", type=str)
        )
        self.ffmpeg_scd_threshold_spinbox.setValue(
            self.settings.value("ffmpeg_scd_threshold", 10.0, type=float)
        )
        self.ffmpeg_mb_size_edit.setText( # Use setText for QLineEdit
            self.settings.value("ffmpeg_mb_size", "(default)", type=str)
        )
        self.ffmpeg_vsbmc_checkbox.setChecked(
            self.settings.value("ffmpeg_vsbmc", False, type=bool)
        )
        self.ffmpeg_unsharp_group.setChecked(
            self.settings.value("ffmpeg_apply_unsharp", True, type=bool)
        )
        self.ffmpeg_unsharp_lx_spinbox.setValue(
            self.settings.value("ffmpeg_unsharp_lx", 7, type=int)
        )
        self.ffmpeg_unsharp_ly_spinbox.setValue(
            self.settings.value("ffmpeg_unsharp_ly", 7, type=int)
        )
        self.ffmpeg_unsharp_la_spinbox.setValue(
            self.settings.value("ffmpeg_unsharp_la", 1.0, type=float)
        )
        self.ffmpeg_unsharp_cx_spinbox.setValue(
            self.settings.value("ffmpeg_unsharp_cx", 5, type=int)
        )
        self.ffmpeg_unsharp_cy_spinbox.setValue(
            self.settings.value("ffmpeg_unsharp_cy", 5, type=int)
        )
        self.ffmpeg_unsharp_ca_spinbox.setValue(
            self.settings.value("ffmpeg_unsharp_ca", 0.0, type=float)
        )
        self.ffmpeg_crf_spinbox.setValue(self.settings.value("ffmpeg_crf", 16, type=int))
        self.ffmpeg_bitrate_spinbox.setValue(
            self.settings.value("ffmpeg_bitrate", 15000, type=int)
        )
        self.ffmpeg_bufsize_spinbox.setValue(
            self.settings.value("ffmpeg_bufsize", 22500, type=int)
        )
        self.ffmpeg_pix_fmt_combo.setCurrentText(
            self.settings.value("ffmpeg_pix_fmt", "yuv444p", type=str)
        )

        # Update UI elements based on loaded settings
        if self.in_dir:
            self.main_tab.in_dir_edit.setText(str(self.in_dir))
        if self.out_file_path:
            self.main_tab.out_file_edit.setText(str(self.out_file_path))

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
            if hasattr(self.main_tab, "fps_spinbox") and self.main_tab.fps_spinbox is not None and isinstance(self.main_tab.fps_spinbox, QSpinBox):
                self.settings.setValue("fps", self.main_tab.fps_spinbox.value())

            if hasattr(self.main_tab, "mid_count_spinbox") and self.main_tab.mid_count_spinbox is not None:
                self.settings.setValue("mid_count", self.main_tab.mid_count_spinbox.value())

            if hasattr(self.main_tab, "max_workers_spinbox") and self.main_tab.max_workers_spinbox is not None:
                self.settings.setValue("max_workers", self.main_tab.max_workers_spinbox.value())

            if hasattr(self.main_tab, "encoder_combo") and self.main_tab.encoder_combo is not None:
                self.settings.setValue("encoder", self.main_tab.encoder_combo.currentText())

            # Save RIFE v4.6 settings with safety checks
            # Use alias self.model_combo which points to self.main_tab.rife_model_combo
            if hasattr(self, "model_combo") and self.model_combo is not None:
                self.settings.setValue("rife_model_key", self.model_combo.currentText())

            if hasattr(self.main_tab, "rife_tile_checkbox") and self.main_tab.rife_tile_checkbox is not None:
                self.settings.setValue("rife_tile_enable", self.main_tab.rife_tile_checkbox.isChecked())

            if hasattr(self.main_tab, "rife_tile_size_spinbox") and self.main_tab.rife_tile_size_spinbox is not None:
                self.settings.setValue("rife_tile_size", self.main_tab.rife_tile_size_spinbox.value())

            if hasattr(self.main_tab, "rife_uhd_checkbox") and self.main_tab.rife_uhd_checkbox is not None:
                self.settings.setValue("rife_uhd_mode", self.main_tab.rife_uhd_checkbox.isChecked())

            if hasattr(self.main_tab, "rife_thread_spec_edit") and self.main_tab.rife_thread_spec_edit is not None:
                self.settings.setValue("rife_thread_spec", self.main_tab.rife_thread_spec_edit.text())

            if hasattr(self.main_tab, "rife_tta_spatial_checkbox") and self.main_tab.rife_tta_spatial_checkbox is not None:
                self.settings.setValue(
                    "rife_tta_spatial", self.main_tab.rife_tta_spatial_checkbox.isChecked()
                )

            if hasattr(self.main_tab, "rife_tta_temporal_checkbox") and self.main_tab.rife_tta_temporal_checkbox is not None:
                self.settings.setValue(
                    "rife_tta_temporal", self.main_tab.rife_tta_temporal_checkbox.isChecked()
                )
        except RuntimeError as e:
            LOGGER.warning(f"Error saving widget settings: {e}")
            return  # Exit early to avoid further widget access causing errors

        # Save Sanchez settings
        try:
            if hasattr(self.main_tab, "sanchez_false_colour_checkbox") and self.main_tab.sanchez_false_colour_checkbox is not None:
                self.settings.setValue(
                    "sanchez_false_colour", self.main_tab.sanchez_false_colour_checkbox.isChecked()
                )

            # Use the new combo box alias (self.sanchez_res_km_combo points to self.main_tab.sanchez_res_combo)
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

            # Save FFmpeg settings - with safety checks and correct tab access
            if hasattr(self.ffmpeg_settings_tab, "use_ffmpeg_interp_checkbox") and self.ffmpeg_settings_tab.use_ffmpeg_interp_checkbox is not None:
                self.settings.setValue(
                    "ffmpeg_use_interp", self.ffmpeg_settings_tab.use_ffmpeg_interp_checkbox.isChecked()
                )

            if hasattr(self.ffmpeg_settings_tab, "ffmpeg_filter_preset_combo") and self.ffmpeg_settings_tab.ffmpeg_filter_preset_combo is not None:
                self.settings.setValue(
                    "ffmpeg_filter_preset", self.ffmpeg_settings_tab.ffmpeg_filter_preset_combo.currentText()
                )

            if hasattr(self.ffmpeg_settings_tab, "mi_mode_combo") and self.ffmpeg_settings_tab.mi_mode_combo is not None:
                self.settings.setValue("ffmpeg_mi_mode", self.ffmpeg_settings_tab.mi_mode_combo.currentText())

            if hasattr(self.ffmpeg_settings_tab, "mc_mode_combo") and self.ffmpeg_settings_tab.mc_mode_combo is not None:
                self.settings.setValue("ffmpeg_mc_mode", self.ffmpeg_settings_tab.mc_mode_combo.currentText())

            if hasattr(self.ffmpeg_settings_tab, "me_mode_combo") and self.ffmpeg_settings_tab.me_mode_combo is not None:
                self.settings.setValue("ffmpeg_me_mode", self.ffmpeg_settings_tab.me_mode_combo.currentText())

            if hasattr(self.ffmpeg_settings_tab, "me_algo_combo") and self.ffmpeg_settings_tab.me_algo_combo is not None:
                self.settings.setValue("ffmpeg_me_algo", self.ffmpeg_settings_tab.me_algo_combo.currentText()) # Use currentText for combo

            if hasattr(self.ffmpeg_settings_tab, "search_param_spinbox") and self.ffmpeg_settings_tab.search_param_spinbox is not None:
                self.settings.setValue("ffmpeg_search_param", self.ffmpeg_settings_tab.search_param_spinbox.value())

            if hasattr(self.ffmpeg_settings_tab, "scd_combo") and self.ffmpeg_settings_tab.scd_combo is not None: # Renamed from scd_mode_combo
                self.settings.setValue("ffmpeg_scd_mode", self.ffmpeg_settings_tab.scd_combo.currentText())

            if hasattr(self.ffmpeg_settings_tab, "scd_threshold_spinbox") and self.ffmpeg_settings_tab.scd_threshold_spinbox is not None:
                self.settings.setValue(
                    "ffmpeg_scd_threshold", self.ffmpeg_settings_tab.scd_threshold_spinbox.value()
                )

            if hasattr(self.ffmpeg_settings_tab, "mb_size_combo") and self.ffmpeg_settings_tab.mb_size_combo is not None:
                self.settings.setValue("ffmpeg_mb_size", self.ffmpeg_settings_tab.mb_size_combo.currentText()) # Use currentText for combo

            if hasattr(self.ffmpeg_settings_tab, "vsbmc_checkbox") and self.ffmpeg_settings_tab.vsbmc_checkbox is not None:
                self.settings.setValue("ffmpeg_vsbmc", self.ffmpeg_settings_tab.vsbmc_checkbox.isChecked())

            if hasattr(self.ffmpeg_settings_tab, "unsharp_group") and self.ffmpeg_settings_tab.unsharp_group is not None:
                self.settings.setValue("ffmpeg_apply_unsharp", self.ffmpeg_settings_tab.unsharp_group.isChecked())

            if hasattr(self.ffmpeg_settings_tab, "unsharp_lx_spinbox") and self.ffmpeg_settings_tab.unsharp_lx_spinbox is not None:
                self.settings.setValue("ffmpeg_unsharp_lx", self.ffmpeg_settings_tab.unsharp_lx_spinbox.value())

            if hasattr(self.ffmpeg_settings_tab, "unsharp_ly_spinbox") and self.ffmpeg_settings_tab.unsharp_ly_spinbox is not None:
                self.settings.setValue("ffmpeg_unsharp_ly", self.ffmpeg_settings_tab.unsharp_ly_spinbox.value())

            if hasattr(self.ffmpeg_settings_tab, "unsharp_la_spinbox") and self.ffmpeg_settings_tab.unsharp_la_spinbox is not None:
                self.settings.setValue("ffmpeg_unsharp_la", self.ffmpeg_settings_tab.unsharp_la_spinbox.value())

            if hasattr(self.ffmpeg_settings_tab, "unsharp_cx_spinbox") and self.ffmpeg_settings_tab.unsharp_cx_spinbox is not None:
                self.settings.setValue("ffmpeg_unsharp_cx", self.ffmpeg_settings_tab.unsharp_cx_spinbox.value())

            if hasattr(self.ffmpeg_settings_tab, "unsharp_cy_spinbox") and self.ffmpeg_settings_tab.unsharp_cy_spinbox is not None:
                self.settings.setValue("ffmpeg_unsharp_cy", self.ffmpeg_settings_tab.unsharp_cy_spinbox.value())

            if hasattr(self.ffmpeg_settings_tab, "unsharp_ca_spinbox") and self.ffmpeg_settings_tab.unsharp_ca_spinbox is not None:
                self.settings.setValue("ffmpeg_ca", self.ffmpeg_settings_tab.unsharp_ca_spinbox.value()) # Key was ffmpeg_ca, corrected

            if hasattr(self.ffmpeg_settings_tab, "crf_spinbox") and self.ffmpeg_settings_tab.crf_spinbox is not None:
                self.settings.setValue("ffmpeg_crf", self.ffmpeg_settings_tab.crf_spinbox.value())

            if hasattr(self.ffmpeg_settings_tab, "bitrate_spinbox") and self.ffmpeg_settings_tab.bitrate_spinbox is not None:
                self.settings.setValue("ffmpeg_bitrate", self.ffmpeg_settings_tab.bitrate_spinbox.value())

            if hasattr(self.ffmpeg_settings_tab, "bufsize_spinbox") and self.ffmpeg_settings_tab.bufsize_spinbox is not None:
                self.settings.setValue("ffmpeg_bufsize", self.ffmpeg_settings_tab.bufsize_spinbox.value())

            if hasattr(self.ffmpeg_settings_tab, "pix_fmt_combo") and self.ffmpeg_settings_tab.pix_fmt_combo is not None:
                self.settings.setValue("ffmpeg_pix_fmt", self.ffmpeg_settings_tab.pix_fmt_combo.currentText())

    def _validate_thread_spec(self, text: str) -> None:
        LOGGER.debug(f"Entering _validate_thread_spec... text={text}")
        """Validate the RIFE thread specification format."""
        # Simple regex check for format like "1:2:2"
        if not re.fullmatch(r"\d+:\d+:\d+", text):
            self.main_tab.rife_thread_spec_edit.setStyleSheet("color: red;")
            self.main_tab.start_button.setEnabled(False)  # Disable start button if invalid
            LOGGER.warning(f"Invalid RIFE thread specification format: {text}")
        else:
            self.main_tab.rife_thread_spec_edit.setStyleSheet("")  # Reset style
            self._update_start_button_state()  # Re-check start button state

    def _populate_models(self) -> None:
        LOGGER.debug("Entering _populate_models...")
        """Populate the RIFE model combo box."""
        available_models = config.get_available_rife_models() # Use correct function name
        # Use alias self.model_combo which points to self.main_tab.rife_model_combo
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
            )  # Update state variable using alias
        else:
            self.model_combo.addItem("No RIFE models found")
            self.model_combo.setEnabled(False)
            self.current_model_key = ""  # Clear state variable
            LOGGER.warning("No RIFE models found.")

    def _toggle_sanchez_res_enabled(self, state: Qt.CheckState) -> None:
        """Enables or disables the Sanchez resolution combo box based on the checkbox state."""
        # Use the combo box alias defined in __init__
        self.sanchez_res_km_combo.setEnabled(state == Qt.CheckState.Checked.value)

    def _update_rife_ui_elements(self) -> None:
        LOGGER.debug("Entering _update_rife_ui_elements...")
        """Updates the visibility and state of RIFE-specific UI elements."""
        is_rife = self.current_encoder == "RIFE"

        # Toggle visibility of RIFE options group
        # Access group via main_tab
        rife_options_parent = self.main_tab.rife_options_group.parentWidget() # Use group
        if rife_options_parent is not None: # Check if parent exists
            rife_options_parent.setVisible(is_rife)
        # Use alias self.model_combo which points to self.main_tab.rife_model_combo
        model_combo_parent = self.model_combo.parentWidget()
        if model_combo_parent is not None: # Check if parent exists
            model_combo_parent.setVisible(is_rife)  # Label and combo box

        # Update state of RIFE options based on capability
        if is_rife:
            rife_exe = None
            try:
                rife_exe = config.find_rife_executable(self.current_model_key) # Keep this to check for exe existence
                capability_detector = RifeCapabilityManager(model_key=self.current_model_key) # Instantiate with model_key

                self.main_tab.rife_tile_checkbox.setEnabled(
                    capability_detector.capabilities.get("tiling", False)
                )
                # Tile size enabled state is handled by _toggle_tile_size_enabled signal in MainTab
                self.main_tab.rife_uhd_checkbox.setEnabled(capability_detector.capabilities.get("uhd", False))
                self.main_tab.rife_thread_spec_edit.setEnabled(
                    capability_detector.capabilities.get("thread_spec", False)
                )
                self.main_tab.rife_tta_spatial_checkbox.setEnabled(
                    capability_detector.capabilities.get("tta_spatial", False)
                )
                self.main_tab.rife_tta_temporal_checkbox.setEnabled(
                    capability_detector.capabilities.get("tta_temporal", False)
                )

                # Warn if selected model doesn't support features
                if (
                    self.main_tab.rife_tile_checkbox.isChecked()
                    and not capability_detector.capabilities.get("tiling", False) # Access capability from dict
                ):
                    LOGGER.warning(
                        f"Selected model '{self.current_model_key}' does not support tiling."
                    )
                if (
                    self.main_tab.rife_uhd_checkbox.isChecked()
                    and not capability_detector.capabilities.get("uhd", False) # Access capability from dict
                ):
                    LOGGER.warning(
                        f"Selected model '{self.current_model_key}' does not support UHD mode."
                    )
                if (
                    self.main_tab.rife_thread_spec_edit.text() != "1:2:2"
                    and not capability_detector.capabilities.get("thread_spec", False) # Access capability from dict
                ):
                    LOGGER.warning(
                        f"Selected model '{self.current_model_key}' does not support custom thread specification."
                    )
                if (
                    self.main_tab.rife_tta_spatial_checkbox.isChecked()
                    and not capability_detector.capabilities.get("tta_spatial", False) # Access capability from dict
                ):
                    LOGGER.warning(
                        f"Selected model '{self.current_model_key}' does not support spatial TTA."
                    )
                if (
                    self.main_tab.rife_tta_temporal_checkbox.isChecked()
                    and not capability_detector.capabilities.get("tta_temporal", False) # Access capability from dict
                 ):
                    LOGGER.warning(
                        f"Selected model '{self.current_model_key}' does not support temporal TTA."
                    )

            except FileNotFoundError:
                # If RIFE executable is not found for the selected model, disable all RIFE options
                self.main_tab.rife_tile_checkbox.setEnabled(False)
                self.main_tab.rife_tile_size_spinbox.setEnabled(False)
                self.main_tab.rife_uhd_checkbox.setEnabled(False)
                self.main_tab.rife_thread_spec_edit.setEnabled(False)
                self.main_tab.rife_tta_spatial_checkbox.setEnabled(False)
                self.main_tab.rife_tta_temporal_checkbox.setEnabled(False)
                LOGGER.warning(
                    f"RIFE executable not found for model '{self.current_model_key}'. RIFE options disabled."
                )
            except Exception as e:
                LOGGER.error(
                    f"Error checking RIFE capabilities for model '{self.current_model_key}': {e}"
                )
                # Disable options on error
                self.main_tab.rife_tile_checkbox.setEnabled(False)
                self.main_tab.rife_tile_size_spinbox.setEnabled(False)
                self.main_tab.rife_uhd_checkbox.setEnabled(False)
                self.main_tab.rife_thread_spec_edit.setEnabled(False)
                self.main_tab.rife_tta_spatial_checkbox.setEnabled(False)
                self.main_tab.rife_tta_temporal_checkbox.setEnabled(False)

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
        apply_sanchez: bool, # Renamed from sanchez_enabled for clarity
        crop_rect: Optional[Tuple[int, int, int, int]],
    ) -> QPixmap | None:
        """Loads, processes (crop/sanchez), scales, and returns a preview pixmap
        using the provided ImageProcessor instances. Handles Sanchez caching.
        """
        target_label.file_path = None # Clear previous path
        target_label.processed_image = None # Clear previous full-res image
        processed_qimage: QImage | None = None # To store the full-res processed image
        sanchez_processing_failed = False # Flag to indicate Sanchez processing failure
        sanchez_error_message = ""
        image_data_to_process: ImageData | None = None # Store loaded/cached data
        using_cache = False # Flag to indicate if cache was used

        try:
            # 1. Load Original or Get from Cache (if Sanchez enabled)
            # -------------------------------------------------------
            if apply_sanchez:
                if image_path in self.sanchez_preview_cache:
                    LOGGER.debug(f"Using cached Sanchez result for {image_path.name}")
                    cached_array = self.sanchez_preview_cache[image_path]
                    # Create ImageData manually from cached numpy array
                    # Assume original metadata isn't critical for preview display after Sanchez
                    image_data_to_process = ImageData(image_data=cached_array, metadata={'source_path': image_path, 'cached': True})
                    using_cache = True
                else:
                    LOGGER.debug(f"No cached Sanchez result for {image_path.name}, processing...")
                    original_image_data = None
                    try:
                        # Load original first
                        original_image_data = image_loader.load(str(image_path))
                        if original_image_data and original_image_data.image_data is not None:
                             # Read resolution from ComboBox
                            res_km_str = "4"
                            if hasattr(self, 'sanchez_res_km_combo') and self.sanchez_res_km_combo is not None:
                                try: res_km_str = self.sanchez_res_km_combo.currentText()
                                except (RuntimeError, AttributeError) as e: LOGGER.warning(f"Could not get Sanchez resolution value: {e}")
                            else: LOGGER.warning("Sanchez resolution ComboBox not found")
                            try: res_km_val = float(res_km_str)
                            except ValueError: res_km_val = 4.0

                            LOGGER.debug(f"Applying Sanchez to preview for: {image_path.name} with res_km={res_km_val}")
                            sanchez_kwargs = {'res_km': res_km_val}
                            if 'filename' not in original_image_data.metadata:
                                original_image_data.metadata['filename'] = image_path.name

                            # Run Sanchez Processor
                            sanchez_result = sanchez_processor.process(original_image_data, **sanchez_kwargs)

                            if sanchez_result and sanchez_result.image_data is not None:
                                LOGGER.debug("Sanchez processing completed.")
                                # Cache the result (as NumPy array)
                                result_array: Optional[np.ndarray[Any, np.dtype[np.uint8]]] = None
                                if isinstance(sanchez_result.image_data, Image.Image):
                                    result_array = np.array(sanchez_result.image_data)
                                elif isinstance(sanchez_result.image_data, np.ndarray):
                                    result_array = sanchez_result.image_data

                                if result_array is not None:
                                    self.sanchez_preview_cache[image_path] = result_array.copy()
                                    LOGGER.debug(f"Stored Sanchez result in cache for: {image_path.name}")
                                    image_data_to_process = sanchez_result # Use the successful result
                                else:
                                    LOGGER.warning("Sanchez processed data was not in expected format (PIL/NumPy) for caching.")
                                    sanchez_processing_failed = True # Treat as failure if format wrong
                                    sanchez_error_message = "Invalid output format"
                                    image_data_to_process = original_image_data # Fallback
                            else:
                                LOGGER.warning(f"Sanchez processing returned no data for {image_path.name}")
                                sanchez_processing_failed = True
                                sanchez_error_message = "Processing returned None"
                                image_data_to_process = original_image_data # Fallback
                        else:
                             LOGGER.warning(f"Failed to load original image for Sanchez: {image_path.name}")
                             sanchez_processing_failed = True # Treat as failure if load fails
                             sanchez_error_message = "Load failed"
                             # image_data_to_process remains None here

                    except Exception as e_sanchez:
                        LOGGER.exception(f"Error during Sanchez processing for {image_path.name}: {e_sanchez}")
                        sanchez_processing_failed = True
                        sanchez_error_message = str(e_sanchez)
                        # Use original data if loaded, otherwise it remains None
                        image_data_to_process = original_image_data if original_image_data else None

            else: # Sanchez not enabled
                try:
                    image_data_to_process = image_loader.load(str(image_path))
                except Exception as e_load:
                     LOGGER.exception(f"Error loading image when Sanchez disabled: {e_load}")
                     return None # Cannot proceed if basic load fails

            # Check if we have any image data at all
            if image_data_to_process is None or image_data_to_process.image_data is None:
                LOGGER.warning(f"Failed to load or process image: {image_path}")
                return None

            # 2. Convert Initial Data to NumPy Array (for consistency)
            # -------------------------------------------------------
            initial_img_array: Optional[np.ndarray[Any, np.dtype[np.uint8]]] = None
            if isinstance(image_data_to_process.image_data, Image.Image):
                initial_img_array = np.array(image_data_to_process.image_data)
            elif isinstance(image_data_to_process.image_data, np.ndarray):
                initial_img_array = image_data_to_process.image_data
            else:
                LOGGER.error(f"Unsupported initial image data type: {type(image_data_to_process.image_data)}")
                return None

            # 3. Convert to QImage (Full Resolution, Uncropped) and Store for Dialogs
            # ----------------------------------------------------------------------
            full_res_qimage: Optional[QImage] = None
            try:
                height, width, channel = initial_img_array.shape
                bytes_per_line = channel * width
                if channel == 4: format = QImage.Format.Format_RGBA8888
                elif channel == 3: format = QImage.Format.Format_RGB888
                elif channel == 1:
                    format = QImage.Format.Format_Grayscale8
                    bytes_per_line = width
                else: raise ValueError(f"Unsupported number of channels: {channel}")
                contiguous_img_array = np.ascontiguousarray(initial_img_array)
                full_res_qimage = QImage(
                    contiguous_img_array.data, width, height, bytes_per_line, format
                ).copy()
                target_label.processed_image = full_res_qimage.copy() # Store for dialogs
                target_label.file_path = str(image_path) # Store path too
                LOGGER.debug("Stored full-res, uncropped, potentially Sanchez'd QImage in label.")
            except Exception as conversion_err:
                LOGGER.exception(f"Failed converting initial NumPy array to QImage: {conversion_err}")
                return None # Cannot proceed if initial conversion fails

            # 4. Crop (if requested) - Operates on the NumPy array
            # ----------------------------------------------------
            final_img_array = initial_img_array # Start with the potentially Sanchez'd array
            LOGGER.debug(f"PRE-CROP Check: crop_rect={crop_rect}, initial_img_array shape={initial_img_array.shape if initial_img_array is not None else 'None'}") # DEBUG LOG
            if crop_rect:
                LOGGER.debug(f"INSIDE CROP BLOCK: Applying crop {crop_rect} to preview for {image_path.name}") # DEBUG LOG
                try:
                    # Create a temporary ImageData for cropping API
                    LOGGER.debug(f"BEFORE CROP: initial_img_array shape={initial_img_array.shape if initial_img_array is not None else 'None'}") # DEBUG LOG
                    temp_image_data_for_crop = ImageData(image_data=initial_img_array, metadata=image_data_to_process.metadata)
                    x, y, w, h = crop_rect
                    crop_rect_pil = (x, y, x + w, y + h)
                    cropped_image_data = image_cropper.crop(temp_image_data_for_crop, crop_rect_pil)

                    # Extract NumPy array from cropped result
                    if cropped_image_data and cropped_image_data.image_data is not None:
                        if isinstance(cropped_image_data.image_data, Image.Image):
                            final_img_array = np.array(cropped_image_data.image_data)
                        elif isinstance(cropped_image_data.image_data, np.ndarray):
                            final_img_array = cropped_image_data.image_data
                        LOGGER.debug(f"AFTER CROP (Success): final_img_array shape={final_img_array.shape if final_img_array is not None else 'None'}") # DEBUG LOG
                    else:
                         LOGGER.warning("Cropping returned no data, using uncropped image.")
                         LOGGER.debug(f"AFTER CROP (No Data): final_img_array shape={final_img_array.shape if final_img_array is not None else 'None'}") # DEBUG LOG (still uncropped)
                except Exception as e_crop:
                    LOGGER.exception(f"Error during crop processing for preview {image_path.name}: {e_crop}")
                    LOGGER.debug(f"AFTER CROP (Exception): final_img_array shape={final_img_array.shape if final_img_array is not None else 'None'}") # DEBUG LOG (still uncropped)
                    # If cropping fails, final_img_array remains the uncropped version

            # 5. Convert Final (potentially cropped) NumPy Array to QImage
            # ------------------------------------------------------------
            final_q_image: Optional[QImage] = None
            try:
                height, width, channel = final_img_array.shape
                bytes_per_line = channel * width
                if channel == 4: format = QImage.Format.Format_RGBA8888
                elif channel == 3: format = QImage.Format.Format_RGB888
                elif channel == 1:
                    format = QImage.Format.Format_Grayscale8
                    bytes_per_line = width
                else: raise ValueError(f"Unsupported number of channels: {channel}")
                contiguous_img_array = np.ascontiguousarray(final_img_array)
                final_q_image = QImage(
                    contiguous_img_array.data, width, height, bytes_per_line, format
                ).copy()
                LOGGER.debug("Successfully converted final (potentially cropped) NumPy array to QImage")
            except Exception as conversion_err:
                LOGGER.exception(f"Failed converting final NumPy array to QImage: {conversion_err}")
                # If final conversion fails, maybe try using the uncropped full_res_qimage?
                # For now, let's return None to indicate failure.
                return None

            # 6. Scale the Final QImage for Preview Display
            # ---------------------------------------------
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

            # 7. Create QPixmap and Add Sanchez Warning if Needed
            # ---------------------------------------------------
            pixmap = QPixmap.fromImage(scaled_img)
            LOGGER.debug("QPixmap created successfully")

            draw_sanchez_warning = False
            # Only show warning if Sanchez was requested AND failed
            if apply_sanchez and sanchez_processing_failed:
                 # Double-check checkbox state in case user toggled it off during processing
                 sanchez_still_checked = False
                 if hasattr(self.main_tab, 'sanchez_false_colour_checkbox') and self.main_tab.sanchez_false_colour_checkbox is not None:
                     try:
                         sanchez_still_checked = self.main_tab.sanchez_false_colour_checkbox.isChecked()
                     except (RuntimeError, AttributeError): pass # Ignore if checkbox gone
                 if sanchez_still_checked:
                     draw_sanchez_warning = True

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
                # Ensure label state is cleared on error
                if hasattr(target_label, 'file_path'): target_label.file_path = None
                if hasattr(target_label, 'processed_image'): target_label.processed_image = None
            except (RuntimeError, AttributeError): pass
            return None

    def _clear_preview_labels(self, message: str = "First Frame") -> None:
        """Helper method to clear all preview labels safely."""
        try:
            # Clear first frame
            if hasattr(self.main_tab, 'first_frame_label') and self.main_tab.first_frame_label is not None:
                try:
                    self.main_tab.first_frame_label.clear()
                    self.main_tab.first_frame_label.setText(message)
                    self.main_tab.first_frame_label.file_path = None
                    self.main_tab.first_frame_label.processed_image = None
                except (RuntimeError, AttributeError) as e:
                    LOGGER.warning(f"Error clearing first frame label: {e}")

            # Clear middle frame
            if hasattr(self.main_tab, 'middle_frame_label') and self.main_tab.middle_frame_label is not None:
                try:
                    self.main_tab.middle_frame_label.clear()
                    self.main_tab.middle_frame_label.setText("Middle Frame")
                    self.main_tab.middle_frame_label.file_path = None
                    self.main_tab.middle_frame_label.processed_image = None
                except (RuntimeError, AttributeError) as e:
                    LOGGER.warning(f"Error clearing middle frame label: {e}")

            # Clear last frame
            if hasattr(self.main_tab, 'last_frame_label') and self.main_tab.last_frame_label is not None:
                try:
                    self.main_tab.last_frame_label.clear()
                    self.main_tab.last_frame_label.setText("Last Frame")
                    self.main_tab.last_frame_label.file_path = None
                    self.main_tab.last_frame_label.processed_image = None
                except (RuntimeError, AttributeError) as e:
                    LOGGER.warning(f"Error clearing last frame label: {e}")
                    
        except Exception as e:
            LOGGER.warning(f"Error in _clear_preview_labels: {e}")
    
    def _update_previews(self) -> None:
        LOGGER.debug(f"Entering _update_previews. Current crop_rect: {self.current_crop_rect}, Sanchez enabled: {self.main_tab.sanchez_false_colour_checkbox.isChecked()}")
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
                    self.main_tab.first_frame_label,
                    self.image_loader,
                    self.sanchez_processor,
                    self.image_cropper,
                    # Pass the required arguments
                    apply_sanchez=self.main_tab.sanchez_false_colour_checkbox.isChecked(),
                    crop_rect=self.current_crop_rect,
                )
                if first_pixmap:
                    try:
                        self.main_tab.first_frame_label.setPixmap(first_pixmap)
                        LOGGER.debug("Successfully set first frame preview")
                    except (RuntimeError, AttributeError) as e:
                        LOGGER.error(f"Error setting first frame pixmap: {e}")
                else:
                    LOGGER.warning("First frame preview generation failed")
                    try:
                        self.main_tab.first_frame_label.clear()
                        self.main_tab.first_frame_label.setText("Error loading preview")
                        self.main_tab.first_frame_label.file_path = None
                        self.main_tab.first_frame_label.processed_image = None
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
                        self.main_tab.middle_frame_label,
                        self.image_loader,
                        self.sanchez_processor,
                        self.image_cropper,
                        # Pass the required arguments
                        apply_sanchez=self.main_tab.sanchez_false_colour_checkbox.isChecked(),
                        crop_rect=self.current_crop_rect,
                    )
                    if middle_pixmap:
                        try:
                            self.main_tab.middle_frame_label.setPixmap(middle_pixmap)
                            LOGGER.debug("Successfully set middle frame preview")
                        except (RuntimeError, AttributeError) as e:
                            LOGGER.error(f"Error setting middle frame pixmap: {e}")
                    else:
                        LOGGER.warning("Middle frame preview generation failed")
                        try:
                            self.main_tab.middle_frame_label.clear()
                            self.main_tab.middle_frame_label.setText("Error loading preview")
                            self.main_tab.middle_frame_label.file_path = None
                            self.main_tab.middle_frame_label.processed_image = None
                        except (RuntimeError, AttributeError) as e:
                            LOGGER.error(f"Error clearing middle frame: {e}")
                except Exception as e:
                    LOGGER.error(f"Error processing middle frame preview: {e}")
            else:
                try:
                    LOGGER.debug("No middle frame available")
                    self.main_tab.middle_frame_label.clear()
                    self.main_tab.middle_frame_label.setText("Middle Frame (N/A)")
                    self.main_tab.middle_frame_label.file_path = None
                    self.main_tab.middle_frame_label.processed_image = None
                except (RuntimeError, AttributeError) as e:
                    LOGGER.error(f"Error clearing middle frame: {e}")

            # Process last frame
            try:
                LOGGER.debug(f"Loading last frame preview: {last_frame_path.name}")
                last_pixmap = self._load_process_scale_preview(
                    last_frame_path,
                    self.main_tab.last_frame_label,
                    self.image_loader,
                    self.sanchez_processor,
                    self.image_cropper,
                    # Pass the required arguments
                    apply_sanchez=self.main_tab.sanchez_false_colour_checkbox.isChecked(),
                    crop_rect=self.current_crop_rect,
                )
                if last_pixmap:
                    try:
                        self.main_tab.last_frame_label.setPixmap(last_pixmap)
                        LOGGER.debug("Successfully set last frame preview")
                    except (RuntimeError, AttributeError) as e:
                        LOGGER.error(f"Error setting last frame pixmap: {e}")
                else:
                    LOGGER.warning("Last frame preview generation failed")
                    try:
                        self.main_tab.last_frame_label.clear()
                        self.main_tab.last_frame_label.setText("Error loading preview")
                        self.main_tab.last_frame_label.file_path = None
                        self.main_tab.last_frame_label.processed_image = None
                    except (RuntimeError, AttributeError) as e:
                        LOGGER.error(f"Error clearing last frame: {e}")
            except Exception as e:
                LOGGER.error(f"Error processing last frame preview: {e}")

# Update crop button state after previews are handled
            self.main_tab._update_crop_buttons_state()
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
                if hasattr(self.main_tab, 'rife_thread_spec_edit') and self.main_tab.rife_thread_spec_edit is not None:
                    try:
                        thread_spec = self.main_tab.rife_thread_spec_edit.text()
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
            if hasattr(self.main_tab, 'start_button') and self.main_tab.start_button is not None:
                try:
                    self.main_tab.start_button.setEnabled(can_start)
                except (RuntimeError, AttributeError):
                    LOGGER.warning("Could not set start button enabled state")
        except Exception as e:
            LOGGER.warning(f"Error in final start button state calculation: {e}")

    def _set_processing_state(self, processing: bool) -> None:
        """Sets the processing state and updates UI elements accordingly."""
        self.is_processing = processing
        self.main_tab.start_button.setEnabled(
            not processing
            and self.in_dir is not None
            and self.out_file_path is not None
        )
        self.main_tab.in_dir_edit.setEnabled(not processing)
        self.main_tab.out_file_edit.setEnabled(not processing)
        self.main_tab.crop_button.setEnabled(not processing)
        self.main_tab.clear_crop_button.setEnabled(
            not processing and self.current_crop_rect is not None
        )
        self.tab_widget.setEnabled(not processing)  # Disable tabs during processing
        # self.main_tab.open_in_vlc_button.setVisible(False)  # Commented out: Attribute does not exist on MainTab

        # Update progress bar visibility
        # self.main_tab.progress_bar.setVisible(processing) # Commented out: Attribute does not exist on MainTab
        if not processing:
            # self.main_tab.progress_bar.setValue(0)  # Commented out: Attribute does not exist on MainTab
            pass # Add pass to avoid indentation error

    def _update_crop_buttons_state(self) -> None:
        """Updates the enabled state of the crop and clear crop buttons."""
        has_in_dir = self.in_dir is not None and self.in_dir.is_dir()
        self.main_tab.crop_button.setEnabled(has_in_dir and not self.is_processing)
        self.main_tab.clear_crop_button.setEnabled(
            self.current_crop_rect is not None and not self.is_processing
        )

    def _update_rife_options_state(self, encoder_type: str) -> None:
        """Updates the visibility and enabled state of RIFE-specific options."""
        is_rife = encoder_type == "RIFE"

        # Toggle visibility of RIFE options group
        rife_options_parent = self.main_tab.rife_options_group.parentWidget() # Use group
        if rife_options_parent is not None: # Check if parent exists
            rife_options_parent.setVisible(is_rife)
            
    def _update_scd_thresh_state(self, scd_mode: str) -> None:
        """Updates the enabled state of the SCD threshold control based on the selected SCD mode."""
        # Enable SCD threshold only when SCD mode is not 'none'
        self.ffmpeg_settings_tab.ffmpeg_scd_threshold_spinbox.setEnabled(scd_mode != "none")
        
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
        LOGGER.debug("Entering _start...")
        if not self.in_dir or not self.out_file_path:
            LOGGER.warning("Input directory or output file not set. Cannot start.")
            self._set_processing_state(False) # Ensure UI is re-enabled
            return

        # Update UI to processing state
        self._set_processing_state(True)

        # --- Gather arguments for VfiWorker ---
        try:
            # Basic args
            in_dir = self.in_dir
            out_file_path = self.out_file_path
            fps = self.main_tab.fps_spinbox.value()
            # VfiWorker expects num_intermediate_frames, which is multiplier - 1
            mid_count = self.main_tab.multiplier_spinbox.value() - 1
            max_workers = os.cpu_count() or 1
            encoder = self.main_tab.encoder_combo.currentText()

            # FFmpeg settings (Access widgets directly from self)
            use_ffmpeg_interp = self.ffmpeg_settings_group.isChecked() # Use groupbox state
            filter_preset = self.ffmpeg_filter_preset_combo.currentText()
            mi_mode = self.ffmpeg_mi_mode_combo.currentText()
            mc_mode = self.ffmpeg_mc_mode_combo.currentText()
            me_mode = self.ffmpeg_me_mode_combo.currentText()
            me_algo = self.ffmpeg_me_algo_edit.text() # Use .text() for QLineEdit
            search_param = self.ffmpeg_search_param_spinbox.value()
            scd_mode = self.ffmpeg_scd_combo.currentText()
            # scd_threshold is only relevant if scd_mode is not 'none'
            scd_threshold = self.ffmpeg_scd_threshold_spinbox.value() if scd_mode != "none" else None

            # minter_mb_size needs parsing from QLineEdit text
            mb_size_text = self.ffmpeg_mb_size_edit.text() # Use .text() for QLineEdit
            minter_mb_size = int(mb_size_text) if mb_size_text.isdigit() else None

            minter_vsbmc = 1 if self.ffmpeg_vsbmc_checkbox.isChecked() else 0

            # Unsharp settings
            apply_unsharp = self.ffmpeg_unsharp_group.isChecked()
            unsharp_lx = self.ffmpeg_unsharp_lx_spinbox.value()
            unsharp_ly = self.ffmpeg_unsharp_ly_spinbox.value()
            unsharp_la = self.ffmpeg_unsharp_la_spinbox.value()
            unsharp_cx = self.ffmpeg_unsharp_cx_spinbox.value()
            unsharp_cy = self.ffmpeg_unsharp_cy_spinbox.value()
            unsharp_ca = self.ffmpeg_unsharp_ca_spinbox.value()

            # Quality settings
            crf = self.ffmpeg_crf_spinbox.value()
            bitrate_kbps = self.ffmpeg_bitrate_spinbox.value()
            bufsize_kb = self.ffmpeg_bufsize_spinbox.value()
            pix_fmt = self.ffmpeg_pix_fmt_combo.currentText()

            # Other args
            # skip_model corresponds to 'Keep Intermediate Files' checkbox in MainTab
            # skip_model = self.main_tab.keep_temps_checkbox.isChecked() # Removed: Checkbox doesn't exist
            skip_model = False # Default to not keeping intermediate files
            crop_rect = self.current_crop_rect
            debug_mode = self.debug_mode

            # RIFE settings
            rife_tile_enable = self.main_tab.rife_tile_checkbox.isChecked()
            rife_tile_size = self.main_tab.rife_tile_size_spinbox.value()
            rife_uhd_mode = self.main_tab.rife_uhd_checkbox.isChecked()
            rife_thread_spec = self.main_tab.rife_thread_spec_edit.text()
            rife_tta_spatial = self.main_tab.rife_tta_spatial_checkbox.isChecked()
            rife_tta_temporal = self.main_tab.rife_tta_temporal_checkbox.isChecked()
            # Get model key from MainTab's stored value
            model_key = self.main_tab.current_model_key
            if not model_key: # Add a fallback just in case
                 model_key = self.main_tab.rife_model_combo.currentText().split('(')[-1].strip(') ')
                 LOGGER.warning(f"MainTab current_model_key was empty, using fallback from text: {model_key}")


            # Sanchez settings
            false_colour = self.main_tab.sanchez_false_colour_checkbox.isChecked()
            res_km = int(float(self.main_tab.sanchez_res_combo.currentText()))

            # Sanchez temp dir
            sanchez_gui_temp_dir = self._sanchez_gui_temp_dir

        except Exception as e:
            LOGGER.exception("Error gathering arguments for VfiWorker:")
            QMessageBox.critical(self, "Error", f"Failed to gather processing settings: {e}")
            self._set_processing_state(False) # Ensure UI is re-enabled on error
            return

        # --- Instantiate and run VfiWorker ---
        self.vfi_worker = VfiWorker(
            in_dir=in_dir,
            out_file_path=out_file_path,
            fps=fps,
            mid_count=mid_count,
            max_workers=max_workers,
            encoder=encoder,
            # FFmpeg settings
            use_preset_optimal=False, # This seems unused in VfiWorker.__init__ now
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
            # Unsharp settings
            apply_unsharp=apply_unsharp,
            unsharp_lx=unsharp_lx,
            unsharp_ly=unsharp_ly,
            unsharp_la=unsharp_la,
            unsharp_cx=unsharp_cx,
            unsharp_cy=unsharp_cy,
            unsharp_ca=unsharp_ca,
            # Quality settings
            crf=crf,
            bitrate_kbps=bitrate_kbps,
            bufsize_kb=bufsize_kb,
            pix_fmt=pix_fmt,
            # Other args
            skip_model=skip_model,
            crop_rect=crop_rect,
            debug_mode=debug_mode,
            # RIFE settings
            rife_tile_enable=rife_tile_enable,
            rife_tile_size=rife_tile_size,
            rife_uhd_mode=rife_uhd_mode,
            rife_thread_spec=rife_thread_spec,
            rife_tta_spatial=rife_tta_spatial,
            rife_tta_temporal=rife_tta_temporal,
            model_key=model_key,
            # Sanchez settings
            false_colour=false_colour,
            res_km=res_km,
            # Sanchez temp dir
            sanchez_gui_temp_dir=sanchez_gui_temp_dir,
        )

        self.vfi_worker.progress.connect(self._update_progress)
        self.vfi_worker.finished.connect(self._handle_process_finished)
        self.vfi_worker.error.connect(self._handle_process_error)

        # Start the worker thread
        LOGGER.info("Starting VFI worker thread...")
        self.vfi_worker.start()
        LOGGER.debug("VFI worker thread started.")

        # Update status bar (already done by _set_processing_state)
        # self.status_bar.showMessage("Processing started...")

    def _update_progress(self, current: int, total: int, eta: float) -> None:
        """Update the status bar with the current progress."""
        try:
            if total > 0:
                percent = int((current / total) * 100)
                eta_str = f"{eta:.1f}s" if eta > 0 else "..."
                status_text = f"Processing: {current}/{total} ({percent}%) ETA: {eta_str}"
                self.status_bar.showMessage(status_text)
            else:
                # Handle case where total is 0 or unknown
                self.status_bar.showMessage(f"Processing frame {current}...")
            QApplication.processEvents() # Keep UI responsive
        except Exception as e:
            LOGGER.error(f"Error updating status bar: {e}", exc_info=True)
            self.status_bar.showMessage("Error updating progress...")

    def _handle_process_finished(self, output_path: Path) -> None: # Changed type hint
        """Handle the process finished signal."""
        output_path_str = str(output_path)
        LOGGER.info(f"Process finished successfully. Output: {output_path_str}")
        self._set_processing_state(False)
        self.status_bar.showMessage(f"Finished: {output_path_str}", 10000) # Show for 10s
        # self.main_tab.open_in_vlc_button.setVisible(False) # Button removed/logic changed
        self.vfi_worker = None # Clear worker reference

        # Ask user if they want to open the file location
        reply = QMessageBox.question(
            self,
            "Process Finished",
            f"Video saved to:\n{output_path_str}\n\nOpen the file location?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Use QUrl.fromLocalFile for cross-platform compatibility
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_path.parent)))


    def _handle_process_error(self, error_message: str) -> None:
        """Handle the process error signal."""
        LOGGER.error(f"Process failed: {error_message}")
        self._set_processing_state(False)
        self.status_bar.showMessage(f"Error: {error_message}", 0) # Show indefinitely until cleared
        self.vfi_worker = None # Clear worker reference

        # --- Detailed Error Reporting ---
        details = f"An error occurred during video processing:\n\n{error_message}\n\n"
        # Show an error message box
        QMessageBox.critical(
            self,
            "Processing Error",
            details # Show the detailed message
        )
        # Determine if the current encoder is RIFE
        current_encoder_text = self.main_tab.encoder_combo.currentText()
        is_rife = current_encoder_text.startswith("RIFE")
        LOGGER.debug(f"Current encoder: {current_encoder_text}, is_rife: {is_rife}")

        # Use alias self.model_combo which points to self.main_tab.rife_model_combo
        model_combo_parent = self.model_combo.parentWidget()
        if model_combo_parent is not None: # Check if parent exists
            model_combo_parent.setVisible(is_rife)  # Label and combo box

        # Update state of RIFE options based on capability
        if is_rife:
            rife_exe = None
            try:
                rife_exe = config.find_rife_executable(self.current_model_key) # Keep this to check for exe existence
                capability_detector = RifeCapabilityManager(model_key=self.current_model_key) # Instantiate with model_key

                self.main_tab.rife_tile_checkbox.setEnabled(
                    capability_detector.capabilities.get("tiling", False)
                )
                # Tile size enabled state is handled by _toggle_tile_size_enabled signal in MainTab
                self.main_tab.rife_uhd_checkbox.setEnabled(capability_detector.capabilities.get("uhd", False))
                self.main_tab.rife_thread_spec_edit.setEnabled(
                    capability_detector.capabilities.get("thread_spec", False)
                )
                self.main_tab.rife_tta_spatial_checkbox.setEnabled(
                    capability_detector.capabilities.get("tta_spatial", False)
                )
                self.main_tab.rife_tta_temporal_checkbox.setEnabled(
                    capability_detector.capabilities.get("tta_temporal", False)
                )

                # Warn if selected model doesn't support features
                if (
                    self.main_tab.rife_tile_checkbox.isChecked()
                    and not capability_detector.capabilities.get("tiling", False) # Access capability from dict
                ):
                    LOGGER.warning(
                        f"Selected model '{self.current_model_key}' does not support tiling."
                    )
                if (
                    self.main_tab.rife_uhd_checkbox.isChecked()
                    and not capability_detector.capabilities.get("uhd", False) # Access capability from dict
                ):
                    LOGGER.warning(
                        f"Selected model '{self.current_model_key}' does not support UHD mode."
                    )
                if (
                    self.main_tab.rife_thread_spec_edit.text() != "1:2:2"
                    and not capability_detector.capabilities.get("thread_spec", False) # Access capability from dict
                ):
                    LOGGER.warning(
                        f"Selected model '{self.current_model_key}' does not support custom thread specification."
                    )
                if (
                    self.main_tab.rife_tta_spatial_checkbox.isChecked()
                    and not capability_detector.capabilities.get("tta_spatial", False) # Access capability from dict
                ):
                    LOGGER.warning(
                        f"Selected model '{self.current_model_key}' does not support spatial TTA."
                    )
                if (
                    self.main_tab.rife_tta_temporal_checkbox.isChecked()
                    and not capability_detector.capabilities.get("tta_temporal", False) # Access capability from dict
                ):
                    LOGGER.warning(
                        f"Selected model '{self.current_model_key}' does not support temporal TTA."
                    )

            except FileNotFoundError:
                # If RIFE executable is not found for the selected model, disable all RIFE options
                self.main_tab.rife_tile_checkbox.setEnabled(False)
                self.main_tab.rife_tile_size_spinbox.setEnabled(False)
                self.main_tab.rife_uhd_checkbox.setEnabled(False)
                self.main_tab.rife_thread_spec_edit.setEnabled(False)
                self.main_tab.rife_tta_spatial_checkbox.setEnabled(False)
                self.main_tab.rife_tta_temporal_checkbox.setEnabled(False)
                LOGGER.warning(
                    f"RIFE executable not found for model '{self.current_model_key}'. RIFE options disabled."
                )
            except Exception as e:
                LOGGER.error(
                    f"Error checking RIFE capabilities for model '{self.current_model_key}': {e}"
                )
                # Disable options on error
                self.main_tab.rife_tile_checkbox.setEnabled(False)
                self.main_tab.rife_tile_size_spinbox.setEnabled(False)
                self.main_tab.rife_uhd_checkbox.setEnabled(False)
                self.main_tab.rife_thread_spec_edit.setEnabled(False)
                self.main_tab.rife_tta_spatial_checkbox.setEnabled(False)
                self.main_tab.rife_tta_temporal_checkbox.setEnabled(False)

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
            # Access labels via main_tab
            frame_label = getattr(self.main_tab, label_attr)
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
        # Assign to main_tab attribute
        self.main_tab.fps_spinbox = QSpinBox()
        self.main_tab.fps_spinbox.setRange(1, 240)
        self.main_tab.fps_spinbox.setValue(30)
        processing_layout.addWidget(self.main_tab.fps_spinbox, 0, 1)

        # Mid frames control
        processing_layout.addWidget(QLabel("Mid Frames per Pair:"), 1, 0)
        # Assign to main_tab attribute
        self.main_tab.mid_count_spinbox = QSpinBox()
        self.main_tab.mid_count_spinbox.setRange(1, 10)
        self.main_tab.mid_count_spinbox.setValue(1)
        processing_layout.addWidget(self.main_tab.mid_count_spinbox, 1, 1)

        # Max workers control
        processing_layout.addWidget(QLabel("Max Workers:"), 2, 0)
        # Assign to main_tab attribute
        self.main_tab.max_workers_spinbox = QSpinBox()
        self.main_tab.max_workers_spinbox.setRange(1, os.cpu_count() or 1)
        self.main_tab.max_workers_spinbox.setValue(os.cpu_count() or 1)
        processing_layout.addWidget(self.main_tab.max_workers_spinbox, 2, 1)

        # Encoder selection
        processing_layout.addWidget(QLabel("Encoder:"), 3, 0)
        # Assign to main_tab attribute
        self.main_tab.encoder_combo = QComboBox()
        self.main_tab.encoder_combo.addItems(["RIFE", "FFmpeg", "Sanchez"])
        self.main_tab.encoder_combo.setCurrentText(self.current_encoder)  # Set initial value
        self.main_tab.encoder_combo.currentTextChanged.connect(
            self._update_rife_options_state # This method now accesses main_tab widgets
        )
        processing_layout.addWidget(self.main_tab.encoder_combo, 3, 1)
        
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

