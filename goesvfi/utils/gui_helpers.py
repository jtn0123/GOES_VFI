"""
GUI Helper Utilities for GOES-VFI

This module provides helper functions for the GUI, including RIFE capability detection
and UI element management.
"""

import pathlib
import logging
from typing import Dict, Optional, Tuple

from PyQt6.QtWidgets import QWidget, QCheckBox, QSpinBox, QLineEdit, QComboBox, QLabel

from goesvfi.utils.config import find_rife_executable
from goesvfi.utils.rife_analyzer import RifeCapabilityDetector

# Set up logging
from typing import Any, Optional, Tuple # Added Any
from PyQt6.QtCore import pyqtSignal, Qt, QPoint, QRect, QSize
from PyQt6.QtWidgets import ( # Added more imports here
    QLabel,
    QDialog,
    QWidget,
    QVBoxLayout,
    QApplication,
    QDialogButtonBox,
    QRubberBand,
)
from PyQt6.QtGui import QPixmap, QMouseEvent, QImage, QPainter, QPen, QColor

# Set up logging
# logger = logging.getLogger(__name__) # Already defined below, remove duplicate if inserting here
LOGGER = logging.getLogger(__name__) # Use consistent naming


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
logger = logging.getLogger(__name__)


class RifeCapabilityManager:
    """
    Manages RIFE CLI capabilities and updates UI elements accordingly.

    This class detects the capabilities of the RIFE CLI executable and
    updates UI elements to reflect what options are available.
    """

    def __init__(self, model_key: str = "rife-v4.6"):
        """
        Initialize the capability manager.

        Args:
            model_key: The model key to use for finding the RIFE executable
        """
        self.model_key = model_key
        self.detector: Optional[RifeCapabilityDetector] = None
        self.capabilities: Dict[str, bool] = {}
        self.exe_path: Optional[pathlib.Path] = None
        self.version: Optional[str] = None

        # Try to detect capabilities
        self._detect_capabilities()

    def _detect_capabilities(self) -> None:
        """
        Detect the capabilities of the RIFE CLI executable.
        """
        try:
            # Find the RIFE executable
            self.exe_path = find_rife_executable(self.model_key)

            # Create a capability detector
            self.detector = RifeCapabilityDetector(self.exe_path)

            # Store capabilities
            self.capabilities = {
                "tiling": self.detector.supports_tiling(),
                "uhd": self.detector.supports_uhd(),
                "tta_spatial": self.detector.supports_tta_spatial(),
                "tta_temporal": self.detector.supports_tta_temporal(),
                "thread_spec": self.detector.supports_thread_spec(),
                "batch_processing": self.detector.supports_batch_processing(),
                "timestep": self.detector.supports_timestep(),
                "model_path": self.detector.supports_model_path(),
                "gpu_id": self.detector.supports_gpu_id(),
            }

            # Store version
            self.version = self.detector.version

            logger.info(f"RIFE capabilities detected: {self.capabilities}")
            logger.info(f"RIFE version detected: {self.version}")

        except Exception as e:
            logger.error(f"Error detecting RIFE capabilities: {e}")
            # Set all capabilities to False
            self.capabilities = {
                "tiling": False,
                "uhd": False,
                "tta_spatial": False,
                "tta_temporal": False,
                "thread_spec": False,
                "batch_processing": False,
                "timestep": False,
                "model_path": False,
                "gpu_id": False,
            }

    def update_ui_elements(
        self,
        tile_enable_cb: QCheckBox,
        tile_size_spin: QSpinBox,
        uhd_mode_cb: QCheckBox,
        thread_spec_edit: QLineEdit,
        thread_spec_label: QLabel,
        tta_spatial_cb: QCheckBox,
        tta_temporal_cb: QCheckBox,
    ) -> None:
        """
        Update UI elements based on detected capabilities.

        Args:
            tile_enable_cb: The tiling enable checkbox
            tile_size_spin: The tile size spinner
            uhd_mode_cb: The UHD mode checkbox
            thread_spec_edit: The thread specification text field
            thread_spec_label: The thread specification label
            tta_spatial_cb: The TTA spatial checkbox
            tta_temporal_cb: The TTA temporal checkbox
        """
        # Update tiling elements
        if self.capabilities.get("tiling", False):
            tile_enable_cb.setEnabled(True)
            tile_enable_cb.setToolTip("Enable tiling for large images")
            # Only enable tile size spinner if tiling is enabled
            tile_size_spin.setEnabled(tile_enable_cb.isChecked())
        else:
            tile_enable_cb.setEnabled(False)
            tile_enable_cb.setToolTip("Tiling not supported by this RIFE executable")
            tile_size_spin.setEnabled(False)
            tile_size_spin.setToolTip("Tiling not supported by this RIFE executable")

        # Update UHD mode
        if self.capabilities.get("uhd", False):
            uhd_mode_cb.setEnabled(True)
            uhd_mode_cb.setToolTip(
                "Enable UHD mode for 4K+ images (slower but better quality)"
            )
        else:
            uhd_mode_cb.setEnabled(False)
            uhd_mode_cb.setToolTip("UHD mode not supported by this RIFE executable")

        # Update thread specification
        if self.capabilities.get("thread_spec", False):
            thread_spec_edit.setEnabled(True)
            thread_spec_label.setEnabled(True)
            thread_spec_edit.setToolTip("Thread specification (load:proc:save)")
        else:
            thread_spec_edit.setEnabled(False)
            thread_spec_label.setEnabled(False)
            thread_spec_edit.setToolTip(
                "Thread specification not supported by this RIFE executable"
            )

        # Update TTA spatial
        if self.capabilities.get("tta_spatial", False):
            tta_spatial_cb.setEnabled(True)
            tta_spatial_cb.setToolTip(
                "Enable spatial test-time augmentation (slower but better quality)"
            )
        else:
            tta_spatial_cb.setEnabled(False)
            tta_spatial_cb.setToolTip(
                "Spatial TTA not supported by this RIFE executable"
            )

        # Update TTA temporal
        if self.capabilities.get("tta_temporal", False):
            tta_temporal_cb.setEnabled(True)
            tta_temporal_cb.setToolTip(
                "Enable temporal test-time augmentation (slower but better quality)"
            )
        else:
            tta_temporal_cb.setEnabled(False)
            tta_temporal_cb.setToolTip(
                "Temporal TTA not supported by this RIFE executable"
            )

    def get_capability_summary(self) -> str:
        """
        Get a summary of the detected capabilities.

        Returns:
            A string summarizing the detected capabilities
        """
        if not self.detector:
            return "RIFE capabilities not detected"

        version_str = f"v{self.version}" if self.version else "unknown version"

        # Count supported features
        supported_count = sum(1 for v in self.capabilities.values() if v)
        total_count = len(self.capabilities)

        return (
            f"RIFE {version_str} - {supported_count}/{total_count} features supported"
        )
