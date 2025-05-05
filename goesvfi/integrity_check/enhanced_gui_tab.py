"""Enhanced GUI tab for integrity checking with CDN/S3 hybrid fetching.

This module provides the EnhancedIntegrityCheckTab class, which extends the
base IntegrityCheckTab with support for hybrid CDN/S3 fetching of GOES-16 
and GOES-18 Band 13 imagery.
"""

import os
import time
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple, cast, Union

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QPushButton, QProgressBar, QTableView, QHeaderView,
    QGroupBox, QCheckBox, QComboBox, QDateTimeEdit, QSpinBox,
    QFileDialog, QLineEdit, QTextEdit, QMessageBox, QSplitter,
    QScrollArea, QFrame, QSizePolicy, QTabWidget, QDialog,
    QDialogButtonBox, QStackedWidget, QApplication, QRadioButton,
    QToolButton, QStyle, QToolTip, QMenu
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
from .view_model import ScanStatus, MissingTimestamp
from .time_index import SatellitePattern, TimeIndex
from .gui_tab import IntegrityCheckTab, MissingTimestampsModel, CacheInfoDialog
from .enhanced_view_model import (
    EnhancedIntegrityCheckViewModel, EnhancedMissingTimestamp, FetchSource
)

LOGGER = log.get_logger(__name__)


class EnhancedMissingTimestampsModel(MissingTimestampsModel):
    """Enhanced model for displaying missing timestamps with source information."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = ["Timestamp", "Satellite", "Source", "Status", "Progress", "Path"]
    
    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole) -> Any:
        """Return data for the specified index and role."""
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        
        item = cast(EnhancedMissingTimestamp, self._items[index.row()])
        col = index.column()
        
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:  # Timestamp
                return item.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            elif col == 1:  # Satellite
                return item.satellite.name if item.satellite else "Unknown"
            elif col == 2:  # Source
                return item.source.upper() if item.source else "AUTO"
            elif col == 3:  # Status
                if item.is_downloaded:
                    return "Downloaded"
                elif item.is_downloading:
                    return "Downloading..."
                elif item.download_error:
                    return f"Error: {item.download_error}"
                else:
                    return "Missing"
            elif col == 4:  # Progress
                if item.is_downloading:
                    return f"{item.progress}%"
                elif item.is_downloaded:
                    return "100%"
                else:
                    return ""
            elif col == 5:  # Path
                if item.local_path:
                    return item.local_path
                else:
                    return ""
        
        elif role == Qt.ItemDataRole.BackgroundRole:
            if col == 3:  # Status column
                if item.is_downloaded:
                    return QColor(200, 255, 200)  # Light green
                elif item.download_error:
                    return QColor(255, 200, 200)  # Light red
                elif item.is_downloading:
                    return QColor(200, 200, 255)  # Light blue
        
        return None


class AWSConfigDialog(QDialog):
    """Dialog for configuring AWS S3 settings."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("AWS Configuration")
        self.setMinimumWidth(400)
        
        # Create layout
        layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        
        # AWS profile
        self.profile_edit = QLineEdit()
        self.profile_edit.setPlaceholderText("default")
        form_layout.addRow("AWS Profile:", self.profile_edit)
        
        # AWS region
        self.region_combo = QComboBox()
        regions = [
            "us-east-1", "us-east-2", "us-west-1", "us-west-2",
            "eu-west-1", "eu-west-2", "eu-central-1",
            "ap-northeast-1", "ap-northeast-2", "ap-southeast-1", "ap-southeast-2",
            "sa-east-1"
        ]
        self.region_combo.addItems(regions)
        self.region_combo.setCurrentText("us-east-1")  # GOES data is in us-east-1
        form_layout.addRow("AWS Region:", self.region_combo)
        
        # Note about credentials
        note_label = QLabel(
            "Note: AWS credentials should be configured in your ~/.aws/credentials file. "
            "If no profile is specified, the default profile will be used."
        )
        note_label.setWordWrap(True)
        note_label.setStyleSheet("QLabel { color: #666; }")
        
        layout.addLayout(form_layout)
        layout.addWidget(note_label)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_aws_profile(self) -> Optional[str]:
        """Get the AWS profile name."""
        profile = self.profile_edit.text().strip()
        return profile if profile else None
    
    def get_aws_region(self) -> str:
        """Get the AWS region."""
        return self.region_combo.currentText()
    
    def set_aws_profile(self, profile: Optional[str]) -> None:
        """Set the AWS profile name."""
        self.profile_edit.setText(profile or "")
    
    def set_aws_region(self, region: str) -> None:
        """Set the AWS region."""
        self.region_combo.setCurrentText(region)


class CDNConfigDialog(QDialog):
    """Dialog for configuring CDN settings."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("CDN Configuration")
        self.setMinimumWidth(400)
        
        # Create layout
        layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        
        # Resolution
        self.resolution_combo = QComboBox()
        resolutions = ["1000m", "500m", "250m", "100m"]
        self.resolution_combo.addItems(resolutions)
        self.resolution_combo.setCurrentText(TimeIndex.CDN_RES)
        form_layout.addRow("Resolution:", self.resolution_combo)
        
        # Note about resolutions
        note_label = QLabel(
            "Note: Lower resolutions download faster but have less detail. "
            "The NOAA STAR CDN may not provide all resolutions for all images."
        )
        note_label.setWordWrap(True)
        note_label.setStyleSheet("QLabel { color: #666; }")
        
        layout.addLayout(form_layout)
        layout.addWidget(note_label)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_cdn_resolution(self) -> str:
        """Get the CDN resolution."""
        return self.resolution_combo.currentText()
    
    def set_cdn_resolution(self, resolution: str) -> None:
        """Set the CDN resolution."""
        self.resolution_combo.setCurrentText(resolution)


class EnhancedIntegrityCheckTab(IntegrityCheckTab):
    """
    Enhanced QWidget tab for verifying timestamp integrity and finding gaps in GOES imagery.
    
    This tab extends the base IntegrityCheckTab with support for:
    1. GOES-16 and GOES-18 satellites
    2. Hybrid CDN/S3 fetching based on timestamp recency
    3. NetCDF to PNG rendering for S3 data
    4. Enhanced progress reporting
    """
    
    def __init__(self, view_model: EnhancedIntegrityCheckViewModel, parent=None):
        """
        Initialize the EnhancedIntegrityCheckTab.
        
        Args:
            view_model: The EnhancedIntegrityCheckViewModel instance to use
            parent: Optional parent widget
        """
        # Skip the base class __init__ and call its parent directly to avoid
        # TypeError checks and reconnect signals with our own implementation
        QWidget.__init__(self, parent)
        
        if not isinstance(view_model, EnhancedIntegrityCheckViewModel):
            raise TypeError("view_model must be an instance of EnhancedIntegrityCheckViewModel")
        
        self.view_model = view_model
        
        # Create UI components
        self._setup_ui()
        
        # Connect signals from view model
        self._connect_enhanced_signals()
        
        # Initial UI update
        self._update_ui_from_view_model()
    
    def _setup_ui(self) -> None:
        """Set up the user interface with enhanced features."""
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
        
        # Quick select buttons
        quick_select_layout = QHBoxLayout()
        
        yesterday_button = QPushButton("Yesterday")
        yesterday_button.clicked.connect(self._set_yesterday)
        quick_select_layout.addWidget(yesterday_button)
        
        week_button = QPushButton("Last Week")
        week_button.clicked.connect(self._set_last_week)
        quick_select_layout.addWidget(week_button)
        
        month_button = QPushButton("Last Month")
        month_button.clicked.connect(self._set_last_month)
        quick_select_layout.addWidget(month_button)
        
        date_layout.addRow("Quick Select:", quick_select_layout)
        
        date_group.setLayout(date_layout)
        controls_layout.addWidget(date_group)
        
        # Satellite group (enhanced)
        satellite_group = QGroupBox("Satellite")
        satellite_layout = QVBoxLayout()
        
        # GOES-16 radio button
        self.goes16_radio = QRadioButton("GOES-16 (East)")
        self.goes16_radio.setToolTip("GOES East (75.2°W)")
        
        # GOES-18 radio button
        self.goes18_radio = QRadioButton("GOES-18 (West)")
        self.goes18_radio.setToolTip("GOES West (137.2°W)")
        self.goes18_radio.setChecked(True)  # Default to GOES-18
        
        satellite_layout.addWidget(self.goes16_radio)
        satellite_layout.addWidget(self.goes18_radio)
        
        # Interval
        interval_layout = QHBoxLayout()
        interval_label = QLabel("Interval:")
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setRange(0, 60)
        self.interval_spinbox.setValue(10)  # Default to 10 minutes
        self.interval_spinbox.setSuffix(" min")
        self.interval_spinbox.setSpecialValueText("Auto-detect")
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(self.interval_spinbox)
        
        satellite_layout.addLayout(interval_layout)
        satellite_group.setLayout(satellite_layout)
        controls_layout.addWidget(satellite_group)
        
        # Fetch options group (enhanced)
        fetch_group = QGroupBox("Fetch Options")
        fetch_layout = QVBoxLayout()
        
        # Fetch source radio buttons
        self.auto_radio = QRadioButton("Auto (Hybrid CDN/S3)")
        self.auto_radio.setToolTip("Automatically select CDN for recent data, S3 for older data")
        self.auto_radio.setChecked(True)
        
        self.cdn_radio = QRadioButton("CDN Only")
        self.cdn_radio.setToolTip("NOAA STAR CDN (faster, but limited history)")
        
        self.s3_radio = QRadioButton("S3 Only")
        self.s3_radio.setToolTip("AWS S3 buckets (full history, NetCDF format)")
        
        self.local_radio = QRadioButton("Local Only")
        self.local_radio.setToolTip("Only scan local files, don't fetch from remote sources")
        
        fetch_layout.addWidget(self.auto_radio)
        
        # CDN option with settings button
        cdn_layout = QHBoxLayout()
        cdn_layout.addWidget(self.cdn_radio)
        self.cdn_settings_button = QToolButton()
        self.cdn_settings_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.cdn_settings_button.setToolTip("Configure CDN settings")
        self.cdn_settings_button.clicked.connect(self._configure_cdn)
        cdn_layout.addWidget(self.cdn_settings_button)
        cdn_layout.addStretch()
        fetch_layout.addLayout(cdn_layout)
        
        # S3 option with settings button
        s3_layout = QHBoxLayout()
        s3_layout.addWidget(self.s3_radio)
        self.s3_settings_button = QToolButton()
        self.s3_settings_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.s3_settings_button.setToolTip("Configure AWS S3 settings")
        self.s3_settings_button.clicked.connect(self._configure_s3)
        s3_layout.addWidget(self.s3_settings_button)
        s3_layout.addStretch()
        fetch_layout.addLayout(s3_layout)
        
        fetch_layout.addWidget(self.local_radio)
        
        # Auto-download checkbox
        self.auto_download_checkbox = QCheckBox("Auto-Download Missing Files")
        self.auto_download_checkbox.setToolTip("Automatically download missing files after scan")
        fetch_layout.addWidget(self.auto_download_checkbox)
        
        # Force rescan checkbox
        self.force_rescan_checkbox = QCheckBox("Force Rescan")
        self.force_rescan_checkbox.setToolTip("Ignore cached results and perform a new scan")
        fetch_layout.addWidget(self.force_rescan_checkbox)
        
        fetch_group.setLayout(fetch_layout)
        controls_layout.addWidget(fetch_group)
        
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
        
        # Disk space info
        self.disk_space_label = QLabel("Disk space: 0 GB / 0 GB")
        directory_layout.addWidget(self.disk_space_label)
        
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
        
        # Bottom section: Results table (enhanced)
        results_group = QGroupBox("Missing Timestamps")
        results_layout = QVBoxLayout()
        
        # Table view with enhanced model
        self.table_view = QTableView()
        self.table_model = EnhancedMissingTimestampsModel()
        self.table_view.setModel(self.table_model)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table_view.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)  # Path column
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._show_context_menu)
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
        
        # Reset database button
        self.reset_db_button = QPushButton("Reset Database")
        self.reset_db_button.setToolTip("Reset the database and clear all cached data")
        actions_layout.addWidget(self.reset_db_button)
        
        actions_layout.addStretch()
        results_layout.addLayout(actions_layout)
        
        results_group.setLayout(results_layout)
        main_layout.addWidget(results_group, 1)  # Give table stretch priority
        
        # Connect widget signals
        self.directory_browse_button.clicked.connect(self._browse_directory)
        self.scan_button.clicked.connect(self._start_enhanced_scan)
        self.cancel_button.clicked.connect(self._cancel_operation)
        self.download_button.clicked.connect(self._download_missing)
        self.export_button.clicked.connect(self._export_report)
        self.cache_button.clicked.connect(self._show_cache_info)
        self.reset_db_button.clicked.connect(self._reset_database)
        
        # Connect radio button signals
        self.goes16_radio.toggled.connect(self._satellite_changed)
        self.goes18_radio.toggled.connect(self._satellite_changed)
        
        self.auto_radio.toggled.connect(self._fetch_source_changed)
        self.cdn_radio.toggled.connect(self._fetch_source_changed)
        self.s3_radio.toggled.connect(self._fetch_source_changed)
        self.local_radio.toggled.connect(self._fetch_source_changed)
    
    def _connect_enhanced_signals(self) -> None:
        """Connect signals from the enhanced view model."""
        # Connect base signals
        self.view_model.status_updated.connect(self._update_status)
        self.view_model.status_type_changed.connect(self._update_status_type)
        self.view_model.progress_updated.connect(self._update_progress)
        self.view_model.missing_items_updated.connect(self._update_missing_items)
        self.view_model.scan_completed.connect(self._handle_scan_completed)
        self.view_model.download_progress_updated.connect(self._update_download_progress)
        self.view_model.download_item_updated.connect(self._update_download_item)
        
        # Connect enhanced signals
        enhanced_view_model = cast(EnhancedIntegrityCheckViewModel, self.view_model)
        enhanced_view_model.satellite_changed.connect(self._update_satellite_ui)
        enhanced_view_model.fetch_source_changed.connect(self._update_fetch_source_ui)
        enhanced_view_model.download_item_progress.connect(self._update_download_item_progress)
        enhanced_view_model.disk_space_updated.connect(self._update_disk_space)
    
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
        
        # Satellite selection
        enhanced_view_model = cast(EnhancedIntegrityCheckViewModel, self.view_model)
        satellite = enhanced_view_model.satellite
        
        if satellite == SatellitePattern.GOES_16:
            self.goes16_radio.setChecked(True)
        elif satellite == SatellitePattern.GOES_18:
            self.goes18_radio.setChecked(True)
        
        # Fetch source selection
        fetch_source = enhanced_view_model.fetch_source
        
        if fetch_source == FetchSource.AUTO:
            self.auto_radio.setChecked(True)
        elif fetch_source == FetchSource.CDN:
            self.cdn_radio.setChecked(True)
        elif fetch_source == FetchSource.S3:
            self.s3_radio.setChecked(True)
        elif fetch_source == FetchSource.LOCAL:
            self.local_radio.setChecked(True)
        
        # Checkboxes
        self.force_rescan_checkbox.setChecked(self.view_model.force_rescan)
        self.auto_download_checkbox.setChecked(self.view_model.auto_download)
        
        # Status and progress
        self.status_label.setText(self.view_model.status_message)
        self._update_button_states()
    
    def _update_disk_space(self, used_gb: float, total_gb: float) -> None:
        """Update the disk space information label."""
        if total_gb > 0:
            percent = int((used_gb / total_gb) * 100)
            self.disk_space_label.setText(
                f"Disk space: {used_gb:.1f} GB / {total_gb:.1f} GB ({percent}% used)"
            )
            
            # Change color if disk space is low
            if percent > 90:
                self.disk_space_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
            elif percent > 80:
                self.disk_space_label.setStyleSheet("QLabel { color: orange; }")
            else:
                self.disk_space_label.setStyleSheet("")
        else:
            self.disk_space_label.setText("Disk space: Unknown")
    
    def _update_satellite_ui(self, satellite: SatellitePattern) -> None:
        """Update the UI based on the selected satellite."""
        if satellite == SatellitePattern.GOES_16 and not self.goes16_radio.isChecked():
            self.goes16_radio.setChecked(True)
        elif satellite == SatellitePattern.GOES_18 and not self.goes18_radio.isChecked():
            self.goes18_radio.setChecked(True)
    
    def _update_fetch_source_ui(self, source: FetchSource) -> None:
        """Update the UI based on the selected fetch source."""
        if source == FetchSource.AUTO and not self.auto_radio.isChecked():
            self.auto_radio.setChecked(True)
        elif source == FetchSource.CDN and not self.cdn_radio.isChecked():
            self.cdn_radio.setChecked(True)
        elif source == FetchSource.S3 and not self.s3_radio.isChecked():
            self.s3_radio.setChecked(True)
        elif source == FetchSource.LOCAL and not self.local_radio.isChecked():
            self.local_radio.setChecked(True)
    
    def _update_download_item_progress(self, index: int, progress: int) -> None:
        """Update the progress for a specific download item."""
        if 0 <= index < len(self.view_model.missing_items):
            item = cast(EnhancedMissingTimestamp, self.view_model.missing_items[index])
            item.progress = progress
            
            # Update the table model
            self.table_model.updateItem(index, item)
            
            # Process events to ensure UI updates immediately
            QApplication.processEvents()
    
    def _show_context_menu(self, position) -> None:
        """Show context menu for the table view."""
        indexes = self.table_view.selectedIndexes()
        if not indexes:
            return
        
        # Get the row index (they all share the same row)
        row = indexes[0].row()
        item = self.view_model.missing_items[row]
        
        menu = QMenu()
        
        # Show file action
        if item.is_downloaded and item.local_path:
            action_show = QAction("Show in File Explorer", self)
            action_show.triggered.connect(lambda: self._show_in_explorer(item.local_path))
            menu.addAction(action_show)
        
        # Download action
        if not item.is_downloaded and not item.is_downloading:
            action_download = QAction("Download This File", self)
            action_download.triggered.connect(lambda: self._download_single_item(row))
            menu.addAction(action_download)
        
        if menu.actions():
            menu.exec(self.table_view.viewport().mapToGlobal(position))
    
    def _show_in_explorer(self, path: str) -> None:
        """Show a file in the file explorer."""
        import subprocess
        import platform
        
        try:
            file_path = Path(path)
            if not file_path.exists():
                QMessageBox.warning(self, "File Not Found", 
                                   f"The file {path} does not exist.")
                return
            
            system = platform.system()
            if system == "Windows":
                subprocess.Popen(["explorer", "/select,", str(file_path)])
            elif system == "Darwin":  # macOS
                subprocess.Popen(["open", "-R", str(file_path)])
            else:  # Linux
                parent_path = file_path.parent
                subprocess.Popen(["xdg-open", str(parent_path)])
        except Exception as e:
            LOGGER.error(f"Error showing file in explorer: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open file explorer: {e}")
    
    def _download_single_item(self, row_index: int) -> None:
        """Download a single missing item."""
        if row_index < 0 or row_index >= len(self.view_model.missing_items):
            return
        
        # Not implemented yet - would need to add a single-item download method to view model
        QMessageBox.information(self, "Not Implemented", 
                               "Single item download is not yet implemented. Use the 'Download Missing Files' button instead.")
    
    def _satellite_changed(self) -> None:
        """Handle satellite radio button changes."""
        enhanced_view_model = cast(EnhancedIntegrityCheckViewModel, self.view_model)
        
        if self.goes16_radio.isChecked():
            enhanced_view_model.satellite = SatellitePattern.GOES_16
        elif self.goes18_radio.isChecked():
            enhanced_view_model.satellite = SatellitePattern.GOES_18
    
    def _fetch_source_changed(self) -> None:
        """Handle fetch source radio button changes."""
        enhanced_view_model = cast(EnhancedIntegrityCheckViewModel, self.view_model)
        
        if self.auto_radio.isChecked():
            enhanced_view_model.fetch_source = FetchSource.AUTO
        elif self.cdn_radio.isChecked():
            enhanced_view_model.fetch_source = FetchSource.CDN
        elif self.s3_radio.isChecked():
            enhanced_view_model.fetch_source = FetchSource.S3
        elif self.local_radio.isChecked():
            enhanced_view_model.fetch_source = FetchSource.LOCAL
    
    def _set_yesterday(self) -> None:
        """Set the date range to yesterday (full day)."""
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
    
    def _set_last_week(self) -> None:
        """Set the date range to the last week."""
        end_date = datetime.now() - timedelta(days=1)
        start_date = end_date - timedelta(days=6)  # Last 7 days including yesterday
        
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=0)
        
        self.start_date_edit.setDateTime(QDateTime(
            QDate(start_date.year, start_date.month, start_date.day),
            QTime(start_date.hour, start_date.minute)
        ))
        
        self.end_date_edit.setDateTime(QDateTime(
            QDate(end_date.year, end_date.month, end_date.day),
            QTime(end_date.hour, end_date.minute)
        ))
    
    def _set_last_month(self) -> None:
        """Set the date range to the last month."""
        end_date = datetime.now() - timedelta(days=1)
        start_date = end_date - timedelta(days=29)  # Last 30 days including yesterday
        
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=0)
        
        self.start_date_edit.setDateTime(QDateTime(
            QDate(start_date.year, start_date.month, start_date.day),
            QTime(start_date.hour, start_date.minute)
        ))
        
        self.end_date_edit.setDateTime(QDateTime(
            QDate(end_date.year, end_date.month, end_date.day),
            QTime(end_date.hour, end_date.minute)
        ))
    
    def _configure_cdn(self) -> None:
        """Configure CDN settings."""
        enhanced_view_model = cast(EnhancedIntegrityCheckViewModel, self.view_model)
        
        dialog = CDNConfigDialog(self)
        dialog.set_cdn_resolution(enhanced_view_model.cdn_resolution)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            enhanced_view_model.cdn_resolution = dialog.get_cdn_resolution()
    
    def _configure_s3(self) -> None:
        """Configure S3 settings."""
        enhanced_view_model = cast(EnhancedIntegrityCheckViewModel, self.view_model)
        
        dialog = AWSConfigDialog(self)
        dialog.set_aws_profile(enhanced_view_model.aws_profile)
        dialog.set_aws_region(enhanced_view_model._s3_region)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            enhanced_view_model.aws_profile = dialog.get_aws_profile()
            enhanced_view_model._s3_region = dialog.get_aws_region()
    
    def _reset_database(self) -> None:
        """Reset the database."""
        reply = QMessageBox.question(
            self, 
            "Reset Database",
            "Are you sure you want to reset the database? This will delete all cached data.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            enhanced_view_model = cast(EnhancedIntegrityCheckViewModel, self.view_model)
            enhanced_view_model.reset_database()
    
    def _start_enhanced_scan(self) -> None:
        """Start the enhanced scan operation."""
        # Update view model parameters from UI
        self.view_model.start_date = self.start_date_edit.dateTime().toPython()
        self.view_model.end_date = self.end_date_edit.dateTime().toPython()
        self.view_model.interval_minutes = self.interval_spinbox.value()
        self.view_model.force_rescan = self.force_rescan_checkbox.isChecked()
        self.view_model.auto_download = self.auto_download_checkbox.isChecked()
        
        # Clear the table
        self.table_model.setItems([])
        
        # Start enhanced scan
        enhanced_view_model = cast(EnhancedIntegrityCheckViewModel, self.view_model)
        enhanced_view_model.start_enhanced_scan()
        
        # Update UI
        self._update_button_states()
    
    def _download_missing(self) -> None:
        """Start downloading missing files with enhanced functionality."""
        if not self.view_model.has_missing_items:
            QMessageBox.information(self, "No Missing Files", 
                                   "There are no missing files to download.")
            return
        
        # Start enhanced downloads
        enhanced_view_model = cast(EnhancedIntegrityCheckViewModel, self.view_model)
        enhanced_view_model.start_enhanced_downloads()
        
        # Update UI
        self._update_button_states()