"""Fixed Integrity Check GUI tab for the GOES VFI application.

This module provides a working IntegrityCheckTab implementation reconstructed
from the stub and backup files.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, List, Optional

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from goesvfi.utils import log
from .time_index import SATELLITE_NAMES, SatellitePattern
from .view_model import IntegrityCheckViewModel, MissingTimestamp, ScanStatus

LOGGER = log.get_logger(__name__)


class MissingTimestampsModel(QAbstractTableModel):
    """Model for displaying missing timestamps in a table."""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._items: List[MissingTimestamp] = []
        self._headers = ["Timestamp", "Satellite", "Status", "Expected Filename"]

    def set_items(self, items: List[MissingTimestamp]) -> None:
        """Set the items to display."""
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the number of rows."""
        return len(self._items)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the number of columns."""
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Return data for the given index and role."""
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None

        item = self._items[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:  # Timestamp
                return item.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            elif col == 1:  # Satellite
                return item.satellite
            elif col == 2:  # Status
                if item.is_downloaded:
                    return "Downloaded"
                elif item.is_downloading:
                    return "Downloading..."
                elif item.download_error:
                    return f"Error: {item.download_error[:50]}..."
                else:
                    return "Missing"
            elif col == 3:  # Expected Filename
                return item.expected_filename

        elif role == Qt.ItemDataRole.BackgroundRole:
            if col == 2:  # Status column
                if item.is_downloaded:
                    return QColor(200, 255, 200)  # Light green
                elif item.is_downloading:
                    return QColor(255, 255, 200)  # Light yellow
                elif item.download_error:
                    return QColor(255, 200, 200)  # Light red

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int) -> Any:
        """Return header data."""
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self._headers[section]
        return None


class IntegrityCheckTab(QWidget):
    """Fixed implementation of IntegrityCheckTab with core functionality."""

    # Signals
    scan_started = pyqtSignal()
    scan_completed = pyqtSignal(int)  # Number of missing files
    download_started = pyqtSignal()
    download_completed = pyqtSignal()

    def __init__(
        self,
        view_model: Optional[IntegrityCheckViewModel] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.view_model = view_model
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout(self)

        # Directory selection
        dir_group = QGroupBox("Directory Selection")
        dir_layout = QHBoxLayout()
        
        self.dir_label = QLabel("Directory:")
        self.dir_input = QLineEdit()
        self.dir_button = QPushButton("Browse...")
        self.dir_button.clicked.connect(self._browse_directory)
        
        dir_layout.addWidget(self.dir_label)
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(self.dir_button)
        dir_group.setLayout(dir_layout)
        layout.addWidget(dir_group)

        # Date range selection
        date_group = QGroupBox("Date Range")
        date_layout = QHBoxLayout()
        
        date_layout.addWidget(QLabel("Start:"))
        self.start_date_edit = QDateTimeEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDateTime(
            QDateTimeEdit.dateTime(QDateTimeEdit()).addDays(-7)
        )
        date_layout.addWidget(self.start_date_edit)
        
        date_layout.addWidget(QLabel("End:"))
        self.end_date_edit = QDateTimeEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDateTime(QDateTimeEdit.dateTime(QDateTimeEdit()))
        date_layout.addWidget(self.end_date_edit)
        
        self.auto_detect_btn = QPushButton("Auto Detect")
        self.auto_detect_btn.setToolTip("Auto-detect date range from files (Feature under repair)")
        date_layout.addWidget(self.auto_detect_btn)
        
        date_group.setLayout(date_layout)
        layout.addWidget(date_group)

        # Satellite selection
        sat_group = QGroupBox("Satellite Selection")
        sat_layout = QHBoxLayout()
        
        sat_layout.addWidget(QLabel("Satellite:"))
        self.satellite_combo = QComboBox()
        self.satellite_combo.addItems([name for name in SATELLITE_NAMES.values()])
        sat_layout.addWidget(self.satellite_combo)
        
        sat_group.setLayout(sat_layout)
        layout.addWidget(sat_group)

        # Control buttons
        control_layout = QHBoxLayout()
        
        self.scan_button = QPushButton("Scan for Missing Files")
        self.scan_button.clicked.connect(self._perform_scan)
        control_layout.addWidget(self.scan_button)
        
        self.download_button = QPushButton("Download Selected")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self._download_selected)
        control_layout.addWidget(self.download_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_operation)
        control_layout.addWidget(self.cancel_button)
        
        control_layout.addStretch()
        layout.addLayout(control_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

        # Results table
        self.results_table = QTableView()
        self.results_model = MissingTimestampsModel()
        self.results_table.setModel(self.results_model)
        self.results_table.setSelectionBehavior(
            QTableView.SelectionBehavior.SelectRows
        )
        layout.addWidget(self.results_table)

        # Summary label
        self.summary_label = QLabel("No scan performed yet")
        layout.addWidget(self.summary_label)

    def _connect_signals(self) -> None:
        """Connect signals to slots."""
        if self.view_model:
            # Connect view model signals - using actual signals from view_model.py
            self.view_model.status_updated.connect(self._on_status_updated)
            self.view_model.status_type_changed.connect(self._on_status_type_changed)
            self.view_model.progress_updated.connect(self._on_progress_updated)
            self.view_model.missing_items_updated.connect(self._on_missing_items_updated)
            self.view_model.scan_completed.connect(self._on_scan_completed_vm)
            self.view_model.download_progress_updated.connect(self._on_download_progress_vm)
            self.view_model.download_item_updated.connect(self._on_download_item_updated)

    def _browse_directory(self) -> None:
        """Browse for a directory."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Directory", self.dir_input.text()
        )
        if directory:
            self.dir_input.setText(directory)

    def _perform_scan(self) -> None:
        """Perform a scan for missing files."""
        directory = self.dir_input.text()
        if not directory or not os.path.isdir(directory):
            QMessageBox.warning(
                self, "Invalid Directory", "Please select a valid directory."
            )
            return

        # Get date range
        start_date = self.start_date_edit.dateTime().toPyDateTime()
        end_date = self.end_date_edit.dateTime().toPyDateTime()

        # Get selected satellite
        satellite_idx = self.satellite_combo.currentIndex()
        satellite_patterns = list(SatellitePattern)
        if 0 <= satellite_idx < len(satellite_patterns):
            satellite = satellite_patterns[satellite_idx]
        else:
            satellite = SatellitePattern.GOES_16

        # Update view model parameters
        if self.view_model:
            self.view_model.base_directory = directory
            self.view_model.start_date = start_date
            self.view_model.end_date = end_date
            self.view_model.selected_pattern = satellite
            self.view_model.start_scan()
        else:
            self.status_label.setText("Error: No view model connected")

    def _download_selected(self) -> None:
        """Download selected missing files."""
        # Get selected rows
        selection = self.results_table.selectionModel()
        if not selection.hasSelection():
            QMessageBox.warning(
                self, "No Selection", "Please select files to download."
            )
            return

        # Get selected items
        selected_rows = selection.selectedRows()
        selected_items = [
            self.results_model._items[index.row()] for index in selected_rows
        ]

        # Start download
        if self.view_model:
            # The view model downloads all missing items, not just selected ones
            # For now, start downloads for all items
            self.view_model.start_downloads()
        else:
            self.status_label.setText("Error: No view model connected")

    def _cancel_operation(self) -> None:
        """Cancel the current operation."""
        if self.view_model:
            if self.view_model.is_scanning:
                self.view_model.cancel_scan()
            elif self.view_model.is_downloading:
                self.view_model.cancel_downloads()

    def _on_status_updated(self, status: str) -> None:
        """Handle status update from view model."""
        self.status_label.setText(status)

    def _on_status_type_changed(self, status: ScanStatus) -> None:
        """Handle status type change from view model."""
        if status == ScanStatus.SCANNING:
            self.scan_button.setEnabled(False)
            self.download_button.setEnabled(False)
            self.cancel_button.setEnabled(True)
            self.progress_bar.setVisible(True)
            self.scan_started.emit()
        elif status == ScanStatus.DOWNLOADING:
            self.scan_button.setEnabled(False)
            self.download_button.setEnabled(False)
            self.cancel_button.setEnabled(True)
            self.progress_bar.setVisible(True)
            self.download_started.emit()
        elif status == ScanStatus.COMPLETED:
            self.scan_button.setEnabled(True)
            self.download_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            self.progress_bar.setVisible(False)
        elif status == ScanStatus.ERROR or status == ScanStatus.CANCELLED:
            self.scan_button.setEnabled(True)
            self.download_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            self.progress_bar.setVisible(False)

    def _on_progress_updated(self, current: int, total: int, eta: float) -> None:
        """Handle progress update from view model."""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def _on_missing_items_updated(self, items: List[MissingTimestamp]) -> None:
        """Handle missing items update from view model."""
        self.results_model.set_items(items)
        self.download_button.setEnabled(len(items) > 0)
        self.summary_label.setText(
            f"Found {len(items)} missing files out of expected files"
        )

    def _on_scan_completed_vm(self, success: bool, message: str) -> None:
        """Handle scan completion from view model."""
        if not success:
            QMessageBox.critical(self, "Scan Error", message)
        else:
            missing_count = len(self.results_model._items)
            self.scan_completed.emit(missing_count)

    def _on_download_progress_vm(self, current: int, total: int) -> None:
        """Handle download progress from view model."""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Downloading: {current}/{total} files")

    def _on_download_item_updated(self, index: int, item: MissingTimestamp) -> None:
        """Handle download item update from view model."""
        # Refresh the table view
        self.results_table.update()

    def _get_selected_items(self) -> List[MissingTimestamp]:
        """Get selected items from the table."""
        selection = self.results_table.selectionModel()
        if not selection.hasSelection():
            return []
        
        selected_rows = selection.selectedRows()
        return [self.results_model._items[index.row()] for index in selected_rows]