"""File and directory picker functionality for MainWindow."""

from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import QFileDialog

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class FilePickerManager:
    """Manages file and directory selection dialogs."""

    def pick_input_directory(self, main_window: Any) -> None:
        """Open a directory dialog to select the input image folder.

        Args:
            main_window: The MainWindow instance
        """
        LOGGER.debug("Entering pick_input_directory...")
        dir_path = QFileDialog.getExistingDirectory(main_window, "Select Input Image Folder")
        if dir_path:
            # Validate the selected directory
            validation_result = self._validate_input_directory(dir_path)
            if not validation_result["valid"]:
                from PyQt6.QtWidgets import QMessageBox

                QMessageBox.warning(main_window, "Invalid Directory", validation_result["message"])
                return

            LOGGER.debug("Input directory selected: %s", dir_path)
            main_window.in_dir = Path(dir_path)
            main_window.main_tab.in_dir_edit.setText(dir_path)
            main_window._update_start_button_state()
            LOGGER.debug("Emitting request_previews_update from pick_input_directory")
            main_window.request_previews_update.emit()

    def pick_output_file(self, main_window: Any) -> None:
        """Open a file dialog to select the output MP4 file path.

        Args:
            main_window: The MainWindow instance
        """
        LOGGER.debug("Entering pick_output_file...")
        file_path, _ = QFileDialog.getSaveFileName(main_window, "Save Output Video", "", "MP4 Files (*.mp4)")
        if file_path:
            # Validate the selected output file
            validation_result = self._validate_output_file(file_path)
            if not validation_result["valid"]:
                from PyQt6.QtWidgets import QMessageBox

                QMessageBox.warning(main_window, "Invalid Output File", validation_result["message"])
                return

            # Show warning if file exists
            if "overwritten" in validation_result["message"]:
                from PyQt6.QtWidgets import QMessageBox

                reply = QMessageBox.question(
                    main_window,
                    "File Exists",
                    validation_result["message"] + "\n\nDo you want to continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

            LOGGER.debug("Output file selected: %s", file_path)
            main_window.out_file_path = Path(file_path)
            main_window.main_tab.out_file_edit.setText(file_path)
            main_window._update_start_button_state()

    def set_input_dir_from_sorter(self, main_window: Any, directory: Path) -> None:
        """Sets the input directory from a sorter tab.

        Args:
            main_window: The MainWindow instance
            directory: The directory path selected from sorter
        """
        LOGGER.debug("Entering set_input_dir_from_sorter... directory=%s", directory)
        # Use the regular set_in_dir method to ensure proper state updates and settings saving
        main_window.set_in_dir(directory)
        main_window.main_tab.in_dir_edit.setText(str(directory))
        main_window._update_start_button_state()
        main_window.request_previews_update.emit()

    def _validate_input_directory(self, dir_path: str) -> dict[str, Any]:
        """Validate the selected input directory.

        Args:
            dir_path: Path to the directory to validate

        Returns:
            Dictionary with 'valid' boolean and 'message' string
        """
        try:
            path_obj = Path(dir_path)

            # Check if path exists
            if not path_obj.exists():
                return {"valid": False, "message": "Selected directory does not exist."}

            # Check if it's actually a directory
            if not path_obj.is_dir():
                return {"valid": False, "message": "Please select a directory, not a file."}

            # Check if directory is readable
            if not path_obj.is_dir():
                return {"valid": False, "message": "Directory is not accessible."}

            # Check if directory contains image files
            image_extensions = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif"}
            image_files = [f for f in path_obj.iterdir() if f.is_file() and f.suffix.lower() in image_extensions]

            if not image_files:
                return {
                    "valid": False,
                    "message": "Directory does not contain any supported image files (.png, .jpg, .tif, etc.).",
                }

            # Check minimum number of images for video creation
            if len(image_files) < 2:
                return {"valid": False, "message": "Directory must contain at least 2 images to create a video."}

            return {"valid": True, "message": f"Directory contains {len(image_files)} image files."}

        except Exception as e:
            LOGGER.exception("Error validating input directory: %s", e)
            return {"valid": False, "message": f"Error accessing directory: {e}"}

    def _validate_output_file(self, file_path: str) -> dict[str, Any]:
        """Validate the selected output file path.

        Args:
            file_path: Path to the output file to validate

        Returns:
            Dictionary with 'valid' boolean and 'message' string
        """
        try:
            path_obj = Path(file_path)

            # Check if parent directory exists and is writable
            parent_dir = path_obj.parent
            if not parent_dir.exists():
                return {"valid": False, "message": "Output directory does not exist."}

            if not parent_dir.is_dir():
                return {"valid": False, "message": "Invalid output directory."}

            # Check if we can write to the parent directory
            try:
                test_file = parent_dir / "test_write_access.tmp"
                test_file.touch()
                test_file.unlink()
            except Exception:
                return {"valid": False, "message": "Cannot write to output directory. Check permissions."}

            # Check file extension
            if not file_path.lower().endswith(".mp4"):
                return {"valid": False, "message": "Output file must have .mp4 extension."}

            # Check if file already exists and warn
            if path_obj.exists():
                return {"valid": True, "message": "Warning: Output file already exists and will be overwritten."}

            return {"valid": True, "message": "Output path is valid."}

        except Exception as e:
            LOGGER.exception("Error validating output file: %s", e)
            return {"valid": False, "message": f"Error validating output path: {e}"}
