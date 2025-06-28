"""Signal connection management for the GUI application.

This module centralizes signal-slot connections to reduce coupling
and improve maintainability.
"""

from typing import Any

from PyQt6.QtCore import QObject

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class SignalBroker(QObject):
    """Manages signal connections between GUI components."""

    def __init__(self) -> None:
        """Initialize the signal broker."""
        super().__init__()

    def setup_main_window_connections(self, main_window: Any) -> None:
        """Set up all signal connections for the main window.

        Args:
            main_window: The MainWindow instance
        """
        LOGGER.debug("Setting up main window signal connections")

        # Connect preview update signal
        main_window.request_previews_update.connect(main_window._update_previews)
        LOGGER.debug("Connected request_previews_update to _update_previews")

        # Connect tab widget signals
        main_window.tab_widget.currentChanged.connect(main_window._on_tab_changed)
        LOGGER.debug("Connected tab widget currentChanged")

        # Connect view model signals
        main_window.main_view_model.status_updated.connect(main_window.status_bar.showMessage)
        main_window.main_view_model.processing_vm.status_updated.connect(
            main_window.main_view_model.update_global_status_from_child
        )
        LOGGER.debug("Connected view model status updates")

        # Connect sorter tab signals (only if tabs exist - they may be lazily loaded)
        if hasattr(main_window, "file_sorter_tab") and main_window.file_sorter_tab is not None:
            main_window.file_sorter_tab.directory_selected.connect(main_window._set_in_dir_from_sorter)
        if hasattr(main_window, "date_sorter_tab") and main_window.date_sorter_tab is not None:
            main_window.date_sorter_tab.directory_selected.connect(main_window._set_in_dir_from_sorter)
        LOGGER.debug("Connected available sorter tab signals")

        # Connect encoder combo signal
        main_window.main_tab.encoder_combo.currentTextChanged.connect(
            lambda encoder_type: main_window._update_rife_ui_elements()
        )
        LOGGER.debug("Connected encoder combo signal")

        # Connect processing started signal
        try:
            main_window.main_tab.processing_started.connect(main_window._handle_processing)
            LOGGER.info("Successfully connected MainTab.processing_started signal")
        except Exception as e:
            LOGGER.exception("Error connecting processing_started signal: %s", e)

        # Connect model combo
        if hasattr(main_window, "_connect_model_combo"):
            main_window._connect_model_combo()
            LOGGER.debug("Connected model combo")

    def setup_worker_connections(self, main_window: Any, worker: Any) -> None:
        """Set up connections for a VFI worker.

        Args:
            main_window: The MainWindow instance
            worker: The VfiWorker instance
        """
        LOGGER.debug("Setting up VFI worker connections")

        worker.progress.connect(main_window._on_processing_progress)
        worker.finished.connect(main_window._on_processing_finished)
        worker.error.connect(main_window._on_processing_error)

        LOGGER.debug("Connected all VFI worker signals")
