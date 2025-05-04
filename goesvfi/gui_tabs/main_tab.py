# goesvfi/gui_tabs/main_tab.py

import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, cast, TypedDict, Dict, List, Optional, Set # Add TypedDict, Dict, List, Optional, Set
from enum import Enum # Add this import

import numpy as np
from PIL import Image # Add PIL Image import
from goesvfi.utils import config # Import config
# RIFEModelDetails is defined locally below, remove incorrect import
from goesvfi.pipeline.image_processing_interfaces import ImageData # Add ImageData import
from PyQt6.QtCore import QSettings, Qt, QTimer, pyqtSignal, pyqtSlot # Add pyqtSlot
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
from goesvfi.gui_tabs.ffmpeg_settings_tab import FFMPEG_PROFILES # Correct import path
from goesvfi.utils.gui_helpers import ClickableLabel, CropDialog, ZoomDialog # Import moved classes
from goesvfi.utils.log import get_logger # Use get_logger
LOGGER = get_logger(__name__) # Get logger instance
from goesvfi.utils.config import get_available_rife_models, get_cache_dir # Import from config
from goesvfi.utils.rife_analyzer import analyze_rife_executable # Import analyzer function
from goesvfi.view_models.main_window_view_model import MainWindowViewModel
from goesvfi.view_models.processing_view_model import ProcessingViewModel
from goesvfi.pipeline.image_processing_interfaces import ImageData # Import ImageData


# Define RIFEModelDetails TypedDict locally
class RIFEModelDetails(TypedDict):
    version: Optional[str]
    capabilities: Dict[str, bool]
    supported_args: List[str]
    help_text: Optional[str]


class MainTab(QWidget):
    """Encapsulates the UI and logic for the main processing tab."""

    # Signal to request preview updates, potentially passing the reason
    request_previews_update = pyqtSignal(str, name="requestPreviewsUpdate")
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
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.main_view_model = main_view_model
        self.processing_vm = main_view_model.processing_vm # Convenience access
        self.image_loader = image_loader
        self.sanchez_processor = sanchez_processor
        self.image_cropper = image_cropper
        self.settings = settings

        # --- State Variables ---
        self.sanchez_preview_cache: dict[Path, np.ndarray[Any, Any]] = {} # Cache for Sanchez results
        self.in_dir: Path | None = None
        self.out_file_path: Path | None = None
        self.current_crop_rect: tuple[int, int, int, int] | None = None
        self.vfi_worker: VfiWorker | None = None
        self.is_processing = False
        self.current_encoder = "RIFE"  # Default encoder
        self.current_model_key = "rife-v4.6"  # Default RIFE model key
        self.available_models: Dict[str, RIFEModelDetails] = {} # Use Dict
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
        self.sanchez_false_colour_checkbox = QCheckBox("False Colour")
        self.sanchez_false_colour_checkbox.setChecked(False)
        sanchez_layout.addWidget(self.sanchez_false_colour_checkbox, 0, 0, 1, 2)
        sanchez_layout.addWidget(QLabel("Resolution (km):"), 1, 0)
        self.sanchez_res_combo = QComboBox()
        self.sanchez_res_combo.addItems(["0.5", "1", "2", "4"])
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
        layout.addLayout(settings_layout)
        layout.addWidget(self.sanchez_options_group)
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
        self.sanchez_false_colour_checkbox.stateChanged.connect(lambda: self.request_previews_update.emit("sanchez_toggle"))

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

        # Internal Preview Update Signal
        self.request_previews_update.connect(self._update_previews)


    def _post_init_setup(self) -> None:
        """Perform initial UI state updates after UI creation and signal connection."""
        LOGGER.debug("MainTab: Performing post-init setup...")
        self._populate_models()
        self._update_rife_ui_elements()
        self._update_start_button_state()
        self._update_crop_buttons_state()
        self._update_rife_options_state(self.current_encoder)
        self._update_sanchez_options_state(self.current_encoder)
        # Trigger initial preview load slightly after UI is shown
        QTimer.singleShot(100, lambda: self.request_previews_update.emit("initial_load"))
        LOGGER.debug("MainTab: Post-init setup complete.")

    # --- Signal Handlers and UI Update Methods ---

    def _on_in_dir_changed(self, text: str) -> None:
        """Handle changes to the input directory text."""
        self.in_dir = Path(text) if text else None
        self._update_start_button_state()
        self.request_previews_update.emit("in_dir_changed")

    def _on_out_file_changed(self, text: str) -> None:
        """Handle changes to the output file text."""
        self.out_file_path = Path(text) if text else None
        self._update_start_button_state()

    def _pick_in_dir(self) -> None:
        LOGGER.debug("Entering _pick_in_dir...")
        start_dir = str(self.in_dir) if self.in_dir and self.in_dir.exists() else ""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Input Image Folder", start_dir)
        if dir_path:
            LOGGER.debug(f"Input directory selected: {dir_path}")
            # No need to set self.in_dir here, _on_in_dir_changed will handle it
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
             # No need to set self.out_file_path here, _on_out_file_changed will handle it
            self.out_file_edit.setText(file_path)

    def _on_crop_clicked(self) -> None:
        LOGGER.debug("Entering _on_crop_clicked...")
        if self.in_dir and self.in_dir.is_dir():
            image_files = sorted(
                [
                    f
                    for f in self.in_dir.iterdir()
                    if f.suffix.lower() in [".png", ".jpg", ".jpeg", ".tif", ".tiff"]
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
                        full_res_image: QImage | None = getattr(self.first_frame_label, 'processed_image', None)

                        if full_res_image is not None and isinstance(full_res_image, QImage) and not full_res_image.isNull():
                             LOGGER.debug("Successfully retrieved full-res processed_image from first_frame_label.")
                             pixmap_for_dialog = QPixmap.fromImage(full_res_image)
                        else:
                             LOGGER.warning("processed_image not found or invalid on first_frame_label. Will fall back to original image.")
                             pixmap_for_dialog = None

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

                    if pixmap_for_dialog is None or pixmap_for_dialog.isNull():
                         LOGGER.error(f"Failed to prepare any pixmap for crop dialog: {first_image_path}")
                         QMessageBox.critical(self, "Error", f"Could not load or process image for cropping: {first_image_path}")
                         return

                    dialog = CropDialog(pixmap_for_dialog, self.current_crop_rect, self)
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        crop_rect = dialog.getRect()
                        self.current_crop_rect = (
                            crop_rect.x(),
                            crop_rect.y(),
                            crop_rect.width(),
                            crop_rect.height(),
                        )
                        LOGGER.info(f"Crop rectangle set to: {self.current_crop_rect}")
                        self._update_crop_buttons_state()
                        self.request_previews_update.emit("crop_set")
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

    def _on_clear_crop_clicked(self) -> None:
        """Clear the current crop rectangle."""
        LOGGER.debug("Entering _on_clear_crop_clicked...")
        if self.current_crop_rect:
            self.current_crop_rect = None
            LOGGER.info("Crop rectangle cleared.")
            self._update_crop_buttons_state()
            self.request_previews_update.emit("crop_cleared")

    def _show_zoom(self, label: ClickableLabel) -> None:
        """Show a zoomable dialog for the clicked preview image."""
        LOGGER.debug("Entering _show_zoom...")
        if label.pixmap() and not label.pixmap().isNull():
             # Try to get the full-resolution processed image if available
            full_res_image: QImage | None = getattr(label, 'processed_image', None)
            if full_res_image and isinstance(full_res_image, QImage) and not full_res_image.isNull():
                 LOGGER.debug("Showing zoom dialog with full-res processed image.")
                 zoom_pixmap = QPixmap.fromImage(full_res_image)
            else:
                 LOGGER.debug("Showing zoom dialog with label's potentially scaled pixmap (fallback).")
                 zoom_pixmap = label.pixmap() # Fallback to the potentially scaled pixmap

            dialog = ZoomDialog(zoom_pixmap, self)
            dialog.exec()
        else:
            LOGGER.warning("No valid pixmap found on the label to zoom.")

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

        # Encoder Selection
        layout.addWidget(QLabel("Encoder:"), 0, 0)
        self.encoder_combo = QComboBox()
        self.encoder_combo.addItems(["RIFE", "Sanchez", "FFmpeg"]) # Add FFmpeg later if needed
        self.encoder_combo.setCurrentText(self.current_encoder) # Set initial value
        layout.addWidget(self.encoder_combo, 0, 1)

        # Interpolation Multiplier
        layout.addWidget(QLabel("Interpolation Multiplier:"), 1, 0)
        self.multiplier_spinbox = QSpinBox()
        self.multiplier_spinbox.setRange(2, 16) # Example range
        self.multiplier_spinbox.setValue(2)
        layout.addWidget(self.multiplier_spinbox, 1, 1)

        # Output FPS
        layout.addWidget(QLabel("Output FPS:"), 2, 0)
        self.fps_spinbox = QSpinBox()
        self.fps_spinbox.setRange(1, 120)
        self.fps_spinbox.setValue(30)
        layout.addWidget(self.fps_spinbox, 2, 1)

        # Keep Intermediate Files
        self.keep_temps_checkbox = QCheckBox("Keep Intermediate Files")
        self.keep_temps_checkbox.setChecked(False)
        layout.addWidget(self.keep_temps_checkbox, 3, 0, 1, 2) # Span 2 columns

        # Use Raw Encoder (RIFE only)
        self.use_raw_encoder_checkbox = QCheckBox("Use Raw Encoder (RIFE Only)")
        self.use_raw_encoder_checkbox.setChecked(False)
        layout.addWidget(self.use_raw_encoder_checkbox, 4, 0, 1, 2)

        return group

    def _toggle_tile_size_enabled(self, state: Qt.CheckState) -> None: # Expect CheckState enum
        """Enable/disable the tile size spinbox based on the checkbox state."""
        self.rife_tile_size_spinbox.setEnabled(state == Qt.CheckState.Checked) # Compare directly with enum

    def _validate_thread_spec(self, text: str) -> None:
        """Validate the RIFE thread spec input format."""
        valid_pattern = re.compile(r"^\d+:\d+:\d+$")
        if text and not valid_pattern.match(text):
            self.rife_thread_spec_edit.setStyleSheet("border: 1px solid red;")
            self.rife_thread_spec_edit.setToolTip("Invalid format. Use 'enc:dec:proc' (e.g., 1:2:2)")
        else:
            self.rife_thread_spec_edit.setStyleSheet("") # Reset style
            self.rife_thread_spec_edit.setToolTip("Specify thread distribution (encoder:decoder:processor)")

    def _start(self) -> None:
        """Gather settings and emit signal to start the VFI process."""
        LOGGER.info("Start button clicked.")
        args = self.get_processing_args()
        if args is None:
            QMessageBox.warning(self, "Warning", "Invalid settings. Please check input/output paths.")
            return

        if self.is_processing:
            QMessageBox.warning(self, "Warning", "Processing is already running.")
            return

        self.is_processing = True
        self.start_button.setText("Processing...")
        self.start_button.setEnabled(False)

        LOGGER.info(f"Starting VFI process with args: {args}")
        self.processing_started.emit(args) # Emit signal for main window to handle worker

    # Note: _on_worker_finished and _on_worker_progress are removed
    # The main window should connect to the worker signals directly or via the VM

    def set_processing_state(self, is_processing: bool) -> None:
        """Update the UI based on whether processing is active."""
        self.is_processing = is_processing
        self._reset_start_button() # Updates text and enabled state

    def _reset_start_button(self) -> None:
        """Reset the start button state after processing."""
        self.start_button.setText("Start Video Interpolation" if not self.is_processing else "Processing...")
        self.start_button.setEnabled(self._can_start())

    def _update_start_button_state(self) -> None:
        """Enable the start button only if input and output paths are set."""
        self.start_button.setEnabled(self._can_start())

    def _can_start(self) -> bool:
        """Check if processing can be started."""
        return bool(self.in_dir and self.out_file_path and not self.is_processing)

    @pyqtSlot(str) # Explicitly define slot for clarity
    def _update_previews(self, reason: str = "unknown") -> None:
        """Load and display the first, middle, and last frame previews."""
        LOGGER.debug(f"Entering _update_previews (reason: {reason})... in_dir: {self.in_dir}")
        if not self.in_dir or not self.in_dir.is_dir():
            LOGGER.debug("No valid input directory, clearing previews.")
            self.first_frame_label.clear()
            self.middle_frame_label.clear()
            self.last_frame_label.clear()
            setattr(self.first_frame_label, 'processed_image', None) # Clear stored image
            setattr(self.middle_frame_label, 'processed_image', None)
            setattr(self.last_frame_label, 'processed_image', None)
            return

        try:
            image_files = sorted(
                [
                    f
                    for f in self.in_dir.iterdir()
                    if f.suffix.lower() in [".png", ".jpg", ".jpeg", ".tif", ".tiff"]
                ]
            )
            LOGGER.debug(f"Found {len(image_files)} images for preview.")

            if not image_files:
                LOGGER.debug("No image files found, clearing previews.")
                self.first_frame_label.clear()
                self.middle_frame_label.clear()
                self.last_frame_label.clear()
                setattr(self.first_frame_label, 'processed_image', None)
                setattr(self.middle_frame_label, 'processed_image', None)
                setattr(self.last_frame_label, 'processed_image', None)
                return

            first_img_path = image_files[0]
            middle_img_path = image_files[len(image_files) // 2]
            last_img_path = image_files[-1]

            sanchez_enabled = self.sanchez_false_colour_checkbox.isChecked()
            target_size = self.first_frame_label.size() # Use label size as hint
            # Ensure a minimum size for loading if label size is initially tiny
            min_dim = 100
            target_width = max(target_size.width(), min_dim)
            target_height = max(target_size.height(), min_dim)

            LOGGER.debug(f"Loading previews: First={first_img_path.name}, Middle={middle_img_path.name}, Last={last_img_path.name}")
            LOGGER.debug(f"Sanchez enabled: {sanchez_enabled}, Crop rect: {self.current_crop_rect}, Target size: {target_width}x{target_height}")

            # Load, process, and scale each preview
            self._load_process_scale_preview(self.first_frame_label, first_img_path, sanchez_enabled, self.current_crop_rect, target_width, target_height)
            self._load_process_scale_preview(self.middle_frame_label, middle_img_path, sanchez_enabled, self.current_crop_rect, target_width, target_height)
            self._load_process_scale_preview(self.last_frame_label, last_img_path, sanchez_enabled, self.current_crop_rect, target_width, target_height)

        except Exception as e:
            LOGGER.exception("Error updating previews:")
            self.first_frame_label.setText("Error")
            self.middle_frame_label.setText("Error")
            self.last_frame_label.setText("Error")
            setattr(self.first_frame_label, 'processed_image', None)
            setattr(self.middle_frame_label, 'processed_image', None)
            setattr(self.last_frame_label, 'processed_image', None)

    def _load_process_scale_preview(
        self,
        label: QLabel,
        image_path: Path,
        sanchez_enabled: bool,
        crop_rect: tuple[int, int, int, int] | None,
        target_width: int,
        target_height: int
    ) -> None:
        """Helper to load, process (Sanchez/Crop), and scale a single preview image."""
        label.clear() # Clear previous image
        setattr(label, 'processed_image', None) # Clear stored full-res image
        LOGGER.debug(f"Processing preview for: {image_path.name}")

        try:
            # 1. Load Image using ImageLoader
            image_data_obj: Optional[ImageData] = self.image_loader.load(str(image_path)) # Convert Path to str
            if image_data_obj is None or image_data_obj.image_data is None:
                raise ValueError("ImageLoader returned None or invalid ImageData")
            # Use image_data attribute for shape access
            # Safely log shape/size depending on type
            img_dims = image_data_obj.image_data.size if isinstance(image_data_obj.image_data, Image.Image) else image_data_obj.image_data.shape
            LOGGER.debug(f"Loaded image {image_path.name}, shape/size: {img_dims}")

            processed_data_obj = image_data_obj # Start with the original ImageData object

            # 2. Apply Sanchez if enabled
            if sanchez_enabled:
                 # Check cache first
                cache_key = image_path
                if cache_key in self.sanchez_preview_cache:
                    # Retrieve cached NumPy array
                    cached_np_array = self.sanchez_preview_cache[cache_key]
                    # Create a new ImageData object with the cached array and original metadata
                    processed_data_obj = ImageData(
                        image_data=cached_np_array,
                        source_path=processed_data_obj.source_path,
                        metadata=processed_data_obj.metadata.copy() # Use a copy
                    )
                    LOGGER.debug(f"Using cached Sanchez result for {image_path.name}")
                else:
                    try:
                        # Ensure cache dir for Sanchez previews exists
                        sanchez_preview_cache_dir = get_cache_dir() / "sanchez_previews"
                        os.makedirs(sanchez_preview_cache_dir, exist_ok=True)
                        # SanchezProcessor expects and returns ImageData
                        processed_data_obj = self.sanchez_processor.process(processed_data_obj)
                        # Cache the NumPy array part
                        if processed_data_obj.image_data is not None:
                             # Ensure we cache an ndarray
                             img_data_to_cache = processed_data_obj.image_data
                             if isinstance(img_data_to_cache, Image.Image):
                                 img_data_to_cache = np.array(img_data_to_cache)
                             self.sanchez_preview_cache[cache_key] = img_data_to_cache
                             LOGGER.debug(f"Applied Sanchez to {image_path.name}, shape: {img_data_to_cache.shape}") # Use shape from ndarray
                        else:
                             LOGGER.warning(f"Sanchez processing returned None for image_data for {image_path.name}")
                             processed_data_obj = image_data_obj # Fallback
                    except Exception as sanchez_err:
                         LOGGER.error(f"Sanchez processing failed for preview {image_path.name}: {sanchez_err}")
                         # Fallback to original ImageData if Sanchez fails
                         processed_data_obj = image_data_obj


            # 3. Apply Cropping if enabled
            if crop_rect:
                try:
                    # ImageCropper expects and returns ImageData
                    processed_data_obj = self.image_cropper.crop(processed_data_obj, crop_rect)
                    if processed_data_obj.image_data is not None:
                         # Safely log shape/size depending on type
                         img_dims_after_crop = processed_data_obj.image_data.size if isinstance(processed_data_obj.image_data, Image.Image) else processed_data_obj.image_data.shape
                         LOGGER.debug(f"Applied crop {crop_rect} to {image_path.name}, shape/size: {img_dims_after_crop}")
                    else:
                         LOGGER.warning(f"Cropping returned None for image_data for {image_path.name}")
                         # Fallback handled below
                except Exception as crop_err:
                    LOGGER.error(f"Cropping failed for preview {image_path.name}: {crop_err}")
                    # Fallback to potentially Sanchez-processed data if crop fails
                    # processed_data_obj remains as it was before attempting crop


            # 4. Convert processed NumPy array (from ImageData) to QImage
            if processed_data_obj.image_data is None:
                 raise ValueError("Processed image data is None before QImage conversion")

            # Ensure image data is a NumPy array before QImage conversion
            image_data_for_qimage = processed_data_obj.image_data
            if isinstance(image_data_for_qimage, Image.Image):
                LOGGER.debug("Converting PIL Image to NumPy array for QImage")
                image_data_for_qimage = np.array(image_data_for_qimage)
            elif not isinstance(image_data_for_qimage, np.ndarray):
                 # This case should ideally not happen if ImageData is handled correctly
                 raise TypeError(f"Unexpected image data type for QImage conversion: {type(image_data_for_qimage)}")

            final_np_array = image_data_for_qimage # Now guaranteed to be ndarray
            height, width = final_np_array.shape[:2] # Handle grayscale or RGB
            if final_np_array.ndim == 3 and final_np_array.shape[2] == 3:
                bytes_per_line = 3 * width
                q_image_format = QImage.Format.Format_RGB888
            elif final_np_array.ndim == 2: # Grayscale
                bytes_per_line = width
                q_image_format = QImage.Format.Format_Grayscale8
            elif final_np_array.ndim == 3 and final_np_array.shape[2] == 4: # RGBA
                bytes_per_line = 4 * width
                q_image_format = QImage.Format.Format_RGBA8888
            else:
                raise ValueError(f"Unsupported image array shape for QImage conversion: {final_np_array.shape}")

            # Ensure data is contiguous
            if not final_np_array.flags['C_CONTIGUOUS']:
                final_np_array = np.ascontiguousarray(final_np_array)

            q_image = QImage(final_np_array.data, width, height, bytes_per_line, q_image_format).copy() # Copy data

            if q_image.isNull():
                 raise ValueError("Failed to convert NumPy array to QImage")

            # Store the full-resolution processed QImage on the label before scaling
            setattr(label, 'processed_image', q_image)
            LOGGER.debug(f"Stored full-res processed QImage on label for {image_path.name}")


            # 5. Scale QImage to fit the label
            pixmap = QPixmap.fromImage(q_image)
            scaled_pixmap = pixmap.scaled(target_width, target_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

            # 6. Set Pixmap on Label
            label.setPixmap(scaled_pixmap)
            LOGGER.debug(f"Set scaled pixmap ({scaled_pixmap.width()}x{scaled_pixmap.height()}) on label for {image_path.name}")

        except Exception as e:
            LOGGER.exception(f"Error processing preview for {image_path.name}:")
            label.setText("Error")
            setattr(label, 'processed_image', None) # Clear stored image on error


    def _update_crop_buttons_state(self) -> None:
        """Enable/disable crop buttons based on whether a crop is active."""
        has_crop = self.current_crop_rect is not None
        self.clear_crop_button.setEnabled(has_crop)
        # Optionally change the text of the crop button
        self.crop_button.setText("Modify Crop Region" if has_crop else "Select Crop Region")

    def _update_rife_ui_elements(self) -> None:
        """Update RIFE UI elements based on the selected model's capabilities."""
        LOGGER.debug(f"Updating RIFE UI elements for model: {self.current_model_key}")
        details: RIFEModelDetails | None = self.available_models.get(self.current_model_key)
        if not details:
            LOGGER.warning(f"No details found for RIFE model: {self.current_model_key}")
            # Disable most options if model details are missing
            self.rife_tile_checkbox.setEnabled(False)
            self.rife_tile_size_spinbox.setEnabled(False)
            self.rife_uhd_checkbox.setEnabled(False)
            self.rife_thread_spec_edit.setEnabled(False)
            self.rife_tta_spatial_checkbox.setEnabled(False)
            self.rife_tta_temporal_checkbox.setEnabled(False)
            return

        # Enable/disable based on model capabilities
        # Access capabilities safely from the details dictionary
        capabilities = details.get("capabilities", {})
        can_tile = capabilities.get("tiling", False)
        can_uhd = capabilities.get("uhd", False)
        can_thread = capabilities.get("thread_spec", False)
        can_tta_s = capabilities.get("tta_spatial", False)
        can_tta_t = capabilities.get("tta_temporal", False)

        self.rife_tile_checkbox.setEnabled(can_tile)
        # Only enable size spinbox if tiling is supported AND checked
        self.rife_tile_size_spinbox.setEnabled(can_tile and self.rife_tile_checkbox.isChecked())
        self.rife_uhd_checkbox.setEnabled(can_uhd)
        self.rife_thread_spec_edit.setEnabled(can_thread)
        self.rife_tta_spatial_checkbox.setEnabled(can_tta_s)
        self.rife_tta_temporal_checkbox.setEnabled(can_tta_t)

        LOGGER.debug(f"RIFE UI Updated: Tile={can_tile}, UHD={can_uhd}, Thread={can_thread}, TTA-S={can_tta_s}, TTA-T={can_tta_t}")


    def _update_rife_options_state(self, encoder: str) -> None:
        """Show/hide the RIFE options group based on the selected encoder."""
        is_rife = encoder == "RIFE"
        self.rife_options_group.setVisible(is_rife)
        self.use_raw_encoder_checkbox.setVisible(is_rife) # Show raw encoder only for RIFE

    def _update_sanchez_options_state(self, encoder: str) -> None:
        """Show/hide the Sanchez options group based on the selected encoder."""
        is_sanchez = encoder == "Sanchez"
        self.sanchez_options_group.setVisible(is_sanchez)

    def _on_encoder_changed(self, encoder: str) -> None:
        """Handle changes in the selected encoder."""
        LOGGER.debug(f"Encoder changed to: {encoder}")
        self.current_encoder = encoder
        self._update_rife_options_state(encoder)
        self._update_sanchez_options_state(encoder)
        # self._update_ffmpeg_controls_state(encoder == "FFmpeg") # Handled by FFmpeg tab later
        self.request_previews_update.emit("encoder_changed") # Previews might change (Sanchez)

    def _populate_models(self) -> None:
        """Populate the RIFE model selection combo box by finding models and analyzing them."""
        LOGGER.debug("Populating RIFE models...")
        self.rife_model_combo.clear()
        self.available_models.clear() # Clear existing details

        try:
            model_keys = get_available_rife_models() # Get keys from config helper
            if not model_keys:
                LOGGER.warning("No RIFE model directories found.")
                self.rife_model_combo.addItem("No Models Found")
                self.rife_model_combo.setEnabled(False)
                return

            # Get project root to construct model paths
            project_root = Path(__file__).parent.parent.parent # Adjust based on actual structure if needed

            for key in model_keys:
                model_dir = project_root / "models" / key
                # Attempt to find the executable for this model to analyze it
                # Note: find_rife_executable logic might need refinement depending on how models are packaged
                try:
                    # We need the *actual* exe path associated with the model key to analyze it.
                    # Assuming find_rife_executable can locate it based on the key or a default path.
                    # If each model *folder* contains its *own* executable, adjust find_rife_executable
                    # or the logic here accordingly. For now, assume find_rife_executable works.
                    # Let's use a placeholder path for analysis if find_rife_executable isn't suitable here.
                    # A better approach would be to store exe path alongside model key.
                    # Using the default rife-cli path from config for analysis as a temporary measure:
                    default_rife_exe_path = get_cache_dir().parent / "goesvfi/bin/rife-cli" # Example path, adjust as needed
                    if not default_rife_exe_path.exists():
                         # Try finding via config's find_rife_executable as fallback
                         try:
                              default_rife_exe_path = config.find_rife_executable(key) # Use config's finder
                         except FileNotFoundError:
                              LOGGER.warning(f"Could not find RIFE executable to analyze model '{key}'. Skipping analysis.")
                              # Add model without details if analysis fails? Or skip? Skipping for now.
                              continue

                    LOGGER.debug(f"Analyzing RIFE executable for model '{key}' using: {default_rife_exe_path}")
                    details = analyze_rife_executable(default_rife_exe_path)
                    # Cast the result to our TypedDict for type safety
                    self.available_models[key] = cast(RIFEModelDetails, details)
                    LOGGER.debug(f"Analyzed model '{key}': {details}")
                except FileNotFoundError:
                    LOGGER.warning(f"RIFE executable not found for model '{key}'. Cannot analyze capabilities.")
                except Exception as e:
                    LOGGER.error(f"Error analyzing RIFE executable for model '{key}': {e}")

        except Exception as e:
            LOGGER.exception(f"Error retrieving or analyzing RIFE models: {e}")
            self.available_models.clear() # Ensure it's clear on error

        if not self.available_models:
             LOGGER.warning("No RIFE models could be successfully analyzed.")
             self.rife_model_combo.addItem("No Analyzable Models Found")
             self.rife_model_combo.setEnabled(False)
             return

        self.rife_model_combo.setEnabled(True)
        # Add models sorted alphabetically by key
        for model_key in sorted(self.available_models.keys()):
            model_capability_details: RIFEModelDetails = self.available_models[model_key] # Renamed variable
            # Display name could be more user-friendly if available, otherwise use key
            # Access version using dictionary key lookup
            display_name = f"{model_key} (v{model_capability_details['version']})" if model_capability_details.get('version') else model_key
            self.rife_model_combo.addItem(display_name, userData=model_key) # Store key in userData

        # Try to restore previous selection or set default
        saved_model = self.settings.value("rife/model", self.current_model_key)
        index = self.rife_model_combo.findData(saved_model)
        if index != -1:
            self.rife_model_combo.setCurrentIndex(index)
            self.current_model_key = saved_model
        elif self.rife_model_combo.count() > 0:
             self.rife_model_combo.setCurrentIndex(0) # Default to first if saved not found
             self.current_model_key = self.rife_model_combo.itemData(0)

        LOGGER.info(f"RIFE models populated. Selected: {self.current_model_key}")
        self._update_rife_ui_elements() # Update UI based on initially selected model


    def _connect_model_combo(self) -> None:
        """Connect signals for the RIFE model combo box."""
        self.rife_model_combo.currentIndexChanged.connect(self._on_model_selected)

    def _on_model_selected(self, index: int) -> None:
        """Handle selection changes in the RIFE model combo box."""
        if index == -1: return # Should not happen if populated
        selected_key = self.rife_model_combo.itemData(index)
        if selected_key and selected_key != self.current_model_key:
            self.current_model_key = selected_key
            LOGGER.info(f"RIFE model selected: {self.current_model_key}")
            self._update_rife_ui_elements()
            # Persist selection (optional, or handled by main window save)
            # self.settings.setValue("rife/model", self.current_model_key)

    # --- Public Methods ---

    def get_processing_args(self) -> Dict[str, Any] | None: # Add type parameters
        """Gathers current settings from the UI into a dictionary suitable for VfiWorker.
           Returns None if inputs are invalid."""
        LOGGER.debug("Gathering processing arguments from MainTab UI...")
        if not self.in_dir or not self.out_file_path:
            LOGGER.error("Input or output path missing.")
            return None
        if not self.in_dir.is_dir():
            LOGGER.error(f"Input path is not a directory: {self.in_dir}")
            return None

        encoder_str = self.encoder_combo.currentText()
        multiplier = self.multiplier_spinbox.value()
        fps = self.fps_spinbox.value()
        keep_temps = self.keep_temps_checkbox.isChecked()
        use_raw_encoder = self.use_raw_encoder_checkbox.isChecked()

        rife_params = None
        sanchez_params = None
        ffmpeg_params: Optional[Dict[str, Any]] = None # Will be gathered from FFmpeg tab later, add type hint

        if encoder_str == "RIFE":
            interpolation_method = InterpolationMethod.RIFE
            raw_encoder_method = RawEncoderMethod.RIFE if use_raw_encoder else RawEncoderMethod.NONE
            rife_params = {
                "model": self.current_model_key,
                "enable_tiling": self.rife_tile_checkbox.isChecked(),
                "tile_size": self.rife_tile_size_spinbox.value(),
                "uhd_mode": self.rife_uhd_checkbox.isChecked(),
                "thread_spec": self.rife_thread_spec_edit.text() or None,
                "tta_spatial": self.rife_tta_spatial_checkbox.isChecked(),
                "tta_temporal": self.rife_tta_temporal_checkbox.isChecked(),
            }
        elif encoder_str == "Sanchez":
            interpolation_method = InterpolationMethod.NONE
            raw_encoder_method = RawEncoderMethod.SANCHEZ
            sanchez_params = {
                "false_colour": self.sanchez_false_colour_checkbox.isChecked(),
                "resolution_km": float(self.sanchez_res_combo.currentText()),
            }
        elif encoder_str == "FFmpeg":
            interpolation_method = InterpolationMethod.FFMPEG
            raw_encoder_method = RawEncoderMethod.NONE
            # NOTE: FFmpeg params need to be fetched from the FFmpeg tab externally
            LOGGER.warning("FFmpeg selected in MainTab, but FFmpeg params must be gathered externally.")
            # ffmpeg_params is already initialized to None, it will be populated externally if needed.
            # Remove the redundant definition below.
            # ffmpeg_params: Dict[str, Any] = {} # Placeholder - expect external merge + Add type hint
        else:
             LOGGER.error(f"Unknown encoder selected: {encoder_str}")
             return None

        args = {
            "input_dir": self.in_dir,
            "output_file": self.out_file_path,
            "interpolation_method": interpolation_method,
            "raw_encoder_method": raw_encoder_method,
            "multiplier": multiplier,
            "output_fps": fps,
            "crop_rect": self.current_crop_rect,
            "keep_intermediate": keep_temps,
            "rife_params": rife_params,
            "sanchez_params": sanchez_params,
            "ffmpeg_params": ffmpeg_params, # Pass potentially empty dict
        }
        LOGGER.debug(f"Gathered processing args: {args}")
        return args

    def set_input_directory(self, directory: Path | str) -> None:
        """Programmatically sets the input directory."""
        path = Path(directory)
        LOGGER.info(f"Setting input directory programmatically: {path}")
        self.in_dir_edit.setText(str(path)) # Triggers signals

    def load_settings(self) -> None:
        """Load settings specific to the MainTab from QSettings."""
        LOGGER.debug("MainTab: Loading settings...")
        # Input/Output Paths
        in_dir_str = self.settings.value("paths/inputDirectory", "")
        if in_dir_str and Path(in_dir_str).exists():
            self.in_dir_edit.setText(in_dir_str) # Triggers update
        out_file_str = self.settings.value("paths/outputFile", "")
        if out_file_str:
            self.out_file_edit.setText(out_file_str) # Triggers update

        # Crop Rectangle
        crop_val = self.settings.value("processing/cropRectangle")
        if isinstance(crop_val, (list, tuple)) and len(crop_val) == 4:
             try:
                 # Cast the tuple to the expected type
                 self.current_crop_rect = cast(tuple[int, int, int, int], tuple(int(x) for x in crop_val))
                 LOGGER.debug(f"Loaded crop rect: {self.current_crop_rect}")
                 self._update_crop_buttons_state()
             except (ValueError, TypeError):
                 LOGGER.warning(f"Invalid crop rectangle value in settings: {crop_val}")
                 self.current_crop_rect = None
        else:
            self.current_crop_rect = None
        self._update_crop_buttons_state() # Ensure buttons are correct even if no crop loaded

        # Processing Settings
        self.encoder_combo.setCurrentText(self.settings.value("processing/encoder", "RIFE"))
        self.multiplier_spinbox.setValue(int(self.settings.value("processing/multiplier", 2)))
        self.fps_spinbox.setValue(int(self.settings.value("processing/fps", 30)))
        self.keep_temps_checkbox.setChecked(self.settings.value("processing/keepTemps", False, type=bool))
        self.use_raw_encoder_checkbox.setChecked(self.settings.value("processing/useRawEncoder", False, type=bool))

        # RIFE Settings
        # Model is loaded in _populate_models
        self.rife_tile_checkbox.setChecked(self.settings.value("rife/enableTiling", False, type=bool))
        self.rife_tile_size_spinbox.setValue(int(self.settings.value("rife/tileSize", 256)))
        self.rife_uhd_checkbox.setChecked(self.settings.value("rife/uhdMode", False, type=bool))
        self.rife_thread_spec_edit.setText(self.settings.value("rife/threadSpec", ""))
        self.rife_tta_spatial_checkbox.setChecked(self.settings.value("rife/ttaSpatial", False, type=bool))
        self.rife_tta_temporal_checkbox.setChecked(self.settings.value("rife/ttaTemporal", False, type=bool))
        self._toggle_tile_size_enabled(self.rife_tile_checkbox.checkState()) # Pass enum, not value

        # Sanchez Settings
        self.sanchez_false_colour_checkbox.setChecked(self.settings.value("sanchez/falseColour", False, type=bool))
        self.sanchez_res_combo.setCurrentText(self.settings.value("sanchez/resolutionKm", "4"))

        # Update UI based on loaded settings
        self._update_rife_options_state(self.encoder_combo.currentText())
        self._update_sanchez_options_state(self.encoder_combo.currentText())
        self._update_rife_ui_elements() # Update RIFE controls based on loaded model/settings
        self._update_start_button_state()

        LOGGER.debug("MainTab: Settings loaded.")
        # Trigger preview update after loading settings
        QTimer.singleShot(150, lambda: self.request_previews_update.emit("settings_loaded"))


    def save_settings(self) -> None:
        """Save settings specific to the MainTab to QSettings."""
        LOGGER.debug("MainTab: Saving settings...")
        # Paths
        if self.in_dir: self.settings.setValue("paths/inputDirectory", str(self.in_dir))
        if self.out_file_path: self.settings.setValue("paths/outputFile", str(self.out_file_path))

        # Crop
        if self.current_crop_rect:
            self.settings.setValue("processing/cropRectangle", list(self.current_crop_rect))
        else:
            self.settings.remove("processing/cropRectangle") # Remove if None

        # Processing
        self.settings.setValue("processing/encoder", self.encoder_combo.currentText())
        self.settings.setValue("processing/multiplier", self.multiplier_spinbox.value())
        self.settings.setValue("processing/fps", self.fps_spinbox.value())
        self.settings.setValue("processing/keepTemps", self.keep_temps_checkbox.isChecked())
        self.settings.setValue("processing/useRawEncoder", self.use_raw_encoder_checkbox.isChecked())

        # RIFE
        self.settings.setValue("rife/model", self.current_model_key)
        self.settings.setValue("rife/enableTiling", self.rife_tile_checkbox.isChecked())
        self.settings.setValue("rife/tileSize", self.rife_tile_size_spinbox.value())
        self.settings.setValue("rife/uhdMode", self.rife_uhd_checkbox.isChecked())
        self.settings.setValue("rife/threadSpec", self.rife_thread_spec_edit.text())
        self.settings.setValue("rife/ttaSpatial", self.rife_tta_spatial_checkbox.isChecked())
        self.settings.setValue("rife/ttaTemporal", self.rife_tta_temporal_checkbox.isChecked())

        # Sanchez
        self.settings.setValue("sanchez/falseColour", self.sanchez_false_colour_checkbox.isChecked())
        self.settings.setValue("sanchez/resolutionKm", self.sanchez_res_combo.currentText())

        LOGGER.debug("MainTab: Settings saved.")