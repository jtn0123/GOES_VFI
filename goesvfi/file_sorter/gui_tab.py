import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QFileDialog, QMessageBox,
    QProgressBar, QGroupBox, QGridLayout, QTextEdit, QSizePolicy, QScrollBar, QCheckBox, QComboBox
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from goesvfi.file_sorter.sorter import FileSorter, DuplicateMode
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, Tuple

LOGGER = logging.getLogger(__name__)

class FileSorterTab(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Source Group
        source_group = QGroupBox("Source")
        source_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        source_layout = QGridLayout()
        source_layout.setContentsMargins(10, 15, 10, 10)
        source_layout.setSpacing(8)

        source_label = QLabel("Folder:")
        self.source_line_edit = QLineEdit()
        source_browse_button = QPushButton("Browse...")
        source_browse_button.setFixedWidth(100)
        
        source_layout.addWidget(source_label, 0, 0)
        source_layout.addWidget(self.source_line_edit, 0, 1)
        source_layout.addWidget(source_browse_button, 0, 2)
        source_group.setLayout(source_layout)
        main_layout.addWidget(source_group)

        # Destination Group
        destination_group = QGroupBox("Destination")
        destination_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        destination_layout = QGridLayout()
        destination_layout.setContentsMargins(10, 15, 10, 10)
        destination_layout.setSpacing(8)

        destination_label = QLabel("Output Folder:")
        destination_info = QLabel("(Files will be sorted to a 'converted' subfolder)")
        destination_info.setStyleSheet("color: #666; font-style: italic;")
        
        destination_layout.addWidget(destination_label, 0, 0)
        destination_layout.addWidget(destination_info, 0, 1, 1, 2)
        destination_group.setLayout(destination_layout)
        main_layout.addWidget(destination_group)

        # Options Group
        options_group = QGroupBox("Options")
        options_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        options_layout = QVBoxLayout()
        options_layout.setContentsMargins(10, 15, 10, 10)
        options_layout.setSpacing(8)

        # Dry Run Checkbox
        self.dry_run_checkbox = QCheckBox("Dry Run (Log actions without moving files)")
        options_layout.addWidget(self.dry_run_checkbox)

        # Duplicate Handling
        duplicate_label = QLabel("Duplicate Handling:")
        self.duplicate_combo = QComboBox()
        self.duplicate_combo.addItems(["Overwrite", "Skip", "Rename"])
        options_layout.addWidget(duplicate_label)
        options_layout.addWidget(self.duplicate_combo)

        options_group.setLayout(options_layout)
        main_layout.addWidget(options_group)

        # Actions Group
        actions_group = QGroupBox("Actions")
        actions_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        actions_layout = QVBoxLayout()
        actions_layout.setContentsMargins(10, 15, 10, 10)
        actions_layout.setSpacing(8)

        # Sort Button
        self.sort_button = QPushButton("Sort Files")
        self.sort_button.setFixedHeight(30)
        actions_layout.addWidget(self.sort_button)
        actions_group.setLayout(actions_layout)
        main_layout.addWidget(actions_group)

        # Status Group
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout()
        status_layout.setContentsMargins(10, 15, 10, 10)
        status_layout.setSpacing(10)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - %v of %m")
        status_layout.addWidget(self.progress_bar)
        
        # Status Text Display
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(150)
        self.status_text.setStyleSheet("background-color: #f5f5f5;")
        status_layout.addWidget(self.status_text)

        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)

        # Connect signals
        source_browse_button.clicked.connect(self._browse_source)
        self.sort_button.clicked.connect(self._start_sorting)

        # Set main layout
        self.setLayout(main_layout)

    def _browse_source(self) -> None:
        """Opens a file dialog to select source folder"""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Source Folder")
        if folder_path:
            self.source_line_edit.setText(folder_path)

    def _start_sorting(self) -> None:
        """Starts the file sorting process in a background thread"""
        source_path = self.source_line_edit.text()

        if not source_path:
            QMessageBox.warning(self, "Input Error", "Please select a source folder.")
            return

        # Calculate the output path (which will be a 'converted' subfolder)
        source_path_obj = Path(source_path)
        output_path = source_path_obj / "converted"
        
        LOGGER.info(f"Sorting started from {source_path}")
        LOGGER.info(f"Files will be sorted to {output_path}")

        # Clear previous logs and reset progress
        self.status_text.clear()
        self.progress_bar.setValue(0)
        self._add_status_message(f"Starting file sort operation from {source_path}")
        self._add_status_message(f"Files will be sorted to {output_path}")
        
        # Disable the sort button while processing
        self.sort_button.setEnabled(False)

        # Get options from UI
        dry_run = self.dry_run_checkbox.isChecked()
        # Map the string from the combo box to the DuplicateMode enum
        duplicate_mode_str = self.duplicate_combo.currentText()
        duplicate_mode = DuplicateMode[duplicate_mode_str.upper()] # Assuming enum members are uppercase

        # Create and start worker thread
        self.worker: SorterWorker = SorterWorker(source_path, dry_run, duplicate_mode)
        self.worker.progress.connect(self._update_progress)
        self.worker.finished.connect(self._on_sorting_finished)
        self.worker.error.connect(self._handle_error)
        self.worker.start()

    def _update_progress(self, percent: int, message: str) -> None:
        """Update both progress bar and status text"""
        LOGGER.info(f"Progress: {percent}% - {message}")
        
        # Update progress bar
        self.progress_bar.setValue(percent)
        
        # Update status text
        self._add_status_message(message)

    def _add_status_message(self, message: str) -> None:
        """Adds a new message to the status text area with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.append(f"[{timestamp}] {message}")
        # Auto-scroll to bottom
        v_scrollbar = self.status_text.verticalScrollBar()
        if v_scrollbar:
            v_scrollbar.setValue(v_scrollbar.maximum())

    def _on_sorting_finished(self, message: str) -> None:
        """Handle completion of sorting process"""
        LOGGER.info(f"Sorting finished: {message}")
        self._add_status_message(f"✓ {message}")
        QMessageBox.information(self, "Sorting Complete", message)
        self.progress_bar.setValue(100)
        self.sort_button.setEnabled(True)

    def _handle_error(self, message: str) -> None:
        """Handle errors during sorting"""
        LOGGER.error(f"Sorting error: {message}")
        self._add_status_message(f"❌ ERROR: {message}")
        QMessageBox.critical(self, "Sorting Error", message)
        self.sort_button.setEnabled(True)


class SorterWorker(QThread):
    """Worker thread for file sorting operations"""
    progress = pyqtSignal(int, str)  # Changed to emit both percent and message
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, source_path: str, dry_run: bool, duplicate_mode: DuplicateMode):
        super().__init__()
        self.source_path = source_path
        self.dry_run = dry_run
        self.duplicate_mode = duplicate_mode

    def run(self) -> None:
        try:
            # Create sorter instance with dry_run and duplicate_mode
            sorter = FileSorter(dry_run=self.dry_run, duplicate_mode=self.duplicate_mode)
            
            # Set progress callback to emit both percent and message
            def progress_callback(percent: int, message: str) -> None:
                self.progress.emit(percent, message)
            
            # Set the progress callback
            sorter.set_progress_callback(progress_callback)
            
            # Run the sort operation
            stats = sorter.sort_files(self.source_path)
            
            # Create success message with stats
            size_in_mb = round(stats['total_bytes'] / (1024 * 1024), 2)
            success_msg = (
                f"File sorting completed successfully.\n"
                f"Files copied: {stats['files_copied']}\n"
                f"Files skipped: {stats['files_skipped']}\n"
                f"Total data: {size_in_mb} MB\n"
                f"Duration: {stats['duration']}"
            )
            
            self.finished.emit(success_msg)
        except Exception as e:
            self.error.emit(f"An error occurred during sorting: {e}")