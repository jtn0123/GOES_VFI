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
from PyQt6.QtCore import pyqtSignal, Qt, QPoint, QRect, QSize, QPointF # Added QPointF
from PyQt6.QtGui import QWheelEvent, QScreen # Added QWheelEvent, QScreen
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

from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout, QApplication, QSizePolicy, QWidget # Added QWidget
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QMouseEvent # Added QMouseEvent
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal # Added QRect, QPoint, pyqtSignal


# ────────────────────────────── Image Viewer Dialog ──────────────────────────────
class ImageViewerDialog(QDialog):
    """A dialog to display a QImage, scaled down to fit the screen."""

    def __init__(self, image: QImage, parent: QWidget | None = None):
        super().__init__(parent)
        self.original_qimage: QImage = image # Store original QImage
        # self.zoom_factor will be calculated below based on initial fit
        self.max_zoom: float = 20.0 # Allow more zoom in
        self.pan_offset = QPointF(0.0, 0.0) # Top-left corner of visible area in full zoomed image coords
        self.panning = False
        self.last_pan_pos: Optional[QPointF] = None
        self.was_dragged = False # To distinguish click from drag

        # --- Style Changes for Borderless/Transparent/Click-to-Close ---
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # --- End Style Changes ---
        self.setWindowTitle("Image Viewer") # Title won't be visible, but keep for identification
        self.setModal(False) # Non-modal

        if self.original_qimage.isNull():
            # Handle case where image is invalid
            layout = QVBoxLayout(self)
            error_label = QLabel("Error: Invalid image provided.")
            layout.addWidget(error_label)
            self.setLayout(layout)
            self.resize(200, 50)
            return

        # Get available screen geometry
        screen = QApplication.primaryScreen()
        screen_size = screen.availableGeometry().size() if screen else QSize(1024, 768) # Fallback

        # Calculate initial scaled size to fit screen (don't scale up)
        image_size = self.original_qimage.size()
        scaled_size = image_size.scaled(screen_size, Qt.AspectRatioMode.KeepAspectRatio)

        # Calculate the initial zoom factor to fit the image within the scaled_size
        img_w = self.original_qimage.width()
        img_h = self.original_qimage.height()
        win_w = scaled_size.width()
        win_h = scaled_size.height()

        if img_w > 0 and img_h > 0:
            width_ratio = win_w / img_w
            height_ratio = win_h / img_h
            initial_zoom = min(width_ratio, height_ratio)
            # Don't scale up initially if the image is smaller than the window
            self.zoom_factor = min(initial_zoom, 1.0)
        else:
            # Handle zero-dimension image case (though unlikely if not isNull())
            self.zoom_factor = 1.0

        # Set min_zoom relative to initial fit, allowing zoom out to 10% of fit
        self.min_zoom: float = self.zoom_factor * 0.1

        # Create label
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(False) # We handle scaling/cropping

        # Set fixed size for dialog and label based on initial fit
        self.setFixedSize(scaled_size)
        self.image_label.setFixedSize(scaled_size)

        # Initial display
        self.update_display()

        # Center the dialog initially
        self._center_on_screen() # Renamed to avoid conflict if inherited

    def _center_on_screen(self) -> None:
        """Centers the dialog on the primary screen."""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            dialog_geometry = self.frameGeometry()
            center_point = screen_geometry.center()
            dialog_geometry.moveCenter(center_point)
            self.move(dialog_geometry.topLeft())

    def _clamp_pan_offset(self) -> None:
        """Clamps the pan offset based on current zoom and image/view size."""
        if self.original_qimage.isNull():
            return

        view_size = self.size()
        zoomed_size = self.original_qimage.size() * self.zoom_factor

        # Calculate maximum possible pan offsets
        # Ensure zoomed_size dimensions are at least view_size dimensions for max_pan calc
        # This prevents negative max_pan values when zoomed out smaller than the view
        effective_zoomed_width = max(zoomed_size.width(), view_size.width())
        effective_zoomed_height = max(zoomed_size.height(), view_size.height())

        max_pan_x = max(0.0, effective_zoomed_width - view_size.width())
        max_pan_y = max(0.0, effective_zoomed_height - view_size.height())


        # Clamp
        new_x = max(0.0, min(self.pan_offset.x(), max_pan_x))
        new_y = max(0.0, min(self.pan_offset.y(), max_pan_y))
        self.pan_offset = QPointF(new_x, new_y)


    def update_display(self) -> None:
        """Renders the visible portion of the potentially zoomed and panned image."""
        if self.original_qimage.isNull():
            return

        # 1. Calculate the size of the fully zoomed image
        zoomed_size = self.original_qimage.size() * self.zoom_factor
        # Ensure minimum size
        zoomed_size.setWidth(max(1, zoomed_size.width()))
        zoomed_size.setHeight(max(1, zoomed_size.height()))


        # 2. Scale the original image to the fully zoomed size (can be large)
        #    Use SmoothTransformation for better quality when zooming
        full_zoomed_qimage = self.original_qimage.scaled(
            zoomed_size,
            Qt.AspectRatioMode.KeepAspectRatio, # Should not matter if aspect is preserved by zoom_factor calc
            Qt.TransformationMode.SmoothTransformation
        )

        # 3. Define the source rectangle (viewport) to copy from full_zoomed_qimage
        #    The viewport top-left is self.pan_offset, size is self.size() (dialog/label size)
        #    Ensure the viewport coordinates are integers for QRect
        viewport = QRect(self.pan_offset.toPoint(), self.size())

        # 4. Clamp viewport to be within the bounds of the full_zoomed_qimage
        #    This prevents errors if panning goes slightly out of bounds before clamping
        #    Also ensures we don't try to copy outside the source image
        viewport = viewport.intersected(full_zoomed_qimage.rect())

        # 5. Copy the viewport from the fully zoomed image
        #    Handle potential empty viewport if zoom is very small or panning is extreme
        if viewport.isValid() and not viewport.isEmpty():
             visible_qimage = full_zoomed_qimage.copy(viewport)
        else:
             # Create a blank image of the correct size if viewport is invalid
             # Fill with transparent background
             visible_qimage = QImage(self.size(), QImage.Format.Format_ARGB32_Premultiplied)
             visible_qimage.fill(Qt.GlobalColor.transparent)


        # 6. Convert to pixmap and display
        #    Ensure the pixmap is created with the correct device pixel ratio if needed,
        #    though for simple display, this is often handled automatically.
        pixmap_to_display = QPixmap.fromImage(visible_qimage)
        self.image_label.setPixmap(pixmap_to_display)


    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel scrolling for zooming towards the cursor."""
        if self.original_qimage.isNull():
            event.ignore()
            return

        angle = event.angleDelta().y()
        if angle == 0:
            event.ignore()
            return

        zoom_in_factor = 1.15 # Slightly faster zoom
        zoom_out_factor = 1 / zoom_in_factor

        # --- Zoom to Cursor Logic ---
        # 1. Get cursor position relative to the image label
        cursor_pos_label = event.position() # QPointF

        # 2. Calculate the corresponding point on the *current* fully zoomed image
        #    This is the pan offset + cursor position within the view
        point_on_full_image = self.pan_offset + cursor_pos_label

        # 3. Calculate the new zoom factor
        old_zoom_factor = self.zoom_factor
        if angle > 0: # Scroll up (zoom in)
            new_zoom_factor = old_zoom_factor * zoom_in_factor
        else: # Scroll down (zoom out)
            new_zoom_factor = old_zoom_factor * zoom_out_factor

        # Clamp zoom factor
        new_zoom_factor = max(self.min_zoom, min(new_zoom_factor, self.max_zoom))

        # If zoom didn't change (due to clamping), do nothing
        if abs(new_zoom_factor - old_zoom_factor) < 1e-6:
             event.accept() # Still accept event even if no change
             return

        # 4. Calculate zoom ratio
        scale_change = new_zoom_factor / old_zoom_factor

        # 5. Calculate where the target point *would be* on the *newly* scaled full image
        new_point_on_full_image = point_on_full_image * scale_change

        # 6. Calculate the new pan offset required to keep that point under the cursor
        #    New Offset = New Point - Cursor Position
        self.pan_offset = new_point_on_full_image - cursor_pos_label

        # 7. Update the zoom factor *after* calculating the new offset
        self.zoom_factor = new_zoom_factor

        # 8. Apply bounds checking/clamping to the new pan_offset
        self._clamp_pan_offset()
        # --- End Zoom to Cursor Logic ---

        # 9. Update the display
        self.update_display()
        event.accept() # Indicate event was handled


    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        """Initiate panning or close on click."""
        if event and event.button() == Qt.MouseButton.LeftButton:
            self.panning = True
            self.last_pan_pos = event.position() # Store as QPointF
            self.was_dragged = False # Reset drag flag
            LOGGER.debug(f"ImageViewerDialog mousePressEvent: Start pan at {self.last_pan_pos}")
            event.accept()
        else:
            # Pass other button presses (like right-click) to the base class
            # Check if event is None before calling super
            if event:
                super().mousePressEvent(event)
            else:
                # Handle the case where event is None if necessary, though unlikely
                pass


    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        """Handle panning when dragging."""
        if event and self.panning and self.last_pan_pos is not None:
            current_pos = event.position()
            delta = current_pos - self.last_pan_pos
            self.pan_offset -= delta # Subtract delta to move image with cursor
            self.last_pan_pos = current_pos # Update last position

            # Clamp pan offset after moving
            self._clamp_pan_offset()

            self.update_display()
            self.was_dragged = True # Mark that a drag occurred
            # LOGGER.debug(f"ImageViewerDialog mouseMoveEvent: Panning, offset={self.pan_offset}") # Optional: very verbose
            event.accept()
        else:
            # Pass other move events to the base class
            if event:
                super().mouseMoveEvent(event)


    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        """Finalize panning or close on click."""
        if event and event.button() == Qt.MouseButton.LeftButton:
            if self.panning:
                LOGGER.debug(f"ImageViewerDialog mouseReleaseEvent: Panning ended. Dragged: {self.was_dragged}")
                if not self.was_dragged:
                    # If it was a click (no drag), close the dialog
                    LOGGER.debug("ImageViewerDialog: Click detected (no drag), closing.")
                    self.accept() # Use accept() for dialogs
                # Reset panning state regardless
                self.panning = False
                self.last_pan_pos = None
                event.accept()
            else:
                 # This case might occur if the press happened outside the window
                 # or if the event propagation was unusual.
                 LOGGER.debug("ImageViewerDialog mouseReleaseEvent: Left button released but not panning.")
                 # Decide if we should still close or pass to super
                 # If the goal is "click anywhere closes", maybe close here too?
                 # For now, let's pass to super if not panning.
                 super().mouseReleaseEvent(event)

        else:
            # Pass other button releases to the base class
            if event:
                super().mouseReleaseEvent(event)
# ────────────────────────────── Crop Selection Dialog ──────────────────────────────
# ────────────────────────────── Crop Label (Handles Drawing) ─────────────────────────
class CropLabel(QLabel):
    """A QLabel subclass that handles drawing the crop selection rectangle."""
    selection_changed = pyqtSignal(QRect) # Signal emitted when selection changes
    selection_finished = pyqtSignal(QRect) # Signal emitted when selection is finalized

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMouseTracking(True) # Need mouse move events

        self.selecting = False
        self.selection_start_point: Optional[QPoint] = None # In pixmap coordinates
        self.selection_end_point: Optional[QPoint] = None   # In pixmap coordinates
        self.selected_rect: Optional[QRect] = None # Final selection in *pixmap* coordinates

        # Store pixmap offset for coordinate mapping
        self._pixmap_offset_x = 0.0
        self._pixmap_offset_y = 0.0

    def setPixmap(self, pixmap: QPixmap) -> None:
        super().setPixmap(pixmap)
        self._recalculate_pixmap_offset()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._recalculate_pixmap_offset()

    def _recalculate_pixmap_offset(self) -> None:
        """Calculates the offset of the centered pixmap within the label."""
        pix = self.pixmap()
        if pix and not pix.isNull():
            pixmap_size = pix.size()
            label_size = self.size()
            self._pixmap_offset_x = (label_size.width() - pixmap_size.width()) / 2
            self._pixmap_offset_y = (label_size.height() - pixmap_size.height()) / 2
        else:
            self._pixmap_offset_x = 0.0
            self._pixmap_offset_y = 0.0

    def _get_pos_on_pixmap(self, event_pos: QPoint) -> Optional[QPoint]:
        """Maps a point from label coordinates to pixmap coordinates."""
        pix = self.pixmap()
        if not pix or pix.isNull():
            return None

        pix_x = event_pos.x() - self._pixmap_offset_x
        pix_y = event_pos.y() - self._pixmap_offset_y

        # Check if the point is within the pixmap bounds
        if 0 <= pix_x < pix.width() and 0 <= pix_y < pix.height():
            return QPoint(int(pix_x), int(pix_y))
        return None # Outside pixmap bounds

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event and event.button() == Qt.MouseButton.LeftButton:
            pos_on_pixmap = self._get_pos_on_pixmap(event.pos())
            if pos_on_pixmap:
                self.selecting = True
                self.selection_start_point = pos_on_pixmap
                self.selection_end_point = self.selection_start_point
                self.selected_rect = None # Clear previous final selection
                logger.debug(f"CropLabel: Selection started at (pixmap coords): {self.selection_start_point}")
                self.update()
            else:
                # Click outside pixmap, pass event up
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if event and self.selecting and self.selection_start_point:
            # Get position relative to label, then map and clamp to pixmap
            pos_on_pixmap = self._get_pos_on_pixmap(event.pos())
            if pos_on_pixmap: # Still within pixmap bounds
                 self.selection_end_point = pos_on_pixmap
            else:
                 # If dragged outside, clamp to the edge
                 pix = self.pixmap()
                 if pix:
                     clamped_x = max(0, min(event.pos().x() - self._pixmap_offset_x, pix.width() - 1))
                     clamped_y = max(0, min(event.pos().y() - self._pixmap_offset_y, pix.height() - 1))
                     self.selection_end_point = QPoint(int(clamped_x), int(clamped_y))

            if self.selection_end_point:
                 current_rect = QRect(self.selection_start_point, self.selection_end_point).normalized()
                 self.selection_changed.emit(current_rect) # Emit current rect during drag
                 self.update()
        else:
            super().mouseMoveEvent(event)


    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        if event and event.button() == Qt.MouseButton.LeftButton and self.selecting:
            self.selecting = False
            # Final position update
            pos_on_pixmap = self._get_pos_on_pixmap(event.pos())
            if pos_on_pixmap:
                 self.selection_end_point = pos_on_pixmap
            else:
                 # Clamp if released outside
                 pix = self.pixmap()
                 if pix and self.selection_end_point: # Use last known good end point if needed
                     clamped_x = max(0, min(event.pos().x() - self._pixmap_offset_x, pix.width() - 1))
                     clamped_y = max(0, min(event.pos().y() - self._pixmap_offset_y, pix.height() - 1))
                     self.selection_end_point = QPoint(int(clamped_x), int(clamped_y))

            if self.selection_start_point and self.selection_end_point:
                final_rect_pixmap = QRect(self.selection_start_point, self.selection_end_point).normalized()
                if final_rect_pixmap.width() > 0 and final_rect_pixmap.height() > 0:
                    self.selected_rect = final_rect_pixmap
                    logger.debug(f"CropLabel: Selection finished, rect (pixmap coords): {self.selected_rect}")
                    self.selection_finished.emit(self.selected_rect) # Emit final rect
                else:
                    self.selected_rect = None # Treat zero-size as no selection
                    logger.debug("CropLabel: Selection resulted in zero size.")
                    self.selection_finished.emit(QRect()) # Emit empty rect
            else:
                 self.selected_rect = None
                 self.selection_finished.emit(QRect()) # Emit empty rect

            self.update()
        else:
            super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        """Draws the base pixmap and the selection rectangle over it."""
        super().paintEvent(event) # Draw the label background etc.

        pix = self.pixmap()
        if not pix or pix.isNull():
            return # Nothing to draw on

        painter = QPainter(self) # Paint on the label itself
        try:
            # Painter coordinates are relative to the label widget

            rect_to_draw_pixmap = None # Rectangle in pixmap coordinates
            pen = None

            # Determine what to draw
            if self.selecting and self.selection_start_point and self.selection_end_point:
                rect_to_draw_pixmap = QRect(self.selection_start_point, self.selection_end_point).normalized()
                pen = QPen(QColor(255, 0, 0, 180), 1, Qt.PenStyle.DashLine) # Red dashed
            elif not self.selecting and self.selected_rect:
                rect_to_draw_pixmap = self.selected_rect
                pen = QPen(QColor("lime"), 2, Qt.PenStyle.SolidLine) # Bright green

            # If we have a valid rectangle and pen, draw it
            if rect_to_draw_pixmap and pen:
                 # Map the pixmap coordinates to label coordinates for drawing
                 draw_rect = QRect(
                     int(self._pixmap_offset_x + rect_to_draw_pixmap.x()),
                     int(self._pixmap_offset_y + rect_to_draw_pixmap.y()),
                     rect_to_draw_pixmap.width(),
                     rect_to_draw_pixmap.height()
                 )

                 painter.setPen(pen)
                 if draw_rect.width() > 0 and draw_rect.height() > 0:
                      painter.drawRect(draw_rect)
                      # logger.debug(f"CropLabel: Drawing rect {draw_rect}") # Optional debug

        finally:
            if painter.isActive():
                 painter.end()

# ────────────────────────────── Crop Selection Dialog ───────────────────────────────

class CropSelectionDialog(QDialog):
    """
    A dialog for selecting a rectangular crop region on a full-resolution image.

    Displays the image in a custom CropLabel and allows the user to draw a rectangle.
    The selected rectangle coordinates are relative to the original image dimensions.
    """
    def __init__(self, image: QImage, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Select Crop Region")
        self.setModal(True) # Ensure it blocks interaction until closed

        if image.isNull():
            LOGGER.error("CropSelectionDialog received an invalid QImage.")
            self.image = QImage() # Empty image
        else:
            self.image = image

        # Use the custom CropLabel
        self.image_label = CropLabel(self)

        # Scale pixmap for display if too large, but keep original image for coords
        screen = QApplication.primaryScreen()
        max_size = screen.availableGeometry().size() * 0.9 if screen else QSize(1200, 800)
        self.display_pixmap = QPixmap.fromImage(self.image).scaled(
            max_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(self.display_pixmap)
        # Alignment and MouseTracking handled within CropLabel

        # Calculate scale factor between original image and displayed pixmap
        if self.display_pixmap.width() > 0:
             self.scale_factor = self.image.width() / self.display_pixmap.width()
        else:
             self.scale_factor = 1.0

        # Store the final selected rect (in *display* coordinates) from the label signal
        self._final_selected_rect_display: Optional[QRect] = None
        self.image_label.selection_finished.connect(self._store_final_selection)

        # Layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.image_label)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

        # Adjust dialog size to fit the scaled pixmap + buttons
        self.resize(self.display_pixmap.size() + QSize(0, 50)) # Add some height for buttons

    def _store_final_selection(self, rect_display: QRect):
        """Stores the final selection rectangle received from CropLabel."""
        if rect_display.isNull() or rect_display.width() <= 0 or rect_display.height() <= 0:
             self._final_selected_rect_display = None
        else:
             self._final_selected_rect_display = rect_display
        logger.debug(f"CropSelectionDialog: Received final selection (display coords): {self._final_selected_rect_display}")

    # Mouse and Paint events are now handled by CropLabel

    def get_selected_rect(self) -> QRect:
        """
        Calculates and returns the selected rectangle in original image coordinates.
        Uses the stored rectangle from the CropLabel signal.

        Returns:
            QRect: The selected rectangle in original image coordinates, clamped and validated.
                   Returns an empty QRect if no valid selection was made or the dialog was cancelled.
        """
        # Use the stored rectangle from the signal
        if self._final_selected_rect_display and not self._final_selected_rect_display.isNull():
            rect_display = self._final_selected_rect_display.normalized()

            # Convert display coordinates to original image coordinates
            img_x = int(rect_display.x() * self.scale_factor)
            img_y = int(rect_display.y() * self.scale_factor)
            img_w = int(rect_display.width() * self.scale_factor)
            img_h = int(rect_display.height() * self.scale_factor)

            # Create the rectangle in original image coordinates
            final_rect_image = QRect(img_x, img_y, img_w, img_h)

            # --- Validation and Clamping ---
            # Ensure width/height are at least 1
            if final_rect_image.width() <= 0: final_rect_image.setWidth(1)
            if final_rect_image.height() <= 0: final_rect_image.setHeight(1)

            # Clamp to original image boundaries
            img_w_orig = self.image.width()
            img_h_orig = self.image.height()
            if img_w_orig <= 0 or img_h_orig <= 0:
                logger.warning("Original image has invalid dimensions, cannot clamp selection.")
                return QRect() # Avoid issues with invalid image

            clamped_x = max(0, final_rect_image.left())
            clamped_y = max(0, final_rect_image.top())
            # Calculate clamped right/bottom based on original image size
            clamped_r = min(final_rect_image.right(), img_w_orig - 1) # right edge is inclusive index
            clamped_b = min(final_rect_image.bottom(), img_h_orig - 1) # bottom edge is inclusive index

            # Recalculate width/height after clamping edges
            clamped_w = clamped_r - clamped_x + 1
            clamped_h = clamped_b - clamped_y + 1

            # Ensure width/height are still valid (>= 1) after clamping
            if clamped_w <= 0 or clamped_h <= 0:
                 logger.warning(f"Selection clamping resulted in non-positive dimensions ({clamped_w}x{clamped_h}). Returning empty rect.")
                 return QRect()

            return QRect(clamped_x, clamped_y, clamped_w, clamped_h)

        # Return empty rect if self._final_selected_rect_display is None or Null
        return QRect()
