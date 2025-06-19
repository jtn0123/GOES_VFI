"""UI/UX improvements for GOES_VFI application.

This module provides enhanced user interface components including:
    - Better error handling and user feedback
- Interactive tutorials and help system
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List
import sys

from PyQt6.QtCore import QObject, pyqtSignal
from enum import Enum
import traceback

- Undo/redo functionality
- Progress indicators and status updates
- Accessibility improvements
"""

QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
QTextEdit, QProgressBar, QWidget, QApplication,
QGroupBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)

class ErrorSeverity(Enum):  # pylint: disable=too-few-public-methods
"""Error severity levels for user feedback."""
INFO = "info"
WARNING = "warning"
ERROR = "error"
CRITICAL = "critical"

@dataclass
class UserAction:
    """Represents a user action that can be undone/redone."""
    name: str
    description: str
    undo_func: Callable[[], None]
    redo_func: Callable[[], None]
    timestamp: float = field(default_factory=lambda: __import__('time').time())
    metadata: Dict[str, Any] = field(default_factory=dict)

class UndoRedoManager(QObject):
    """Manages undo/redo functionality for the application."""

    # Signals
    can_undo_changed = pyqtSignal(bool)
    can_redo_changed = pyqtSignal(bool)
    action_performed = pyqtSignal(str)  # Action description

    def __init__(self, max_actions: int = 50):
        """Initialize the undo/redo manager.

        Args:
            max_actions: Maximum number of actions to keep in history
        """
        super().__init__()
        self.max_actions = max_actions
        self.undo_stack: List[UserAction] = []
        self.redo_stack: List[UserAction] = []

    def execute_action(self, action: UserAction) -> bool:
        """Execute an action and add it to the undo stack.

        Args:
            action: The action to execute

        Returns:
            True if action was executed successfully
        """
        try:
            pass
            # Execute the redo function (which performs the action)
            action.redo_func()

            # Add to undo stack
            self.undo_stack.append(action)

            # Limit stack size
            if len(self.undo_stack) > self.max_actions:
                pass
                self.undo_stack.pop(0)

            # Clear redo stack (new action invalidates redo history)
            self.redo_stack.clear()

            # Emit signals
            self.action_performed.emit(action.description)
            self.can_undo_changed.emit(True)
            self.can_redo_changed.emit(False)

            LOGGER.info("Action executed: %s", action.name)
            return True

        except Exception as e:
            pass
            LOGGER.error("Failed to execute action "{action.name}': {e}")
            return False

    def undo(self) -> bool:
        """Undo the last action.

        Returns:
            True if action was undone successfully
        """
        if not self.undo_stack:
            pass
            return False

        try:
            action = self.undo_stack.pop()
            action.undo_func()

            self.redo_stack.append(action)

            self.action_performed.emit(f"Undid: {action.description}")
            self.can_undo_changed.emit(len(self.undo_stack) > 0)
            self.can_redo_changed.emit(True)

            LOGGER.info("Action undone: %s", action.name)
            return True

        except Exception as e:
            pass
            LOGGER.error("Failed to undo action: %s", e)
            return False

    def redo(self) -> bool:
        """Redo the last undone action.

        Returns:
            True if action was redone successfully
        """
        if not self.redo_stack:
            pass
            return False

        try:
            action = self.redo_stack.pop()
            action.redo_func()

            self.undo_stack.append(action)

            self.action_performed.emit(f"Redid: {action.description}")
            self.can_undo_changed.emit(True)
            self.can_redo_changed.emit(len(self.redo_stack) > 0)

            LOGGER.info("Action redone: %s", action.name)
            return True

        except Exception as e:
            pass
            LOGGER.error("Failed to redo action: %s", e)
            return False

    def can_undo(self) -> bool:
        """Check if undo is available."""
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        pass
        """Check if redo is available."""
        return len(self.redo_stack) > 0

    def get_undo_text(self) -> str:
        pass
        """Get description of next undo action."""
        if self.undo_stack:
            pass
            return f"Undo {self.undo_stack[-1].description}"
        return "Undo"

    def get_redo_text(self) -> str:
        """Get description of next redo action."""
        if self.redo_stack:
            pass
            return f"Redo {self.redo_stack[-1].description}"
        return "Redo"

    def clear_history(self) -> None:
        """Clear all undo/redo history."""
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.can_undo_changed.emit(False)
        self.can_redo_changed.emit(False)

class ErrorDialog(QDialog):  # pylint: disable=too-few-public-methods
"""Enhanced error dialog with better user feedback."""

def __init__(self, title: str, message: str, details: str = "",:)
severity: ErrorSeverity = ErrorSeverity.ERROR, parent=None):
                     """Initialize the error dialog.

Args:
            title: Dialog title
            message: Main error message
            details: Detailed error information
            severity: Error severity level
            parent: Parent widget
"""
super().__init__(parent)
self.setWindowTitle(title)
self.setModal(True)
self.setMinimumSize(500, 300)

self.severity = severity
self.setup_ui(message, details)

def setup_ui(self, message: str, details: str) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Header with icon and message
        header_layout = QHBoxLayout()

        # Icon based on severity
        icon_label = QLabel()
        icon_label.setFixedSize(48, 48)

        # Set icon based on severity
        app = QApplication.instance()
        if app:
            pass
            if self.severity == ErrorSeverity.CRITICAL:
                pass
                icon_label.setPixmap(app.style().standardIcon())
                app.style().StandardPixmap.SP_MessageBoxCritical
                ).pixmap(48, 48))
            elif self.severity == ErrorSeverity.ERROR:
                pass
                icon_label.setPixmap(app.style().standardIcon())
                app.style().StandardPixmap.SP_MessageBoxWarning
                ).pixmap(48, 48))
            elif self.severity == ErrorSeverity.WARNING:
                pass
                icon_label.setPixmap(app.style().standardIcon())
                app.style().StandardPixmap.SP_MessageBoxInformation
                ).pixmap(48, 48))
            else:  # INFO
            icon_label.setPixmap(app.style().standardIcon())
            app.style().StandardPixmap.SP_MessageBoxInformation
            ).pixmap(48, 48))

        header_layout.addWidget(icon_label)

        # Message
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setFont(QFont("", 12))
        header_layout.addWidget(message_label, 1)

        layout.addLayout(header_layout)

        # Details section (collapsible)
        if details:
            pass
            details_group = QGroupBox("Technical Details")
            details_layout = QVBoxLayout(details_group)

            details_text = QTextEdit()
            details_text.setPlainText(details)
            details_text.setReadOnly(True)
            details_text.setMaximumHeight(200)
            details_layout.addWidget(details_text)

            layout.addWidget(details_group)

        # Buttons
        button_layout = QHBoxLayout()

        # Copy to clipboard button
        if details:
            pass
            copy_button = QPushButton("Copy Details")
            copy_button.clicked.connect(lambda: self.copy_to_clipboard(details))
            button_layout.addWidget(copy_button)

        button_layout.addStretch()

        # OK button
        ok_button = QPushButton("OK")
        ok_button.setDefault(True)
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)

        layout.addLayout(button_layout)

def copy_to_clipboard(self, text: str) -> None:
        """Copy text to clipboard."""
        app = QApplication.instance()
        if app and app.clipboard():
            pass
            app.clipboard().setText(text)
            LOGGER.info("Error details copied to clipboard")

class ProgressDialog(QDialog):
    """Enhanced progress dialog with cancellation support."""

    # Signals
    cancelled = pyqtSignal()

    def __init__(self, title: str = "Processing...", parent=None):
        """Initialize the progress dialog.

        Args:
            title: Dialog title
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(400, 150)

        self.cancelled_flag = False
        self.setup_ui()

    def setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Status label
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Sub-status label
        self.sub_status_label = QLabel("")
        self.sub_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_status_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.sub_status_label)

        # Cancel button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_operation)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def update_progress(self, value: int, status: str = "", sub_status: str = "") -> None:
        """Update progress and status.

        Args:
            value: Progress value (0-100)
            status: Main status message
            sub_status: Secondary status message
        """
        self.progress_bar.setValue(value)

        if status:
            pass
            self.status_label.setText(status)

        if sub_status:
            pass
            self.sub_status_label.setText(sub_status)

        # Process events to keep UI responsive
        QApplication.processEvents()

    def cancel_operation(self) -> None:
        """Handle cancel button click."""
        self.cancelled_flag = True
        self.cancelled.emit()
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("Cancelling...")

    def is_cancelled(self) -> bool:
        """Check if operation was cancelled."""
        return self.cancelled_flag

class TutorialManager(QObject):
    pass
    """Manages interactive tutorials for the application."""

    # Signals
    tutorial_started = pyqtSignal(str)  # Tutorial ID
    tutorial_completed = pyqtSignal(str)  # Tutorial ID
    tutorial_skipped = pyqtSignal(str)  # Tutorial ID

    def __init__(self):
        """Initialize the tutorial manager."""
        super().__init__()
        self.tutorials: Dict[str, Dict[str, Any]] = {}
        self.completed_tutorials: set = set()
        self.load_tutorials()

    def load_tutorials(self) -> None:
        """Load tutorial definitions."""
        self.tutorials = {
        "first_run": {
        "title": "Welcome to GOES_VFI",
        "description": "Learn the basics of processing satellite data",
        "steps": [
        {
        "title": "Select Input Directory",
        "description": "Choose a folder containing your satellite images",
        "target": "input_directory_button",
        "action": "highlight"
        },
        {
        "title": "Choose Output File",
        "description": "Specify where to save your video",
        "target": "output_file_button",
        "action": "highlight"
        },
        {
        "title": "Configure Settings",
        "description": "Adjust frame rate and processing options",
        "target": "settings_group",
        "action": "highlight"
        },
        {
        "title": "Start Processing",
        "description": "Click Start to begin creating your video",
        "target": "start_button",
        "action": "highlight"
        }
        ]
        },
        "resource_limits": {
        "title": "Resource Management",
        "description": "Learn how to configure resource limits",
        "steps": [
        {
        "title": "Resource Limits Tab",
        "description": "Switch to the Resource Limits tab",
        "target": "resource_limits_tab",
        "action": "click"
        },
        {
        "title": "Memory Limits",
        "description": "Set memory usage limits to prevent crashes",
        "target": "memory_limit_checkbox",
        "action": "highlight"
        },
        {
        "title": "Processing Time",
        "description": "Set maximum processing time",
        "target": "time_limit_checkbox",
        "action": "highlight"
        }
        ]
        },
        "error_recovery": {
        "title": "Error Recovery",
        "description": "Learn how to handle and recover from errors",
        "steps": [
        {
        "title": "Error Dialog",
        "description": "Understanding error messages and solutions",
        "target": None,
        "action": "info"
        },
        {
        "title": "Log Files",
        "description": "Where to find detailed error information",
        "target": None,
        "action": "info"
        }
        ]
        }
        }

    def start_tutorial(self, tutorial_id: str, target_widget: QWidget) -> bool:
        """Start an interactive tutorial.

        Args:
            tutorial_id: ID of the tutorial to start
            target_widget: Widget to attach tutorial to

        Returns:
            True if tutorial was started successfully
        """
        if tutorial_id not in self.tutorials:
            pass
            LOGGER.error("Tutorial "{tutorial_id}' not found")
            return False

        tutorial = self.tutorials[tutorial_id]

        # Show tutorial dialog
        dialog = TutorialDialog(tutorial, target_widget, self)
        dialog.tutorial_completed.connect()
        lambda: self.completed_tutorials.add(tutorial_id)
        )
        dialog.tutorial_completed.connect()
        lambda: self.tutorial_completed.emit(tutorial_id)
        )
        dialog.tutorial_skipped.connect()
        lambda: self.tutorial_skipped.emit(tutorial_id)
        )

        self.tutorial_started.emit(tutorial_id)
        dialog.show()

        return True

    def is_tutorial_completed(self, tutorial_id: str) -> bool:
        """Check if a tutorial has been completed."""
        return tutorial_id in self.completed_tutorials

    def mark_tutorial_completed(self, tutorial_id: str) -> None:
        """Mark a tutorial as completed."""
        self.completed_tutorials.add(tutorial_id)
        self.tutorial_completed.emit(tutorial_id)

    def get_available_tutorials(self) -> List[str]:
        """Get list of available tutorial IDs."""
        return list(self.tutorials.keys())

class TutorialDialog(QDialog):
    """Interactive tutorial dialog."""

    # Signals
    tutorial_completed = pyqtSignal()
    tutorial_skipped = pyqtSignal()

    def __init__(self, tutorial: Dict[str, Any], target_widget: QWidget, parent=None):
        """Initialize the tutorial dialog.

        Args:
            tutorial: Tutorial definition
            target_widget: Target widget for tutorial
            parent: Parent widget
        """
        super().__init__(parent)
        self.tutorial = tutorial
        self.target_widget = target_widget
        self.current_step = 0

        self.setWindowTitle(tutorial["title"])
        self.setModal(False)
        self.setFixedSize(350, 200)

        self.setup_ui()
        self.show_current_step()

    def setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Title and description
        title_label = QLabel(self.tutorial["title"])
        title_label.setFont(QFont("", 14, QFont.Weight.Bold))
        layout.addWidget(title_label)

        desc_label = QLabel(self.tutorial["description"])
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Step content
        self.step_widget = QFrame()
        self.step_layout = QVBoxLayout(self.step_widget)
        layout.addWidget(self.step_widget)

        # Navigation buttons
        button_layout = QHBoxLayout()

        self.skip_button = QPushButton("Skip Tutorial")
        self.skip_button.clicked.connect(self.skip_tutorial)
        button_layout.addWidget(self.skip_button)

        button_layout.addStretch()

        self.prev_button = QPushButton("Previous")
        self.prev_button.clicked.connect(self.previous_step)
        self.prev_button.setEnabled(False)
        button_layout.addWidget(self.prev_button)

        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.next_step)
        button_layout.addWidget(self.next_button)

        layout.addLayout(button_layout)

    def show_current_step(self) -> None:
        """Show the current tutorial step."""
        # Clear previous step content
        for i in reversed(range(self.step_layout.count())):
            self.step_layout.itemAt(i).widget().setParent(None)

        if self.current_step >= len(self.tutorial["steps"]):
            pass
            self.complete_tutorial()
            return

        step = self.tutorial["steps"][self.current_step]

        # Step title
        step_title = QLabel(f"Step {self.current_step + 1}: {step['title']}")
        step_title.setFont(QFont("", 12, QFont.Weight.Bold))
        self.step_layout.addWidget(step_title)

        # Step description
        step_desc = QLabel(step["description"])
        step_desc.setWordWrap(True)
        self.step_layout.addWidget(step_desc)

        # Update button states
        self.prev_button.setEnabled(self.current_step > 0)

        if self.current_step == len(self.tutorial["steps"]) - 1:
            pass
            self.next_button.setText("Complete")
        else:
            self.next_button.setText("Next")

    def next_step(self) -> None:
        """Move to the next tutorial step."""
        self.current_step += 1
        self.show_current_step()

    def previous_step(self) -> None:
        """Move to the previous tutorial step."""
        if self.current_step > 0:
            pass
            self.current_step -= 1
            self.show_current_step()

    def skip_tutorial(self) -> None:
        """Skip the tutorial."""
        self.tutorial_skipped.emit()
        self.close()

    def complete_tutorial(self) -> None:
        """Complete the tutorial."""
        self.tutorial_completed.emit()
        self.close()

class StatusManager(QObject):
    """Manages application status messages and notifications."""

    # Signals
    status_changed = pyqtSignal(str, int)  # message, timeout
    permanent_status_changed = pyqtSignal(str)
    notification_added = pyqtSignal(str, str)  # title, message

    def __init__(self):
        pass
        """Initialize the status manager."""
        super().__init__()
        self.current_status = ""
        self.permanent_status = ""

    def show_status(self, message: str, timeout: int = 5000) -> None:
        """Show a temporary status message.

        Args:
            message: Status message to show
            timeout: Timeout in milliseconds (0 = permanent)
        """
        self.current_status = message
        self.status_changed.emit(message, timeout)
        LOGGER.info("Status: %s", message)

    def set_permanent_status(self, message: str) -> None:
        """Set a permanent status message.

        Args:
            message: Permanent status message
        """
        self.permanent_status = message
        self.permanent_status_changed.emit(message)

    def show_notification(self, title: str, message: str) -> None:
        """Show a notification.

        Args:
            pass
            title: Notification title
            message: Notification message
        """
        self.notification_added.emit(title, message)
        LOGGER.info("Notification: %s - %s", title, message)

    def get_current_status(self) -> str:
        """Get the current status message."""
        return self.current_status

    def get_permanent_status(self) -> str:
        """Get the permanent status message."""
        return self.permanent_status

def show_error_dialog(title: str,
message: str,
details: str = "",
severity: ErrorSeverity = ErrorSeverity.ERROR,
parent=None,
) -> None:
    """Show an enhanced error dialog.

    Args:
        title: Dialog title
        message: Main error message
        details: Detailed error information
        severity: Error severity level
        parent: Parent widget
    """
    dialog = ErrorDialog(title, message, details, severity, parent)
    dialog.exec()

def handle_exception(exc_type, exc_value, exc_traceback, parent=None) -> None:
    pass
    """Global exception handler with enhanced error dialog.

    Args:
        pass
        exc_type: Exception type
        exc_value: Exception value
        exc_traceback: Exception traceback
        parent: Parent widget for dialog
    """
    if issubclass(exc_type, KeyboardInterrupt):
        pass
        # Allow keyboard interrupt to work normally
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    # Format the exception
    error_msg = str(exc_value)
    error_details = ''.join(traceback.format_exception())
    exc_type, exc_value, exc_traceback
    ))

    # Determine severity
    if issubclass(exc_type, (SystemExit, SystemError)):
        pass
    pass
    severity = ErrorSeverity.CRITICAL
    elif issubclass(exc_type, (RuntimeError, OSError, IOError)):
        pass
        severity = ErrorSeverity.ERROR
    else:
        severity = ErrorSeverity.WARNING

    # Show error dialog
    show_error_dialog()
    title=f"Unexpected Error: {exc_type.__name__}",
    message=error_msg or "An unexpected error occurred",
    details=error_details,
    severity=severity,
    parent=parent
    )

    # Log the exception
    LOGGER.exception("Unhandled exception: %s: %s", exc_type.__name__, error_msg)

def create_progress_callback(dialog: ProgressDialog,
) -> Callable[[int, str, str], bool]:
    """Create a progress callback function for use with the progress dialog.

    Args:
        dialog: Progress dialog to update

    Returns:
        Callback function that returns True if should continue, False if cancelled
    """
    def progress_callback(value: int, status: str = "", sub_status: str = "") -> bool:
        """Progress callback function.

        Args:
            value: Progress value (0-100)
            status: Main status message
            sub_status: Secondary status message

        Returns:
            True if should continue, False if cancelled
        """
        dialog.update_progress(value, status, sub_status)
        return not dialog.is_cancelled()

    return progress_callback
