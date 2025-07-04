# goesvfi/gui_tabs/main_tab.py

from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum
import json
import os
from pathlib import Path
import re
from typing import Any, TypedDict, cast

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
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from goesvfi.gui_components.icon_manager import get_icon
from goesvfi.gui_components.main_tab_settings import MainTabSettings
from goesvfi.gui_components.update_manager import register_update, request_update
from goesvfi.gui_components.widget_factory import WidgetFactory
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

# Image channel constants
RGB_CHANNELS = 3
RGBA_CHANNELS = 4
GRAYSCALE_CHANNELS = 1

# Image dimensions
GRAYSCALE_DIMENSIONS = 2
COLOR_DIMENSIONS = 3

# Crop rectangle components
CROP_RECT_COMPONENTS = 4

# Image sampling thresholds
MINIMUM_IMAGES_FOR_SAMPLING = 2


# Custom button class with enhanced event handling
class SuperButton(QPushButton):
    """A custom button class that ensures clicks are properly processed."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.click_callback: Callable[[], None] | None = None
        LOGGER.debug("SuperButton created with text: %s", text)

    def set_click_callback(self, callback: Callable[[], None] | None) -> None:
        """Set a direct callback function for click events."""
        self.click_callback = callback
        LOGGER.debug(
            "SuperButton callback set: %s",
            callback.__name__ if callback else None,
        )

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        """Explicitly override mouse press event."""
        if event is None:
            return

        LOGGER.debug("SuperButton MOUSE PRESS: %s", event.button())
        # Call the parent implementation
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
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
    version: str | None
    capabilities: dict[str, bool]
    supported_args: list[str]
    help_text: str | None
    _mtime: float  # Add _mtime used for caching


# Helper function (to be added inside MainTab or globally in the file)
def numpy_to_qimage(array: NDArray[np.uint8]) -> QImage:
    """Converts a NumPy array (H, W, C) in RGB format to QImage."""
    if array is None or array.size == 0:
        return QImage()
    try:
        height, width, channel = array.shape
        if channel == RGB_CHANNELS:  # RGB
            bytes_per_line = RGB_CHANNELS * width
            image_format = QImage.Format.Format_RGB888
            # Create QImage from buffer protocol. Make a copy to be safe.
            qimage = QImage(array.data, width, height, bytes_per_line, image_format).copy()
        elif channel == RGBA_CHANNELS:  # RGBA?
            bytes_per_line = RGBA_CHANNELS * width
            image_format = QImage.Format.Format_RGBA8888
            qimage = QImage(array.data, width, height, bytes_per_line, image_format).copy()
        elif channel == GRAYSCALE_CHANNELS or len(array.shape) == GRAYSCALE_DIMENSIONS:  # Grayscale
            height, width = array.shape[:2]
            bytes_per_line = width
            image_format = QImage.Format.Format_Grayscale8
            # Ensure array is contiguous C-style for grayscale
            gray_array = np.ascontiguousarray(array.squeeze())
            qimage = QImage(gray_array.data, width, height, bytes_per_line, image_format).copy()
        else:
            LOGGER.error("Unsupported NumPy array shape for QImage conversion: %s", array.shape)
            return QImage()

        if qimage.isNull():
            LOGGER.error("Failed to create QImage from NumPy array (check format/data).")
            return QImage()
        return qimage
    except Exception:
        LOGGER.exception("Error converting NumPy array to QImage")
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

        # Initialize centralized settings manager
        self.tab_settings = MainTabSettings(settings)

        self.main_window_preview_signal = request_previews_update_signal  # Store the signal
        self.main_window_ref = main_window_ref  # Store the MainWindow reference

        # --- State Variables ---
        # self.in_dir and self.current_crop_rect removed, managed by MainWindow
        self.out_file_path: Path | None = None  # Keep output path state local
        self.vfi_worker: VfiWorker | None = None  # type: ignore
        self.is_processing = False
        self.current_encoder = "RIFE"  # Default encoder
        self.current_model_key: str | None = "rife-v4.6"  # Default RIFE model key
        self.available_models: dict[str, RIFEModelDetails] = {}  # Use Dict
        self.image_viewer_dialog: ImageViewerDialog | None = None  # Add member to hold viewer reference
        # -----------------------

        # Initialize UpdateManager integration
        self._setup_update_manager()

        # Enable drag and drop
        self.setAcceptDrops(True)

        self._setup_ui()
        self._connect_signals()
        self._post_init_setup()  # Perform initial state updates

    @staticmethod
    def _create_header() -> QLabel:
        """Create the enhanced header for the main tab."""
        # Create header with icon
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)

        icon_label = QLabel()
        icon_label.setPixmap(get_icon("🎬").pixmap(32, 32))
        header_layout.addWidget(icon_label)

        text_label = WidgetFactory.create_label("GOES VFI - Video Frame Interpolation", style="header")
        header_layout.addWidget(text_label)
        header_layout.addStretch()

        return header_widget

    def _setup_ui(self) -> None:
        """Create the UI elements for the main tab."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)  # Adjust margins
        layout.setSpacing(10)  # Adjust spacing between major groups

        # Apply qt-material theme properties to main tab
        WidgetFactory.update_widget_style(self, "MainTab")

        # Add enhanced header
        header = MainTab._create_header()
        layout.addWidget(header)

        # Input/Output Group
        io_group = WidgetFactory.create_group_box(self.tr("Input/Output"))
        # Add icon to group box title
        io_group.setStyleSheet("QGroupBox::title { padding-left: 24px; }")
        io_layout = QGridLayout(io_group)
        io_layout.setContentsMargins(10, 15, 10, 10)
        io_layout.setSpacing(8)

        # Input directory row (Layout for LineEdit and Button)
        in_dir_layout = QHBoxLayout()
        self.in_dir_edit = WidgetFactory.create_line_edit(placeholder="Select input image folder...")
        self.in_dir_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.in_dir_button = WidgetFactory.create_button(
            self.tr("Browse..."),
            style="secondary",
            objectName="browse_button",
            toolTip="Browse for input directory containing image files",
        )
        in_dir_layout.addWidget(self.in_dir_edit)
        in_dir_layout.addWidget(self.in_dir_button)
        # Connect button click here for clarity
        self.in_dir_button.clicked.connect(self._pick_in_dir)

        in_label = WidgetFactory.create_label(self.tr("Input Directory:"), style="standard")
        io_layout.addWidget(in_label, 0, 0)
        io_layout.addLayout(in_dir_layout, 0, 1, 1, 2)  # Span layout across 2 columns

        # Output file row (Layout for LineEdit and Button)
        out_file_layout = QHBoxLayout()
        self.out_file_edit = WidgetFactory.create_line_edit(placeholder="Select output MP4 file...")
        self.out_file_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.out_file_button = WidgetFactory.create_button(
            self.tr("Browse..."),
            style="secondary",
            objectName="browse_button",
            toolTip="Browse for output video file location",
        )
        out_file_layout.addWidget(self.out_file_edit)
        out_file_layout.addWidget(self.out_file_button)
        # Connect button click here
        self.out_file_button.clicked.connect(self._pick_out_file)

        out_label = WidgetFactory.create_label(self.tr("Output File (MP4):"), style="standard")
        io_layout.addWidget(out_label, 1, 0)
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
        self.crop_button.setIcon(get_icon("✂️"))
        self.crop_button.setObjectName("crop_button")
        WidgetFactory.update_widget_style(self.crop_button, "DialogButton")
        self.crop_button.setToolTip("Select a region of the image to crop during processing")
        self.clear_crop_button = SuperButton(self.tr("Clear Crop"))
        self.clear_crop_button.setIcon(get_icon("❌"))
        self.clear_crop_button.setObjectName("clear_crop_button")
        WidgetFactory.update_widget_style(self.clear_crop_button, "DialogButton")
        self.clear_crop_button.setToolTip("Remove the current crop selection and use full image")
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
        self.rife_options_group = WidgetFactory.create_group_box(self.tr("🤖 RIFE Options"))
        self.rife_options_group.setCheckable(False)
        rife_layout = QGridLayout(self.rife_options_group)
        rife_model_label = WidgetFactory.create_label(self.tr("RIFE Model:"), style="standard")
        rife_layout.addWidget(rife_model_label, 0, 0)
        self.rife_model_combo = QComboBox()
        self.rife_model_combo.setToolTip("Select the RIFE model version for frame interpolation")
        rife_layout.addWidget(self.rife_model_combo, 0, 1)
        self.rife_tile_checkbox = QCheckBox(self.tr("Enable Tiling"))
        self.rife_tile_checkbox.setChecked(False)
        self.rife_tile_checkbox.setToolTip("Process image in tiles to reduce memory usage")
        rife_layout.addWidget(self.rife_tile_checkbox, 1, 0)
        self.rife_tile_size_spinbox = QSpinBox()
        self.rife_tile_size_spinbox.setRange(32, 1024)
        self.rife_tile_size_spinbox.setValue(256)
        self.rife_tile_size_spinbox.setEnabled(False)
        self.rife_tile_size_spinbox.setToolTip("Size of tiles in pixels when tiling is enabled")
        rife_layout.addWidget(self.rife_tile_size_spinbox, 1, 1)
        self.tile_size_spinbox = self.rife_tile_size_spinbox  # Alias
        self.rife_uhd_checkbox = QCheckBox(self.tr("UHD Mode"))
        self.rife_uhd_checkbox.setChecked(False)
        self.rife_uhd_checkbox.setToolTip("Enable UHD mode for 4K video processing")
        rife_layout.addWidget(self.rife_uhd_checkbox, 2, 0, 1, 2)
        thread_spec_label = WidgetFactory.create_label(self.tr("Thread Spec:"), style="standard")
        rife_layout.addWidget(thread_spec_label, 3, 0)
        self.rife_thread_spec_edit = WidgetFactory.create_line_edit(
            placeholder="e.g., 1:2:2, 2:2:1", toolTip=self.tr("Specify thread distribution (encoder:decoder:processor)")
        )
        rife_layout.addWidget(self.rife_thread_spec_edit, 3, 1)
        self.rife_tta_spatial_checkbox = QCheckBox(self.tr("TTA Spatial"))
        self.rife_tta_spatial_checkbox.setChecked(False)
        self.rife_tta_spatial_checkbox.setToolTip(
            "Test-Time Augmentation for spatial dimensions (improves quality but slower)"
        )
        rife_layout.addWidget(self.rife_tta_spatial_checkbox, 4, 0, 1, 2)
        self.rife_tta_temporal_checkbox = QCheckBox(self.tr("TTA Temporal"))
        self.rife_tta_temporal_checkbox.setChecked(False)
        self.rife_tta_temporal_checkbox.setToolTip(
            "Test-Time Augmentation for temporal dimension (improves quality but slower)"
        )
        rife_layout.addWidget(self.rife_tta_temporal_checkbox, 5, 0, 1, 2)

        # Sanchez Options Group
        self.sanchez_options_group = WidgetFactory.create_group_box(self.tr("🌍 Sanchez Options"))
        self.sanchez_options_group.setCheckable(False)
        sanchez_layout = QGridLayout(self.sanchez_options_group)
        # False colour checkbox moved near previews
        # sanchez_layout.addWidget(self.sanchez_false_colour_checkbox, 0, 0, 1, 2) # REMOVED
        res_label = WidgetFactory.create_label(self.tr("Resolution (km):"), style="standard")
        sanchez_layout.addWidget(res_label, 1, 0)  # Adjusted row index if needed (seems okay)
        self.sanchez_res_combo = QComboBox()
        self.sanchez_res_combo.addItems([
            self.tr("0.5"),
            self.tr("1"),
            self.tr("2"),
            self.tr("4"),
        ])  # Keep other Sanchez options here
        self.sanchez_res_combo.setCurrentText("4")
        sanchez_layout.addWidget(self.sanchez_res_combo, 1, 1)
        self.sanchez_res_km_combo = self.sanchez_res_combo  # Alias

        # Create a completely redesigned start button implementation
        self.start_button = SuperButton(self.tr("START"))
        self.start_button.setObjectName("start_button")
        self.start_button.setToolTip("Start video interpolation processing")
        self.start_button.setMinimumHeight(50)
        self.start_button.setEnabled(True)  # Initially enabled for debugging
        WidgetFactory.update_widget_style(self.start_button, "StartButton")

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
        LOGGER.debug("MainWindow has _handle_processing method: %s", has_processing_handler)

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
            except Exception:
                LOGGER.exception("Failed to verify/connect processing_started signal")
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

    def _setup_update_manager(self) -> None:
        """Initialize UpdateManager integration for efficient UI updates."""
        # Register common UI update operations with the global UpdateManager
        register_update("main_tab_preview_update", self._update_preview_displays, priority=1)
        register_update("main_tab_ui_state", self._update_ui_state_internal, priority=2)
        register_update("main_tab_crop_buttons", self._update_crop_buttons_state, priority=0)
        register_update("main_tab_start_button", self._update_start_button_state, priority=2)

        LOGGER.debug("UpdateManager integration set up for MainTab")

    def _update_ui_state_internal(self) -> None:
        """Internal method for batched UI state updates."""
        # This replaces multiple individual update calls with a single batched operation
        self._update_rife_ui_elements()
        # Could include other related UI updates here

    def _update_preview_displays(self) -> None:
        """Update preview displays through UpdateManager."""
        # This would replace direct preview updates with batched ones
        if self.main_window_preview_signal:
            self.main_window_preview_signal.emit()

    # Drag and Drop functionality (enhanced features from EnhancedMainTab concepts)
    def dragEnterEvent(self, event) -> None:
        """Handle drag enter events for file drops."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            # Add visual feedback
            self.setProperty("drag_active", True)
            self.setStyleSheet(self.styleSheet() + " MainTab[drag_active='true'] { border: 2px dashed #4CAF50; }")

    def dragLeaveEvent(self, event) -> None:
        """Handle drag leave events."""
        self.setProperty("drag_active", False)
        # Remove visual feedback
        self.setStyleSheet(
            self.styleSheet().replace(" MainTab[drag_active='true'] { border: 2px dashed #4CAF50; }", "")
        )

    def dropEvent(self, event) -> None:
        """Handle file drop events."""
        self.setProperty("drag_active", False)
        self.setStyleSheet(
            self.styleSheet().replace(" MainTab[drag_active='true'] { border: 2px dashed #4CAF50; }", "")
        )

        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                file_path = Path(urls[0].toLocalFile())
                self._handle_dropped_file(file_path)
                event.acceptProposedAction()

    def _handle_dropped_file(self, file_path: Path) -> None:
        """Handle a dropped file, setting appropriate input/output paths."""
        if file_path.is_dir():
            # Directory dropped - set as input directory
            if hasattr(self.main_window_ref, "in_dir_edit"):
                self.main_window_ref.in_dir_edit.setText(str(file_path))
                self.main_window_ref.in_dir = file_path
                LOGGER.info("Input directory set via drag & drop: %s", file_path)

                # Show notification using UpdateManager for batched updates
                if hasattr(self.main_window_ref, "status_bar"):
                    self.main_window_ref.status_bar.showMessage(f"Input directory: {file_path.name}", 3000)

        elif file_path.suffix.lower() in {".mp4", ".avi", ".mov", ".mkv", ".webm"}:
            # Video file dropped - set as output file
            self.out_file_path = file_path
            self.out_file_edit.setText(str(file_path))
            LOGGER.info("Output file set via drag & drop: %s", file_path)

            # Show notification
            if hasattr(self.main_window_ref, "status_bar"):
                self.main_window_ref.status_bar.showMessage(f"Output file: {file_path.name}", 3000)

        elif file_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
            # Image file dropped - set parent directory as input
            parent_dir = file_path.parent
            if hasattr(self.main_window_ref, "in_dir_edit"):
                self.main_window_ref.in_dir_edit.setText(str(parent_dir))
                self.main_window_ref.in_dir = parent_dir
                LOGGER.info("Input directory set from image file via drag & drop: %s", parent_dir)

                # Show notification
                if hasattr(self.main_window_ref, "status_bar"):
                    self.main_window_ref.status_bar.showMessage(f"Input directory: {parent_dir.name}", 3000)

    def request_ui_update(self, update_type: str = "ui_state") -> None:
        """Request a UI update through the UpdateManager.

        Args:
            update_type: Type of update to request (ui_state, preview, crop_buttons, start_button)
        """
        update_id = f"main_tab_{update_type}"
        request_update(update_id)

    # --- Signal Handlers and UI Update Methods ---

    def _on_in_dir_changed(self, text: str) -> None:
        """Handle changes to the input directory text."""
        # Update MainWindow's in_dir state using the stored reference
        LOGGER.debug("Updating MainWindow in_dir via main_window_ref: %s", text)
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
            LOGGER.debug("Input directory selected: %s", dir_path)
            # Setting text triggers _on_in_dir_changed, which updates MainWindow state via main_window_ref
            self.in_dir_edit.setText(dir_path)

    def _pick_out_file(self) -> None:
        """Select the output file path."""
        LOGGER.debug("Entering _pick_out_file...")

        # Get starting directory/file
        start_dir = ""
        start_file = ""
        if self.out_file_path:
            LOGGER.debug("Current out_file_path: %s", self.out_file_path)
            if self.out_file_path.parent and self.out_file_path.parent.exists():
                start_dir = str(self.out_file_path.parent)
                LOGGER.debug("Using parent dir for file dialog: %s", start_dir)
            start_file = str(self.out_file_path)
            LOGGER.debug("Using current path for file dialog: %s", start_file)

        # If we have an input directory but no output file yet, suggest a file path based on input
        if not start_file and not start_dir:
            main_window = self.main_window_ref
            current_in_dir = getattr(main_window, "in_dir", None)
            if current_in_dir and current_in_dir.exists():
                # Use input directory name + timestamped output name for uniqueness
                from datetime import datetime

                timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                dir_name = current_in_dir.name
                start_dir = str(current_in_dir.parent)
                suggested_name = f"{dir_name}_output_{timestamp}.mp4"
                start_file = str(current_in_dir.parent / suggested_name)
                LOGGER.debug("Suggesting timestamped output file: %s", start_file)

        # Get save filename
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Output Video", start_file or start_dir, "MP4 Files (*.mp4)"
        )

        if file_path:
            LOGGER.debug("Output file selected: %s", file_path)
            # Double check file has .mp4 extension
            if not file_path.lower().endswith(".mp4"):
                file_path += ".mp4"
                LOGGER.debug("Added .mp4 extension: %s", file_path)

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
            image_files = self._get_image_files_for_crop(cast("Path", current_in_dir))
            if not image_files:
                return

            first_image_path = image_files[0]
            LOGGER.debug("Preparing image for crop dialog: %s", first_image_path)

            full_res_qimage = self._prepare_image_for_crop_dialog(first_image_path)
            if full_res_qimage is None or full_res_qimage.isNull():
                self._show_crop_image_error(first_image_path)
                return

            self._execute_crop_dialog(full_res_qimage)

        except Exception as e:
            LOGGER.exception("Error in _on_crop_clicked for %s", current_in_dir)
            QMessageBox.critical(
                self,
                "Error",
                f"An unexpected error occurred during cropping setup: {e}",
            )

    def _log_crop_debug_info(self) -> None:
        """Log debug information for crop operation."""
        try:
            mw_ref = self.main_window_ref
            LOGGER.debug("_on_crop_clicked: main_window_ref type: %s", type(mw_ref))
            in_dir_check = getattr(mw_ref, "in_dir", "AttributeMissing")
            LOGGER.debug("_on_crop_clicked: Accessed main_window_ref.in_dir: %s", in_dir_check)
            crop_rect_check = getattr(mw_ref, "current_crop_rect", "AttributeMissing")
            LOGGER.debug("_on_crop_clicked: Accessed main_window_ref.current_crop_rect: %s", crop_rect_check)
        except Exception:
            LOGGER.exception("_on_crop_clicked: Error accessing main_window_ref attributes early")

    def _validate_input_directory_for_crop(self, current_in_dir: Path | None) -> bool:
        """Validate that input directory is suitable for cropping."""
        if not current_in_dir or not current_in_dir.is_dir():
            LOGGER.warning("No input directory selected for cropping.")
            QMessageBox.warning(self, "Warning", "Please select an input directory first.")
            return False
        return True

    def _get_image_files_for_crop(self, current_in_dir: Path) -> list[Path]:
        """Get sorted list of image files from directory."""
        image_files = sorted([
            f for f in current_in_dir.iterdir() if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
        ])
        LOGGER.debug("Found %s image files in %s", len(image_files), current_in_dir)

        if not image_files:
            LOGGER.warning("No images found in the input directory to crop.")
            QMessageBox.warning(self, "Warning", "No images found in the input directory to crop.")

        return image_files

    def _prepare_image_for_crop_dialog(self, first_image_path: Path) -> QImage | None:
        """Prepare image for crop dialog, handling Sanchez processing if needed."""
        is_sanchez = self.sanchez_false_colour_checkbox.isChecked()
        LOGGER.debug("Sanchez checked: %s", is_sanchez)

        full_res_qimage = None

        if is_sanchez:
            full_res_qimage = self._try_get_sanchez_image_for_crop(first_image_path)

        # Fallback to original image if Sanchez failed or wasn't used
        if full_res_qimage is None or full_res_qimage.isNull():
            full_res_qimage = MainTab._load_original_image_for_crop(first_image_path)

        return full_res_qimage

    def _try_get_sanchez_image_for_crop(self, first_image_path: Path) -> QImage | None:
        """Try to get Sanchez-processed image for cropping."""
        LOGGER.debug("Sanchez preview enabled. Trying to get/process Sanchez image.")

        # Check cache first
        sanchez_cache = getattr(self.main_window_ref, "sanchez_preview_cache", {})
        cached_np_array = sanchez_cache.get(first_image_path)

        if cached_np_array is not None:
            return MainTab._convert_cached_sanchez_to_qimage(cached_np_array, first_image_path)
        return self._process_fresh_sanchez_image(first_image_path)

    @staticmethod
    def _convert_cached_sanchez_to_qimage(
        cached_np_array: NDArray[np.float64], first_image_path: Path
    ) -> QImage | None:
        """Convert cached Sanchez array to QImage."""
        LOGGER.debug("Found cached Sanchez result for %s.", first_image_path.name)
        # Convert float64 array to uint8 for QImage conversion
        uint8_array = (cached_np_array * 255).astype(np.uint8)
        full_res_qimage = numpy_to_qimage(uint8_array)

        if full_res_qimage.isNull():
            LOGGER.error("Failed to convert cached Sanchez NumPy array to QImage.")
            return None

        return full_res_qimage

    def _process_fresh_sanchez_image(self, first_image_path: Path) -> QImage | None:
        """Process fresh Sanchez image for cropping."""
        LOGGER.debug("No cached Sanchez result for %s. Processing...", first_image_path.name)

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
            LOGGER.exception("Error processing image with Sanchez for cropping")
            QMessageBox.warning(
                self,
                "Warning",
                f"Could not process Sanchez image for cropping: {e}\\n\\nShowing original image instead.",
            )
            return None

    @staticmethod
    def _load_original_image_for_crop(first_image_path: Path) -> QImage | None:
        """Load original image for cropping."""
        LOGGER.debug("Loading original image for cropping (Sanchez not used or failed).")

        # Simple QImage loading as fallback
        full_res_qimage = QImage(str(first_image_path))

        if full_res_qimage.isNull():
            LOGGER.error("Failed to load original image for cropping.")
            return None

        LOGGER.debug("Successfully loaded original image for cropping.")
        return full_res_qimage

    def _load_original_image_data(self, image_path: Path) -> ImageData | None:
        """Load original image data using MainWindow's image loader."""
        loader = getattr(self.main_window_ref, "image_loader", None)
        if not loader:
            LOGGER.error("Could not access MainWindow's image_loader.")
            return None

        return cast("ImageData | None", loader.load(str(image_path)))

    def _show_crop_image_error(self, first_image_path: Path) -> None:
        """Show error message when image cannot be loaded for cropping."""
        LOGGER.error("Failed to load or process any image for cropping: %s", first_image_path)
        QMessageBox.critical(
            self,
            "Error",
            f"Could not load or process image for cropping: {first_image_path}",
        )

    def _execute_crop_dialog(self, full_res_qimage: QImage) -> None:
        """Execute the crop selection dialog and handle results."""
        LOGGER.debug("Opening CropSelectionDialog with image size: %s", full_res_qimage.size())

        initial_rect = self._get_initial_crop_rect()

        LOGGER.debug("Instantiating CropSelectionDialog...")
        dialog = CropSelectionDialog(full_res_qimage, initial_rect, self)

        LOGGER.debug("Calling dialog.exec()...")
        result_code = dialog.exec()
        LOGGER.debug("Dialog result code: %s", result_code)

        if result_code == QDialog.DialogCode.Accepted:
            self._handle_crop_dialog_accepted(dialog)
        else:
            LOGGER.info("Crop dialog cancelled.")

        LOGGER.debug("Exiting _on_crop_clicked.")

    def _get_initial_crop_rect(self) -> QRect | None:
        """Get initial crop rectangle from MainWindow state."""
        current_crop_rect_mw = getattr(self.main_window_ref, "current_crop_rect", None)
        if current_crop_rect_mw:
            x, y, w, h = current_crop_rect_mw
            initial_rect = QRect(x, y, w, h)
            LOGGER.debug("Using existing crop rect as initial: %s", initial_rect)
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
                LOGGER.info("Crop rectangle set to: %s", new_crop_rect_tuple)
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

        full_res_image = MainTab._extract_image_from_label(label)
        if not full_res_image:
            self._show_image_unavailable_dialog(label)
            return

        LOGGER.debug("Found full-resolution image on label. Preparing ImageViewerDialog.")

        processed_image_result = self._process_image_for_zoom(full_res_image)
        image_to_show, is_cropped_view = processed_image_result

        info_title = self._build_zoom_dialog_title(label, is_cropped_view)

        self._display_zoom_dialog(image_to_show, info_title)

    @staticmethod
    def _extract_image_from_label(label: ClickableLabel) -> QImage | None:
        """Extract and validate image from label."""
        full_res_image = getattr(label, "processed_image", None)

        if full_res_image and isinstance(full_res_image, QImage) and not full_res_image.isNull():
            return cast("QImage", full_res_image)

        return None

    def _process_image_for_zoom(self, full_res_image: QImage) -> tuple[QImage, bool]:
        """Process image for zoom view, applying crop if needed."""
        crop_rect_tuple = getattr(self.main_window_ref, "current_crop_rect", None)

        if not crop_rect_tuple:
            LOGGER.debug("No crop rectangle found, showing full image in zoom.")
            return full_res_image, False

        try:
            return MainTab._apply_crop_to_image(full_res_image, crop_rect_tuple)
        except Exception:
            LOGGER.exception("Error applying crop in _show_zoom")
            return full_res_image, False

    @staticmethod
    def _apply_crop_to_image(full_res_image: QImage, crop_rect_tuple: tuple[int, int, int, int]) -> tuple[QImage, bool]:
        """Apply crop rectangle to image if valid."""
        x, y, w, h = crop_rect_tuple
        crop_qrect = QRect(x, y, w, h)
        img_rect = full_res_image.rect()

        if not img_rect.contains(crop_qrect):
            LOGGER.warning("Crop rectangle %s is outside image bounds %s. Showing full image.", crop_qrect, img_rect)
            return full_res_image, False

        LOGGER.debug("Applying crop %s to zoom view.", crop_qrect)
        cropped_qimage = full_res_image.copy(crop_qrect)

        if cropped_qimage.isNull():
            LOGGER.error("Failed to crop QImage.")
            return full_res_image, False

        LOGGER.debug("Cropped image size for zoom: %s", cropped_qimage.size())
        return cropped_qimage, True

    def _build_zoom_dialog_title(self, label: ClickableLabel, is_cropped_view: bool) -> str:
        """Build title for zoom dialog with preview information."""
        preview_type = self._get_preview_type(label)
        info_title = preview_type

        info_title = self._add_crop_info_to_title(info_title, is_cropped_view)
        return MainTab._add_file_info_to_title(info_title, label)

    def _get_preview_type(self, label: ClickableLabel) -> str:
        """Get preview type based on which label was clicked."""
        if label == self.first_frame_label:
            return "First Frame"
        if label == self.middle_frame_label:
            return "Middle Frame"
        if label == self.last_frame_label:
            return "Last Frame"
        return ""

    def _add_crop_info_to_title(self, info_title: str, is_cropped_view: bool) -> str:
        """Add crop information to dialog title."""
        crop_rect_tuple = getattr(self.main_window_ref, "current_crop_rect", None)

        if is_cropped_view and crop_rect_tuple and len(crop_rect_tuple) >= CROP_RECT_COMPONENTS:
            info_title += f" (Cropped: {crop_rect_tuple[2]}x{crop_rect_tuple[3]})"
        elif crop_rect_tuple is not None:
            info_title += " (Full Image - Crop Disabled)"

        return info_title

    @staticmethod
    def _add_file_info_to_title(info_title: str, label: ClickableLabel) -> str:
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

        # Extract title and info text
        title = info_title.replace("🔍 ", "")
        info_text = f"{image_to_show.width()}x{image_to_show.height()}"

        self.image_viewer_dialog = ImageViewerDialog(image=image_to_show, title=title, info_text=info_text)

        LOGGER.debug("Opening ImageViewerDialog - Title: %s", title)
        LOGGER.debug("Image dimensions: %sx%s", image_to_show.width(), image_to_show.height())

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
        msg += MainTab._get_image_unavailable_reason(label)
        msg += "\n\nTry updating previews or verifying the input directory."

        QMessageBox.information(self, "Preview Not Available", msg)

    @staticmethod
    def _get_image_unavailable_reason(label: ClickableLabel) -> str:
        """Get specific reason why image is unavailable."""
        if not hasattr(label, "processed_image"):
            return "\n\nReason: No processed image data is attached to this preview."
        if label.processed_image is None:
            return "\n\nReason: The processed image data is null."
        if not isinstance(label.processed_image, QImage):
            return f"\n\nReason: The image data is not a QImage (found {type(label.processed_image)})."
        if label.processed_image.isNull():
            return "\n\nReason: The image is empty or invalid."
        return ""

    def _enhance_preview_area(self) -> QGroupBox:
        """Create the group box containing the preview image labels."""
        previews_group = WidgetFactory.create_group_box(self.tr("Previews"))
        # Add icon to group box title
        previews_group.setStyleSheet("QGroupBox::title { padding-left: 24px; }")
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

            title_label = WidgetFactory.create_label(preview_titles[i])
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setToolTip(self.tr("Click to zoom"))
            label.setMinimumSize(200, 200)  # Ensure reasonable minimum size for preview visibility
            label.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )  # Allow expanding but maintain minimum
            WidgetFactory.update_widget_style(label, "ImagePreview")  # Use theme class

            container_layout.addWidget(title_label)
            container_layout.addWidget(label, 1)  # Give label stretch factor
            previews_layout.addWidget(container)

        return previews_group

    def _create_processing_settings_group(self) -> QGroupBox:
        """Create the group box for general processing settings."""
        group = WidgetFactory.create_group_box(self.tr("Processing Settings"))
        # Add icon to group box title
        group.setStyleSheet("QGroupBox::title { padding-left: 24px; }")
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
        self.fps_spinbox.setToolTip("Target frames per second for the output video")
        fps_label = WidgetFactory.create_label(self.tr("Output FPS:"), style="standard")
        layout.addWidget(fps_label, 0, 0)
        layout.addWidget(self.fps_spinbox, 0, 1)

        self.multiplier_spinbox = QSpinBox()  # Renamed from mid_count_spinbox for clarity
        self.multiplier_spinbox.setRange(2, 16)  # Example range
        self.multiplier_spinbox.setValue(2)
        self.multiplier_spinbox.setToolTip("Number of frames to interpolate between each pair of input frames")
        multiplier_label = WidgetFactory.create_label(self.tr("Frame Multiplier:"), style="standard")
        layout.addWidget(multiplier_label, 1, 0)
        layout.addWidget(self.multiplier_spinbox, 1, 1)
        self.mid_count_spinbox = self.multiplier_spinbox  # Alias for compatibility if needed

        self.max_workers_spinbox = QSpinBox()
        cpu_cores = os.cpu_count()
        default_workers = max(1, cpu_cores // 2) if cpu_cores else 1
        self.max_workers_spinbox.setRange(1, os.cpu_count() or 1)
        self.max_workers_spinbox.setValue(default_workers)
        self.max_workers_spinbox.setToolTip("Number of parallel worker threads for processing")
        workers_label = WidgetFactory.create_label(self.tr("Max Workers:"), style="standard")
        layout.addWidget(workers_label, 2, 0)
        layout.addWidget(self.max_workers_spinbox, 2, 1)

        self.encoder_combo = QComboBox()
        self.encoder_combo.addItems([self.tr("RIFE"), self.tr("FFmpeg")])  # Add other encoders if supported
        self.encoder_combo.setToolTip("Select the video interpolation engine")
        encoder_label = WidgetFactory.create_label(self.tr("Encoder:"), style="standard")
        layout.addWidget(encoder_label, 3, 0)
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
            WidgetFactory.update_widget_style(self.rife_thread_spec_edit, "")
            return

        # Basic regex for N:N:N format (allows single digits or more)
        if re.fullmatch(r"\d+:\d+:\d+", text):
            WidgetFactory.update_widget_style(self.rife_thread_spec_edit, "")
        else:
            WidgetFactory.update_widget_style(self.rife_thread_spec_edit, "ValidationError")  # Use theme error class

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
        LOGGER.debug("in_dir_from_parent: %s", in_dir_from_parent)
        LOGGER.debug("in_dir_from_ref: %s", in_dir_from_ref)
        LOGGER.debug("in_dir_from_edit: %s", in_dir_from_edit)

        # Use main_window_ref for consistency
        main_window = self.main_window_ref
        current_in_dir = getattr(main_window, "in_dir", None)
        LOGGER.debug("Current input directory: %s, Output file: %s", current_in_dir, self.out_file_path)

        if not current_in_dir or not self.out_file_path:
            error_msg = f"Missing paths for processing: in_dir={current_in_dir}, out_file={self.out_file_path}"
            LOGGER.warning(error_msg)
            QMessageBox.warning(self, "Missing Paths", "Please select both input and output paths.")
            return

        # Check for files in input directory
        try:
            if current_in_dir and current_in_dir.is_dir():
                image_files = sorted([
                    f
                    for f in current_in_dir.iterdir()
                    if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
                ])
                LOGGER.debug("Found %s image files in input directory", len(image_files))
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
                LOGGER.warning("Input directory invalid or doesn't exist: %s", current_in_dir)
                QMessageBox.warning(
                    self,
                    "Invalid Directory",
                    "The selected input directory is invalid or doesn't exist.",
                )
                return
        except Exception as e:
            LOGGER.exception("Error checking input directory")
            QMessageBox.critical(self, "Error", f"Error checking input directory: {e}")
            return

        # Get processing arguments
        LOGGER.debug("Gathering processing arguments...")
        args = self.get_processing_args()

        if args:
            # Deep verify the processing arguments
            self._deep_verify_args(args)

            LOGGER.info("Starting processing with args: %s", args)

            # Update GUI state before emitting signal
            LOGGER.debug("Setting processing state to True")
            self.set_processing_state(True)

            LOGGER.debug("=== Emitting processing_started signal ===")
            # Check if main_window has the handler method (can't directly check connected slots in PyQt6)
            main_window = self.main_window_ref
            has_handler = hasattr(main_window, "_handle_processing")
            LOGGER.debug("MainWindow has processing handler method: %s", has_handler)

            try:
                self._start_worker(args)
            except Exception as signal_error:
                LOGGER.exception("Error starting worker")
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
        LOGGER.debug("Has valid input directory: %s", has_in_dir)

        # Check output file
        has_out_file = bool(self.out_file_path)
        LOGGER.debug("Has output file path: %s", has_out_file)

        # Check encoder specific requirements
        current_encoder = self.encoder_combo.currentText()
        LOGGER.debug("Current encoder: %s", current_encoder)

        encoder_ok = True
        if current_encoder == "RIFE":
            model_key = self.rife_model_combo.currentData()
            encoder_ok = bool(model_key)
            LOGGER.debug("RIFE model selected: %s, valid: %s", model_key, encoder_ok)

        # Final state check
        should_be_enabled = has_in_dir and has_out_file and encoder_ok and not self.is_processing
        LOGGER.debug("Start button should be enabled: %s", should_be_enabled)

        # Compare with actual state
        actual_enabled = self.start_button.isEnabled()
        LOGGER.debug("Start button is actually enabled: %s", actual_enabled)

        if should_be_enabled != actual_enabled:
            LOGGER.warning("Start button state mismatch! Should be: %s, Is: %s", should_be_enabled, actual_enabled)

        return should_be_enabled

    def _deep_verify_args(self, args: dict[str, Any]) -> None:
        """Perform a deep verification of processing arguments for debugging."""
        LOGGER.debug("Deep verification of processing arguments...")

        MainTab._verify_critical_paths(args)
        MainTab._verify_encoder_arguments(args)
        self._verify_crop_rectangle(args)
        MainTab._verify_processing_parameters(args)

    @staticmethod
    def _verify_critical_paths(args: dict[str, Any]) -> None:
        """Verify input and output path arguments."""
        MainTab._verify_input_directory(args)
        MainTab._verify_output_file(args)

    @staticmethod
    def _verify_input_directory(args: dict[str, Any]) -> None:
        """Verify input directory exists and is accessible."""
        in_dir = args.get("in_dir")
        if not in_dir:
            LOGGER.error("Missing required argument: in_dir")
            return

        exists = in_dir.exists()
        is_dir = in_dir.is_dir() if exists else False
        LOGGER.debug("in_dir: %s, exists: %s, is_dir: %s", in_dir, exists, is_dir)

        if exists and is_dir:
            MainTab._check_input_directory_contents(in_dir)

    @staticmethod
    def _verify_output_file(args: dict[str, Any]) -> None:
        """Verify output file path and directory writability."""
        out_file = args.get("out_file")
        if not out_file:
            LOGGER.error("Missing required argument: out_file")
            return

        out_dir = out_file.parent
        dir_exists = out_dir.exists()
        dir_writable = os.access(str(out_dir), os.W_OK) if dir_exists else False
        LOGGER.debug("out_file: %s, dir_exists: %s, dir_writable: %s", out_file, dir_exists, dir_writable)

    @staticmethod
    def _verify_encoder_arguments(args: dict[str, Any]) -> None:
        """Verify encoder-specific arguments."""
        encoder = args.get("encoder")
        LOGGER.debug("encoder: %s", encoder)

        if encoder == "RIFE":
            MainTab._verify_rife_arguments(args)
        elif encoder == "FFmpeg":
            MainTab._verify_ffmpeg_arguments(args)

    @staticmethod
    def _verify_rife_arguments(args: dict[str, Any]) -> None:
        """Verify RIFE-specific arguments."""
        rife_model_key = args.get("rife_model_key")
        rife_model_path = args.get("rife_model_path")
        rife_exe_path = args.get("rife_exe_path")

        LOGGER.debug("rife_model_key: %s", rife_model_key)
        LOGGER.debug("rife_model_path: %s", rife_model_path)
        LOGGER.debug("rife_exe_path: %s", rife_exe_path)

        if rife_exe_path:
            exe_exists = rife_exe_path.exists()
            exe_executable = os.access(str(rife_exe_path), os.X_OK) if exe_exists else False
            LOGGER.debug("rife_exe_path exists: %s, executable: %s", exe_exists, exe_executable)
        else:
            LOGGER.error("Missing required RIFE executable path")

    @staticmethod
    def _verify_ffmpeg_arguments(args: dict[str, Any]) -> None:
        """Verify FFmpeg-specific arguments."""
        LOGGER.debug("Checking FFmpeg-specific arguments...")
        ffmpeg_args = args.get("ffmpeg_args")

        if ffmpeg_args:
            LOGGER.debug("FFmpeg arguments provided: %s", ffmpeg_args)
            MainTab._log_ffmpeg_settings(ffmpeg_args)
        else:
            LOGGER.warning("No FFmpeg arguments provided")
            MainTab._debug_generate_ffmpeg_command(args)

    @staticmethod
    def _log_ffmpeg_settings(ffmpeg_args: dict[str, Any]) -> None:
        """Log FFmpeg settings for verification."""
        if "profile" in ffmpeg_args:
            profile_name = ffmpeg_args.get("profile")
            LOGGER.debug("FFmpeg profile: %s", profile_name)

        if "crf" in ffmpeg_args:
            crf = ffmpeg_args.get("crf")
            LOGGER.debug("FFmpeg CRF: %s", crf)

        if "bitrate" in ffmpeg_args:
            bitrate = ffmpeg_args.get("bitrate")
            LOGGER.debug("FFmpeg bitrate: %s", bitrate)

    def _verify_crop_rectangle(self, args: dict[str, Any]) -> None:
        """Verify crop rectangle dimensions and validity."""
        crop_rect = args.get("crop_rect")
        if not crop_rect:
            LOGGER.debug("No crop rectangle specified")
            return

        LOGGER.debug("crop_rect: %s", crop_rect)

        try:
            x, y, w, h = crop_rect
            LOGGER.debug("Crop dimensions - x: %s, y: %s, width: %s, height: %s", x, y, w, h)

            if w <= 0 or h <= 0:
                LOGGER.error("Invalid crop rectangle dimensions: width=%s, height=%s", w, h)
                return

            MainTab._verify_crop_against_input_images(args, crop_rect)
            self._debug_check_ffmpeg_crop_integration(crop_rect)

        except (ValueError, TypeError):
            LOGGER.exception("Invalid crop rectangle format")

    @staticmethod
    def _verify_crop_against_input_images(args: dict[str, Any], crop_rect: tuple[int, int, int, int]) -> None:
        """Verify crop rectangle against actual image dimensions."""
        in_dir = args.get("in_dir")
        if in_dir is not None:
            in_dir_path = Path(in_dir) if isinstance(in_dir, str) else in_dir
            MainTab._verify_crop_against_images(in_dir_path, crop_rect)

    @staticmethod
    def _verify_processing_parameters(args: dict[str, Any]) -> None:
        """Verify other processing parameters."""
        parameters = {
            "fps": args.get("fps"),
            "multiplier": args.get("multiplier"),
            "max_workers": args.get("max_workers"),
            "sanchez_enabled": args.get("sanchez_enabled"),
            "sanchez_resolution_km": args.get("sanchez_resolution_km"),
        }

        for param_name, param_value in parameters.items():
            LOGGER.debug("%s: %s", param_name, param_value)

    @staticmethod
    def _check_input_directory_contents(in_dir: Path) -> None:
        """Check images in the input directory and report details for debugging."""
        try:
            image_files = sorted([
                f for f in in_dir.iterdir() if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
            ])

            LOGGER.debug("Found %s image files in %s", len(image_files), in_dir)

            if not image_files:
                LOGGER.warning("No image files found in input directory")
                return

            # Sample the first, middle, and last image for dimensions
            sample_indices = [0]
            if len(image_files) > MINIMUM_IMAGES_FOR_SAMPLING:
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
                    sample_stats.append({
                        "index": idx,
                        "filename": img_path.name,
                        "dimensions": img.size,
                        "shape": img_array.shape,
                        "dtype": str(img_array.dtype),
                    })
                except Exception:
                    LOGGER.exception("Error analyzing image %s", image_files[idx])

            LOGGER.debug("Sample image stats: %s", sample_stats)

        except Exception:
            LOGGER.exception("Error checking input directory contents")

    @staticmethod
    def _verify_crop_against_images(in_dir: Path, crop_rect: tuple[int, int, int, int]) -> None:
        """Verify that crop rectangle is valid for the images in the directory."""
        try:
            image_files = sorted([
                f for f in in_dir.iterdir() if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
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

            within_bounds = (
                0 <= x < img_width
                and 0 <= y < img_height
                and 0 < crop_right <= img_width
                and 0 < crop_bottom <= img_height
            )

            LOGGER.debug("Image dimensions: %sx%s", img_width, img_height)
            LOGGER.debug("Crop rectangle: (%s, %s, %s, %s)", x, y, w, h)
            LOGGER.debug("Crop bottom-right: (%s, %s)", crop_right, crop_bottom)
            LOGGER.debug("Crop within bounds: %s", within_bounds)

            if not within_bounds:
                LOGGER.warning(
                    "Crop rectangle (%s, %s, %s, %s) exceeds image dimensions (%sx%s)",
                    x,
                    y,
                    w,
                    h,
                    img_width,
                    img_height,
                )

            # Calculate percentages for context
            crop_width_percent = (w / img_width) * 100
            crop_height_percent = (h / img_height) * 100
            crop_area_percent = (w * h) / (img_width * img_height) * 100

            LOGGER.debug("Crop width: %spx (%.1f%% of image width)", w, crop_width_percent)
            LOGGER.debug("Crop height: %spx (%.1f%% of image height)", h, crop_height_percent)
            LOGGER.debug("Crop area: %spx² (%.1f%% of image area)", w * h, crop_area_percent)

        except Exception:
            LOGGER.exception("Error verifying crop against images")

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
            LOGGER.debug("FFmpeg crop filter would be: %s", crop_filter)

            # Check for potential issues with odd dimensions (h264/h265 requirement)
            has_odd_dimensions = w % 2 != 0 or h % 2 != 0
            if has_odd_dimensions:
                LOGGER.warning("Crop dimensions (%sx%s) have odd values, which may cause issues with some codecs", w, h)
                # Suggest fixed dimensions
                fixed_w = w + (1 if w % 2 != 0 else 0)
                fixed_h = h + (1 if h % 2 != 0 else 0)
                LOGGER.debug("Suggested fixed dimensions: %sx%s", fixed_w, fixed_h)

        except Exception:
            LOGGER.exception("Error checking FFmpeg crop integration")

    @staticmethod
    def _debug_generate_ffmpeg_command(args: dict[str, Any]) -> None:
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

            LOGGER.debug("Sample FFmpeg command with crop/fps: %s", " ".join(command))

        except Exception:
            LOGGER.exception("Error generating sample FFmpeg command")

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
        browse_buttons = self.findChildren(QPushButton, "browse_button")
        if len(browse_buttons) > 0:
            in_browse_button = browse_buttons[0]
            in_browse_button.setEnabled(not is_processing)
        if len(browse_buttons) > 1:
            out_browse_button = browse_buttons[1]
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

    def _generate_timestamped_output_path(self, base_dir: Path | None = None, base_name: str | None = None) -> Path:
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
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        return base_dir / f"{base_name}_output_{timestamp}.mp4"

    def _direct_start_handler(self) -> None:
        """Simplified handler for the start button that directly calls main processing code.

        This handler is more reliable as it avoids complex signal connections and
        directly executes the processing workflow.
        """
        LOGGER.info("Direct start handler called")

        try:
            # Step 1: Ensure valid output path
            if not self._ensure_valid_output_path():
                return

            # Step 2: Validate input directory and get image files
            current_in_dir, image_files = self._validate_input_directory()
            if not current_in_dir or not image_files:
                return

            # Step 3: Prepare processing arguments
            args = self._prepare_processing_arguments()
            if not args:
                return

            # Step 4: Start the actual processing
            self._execute_processing(args, current_in_dir, image_files)

        except Exception as e:
            LOGGER.exception("Error in direct start handler")
            self._handle_start_error(e)

    def _ensure_valid_output_path(self) -> bool:
        """Ensure we have a valid output path, generating one if necessary.

        Returns:
            True if valid output path is available, False otherwise
        """
        # Generate fresh timestamped path if we have an existing one
        if self.out_file_path:
            base_dir, base_name = self._extract_output_path_components()
            fresh_output_path = self._generate_timestamped_output_path(base_dir, base_name)
            self._update_output_path_ui(fresh_output_path)
            return True

        # Generate default path if none exists
        return self._generate_default_output_path()

    def _extract_output_path_components(self) -> tuple[Path, str]:
        """Extract directory and base name from existing output path.

        Returns:
            Tuple of (directory, base_name)
        """
        base_dir = self.out_file_path.parent
        filename = self.out_file_path.stem

        # Try to extract original name before timestamp
        match = re.match(r"(.+?)_output_\d{8}_\d{6}", filename)
        if match:
            base_name = match.group(1)
        elif "_output" in filename:
            base_name = filename.split("_output")[0]
        else:
            base_name = filename

        return base_dir, base_name

    def _update_output_path_ui(self, output_path: Path) -> None:
        """Update UI with new output path."""
        self.out_file_path = output_path
        self.out_file_edit.setText(str(output_path))
        LOGGER.debug("Updated output path: %s", output_path)

        # Show notification in status bar
        main_window = self.main_window_ref
        if hasattr(main_window, "status_bar"):
            main_window.status_bar.showMessage(f"Using output file: {output_path.name}", 5000)

    def _generate_default_output_path(self) -> bool:
        """Generate a default output path when none exists.

        Returns:
            True if default path was generated successfully, False otherwise
        """
        LOGGER.info("No output file selected - auto-generating default output path")

        current_in_dir = getattr(self.main_window_ref, "in_dir", None)
        if not current_in_dir or not current_in_dir.is_dir():
            QMessageBox.warning(
                self,
                "Input Directory Required",
                "Please select a valid input directory first.",
            )
            return False

        # Create timestamped default output path
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        default_output = current_in_dir.parent / f"{current_in_dir.name}_output_{timestamp}.mp4"
        self._update_output_path_ui(default_output)

        # Show notification
        if hasattr(self.main_window_ref, "status_bar"):
            self.main_window_ref.status_bar.showMessage(f"Auto-generated output file: {default_output.name}", 5000)

        return True

    def _validate_input_directory(self) -> tuple[Path | None, list[Path] | None]:
        """Validate input directory and return image files.

        Returns:
            Tuple of (input_directory, image_files) or (None, None) if invalid
        """
        current_in_dir = getattr(self.main_window_ref, "in_dir", None)

        # Check if directory exists
        if not current_in_dir or not current_in_dir.is_dir():
            QMessageBox.warning(
                self,
                "Input Directory Required",
                "Please select a valid input directory containing images.",
            )
            return None, None

        # Find image files
        try:
            image_files = sorted([
                f for f in current_in_dir.iterdir() if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
            ])

            if not image_files:
                QMessageBox.warning(
                    self,
                    "No Images Found",
                    f"No image files found in {current_in_dir}.\nPlease select a directory with images.",
                )
                return None, None

            LOGGER.info("Found %d image files in %s", len(image_files), current_in_dir)
            return current_in_dir, image_files

        except Exception as e:
            LOGGER.exception("Error checking for images")
            QMessageBox.critical(self, "Error", f"Error checking input directory: {e}")
            return None, None

    def _prepare_processing_arguments(self) -> dict | None:
        """Prepare and validate processing arguments.

        Returns:
            Processing arguments dict or None if validation failed
        """
        args = self.get_processing_args()
        if not args:
            LOGGER.error("Failed to generate processing arguments")
            return None
        return args

    def _execute_processing(self, args: dict, input_dir: Path, image_files: list[Path]) -> None:
        """Execute the actual processing with the given arguments.

        Args:
            args: Processing arguments
            input_dir: Input directory path
            image_files: List of image file paths
        """
        # Update UI to show processing started
        self.set_processing_state(True)

        # Show processing confirmation
        QMessageBox.information(
            self,
            "Processing Started",
            f"Starting video processing with {len(image_files)} images.\n\n"
            f"Input: {input_dir}\n"
            f"Output: {self.out_file_path}",
        )

        # Start processing
        try:
            LOGGER.info("Starting processing")
            self.processing_started.emit(args)

            # Fallback to direct method call if needed
            if hasattr(self.main_window_ref, "_handle_processing"):
                LOGGER.debug("Calling main_window._handle_processing directly as fallback")
                self.main_window_ref._handle_processing(args)

            LOGGER.info("Processing started successfully")

        except Exception:
            self.set_processing_state(False)  # Reset UI state
            raise  # Re-raise to be handled by caller

    def _handle_start_error(self, error: Exception) -> None:
        """Handle errors that occur during processing start.

        Args:
            error: The exception that occurred
        """
        LOGGER.error("Error starting processing")
        self.set_processing_state(False)  # Reset UI state

        # Show detailed error to user
        current_in_dir = getattr(self.main_window_ref, "in_dir", "Unknown")
        error_details = f"An error occurred: {error}\n\n"
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

            LOGGER.warning("Start button clicked but missing requirements: %s", error_msg)
            QMessageBox.warning(self, "Missing Requirements", error_msg)

    def _diagnose_start_button(self) -> None:
        """Debug the start button state."""
        LOGGER.debug("----- START BUTTON DIAGNOSIS -----")

        # Check input directory
        main_window = self.main_window_ref
        current_in_dir = getattr(main_window, "in_dir", None)
        out_file = self.out_file_path

        LOGGER.debug("Input dir exists: %s", current_in_dir is not None)
        if current_in_dir:
            LOGGER.debug("Input dir path: %s", current_in_dir)
            LOGGER.debug("Input dir is directory: %s", current_in_dir.is_dir() if current_in_dir else False)

        LOGGER.debug("Output file exists: %s", out_file is not None)
        if out_file:
            LOGGER.debug("Output file path: %s", out_file)

        # Check RIFE model
        encoder = self.encoder_combo.currentText()
        LOGGER.debug("Encoder: %s", encoder)

        if encoder == "RIFE":
            model_key = self.rife_model_combo.currentData()
            LOGGER.debug("RIFE model key: %s", model_key)

        LOGGER.debug("Is processing: %s", self.is_processing)

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
                    LOGGER.debug("%s text: %s", key, widget.text())
                elif hasattr(widget, "currentText"):
                    LOGGER.debug("%s currentText: %s", key, widget.currentText())
                elif hasattr(widget, "value"):
                    LOGGER.debug("%s value: %s", key, widget.value())
            except Exception:
                LOGGER.exception("Error getting value for %s", key)

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
            "Start button check: has_paths=%s, in_dir=%s, out_file=%s", has_paths, current_in_dir, self.out_file_path
        )

        # Check RIFE model only if RIFE is selected encoder
        rife_ok = True
        if self.encoder_combo.currentText() == "RIFE":
            rife_ok = bool(self.rife_model_combo.currentData())  # Check if a valid model is selected
            LOGGER.debug("Start button check: RIFE selected, model_ok=%s", rife_ok)

        can_start = bool(has_paths and rife_ok and not self.is_processing)
        LOGGER.debug("Start button should be enabled: %s", can_start)

        # Update button state
        self.start_button.setEnabled(can_start)

        # Update button text and style
        if self.is_processing:
            # Processing mode
            self.start_button.setText(self.tr("Cancel"))
            WidgetFactory.update_widget_style(self.start_button, "CancelButton")
        # Ready or disabled mode
        elif can_start:
            self.start_button.setText(self.tr("START"))
            WidgetFactory.update_widget_style(self.start_button, "StartButton")
        else:
            self.start_button.setText(self.tr("START"))
            WidgetFactory.update_widget_style(self.start_button, "StartButtonDisabled")

        # Print debug info about button state
        LOGGER.debug("Start button enabled: %s", self.start_button.isEnabled())

    @pyqtSlot(bool, str)
    def _on_processing_finished(self, success: bool, message: str) -> None:
        """Handle the processing finished signal from the worker."""
        LOGGER.info("MainTab received processing finished: Success=%s, Message=%s", success, message)
        self.set_processing_state(False)
        self.processing_finished.emit(success, message)  # Forward the signal
        if success:
            QMessageBox.information(self, "Success", f"Video interpolation finished!\nOutput: {message}")
        # Error message handled by _on_processing_error

    def _on_processing_error(self, error_message: str) -> None:
        """Handle processing errors."""
        LOGGER.error("MainTab received processing error: %s", error_message)
        self.set_processing_state(False)
        self.processing_finished.emit(False, error_message)  # Forward the signal
        QMessageBox.critical(self, "Error", f"Processing failed:\n{error_message}")

    def _on_worker_progress(self, current: int, total: int, eta: float) -> None:
        """Update progress through the view model."""
        try:
            self.processing_vm.update_progress(current, total, eta)
        except Exception:  # pragma: no cover - UI update errors
            LOGGER.exception("Progress update failed")

    def _start_worker(self, args: dict[str, Any]) -> None:
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
            "_update_crop_buttons_state: Checking conditions - has_in_dir=%s, has_crop=%s", has_in_dir, has_crop
        )  # Original DEBUG log
        self.crop_button.setEnabled(has_in_dir)
        # Enable clear button only if both input dir and crop exist
        self.clear_crop_button.setEnabled(has_in_dir and has_crop)

        # LOGGER.debug("_update_crop_buttons_state: main_window=%s, ", main_window
        #              "has_in_dir=%s, has_crop=%s", has_in_dir, has_crop) # Original commented DEBUG log

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

        try:
            # Step 1: Load cached analysis
            cached_analysis = self._load_model_analysis_cache()

            # Step 2: Get available models
            found_models = self._get_available_models()
            if not found_models:
                return

            # Step 3: Process each model
            needs_cache_update = self._process_models(found_models, cached_analysis)

            # Step 4: Save cache if needed
            if needs_cache_update:
                self._save_model_analysis_cache(cached_analysis)

            # Step 5: Restore last selected model
            self._restore_selected_model()

            # Step 6: Update UI
            self._finalize_model_population()

        except Exception:
            LOGGER.exception("Error populating models")
            self._handle_model_population_error()

    def _load_model_analysis_cache(self) -> dict[str, RIFEModelDetails]:
        """Load cached model analysis from file.

        Returns:
            Dictionary of cached analysis results
        """
        cache_dir = get_cache_dir()
        analysis_cache_file = cache_dir / "rife_analysis_cache.json"
        cached_analysis: dict[str, RIFEModelDetails] = {}

        if analysis_cache_file.exists():
            try:
                with open(analysis_cache_file, encoding="utf-8") as f:
                    cached_analysis = json.load(f)
                LOGGER.debug("Loaded RIFE analysis cache from %s", analysis_cache_file)
            except Exception as e:
                LOGGER.warning("Failed to load RIFE analysis cache: %s", e)

        return cached_analysis

    def _get_available_models(self) -> list[str]:
        """Get list of available RIFE models.

        Returns:
            List of model names, or empty list if none found
        """
        found_models = get_available_rife_models()

        if not found_models:
            LOGGER.warning("No RIFE models found in the 'models' directory.")
            self.rife_model_combo.addItem("No Models Found", userData=None)
            self.rife_model_combo.setEnabled(False)
            return []

        self.rife_model_combo.setEnabled(True)
        return found_models

    def _process_models(self, found_models: list[str], cached_analysis: dict[str, RIFEModelDetails]) -> bool:
        """Process each found model and add to combo box.

        Args:
            found_models: List of model names to process
            cached_analysis: Cache of previous analysis results

        Returns:
            True if cache needs updating, False otherwise
        """
        needs_cache_update = False
        project_root = config.get_project_root()

        for key in found_models:
            model_dir = project_root / "models" / key
            rife_exe = config.find_rife_executable(key)

            if not rife_exe:
                LOGGER.warning("RIFE executable not found for model %r in %s", key, model_dir)
                continue

            # Get or analyze model details
            details, cache_updated = self._get_model_details(key, rife_exe, cached_analysis)
            if cache_updated:
                needs_cache_update = True

            # Add to available models and combo box
            self.available_models[key] = details
            self._add_model_to_combo(key, details)

        return needs_cache_update

    def _get_model_details(
        self, key: str, rife_exe: Path, cached_analysis: dict[str, RIFEModelDetails]
    ) -> tuple[RIFEModelDetails, bool]:
        """Get model details from cache or by analysis.

        Args:
            key: Model key/name
            rife_exe: Path to RIFE executable
            cached_analysis: Cache dictionary

        Returns:
            Tuple of (model_details, cache_was_updated)
        """
        exe_path_str = str(rife_exe)
        exe_mtime = os.path.getmtime(rife_exe)

        # Check cache first
        if exe_path_str in cached_analysis and cached_analysis[exe_path_str].get("_mtime") == exe_mtime:
            LOGGER.debug("Using cached analysis for %s (%s)", key, rife_exe.name)
            return cached_analysis[exe_path_str], False

        # Analyze executable
        LOGGER.info("Analyzing RIFE executable for model %r: %s", key, rife_exe)
        try:
            details_raw = analyze_rife_executable(rife_exe)
            details = cast("RIFEModelDetails", details_raw)
            details["_mtime"] = exe_mtime
            cached_analysis[exe_path_str] = details
            LOGGER.debug("Analysis complete for %s. Capabilities: %s", key, details.get("capabilities"))
            return details, True

        except Exception as e:
            LOGGER.exception("Failed to analyze RIFE executable for model %r", key)
            error_details = cast(
                "RIFEModelDetails",
                {
                    "version": "Error",
                    "capabilities": {},
                    "supported_args": [],
                    "help_text": f"Error: {e}",
                    "_mtime": exe_mtime,
                },
            )
            cached_analysis[exe_path_str] = error_details
            return error_details, True

    def _add_model_to_combo(self, key: str, details: RIFEModelDetails) -> None:
        """Add a model to the combo box with appropriate display name.

        Args:
            key: Model key/name
            details: Model analysis details
        """
        display_name = f"{key} (v{details.get('version', 'Unknown')})"
        if details.get("version") == "Error":
            display_name = f"{key} (Analysis Error)"
        self.rife_model_combo.addItem(display_name, userData=key)

    def _save_model_analysis_cache(self, cached_analysis: dict[str, RIFEModelDetails]) -> None:
        """Save updated model analysis cache to file.

        Args:
            cached_analysis: Cache dictionary to save
        """
        try:
            cache_dir = get_cache_dir()
            analysis_cache_file = cache_dir / "rife_analysis_cache.json"
            os.makedirs(cache_dir, exist_ok=True)

            with open(analysis_cache_file, "w", encoding="utf-8") as f:
                json.dump(cached_analysis, f, indent=4)
            LOGGER.debug("Saved updated RIFE analysis cache to %s", analysis_cache_file)

        except Exception as e:
            LOGGER.warning("Failed to save RIFE analysis cache: %s", e)

    def _restore_selected_model(self) -> None:
        """Restore the last selected model from settings."""
        last_model_key = self.tab_settings.get_model_key()
        index = self.rife_model_combo.findData(last_model_key)

        if index != -1:
            self.rife_model_combo.setCurrentIndex(index)
            LOGGER.debug("Restored last selected RIFE model: %s", last_model_key)
        elif self.rife_model_combo.count() > 0:
            self.rife_model_combo.setCurrentIndex(0)
            LOGGER.debug("Last selected RIFE model not found, selecting first available.")

    def _finalize_model_population(self) -> None:
        """Finalize model population by updating UI elements."""
        self._update_rife_ui_elements()
        self._update_start_button_state()

    def _handle_model_population_error(self) -> None:
        """Handle errors during model population."""
        self.rife_model_combo.clear()
        self.rife_model_combo.addItem("Error Loading Models", userData=None)
        self.rife_model_combo.setEnabled(False)

    def _on_model_selected(self, index: int) -> None:
        """Handle selection changes in the RIFE model combo box."""
        model_key = self.rife_model_combo.itemData(index)
        if model_key and model_key in self.available_models:
            self.current_model_key = model_key
            LOGGER.info("RIFE model selected: %s", model_key)
            self._update_rife_ui_elements()
            self._update_start_button_state()
        else:
            LOGGER.warning("Invalid model selected at index %s, data: %s", index, model_key)
            self.current_model_key = None  # Resetting seems safer. Type hint updated to Optional[str]
            self._update_rife_ui_elements()  # Disable options
            self._update_start_button_state()

    def get_processing_args(self) -> dict[str, Any] | None:
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
        MainTab._add_encoder_specific_arguments(args, encoder, rife_model_key, main_window)

        LOGGER.debug("Processing arguments gathered: %s", args)
        return args

    def _get_main_window_reference(self) -> QObject:
        """Get main window reference with fallback."""
        main_window = self.main_window_ref
        if not main_window:
            LOGGER.warning("main_window_ref is None, falling back to parent()")
            main_window = self.parent()
        return cast("QObject", main_window)

    def _validate_processing_inputs(self, main_window: QObject) -> tuple[Path, Any, str, str] | None:
        """Validate all required inputs for processing."""
        # Get critical parameters
        current_in_dir = getattr(main_window, "in_dir", None)
        current_crop_rect_mw = getattr(main_window, "current_crop_rect", None)
        LOGGER.debug("Input directory from main_window: %s", current_in_dir)
        LOGGER.debug("Crop rect from main_window: %s", current_crop_rect_mw)
        LOGGER.debug("Output file path: %s", self.out_file_path)

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

    def _validate_input_directory(self, current_in_dir: Path | None) -> bool:
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
            LOGGER.exception(error_msg)
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

    def _validate_encoder_and_model(self) -> tuple[str, str] | None:
        """Validate encoder selection and associated model."""
        encoder = self.encoder_combo.currentText()
        rife_model_key = self.rife_model_combo.currentData()
        LOGGER.debug("Selected encoder: %s", encoder)
        LOGGER.debug("Selected RIFE model: %s", rife_model_key)

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
                LOGGER.info("Creating output directory: %s", out_dir)
                out_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                error_msg = f"Could not create output directory: {e}"
                LOGGER.exception(error_msg)
                QMessageBox.critical(self, "Error", error_msg)
                return False
        return True

    def _build_base_arguments(
        self,
        current_in_dir: Path,
        current_crop_rect_mw: Any,
        encoder: str,
        rife_model_key: str,
    ) -> dict[str, Any]:
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

    def _add_rife_arguments(self, args: dict[str, Any], encoder: str, rife_model_key: str) -> None:
        """Add RIFE-specific arguments to args dictionary."""
        if encoder == "RIFE":
            args.update({
                "rife_model_key": rife_model_key,
                "rife_model_path": (config.get_project_root() / "models" / rife_model_key if rife_model_key else None),
                "rife_exe_path": (config.find_rife_executable(rife_model_key) if rife_model_key else None),
                "rife_tta_spatial": self.rife_tta_spatial_checkbox.isChecked(),
                "rife_tta_temporal": self.rife_tta_temporal_checkbox.isChecked(),
                "rife_uhd": self.rife_uhd_checkbox.isChecked(),
                "rife_tiling_enabled": self.rife_tile_checkbox.isChecked(),
                "rife_tile_size": self.rife_tile_size_spinbox.value(),
                "rife_thread_spec": (self.rife_thread_spec_edit.text() or None),
            })
        else:
            args.update({
                "rife_model_key": None,
                "rife_model_path": None,
                "rife_exe_path": None,
                "rife_tta_spatial": False,
                "rife_tta_temporal": False,
                "rife_uhd": False,
                "rife_tiling_enabled": False,
                "rife_tile_size": None,
                "rife_thread_spec": None,
            })

    @staticmethod
    def _add_encoder_specific_arguments(
        args: dict[str, Any],
        encoder: str,
        rife_model_key: str,
        main_window: QObject,
    ) -> None:
        """Add encoder-specific arguments."""
        if encoder == "FFmpeg":
            args["ffmpeg_args"] = MainTab._get_ffmpeg_arguments(main_window)
        else:
            args["ffmpeg_args"] = None

    @staticmethod
    def _get_ffmpeg_arguments(main_window: QObject) -> dict[str, Any]:
        """Get FFmpeg-specific arguments from FFmpeg tab."""
        ffmpeg_tab = getattr(main_window, "ffmpeg_tab", None)
        if ffmpeg_tab:
            try:
                ffmpeg_args: dict[str, Any] = getattr(ffmpeg_tab, "get_ffmpeg_args", dict)()
                LOGGER.debug("Added FFmpeg args from ffmpeg_tab: %s", ffmpeg_args)
                return ffmpeg_args
            except Exception:
                LOGGER.exception("Error getting FFmpeg args")
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
        except Exception:
            LOGGER.exception("Error loading settings")

    def _log_settings_debug_info(self) -> None:
        """Log debug information about settings storage."""
        org_name = self.settings.organizationName()
        app_name = self.settings.applicationName()
        filename = self.settings.fileName()
        LOGGER.debug("QSettings details: org=%s, app=%s, file=%s", org_name, app_name, filename)

        all_keys = self.settings.allKeys()
        LOGGER.debug("Available settings keys: %s", all_keys)

    def _load_input_output_settings(self, main_window: QObject) -> None:
        """Load input directory and output file settings."""
        LOGGER.debug("Loading input/output settings...")
        self._load_input_directory_setting(main_window)
        self._load_output_file_setting()

    def _load_input_directory_setting(self, main_window: QObject) -> None:
        """Load input directory setting with fallback logic."""
        LOGGER.debug("Loading input directory path...")

        try:
            in_dir_str = self.tab_settings.get_input_directory()
            LOGGER.debug("Raw input directory from settings: %r", in_dir_str)

            loaded_in_dir = MainTab._resolve_input_directory_path(in_dir_str)
            self._update_input_directory_ui(main_window, loaded_in_dir)
        except Exception:
            LOGGER.exception("Error loading input directory setting")
            self._update_input_directory_ui(main_window, None)

    @staticmethod
    def _resolve_input_directory_path(in_dir_str: str) -> Path | None:
        """Resolve input directory path with fallback to common locations."""
        if not in_dir_str:
            LOGGER.debug("No input directory string in settings")
            return None

        try:
            in_dir_path = Path(in_dir_str)
            exists = in_dir_path.exists()
            is_dir = in_dir_path.is_dir() if exists else False
            LOGGER.debug("Input path exists: %s, is directory: %s", exists, is_dir)

            if exists and is_dir:
                LOGGER.info("Loaded valid input directory: %s", in_dir_str)
                return in_dir_path

            # Try fallback locations
            return MainTab._find_directory_in_common_locations(in_dir_path.name, in_dir_str)
        except Exception:
            LOGGER.exception("Error resolving input directory path")
            return None

    @staticmethod
    def _find_directory_in_common_locations(dir_name: str, original_path: str) -> Path | None:
        """Find directory in common locations when original path doesn't exist."""
        LOGGER.warning("Saved input directory does not exist: %s", original_path)
        LOGGER.debug("Will check if directory exists in other locations...")

        potential_locations = [
            Path.home() / "Downloads" / dir_name,
            Path.home() / "Documents" / dir_name,
            Path.home() / "Desktop" / dir_name,
            Path.cwd() / dir_name,
        ]

        for potential_path in potential_locations:
            LOGGER.debug("Checking potential location: %s", potential_path)
            if potential_path.exists() and potential_path.is_dir():
                LOGGER.info("Found matching directory in alternate location: %s", potential_path)
                return potential_path

        return None

    def _update_input_directory_ui(self, main_window: QObject, loaded_in_dir: Path | None) -> None:
        """Update UI elements with loaded input directory."""
        LOGGER.debug("Final loaded input directory: %s", loaded_in_dir)

        if hasattr(main_window, "set_in_dir"):
            main_window.set_in_dir(loaded_in_dir)

            if loaded_in_dir:
                self.in_dir_edit.setText(str(loaded_in_dir))
                LOGGER.info("Set input directory in UI: %s", loaded_in_dir)
            else:
                self.in_dir_edit.setText(self.tr(""))
                LOGGER.debug("Cleared input directory in UI (no valid directory found)")
        else:
            LOGGER.error("Parent does not have set_in_dir method")

    def _load_output_file_setting(self) -> None:
        """Load output file setting with fallback logic."""
        LOGGER.debug("Loading output file path...")
        out_file_str = self.tab_settings.get_output_file()
        LOGGER.debug("Raw output file from settings: %r", out_file_str)

        if not out_file_str:
            self.out_file_path = None
            self.out_file_edit.setText(self.tr(""))
            LOGGER.debug("No output file string in settings")
            return

        try:
            out_file_path = Path(out_file_str)
            resolved_path = MainTab._resolve_output_file_path(out_file_path, out_file_str)
            self.out_file_edit.setText(str(resolved_path))
        except Exception:
            LOGGER.exception("Error loading output file path")
            self.out_file_path = None

    @staticmethod
    def _resolve_output_file_path(out_file_path: Path, original_str: str) -> Path:
        """Resolve output file path with fallback logic."""
        parent_exists = out_file_path.parent.exists() if out_file_path.parent != Path() else True

        if parent_exists:
            LOGGER.info("Loaded output file with valid parent directory: %s", original_str)
            return out_file_path

        LOGGER.warning("Parent directory for output file doesn't exist: %s", out_file_path.parent)
        new_path = Path.home() / "Downloads" / out_file_path.name
        LOGGER.info("Generated alternative output path: %s", new_path)
        return new_path

    def _load_processing_settings(self) -> None:
        """Load processing-related settings."""
        LOGGER.debug("Loading processing settings...")

        # Load all processing settings at once using batch operation
        settings = self.tab_settings.load_all_processing_settings()

        LOGGER.debug("Setting FPS: %s", settings["fps"])
        self.fps_spinbox.setValue(settings["fps"])

        LOGGER.debug("Setting multiplier: %s", settings["multiplier"])
        self.mid_count_spinbox.setValue(settings["multiplier"])

        LOGGER.debug("Setting max workers: %s", settings["max_workers"])
        self.max_workers_spinbox.setValue(settings["max_workers"])

        LOGGER.debug("Setting encoder: %s", settings["encoder"])
        self.encoder_combo.setCurrentText(settings["encoder"])

    def _load_rife_settings(self) -> None:
        """Load RIFE-specific settings."""
        LOGGER.debug("Loading RIFE options...")

        # Load all RIFE settings at once using batch operation
        rife_settings = self.tab_settings.load_all_rife_settings()

        LOGGER.debug("Setting model key: %s", rife_settings["model_key"])
        # Note: model key is handled separately in _populate_models method

        LOGGER.debug("Setting tiling enabled: %s", rife_settings["tiling_enabled"])
        self.rife_tile_checkbox.setChecked(rife_settings["tiling_enabled"])

        LOGGER.debug("Setting tile size: %s", rife_settings["tile_size"])
        self.rife_tile_size_spinbox.setValue(rife_settings["tile_size"])

        LOGGER.debug("Setting UHD mode: %s", rife_settings["uhd_mode"])
        self.rife_uhd_checkbox.setChecked(rife_settings["uhd_mode"])

        LOGGER.debug("Setting thread spec: %r", rife_settings["thread_spec"])
        self.rife_thread_spec_edit.setText(rife_settings["thread_spec"])

        LOGGER.debug("Setting TTA spatial: %s", rife_settings["tta_spatial"])
        self.rife_tta_spatial_checkbox.setChecked(rife_settings["tta_spatial"])

        LOGGER.debug("Setting TTA temporal: %s", rife_settings["tta_temporal"])
        self.rife_tta_temporal_checkbox.setChecked(rife_settings["tta_temporal"])

    def _load_sanchez_settings(self) -> None:
        """Load Sanchez-specific settings."""
        LOGGER.debug("Loading Sanchez options...")

        # Load all Sanchez settings at once using batch operation
        sanchez_settings = self.tab_settings.load_all_sanchez_settings()

        LOGGER.debug("Setting false color: %s", sanchez_settings["false_color_enabled"])
        self.sanchez_false_colour_checkbox.setChecked(sanchez_settings["false_color_enabled"])

        LOGGER.debug("Setting resolution km: %r", sanchez_settings["resolution_km"])
        # Note: Resolution km UI update handled in sanchez combo update method

    def _load_crop_settings(self, main_window: QObject) -> None:
        """Load crop rectangle settings."""
        LOGGER.debug("Loading crop rectangle...")

        try:
            crop_rect_str = self.tab_settings.get_crop_rectangle()
            LOGGER.debug("Raw crop rectangle from settings: %r", crop_rect_str)

            loaded_crop_rect = MainTab._parse_crop_rectangle(crop_rect_str)
            MainTab._update_crop_rectangle_ui(main_window, loaded_crop_rect)
        except Exception:
            LOGGER.exception("Error loading crop rectangle setting")
            MainTab._update_crop_rectangle_ui(main_window, None)

    @staticmethod
    def _parse_crop_rectangle(crop_rect_str: str) -> tuple[int, int, int, int] | None:
        """Parse crop rectangle string into coordinates tuple."""
        if not crop_rect_str:
            LOGGER.debug("No crop rectangle string in settings")
            return None

        try:
            coords = [int(c.strip()) for c in crop_rect_str.split(",")]
            if len(coords) == CROP_RECT_COMPONENTS:
                LOGGER.info("Loaded crop rectangle: %s", tuple(coords))
                return cast("tuple[int, int, int, int]", tuple(coords))
            LOGGER.warning("Invalid crop rectangle format in settings: %s", crop_rect_str)
            return None
        except ValueError:
            LOGGER.warning("Could not parse crop rectangle from settings: %s", crop_rect_str)
            return None

    @staticmethod
    def _update_crop_rectangle_ui(
        main_window: QObject,
        loaded_crop_rect: tuple[int, int, int, int] | None,
    ) -> None:
        """Update UI with loaded crop rectangle."""
        LOGGER.debug("Final loaded crop rectangle: %s", loaded_crop_rect)

        if hasattr(main_window, "set_crop_rect"):
            main_window.set_crop_rect(loaded_crop_rect)
            LOGGER.debug("Crop rectangle set in MainWindow: %s", loaded_crop_rect)
        else:
            LOGGER.error("Parent does not have set_crop_rect method")

    def _load_boolean_setting(self, key: str, default: bool) -> bool:
        """Load boolean setting with proper type conversion."""
        raw_value = self.tab_settings.get_value(key, default, bool)

        if isinstance(raw_value, bool):
            return raw_value
        if isinstance(raw_value, str):
            return raw_value.lower() == "true"
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
        self._log_settings_debug_info()
        main_window = self.parent()

        try:
            self._save_path_settings(main_window)
            self._save_processing_settings()
            self._save_rife_settings()
            self._save_sanchez_settings()
            self._save_crop_settings(main_window)

            # Force settings to sync to disk
            self.settings.sync()
            LOGGER.info("MainTab: Settings saved successfully.")

            self._verify_saved_settings()

        except Exception:
            LOGGER.exception("Error saving settings")
            # Continue without failing - don't crash the app if settings saving fails

    def _log_settings_debug_info(self) -> None:
        """Log debug information about settings storage."""
        org_name = self.settings.organizationName()
        app_name = self.settings.applicationName()
        filename = self.settings.fileName()
        LOGGER.debug("QSettings save details: org=%s, app=%s, file=%s", org_name, app_name, filename)

    def _save_path_settings(self, main_window: QObject) -> None:
        """Save file and directory path settings."""
        LOGGER.debug("Saving path settings...")

        # Save input directory from text field first
        self._save_input_directory_from_text()

        # Save input directory from MainWindow state as backup
        self._save_input_directory_from_window(main_window)

        # Save output file path
        self._save_output_file_path()

    def _save_input_directory_from_text(self) -> None:
        """Save input directory from the text field."""
        in_dir_text = self.in_dir_edit.text().strip()
        if in_dir_text:
            try:
                text_dir_path = Path(in_dir_text)
                if text_dir_path.exists() and text_dir_path.is_dir():
                    LOGGER.debug("Saving input directory from text field: %r", text_dir_path)
                    in_dir_str = str(text_dir_path.resolve())
                    self.tab_settings.set_input_directory(in_dir_str)
                    self.settings.sync()  # Force immediate sync
            except Exception:
                LOGGER.exception("Error saving input directory from text field")

    def _save_input_directory_from_window(self, main_window: QObject) -> None:
        """Save input directory from MainWindow state."""
        current_in_dir = getattr(main_window, "in_dir", None)
        LOGGER.debug("Got input directory from main window: %s", current_in_dir)

        if current_in_dir:
            try:
                in_dir_str = str(current_in_dir.resolve())
                LOGGER.debug("Saving input directory from MainWindow (absolute): %r", in_dir_str)
                self.tab_settings.set_input_directory(in_dir_str)
                self.settings.sync()
            except Exception:
                LOGGER.exception("Failed to resolve absolute path for input directory")
        else:
            LOGGER.debug("No input directory to save (None/empty)")

    def _save_output_file_path(self) -> None:
        """Save output file path setting."""
        if self.out_file_path:
            try:
                out_file_str = str(self.out_file_path.resolve())
                LOGGER.debug("Saving output file path (absolute): %r", out_file_str)
                self.tab_settings.set_output_file(out_file_str)
            except Exception:
                LOGGER.exception("Failed to resolve absolute path for output file")
                # Fall back to regular path string
                out_file_str = str(self.out_file_path)
                LOGGER.debug("Saving output file path (non-resolved): %r", out_file_str)
                self.tab_settings.set_output_file(out_file_str)
        else:
            LOGGER.debug("Removing output file setting (None/empty)")
            self.tab_settings.set_output_file("")

    def _save_processing_settings(self) -> None:
        """Save processing-related settings."""
        LOGGER.debug("Saving processing settings...")

        fps_value = self.fps_spinbox.value()
        multiplier_value = self.mid_count_spinbox.value()
        max_workers_value = self.max_workers_spinbox.value()
        encoder_value = self.encoder_combo.currentText()

        LOGGER.debug(
            "Saving FPS: %s, multiplier: %s, max_workers: %s, encoder: %s",
            fps_value,
            multiplier_value,
            max_workers_value,
            encoder_value,
        )

        # Use batch operation for efficiency
        self.tab_settings.save_all_processing_settings(
            fps=fps_value, multiplier=multiplier_value, max_workers=max_workers_value, encoder=encoder_value
        )

        # Save model key separately (part of RIFE settings)
        model_key = self.rife_model_combo.currentData()
        LOGGER.debug("Saving model key: %r", model_key)
        self.tab_settings.set_model_key(model_key or "")

    def _save_rife_settings(self) -> None:
        """Save RIFE-specific settings."""
        tile_enabled = self.rife_tile_checkbox.isChecked()
        tile_size = self.rife_tile_size_spinbox.value()
        uhd_mode = self.rife_uhd_checkbox.isChecked()
        thread_spec = self.rife_thread_spec_edit.text()
        tta_spatial = self.rife_tta_spatial_checkbox.isChecked()
        tta_temporal = self.rife_tta_temporal_checkbox.isChecked()
        model_key = self.rife_model_combo.currentData() or ""

        LOGGER.debug(
            "Saving RIFE settings - tiling: %s, tile_size: %s, uhd: %s, thread_spec: %r, tta_spatial: %s, tta_temporal: %s",
            tile_enabled,
            tile_size,
            uhd_mode,
            thread_spec,
            tta_spatial,
            tta_temporal,
        )

        # Use batch operation for efficiency
        self.tab_settings.save_all_rife_settings(
            model_key=model_key,
            tile_enabled=tile_enabled,
            tile_size=tile_size,
            uhd_mode=uhd_mode,
            thread_spec=thread_spec,
            tta_spatial=tta_spatial,
            tta_temporal=tta_temporal,
        )

    def _save_sanchez_settings(self) -> None:
        """Save Sanchez-specific settings."""
        LOGGER.debug("Saving Sanchez options...")

        false_color = self.sanchez_false_colour_checkbox.isChecked()
        res_km = self.sanchez_res_combo.currentText()

        LOGGER.debug("Saving false color: %s, resolution km: %r", false_color, res_km)

        # Use batch operation for efficiency
        self.tab_settings.save_all_sanchez_settings(false_color=false_color, res_km=res_km)

    def _save_crop_settings(self, main_window: QObject) -> None:
        """Save crop rectangle settings."""
        LOGGER.debug("Saving crop rectangle...")
        current_crop_rect_mw = getattr(main_window, "current_crop_rect", None)
        LOGGER.debug("Got crop rectangle from main window: %s", current_crop_rect_mw)

        if current_crop_rect_mw:
            rect_str = ",".join(map(str, current_crop_rect_mw))
            LOGGER.debug("Saving crop rectangle: '%s'", rect_str)
            self.tab_settings.set_crop_rectangle(rect_str)
        else:
            LOGGER.debug("No crop rectangle to save (None/empty)")
            self.tab_settings.set_crop_rectangle("")

    def _verify_saved_settings(self) -> None:
        """Verify that settings were actually saved correctly."""
        try:
            # Check if input directory was actually saved
            saved_in_dir = self.tab_settings.get_input_directory()
            LOGGER.debug("Verification - Saved input directory: '%s'", saved_in_dir)

            # Check if crop rectangle was actually saved
            saved_crop_rect = self.tab_settings.get_crop_rectangle()
            LOGGER.debug("Verification - Saved crop rectangle: '%s'", saved_crop_rect)

            # Check some processing settings
            saved_fps = self.tab_settings.get_fps()
            saved_encoder = self.tab_settings.get_encoder()
            LOGGER.debug("Verification - Saved FPS: %s, encoder: '%s'", saved_fps, saved_encoder)

            # List all keys again to verify
            all_keys_after = self.settings.allKeys()
            LOGGER.debug("Verification - Settings keys after save: %s", all_keys_after)
        except Exception:
            LOGGER.exception("Error verifying saved settings")
