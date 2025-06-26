"""ViewModel for the Date Sorter tab in the GOES VFI application.

This module defines the DateSorterViewModel class, which manages the state and
presentation logic for the Date Sorter feature. It interacts with the DateSorter
model and exposes data and commands to the GUI view layer.
"""

import threading
from typing import Callable, Optional

from goesvfi.utils import log

from .sorter import DateSorter  # Import the DateSorter model

# Placeholder for potential observer pattern or state management
# from goesvfi.utils.observer import Observable

LOGGER = log.get_logger(__name__)


class DateSorterViewModel:
    """
    ViewModel for the Date Sorter GUI tab.

    This class manages the state and presentation logic for the Date Sorter feature,
    acting as an intermediary between the DateSorter model and the GUI view.
    It exposes properties representing the current state and provides command methods
    for user actions such as selecting directories and starting/canceling the sorting process.
    """

    def __init__(self, sorter_model: DateSorter) -> None:
        """
        Initializes the DateSorterViewModel with default state.

        Args:
                    sorter_model (DateSorter): The DateSorter model instance to use for file operations.

        Attributes:
                    _source_directory (Optional[str]): The currently selected source directory for sorting.
            _destination_directory (Optional[str]): The currently selected destination directory for sorted files.
        _is_sorting (bool): Whether a sorting operation is currently in progress.
        _progress_percentage (float): The current progress of the sorting operation (0-100).
        _status_message (str): A message describing the current status for display in the UI.
        _date_format_pattern (str): The date format pattern used for sorting files.
        _cancel_requested (bool): Internal flag indicating if a cancel operation has been requested.
            _observer (Optional[Callable[[], None]]): Optional callback for observer notification.
        """
        self.sorter_model = sorter_model  # Store the DateSorter model instance
        self._source_directory: Optional[str] = None
        self._destination_directory: Optional[str] = None
        self._is_sorting: bool = False
        self._progress_percentage: float = 0.0
        self._status_message: str = "Ready"
        self._date_format_pattern: str = "%Y/%m/%d"  # Example default
        self._cancel_requested: bool = False  # Flag for cancellation

        # Placeholder for observer notification mechanism
        self._observer: Optional[Callable[[], None]] = None

        # Properties that might be observable in a full MVVM implementation
        # self.source_directory = Observable(None)
        # self.destination_directory = Observable(None)
        # self.is_sorting = Observable(False)
        # self.progress_percentage = Observable(0.0)
        # self.status_message = Observable("Ready")
        # self.date_format_pattern = Observable("%Y/%m/%d")

    def set_observer(self, observer: Callable[[], None]) -> None:
        """Sets the observer callback to notify the View of state changes."""
        self._observer = observer  # pylint: disable=attribute-defined-outside-init

    def _notify_observer(self) -> None:
        """Notifies the registered observer of state changes."""
        if self._observer:
            self._observer()

    @property
    def source_directory(self) -> Optional[str]:
        """
        The currently selected source directory for sorting.

        Returns:
            Optional[str]: The path to the source directory, or None if not set.
        """
        return self._source_directory

    @source_directory.setter
    def source_directory(self, value: Optional[str]) -> None:
        """
        Sets the source directory for sorting.

        Args:
            value (Optional[str]): The path to the source directory.
        """
        self._source_directory = value  # pylint: disable=attribute-defined-outside-init
        # Notify observers if using Observable
        # self.source_directory.set(value)

    @property
    def destination_directory(self) -> Optional[str]:
        """
        The currently selected destination directory for sorted files.

        Returns:
            Optional[str]: The path to the destination directory, or None if not set.
        """
        return self._destination_directory

    @destination_directory.setter
    def destination_directory(self, value: Optional[str]) -> None:
        """
        Sets the destination directory for sorted files.

        Args:
            value (Optional[str]): The path to the destination directory.
        """
        self._destination_directory = value  # pylint: disable=attribute-defined-outside-init
        # Notify observers if using Observable
        # self.destination_directory.set(value)

    @property
    def is_sorting(self) -> bool:
        """
        Whether a sorting operation is currently in progress.

        Returns:
            bool: True if sorting is in progress, False otherwise.
        """
        return self._is_sorting

    @is_sorting.setter
    def is_sorting(self, value: bool) -> None:
        """
        Sets the sorting state.

        Args:
            value (bool): True if sorting is in progress, False otherwise.
        """
        self._is_sorting = value  # pylint: disable=attribute-defined-outside-init
        # Notify observers if using Observable
        # self.is_sorting.set(value)

    @property
    def progress_percentage(self) -> float:
        """
        The current progress of the sorting operation as a percentage.

        Returns:
            float: Progress percentage (0-100).
        """
        return self._progress_percentage

    @progress_percentage.setter
    def progress_percentage(self, value: float) -> None:
        """
        Sets the progress percentage of the sorting operation.

        Args:
            value (float): Progress percentage (0-100).
        """
        self._progress_percentage = value  # pylint: disable=attribute-defined-outside-init
        # Notify observers if using Observable
        # self.progress_percentage.set(value)

    @property
    def status_message(self) -> str:
        """
        The current status message for display in the UI.

        Returns:
            str: Status message describing the current state.
        """
        return self._status_message

    @status_message.setter
    def status_message(self, value: str) -> None:
        """
        Sets the status message for display in the UI.

        Args:
            value (str): The status message.
        """
        self._status_message = value  # pylint: disable=attribute-defined-outside-init
        # Notify observers if using Observable
        # self.status_message.set(value)

    @property
    def date_format_pattern(self) -> str:
        """
        The date format pattern used for sorting files.

        Returns:
            str: The date format pattern (e.g., "%Y/%m/%d").
        """
        return self._date_format_pattern

    @date_format_pattern.setter
    def date_format_pattern(self, value: str) -> None:
        """
        Sets the date format pattern for sorting files.

        Args:
            value (str): The date format pattern (e.g., "%Y/%m/%d").
        """
        self._date_format_pattern = value  # pylint: disable=attribute-defined-outside-init
        # Notify observers if using Observable
        # self.date_format_pattern.set(value)

    @property
    def can_start_sorting(self) -> bool:
        """
        Whether the sorting process can be started.

        Returns:
            bool: True if both source and destination directories are set and valid,
            and no sorting is currently in progress; False otherwise.
        """
        return self.source_directory is not None and self.destination_directory is not None and not self.is_sorting

    def select_source_directory(self) -> None:
        """
        Command to select the source directory.

        This method should be triggered by the UI when the user wants to choose
        a source directory for sorting. The actual implementation should open a
        directory selection dialog and update `source_directory` accordingly.

        Side Effects:


            Updates `source_directory`.
            Notifies observers if implemented.

        Note:


            This is a placeholder implementation for testing purposes.
        """
        # This method will typically trigger a file dialog in the View
        # and the View will update the source_directory property.
        LOGGER.info("Action: Select Source Directory (Placeholder)")
        # Example: self.source_directory = "/path/to/selected/source"
        # self._notify_observer()

    def select_destination_directory(self) -> None:
        """
        Command to select the destination directory.

        This method should be triggered by the UI when the user wants to choose
        a destination directory for sorted files. The actual implementation should
        open a directory selection dialog and update `destination_directory` accordingly.

        Side Effects:


            Updates `destination_directory`.
            Notifies observers if implemented.

        Note:


            This is a placeholder implementation for testing purposes.
        """
        # This method will typically trigger a file dialog in the View
        # and the View will update the destination_directory property.
        LOGGER.info("Action: Select Destination Directory (Placeholder)")
        # Example: self.destination_directory = "/path/to/selected/destination"
        # self._notify_observer()

    def start_sorting(self) -> None:
        """
        Command to start the sorting process.

        Initiates the file sorting operation in a separate thread if the
        preconditions are met (valid source/destination directories and not already sorting).

        Side Effects:


            Updates `is_sorting`, `status_message`, `progress_percentage`, and `_cancel_requested`.
            Starts a new thread for the sorting operation.
            Notifies observers if implemented.

        If preconditions are not met, this method does nothing.
        """
        if self.can_start_sorting:
            self._cancel_requested = False  # Reset cancellation flag  # pylint: disable=attribute-defined-outside-init
            self.is_sorting = True
            self.status_message = "Sorting..."
            self.progress_percentage = 0.0
            self._notify_observer()  # Notify view of state change

            # Run the sorting in a separate thread
            self._sort_thread = threading.Thread(
                target=self._sort_worker
            )  # pylint: disable=attribute-defined-outside-init
            self._sort_thread.start()

    def _sort_worker(self) -> None:
        """Worker function for the sorting thread."""
        try:
            # Ensure source and destination directories are not None before calling sort_files
            assert self.source_directory is not None
            assert self.destination_directory is not None

            self.sorter_model.sort_files(
                source=self.source_directory,
                destination=self.destination_directory,
                date_format=self.date_format_pattern,
                progress_callback=self._update_progress,
                should_cancel=lambda: self._cancel_requested,
            )
            self.status_message = "Sorting complete!"
        except FileNotFoundError as e:
            self.status_message = f"Error: {e}"
        except Exception as e:
            self.status_message = f"An error occurred: {e}"
        finally:
            self.is_sorting = False
            self.progress_percentage = 100.0  # Ensure progress is 100% on completion/error
            self._notify_observer()  # Notify view of state change

    def _update_progress(self, current: int, total: int) -> None:
        """Callback function to update sorting progress."""
        if total > 0:
            self.progress_percentage = (current / total) * 100.0
            self.status_message = f"Sorting: {current}/{total} files processed"
        else:
            self.progress_percentage = 0.0
            self.status_message = "Sorting: Initializing..."
        self._notify_observer()  # Notify view of progress update

    def cancel_sorting(self) -> None:
        """
        Command to cancel the ongoing sorting process.

        If a sorting operation is in progress, sets the cancellation flag and updates
        the status message. The sorting thread should periodically check this flag and
        terminate if set.

        Side Effects:


            Updates `_cancel_requested` and `status_message`.
            Notifies observers if implemented.
        """
        if self.is_sorting:
            self._cancel_requested = True  # pylint: disable=attribute-defined-outside-init
            self.status_message = "Cancellation requested..."
            self._notify_observer()  # Notify view of state change
