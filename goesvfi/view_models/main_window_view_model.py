"""Main window ViewModel for the GOES VFI application.

This module defines the MainWindowViewModel class, which coordinates child ViewModels
and manages global application state for the main application window.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, pyqtSignal

from goesvfi.date_sorter.sorter import DateSorter
from goesvfi.date_sorter.view_model import DateSorterViewModel
from goesvfi.file_sorter.sorter import FileSorter
from goesvfi.file_sorter.view_model import FileSorterViewModel
from goesvfi.view_models.processing_view_model import ProcessingViewModel
from goesvfi.gui_components.preview_manager import PreviewManager
from goesvfi.gui_components.processing_manager import ProcessingManager

# Import Models

# Import Child ViewModels

# Import other core components if needed for ProcessingViewModel later
# from goesvfi.pipeline import ...

LOGGER = logging.getLogger(__name__)


class MainWindowViewModel(QObject):
    """
    ViewModel for the main application window (MainWindow).

    This class coordinates the child ViewModels for each main tab (File Sorter,)
    Date Sorter, Processing) and manages global application state such as the
    current status message and active tab index. It provides signals and methods
    for global actions and state changes, serving as the central ViewModel for the GUI.
    """

    # Signals for global state changes
    status_updated = pyqtSignal(str)
    active_tab_changed = pyqtSignal(int)  # Emits the index of the new active tab

    def __init__(
        self,
        file_sorter_model: FileSorter,
        date_sorter_model: DateSorter,
        preview_manager: PreviewManager,
        processing_manager: ProcessingManager,
        parent: QObject | None = None,
    ) -> None:
        """
        Initializes the MainWindowViewModel and its child ViewModels.

        Args:
            file_sorter_model: Model for the File Sorter tab.
            date_sorter_model: Model for the Date Sorter tab.
            preview_manager: PreviewManager instance used by ProcessingViewModel.
            processing_manager: ProcessingManager instance used by ProcessingViewModel.
            parent: Optional parent QObject.

        Attributes:
            pass
            file_sorter_vm (FileSorterViewModel): ViewModel for the File Sorter tab.
            date_sorter_vm (DateSorterViewModel): ViewModel for the Date Sorter tab.
            processing_vm (ProcessingViewModel): ViewModel for the Processing tab.
            _status (str): The current global status message.
            _active_tab_index (int): The index of the currently active tab.

        This constructor coordinates the instantiation of all child ViewModels and
        sets up the initial global state for the main window.
        """
        super().__init__(parent)
        LOGGER.info("MainWindowViewModel initializing...")

        # Instantiate and store child ViewModels, passing required models
        self.file_sorter_vm = FileSorterViewModel(file_sorter_model)
        LOGGER.info("FileSorterViewModel instantiated.")
        self.date_sorter_vm = DateSorterViewModel(date_sorter_model)
        LOGGER.info("DateSorterViewModel instantiated.")

        self.preview_manager = preview_manager
        self.processing_manager = processing_manager

        self.processing_vm = ProcessingViewModel(
            preview_manager=preview_manager,
            processing_manager=processing_manager,
            parent=self,
        )
        LOGGER.info("ProcessingViewModel instantiated.")

        # Initialize global state properties
        self._status: str = "Ready"
        self._active_tab_index: int = 0  # Default to the first tab

        LOGGER.info("MainWindowViewModel initialized.")

    # --- Global State Properties ---

    @property
    def status(self) -> str:
        """
        The current global status message for the application.

        Returns:
            str: The current status message.
        """
        return self._status

    @status.setter
    def status(self, value: str) -> None:
        """
        Sets the global status message and emits a signal.

        Args:
            value (str): The new status message.
        """
        if self._status != value:
            self._status = value  # pylint: disable=attribute-defined-outside-init
            self.status_updated.emit(self._status)
            LOGGER.debug("Global status updated: %s", self._status)

    @property
    def active_tab_index(self) -> int:
        """
        The index of the currently active tab in the main window.

        Returns:
            int: The index of the active tab.
        """
        return self._active_tab_index

    @active_tab_index.setter
    def active_tab_index(self, index: int) -> None:
        """
        Sets the active tab index and emits a signal.

        Args:
            index (int): The new active tab index.
        """
        if self._active_tab_index != index:
            self._active_tab_index = (
                index  # pylint: disable=attribute-defined-outside-init
            )
            self.active_tab_changed.emit(self._active_tab_index)
            LOGGER.debug("Active tab changed to index: %s", self._active_tab_index)

    # --- Global Actions ---

    def quit_application(self) -> None:
        """
        Handles the application quit action.

        This method can be called to initiate application shutdown logic,
        such as prompting the user to save work or performing cleanup.
        The actual closing is handled by the View (MainWindow).

        Side Effects:
            Logs the quit action.
        """
        LOGGER.info("Quit application action triggered.")
        # In a real application, you might prompt to save, clean up, etc.
        # For now, just log. The actual closing is handled by the View (MainWindow).
        pass  # The MainWindow's closeEvent will handle the actual closing

    def show_about_dialog(self) -> None:
        """
        Handles the action to show the About dialog.

        This method can be called to trigger the display of an About dialog.
        The actual dialog display is typically handled by the View.

        Side Effects:
            Logs the action.
        """
        LOGGER.info("Show About dialog action triggered.")
        # Logic to show the dialog would typically be handled by the View,
        # potentially triggered by a signal from here or by the View calling this method.
        # For now, just log.

    # --- Coordination Methods (Example) ---

    def update_global_status_from_child(self, message: str) -> None:
        """
        Allows child ViewModels to update the global status message.

        Args:
            message (str): The new status message to set globally.
        """
        self.status = message

    # Add more methods as needed to coordinate between ViewModels or handle global logic
