"""
GUI Helper Utilities for GOES-VFI

This module provides helper functions for the GUI, including RIFE capability detection
and UI element management.
"""

import logging
import pathlib
from typing import Dict, Optional

from PyQt6.QtCore import QPoint, QPointF, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QCheckBox, QDialog, QLabel, QLineEdit, QRubberBand, QSpinBox

from goesvfi.utils.config import find_rife_executable
from goesvfi.utils.rife_analyzer import RifeCapabilityDetector

# Set up logging
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


# GUI Component classes
class ClickableLabel(QLabel):
    """A QLabel that emits a signal when clicked."""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        """Initialize the ClickableLabel."""
        super().__init__(parent)
        self.file_path = None
        self.processed_image = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        """Emit clicked signal on mouse release."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class CropLabel(QLabel):
    """A QLabel for selecting crop regions on images."""

    # Signals
    selection_changed = pyqtSignal()
    selection_finished = pyqtSignal()

    def __init__(self, parent=None):
        """Initialize the CropLabel."""
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMouseTracking(True)

        # Selection state
        self.selecting = False
        self.selection_start_point = None
        self.selection_end_point = None
        self.selected_rect = None

        # Pixmap offset for centering
        self._pixmap_offset_x = 0
        self._pixmap_offset_y = 0

    def setPixmap(self, pixmap):
        """Set pixmap and calculate offsets for centering."""
        super().setPixmap(pixmap)
        if pixmap and not pixmap.isNull():
            # Calculate offsets for centering
            label_width = self.width()
            label_height = self.height()
            pixmap_width = pixmap.width()
            pixmap_height = pixmap.height()

            self._pixmap_offset_x = max(0, (label_width - pixmap_width) // 2)
            self._pixmap_offset_y = max(0, (label_height - pixmap_height) // 2)

    def _get_pos_on_pixmap(self, pos):
        """Convert widget position to pixmap position."""
        if not self.pixmap() or self.pixmap().isNull():
            return None

        # Adjust for offset
        x = pos.x() - self._pixmap_offset_x
        y = pos.y() - self._pixmap_offset_y

        # Clamp to pixmap bounds
        x = max(0, min(x, self.pixmap().width() - 1))
        y = max(0, min(y, self.pixmap().height() - 1))

        return QPoint(x, y)

    def mousePressEvent(self, event):
        """Start selection on mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._get_pos_on_pixmap(event.position().toPoint())
            if pos:
                self.selecting = True
                self.selection_start_point = pos
                self.selection_end_point = pos
                self.selected_rect = None
                self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Update selection on mouse move."""
        if self.selecting:
            pos = self._get_pos_on_pixmap(event.position().toPoint())
            if pos:
                self.selection_end_point = pos
                self.selection_changed.emit()
                self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Finalize selection on mouse release."""
        if event.button() == Qt.MouseButton.LeftButton and self.selecting:
            self.selecting = False
            if self.selection_start_point and self.selection_end_point:
                # Create normalized rectangle
                x1 = min(self.selection_start_point.x(), self.selection_end_point.x())
                y1 = min(self.selection_start_point.y(), self.selection_end_point.y())
                x2 = max(self.selection_start_point.x(), self.selection_end_point.x())
                y2 = max(self.selection_start_point.y(), self.selection_end_point.y())

                self.selected_rect = QRect(x1, y1, x2 - x1, y2 - y1)
                self.selection_finished.emit()
                self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        """Paint the label with selection overlay."""
        super().paintEvent(event)

        if (
            (self.selecting or self.selected_rect)
            and self.selection_start_point
            and self.selection_end_point
        ):
            painter = QPainter(self)
            painter.setPen(Qt.GlobalColor.red)

            # Calculate rectangle to draw
            if self.selecting:
                x1 = min(self.selection_start_point.x(), self.selection_end_point.x())
                y1 = min(self.selection_start_point.y(), self.selection_end_point.y())
                x2 = max(self.selection_start_point.x(), self.selection_end_point.x())
                y2 = max(self.selection_start_point.y(), self.selection_end_point.y())
                rect = QRect(
                    x1 + self._pixmap_offset_x,
                    y1 + self._pixmap_offset_y,
                    x2 - x1,
                    y2 - y1,
                )
            elif self.selected_rect is not None:
                rect = QRect(
                    self.selected_rect.x() + self._pixmap_offset_x,
                    self.selected_rect.y() + self._pixmap_offset_y,
                    self.selected_rect.width(),
                    self.selected_rect.height(),
                )
            else:
                return  # No selection to draw

            painter.drawRect(rect)


class CropSelectionDialog(QDialog):
    """Dialog for selecting a crop region on an image."""

    def __init__(self, image=None, initial_rect=None, parent=None):
        """Initialize the dialog with an optional image and initial rectangle."""
        super().__init__(parent)
        self.setWindowTitle("Select Crop Region")
        self.setModal(True)
        self.image = image if image and not image.isNull() else QImage()
        self.initial_rect = initial_rect
        self.crop_label = CropLabel()
        self.scale_factor = 1.0
        self._final_selected_rect_display = QRect()

        if image and isinstance(image, QImage) and not image.isNull():
            self.crop_label.setPixmap(QPixmap.fromImage(image))
            # Calculate scale factor if needed
            self.scale_factor = 1.0

        if initial_rect:
            self.crop_label.selected_rect = initial_rect

    def get_selected_rect(self):
        """Get the selected rectangle in original image coordinates."""
        if self._final_selected_rect_display is None or (
            isinstance(self._final_selected_rect_display, QRect)
            and self._final_selected_rect_display.isNull()
        ):
            return QRect()

        # Scale up from display to original coordinates
        x = int(self._final_selected_rect_display.x() * self.scale_factor)
        y = int(self._final_selected_rect_display.y() * self.scale_factor)
        w = int(self._final_selected_rect_display.width() * self.scale_factor)
        h = int(self._final_selected_rect_display.height() * self.scale_factor)

        # Clamp to image bounds
        if not self.image.isNull():
            x = max(0, min(x, self.image.width() - 1))
            y = max(0, min(y, self.image.height() - 1))
            w = min(w, self.image.width() - x)
            h = min(h, self.image.height() - y)

        return QRect(x, y, w, h)

    def _store_final_selection(self, rect=None):
        """Internal method to store the final selection."""
        if rect is None:
            rect = self.crop_label.selected_rect

        if rect and not rect.isNull() and rect.width() > 0 and rect.height() > 0:
            self._final_selected_rect_display = rect
        else:
            self._final_selected_rect_display = None

    def store_final_selection(self):
        """Store the final selection (called before dialog closes)."""
        self._store_final_selection()


class ImageViewerDialog(QDialog):
    """Dialog for viewing an image with zoom and pan capabilities."""

    def __init__(self, image=None, title="Full Resolution", info_text="", parent=None):
        """Initialize the image viewer dialog."""
        super().__init__(parent)
        self.setWindowTitle(title)
        self.original_qimage = image  # Store as original_qimage for compatibility
        self.image = image
        self.info_text = info_text

        # Zoom and pan state
        self.zoom_factor = 1.0
        self.panning = False
        self.was_dragged = False
        self.last_pan_pos = QPointF()
        self.pan_offset = QPointF(0.0, 0.0)

        # Set up the dialog
        self.setModal(True)
        self.setMinimumSize(800, 600)

        if image and isinstance(image, QImage) and not image.isNull():
            # Size the dialog to fit the image (with some limits)
            width = min(image.width() + 50, 1200)
            height = min(image.height() + 50, 900)
            self.resize(width, height)

    def wheelEvent(self, event):
        """Handle zoom with mouse wheel."""
        # Get zoom direction
        delta = event.angleDelta().y()
        zoom_in = delta > 0

        # Update zoom factor
        if zoom_in:
            self.zoom_factor *= 1.1
        else:
            self.zoom_factor /= 1.1

        # Clamp zoom factor
        self.zoom_factor = max(0.1, min(self.zoom_factor, 10.0))

        self.update()
        event.accept()

    def mousePressEvent(self, event):
        """Start panning on mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.panning = True
            self.was_dragged = False
            self.last_pan_pos = event.position()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle panning."""
        if self.panning:
            self.was_dragged = True
            # In a real implementation, we would update the view offset here
            self.last_pan_pos = event.position()
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Stop panning on mouse release."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.panning and not self.was_dragged:
                # Click without drag - close the dialog
                self.accept()
            self.panning = False
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        """Paint the image."""
        super().paintEvent(event)

        if self.image and isinstance(self.image, QImage) and not self.image.isNull():
            painter = QPainter(self)

            # For now, just draw the image centered
            # In a real implementation, we would apply zoom and pan transforms
            rect = self.rect()
            image_rect = self.image.rect()

            # Center the image
            x = (rect.width() - image_rect.width()) // 2
            y = (rect.height() - image_rect.height()) // 2

            painter.drawImage(x, y, self.image)


class ZoomDialog(QDialog):
    """A frameless dialog for showing zoomed images."""

    def __init__(self, pixmap, parent=None):
        """Initialize the zoom dialog with a pixmap."""
        super().__init__(parent)
        self.pixmap = pixmap

        # Set frameless window with translucent background
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Size to match pixmap
        if pixmap and not pixmap.isNull():
            self.resize(pixmap.size())

    def mousePressEvent(self, event):
        """Close dialog on mouse press."""
        self.close()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        """Paint the pixmap."""
        super().paintEvent(event)
        if self.pixmap and not self.pixmap.isNull():
            painter = QPainter(self)
            painter.drawPixmap(0, 0, self.pixmap)


class CropDialog(QDialog):
    """Dialog for selecting a crop region with scaling support."""

    def __init__(self, pixmap, initial_rect=None, parent=None):
        """Initialize with a pixmap and optional initial rectangle."""
        super().__init__(parent)
        self.setWindowTitle("Select Crop Region")
        self.original_pixmap = pixmap
        self.initial_rect = initial_rect
        self.scale_factor = 1.0
        self.crop_rect_scaled = QRect()
        self.origin = QPoint()

        # Create a label to hold the image
        self.lbl = QLabel()
        self.lbl.setParent(self)

        # Create rubber band for selection
        self.rubber = QRubberBand(QRubberBand.Shape.Rectangle, self)

        # Calculate scale factor if needed
        if pixmap and not pixmap.isNull():
            # In a real implementation, we would scale down large images
            # For now, just use scale factor of 1.0
            self.scale_factor = 1.0
            self.lbl.setPixmap(pixmap)

        if initial_rect:
            # Handle both tuple and QRect
            if isinstance(initial_rect, (tuple, list)) and len(initial_rect) == 4:
                x, y, w, h = initial_rect
                self.crop_rect_scaled = QRect(x, y, w, h)
            elif isinstance(initial_rect, QRect):
                self.crop_rect_scaled = initial_rect

            # Set rubber band geometry if we have an initial rect
            if not self.crop_rect_scaled.isNull():
                self.rubber.setGeometry(self.crop_rect_scaled)

    def getRect(self):
        """Get the crop rectangle in original image coordinates."""
        if self.crop_rect_scaled.isNull():
            return None

        # Scale up to original coordinates (if image was scaled down for display)
        x = int(self.crop_rect_scaled.x() * self.scale_factor)
        y = int(self.crop_rect_scaled.y() * self.scale_factor)
        w = int(self.crop_rect_scaled.width() * self.scale_factor)
        h = int(self.crop_rect_scaled.height() * self.scale_factor)

        return QRect(x, y, w, h)

    def get_rect(self):
        """Alias for getRect for backwards compatibility."""
        rect = self.getRect()
        if rect:
            return (rect.x(), rect.y(), rect.width(), rect.height())
        return None

    def mousePressEvent(self, event):
        """Handle mouse press to start selection."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Start selection
            self.origin = event.position().toPoint()
            self.crop_rect_scaled = QRect(self.origin, self.origin)
            self.update()
        super().mousePressEvent(event)
