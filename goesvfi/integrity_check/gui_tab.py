"""GUI tab for integrity checking in the GOES VFI application.

This module provides the IntegrityCheckTab class, which implements the UI for
the Integrity Check feature in the GOES VFI application.
"""

import time
import os
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple, cast

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QPushButton, QProgressBar, QTableView, QHeaderView,
    QGroupBox, QCheckBox, QComboBox, QDateTimeEdit, QSpinBox,
    QFileDialog, QLineEdit, QTextEdit, QMessageBox, QSplitter,
    QScrollArea, QFrame, QSizePolicy, QTabWidget, QDialog,
    QDialogButtonBox, QStackedWidget, QApplication
)
from PyQt6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, QDateTime, QDate, QTime,
    pyqtSignal, QObject, QSize, QThreadPool, QThread, QRunnable,
    QSortFilterProxyModel, QTimer
)
from PyQt6.QtGui import (
    QColor, QPalette, QIcon, QFont, QPixmap, QBrush, QAction,
    QStandardItemModel, QStandardItem
)

from goesvfi.utils import log
from .view_model import IntegrityCheckViewModel, ScanStatus, MissingTimestamp
from .time_index import SatellitePattern, SATELLITE_NAMES

LOGGER = log.get_logger(__name__)


class MissingTimestampsModel(QAbstractTableModel):
    """Model for displaying missing timestamps in a table view."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: List[MissingTimestamp] = []
        self._headers = ["Timestamp", "Filename", "Status", "Path"]
        
    def rowCount(self, parent=QModelIndex()) -> int:
        """Return the number of rows in the model."""
        return len(self._items)
    
    def columnCount(self, parent=QModelIndex()) -> int:
        """Return the number of columns in the model."""
        return len(self._headers)
    
    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole) -> Any:
        """Return data for the specified index and role."""
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        
        item = self._items[index.row()]
        col = index.column()
        
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:  # Timestamp
                return item.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            elif col == 1:  # Filename
                return item.expected_filename
            elif col == 2:  # Status
                if item.is_downloaded:
                    return "Downloaded"
                elif item.is_downloading:
                    return "Downloading..."
                elif item.download_error:
                    return f"Error: {item.download_error}"
                else:
                    return "Missing"
            elif col == 3:  # Path
                if item.local_path:
                    return item.local_path
                else:
                    return ""
        
        elif role == Qt.ItemDataRole.BackgroundRole:
            if col == 2:  # Status column
                if item.is_downloaded:
                    return QColor(200, 255, 200)  # Light green
                elif item.download_error:
                    return QColor(255, 200, 200)  # Light red
                elif item.is_downloading:
                    return QColor(200, 200, 255)  # Light blue
            
        return None
    
    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole) -> Any:
        """Return header data for the specified section, orientation, and role."""
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self._headers[section]
        return None
    
    def setItems(self, items: List[MissingTimestamp]) -> None:
        """Set the items to be displayed in the model."""
        self.beginResetModel()
        self._items = items
        self.endResetModel()
    
    def updateItem(self, index: int, item: MissingTimestamp) -> None:
        """Update a specific item in the model."""
        if 0 <= index < len(self._items):
            self._items[index] = item
            top_left = self.index(index, 0)
            bottom_right = self.index(index, self.columnCount() - 1)
            self.dataChanged.emit(top_left, bottom_right)


class CacheInfoDialog(QDialog):
    """Dialog displaying cache statistics and management options."""
    
    def __init__(self, view_model: IntegrityCheckViewModel, parent=None):
        super().__init__(parent)
        
        self.view_model = view_model
        
        self.setWindowTitle("Cache Information")
        self.setMinimumWidth(500)
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Info group
        info_group = QGroupBox("Cache Statistics")
        info_layout = QFormLayout()
        
        self.scan_count_label = QLabel("0")
        self.missing_count_label = QLabel("0")
        self.cache_size_label = QLabel("0 MB")
        self.last_scan_label = QLabel("Never")
        self.cache_path_label = QLabel("")
        
        info_layout.addRow("Total Scans:", self.scan_count_label)
        info_layout.addRow("Missing Items:", self.missing_count_label)
        info_layout.addRow("Cache Size:", self.cache_size_label)
        info_layout.addRow("Last Scan:", self.last_scan_label)
        info_layout.addRow("Cache Path:", self.cache_path_label)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Management group
        management_group = QGroupBox("Cache Management")
        management_layout = QVBoxLayout()
        
        self.clear_cache_button = QPushButton("Clear Cache")
        self.clear_cache_button.clicked.connect(self._clear_cache)
        
        management_layout.addWidget(self.clear_cache_button)
        management_group.setLayout(management_layout)
        layout.addWidget(management_group)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Refresh stats
        self._refresh_stats()
    
    def _refresh_stats(self) -> None:
        """Refresh cache statistics displayed in the dialog."""
        stats = self.view_model.get_cache_stats()
        
        self.scan_count_label.setText(str(stats.get('scan_count', 0)))
        self.missing_count_label.setText(str(stats.get('missing_count', 0)))
        self.cache_size_label.setText(f"{stats.get('db_size_mb', 0)} MB")
        
        last_scan = stats.get('last_scan')
        if last_scan:
            self.last_scan_label.setText(last_scan.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            self.last_scan_label.setText("Never")
            
        self.cache_path_label.setText(stats.get('db_path', ''))
    
    def _clear_cache(self) -> None:
        """Clear the cache database."""
        reply = QMessageBox.question(
            self, 
            "Clear Cache",
            "Are you sure you want to clear the cache? This will delete all saved scan results.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.view_model.clear_cache()
            self._refresh_stats()


class IntegrityCheckTab(QWidget):
    """
    QWidget tab for verifying timestamp integrity and finding gaps in GOES imagery.
    
    This tab allows users to scan directories for satellite imagery, identify
    missing timestamps, and optionally download missing files from a remote source.
    """
    
    # Signal when directory is selected (for coordination with other tabs)
    directory_selected = pyqtSignal(str)
    
    def __init__(self, view_model: IntegrityCheckViewModel, parent=None):
        """
        Initialize the IntegrityCheckTab.
        
        Args:
            view_model: The ViewModel instance to use
            parent: Optional parent widget
        """
        super().__init__(parent)
        
        if not isinstance(view_model, IntegrityCheckViewModel):
            raise TypeError("view_model must be an instance of IntegrityCheckViewModel")
        
        self.view_model = view_model
        
        # Create UI components
        self._setup_ui()
        
        # Connect signals from view model
        self._connect_signals()
        
        # Initial UI update
        self._update_ui_from_view_model()
    
    def _setup_ui(self) -> None:
        """Set up the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        
        # Top section: Controls
        controls_section = QWidget()
        controls_layout = QHBoxLayout(controls_section)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        
        # Date range group
        date_group = QGroupBox("Date Range")
        date_layout = QFormLayout()
        
        # Start date
        self.start_date_edit = QDateTimeEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        self.start_date_edit.setDateTime(QDateTime(
            QDate(yesterday_start.year, yesterday_start.month, yesterday_start.day),
            QTime(yesterday_start.hour, yesterday_start.minute)
        ))
        date_layout.addRow("From:", self.start_date_edit)
        
        # End date
        self.end_date_edit = QDateTimeEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        yesterday_end = yesterday.replace(hour=23, minute=59, second=59, microsecond=0)
        self.end_date_edit.setDateTime(QDateTime(
            QDate(yesterday_end.year, yesterday_end.month, yesterday_end.day),
            QTime(yesterday_end.hour, yesterday_end.minute)
        ))
        date_layout.addRow("To:", self.end_date_edit)
        
        date_group.setLayout(date_layout)
        controls_layout.addWidget(date_group)
        
        # Options group
        options_group = QGroupBox("Options")
        options_layout = QFormLayout()
        
        # Interval
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setRange(0, 60)
        self.interval_spinbox.setValue(0)
        self.interval_spinbox.setSuffix(" min")
        self.interval_spinbox.setSpecialValueText("Auto-detect")
        options_layout.addRow("Interval:", self.interval_spinbox)
        
        # Satellite pattern
        self.satellite_combo = QComboBox()
        for pattern in SatellitePattern:
            self.satellite_combo.addItem(SATELLITE_NAMES[pattern], pattern.value)
        options_layout.addRow("Satellite:", self.satellite_combo)
        
        # Force rescan checkbox
        self.force_rescan_checkbox = QCheckBox("Force Rescan")
        self.force_rescan_checkbox.setToolTip("Ignore cached results and perform a new scan")
        options_layout.addRow("", self.force_rescan_checkbox)
        
        # Auto-download checkbox
        self.auto_download_checkbox = QCheckBox("Auto-Download Missing Files")
        self.auto_download_checkbox.setToolTip("Automatically download missing files after scan")
        options_layout.addRow("", self.auto_download_checkbox)
        
        options_group.setLayout(options_layout)
        controls_layout.addWidget(options_group)
        
        # Directory group
        directory_group = QGroupBox("Directory")
        directory_layout = QVBoxLayout()
        
        # Directory selection
        directory_select_layout = QHBoxLayout()
        self.directory_edit = QLineEdit()
        self.directory_edit.setReadOnly(True)
        self.directory_browse_button = QPushButton("Browse...")
        directory_select_layout.addWidget(self.directory_edit)
        directory_select_layout.addWidget(self.directory_browse_button)
        directory_layout.addLayout(directory_select_layout)
        
        # Scan button
        self.scan_button = QPushButton("Verify Integrity")
        self.scan_button.setMinimumHeight(40)
        self.scan_button.setStyleSheet("QPushButton { font-weight: bold; }")
        directory_layout.addWidget(self.scan_button)
        
        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        directory_layout.addWidget(self.cancel_button)
        
        directory_group.setLayout(directory_layout)
        controls_layout.addWidget(directory_group)
        
        main_layout.addWidget(controls_section)
        
        # Middle section: Progress and status
        progress_section = QWidget()
        progress_layout = QVBoxLayout(progress_section)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        # Status message
        self.status_label = QLabel("Ready to scan")
        self.status_label.setStyleSheet("QLabel { font-weight: bold; }")
        progress_layout.addWidget(self.status_label)
        
        main_layout.addWidget(progress_section)
        
        # Bottom section: Results table
        results_group = QGroupBox("Missing Timestamps")
        results_layout = QVBoxLayout()
        
        # Table view
        self.table_view = QTableView()
        self.table_model = MissingTimestampsModel()
        self.table_view.setModel(self.table_model)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table_view.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setAlternatingRowColors(True)
        results_layout.addWidget(self.table_view)
        
        # Action buttons
        actions_layout = QHBoxLayout()
        
        self.download_button = QPushButton("Download Missing Files")
        self.download_button.setEnabled(False)
        actions_layout.addWidget(self.download_button)
        
        self.export_button = QPushButton("Export Report")
        self.export_button.setEnabled(False)
        actions_layout.addWidget(self.export_button)
        
        self.cache_button = QPushButton("Cache Info")
        actions_layout.addWidget(self.cache_button)
        
        actions_layout.addStretch()
        results_layout.addLayout(actions_layout)
        
        results_group.setLayout(results_layout)
        main_layout.addWidget(results_group, 1)  # Give table stretch priority
        
        # Connect widget signals
        self.directory_browse_button.clicked.connect(self._browse_directory)
        self.scan_button.clicked.connect(self._start_scan)
        self.cancel_button.clicked.connect(self._cancel_operation)
        self.download_button.clicked.connect(self._download_missing)
        self.export_button.clicked.connect(self._export_report)
        self.cache_button.clicked.connect(self._show_cache_info)
        
        # Initialize date range to yesterday (full day)
        self._update_date_range_to_yesterday()
    
    def _connect_signals(self) -> None:
        """Connect signals from the view model."""
        self.view_model.status_updated.connect(self._update_status)
        self.view_model.status_type_changed.connect(self._update_status_type)
        self.view_model.progress_updated.connect(self._update_progress)
        self.view_model.missing_items_updated.connect(self._update_missing_items)
        self.view_model.scan_completed.connect(self._handle_scan_completed)
        self.view_model.download_progress_updated.connect(self._update_download_progress)
        self.view_model.download_item_updated.connect(self._update_download_item)
    
    def _update_ui_from_view_model(self) -> None:
        """Update UI elements with the current state from the view model."""
        # Directory
        self.directory_edit.setText(str(self.view_model.base_directory))
        
        # Date range
        start_dt = self.view_model.start_date
        self.start_date_edit.setDateTime(QDateTime(
            QDate(start_dt.year, start_dt.month, start_dt.day),
            QTime(start_dt.hour, start_dt.minute)
        ))
        
        end_dt = self.view_model.end_date
        self.end_date_edit.setDateTime(QDateTime(
            QDate(end_dt.year, end_dt.month, end_dt.day),
            QTime(end_dt.hour, end_dt.minute)
        ))
        
        # Options
        self.interval_spinbox.setValue(self.view_model.interval_minutes)
        
        # Find index for the selected pattern
        pattern_index = 0
        for i in range(self.satellite_combo.count()):
            if self.satellite_combo.itemData(i) == self.view_model.selected_pattern.value:
                pattern_index = i
                break
        self.satellite_combo.setCurrentIndex(pattern_index)
        
        # Checkboxes
        self.force_rescan_checkbox.setChecked(self.view_model.force_rescan)
        self.auto_download_checkbox.setChecked(self.view_model.auto_download)
        
        # Status and progress
        self.status_label.setText(self.view_model.status_message)
        self._update_button_states()
    
    def _update_button_states(self) -> None:
        """Update button enabled states based on the view model state."""
        is_scanning = self.view_model.is_scanning
        is_downloading = self.view_model.is_downloading
        has_missing_items = self.view_model.has_missing_items
        
        # Scan button enabled when not scanning or downloading
        self.scan_button.setEnabled(self.view_model.can_start_scan)
        
        # Cancel button enabled during scanning or downloading
        self.cancel_button.setEnabled(is_scanning or is_downloading)
        
        # Download button enabled when there are missing items and not currently downloading
        self.download_button.setEnabled(has_missing_items and not is_downloading)
        
        # Export button enabled when there are missing items
        self.export_button.setEnabled(has_missing_items)
    
    def _update_date_range_to_yesterday(self) -> None:
        """Update the date range to yesterday (full day)."""
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_end = yesterday.replace(hour=23, minute=59, second=59, microsecond=0)
        
        self.start_date_edit.setDateTime(QDateTime(
            QDate(yesterday_start.year, yesterday_start.month, yesterday_start.day),
            QTime(yesterday_start.hour, yesterday_start.minute)
        ))
        
        self.end_date_edit.setDateTime(QDateTime(
            QDate(yesterday_end.year, yesterday_end.month, yesterday_end.day),
            QTime(yesterday_end.hour, yesterday_end.minute)
        ))
        
        # Update view model
        self.view_model.start_date = yesterday_start
        self.view_model.end_date = yesterday_end
    
    def _browse_directory(self) -> None:
        """Open a dialog to select the base directory."""
        directory = QFileDialog.getExistingDirectory(self, "Select Directory", 
                                                    str(self.view_model.base_directory))
        if directory:
            self.view_model.base_directory = directory
            self.directory_edit.setText(directory)
            self.directory_selected.emit(directory)
    
    def _start_scan(self) -> None:
        """Start the scan operation."""
        # Update view model parameters from UI
        self.view_model.start_date = self.start_date_edit.dateTime().toPython()
        self.view_model.end_date = self.end_date_edit.dateTime().toPython()
        self.view_model.interval_minutes = self.interval_spinbox.value()
        
        pattern_value = self.satellite_combo.currentData()
        self.view_model.selected_pattern = SatellitePattern(pattern_value)
        
        self.view_model.force_rescan = self.force_rescan_checkbox.isChecked()
        self.view_model.auto_download = self.auto_download_checkbox.isChecked()
        
        # Start scan
        self.view_model.start_scan()
        
        # Update UI
        self._update_button_states()
    
    def _cancel_operation(self) -> None:
        """Cancel the ongoing operation."""
        if self.view_model.is_scanning:
            self.view_model.cancel_scan()
        elif self.view_model.is_downloading:
            self.view_model.cancel_downloads()
        
        self.status_label.setText("Cancelling...")
    
    def _download_missing(self) -> None:
        """Start downloading missing files."""
        if not self.view_model.has_missing_items:
            QMessageBox.information(self, "No Missing Files", 
                                   "There are no missing files to download.")
            return
        
        # Start downloads
        self.view_model.start_downloads()
        
        # Update UI
        self._update_button_states()
    
    def _export_report(self) -> None:
        """Export a report of missing timestamps."""
        if not self.view_model.has_missing_items:
            QMessageBox.information(self, "No Data", 
                                   "There are no missing files to export.")
            return
        
        # Get file path from user
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Report", 
            os.path.join(os.path.expanduser("~"), "missing_timestamps.csv"),
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            # Generate report
            with open(file_path, 'w') as f:
                # Write header
                f.write("Timestamp,Filename,Status,Path\n")
                
                # Write data
                for item in self.view_model.missing_items:
                    status = "Downloaded" if item.is_downloaded else "Missing"
                    if item.download_error:
                        status = f"Error: {item.download_error}"
                    
                    f.write(f"{item.timestamp.strftime('%Y-%m-%d %H:%M:%S')},"
                           f"{item.expected_filename},"
                           f"{status},"
                           f"{item.local_path}\n")
            
            QMessageBox.information(self, "Export Complete", 
                                   f"Report exported to {file_path}")
            
        except Exception as e:
            LOGGER.error(f"Error exporting report: {e}")
            QMessageBox.critical(self, "Export Error", 
                                f"Error exporting report: {e}")
    
    def _show_cache_info(self) -> None:
        """Show the cache information dialog."""
        dialog = CacheInfoDialog(self.view_model, self)
        dialog.exec()
    
    # --- Slot handlers for view model signals ---
    
    def _update_status(self, message: str) -> None:
        """Update the status message."""
        self.status_label.setText(message)
    
    def _update_status_type(self, status: ScanStatus) -> None:
        """Update the status type and button states."""
        self._update_button_states()
    
    def _update_progress(self, current: int, total: int, eta: float) -> None:
        """Update the progress bar."""
        progress_percent = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(progress_percent)
        
        # Format ETA if available
        if eta > 0:
            eta_minutes = int(eta / 60)
            eta_seconds = int(eta % 60)
            self.progress_bar.setFormat(f"{progress_percent}% - ETA: {eta_minutes}m {eta_seconds}s")
        else:
            self.progress_bar.setFormat(f"{progress_percent}%")
    
    def _update_missing_items(self, items: List[MissingTimestamp]) -> None:
        """Update the table model with missing items."""
        self.table_model.setItems(items)
        self._update_button_states()
    
    def _handle_scan_completed(self, success: bool, message: str) -> None:
        """Handle scan completion."""
        if success:
            # Reset progress bar to show 100%
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("100%")
            
            # Show success message
            if self.view_model.missing_count > 0:
                QMessageBox.information(
                    self, 
                    "Scan Complete", 
                    f"Found {self.view_model.missing_count} missing timestamps "
                    f"out of {self.view_model.total_expected} expected."
                )
            else:
                QMessageBox.information(
                    self,
                    "Scan Complete",
                    "No missing timestamps found. All files are present!"
                )
        else:
            # Show error message
            QMessageBox.critical(self, "Scan Error", message)
        
        # Update button states
        self._update_button_states()
    
    def _update_download_progress(self, current: int, total: int) -> None:
        """Update the progress bar for downloads."""
        progress_percent = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(progress_percent)
        self.progress_bar.setFormat(f"{progress_percent}% - {current}/{total} files")
    
    def _update_download_item(self, index: int, item: MissingTimestamp) -> None:
        """Update a specific item in the table model."""
        self.table_model.updateItem(index, item)
        
        # Process events to ensure UI updates immediately
        QApplication.processEvents()