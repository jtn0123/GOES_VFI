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
from PyQt6.QtCore import QSettings, Qt, QTimer, pyqtSignal, pyqtSlot, QRect, QObject, QPointF # Add QObject, QPointF
from PyQt6.QtGui import QColor, QImage, QPixmap, QMouseEvent, QCursor # Add QMouseEvent, QCursor
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

# Custom button class with enhanced event handling
class SuperButton(QPushButton):
    """A custom button class that ensures clicks are properly processed."""
    
    def __init__(self, text: str, parent: QWidget = None):
        super().__init__(text, parent)
        self.click_callback = None
        print(f"SuperButton created with text: {text}")
        
    def set_click_callback(self, callback):
        """Set a direct callback function for click events."""
        self.click_callback = callback
        print(f"SuperButton callback set: {callback.__name__ if callback else 'None'}")
        
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Explicitly override mouse press event."""
        print(f"SuperButton MOUSE PRESS: {event.button()}")
        # Call the parent implementation
        super().mousePressEvent(event)
        
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Explicitly override mouse release event for better click detection."""
        print(f"SuperButton MOUSE RELEASE: {event.button()}")
        super().mouseReleaseEvent(event)
        
        # If it's a left-click release, call our callback
        if event.button() == Qt.MouseButton.LeftButton:
            print("SuperButton: LEFT CLICK DETECTED")
            if self.click_callback:
                print(f"SuperButton: Calling callback {self.click_callback.__name__}")
                QTimer.singleShot(10, self.click_callback)  # Small delay to ensure UI updates
            else:
                print("SuperButton: No callback registered")

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
        # Ensure we're using the same settings instance as MainWindow
        self.settings = settings
        # Force settings to sync at initialization to ensure freshest data
        self.settings.sync()
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

        # Create a completely redesigned start button implementation
        self.start_button = QPushButton("START")
        self.start_button.setObjectName("start_button") 
        self.start_button.setMinimumHeight(50)
        self.start_button.setEnabled(True)  # Initially enabled for debugging
        self.start_button.setStyleSheet("""
            QPushButton#start_button {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                font-size: 16px;
                border-radius: 5px;
                padding: 8px 16px;
            }
            QPushButton#start_button:hover {
                background-color: #45a049;
            }
            QPushButton#start_button:pressed {
                background-color: #3e8e41;
            }
        """)
        
        # Create a button container for the start button
        button_container = QWidget()
        button_layout = QVBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add just the regular start button
        button_layout.addWidget(self.start_button)
        
        # Connect standard button
        self.start_button.clicked.connect(self._direct_start_handler)
        
        # Log button creation
        LOGGER.debug("Start button created and connected")

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
        layout.addWidget(button_container)  # Add the button container with both buttons

        # --- Aliases for potential external access or future refactoring ---
        self.model_combo = self.rife_model_combo
        # -------------------------------------------------------------------


    def _connect_signals(self) -> None:
        """Connect signals to slots for the main tab."""
        LOGGER.debug("Connecting MainTab signals...")
        
        # IO Controls
        LOGGER.debug("Connecting IO control signals...")
        self.in_dir_edit.textChanged.connect(self._on_in_dir_changed)
        # Button connections moved to _setup_ui where buttons are created
        self.out_file_edit.textChanged.connect(self._on_out_file_changed)

        # Preview Controls
        LOGGER.debug("Connecting preview control signals...")
        self.first_frame_label.clicked.connect(lambda: self._show_zoom(self.first_frame_label))
        self.middle_frame_label.clicked.connect(lambda: self._show_zoom(self.middle_frame_label))
        self.last_frame_label.clicked.connect(lambda: self._show_zoom(self.last_frame_label))
        self.sanchez_false_colour_checkbox.stateChanged.connect(self.main_window_preview_signal.emit) # Emit MainWindow signal

        # Crop Controls
        LOGGER.debug("Connecting crop control signals...")
        self.crop_button.clicked.connect(self._on_crop_clicked)
        self.clear_crop_button.clicked.connect(self._on_clear_crop_clicked)

        # Processing Settings
        LOGGER.debug("Connecting processing setting signals...")
        self.encoder_combo.currentTextChanged.connect(self._on_encoder_changed)

        # RIFE Options
        LOGGER.debug("Connecting RIFE option signals...")
        self.rife_tile_checkbox.stateChanged.connect(self._toggle_tile_size_enabled)
        self.rife_thread_spec_edit.textChanged.connect(self._validate_thread_spec)
        self._connect_model_combo() # Connect RIFE model combo signals

        # Note: Start button connection is now handled in _setup_ui
        # for clarity and to avoid multiple connections
        LOGGER.debug("Start button already connected in _setup_ui")
        
        # Verify that our processing signals are connected to MainWindow
        LOGGER.debug("Verifying processing signal connections...")
        self._verify_processing_signal_connections()
        
        LOGGER.debug("All MainTab signals connected.")

    def _verify_processing_signal_connections(self) -> None:
        """Verify that processing signals are properly connected to MainWindow."""
        # In PyQt6, we can't directly get receiver count, so instead check main_window for
        # expected handler methods
        LOGGER.debug("Verifying processing signal connections...")
        
        # Check if MainWindow has methods for handling our signals
        main_window = self.main_window_ref
        has_processing_handler = hasattr(main_window, '_handle_processing')
        LOGGER.debug(f"MainWindow has _handle_processing method: {has_processing_handler}")
            
        if not has_processing_handler:
            LOGGER.error("WARNING: MainWindow does not have _handle_processing method!")
            # Try fallback options if needed
        else:
            LOGGER.debug("MainWindow appears to have necessary handler methods")
        
        # Try to manually connect to MainWindow if possible (will be ignored if already connected)
        if has_processing_handler:
            try:
                LOGGER.debug("Ensuring processing_started signal is connected...")
                # Note: PyQt6 will silently ignore duplicate connections
                self.processing_started.connect(main_window._handle_processing)
                LOGGER.debug("Processing signal connection verified/created")
            except Exception as e:
                LOGGER.exception(f"Failed to verify/connect processing_started signal: {e}")
        else:
            LOGGER.error("Cannot connect: main_window does not have required handler methods")


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
        """Select the output file path."""
        LOGGER.debug("Entering _pick_out_file...")
        
        # Get starting directory/file
        start_dir = ""
        start_file = ""
        if self.out_file_path:
            LOGGER.debug(f"Current out_file_path: {self.out_file_path}")
            if self.out_file_path.parent and self.out_file_path.parent.exists():
                start_dir = str(self.out_file_path.parent)
                LOGGER.debug(f"Using parent dir for file dialog: {start_dir}")
            start_file = str(self.out_file_path)
            LOGGER.debug(f"Using current path for file dialog: {start_file}")
            
        # If we have an input directory but no output file yet, suggest a file path based on input
        if not start_file and not start_dir:
            main_window = self.main_window_ref
            current_in_dir = getattr(main_window, 'in_dir', None)
            if current_in_dir and current_in_dir.exists():
                # Use input directory name + timestamped output name for uniqueness
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dir_name = current_in_dir.name
                start_dir = str(current_in_dir.parent)
                suggested_name = f"{dir_name}_output_{timestamp}.mp4"
                start_file = str(current_in_dir.parent / suggested_name)
                LOGGER.debug(f"Suggesting timestamped output file: {start_file}")

        # Get save filename
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Output Video", start_file or start_dir, "MP4 Files (*.mp4)"
        )
        
        if file_path:
            LOGGER.debug(f"Output file selected: {file_path}")
            # Double check file has .mp4 extension
            if not file_path.lower().endswith('.mp4'):
                file_path += '.mp4'
                LOGGER.debug(f"Added .mp4 extension: {file_path}")
                
            # Setting text triggers _on_out_file_changed -> sets self.out_file_path
            self.out_file_edit.setText(file_path)
            
            # Update button state immediately
            self._update_start_button_state()
        else:
            LOGGER.debug("No output file selected")

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
            
            # Keep track of whether we're showing a cropped view for UI indication
            is_cropped_view = False

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
                            is_cropped_view = True
                            LOGGER.debug(f"Cropped image size for zoom: {image_to_show.size()}")
                        else:
                            LOGGER.error("Failed to crop QImage.")
                    else:
                        LOGGER.warning(f"Crop rectangle {crop_qrect} is outside image bounds {img_rect}. Showing full image.")

                except Exception as e:
                    LOGGER.exception(f"Error applying crop in _show_zoom: {e}")
            else:
                LOGGER.debug("No crop rectangle found, showing full image in zoom.")

            # Get display details for preview info
            # For example: which preview is this (first, middle, last)
            preview_type = ""
            if label == self.first_frame_label:
                preview_type = "First Frame"
            elif label == self.middle_frame_label:
                preview_type = "Middle Frame"
            elif label == self.last_frame_label:
                preview_type = "Last Frame"
                
            # Construct additional info for the dialog title
            info_title = preview_type
            if is_cropped_view:
                # Add crop indicator
                info_title += f" (Cropped: {crop_rect_tuple[2]}x{crop_rect_tuple[3]})"
            elif crop_rect_tuple:
                # There's a crop rect but we're showing the full image (e.g., bounds issue)
                info_title += " (Full Image - Crop Disabled)"
                
            # Get image file path if available (for showing file details)
            file_path = getattr(label, 'file_path', None)
            if file_path:
                # Extract just the filename to keep it clean
                try:
                    from pathlib import Path
                    p = Path(file_path)
                    info_title += f" - {p.name}"
                except Exception:
                    # Fall back to full path if parsing fails
                    info_title += f" - {file_path}"

            # Close existing viewer if it's open
            if self.image_viewer_dialog and self.image_viewer_dialog.isVisible():
                LOGGER.debug("Closing existing image viewer dialog.")
                self.image_viewer_dialog.close() # Close the previous dialog

            # Instantiate the new ImageViewerDialog with enhanced info
            self.image_viewer_dialog = ImageViewerDialog(image_to_show) # Use image_to_show
            
            # Set custom title with info (could be extended to handle with new parameter)
            self.image_viewer_dialog.setWindowTitle(info_title)
            
            # Enhanced debug info for better troubleshooting
            LOGGER.debug(f"Opening ImageViewerDialog - Title: {info_title}")
            LOGGER.debug(f"Image dimensions: {image_to_show.width()}x{image_to_show.height()}")
            
            # Show the new dialog (non-modal)
            self.image_viewer_dialog.show()
            LOGGER.debug("New image viewer dialog shown.")
            
            # IMPROVEMENT: Future enhancement - Add a "Show Crop Overlay" mode 
            # that shows the original image with a rectangle highlighting the crop area
            # This would require modifying the ImageViewerDialog class to support overlay drawing
            
        else:
            LOGGER.warning("No valid full-resolution 'processed_image' found on the clicked label.")
            
            # Provide better feedback to user when image isn't available
            msg = "The full-resolution image is not available for preview yet."
            
            # Check if we have any context to add
            if not hasattr(label, 'processed_image'):
                msg += "\n\nReason: No processed image data is attached to this preview."
            elif label.processed_image is None:
                msg += "\n\nReason: The processed image data is null."
            elif not isinstance(label.processed_image, QImage):
                msg += f"\n\nReason: The image data is not a QImage (found {type(label.processed_image)})."
            elif label.processed_image.isNull():
                msg += "\n\nReason: The image is empty or invalid."
                
            # Suggest a solution
            msg += "\n\nTry updating previews or verifying the input directory."
            
            # Show a helpful message dialog instead of just logging
            QMessageBox.information(self, "Preview Not Available", msg)

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
        # Print to stdout for immediate visibility
        print("\n============ START METHOD CALLED ============")
        print("Preparing to start processing with signal emission")
        LOGGER.debug("================== START BUTTON CLICKED ==================")
        LOGGER.debug("MainTab: Start button clicked.")
        
        # Verify that the button should be enabled based on state
        can_start = self._verify_start_button_state()
        if not can_start:
            error_msg = "Start button clicked but state verification shows it should be disabled!"
            LOGGER.error(error_msg)
            print(f"ERROR: {error_msg}")
            # Continue anyway since the user managed to click it
            print("Continuing despite verification failure...")
        
        # Get parent references through multiple approaches for debugging
        parent_obj = self.parent()
        parent_type = type(parent_obj).__name__
        LOGGER.debug(f"Parent object type: {parent_type}")
        print(f"Parent object type: {parent_type}")
        
        main_window_from_parent = cast(QObject, parent_obj)
        main_window_from_ref = self.main_window_ref  
        
        # Log IDs to verify they're the same object
        mw_parent_id = id(main_window_from_parent)
        mw_ref_id = id(main_window_from_ref)
        LOGGER.debug(f"main_window_from_parent id: {mw_parent_id}")
        LOGGER.debug(f"main_window_from_ref id: {mw_ref_id}")
        print(f"MainWindow from parent id: {mw_parent_id}")
        print(f"MainWindow from ref id: {mw_ref_id}")
        print(f"Are references to same object? {mw_parent_id == mw_ref_id}")
        
        # Check input directory through multiple approaches
        in_dir_from_parent = getattr(main_window_from_parent, 'in_dir', None)
        in_dir_from_ref = getattr(main_window_from_ref, 'in_dir', None)
        print(f"Input dir from parent: {in_dir_from_parent}")
        print(f"Input dir from ref: {in_dir_from_ref}")
        in_dir_from_edit = self.in_dir_edit.text()
        LOGGER.debug(f"in_dir_from_parent: {in_dir_from_parent}")
        LOGGER.debug(f"in_dir_from_ref: {in_dir_from_ref}")
        LOGGER.debug(f"in_dir_from_edit: {in_dir_from_edit}")
        
        # Use main_window_ref for consistency
        main_window = self.main_window_ref
        current_in_dir = getattr(main_window, 'in_dir', None)
        LOGGER.debug(f"Current input directory: {current_in_dir}, Output file: {self.out_file_path}")

        if not current_in_dir or not self.out_file_path:
            error_msg = f"Missing paths for processing: in_dir={current_in_dir}, out_file={self.out_file_path}"
            LOGGER.warning(error_msg)
            QMessageBox.warning(self, "Missing Paths", "Please select both input and output paths.")
            return

        # Check for files in input directory
        try:
            if current_in_dir and current_in_dir.is_dir():
                image_files = sorted([
                    f for f in current_in_dir.iterdir()
                    if f.suffix.lower() in [".png", ".jpg", ".jpeg", ".tif", ".tiff"]
                ])
                LOGGER.debug(f"Found {len(image_files)} image files in input directory")
                if not image_files:
                    LOGGER.warning("No image files found in the input directory")
                    QMessageBox.warning(self, "No Images Found", 
                                       f"No image files found in the selected directory:\n{current_in_dir}\n\n"
                                       "Please select a directory containing image files.")
                    return
            else:
                LOGGER.warning(f"Input directory invalid or doesn't exist: {current_in_dir}")
                QMessageBox.warning(self, "Invalid Directory", 
                                   "The selected input directory is invalid or doesn't exist.")
                return
        except Exception as e:
            LOGGER.exception(f"Error checking input directory: {e}")
            QMessageBox.critical(self, "Error", f"Error checking input directory: {e}")
            return

        # Get processing arguments
        LOGGER.debug("Gathering processing arguments...")
        args = self.get_processing_args()
        
        if args:
            # Deep verify the processing arguments
            self._deep_verify_args(args)
            
            LOGGER.info(f"Starting processing with args: {args}")
            
            # Update GUI state before emitting signal
            LOGGER.debug("Setting processing state to True")
            self.set_processing_state(True)
            
            LOGGER.debug("=== Emitting processing_started signal ===")
            # Check if main_window has the handler method (can't directly check connected slots in PyQt6)
            main_window = self.main_window_ref
            has_handler = hasattr(main_window, '_handle_processing')
            LOGGER.debug(f"MainWindow has processing handler method: {has_handler}")
            
            # Try direct connections first
            try:
                LOGGER.debug("Emitting processing_started signal with args")
                # Print detailed info for debugging
                print("\n===== EMITTING SIGNAL: processing_started =====")
                print(f"Signal args size: {len(args) if args else 0}")
                print(f"Args keys: {list(args.keys()) if args else 'None'}")
                print(f"In directory path: {args.get('in_dir')}")
                print(f"Out file path: {args.get('out_file')}")
                print(f"Encoder type: {args.get('encoder')}")
                
                # Check signal connection status
                receivers = self.processing_started.receivers()
                print(f"Signal has {receivers} receivers connected")
                if receivers == 0:
                    print("WARNING: No receivers connected to processing_started signal!")
                    LOGGER.error("No receivers connected to processing_started signal!")
                
                # Emit the signal
                self.processing_started.emit(args) # Emit signal with processing arguments
                print("Signal emission attempt completed")
                LOGGER.debug("Signal emission completed")
                
                # Wait a short time to see if the signal was processed
                LOGGER.debug("Waiting briefly to see if signal was handled...")
                # No need for an actual delay in Python
                
                # For visual confirmation in GUI that something is happening
                QMessageBox.information(self, "Processing Started", 
                                      "Processing has started. This dialog will close in 2 seconds...")
                # Close the dialog automatically after 2 seconds
                QTimer.singleShot(2000, lambda: None)
                
            except Exception as signal_error:
                LOGGER.exception(f"Error during signal emission: {signal_error}")
            
            # As a fallback, try direct method call if signal might not be working
            LOGGER.debug("Trying direct method call as additional fallback...")
            if hasattr(main_window, '_handle_processing'):
                try:
                    LOGGER.debug("Calling main_window._handle_processing directly")
                    main_window._handle_processing(args)
                except Exception as direct_call_error:
                    LOGGER.exception(f"Error during direct method call: {direct_call_error}")
            else:
                LOGGER.error("main_window does not have _handle_processing method")
        else:
            # Error message already shown by get_processing_args
            LOGGER.warning("Processing not started due to invalid arguments.")
            
        LOGGER.debug("================== START BUTTON PROCESSING COMPLETE ==================")
        
    def _verify_start_button_state(self) -> bool:
        """Verify that the start button should be enabled based on current state."""
        LOGGER.debug("Verifying start button state...")
        
        # Check input directory
        main_window = self.main_window_ref
        current_in_dir = getattr(main_window, 'in_dir', None)
        has_in_dir = bool(current_in_dir and current_in_dir.is_dir())
        LOGGER.debug(f"Has valid input directory: {has_in_dir}")
        
        # Check output file
        has_out_file = bool(self.out_file_path)
        LOGGER.debug(f"Has output file path: {has_out_file}")
        
        # Check encoder specific requirements
        current_encoder = self.encoder_combo.currentText()
        LOGGER.debug(f"Current encoder: {current_encoder}")
        
        encoder_ok = True
        if current_encoder == "RIFE":
            model_key = self.rife_model_combo.currentData()
            encoder_ok = bool(model_key)
            LOGGER.debug(f"RIFE model selected: {model_key}, valid: {encoder_ok}")
        
        # Final state check
        should_be_enabled = has_in_dir and has_out_file and encoder_ok and not self.is_processing
        LOGGER.debug(f"Start button should be enabled: {should_be_enabled}")
        
        # Compare with actual state
        actual_enabled = self.start_button.isEnabled()
        LOGGER.debug(f"Start button is actually enabled: {actual_enabled}")
        
        if should_be_enabled != actual_enabled:
            LOGGER.warning(f"Start button state mismatch! Should be: {should_be_enabled}, Is: {actual_enabled}")
        
        return should_be_enabled
        
    def _deep_verify_args(self, args: Dict[str, Any]) -> None:
        """Perform a deep verification of processing arguments for debugging."""
        LOGGER.debug("Deep verification of processing arguments...")
        
        # Check critical paths
        in_dir = args.get('in_dir')
        if in_dir:
            exists = in_dir.exists()
            is_dir = in_dir.is_dir() if exists else False
            LOGGER.debug(f"in_dir: {in_dir}, exists: {exists}, is_dir: {is_dir}")
            if exists and is_dir:
                # Check image files and dimensions
                self._check_input_directory_contents(in_dir)
        else:
            LOGGER.error("Missing required argument: in_dir")
            
        out_file = args.get('out_file')
        if out_file:
            out_dir = out_file.parent
            dir_exists = out_dir.exists()
            dir_writable = os.access(str(out_dir), os.W_OK) if dir_exists else False
            LOGGER.debug(f"out_file: {out_file}, dir_exists: {dir_exists}, dir_writable: {dir_writable}")
        else:
            LOGGER.error("Missing required argument: out_file")
            
        # Check encoder-specific arguments
        encoder = args.get('encoder')
        LOGGER.debug(f"encoder: {encoder}")
        
        if encoder == "RIFE":
            rife_model_key = args.get('rife_model_key')
            rife_model_path = args.get('rife_model_path')
            rife_exe_path = args.get('rife_exe_path')
            
            LOGGER.debug(f"rife_model_key: {rife_model_key}")
            LOGGER.debug(f"rife_model_path: {rife_model_path}")
            LOGGER.debug(f"rife_exe_path: {rife_exe_path}")
            
            if rife_exe_path:
                exe_exists = rife_exe_path.exists()
                exe_executable = os.access(str(rife_exe_path), os.X_OK) if exe_exists else False
                LOGGER.debug(f"rife_exe_path exists: {exe_exists}, executable: {exe_executable}")
            else:
                LOGGER.error("Missing required RIFE executable path")
                
        elif encoder == "FFmpeg":
            # Check FFmpeg specific arguments
            LOGGER.debug("Checking FFmpeg-specific arguments...")
            ffmpeg_args = args.get('ffmpeg_args')
            if ffmpeg_args:
                LOGGER.debug(f"FFmpeg arguments provided: {ffmpeg_args}")
                # Check for FFmpeg profile settings
                if 'profile' in ffmpeg_args:
                    profile_name = ffmpeg_args.get('profile')
                    LOGGER.debug(f"FFmpeg profile: {profile_name}")
                    
                # Check for quality settings
                if 'crf' in ffmpeg_args:
                    crf = ffmpeg_args.get('crf')
                    LOGGER.debug(f"FFmpeg CRF: {crf}")
                    
                if 'bitrate' in ffmpeg_args:
                    bitrate = ffmpeg_args.get('bitrate')
                    LOGGER.debug(f"FFmpeg bitrate: {bitrate}")
            else:
                LOGGER.warning("No FFmpeg arguments provided")
                # Try to generate a default FFmpeg command to verify integration
                self._debug_generate_ffmpeg_command(args)
                
        # Check crop rectangle if present
        crop_rect = args.get('crop_rect')
        if crop_rect:
            LOGGER.debug(f"crop_rect: {crop_rect}")
            # Validate dimensions
            try:
                x, y, w, h = crop_rect
                LOGGER.debug(f"Crop dimensions - x: {x}, y: {y}, width: {w}, height: {h}")
                if w <= 0 or h <= 0:
                    LOGGER.error(f"Invalid crop rectangle dimensions: width={w}, height={h}")
                else:
                    # Verify crop dimensions against actual image dimensions
                    self._verify_crop_against_images(in_dir, crop_rect)
                    
                    # Check how crop will be passed to FFmpeg
                    self._debug_check_ffmpeg_crop_integration(crop_rect)
            except (ValueError, TypeError) as e:
                LOGGER.error(f"Invalid crop rectangle format: {e}")
        else:
            LOGGER.debug("No crop rectangle specified")
            
        # Check other parameters that affect processing
        fps = args.get('fps')
        multiplier = args.get('multiplier')
        max_workers = args.get('max_workers')
        sanchez_enabled = args.get('sanchez_enabled')
        sanchez_resolution_km = args.get('sanchez_resolution_km')
        
        LOGGER.debug(f"fps: {fps}")
        LOGGER.debug(f"multiplier: {multiplier}")
        LOGGER.debug(f"max_workers: {max_workers}")
        LOGGER.debug(f"sanchez_enabled: {sanchez_enabled}")
        LOGGER.debug(f"sanchez_resolution_km: {sanchez_resolution_km}")
        
    def _check_input_directory_contents(self, in_dir: Path) -> None:
        """Check images in the input directory and report details for debugging."""
        try:
            image_files = sorted([
                f for f in in_dir.iterdir()
                if f.suffix.lower() in [".png", ".jpg", ".jpeg", ".tif", ".tiff"]
            ])
            
            LOGGER.debug(f"Found {len(image_files)} image files in {in_dir}")
            
            if not image_files:
                LOGGER.warning("No image files found in input directory")
                return
                
            # Sample the first, middle, and last image for dimensions
            sample_indices = [0]
            if len(image_files) > 2:
                sample_indices.append(len(image_files) // 2)
            if len(image_files) > 1:
                sample_indices.append(len(image_files) - 1)
                
            import numpy as np
            from PIL import Image
            
            sample_stats = []
            for idx in sample_indices:
                try:
                    img_path = image_files[idx]
                    img = Image.open(img_path)
                    img_array = np.array(img)
                    sample_stats.append({
                        "index": idx,
                        "filename": img_path.name,
                        "dimensions": img.size,
                        "shape": img_array.shape,
                        "dtype": str(img_array.dtype)
                    })
                except Exception as e:
                    LOGGER.error(f"Error analyzing image {image_files[idx]}: {e}")
                    
            LOGGER.debug(f"Sample image stats: {sample_stats}")
            
        except Exception as e:
            LOGGER.exception(f"Error checking input directory contents: {e}")
            
    def _verify_crop_against_images(self, in_dir: Path, crop_rect: tuple) -> None:
        """Verify that crop rectangle is valid for the images in the directory."""
        try:
            image_files = sorted([
                f for f in in_dir.iterdir()
                if f.suffix.lower() in [".png", ".jpg", ".jpeg", ".tif", ".tiff"]
            ])
            
            if not image_files:
                LOGGER.warning("No images found to verify crop against")
                return
                
            # Check the first image
            from PIL import Image
            
            img_path = image_files[0]
            img = Image.open(img_path)
            img_width, img_height = img.size
            
            x, y, w, h = crop_rect
            
            # Check if crop is within image bounds
            crop_right = x + w
            crop_bottom = y + h
            
            within_bounds = (0 <= x < img_width and 
                             0 <= y < img_height and
                             0 < crop_right <= img_width and
                             0 < crop_bottom <= img_height)
                             
            LOGGER.debug(f"Image dimensions: {img_width}x{img_height}")
            LOGGER.debug(f"Crop rectangle: ({x}, {y}, {w}, {h})")
            LOGGER.debug(f"Crop bottom-right: ({crop_right}, {crop_bottom})")
            LOGGER.debug(f"Crop within bounds: {within_bounds}")
            
            if not within_bounds:
                LOGGER.warning(f"Crop rectangle ({x}, {y}, {w}, {h}) exceeds image dimensions ({img_width}x{img_height})")
                
            # Calculate percentages for context
            crop_width_percent = (w / img_width) * 100
            crop_height_percent = (h / img_height) * 100
            crop_area_percent = (w * h) / (img_width * img_height) * 100
            
            LOGGER.debug(f"Crop width: {w}px ({crop_width_percent:.1f}% of image width)")
            LOGGER.debug(f"Crop height: {h}px ({crop_height_percent:.1f}% of image height)")
            LOGGER.debug(f"Crop area: {w*h}px² ({crop_area_percent:.1f}% of image area)")
            
        except Exception as e:
            LOGGER.exception(f"Error verifying crop against images: {e}")
            
    def _debug_check_ffmpeg_crop_integration(self, crop_rect: tuple) -> None:
        """Debug how crop rectangle would be passed to FFmpeg."""
        try:
            x, y, w, h = crop_rect
            
            # Check if FFmpeg settings tab is accessible
            main_window = self.main_window_ref
            ffmpeg_tab = getattr(main_window, 'ffmpeg_tab', None)
            
            if ffmpeg_tab:
                LOGGER.debug("FFmpeg settings tab found, checking for crop integration")
                # TODO: Add actual checks for FFmpeg tab handling of crop rectangle
            else:
                LOGGER.debug("FFmpeg settings tab not accessible for crop integration check")
            
            # Simulate FFmpeg crop filter string
            crop_filter = f"crop={w}:{h}:{x}:{y}"
            LOGGER.debug(f"FFmpeg crop filter would be: {crop_filter}")
            
            # Check for potential issues with odd dimensions (h264/h265 requirement)
            has_odd_dimensions = (w % 2 != 0 or h % 2 != 0)
            if has_odd_dimensions:
                LOGGER.warning(f"Crop dimensions ({w}x{h}) have odd values, which may cause issues with some codecs")
                # Suggest fixed dimensions
                fixed_w = w + (1 if w % 2 != 0 else 0)
                fixed_h = h + (1 if h % 2 != 0 else 0)
                LOGGER.debug(f"Suggested fixed dimensions: {fixed_w}x{fixed_h}")
                
        except Exception as e:
            LOGGER.exception(f"Error checking FFmpeg crop integration: {e}")
            
    def _debug_generate_ffmpeg_command(self, args: Dict[str, Any]) -> None:
        """Generate a sample FFmpeg command for debugging."""
        try:
            from goesvfi.pipeline.ffmpeg_builder import FFmpegCommandBuilder
            
            in_dir = args.get('in_dir')
            out_file = args.get('out_file')
            crop_rect = args.get('crop_rect')
            fps = args.get('fps', 60)
            
            if not in_dir or not out_file:
                LOGGER.warning("Cannot generate FFmpeg command without input directory and output file")
                return
                
            # Create a dummy input file path
            input_path = in_dir / "dummy_input.mp4"
            output_path = out_file
            
            # Build a sample FFmpeg command
            builder = FFmpegCommandBuilder()
            builder.set_input(input_path)
            builder.set_output(output_path)
            builder.set_encoder("Software x264")
            builder.set_crf(20)
            builder.set_pix_fmt("yuv420p")
            
            command = builder.build()
            
            # Add crop and fps filters that would be used
            crop_fps_filters = []
            if crop_rect:
                x, y, w, h = crop_rect
                crop_fps_filters.append(f"crop={w}:{h}:{x}:{y}")
            crop_fps_filters.append(f"fps={fps}")
            
            # Insert filters before output path in command
            if crop_fps_filters:
                filter_str = ",".join(crop_fps_filters)
                filter_idx = command.index(str(output_path))
                command.insert(filter_idx, "-filter:v")
                command.insert(filter_idx + 1, filter_str)
            
            LOGGER.debug(f"Sample FFmpeg command with crop/fps: {' '.join(command)}")
            
        except Exception as e:
            LOGGER.exception(f"Error generating sample FFmpeg command: {e}")
            


    # --- Worker Interaction ---
    # These methods handle signals from the VfiWorker thread

    def set_processing_state(self, is_processing: bool) -> None:
        """Update UI elements based on processing state."""
        self.is_processing = is_processing
        
        # Update both buttons via _update_start_button_state
        # This will set the text, style, and enabled state
        self._update_start_button_state()
        
        # Disable relevant controls during processing
        self.in_dir_edit.setEnabled(not is_processing)
        self.out_file_edit.setEnabled(not is_processing)
        
        # Find browse buttons and disable them
        in_browse_button = self.findChild(QPushButton, "browse_button") # Assuming only one for input for now
        out_browse_button = self.findChildren(QPushButton, "browse_button")[1] # Assuming second is output
        if in_browse_button: in_browse_button.setEnabled(not is_processing)
        if out_browse_button: out_browse_button.setEnabled(not is_processing)
        
        # Update ViewModel state
        if is_processing:
            self.processing_vm.start_processing() # Call correct ViewModel method
            
            # Show processing confirmation
            print("\n====== PROCESSING STARTED ======")
            LOGGER.info("Processing started - UI updated to processing state")
        else:
            # Cancel processing in ViewModel
            self.processing_vm.cancel_processing() # Call correct ViewModel method
            
            print("\n====== PROCESSING STOPPED ======")
            LOGGER.info("Processing stopped - UI updated to ready state")


    def _reset_start_button(self) -> None:
        """Resets the start button text and enables it."""
        self.start_button.setText("Start Video Interpolation")
        self.set_processing_state(False)
        self._update_start_button_state() # Re-evaluate if it should be enabled


    def _start_button_mouse_press(self, event: QMouseEvent) -> None:
        """Direct mouse event handler for start button."""
        # Always call the original event handler first
        QPushButton.mousePressEvent(self.start_button, event)
        
        print("START BUTTON MOUSE PRESS DETECTED")
        LOGGER.debug("START BUTTON MOUSE PRESS DETECTED - DIRECT EVENT HANDLER")
        
        # Manually handle the press if it's a left click
        if event.button() == Qt.MouseButton.LeftButton:
            print(f"LEFT CLICK ON START BUTTON: enabled={self.start_button.isEnabled()}")
            LOGGER.debug(f"LEFT CLICK ON START BUTTON: enabled={self.start_button.isEnabled()}")
            
            # Force the _start method to be called regardless of enabled state
            # This is for debugging - in production we'd respect the enabled state
            QTimer.singleShot(200, self._direct_start)
    
    def _generate_timestamped_output_path(self, base_dir=None, base_name=None):
        """Generate a fresh timestamped output path for uniqueness across runs.
        
        Args:
            base_dir: Optional directory to use (defaults to input dir's parent)
            base_name: Optional base name (defaults to input dir's name)
            
        Returns:
            Path object with timestamped output file path
        """
        # Import inside function to avoid circular imports
        from datetime import datetime
        
        # Get the main window reference
        main_window = self.main_window_ref
        
        # Get input directory to use as base if not specified
        if not base_dir or not base_name:
            current_in_dir = getattr(main_window, 'in_dir', None)
            if current_in_dir and current_in_dir.is_dir():
                if not base_dir:
                    base_dir = current_in_dir.parent
                if not base_name:
                    base_name = current_in_dir.name
        
        # Use current directory and generic name if still not set
        if not base_dir:
            import os
            base_dir = Path(os.getcwd())
        if not base_name:
            base_name = "output"
            
        # Generate timestamp and create path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return base_dir / f"{base_name}_output_{timestamp}.mp4"
    
    def _direct_start_handler(self) -> None:
        """New simplified handler for the start button that directly calls main processing code.
        
        This handler is more reliable as it avoids complex signal connections and
        directly executes the processing workflow.
        """
        # Print to stdout for immediate visibility
        print("\n===== DIRECT START HANDLER CALLED =====")
        LOGGER.info("Enhanced start button handler called")
        
        # Always generate a fresh timestamped output path for each run
        # If one already exists, parse it to extract the base parts
        base_dir = None
        base_name = None
        
        if self.out_file_path:
            # Extract directory and basename from existing path
            base_dir = self.out_file_path.parent
            
            # Try to extract the original name before the timestamp
            import re
            filename = self.out_file_path.stem  # Get filename without extension
            # Check if it matches pattern like "name_output_20230405_123456"
            match = re.match(r"(.+?)_output_\d{8}_\d{6}", filename)
            if match:
                # Extract the original name
                base_name = match.group(1)
            else:
                # If no timestamp found, try to remove _output suffix
                if "_output" in filename:
                    base_name = filename.split("_output")[0]
                else:
                    # Just use the whole name as base
                    base_name = filename
        
        # Generate fresh path
        fresh_output_path = self._generate_timestamped_output_path(base_dir, base_name)
        self.out_file_path = fresh_output_path
        self.out_file_edit.setText(str(fresh_output_path))
        print(f"Fresh timestamped output path: {fresh_output_path}")
        
        # Show notification if status bar exists
        main_window = self.main_window_ref
        if hasattr(main_window, 'status_bar'):
            main_window.status_bar.showMessage(f"Using output file: {fresh_output_path.name}", 5000)
            
        # If somehow we still don't have a valid output path (very unlikely at this point)
        if not self.out_file_path:
            print("No output file selected - auto-generating default output path")
            
            # Get input directory from main window
            main_window = self.main_window_ref
            current_in_dir = getattr(main_window, 'in_dir', None)
            
            if current_in_dir and current_in_dir.is_dir():
                # Create a default output file path with timestamp to ensure uniqueness
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                default_output = current_in_dir.parent / f"{current_in_dir.name}_output_{timestamp}.mp4"
                self.out_file_path = default_output
                self.out_file_edit.setText(str(default_output))
                print(f"Timestamped output file set to: {default_output}")
                
                # Show a small notification in the status bar (don't block with a dialog)
                if hasattr(main_window, 'status_bar'):
                    main_window.status_bar.showMessage(f"Auto-generated output file: {default_output.name}", 5000)
            else:
                print("Can't create default output - no input directory")
                QMessageBox.warning(self, "Input Directory Required", 
                                  "Please select a valid input directory first.")
                return
                
        # Get current state from main window
        main_window = self.main_window_ref
        current_in_dir = getattr(main_window, 'in_dir', None)
        
        # Verify we have an input directory
        if not current_in_dir or not current_in_dir.is_dir():
            print("No valid input directory selected")
            QMessageBox.warning(self, "Input Directory Required", 
                               "Please select a valid input directory containing images.")
            return
            
        # Check for images in input directory
        try:
            image_files = sorted([
                f for f in current_in_dir.iterdir()
                if f.suffix.lower() in [".png", ".jpg", ".jpeg", ".tif", ".tiff"]
            ])
            
            if not image_files:
                print(f"No image files found in {current_in_dir}")
                QMessageBox.warning(self, "No Images Found", 
                                   f"No image files found in {current_in_dir}.\nPlease select a directory with images.")
                return
                
            print(f"Found {len(image_files)} image files in {current_in_dir}")
        except Exception as e:
            print(f"Error checking for images: {e}")
            QMessageBox.critical(self, "Error", f"Error checking input directory: {e}")
            return
        
        # Gather processing arguments
        args = self.get_processing_args()
        if not args:
            print("Failed to generate processing arguments")
            return  # Error message already shown by get_processing_args
        
        # Update UI to show processing started
        self.set_processing_state(True)
        
        # Show processing confirmation to user
        QMessageBox.information(self, "Processing Started", 
                               f"Starting video processing with {len(image_files)} images.\n\n"
                               f"Input: {current_in_dir}\n"
                               f"Output: {self.out_file_path}")
        
        # Trigger processing via direct MainWindow method call
        try:
            print("\n===== STARTING PROCESSING =====")
            LOGGER.info("Starting processing via direct handler")
            
            # Attempt direct emit of signal first
            self.processing_started.emit(args)
            
            # Fallback to direct method call if needed
            if hasattr(main_window, '_handle_processing'):
                print("Calling main_window._handle_processing directly as fallback")
                main_window._handle_processing(args)
                
            print("Processing started successfully")
                
        except Exception as e:
            print(f"ERROR starting processing: {e}")
            LOGGER.exception("Error in direct start handler")
            self.set_processing_state(False)  # Reset UI state
            
            # Show detailed error to user
            error_details = f"An error occurred: {e}\n\n"
            error_details += f"Input dir: {current_in_dir}\n"
            error_details += f"Output file: {self.out_file_path}\n"
            
            QMessageBox.critical(self, "Error Starting Process", error_details)
    
    def _direct_start(self) -> None:
        """Original direct handler for start button click."""
        # Print to stdout for immediate visibility
        print("\n===== START BUTTON CLICKED - DIRECT START HANDLER =====")
        LOGGER.debug("Start button clicked - _direct_start called")
        
        # Check if conditions are met for starting processing
        main_window = self.main_window_ref
        current_in_dir = getattr(main_window, 'in_dir', None)
        has_in_dir = bool(current_in_dir and current_in_dir.is_dir())
        has_out_file = bool(self.out_file_path)
        
        # Log the state for debugging - both to log and stdout
        debug_msg = f"Start conditions: has_in_dir={has_in_dir}, has_out_file={has_out_file}"
        print(debug_msg)
        LOGGER.debug(debug_msg)
        
        # Debug the reference chains
        print(f"MainWindow reference exists: {main_window is not None}")
        print(f"Input directory from MainWindow: {current_in_dir}")
        print(f"Output file path: {self.out_file_path}")
        
        if has_in_dir and has_out_file:
            # Call the actual start method with trace
            print("All conditions met - calling _start() method")
            try:
                self._start()
                print("_start() method completed")
            except Exception as e:
                print(f"ERROR in _start() method: {e}")
                LOGGER.exception("Error in _start() method")
                # Show error to user
                QMessageBox.critical(self, "Error Starting Process", 
                                    f"An error occurred when starting the process: {e}")
        else:
            # Show a message to the user about what's missing
            error_msg = "Cannot start processing. "
            if not has_in_dir:
                error_msg += "Please select an input directory. "
            if not has_out_file:
                error_msg += "Please select an output file."
                
            LOGGER.warning(f"Start button clicked but missing requirements: {error_msg}")
            print(f"Missing requirements: {error_msg}")
            QMessageBox.warning(self, "Missing Requirements", error_msg)
            
    def _diagnose_start_button(self) -> None:
        """Debug the start button state."""
        LOGGER.debug("----- START BUTTON DIAGNOSIS -----")
        
        # Check input directory
        main_window = self.main_window_ref
        current_in_dir = getattr(main_window, 'in_dir', None)
        out_file = self.out_file_path
        
        LOGGER.debug(f"Input dir exists: {current_in_dir is not None}")
        if current_in_dir:
            LOGGER.debug(f"Input dir path: {current_in_dir}")
            LOGGER.debug(f"Input dir is directory: {current_in_dir.is_dir() if current_in_dir else False}")
            
        LOGGER.debug(f"Output file exists: {out_file is not None}")
        if out_file:
            LOGGER.debug(f"Output file path: {out_file}")
            
        # Check RIFE model
        encoder = self.encoder_combo.currentText()
        LOGGER.debug(f"Encoder: {encoder}")
        
        if encoder == "RIFE":
            model_key = self.rife_model_combo.currentData()
            LOGGER.debug(f"RIFE model key: {model_key}")
            
        LOGGER.debug(f"Is processing: {self.is_processing}")
        
        # Check field values
        for key, widget in [
            ("in_dir_edit", self.in_dir_edit),
            ("out_file_edit", self.out_file_edit),
            ("fps_spinbox", self.fps_spinbox),
            ("multiplier_spinbox", self.multiplier_spinbox),
            ("max_workers_spinbox", self.max_workers_spinbox),
            ("encoder_combo", self.encoder_combo),
            ("rife_model_combo", self.rife_model_combo),
        ]:
            try:
                if hasattr(widget, "text"):
                    LOGGER.debug(f"{key} text: {widget.text()}")
                elif hasattr(widget, "currentText"):
                    LOGGER.debug(f"{key} currentText: {widget.currentText()}")
                elif hasattr(widget, "value"):
                    LOGGER.debug(f"{key} value: {widget.value()}")
            except Exception as e:
                LOGGER.error(f"Error getting value for {key}: {e}")
                
        LOGGER.debug("----------------------------------")
            
    def _debug_start_button_clicked(self) -> None:
        """Debug handler added directly to the start button in setup_ui."""
        print("START BUTTON CLICKED - DEBUG HANDLER")
        LOGGER.debug("START BUTTON CLICKED - DEBUG HANDLER TRIGGERED")
        # Call the actual handler directly to bypass any signal issues
        self._direct_start()
        
    def _update_start_button_state(self) -> None:
        """Enable/disable start button based on paths and RIFE model availability."""
        main_window = self.main_window_ref # Use stored reference for consistency
        current_in_dir = getattr(main_window, 'in_dir', None)
        
        # For simplicity, only require input directory - we can auto-generate output path
        # Original: has_paths = current_in_dir and self.out_file_path
        has_paths = bool(current_in_dir)  # Only input directory is required
        LOGGER.debug(f"Start button check: has_paths={has_paths}, in_dir={current_in_dir}, out_file={self.out_file_path}")
        
        # Check RIFE model only if RIFE is selected encoder
        rife_ok = True
        if self.encoder_combo.currentText() == "RIFE":
            rife_ok = bool(self.rife_model_combo.currentData()) # Check if a valid model is selected
            LOGGER.debug(f"Start button check: RIFE selected, model_ok={rife_ok}")

        can_start = bool(has_paths and rife_ok and not self.is_processing)
        LOGGER.debug(f"Start button should be enabled: {can_start}")
        
        # Update button state
        self.start_button.setEnabled(can_start)
        
        # Update button text and style
        if self.is_processing:
            # Processing mode
            self.start_button.setText("Cancel")
            self.start_button.setStyleSheet("""
                QPushButton#start_button {
                    background-color: #f44336; 
                    color: white;
                    font-weight: bold;
                    font-size: 16px;
                    border-radius: 5px;
                }
            """)
        else:
            # Ready or disabled mode
            if can_start:
                self.start_button.setText("START")
                self.start_button.setStyleSheet("""
                    QPushButton#start_button {
                        background-color: #4CAF50;
                        color: white;
                        font-weight: bold;
                        font-size: 16px;
                        border-radius: 5px;
                        padding: 8px 16px;
                    }
                    QPushButton#start_button:hover {
                        background-color: #45a049;
                    }
                    QPushButton#start_button:pressed {
                        background-color: #3e8e41;
                    }
                """)
            else:
                self.start_button.setText("START")
                self.start_button.setStyleSheet("""
                    QPushButton#start_button {
                        background-color: #9E9E9E;
                        color: #F5F5F5;
                        font-weight: bold;
                        font-size: 16px;
                        border-radius: 5px;
                        padding: 8px 16px;
                    }
                """)
                
        # Print debug info about button state
        LOGGER.debug(f"Start button enabled: {self.start_button.isEnabled()}")


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
        LOGGER.debug("Gathering processing arguments...")
        
        # Try multiple approaches to get main_window reference
        main_window = self.main_window_ref  # Prefer using the stored reference
        if not main_window:
            LOGGER.warning("main_window_ref is None, falling back to parent()")
            main_window = cast(QObject, self.parent())
            
        # Fetch critical parameters with logging
        current_in_dir = getattr(main_window, 'in_dir', None)
        LOGGER.debug(f"Input directory from main_window: {current_in_dir}")
        current_crop_rect_mw = getattr(main_window, 'current_crop_rect', None)
        LOGGER.debug(f"Crop rect from main_window: {current_crop_rect_mw}")
        LOGGER.debug(f"Output file path: {self.out_file_path}")

        # Verify input directory
        if not current_in_dir:
            error_msg = "Input directory not selected."
            LOGGER.error(error_msg)
            QMessageBox.critical(self, "Error", error_msg)
            return None
            
        # Verify input directory exists and is valid
        if not current_in_dir.exists() or not current_in_dir.is_dir():
            error_msg = f"Input directory does not exist or is not a directory: {current_in_dir}"
            LOGGER.error(error_msg)
            QMessageBox.critical(self, "Error", error_msg)
            return None
            
        # Verify output file
        if not self.out_file_path:
            error_msg = "Output file not selected."
            LOGGER.error(error_msg)
            QMessageBox.critical(self, "Error", error_msg)
            return None
            
        # Get and validate encoder parameters
        encoder = self.encoder_combo.currentText()
        LOGGER.debug(f"Selected encoder: {encoder}")
        rife_model_key = self.rife_model_combo.currentData()
        LOGGER.debug(f"Selected RIFE model: {rife_model_key}")

        if encoder == "RIFE" and not rife_model_key:
            error_msg = "No RIFE model selected."
            LOGGER.error(error_msg)
            QMessageBox.critical(self, "Error", error_msg)
            return None
            
        # Ensure output directory exists
        if self.out_file_path:
            out_dir = self.out_file_path.parent
            if not out_dir.exists():
                try:
                    LOGGER.info(f"Creating output directory: {out_dir}")
                    out_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    error_msg = f"Could not create output directory: {e}"
                    LOGGER.error(error_msg)
                    QMessageBox.critical(self, "Error", error_msg)
                    return None

        # Create arguments dictionary
        LOGGER.debug("Building arguments dictionary...")
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
        }
        
        # Add FFmpeg specific args if needed
        if encoder == "FFmpeg":
            # Try to get FFmpeg tab from MainWindow to get its settings
            ffmpeg_tab = getattr(main_window, 'ffmpeg_tab', None)
            if ffmpeg_tab:
                try:
                    # Get FFmpeg settings from tab (method name may vary)
                    ffmpeg_args = getattr(ffmpeg_tab, 'get_ffmpeg_args', lambda: {})()
                    args["ffmpeg_args"] = ffmpeg_args
                    LOGGER.debug(f"Added FFmpeg args from ffmpeg_tab: {ffmpeg_args}")
                except Exception as e:
                    LOGGER.exception(f"Error getting FFmpeg args: {e}")
                    args["ffmpeg_args"] = {}
            else:
                LOGGER.warning("FFmpeg selected but ffmpeg_tab not found in MainWindow")
                args["ffmpeg_args"] = {}
        else:
            args["ffmpeg_args"] = None
            
        LOGGER.debug(f"Processing arguments gathered: {args}")
        return args


    def set_input_directory(self, directory: Path | str) -> None:
        """Public method to set the input directory text edit."""
        # This might be called from MainWindow or sorter tabs
        self.in_dir_edit.setText(str(directory)) # Triggers _on_in_dir_changed


    def load_settings(self) -> None:
        """Load settings relevant to the MainTab from QSettings."""
        LOGGER.debug("MainTab: Loading settings...")
        
        # Debug settings storage
        org_name = self.settings.organizationName()
        app_name = self.settings.applicationName()
        filename = self.settings.fileName()
        LOGGER.debug(f"QSettings details: org={org_name}, app={app_name}, file={filename}")
        
        # List all available keys for debugging
        all_keys = self.settings.allKeys()
        LOGGER.debug(f"Available settings keys: {all_keys}")
        
        main_window = cast(QObject, self.parent())

        try:
            # --- Load Input/Output ---
            # Load input dir and set it in MainWindow
            LOGGER.debug("Loading input directory path...")
            # Force a sync to ensure we're reading the latest settings from disk
            self.settings.sync()
            
            # Attempt to load input directory path with debug logging
            try:
                in_dir_str = self.settings.value("paths/inputDirectory", "", type=str)
                LOGGER.debug(f"Raw input directory from settings: '{in_dir_str}'")
                loaded_in_dir = None
                
                if in_dir_str:
                    try:
                        in_dir_path = Path(in_dir_str)
                        # Check if path exists and is a directory
                        exists = in_dir_path.exists()
                        is_dir = in_dir_path.is_dir() if exists else False
                        LOGGER.debug(f"Input path exists: {exists}, is directory: {is_dir}")
                        
                        if exists and is_dir:
                            # Path exists and is a directory - use it
                            loaded_in_dir = in_dir_path
                            LOGGER.info(f"Loaded valid input directory: {in_dir_str}")
                        else:
                            # Try to find the directory with the same name in common locations
                            LOGGER.warning(f"Saved input directory does not exist: {in_dir_str}")
                            LOGGER.debug("Will check if directory exists in other locations...")
                            
                            # Get just the directory name (without parent directories)
                            dir_name = in_dir_path.name
                            
                            # Check common locations
                            potential_locations = [
                                Path.home() / "Downloads" / dir_name,
                                Path.home() / "Documents" / dir_name,
                                Path.home() / "Desktop" / dir_name,
                                Path.cwd() / dir_name
                            ]
                            
                            for potential_path in potential_locations:
                                LOGGER.debug(f"Checking potential location: {potential_path}")
                                if potential_path.exists() and potential_path.is_dir():
                                    LOGGER.info(f"Found matching directory in alternate location: {potential_path}")
                                    loaded_in_dir = potential_path
                                    break
                    except Exception as e:
                        LOGGER.error(f"Error loading input directory path: {e}")
                else:
                    LOGGER.debug("No input directory string in settings")
            except Exception as e:
                LOGGER.error(f"Error accessing input directory setting: {e}")
                loaded_in_dir = None
            
            # Update UI with loaded directory
            LOGGER.debug(f"Final loaded input directory: {loaded_in_dir}")
            if hasattr(main_window, 'set_in_dir'):
                # Always call set_in_dir to ensure proper UI state, even if path is None
                main_window.set_in_dir(loaded_in_dir) # Set state in MainWindow
                
                # Update local text field
                if loaded_in_dir:
                    self.in_dir_edit.setText(str(loaded_in_dir))
                    LOGGER.info(f"Set input directory in UI: {loaded_in_dir}")
                else:
                    self.in_dir_edit.setText("")
                    LOGGER.debug("Cleared input directory in UI (no valid directory found)")
            else:
                LOGGER.error("Parent does not have set_in_dir method")

            # Load output file (still managed locally in MainTab)
            LOGGER.debug("Loading output file path...")
            out_file_str = self.settings.value("paths/outputFile", "", type=str)
            LOGGER.debug(f"Raw output file from settings: '{out_file_str}'")
            
            if out_file_str:
                try:
                    out_file_path = Path(out_file_str)
                    # Check if parent directory exists (file itself may not exist yet)
                    parent_exists = out_file_path.parent.exists() if out_file_path.parent != Path() else True
                    
                    if parent_exists:
                        # Parent directory exists - use this path
                        LOGGER.info(f"Loaded output file with valid parent directory: {out_file_str}")
                        self.out_file_edit.setText(str(out_file_path))  # Triggers _on_out_file_changed -> sets self.out_file_path
                    else:
                        # If parent directory doesn't exist, try to generate a new path
                        LOGGER.warning(f"Parent directory for output file doesn't exist: {out_file_path.parent}")
                        
                        # Use output file name but in Downloads directory
                        new_path = Path.home() / "Downloads" / out_file_path.name
                        LOGGER.info(f"Generated alternative output path: {new_path}")
                        self.out_file_edit.setText(str(new_path))  # Use alternative path
                        
                except Exception as e:
                    LOGGER.error(f"Error loading output file path: {e}")
                    self.out_file_path = None
            else:
                self.out_file_path = None  # Ensure state is None if empty
                self.out_file_edit.setText("")  # Clear the text field
                LOGGER.debug("No output file string in settings")

            # --- Load Processing Settings ---
            LOGGER.debug("Loading processing settings...")
            fps_value = self.settings.value("processing/fps", 60, type=int)
            LOGGER.debug(f"Setting FPS: {fps_value}")
            self.fps_spinbox.setValue(fps_value)
            
            multiplier_value = self.settings.value("processing/multiplier", 2, type=int)
            LOGGER.debug(f"Setting multiplier: {multiplier_value}")
            self.mid_count_spinbox.setValue(multiplier_value)
            
            cpu_cores = os.cpu_count()
            default_workers = max(1, cpu_cores // 2) if cpu_cores else 1
            max_workers_value = self.settings.value("processing/maxWorkers", default_workers, type=int)
            LOGGER.debug(f"Setting max workers: {max_workers_value} (default was {default_workers})")
            self.max_workers_spinbox.setValue(max_workers_value)
            
            encoder_value = self.settings.value("processing/encoder", "RIFE", type=str)
            LOGGER.debug(f"Setting encoder: {encoder_value}")
            self.encoder_combo.setCurrentText(encoder_value)

            # --- Load RIFE Options ---
            LOGGER.debug("Loading RIFE options...")
            # self.rife_model_combo requires models to be populated first, handled in _post_init_setup -> _populate_models
            
            # Carefully handle boolean values which can sometimes load incorrectly
            tile_enabled_raw = self.settings.value("rife/tilingEnabled", False) 
            # Convert to proper boolean - QSettings can return strings "true"/"false" or QVariant
            tile_enabled = False
            if isinstance(tile_enabled_raw, bool):
                tile_enabled = tile_enabled_raw
            elif isinstance(tile_enabled_raw, str):
                tile_enabled = tile_enabled_raw.lower() == 'true'
            else:
                tile_enabled = bool(tile_enabled_raw)
            LOGGER.debug(f"Setting tiling enabled: {tile_enabled} (raw value: {tile_enabled_raw}, type: {type(tile_enabled_raw)})")
            self.rife_tile_checkbox.setChecked(tile_enabled)
            
            tile_size_value = self.settings.value("rife/tileSize", 256, type=int)
            LOGGER.debug(f"Setting tile size: {tile_size_value}")
            self.rife_tile_size_spinbox.setValue(tile_size_value)
            
            # Handle UHD mode boolean
            uhd_mode_raw = self.settings.value("rife/uhdMode", False)
            uhd_mode = False
            if isinstance(uhd_mode_raw, bool):
                uhd_mode = uhd_mode_raw
            elif isinstance(uhd_mode_raw, str):
                uhd_mode = uhd_mode_raw.lower() == 'true'
            else:
                uhd_mode = bool(uhd_mode_raw)
            LOGGER.debug(f"Setting UHD mode: {uhd_mode} (raw value: {uhd_mode_raw}, type: {type(uhd_mode_raw)})")
            self.rife_uhd_checkbox.setChecked(uhd_mode)
            
            thread_spec_value = self.settings.value("rife/threadSpec", "", type=str)
            LOGGER.debug(f"Setting thread spec: '{thread_spec_value}'")
            self.rife_thread_spec_edit.setText(thread_spec_value)
            
            # Handle TTA spatial boolean
            tta_spatial_raw = self.settings.value("rife/ttaSpatial", False)
            tta_spatial = False
            if isinstance(tta_spatial_raw, bool):
                tta_spatial = tta_spatial_raw
            elif isinstance(tta_spatial_raw, str):
                tta_spatial = tta_spatial_raw.lower() == 'true'
            else:
                tta_spatial = bool(tta_spatial_raw)
            LOGGER.debug(f"Setting TTA spatial: {tta_spatial} (raw value: {tta_spatial_raw}, type: {type(tta_spatial_raw)})")
            self.rife_tta_spatial_checkbox.setChecked(tta_spatial)
            
            # Handle TTA temporal boolean
            tta_temporal_raw = self.settings.value("rife/ttaTemporal", False)
            tta_temporal = False
            if isinstance(tta_temporal_raw, bool):
                tta_temporal = tta_temporal_raw
            elif isinstance(tta_temporal_raw, str):
                tta_temporal = tta_temporal_raw.lower() == 'true'
            else:
                tta_temporal = bool(tta_temporal_raw)
            LOGGER.debug(f"Setting TTA temporal: {tta_temporal} (raw value: {tta_temporal_raw}, type: {type(tta_temporal_raw)})")
            self.rife_tta_temporal_checkbox.setChecked(tta_temporal)

            # --- Load Sanchez Options ---
            LOGGER.debug("Loading Sanchez options...")
            
            # Handle false color boolean
            false_color_raw = self.settings.value("sanchez/falseColorEnabled", False)
            false_color = False
            if isinstance(false_color_raw, bool):
                false_color = false_color_raw
            elif isinstance(false_color_raw, str):
                false_color = false_color_raw.lower() == 'true'
            else:
                false_color = bool(false_color_raw)
            LOGGER.debug(f"Setting false color: {false_color} (raw value: {false_color_raw}, type: {type(false_color_raw)})")
            self.sanchez_false_colour_checkbox.setChecked(false_color)
            
            res_km_value = self.settings.value("sanchez/resolutionKm", "4", type=str)
            LOGGER.debug(f"Setting resolution km: '{res_km_value}'")
            # Check if the value exists in the combo box items
            index = self.sanchez_res_combo.findText(res_km_value)
            if index >= 0:
                self.sanchez_res_combo.setCurrentText(res_km_value)
            else:
                LOGGER.warning(f"Resolution value '{res_km_value}' not found in combo box, using default")

            # --- Load Crop State and set it in MainWindow ---
            LOGGER.debug("Loading crop rectangle...")
            # Attempt to load crop rectangle with enhanced error handling
            try:
                crop_rect_str = self.settings.value("preview/cropRectangle", "", type=str)
                LOGGER.debug(f"Raw crop rectangle from settings: '{crop_rect_str}'")
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
                else:
                    LOGGER.debug("No crop rectangle string in settings")
            except Exception as e:
                LOGGER.error(f"Error accessing crop rectangle setting: {e}")
                loaded_crop_rect = None

            LOGGER.debug(f"Final loaded crop rectangle: {loaded_crop_rect}")
            if hasattr(main_window, 'set_crop_rect'):
                main_window.set_crop_rect(loaded_crop_rect) # Set state in MainWindow
                LOGGER.debug(f"Crop rectangle set in MainWindow: {loaded_crop_rect}")
            else:
                LOGGER.error("Parent does not have set_crop_rect method")

            # Update UI states based on loaded settings
            LOGGER.debug("Updating UI elements based on loaded settings...")
            self._update_rife_ui_elements() # Handles model combo based on loaded encoder
            self._update_start_button_state()
            self._update_crop_buttons_state()
            self._update_rife_options_state(self.encoder_combo.currentText())
            self._update_sanchez_options_state(self.encoder_combo.currentText())
            self._toggle_tile_size_enabled(self.rife_tile_checkbox.isChecked())

            # Trigger preview update via MainWindow's signal AFTER loading settings
            LOGGER.debug("Triggering preview update after settings load")
            self.main_window_preview_signal.emit()

            LOGGER.info("MainTab: Settings loaded successfully.")
            
        except Exception as e:
            LOGGER.exception(f"Error loading settings: {e}")
            # Continue without failing - don't crash the app if settings loading fails


    def save_settings(self) -> None:
        """Save settings relevant to the MainTab to QSettings."""
        LOGGER.debug("MainTab: Saving settings...")
        
        # Debug settings storage before saving
        org_name = self.settings.organizationName()
        app_name = self.settings.applicationName()
        filename = self.settings.fileName()
        LOGGER.debug(f"QSettings save details: org={org_name}, app={app_name}, file={filename}")
        
        main_window = cast(QObject, self.parent())

        try:
            # --- Save Paths ---
            LOGGER.debug("Saving path settings...")
            
            # First, save directly from the text field - this ensures even the most recent changes are saved
            # even if they haven't been processed by MainWindow yet
            in_dir_text = self.in_dir_edit.text().strip()
            if in_dir_text:
                try:
                    text_dir_path = Path(in_dir_text)
                    if text_dir_path.exists() and text_dir_path.is_dir():
                        LOGGER.debug(f"Saving input directory from text field: '{text_dir_path}'")
                        in_dir_str = str(text_dir_path.resolve())
                        self.settings.setValue("paths/inputDirectory", in_dir_str)
                        self.settings.setValue("inputDir", in_dir_str)  # Alternate key for redundancy
                        self.settings.sync()  # Force immediate sync
                except Exception as e:
                    LOGGER.error(f"Error saving input directory from text field: {e}")
            
            # Then also try to save from MainWindow's state as a backup
            current_in_dir = getattr(main_window, 'in_dir', None)
            LOGGER.debug(f"Got input directory from main window: {current_in_dir}")
            
            if current_in_dir:
                # Get absolute path to ensure it can be restored reliably
                try:
                    in_dir_str = str(current_in_dir.resolve())
                    LOGGER.debug(f"Saving input directory from MainWindow (absolute): '{in_dir_str}'")
                    self.settings.setValue("paths/inputDirectory", in_dir_str)
                    self.settings.setValue("inputDir", in_dir_str)  # Alternate key for redundancy
                    # Force immediate sync after saving this critical value
                    self.settings.sync()
                except Exception as e:
                    LOGGER.error(f"Failed to resolve absolute path for input directory: {e}")
            elif not in_dir_text:
                LOGGER.debug("No input directory to save (None/empty)")
                # We don't remove it so we can restore the last value - safer for users
                # self.settings.remove("paths/inputDirectory") # Clear if None

            # Save output file (still managed locally in MainTab) - ensure we use absolute paths
            if self.out_file_path:
                try:
                    out_file_str = str(self.out_file_path.resolve())
                    LOGGER.debug(f"Saving output file path (absolute): '{out_file_str}'")
                    self.settings.setValue("paths/outputFile", out_file_str)
                except Exception as e:
                    LOGGER.error(f"Failed to resolve absolute path for output file: {e}")
                    # Fall back to regular path string
                    out_file_str = str(self.out_file_path)
                    LOGGER.debug(f"Saving output file path (non-resolved): '{out_file_str}'")
                    self.settings.setValue("paths/outputFile", out_file_str)
            else:
                LOGGER.debug("Removing output file setting (None/empty)")
                self.settings.remove("paths/outputFile")

            # --- Save Processing Settings ---
            LOGGER.debug("Saving processing settings...")
            fps_value = self.fps_spinbox.value()
            LOGGER.debug(f"Saving FPS: {fps_value}")
            self.settings.setValue("processing/fps", fps_value)
            
            multiplier_value = self.mid_count_spinbox.value()
            LOGGER.debug(f"Saving multiplier: {multiplier_value}")
            self.settings.setValue("processing/multiplier", multiplier_value)
            
            max_workers_value = self.max_workers_spinbox.value()
            LOGGER.debug(f"Saving max workers: {max_workers_value}")
            self.settings.setValue("processing/maxWorkers", max_workers_value)
            
            encoder_value = self.encoder_combo.currentText()
            LOGGER.debug(f"Saving encoder: '{encoder_value}'")
            self.settings.setValue("processing/encoder", encoder_value)

            # --- Save RIFE Options ---
            LOGGER.debug("Saving RIFE options...")
            
            model_key = self.rife_model_combo.currentData()
            LOGGER.debug(f"Saving RIFE model key: '{model_key}'")
            self.settings.setValue("rife/modelKey", model_key) # Save model key
            
            tile_enabled = self.rife_tile_checkbox.isChecked()
            LOGGER.debug(f"Saving tiling enabled: {tile_enabled}")
            self.settings.setValue("rife/tilingEnabled", tile_enabled)
            
            tile_size = self.rife_tile_size_spinbox.value()
            LOGGER.debug(f"Saving tile size: {tile_size}")
            self.settings.setValue("rife/tileSize", tile_size)
            
            uhd_mode = self.rife_uhd_checkbox.isChecked()
            LOGGER.debug(f"Saving UHD mode: {uhd_mode}")
            self.settings.setValue("rife/uhdMode", uhd_mode)
            
            thread_spec = self.rife_thread_spec_edit.text()
            LOGGER.debug(f"Saving thread spec: '{thread_spec}'")
            self.settings.setValue("rife/threadSpec", thread_spec)
            
            tta_spatial = self.rife_tta_spatial_checkbox.isChecked()
            LOGGER.debug(f"Saving TTA spatial: {tta_spatial}")
            self.settings.setValue("rife/ttaSpatial", tta_spatial)
            
            tta_temporal = self.rife_tta_temporal_checkbox.isChecked()
            LOGGER.debug(f"Saving TTA temporal: {tta_temporal}")
            self.settings.setValue("rife/ttaTemporal", tta_temporal)

            # --- Save Sanchez Options ---
            LOGGER.debug("Saving Sanchez options...")
            
            false_color = self.sanchez_false_colour_checkbox.isChecked()
            LOGGER.debug(f"Saving false color enabled: {false_color}")
            self.settings.setValue("sanchez/falseColorEnabled", false_color)
            
            res_km = self.sanchez_res_combo.currentText()
            LOGGER.debug(f"Saving resolution km: '{res_km}'")
            self.settings.setValue("sanchez/resolutionKm", res_km)

            # --- Save Crop State from MainWindow's state ---
            LOGGER.debug("Saving crop rectangle...")
            current_crop_rect_mw = getattr(main_window, 'current_crop_rect', None)
            LOGGER.debug(f"Got crop rectangle from main window: {current_crop_rect_mw}")
            
            if current_crop_rect_mw:
                rect_str = ",".join(map(str, current_crop_rect_mw))
                LOGGER.debug(f"Saving crop rectangle: '{rect_str}'")
                # Save to multiple keys for redundancy
                self.settings.setValue("preview/cropRectangle", rect_str)
                self.settings.setValue("cropRect", rect_str)  # Alternate key
                # Force immediate sync after saving this critical value
                self.settings.sync()
                
                # Verify it was actually saved
                saved_rect = self.settings.value("preview/cropRectangle", "", type=str)
                LOGGER.debug(f"Verification - Crop rectangle after save: '{saved_rect}'")
            else:
                LOGGER.debug("No crop rectangle to save (None/empty)")
                # We don't remove it so we can restore the last value - safer for users
                # self.settings.remove("preview/cropRectangle")

            # Force settings to sync to disk
            self.settings.sync()
            LOGGER.info("MainTab: Settings saved successfully.")
            
            # Verify saved settings after sync
            try:
                # Check if input directory was actually saved
                saved_in_dir = self.settings.value("paths/inputDirectory", "", type=str)
                LOGGER.debug(f"Verification - Saved input directory: '{saved_in_dir}'")
                
                # Check if crop rectangle was actually saved
                saved_crop_rect = self.settings.value("preview/cropRectangle", "", type=str)
                LOGGER.debug(f"Verification - Saved crop rectangle: '{saved_crop_rect}'")
                
                # List all keys again to verify
                all_keys_after = self.settings.allKeys()
                LOGGER.debug(f"Verification - Settings keys after save: {all_keys_after}")
            except Exception as ve:
                LOGGER.error(f"Error verifying saved settings: {ve}")
            
        except Exception as e:
            LOGGER.exception(f"Error saving settings: {e}")
            # Continue without failing - don't crash the app if settings saving fails