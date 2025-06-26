"""
Enhanced user feedback utilities for integrity check tabs.

This module provides improved user feedback functionality, including detailed
progress reporting, error messaging, and status updates for the integrity check system.
"""

import logging
from datetime import datetime
from enum import Enum, auto
from typing import List, Optional, Tuple

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Configure logging
LOGGER = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of user messages with corresponding visual styling."""

    INFO = auto()
    SUCCESS = auto()
    WARNING = auto()
    ERROR = auto()
    DEBUG = auto()


class FeedbackManager(QObject):
    """
    Central manager for user feedback across the integrity check system.

    This class provides a standardized approach for displaying progress, status messages,
    and error notifications to the user, with consistent styling and behavior.
    """

    # Signals for communication
    message_added = pyqtSignal(str, object)  # message, message_type
    status_updated = pyqtSignal(str, object)  # status_text, message_type
    progress_updated = pyqtSignal(int, int, float)  # current, total, eta
    task_started = pyqtSignal(str)  # task_name
    task_completed = pyqtSignal(str, bool)  # task_name, success
    error_occurred = pyqtSignal(str, str)  # error_title, error_message

    def __init__(self) -> None:
        """Initialize the feedback manager."""
        super().__init__()

        # Create message history
        self._message_history: List[Tuple[str, MessageType, datetime]] = []

        # Create progress tracking
        self._current_task: Optional[str] = None
        self._progress_current: int = 0
        self._progress_total: int = 0
        self._progress_start_time: float = 0

        # Create status tracking
        self._current_status: str = "Ready"
        self._current_status_type: MessageType = MessageType.INFO

    def add_message(self, message: str, message_type: MessageType = MessageType.INFO) -> None:
        """Add a message to the history and emit signal.

        Args:
            message: The message text
            message_type: Type of message
        """
        timestamp = datetime.now()
        self._message_history.append((message, message_type, timestamp))
        self.message_added.emit(message, message_type)
        LOGGER.debug("Added %s message: %s", message_type.name, message)

    def update_status(self, status: str, message_type: MessageType = MessageType.INFO) -> None:
        """Update the current status.

        Args:
            status: New status text
            message_type: Type of status message
        """
        self._current_status = status
        self._current_status_type = message_type
        self.status_updated.emit(status, message_type)
        LOGGER.debug("Status updated to: %s", status)

    def update_progress(self, current: int, total: int, eta: float = 0.0) -> None:
        """Update progress information.

        Args:
            current: Current progress value
            total: Total progress value
            eta: Estimated time to completion in seconds
        """
        self._progress_current = current
        self._progress_total = total
        self.progress_updated.emit(current, total, eta)

    def start_task(self, task_name: str) -> None:
        """Start a new task.

        Args:
            task_name: Name of the task
        """
        self._current_task = task_name
        self._progress_start_time = datetime.now().timestamp()
        self.task_started.emit(task_name)
        self.add_message(f"Started: {task_name}", MessageType.INFO)
        LOGGER.info("Task started: %s", task_name)

    def complete_task(self, task_name: str, success: bool = True) -> None:
        """Complete a task.

        Args:
            task_name: Name of the task
            success: Whether the task completed successfully
        """
        elapsed = datetime.now().timestamp() - self._progress_start_time
        self.task_completed.emit(task_name, success)

        if success:
            self.add_message(f"Completed: {task_name} ({elapsed:.1f}s)", MessageType.SUCCESS)
        else:
            self.add_message(f"Failed: {task_name} ({elapsed:.1f}s)", MessageType.ERROR)

        self._current_task = None
        LOGGER.info("Task %s: %s", "completed" if success else "failed", task_name)

    def report_error(self, title: str, message: str) -> None:
        """Report an error.

        Args:
            title: Error title
            message: Error message
        """
        self.error_occurred.emit(title, message)
        self.add_message(f"{title}: {message}", MessageType.ERROR)
        LOGGER.error("%s: %s", title, message)

    def get_message_history(self, limit: Optional[int] = None) -> List[Tuple[str, MessageType, datetime]]:
        """Get message history.

        Args:
            limit: Maximum number of messages to return

        Returns:
            List of (message, type, timestamp) tuples
        """
        if limit:
            return self._message_history[-limit:]
        return self._message_history.copy()


class FeedbackWidget(QWidget):
    """Widget for displaying feedback messages with color coding."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the feedback widget."""
        super().__init__(parent)

        # Create UI
        layout = QVBoxLayout(self)

        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setProperty("class", "FeedbackStatusLabel")
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setProperty("class", "DataProgress")
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Message list
        self.message_list = QListWidget()
        self.message_list.setMaximumHeight(150)
        self.message_list.setProperty("class", "FeedbackMessageList")
        layout.addWidget(self.message_list)

        # Connect to feedback manager if available
        self.feedback_manager: Optional[FeedbackManager] = None

    def set_feedback_manager(self, manager: FeedbackManager) -> None:
        """Connect to a feedback manager.

        Args:
            manager: The feedback manager to connect to
        """
        self.feedback_manager = manager

        # Connect signals
        manager.message_added.connect(self._on_message_added)
        manager.status_updated.connect(self._on_status_updated)
        manager.progress_updated.connect(self._on_progress_updated)

    def _on_message_added(self, message: str, message_type: MessageType) -> None:
        """Handle new message from feedback manager."""
        item = QListWidgetItem(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

        # Set color based on type
        color_map = {
            MessageType.INFO: QColor("#3498db"),
            MessageType.SUCCESS: QColor("#2ecc71"),
            MessageType.WARNING: QColor("#f39c12"),
            MessageType.ERROR: QColor("#e74c3c"),
            MessageType.DEBUG: QColor("#95a5a6"),
        }

        if message_type in color_map:
            item.setForeground(color_map[message_type])

        self.message_list.insertItem(0, item)

        # Keep only last 100 messages
        while self.message_list.count() > 100:
            self.message_list.takeItem(self.message_list.count() - 1)

    def _on_status_updated(self, status: str, message_type: MessageType) -> None:
        """Handle status update from feedback manager."""
        self.status_label.setText(status)

        # Update theme class based on message type
        class_map = {
            MessageType.INFO: "FeedbackStatusInfo",
            MessageType.SUCCESS: "FeedbackStatusSuccess",
            MessageType.WARNING: "FeedbackStatusWarning",
            MessageType.ERROR: "FeedbackStatusError",
            MessageType.DEBUG: "FeedbackStatusDebug",
        }

        theme_class = class_map.get(message_type, "FeedbackStatusLabel")
        self.status_label.setProperty("class", theme_class)

    def _on_progress_updated(self, current: int, total: int, eta: float) -> None:
        """Handle progress update from feedback manager."""
        if total > 0:
            self.progress_bar.setVisible(True)
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)

            # Update format with ETA if available
            percentage = (current / total) * 100
            if eta > 0:
                eta_min = int(eta / 60)
                eta_sec = int(eta % 60)
                self.progress_bar.setFormat(f"{percentage:.1f}% - ETA: {eta_min}m {eta_sec}s")
            else:
                self.progress_bar.setFormat(f"{percentage:.1f}%")
        else:
            self.progress_bar.setVisible(False)


class ErrorDetailsDialog(QDialog):
    """Dialog for showing detailed error information."""

    def __init__(
        self,
        error_title: str,
        error_message: str,
        traceback: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the error details dialog."""
        super().__init__(parent)

        # Apply material theme dialog class
        self.setProperty("class", "CropSelectionDialog")

        self.setWindowTitle(error_title)
        self.setModal(True)
        self.resize(600, 400)

        layout = QVBoxLayout(self)

        # Error message
        message_label = QLabel(error_message)
        message_label.setWordWrap(True)
        message_label.setProperty("class", "ErrorDialogMessage")
        layout.addWidget(message_label)

        # Traceback if available
        if traceback:
            traceback_label = QLabel("Traceback:")
            layout.addWidget(traceback_label)

            traceback_text = QPlainTextEdit()
            traceback_text.setPlainText(traceback)
            traceback_text.setReadOnly(True)
            traceback_text.setProperty("class", "ErrorDialogTraceback")
            layout.addWidget(traceback_text)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
