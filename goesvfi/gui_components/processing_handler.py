"""Processing handler for VFI worker management."""

from typing import Any, Dict

from PyQt6.QtWidgets import QMessageBox

from goesvfi.gui_components.worker_factory import WorkerFactory
from goesvfi.pipeline.run_vfi import VfiWorker
from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class ProcessingHandler:
    """Handles VFI processing workflow."""

    def handle_processing(self, main_window: Any, args: Dict[str, Any]) -> None:
        """Handle the processing_started signal from MainTab.

        Creates and starts a VfiWorker with the provided arguments.

        Args:
            main_window: The MainWindow instance
            args: Dictionary of processing arguments from MainTab
        """
        # Check if already processing
        if getattr(main_window, "is_processing", False):
            LOGGER.warning("Processing already in progress, ignoring duplicate request")
            return

        if not args:
            LOGGER.warning("Empty args dictionary received!")
            return

        LOGGER.info("Starting video interpolation processing")
        LOGGER.debug("Processing arguments: %s", args)

        # Update UI state
        main_window.is_processing = True
        main_window._set_processing_state(True)

        # Terminate any previous worker
        self._terminate_previous_worker(main_window)

        # Create and start new worker
        if not self._create_and_start_worker(main_window, args):
            return

        # Update UI to reflect processing state
        main_window.main_view_model.processing_vm.start_processing()

    def _terminate_previous_worker(self, main_window: Any) -> None:
        """Terminate any running VFI worker.

        Args:
            main_window: The MainWindow instance
        """
        if main_window.vfi_worker and main_window.vfi_worker.isRunning():
            LOGGER.warning("Terminating previous VfiWorker thread")
            try:
                main_window.vfi_worker.terminate()
                main_window.vfi_worker.wait(1000)  # Wait up to 1 second
            except Exception as e:
                LOGGER.exception("Error terminating previous worker: %s", e)

    def _create_and_start_worker(self, main_window: Any, args: Dict[str, Any]) -> bool:
        """Create and start a new VFI worker.

        Args:
            main_window: The MainWindow instance
            args: Processing arguments

        Returns:
            True if worker was created and started successfully, False otherwise
        """
        try:
            main_window.vfi_worker = WorkerFactory.create_worker(
                args, main_window.debug_mode
            )
        except Exception as e:
            LOGGER.exception("Failed to create VfiWorker: %s", e)
            main_window.is_processing = False
            main_window._set_processing_state(False)

            # Show error message
            QMessageBox.critical(
                main_window,
                "Error",
                f"Failed to initialize processing pipeline.\n\nError: {str(e)}",
            )
            main_window.main_tab._reset_start_button()
            return False

        # Connect worker signals through SignalBroker
        main_window.signal_broker.setup_worker_connections(
            main_window, main_window.vfi_worker
        )

        # Start the worker thread
        main_window.vfi_worker.start()
        LOGGER.info("VfiWorker thread started")

        return True
