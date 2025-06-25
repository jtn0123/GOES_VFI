# goesvfi/gui_tabs/main_tab.py

import json
import os
import re
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict, cast

import numpy as np
from numpy.typing import NDArray
from PyQt6.QtCore import QObject, QRect, QSettings, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QImage, QMouseEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
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

from goesvfi.pipeline.image_cropper import ImageCropper
from goesvfi.pipeline.image_loader import ImageLoader
from goesvfi.pipeline.image_processing_interfaces import ImageData
from goesvfi.pipeline.run_vfi import VfiWorker
from goesvfi.pipeline.sanchez_processor import SanchezProcessor
from goesvfi.utils import config, log
from goesvfi.utils.config import get_available_rife_models, get_cache_dir
from goesvfi.utils.gui_helpers import (
    ClickableLabel,
    CropSelectionDialog,
    ImageViewerDialog,
)
from goesvfi.utils.rife_analyzer import analyze_rife_executable
from goesvfi.utils.validation import validate_path_exists, validate_positive_int
from goesvfi.view_models.main_window_view_model import MainWindowViewModel

LOGGER = log.get_logger(__name__)


# Custom button class with enhanced event handling
class SuperButton(QPushButton):
    """A custom button class that ensures clicks are properly processed."""

    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        self.click_callback: Optional[Callable[[], None]] = None
        LOGGER.debug("SuperButton created with text: %s", text)

    def set_click_callback(self, callback: Optional[Callable[[], None]]) -> None:
        """Set a direct callback function for click events."""
        self.click_callback = callback
        LOGGER.debug(
            "SuperButton callback set: %s",
            callback.__name__ if callback else None,
        )

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Explicitly override mouse press event."""
        if event is None:
            return

        LOGGER.debug("SuperButton MOUSE PRESS: %s", event.button())
        # Call the parent implementation
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        """Explicitly override mouse release event for better click detection."""
        if event is None:
            return

        LOGGER.debug("SuperButton MOUSE RELEASE: %s", event.button())
        super().mouseReleaseEvent(event)

        # If it's a left-click release, call our callback
        if event.button() == Qt.MouseButton.LeftButton:
            LOGGER.debug("SuperButton: LEFT CLICK DETECTED")
            if self.click_callback:
                LOGGER.debug(
                    "SuperButton: Calling callback %s",
                    self.click_callback.__name__,
                )
                QTimer.singleShot(10, self.click_callback)  # Small delay to ensure UI updates
            else:
                LOGGER.debug("SuperButton: No callback registered")


# Define Enums for interpolation and raw encoding methods
class InterpolationMethod(Enum):
    NONE = "None"
    RIFE = "RIFE"
    FFMPEG = "FFmpeg"


class RawEncoderMethod(Enum):
    NONE = "None"
    RIFE = "RIFE"
    SANCHEZ = "Sanchez"


# Define RIFEModelDetails TypedDict locally
class RIFEModelDetails(TypedDict, total=False):  # Use total=False for compatibility < 3.11
    version: Optional[str]
    capabilities: Dict[str, bool]
    supported_args: List[str]
    help_text: Optional[str]
    _mtime: float  # Add _mtime used for caching


# Helper function (to be added inside MainTab or globally in the file)
def numpy_to_qimage(array: NDArray[np.uint8]) -> QImage:
    """Converts a NumPy array (H, W, C) in RGB format to QImage."""
    if array is None or array.size == 0:
        return QImage()
    try:
        height, width, channel = array.shape
        if channel == 3:  # RGB
            bytes_per_line = 3 * width
            image_format = QImage.Format.Format_RGB888
            # Create QImage from buffer protocol. Make a copy to be safe.
            qimage = QImage(array.data, width, height, bytes_per_line, image_format).copy()
        elif channel == 4:  # RGBA?
            bytes_per_line = 4 * width
            image_format = QImage.Format.Format_RGBA8888
            qimage = QImage(array.data, width, height, bytes_per_line, image_format).copy()
        elif channel == 1 or len(array.shape) == 2:  # Grayscale
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
    mid_count_spinbox: QSpinBox  # Corrected name based on MainWindow usage
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
        request_previews_update_signal: Any,  # Accept MainWindow's signal (bound signal)
        main_window_ref: Any,  # Add reference to MainWindow
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.main_view_model = main_view_model
        self.processing_vm = main_view_model.processing_vm  # Convenience access
        self.image_loader = image_loader
        self.sanchez_processor = sanchez_processor
        self.image_cropper = image_cropper
        # Ensure we're using the same settings instance as MainWindow
        self.settings = settings
        # Force settings to sync at initialization to ensure freshest data
        self.settings.sync()
        self.main_window_preview_signal = request_previews_update_signal  # Store the signal
        self.main_window_ref = main_window_ref  # Store the MainWindow reference

        # --- State Variables ---
        # self.in_dir and self.current_crop_rect removed, managed by MainWindow
        self.out_file_path: Path | None = None  # Keep output path state local
        self.vfi_worker: "VfiWorker | None" = None  # type: ignore
        self.is_processing = False
        self.current_encoder = "RIFE"  # Default encoder
        self.current_model_key: str | None = "rife-v4.6"  # Default RIFE model key
        self.available_models: Dict[str, RIFEModelDetails] = {}  # Use Dict
        self.image_viewer_dialog: Optional[ImageViewerDialog] = None  # Add member to hold viewer reference
        # -----------------------

        self._setup_ui()
        self._connect_signals()
        self._post_init_setup()  # Perform initial state updates

    def _create_header(self) -> QLabel:
        """Create the enhanced header for the main tab."""
        header = QLabel("🎬 GOES VFI - Video Frame Interpolation")
        header.setStyleSheet(
            """
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: #ffffff;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a6fa5, stop:0.5 #3a5f95, stop:1 #2a4f85);
                padding: 15px 20px;
                border-radius: 10px;
                margin-bottom: 10px;
                border: 2px solid #5a7fb5;
            }
            """
        )
        return header

    def _setup_ui(self) -> None:
        """Create the UI elements for the main tab."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)  # Adjust margins
        layout.setSpacing(10)  # Adjust spacing between major groups

        # Apply enhanced styling to the main tab
        self.setStyleSheet(
            """
            QGroupBox {
                background-color: #2d2d2d;
                border: 2px solid #454545;
                border-radius: 8px;
                font-weight: bold;
                font-size: 12px;
                color: #f0f0f0;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #ffffff;
            }
            QLineEdit {
                padding: 6px 10px;
                background-color: #3a3a3a;
                border: 2px solid #555555;
                border-radius: 6px;
                color: #f0f0f0;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #4a6fa5;
            }
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #5a7fb5;
            }
            QPushButton:pressed {
                background-color: #3a5f95;
            }
            QComboBox {
                padding: 6px 10px;
                background-color: #3a3a3a;
                border: 2px solid #555555;
                border-radius: 6px;
                color: #f0f0f0;
                font-size: 11px;
            }
            QComboBox:hover {
                border-color: #4a6fa5;
            }
            QSpinBox {
                padding: 6px 10px;
                background-color: #3a3a3a;
                border: 2px solid #555555;
                border-radius: 6px;
                color: #f0f0f0;
                font-size: 11px;
            }
            QSpinBox:hover {
                border-color: #4a6fa5;
            }
            QCheckBox {
                color: #f0f0f0;
                font-size: 11px;
            }
            QLabel {
                color: #f0f0f0;
                font-size: 11px;
            }
        """
        )

        # Add enhanced header
        header = self._create_header()
        layout.addWidget(header)

        # Input/Output Group
        io_group = QGroupBox(self.tr("📁 Input/Output"))
        io_layout = QGridLayout(io_group)
        io_layout.setContentsMargins(10, 15, 10, 10)
        io_layout.setSpacing(8)

        # Input directory row (Layout for LineEdit and Button)
        in_dir_layout = QHBoxLayout()
        self.in_dir_edit = QLineEdit()
        self.in_dir_edit.setPlaceholderText("Select input image folder...")
        self.in_dir_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.in_dir_button = QPushButton(self.tr("Browse..."))
        self.in_dir_button.setObjectName("browse_button")
        in_dir_layout.addWidget(self.in_dir_edit)
        in_dir_layout.addWidget(self.in_dir_button)
        # Connect button click here for clarity
        self.in_dir_button.clicked.connect(self._pick_in_dir)

        io_layout.addWidget(QLabel(self.tr("Input Directory:")), 0, 0)
        io_layout.addLayout(in_dir_layout, 0, 1, 1, 2)  # Span layout across 2 columns

        # Output file row (Layout for LineEdit and Button)
        out_file_layout = QHBoxLayout()
        self.out_file_edit = QLineEdit()
        self.out_file_edit.setPlaceholderText("Select output MP4 file...")
        self.out_file_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.out_file_button = QPushButton(self.tr("Browse..."))
        self.out_file_button.setObjectName("browse_button")
        out_file_layout.addWidget(self.out_file_edit)
        out_file_layout.addWidget(self.out_file_button)
        # Connect button click here
        self.out_file_button.clicked.connect(self._pick_out_file)

        io_layout.addWidget(QLabel(self.tr("Output File (MP4):")), 1, 0)
        io_layout.addLayout(out_file_layout, 1, 1, 1, 2)  # Span layout across 2 columns

        # Preview Area
        self.first_frame_label = ClickableLabel()
        self.middle_frame_label = ClickableLabel()
        self.last_frame_label = ClickableLabel()
        previews_group = self._enhance_preview_area()  # Calls helper to setup layout

        # Crop Buttons
        crop_buttons_layout = QHBoxLayout()
        crop_buttons_layout.setContentsMargins(10, 0, 10, 0)
        self.crop_button = SuperButton(self.tr("Select Crop Region"))
        self.crop_button.setObjectName("crop_button")
        self.clear_crop_button = SuperButton(self.tr("Clear Crop"))
        self.clear_crop_button.setObjectName("clear_crop_button")
        crop_buttons_layout.addWidget(self.crop_button)
        crop_buttons_layout.addWidget(self.clear_crop_button)
        crop_buttons_layout.addStretch(1)

        # Sanchez Preview Checkbox (Moved here)
        sanchez_preview_layout = QHBoxLayout()
        sanchez_preview_layout.setContentsMargins(10, 5, 10, 0)  # Add some top margin
        self.sanchez_false_colour_checkbox = QCheckBox(self.tr("Enable Sanchez/False Color Preview"))
        self.sanchez_false_colour_checkbox.setChecked(False)
        self.sanchez_false_colour_checkbox.setToolTip(self.tr("Show previews processed with Sanchez false color."))
        sanchez_preview_layout.addWidget(self.sanchez_false_colour_checkbox)
        sanchez_preview_layout.addStretch(1)

        # Processing Settings Group
        processing_group = self._create_processing_settings_group()  # Calls helper

        # RIFE Options Group
        self.rife_options_group = QGroupBox(self.tr("🤖 RIFE Options"))
        self.rife_options_group.setCheckable(False)
        rife_layout = QGridLayout(self.rife_options_group)
        rife_layout.addWidget(QLabel(self.tr("RIFE Model:")), 0, 0)
        self.rife_model_combo = QComboBox()
        rife_layout.addWidget(self.rife_model_combo, 0, 1)
        self.rife_tile_checkbox = QCheckBox(self.tr("Enable Tiling"))
        self.rife_tile_checkbox.setChecked(False)
        rife_layout.addWidget(self.rife_tile_checkbox, 1, 0)
        self.rife_tile_size_spinbox = QSpinBox()
        self.rife_tile_size_spinbox.setRange(32, 1024)
        self.rife_tile_size_spinbox.setValue(256)
        self.rife_tile_size_spinbox.setEnabled(False)
        rife_layout.addWidget(self.rife_tile_size_spinbox, 1, 1)
        self.tile_size_spinbox = self.rife_tile_size_spinbox  # Alias
        self.rife_uhd_checkbox = QCheckBox(self.tr("UHD Mode"))
        self.rife_uhd_checkbox.setChecked(False)
        rife_layout.addWidget(self.rife_uhd_checkbox, 2, 0, 1, 2)
        rife_layout.addWidget(QLabel(self.tr("Thread Spec:")), 3, 0)
        self.rife_thread_spec_edit = QLineEdit()
        self.rife_thread_spec_edit.setPlaceholderText("e.g., 1:2:2, 2:2:1")
        self.rife_thread_spec_edit.setToolTip(self.tr("Specify thread distribution (encoder:decoder:processor)"))
        rife_layout.addWidget(self.rife_thread_spec_edit, 3, 1)
        self.rife_tta_spatial_checkbox = QCheckBox(self.tr("TTA Spatial"))
        self.rife_tta_spatial_checkbox.setChecked(False)
        rife_layout.addWidget(self.rife_tta_spatial_checkbox, 4, 0, 1, 2)
        self.rife_tta_temporal_checkbox = QCheckBox(self.tr("TTA Temporal"))
        self.rife_tta_temporal_checkbox.setChecked(False)
        rife_layout.addWidget(self.rife_tta_temporal_checkbox, 5, 0, 1, 2)

        # Sanchez Options Group
        self.sanchez_options_group = QGroupBox(self.tr("🌍 Sanchez Options"))
        self.sanchez_options_group.setCheckable(False)
        sanchez_layout = QGridLayout(self.sanchez_options_group)
        # False colour checkbox moved near previews
        # sanchez_layout.addWidget(self.sanchez_false_colour_checkbox, 0, 0, 1, 2) # REMOVED
        sanchez_layout.addWidget(QLabel(self.tr("Resolution (km):")), 1, 0)  # Adjusted row index if needed (seems okay)
        self.sanchez_res_combo = QComboBox()
        self.sanchez_res_combo.addItems(
            [self.tr("0.5"), self.tr("1"), self.tr("2"), self.tr("4")]
        )  # Keep other Sanchez options here
        self.sanchez_res_combo.setCurrentText("4")
        sanchez_layout.addWidget(self.sanchez_res_combo, 1, 1)
        self.sanchez_res_km_combo = self.sanchez_res_combo  # Alias

        # Create a completely redesigned start button implementation
        self.start_button = SuperButton(self.tr("START"))
        self.start_button.setObjectName("start_button")
        self.start_button.setMinimumHeight(50)
        self.start_button.setEnabled(True)  # Initially enabled for debugging
        self.start_button.setStyleSheet(
            """
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
        """
        )

        # Create a button container for the start button
        button_container = QWidget()
        button_layout = QVBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)

        # Add just the regular start button
        button_layout.addWidget(self.start_button)

        # Connect standard button
        self.start_button.clicked.connect(self._direct_start_handler)
        # Also use SuperButton's special callback for extra reliability
        self.start_button.set_click_callback(self._direct_start_handler)

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
        layout.addLayout(sanchez_preview_layout)  # Add Sanchez preview checkbox layout here
        layout.addLayout(settings_layout)
        layout.addWidget(self.sanchez_options_group)  # Keep Sanchez options group for other settings
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
        self.sanchez_false_colour_checkbox.stateChanged.connect(
            self.main_window_preview_signal.emit
        )  # Emit MainWindow signal

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
        self._connect_model_combo()  # Connect RIFE model combo signals

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
        has_processing_handler = hasattr(main_window, "_handle_processing")
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
        if hasattr(self.main_window_ref, "set_in_dir"):
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
        current_in_dir = getattr(self.main_window_ref, "in_dir", None)
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
            current_in_dir = getattr(main_window, "in_dir", None)
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
            if not file_path.lower().endswith(".mp4"):
                file_path += ".mp4"
                LOGGER.debug(f"Added .mp4 extension: {file_path}")

            # Setting text triggers _on_out_file_changed -> sets self.out_file_path
            self.out_file_edit.setText(file_path)

            # Update button state immediately
            self._update_start_button_state()
        else:
            LOGGER.debug("No output file selected")

    def _on_crop_clicked(self) -> None:
        """Handle crop button clicked event."""
        LOGGER.debug("_on_crop_clicked: Function entered.")

        self._log_crop_debug_info()

        current_in_dir = getattr(self.main_window_ref, "in_dir", None)
        if not self._validate_input_directory_for_crop(current_in_dir):
            return

        try:
            image_files = self._get_image_files_for_crop(cast(Path, current_in_dir))
            if not image_files:
                return

            first_image_path = image_files[0]
            LOGGER.debug(f"Preparing image for crop dialog: {first_image_path}")

            full_res_qimage = self._prepare_image_for_crop_dialog(first_image_path)
            if full_res_qimage is None or full_res_qimage.isNull():
                self._show_crop_image_error(first_image_path)
                return

            self._execute_crop_dialog(full_res_qimage)

        except Exception as e:
            LOGGER.exception(f"Error in _on_crop_clicked for {current_in_dir}: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"An unexpected error occurred during cropping setup: {e}",
            )

    def _log_crop_debug_info(self) -> None:
        """Log debug information for crop operation."""
        try:
            mw_ref = self.main_window_ref
            LOGGER.debug(f"_on_crop_clicked: main_window_ref type: {type(mw_ref)}")
            in_dir_check = getattr(mw_ref, "in_dir", "AttributeMissing")
            LOGGER.debug(f"_on_crop_clicked: Accessed main_window_ref.in_dir: {in_dir_check}")
            crop_rect_check = getattr(mw_ref, "current_crop_rect", "AttributeMissing")
            LOGGER.debug(f"_on_crop_clicked: Accessed main_window_ref.current_crop_rect: {crop_rect_check}")
        except Exception as e:
            LOGGER.exception(f"_on_crop_clicked: Error accessing main_window_ref attributes early: {e}")

    def _validate_input_directory_for_crop(self, current_in_dir: Optional[Path]) -> bool:
        """Validate that input directory is suitable for cropping."""
        if not current_in_dir or not current_in_dir.is_dir():
            LOGGER.warning("No input directory selected for cropping.")
            QMessageBox.warning(self, "Warning", "Please select an input directory first.")
            return False
        return True

    def _get_image_files_for_crop(self, current_in_dir: Path) -> List[Path]:
        """Get sorted list of image files from directory."""
        image_files = sorted(
            [f for f in current_in_dir.iterdir() if f.suffix.lower() in [".png", ".jpg", ".jpeg", ".tif", ".tiff"]]
        )
        LOGGER.debug(f"Found {len(image_files)} image files in {current_in_dir}")

        if not image_files:
            LOGGER.warning("No images found in the input directory to crop.")
            QMessageBox.warning(self, "Warning", "No images found in the input directory to crop.")

        return image_files

    def _prepare_image_for_crop_dialog(self, first_image_path: Path) -> Optional[QImage]:
        """Prepare image for crop dialog, handling Sanchez processing if needed."""
        is_sanchez = self.sanchez_false_colour_checkbox.isChecked()
        LOGGER.debug(f"Sanchez checked: {is_sanchez}")

        full_res_qimage = None

        if is_sanchez:
            full_res_qimage = self._try_get_sanchez_image_for_crop(first_image_path)

        # Fallback to original image if Sanchez failed or wasn't used
        if full_res_qimage is None or full_res_qimage.isNull():
            full_res_qimage = self._load_original_image_for_crop(first_image_path)

        return full_res_qimage

    def _try_get_sanchez_image_for_crop(self, first_image_path: Path) -> Optional[QImage]:
        """Try to get Sanchez-processed image for cropping."""
        LOGGER.debug("Sanchez preview enabled. Trying to get/process Sanchez image.")

        # Check cache first
        sanchez_cache = getattr(self.main_window_ref, "sanchez_preview_cache", {})
        cached_np_array = sanchez_cache.get(first_image_path)

        if cached_np_array is not None:
            return self._convert_cached_sanchez_to_qimage(cached_np_array, first_image_path)
        else:
            return self._process_fresh_sanchez_image(first_image_path)

    def _convert_cached_sanchez_to_qimage(
        self, cached_np_array: NDArray[np.float64], first_image_path: Path
    ) -> Optional[QImage]:
        """Convert cached Sanchez array to QImage."""
        LOGGER.debug(f"Found cached Sanchez result for {first_image_path.name}.")
        # Convert float64 array to uint8 for QImage conversion
        uint8_array = (cached_np_array * 255).astype(np.uint8)
        full_res_qimage = numpy_to_qimage(uint8_array)

        if full_res_qimage.isNull():
            LOGGER.error("Failed to convert cached Sanchez NumPy array to QImage.")
            return None

        return full_res_qimage

    def _process_fresh_sanchez_image(self, first_image_path: Path) -> Optional[QImage]:
        """Process fresh Sanchez image for cropping."""
        LOGGER.debug(f"No cached Sanchez result for {first_image_path.name}. Processing...")

        try:
            original_image_data = self._load_original_image_data(first_image_path)
            if not original_image_data or original_image_data.image_data is None:
                return None

            processor = getattr(self.main_window_ref, "sanchez_processor", None)
            if not processor:
                LOGGER.error("Could not access MainWindow's sanchez_processor.")
                return None

            # Use process_image method that returns ImageData
            sanchez_result_data = processor.process_image(original_image_data)
            if not sanchez_result_data or sanchez_result_data.image_data is None:
                LOGGER.error("Sanchez processing failed to return valid data.")
                return None

            full_res_qimage = numpy_to_qimage(sanchez_result_data.image_data)
            if full_res_qimage.isNull():
                LOGGER.error("Failed to convert processed Sanchez NumPy array to QImage.")
                return None

            LOGGER.debug("Successfully processed with Sanchez for cropping.")
            return full_res_qimage

        except Exception as e:
            LOGGER.exception(f"Error processing image with Sanchez for cropping: {e}")
            QMessageBox.warning(
                self,
                "Warning",
                f"Could not process Sanchez image for cropping: {e}\\n\\nShowing original image instead.",
            )
            return None

    def _load_original_image_for_crop(self, first_image_path: Path) -> Optional[QImage]:
        """Load original image for cropping."""
        LOGGER.debug("Loading original image for cropping (Sanchez not used or failed).")

        # Simple QImage loading as fallback
        full_res_qimage = QImage(str(first_image_path))

        if full_res_qimage.isNull():
            LOGGER.error("Failed to load original image for cropping.")
            return None

        LOGGER.debug("Successfully loaded original image for cropping.")
        return full_res_qimage

    def _load_original_image_data(self, image_path: Path) -> Optional[ImageData]:
        """Load original image data using MainWindow's image loader."""
        loader = getattr(self.main_window_ref, "image_loader", None)
        if not loader:
            LOGGER.error("Could not access MainWindow's image_loader.")
            return None

        return cast(Optional[ImageData], loader.load(str(image_path)))

    def _show_crop_image_error(self, first_image_path: Path) -> None:
        """Show error message when image cannot be loaded for cropping."""
        LOGGER.error(f"Failed to load or process any image for cropping: {first_image_path}")
        QMessageBox.critical(
            self,
            "Error",
            f"Could not load or process image for cropping: {first_image_path}",
        )

    def _execute_crop_dialog(self, full_res_qimage: QImage) -> None:
        """Execute the crop selection dialog and handle results."""
        LOGGER.debug(f"Opening CropSelectionDialog with image size: {full_res_qimage.size()}")

        initial_rect = self._get_initial_crop_rect()

        LOGGER.debug("Instantiating CropSelectionDialog...")
        dialog = CropSelectionDialog(full_res_qimage, initial_rect, self)

        LOGGER.debug("Calling dialog.exec()...")
        result_code = dialog.exec()
        LOGGER.debug(f"Dialog result code: {result_code}")

        if result_code == QDialog.DialogCode.Accepted:
            self._handle_crop_dialog_accepted(dialog)
        else:
            LOGGER.info("Crop dialog cancelled.")

        LOGGER.debug("Exiting _on_crop_clicked.")

    def _get_initial_crop_rect(self) -> Optional[QRect]:
        """Get initial crop rectangle from MainWindow state."""
        current_crop_rect_mw = getattr(self.main_window_ref, "current_crop_rect", None)
        if current_crop_rect_mw:
            x, y, w, h = current_crop_rect_mw
            initial_rect = QRect(x, y, w, h)
            LOGGER.debug(f"Using existing crop rect as initial: {initial_rect}")
            return initial_rect
        return None

    def _handle_crop_dialog_accepted(self, dialog: CropSelectionDialog) -> None:
        """Handle accepted crop dialog result."""
        crop_qrect = dialog.get_selected_rect()

        if not crop_qrect.isNull() and crop_qrect.isValid():
            new_crop_rect_tuple = (
                crop_qrect.x(),
                crop_qrect.y(),
                crop_qrect.width(),
                crop_qrect.height(),
            )

            setter = getattr(self.main_window_ref, "set_crop_rect", None)
            if setter:
                setter(new_crop_rect_tuple)
                LOGGER.info(f"Crop rectangle set to: {new_crop_rect_tuple}")
                self.main_window_preview_signal.emit()
            else:
                LOGGER.error("main_window_ref does not have set_crop_rect method")
        else:
            LOGGER.info("Crop dialog accepted but no valid rectangle selected.")

    def _on_clear_crop_clicked(self) -> None:
        """Clear the current crop rectangle."""
        LOGGER.debug("Entering _on_clear_crop_clicked...")
        # Access MainWindow's state via the reference
        current_crop_rect_mw = getattr(self.main_window_ref, "current_crop_rect", None)

        if current_crop_rect_mw:
            # Update MainWindow's crop_rect state via the reference
            if hasattr(self.main_window_ref, "set_crop_rect"):
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

        full_res_image = self._extract_image_from_label(label)
        if not full_res_image:
            self._show_image_unavailable_dialog(label)
            return

        LOGGER.debug("Found full-resolution image on label. Preparing ImageViewerDialog.")

        processed_image_result = self._process_image_for_zoom(full_res_image)
        image_to_show, is_cropped_view = processed_image_result

        info_title = self._build_zoom_dialog_title(label, is_cropped_view)

        self._display_zoom_dialog(image_to_show, info_title)

    def _extract_image_from_label(self, label: ClickableLabel) -> Optional[QImage]:
        """Extract and validate image from label."""
        full_res_image = getattr(label, "processed_image", None)

        if full_res_image and isinstance(full_res_image, QImage) and not full_res_image.isNull():
            return cast(QImage, full_res_image)

        return None

    def _process_image_for_zoom(self, full_res_image: QImage) -> Tuple[QImage, bool]:
        """Process image for zoom view, applying crop if needed."""
        crop_rect_tuple = getattr(self.main_window_ref, "current_crop_rect", None)

        if not crop_rect_tuple:
            LOGGER.debug("No crop rectangle found, showing full image in zoom.")
            return full_res_image, False

        try:
            return self._apply_crop_to_image(full_res_image, crop_rect_tuple)
        except Exception as e:
            LOGGER.exception(f"Error applying crop in _show_zoom: {e}")
            return full_res_image, False

    def _apply_crop_to_image(
        self, full_res_image: QImage, crop_rect_tuple: Tuple[int, int, int, int]
    ) -> Tuple[QImage, bool]:
        """Apply crop rectangle to image if valid."""
        x, y, w, h = crop_rect_tuple
        crop_qrect = QRect(x, y, w, h)
        img_rect = full_res_image.rect()

        if not img_rect.contains(crop_qrect):
            LOGGER.warning(f"Crop rectangle {crop_qrect} is outside image bounds {img_rect}. Showing full image.")
            return full_res_image, False

        LOGGER.debug(f"Applying crop {crop_qrect} to zoom view.")
        cropped_qimage = full_res_image.copy(crop_qrect)

        if cropped_qimage.isNull():
            LOGGER.error("Failed to crop QImage.")
            return full_res_image, False

        LOGGER.debug(f"Cropped image size for zoom: {cropped_qimage.size()}")
        return cropped_qimage, True

    def _build_zoom_dialog_title(self, label: ClickableLabel, is_cropped_view: bool) -> str:
        """Build title for zoom dialog with preview information."""
        preview_type = self._get_preview_type(label)
        info_title = preview_type

        info_title = self._add_crop_info_to_title(info_title, is_cropped_view)
        info_title = self._add_file_info_to_title(info_title, label)

        return info_title

    def _get_preview_type(self, label: ClickableLabel) -> str:
        """Get preview type based on which label was clicked."""
        if label == self.first_frame_label:
            return "First Frame"
        elif label == self.middle_frame_label:
            return "Middle Frame"
        elif label == self.last_frame_label:
            return "Last Frame"
        return ""

    def _add_crop_info_to_title(self, info_title: str, is_cropped_view: bool) -> str:
        """Add crop information to dialog title."""
        crop_rect_tuple = getattr(self.main_window_ref, "current_crop_rect", None)

        if is_cropped_view and crop_rect_tuple and len(crop_rect_tuple) >= 4:
            info_title += f" (Cropped: {crop_rect_tuple[2]}x{crop_rect_tuple[3]})"
        elif crop_rect_tuple is not None:
            info_title += " (Full Image - Crop Disabled)"

        return info_title

    def _add_file_info_to_title(self, info_title: str, label: ClickableLabel) -> str:
        """Add file information to dialog title."""
        file_path = getattr(label, "file_path", None)
        if file_path:
            try:
                p = Path(file_path)
                info_title += f" - {p.name}"
            except Exception:
                info_title += f" - {file_path}"

        return info_title

    def _display_zoom_dialog(self, image_to_show: QImage, info_title: str) -> None:
        """Display the zoom dialog with the processed image."""
        self._close_existing_viewer()

        self.image_viewer_dialog = ImageViewerDialog(image_to_show)
        self.image_viewer_dialog.setWindowTitle(info_title)

        LOGGER.debug(f"Opening ImageViewerDialog - Title: {info_title}")
        LOGGER.debug(f"Image dimensions: {image_to_show.width()}x{image_to_show.height()}")

        self.image_viewer_dialog.show()
        LOGGER.debug("New image viewer dialog shown.")

    def _close_existing_viewer(self) -> None:
        """Close existing image viewer if open."""
        if self.image_viewer_dialog and self.image_viewer_dialog.isVisible():
            LOGGER.debug("Closing existing image viewer dialog.")
            self.image_viewer_dialog.close()

    def _show_image_unavailable_dialog(self, label: ClickableLabel) -> None:
        """Show dialog when image is not available for preview."""
        LOGGER.warning("No valid full-resolution 'processed_image' found on the clicked label.")

        msg = "The full-resolution image is not available for preview yet."
        msg += self._get_image_unavailable_reason(label)
        msg += "\n\nTry updating previews or verifying the input directory."

        QMessageBox.information(self, "Preview Not Available", msg)

    def _get_image_unavailable_reason(self, label: ClickableLabel) -> str:
        """Get specific reason why image is unavailable."""
        if not hasattr(label, "processed_image"):
            return "\n\nReason: No processed image data is attached to this preview."
        elif label.processed_image is None:
            return "\n\nReason: The processed image data is null."
        elif not isinstance(label.processed_image, QImage):
            return f"\n\nReason: The image data is not a QImage (found {type(label.processed_image)})."
        elif label.processed_image.isNull():
            return "\n\nReason: The image is empty or invalid."
        return ""

    def _enhance_preview_area(self) -> QGroupBox:
        """Create the group box containing the preview image labels."""
        previews_group = QGroupBox(self.tr("🖼️ Previews"))
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
            label.setToolTip(self.tr("Click to zoom"))
            label.setMinimumSize(100, 100)  # Ensure minimum size
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)  # Allow shrinking/expanding
            label.setStyleSheet("border: 1px solid gray; background-color: #2a2a2a;")  # Style

            container_layout.addWidget(title_label)
            container_layout.addWidget(label, 1)  # Give label stretch factor
            previews_layout.addWidget(container)

        return previews_group

    def _create_processing_settings_group(self) -> QGroupBox:
        """Create the group box for general processing settings."""
        group = QGroupBox(self.tr("⚙️ Processing Settings"))
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
        layout.addWidget(QLabel(self.tr("Output FPS:")), 0, 0)
        layout.addWidget(self.fps_spinbox, 0, 1)

        self.multiplier_spinbox = QSpinBox()  # Renamed from mid_count_spinbox for clarity
        self.multiplier_spinbox.setRange(2, 16)  # Example range
        self.multiplier_spinbox.setValue(2)
        layout.addWidget(QLabel(self.tr("Frame Multiplier:")), 1, 0)
        layout.addWidget(self.multiplier_spinbox, 1, 1)
        self.mid_count_spinbox = self.multiplier_spinbox  # Alias for compatibility if needed

        self.max_workers_spinbox = QSpinBox()
        cpu_cores = os.cpu_count()
        default_workers = max(1, cpu_cores // 2) if cpu_cores else 1
        self.max_workers_spinbox.setRange(1, os.cpu_count() or 1)
        self.max_workers_spinbox.setValue(default_workers)
        layout.addWidget(QLabel(self.tr("Max Workers:")), 2, 0)
        layout.addWidget(self.max_workers_spinbox, 2, 1)

        self.encoder_combo = QComboBox()
        self.encoder_combo.addItems([self.tr("RIFE"), self.tr("FFmpeg")])  # Add other encoders if supported
        layout.addWidget(QLabel(self.tr("Encoder:")), 3, 0)
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
        if not text:  # Allow empty
            self.rife_thread_spec_edit.setStyleSheet("")
            return

        # Basic regex for N:N:N format (allows single digits or more)
        if re.fullmatch(r"\d+:\d+:\d+", text):
            self.rife_thread_spec_edit.setStyleSheet("")
        else:
            self.rife_thread_spec_edit.setStyleSheet("background-color: #401010;")  # Indicate error

    def _start(self) -> None:
        """Prepare arguments and emit the processing_started signal."""
        # Log start of processing attempt
        LOGGER.info("START METHOD CALLED")
        LOGGER.debug("Preparing to start processing with signal emission")
        LOGGER.debug("================== START BUTTON CLICKED ==================")
        LOGGER.debug("MainTab: Start button clicked.")

        # Verify that the button should be enabled based on state
        can_start = self._verify_start_button_state()
        if not can_start:
            error_msg = "Start button clicked but state verification shows it should be disabled!"
            LOGGER.error(error_msg)
            # Continue anyway since the user managed to click it
            LOGGER.debug("Continuing despite verification failure...")

        # Get parent references through multiple approaches for debugging
        parent_obj = self.parent()
        parent_type = type(parent_obj).__name__
        LOGGER.debug("Parent object type: %s", parent_type)

        main_window_from_parent = parent_obj
        main_window_from_ref = self.main_window_ref

        # Log IDs to verify they're the same object
        mw_parent_id = id(main_window_from_parent)
        mw_ref_id = id(main_window_from_ref)
        LOGGER.debug("main_window_from_parent id: %s", mw_parent_id)
        LOGGER.debug("main_window_from_ref id: %s", mw_ref_id)
        LOGGER.debug(
            "Are references to same object? %s",
            mw_parent_id == mw_ref_id,
        )

        # Check input directory through multiple approaches
        in_dir_from_parent = getattr(main_window_from_parent, "in_dir", None)
        in_dir_from_ref = getattr(main_window_from_ref, "in_dir", None)
        LOGGER.debug("Input dir from parent: %s", in_dir_from_parent)
        LOGGER.debug("Input dir from ref: %s", in_dir_from_ref)
        in_dir_from_edit = self.in_dir_edit.text()
        LOGGER.debug(f"in_dir_from_parent: {in_dir_from_parent}")
        LOGGER.debug(f"in_dir_from_ref: {in_dir_from_ref}")
        LOGGER.debug(f"in_dir_from_edit: {in_dir_from_edit}")

        # Use main_window_ref for consistency
        main_window = self.main_window_ref
        current_in_dir = getattr(main_window, "in_dir", None)
        LOGGER.debug(f"Current input directory: {current_in_dir}, Output file: {self.out_file_path}")

        if not current_in_dir or not self.out_file_path:
            error_msg = f"Missing paths for processing: in_dir={current_in_dir}, out_file={self.out_file_path}"
            LOGGER.warning(error_msg)
            QMessageBox.warning(self, "Missing Paths", "Please select both input and output paths.")
            return

        # Check for files in input directory
        try:
            if current_in_dir and current_in_dir.is_dir():
                image_files = sorted(
                    [
                        f
                        for f in current_in_dir.iterdir()
                        if f.suffix.lower() in [".png", ".jpg", ".jpeg", ".tif", ".tiff"]
                    ]
                )
                LOGGER.debug(f"Found {len(image_files)} image files in input directory")
                if not image_files:
                    LOGGER.warning("No image files found in the input directory")
                    QMessageBox.warning(
                        self,
                        "No Images Found",
                        f"No image files found in the selected directory:\n{current_in_dir}\n\n"
                        "Please select a directory containing image files.",
                    )
                    return
            else:
                LOGGER.warning(f"Input directory invalid or doesn't exist: {current_in_dir}")
                QMessageBox.warning(
                    self,
                    "Invalid Directory",
                    "The selected input directory is invalid or doesn't exist.",
                )
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
            has_handler = hasattr(main_window, "_handle_processing")
            LOGGER.debug(f"MainWindow has processing handler method: {has_handler}")

            try:
                self._start_worker(args)
            except Exception as signal_error:
                LOGGER.exception("Error starting worker: %s", signal_error)
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to start processing:\n{signal_error}",
                )
        else:
            # Error message already shown by get_processing_args
            LOGGER.warning("Processing not started due to invalid arguments.")

        LOGGER.debug("================== START BUTTON PROCESSING COMPLETE ==================")

    def _verify_start_button_state(self) -> bool:
        """Verify that the start button should be enabled based on current state."""
        LOGGER.debug("Verifying start button state...")

        # Check input directory
        main_window = self.main_window_ref
        current_in_dir = getattr(main_window, "in_dir", None)
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

        self._verify_critical_paths(args)
        self._verify_encoder_arguments(args)
        self._verify_crop_rectangle(args)
        self._verify_processing_parameters(args)

    def _verify_critical_paths(self, args: Dict[str, Any]) -> None:
        """Verify input and output path arguments."""
        self._verify_input_directory(args)
        self._verify_output_file(args)

    def _verify_input_directory(self, args: Dict[str, Any]) -> None:
        """Verify input directory exists and is accessible."""
        in_dir = args.get("in_dir")
        if not in_dir:
            LOGGER.error("Missing required argument: in_dir")
            return

        exists = in_dir.exists()
        is_dir = in_dir.is_dir() if exists else False
        LOGGER.debug(f"in_dir: {in_dir}, exists: {exists}, is_dir: {is_dir}")

        if exists and is_dir:
            self._check_input_directory_contents(in_dir)

    def _verify_output_file(self, args: Dict[str, Any]) -> None:
        """Verify output file path and directory writability."""
        out_file = args.get("out_file")
        if not out_file:
            LOGGER.error("Missing required argument: out_file")
            return

        out_dir = out_file.parent
        dir_exists = out_dir.exists()
        dir_writable = os.access(str(out_dir), os.W_OK) if dir_exists else False
        LOGGER.debug(f"out_file: {out_file}, dir_exists: {dir_exists}, dir_writable: {dir_writable}")

    def _verify_encoder_arguments(self, args: Dict[str, Any]) -> None:
        """Verify encoder-specific arguments."""
        encoder = args.get("encoder")
        LOGGER.debug(f"encoder: {encoder}")

        if encoder == "RIFE":
            self._verify_rife_arguments(args)
        elif encoder == "FFmpeg":
            self._verify_ffmpeg_arguments(args)

    def _verify_rife_arguments(self, args: Dict[str, Any]) -> None:
        """Verify RIFE-specific arguments."""
        rife_model_key = args.get("rife_model_key")
        rife_model_path = args.get("rife_model_path")
        rife_exe_path = args.get("rife_exe_path")

        LOGGER.debug(f"rife_model_key: {rife_model_key}")
        LOGGER.debug(f"rife_model_path: {rife_model_path}")
        LOGGER.debug(f"rife_exe_path: {rife_exe_path}")

        if rife_exe_path:
            exe_exists = rife_exe_path.exists()
            exe_executable = os.access(str(rife_exe_path), os.X_OK) if exe_exists else False
            LOGGER.debug(f"rife_exe_path exists: {exe_exists}, executable: {exe_executable}")
        else:
            LOGGER.error("Missing required RIFE executable path")

    def _verify_ffmpeg_arguments(self, args: Dict[str, Any]) -> None:
        """Verify FFmpeg-specific arguments."""
        LOGGER.debug("Checking FFmpeg-specific arguments...")
        ffmpeg_args = args.get("ffmpeg_args")

        if ffmpeg_args:
            LOGGER.debug(f"FFmpeg arguments provided: {ffmpeg_args}")
            self._log_ffmpeg_settings(ffmpeg_args)
        else:
            LOGGER.warning("No FFmpeg arguments provided")
            self._debug_generate_ffmpeg_command(args)

    def _log_ffmpeg_settings(self, ffmpeg_args: Dict[str, Any]) -> None:
        """Log FFmpeg settings for verification."""
        if "profile" in ffmpeg_args:
            profile_name = ffmpeg_args.get("profile")
            LOGGER.debug(f"FFmpeg profile: {profile_name}")

        if "crf" in ffmpeg_args:
            crf = ffmpeg_args.get("crf")
            LOGGER.debug(f"FFmpeg CRF: {crf}")

        if "bitrate" in ffmpeg_args:
            bitrate = ffmpeg_args.get("bitrate")
            LOGGER.debug(f"FFmpeg bitrate: {bitrate}")

    def _verify_crop_rectangle(self, args: Dict[str, Any]) -> None:
        """Verify crop rectangle dimensions and validity."""
        crop_rect = args.get("crop_rect")
        if not crop_rect:
            LOGGER.debug("No crop rectangle specified")
            return

        LOGGER.debug(f"crop_rect: {crop_rect}")

        try:
            x, y, w, h = crop_rect
            LOGGER.debug(f"Crop dimensions - x: {x}, y: {y}, width: {w}, height: {h}")

            if w <= 0 or h <= 0:
                LOGGER.error(f"Invalid crop rectangle dimensions: width={w}, height={h}")
                return

            self._verify_crop_against_input_images(args, crop_rect)
            self._debug_check_ffmpeg_crop_integration(crop_rect)

        except (ValueError, TypeError) as e:
            LOGGER.error(f"Invalid crop rectangle format: {e}")

    def _verify_crop_against_input_images(self, args: Dict[str, Any], crop_rect: Tuple[int, int, int, int]) -> None:
        """Verify crop rectangle against actual image dimensions."""
        in_dir = args.get("in_dir")
        if in_dir is not None:
            in_dir_path = Path(in_dir) if isinstance(in_dir, str) else in_dir
            self._verify_crop_against_images(in_dir_path, crop_rect)

    def _verify_processing_parameters(self, args: Dict[str, Any]) -> None:
        """Verify other processing parameters."""
        parameters = {
            "fps": args.get("fps"),
            "multiplier": args.get("multiplier"),
            "max_workers": args.get("max_workers"),
            "sanchez_enabled": args.get("sanchez_enabled"),
            "sanchez_resolution_km": args.get("sanchez_resolution_km"),
        }

        for param_name, param_value in parameters.items():
            LOGGER.debug(f"{param_name}: {param_value}")

    def _check_input_directory_contents(self, in_dir: Path) -> None:
        """Check images in the input directory and report details for debugging."""
        try:
            image_files = sorted(
                [f for f in in_dir.iterdir() if f.suffix.lower() in [".png", ".jpg", ".jpeg", ".tif", ".tiff"]]
            )

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

            from PIL import Image

            sample_stats = []
            for idx in sample_indices:
                try:
                    img_path = image_files[idx]
                    img = Image.open(img_path)
                    img_array = np.array(img)
                    sample_stats.append(
                        {
                            "index": idx,
                            "filename": img_path.name,
                            "dimensions": img.size,
                            "shape": img_array.shape,
                            "dtype": str(img_array.dtype),
                        }
                    )
                except Exception as e:
                    LOGGER.error(f"Error analyzing image {image_files[idx]}: {e}")

            LOGGER.debug(f"Sample image stats: {sample_stats}")

        except Exception as e:
            LOGGER.exception(f"Error checking input directory contents: {e}")

    def _verify_crop_against_images(self, in_dir: Path, crop_rect: tuple[int, int, int, int]) -> None:
        """Verify that crop rectangle is valid for the images in the directory."""
        try:
            image_files = sorted(
                [f for f in in_dir.iterdir() if f.suffix.lower() in [".png", ".jpg", ".jpeg", ".tif", ".tiff"]]
            )

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

            within_bounds = (
                0 <= x < img_width
                and 0 <= y < img_height
                and 0 < crop_right <= img_width
                and 0 < crop_bottom <= img_height
            )

            LOGGER.debug(f"Image dimensions: {img_width}x{img_height}")
            LOGGER.debug(f"Crop rectangle: ({x}, {y}, {w}, {h})")
            LOGGER.debug(f"Crop bottom-right: ({crop_right}, {crop_bottom})")
            LOGGER.debug(f"Crop within bounds: {within_bounds}")

            if not within_bounds:
                LOGGER.warning(
                    f"Crop rectangle ({x}, {y}, {w}, {h}) exceeds image dimensions ({img_width}x{img_height})"
                )

            # Calculate percentages for context
            crop_width_percent = (w / img_width) * 100
            crop_height_percent = (h / img_height) * 100
            crop_area_percent = (w * h) / (img_width * img_height) * 100

            LOGGER.debug(f"Crop width: {w}px ({crop_width_percent:.1f}% of image width)")
            LOGGER.debug(f"Crop height: {h}px ({crop_height_percent:.1f}% of image height)")
            LOGGER.debug(f"Crop area: {w * h}px² ({crop_area_percent:.1f}% of image area)")

        except Exception as e:
            LOGGER.exception(f"Error verifying crop against images: {e}")

    def _debug_check_ffmpeg_crop_integration(self, crop_rect: tuple[int, int, int, int]) -> None:
        """Debug how crop rectangle would be passed to FFmpeg."""
        try:
            x, y, w, h = crop_rect

            # Check if FFmpeg settings tab is accessible
            main_window = self.main_window_ref
            ffmpeg_tab = getattr(main_window, "ffmpeg_tab", None)

            if ffmpeg_tab:
                LOGGER.debug("FFmpeg settings tab found, checking for crop integration")
                # TODO: Add actual checks for FFmpeg tab handling of crop rectangle
            else:
                LOGGER.debug("FFmpeg settings tab not accessible for crop integration check")

            # Simulate FFmpeg crop filter string
            crop_filter = f"crop={w}:{h}:{x}:{y}"
            LOGGER.debug(f"FFmpeg crop filter would be: {crop_filter}")

            # Check for potential issues with odd dimensions (h264/h265 requirement)
            has_odd_dimensions = w % 2 != 0 or h % 2 != 0
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

            in_dir = args.get("in_dir")
            out_file = args.get("out_file")
            crop_rect = args.get("crop_rect")
            fps = args.get("fps", 60)

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
        in_browse_button = self.findChild(QPushButton, "browse_button")  # Assuming only one for input for now
        out_browse_button = self.findChildren(QPushButton, "browse_button")[1]  # Assuming second is output
        if in_browse_button:
            in_browse_button.setEnabled(not is_processing)
        if out_browse_button:
            out_browse_button.setEnabled(not is_processing)

        # Update ViewModel state
        if is_processing:
            self.processing_vm.start_processing()  # Call correct ViewModel method

            # Show processing confirmation
            LOGGER.info("PROCESSING STARTED")
            LOGGER.info("Processing started - UI updated to processing state")
        else:
            # Cancel processing in ViewModel
            self.processing_vm.cancel_processing()  # Call correct ViewModel method

            LOGGER.info("PROCESSING STOPPED")
            LOGGER.info("Processing stopped - UI updated to ready state")

    def _reset_start_button(self) -> None:
        """Resets the start button text and enables it."""
        self.start_button.setText(self.tr("Start Video Interpolation"))
        self.set_processing_state(False)
        self._update_start_button_state()  # Re-evaluate if it should be enabled

    def _start_button_mouse_press(self, event: QMouseEvent) -> None:
        """Direct mouse event handler for start button."""
        # Always call the original event handler first
        QPushButton.mousePressEvent(self.start_button, event)

        LOGGER.debug("START BUTTON MOUSE PRESS DETECTED - DIRECT EVENT HANDLER")

        # Manually handle the press if it's a left click
        if event.button() == Qt.MouseButton.LeftButton:
            LOGGER.debug(
                "LEFT CLICK ON START BUTTON: enabled=%s",
                self.start_button.isEnabled(),
            )

            # Force the _start method to be called regardless of enabled state
            # This is for debugging - in production we'd respect the enabled state
            QTimer.singleShot(200, self._direct_start)

    def _generate_timestamped_output_path(
        self, base_dir: Optional[Path] = None, base_name: Optional[str] = None
    ) -> Path:
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
            current_in_dir = getattr(main_window, "in_dir", None)
            if current_in_dir and current_in_dir.is_dir():
                if not base_dir:
                    base_dir = current_in_dir.parent
                if not base_name:
                    base_name = current_in_dir.name

        # Use current directory and generic name if still not set
        if not base_dir:
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
        LOGGER.info("DIRECT START HANDLER CALLED")
        LOGGER.info("Enhanced start button handler called")

        # Always generate a fresh timestamped output path for each run
        # If one already exists, parse it to extract the base parts
        base_dir = None
        base_name = None

        if self.out_file_path:
            # Extract directory and basename from existing path
            base_dir = self.out_file_path.parent

            # Try to extract the original name before the timestamp
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
        LOGGER.debug("Fresh timestamped output path: %s", fresh_output_path)

        # Show notification if status bar exists
        main_window = self.main_window_ref
        if hasattr(main_window, "status_bar"):
            main_window.status_bar.showMessage(f"Using output file: {fresh_output_path.name}", 5000)

        # If somehow we still don't have a valid output path (very unlikely at this point)
        if not self.out_file_path:
            LOGGER.info("No output file selected - auto-generating default output path")

            # Get input directory from main window
            main_window = self.main_window_ref
            current_in_dir = getattr(main_window, "in_dir", None)

            if current_in_dir and current_in_dir.is_dir():
                # Create a default output file path with timestamp to ensure uniqueness
                from datetime import datetime

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                default_output = current_in_dir.parent / f"{current_in_dir.name}_output_{timestamp}.mp4"
                self.out_file_path = default_output
                self.out_file_edit.setText(str(default_output))
                LOGGER.debug("Timestamped output file set to: %s", default_output)

                # Show a small notification in the status bar (don't block with a dialog)
                if hasattr(main_window, "status_bar"):
                    main_window.status_bar.showMessage(f"Auto-generated output file: {default_output.name}", 5000)
            else:
                LOGGER.error("Can't create default output - no input directory")
                QMessageBox.warning(
                    self,
                    "Input Directory Required",
                    "Please select a valid input directory first.",
                )
                return

        # Get current state from main window
        main_window = self.main_window_ref
        current_in_dir = getattr(main_window, "in_dir", None)

        # Verify we have an input directory
        if not current_in_dir or not current_in_dir.is_dir():
            LOGGER.error("No valid input directory selected")
            QMessageBox.warning(
                self,
                "Input Directory Required",
                "Please select a valid input directory containing images.",
            )
            return

        # Check for images in input directory
        try:
            image_files = sorted(
                [f for f in current_in_dir.iterdir() if f.suffix.lower() in [".png", ".jpg", ".jpeg", ".tif", ".tiff"]]
            )

            if not image_files:
                LOGGER.warning("No image files found in %s", current_in_dir)
                QMessageBox.warning(
                    self,
                    "No Images Found",
                    f"No image files found in {current_in_dir}.\nPlease select a directory with images.",
                )
                return

            LOGGER.info("Found %d image files in %s", len(image_files), current_in_dir)
        except Exception as e:
            LOGGER.exception("Error checking for images: %s", e)
            QMessageBox.critical(self, "Error", f"Error checking input directory: {e}")
            return

        # Gather processing arguments
        args = self.get_processing_args()
        if not args:
            LOGGER.error("Failed to generate processing arguments")
            return  # Error message already shown by get_processing_args

        # Update UI to show processing started
        self.set_processing_state(True)

        # Show processing confirmation to user
        QMessageBox.information(
            self,
            "Processing Started",
            f"Starting video processing with {len(image_files)} images.\n\n"
            f"Input: {current_in_dir}\n"
            f"Output: {self.out_file_path}",
        )

        # Trigger processing via direct MainWindow method call
        try:
            LOGGER.info("STARTING PROCESSING")
            LOGGER.info("Starting processing via direct handler")

            # Attempt direct emit of signal first
            self.processing_started.emit(args)

            # Fallback to direct method call if needed
            if hasattr(main_window, "_handle_processing"):
                LOGGER.debug("Calling main_window._handle_processing directly as fallback")
                main_window._handle_processing(args)

            LOGGER.info("Processing started successfully")

        except Exception as e:
            LOGGER.exception("Error starting processing: %s", e)
            LOGGER.exception("Error in direct start handler")
            self.set_processing_state(False)  # Reset UI state

            # Show detailed error to user
            error_details = f"An error occurred: {e}\n\n"
            error_details += f"Input dir: {current_in_dir}\n"
            error_details += f"Output file: {self.out_file_path}\n"

            QMessageBox.critical(self, "Error Starting Process", error_details)

    def _direct_start(self) -> None:
        """Original direct handler for start button click."""
        LOGGER.debug("START BUTTON CLICKED - DIRECT START HANDLER")
        LOGGER.debug("Start button clicked - _direct_start called")

        # Check if conditions are met for starting processing
        main_window = self.main_window_ref
        current_in_dir = getattr(main_window, "in_dir", None)
        has_in_dir = bool(current_in_dir and current_in_dir.is_dir())
        has_out_file = bool(self.out_file_path)

        # Log the state for debugging - both to log and stdout
        debug_msg = f"Start conditions: has_in_dir={has_in_dir}, has_out_file={has_out_file}"
        LOGGER.debug(debug_msg)

        # Debug the reference chains
        LOGGER.debug("MainWindow reference exists: %s", main_window is not None)
        LOGGER.debug("Input directory from MainWindow: %s", current_in_dir)
        LOGGER.debug("Output file path: %s", self.out_file_path)

        if has_in_dir and has_out_file:
            # Call the actual start method with trace
            LOGGER.debug("All conditions met - calling _start() method")
            try:
                self._start()
                LOGGER.debug("_start() method completed")
            except Exception as e:
                LOGGER.exception("Error in _start() method")
                # Show error to user
                QMessageBox.critical(
                    self,
                    "Error Starting Process",
                    f"An error occurred when starting the process: {e}",
                )
        else:
            # Show a message to the user about what's missing
            error_msg = "Cannot start processing. "
            if not has_in_dir:
                error_msg += "Please select an input directory. "
            if not has_out_file:
                error_msg += "Please select an output file."

            LOGGER.warning(f"Start button clicked but missing requirements: {error_msg}")
            QMessageBox.warning(self, "Missing Requirements", error_msg)

    def _diagnose_start_button(self) -> None:
        """Debug the start button state."""
        LOGGER.debug("----- START BUTTON DIAGNOSIS -----")

        # Check input directory
        main_window = self.main_window_ref
        current_in_dir = getattr(main_window, "in_dir", None)
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
        LOGGER.debug("START BUTTON CLICKED - DEBUG HANDLER")
        LOGGER.debug("START BUTTON CLICKED - DEBUG HANDLER TRIGGERED")
        # Call the actual handler directly to bypass any signal issues
        self._direct_start()

    def _update_start_button_state(self) -> None:
        """Enable/disable start button based on paths and RIFE model availability."""
        main_window = self.main_window_ref  # Use stored reference for consistency
        current_in_dir = getattr(main_window, "in_dir", None)

        # For simplicity, only require input directory - we can auto-generate output path
        # Original: has_paths = current_in_dir and self.out_file_path
        has_paths = bool(current_in_dir)  # Only input directory is required
        LOGGER.debug(
            f"Start button check: has_paths={has_paths}, in_dir={current_in_dir}, out_file={self.out_file_path}"
        )

        # Check RIFE model only if RIFE is selected encoder
        rife_ok = True
        if self.encoder_combo.currentText() == "RIFE":
            rife_ok = bool(self.rife_model_combo.currentData())  # Check if a valid model is selected
            LOGGER.debug(f"Start button check: RIFE selected, model_ok={rife_ok}")

        can_start = bool(has_paths and rife_ok and not self.is_processing)
        LOGGER.debug(f"Start button should be enabled: {can_start}")

        # Update button state
        self.start_button.setEnabled(can_start)

        # Update button text and style
        if self.is_processing:
            # Processing mode
            self.start_button.setText(self.tr("Cancel"))
            self.start_button.setStyleSheet(
                """
                QPushButton#start_button {
                    background-color: #f44336;
                    color: white;
                    font-weight: bold;
                    font-size: 16px;
                    border-radius: 5px;
                }
            """
            )
        else:
            # Ready or disabled mode
            if can_start:
                self.start_button.setText(self.tr("START"))
                self.start_button.setStyleSheet(
                    """
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
                """
                )
            else:
                self.start_button.setText(self.tr("START"))
                self.start_button.setStyleSheet(
                    """
                    QPushButton#start_button {
                        background-color: #9E9E9E;
                        color: #F5F5F5;
                        font-weight: bold;
                        font-size: 16px;
                        border-radius: 5px;
                        padding: 8px 16px;
                    }
                """
                )

        # Print debug info about button state
        LOGGER.debug(f"Start button enabled: {self.start_button.isEnabled()}")

    @pyqtSlot(bool, str)
    def _on_processing_finished(self, success: bool, message: str) -> None:
        """Handle the processing finished signal from the worker."""
        LOGGER.info(f"MainTab received processing finished: Success={success}, Message={message}")
        self.set_processing_state(False)
        self.processing_finished.emit(success, message)  # Forward the signal
        if success:
            QMessageBox.information(self, "Success", f"Video interpolation finished!\nOutput: {message}")
        # Error message handled by _on_processing_error

    def _on_processing_error(self, error_message: str) -> None:
        """Handle processing errors."""
        LOGGER.error(f"MainTab received processing error: {error_message}")
        self.set_processing_state(False)
        self.processing_finished.emit(False, error_message)  # Forward the signal
        QMessageBox.critical(self, "Error", f"Processing failed:\n{error_message}")

    def _on_worker_progress(self, current: int, total: int, eta: float) -> None:
        """Update progress through the view model."""
        try:
            self.processing_vm.update_progress(current, total, eta)
        except Exception as e:  # pragma: no cover - UI update errors
            LOGGER.exception("Progress update failed: %s", e)

    def _start_worker(self, args: Dict[str, Any]) -> None:
        """Create and start the VfiWorker thread using provided args."""
        ffmpeg_args = args.get("ffmpeg_args") or {}

        self.vfi_worker = VfiWorker(
            in_dir=str(args["in_dir"]),
            out_file_path=str(args["out_file"]),
            fps=args.get("fps", 30),
            mid_count=args.get("multiplier", 2) - 1,
            max_workers=args.get("max_workers", 1),
            encoder=args.get("encoder", "RIFE"),
            use_ffmpeg_interp=ffmpeg_args.get("use_ffmpeg_interp", False),
            filter_preset=ffmpeg_args.get("filter_preset", "full"),
            mi_mode=ffmpeg_args.get("mi_mode", "bidir"),
            mc_mode=ffmpeg_args.get("mc_mode", "aobmc"),
            me_mode=ffmpeg_args.get("me_mode", "bidir"),
            me_algo=ffmpeg_args.get("me_algo", "epzs"),
            search_param=ffmpeg_args.get("search_param", 64),
            scd_mode=ffmpeg_args.get("scd_mode", "fdiff"),
            scd_threshold=ffmpeg_args.get("scd_threshold", 10.0),
            minter_mb_size=ffmpeg_args.get("minter_mb_size", 16),
            minter_vsbmc=ffmpeg_args.get("minter_vsbmc", 1),
            apply_unsharp=ffmpeg_args.get("apply_unsharp", False),
            unsharp_lx=ffmpeg_args.get("unsharp_lx", 5.0),
            unsharp_ly=ffmpeg_args.get("unsharp_ly", 5.0),
            unsharp_la=ffmpeg_args.get("unsharp_la", 1.0),
            unsharp_cx=ffmpeg_args.get("unsharp_cx", 5.0),
            unsharp_cy=ffmpeg_args.get("unsharp_cy", 5.0),
            unsharp_ca=ffmpeg_args.get("unsharp_ca", 0.0),
            crf=ffmpeg_args.get("crf", 23),
            bitrate_kbps=ffmpeg_args.get("bitrate_kbps"),
            bufsize_kb=ffmpeg_args.get("bufsize_kb"),
            pix_fmt=ffmpeg_args.get("pix_fmt", "yuv420p"),
            skip_model=False,
            crop_rect=args.get("crop_rect"),
            debug_mode=getattr(self.main_window_ref, "debug_mode", False),
            rife_tile_enable=args.get("rife_tiling_enabled", False),
            rife_tile_size=args.get("rife_tile_size", 256),
            rife_uhd_mode=args.get("rife_uhd", False),
            rife_thread_spec=args.get("rife_thread_spec"),
            rife_tta_spatial=args.get("rife_tta_spatial", False),
            rife_tta_temporal=args.get("rife_tta_temporal", False),
            model_key=args.get("rife_model_key"),
            false_colour=args.get("sanchez_enabled", False),
            res_km=int(float(args.get("sanchez_resolution_km", 4))),
            sanchez_gui_temp_dir=args.get("sanchez_gui_temp_dir"),
        )

        self.vfi_worker.progress.connect(self._on_worker_progress)
        self.vfi_worker.finished.connect(lambda p: self._on_processing_finished(True, p))
        self.vfi_worker.error.connect(self._on_processing_error)
        self.vfi_worker.start()

    # --- Methods removed as preview logic is now centralized in MainWindow ---
    # _update_previews
    # _convert_image_data_to_qimage
    # _load_process_scale_preview
    # -----------------------------------------------------------------------

    def _update_crop_buttons_state(self) -> None:
        """Enable/disable crop buttons based on input directory and current crop state in MainWindow."""
        # Use the stored reference to MainWindow, not self.parent()
        main_window = self.main_window_ref
        has_in_dir = getattr(main_window, "in_dir", None) is not None
        has_crop = getattr(main_window, "current_crop_rect", None) is not None

        # Removed diagnostic print statements
        LOGGER.debug(
            f"_update_crop_buttons_state: Checking conditions - has_in_dir={has_in_dir}, has_crop={has_crop}"
        )  # Original DEBUG log
        self.crop_button.setEnabled(has_in_dir)
        # Enable clear button only if both input dir and crop exist
        self.clear_crop_button.setEnabled(has_in_dir and has_crop)

        # LOGGER.debug(f"_update_crop_buttons_state: main_window={main_window}, "
        #              f"has_in_dir={has_in_dir}, has_crop={has_crop}") # Original commented DEBUG log

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
        if not caps.get("uhd", False):
            self.rife_uhd_checkbox.setChecked(False)
        if not caps.get("tta_spatial", False):
            self.rife_tta_spatial_checkbox.setChecked(False)
        if not caps.get("tta_temporal", False):
            self.rife_tta_temporal_checkbox.setChecked(False)
        if not caps.get("tiling", False):
            self.rife_tile_checkbox.setChecked(False)
        if not caps.get("custom_thread_count", False):
            self.rife_thread_spec_edit.setText(self.tr(""))

    def _update_rife_options_state(self, encoder: str) -> None:
        """Enable/disable the RIFE options group based on the selected encoder."""
        is_rife = encoder == "RIFE"
        self.rife_options_group.setEnabled(is_rife)

    def _update_sanchez_options_state(self, encoder: str) -> None:
        """Enable/disable the Sanchez options group based on the selected encoder."""
        # Sanchez is used for false color preview with RIFE
        is_rife = encoder == "RIFE"
        self.sanchez_options_group.setEnabled(is_rife)

    def _on_encoder_changed(self, encoder: str) -> None:
        """Handle changes in the selected encoder."""
        self.current_encoder = encoder
        self._update_rife_options_state(encoder)
        self._update_sanchez_options_state(encoder)
        # Potentially update FFmpeg tab state if needed (e.g., disable if RIFE selected)
        # This might require a signal to MainWindow or direct interaction if FFmpeg tab is accessible.
        self._update_start_button_state()  # Re-check start button validity

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
                with open(analysis_cache_file, "r", encoding="utf-8") as f:
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
        for key in found_models:  # Iterate directly over the list of model names
            model_dir = project_root / "models" / key
            rife_exe = config.find_rife_executable(key)  # Pass model key (string) not directory (Path)
            if not rife_exe:
                LOGGER.warning(f"RIFE executable not found for model {key!r} in {model_dir}")
                continue

            exe_path_str = str(rife_exe)
            exe_mtime = os.path.getmtime(rife_exe)

            # Check cache
            if exe_path_str in cached_analysis and cached_analysis[exe_path_str].get("_mtime") == exe_mtime:
                LOGGER.debug(f"Using cached analysis for {key} ({rife_exe.name})")
                details = cached_analysis[exe_path_str]
            else:
                LOGGER.info(f"Analyzing RIFE executable for model {key!r}: {rife_exe}")
                try:
                    # Cast the result to the TypedDict
                    details_raw = analyze_rife_executable(rife_exe)
                    details = cast(RIFEModelDetails, details_raw)
                    details["_mtime"] = exe_mtime  # Store modification time for cache validation
                    cached_analysis[exe_path_str] = details  # Update cache entry
                    needs_cache_update = True
                    LOGGER.debug(f"Analysis complete for {key}. Capabilities: {details.get('capabilities')}")
                except Exception as e:
                    LOGGER.exception(f"Failed to analyze RIFE executable for model {key!r}: {e}")
                    # Ensure the error dictionary conforms to the TypedDict structure
                    # (even if values are defaults/errors)
                    details = cast(
                        RIFEModelDetails,
                        {
                            "version": "Error",
                            "capabilities": {},
                            "supported_args": [],
                            "help_text": f"Error: {e}",
                            "_mtime": exe_mtime,
                        },
                    )
                    cached_analysis[exe_path_str] = details  # Cache error state too
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
                with open(analysis_cache_file, "w", encoding="utf-8") as f:
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
            self.rife_model_combo.setCurrentIndex(0)  # Select first available if last not found
            LOGGER.debug("Last selected RIFE model not found, selecting first available.")

        self._update_rife_ui_elements()  # Update UI based on the initially selected model
        self._update_start_button_state()  # Update start button state

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
            self.current_model_key = None  # Resetting seems safer. Type hint updated to Optional[str]
            self._update_rife_ui_elements()  # Disable options
            self._update_start_button_state()

    def get_processing_args(self) -> Dict[str, Any] | None:
        """Gather all processing arguments from the UI."""
        LOGGER.debug("Gathering processing arguments...")

        main_window = self._get_main_window_reference()
        validation_result = self._validate_processing_inputs(main_window)
        if not validation_result:
            return None

        current_in_dir, current_crop_rect_mw, encoder, rife_model_key = validation_result

        if not self._ensure_output_directory_exists():
            return None

        args = self._build_base_arguments(current_in_dir, current_crop_rect_mw, encoder, rife_model_key)
        self._add_encoder_specific_arguments(args, encoder, rife_model_key, main_window)

        LOGGER.debug(f"Processing arguments gathered: {args}")
        return args

    def _get_main_window_reference(self) -> QObject:
        """Get main window reference with fallback."""
        main_window = self.main_window_ref
        if not main_window:
            LOGGER.warning("main_window_ref is None, falling back to parent()")
            main_window = self.parent()
        return cast(QObject, main_window)

    def _validate_processing_inputs(self, main_window: QObject) -> Optional[Tuple[Path, Any, str, str]]:
        """Validate all required inputs for processing."""
        # Get critical parameters
        current_in_dir = getattr(main_window, "in_dir", None)
        current_crop_rect_mw = getattr(main_window, "current_crop_rect", None)
        LOGGER.debug(f"Input directory from main_window: {current_in_dir}")
        LOGGER.debug(f"Crop rect from main_window: {current_crop_rect_mw}")
        LOGGER.debug(f"Output file path: {self.out_file_path}")

        # Validate input directory
        if not self._validate_input_directory(current_in_dir):
            return None

        # Validate output file
        if not self._validate_output_file():
            return None

        # Validate encoder and model
        encoder_validation = self._validate_encoder_and_model()
        if not encoder_validation:
            return None

        encoder, rife_model_key = encoder_validation
        return current_in_dir, current_crop_rect_mw, encoder, rife_model_key

    def _validate_input_directory(self, current_in_dir: Optional[Path]) -> bool:
        """Validate input directory exists and is accessible."""
        try:
            validate_path_exists(
                current_in_dir,
                must_be_dir=True,
                field_name="Input directory",
            )
            return True
        except (ValueError, FileNotFoundError, NotADirectoryError) as exc:
            error_msg = str(exc)
            LOGGER.error(error_msg)
            QMessageBox.critical(self, "Error", error_msg)
            return False

    def _validate_output_file(self) -> bool:
        """Validate output file is selected."""
        if not self.out_file_path:
            error_msg = "Output file not selected."
            LOGGER.error(error_msg)
            QMessageBox.critical(self, "Error", error_msg)
            return False
        return True

    def _validate_encoder_and_model(self) -> Optional[Tuple[str, str]]:
        """Validate encoder selection and associated model."""
        encoder = self.encoder_combo.currentText()
        rife_model_key = self.rife_model_combo.currentData()
        LOGGER.debug(f"Selected encoder: {encoder}")
        LOGGER.debug(f"Selected RIFE model: {rife_model_key}")

        if encoder == "RIFE" and not rife_model_key:
            error_msg = "No RIFE model selected."
            LOGGER.error(error_msg)
            QMessageBox.critical(self, "Error", error_msg)
            return None

        return encoder, rife_model_key

    def _ensure_output_directory_exists(self) -> bool:
        """Ensure output directory exists, creating if necessary."""
        if not self.out_file_path:
            return True

        out_dir = self.out_file_path.parent
        if not out_dir.exists():
            try:
                LOGGER.info(f"Creating output directory: {out_dir}")
                out_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                error_msg = f"Could not create output directory: {e}"
                LOGGER.error(error_msg)
                QMessageBox.critical(self, "Error", error_msg)
                return False
        return True

    def _build_base_arguments(
        self,
        current_in_dir: Path,
        current_crop_rect_mw: Any,
        encoder: str,
        rife_model_key: str,
    ) -> Dict[str, Any]:
        """Build base arguments dictionary."""
        LOGGER.debug("Building arguments dictionary...")

        args = {
            "in_dir": current_in_dir,
            "out_file": self.out_file_path,
            "fps": validate_positive_int(self.fps_spinbox.value(), "fps"),
            "multiplier": validate_positive_int(self.multiplier_spinbox.value(), "multiplier"),
            "max_workers": validate_positive_int(self.max_workers_spinbox.value(), "max_workers"),
            "encoder": encoder,
            "sanchez_enabled": self.sanchez_false_colour_checkbox.isChecked(),
            "sanchez_resolution_km": float(self.sanchez_res_combo.currentText()),
            "crop_rect": current_crop_rect_mw,
        }

        self._add_rife_arguments(args, encoder, rife_model_key)
        return args

    def _add_rife_arguments(self, args: Dict[str, Any], encoder: str, rife_model_key: str) -> None:
        """Add RIFE-specific arguments to args dictionary."""
        if encoder == "RIFE":
            args.update(
                {
                    "rife_model_key": rife_model_key,
                    "rife_model_path": (
                        config.get_project_root() / "models" / rife_model_key if rife_model_key else None
                    ),
                    "rife_exe_path": (config.find_rife_executable(rife_model_key) if rife_model_key else None),
                    "rife_tta_spatial": self.rife_tta_spatial_checkbox.isChecked(),
                    "rife_tta_temporal": self.rife_tta_temporal_checkbox.isChecked(),
                    "rife_uhd": self.rife_uhd_checkbox.isChecked(),
                    "rife_tiling_enabled": self.rife_tile_checkbox.isChecked(),
                    "rife_tile_size": self.rife_tile_size_spinbox.value(),
                    "rife_thread_spec": (
                        self.rife_thread_spec_edit.text() if self.rife_thread_spec_edit.text() else None
                    ),
                }
            )
        else:
            args.update(
                {
                    "rife_model_key": None,
                    "rife_model_path": None,
                    "rife_exe_path": None,
                    "rife_tta_spatial": False,
                    "rife_tta_temporal": False,
                    "rife_uhd": False,
                    "rife_tiling_enabled": False,
                    "rife_tile_size": None,
                    "rife_thread_spec": None,
                }
            )

    def _add_encoder_specific_arguments(
        self,
        args: Dict[str, Any],
        encoder: str,
        rife_model_key: str,
        main_window: QObject,
    ) -> None:
        """Add encoder-specific arguments."""
        if encoder == "FFmpeg":
            args["ffmpeg_args"] = self._get_ffmpeg_arguments(main_window)
        else:
            args["ffmpeg_args"] = None

    def _get_ffmpeg_arguments(self, main_window: QObject) -> Dict[str, Any]:
        """Get FFmpeg-specific arguments from FFmpeg tab."""
        ffmpeg_tab = getattr(main_window, "ffmpeg_tab", None)
        if ffmpeg_tab:
            try:
                ffmpeg_args: Dict[str, Any] = getattr(ffmpeg_tab, "get_ffmpeg_args", lambda: {})()
                LOGGER.debug(f"Added FFmpeg args from ffmpeg_tab: {ffmpeg_args}")
                return ffmpeg_args
            except Exception as e:
                LOGGER.exception(f"Error getting FFmpeg args: {e}")
                return {}
        else:
            LOGGER.warning("FFmpeg selected but ffmpeg_tab not found in MainWindow")
            return {}

    def set_input_directory(self, directory: Path | str) -> None:
        """Public method to set the input directory text edit."""
        # This might be called from MainWindow or sorter tabs
        self.in_dir_edit.setText(str(directory))  # Triggers _on_in_dir_changed

    def load_settings(self) -> None:
        """Load settings relevant to the MainTab from QSettings."""
        LOGGER.debug("MainTab: Loading settings...")

        self._log_settings_debug_info()
        main_window = self.parent()

        try:
            self.settings.sync()
            self._load_input_output_settings(main_window)
            self._load_processing_settings()
            self._load_rife_settings()
            self._load_sanchez_settings()
            self._load_crop_settings(main_window)
            self._finalize_settings_load()

            LOGGER.info("MainTab: Settings loaded successfully.")
        except Exception as e:
            LOGGER.exception(f"Error loading settings: {e}")

    def _log_settings_debug_info(self) -> None:
        """Log debug information about settings storage."""
        org_name = self.settings.organizationName()
        app_name = self.settings.applicationName()
        filename = self.settings.fileName()
        LOGGER.debug(f"QSettings details: org={org_name}, app={app_name}, file={filename}")

        all_keys = self.settings.allKeys()
        LOGGER.debug(f"Available settings keys: {all_keys}")

    def _load_input_output_settings(self, main_window: QObject) -> None:
        """Load input directory and output file settings."""
        LOGGER.debug("Loading input/output settings...")
        self._load_input_directory_setting(main_window)
        self._load_output_file_setting()

    def _load_input_directory_setting(self, main_window: QObject) -> None:
        """Load input directory setting with fallback logic."""
        LOGGER.debug("Loading input directory path...")

        try:
            in_dir_str = self.settings.value("paths/inputDirectory", "", type=str)
            LOGGER.debug(f"Raw input directory from settings: {in_dir_str!r}")

            loaded_in_dir = self._resolve_input_directory_path(in_dir_str)
            self._update_input_directory_ui(main_window, loaded_in_dir)
        except Exception as e:
            LOGGER.error(f"Error loading input directory setting: {e}")
            self._update_input_directory_ui(main_window, None)

    def _resolve_input_directory_path(self, in_dir_str: str) -> Optional[Path]:
        """Resolve input directory path with fallback to common locations."""
        if not in_dir_str:
            LOGGER.debug("No input directory string in settings")
            return None

        try:
            in_dir_path = Path(in_dir_str)
            exists = in_dir_path.exists()
            is_dir = in_dir_path.is_dir() if exists else False
            LOGGER.debug(f"Input path exists: {exists}, is directory: {is_dir}")

            if exists and is_dir:
                LOGGER.info(f"Loaded valid input directory: {in_dir_str}")
                return in_dir_path

            # Try fallback locations
            return self._find_directory_in_common_locations(in_dir_path.name, in_dir_str)
        except Exception as e:
            LOGGER.error(f"Error resolving input directory path: {e}")
            return None

    def _find_directory_in_common_locations(self, dir_name: str, original_path: str) -> Optional[Path]:
        """Find directory in common locations when original path doesn't exist."""
        LOGGER.warning(f"Saved input directory does not exist: {original_path}")
        LOGGER.debug("Will check if directory exists in other locations...")

        potential_locations = [
            Path.home() / "Downloads" / dir_name,
            Path.home() / "Documents" / dir_name,
            Path.home() / "Desktop" / dir_name,
            Path.cwd() / dir_name,
        ]

        for potential_path in potential_locations:
            LOGGER.debug(f"Checking potential location: {potential_path}")
            if potential_path.exists() and potential_path.is_dir():
                LOGGER.info(f"Found matching directory in alternate location: {potential_path}")
                return potential_path

        return None

    def _update_input_directory_ui(self, main_window: QObject, loaded_in_dir: Optional[Path]) -> None:
        """Update UI elements with loaded input directory."""
        LOGGER.debug(f"Final loaded input directory: {loaded_in_dir}")

        if hasattr(main_window, "set_in_dir"):
            main_window.set_in_dir(loaded_in_dir)

            if loaded_in_dir:
                self.in_dir_edit.setText(str(loaded_in_dir))
                LOGGER.info(f"Set input directory in UI: {loaded_in_dir}")
            else:
                self.in_dir_edit.setText(self.tr(""))
                LOGGER.debug("Cleared input directory in UI (no valid directory found)")
        else:
            LOGGER.error("Parent does not have set_in_dir method")

    def _load_output_file_setting(self) -> None:
        """Load output file setting with fallback logic."""
        LOGGER.debug("Loading output file path...")
        out_file_str = self.settings.value("paths/outputFile", "", type=str)
        LOGGER.debug(f"Raw output file from settings: {out_file_str!r}")

        if not out_file_str:
            self.out_file_path = None
            self.out_file_edit.setText(self.tr(""))
            LOGGER.debug("No output file string in settings")
            return

        try:
            out_file_path = Path(out_file_str)
            resolved_path = self._resolve_output_file_path(out_file_path, out_file_str)
            self.out_file_edit.setText(str(resolved_path))
        except Exception as e:
            LOGGER.error(f"Error loading output file path: {e}")
            self.out_file_path = None

    def _resolve_output_file_path(self, out_file_path: Path, original_str: str) -> Path:
        """Resolve output file path with fallback logic."""
        parent_exists = out_file_path.parent.exists() if out_file_path.parent != Path() else True

        if parent_exists:
            LOGGER.info(f"Loaded output file with valid parent directory: {original_str}")
            return out_file_path

        LOGGER.warning(f"Parent directory for output file doesn't exist: {out_file_path.parent}")
        new_path = Path.home() / "Downloads" / out_file_path.name
        LOGGER.info(f"Generated alternative output path: {new_path}")
        return new_path

    def _load_processing_settings(self) -> None:
        """Load processing-related settings."""
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

    def _load_rife_settings(self) -> None:
        """Load RIFE-specific settings."""
        LOGGER.debug("Loading RIFE options...")

        # Load boolean settings with proper conversion
        tile_enabled = self._load_boolean_setting("rife/tilingEnabled", False)
        LOGGER.debug(f"Setting tiling enabled: {tile_enabled}")
        self.rife_tile_checkbox.setChecked(tile_enabled)

        tile_size_value = self.settings.value("rife/tileSize", 256, type=int)
        LOGGER.debug(f"Setting tile size: {tile_size_value}")
        self.rife_tile_size_spinbox.setValue(tile_size_value)

        uhd_mode = self._load_boolean_setting("rife/uhdMode", False)
        LOGGER.debug(f"Setting UHD mode: {uhd_mode}")
        self.rife_uhd_checkbox.setChecked(uhd_mode)

        thread_spec_value = self.settings.value("rife/threadSpec", "", type=str)
        LOGGER.debug(f"Setting thread spec: {thread_spec_value!r}")
        self.rife_thread_spec_edit.setText(thread_spec_value)

        tta_spatial = self._load_boolean_setting("rife/ttaSpatial", False)
        LOGGER.debug(f"Setting TTA spatial: {tta_spatial}")
        self.rife_tta_spatial_checkbox.setChecked(tta_spatial)

        tta_temporal = self._load_boolean_setting("rife/ttaTemporal", False)
        LOGGER.debug(f"Setting TTA temporal: {tta_temporal}")
        self.rife_tta_temporal_checkbox.setChecked(tta_temporal)

    def _load_sanchez_settings(self) -> None:
        """Load Sanchez-specific settings."""
        LOGGER.debug("Loading Sanchez options...")

        false_color = self._load_boolean_setting("sanchez/falseColorEnabled", False)
        LOGGER.debug(f"Setting false color: {false_color}")
        self.sanchez_false_colour_checkbox.setChecked(false_color)

        res_km_value = self.settings.value("sanchez/resolutionKm", "4", type=str)
        LOGGER.debug(f"Setting resolution km: {res_km_value!r}")

    def _load_crop_settings(self, main_window: QObject) -> None:
        """Load crop rectangle settings."""
        LOGGER.debug("Loading crop rectangle...")

        try:
            crop_rect_str = self.settings.value("preview/cropRectangle", "", type=str)
            LOGGER.debug(f"Raw crop rectangle from settings: {crop_rect_str!r}")

            loaded_crop_rect = self._parse_crop_rectangle(crop_rect_str)
            self._update_crop_rectangle_ui(main_window, loaded_crop_rect)
        except Exception as e:
            LOGGER.error(f"Error loading crop rectangle setting: {e}")
            self._update_crop_rectangle_ui(main_window, None)

    def _parse_crop_rectangle(self, crop_rect_str: str) -> Optional[Tuple[int, int, int, int]]:
        """Parse crop rectangle string into coordinates tuple."""
        if not crop_rect_str:
            LOGGER.debug("No crop rectangle string in settings")
            return None

        try:
            coords = [int(c.strip()) for c in crop_rect_str.split(",")]
            if len(coords) == 4:
                LOGGER.info(f"Loaded crop rectangle: {tuple(coords)}")
                return cast(Tuple[int, int, int, int], tuple(coords))
            else:
                LOGGER.warning(f"Invalid crop rectangle format in settings: {crop_rect_str}")
                return None
        except ValueError:
            LOGGER.warning(f"Could not parse crop rectangle from settings: {crop_rect_str}")
            return None

    def _update_crop_rectangle_ui(
        self,
        main_window: QObject,
        loaded_crop_rect: Optional[Tuple[int, int, int, int]],
    ) -> None:
        """Update UI with loaded crop rectangle."""
        LOGGER.debug(f"Final loaded crop rectangle: {loaded_crop_rect}")

        if hasattr(main_window, "set_crop_rect"):
            main_window.set_crop_rect(loaded_crop_rect)
            LOGGER.debug(f"Crop rectangle set in MainWindow: {loaded_crop_rect}")
        else:
            LOGGER.error("Parent does not have set_crop_rect method")

    def _load_boolean_setting(self, key: str, default: bool) -> bool:
        """Load boolean setting with proper type conversion."""
        raw_value = self.settings.value(key, default)

        if isinstance(raw_value, bool):
            return raw_value
        elif isinstance(raw_value, str):
            return raw_value.lower() == "true"
        else:
            return bool(raw_value)

    def _finalize_settings_load(self) -> None:
        """Finalize settings loading by updating UI states."""
        LOGGER.debug("Updating UI elements based on loaded settings...")
        self._update_rife_ui_elements()
        self._update_start_button_state()
        self._update_crop_buttons_state()
        self._update_rife_options_state(self.encoder_combo.currentText())
        self._update_sanchez_options_state(self.encoder_combo.currentText())
        self._toggle_tile_size_enabled(self.rife_tile_checkbox.isChecked())

        LOGGER.debug("Triggering preview update after settings load")
        self.main_window_preview_signal.emit()

    def save_settings(self) -> None:
        """Save settings relevant to the MainTab to QSettings."""
        LOGGER.debug("MainTab: Saving settings...")

        # Debug settings storage before saving
        org_name = self.settings.organizationName()
        app_name = self.settings.applicationName()
        filename = self.settings.fileName()
        LOGGER.debug(f"QSettings save details: org={org_name}, app={app_name}, file={filename}")

        main_window = self.parent()

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
                        LOGGER.debug(f"Saving input directory from text field: {text_dir_path!r}")
                        in_dir_str = str(text_dir_path.resolve())
                        self.settings.setValue("paths/inputDirectory", in_dir_str)
                        self.settings.setValue("inputDir", in_dir_str)  # Alternate key for redundancy
                        self.settings.sync()  # Force immediate sync
                except Exception as e:
                    LOGGER.error(f"Error saving input directory from text field: {e}")

            # Then also try to save from MainWindow's state as a backup
            current_in_dir = getattr(main_window, "in_dir", None)
            LOGGER.debug(f"Got input directory from main window: {current_in_dir}")

            if current_in_dir:
                # Get absolute path to ensure it can be restored reliably
                try:
                    in_dir_str = str(current_in_dir.resolve())
                    LOGGER.debug(f"Saving input directory from MainWindow (absolute): {in_dir_str!r}")
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
                    LOGGER.debug(f"Saving output file path (absolute): {out_file_str!r}")
                    self.settings.setValue("paths/outputFile", out_file_str)
                except Exception as e:
                    LOGGER.error(f"Failed to resolve absolute path for output file: {e}")
                    # Fall back to regular path string
                    out_file_str = str(self.out_file_path)
                    LOGGER.debug(f"Saving output file path (non-resolved): {out_file_str!r}")
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
            model_key = self.rife_model_combo.currentData()
            LOGGER.debug(f"Saving encoder: '{encoder_value}' with model: {model_key!r}")
            self.settings.setValue("rife/modelKey", model_key)  # Save model key

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
            LOGGER.debug(f"Saving thread spec: {thread_spec!r}")
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
            LOGGER.debug(f"Saving resolution km: {res_km!r}")
            self.settings.setValue("sanchez/resolutionKm", res_km)

            # --- Save Crop State from MainWindow's state ---
            LOGGER.debug("Saving crop rectangle...")
            current_crop_rect_mw = getattr(main_window, "current_crop_rect", None)
            LOGGER.debug(f"Got crop rectangle from main window: {current_crop_rect_mw}")

            if current_crop_rect_mw:
                rect_str = ",".join(map(str, current_crop_rect_mw))
                LOGGER.debug(f"Saving crop rectangle: '{rect_str}'")
                self.settings.setValue("preview/cropRectangle", rect_str)
                self.settings.setValue("cropRect", rect_str)  # Alternate key for redundancy
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
