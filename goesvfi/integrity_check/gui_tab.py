"""Fixed Integrity Check GUI tab for the GOES VFI application.

This module provides a working IntegrityCheckTab implementation reconstructed
from the stub and backup files.
"""

import os
from pathlib import Path
from typing import Any, List, Optional

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
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

    def rowCount(self, parent: Optional[QModelIndex] = None) -> int:
        """Return the number of rows."""
        return len(self._items)

    def columnCount(self, parent: Optional[QModelIndex] = None) -> int:
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
                return "Missing"
            elif col == 3:  # Expected Filename
                return item.expected_filename

        elif role == Qt.ItemDataRole.BackgroundRole:
            if col == 2:  # Status column - use theme-based colors
                if item.is_downloaded:
                    return QColor("#ccffcc")  # Success color from theme
                if item.is_downloading:
                    return QColor("#ffffcc")  # Warning color from theme
                if item.download_error:
                    return QColor("#ffcccc")  # Error color from theme

        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:  # type: ignore[override]
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

        # Create feedback manager for better user feedback
        from .enhanced_feedback import FeedbackManager

        self.feedback_manager = FeedbackManager()

        self._setup_ui()
        self._connect_signals()

        # Apply qt-material theme properties
        self.setProperty("class", "IntegrityCheckTab")

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout(self)

        # Directory selection
        dir_group = QGroupBox("Directory Selection")
        dir_layout = QHBoxLayout()

        self.dir_label = QLabel("Directory:")
        self.dir_label.setProperty("class", "FFmpegLabel")
        self.dir_input = QLineEdit()
        self.dir_button = QPushButton("Browse...")
        self.dir_button.setProperty("class", "DialogButton")
        self.dir_button.clicked.connect(self._browse_directory)

        dir_layout.addWidget(self.dir_label)
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(self.dir_button)
        dir_group.setLayout(dir_layout)
        layout.addWidget(dir_group)

        # Date range selection
        date_group = QGroupBox("Date Range")
        date_layout = QHBoxLayout()

        start_date_label = QLabel("Start:")
        start_date_label.setProperty("class", "FFmpegLabel")
        date_layout.addWidget(start_date_label)
        self.start_date_edit = QDateTimeEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDateTime(QDateTimeEdit.dateTime(QDateTimeEdit()).addDays(-7))
        date_layout.addWidget(self.start_date_edit)

        end_date_label = QLabel("End:")
        end_date_label.setProperty("class", "FFmpegLabel")
        date_layout.addWidget(end_date_label)
        self.end_date_edit = QDateTimeEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDateTime(QDateTimeEdit.dateTime(QDateTimeEdit()))
        date_layout.addWidget(self.end_date_edit)

        self.auto_detect_btn = QPushButton("Auto Detect")
        self.auto_detect_btn.setProperty("class", "DialogPrimaryButton")
        self.auto_detect_btn.setToolTip("Auto-detect date range from files in the selected directory")
        self.auto_detect_btn.clicked.connect(self._auto_detect_date_range)
        date_layout.addWidget(self.auto_detect_btn)

        date_group.setLayout(date_layout)
        layout.addWidget(date_group)

        # Satellite selection
        sat_group = QGroupBox("Satellite Selection")
        sat_layout = QHBoxLayout()

        satellite_label = QLabel("Satellite:")
        satellite_label.setProperty("class", "FFmpegLabel")
        sat_layout.addWidget(satellite_label)
        self.satellite_combo = QComboBox()
        self.satellite_combo.addItems(list(SATELLITE_NAMES.values()))
        sat_layout.addWidget(self.satellite_combo)

        sat_group.setLayout(sat_layout)
        layout.addWidget(sat_group)

        # Control buttons
        control_layout = QHBoxLayout()

        self.scan_button = QPushButton("Scan for Missing Files")
        self.scan_button.setProperty("class", "StartButton")
        self.scan_button.clicked.connect(self._perform_scan)
        control_layout.addWidget(self.scan_button)

        self.download_button = QPushButton("Download Selected")
        self.download_button.setProperty("class", "DialogPrimaryButton")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self._download_selected)
        control_layout.addWidget(self.download_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setProperty("class", "CancelButton")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_operation)
        control_layout.addWidget(self.cancel_button)

        control_layout.addStretch()
        layout.addLayout(control_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status label with theme properties
        self.status_label = QLabel("Ready")
        self.status_label.setProperty("class", "StatusLabel")
        layout.addWidget(self.status_label)

        # Results table with selection controls
        results_group = QGroupBox("Scan Results")
        results_layout = QVBoxLayout()

        # Selection controls
        selection_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setProperty("class", "DialogButton")
        self.select_all_btn.clicked.connect(self._select_all_items)
        selection_layout.addWidget(self.select_all_btn)

        self.select_none_btn = QPushButton("Select None")
        self.select_none_btn.setProperty("class", "DialogButton")
        self.select_none_btn.clicked.connect(self._select_no_items)
        selection_layout.addWidget(self.select_none_btn)

        selection_layout.addStretch()
        results_layout.addLayout(selection_layout)

        # Results table
        self.results_table = QTableView()
        self.results_model = MissingTimestampsModel()
        self.results_table.setModel(self.results_model)
        self.results_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QTableView.SelectionMode.MultiSelection)
        results_layout.addWidget(self.results_table)

        results_group.setLayout(results_layout)
        layout.addWidget(results_group)

        # Summary label
        self.summary_label = QLabel("No scan performed yet")
        layout.addWidget(self.summary_label)

        # Add feedback widget for better user feedback
        from .enhanced_feedback import FeedbackWidget

        self.feedback_widget = FeedbackWidget()
        self.feedback_widget.set_feedback_manager(self.feedback_manager)
        feedback_group = QGroupBox("Activity Log")
        feedback_layout = QVBoxLayout()
        feedback_layout.addWidget(self.feedback_widget)
        feedback_group.setLayout(feedback_layout)
        layout.addWidget(feedback_group)

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
        directory = QFileDialog.getExistingDirectory(self, "Select Directory", self.dir_input.text())
        if directory:
            self.dir_input.setText(directory)

    def _perform_scan(self) -> None:
        """Perform a scan for missing files."""
        directory = self.dir_input.text()
        if not directory or not os.path.isdir(directory):
            self.feedback_manager.report_error("Invalid Directory", "Please select a valid directory.")
            QMessageBox.warning(self, "Invalid Directory", "Please select a valid directory.")
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
            self.feedback_manager.start_task("Scanning for missing files")

            # Log scan parameters
            from .enhanced_feedback import MessageType

            self.feedback_manager.add_message(f"Directory: {directory}", MessageType.INFO)
            self.feedback_manager.add_message(
                f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                MessageType.INFO,
            )
            self.feedback_manager.add_message(f"Satellite: {satellite.name}", MessageType.INFO)

            self.view_model.base_directory = Path(directory)
            self.view_model.start_date = start_date
            self.view_model.end_date = end_date
            self.view_model.selected_pattern = satellite
            self.view_model.start_scan()
        else:
            self.feedback_manager.report_error("Configuration Error", "No view model connected")
            self.status_label.setText("Error: No view model connected")

    def _download_selected(self) -> None:
        """Download selected missing files."""
        selected_items = self._get_selected_items()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select files to download.")
            return

        if self.view_model:
            self.view_model.start_downloads(selected_items)
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

        # Update status label theme class based on content
        if "error" in status.lower():
            self.status_label.setProperty("class", "StatusError")
        elif "complete" in status.lower() or "success" in status.lower():
            self.status_label.setProperty("class", "StatusSuccess")
        elif "scanning" in status.lower() or "downloading" in status.lower():
            self.status_label.setProperty("class", "StatusWarning")
        else:
            self.status_label.setProperty("class", "StatusLabel")

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

        # Update progress bar text to show percentage and ETA
        if total > 0:
            percentage = (current / total) * 100
            if eta > 0:
                eta_min = int(eta / 60)
                eta_sec = int(eta % 60)
                self.progress_bar.setFormat(f"{percentage:.1f}% - ETA: {eta_min}m {eta_sec}s")
            else:
                self.progress_bar.setFormat(f"{percentage:.1f}%")

    def _on_missing_items_updated(self, items: List[MissingTimestamp]) -> None:
        """Handle missing items update from view model."""
        self.results_model.set_items(items)
        self.download_button.setEnabled(len(items) > 0)
        self.summary_label.setText(f"Found {len(items)} missing files out of expected files")

    def _on_scan_completed_vm(self, success: bool, message: str) -> None:
        """Handle scan completion from view model."""
        if not success:
            self.feedback_manager.complete_task("Scanning for missing files", success=False)
            self.feedback_manager.report_error("Scan Failed", message)
            QMessageBox.critical(self, "Scan Error", message)
        else:
            missing_count = len(self.results_model._items)
            self.feedback_manager.complete_task("Scanning for missing files", success=True)

            from .enhanced_feedback import MessageType

            self.feedback_manager.add_message(
                f"Scan complete: Found {missing_count} missing files",
                MessageType.SUCCESS,
            )
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
        if not selection or not selection.hasSelection():
            return []

        selected_rows = selection.selectedRows() if selection else []
        return [self.results_model._items[index.row()] for index in selected_rows]

    def _auto_detect_date_range(self) -> None:
        """Auto-detect date range from files in the selected directory."""
        directory = self.dir_input.text()
        if not directory or not os.path.isdir(directory):
            QMessageBox.warning(self, "Invalid Directory", "Please select a valid directory first.")
            return

        # Import enhanced auto-detection
        from .auto_detection_enhanced import (
            AutoDetectionWorker,
            DetectionProgressDialog,
        )

        # Get selected satellite pattern
        satellite_idx = self.satellite_combo.currentIndex()
        satellite_patterns = list(SatellitePattern)
        if 0 <= satellite_idx < len(satellite_patterns):
            satellite = satellite_patterns[satellite_idx]
        else:
            satellite = SatellitePattern.GENERIC

        # Create progress dialog
        progress_dialog = DetectionProgressDialog(
            "Auto-Detecting Date Range",
            "Scanning directory for satellite files...",
            self,
        )

        # Create worker thread
        worker = AutoDetectionWorker("date_range", Path(directory), satellite=satellite)

        # Connect signals
        def on_progress(value: int, message: str, level: str) -> None:
            progress_dialog.setValue(value)
            progress_dialog.setLabelText(message)
            progress_dialog.add_log_message(message, level)

        def on_finished(result: dict) -> None:
            progress_dialog.close()
            worker.quit()
            worker.wait()

            if result["status"] == "success":
                start_date = result["start"]
                end_date = result["end"]
                total_files = result["total_files"]

                # Update date editors
                from PyQt6.QtCore import QDateTime

                self.start_date_edit.setDateTime(QDateTime(start_date))
                self.end_date_edit.setDateTime(QDateTime(end_date))

                QMessageBox.information(
                    self,
                    "Date Range Detected",
                    f"Found {total_files} files from:\n"
                    f"{start_date.strftime('%Y-%m-%d %H:%M')}\n"
                    f"to:\n{end_date.strftime('%Y-%m-%d %H:%M')}",
                )
            elif result["status"] == "no_timestamps":
                QMessageBox.information(
                    self,
                    "No Files Found",
                    "No valid satellite files found in the selected directory.",
                )
            else:
                QMessageBox.warning(
                    self,
                    "Detection Failed",
                    f"Failed to detect date range: {result.get('error', 'Unknown error')}",
                )

        def on_error(error_msg: str, traceback: str) -> None:
            progress_dialog.close()
            worker.quit()
            worker.wait()

            LOGGER.error(f"Auto-detection error: {error_msg}\n{traceback}")
            QMessageBox.critical(
                self,
                "Auto-Detection Error",
                f"An error occurred during auto-detection:\n{error_msg}",
            )

        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)

        # Connect cancel button
        progress_dialog.canceled.connect(worker.cancel)

        # Start the worker
        worker.start()

        # Show the progress dialog
        progress_dialog.exec()

    def _select_all_items(self) -> None:
        """Select all items in the results table."""
        self.results_table.selectAll()

    def _select_no_items(self) -> None:
        """Clear selection in the results table."""
        self.results_table.clearSelection()
