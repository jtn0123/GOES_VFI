"""Processing management functionality for the main GUI window."""

from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from goesvfi.pipeline.run_vfi import VfiWorker
from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)


class ProcessingManager(QObject):
    """Manages video processing functionality for the main window."""

    # Signals
    processing_started = pyqtSignal()
    processing_progress = pyqtSignal(int, int, float)  # current, total, eta
    processing_finished = pyqtSignal(str)  # output_path
    processing_error = pyqtSignal(str)  # error_message
    processing_state_changed = pyqtSignal(bool)  # is_processing

    def __init__(self) -> None:
        """Initialize the processing manager."""
        super().__init__()
        self.worker_thread: QThread | None = None
        self.worker: VfiWorker | None = None
        self.is_processing = False
        self.current_output_path: Path | None = None

    def start_processing(self, args: dict[str, Any]) -> bool:
        """Start video processing with the given arguments.

        Args:
            args: Dictionary containing all processing parameters

        Returns:
            True if processing started successfully, False otherwise
        """
        if self.is_processing:
            LOGGER.warning("Processing already in progress")
            return False

        try:
            # Validate required arguments
            required_keys = ["input_dir", "output_file", "model_location"]
            for key in required_keys:
                if key not in args:
                    msg = f"Missing required argument: {key}"
                    raise ValueError(msg)

            # Store output path
            self.current_output_path = Path(args["output_file"])

            # Create worker thread
            self.worker_thread = QThread()
            self.worker = VfiWorker(**args)
            self.worker.moveToThread(self.worker_thread)

            # Connect signals
            self.worker_thread.started.connect(self.worker.run)
            self.worker.progress.connect(self._handle_progress)
            self.worker.finished.connect(self._handle_finished)
            self.worker.error.connect(self._handle_error)

            # Connect cleanup
            self.worker.finished.connect(self.worker_thread.quit)
            self.worker.error.connect(self.worker_thread.quit)
            self.worker_thread.finished.connect(self._cleanup_thread)

            # Update state
            self.is_processing = True
            self.processing_state_changed.emit(True)
            self.processing_started.emit()

            # Start processing
            self.worker_thread.start()

            LOGGER.info("Processing started successfully")
            return True

        except Exception as e:
            LOGGER.exception("Failed to start processing: %s", e)
            self.processing_error.emit(str(e))
            self.is_processing = False
            self.processing_state_changed.emit(False)
            return False

    def stop_processing(self) -> None:
        """Stop the current processing operation gracefully."""
        if not self.is_processing:
            LOGGER.debug("No processing to stop")
            return

        LOGGER.info("Stopping processing...")

        if self.worker:
            # Request graceful interruption first
            LOGGER.debug("Requesting worker interruption")
            if hasattr(self.worker, "requestInterruption"):
                self.worker.requestInterruption()
            elif hasattr(self.worker, "stop"):
                self.worker.stop()

        if self.worker_thread and self.worker_thread.isRunning():
            # Request thread interruption
            self.worker_thread.requestInterruption()

            # Give the thread time to finish gracefully with progressive timeouts
            if not self.worker_thread.wait(2000):  # First try 2 seconds
                LOGGER.warning("Thread did not stop within 2 seconds, trying longer timeout...")
                if not self.worker_thread.wait(8000):  # Then try 8 more seconds (10 total)
                    LOGGER.error("Thread did not finish gracefully after 10 seconds")
                    # Only terminate as absolute last resort
                    LOGGER.critical("Force terminating worker thread - this may cause data corruption")
                    self.worker_thread.terminate()
                    if not self.worker_thread.wait(2000):
                        LOGGER.critical("Thread termination failed - potential resource leak")
                else:
                    LOGGER.info("Thread stopped gracefully after extended timeout")
            else:
                LOGGER.info("Thread stopped gracefully")

        self._cleanup_thread()

    def _handle_progress(self, current: int, total: int, eta: float) -> None:
        """Handle progress updates from the worker.

        Args:
            current: Current frame number
            total: Total number of frames
            eta: Estimated time remaining in seconds
        """
        self.processing_progress.emit(current, total, eta)

    def _handle_finished(self, output_path: str) -> None:
        """Handle successful completion of processing.

        Args:
            output_path: Path to the output file
        """
        LOGGER.info("Processing completed: %s", output_path)
        self.processing_finished.emit(output_path)
        self.is_processing = False
        self.processing_state_changed.emit(False)

    def _handle_error(self, error_message: str) -> None:
        """Handle processing errors.

        Args:
            error_message: The error message to display
        """
        LOGGER.error("Processing error: %s", error_message)
        self.processing_error.emit(error_message)
        self.is_processing = False
        self.processing_state_changed.emit(False)

    def _cleanup_thread(self) -> None:
        """Clean up the worker thread and worker safely."""
        # Disconnect signals first to prevent any late emissions
        if self.worker:
            try:
                self.worker.progress.disconnect()
                self.worker.finished.disconnect()
                self.worker.error.disconnect()
            except (TypeError, RuntimeError):
                pass  # Signals already disconnected or object deleted

            # Schedule for deletion in next event loop iteration
            self.worker.deleteLater()
            self.worker = None

        if self.worker_thread:
            # Ensure thread is fully stopped before cleanup
            if self.worker_thread.isRunning():
                LOGGER.warning("Thread still running during cleanup")

            # Schedule for deletion in next event loop iteration
            self.worker_thread.deleteLater()
            self.worker_thread = None

        # Reset processing state
        self.is_processing = False
        self.processing_state_changed.emit(False)

        LOGGER.debug("Worker thread cleaned up safely")

    def cleanup_all_resources(self) -> None:
        """Clean up all processing manager resources."""
        LOGGER.info("Cleaning up all processing manager resources")

        # Stop any running processing
        if self.is_processing:
            self.stop_processing()

        # Final cleanup
        self._cleanup_thread()

        LOGGER.info("Processing manager cleanup completed")

    def get_processing_state(self) -> bool:
        """Get the current processing state.

        Returns:
            True if processing is active, False otherwise
        """
        return self.is_processing

    def get_current_output_path(self) -> Path | None:
        """Get the current output file path.

        Returns:
            Path to the current output file, or None if not processing
        """
        return self.current_output_path if self.is_processing else None

    def validate_processing_args(self, args: dict[str, Any]) -> tuple[bool, str]:
        """Validate processing arguments before starting.

        Args:
            args: Dictionary containing processing parameters

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check input directory
            input_dir = args.get("input_dir")
            if not input_dir:
                return False, "No input directory specified"

            input_path = Path(input_dir)
            if not input_path.exists():
                return False, f"Input directory does not exist: {input_dir}"

            if not input_path.is_dir():
                return False, f"Input path is not a directory: {input_dir}"

            # Check output file
            output_file = args.get("output_file")
            if not output_file:
                return False, "No output file specified"

            output_path = Path(output_file)
            if output_path.exists() and not args.get("overwrite"):
                return False, f"Output file already exists: {output_file}"

            # Check model location
            model_location = args.get("model_location")
            if not model_location:
                return False, "No model location specified"

            model_path = Path(model_location)
            if not model_path.exists():
                return False, f"Model location does not exist: {model_location}"

            # Check numeric parameters
            if args.get("exp", 1) < 1:
                return False, "Interpolation factor must be at least 1"

            if args.get("fps", 30) <= 0:
                return False, "FPS must be greater than 0"

            return True, ""

        except Exception as e:
            return False, f"Validation error: {e!s}"
