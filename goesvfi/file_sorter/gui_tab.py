import logging
from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
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

LOGGER = logging.getLogger(__name__)


class FileSorterTab(QWidget):
    directory_selected = pyqtSignal(str)  # Signal emitted when a directory is selected

    # Modified __init__ to accept a ViewModel instance
    def __init__(self, view_model: FileSorterViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        if not isinstance(view_model, FileSorterViewModel):
            raise TypeError("view_model must be an instance of FileSorterViewModel")

        self.view_model = view_model  # Use the provided ViewModel
        # self.view_model.add_observer(self._update_ui)
        # Register observer - Observer pattern not fully implemented in ViewModel

        # Main Layout with enhanced styling
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Add enhanced header
        header = QLabel("📁 File Sorter - Organize Converted Files")
        header.setProperty("class", "AppHeader")
        main_layout.addWidget(header)

        # Source Group with enhanced styling
        source_group = QGroupBox(self.tr("📁 Source Directory"))
        source_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        # Use default qt-material styling for QGroupBox
        source_layout = QGridLayout()
        source_layout.setContentsMargins(10, 15, 10, 10)
        source_layout.setSpacing(8)

        source_label = QLabel(self.tr("📂 Folder:"))
        source_label.setProperty("class", "StandardLabel")

        self.source_line_edit = QLineEdit()
        # Use default qt-material styling for QLineEdit

        source_browse_button = QPushButton(self.tr("🔍 Browse..."))
        source_browse_button.setFixedWidth(120)
        # Use default qt-material styling for QPushButton

        source_layout.addWidget(source_label, 0, 0)
        source_layout.addWidget(self.source_line_edit, 0, 1)
        source_layout.addWidget(source_browse_button, 0, 2)
        source_group.setLayout(source_layout)
        main_layout.addWidget(source_group)

        # Destination Group with enhanced styling
        destination_group = QGroupBox(self.tr("💾 Destination"))
        destination_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        # Use default qt-material styling for QGroupBox
        destination_layout = QGridLayout()
        destination_layout.setContentsMargins(10, 15, 10, 10)
        destination_layout.setSpacing(8)

        destination_label = QLabel(self.tr("📄 Output Folder:"))
        destination_label.setProperty("class", "StandardLabel")

        destination_info = QLabel(self.tr("✨ Files will be sorted to a 'converted' subfolder"))
        destination_info.setProperty("class", "StatusInfo")

        destination_layout.addWidget(destination_label, 0, 0)
        destination_layout.addWidget(destination_info, 0, 1, 1, 2)
        destination_group.setLayout(destination_layout)
        main_layout.addWidget(destination_group)

        # Options Group with enhanced styling
        options_group = QGroupBox(self.tr("⚙️ Options"))
        options_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        # Use default qt-material styling for QGroupBox
        options_layout = QVBoxLayout()
        options_layout.setContentsMargins(10, 15, 10, 10)
        options_layout.setSpacing(8)

        # Dry Run Checkbox with enhanced styling
        self.dry_run_checkbox = QCheckBox(self.tr("📋 Dry Run (Log actions without moving files)"))
        # Use default qt-material styling for QCheckBox
        options_layout.addWidget(self.dry_run_checkbox)

        # Duplicate Handling with enhanced styling
        duplicate_label = QLabel(self.tr("🔄 Duplicate Handling:"))
        duplicate_label.setProperty("class", "StandardLabel")

        self.duplicate_combo = QComboBox()
        self.duplicate_combo.addItems([self.tr("♾️ Overwrite"), self.tr("⏭️ Skip"), self.tr("🔄 Rename")])
        # Use default qt-material styling for QComboBox
        options_layout.addWidget(duplicate_label)
        options_layout.addWidget(self.duplicate_combo)

        options_group.setLayout(options_layout)
        main_layout.addWidget(options_group)

        # Actions Group with enhanced styling
        actions_group = QGroupBox(self.tr("🚀 Actions"))
        actions_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        # Use default qt-material styling for QGroupBox
        actions_layout = QVBoxLayout()
        actions_layout.setContentsMargins(10, 15, 10, 10)
        actions_layout.setSpacing(8)

        # Sort Button with enhanced styling
        self.sort_button = QPushButton(self.tr("📁 Sort Files"))
        self.sort_button.setFixedHeight(40)
        self.sort_button.setProperty("class", "StartButton")
        actions_layout.addWidget(self.sort_button)
        actions_group.setLayout(actions_layout)
        main_layout.addWidget(actions_group)

        # Status Group with enhanced styling
        status_group = QGroupBox(self.tr("📊 Status & Progress"))
        # Use default qt-material styling for QGroupBox
        status_layout = QVBoxLayout()
        status_layout.setContentsMargins(10, 15, 10, 10)
        status_layout.setSpacing(10)

        # Progress Bar with enhanced styling
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - Sorting files...")
        self.progress_bar.setProperty("class", "DataProgress")
        status_layout.addWidget(self.progress_bar)

        # Status Text Display with enhanced styling
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(150)
        self.status_text.setProperty("class", "DatePickerMonospace")
        status_layout.addWidget(self.status_text)

        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)

        # Connect signals
        source_browse_button.clicked.connect(self._browse_source)
        self.sort_button.clicked.connect(self._start_sorting)

        # Set main layout
        self.setLayout(main_layout)

    def _create_header(self, layout: QVBoxLayout) -> None:
        """Create the enhanced header section."""
        header = QLabel("🗂️ File Sorter - Organize Files by Type")
        header.setProperty("class", "AppHeader")
        layout.addWidget(header)

    def _browse_source(self) -> None:
        """Opens a file dialog to select source folder and updates ViewModel"""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Source Folder")
        if folder_path:
            self.view_model.source_directory = folder_path  # Update ViewModel
            self.directory_selected.emit(folder_path)  # Emit signal with selected path

    def _start_sorting(self) -> None:
        """Starts the file sorting process via the ViewModel"""
        self.view_model.start_sorting()  # Delegate to ViewModel

    def _update_ui(self) -> None:
        """Updates UI elements based on ViewModel state"""
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
