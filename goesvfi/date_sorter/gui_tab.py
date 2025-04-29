import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QFileDialog, QMessageBox,
    QProgressBar, QGroupBox, QGridLayout, QTextEdit, QSizePolicy, QScrollBar
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from goesvfi.date_sorter import sorter # Import the sorter module
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable

LOGGER = logging.getLogger(__name__)

class ScannerWorker(QThread):
    """Worker thread to run the DateSorter logic."""
    progress = pyqtSignal(int)  # For updating progress bar (0-100%)
    status = pyqtSignal(str)    # For status messages
    finished = pyqtSignal(str)  # For completion message
    error = pyqtSignal(str)     # For error handling

    def __init__(self, source_path: str) -> None:
        super().__init__()
        self.source_path = source_path

    def run(self) -> None:
        try:
            # Change working directory to source path for scan
            import os
            original_dir = os.getcwd()
            os.chdir(self.source_path)
            
            # Progress callback to handle both percentage and text status
            def progress_handler(percent):
                self.progress.emit(percent)
                
            # Status callback to emit text messages
            def status_handler(message):
                self.status.emit(message)
                
            # Call the main function from sorter.py, passing callbacks
            sorter.main(
                interactive=False, # Disable interactive mode
                progress_callback=progress_handler,
                status_callback=status_handler,
                log_callback=None # We can add a log callback later if needed
            )
            
            # Restore original working directory
            os.chdir(original_dir)
            
            self.finished.emit("Scanning and analysis complete!")
        except Exception as e:
            self.error.emit(f"Error during scanning: {str(e)}")

class DateSorterTab(QWidget):
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

        # Options Group
        options_group = QGroupBox("Analysis Options")
        options_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        options_layout = QGridLayout()
        options_layout.setContentsMargins(10, 15, 10, 10)
        options_layout.setSpacing(8)

        interval_label = QLabel("Time Interval Detection:")
        interval_info = QLabel("(Automatic interval detection will be used)")
        interval_info.setStyleSheet("color: #666; font-style: italic;")
        
        options_layout.addWidget(interval_label, 0, 0)
        options_layout.addWidget(interval_info, 0, 1, 1, 2)
        options_group.setLayout(options_layout)
        main_layout.addWidget(options_group)

        # Actions Group
        actions_group = QGroupBox("Actions")
        actions_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        actions_layout = QVBoxLayout()
        actions_layout.setContentsMargins(10, 15, 10, 10)
        actions_layout.setSpacing(8)

        # Scan Button
        self.scan_button = QPushButton("Scan Folder")
        self.scan_button.setFixedHeight(30)
        actions_layout.addWidget(self.scan_button)
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
        self.progress_bar.setFormat("%p%")
        status_layout.addWidget(self.progress_bar)
        
        # Status Text Display
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMinimumHeight(200)
        self.status_text.setStyleSheet("background-color: #f5f5f5; font-family: monospace;")
        status_layout.addWidget(self.status_text)

        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group, 1)  # Give status area more vertical space

        # Connect signals
        source_browse_button.clicked.connect(self._browse_source)
        self.scan_button.clicked.connect(self._start_scan)

        # Set main layout
        self.setLayout(main_layout)

    def _browse_source(self) -> None:
        """Opens a dialog to select the source folder."""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Source Folder")
        if folder_path:
            self.source_line_edit.setText(folder_path)
            LOGGER.info(f"Selected source folder: {folder_path}")

    def _start_scan(self) -> None:
        """Starts the scanning process in a background thread."""
        source_path = self.source_line_edit.text()
        if not source_path:
            QMessageBox.warning(self, "Input Error", "Please select a source folder.")
            return

        # Clear previous logs and reset progress
        self.status_text.clear()
        self.progress_bar.setValue(0)
        self._add_status_message("Starting date scanning operation...")
        self._add_status_message(f"Source folder: {source_path}")
        
        LOGGER.info(f"Starting scan for folder: {source_path}")
        self.scan_button.setEnabled(False) # Disable button while scanning

        self.worker = ScannerWorker(source_path)
        self.worker.progress.connect(self._update_progress)
        self.worker.status.connect(self._update_status)
        self.worker.finished.connect(self._on_scan_finished)
        self.worker.error.connect(self._handle_error)
        self.worker.start()

    def _update_progress(self, percent: int) -> None:
        """Updates the progress bar."""
        LOGGER.info(f"Progress: {percent}%")
        self.progress_bar.setValue(percent)

    def _update_status(self, message: str) -> None:
        """Updates the status text with messages from worker."""
        LOGGER.info(f"Status: {message}")
        self._add_status_message(message)

    def _add_status_message(self, message: str) -> None:
        """Adds a new message to the status text area with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.append(f"[{timestamp}] {message}")
        # Auto-scroll to bottom
        v_scrollbar: Optional[QScrollBar] = self.status_text.verticalScrollBar()
        if v_scrollbar:
            v_scrollbar.setValue(v_scrollbar.maximum())

    def _on_scan_finished(self, message: str) -> None:
        """Handles the completion of the scanning process."""
        LOGGER.info(f"Scan finished: {message}")
        self._add_status_message(f"✓ {message}")
        QMessageBox.information(self, "Scan Complete", message)
        self.progress_bar.setValue(100)
        self.scan_button.setEnabled(True)

    def _handle_error(self, message: str) -> None:
        """Handles errors during the scanning process."""
        LOGGER.error(f"Scan error: {message}")
        self._add_status_message(f"❌ ERROR: {message}")
        QMessageBox.critical(self, "Scan Error", message)
        self.scan_button.setEnabled(True)