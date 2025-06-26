"""File operations component for the GUI.

This module handles file and directory selection operations, extracted from
the main GUI to reduce complexity and improve modularity.
"""

from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QFileDialog, QWidget

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class FileOperations:
    """Handles file and directory selection operations for the main window."""

    def __init__(self, parent: QWidget) -> None:
        """Initialize the file operations handler.

        Args:
            parent: The parent widget for dialogs
        """
        self.parent = parent

    def select_input_directory(self) -> Optional[Path]:
        """Open a directory dialog to select the input image folder.

        Returns:
            Selected directory path or None if cancelled
        """
        LOGGER.debug("Opening directory selection dialog")
        dir_path = QFileDialog.getExistingDirectory(
            self.parent, "Select Input Image Folder"
        )

        if dir_path:
            LOGGER.debug("Input directory selected: %s", dir_path)
            return Path(dir_path)

        LOGGER.debug("Directory selection cancelled")
        return None

    def select_output_file(self) -> Optional[Path]:
        """Open a file dialog to select the output MP4 file path.

        Returns:
            Selected file path or None if cancelled
        """
        LOGGER.debug("Opening output file selection dialog")
        file_path, _ = QFileDialog.getSaveFileName(
            self.parent, "Save Output Video", "", "MP4 Files (*.mp4)"
        )

        if file_path:
            LOGGER.debug("Output file selected: %s", file_path)
            return Path(file_path)

        LOGGER.debug("Output file selection cancelled")
        return None

    def handle_sorter_directory(self, directory: Path) -> Path:
        """Process a directory from a sorter tab.

        Args:
            directory: The directory path from the sorter

        Returns:
            The validated directory path
        """
        LOGGER.debug("Processing sorter directory: %s", directory)

        # Validate the directory exists
        if not directory.exists():
            LOGGER.warning("Sorter directory does not exist: %s", directory)
            raise ValueError(f"Directory does not exist: {directory}")

        if not directory.is_dir():
            LOGGER.warning("Sorter path is not a directory: %s", directory)
            raise ValueError(f"Path is not a directory: {directory}")

        return directory
