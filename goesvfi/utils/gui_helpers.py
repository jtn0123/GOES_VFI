"""
GUI Helper Utilities for GOES-VFI

This module provides helper functions for the GUI, including RIFE capability detection
and UI element management.
"""

import logging
import pathlib
from typing import Any, Dict, Optional

from PyQt6.QtCore import QPoint, QPointF, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QMouseEvent, QPainter, QPixmap, QWheelEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

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

    def __init__(self, model_key: str = "rife-v4.6") -> None:
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

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the ClickableLabel."""
        super().__init__(parent)
        self.file_path = None
        self.processed_image = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        """Emit clicked signal on mouse release."""
        if event is None:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class CropLabel(QLabel):
    """A QLabel for selecting crop regions on images."""

    # Signals
    selection_changed = pyqtSignal()
    selection_finished = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the CropLabel."""
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMouseTracking(True)

        # Selection state
        self.selecting = False
        self.selection_start_point: Optional[QPoint] = None
        self.selection_end_point: Optional[QPoint] = None
        self.selected_rect: Optional[QRect] = None

        # Pixmap offset for centering
        self._pixmap_offset_x = 0
        self._pixmap_offset_y = 0

    def setPixmap(self, pixmap: QPixmap) -> None:
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

    def _get_pos_on_pixmap(self, pos: QPoint) -> Optional[QPoint]:
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

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Start selection on mouse press."""
        if event is None:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._get_pos_on_pixmap(event.position().toPoint())
            if pos:
                self.selecting = True
                self.selection_start_point = pos
                self.selection_end_point = pos
                self.selected_rect = None
                self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        """Update selection on mouse move."""
        if event is None:
            return
        if self.selecting:
            pos = self._get_pos_on_pixmap(event.position().toPoint())
            if pos:
                self.selection_end_point = pos
                self.selection_changed.emit()
                self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        """Finalize selection on mouse release."""
        if event is None:
            return
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

    def paintEvent(self, event: Any) -> None:
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

    def __init__(
        self,
        image: Optional[QImage] = None,
        initial_rect: Optional[QRect] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the dialog with an optional image and initial rectangle."""
        super().__init__(parent)
        self.setWindowTitle("Select Crop Region")
        self.setModal(True)
        self.resize(800, 600)

        self.image = image if image and not image.isNull() else QImage()
        self.initial_rect = initial_rect
        self.scale_factor = 1.0
        self._final_selected_rect_display = QRect()

        # Create the main layout
        main_layout = QVBoxLayout(self)

        # Create instruction label
        instruction_label = QLabel("Click and drag to select a crop region")
        instruction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instruction_label.setStyleSheet(
            "QLabel { color: #666; font-size: 12px; padding: 8px; }"
        )
        main_layout.addWidget(instruction_label)

        # Create scroll area for the image
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll_area.setMinimumSize(600, 400)

        # Create the crop label
        self.crop_label = CropLabel()
        self.crop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.crop_label.setMinimumSize(200, 200)

        # Set up the image if provided
        if image and isinstance(image, QImage) and not image.isNull():
            # Scale image to fit dialog while maintaining aspect ratio
            max_width, max_height = 700, 450
            if image.width() > max_width or image.height() > max_height:
                scaled_image = image.scaled(
                    max_width,
                    max_height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.scale_factor = max(
                    image.width() / scaled_image.width(),
                    image.height() / scaled_image.height(),
                )
            else:
                scaled_image = image
                self.scale_factor = 1.0

            pixmap = QPixmap.fromImage(scaled_image)
            self.crop_label.setPixmap(pixmap)
            self.crop_label.setFixedSize(pixmap.size())

        # Set initial selection if provided
        if initial_rect and not initial_rect.isNull():
            # Scale down the initial rect to display coordinates
            scaled_rect = QRect(
                int(initial_rect.x() / self.scale_factor),
                int(initial_rect.y() / self.scale_factor),
                int(initial_rect.width() / self.scale_factor),
                int(initial_rect.height() / self.scale_factor),
            )
            self.crop_label.selected_rect = scaled_rect

        scroll_area.setWidget(self.crop_label)
        main_layout.addWidget(scroll_area)

        # Create a horizontal layout for status and preview
        info_layout = QHBoxLayout()

        # Create status label to show selection info
        self.status_label = QLabel("No selection")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            "QLabel { color: #333; font-size: 11px; padding: 4px; }"
        )
        info_layout.addWidget(self.status_label, 2)  # Give status more space

        # Add a preview of the cropped area
        preview_group = QWidget()
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(5, 5, 5, 5)

        preview_title = QLabel("Crop Preview")
        preview_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_title.setStyleSheet(
            "QLabel { font-weight: bold; font-size: 10px; color: #555; }"
        )
        preview_layout.addWidget(preview_title)

        self.crop_preview_label = QLabel("Select a region")
        self.crop_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.crop_preview_label.setFixedSize(120, 120)
        self.crop_preview_label.setStyleSheet(
            """
            QLabel {
                border: 1px solid #ccc;
                background-color: #f5f5f5;
                color: #666;
                font-size: 9px;
            }
        """
        )
        preview_layout.addWidget(self.crop_preview_label)

        info_layout.addWidget(preview_group, 1)  # Give preview less space
        main_layout.addLayout(info_layout)

        # Connect signals to update status
        self.crop_label.selection_changed.connect(self._update_status)
        self.crop_label.selection_finished.connect(self._update_status)

        # Create button layout
        button_layout = QHBoxLayout()

        # Clear selection button
        clear_button = QPushButton("Clear Selection")
        clear_button.clicked.connect(self._clear_selection)
        button_layout.addWidget(clear_button)

        button_layout.addStretch()

        # Cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        # OK button
        ok_button = QPushButton("OK")
        ok_button.setDefault(True)
        ok_button.clicked.connect(self._accept_selection)
        button_layout.addWidget(ok_button)

        main_layout.addLayout(button_layout)

        # Update initial status
        self._update_status()

    def _update_status(self) -> None:
        """Update the status label and crop preview with current selection info."""
        if self.crop_label.selected_rect and not self.crop_label.selected_rect.isNull():
            rect = self.crop_label.selected_rect
            # Convert to original image coordinates for display
            orig_x = int(rect.x() * self.scale_factor)
            orig_y = int(rect.y() * self.scale_factor)
            orig_w = int(rect.width() * self.scale_factor)
            orig_h = int(rect.height() * self.scale_factor)

            self.status_label.setText(
                f"Selection: {orig_x}, {orig_y} → {orig_x + orig_w}, {orig_y + orig_h} "
                f"(size: {orig_w} × {orig_h})"
            )

            # Update crop preview
            self._update_crop_preview(rect)
        else:
            self.status_label.setText("No selection")
            # Clear crop preview
            self.crop_preview_label.clear()
            self.crop_preview_label.setText("Select a region")

    def _update_crop_preview(self, rect: Optional[QRect]) -> None:
        """Update the crop preview label with the selected region."""
        if not rect or rect.isNull() or self.image.isNull():
            # Clear the preview if no valid selection or image
            self.crop_preview_label.clear()
            self.crop_preview_label.setText("Select a region")
            return

        try:
            # Extract the selected region from the original image (not the scaled display image)
            # Convert display coordinates to original image coordinates
            orig_x = int(rect.x() * self.scale_factor)
            orig_y = int(rect.y() * self.scale_factor)
            orig_w = int(rect.width() * self.scale_factor)
            orig_h = int(rect.height() * self.scale_factor)

            # Clamp to image bounds
            orig_x = max(0, min(orig_x, self.image.width() - 1))
            orig_y = max(0, min(orig_y, self.image.height() - 1))
            orig_w = min(orig_w, self.image.width() - orig_x)
            orig_h = min(orig_h, self.image.height() - orig_y)

            if orig_w <= 0 or orig_h <= 0:
                self.crop_preview_label.clear()
                self.crop_preview_label.setText("Invalid region")
                return

            # Extract the crop region from the original image
            cropped_image = self.image.copy(orig_x, orig_y, orig_w, orig_h)

            if cropped_image.isNull():
                self.crop_preview_label.clear()
                self.crop_preview_label.setText("Preview error")
                return

            # Scale the cropped image to fit the preview label (120x120)
            preview_size = 120
            scaled_preview = cropped_image.scaled(
                preview_size,
                preview_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            # Convert to pixmap and set it
            preview_pixmap = QPixmap.fromImage(scaled_preview)
            self.crop_preview_label.setPixmap(preview_pixmap)
            self.crop_preview_label.setText("")  # Clear any text

        except Exception as e:
            logger.error(f"Error updating crop preview: {e}")
            self.crop_preview_label.clear()
            self.crop_preview_label.setText("Preview error")

    def _clear_selection(self) -> None:
        """Clear the current selection."""
        self.crop_label.selected_rect = None
        self.crop_label.selection_start_point = None
        self.crop_label.selection_end_point = None
        self.crop_label.selecting = False
        self.crop_label.update()
        self._update_status()

    def _accept_selection(self) -> None:
        """Accept the current selection and close dialog."""
        if self.crop_label.selected_rect and not self.crop_label.selected_rect.isNull():
            self._store_final_selection()
            self.accept()
        else:
            # Show message if no selection made
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setWindowTitle("No Selection")
            msg.setText(
                "Please select a crop region before clicking OK, or click Cancel to exit."
            )
            msg.exec()

    def get_selected_rect(self) -> QRect:
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

    def _store_final_selection(self, rect: Optional[QRect] = None) -> None:
        """Internal method to store the final selection."""
        if rect is None:
            rect = self.crop_label.selected_rect

        if rect and not rect.isNull() and rect.width() > 0 and rect.height() > 0:
            self._final_selected_rect_display = rect
        else:
            self._final_selected_rect_display = QRect()

    def store_final_selection(self) -> None:
        """Store the final selection (called before dialog closes)."""
        self._store_final_selection()


class ImageViewerDialog(QDialog):
    """Dialog for viewing an image with zoom and pan capabilities."""

    def __init__(
        self,
        image: Optional[QImage] = None,
        title: str = "Full Resolution",
        info_text: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
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

    def wheelEvent(self, event: Optional[QWheelEvent]) -> None:
        """Handle zoom with mouse wheel."""
        if event is None:
            return
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

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Start panning on mouse press."""
        if event is None:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.panning = True
            self.was_dragged = False
            self.last_pan_pos = event.position()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        """Handle panning."""
        if event is None:
            return
        if self.panning:
            self.was_dragged = True
            # In a real implementation, we would update the view offset here
            self.last_pan_pos = event.position()
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        """Stop panning on mouse release."""
        if event is None:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            if self.panning and not self.was_dragged:
                # Click without drag - close the dialog
                self.accept()
            self.panning = False
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: Any) -> None:
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

    def __init__(self, pixmap: QPixmap, parent: Optional[QWidget] = None) -> None:
        """Initialize the zoom dialog with a pixmap."""
        super().__init__(parent)
        self.pixmap = pixmap

        # Set frameless window with translucent background
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Size to match pixmap
        if pixmap and not pixmap.isNull():
            self.resize(pixmap.size())

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Close dialog on mouse press."""
        if event is None:
            return
        self.close()
        super().mousePressEvent(event)

    def paintEvent(self, event: Any) -> None:
        """Paint the pixmap."""
        super().paintEvent(event)
        if self.pixmap and not self.pixmap.isNull():
            painter = QPainter(self)
            painter.drawPixmap(0, 0, self.pixmap)
