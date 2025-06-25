"""File and directory picker functionality for MainWindow."""

from pathlib import Path
from typing import Any, Optional

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
        dir_path = QFileDialog.getExistingDirectory(
            main_window, "Select Input Image Folder"
        )
        if dir_path:
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
        file_path, _ = QFileDialog.getSaveFileName(
            main_window, "Save Output Video", "", "MP4 Files (*.mp4)"
        )
        if file_path:
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
