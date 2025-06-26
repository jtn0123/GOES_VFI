import logging
from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollBar,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from goesvfi.date_sorter.view_model import DateSorterViewModel  # Import the ViewModel

LOGGER = logging.getLogger(__name__)


class DateSorterTab(QWidget):
    directory_selected = pyqtSignal(str)  # Signal emitted when a directory is selected

    # Modified __init__ to accept a ViewModel instance
    def __init__(self, view_model: DateSorterViewModel, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        if not isinstance(view_model, DateSorterViewModel):
            pass
            raise TypeError("view_model must be an instance of DateSorterViewModel")

        self.view_model = view_model  # Use the provided ViewModel

        # Main Layout with enhanced styling
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Add enhanced header
        self._create_header(main_layout)

        # Source Group with enhanced styling
        source_group = QGroupBox(self.tr("📁 Source Directory"))
        source_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        source_group.setStyleSheet(
            """
            QGroupBox {
                background-color: #2d2d2d;
                border: 2px solid #454545;
                border-radius: 8px;
                font-weight: bold;
                font-size: 12px;
                color: #f0f0f0;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #ffffff;
            }
            """
        )
        source_layout = QGridLayout()
        source_layout.setContentsMargins(10, 15, 10, 10)
        source_layout.setSpacing(8)

        source_label = QLabel(self.tr("📂 Folder:"))
        source_label.setStyleSheet("font-weight: bold;")

        self.source_line_edit = QLineEdit()
        self.source_line_edit.setStyleSheet(
            """
            QLineEdit {
                padding: 8px 12px;
                background-color: #3a3a3a;
                border: 2px solid #555555;
                border-radius: 6px;
                color: #f0f0f0;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #4a6fa5;
            }
            """
        )

        source_browse_button = QPushButton(self.tr("🔍 Browse..."))
        source_browse_button.setFixedWidth(120)
        source_browse_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #5a7fb5;
            }
            QPushButton:pressed {
                background-color: #3a5f95;
            }
            """
        )

        source_layout.addWidget(source_label, 0, 0)
        source_layout.addWidget(self.source_line_edit, 0, 1)
        source_layout.addWidget(source_browse_button, 0, 2)
        source_group.setLayout(source_layout)
        main_layout.addWidget(source_group)

        # Options Group with enhanced styling
        options_group = QGroupBox(self.tr("⚙️ Analysis Options"))
        options_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        options_group.setStyleSheet(
            """
            QGroupBox {
                background-color: #2d2d2d;
                border: 2px solid #454545;
                border-radius: 8px;
                font-weight: bold;
                font-size: 12px;
                color: #f0f0f0;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #ffffff;
            }
            """
        )
        options_layout = QGridLayout()
        options_layout.setContentsMargins(10, 15, 10, 10)
        options_layout.setSpacing(8)

        interval_label = QLabel(self.tr("🕰️ Time Interval Detection:"))
        interval_label.setStyleSheet("font-weight: bold;")

        interval_info = QLabel(self.tr("✨ Automatic interval detection will be used"))
        interval_info.setStyleSheet(
            "color: #66aaff; font-style: italic; padding: 4px 8px; " "background-color: #2a2a2a; border-radius: 4px;"
        )

        options_layout.addWidget(interval_label, 0, 0)
        options_layout.addWidget(interval_info, 0, 1, 1, 2)
        options_group.setLayout(options_layout)
        main_layout.addWidget(options_group)

        # Actions Group with enhanced styling
        actions_group = QGroupBox(self.tr("🚀 Actions"))
        actions_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        actions_group.setStyleSheet(
            """
            QGroupBox {
                background-color: #2d2d2d;
                border: 2px solid #454545;
                border-radius: 8px;
                font-weight: bold;
                font-size: 12px;
                color: #f0f0f0;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #ffffff;
            }
            """
        )
        actions_layout = QVBoxLayout()
        actions_layout.setContentsMargins(10, 15, 10, 10)
        actions_layout.setSpacing(8)

        # Scan Button with enhanced styling
        self.scan_button = QPushButton(self.tr("🔍 Scan Folder"))
        self.scan_button.setFixedHeight(40)
        self.scan_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #5a7fb5;
            }
            QPushButton:pressed {
                background-color: #3a5f95;
            }
            QPushButton:disabled {
                background-color: #6a6a6a;
                color: #aaaaaa;
            }
            """
        )
        actions_layout.addWidget(self.scan_button)
        actions_group.setLayout(actions_layout)
        main_layout.addWidget(actions_group)

        # Status Group with enhanced styling
        status_group = QGroupBox(self.tr("📊 Status & Progress"))
        status_group.setStyleSheet(
            """
            QGroupBox {
                background-color: #2d2d2d;
                border: 2px solid #454545;
                border-radius: 8px;
                font-weight: bold;
                font-size: 12px;
                color: #f0f0f0;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #ffffff;
            }
            """
        )
        status_layout = QVBoxLayout()
        status_layout.setContentsMargins(10, 15, 10, 10)
        status_layout.setSpacing(10)

        # Progress Bar with enhanced styling
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - Processing...")
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                border: 2px solid #555555;
                border-radius: 8px;
                background-color: #3a3a3a;
                text-align: center;
                font-weight: bold;
                color: #ffffff;
                padding: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a6fa5, stop:1 #3a5f95);
                border-radius: 6px;
            }
            """
        )
        status_layout.addWidget(self.progress_bar)

        # Status Text Display with enhanced styling
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMinimumHeight(200)
        self.status_text.setStyleSheet(
            """
            QTextEdit {
                background-color: #1a1a1a;
                border: 2px solid #454545;
                border-radius: 6px;
                color: #f0f0f0;
                font-family: 'Courier New', 'DejaVu Sans Mono', monospace;
                font-size: 11px;
                padding: 8px;
                selection-background-color: #4a6fa5;
            }
            QScrollBar:vertical {
                background-color: #2d2d2d;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #555555;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #666666;
            }
            """
        )
        status_layout.addWidget(self.status_text)

        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group, 1)  # Give status area more vertical space

        # Connect signals
        source_browse_button.clicked.connect(self._browse_source)
        self.scan_button.clicked.connect(self._start_scan)

        # Set main layout
        self.setLayout(main_layout)

        # Register observer with ViewModel
        self.view_model.set_observer(self._update_ui)
        self._update_ui()  # Initial UI update

    def _create_header(self, layout: QVBoxLayout) -> None:
        """Create the enhanced header section."""
        header = QLabel("🗺️ Date Sorter - Organize Files by Date")
        header.setStyleSheet(
            """
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #ffffff;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a6fa5, stop:0.5 #3a5f95, stop:1 #2a4f85);
                padding: 12px 16px;
                border-radius: 8px;
                margin-bottom: 10px;
                border: 2px solid #5a7fb5;
            }
            """
        )
        layout.addWidget(header)

    def _browse_source(self) -> None:
        """Opens a dialog to select the source folder and updates the ViewModel."""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Source Folder")
        if folder_path:
            pass
            self.view_model.source_directory = folder_path
            LOGGER.info("Selected source folder: %s", folder_path)
            self.directory_selected.emit(folder_path)  # Emit signal with selected path

    def _start_scan(self) -> None:
        """Calls the start scan command on the ViewModel."""
        if self.view_model.can_start_sorting:
            pass
            self.view_model.start_sorting()
        else:
            # This case should ideally be handled by the ViewModel's can_execute
            # but adding a fallback message here for clarity.
            QMessageBox.warning(self, "Action Not Allowed", "Cannot start scan at this time.")

    def _update_ui(self) -> None:
        """Updates the UI elements based on the ViewModel's state."""
        self.source_line_edit.setText(self.view_model.source_directory)
        self.status_text.setPlainText(self.view_model.status_message)  # Use setPlainText to replace content
        self.progress_bar.setValue(int(self.view_model.progress_percentage))
        self.scan_button.setEnabled(self.view_model.can_start_sorting)

        # Auto-scroll status text to bottom
        v_scrollbar: Optional[QScrollBar] = self.status_text.verticalScrollBar()
        if v_scrollbar:
            v_scrollbar.setValue(v_scrollbar.maximum())

        # Update progress bar format based on progress
        if self.view_model.progress_percentage > 0:
            self.progress_bar.setFormat(f"%p% - {self.view_model.status_message[:30]}...")
        else:
            self.progress_bar.setFormat("Ready to scan...")

        # Update button text based on state
        if self.view_model.progress_percentage > 0 and self.view_model.progress_percentage < 100:
            self.scan_button.setText("⏸️ Scanning...")
        else:
            self.scan_button.setText("🔍 Scan Folder")
