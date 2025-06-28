import logging

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
from goesvfi.gui_components.update_manager import register_update, request_update

LOGGER = logging.getLogger(__name__)


class DateSorterTab(QWidget):
    directory_selected = pyqtSignal(str)  # Signal emitted when a directory is selected

    # Modified __init__ to accept a ViewModel instance
    def __init__(self, view_model: DateSorterViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        if not isinstance(view_model, DateSorterViewModel):
            msg = "view_model must be an instance of DateSorterViewModel"
            raise TypeError(msg)

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

        # Options Group with enhanced styling
        options_group = QGroupBox(self.tr("⚙️ Analysis Options"))
        options_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        # Use default qt-material styling for QGroupBox
        options_layout = QGridLayout()
        options_layout.setContentsMargins(10, 15, 10, 10)
        options_layout.setSpacing(8)

        interval_label = QLabel(self.tr("🕰️ Time Interval Detection:"))
        interval_label.setProperty("class", "StandardLabel")

        interval_info = QLabel(self.tr("✨ Automatic interval detection will be used"))
        interval_info.setProperty("class", "StatusInfo")

        options_layout.addWidget(interval_label, 0, 0)
        options_layout.addWidget(interval_info, 0, 1, 1, 2)
        options_group.setLayout(options_layout)
        main_layout.addWidget(options_group)

        # Actions Group with enhanced styling
        actions_group = QGroupBox(self.tr("🚀 Actions"))
        actions_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        # Use default qt-material styling for QGroupBox
        actions_layout = QVBoxLayout()
        actions_layout.setContentsMargins(10, 15, 10, 10)
        actions_layout.setSpacing(8)

        # Scan Button with enhanced styling
        self.scan_button = QPushButton(self.tr("🔍 Scan Folder"))
        self.scan_button.setFixedHeight(40)
        self.scan_button.setProperty("class", "StartButton")
        actions_layout.addWidget(self.scan_button)
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
        self.progress_bar.setFormat("%p% - Processing...")
        self.progress_bar.setProperty("class", "DataProgress")
        status_layout.addWidget(self.progress_bar)

        # Status Text Display with enhanced styling
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMinimumHeight(200)
        self.status_text.setProperty("class", "DatePickerMonospace")
        status_layout.addWidget(self.status_text)

        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group, 1)  # Give status area more vertical space

        # Connect signals
        source_browse_button.clicked.connect(self._browse_source)
        self.scan_button.clicked.connect(self._start_scan)

        # Set main layout
        self.setLayout(main_layout)

        # Setup UpdateManager integration
        self._setup_update_manager()

        # Register observer with ViewModel
        self.view_model.set_observer(self._update_ui_via_manager)
        self.request_ui_update()  # Initial UI update

    def _create_header(self, layout: QVBoxLayout) -> None:
        """Create the enhanced header section."""
        header = QLabel("🗺️ Date Sorter - Organize Files by Date")
        header.setProperty("class", "AppHeader")
        layout.addWidget(header)

    def _browse_source(self) -> None:
        """Opens a dialog to select the source folder and updates the ViewModel."""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Source Folder")
        if folder_path:
            self.view_model.source_directory = folder_path
            LOGGER.info("Selected source folder: %s", folder_path)
            self.directory_selected.emit(folder_path)  # Emit signal with selected path

    def _start_scan(self) -> None:
        """Calls the start scan command on the ViewModel."""
        if self.view_model.can_start_sorting:
            self.view_model.start_sorting()
        else:
            # This case should ideally be handled by the ViewModel's can_execute
            # but adding a fallback message here for clarity.
            QMessageBox.warning(self, "Action Not Allowed", "Cannot start scan at this time.")

    def _setup_update_manager(self) -> None:
        """Set up UpdateManager integration for batched UI updates."""
        # Register UI update operations
        register_update("date_sorter_ui", self._update_ui, priority=2)
        register_update("date_sorter_progress", self._update_progress_only, priority=1)
        register_update("date_sorter_status", self._update_status_only, priority=2)

        LOGGER.info("DateSorterTab integrated with UpdateManager")

    def _update_ui_via_manager(self) -> None:
        """Observer callback that triggers batched UI update."""
        self.request_ui_update()

    def _update_progress_only(self) -> None:
        """Update only progress elements."""
        self.progress_bar.setValue(int(self.view_model.progress_percentage))
        if self.view_model.progress_percentage > 0:
            self.progress_bar.setFormat(f"{self.view_model.progress_percentage:.1f}%")
        else:
            self.progress_bar.setFormat("Ready")

    def _update_status_only(self) -> None:
        """Update only status text."""
        self.status_text.setPlainText(self.view_model.status_message)
        # Auto-scroll status text to bottom
        v_scrollbar: QScrollBar | None = self.status_text.verticalScrollBar()
        if v_scrollbar:
            v_scrollbar.setValue(v_scrollbar.maximum())
        self.scan_button.setEnabled(self.view_model.can_start_sorting)

    def request_ui_update(self, update_type: str = "ui") -> None:
        """Request UI updates through UpdateManager.

        Args:
            update_type: Type of update ('ui', 'progress', 'status')
        """
        if update_type == "ui":
            request_update("date_sorter_ui")
        elif update_type == "progress":
            request_update("date_sorter_progress")
        elif update_type == "status":
            request_update("date_sorter_status")

    def _update_ui(self) -> None:
        """Updates the UI elements based on the ViewModel's state."""
        self.source_line_edit.setText(self.view_model.source_directory)
        self.status_text.setPlainText(self.view_model.status_message)  # Use setPlainText to replace content
        self.progress_bar.setValue(int(self.view_model.progress_percentage))
        self.scan_button.setEnabled(self.view_model.can_start_sorting)

        # Auto-scroll status text to bottom
        v_scrollbar: QScrollBar | None = self.status_text.verticalScrollBar()
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
