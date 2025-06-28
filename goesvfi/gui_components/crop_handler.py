"""Crop dialog handling for MainWindow."""

from pathlib import Path
from typing import Any

from PyQt6.QtCore import QRect
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QDialog, QMessageBox

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class CropHandler:
    """Handles crop dialog operations for MainWindow."""

    def on_crop_clicked(self, main_window: Any) -> None:
        """Open the crop dialog with the first image.

        Args:
            main_window: The MainWindow instance
        """
        LOGGER.debug("Entering on_crop_clicked...")

        if not main_window.in_dir or not main_window.in_dir.is_dir():
            LOGGER.debug("No input directory selected for cropping.")
            QMessageBox.warning(main_window, "Warning", "Please select an input directory first.")
            return

        image_files = self.get_sorted_image_files(main_window)
        if not image_files:
            LOGGER.debug("No images found in the input directory to crop.")
            QMessageBox.warning(
                main_window,
                "Warning",
                "No images found in the input directory to crop.",
            )
            return

        # Prepare image for dialog
        first_image_path = image_files[0]
        pixmap_for_dialog = self.prepare_image_for_crop_dialog(main_window, first_image_path)

        if not pixmap_for_dialog:
            QMessageBox.critical(
                main_window,
                "Error",
                f"Could not load or process image for cropping: {first_image_path}",
            )
            return

        # Show crop dialog
        self.show_crop_dialog(main_window, pixmap_for_dialog)

    def get_sorted_image_files(self, main_window: Any) -> list[Path]:
        """Get sorted list of image files from input directory.

        Args:
            main_window: The MainWindow instance

        Returns:
            Sorted list of image file paths
        """
        if not main_window.in_dir:
            return []
        return sorted([f for f in main_window.in_dir.iterdir() if f.suffix.lower() in {".png", ".jpg", ".jpeg"}])

    def prepare_image_for_crop_dialog(self, main_window: Any, image_path: Path) -> QPixmap | None:
        """Prepare an image for the crop dialog, applying Sanchez if enabled.

        Args:
            main_window: The MainWindow instance
            image_path: Path to the image file

        Returns:
            QPixmap ready for crop dialog, or None if preparation failed
        """
        LOGGER.debug("Preparing image for crop dialog: %s", image_path)

        try:
            pixmap_for_dialog: QPixmap | None = None
            sanchez_preview_enabled = main_window.main_tab.sanchez_false_colour_checkbox.isChecked()

            if sanchez_preview_enabled:
                # Try to get processed image from preview label
                pixmap_for_dialog = self.get_processed_preview_pixmap(main_window)

            # If Sanchez wasn't enabled or getting preview failed, load original
            if pixmap_for_dialog is None:
                LOGGER.debug("Loading original image for crop dialog")
                original_image = QImage(str(image_path))
                if not original_image.isNull():
                    pixmap_for_dialog = QPixmap.fromImage(original_image)
                else:
                    LOGGER.error("Failed to load original image for cropping: %s", image_path)

            return pixmap_for_dialog

        except Exception:
            LOGGER.exception("Error preparing image for crop dialog")
            return None

    def get_processed_preview_pixmap(self, main_window: Any) -> QPixmap | None:
        """Get the processed preview pixmap from the first frame label.

        Args:
            main_window: The MainWindow instance

        Returns:
            Processed preview pixmap or None if not available
        """
        LOGGER.debug("Attempting to get processed preview pixmap")

        if hasattr(main_window.main_tab, "first_frame_label") and main_window.main_tab.first_frame_label is not None:
            full_res_image = getattr(main_window.main_tab.first_frame_label, "processed_image", None)

            if full_res_image is not None and isinstance(full_res_image, QImage) and not full_res_image.isNull():
                LOGGER.debug("Successfully retrieved processed image from first_frame_label")
                return QPixmap.fromImage(full_res_image)

        LOGGER.warning("processed_image not found or invalid on first_frame_label")
        return None

    def show_crop_dialog(self, main_window: Any, pixmap: QPixmap) -> None:
        """Show the crop selection dialog.

        Args:
            main_window: The MainWindow instance
            pixmap: The image to crop
        """
        from goesvfi.utils.gui_helpers import CropSelectionDialog

        # Convert tuple to QRect if needed
        initial_rect = None
        if main_window.current_crop_rect:
            initial_rect = QRect(*main_window.current_crop_rect)

        dialog = CropSelectionDialog(pixmap.toImage(), initial_rect, main_window)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            crop_rect = dialog.get_selected_rect()
            if crop_rect is not None:
                main_window.current_crop_rect = (
                    crop_rect.x(),
                    crop_rect.y(),
                    crop_rect.width(),
                    crop_rect.height(),
                )
                LOGGER.info("Crop rectangle set to: %s", main_window.current_crop_rect)
                main_window._update_crop_buttons_state()
                main_window.request_previews_update.emit()

    def on_clear_crop_clicked(self, main_window: Any) -> None:
        """Clear the current crop rectangle and update previews.

        Args:
            main_window: The MainWindow instance
        """
        main_window.current_crop_rect = None
        LOGGER.info("Crop rectangle cleared.")
        main_window._update_crop_buttons_state()
        main_window.request_previews_update.emit()
