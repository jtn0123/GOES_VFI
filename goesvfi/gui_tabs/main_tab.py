# goesvfi/gui_tabs/main_tab.py

import logging
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, cast, TypedDict, Dict, List, Optional, Set, TYPE_CHECKING # Add TypedDict, Dict, List, Optional, Set

if TYPE_CHECKING:
    from typing import NotRequired # Use NotRequired for optional keys in TypedDict (Python 3.11+)
    # If using Python < 3.11, use total=False in TypedDict definition instead
from enum import Enum # Add this import

import numpy as np
from PIL import Image # Add PIL Image import
from PyQt6.QtGui import QImage # Add QImage import
from goesvfi.utils import config # Import config
# RIFEModelDetails is defined locally below, remove incorrect import
from goesvfi.pipeline.image_processing_interfaces import ImageData # Add ImageData import
from PyQt6.QtCore import QSettings, Qt, QTimer, pyqtSignal, pyqtSlot, QRect, QObject # Add QObject
from PyQt6.QtGui import QColor, QImage, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

# Define Enums for interpolation and raw encoding methods
class InterpolationMethod(Enum):
    NONE = "None"
    RIFE = "RIFE"
    FFMPEG = "FFmpeg"

class RawEncoderMethod(Enum):
    NONE = "None"
    RIFE = "RIFE"
    SANCHEZ = "Sanchez"

# Remove incorrect import from ffmpeg_builder
# from goesvfi.pipeline.ffmpeg_builder import (
#     FFmpegParams,
#     QualityParams,
#     UnsharpParams,
# )
from goesvfi.pipeline.image_cropper import ImageCropper
from goesvfi.pipeline.image_loader import ImageLoader
from goesvfi.pipeline.run_vfi import VfiWorker
from goesvfi.pipeline.sanchez_processor import SanchezProcessor
from goesvfi.utils.config import FFMPEG_PROFILES
from goesvfi.utils.gui_helpers import ClickableLabel, CropDialog, ZoomDialog, ImageViewerDialog, CropSelectionDialog # Import moved classes AND ImageViewerDialog AND CropSelectionDialog
from goesvfi.utils.log import get_logger # Use get_logger
LOGGER = get_logger(__name__) # Get logger instance
from goesvfi.utils.config import get_available_rife_models, get_cache_dir # Import from config
from goesvfi.utils.rife_analyzer import analyze_rife_executable # Import analyzer function
from goesvfi.view_models.main_window_view_model import MainWindowViewModel
from goesvfi.view_models.processing_view_model import ProcessingViewModel
from goesvfi.pipeline.image_processing_interfaces import ImageData # Import ImageData


# Define RIFEModelDetails TypedDict locally
class RIFEModelDetails(TypedDict, total=False): # Use total=False for compatibility < 3.11
    version: Optional[str]
    capabilities: Dict[str, bool]
    supported_args: List[str]
    help_text: Optional[str]
    _mtime: float # Add _mtime used for caching


# Helper function (to be added inside MainTab or globally in the file)
def numpy_to_qimage(array: np.ndarray) -> QImage:
    """Converts a NumPy array (H, W, C) in RGB format to QImage."""
    if array is None or array.size == 0:
        return QImage()
    try:
        height, width, channel = array.shape
        if channel == 3: # RGB
            bytes_per_line = 3 * width
            image_format = QImage.Format.Format_RGB888
            # Create QImage from buffer protocol. Make a copy to be safe.
            qimage = QImage(array.data, width, height, bytes_per_line, image_format).copy()
        elif channel == 4: # RGBA?
             bytes_per_line = 4 * width
             image_format = QImage.Format.Format_RGBA8888
             qimage = QImage(array.data, width, height, bytes_per_line, image_format).copy()
        elif channel == 1 or len(array.shape) == 2: # Grayscale
             height, width = array.shape[:2]
             bytes_per_line = width
             image_format = QImage.Format.Format_Grayscale8
             # Ensure array is contiguous C-style for grayscale
             gray_array = np.ascontiguousarray(array.squeeze())
             qimage = QImage(gray_array.data, width, height, bytes_per_line, image_format).copy()
        else:
             LOGGER.error(f"Unsupported NumPy array shape for QImage conversion: {array.shape}")
             return QImage()

        if qimage.isNull():
             LOGGER.error("Failed to create QImage from NumPy array (check format/data).")
             return QImage()
        return qimage
    except Exception as e:
        LOGGER.exception(f"Error converting NumPy array to QImage: {e}")
        return QImage()


class MainTab(QWidget):
    """Encapsulates the UI and logic for the main processing tab."""

    # Signal emitted when processing starts
    processing_started = pyqtSignal(dict, name="processingStarted")
    # Signal emitted when processing finishes (success or failure)
    processing_finished = pyqtSignal(bool, str, name="processingFinished")


# --- UI Elements (Declared for type hinting, assigned in MainWindow._create_processing_settings_group) ---
    # Note: These widgets are created and assigned *by* MainWindow, not within MainTab itself.
    # Declaring them here helps mypy understand the attributes exist on the instance.
    fps_spinbox: QSpinBox
    mid_count_spinbox: QSpinBox # Corrected name based on MainWindow usage
    max_workers_spinbox: QSpinBox
    encoder_combo: QComboBox
    # Add other widgets created in MainWindow._create_processing_settings_group if needed
    # --- End UI Element Declarations ---
    def __init__(
        self,
        main_view_model: MainWindowViewModel,
        image_loader: ImageLoader,
        sanchez_processor: SanchezProcessor,
        image_cropper: ImageCropper,
        settings: QSettings,
        request_previews_update_signal: Any, # Accept MainWindow's signal (bound signal)
        main_window_ref: Any, # Add reference to MainWindow
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.main_view_model = main_view_model
        self.processing_vm = main_view_model.processing_vm # Convenience access
        self.image_loader = image_loader
        self.sanchez_processor = sanchez_processor
        self.image_cropper = image_cropper
        self.settings = settings
        self.main_window_preview_signal = request_previews_update_signal # Store the signal
        self.main_window_ref = main_window_ref # Store the MainWindow reference

        # --- State Variables ---
        # self.in_dir and self.current_crop_rect removed, managed by MainWindow
        self.out_file_path: Path | None = None # Keep output path state local
        self.vfi_worker: VfiWorker | None = None
        self.is_processing = False
        self.current_encoder = "RIFE"  # Default encoder
        self.current_model_key: str | None = "rife-v4.6"  # Default RIFE model key
        self.available_models: Dict[str, RIFEModelDetails] = {} # Use Dict
        self.image_viewer_dialog: Optional[ImageViewerDialog] = None # Add member to hold viewer reference
        # -----------------------

        self._setup_ui()
        self._connect_signals()
        self._post_init_setup() # Perform initial state updates

    def _setup_ui(self) -> None:
        """Create the UI elements for the main tab."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)  # Adjust margins
        layout.setSpacing(10)  # Adjust spacing between major groups

        # Input/Output Group
        io_group = QGroupBox("Input/Output")
        io_layout = QGridLayout(io_group)
        io_layout.setContentsMargins(10, 15, 10, 10)
        io_layout.setSpacing(8)

        # Input directory row (Layout for LineEdit and Button)
        in_dir_layout = QHBoxLayout()
        self.in_dir_edit = QLineEdit()
        self.in_dir_edit.setPlaceholderText("Select input image folder...")
        self.in_dir_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        in_dir_button = QPushButton("Browse...")
        in_dir_button.setObjectName("browse_button")
        in_dir_layout.addWidget(self.in_dir_edit)
        in_dir_layout.addWidget(in_dir_button)
        # Connect button click here for clarity
        in_dir_button.clicked.connect(self._pick_in_dir)

        io_layout.addWidget(QLabel("Input Directory:"), 0, 0)
        io_layout.addLayout(in_dir_layout, 0, 1, 1, 2) # Span layout across 2 columns

        # Output file row (Layout for LineEdit and Button)
        out_file_layout = QHBoxLayout()
        self.out_file_edit = QLineEdit()
        self.out_file_edit.setPlaceholderText("Select output MP4 file...")
        self.out_file_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        out_file_button = QPushButton("Browse...")
        out_file_button.setObjectName("browse_button")
        out_file_layout.addWidget(self.out_file_edit)
        out_file_layout.addWidget(out_file_button)
        # Connect button click here
        out_file_button.clicked.connect(self._pick_out_file)

        io_layout.addWidget(QLabel("Output File (MP4):"), 1, 0)
        io_layout.addLayout(out_file_layout, 1, 1, 1, 2) # Span layout across 2 columns


        # Preview Area
        self.first_frame_label = ClickableLabel()
        self.middle_frame_label = ClickableLabel()
        self.last_frame_label = ClickableLabel()
        previews_group = self._enhance_preview_area() # Calls helper to setup layout

        # Crop Buttons
        crop_buttons_layout = QHBoxLayout()
        crop_buttons_layout.setContentsMargins(10, 0, 10, 0)
        self.crop_button = QPushButton("Select Crop Region")
        self.crop_button.setObjectName("crop_button")
        self.clear_crop_button = QPushButton("Clear Crop")
        self.clear_crop_button.setObjectName("clear_crop_button")
        crop_buttons_layout.addWidget(self.crop_button)
        crop_buttons_layout.addWidget(self.clear_crop_button)
        crop_buttons_layout.addStretch(1)

        # Sanchez Preview Checkbox (Moved here)
        sanchez_preview_layout = QHBoxLayout()
        sanchez_preview_layout.setContentsMargins(10, 5, 10, 0) # Add some top margin
        self.sanchez_false_colour_checkbox = QCheckBox("Enable Sanchez/False Color Preview")
        self.sanchez_false_colour_checkbox.setChecked(False)
        self.sanchez_false_colour_checkbox.setToolTip("Show previews processed with Sanchez false color.")
        sanchez_preview_layout.addWidget(self.sanchez_false_colour_checkbox)
        sanchez_preview_layout.addStretch(1)


        # Processing Settings Group
        processing_group = self._create_processing_settings_group() # Calls helper

        # RIFE Options Group
        self.rife_options_group = QGroupBox("RIFE Options")
        self.rife_options_group.setCheckable(False)
        rife_layout = QGridLayout(self.rife_options_group)
        rife_layout.addWidget(QLabel("RIFE Model:"), 0, 0)
        self.rife_model_combo = QComboBox()
        rife_layout.addWidget(self.rife_model_combo, 0, 1)
        self.rife_tile_checkbox = QCheckBox("Enable Tiling")
        self.rife_tile_checkbox.setChecked(False)
        rife_layout.addWidget(self.rife_tile_checkbox, 1, 0)
        self.rife_tile_size_spinbox = QSpinBox()
        self.rife_tile_size_spinbox.setRange(32, 1024)
        self.rife_tile_size_spinbox.setValue(256)
        self.rife_tile_size_spinbox.setEnabled(False)
        rife_layout.addWidget(self.rife_tile_size_spinbox, 1, 1)
        self.tile_size_spinbox = self.rife_tile_size_spinbox # Alias
        self.rife_uhd_checkbox = QCheckBox("UHD Mode")
        self.rife_uhd_checkbox.setChecked(False)
        rife_layout.addWidget(self.rife_uhd_checkbox, 2, 0, 1, 2)
        rife_layout.addWidget(QLabel("Thread Spec:"), 3, 0)
        self.rife_thread_spec_edit = QLineEdit()
        self.rife_thread_spec_edit.setPlaceholderText("e.g., 1:2:2, 2:2:1")
        self.rife_thread_spec_edit.setToolTip("Specify thread distribution (encoder:decoder:processor)")
        rife_layout.addWidget(self.rife_thread_spec_edit, 3, 1)
        self.rife_tta_spatial_checkbox = QCheckBox("TTA Spatial")
        self.rife_tta_spatial_checkbox.setChecked(False)
        rife_layout.addWidget(self.rife_tta_spatial_checkbox, 4, 0, 1, 2)
        self.rife_tta_temporal_checkbox = QCheckBox("TTA Temporal")
        self.rife_tta_temporal_checkbox.setChecked(False)
        rife_layout.addWidget(self.rife_tta_temporal_checkbox, 5, 0, 1, 2)

        # Sanchez Options Group
        self.sanchez_options_group = QGroupBox("Sanchez Options")
        self.sanchez_options_group.setCheckable(False)
        sanchez_layout = QGridLayout(self.sanchez_options_group)
        # False colour checkbox moved near previews
        # sanchez_layout.addWidget(self.sanchez_false_colour_checkbox, 0, 0, 1, 2) # REMOVED
        sanchez_layout.addWidget(QLabel("Resolution (km):"), 1, 0) # Adjusted row index if needed (seems okay)
        self.sanchez_res_combo = QComboBox()
        self.sanchez_res_combo.addItems(["0.5", "1", "2", "4"]) # Keep other Sanchez options here
        self.sanchez_res_combo.setCurrentText("4")
        sanchez_layout.addWidget(self.sanchez_res_combo, 1, 1)
        self.sanchez_res_km_combo = self.sanchez_res_combo # Alias

        # Start Button
        self.start_button = QPushButton("Start Video Interpolation")
        self.start_button.setObjectName("start_button")
        self.start_button.setMinimumHeight(40)
        self.start_button.setEnabled(False)

        # Layout Assembly
        settings_layout = QHBoxLayout()
        settings_layout.setSpacing(10)
        processing_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.rife_options_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        settings_layout.addWidget(processing_group, 1)
        settings_layout.addWidget(self.rife_options_group, 1)

        layout.addWidget(io_group)
        layout.addWidget(previews_group, 1)
        layout.addLayout(crop_buttons_layout)
        layout.addLayout(sanchez_preview_layout) # Add Sanchez preview checkbox layout here
        layout.addLayout(settings_layout)
        layout.addWidget(self.sanchez_options_group) # Keep Sanchez options group for other settings
        layout.addWidget(self.start_button)

        # --- Aliases for potential external access or future refactoring ---
        self.model_combo = self.rife_model_combo
        # -------------------------------------------------------------------


    def _connect_signals(self) -> None:
        """Connect signals to slots for the main tab."""
        # IO Controls
        self.in_dir_edit.textChanged.connect(self._on_in_dir_changed)
        # Button connections moved to _setup_ui where buttons are created
        self.out_file_edit.textChanged.connect(self._on_out_file_changed)

        # Preview Controls
        self.first_frame_label.clicked.connect(lambda: self._show_zoom(self.first_frame_label))
        self.middle_frame_label.clicked.connect(lambda: self._show_zoom(self.middle_frame_label))
        self.last_frame_label.clicked.connect(lambda: self._show_zoom(self.last_frame_label))
        self.sanchez_false_colour_checkbox.stateChanged.connect(self.main_window_preview_signal.emit) # Emit MainWindow signal

        # Crop Controls
        self.crop_button.clicked.connect(self._on_crop_clicked)
        self.clear_crop_button.clicked.connect(self._on_clear_crop_clicked)

        # Processing Settings
        self.encoder_combo.currentTextChanged.connect(self._on_encoder_changed)

        # RIFE Options
        self.rife_tile_checkbox.stateChanged.connect(self._toggle_tile_size_enabled)
        self.rife_thread_spec_edit.textChanged.connect(self._validate_thread_spec)
        self._connect_model_combo() # Connect RIFE model combo signals

        # Start Button
        self.start_button.clicked.connect(self._start)

        # Internal preview update signal connection removed


    def _post_init_setup(self) -> None:
        """Perform initial UI state updates after UI creation and signal connection."""
        LOGGER.debug("MainTab: Performing post-init setup...")
        self._populate_models()
        self._update_rife_ui_elements()
        self._update_start_button_state()
        self._update_crop_buttons_state()
        self._update_rife_options_state(self.current_encoder)
        self._update_sanchez_options_state(self.current_encoder)
        # Initial preview load trigger removed, handled by MainWindow
        LOGGER.debug("MainTab: Post-init setup complete.")

    # --- Signal Handlers and UI Update Methods ---

    def _on_in_dir_changed(self, text: str) -> None:
        """Handle changes to the input directory text."""
        # Update MainWindow's in_dir state using the stored reference
        LOGGER.debug(f"Updating MainWindow in_dir via main_window_ref: {text}")
        if hasattr(self.main_window_ref, 'set_in_dir'):
            self.main_window_ref.set_in_dir(Path(text) if text else None)
        else:
             # This case should ideally not happen if main_window_ref is correct
             LOGGER.error("main_window_ref does NOT have set_in_dir method")

        # The set_in_dir method in MainWindow already updates the start button
        # and emits the preview signal, so no need to do it here again.
        # self._update_start_button_state() # Removed redundant call
        # self.main_window_preview_signal.emit() # Removed redundant call


    def _on_out_file_changed(self, text: str) -> None:
        """Handle changes to the output file text."""
        self.out_file_path = Path(text) if text else None
        self._update_start_button_state()

    def _pick_in_dir(self) -> None:
        LOGGER.debug("Entering _pick_in_dir...")
        # Access MainWindow's in_dir via the reference
        current_in_dir = getattr(self.main_window_ref, 'in_dir', None)
        start_dir = str(current_in_dir) if current_in_dir and current_in_dir.exists() else ""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Input Image Folder", start_dir)
        if dir_path:
            LOGGER.debug(f"Input directory selected: {dir_path}")
            # Setting text triggers _on_in_dir_changed, which updates MainWindow state via main_window_ref
            self.in_dir_edit.setText(dir_path)

    def _pick_out_file(self) -> None:
        LOGGER.debug("Entering _pick_out_file...")
        start_dir = str(self.out_file_path.parent) if self.out_file_path and self.out_file_path.parent.exists() else ""
        start_file = str(self.out_file_path) if self.out_file_path else ""

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Output Video", start_file or start_dir, "MP4 Files (*.mp4)"
        )
        if file_path:
            LOGGER.debug(f"Output file selected: {file_path}")
             # Setting text triggers _on_out_file_changed -> sets self.out_file_path
            self.out_file_edit.setText(file_path)

    def _on_crop_clicked(self) -> None:
# --- BEGIN ADDED DEBUG LOGS ---
        LOGGER.debug("_on_crop_clicked: Function entered.")
        try:
            mw_ref = self.main_window_ref
            LOGGER.debug(f"_on_crop_clicked: main_window_ref type: {type(mw_ref)}")
            in_dir_check = getattr(mw_ref, 'in_dir', 'AttributeMissing')
            LOGGER.debug(f"_on_crop_clicked: Accessed main_window_ref.in_dir: {in_dir_check}")
            crop_rect_check = getattr(mw_ref, 'current_crop_rect', 'AttributeMissing')
            LOGGER.debug(f"_on_crop_clicked: Accessed main_window_ref.current_crop_rect: {crop_rect_check}")
        except Exception as e:
            LOGGER.exception(f"_on_crop_clicked: Error accessing main_window_ref attributes early: {e}")
            # Optionally re-raise or return if this error is critical
        # --- END ADDED DEBUG LOGS ---
        LOGGER.debug("Entering _on_crop_clicked...") # Renamed from _on_select_crop_clicked
        # LOGGER.debug("--- _on_crop_clicked entered ---") # REMOVED DEBUGGING
        # Access MainWindow's state via the reference
        LOGGER.debug(f"Main window ref: {self.main_window_ref}")
        current_in_dir = getattr(self.main_window_ref, 'in_dir', None)
        current_crop_rect_mw_tuple = getattr(self.main_window_ref, 'current_crop_rect', None) # Get tuple

        if not current_in_dir or not current_in_dir.is_dir():
            LOGGER.warning("No input directory selected for cropping.")
            QMessageBox.warning(self, "Warning", "Please select an input directory first.")
            return

        try:
            image_files = sorted(
                [
                    f
                    for f in current_in_dir.iterdir()
                    if f.suffix.lower() in [".png", ".jpg", ".jpeg", ".tif", ".tiff"]
                ]
            )
            LOGGER.debug(f"Found {len(image_files)} image files in {current_in_dir}")
            if not image_files:
                LOGGER.warning("No images found in the input directory to crop.")
                QMessageBox.warning(self, "Warning", "No images found in the input directory to crop.")
                return

            first_image_path = image_files[0]
            LOGGER.debug(f"Preparing image for crop dialog: {first_image_path}")
            LOGGER.debug(f"Image path for cropping: {first_image_path}") # Added logging

            full_res_qimage: QImage | None = None
            is_sanchez = self.sanchez_false_colour_checkbox.isChecked() # Capture state
            LOGGER.debug(f"Sanchez checked: {is_sanchez}") # Added logging
            LOGGER.debug("Attempting to get full-res image...") # Added logging

            if is_sanchez: # Use captured variable
                LOGGER.debug("Sanchez preview enabled. Trying to get/process Sanchez image.")
                # Check cache first
                sanchez_cache = getattr(self.main_window_ref, 'sanchez_preview_cache', {})
                cached_np_array = sanchez_cache.get(first_image_path)

                if cached_np_array is not None:
                    LOGGER.debug(f"Found cached Sanchez result for {first_image_path.name}.")
                    full_res_qimage = numpy_to_qimage(cached_np_array)
                    if full_res_qimage.isNull():
                         LOGGER.error("Failed to convert cached Sanchez NumPy array to QImage.")
                         # Fallback to original below if conversion fails
                else:
                    LOGGER.debug(f"No cached Sanchez result for {first_image_path.name}. Processing...")
                    # Need to load original image and process with Sanchez
                    original_image_data: Optional[ImageData] = None
                    try:
                        # Use MainWindow's image_loader instance
                        loader = getattr(self.main_window_ref, 'image_loader', None)
                        if loader:
                             original_image_data = loader.load_image(first_image_path)
                        else:
                             LOGGER.error("Could not access MainWindow's image_loader.")

                        if original_image_data and original_image_data.image_data is not None:
                             # Use MainWindow's sanchez_processor instance
                             processor = getattr(self.main_window_ref, 'sanchez_processor', None)
                             if processor:
                                  # Process (this might update cache internally, or we might need to add it)
                                  # Assuming process_image returns ImageData with the processed np.ndarray
                                  # We need the *uncropped* version here.
                                  # Let's assume SanchezProcessor doesn't apply crop.
                                  sanchez_result_data = processor.process_image(original_image_data)
                                  if sanchez_result_data and sanchez_result_data.image_data is not None:
                                       LOGGER.debug("Sanchez processing successful.")
                                       full_res_qimage = numpy_to_qimage(sanchez_result_data.image_data)
                                       # Optionally update cache if processor doesn't do it
                                       # sanchez_cache[first_image_path] = sanchez_result_data.image_data
                                  else:
                                       LOGGER.error("Sanchez processing failed to return valid data.")
                             else:
                                  LOGGER.error("Could not access MainWindow's sanchez_processor.")
                        else:
                             LOGGER.error(f"Failed to load original image {first_image_path} for Sanchez processing.")

                    except Exception as proc_err:
                        LOGGER.exception(f"Error during Sanchez processing for crop dialog: {proc_err}")
                        QMessageBox.warning(self, "Warning", f"Could not process Sanchez image for cropping: {proc_err}\n\nShowing original image instead.")
                        # Fallback handled below

                # If Sanchez processing failed or wasn't possible, fall back to original
                if full_res_qimage is None or full_res_qimage.isNull():
                     LOGGER.warning("Falling back to loading original image for crop dialog after Sanchez attempt.")
                     full_res_qimage = QImage(str(first_image_path))

            else:
                # Sanchez disabled, just load the original image
                LOGGER.debug("Sanchez preview disabled. Loading original image.")
                full_res_qimage = QImage(str(first_image_path))

            # Final check if we have a valid QImage
            LOGGER.debug(f"Got image data: {type(full_res_qimage)}, isNull: {full_res_qimage.isNull()}") # Added logging
            if full_res_qimage is None or full_res_qimage.isNull():
                LOGGER.error(f"Failed to load or process any image for cropping: {first_image_path}")
                QMessageBox.critical(self, "Error", f"Could not load or process image for cropping: {first_image_path}")
                return

            # --- DEBUG LOGGING REMOVED ---
            # --- Use the new CropSelectionDialog ---
            LOGGER.debug(f"Opening CropSelectionDialog with image size: {full_res_qimage.size()}")
            LOGGER.debug("Instantiating CropSelectionDialog...") # Added logging
            dialog = CropSelectionDialog(full_res_qimage, self) # Pass QImage

            LOGGER.debug("Calling dialog.exec()...") # Added logging
            result_code = dialog.exec() # Store result code
            LOGGER.debug(f"Dialog result code: {result_code}") # Added logging
            if result_code == QDialog.DialogCode.Accepted:
                crop_qrect = dialog.get_selected_rect() # Returns QRect in image coordinates
                if not crop_qrect.isNull() and crop_qrect.isValid():
                    new_crop_rect_tuple = (
                        crop_qrect.x(),
                        crop_qrect.y(),
                        crop_qrect.width(),
                        crop_qrect.height(),
                    )
                    # Update MainWindow's crop_rect state via the reference
                    setter = getattr(self.main_window_ref, 'set_crop_rect', None)
                    if setter:
                         setter(new_crop_rect_tuple) # This comment is incorrect, setter only sets the value.
                         LOGGER.info(f"Crop rectangle set to: {new_crop_rect_tuple}")
                         self.main_window_preview_signal.emit() # <<< ADDED: Explicitly trigger preview update
                    else:
                         LOGGER.error("main_window_ref does not have set_crop_rect method")
                else:
                     LOGGER.info("Crop dialog accepted but no valid rectangle selected.")
            else:
                 LOGGER.info("Crop dialog cancelled.")

            LOGGER.debug("Exiting _on_crop_clicked.") # Added logging
        except Exception as e:
            LOGGER.exception(f"Error in _on_crop_clicked for {current_in_dir}: {e}")
            QMessageBox.critical(self, "Error", f"An unexpected error occurred during cropping setup: {e}")

    def _on_clear_crop_clicked(self) -> None:
        """Clear the current crop rectangle."""
        LOGGER.debug("Entering _on_clear_crop_clicked...")
        # Access MainWindow's state via the reference
        current_crop_rect_mw = getattr(self.main_window_ref, 'current_crop_rect', None)

        if current_crop_rect_mw:
             # Update MainWindow's crop_rect state via the reference
            if hasattr(self.main_window_ref, 'set_crop_rect'):
                 self.main_window_ref.set_crop_rect(None)
            else:
                 LOGGER.error("main_window_ref does not have set_crop_rect method")

            LOGGER.info("Crop rectangle cleared.")
            # Explicitly update button state and trigger preview refresh
            self._update_crop_buttons_state()
            self.main_window_preview_signal.emit()

    def _show_zoom(self, label: ClickableLabel) -> None:
        """Show the full-resolution image in a dedicated viewer dialog."""
        LOGGER.debug("Entering _show_zoom...")
        # Try to get the full-resolution processed image stored on the label
        full_res_image: QImage | None = getattr(label, 'processed_image', None)

        if full_res_image and isinstance(full_res_image, QImage) and not full_res_image.isNull():
            LOGGER.debug("Found full-resolution image on label. Preparing ImageViewerDialog.")

            image_to_show = full_res_image # Default to full image
            crop_rect_tuple = getattr(self.main_window_ref, 'current_crop_rect', None)

            if crop_rect_tuple:
                try:
                    x, y, w, h = crop_rect_tuple
                    crop_qrect = QRect(x, y, w, h)
                    # Ensure crop rect is within image bounds
                    img_rect = full_res_image.rect()
                    if img_rect.contains(crop_qrect):
                        LOGGER.debug(f"Applying crop {crop_qrect} to zoom view.")
                        cropped_qimage = full_res_image.copy(crop_qrect)
                        if not cropped_qimage.isNull():
                            image_to_show = cropped_qimage # Use the cropped QImage
                            LOGGER.debug(f"Cropped image size for zoom: {image_to_show.size()}")
                        else:
                            LOGGER.error("Failed to crop QImage.")
                    else:
                        LOGGER.warning(f"Crop rectangle {crop_qrect} is outside image bounds {img_rect}. Showing full image.")

                except Exception as e:
                    LOGGER.exception(f"Error applying crop in _show_zoom: {e}")
            else:
                LOGGER.debug("No crop rectangle found, showing full image in zoom.")

            # Close existing viewer if it's open
            if self.image_viewer_dialog and self.image_viewer_dialog.isVisible():
                LOGGER.debug("Closing existing image viewer dialog.")
                self.image_viewer_dialog.close() # Close the previous dialog

            # Instantiate the new ImageViewerDialog using the potentially cropped image
            # No parent is passed, making it a top-level window
            self.image_viewer_dialog = ImageViewerDialog(image_to_show) # Use image_to_show

            # Show the new dialog (non-modal)
            self.image_viewer_dialog.show()
            LOGGER.debug("New image viewer dialog shown.")
        else:
            LOGGER.warning("No valid full-resolution 'processed_image' found on the clicked label.")
            # Optionally, show a message to the user or just log the warning
            # QMessageBox.warning(self, "Image Not Ready", "The full-resolution image is not available yet.")

    def _enhance_preview_area(self) -> QGroupBox:
        """Create the group box containing the preview image labels."""
        previews_group = QGroupBox("Previews")
        previews_layout = QHBoxLayout(previews_group)
        previews_layout.setContentsMargins(10, 15, 10, 10)
        previews_layout.setSpacing(10)

        preview_labels = [
            self.first_frame_label,
            self.middle_frame_label,
            self.last_frame_label,
        ]
        preview_titles = ["First Frame", "Middle Frame", "Last Frame"]

        for i, label in enumerate(preview_labels):
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(5)

            title_label = QLabel(preview_titles[i])
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setToolTip("Click to zoom")
            label.setMinimumSize(100, 100) # Ensure minimum size
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored) # Allow shrinking/expanding
            label.setStyleSheet("border: 1px solid gray; background-color: #2a2a2a;") # Style

            container_layout.addWidget(title_label)
            container_layout.addWidget(label, 1) # Give label stretch factor
            previews_layout.addWidget(container)

        return previews_group

    def _create_processing_settings_group(self) -> QGroupBox:
        """Create the group box for general processing settings."""
        group = QGroupBox("Processing Settings")
        layout = QGridLayout(group)
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setSpacing(8)

        # Assign widgets created in MainWindow to self attributes for access
        # These are assumed to be passed or accessible via parent/main_window if needed,
        # but typically they are created *here* or passed into the tab.
        # Let's assume they are created here for now, matching typical tab structure.
        # If they are truly created in MainWindow, this needs adjustment.

        self.fps_spinbox = QSpinBox()
        self.fps_spinbox.setRange(1, 120)
        self.fps_spinbox.setValue(60)
        layout.addWidget(QLabel("Output FPS:"), 0, 0)
        layout.addWidget(self.fps_spinbox, 0, 1)

        self.multiplier_spinbox = QSpinBox() # Renamed from mid_count_spinbox for clarity
        self.multiplier_spinbox.setRange(2, 16) # Example range
        self.multiplier_spinbox.setValue(2)
        layout.addWidget(QLabel("Frame Multiplier:"), 1, 0)
        layout.addWidget(self.multiplier_spinbox, 1, 1)
        self.mid_count_spinbox = self.multiplier_spinbox # Alias for compatibility if needed

        self.max_workers_spinbox = QSpinBox()
        cpu_cores = os.cpu_count()
        default_workers = max(1, cpu_cores // 2) if cpu_cores else 1
        self.max_workers_spinbox.setRange(1, os.cpu_count() or 1)
        self.max_workers_spinbox.setValue(default_workers)
        layout.addWidget(QLabel("Max Workers:"), 2, 0)
        layout.addWidget(self.max_workers_spinbox, 2, 1)

        self.encoder_combo = QComboBox()
        self.encoder_combo.addItems(["RIFE", "FFmpeg"]) # Add other encoders if supported
        layout.addWidget(QLabel("Encoder:"), 3, 0)
        layout.addWidget(self.encoder_combo, 3, 1)

        return group


    def _toggle_tile_size_enabled(self, state: int | bool) -> None:
        """Enable/disable the tile size spinbox based on the checkbox state."""
        enabled = bool(state)
        self.rife_tile_size_spinbox.setEnabled(enabled)


    def _connect_model_combo(self) -> None:
        """Connect signals for the RIFE model combo box."""
        self.rife_model_combo.currentIndexChanged.connect(self._on_model_selected)


    def _validate_thread_spec(self, text: str) -> None:
        """Validate the RIFE thread specification format."""
        if not text: # Allow empty
            self.rife_thread_spec_edit.setStyleSheet("")
            return

        # Basic regex for N:N:N format (allows single digits or more)
        if re.fullmatch(r"\d+:\d+:\d+", text):
            self.rife_thread_spec_edit.setStyleSheet("")
        else:
            self.rife_thread_spec_edit.setStyleSheet("background-color: #401010;") # Indicate error


    def _start(self) -> None:
        """Prepare arguments and emit the processing_started signal."""
        LOGGER.debug("MainTab: Start button clicked.")
        LOGGER.debug("Emitting processing_started signal")
        main_window = cast(QObject, self.parent())
        current_in_dir = getattr(main_window, 'in_dir', None)
        LOGGER.debug(f"Current input directory: {current_in_dir}, Output file: {self.out_file_path}")

        if not current_in_dir or not self.out_file_path:
            LOGGER.warning("Missing paths for processing")
            QMessageBox.warning(self, "Missing Paths", "Please select both input and output paths.")
            return

        args = self.get_processing_args()
        if args:
            LOGGER.info(f"Starting processing with args: {args}")
            self.set_processing_state(True)
            LOGGER.debug("Emitting processing_started signal")
            # Add a direct print to stdout for clearer debugging
            print(f"EMITTING SIGNAL: processing_started with {len(args) if args else 0} args")
            self.processing_started.emit(args) # Emit signal with processing arguments
            LOGGER.debug("Signal emitted")
        else:
            # Error message already shown by get_processing_args
            LOGGER.warning("Processing not started due to invalid arguments.")


    # --- Worker Interaction ---
    # These methods handle signals from the VfiWorker thread

    def set_processing_state(self, is_processing: bool) -> None:
        """Update UI elements based on processing state."""
        self.is_processing = is_processing
        self.start_button.setText("Cancel Processing" if is_processing else "Start Video Interpolation")
        # Disable relevant controls during processing
        self.in_dir_edit.setEnabled(not is_processing)
        self.out_file_edit.setEnabled(not is_processing)
        # Find browse buttons and disable them
        in_browse_button = self.findChild(QPushButton, "browse_button") # Assuming only one for input for now
        out_browse_button = self.findChildren(QPushButton, "browse_button")[1] # Assuming second is output
        if in_browse_button: in_browse_button.setEnabled(not is_processing)
        if out_browse_button: out_browse_button.setEnabled(not is_processing)
        # self.processing_vm.set_processing(is_processing) # Incorrect method
        if is_processing:
            self.processing_vm.start_processing() # Call correct ViewModel method
        else:
            # Assuming a method like stop_processing or cancel_processing exists
            # If this causes issues, the ViewModel needs inspection.
            self.processing_vm.cancel_processing() # Call correct ViewModel method


    def _reset_start_button(self) -> None:
        """Resets the start button text and enables it."""
        self.start_button.setText("Start Video Interpolation")
        self.set_processing_state(False)
        self._update_start_button_state() # Re-evaluate if it should be enabled


    def _update_start_button_state(self) -> None:
        """Enable/disable start button based on paths and RIFE model availability."""
        main_window = cast(QObject, self.parent())
        current_in_dir = getattr(main_window, 'in_dir', None)
        has_paths = current_in_dir and self.out_file_path
        # Check RIFE model only if RIFE is selected encoder
        rife_ok = True
        if self.encoder_combo.currentText() == "RIFE":
            rife_ok = bool(self.rife_model_combo.currentData()) # Check if a valid model is selected

        can_start = bool(has_paths and rife_ok)
        self.start_button.setEnabled(can_start and not self.is_processing)


    @pyqtSlot(bool, str)
    def _on_processing_finished(self, success: bool, message: str) -> None:
        """Handle the processing finished signal from the worker."""
        LOGGER.info(f"MainTab received processing finished: Success={success}, Message={message}")
        self.set_processing_state(False)
        self.processing_finished.emit(success, message) # Forward the signal
        if success:
            QMessageBox.information(self, "Success", f"Video interpolation finished!\nOutput: {message}")
        # Error message handled by _on_processing_error


    def _on_processing_error(self, error_message: str) -> None:
        """Handle processing errors."""
        LOGGER.error(f"MainTab received processing error: {error_message}")
        self.set_processing_state(False)
        self.processing_finished.emit(False, error_message) # Forward the signal
        QMessageBox.critical(self, "Error", f"Processing failed:\n{error_message}")


    # --- Methods removed as preview logic is now centralized in MainWindow ---
    # _update_previews
    # _convert_image_data_to_qimage
    # _load_process_scale_preview
    # -----------------------------------------------------------------------


    def _update_crop_buttons_state(self) -> None:
        """Enable/disable crop buttons based on input directory and current crop state in MainWindow."""
        # Use the stored reference to MainWindow, not self.parent()
        main_window = self.main_window_ref
        has_in_dir = getattr(main_window, 'in_dir', None) is not None
        has_crop = getattr(main_window, 'current_crop_rect', None) is not None

        # Removed diagnostic print statements
        LOGGER.debug(f"_update_crop_buttons_state: Checking conditions - has_in_dir={has_in_dir}, has_crop={has_crop}") # Original DEBUG log
        self.crop_button.setEnabled(has_in_dir)
        # Enable clear button only if both input dir and crop exist
        self.clear_crop_button.setEnabled(has_in_dir and has_crop)

        # LOGGER.debug(f"_update_crop_buttons_state: main_window={main_window}, has_in_dir={has_in_dir}, has_crop={has_crop}") # Original commented DEBUG log

    def _update_rife_ui_elements(self) -> None:
        """Update RIFE-specific UI elements based on selected model capabilities."""
        model_key = self.rife_model_combo.currentData()
        if not model_key or model_key not in self.available_models:
            # Disable RIFE options if no valid model selected
            self.rife_uhd_checkbox.setEnabled(False)
            self.rife_tta_spatial_checkbox.setEnabled(False)
            self.rife_tta_temporal_checkbox.setEnabled(False)
            self.rife_tile_checkbox.setEnabled(False)
            self.rife_tile_size_spinbox.setEnabled(False)
            self.rife_thread_spec_edit.setEnabled(False)
            return

        details = self.available_models[model_key]
        caps = details.get("capabilities", {})

        # Enable/disable based on capabilities
        self.rife_uhd_checkbox.setEnabled(caps.get("uhd", False))
        self.rife_tta_spatial_checkbox.setEnabled(caps.get("tta_spatial", False))
        self.rife_tta_temporal_checkbox.setEnabled(caps.get("tta_temporal", False))
        self.rife_tile_checkbox.setEnabled(caps.get("tiling", False))
        # Tile size enabled based on checkbox state (connected signal)
        self.rife_tile_size_spinbox.setEnabled(self.rife_tile_checkbox.isChecked() and caps.get("tiling", False))
        self.rife_thread_spec_edit.setEnabled(caps.get("custom_thread_count", False))

        # Reset checkboxes if capability is false
        if not caps.get("uhd", False): self.rife_uhd_checkbox.setChecked(False)
        if not caps.get("tta_spatial", False): self.rife_tta_spatial_checkbox.setChecked(False)
        if not caps.get("tta_temporal", False): self.rife_tta_temporal_checkbox.setChecked(False)
        if not caps.get("tiling", False): self.rife_tile_checkbox.setChecked(False)
        if not caps.get("custom_thread_count", False): self.rife_thread_spec_edit.setText("")


    def _update_rife_options_state(self, encoder: str) -> None:
        """Enable/disable the RIFE options group based on the selected encoder."""
        is_rife = encoder == "RIFE"
        self.rife_options_group.setEnabled(is_rife)


    def _update_sanchez_options_state(self, encoder: str) -> None:
        """Enable/disable the Sanchez options group based on the selected encoder."""
        is_sanchez = encoder == "Sanchez" # Assuming Sanchez might be an encoder option later
        # For now, Sanchez options might be relevant even with RIFE/FFmpeg if used for preview/post-processing
        # Let's keep it enabled unless explicitly tied to a "Sanchez Encoder" mode.
        # self.sanchez_options_group.setEnabled(is_sanchez)
        self.sanchez_options_group.setEnabled(True) # Keep enabled for now


    def _on_encoder_changed(self, encoder: str) -> None:
        """Handle changes in the selected encoder."""
        self.current_encoder = encoder
        self._update_rife_options_state(encoder)
        self._update_sanchez_options_state(encoder)
        # Potentially update FFmpeg tab state if needed (e.g., disable if RIFE selected)
        # This might require a signal to MainWindow or direct interaction if FFmpeg tab is accessible.
        self._update_start_button_state() # Re-check start button validity


    def _populate_models(self) -> None:
        """Populate the RIFE model selection combo box by finding models and analyzing them."""
        LOGGER.debug("Populating RIFE models...")
        self.rife_model_combo.clear()
        self.available_models.clear()
        project_root = config.get_project_root()
        models_base_dir = project_root / "models"
        cache_dir = get_cache_dir()
        analysis_cache_file = cache_dir / "rife_analysis_cache.json"

        # Load cached analysis if available
        cached_analysis: Dict[str, RIFEModelDetails] = {}
        if analysis_cache_file.exists():
            try:
                with open(analysis_cache_file, 'r') as f:
                    cached_analysis = json.load(f)
                LOGGER.debug(f"Loaded RIFE analysis cache from {analysis_cache_file}")
            except Exception as e:
                LOGGER.warning(f"Failed to load RIFE analysis cache: {e}")

        found_models = get_available_rife_models()
        if not found_models:
            LOGGER.warning("No RIFE models found in the 'models' directory.")
            self.rife_model_combo.addItem("No Models Found", userData=None)
            self.rife_model_combo.setEnabled(False)
            return

        self.rife_model_combo.setEnabled(True)
        needs_cache_update = False
        for key in found_models: # Iterate directly over the list of model names
            model_dir = project_root / "models" / key
            rife_exe = config.find_rife_executable(key) # Pass model key (string) not directory (Path)
            if not rife_exe:
                LOGGER.warning(f"RIFE executable not found for model '{key}' in {model_dir}")
                continue

            exe_path_str = str(rife_exe)
            exe_mtime = os.path.getmtime(rife_exe)

            # Check cache
            if exe_path_str in cached_analysis and cached_analysis[exe_path_str].get("_mtime") == exe_mtime:
                LOGGER.debug(f"Using cached analysis for {key} ({rife_exe.name})")
                details = cached_analysis[exe_path_str]
            else:
                LOGGER.info(f"Analyzing RIFE executable for model '{key}': {rife_exe}")
                try:
                    # Cast the result to the TypedDict
                    details_raw = analyze_rife_executable(rife_exe)
                    details = cast(RIFEModelDetails, details_raw)
                    details["_mtime"] = exe_mtime # Store modification time for cache validation
                    cached_analysis[exe_path_str] = details # Update cache entry
                    needs_cache_update = True
                    LOGGER.debug(f"Analysis complete for {key}. Capabilities: {details.get('capabilities')}")
                except Exception as e:
                    LOGGER.exception(f"Failed to analyze RIFE executable for model '{key}': {e}")
                    # Ensure the error dictionary conforms to the TypedDict structure (even if values are defaults/errors)
                    details = cast(RIFEModelDetails, {"version": "Error", "capabilities": {}, "supported_args": [], "help_text": f"Error: {e}", "_mtime": exe_mtime})
                    cached_analysis[exe_path_str] = details # Cache error state too
                    needs_cache_update = True


            self.available_models[key] = details
            display_name = f"{key} (v{details.get('version', 'Unknown')})"
            if details.get("version") == "Error":
                 display_name = f"{key} (Analysis Error)"
            self.rife_model_combo.addItem(display_name, userData=key)

        # Save updated cache
        if needs_cache_update:
            try:
                os.makedirs(cache_dir, exist_ok=True)
                with open(analysis_cache_file, 'w') as f:
                    json.dump(cached_analysis, f, indent=4)
                LOGGER.debug(f"Saved updated RIFE analysis cache to {analysis_cache_file}")
            except Exception as e:
                LOGGER.warning(f"Failed to save RIFE analysis cache: {e}")


        # Try to restore last selected model
        last_model_key = self.settings.value("rife/modelKey", "rife-v4.6", type=str)
        index = self.rife_model_combo.findData(last_model_key)
        if index != -1:
            self.rife_model_combo.setCurrentIndex(index)
            LOGGER.debug(f"Restored last selected RIFE model: {last_model_key}")
        elif self.rife_model_combo.count() > 0:
             self.rife_model_combo.setCurrentIndex(0) # Select first available if last not found
             LOGGER.debug("Last selected RIFE model not found, selecting first available.")

        self._update_rife_ui_elements() # Update UI based on the initially selected model
        self._update_start_button_state() # Update start button state


    def _on_model_selected(self, index: int) -> None:
        """Handle selection changes in the RIFE model combo box."""
        model_key = self.rife_model_combo.itemData(index)
        if model_key and model_key in self.available_models:
            self.current_model_key = model_key
            LOGGER.info(f"RIFE model selected: {model_key}")
            self._update_rife_ui_elements()
            self._update_start_button_state()
        else:
            LOGGER.warning(f"Invalid model selected at index {index}, data: {model_key}")
            self.current_model_key = None # Resetting seems safer. Type hint updated to Optional[str]
            self._update_rife_ui_elements() # Disable options
            self._update_start_button_state()


    def get_processing_args(self) -> Dict[str, Any] | None: # Add type parameters
        """Gather all processing arguments from the UI."""
        main_window = cast(QObject, self.parent())
        current_in_dir = getattr(main_window, 'in_dir', None)
        current_crop_rect_mw = getattr(main_window, 'current_crop_rect', None)

        if not current_in_dir:
            QMessageBox.critical(self, "Error", "Input directory not selected.")
            return None
        if not self.out_file_path:
            QMessageBox.critical(self, "Error", "Output file not selected.")
            return None

        encoder = self.encoder_combo.currentText()
        rife_model_key = self.rife_model_combo.currentData()

        if encoder == "RIFE" and not rife_model_key:
             QMessageBox.critical(self, "Error", "No RIFE model selected.")
             return None

        args = {
            "in_dir": current_in_dir,
            "out_file": self.out_file_path,
            "fps": self.fps_spinbox.value(),
            "multiplier": self.multiplier_spinbox.value(),
            "max_workers": self.max_workers_spinbox.value(),
            "encoder": encoder,
            "rife_model_key": rife_model_key if encoder == "RIFE" else None,
            "rife_model_path": (config.get_project_root() / "models" / rife_model_key) if encoder == "RIFE" and rife_model_key else None,
            "rife_exe_path": config.find_rife_executable(rife_model_key) if encoder == "RIFE" and rife_model_key else None,
            "rife_tta_spatial": self.rife_tta_spatial_checkbox.isChecked() if encoder == "RIFE" else False,
            "rife_tta_temporal": self.rife_tta_temporal_checkbox.isChecked() if encoder == "RIFE" else False,
            "rife_uhd": self.rife_uhd_checkbox.isChecked() if encoder == "RIFE" else False,
            "rife_tiling_enabled": self.rife_tile_checkbox.isChecked() if encoder == "RIFE" else False,
            "rife_tile_size": self.rife_tile_size_spinbox.value() if encoder == "RIFE" else None,
            "rife_thread_spec": self.rife_thread_spec_edit.text() if encoder == "RIFE" and self.rife_thread_spec_edit.text() else None,
            "sanchez_enabled": self.sanchez_false_colour_checkbox.isChecked(), # This might control post-processing or preview, not necessarily encoding
            "sanchez_resolution_km": float(self.sanchez_res_combo.currentText()),
            "crop_rect": current_crop_rect_mw,
            # TODO: Add FFmpeg specific args from FFmpegSettingsTab if encoder is FFmpeg
            "ffmpeg_args": None # Placeholder
        }
        return args


    def set_input_directory(self, directory: Path | str) -> None:
        """Public method to set the input directory text edit."""
        # This might be called from MainWindow or sorter tabs
        self.in_dir_edit.setText(str(directory)) # Triggers _on_in_dir_changed


    def load_settings(self) -> None:
        """Load settings relevant to the MainTab from QSettings."""
        LOGGER.debug("MainTab: Loading settings...")
        main_window = cast(QObject, self.parent())

        # --- Load Input/Output ---
        # Load input dir and set it in MainWindow
        in_dir_str = self.settings.value("paths/inputDirectory", "", type=str)
        loaded_in_dir = Path(in_dir_str) if in_dir_str and Path(in_dir_str).is_dir() else None
        if hasattr(main_window, 'set_in_dir'):
            main_window.set_in_dir(loaded_in_dir) # Set state in MainWindow
            self.in_dir_edit.setText(in_dir_str if loaded_in_dir else "") # Update local widget
            if loaded_in_dir:
                 LOGGER.info(f"Loaded input directory: {in_dir_str}")
            else:
                 LOGGER.debug("No valid saved input directory found.")
        else:
            LOGGER.error("Parent does not have set_in_dir method")

        # Load output file (still managed locally in MainTab)
        out_file_str = self.settings.value("paths/outputFile", "", type=str)
        if out_file_str:
             self.out_file_edit.setText(out_file_str) # Triggers _on_out_file_changed -> sets self.out_file_path
             LOGGER.info(f"Loaded output file: {out_file_str}")
        else:
             self.out_file_path = None # Ensure state is None if empty

        # --- Load Processing Settings ---
        self.fps_spinbox.setValue(self.settings.value("processing/fps", 60, type=int))
        self.mid_count_spinbox.setValue(self.settings.value("processing/multiplier", 2, type=int))
        cpu_cores = os.cpu_count()
        default_workers = max(1, cpu_cores // 2) if cpu_cores else 1
        self.max_workers_spinbox.setValue(self.settings.value("processing/maxWorkers", default_workers, type=int))
        self.encoder_combo.setCurrentText(self.settings.value("processing/encoder", "RIFE", type=str))

        # --- Load RIFE Options ---
        # self.rife_model_combo requires models to be populated first, handled in _post_init_setup -> _populate_models
        self.rife_tile_checkbox.setChecked(self.settings.value("rife/tilingEnabled", False, type=bool))
        self.rife_tile_size_spinbox.setValue(self.settings.value("rife/tileSize", 256, type=int))
        self.rife_uhd_checkbox.setChecked(self.settings.value("rife/uhdMode", False, type=bool))
        self.rife_thread_spec_edit.setText(self.settings.value("rife/threadSpec", "", type=str))
        self.rife_tta_spatial_checkbox.setChecked(self.settings.value("rife/ttaSpatial", False, type=bool))
        self.rife_tta_temporal_checkbox.setChecked(self.settings.value("rife/ttaTemporal", False, type=bool))

        # --- Load Sanchez Options ---
        self.sanchez_false_colour_checkbox.setChecked(self.settings.value("sanchez/falseColorEnabled", False, type=bool))
        self.sanchez_res_combo.setCurrentText(self.settings.value("sanchez/resolutionKm", "4", type=str))

        # --- Load Crop State and set it in MainWindow ---
        crop_rect_str = self.settings.value("preview/cropRectangle", "", type=str)
        loaded_crop_rect = None
        if crop_rect_str:
             try:
                  coords = [int(c.strip()) for c in crop_rect_str.split(',')]
                  if len(coords) == 4:
                       loaded_crop_rect = tuple(coords)
                       LOGGER.info(f"Loaded crop rectangle: {loaded_crop_rect}")
                  else:
                       LOGGER.warning(f"Invalid crop rectangle format in settings: {crop_rect_str}")
             except ValueError:
                  LOGGER.warning(f"Could not parse crop rectangle from settings: {crop_rect_str}")

        if hasattr(main_window, 'set_crop_rect'):
             main_window.set_crop_rect(loaded_crop_rect) # Set state in MainWindow
        else:
             LOGGER.error("Parent does not have set_crop_rect method")


        # Update UI states based on loaded settings
        self._update_rife_ui_elements() # Handles model combo based on loaded encoder
        self._update_start_button_state()
        self._update_crop_buttons_state()
        self._update_rife_options_state(self.encoder_combo.currentText())
        self._update_sanchez_options_state(self.encoder_combo.currentText())
        self._toggle_tile_size_enabled(self.rife_tile_checkbox.isChecked())

        # Trigger preview update via MainWindow's signal AFTER loading settings
        self.main_window_preview_signal.emit()

        LOGGER.debug("MainTab: Settings loaded.")


    def save_settings(self) -> None:
        """Save settings relevant to the MainTab to QSettings."""
        LOGGER.debug("MainTab: Saving settings...")
        main_window = cast(QObject, self.parent())

        # --- Save Paths ---
        # Save input directory from MainWindow's state
        current_in_dir = getattr(main_window, 'in_dir', None)
        if current_in_dir:
             self.settings.setValue("paths/inputDirectory", str(current_in_dir))
        else:
             self.settings.remove("paths/inputDirectory") # Clear if None

        # Save output file (still managed locally in MainTab)
        if self.out_file_path:
             self.settings.setValue("paths/outputFile", str(self.out_file_path))
        else:
             self.settings.remove("paths/outputFile")

        # --- Save Processing Settings ---
        self.settings.setValue("processing/fps", self.fps_spinbox.value())
        self.settings.setValue("processing/multiplier", self.mid_count_spinbox.value())
        self.settings.setValue("processing/maxWorkers", self.max_workers_spinbox.value())
        self.settings.setValue("processing/encoder", self.encoder_combo.currentText())

        # --- Save RIFE Options ---
        self.settings.setValue("rife/modelKey", self.rife_model_combo.currentData()) # Save model key
        self.settings.setValue("rife/tilingEnabled", self.rife_tile_checkbox.isChecked())
        self.settings.setValue("rife/tileSize", self.rife_tile_size_spinbox.value())
        self.settings.setValue("rife/uhdMode", self.rife_uhd_checkbox.isChecked())
        self.settings.setValue("rife/threadSpec", self.rife_thread_spec_edit.text())
        self.settings.setValue("rife/ttaSpatial", self.rife_tta_spatial_checkbox.isChecked())
        self.settings.setValue("rife/ttaTemporal", self.rife_tta_temporal_checkbox.isChecked())

        # --- Save Sanchez Options ---
        self.settings.setValue("sanchez/falseColorEnabled", self.sanchez_false_colour_checkbox.isChecked())
        self.settings.setValue("sanchez/resolutionKm", self.sanchez_res_combo.currentText())

        # --- Save Crop State from MainWindow's state ---
        current_crop_rect_mw = getattr(main_window, 'current_crop_rect', None)
        if current_crop_rect_mw:
             rect_str = ",".join(map(str, current_crop_rect_mw))
             self.settings.setValue("preview/cropRectangle", rect_str)
        else:
             self.settings.remove("preview/cropRectangle")

        LOGGER.debug("MainTab: Settings saved.")