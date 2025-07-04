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
        self.connections: list[tuple[QObject, str, Any]] = []
        self.worker_connections: list[tuple[QObject, str, Any]] = []

    def setup_main_window_connections(self, main_window: Any) -> None:
        """Set up all signal connections for the main window.

        Args:
            main_window: The MainWindow instance
        """
        LOGGER.debug("Setting up main window signal connections")

        # Clear any existing connections first
        self.disconnect_all_main_window_connections()

        # Connect preview update signal
        self._make_connection(
            main_window.request_previews_update,
            main_window._update_previews,
            "request_previews_update to _update_previews",
        )

        # Connect tab widget signals
        self._make_connection(
            main_window.tab_widget.currentChanged, main_window._on_tab_changed, "tab widget currentChanged"
        )

        # Connect view model signals
        self._make_connection(
            main_window.main_view_model.status_updated,
            main_window.status_bar.showMessage,
            "main view model status updates",
        )
        self._make_connection(
            main_window.main_view_model.processing_vm.status_updated,
            main_window.main_view_model.update_global_status_from_child,
            "processing view model status updates",
        )

        # Connect sorter tab signals (only if tabs exist - they may be lazily loaded)
        if hasattr(main_window, "file_sorter_tab") and main_window.file_sorter_tab is not None:
            self._make_connection(
                main_window.file_sorter_tab.directory_selected,
                main_window._set_in_dir_from_sorter,
                "file sorter tab directory selected",
            )
        if hasattr(main_window, "date_sorter_tab") and main_window.date_sorter_tab is not None:
            self._make_connection(
                main_window.date_sorter_tab.directory_selected,
                main_window._set_in_dir_from_sorter,
                "date sorter tab directory selected",
            )

        # Connect encoder combo signal
        self._make_connection(
            main_window.main_tab.encoder_combo.currentTextChanged,
            lambda encoder_type: main_window._update_rife_ui_elements(),
            "encoder combo signal",
        )

        # Connect processing started signal
        try:
            self._make_connection(
                main_window.main_tab.processing_started, main_window._handle_processing, "processing started signal"
            )
        except Exception as e:
            LOGGER.exception("Error connecting processing_started signal: %s", e)

        # Connect model combo
        if hasattr(main_window, "_connect_model_combo"):
            main_window._connect_model_combo()
            LOGGER.debug("Connected model combo")

        LOGGER.info("Set up %d main window signal connections", len(self.connections))

    def setup_worker_connections(self, main_window: Any, worker: Any) -> None:
        """Set up connections for a VFI worker.

        Args:
            main_window: The MainWindow instance
            worker: The VfiWorker instance
        """
        LOGGER.debug("Setting up VFI worker connections")

        # Clear any existing worker connections first
        self.disconnect_all_worker_connections()

        # Connect worker signals with tracking
        self._make_worker_connection(worker.progress, main_window._on_processing_progress, "worker progress")
        self._make_worker_connection(worker.finished, main_window._on_processing_finished, "worker finished")
        self._make_worker_connection(worker.error, main_window._on_processing_error, "worker error")

        LOGGER.info("Set up %d worker signal connections", len(self.worker_connections))

    def _make_connection(self, signal: Any, slot: Any, description: str) -> None:
        """Make a tracked signal connection.

        Args:
            signal: The signal to connect
            slot: The slot to connect to
            description: Description for logging
        """
        try:
            signal.connect(slot)
            # Store connection info for cleanup
            self.connections.append((signal, slot, description))
            LOGGER.debug("Connected %s", description)
        except Exception as e:
            LOGGER.exception("Failed to connect %s: %s", description, e)

    def _make_worker_connection(self, signal: Any, slot: Any, description: str) -> None:
        """Make a tracked worker signal connection.

        Args:
            signal: The signal to connect
            slot: The slot to connect to
            description: Description for logging
        """
        try:
            signal.connect(slot)
            # Store connection info for cleanup
            self.worker_connections.append((signal, slot, description))
            LOGGER.debug("Connected %s", description)
        except Exception as e:
            LOGGER.exception("Failed to connect %s: %s", description, e)

    def disconnect_all_main_window_connections(self) -> None:
        """Disconnect all main window signal connections."""
        disconnected_count = 0
        for signal, slot, description in self.connections:
            try:
                # Disconnect all connections from this signal to avoid signature issues
                signal.disconnect()
                disconnected_count += 1
                LOGGER.debug("Disconnected %s", description)
            except (TypeError, RuntimeError) as e:
                # Signal was already disconnected or object was deleted
                LOGGER.debug("Could not disconnect %s: %s", description, e)
            except Exception as e:
                LOGGER.exception("Error disconnecting %s: %s", description, e)

        self.connections.clear()
        if disconnected_count > 0:
            LOGGER.info("Disconnected %d main window signal connections", disconnected_count)

    def disconnect_all_worker_connections(self) -> None:
        """Disconnect all worker signal connections."""
        disconnected_count = 0
        for signal, slot, description in self.worker_connections:
            try:
                # Disconnect all connections from this signal to avoid signature issues
                signal.disconnect()
                disconnected_count += 1
                LOGGER.debug("Disconnected %s", description)
            except (TypeError, RuntimeError) as e:
                # Signal was already disconnected or object was deleted
                LOGGER.debug("Could not disconnect %s: %s", description, e)
            except Exception as e:
                LOGGER.exception("Error disconnecting %s: %s", description, e)

        self.worker_connections.clear()
        if disconnected_count > 0:
            LOGGER.info("Disconnected %d worker signal connections", disconnected_count)

    def disconnect_all_connections(self) -> None:
        """Disconnect all tracked signal connections."""
        self.disconnect_all_main_window_connections()
        self.disconnect_all_worker_connections()
        LOGGER.info("Disconnected all signal connections")
