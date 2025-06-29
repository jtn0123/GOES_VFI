import logging

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from goesvfi.file_sorter.view_model import FileSorterViewModel  # Import ViewModel
from goesvfi.gui_components.icon_manager import get_icon
from goesvfi.gui_components.update_manager import register_update, request_update

LOGGER = logging.getLogger(__name__)


class FileSorterTab(QWidget):
    """Tab widget for organizing files by type."""

    directory_selected = pyqtSignal(str)  # Signal emitted when a directory is selected

    def __init__(self, view_model: FileSorterViewModel, parent: QWidget | None = None) -> None:
        """Initialize the FileSorterTab.

        Args:
            view_model: The ViewModel instance to use
            parent: Parent widget

        Raises:
            TypeError: If view_model is not an instance of FileSorterViewModel
        """
        super().__init__(parent)

        if not isinstance(view_model, FileSorterViewModel):
            msg = "view_model must be an instance of FileSorterViewModel"
            raise TypeError(msg)

        self.view_model = view_model  # Use the provided ViewModel
        # self.view_model.add_observer(self._update_ui)
        # Register observer - Observer pattern not fully implemented in ViewModel

        # Main Layout with enhanced styling
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Add enhanced header
        self._create_header(main_layout)

        # Create UI sections
        source_browse_button = self._create_source_section(main_layout)
        self._create_destination_section(main_layout)
        self._create_options_section(main_layout)
        self._create_actions_section(main_layout)
        self._create_status_section(main_layout)

        # Connect signals
        source_browse_button.clicked.connect(self._browse_source)
        self.sort_button.clicked.connect(self._start_sorting)

        # Setup UpdateManager integration
        self._setup_update_manager()

        # Set main layout
        self.setLayout(main_layout)

    def _create_header(self, layout: QVBoxLayout) -> None:  # noqa: PLR6301
        """Create the enhanced header section."""
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)

        icon_label = QLabel()
        icon_label.setPixmap(get_icon("📁").pixmap(24, 24))
        header_layout.addWidget(icon_label)

        header_text = QLabel("File Sorter - Organize Converted Files")
        header_text.setProperty("class", "AppHeader")
        header_layout.addWidget(header_text)
        header_layout.addStretch()

        layout.addWidget(header_widget)

    def _create_source_section(self, layout: QVBoxLayout) -> QPushButton:
        """Create the source directory section.

        Returns:
            QPushButton: The browse button for connecting signals
        """
        source_group = QGroupBox(self.tr("Source Directory"))
        source_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        source_layout = QGridLayout()
        source_layout.setContentsMargins(10, 15, 10, 10)
        source_layout.setSpacing(8)

        source_label = QLabel(self.tr("Folder:"))
        source_label.setProperty("class", "StandardLabel")

        self.source_line_edit = QLineEdit()

        source_browse_button = QPushButton(self.tr("Browse..."))
        source_browse_button.setFixedWidth(120)

        source_layout.addWidget(source_label, 0, 0)
        source_layout.addWidget(self.source_line_edit, 0, 1)
        source_layout.addWidget(source_browse_button, 0, 2)
        source_group.setLayout(source_layout)
        layout.addWidget(source_group)

        return source_browse_button

    def _create_destination_section(self, layout: QVBoxLayout) -> None:
        """Create the destination section."""
        destination_group = QGroupBox(self.tr("Destination"))
        destination_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        destination_layout = QGridLayout()
        destination_layout.setContentsMargins(10, 15, 10, 10)
        destination_layout.setSpacing(8)

        destination_label = QLabel(self.tr("Output Folder:"))
        destination_label.setProperty("class", "StandardLabel")

        destination_info = QLabel(self.tr("Files will be sorted to a 'converted' subfolder"))
        destination_info.setProperty("class", "StatusInfo")

        destination_layout.addWidget(destination_label, 0, 0)
        destination_layout.addWidget(destination_info, 0, 1, 1, 2)
        destination_group.setLayout(destination_layout)
        layout.addWidget(destination_group)

    def _create_options_section(self, layout: QVBoxLayout) -> None:
        """Create the options section."""
        options_group = QGroupBox(self.tr("Options"))
        options_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        options_layout = QVBoxLayout()
        options_layout.setContentsMargins(10, 15, 10, 10)
        options_layout.setSpacing(8)

        self.dry_run_checkbox = QCheckBox(self.tr("Dry Run (Log actions without moving files)"))
        options_layout.addWidget(self.dry_run_checkbox)

        duplicate_label = QLabel(self.tr("Duplicate Handling:"))
        duplicate_label.setProperty("class", "StandardLabel")

        self.duplicate_combo = QComboBox()
        self.duplicate_combo.addItems([self.tr("Overwrite"), self.tr("Skip"), self.tr("Rename")])
        options_layout.addWidget(duplicate_label)
        options_layout.addWidget(self.duplicate_combo)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

    def _create_actions_section(self, layout: QVBoxLayout) -> None:
        """Create the actions section."""
        actions_group = QGroupBox(self.tr("Actions"))
        actions_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        actions_layout = QVBoxLayout()
        actions_layout.setContentsMargins(10, 15, 10, 10)
        actions_layout.setSpacing(8)

        self.sort_button = QPushButton(self.tr("Sort Files"))
        self.sort_button.setFixedHeight(40)
        self.sort_button.setProperty("class", "StartButton")
        actions_layout.addWidget(self.sort_button)
        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)

    def _create_status_section(self, layout: QVBoxLayout) -> None:
        """Create the status section."""
        status_group = QGroupBox(self.tr("Status & Progress"))
        status_layout = QVBoxLayout()
        status_layout.setContentsMargins(10, 15, 10, 10)
        status_layout.setSpacing(10)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - Sorting files...")
        self.progress_bar.setProperty("class", "DataProgress")
        status_layout.addWidget(self.progress_bar)

        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(150)
        self.status_text.setProperty("class", "DatePickerMonospace")
        status_layout.addWidget(self.status_text)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

    def _browse_source(self) -> None:
        """Opens a file dialog to select source folder and updates ViewModel."""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Source Folder")
        if folder_path:
            self.view_model.source_directory = folder_path  # Update ViewModel
            self.directory_selected.emit(folder_path)  # Emit signal with selected path

    def _start_sorting(self) -> None:
        """Starts the file sorting process via the ViewModel."""
        self.view_model.start_sorting()  # Delegate to ViewModel

    def _setup_update_manager(self) -> None:
        """Set up UpdateManager integration for batched UI updates."""
        # Register UI update operations
        register_update("file_sorter_ui", self._update_ui_batched, priority=2)
        register_update("file_sorter_progress", self._update_progress_batched, priority=1)
        register_update("file_sorter_status", self._update_status_batched, priority=2)

        LOGGER.info("FileSorterTab integrated with UpdateManager")

    def _update_ui_batched(self) -> None:
        """Batched wrapper for full UI update."""
        self._update_ui()

    def _update_progress_batched(self) -> None:
        """Batched wrapper for progress update."""
        self.progress_bar.setValue(int(self.view_model.progress_percentage))

    def _update_status_batched(self) -> None:
        """Batched wrapper for status update."""
        self.status_text.clear()
        self.status_text.append(self.view_model.status_message)
        self.sort_button.setEnabled(self.view_model.can_start_sorting)

    def request_ui_update(self, update_type: str = "ui") -> None:  # noqa: PLR6301
        """Request UI updates through UpdateManager.

        Args:
            update_type: Type of update ('ui', 'progress', 'status')
        """
        if update_type == "ui":
            request_update("file_sorter_ui")
        elif update_type == "progress":
            request_update("file_sorter_progress")
        elif update_type == "status":
            request_update("file_sorter_status")

    def _update_ui(self) -> None:
        """Updates UI elements based on ViewModel state."""
        self.source_line_edit.setText(self.view_model.source_directory)
        # Assuming ViewModel has properties for options and status
        self.dry_run_checkbox.setChecked(self.view_model.dry_run_enabled)
        # Assuming DuplicateMode enum is accessible and has a name attribute
        self.duplicate_combo.setCurrentText(self.view_model.duplicate_mode.capitalize())

        self.progress_bar.setValue(int(self.view_model.progress_percentage))

        # For status text, we might need to append instead of set,
        # or the ViewModel provides a list of messages.
        # For simplicity, let's assume ViewModel provides the current status message.
        # A more robust solution would involve the ViewModel emitting new messages.
        # Let's clear and append for now, assuming ViewModel provides the latest message.
        self.status_text.clear()
        self.status_text.append(self.view_model.status_message)

        self.sort_button.setEnabled(self.view_model.can_start_sorting)

        # Handle completion/error messages from ViewModel
        if self.view_model.show_completion_message:
            QMessageBox.information(self, "Sorting Complete", self.view_model.completion_message)
            self.view_model.show_completion_message = False  # Reset flag
        if self.view_model.show_error_message:
            QMessageBox.critical(self, "Sorting Error", self.view_model.error_message)
            self.view_model.show_error_message = False  # Reset flag
        if self.view_model.show_input_error_message:
            QMessageBox.warning(self, "Input Error", self.view_model.input_error_message)
            self.view_model.show_input_error_message = False  # Reset flag
