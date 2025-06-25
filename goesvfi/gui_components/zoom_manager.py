"""Zoom functionality management for preview images."""

from typing import Optional

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QApplication

from goesvfi.utils import log
from goesvfi.utils.gui_helpers import ClickableLabel, ZoomDialog

LOGGER = log.get_logger(__name__)


class ZoomManager:
    """Manages zoom dialog functionality for preview images."""

    def show_zoom(self, label: ClickableLabel, parent: Optional[object] = None) -> None:
        """Show a zoomed view of the processed image associated with the clicked label.

        Args:
            label: The clicked label containing the image
            parent: Parent widget for the dialog
        """
        LOGGER.debug(
            "Entering show_zoom for label: %s",
            label.objectName() if label else "Unknown",
        )

        # Get the full resolution processed pixmap from the label
        if not hasattr(label, "processed_image") or label.processed_image is None:
            LOGGER.warning(
                "Clicked label has no processed image attribute or it is None."
            )
            return

        if not isinstance(label.processed_image, QImage):
            LOGGER.warning(
                "Label's processed_image is not a QImage: %s",
                type(label.processed_image),
            )
            return

        full_res_processed_pixmap = QPixmap.fromImage(label.processed_image)
        if full_res_processed_pixmap.isNull():
            LOGGER.warning("Failed to create QPixmap from processed image for zoom.")
            return

        # Scale pixmap for display
        scaled_pix = self._scale_pixmap_for_display(full_res_processed_pixmap)

        if scaled_pix.isNull():
            LOGGER.error("Failed to create scaled pixmap for zoom dialog.")
            return

        LOGGER.debug("Showing ZoomDialog with pixmap size: %s", scaled_pix.size())
        dialog = ZoomDialog(scaled_pix, parent)
        dialog.exec()

    def _scale_pixmap_for_display(self, pixmap: QPixmap) -> QPixmap:
        """Scale pixmap to fit screen if needed.

        Args:
            pixmap: The pixmap to scale

        Returns:
            Scaled pixmap or original if no scaling needed
        """
        screen = QApplication.primaryScreen()
        if screen:
            # Use 90% of available screen size
            max_size = screen.availableGeometry().size() * 0.9

            # Check if scaling is needed
            if (
                pixmap.size().width() > max_size.width()
                or pixmap.size().height() > max_size.height()
            ):
                LOGGER.debug(
                    "Scaling zoom image from %s to fit %s", pixmap.size(), max_size
                )
                return pixmap.scaled(
                    max_size,
                    aspectMode=1,  # Qt.AspectRatioMode.KeepAspectRatio
                    transformMode=1,  # Qt.TransformationMode.SmoothTransformation
                )
            else:
                LOGGER.debug("Using original size for zoom image as it fits screen.")
                return pixmap
        else:
            # Fallback if screen info is not available
            LOGGER.warning(
                "Could not get screen geometry for zoom dialog scaling, using fallback size."
            )
            fallback_size = QSize(1024, 768)
            return pixmap.scaled(
                fallback_size,
                aspectMode=1,  # Qt.AspectRatioMode.KeepAspectRatio
                transformMode=1,  # Qt.TransformationMode.SmoothTransformation
            )
