"""
This module defines the ProcessingViewModel class, which is intended to manage
the state, input parameters, and results for the core VFI processing pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class ProcessingViewModel(QObject):
    """
    ViewModel for the main VFI processing tab.

    This class manages input parameters, processing state, and results
    for the core VFI pipeline. It coordinates the main processing logic and
    communicates with the GUI view.
    """

    # Signal definitions for view binding
    status_updated = pyqtSignal(str)  # General status updates
    progress_updated = pyqtSignal(int, int, float)  # current, total, eta_seconds
    processing_finished = pyqtSignal(bool, str)  # success/failure, message

    def __init__(self, parent: QObject | None = None):
        """
        Initializes the ProcessingViewModel.

        Args:
            parent (Optional[QObject]): The parent QObject, if any.
        """
        super().__init__(parent)
        LOGGER.info("ProcessingViewModel initialized")

        # State tracking
        self._is_processing = False
        self._current_progress = 0
        self._total_frames = 0
        self._time_elapsed = 0.0
        self._status_message = "Ready"
        self._output_file_path: Optional[Path] = None

        # Initialize properties for input parameters
        self._input_directory: Optional[Path] = None
        self._output_file: Optional[Path] = None

    def start_processing(self) -> None:
        """
        Command to start the VFI processing pipeline.

        This method should be triggered by the UI to initiate the main VFI processing.
        Sets the internal state to processing and emits a status update.
        """
        if self._is_processing:
            LOGGER.warning("Processing already in progress, ignoring start request")
            return

        LOGGER.info("Starting processing")
        self._is_processing = True
        self._current_progress = 0
        self._total_frames = 0
        self._time_elapsed = 0.0
        self._status_message = "Processing started"
        self.status_updated.emit(self._status_message)

    def cancel_processing(self) -> None:
        """
        Command to cancel the ongoing VFI processing.

        This method should be triggered by the UI to request cancellation of the
        main VFI processing pipeline.
        """
        if not self._is_processing:
            LOGGER.warning("No processing in progress, ignoring cancel request")
            return

        LOGGER.info("Cancelling processing")
        self._is_processing = False
        self._status_message = "Processing cancelled"
        self.status_updated.emit(self._status_message)

        # Emit processing_finished signal with success=False
        self.processing_finished.emit(False, "Processing cancelled by user")

    def update_progress(self, current: int, total: int, time_elapsed: float) -> None:
        """
        Update the progress information during processing.

        Args:
            current: Current frame being processed
            total: Total number of frames to process
            time_elapsed: Time elapsed in seconds
        """
        LOGGER.debug(
            "Progress update: %s/%s frames, %.2fs", current, total, time_elapsed
        )

        # Update internal state
        self._current_progress = current
        self._total_frames = total
        self._time_elapsed = time_elapsed

        # Update status message
        percentage = (current / total * 100) if total > 0 else 0
        self._status_message = f"Processing: {percentage:.1f}% ({current}/{total})"

        # Emit signals for view updates
        self.status_updated.emit(self._status_message)
        self.progress_updated.emit(current, total, time_elapsed)

    def finish_processing(self, success: bool, message: str | Path = "") -> None:
        """
        Handle completion of processing.

        Args:
            success: Whether processing completed successfully
            message: Success message or error information (can be string or Path)
        """
        LOGGER.info("Processing finished. Success: %s, Message: %s", success, message)

        # Update internal state
        self._is_processing = False

        # Convert Path to string if needed
        if isinstance(message, Path):
            # Store the path in our output_file_path property
            self._output_file_path = message
            # Convert to string for the message
            message_str = str(message)
        else:
            message_str = str(message) if message else ""

        # Set appropriate status message
        if success:
            if not message_str:
                message_str = "Processing completed successfully"
            self._status_message = f"Complete: {message_str}"
        else:
            if not message_str:
                message_str = "Processing failed"
            self._status_message = f"Error: {message_str}"

        # Emit signals for view updates
        self.status_updated.emit(self._status_message)
        self.processing_finished.emit(success, message_str)

    def set_output_file_path(self, path: Path) -> None:
        """
        Set the output file path after successful processing.

        Args:
            path: The path to the generated output file
        """
        LOGGER.info("Output file path set: %s", path)
        self._output_file_path = path

    # Properties
    @property
    def status(self) -> str:
        """
        The current status message for the processing tab.

        Returns:
            str: Status message describing the current state.
        """
        return self._status_message

    @property
    def is_processing(self) -> bool:
        """
        Whether processing is currently in progress.

        Returns:
            bool: True if processing is in progress, False otherwise
        """
        return self._is_processing

    @property
    def current_progress(self) -> int:
        """
        The current progress value.

        Returns:
            int: Current frame being processed
        """
        return self._current_progress

    @property
    def total_frames(self) -> int:
        """
        The total number of frames to process.

        Returns:
            int: Total number of frames
        """
        return self._total_frames

    @property
    def output_file_path(self) -> Optional[Path]:
        """
        The path to the generated output file.

        Returns:
            Optional[Path]: The output file path, or None if not set
        """
        return self._output_file_path
