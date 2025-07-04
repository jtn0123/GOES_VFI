"""ViewModel for the File Sorter tab in the GOES VFI application.

This module defines the FileSorterViewModel class, which manages the state and
presentation logic for the File Sorter feature. It interacts with the FileSorter
model and exposes data and commands to the GUI view layer.
"""

import os  # Added for basic path validation
import threading

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QFileDialog

from goesvfi.utils import log

from .sorter import FileSorter  # Import the FileSorter model

LOGGER = log.get_logger(__name__)


class FileSorterViewModel(QObject):
    """ViewModel for the File Sorter GUI tab.

    This class manages the state and presentation logic for the File Sorter feature,
    acting as an intermediary between the FileSorter model and the GUI view.
    It exposes properties representing the current state and provides command methods
    for user actions such as selecting directories and starting/canceling the sorting process.
    """

    # Qt signals
    source_directory_changed = pyqtSignal(str)
    destination_directory_changed = pyqtSignal(str)
    status_message_changed = pyqtSignal(str)

    def __init__(self, sorter_model: FileSorter) -> None:
        """Initializes the FileSorterViewModel with default state.

        Args:
                    sorter_model (FileSorter): The FileSorter model instance to use for file operations.

        Attributes:
                    source_directory (Optional[str]): The currently selected source directory for sorting.
        destination_directory(
                        Optional[str]
                    ): The currently selected destination directory for sorted files.
                    is_sorting (bool): Whether a sorting operation is currently in progress.
                    progress_percentage (float): The current progress of the sorting operation (0-100).
                    status_message (str): A message describing the current status for display in the UI.
                    _cancel_requested (bool): Internal flag indicating if a cancel operation has been requested.
        """
        super().__init__()
        self.sorter_model = sorter_model  # Store the FileSorter model instance
        self.file_sorter = sorter_model  # Alias for compatibility
        self._source_directory: str | None = None
        self._destination_directory: str | None = None
        self.is_sorting: bool = False
        self.progress_percentage: float = 0.0
        self._status_message: str = "Ready"
        self._cancel_requested: bool = False  # Flag for cancellation

        # New attributes for UI state
        self._dry_run_enabled: bool = False
        self._duplicate_mode: str = "copy"  # Assuming a default mode like "copy"
        self._completion_message: str = ""
        self._error_message: str = ""
        self._input_error_message: str = ""
        self._show_completion_message: bool = False
        self._show_error_message: bool = False
        self._show_input_error_message: bool = False

    @property
    def source_directory(self) -> str | None:
        """Get the source directory."""
        return self._source_directory

    @source_directory.setter
    def source_directory(self, value: str | None) -> None:
        """Set the source directory."""
        if self._source_directory != value:
            self._source_directory = value
            self.source_directory_changed.emit(value or "")

    @property
    def destination_directory(self) -> str | None:
        """Get the destination directory."""
        return self._destination_directory

    @destination_directory.setter
    def destination_directory(self, value: str | None) -> None:
        """Set the destination directory."""
        if self._destination_directory != value:
            self._destination_directory = value
            self.destination_directory_changed.emit(value or "")

    @property
    def status_message(self) -> str:
        """Get the status message."""
        return self._status_message

    @status_message.setter
    def status_message(self, value: str) -> None:
        """Set the status message."""
        old_value = self._status_message
        self._status_message = value
        if old_value != value:
            self.status_message_changed.emit(value)

    @property
    def can_start_sorting(self) -> bool:
        """Whether the sorting process can be started.

        Returns:
            bool: True if both source and destination directories are set and valid,
                  and no sorting is currently in progress; False otherwise.
        """
        # Basic validation: ensure directories are set and exist
        return (
            self.source_directory is not None
            and os.path.isdir(self.source_directory)
            and self.destination_directory is not None
            and os.path.isdir(self.destination_directory)
            and not self.is_sorting
        )

    @property
    def dry_run_enabled(self) -> bool:
        return self._dry_run_enabled

    @dry_run_enabled.setter
    def dry_run_enabled(self, value: bool) -> None:
        self._dry_run_enabled = value

    @property
    def duplicate_mode(self) -> str:
        return self._duplicate_mode

    @duplicate_mode.setter
    def duplicate_mode(self, value: str) -> None:
        self._duplicate_mode = value

    @property
    def completion_message(self) -> str:
        return self._completion_message

    @completion_message.setter
    def completion_message(self, value: str) -> None:
        self._completion_message = value

    @property
    def error_message(self) -> str:
        return self._error_message

    @error_message.setter
    def error_message(self, value: str) -> None:
        self._error_message = value

    @property
    def input_error_message(self) -> str:
        return self._input_error_message

    @input_error_message.setter
    def input_error_message(self, value: str) -> None:
        self._input_error_message = value

    @property
    def show_completion_message(self) -> bool:
        return self._show_completion_message

    @show_completion_message.setter
    def show_completion_message(self, value: bool) -> None:
        self._show_completion_message = value

    @property
    def show_error_message(self) -> bool:
        return self._show_error_message

    @show_error_message.setter
    def show_error_message(self, value: bool) -> None:
        self._show_error_message = value

    @property
    def show_input_error_message(self) -> bool:
        return self._show_input_error_message

    @show_input_error_message.setter
    def show_input_error_message(self, value: bool) -> None:
        self._show_input_error_message = value

    def select_source_directory(self) -> None:
        """Command to select the source directory.

        This method should be triggered by the UI when the user wants to choose
        a source directory for sorting. The actual implementation should open a
        directory selection dialog and update `source_directory` accordingly.

        Side Effects:
            Updates `source_directory` and `status_message`.
            Notifies observers if implemented.
        """
        LOGGER.info("Command: Select Source Directory")
        try:
            directory = QFileDialog.getExistingDirectory(None, "Select Source Directory")
            if directory:  # Only update if a directory was selected (not cancelled)
                self.source_directory = directory
                self.status_message = f"Source directory set to: {directory}"
        except Exception as e:
            LOGGER.exception("Error selecting source directory: %s", e)
            # Handle error gracefully without raising

    def select_destination_directory(self) -> None:
        """Command to select the destination directory.

        This method should be triggered by the UI when the user wants to choose
        a destination directory for sorted files. The actual implementation should
        open a directory selection dialog and update `destination_directory` accordingly.

        Side Effects:
            Updates `destination_directory` and `status_message`.
            Notifies observers if implemented.
        """
        LOGGER.info("Command: Select Destination Directory")
        try:
            directory = QFileDialog.getExistingDirectory(None, "Select Destination Directory")
            if directory:  # Only update if a directory was selected (not cancelled)
                self.destination_directory = directory
                self.status_message = f"Destination directory set to: {directory}"
        except Exception as e:
            LOGGER.exception("Error selecting destination directory: %s", e)
            # Handle error gracefully without raising

    def start_sorting(self) -> None:
        """Command to start the sorting process.

        Initiates the file sorting operation in a separate thread if the
        preconditions are met (valid source/destination directories and not already sorting).

        Side Effects:
            Updates `is_sorting`, `status_message`, `progress_percentage`, and `_cancel_requested`.
            Starts a new thread for the sorting operation.
            Notifies observers if implemented.

        If preconditions are not met, updates `status_message` with an error.
        """
        if self.can_start_sorting:
            LOGGER.info("Command: Start Sorting from %s to %s", self.source_directory, self.destination_directory)
            self.is_sorting = True
            self.status_message = "Sorting started..."
            self.progress_percentage = 0.0
            self._cancel_requested = False  # Reset cancellation flag
            # Notify observers about state change (is_sorting, status_message, progress_percentage)
            # Assuming an observer pattern is in place, call the update method here.
            # Example: self._notify_observers()

            # Start the sorting process in a new thread
            sorting_thread = threading.Thread(target=self._sort_worker)
            sorting_thread.start()
        else:
            LOGGER.error(
                "Cannot start sorting: Source or destination directory not set/invalid, or sorting already in progress."
            )
            self.status_message = "Cannot start sorting."
            # Notify observers about status change

    def cancel_sorting(self) -> None:
        """Command to cancel the ongoing sorting process.

        If a sorting operation is in progress, sets the cancellation flag and updates
        the status message. The sorting thread should periodically check this flag and
        terminate if set.

        Side Effects:
            Updates `_cancel_requested` and `status_message`.
            Notifies observers if implemented.
        """
        if self.is_sorting:
            LOGGER.info("Command: Cancel Sorting requested.")
            self._cancel_requested = True
            self.status_message = "Cancellation requested..."
            # Notify observers about status change
        else:
            LOGGER.info("No sorting process to cancel.")

    def _sort_worker(self) -> None:
        """Worker function executed in a separate thread to perform the sorting."""
        try:
            # Ensure source and destination directories are not None before calling sort_files
            assert self.source_directory is not None
            assert self.destination_directory is not None

            # Call the sorter model's sort method
            # Assuming sorter_model.sort_files now accepts source, destination, progress_callback, and should_cancel
            self.sorter_model.sort_files(
                source=self.source_directory,
                destination=self.destination_directory,
                progress_callback=self._update_progress,
                should_cancel=lambda: self._cancel_requested,
            )
            self.status_message = "Sorting complete."
        except Exception as e:
            self.status_message = f"Error during sorting: {e}"
            LOGGER.exception("Error during sorting")
        finally:
            self.is_sorting = False
            self.progress_percentage = 0.0  # Reset progress on completion or error
            self._cancel_requested = False  # Reset cancellation flag
            # Notify observers about state change (is_sorting, status_message, progress_percentage)
            # Example: self._notify_observers()
            LOGGER.info("Sorting worker finished.")

    def _update_progress(self, current: int, total: int) -> None:
        """Callback function to update progress from the sorter model."""
        if total > 0:
            self.progress_percentage = (current / total) * 100
            self.status_message = f"Sorting: {current}/{total} files processed."
        else:
            self.progress_percentage = 0.0
            self.status_message = "Sorting: No files to process."
        # Notify observers about progress and status change
        # Example: self._notify_observers()

    # Placeholder for observer notification - replace with actual implementation
    # def _notify_observers(self):
    #     """Notifies registered observers of state changes."""
    #     pass # Implement observer notification logic here
