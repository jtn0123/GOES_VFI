"""GUI Helper Utilities for GOES-VFI.

This module provides helper functions for the GUI, including RIFE capability detection
and UI element management.
"""

import logging
import pathlib
from typing import Any

from PyQt6.QtCore import QPoint, QPointF, QRect, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from goesvfi.utils.config import find_rife_executable
from goesvfi.utils.rife_analyzer import RifeCapabilityDetector

# Set up logging
logger = logging.getLogger(__name__)


class RifeCapabilityManager:
    """Manages RIFE CLI capabilities and updates UI elements accordingly.

    This class detects the capabilities of the RIFE CLI executable and
    updates UI elements to reflect what options are available.
    """

    def __init__(self, model_key: str = "rife-v4.6") -> None:
        """Initialize the capability manager.

        Args:
            model_key: The model key to use for finding the RIFE executable
        """
        self.model_key = model_key
        self.detector: RifeCapabilityDetector | None = None
        self.capabilities: dict[str, bool] = {}
        self.exe_path: pathlib.Path | None = None
        self.version: str | None = None

        # Try to detect capabilities
        self._detect_capabilities()

    def _detect_capabilities(self) -> None:
        """Detect the capabilities of the RIFE CLI executable."""
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

            logger.info("RIFE capabilities detected: %s", self.capabilities)
            logger.info("RIFE version detected: %s", self.version)

        except Exception as e:
            logger.exception("Error detecting RIFE capabilities: %s", e)
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
        """Update UI elements based on detected capabilities.

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
            uhd_mode_cb.setToolTip("Enable UHD mode for 4K+ images (slower but better quality)")
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
            thread_spec_edit.setToolTip("Thread specification not supported by this RIFE executable")

        # Update TTA spatial
        if self.capabilities.get("tta_spatial", False):
            tta_spatial_cb.setEnabled(True)
            tta_spatial_cb.setToolTip("Enable spatial test-time augmentation (slower but better quality)")
        else:
            tta_spatial_cb.setEnabled(False)
            tta_spatial_cb.setToolTip("Spatial TTA not supported by this RIFE executable")

        # Update TTA temporal
        if self.capabilities.get("tta_temporal", False):
            tta_temporal_cb.setEnabled(True)
            tta_temporal_cb.setToolTip("Enable temporal test-time augmentation (slower but better quality)")
        else:
            tta_temporal_cb.setEnabled(False)
            tta_temporal_cb.setToolTip("Temporal TTA not supported by this RIFE executable")

    def get_capability_summary(self) -> str:
        """Get a summary of the detected capabilities.

        Returns:
            A string summarizing the detected capabilities
        """
        if not self.detector:
            return "RIFE capabilities not detected"

        version_str = f"v{self.version}" if self.version else "unknown version"

        # Count supported features
        supported_count = sum(1 for v in self.capabilities.values() if v)
        total_count = len(self.capabilities)

        return f"RIFE {version_str} - {supported_count}/{total_count} features supported"


# GUI Component classes
class ClickableLabel(QLabel):
    """A QLabel that emits a signal when clicked."""

    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the ClickableLabel."""
        super().__init__(parent)
        self.file_path: str | None = None
        self.processed_image = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
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

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the CropLabel."""
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMouseTracking(True)

        # Selection state
        self.selecting = False
        self.selection_start_point: QPoint | None = None
        self.selection_end_point: QPoint | None = None
        self.selected_rect: QRect | None = None

        # Pixmap offset for centering
        self._pixmap_offset_x = 0
        self._pixmap_offset_y = 0

        # Handle detection
        self.handle_size = 12
        self.active_handle: str | None = None  # Which handle is being dragged
        self.resizing = False

        # Parent dialog reference for aspect ratio
        self._parent_dialog: Any | None = None

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

    def _get_pos_on_pixmap(self, pos: QPoint) -> QPoint | None:
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

    def _get_handle_at_pos(self, pos: QPoint) -> str | None:
        """Check if position is over a selection handle."""
        if not self.selected_rect or self.selected_rect.isNull():
            return None

        # Convert to widget coordinates
        rect = QRect(
            self.selected_rect.x() + self._pixmap_offset_x,
            self.selected_rect.y() + self._pixmap_offset_y,
            self.selected_rect.width(),
            self.selected_rect.height(),
        )

        # Define handle regions
        handles = {
            "tl": QRect(
                rect.x() - self.handle_size // 2,
                rect.y() - self.handle_size // 2,
                self.handle_size,
                self.handle_size,
            ),
            "tr": QRect(
                rect.x() + rect.width() - self.handle_size // 2,
                rect.y() - self.handle_size // 2,
                self.handle_size,
                self.handle_size,
            ),
            "bl": QRect(
                rect.x() - self.handle_size // 2,
                rect.y() + rect.height() - self.handle_size // 2,
                self.handle_size,
                self.handle_size,
            ),
            "br": QRect(
                rect.x() + rect.width() - self.handle_size // 2,
                rect.y() + rect.height() - self.handle_size // 2,
                self.handle_size,
                self.handle_size,
            ),
        }

        # Check which handle contains the position
        for handle_name, handle_rect in handles.items():
            if handle_rect.contains(pos):
                return handle_name

        return None

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        """Start selection or handle resize on mouse press."""
        if event is None:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            widget_pos = event.position().toPoint()

            # Check if we're clicking on a handle
            handle = self._get_handle_at_pos(widget_pos)
            if handle:
                self.resizing = True
                self.active_handle = handle
                self.selection_start_point = self._get_pos_on_pixmap(widget_pos)
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                self.update()
                return

            # Otherwise start new selection
            pos = self._get_pos_on_pixmap(widget_pos)
            if pos:
                self.selecting = True
                self.resizing = False
                self.active_handle = None
                self.selection_start_point = pos
                self.selection_end_point = pos
                self.selected_rect = None
                self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        """Update selection or resize on mouse move."""
        if event is None:
            return

        widget_pos = event.position().toPoint()
        pos = self._get_pos_on_pixmap(widget_pos)

        if self.resizing and self.active_handle and self.selected_rect and pos:
            self._handle_resize_move(pos)
        elif self.selecting and pos:
            self._handle_selection_move(pos)
        else:
            self._update_hover_cursor(widget_pos)

        super().mouseMoveEvent(event)

    def _handle_resize_move(self, pos: QPoint) -> None:
        """Handle mouse move during resize."""
        if not self.selected_rect or not self.active_handle:
            return

        new_rect = QRect(self.selected_rect)

        if "l" in self.active_handle:  # Left handles
            new_rect.setLeft(pos.x())
        if "r" in self.active_handle:  # Right handles
            new_rect.setRight(pos.x())
        if "t" in self.active_handle:  # Top handles
            new_rect.setTop(pos.y())
        if "b" in self.active_handle:  # Bottom handles
            new_rect.setBottom(pos.y())

        # Ensure minimum size
        if new_rect.width() > 10 and new_rect.height() > 10:
            # Apply aspect ratio constraint if locked
            if self._should_constrain_aspect():
                self._apply_aspect_ratio_constraint(new_rect, self.active_handle)

            self.selected_rect = new_rect.normalized()
            self.selection_changed.emit()
            self.update()

    def _handle_selection_move(self, pos: QPoint) -> None:
        """Handle mouse move during selection."""
        self.selection_end_point = pos

        # Apply aspect ratio constraint while dragging if locked
        if self._should_constrain_aspect():
            self._constrain_end_point_to_aspect_ratio()

        self.selection_changed.emit()
        self.update()

    def _update_hover_cursor(self, widget_pos: QPoint) -> None:
        """Update cursor based on handle hover."""
        handle = self._get_handle_at_pos(widget_pos)
        if handle:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def _should_constrain_aspect(self) -> bool:
        """Check if aspect ratio should be constrained."""
        return bool(
            self._parent_dialog
            and hasattr(self._parent_dialog, "constrain_aspect")
            and self._parent_dialog.constrain_aspect
            and hasattr(self._parent_dialog, "aspect_ratio")
            and self._parent_dialog.aspect_ratio
        )

    def _constrain_end_point_to_aspect_ratio(self) -> None:
        """Constrain the end point to maintain aspect ratio while dragging."""
        if not self.selection_start_point or not self.selection_end_point:
            return

        if not self._parent_dialog or not self._parent_dialog.aspect_ratio:
            return

        # Calculate the dimensions
        width = abs(self.selection_end_point.x() - self.selection_start_point.x())
        height = abs(self.selection_end_point.y() - self.selection_start_point.y())

        # Calculate what the dimensions would be for each constraint
        # Option 1: Keep width, adjust height
        height_from_width = width / self._parent_dialog.aspect_ratio
        # Option 2: Keep height, adjust width
        width_from_height = height * self._parent_dialog.aspect_ratio

        # Choose the option that results in the larger area (more intuitive for users)
        area1 = width * height_from_width
        area2 = width_from_height * height

        if area1 >= area2:
            # Use width as base, adjust height
            new_height = int(height_from_width)
            if self.selection_end_point.y() > self.selection_start_point.y():
                self.selection_end_point.setY(self.selection_start_point.y() + new_height)
            else:
                self.selection_end_point.setY(self.selection_start_point.y() - new_height)
        else:
            # Use height as base, adjust width
            new_width = int(width_from_height)
            if self.selection_end_point.x() > self.selection_start_point.x():
                self.selection_end_point.setX(self.selection_start_point.x() + new_width)
            else:
                self.selection_end_point.setX(self.selection_start_point.x() - new_width)

    def _apply_aspect_ratio_constraint(self, rect: QRect, handle: str) -> None:
        """Apply aspect ratio constraint when resizing from a handle."""
        if not self._parent_dialog or not self._parent_dialog.aspect_ratio:
            return

        # Determine which dimension changed more
        if "l" in handle or "r" in handle:
            # Width changed, adjust height
            new_height = int(rect.width() / self._parent_dialog.aspect_ratio)
            if "t" in handle:
                rect.setTop(rect.bottom() - new_height)
            else:
                rect.setBottom(rect.top() + new_height)
        else:
            # Height changed, adjust width
            new_width = int(rect.height() * self._parent_dialog.aspect_ratio)
            if "l" in handle:
                rect.setLeft(rect.right() - new_width)
            else:
                rect.setRight(rect.left() + new_width)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        """Finalize selection or resize on mouse release."""
        if event is None:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            if self.resizing:
                self.resizing = False
                self.active_handle = None
                self.setCursor(Qt.CursorShape.CrossCursor)
                self.selection_finished.emit()
                self.update()
            elif self.selecting:
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
        """Paint the label with selection overlay and darkened area."""
        super().paintEvent(event)

        if (self.selecting or self.selected_rect) and self.selection_start_point and self.selection_end_point:
            painter = QPainter(self)

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

            # Draw darkened overlay outside selection with gradient effect
            if self.pixmap() and not self.pixmap().isNull():
                # Create a dark overlay for the entire widget
                overlay_color = QColor(0, 0, 0, 150)  # Darker overlay
                painter.fillRect(self.rect(), overlay_color)

                # Clear the selection area (make it fully transparent)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(rect, Qt.GlobalColor.transparent)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

                # Redraw just the selection area from the original pixmap
                if rect.width() > 0 and rect.height() > 0:
                    source_rect = QRect(
                        rect.x() - self._pixmap_offset_x,
                        rect.y() - self._pixmap_offset_y,
                        rect.width(),
                        rect.height(),
                    )
                    painter.drawPixmap(rect, self.pixmap(), source_rect)

            # Draw selection border with glow effect
            # Outer glow
            glow_pen = QPen(QColor(255, 255, 0, 80), 6, Qt.PenStyle.SolidLine)
            painter.setPen(glow_pen)
            painter.drawRect(rect)

            # Main border
            pen = QPen(QColor(255, 255, 0, 255), 3, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawRect(rect)

            # Inner border for contrast
            inner_pen = QPen(QColor(255, 255, 255, 200), 1, Qt.PenStyle.SolidLine)
            painter.setPen(inner_pen)
            inner_rect = rect.adjusted(1, 1, -1, -1)
            painter.drawRect(inner_rect)

            # Draw corner handles with better styling
            handle_color = QColor(255, 255, 0, 255)
            handle_border = QColor(0, 0, 0, 200)
            handle_size = 10  # Slightly larger handles

            # Draw handles with border for better visibility
            handles = [
                (rect.x(), rect.y()),  # Top-left
                (rect.x() + rect.width(), rect.y()),  # Top-right
                (rect.x(), rect.y() + rect.height()),  # Bottom-left
                (rect.x() + rect.width(), rect.y() + rect.height()),  # Bottom-right
            ]

            for x, y in handles:
                # Draw shadow
                painter.fillRect(
                    x - handle_size // 2 + 1,
                    y - handle_size // 2 + 1,
                    handle_size,
                    handle_size,
                    QColor(0, 0, 0, 100),
                )
                # Draw border
                painter.fillRect(
                    x - handle_size // 2 - 1,
                    y - handle_size // 2 - 1,
                    handle_size + 2,
                    handle_size + 2,
                    handle_border,
                )
                # Draw handle
                painter.fillRect(
                    x - handle_size // 2,
                    y - handle_size // 2,
                    handle_size,
                    handle_size,
                    handle_color,
                )

            # Draw size info in the selection if it's large enough
            if rect.width() > 100 and rect.height() > 50:
                size_text = f"{rect.width()} × {rect.height()}"
                font = painter.font()
                font.setPointSize(12)
                font.setBold(True)
                painter.setFont(font)

                # Draw text with background
                text_rect = painter.boundingRect(rect, Qt.AlignmentFlag.AlignCenter, size_text)
                bg_rect = text_rect.adjusted(-8, -4, 8, 4)
                painter.fillRect(bg_rect, QColor(0, 0, 0, 180))

                painter.setPen(QColor(255, 255, 255, 255))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, size_text)


class CropSelectionDialog(QDialog):
    """Full-screen borderless dialog for selecting a crop region on an image."""

    def __init__(
        self,
        image: QImage | None = None,
        initial_rect: QRect | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the dialog with an optional image and initial rectangle."""
        # Create as a top-level window to avoid parent window constraints
        super().__init__(None)  # Pass None to make it a true top-level window

        # Set window title
        self.setWindowTitle("Select Crop Region")

        # Keep reference to parent for cleanup if needed
        self._parent = parent

        # Make the dialog frameless with minimal borders and ensure it's on top
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # Tool flag helps with window management
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)

        # Use most of screen real estate with small margin
        screen = QApplication.primaryScreen()
        if screen:
            screen_rect = screen.availableGeometry()  # Use available geometry to respect taskbars
            margin = 40  # Small margin around edges

            # Calculate dialog dimensions
            dialog_width = screen_rect.width() - 2 * margin
            dialog_height = screen_rect.height() - 2 * margin

            # Center the dialog on screen
            x = screen_rect.x() + margin
            y = screen_rect.y() + margin

            self.setGeometry(x, y, dialog_width, dialog_height)

            # Ensure the window is properly sized before showing
            self.setMinimumSize(800, 600)  # Minimum size to ensure buttons are visible

        self.image = image if image and not image.isNull() else QImage()
        self.initial_rect = initial_rect
        self.scale_factor = 1.0
        self._final_selected_rect_display = QRect()
        self.zoom_level = 1.0
        self.pan_offset = QPointF(0, 0)
        self.is_panning = False
        self.last_mouse_pos = QPoint()
        self.aspect_ratio: float | None = None  # None means freeform
        self.constrain_aspect = False

        # Apply qt-material theme properties
        self.setProperty("class", "CropSelectionDialog")

        # Create the main layout with no margins for full screen
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create header bar with instructions and controls
        header_widget = QWidget()
        header_widget.setFixedHeight(80)
        header_widget.setProperty("class", "ControlFrame")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 10, 20, 10)

        # Add header title
        header_title = QLabel("✂️ Crop Selection Tool")
        header_title.setProperty("class", "AppHeader")
        header_layout.addWidget(header_title)

        header_layout.addSpacing(20)

        # Instructions
        instruction_label = QLabel("📍 Click and drag to select region")
        instruction_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        instruction_label.setProperty("class", "StandardLabel")
        header_layout.addWidget(instruction_label)

        # Add aspect ratio controls
        aspect_container = QWidget()
        aspect_layout = QHBoxLayout(aspect_container)
        aspect_layout.setContentsMargins(0, 0, 0, 0)
        aspect_layout.setSpacing(10)

        # Aspect ratio label
        aspect_label = QLabel("📐 Aspect Ratio:")
        aspect_label.setProperty("class", "StandardLabel")
        aspect_layout.addWidget(aspect_label)

        # Aspect ratio combo box
        self.aspect_combo = QComboBox()
        self.aspect_combo.setToolTip("Select a predefined aspect ratio or use freeform")
        # Use default qt-material styling for combo box
        self.aspect_combo.addItems([
            "Freeform",
            "16:9 (HD)",
            "4:3 (Standard)",
            "1:1 (Square)",
            "3:2 (Photo)",
            "2:1 (Cinema)",
            "9:16 (Portrait)",
        ])
        self.aspect_combo.currentTextChanged.connect(self._on_aspect_changed)
        aspect_layout.addWidget(self.aspect_combo)

        # Constrain checkbox
        self.constrain_checkbox = QCheckBox("🔒 Lock")
        self.constrain_checkbox.setToolTip("Lock aspect ratio when resizing selection")
        # Use default qt-material styling for checkbox
        self.constrain_checkbox.toggled.connect(self._on_constrain_toggled)
        aspect_layout.addWidget(self.constrain_checkbox)

        header_layout.addWidget(aspect_container)
        header_layout.addStretch()

        # Add zoom level indicator
        zoom_prefix = QLabel("🔍 Zoom:")
        zoom_prefix.setProperty("class", "StandardLabel")
        header_layout.addWidget(zoom_prefix)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setProperty("class", "StatusInfo")
        header_layout.addWidget(self.zoom_label)

        main_layout.addWidget(header_widget)

        # Create main content area (no scroll area needed for full screen)
        content_widget = QWidget()
        content_widget.setProperty("class", "CropDialogContent")  # Theme handled by qt-material
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # Create the crop label
        self.crop_label = CropLabel()
        self.crop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.crop_label.setMinimumSize(200, 200)
        self.crop_label._parent_dialog = self  # type: ignore  # Set reference for aspect ratio

        # Set up the image if provided
        if image and isinstance(image, QImage) and not image.isNull():
            # Get available space for the image
            screen = QApplication.primaryScreen()
            if screen:
                screen_size = screen.size()
                # Leave space for header (60px) and footer (100px) and margins (80px total)
                available_height = screen_size.height() - 240
                available_width = screen_size.width() - 120
            else:
                available_height = 800
                available_width = 1200

            # Scale image to fit available space while maintaining aspect ratio
            scaled_image = image.scaled(
                available_width,
                available_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            # Calculate scale factor for coordinate conversion
            self.scale_factor = max(
                image.width() / scaled_image.width(),
                image.height() / scaled_image.height(),
            )

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

        content_layout.addWidget(self.crop_label)
        main_layout.addWidget(content_widget, 1)  # Stretch to fill available space

        # Create footer bar with status and preview
        footer_widget = QWidget()
        footer_widget.setFixedHeight(120)
        footer_widget.setProperty("class", "ControlFrame")
        footer_layout = QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(20, 10, 20, 10)

        # Status info on the left
        status_widget = QWidget()
        status_layout = QVBoxLayout(status_widget)
        status_layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("📊 No selection")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.status_label.setProperty("class", "StatusInfo")
        status_layout.addWidget(self.status_label)

        # Add tips
        tips_label = QLabel("💡 Tips: Use Lock for aspect ratio • Click corners to resize • Scroll to zoom")
        tips_label.setProperty("class", "StandardLabel")
        tips_label.setWordWrap(True)
        status_layout.addWidget(tips_label)

        footer_layout.addWidget(status_widget, 2)

        # Preview in the center
        preview_container = QWidget()
        preview_container.setFixedSize(140, 80)
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(10, 0, 10, 0)
        preview_layout.setSpacing(2)

        preview_title = QLabel("👁️ Preview")
        preview_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_title.setProperty("class", "StandardLabel")
        preview_layout.addWidget(preview_title)

        self.crop_preview_label = ClickableLabel()
        self.crop_preview_label.setText("Select a region")
        self.crop_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.crop_preview_label.setFixedSize(120, 60)
        self.crop_preview_label.setStyleSheet(
            """
            QLabel {
                border: 2px dashed rgba(255, 255, 255, 0.3);
                border-radius: 4px;
                background-color: rgba(0, 0, 0, 0.2);
            }
        """
        )
        self.crop_preview_label.setToolTip("Click to see full preview")
        self.crop_preview_label.clicked.connect(self._show_full_preview)
        preview_layout.addWidget(self.crop_preview_label)

        footer_layout.addWidget(preview_container)
        footer_layout.addStretch(1)

        # Add action buttons to the footer (before adding footer to main layout)
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(10)

        # Clear button - starts disabled
        self.clear_button = QPushButton("🗑️ Clear")
        self.clear_button.setProperty("class", "DialogButton")
        self.clear_button.setToolTip("Clear the current selection")
        self.clear_button.clicked.connect(self._clear_selection)
        self.clear_button.setEnabled(False)
        button_layout.addWidget(self.clear_button)

        # Cancel button
        cancel_button = QPushButton("❌ Cancel (Esc)")
        cancel_button.setProperty("class", "DialogButton")
        cancel_button.setToolTip("Cancel and close without cropping")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        # OK button with accent color - starts disabled
        self.ok_button = QPushButton("✅ Crop (Enter)")
        self.ok_button.setProperty("class", "StartButton")
        self.ok_button.setToolTip("Apply the crop selection")
        self.ok_button.clicked.connect(self._accept_selection)
        self.ok_button.setEnabled(False)
        button_layout.addWidget(self.ok_button)

        footer_layout.addWidget(button_container)

        # Now add the footer to the main layout
        main_layout.addWidget(footer_widget)

        # Connect signals to update status
        self.crop_label.selection_changed.connect(self._update_status)
        self.crop_label.selection_finished.connect(self._update_status)
        self.crop_label.selection_finished.connect(self._on_selection_finished)

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

            # Calculate aspect ratio if selection exists
            aspect_text = ""
            if orig_w > 0 and orig_h > 0:
                current_ratio = orig_w / orig_h
                aspect_text = f" | Ratio: {current_ratio:.2f}:1"

            self.status_label.setText(
                f"📊 Selection: {orig_x}, {orig_y} → {orig_x + orig_w}, {orig_y + orig_h} "
                f"(size: {orig_w} × {orig_h}){aspect_text}"
            )

            # Update crop preview
            self._update_crop_preview(rect)
        else:
            self.status_label.setText("📊 No selection")
            # Clear crop preview
            self.crop_preview_label.clear()
            self.crop_preview_label.setText("Select a region")

    def _update_crop_preview(self, rect: QRect | None) -> None:
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
            logger.exception("Error updating crop preview: %s", e)
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
            msg.setText("Please select a crop region before clicking OK, or click Cancel to exit.")
            msg.exec()

    def get_selected_rect(self) -> QRect:
        """Get the selected rectangle in original image coordinates."""
        if self._final_selected_rect_display is None or (
            isinstance(self._final_selected_rect_display, QRect) and self._final_selected_rect_display.isNull()
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

    def _store_final_selection(self, rect: QRect | None = None) -> None:
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

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        """Handle keyboard shortcuts."""
        if event is None:
            return

        key = event.key()

        # ESC to cancel
        if key == Qt.Key.Key_Escape:
            self.reject()
        # Enter/Return to accept
        elif key in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self._accept_selection()
        # Delete/Backspace to clear selection
        elif key in {Qt.Key.Key_Delete, Qt.Key.Key_Backspace}:
            self._clear_selection()
        # Plus/Equals to zoom in
        elif key in {Qt.Key.Key_Plus, Qt.Key.Key_Equal}:
            self._zoom_in()
        # Minus to zoom out
        elif key == Qt.Key.Key_Minus:
            self._zoom_out()
        # R to reset zoom
        elif key == Qt.Key.Key_R:
            self._reset_zoom()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent | None) -> None:
        """Handle mouse wheel for zooming."""
        if event is None:
            return

        # Get zoom direction
        delta = event.angleDelta()

        # For Mac touchpad, check both Y and X deltas
        y_delta = delta.y()
        x_delta = delta.x()

        # Use whichever delta is larger in magnitude
        if abs(y_delta) > abs(x_delta):
            # Vertical scrolling (normal mouse wheel or vertical touchpad)
            if y_delta > 0:
                self._zoom_in()
            else:
                self._zoom_out()
        elif x_delta != 0:
            # Horizontal scrolling (sometimes used on touchpads)
            if x_delta > 0:
                self._zoom_in()
            else:
                self._zoom_out()

        event.accept()

    def _zoom_in(self) -> None:
        """Zoom in on the image."""
        if hasattr(self, "zoom_level"):
            self.zoom_level = min(self.zoom_level * 1.2, 5.0)
            self._update_zoom_display()
            self._apply_zoom()

    def _zoom_out(self) -> None:
        """Zoom out on the image."""
        if hasattr(self, "zoom_level"):
            self.zoom_level = max(self.zoom_level / 1.2, 0.2)
            self._update_zoom_display()
            self._apply_zoom()

    def _reset_zoom(self) -> None:
        """Reset zoom to 100%."""
        if hasattr(self, "zoom_level"):
            self.zoom_level = 1.0
            self._update_zoom_display()
            self._apply_zoom()

    def _update_zoom_display(self) -> None:
        """Update the zoom level indicator."""
        if hasattr(self, "zoom_label"):
            self.zoom_label.setText(f"{int(self.zoom_level * 100)}%")

    def _apply_zoom(self) -> None:
        """Apply the current zoom level to the image display."""
        if not self.image or self.image.isNull():
            return

        # Get base dimensions
        screen = QApplication.primaryScreen()
        if screen:
            screen_size = screen.size()
            available_height = screen_size.height() - 240
            available_width = screen_size.width() - 120
        else:
            available_height = 800
            available_width = 1200

        # Apply zoom to available space
        target_width = int(available_width * self.zoom_level)
        target_height = int(available_height * self.zoom_level)

        # Scale image with zoom
        scaled_image = self.image.scaled(
            target_width,
            target_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        # Update scale factor
        self.scale_factor = max(
            self.image.width() / scaled_image.width(),
            self.image.height() / scaled_image.height(),
        )

        # Update the pixmap
        pixmap = QPixmap.fromImage(scaled_image)
        self.crop_label.setPixmap(pixmap)
        self.crop_label.setFixedSize(pixmap.size())

        # Keep selection if it exists
        if self.initial_rect:
            display_rect = QRect(
                int(self.initial_rect.x() / self.scale_factor),
                int(self.initial_rect.y() / self.scale_factor),
                int(self.initial_rect.width() / self.scale_factor),
                int(self.initial_rect.height() / self.scale_factor),
            )
            self.crop_label.selected_rect = display_rect

    def _on_selection_finished(self) -> None:
        """Called when selection is finished."""
        # Enable/disable buttons based on selection
        has_selection = self.crop_label.selected_rect is not None and not self.crop_label.selected_rect.isNull()
        if hasattr(self, "clear_button"):
            self.clear_button.setEnabled(has_selection)
        if hasattr(self, "ok_button"):
            self.ok_button.setEnabled(has_selection)

    def _on_aspect_changed(self, text: str) -> None:
        """Handle aspect ratio selection change."""
        if text == "Freeform":
            self.aspect_ratio = None
            self.constrain_checkbox.setChecked(False)
            self.constrain_checkbox.setEnabled(False)
        else:
            # Parse aspect ratio from text (width/height)
            if "16:9" in text:
                self.aspect_ratio = 16 / 9  # 1.778 - wider than tall
            elif "4:3" in text:
                self.aspect_ratio = 4 / 3  # 1.333 - wider than tall
            elif "1:1" in text:
                self.aspect_ratio = 1.0  # Square
            elif "3:2" in text:
                self.aspect_ratio = 3 / 2  # 1.5 - wider than tall
            elif "2:1" in text:
                self.aspect_ratio = 2.0  # 2.0 - much wider than tall
            elif "9:16" in text:
                self.aspect_ratio = 9 / 16  # 0.563 - taller than wide (portrait)

            self.constrain_checkbox.setEnabled(True)

            # Debug log removed for production

            # Apply aspect ratio to current selection if locked
            if self.constrain_checkbox.isChecked() and self.crop_label.selected_rect:
                self._apply_aspect_ratio()

    def _on_constrain_toggled(self, checked: bool) -> None:
        """Handle constraint checkbox toggle."""
        self.constrain_aspect = checked
        if checked and self.aspect_ratio and self.crop_label.selected_rect:
            self._apply_aspect_ratio()

    def _apply_aspect_ratio(self) -> None:
        """Apply the current aspect ratio to the selection."""
        if not self.crop_label.selected_rect or not self.aspect_ratio:
            return

        rect = self.crop_label.selected_rect
        current_width = rect.width()
        current_height = rect.height()

        if current_width == 0 or current_height == 0:
            return

        # Calculate new dimensions maintaining aspect ratio
        current_ratio = current_width / current_height

        if current_ratio > self.aspect_ratio:
            # Too wide, adjust width
            new_width = int(current_height * self.aspect_ratio)
            new_height = current_height
        else:
            # Too tall, adjust height
            new_width = current_width
            new_height = int(current_width / self.aspect_ratio)

        # Update the rectangle
        rect.setWidth(new_width)
        rect.setHeight(new_height)
        self.crop_label.selected_rect = rect
        self.crop_label.update()
        self._update_status()

    def exec(self) -> int:
        """Override exec to ensure dialog is properly positioned and visible."""
        # Ensure the dialog is on top and visible
        self.raise_()
        self.activateWindow()

        # Force a repaint to ensure all widgets are visible
        QApplication.processEvents()

        # Call the parent exec
        result = super().exec()
        return int(result)

    def showEvent(self, event: Any) -> None:
        """Override showEvent to ensure proper positioning."""
        super().showEvent(event)

        # Ensure we're on top
        self.raise_()
        self.activateWindow()

        # Force geometry update
        self.updateGeometry()

    def _show_full_preview(self) -> None:
        """Show the full cropped preview in a dialog."""
        if not self.crop_label.selected_rect or self.crop_label.selected_rect.isNull():
            return

        if self.image.isNull():
            return

        # Extract the crop region at full resolution
        orig_x = int(self.crop_label.selected_rect.x() * self.scale_factor)
        orig_y = int(self.crop_label.selected_rect.y() * self.scale_factor)
        orig_w = int(self.crop_label.selected_rect.width() * self.scale_factor)
        orig_h = int(self.crop_label.selected_rect.height() * self.scale_factor)

        # Clamp to image bounds
        orig_x = max(0, min(orig_x, self.image.width() - 1))
        orig_y = max(0, min(orig_y, self.image.height() - 1))
        orig_w = min(orig_w, self.image.width() - orig_x)
        orig_h = min(orig_h, self.image.height() - orig_y)

        if orig_w <= 0 or orig_h <= 0:
            return

        # Extract the cropped image
        cropped_image = self.image.copy(orig_x, orig_y, orig_w, orig_h)

        # Create a simple preview dialog
        preview_dialog = QDialog(self)
        preview_dialog.setWindowTitle("👁️ Crop Preview")
        preview_dialog.setModal(True)

        layout = QVBoxLayout(preview_dialog)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Create a label to show the image
        preview_label = QLabel()
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Scale the preview to fit a reasonable window size
        max_size = 800
        if cropped_image.width() > max_size or cropped_image.height() > max_size:
            scaled = cropped_image.scaled(
                max_size,
                max_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            preview_label.setPixmap(QPixmap.fromImage(scaled))
        else:
            preview_label.setPixmap(QPixmap.fromImage(cropped_image))

        layout.addWidget(preview_label)

        # Add size info
        info_label = QLabel(f"📊 Size: {orig_w} × {orig_h} pixels")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setProperty("class", "StatusInfo")
        layout.addWidget(info_label)

        # Add close button
        close_button = QPushButton("✅ Close")
        close_button.setProperty("class", "DialogButton")
        close_button.clicked.connect(preview_dialog.accept)
        layout.addWidget(close_button)

        preview_dialog.exec()


class ImageViewerDialog(QDialog):
    """Dialog for viewing an image with zoom and pan capabilities."""

    def __init__(
        self,
        image: QImage | None = None,
        title: str = "Full Resolution",
        info_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the image viewer dialog."""
        super().__init__(parent)
        self.setWindowTitle(f"🔍 {title}")
        self.original_qimage = image  # Store as original_qimage for compatibility
        self.image = image
        self.info_text = info_text

        # Zoom and pan state
        self.zoom_factor = 1.0
        self.min_zoom_factor = 0.1
        self.max_zoom_factor = 10.0
        self.panning = False
        self.was_dragged = False
        self.last_pan_pos = QPointF()
        self.pan_offset = QPointF(0.0, 0.0)

        # Set up the dialog
        self.setModal(True)
        self.setMinimumSize(800, 600)
        self.setProperty("class", "ImageViewerDialog")

        # Create UI layout
        self._setup_ui()

        if image and isinstance(image, QImage) and not image.isNull():
            # Size the dialog to fill most of the screen (90% to maximize space)
            screen = QApplication.primaryScreen()
            if screen:
                screen_rect = screen.availableGeometry()
                max_width = int(screen_rect.width() * 0.9)
                max_height = int(screen_rect.height() * 0.9)

                # Calculate ideal size based on image aspect ratio
                image_aspect = image.width() / image.height()
                screen_aspect = max_width / max_height

                # Fit image to fill as much screen as possible
                if image_aspect > screen_aspect:
                    # Image is wider - fit to width
                    width = max_width
                    height = int(width / image_aspect) + 150  # Extra for header/footer
                    # Make sure we don't exceed max height
                    if height > max_height:
                        height = max_height
                        width = int((height - 150) * image_aspect)
                else:
                    # Image is taller - fit to height
                    height = max_height
                    width = int((height - 150) * image_aspect) + 40  # Extra for margins
                    # Make sure we don't exceed max width
                    if width > max_width:
                        width = max_width
                        height = int(width / image_aspect) + 150

                self.resize(width, height)

                # Center on screen
                self.move(
                    int((screen_rect.width() - width) / 2),
                    int((screen_rect.height() - height) / 2),
                )
            else:
                # Fallback sizing
                width = min(image.width() + 100, 1200)
                height = min(image.height() + 200, 900)
                self.resize(width, height)

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Add header with controls
        header_widget = QWidget()
        header_widget.setProperty("class", "ControlFrame")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 10, 10, 10)

        # Add title
        title_label = QLabel(f"🔍 {self.windowTitle().replace('🔍 ', '')}")
        title_label.setProperty("class", "AppHeader")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Add zoom indicator
        self.zoom_label = QLabel(f"🔍 Zoom: {int(self.zoom_factor * 100)}%")
        self.zoom_label.setProperty("class", "StatusInfo")
        header_layout.addWidget(self.zoom_label)

        # Add instructions
        instructions = QLabel("💡 Scroll to zoom • Drag to pan • Click to close")
        instructions.setProperty("class", "StandardLabel")
        header_layout.addWidget(instructions)

        layout.addWidget(header_widget)

        # Create image display label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet(
            """
            QLabel {
                background-color: rgba(0, 0, 0, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
        """
        )

        # Set the image if available
        if self.image and not self.image.isNull():
            # Don't set image here - wait for showEvent when we know the actual size
            pass

        layout.addWidget(self.image_label, 1)  # Give it stretch priority

        # Add footer if info text is provided
        if self.info_text:
            footer_widget = QWidget()
            footer_widget.setProperty("class", "ControlFrame")
            footer_layout = QHBoxLayout(footer_widget)
            footer_layout.setContentsMargins(10, 10, 10, 10)

            info_label = QLabel(f"📄 {self.info_text}")
            info_label.setProperty("class", "StatusInfo")
            footer_layout.addWidget(info_label)

            footer_layout.addStretch()

            layout.addWidget(footer_widget)

    def wheelEvent(self, event: QWheelEvent | None) -> None:
        """Handle zoom with mouse wheel."""
        if event is None:
            return
        # Get zoom direction
        delta = event.angleDelta().y()
        zoom_in = delta > 0

        # Calculate new zoom factor
        new_zoom_factor = self.zoom_factor * 1.1 if zoom_in else self.zoom_factor / 1.1

        # Get available space for image
        available_width = self.width() - 40
        available_height = self.height() - 150  # Approximate header/footer height

        # Calculate what the image size would be with new zoom
        if self.image and not self.image.isNull():
            target_width = int(self.image.width() * new_zoom_factor)
            target_height = int(self.image.height() * new_zoom_factor)

            # When zooming in, stop if image would exceed window bounds
            if zoom_in and (target_width >= available_width or target_height >= available_height):
                # Calculate the maximum zoom that fits
                max_zoom_x = available_width / self.image.width()
                max_zoom_y = available_height / self.image.height()
                max_zoom = max(max_zoom_x, max_zoom_y)  # Use max to fill at least one dimension

                new_zoom_factor = min(new_zoom_factor, max_zoom)

        # Apply zoom limits
        new_zoom_factor = max(self.min_zoom_factor, min(new_zoom_factor, self.max_zoom_factor))

        # Only update if zoom actually changed
        if abs(new_zoom_factor - self.zoom_factor) > 0.001:
            self.zoom_factor = new_zoom_factor

            # Update zoom label
            if hasattr(self, "zoom_label"):
                self.zoom_label.setText(f"🔍 Zoom: {int(self.zoom_factor * 100)}%")

            # Update image display with new zoom
            if hasattr(self, "image_label") and self.image and not self.image.isNull():
                self._update_image_display()

            self.update()

        event.accept()

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        """Start panning on mouse press."""
        if event is None:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.panning = True
            self.was_dragged = False
            self.last_pan_pos = event.position()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        """Handle panning."""
        if event is None:
            return
        if self.panning:
            self.was_dragged = True
            # In a real implementation, we would update the view offset here
            self.last_pan_pos = event.position()
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        """Stop panning on mouse release."""
        if event is None:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            if self.panning and not self.was_dragged:
                # Click without drag - close the dialog
                self.accept()
            self.panning = False
        super().mouseReleaseEvent(event)

    def showEvent(self, event: Any) -> None:
        """Handle show event to properly size the image."""
        super().showEvent(event)

        if self.image and not self.image.isNull() and hasattr(self, "image_label"):
            # Reset zoom to 1.0 to fill the window optimally on first show
            self.zoom_factor = 1.0
            # Now that the dialog is shown, we know the actual size
            self._update_image_display()
            # Update zoom label
            if hasattr(self, "zoom_label"):
                self.zoom_label.setText(f"🔍 Zoom: {int(self.zoom_factor * 100)}%")

    def resizeEvent(self, event: Any) -> None:
        """Handle resize event to update image display."""
        super().resizeEvent(event)

        if self.image and not self.image.isNull() and hasattr(self, "image_label"):
            self._update_image_display()

    def _update_image_display(self) -> None:
        """Update the image display based on current dialog size and zoom."""
        if not self.image or self.image.isNull() or not hasattr(self, "image_label"):
            return

        try:
            # Get available space for image (accounting for header/footer)
            available_width = max(100, self.width() - 40)
            available_height = max(100, self.height() - 150)  # Approximate header/footer height

            # Calculate the initial scale to fill as much space as possible
            scale_x = available_width / self.image.width()
            scale_y = available_height / self.image.height()

            # Use the scale that fills the most space without exceeding bounds
            base_scale = min(scale_x, scale_y)

            # Apply zoom factor on top of base scale
            final_scale = base_scale * self.zoom_factor

            # Calculate target dimensions
            target_width = int(self.image.width() * final_scale)
            target_height = int(self.image.height() * final_scale)

            # Ensure minimum size
            target_width = max(50, target_width)
            target_height = max(50, target_height)

            # Scale the image
            scaled_image = self.image.scaled(
                target_width,
                target_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            self.image_label.setPixmap(QPixmap.fromImage(scaled_image))

        except Exception as e:
            logger.exception("Error updating image display: %s", e)
            # Try to at least show something
            if self.image and not self.image.isNull():
                self.image_label.setPixmap(QPixmap.fromImage(self.image))


class ZoomDialog(QDialog):
    """A frameless dialog for showing zoomed images."""

    def __init__(self, pixmap: QPixmap, parent: QWidget | None = None) -> None:
        """Initialize the zoom dialog with a pixmap."""
        super().__init__(parent)

        # Apply material theme dialog class
        self.setProperty("class", "ImageViewerDialog")

        self.pixmap = pixmap

        # Set frameless window with translucent background
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Size to match pixmap
        if pixmap and not pixmap.isNull():
            self.resize(pixmap.size())

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
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
