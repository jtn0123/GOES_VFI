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
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from PyQt6.QtCore import (
    QAbstractTableModel,
    QDate,
    QDateTime,
    QModelIndex,
    QObject,
    QPoint,
    QRunnable,
    QSize,
    QSortFilterProxyModel,
    Qt,
    QThread,
    QThreadPool,
    QTime,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QAction,
    QBrush,
    QCloseEvent,
    QColor,
    QFont,
    QIcon,
    QPalette,
    QPixmap,
    QStandardItem,
    QStandardItemModel,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStyle,
    QTableView,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from goesvfi.utils import log

from .date_range_selector import UnifiedDateRangeSelector
from .enhanced_imagery_tab import EnhancedGOESImageryTab
from .enhanced_view_model import (
    EnhancedIntegrityCheckViewModel,
    EnhancedMissingTimestamp,
    FetchSource,
)
from .gui_tab import CacheInfoDialog, IntegrityCheckTab, MissingTimestampsModel
from .time_index import SatellitePattern, TimeIndex
from .view_model import MissingTimestamp, ScanStatus

LOGGER = log.get_logger(__name__)


class EnhancedMissingTimestampsModel(MissingTimestampsModel):
    """Enhanced model for displaying missing timestamps with source information."""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._headers = [
            "Timestamp",
            "Satellite",
            "Source",
            "Status",
            "Progress",
            "Path",
        ]

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Return data for the specified index and role."""
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None

        item = cast(EnhancedMissingTimestamp, self._items[index.row()])
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:  # Timestamp
                return item.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            elif col == 1:  # Satellite
                return item.satellite if isinstance(item.satellite, str) else "Unknown"
            elif col == 2:  # Source
                return item.source.upper() if item.source else "AUTO"
            elif col == 3:  # Status
                if item.is_downloaded:
                    return "Downloaded"
                elif item.is_downloading:
                    return "Downloading..."
                elif item.download_error:
                    # Format error message to be more user-friendly
                    error_msg = item.download_error

                    # Extract error code if present
                    error_code = "Unknown"
                    if "[Error " in error_msg and "]" in error_msg:
                        try:
                            error_code = error_msg.split("[Error ")[1].split("]")[0]
                            # Keep just the error code part for display
                            error_msg = f"Error {error_code}"
                        except:
                            pass

                    # Handle SQLite thread errors specially
                    if "SQLite objects created in a thread" in error_msg:
                        return "Error: Database thread conflict"

                    # Handle common error types with user-friendly messages
                    if (
                        "unable to connect" in error_msg.lower()
                        or "connection" in error_msg.lower()
                    ):
                        return "Error: Connection failed"
                    elif "not found" in error_msg.lower() or "404" in error_msg:
                        return "Error: File not found"
                    elif (
                        "permission" in error_msg.lower()
                        or "access denied" in error_msg.lower()
                    ):
                        return "Error: Access denied"
                    elif "timeout" in error_msg.lower():
                        return "Error: Connection timeout"
                    elif "service" in error_msg.lower():
                        return "Error: Service unavailable"
                    elif "unexpected" in error_msg.lower():
                        # Show a simpler version of unexpected errors
                        return f"Error: Download failed ({error_code})"

                    # If we get here, use a simpler version of the error
                    if len(error_msg) > 50:
                        return f"Error: {error_msg[:47]}..."
                    return f"Error: {error_msg}"
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

        elif role == Qt.ItemDataRole.ToolTipRole:
            # Add tooltips with more details for certain columns
            if col == 3 and item.download_error:  # Status column with error
                # Create a more detailed tooltip that shows the full error message
                tooltip = "Double-click for details\n\n"

                # Add the error message, but limit length for very long ones
                if len(item.download_error) > 500:
                    tooltip += item.download_error[:500] + "...\n\n"
                else:
                    tooltip += item.download_error + "\n\n"

                # Add a hint about viewing more details
                tooltip += "Right-click to show context menu with more options"
                return tooltip

            elif col == 0:  # Timestamp column
                # Show full ISO format with TZ info in tooltip
                return item.timestamp.isoformat()

            elif col == 5 and item.local_path:  # Path column with content
                # Show "Double-click to open" for downloaded files
                if item.is_downloaded:
                    return f"Double-click to open folder containing:\n{item.local_path}"

        elif role == Qt.ItemDataRole.BackgroundRole:
            if col == 3:  # Status column
                if item.is_downloaded:
                    return QColor(0, 120, 0)  # Dark green for dark mode
                elif item.download_error:
                    return QColor(120, 0, 0)  # Dark red for dark mode
                elif item.is_downloading:
                    return QColor(0, 0, 120)  # Dark blue for dark mode

        # For dark mode, we want to ensure text is visible against colored backgrounds
        elif role == Qt.ItemDataRole.ForegroundRole:
            if col == 3:  # Status column
                if item.is_downloaded or item.download_error or item.is_downloading:
                    return QColor(
                        255, 255, 255
                    )  # White text for better visibility on colored backgrounds

        return None


class AWSConfigDialog(QDialog):
    """Dialog for configuring AWS S3 settings."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle(self.tr("AWS S3 Configuration"))
        self.setMinimumWidth(500)

        # Create layout
        layout = QVBoxLayout(self)

        # Info label about unsigned access
        info_label = QLabel(
            "<b>Important:</b> AWS credentials are <b>NOT</b> required to access NOAA GOES data. "
            "This application uses unsigned S3 access for the public NOAA buckets."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet(
            "QLabel { background-color: #e5f5e5; padding: 10px; border-radius: 5px; }"
        )
        layout.addWidget(info_label)

        form_layout = QFormLayout()

        # AWS profile
        self.profile_edit = QLineEdit()
        self.profile_edit.setPlaceholderText("Leave empty for unsigned access")
        form_layout.addRow("AWS Profile (optional):", self.profile_edit)

        # AWS region
        self.region_combo = QComboBox()
        regions = [
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "us-west-2",
            "eu-west-1",
            "eu-west-2",
            "eu-central-1",
            "ap-northeast-1",
            "ap-northeast-2",
            "ap-southeast-1",
            "ap-southeast-2",
            "sa-east-1",
        ]
        self.region_combo.addItems(regions)
        self.region_combo.setCurrentText("us-east-1")  # GOES data is in us-east-1
        form_layout.addRow("AWS Region:", self.region_combo)

        # Note about credentials
        note_label = QLabel(
            "Note: NOAA GOES data is stored in the <b>us-east-1</b> region in public S3 buckets. "
            "The application uses unsigned S3 access by default, which requires no credentials. "
            "Only provide a profile if you need to access private buckets."
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

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle(self.tr("CDN Configuration"))
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


class AdvancedOptionsDialog(QDialog):
    """Dialog for configuring advanced integrity check options."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle(self.tr("Advanced Integrity Check Options"))
        self.setMinimumWidth(500)

        # Create layout
        layout = QVBoxLayout(self)

        # Connection Options Group
        connection_group = QGroupBox(self.tr("Connection Options"))
        connection_layout = QFormLayout()

        # Connection timeout
        self.timeout_spinbox = QSpinBox()
        self.timeout_spinbox.setRange(30, 300)
        self.timeout_spinbox.setValue(60)
        self.timeout_spinbox.setSuffix(" seconds")
        connection_layout.addRow("Connection Timeout:", self.timeout_spinbox)

        # Maximum concurrent downloads
        self.max_concurrent_spinbox = QSpinBox()
        self.max_concurrent_spinbox.setRange(1, 20)
        self.max_concurrent_spinbox.setValue(5)
        self.max_concurrent_spinbox.setToolTip(
            self.tr("Maximum number of concurrent downloads. Higher values may improve speed but increase resource usage.")
        )
        connection_layout.addRow(
            "Max Concurrent Downloads:", self.max_concurrent_spinbox
        )

        # Retry attempts
        self.retry_spinbox = QSpinBox()
        self.retry_spinbox.setRange(0, 5)
        self.retry_spinbox.setValue(2)
        self.retry_spinbox.setToolTip(
            self.tr("Number of times to retry failed downloads automatically")
        )
        connection_layout.addRow("Auto-retry Attempts:", self.retry_spinbox)

        connection_group.setLayout(connection_layout)
        layout.addWidget(connection_group)

        # Performance Options Group
        performance_group = QGroupBox(self.tr("Performance Options"))
        performance_layout = QFormLayout()

        # Network throttling
        self.throttle_checkbox = QCheckBox()
        self.throttle_checkbox.setToolTip(
            self.tr("Limit download speed to reduce impact on your network")
        )
        performance_layout.addRow("Enable Network Throttling:", self.throttle_checkbox)

        # Throttle speed
        self.throttle_spinbox = QSpinBox()
        self.throttle_spinbox.setRange(100, 10000)
        self.throttle_spinbox.setValue(1000)
        self.throttle_spinbox.setSuffix(" KB/s")
        self.throttle_spinbox.setEnabled(False)
        self.throttle_spinbox.setToolTip(self.tr("Maximum download speed per file"))
        performance_layout.addRow("Max Download Speed:", self.throttle_spinbox)
        self.throttle_checkbox.toggled.connect(self.throttle_spinbox.setEnabled)

        # Process priority
        self.priority_combo = QComboBox()
        self.priority_combo.addItems([self.tr("Normal"), self.tr("Low"), self.tr("High")])
        self.priority_combo.setCurrentText("Normal")
        self.priority_combo.setToolTip(self.tr("Process priority for download operations"))
        performance_layout.addRow("Process Priority:", self.priority_combo)

        performance_group.setLayout(performance_layout)
        layout.addWidget(performance_group)

        # Image Processing Options Group
        image_group = QGroupBox(self.tr("Image Processing Options"))
        image_layout = QFormLayout()

        # Auto-enhance images
        self.auto_enhance_checkbox = QCheckBox()
        self.auto_enhance_checkbox.setToolTip(
            self.tr("Automatically enhance downloaded images for better visibility")
        )
        image_layout.addRow("Auto-enhance Images:", self.auto_enhance_checkbox)

        # Apply false color
        self.false_color_checkbox = QCheckBox()
        self.false_color_checkbox.setToolTip(
            self.tr("Apply false coloring to IR images for better visualization")
        )
        image_layout.addRow("Apply False Color:", self.false_color_checkbox)

        # Automatically convert NetCDF
        self.convert_netcdf_checkbox = QCheckBox()
        self.convert_netcdf_checkbox.setChecked(True)
        self.convert_netcdf_checkbox.setToolTip(
            self.tr("Automatically convert NetCDF files to PNG after download")
        )
        image_layout.addRow("Auto-convert NetCDF:", self.convert_netcdf_checkbox)

        image_group.setLayout(image_layout)
        layout.addWidget(image_group)

        # Notification Options Group
        notification_group = QGroupBox(self.tr("Notification Options"))
        notification_layout = QFormLayout()

        # Desktop notifications
        self.desktop_notify_checkbox = QCheckBox()
        self.desktop_notify_checkbox.setToolTip(
            self.tr("Show desktop notifications when operations complete")
        )
        notification_layout.addRow(
            "Desktop Notifications:", self.desktop_notify_checkbox
        )

        # Sound alerts
        self.sound_alerts_checkbox = QCheckBox()
        self.sound_alerts_checkbox.setToolTip(
            self.tr("Play sound when operations complete or errors occur")
        )
        notification_layout.addRow("Sound Alerts:", self.sound_alerts_checkbox)

        notification_group.setLayout(notification_layout)
        layout.addWidget(notification_group)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Connect signals
        self.throttle_checkbox.toggled.connect(self.throttle_spinbox.setEnabled)

    def get_options(self) -> Dict[str, Any]:
        """Get the options as a dictionary."""
        return {
            "timeout": self.timeout_spinbox.value(),
            "max_concurrent": self.max_concurrent_spinbox.value(),
            "retry_attempts": self.retry_spinbox.value(),
            "throttle_enabled": self.throttle_checkbox.isChecked(),
            "throttle_speed": self.throttle_spinbox.value()
            if self.throttle_checkbox.isChecked()
            else 0,
            "process_priority": self.priority_combo.currentText().lower(),
            "auto_enhance": self.auto_enhance_checkbox.isChecked(),
            "false_color": self.false_color_checkbox.isChecked(),
            "convert_netcdf": self.convert_netcdf_checkbox.isChecked(),
            "desktop_notify": self.desktop_notify_checkbox.isChecked(),
            "sound_alerts": self.sound_alerts_checkbox.isChecked(),
        }

    def set_options(self, options: Dict[str, Any]) -> None:
        """Set the options from a dictionary."""
        if "timeout" in options:
            self.timeout_spinbox.setValue(options["timeout"])
        if "max_concurrent" in options:
            self.max_concurrent_spinbox.setValue(options["max_concurrent"])
        if "retry_attempts" in options:
            self.retry_spinbox.setValue(options["retry_attempts"])
        if "throttle_enabled" in options:
            self.throttle_checkbox.setChecked(options["throttle_enabled"])
        if "throttle_speed" in options and options["throttle_enabled"]:
            self.throttle_spinbox.setValue(options["throttle_speed"])
        if "process_priority" in options:
            self.priority_combo.setCurrentText(options["process_priority"].capitalize())
        if "auto_enhance" in options:
            self.auto_enhance_checkbox.setChecked(options["auto_enhance"])
        if "false_color" in options:
            self.false_color_checkbox.setChecked(options["false_color"])
        if "convert_netcdf" in options:
            self.convert_netcdf_checkbox.setChecked(options["convert_netcdf"])
        if "desktop_notify" in options:
            self.desktop_notify_checkbox.setChecked(options["desktop_notify"])
        if "sound_alerts" in options:
            self.sound_alerts_checkbox.setChecked(options["sound_alerts"])


class BatchOperationsDialog(QDialog):
    """Dialog for performing batch operations on integrity check results."""

    def __init__(
        self, items: List[EnhancedMissingTimestamp], parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)

        self.items = items

        self.setWindowTitle(self.tr("Batch Operations"))
        self.setMinimumWidth(500)

        # Create layout
        layout = QVBoxLayout(self)

        # Operations selection
        operation_group = QGroupBox(self.tr("Select Operation"))
        operation_layout = QVBoxLayout()

        self.download_radio = QRadioButton("Download Selected Files")
        self.download_radio.setChecked(True)
        operation_layout.addWidget(self.download_radio)

        self.retry_radio = QRadioButton("Retry Failed Downloads")
        operation_layout.addWidget(self.retry_radio)

        self.export_radio = QRadioButton("Export Selected Items to CSV")
        operation_layout.addWidget(self.export_radio)

        self.delete_radio = QRadioButton("Delete Selected Files")
        operation_layout.addWidget(self.delete_radio)

        operation_group.setLayout(operation_layout)
        layout.addWidget(operation_group)

        # Filter options
        filter_group = QGroupBox(self.tr("Filter Options"))
        filter_layout = QVBoxLayout()

        self.filter_all_radio = QRadioButton("All Items")
        self.filter_all_radio.setChecked(True)
        filter_layout.addWidget(self.filter_all_radio)

        self.filter_selected_radio = QRadioButton("Selected Items Only")
        filter_layout.addWidget(self.filter_selected_radio)

        self.filter_failed_radio = QRadioButton("Failed Downloads Only")
        filter_layout.addWidget(self.filter_failed_radio)

        self.filter_missing_radio = QRadioButton("Missing Files Only")
        filter_layout.addWidget(self.filter_missing_radio)

        self.filter_downloaded_radio = QRadioButton("Downloaded Files Only")
        filter_layout.addWidget(self.filter_downloaded_radio)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # Summary label
        self.summary_label = QLabel(self.tr("Selected operation will process X items"))
        layout.addWidget(self.summary_label)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Connect signals
        self.download_radio.toggled.connect(self._update_summary)
        self.retry_radio.toggled.connect(self._update_summary)
        self.export_radio.toggled.connect(self._update_summary)
        self.delete_radio.toggled.connect(self._update_summary)
        self.filter_all_radio.toggled.connect(self._update_summary)
        self.filter_selected_radio.toggled.connect(self._update_summary)
        self.filter_failed_radio.toggled.connect(self._update_summary)
        self.filter_missing_radio.toggled.connect(self._update_summary)
        self.filter_downloaded_radio.toggled.connect(self._update_summary)

        # Initial update
        self._update_summary()

    def _update_summary(self) -> None:
        """Update the summary label based on selected options."""
        operation = "Download"
        if self.retry_radio.isChecked():
            operation = "Retry"
        elif self.export_radio.isChecked():
            operation = "Export"
        elif self.delete_radio.isChecked():
            operation = "Delete"

        # Count items based on filter
        count = len(self.items)
        if self.filter_failed_radio.isChecked():
            count = sum(
                1
                for item in self.items
                if not item.is_downloaded and item.download_error
            )
        elif self.filter_missing_radio.isChecked():
            count = sum(1 for item in self.items if not item.is_downloaded)
        elif self.filter_downloaded_radio.isChecked():
            count = sum(1 for item in self.items if item.is_downloaded)

        self.summary_label.setText(
            f"Selected operation will {operation.lower()} {count} items"
        )

    def get_options(self) -> Dict[str, Any]:
        """Get the selected options."""
        operation = "download"
        if self.retry_radio.isChecked():
            operation = "retry"
        elif self.export_radio.isChecked():
            operation = "export"
        elif self.delete_radio.isChecked():
            operation = "delete"

        filter_type = "all"
        if self.filter_selected_radio.isChecked():
            filter_type = "selected"
        elif self.filter_failed_radio.isChecked():
            filter_type = "failed"
        elif self.filter_missing_radio.isChecked():
            filter_type = "missing"
        elif self.filter_downloaded_radio.isChecked():
            filter_type = "downloaded"

        return {"operation": operation, "filter": filter_type}


class EnhancedIntegrityCheckTab(IntegrityCheckTab):
    """
    Enhanced QWidget tab for verifying timestamp integrity and finding gaps in GOES imagery.

    This tab extends the base IntegrityCheckTab with support for:
    1. GOES-16 and GOES-18 satellites
    2. Hybrid CDN/S3 fetching based on timestamp recency
    3. NetCDF to PNG rendering for S3 data
    4. Enhanced progress reporting
    5. Advanced error diagnostics and troubleshooting
    6. Batch operations for efficient file management
    7. Advanced configuration options
    """

    # Custom signals
    directory_selected = pyqtSignal(str)
    date_range_changed = pyqtSignal(
        datetime, datetime
    )  # Signal when date range changes

    def __init__(
        self,
        view_model: EnhancedIntegrityCheckViewModel,
        parent: Optional[QWidget] = None,
    ) -> None:
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
            raise TypeError(
                "view_model must be an instance of EnhancedIntegrityCheckViewModel"
            )

        self.view_model = view_model

        # Initialize progress tracking attributes
        self._last_progress_update_time: float = time.time()
        self._last_progress_count: int = 0
        self._downloaded_success_count: int = 0
        self._downloaded_failed_count: int = 0

        # Apply stylesheet for enhanced visual appearance
        self._apply_stylesheet()

        # Create UI components
        self._setup_ui()

        # Connect signals from view model
        self._connect_enhanced_signals()

        # Initial UI update
        self._update_ui_from_view_model()

    def _apply_stylesheet(self) -> None:
        """Apply stylesheet for better UI appearance."""
        # Define common styles for the entire tab
        self.setStyleSheet(
            """
            QGroupBox {
                font-weight: bold;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 16px;
                background-color: #2a2a2a;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }

            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px 15px;
                min-height: 24px;
            }

            QPushButton:hover {
                background-color: #444;
                border: 1px solid #666;
            }

            QPushButton:pressed {
                background-color: #222;
            }

            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666;
                border: 1px solid #444;
            }

            QPushButton[primary="true"] {
                background-color: #2b5d8e;
                color: white;
                font-weight: bold;
            }

            QPushButton[primary="true"]:hover {
                background-color: #366ca0;
            }

            QPushButton[destructive="true"] {
                background-color: #8e2b2b;
                color: white;
            }

            QPushButton[destructive="true"]:hover {
                background-color: #a03636;
            }

            QTableView {
                alternate-background-color: #333;
                background-color: #222;
                border: 1px solid #444;
                gridline-color: #444;
                selection-background-color: #3a6ea5;
            }

            QHeaderView::section {
                background-color: #2d2d2d;
                color: white;
                padding: 4px;
                border: 1px solid #444;
            }

            QLineEdit, QDateTimeEdit, QComboBox, QSpinBox {
                background-color: #333;
                color: white;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 3px;
                min-height: 22px;
            }

            QRadioButton, QCheckBox {
                spacing: 8px;
            }

            QRadioButton::indicator, QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }

            QProgressBar {
                border: 1px solid #555;
                border-radius: 3px;
                background-color: #333;
                text-align: center;
                color: white;
            }

            QProgressBar::chunk {
                background-color: #2b5d8e;
                width: 10px;
                margin: 0.5px;
            }

            QLabel[status="error"] {
                color: #ff5555;
            }

            QLabel[status="success"] {
                color: #55ff7f;
            }

            QLabel[status="warning"] {
                color: #ffaa55;
            }

            QLabel[status="info"] {
                color: #55aaff;
            }
        """
        )

    def closeEvent(self, event: Optional[QCloseEvent]) -> None:
        """Handle the close event with proper cleanup.

        This ensures all resources are properly cleaned up when the tab is closed,
        particularly any network connections or background operations.

        Args:
            event: The close event
        """
        try:
            LOGGER.debug("Enhanced integrity check tab is closing, performing cleanup")

            # Ensure any running operations are canceled first
            self._cancel_operation()

            # Cleanup view model resources if needed
            enhanced_view_model = cast(EnhancedIntegrityCheckViewModel, self.view_model)

            # Cancel any pending background tasks
            if (
                hasattr(enhanced_view_model, "scan_task")
                and enhanced_view_model.scan_task is not None
            ):
                LOGGER.debug("Canceling pending scan task")
                try:
                    enhanced_view_model.scan_task.cancel()
                except Exception as e:
                    LOGGER.error(f"Error canceling scan task: {e}")

            # Close any network connections
            if hasattr(enhanced_view_model, "cleanup") and callable(
                enhanced_view_model.cleanup
            ):
                LOGGER.debug("Calling view model cleanup method")
                try:
                    enhanced_view_model.cleanup()
                except Exception as e:
                    LOGGER.error(f"Error during view model cleanup: {e}")

            # Process any pending events to ensure UI updates
            QApplication.processEvents()

            LOGGER.debug("Enhanced integrity check tab cleanup completed")
        except Exception as e:
            LOGGER.error(f"Error during tab cleanup: {e}")
            import traceback

            LOGGER.error(traceback.format_exc())

        # Call the parent class closeEvent
        super().closeEvent(event)

    def _setup_ui(self) -> None:
        """Set up the user interface with enhanced features."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # Top section: Controls
        controls_section = QWidget()
        controls_layout = QHBoxLayout(controls_section)
        controls_layout.setContentsMargins(0, 0, 0, 0)

        # Use the new unified date range selector component
        self.date_selector = UnifiedDateRangeSelector(
            self, include_visual_picker=True, include_presets=True
        )

        # Apply some styling to match the dark theme
        self.date_selector.setStyleSheet(
            """
            QGroupBox {
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 1.5ex;
                font-weight: bold;
                color: #e0e0e0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
            }
        """
        )

        # Add auto detect button manually to maintain that functionality
        # since it requires access to the directory
        auto_detect_button = QPushButton(self.tr("Auto Detect from Files"))
        auto_detect_button.setToolTip(
            self.tr("Automatically detect date range from files in the selected directory")
        )
        auto_detect_button.clicked.connect(self._auto_detect_date_range)
        auto_detect_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4c72b0;
                color: white;
                font-weight: bold;
                padding: 6px;
                border-radius: 4px;
                border: 1px solid #5d83c1;
            }
            QPushButton:hover {
                background-color: #5a80c0;
                border: 1px solid #6a90d0;
            }
            QPushButton:pressed {
                background-color: #3c629a;
                border: 1px solid #4c72b0;
            }
            QPushButton:disabled {
                background-color: #333;
                color: #777;
                border: 1px solid #444;
            }
        """
        )

        # Create container for the date selector and auto-detect button
        date_container = QWidget()
        date_layout = QVBoxLayout(date_container)
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.addWidget(self.date_selector)
        date_layout.addWidget(auto_detect_button)

        controls_layout.addWidget(date_container)

        # Satellite group with dark mode styling
        satellite_group = QGroupBox(self.tr("Satellite"))
        satellite_group.setStyleSheet(
            """
            QGroupBox {
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 1.5ex;
                font-weight: bold;
                color: #e0e0e0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
            }
        """
        )
        satellite_layout = QVBoxLayout()

        # Radio button styling for dark theme
        radio_style = """
            QRadioButton {
                color: #e0e0e0;
                spacing: 5px;
            }
            QRadioButton::indicator {
                width: 13px;
                height: 13px;
            }
            QRadioButton::indicator:unchecked {
                border: 1px solid #555;
                border-radius: 7px;
                background-color: #333;
            }
            QRadioButton::indicator:checked {
                border: 1px solid #4c72b0;
                border-radius: 7px;
                background-color: #4c72b0;
            }
        """

        # GOES-16 radio button
        self.goes16_radio = QRadioButton("GOES-16 (East)")
        self.goes16_radio.setToolTip(self.tr("GOES East (75.2°W)"))
        self.goes16_radio.setStyleSheet(radio_style)

        # GOES-18 radio button
        self.goes18_radio = QRadioButton("GOES-18 (West)")
        self.goes18_radio.setToolTip(self.tr("GOES West (137.2°W)"))
        self.goes18_radio.setStyleSheet(radio_style)
        self.goes18_radio.setChecked(True)  # Default to GOES-18

        satellite_layout.addWidget(self.goes16_radio)
        satellite_layout.addWidget(self.goes18_radio)

        # Auto-detect satellite button
        auto_detect_satellite_button = QPushButton(self.tr("Auto-Detect Satellite"))
        auto_detect_satellite_button.setToolTip(
            self.tr("Automatically detect satellite type from files in the selected directory")
        )
        auto_detect_satellite_button.clicked.connect(self._auto_detect_satellite)
        auto_detect_satellite_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4c72b0;
                color: white;
                font-weight: bold;
                padding: 6px;
                border-radius: 4px;
                border: 1px solid #5d83c1;
            }
            QPushButton:hover {
                background-color: #5a80c0;
                border: 1px solid #6a90d0;
            }
            QPushButton:pressed {
                background-color: #3c629a;
                border: 1px solid #4c72b0;
            }
            QPushButton:disabled {
                background-color: #333;
                color: #777;
                border: 1px solid #444;
            }
        """
        )
        satellite_layout.addWidget(auto_detect_satellite_button)

        # Interval
        interval_layout = QHBoxLayout()
        interval_label = QLabel(self.tr("Interval:"))
        interval_label.setStyleSheet("QLabel { color: #e0e0e0; }")

        # Spinbox with dark theme styling
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setRange(0, 60)
        self.interval_spinbox.setValue(10)  # Default to 10 minutes
        self.interval_spinbox.setSuffix(" min")
        self.interval_spinbox.setSpecialValueText("Auto-detect")
        self.interval_spinbox.setStyleSheet(
            """
            QSpinBox {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 2px;
                min-width: 70px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #444;
                border: 1px solid #555;
                border-radius: 2px;
                width: 14px;
                margin: 1px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #5a80c0;
            }
            QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {
                background-color: #3c629a;
            }
        """
        )

        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(self.interval_spinbox)

        satellite_layout.addLayout(interval_layout)
        satellite_group.setLayout(satellite_layout)
        controls_layout.addWidget(satellite_group)

        # Fetch options group with dark mode styling
        fetch_group = QGroupBox(self.tr("Fetch Options"))
        fetch_group.setStyleSheet(
            satellite_group.styleSheet()
        )  # Reuse styling from satellite group
        fetch_layout = QVBoxLayout()

        # Fetch source radio buttons
        self.auto_radio = QRadioButton("Auto (Hybrid CDN/S3)")
        self.auto_radio.setToolTip(
            self.tr("Automatically select CDN for recent data, S3 for older data")
        )
        self.auto_radio.setStyleSheet(radio_style)
        self.auto_radio.setChecked(True)

        self.cdn_radio = QRadioButton("CDN Only")
        self.cdn_radio.setToolTip(self.tr("NOAA STAR CDN (faster, but limited history)"))
        self.cdn_radio.setStyleSheet(radio_style)

        self.s3_radio = QRadioButton("S3 Only")
        self.s3_radio.setToolTip(self.tr("AWS S3 buckets (full history, NetCDF format)"))
        self.s3_radio.setStyleSheet(radio_style)

        self.local_radio = QRadioButton("Local Only")
        self.local_radio.setToolTip(
            self.tr("Only scan local files, don't fetch from remote sources")
        )
        self.local_radio.setStyleSheet(radio_style)

        fetch_layout.addWidget(self.auto_radio)

        # CDN option with settings button
        cdn_layout = QHBoxLayout()
        cdn_layout.addWidget(self.cdn_radio)
        self.cdn_settings_button = QToolButton()
        style = self.style()
        if style is not None:
            self.cdn_settings_button.setIcon(
                style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
            )
        self.cdn_settings_button.setToolTip(self.tr("Configure CDN settings"))
        self.cdn_settings_button.clicked.connect(self._configure_cdn)
        cdn_layout.addWidget(self.cdn_settings_button)
        cdn_layout.addStretch()
        fetch_layout.addLayout(cdn_layout)

        # S3 option with settings button
        s3_layout = QHBoxLayout()
        s3_layout.addWidget(self.s3_radio)
        self.s3_settings_button = QToolButton()
        style = self.style()
        if style is not None:
            self.s3_settings_button.setIcon(
                style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
            )
        self.s3_settings_button.setToolTip(self.tr("Configure AWS S3 settings"))
        self.s3_settings_button.clicked.connect(self._configure_s3)
        s3_layout.addWidget(self.s3_settings_button)
        s3_layout.addStretch()
        fetch_layout.addLayout(s3_layout)

        fetch_layout.addWidget(self.local_radio)

        # Checkbox styling for dark theme
        checkbox_style = """
            QCheckBox {
                color: #e0e0e0;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 13px;
                height: 13px;
                border: 1px solid #555;
                border-radius: 3px;
                background-color: #333;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #4c72b0;
                background-color: #4c72b0;
            }
            QCheckBox::indicator:unchecked:hover {
                border: 1px solid #4c72b0;
            }
        """

        # Auto-download checkbox
        self.auto_download_checkbox = QCheckBox(self.tr("Auto-Download Missing Files"))
        self.auto_download_checkbox.setToolTip(
            self.tr("Automatically download missing files after scan")
        )
        self.auto_download_checkbox.setStyleSheet(checkbox_style)
        fetch_layout.addWidget(self.auto_download_checkbox)

        # Force rescan checkbox
        self.force_rescan_checkbox = QCheckBox(self.tr("Force Rescan"))
        self.force_rescan_checkbox.setToolTip(
            self.tr("Ignore cached results and perform a new scan")
        )
        self.force_rescan_checkbox.setStyleSheet(checkbox_style)
        fetch_layout.addWidget(self.force_rescan_checkbox)

        fetch_group.setLayout(fetch_layout)
        controls_layout.addWidget(fetch_group)

        # Directory group with dark mode styling
        directory_group = QGroupBox(self.tr("Directory"))
        directory_group.setStyleSheet(
            satellite_group.styleSheet()
        )  # Reuse styling from satellite group
        directory_layout = QVBoxLayout()

        # Directory selection
        directory_select_layout = QHBoxLayout()
        self.directory_edit = QLineEdit()
        self.directory_edit.setReadOnly(True)
        self.directory_edit.setStyleSheet(
            """
            QLineEdit {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px;
            }
            QLineEdit:read-only {
                background-color: #333;
            }
        """
        )

        # Browse button styling
        self.directory_browse_button = QPushButton(self.tr("Browse..."))
        self.directory_browse_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4c72b0;
                color: white;
                font-weight: bold;
                padding: 6px;
                border-radius: 4px;
                border: 1px solid #5d83c1;
            }
            QPushButton:hover {
                background-color: #5a80c0;
                border: 1px solid #6a90d0;
            }
            QPushButton:pressed {
                background-color: #3c629a;
                border: 1px solid #4c72b0;
            }
            QPushButton:disabled {
                background-color: #333;
                color: #777;
                border: 1px solid #444;
            }
        """
        )
        self.directory_browse_button.setToolTip(
            self.tr("Browse for a directory containing GOES imagery")
        )

        directory_select_layout.addWidget(self.directory_edit)
        directory_select_layout.addWidget(self.directory_browse_button)
        directory_layout.addLayout(directory_select_layout)

        # Disk space info with dark mode styling
        self.disk_space_label = QLabel(self.tr("Disk space: 0 GB / 0 GB"))
        self.disk_space_label.setStyleSheet("QLabel { color: #e0e0e0; }")
        directory_layout.addWidget(self.disk_space_label)

        # Scan button with enhanced styling
        self.scan_button = QPushButton(self.tr("Verify Integrity"))
        self.scan_button.setMinimumHeight(40)
        self.scan_button.setProperty("primary", "true")
        self.scan_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_button.setMinimumWidth(150)
        directory_layout.addWidget(self.scan_button)

        # Cancel button with proper styling
        self.cancel_button = QPushButton(self.tr("Cancel"))
        self.cancel_button.setEnabled(False)
        self.cancel_button.setMinimumWidth(120)
        directory_layout.addWidget(self.cancel_button)

        directory_group.setLayout(directory_layout)
        controls_layout.addWidget(directory_group)

        main_layout.addWidget(controls_section)

        # Middle section: Progress and status
        progress_section = QWidget()
        progress_layout = QVBoxLayout(progress_section)
        progress_layout.setContentsMargins(0, 0, 0, 0)

        # Progress bar with improved styling from central stylesheet
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setMinimumHeight(24)
        progress_layout.addWidget(self.progress_bar)

        # Status message with default normal style
        self.status_label = QLabel(self.tr("Ready to scan"))
        self.status_label.setFont(QFont("", 0, QFont.Weight.Bold))
        self.status_label.setMinimumHeight(24)
        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        progress_layout.addWidget(self.status_label)

        main_layout.addWidget(progress_section)

        # Bottom section: Results table with dark mode styling
        results_group = QGroupBox(self.tr("Missing Timestamps"))
        results_group.setStyleSheet(
            satellite_group.styleSheet()
        )  # Reuse styling from satellite group
        results_layout = QVBoxLayout()

        # Table view with enhanced model and dark theme styling
        self.table_view = QTableView()
        self.table_model = EnhancedMissingTimestampsModel()
        self.table_view.setModel(self.table_model)

        # Get headers and handle possible None cases
        horizontal_header = self.table_view.horizontalHeader()
        vertical_header = self.table_view.verticalHeader()

        if horizontal_header is not None:
            horizontal_header.setSectionResizeMode(
                QHeaderView.ResizeMode.ResizeToContents
            )
            horizontal_header.setSectionResizeMode(
                5, QHeaderView.ResizeMode.Stretch
            )  # Path column

        if vertical_header is not None:
            vertical_header.setVisible(False)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._show_context_menu)
        # Connect double-click handler
        self.table_view.doubleClicked.connect(self._handle_table_double_click)

        # Apply dark mode styling to the table view
        self.table_view.setStyleSheet(
            """
            QTableView {
                background-color: #2d2d2d;
                color: #e0e0e0;
                gridline-color: #444;
                border: 1px solid #555;
                border-radius: 4px;
            }
            QTableView::item {
                padding: 4px;
            }
            QTableView::item:selected {
                background-color: #4c72b0;
                color: white;
            }
            QHeaderView::section {
                background-color: #3d3d3d;
                color: #e0e0e0;
                padding: 4px;
                border: 1px solid #555;
                border-radius: 0px;
                font-weight: bold;
            }
            QHeaderView::section:checked {
                background-color: #4c72b0;
            }
            QTableView QTableCornerButton::section {
                background-color: #3d3d3d;
                border: 1px solid #555;
            }
            QScrollBar:vertical {
                background-color: #2d2d2d;
                width: 14px;
                margin: 15px 0 15px 0;
                border: 1px solid #555;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #5d5d5d;
                min-height: 30px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #4c72b0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                background: none;
                height: 15px;
                subcontrol-position: bottom;
                subcontrol-origin: margin;
            }
        """
        )

        results_layout.addWidget(self.table_view)

        # Action buttons
        actions_layout = QHBoxLayout()

        # Action buttons with improved styling
        self.download_button = QPushButton(self.tr("Download Missing Files"))
        self.download_button.setEnabled(False)
        self.download_button.setProperty("primary", "true")
        self.download_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_button.setToolTip(
            self.tr("Download all missing files identified in the scan")
        )
        self.download_button.setMinimumWidth(180)
        actions_layout.addWidget(self.download_button)

        # Retry button for failed downloads
        self.retry_button = QPushButton(self.tr("Retry Failed Downloads"))
        self.retry_button.setEnabled(False)
        self.retry_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retry_button.setToolTip(
            self.tr("Retry downloading files that failed in the previous attempt")
        )
        self.retry_button.setMinimumWidth(180)
        actions_layout.addWidget(self.retry_button)

        # Advanced options button (dropdown menu)
        self.advanced_button = QPushButton(self.tr("Advanced Options ▼"))
        self.advanced_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.advanced_button.setToolTip(self.tr("Show additional advanced options"))
        self.advanced_button.clicked.connect(self._show_advanced_menu)
        actions_layout.addWidget(self.advanced_button)

        self.export_button = QPushButton(self.tr("Export Report"))
        self.export_button.setEnabled(False)
        self.export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_button.setToolTip(
            self.tr("Export a report of missing timestamps to a CSV file")
        )
        actions_layout.addWidget(self.export_button)

        self.cache_button = QPushButton(self.tr("Cache Info"))
        self.cache_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cache_button.setToolTip(
            self.tr("Show information about the current cache database")
        )
        actions_layout.addWidget(self.cache_button)

        # Reset database button (destructive action)
        self.reset_db_button = QPushButton(self.tr("Reset Database"))
        self.reset_db_button.setProperty("destructive", "true")
        self.reset_db_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_db_button.setToolTip(self.tr("Reset the database and clear all cached data"))
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
        self.retry_button.clicked.connect(self._retry_failed_downloads)
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

        # Default advanced options
        self.advanced_options: Dict[str, Union[int, bool, str]] = {
            "timeout": 60,
            "max_concurrent": 5,
            "retry_attempts": 2,
            "throttle_enabled": False,
            "throttle_speed": 1000,
            "process_priority": "normal",
            "auto_enhance": False,
            "false_color": False,
            "convert_netcdf": True,
            "desktop_notify": False,
            "sound_alerts": False,
        }

    def _connect_enhanced_signals(self) -> None:
        """Connect signals from the enhanced view model."""
        # Connect base signals
        self.view_model.status_updated.connect(self._update_status)
        self.view_model.status_type_changed.connect(self._update_status_type)
        self.view_model.progress_updated.connect(self._update_progress)
        self.view_model.missing_items_updated.connect(self._update_missing_items)
        self.view_model.scan_completed.connect(self._handle_scan_completed)
        self.view_model.download_progress_updated.connect(
            self._update_download_progress
        )
        self.view_model.download_item_updated.connect(self._update_download_item)

        # Connect enhanced signals
        enhanced_view_model = cast(EnhancedIntegrityCheckViewModel, self.view_model)
        enhanced_view_model.satellite_changed.connect(self._update_satellite_ui)
        enhanced_view_model.fetch_source_changed.connect(self._update_fetch_source_ui)
        enhanced_view_model.download_item_progress.connect(
            self._update_download_item_progress
        )
        enhanced_view_model.disk_space_updated.connect(self._update_disk_space)

        # Connect date range selector signals
        self.date_selector.dateRangeSelected.connect(self._on_date_range_selected)

    def _update_ui_from_view_model(self) -> None:
        """Update UI elements with the current state from the view model."""
        # Directory
        self.directory_edit.setText(str(self.view_model.base_directory))

        # Date range - use the unified date range selector
        self.date_selector.set_date_range(
            self.view_model.start_date, self.view_model.end_date
        )

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
        self._update_status_display(self.view_model.status_message)
        self._update_button_states()

    def _update_status_display(self, message: str, status_type: str = "normal") -> None:
        """
        Update the status display with improved visual styling based on message type.

        Args:
            message: The status message to display
            status_type: One of "normal", "success", "error", "warning", or "info"
        """
        # Detect status type from message content if not explicitly provided
        if status_type == "normal":
            if (
                "error" in message.lower()
                or "fail" in message.lower()
                or "unable" in message.lower()
            ):
                status_type = "error"
            elif "warn" in message.lower() or "caution" in message.lower():
                status_type = "warning"
            elif (
                "success" in message.lower()
                or "complete" in message.lower()
                or "done" in message.lower()
            ):
                status_type = "success"
            elif "info" in message.lower() or "note" in message.lower():
                status_type = "info"

        # Clear previous status
        self.status_label.setProperty("status", "")

        # Set the message
        self.status_label.setText(message)

        # Apply status-specific styling
        if status_type == "error":
            self.status_label.setProperty("status", "error")
        elif status_type == "warning":
            self.status_label.setProperty("status", "warning")
        elif status_type == "success":
            self.status_label.setProperty("status", "success")
        elif status_type == "info":
            self.status_label.setProperty("status", "info")

        # Force style refresh
        style = self.status_label.style()
        if style is not None:
            style.unpolish(self.status_label)
            style.polish(self.status_label)

    def _update_button_states(self) -> None:
        """Update the state of buttons based on the current view model state."""
        # Update scan button state
        # Check if base_directory exists
        has_directory = False
        if self.view_model.base_directory is not None:
            if isinstance(self.view_model.base_directory, Path):
                has_directory = self.view_model.base_directory.exists()
            # Removed unreachable code that was causing mypy issues

        self.scan_button.setEnabled(
            bool(
                has_directory
                and not self.view_model.is_scanning
                and not self.view_model.is_downloading
            )
        )

        # Update cancel button state
        self.cancel_button.setEnabled(
            self.view_model.is_scanning or self.view_model.is_downloading
        )

        # Update download button state - enable only if scan complete and has missing items
        has_missing = self.view_model.has_missing_items
        scan_complete = not self.view_model.is_scanning
        self.download_button.setEnabled(
            has_missing and scan_complete and not self.view_model.is_downloading
        )

        # Update export button state - enable if scan complete and has items
        self.export_button.setEnabled(has_missing and scan_complete)

        # Update retry button state - enable if there are any failed downloads
        if hasattr(self, "retry_button"):
            # Check if there are any failed downloads
            failed_items = [
                item
                for item in self.view_model.missing_items
                if not item.is_downloaded and item.download_error
            ]
            has_failed = len(failed_items) > 0
            self.retry_button.setEnabled(
                has_failed
                and not self.view_model.is_scanning
                and not self.view_model.is_downloading
            )

    def _update_disk_space(self, used_gb: float, total_gb: float) -> None:
        """Update the disk space information label."""
        if total_gb > 0:
            percent = int((used_gb / total_gb) * 100)
            self.disk_space_label.setText(
                f"Disk space: {used_gb:.1f} GB / {total_gb:.1f} GB ({percent}% used)"
            )

            # Change color if disk space is low
            if percent > 90:
                self.disk_space_label.setStyleSheet(
                    "QLabel { color: red; font-weight: bold; }"
                )
            elif percent > 80:
                self.disk_space_label.setStyleSheet("QLabel { color: orange; }")
            else:
                self.disk_space_label.setStyleSheet("")
        else:
            self.disk_space_label.setText(self.tr("Disk space: Unknown"))

    def _update_satellite_ui(self, satellite: SatellitePattern) -> None:
        """Update the UI based on the selected satellite."""
        if satellite == SatellitePattern.GOES_16 and not self.goes16_radio.isChecked():
            self.goes16_radio.setChecked(True)
        elif (
            satellite == SatellitePattern.GOES_18 and not self.goes18_radio.isChecked()
        ):
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

    def _show_context_menu(self, position: QPoint) -> None:
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
            action_show.triggered.connect(
                lambda: self._show_in_explorer(item.local_path)
            )
            menu.addAction(action_show)

        # Download action
        if not item.is_downloaded and not item.is_downloading:
            action_download = QAction("Download This File", self)
            action_download.triggered.connect(lambda: self._download_single_item(row))
            menu.addAction(action_download)

        # Show error details (if there's an error)
        if item.download_error:
            action_error_details = QAction("Show Error Details", self)
            action_error_details.triggered.connect(
                lambda: self._show_error_details(row)
            )
            menu.addAction(action_error_details)

        if menu.actions():
            viewport = self.table_view.viewport()
            if viewport is not None:
                menu.exec(viewport.mapToGlobal(position))

    def _show_advanced_menu(self) -> None:
        """Show the advanced options menu."""
        menu = QMenu(self)

        # Advanced Options action
        action_advanced = QAction("Advanced Configuration...", self)
        action_advanced.triggered.connect(self._show_advanced_options)
        menu.addAction(action_advanced)

        # Batch Operations action
        action_batch = QAction("Batch Operations...", self)
        action_batch.triggered.connect(self._show_batch_operations)
        menu.addAction(action_batch)

        # Network Diagnostics action
        action_network = QAction("Network Diagnostics...", self)
        action_network.triggered.connect(self._show_network_diagnostics)
        menu.addAction(action_network)

        # Visualization Options action
        action_visualization = QAction("Visualization Options...", self)
        action_visualization.triggered.connect(self._show_visualization_options)
        menu.addAction(action_visualization)

        # Save/Load Configuration submenu
        save_load_menu = QMenu("Save/Load Configuration", self)

        action_save = QAction("Save Current Configuration...", self)
        action_save.triggered.connect(self._save_configuration)
        save_load_menu.addAction(action_save)

        action_load = QAction("Load Configuration...", self)
        action_load.triggered.connect(self._load_configuration)
        save_load_menu.addAction(action_load)

        action_reset = QAction("Reset to Defaults", self)
        action_reset.triggered.connect(self._reset_configuration)
        save_load_menu.addAction(action_reset)

        menu.addMenu(save_load_menu)

        # Show the menu at the button's position
        menu.exec(
            self.advanced_button.mapToGlobal(self.advanced_button.rect().bottomLeft())
        )

    def _show_advanced_options(self) -> None:
        """Show the advanced options dialog."""
        dialog = AdvancedOptionsDialog(self)
        dialog.set_options(self.advanced_options)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Update advanced options
            self.advanced_options = dialog.get_options()

            # Apply the options to the view model
            enhanced_view_model = cast(EnhancedIntegrityCheckViewModel, self.view_model)

            # Apply timeout setting to S3/CDN store
            if hasattr(enhanced_view_model, "set_timeout"):
                enhanced_view_model.set_timeout(self.advanced_options["timeout"])

            # Apply max concurrent downloads setting
            if hasattr(enhanced_view_model, "set_max_concurrent_downloads"):
                enhanced_view_model.set_max_concurrent_downloads(
                    self.advanced_options["max_concurrent"]
                )

            # Apply auto-retry setting
            if hasattr(enhanced_view_model, "set_retry_attempts"):
                enhanced_view_model.set_retry_attempts(
                    self.advanced_options["retry_attempts"]
                )

            # Log the updated options
            LOGGER.info(f"Updated advanced options: {self.advanced_options}")

    def _show_batch_operations(self) -> None:
        """Show the batch operations dialog."""
        if not self.view_model.missing_items:
            QMessageBox.information(
                self,
                "Batch Operations",
                "No items available for batch operations. Please scan first.",
                QMessageBox.StandardButton.Ok,
            )
            return

        # Cast to List[EnhancedMissingTimestamp] as we know the view model uses the enhanced type
        enhanced_items = cast(
            List[EnhancedMissingTimestamp], self.view_model.missing_items
        )
        dialog = BatchOperationsDialog(enhanced_items, self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Get the selected options
            options = dialog.get_options()

            # Get the items based on the filter
            items = []
            if options["filter"] == "all":
                items = self.view_model.missing_items
            elif options["filter"] == "selected":
                selection_model = self.table_view.selectionModel()
                if selection_model is not None:
                    selected_indexes = selection_model.selectedRows()
                else:
                    selected_indexes = []
                items = [
                    self.view_model.missing_items[index.row()]
                    for index in selected_indexes
                ]
            elif options["filter"] == "failed":
                items = [
                    item
                    for item in self.view_model.missing_items
                    if not item.is_downloaded and item.download_error
                ]
            elif options["filter"] == "missing":
                items = [
                    item
                    for item in self.view_model.missing_items
                    if not item.is_downloaded
                ]
            elif options["filter"] == "downloaded":
                items = [
                    item for item in self.view_model.missing_items if item.is_downloaded
                ]

            # Perform the operation
            if options["operation"] == "download":
                self._batch_download_items(items)
            elif options["operation"] == "retry":
                self._batch_retry_items(items)
            elif options["operation"] == "export":
                self._batch_export_items(items)
            elif options["operation"] == "delete":
                self._batch_delete_items(items)

    def _batch_download_items(self, items: List[MissingTimestamp]) -> None:
        """Batch download the specified items."""
        # Filter out already downloaded items
        download_items = [item for item in items if not item.is_downloaded]

        if not download_items:
            QMessageBox.information(
                self,
                "Batch Download",
                "No items to download. All selected items are already downloaded.",
                QMessageBox.StandardButton.Ok,
            )
            return

        # Confirm the download
        result = QMessageBox.question(
            self,
            "Confirm Batch Download",
            f"Download {len(download_items)} missing files?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if result == QMessageBox.StandardButton.Yes:
            # Start the download
            # Use cast to inform mypy this is an EnhancedIntegrityCheckViewModel
            enhanced_vm = cast(EnhancedIntegrityCheckViewModel, self.view_model)
            enhanced_vm.download_missing_items(download_items)

    def _batch_retry_items(self, items: List[MissingTimestamp]) -> None:
        """Batch retry the specified items."""
        # Filter for items with download errors
        retry_items = [
            item for item in items if not item.is_downloaded and item.download_error
        ]

        if not retry_items:
            QMessageBox.information(
                self,
                "Batch Retry",
                "No failed downloads to retry among the selected items.",
                QMessageBox.StandardButton.Ok,
            )
            return

        # Confirm the retry
        result = QMessageBox.question(
            self,
            "Confirm Batch Retry",
            f"Retry {len(retry_items)} failed downloads?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if result == QMessageBox.StandardButton.Yes:
            # Start the retry
            # Use cast to inform mypy this is an EnhancedIntegrityCheckViewModel
            enhanced_vm = cast(EnhancedIntegrityCheckViewModel, self.view_model)
            enhanced_vm.retry_failed_downloads(retry_items)

    def _batch_export_items(self, items: List[MissingTimestamp]) -> None:
        """Batch export the specified items to CSV."""
        if not items:
            QMessageBox.information(
                self,
                "Batch Export",
                "No items to export based on the selected filter.",
                QMessageBox.StandardButton.Ok,
            )
            return

        # Ask for the export file path
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Missing Timestamps", "", "CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return

        # Add .csv extension if not present
        if not file_path.lower().endswith(".csv"):
            file_path += ".csv"

        try:
            # Write the CSV file
            with open(file_path, "w", newline="") as csvfile:
                import csv

                fieldnames = [
                    "timestamp",
                    "satellite",
                    "source",
                    "status",
                    "local_path",
                    "error",
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for item in items:
                    status = (
                        "downloaded"
                        if item.is_downloaded
                        else "error"
                        if item.download_error
                        else "missing"
                    )
                    writer.writerow(
                        {
                            "timestamp": item.timestamp.isoformat(),
                            "satellite": item.satellite
                            if hasattr(item, "satellite")
                            and isinstance(item.satellite, str)
                            else "Unknown",
                            "source": item.source
                            if hasattr(item, "source") and item.source
                            else "AUTO",
                            "status": status,
                            "local_path": item.local_path if item.local_path else "",
                            "error": item.download_error if item.download_error else "",
                        }
                    )

            QMessageBox.information(
                self,
                "Export Successful",
                f"Successfully exported {len(items)} items to {file_path}",
                QMessageBox.StandardButton.Ok,
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Error exporting data: {e}",
                QMessageBox.StandardButton.Ok,
            )

    def _batch_delete_items(self, items: List[MissingTimestamp]) -> None:
        """Batch delete the specified items from disk."""
        # Filter for downloaded items with local paths
        delete_items = [
            item for item in items if item.is_downloaded and item.local_path
        ]

        if not delete_items:
            QMessageBox.information(
                self,
                "Batch Delete",
                "No downloaded files to delete among the selected items.",
                QMessageBox.StandardButton.Ok,
            )
            return

        # Confirm the deletion
        result = QMessageBox.warning(
            self,
            "Confirm Batch Delete",
            f"Delete {len(delete_items)} files from disk? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if result == QMessageBox.StandardButton.Yes:
            # Delete the files
            deleted = 0
            errors = 0

            for item in delete_items:
                try:
                    # Delete the file
                    if item.local_path:
                        path = Path(item.local_path)
                        if path.exists():
                            path.unlink()

                            # Update the item status
                            item.is_downloaded = False
                            item.local_path = ""

                            # Update the model
                            index = self.view_model.missing_items.index(item)
                            self.table_model.updateItem(index, item)

                            deleted += 1
                except Exception as e:
                    LOGGER.error(f"Error deleting file {item.local_path}: {e}")
                    errors += 1

            # Show a summary
            if errors > 0:
                QMessageBox.warning(
                    self,
                    "Delete Operation Completed with Errors",
                    f"Deleted {deleted} files. {errors} files could not be deleted.",
                    QMessageBox.StandardButton.Ok,
                )
            else:
                QMessageBox.information(
                    self,
                    "Delete Operation Completed",
                    f"Successfully deleted {deleted} files.",
                    QMessageBox.StandardButton.Ok,
                )

    def _show_network_diagnostics(self) -> None:
        """Show network diagnostics dialog."""
        # Create a text browser dialog to display network diagnostics
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("Network Diagnostics"))
        dialog.setMinimumSize(700, 500)

        layout = QVBoxLayout(dialog)

        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)
        layout.addWidget(text_browser)

        # Add a refresh button
        refresh_button = QPushButton(self.tr("Refresh"))
        refresh_button.clicked.connect(
            lambda: self._update_network_diagnostics(text_browser)
        )

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(refresh_button)
        close_button = QPushButton(self.tr("Close"))
        close_button.clicked.connect(dialog.accept)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

        # Run diagnostics and update the text browser
        self._update_network_diagnostics(text_browser)

        dialog.exec()

    def _update_network_diagnostics(self, text_browser: QTextBrowser) -> None:
        """Update the network diagnostics text browser."""
        # Create a diagnostic report
        text_browser.clear()

        # Display a loading message
        text_browser.setHtml("<h3>Running network diagnostics...</h3>")
        QApplication.processEvents()

        # Get the enhanced view model
        enhanced_view_model = cast(EnhancedIntegrityCheckViewModel, self.view_model)

        # Get diagnostics from S3 store if available
        html = "<h2>Network Diagnostics Report</h2>"
        html += (
            f"<p><b>Timestamp:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
        )

        # Try to get download statistics from the S3 store
        from goesvfi.integrity_check.remote.s3_store import (
            DOWNLOAD_STATS,
            log_download_statistics,
        )

        # Add system info
        html += "<h3>System Information</h3>"
        html += "<table border='1' cellpadding='4' cellspacing='0'>"
        html += f"<tr><td><b>Hostname:</b></td><td>{DOWNLOAD_STATS.get(hostname, 'N/A')}</td></tr>"
        html += f"<tr><td><b>Session ID:</b></td><td>{DOWNLOAD_STATS.get(session_id, 'N/A')}</td></tr>"
        html += f"<tr><td><b>Start Time:</b></td><td>{DOWNLOAD_STATS.get(start_timestamp, 'N/A')}</td></tr>"
        html += "</table>"

        # Add download statistics
        html += "<h3>Download Statistics</h3>"
        html += "<table border='1' cellpadding='4' cellspacing='0'>"
        html += f"<tr><td><b>Total Attempts:</b></td><td>{DOWNLOAD_STATS.get('total_attempts', 0)}</td></tr>"
        html += f"<tr><td><b>Successful:</b></td><td>{DOWNLOAD_STATS.get('successful', 0)}</td></tr>"
        html += f"<tr><td><b>Failed:</b></td><td>{DOWNLOAD_STATS.get('failed', 0)}</td></tr>"
        html += f"<tr><td><b>Retry Count:</b></td><td>{DOWNLOAD_STATS.get('retry_count', 0)}</td></tr>"

        # Calculate success rate
        total = DOWNLOAD_STATS.get("total_attempts", 0)
        if isinstance(total, (int, float)) and total > 0:
            successful = DOWNLOAD_STATS.get("successful", 0)
            if isinstance(successful, (int, float)):
                success_rate = (successful / total) * 100
                html += f"<tr><td><b>Success Rate:</b></td><td>{success_rate:.1f}%</td></tr>"

        # Calculate average download time
        download_times = DOWNLOAD_STATS.get("download_times", [])
        if isinstance(download_times, list) and download_times:
            # Ensure we only have numeric values for the sum
            numeric_times = [t for t in download_times if isinstance(t, (int, float))]
            if numeric_times:
                avg_time = sum(numeric_times) / len(numeric_times)
            html += f"<tr><td><b>Average Download Time:</b></td><td>{avg_time:.2f} seconds</td></tr>"

        # Calculate total data transferred
        total_bytes = DOWNLOAD_STATS.get("total_bytes", 0)
        if isinstance(total_bytes, (int, float)) and total_bytes > 0:
            total_mb = total_bytes / (1024 * 1024)
            html += f"<tr><td><b>Total Data Transferred:</b></td><td>{total_mb:.2f} MB</td></tr>"

        html += "</table>"

        # Add error statistics
        html += "<h3>Error Statistics</h3>"
        html += "<table border='1' cellpadding='4' cellspacing='0'>"
        html += f"<tr><td><b>Not Found Errors:</b></td><td>{DOWNLOAD_STATS.get('not_found', 0)}</td></tr>"
        html += f"<tr><td><b>Auth Errors:</b></td><td>{DOWNLOAD_STATS.get('auth_errors', 0)}</td></tr>"
        html += f"<tr><td><b>Timeouts:</b></td><td>{DOWNLOAD_STATS.get('timeouts', 0)}</td></tr>"
        html += f"<tr><td><b>Network Errors:</b></td><td>{DOWNLOAD_STATS.get('network_errors', 0)}</td></tr>"
        html += "</table>"

        # Add recent errors
        errors = DOWNLOAD_STATS.get("errors", [])
        if errors:
            html += "<h3>Recent Errors</h3>"
            html += "<table border='1' cellpadding='4' cellspacing='0'>"
            html += "<tr><th>Error Type</th><th>Message</th><th>Timestamp</th></tr>"

            # Error entries should be dictionaries with type, message, and timestamp fields
            error_list = errors if isinstance(errors, list) else []
            for error in error_list:
                if isinstance(error, dict):
                    error_type = error.get("type", "Unknown")
                    message = error.get("message", "No message")
                    timestamp = error.get("timestamp", "Unknown")

                    html += f"<tr><td>{error_type}</td><td>{message}</td><td>{timestamp}</td></tr>"
                else:
                    # Handle non-dict errors (shouldn't happen with proper typing)
                    html += f"<tr><td colspan={3!r}>Invalid error format: {str(error)}</td></tr>"

            html += "</table>"

        # Set the HTML content
        text_browser.setHtml(html)

    def _show_visualization_options(self) -> None:
        """Show visualization options dialog."""
        # Visualization options are primarily false color settings
        # Create a dialog for visualization options
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("Visualization Options"))
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)

        # Image display options
        image_group = QGroupBox(self.tr("Image Display"))
        image_layout = QFormLayout()

        # Color scheme selection
        color_scheme_combo = QComboBox()
        color_schemes = [
            "Default",
            "Enhanced",
            "False Color",
            "High Contrast",
            "Grayscale",
        ]
        color_scheme_combo.addItems(color_schemes)
        color_scheme_combo.setCurrentText("Default")
        image_layout.addRow("Color Scheme:", color_scheme_combo)

        # Auto-enhance checkbox
        auto_enhance_checkbox = QCheckBox()
        auto_enhance_value = self.advanced_options.get("auto_enhance", False)
        auto_enhance_checkbox.setChecked(bool(auto_enhance_value))
        image_layout.addRow("Auto-enhance Images:", auto_enhance_checkbox)

        # Apply false color checkbox
        false_color_checkbox = QCheckBox()
        false_color_value = self.advanced_options.get("false_color", False)
        false_color_checkbox.setChecked(bool(false_color_value))
        image_layout.addRow("Apply False Color:", false_color_checkbox)

        image_group.setLayout(image_layout)
        layout.addWidget(image_group)

        # Preview option
        preview_group = QGroupBox(self.tr("Preview Settings"))
        preview_layout = QFormLayout()

        # Preview size
        preview_size_combo = QComboBox()
        preview_sizes = ["Small", "Medium", "Large", "Full Resolution"]
        preview_size_combo.addItems(preview_sizes)
        preview_size_combo.setCurrentText("Medium")
        preview_layout.addRow("Preview Size:", preview_size_combo)

        # Show previews checkbox
        show_previews_checkbox = QCheckBox()
        show_previews_checkbox.setChecked(True)
        preview_layout.addRow("Show Previews:", show_previews_checkbox)

        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        # Table display options
        table_group = QGroupBox(self.tr("Table Display"))
        table_layout = QFormLayout()

        # Timestamp format
        timestamp_format_combo = QComboBox()
        timestamp_formats = [
            "YYYY-MM-DD HH:MM:SS",
            "YYYY-MM-DD HH:MM",
            "MM/DD/YYYY HH:MM",
            "ISO Format",
        ]
        timestamp_format_combo.addItems(timestamp_formats)
        timestamp_format_combo.setCurrentText("YYYY-MM-DD HH:MM:SS")
        table_layout.addRow("Timestamp Format:", timestamp_format_combo)

        # Show file paths checkbox
        show_paths_checkbox = QCheckBox()
        show_paths_checkbox.setChecked(True)
        table_layout.addRow("Show File Paths:", show_paths_checkbox)

        table_group.setLayout(table_layout)
        layout.addWidget(table_group)

        # Add buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Update advanced options
            self.advanced_options["auto_enhance"] = auto_enhance_checkbox.isChecked()
            self.advanced_options["false_color"] = false_color_checkbox.isChecked()

            # Apply changes to view model if needed
            enhanced_view_model = cast(EnhancedIntegrityCheckViewModel, self.view_model)

            # TODO: Apply visualization options to view model

            # Refresh the table view to show updated formatting
            self.table_model.layoutChanged.emit()

    def _save_configuration(self) -> None:
        """Save the current configuration to a file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Configuration", "", "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return

        # Add .json extension if not present
        if not file_path.lower().endswith(".json"):
            file_path += ".json"

        try:
            # Create the configuration dictionary
            config = {
                "advanced_options": self.advanced_options,
                "satellite": self.goes16_radio.isChecked() and "GOES_16" or "GOES_18",
                "fetch_source": self.auto_radio.isChecked()
                and "AUTO"
                or self.cdn_radio.isChecked()
                and "CDN"
                or self.s3_radio.isChecked()
                and "S3"
                or "LOCAL",
                "interval_minutes": self.interval_spinbox.value(),
                "force_rescan": self.force_rescan_checkbox.isChecked(),
                "auto_download": self.auto_download_checkbox.isChecked(),
            }

            # Write the JSON file
            import json

            with open(file_path, "w") as f:
                json.dump(config, f, indent=2)

            QMessageBox.information(
                self,
                "Save Configuration",
                f"Configuration saved to {file_path}",
                QMessageBox.StandardButton.Ok,
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Save Configuration Error",
                f"Error saving configuration: {e}",
                QMessageBox.StandardButton.Ok,
            )

    def _load_configuration(self) -> None:
        """Load configuration from a file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Configuration", "", "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return

        try:
            # Read the JSON file
            import json

            with open(file_path, "r") as f:
                config = json.load(f)

            # Apply the configuration
            if "advanced_options" in config:
                # Update the advanced_options dict without redefining it
                for key, value in config["advanced_options"].items():
                    self.advanced_options[key] = value

            if "satellite" in config:
                if config["satellite"] == "GOES_16":
                    self.goes16_radio.setChecked(True)
                else:
                    self.goes18_radio.setChecked(True)

            if "fetch_source" in config:
                if config["fetch_source"] == "AUTO":
                    self.auto_radio.setChecked(True)
                elif config["fetch_source"] == "CDN":
                    self.cdn_radio.setChecked(True)
                elif config["fetch_source"] == "S3":
                    self.s3_radio.setChecked(True)
                else:
                    self.local_radio.setChecked(True)

            if "interval_minutes" in config:
                self.interval_spinbox.setValue(config["interval_minutes"])

            if "force_rescan" in config:
                self.force_rescan_checkbox.setChecked(config["force_rescan"])

            if "auto_download" in config:
                self.auto_download_checkbox.setChecked(config["auto_download"])

            QMessageBox.information(
                self,
                "Load Configuration",
                f"Configuration loaded from {file_path}",
                QMessageBox.StandardButton.Ok,
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Load Configuration Error",
                f"Error loading configuration: {e}",
                QMessageBox.StandardButton.Ok,
            )

    def _reset_configuration(self) -> None:
        """Reset configuration to defaults."""
        # Confirm reset
        result = QMessageBox.question(
            self,
            "Reset Configuration",
            "Reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if result == QMessageBox.StandardButton.Yes:
            # Reset advanced options
            # Clear the existing dictionary and repopulate with defaults
            self.advanced_options.clear()
            # Add default values
            default_options: Dict[str, Union[int, bool, str]] = {
                "timeout": 60,
                "max_concurrent": 5,
                "retry_attempts": 2,
                "throttle_enabled": False,
                "throttle_speed": 1000,
                "process_priority": "normal",
                "auto_enhance": False,
                "false_color": False,
                "convert_netcdf": True,
                "desktop_notify": False,
                "sound_alerts": False,
            }
            # Update the dictionary with default values
            self.advanced_options.update(default_options)

            # Reset satellite selection
            self.goes18_radio.setChecked(True)

            # Reset fetch source
            self.auto_radio.setChecked(True)

            # Reset interval
            self.interval_spinbox.setValue(10)

            # Reset checkboxes
            self.force_rescan_checkbox.setChecked(False)
            self.auto_download_checkbox.setChecked(False)

            QMessageBox.information(
                self,
                "Reset Configuration",
                "All settings have been reset to defaults.",
                QMessageBox.StandardButton.Ok,
            )

    def _handle_table_double_click(self, index: QModelIndex) -> None:
        """Handle double click on the table view."""
        if not index.isValid():
            return

        # Get the item
        row = index.row()
        item = self.view_model.missing_items[row]

        # If the item has an error, show error details
        if item.download_error:
            self._show_error_details(row)
        # If the item is downloaded, show in explorer
        elif item.is_downloaded and item.local_path:
            self._show_in_explorer(item.local_path)

    def _show_error_details(self, row_index: int) -> None:
        """Show detailed error information for a specific item.

        Args:
            row_index: The index of the row in the table
        """
        if row_index < 0 or row_index >= len(self.view_model.missing_items):
            return

        # Get the item
        item = self.view_model.missing_items[row_index]

        # Only show details if there's an error
        if not item.download_error:
            return

        # Get the error message
        error_msg = item.download_error

        # Extract error code if present
        error_code = "Unknown"
        if "[Error " in error_msg and "]" in error_msg:
            try:
                error_code = error_msg.split("[Error ")[1].split("]")[0]
            except:
                pass

        # Create title based on timestamp
        title = f"Error Details - {item.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

        # Show the detailed error dialog
        self._show_detailed_error_dialog(title, error_msg)

    def _show_in_explorer(self, path: str) -> None:
        """Show a file in the file explorer."""
        import platform
        import subprocess

        try:
            file_path = Path(path)
            if not file_path.exists():
                QMessageBox.warning(
                    self, "File Not Found", f"The file {path} does not exist."
                )
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
        QMessageBox.information(
            self,
            "Not Implemented",
            "Single item download is not yet implemented. Use the 'Download Missing Files' button instead.",
        )

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

    # Date preset methods removed as they are now handled by UnifiedDateRangeSelector

    def _on_date_range_selected(self, start_date: datetime, end_date: datetime) -> None:
        """
        Handle date range selection from the UnifiedDateRangeSelector.

        Args:
            start_date: The selected start date
            end_date: The selected end date
        """
        # Update the view model with the new date range
        self.view_model.start_date = start_date
        self.view_model.end_date = end_date

        # Log date range change
        LOGGER.debug(
            f"Date range changed: {start_date.isoformat()} to {end_date.isoformat()}"
        )

        # Emit our own signal for other components that might be listening
        self.date_range_changed.emit(start_date, end_date)

    def _auto_detect_date_range(self) -> None:
        """Auto-detect date range from files in the selected directory."""
        # Check if base directory is set and exists
        if (
            not self.view_model.base_directory
            or not self.view_model.base_directory.exists()
        ):
            QMessageBox.warning(
                self,
                "No Directory Selected",
                "Please select a directory first to auto-detect date range.",
            )
            return

        try:
            # Show wait cursor and processing message
            self.setCursor(Qt.CursorShape.WaitCursor)
            QApplication.processEvents()
            self.status_message = "Detecting date range from files..."

            # Get current satellite
            enhanced_view_model = cast(EnhancedIntegrityCheckViewModel, self.view_model)
            satellite = enhanced_view_model.satellite

            # Find date range
            from .time_index import TimeIndex

            LOGGER.debug(
                f"Attempting to auto-detect date range for {satellite.name} in {self.view_model.base_directory}"
            )

            start_date, end_date = TimeIndex.find_date_range_in_directory(
                self.view_model.base_directory, satellite
            )

            LOGGER.debug(f"Auto-detect found dates: start={start_date}, end={end_date}")

            if start_date is None or end_date is None:
                # No valid timestamps found
                QMessageBox.information(
                    self,
                    "No Valid Files Found",
                    f"No files with valid timestamps were found in the selected directory for {satellite.name}.\n\n"
                    f"Please check that the directory contains properly named GOES imagery files.",
                )
                return

            # Add some padding to the dates
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=0)

            # Set the date range in the unified date selector
            self.date_selector.set_date_range(start_date, end_date)

            # Update the view model with the new date range
            self.view_model.start_date = start_date
            self.view_model.end_date = end_date

            # Emit date range changed signal
            self.date_range_changed.emit(start_date, end_date)

            # Show success message
            QMessageBox.information(
                self,
                "Date Range Detected",
                f"Date range detected from files:\n\n"
                f"From: {start_date.strftime('%Y-%m-%d %H:%M')}\n"
                f"To: {end_date.strftime('%Y-%m-%d %H:%M')}",
            )
        except Exception as e:
            LOGGER.error(f"Error auto-detecting date range: {e}")
            import traceback

            LOGGER.error(traceback.format_exc())
            QMessageBox.critical(
                self,
                "Error Detecting Date Range",
                f"An error occurred while detecting date range:\n\n{str(e)}",
            )
        finally:
            # Restore cursor and status
            self.setCursor(Qt.CursorShape.ArrowCursor)
            QApplication.processEvents()
            self.status_message = "Ready to scan"

    def _configure_cdn(self) -> None:
        """Configure CDN settings."""
        enhanced_view_model = cast(EnhancedIntegrityCheckViewModel, self.view_model)

        dialog = CDNConfigDialog(self)
        dialog.set_cdn_resolution(enhanced_view_model.cdn_resolution)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            enhanced_view_model.update_cdn_resolution(dialog.get_cdn_resolution())

    def _configure_s3(self) -> None:
        """Configure S3 settings."""
        enhanced_view_model = cast(EnhancedIntegrityCheckViewModel, self.view_model)

        dialog = AWSConfigDialog(self)
        dialog.set_aws_profile(enhanced_view_model.aws_profile)
        dialog.set_aws_region(enhanced_view_model._s3_region)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            enhanced_view_model.set_aws_profile(dialog.get_aws_profile())
            enhanced_view_model._s3_region = dialog.get_aws_region()

    def _reset_database(self) -> None:
        """Reset the database."""
        reply = QMessageBox.question(
            self,
            "Reset Database",
            "Are you sure you want to reset the database? This will delete all cached data.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            enhanced_view_model = cast(EnhancedIntegrityCheckViewModel, self.view_model)
            enhanced_view_model.reset_database()

    def _browse_directory(self) -> None:
        """Browse for and select a directory with comprehensive error handling."""
        try:
            LOGGER.debug("Directory browse requested in enhanced integrity check tab")
            current_dir = self.view_model.base_directory

            # If the current directory doesn't exist, start from home
            if not current_dir.exists():
                current_dir = Path.home()
                LOGGER.debug(f"Using home directory as fallback: {current_dir}")

            # Open directory dialog with error handling
            try:
                LOGGER.debug(
                    f"Opening directory dialog with starting directory: {current_dir}"
                )

                # Set cursor to wait cursor to indicate operation in progress
                self.setCursor(Qt.CursorShape.WaitCursor)
                QApplication.processEvents()  # Process any pending events

                try:
                    directory = QFileDialog.getExistingDirectory(
                        self,
                        "Select Base Directory",
                        str(current_dir),
                        QFileDialog.Option.ShowDirsOnly,
                    )
                finally:
                    # Restore cursor regardless of outcome
                    self.setCursor(Qt.CursorShape.ArrowCursor)
                    QApplication.processEvents()

                LOGGER.debug(f"Selected directory: {directory}")

                if directory:
                    # Verify the directory is accessible
                    path_obj = Path(directory)

                    # Check if it's a valid directory
                    if not path_obj.exists() or not path_obj.is_dir():
                        LOGGER.error(
                            f"Selected path is not a valid directory: {directory}"
                        )
                        QMessageBox.warning(
                            self,
                            "Invalid Directory",
                            f"The selected path is not a valid directory:\n{directory}",
                        )
                        return

                    # Check if directory is readable
                    try:
                        next(path_obj.iterdir(), None)  # Try to read the first item
                    except PermissionError:
                        LOGGER.error(
                            f"Permission denied reading directory: {directory}"
                        )
                        QMessageBox.warning(
                            self,
                            "Permission Denied",
                            f"You don't have permission to read the selected directory:\n{directory}",
                        )
                        return
                    except Exception as e:
                        LOGGER.error(f"Error reading directory contents: {e}")
                        QMessageBox.warning(
                            self,
                            "Directory Access Error",
                            f"Could not access directory contents:\n{directory}\n\nError: {str(e)}",
                        )
                        return

                    # Set the directory in the view model
                    try:
                        LOGGER.debug(f"Setting base directory to: {directory}")
                        self.view_model.base_directory = path_obj
                        self.directory_edit.setText(directory)
                        self.directory_selected.emit(directory)
                    except Exception as e:
                        LOGGER.error(f"Error setting directory in view model: {e}")
                        QMessageBox.critical(
                            self,
                            "Error Setting Directory",
                            f"An error occurred while setting the directory in the application:\n\n{str(e)}",
                        )
                        return

                    # Update disk space info safely
                    try:
                        enhanced_view_model = cast(
                            EnhancedIntegrityCheckViewModel, self.view_model
                        )
                        used_gb, total_gb = enhanced_view_model.get_disk_space_info()
                        self._update_disk_space(used_gb, total_gb)
                    except Exception as e:
                        LOGGER.error(f"Error updating disk space info: {e}")
                        # Don't show error to user for this non-critical operation, just log it

                    # Update button states
                    try:
                        self._update_button_states()
                    except Exception as e:
                        LOGGER.error(f"Error updating button states: {e}")
                        # Don't show error to user for this non-critical operation, just log it

                    LOGGER.debug("Directory browse completed successfully")
            except Exception as e:
                LOGGER.error(f"Error opening directory dialog: {e}")
                import traceback

                LOGGER.error(traceback.format_exc())
                QMessageBox.critical(
                    self,
                    "Error Opening Directory Dialog",
                    f"An error occurred while opening the directory dialog:\n\n{str(e)}",
                )
        except Exception as e:
            LOGGER.error(f"Unhandled exception in _browse_directory: {e}")
            import traceback

            LOGGER.error(traceback.format_exc())
            QMessageBox.critical(
                self,
                "Unexpected Error",
                f"An unexpected error occurred while browsing for a directory:\n\n{str(e)}",
            )

    def _start_enhanced_scan(self) -> None:
        """Start the enhanced scan operation."""
        try:
            # Log the start of scan operation
            LOGGER.debug("Starting enhanced scan operation")

            # Get the date range from the UnifiedDateRangeSelector
            start_date, end_date = self.date_selector.get_date_range()

            # Update view model with dates
            self.view_model.start_date = start_date
            self.view_model.end_date = end_date

            # Log date range
            LOGGER.debug(
                f"Scan date range: {start_date.isoformat()} to {end_date.isoformat()}"
            )

            # Get other parameters
            interval_minutes = self.interval_spinbox.value()
            force_rescan = self.force_rescan_checkbox.isChecked()
            auto_download = self.auto_download_checkbox.isChecked()

            self.view_model.interval_minutes = interval_minutes
            self.view_model.force_rescan = force_rescan
            self.view_model.auto_download = auto_download

            LOGGER.debug(
                f"Scan parameters: interval={interval_minutes}min, force_rescan={force_rescan}, auto_download={auto_download}"
            )

            # Log directory
            LOGGER.debug(f"Scan directory: {self.view_model.base_directory}")

            # Clear the table
            self.table_model.setItems([])

            # Get satellite
            enhanced_view_model = cast(EnhancedIntegrityCheckViewModel, self.view_model)
            satellite = enhanced_view_model.satellite
            fetch_source = enhanced_view_model.fetch_source

            LOGGER.debug(
                f"Satellite: {satellite.name}, Fetch source: {fetch_source.name}"
            )

            # Show detailed scan information to the user
            self.status_label.setText(
                f"<span style='color: #66aaff; font-weight: bold;'>Starting scan:</span> "
                f"{satellite.name} satellite, {fetch_source.name} source, "
                f"interval={interval_minutes}min, "
                f"{start_date.strftime('%Y-%m-%d %H:%M')} to {end_date.strftime('%Y-%m-%d %H:%M')}"
            )

            # Start enhanced scan
            LOGGER.debug("Calling start_enhanced_scan on view model")
            enhanced_view_model.start_enhanced_scan()

            # Update UI
            self._update_button_states()

            LOGGER.debug("Enhanced scan started successfully")
        except Exception as e:
            LOGGER.error(f"Error starting enhanced scan: {e}")
            import traceback

            LOGGER.error(traceback.format_exc())
            QMessageBox.critical(
                self,
                "Error Starting Scan",
                f"An error occurred while starting the scan:\n\n{str(e)}",
            )

    def _download_missing(self) -> None:
        """Start downloading missing files with enhanced functionality."""
        if not self.view_model.has_missing_items:
            QMessageBox.information(
                self, "No Missing Files", "There are no missing files to download."
            )
            return

        # Start enhanced downloads
        enhanced_view_model = cast(EnhancedIntegrityCheckViewModel, self.view_model)
        enhanced_view_model.start_enhanced_downloads()

        # Reset progress bar style in case it was colored for success/failure
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid #444;
                border-radius: 2px;
                text-align: center;
                background-color: #333;
            }
            QProgressBar::chunk {
                background-color: #4c72b0;
                border-radius: 1px;
            }
        """
        )

        # Update UI
        self._update_button_states()

        # Clear status and force UI update
        self.status_label.setText(
            self.tr("<span style='color: #66aaff; font-weight: bold;'>Starting download of missing files...</span>")
        )
        QApplication.processEvents()

    def _retry_failed_downloads(self) -> None:
        """Retry downloading files that failed in the previous attempt."""
        enhanced_view_model = cast(EnhancedIntegrityCheckViewModel, self.view_model)

        # Check if there are any failed downloads to retry
        failed_items = [
            item
            for item in enhanced_view_model.missing_items
            if not item.is_downloaded and item.download_error
        ]

        if not failed_items:
            QMessageBox.information(
                self, "No Failed Downloads", "There are no failed downloads to retry."
            )
            return

        # Show confirmation dialog
        num_failed = len(failed_items)
        result = QMessageBox.question(
            self,
            "Retry Failed Downloads",
            f"Do you want to retry {num_failed} failed downloads?\n\n"
            f"If you're encountering database errors, it's recommended to restart the application first.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if result == QMessageBox.StandardButton.No:
            return

        # Reset the error state of failed items
        for i, item in enumerate(enhanced_view_model.missing_items):
            if item.download_error:
                item.download_error = ""
                item.is_downloading = False
                # Update the item in the table
                enhanced_view_model.download_item_updated.emit(i, item)

        # Start the retry download operation
        enhanced_view_model.start_enhanced_downloads()

        # Reset progress bar style
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid #444;
                border-radius: 2px;
                text-align: center;
                background-color: #333;
            }
            QProgressBar::chunk {
                background-color: #4c72b0;
                border-radius: 1px;
            }
        """
        )

        # Update button states
        self._update_button_states()

        # Update status
        self.status_label.setText(
            f"<span style='color: #66aaff; font-weight: bold;'>Retrying {num_failed} failed downloads...</span>"
        )
        QApplication.processEvents()

    def _auto_detect_satellite(self) -> None:
        """Auto-detect satellite type from files in the selected directory."""
        # Check if base directory is set and exists
        if (
            not self.view_model.base_directory
            or not self.view_model.base_directory.exists()
        ):
            QMessageBox.warning(
                self,
                "No Directory Selected",
                "Please select a directory first to auto-detect satellite type.",
            )
            return

        try:
            # Show wait cursor and processing message
            self.setCursor(Qt.CursorShape.WaitCursor)
            QApplication.processEvents()
            self._update_status_display(
                "Detecting satellite type from files...", "info"
            )

            # Create progress dialog to show progress
            progress_dialog = QProgressDialog(
                "Scanning files...", "Cancel", 0, 100, self
            )
            progress_dialog.setWindowTitle(self.tr("Detecting Satellite Type"))
            progress_dialog.setModal(True)
            progress_dialog.setAutoClose(True)
            progress_dialog.setAutoReset(True)
            progress_dialog.setValue(0)
            progress_dialog.show()
            QApplication.processEvents()

            # Check for both satellites
            directory = self.view_model.base_directory
            enhanced_view_model = cast(EnhancedIntegrityCheckViewModel, self.view_model)

            LOGGER.info(
                f"Auto-detect satellite: Starting scan of directory {directory}"
            )

            # First check for GOES-16
            progress_dialog.setLabelText("Scanning for GOES-16 files...")
            progress_dialog.setValue(10)
            QApplication.processEvents()

            from .time_index import SatellitePattern, TimeIndex

            LOGGER.info(
                f"Auto-detect satellite: Scanning for GOES-16 files in {directory}"
            )

            # Log number of files in the directory
            try:
                png_files = list(directory.glob("**/*.png"))
                all_files = list(directory.glob("**/*"))
                LOGGER.info(
                    f"Directory statistics: {len(png_files)} PNG files, {len(all_files)} total files"
                )
                # Log a few sample filenames for debugging
                if png_files:
                    LOGGER.info(f"Sample PNG files: {[f.name for f in png_files[:5]]}")
                if len(all_files) > len(png_files):
                    non_png_samples = [
                        f.name for f in all_files if f.suffix.lower() != ".png"
                    ][:5]
                    LOGGER.info(f"Sample non-PNG files: {non_png_samples}")
            except Exception as dir_error:
                LOGGER.error(f"Error listing directory contents: {dir_error}")

            goes16_files = []
            try:
                LOGGER.info("Beginning GOES-16 file scan with pattern matching")
                goes16_files = TimeIndex.scan_directory_for_timestamps(
                    directory, SatellitePattern.GOES_16
                )
                LOGGER.info(
                    f"Auto-detect satellite: Found {len(goes16_files)} GOES-16 files"
                )
                # Log the first few timestamps found, if any
                if goes16_files:
                    LOGGER.info(
                        f"Sample GOES-16 timestamps: {[ts.isoformat() for ts in goes16_files[:5]]}"
                    )
            except Exception as scan_error:
                LOGGER.error(
                    f"Auto-detect satellite: Error scanning for GOES-16 files: {scan_error}"
                )
                LOGGER.error(traceback.format_exc())
                # Try to get more context about what went wrong
                try:
                    # If the error was in pattern matching, try to log filesystem state
                    LOGGER.info(
                        f"Directory exists: {directory.exists()}, is directory: {directory.is_dir()}"
                    )

                    # Check permissions
                    import os

                    try:
                        is_readable = os.access(directory, os.R_OK)
                        is_writable = os.access(directory, os.W_OK)
                        is_executable = os.access(directory, os.X_OK)
                        LOGGER.info(
                            f"Directory permissions: Read={is_readable}, Write={is_writable}, Execute={is_executable}"
                        )
                    except Exception as perm_error:
                        LOGGER.error(
                            f"Error checking directory permissions: {perm_error}"
                        )
                except Exception as info_error:
                    LOGGER.error(f"Error getting directory information: {info_error}")

            progress_dialog.setValue(50)
            progress_dialog.setLabelText("Scanning for GOES-18 files...")
            QApplication.processEvents()

            # Then check for GOES-18
            LOGGER.info(
                f"Auto-detect satellite: Scanning for GOES-18 files in {directory}"
            )

            goes18_files = []
            try:
                LOGGER.info("Beginning GOES-18 file scan with pattern matching")
                goes18_files = TimeIndex.scan_directory_for_timestamps(
                    directory, SatellitePattern.GOES_18
                )
                LOGGER.info(
                    f"Auto-detect satellite: Found {len(goes18_files)} GOES-18 files"
                )
                # Log the first few timestamps found, if any
                if goes18_files:
                    LOGGER.info(
                        f"Sample GOES-18 timestamps: {[ts.isoformat() for ts in goes18_files[:5]]}"
                    )
            except Exception as scan_error:
                LOGGER.error(
                    f"Auto-detect satellite: Error scanning for GOES-18 files: {scan_error}"
                )
                LOGGER.error(traceback.format_exc())

            progress_dialog.setValue(90)
            progress_dialog.setLabelText("Analyzing results...")
            QApplication.processEvents()

            # Choose satellite based on file count
            goes16_count = len(goes16_files)
            goes18_count = len(goes18_files)

            LOGGER.info(
                f"Auto-detect satellite: Found {goes16_count} GOES-16 files and {goes18_count} GOES-18 files"
            )

            if goes16_count == 0 and goes18_count == 0:
                # No valid files found
                error_msg = f"No valid GOES files found. Directory might not contain proper GOES imagery: {directory}"
                LOGGER.error(f"Auto-detect satellite: {error_msg}")

                # Log more detailed information about the directory contents
                try:
                    all_files = list(directory.glob("**/*.*"))
                    file_stats = {".png": 0, ".jpg": 0, ".nc": 0, ".txt": 0, "other": 0}
                    LOGGER.info(f"Total files found: {len(all_files)}")

                    for file in all_files:
                        ext = file.suffix.lower()
                        if ext in file_stats:
                            file_stats[ext] += 1
                        else:
                            file_stats["other"] += 1

                    LOGGER.info(f"File extension statistics: {file_stats}")

                    # Log a sample of filenames for pattern analysis
                    sample_files = [f.name for f in all_files[:20]]
                    LOGGER.info(f"Sample filenames: {sample_files}")
                except Exception as info_error:
                    LOGGER.error(
                        f"Error gathering additional directory information: {info_error}"
                    )

                QMessageBox.information(
                    self,
                    "No Valid Files Found",
                    "No valid GOES-16 or GOES-18 files were found in the selected directory.\n\n"
                    "Please check that the directory contains properly named GOES imagery files.\n\n"
                    "Expected filename patterns:\n"
                    "- goes16_YYYYMMDD_HHMMSS_band13.png\n"
                    "- goes18_YYYYMMDD_HHMMSS_band13.png\n"
                    "- YYYYDDDHHMMSS_GOES16-ABI-FD-13-*.jpg\n"
                    "- YYYYDDDHHMMSS_GOES18-ABI-FD-13-*.jpg",
                )
                return

            # Select the satellite with more files
            if goes16_count > goes18_count:
                # Select GOES-16
                LOGGER.info(
                    f"Auto-detect satellite: Selected GOES-16 based on file count ({goes16_count} vs {goes18_count})"
                )
                enhanced_view_model.satellite = SatellitePattern.GOES_16
                self.goes16_radio.setChecked(True)
                satellite_name = "GOES-16 (East)"
            else:
                # Select GOES-18
                LOGGER.info(
                    f"Auto-detect satellite: Selected GOES-18 based on file count ({goes18_count} vs {goes16_count})"
                )
                enhanced_view_model.satellite = SatellitePattern.GOES_18
                self.goes18_radio.setChecked(True)
                satellite_name = "GOES-18 (West)"

            progress_dialog.setValue(100)
            progress_dialog.close()

            # Show success message
            QMessageBox.information(
                self,
                "Satellite Type Detected",
                f"Detected {satellite_name} as the primary satellite in this directory.\n\n"
                f"GOES-16 files found: {goes16_count}\n"
                f"GOES-18 files found: {goes18_count}",
            )

            # Update the UI based on the detected satellite
            self._update_satellite_ui(enhanced_view_model.satellite)
            LOGGER.info(
                f"Auto-detect satellite: Completed successfully, selected {satellite_name}"
            )

        except Exception as e:
            LOGGER.error(
                f"Auto-detect satellite: Critical error in satellite detection: {e}"
            )
            import traceback

            LOGGER.error(traceback.format_exc())

            # Try to get more diagnostic information about the error
            error_context = ""
            try:
                if hasattr(e, "__dict__"):
                    error_context = f"Error attributes: {str(e.__dict__)}"
                    LOGGER.error(error_context)
            except:
                pass

            QMessageBox.critical(
                self,
                "Error Detecting Satellite Type",
                f"An error occurred while detecting satellite type:\n\n{str(e)}\n\n"
                f"Please check if the directory contains valid GOES satellite imagery files.\n"
                f"See the application log for more details.",
            )
        finally:
            # Restore cursor and status
            self.setCursor(Qt.CursorShape.ArrowCursor)
            QApplication.processEvents()
            self._update_status_display("Ready to scan", "normal")

    # Override parent methods with enhanced versions

    def _update_progress(self, current: int, total: int, eta: float) -> None:
        """Update the progress bar with enhanced information."""
        progress_percent = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(progress_percent)

        # Get the current status message to detect if we're in a step or phase
        status_text = self.status_label.text()
        is_step_operation = "Step " in status_text
        is_phase_operation = "Phase " in status_text

        # Custom format based on whether we're showing steps/phases
        if is_step_operation or is_phase_operation:
            # For step/phase operations, we show progress within the operation
            if is_step_operation:
                # For steps (like "Step 3/5: Doing something"), extract step info
                try:
                    step_parts = status_text.split(":", 1)[0].strip()
                    if "/" in step_parts:
                        current_step, total_steps = (
                            step_parts.split("/", 1)[0].split(" ")[-1],
                            step_parts.split("/", 1)[1].split(" ")[0],
                        )
                        step_info = f"Step {current_step}/{total_steps}"
                    else:
                        step_info = "Step progress"
                except:
                    step_info = "Step progress"

                self.progress_bar.setFormat(
                    f"{progress_percent}% - {step_info} ({current}/{total})"
                )
            elif is_phase_operation:
                # For phases (like "Phase 1/2: Doing something"), extract phase info
                try:
                    phase_parts = status_text.split(":", 1)[0].strip()
                    if "/" in phase_parts:
                        current_phase, total_phases = (
                            phase_parts.split("/", 1)[0].split(" ")[-1],
                            phase_parts.split("/", 1)[1].split(" ")[0],
                        )
                        phase_info = f"Phase {current_phase}/{total_phases}"
                    else:
                        phase_info = "Phase progress"
                except:
                    phase_info = "Phase progress"

                self.progress_bar.setFormat(
                    f"{progress_percent}% - {phase_info} ({current}/{total})"
                )
        else:
            # For regular operations or when ETA is available
            if eta > 0:
                eta_minutes = int(eta / 60)
                eta_seconds = int(eta % 60)
                self.progress_bar.setFormat(
                    f"{progress_percent}% - ETA: {eta_minutes}m {eta_seconds}s ({current}/{total})"
                )
            else:
                self.progress_bar.setFormat(f"{progress_percent}% ({current}/{total})")

        # Process events to ensure UI updates
        QApplication.processEvents()

    def _update_status(self, message: str) -> None:
        """Update the status message with enhanced formatting."""
        # Log the incoming message for debugging
        LOGGER.debug(f"Status update received: '{message}'")

        # Add additional styling and details to status messages

        # Check for step indicators like "Step X/Y" in the message
        step_indicator = ""
        if "Step " in message and "/" in message.split("Step ")[1]:
            # Extract and format the step indicator for emphasis
            step_parts = message.split(":", 1)
            if len(step_parts) > 1:
                step_info = step_parts[0].strip()
                details = step_parts[1].strip()

                # Format with step info highlighted
                if "Step 5/5" in step_info and "Scan complete" in message:
                    # Final step with success - green
                    formatted_message = f"<span style='color: #66ff66; font-weight: bold;'>{step_info}:</span> {details}"
                    LOGGER.debug(f"Formatted as completion: '{formatted_message}'")
                else:
                    # Progress step - blue
                    formatted_message = f"<span style='color: #66aaff; font-weight: bold;'>{step_info}:</span> {details}"
                    LOGGER.debug(f"Formatted as step progress: '{formatted_message}'")

                self.status_label.setText(formatted_message)
                LOGGER.debug(f"Status label updated with step formatting")
                QApplication.processEvents()
                return

        # For messages without step indicators, use general category detection
        if "error" in message.lower() or "failed" in message.lower():
            # Error message - make it red and bold
            formatted_message = (
                f"<span style='color: #ff6666; font-weight: bold;'>{message}</span>"
            )

            # For certain common errors, provide extra help based on detected error patterns
            if "unexpected error" in message.lower():
                error_details = (
                    "<br><span style='color: #ffaaaa;'><b>Troubleshooting Tips:</b><br>"
                )

                # Different help based on the specific error context
                if "goes-16" in message.lower() or "goes-18" in message.lower():
                    # Satellite-specific error tips
                    if "auto" in message.lower() and "detect" in message.lower():
                        # Auto-detection error tips
                        error_details += (
                            "• Check if your files follow the correct GOES naming pattern<br>"
                            "• Ensure directory contains GOES-16 or GOES-18 files<br>"
                            "• Try manually selecting the satellite type instead<br>"
                            "• Check the application log for detailed error messages</span>"
                        )
                    elif "fetch" in message.lower() or "download" in message.lower():
                        # Download error tips
                        error_details += (
                            "• Check your internet connection<br>"
                            "• Verify you can access AWS S3 services<br>"
                            "• Ensure the timestamp exists in NOAA archives<br>"
                            "• Try a different timestamp or date range<br>"
                            "• Check available disk space</span>"
                        )
                    else:
                        # General satellite error tips
                        error_details += (
                            "• Check your internet connection<br>"
                            "• Verify satellite selection is correct<br>"
                            "• Try a smaller date range<br>"
                            "• Try setting interval to 10 minutes manually<br>"
                            "• Check the application log for more details</span>"
                        )
                elif "aws" in message.lower() or "s3" in message.lower():
                    # S3-specific error tips
                    error_details += (
                        "• Check your internet connection<br>"
                        "• Verify AWS S3 is accessible from your network<br>"
                        "• Try using CDN source instead of S3<br>"
                        "• Check for firewall or proxy restrictions<br>"
                        "• The timestamp may not be available in NOAA archives</span>"
                    )
                elif "timeout" in message.lower() or "connection" in message.lower():
                    # Network error tips
                    error_details += (
                        "• Check your internet connection<br>"
                        "• AWS S3 may be experiencing issues<br>"
                        "• Your network might be blocking S3 access<br>"
                        "• Try using a different network connection<br>"
                        "• Try again later</span>"
                    )
                elif "file" in message.lower() and "not found" in message.lower():
                    # Missing file error tips
                    error_details += (
                        "• The requested timestamp may not exist in NOAA archives<br>"
                        "• Try a different timestamp or date range<br>"
                        "• Verify satellite selection (GOES-16 vs GOES-18)<br>"
                        "• Data might be available via different source</span>"
                    )
                else:
                    # Generic error tips
                    error_details += (
                        "• Check your internet connection<br>"
                        "• Verify satellite selection is correct<br>"
                        "• Try a smaller date range<br>"
                        "• Check the application log for more details</span>"
                    )

                formatted_message += error_details
                LOGGER.debug(f"Enhanced error message displayed for: {message}")

            # For specific S3-related errors, add more detailed help
            elif "access denied" in message.lower() or "permission" in message.lower():
                formatted_message += (
                    "<br><span style='color: #ffaaaa;'><b>Access Issue Tips:</b><br>"
                    "• NOAA buckets should be publicly accessible<br>"
                    "• Your network may be restricting AWS S3 access<br>"
                    "• Check for firewall or proxy settings<br>"
                    "• Try CDN source instead of S3</span>"
                )

            # For timeout errors, add network troubleshooting
            elif "timeout" in message.lower():
                formatted_message += (
                    "<br><span style='color: #ffaaaa;'><b>Connection Tips:</b><br>"
                    "• Check your internet connection speed and stability<br>"
                    "• AWS S3 may be experiencing high load<br>"
                    "• Try downloading fewer files at once<br>"
                    "• Try again later</span>"
                )

        elif "complete" in message.lower() or "success" in message.lower():
            # Success message - make it green and bold
            formatted_message = (
                f"<span style='color: #66ff66; font-weight: bold;'>{message}</span>"
            )

            # Add a note for download completions with suggestions
            if "download" in message.lower() and "complete" in message.lower():
                if "0 successful" in message.lower() or "failed" in message.lower():
                    # Failed downloads - add help text
                    formatted_message += (
                        "<br><span style='color: #ff9966;'><b>Download Issues Tips:</b><br>"
                        "• Check the application log for detailed error reasons<br>"
                        "• Try a different date range or satellite<br>"
                        "• Verify your internet connection</span>"
                    )

        elif (
            "scanning" in message.lower()
            or "downloading" in message.lower()
            or "step" in message.lower()
        ):
            # In-progress message - make it blue and bold
            formatted_message = (
                f"<span style='color: #66aaff; font-weight: bold;'>{message}</span>"
            )

            # Add more context for scan operations
            if "scanning" in message.lower():
                formatted_message += (
                    "<br><span style='color: #aaccff;'>"
                    "This may take a few moments depending on the date range and interval.</span>"
                )

            # Add more context for download operations
            elif "download" in message.lower():
                formatted_message += (
                    "<br><span style='color: #aaccff;'>"
                    "Download speed depends on your internet connection and AWS S3 availability.</span>"
                )

        elif "detected" in message.lower() and (
            "satellite" in message.lower() or "goes" in message.lower()
        ):
            # Satellite detection message - specialized formatting
            formatted_message = (
                f"<span style='color: #66aaff; font-weight: bold;'>{message}</span>"
                f"<br><span style='color: #aaccff;'>Auto-detection complete. "
                f"You can proceed with the integrity check.</span>"
            )

        else:
            # Regular message - just make it bold
            formatted_message = f"<b>{message}</b>"

        self.status_label.setText(formatted_message)

        # Process events to ensure UI updates
        QApplication.processEvents()

    def _update_download_progress(self, current: int, total: int) -> None:
        """Update the progress bar for downloads with enhanced information."""
        if total <= 0:
            self.progress_bar.setValue(0)
            return

        progress_percent = int((current / total) * 100)
        self.progress_bar.setValue(progress_percent)

        # Calculate download rate when available
        download_rate_text = ""
        if hasattr(self, "_last_progress_update_time") and hasattr(
            self, "_last_progress_count"
        ):
            time_diff = time.time() - self._last_progress_update_time
            if time_diff > 0:
                items_diff = current - self._last_progress_count
                if (
                    items_diff > 0 and time_diff >= 1.0
                ):  # Only calculate if at least 1 second passed
                    download_rate = items_diff / time_diff  # items per second
                    download_rate_text = f" | {download_rate:.1f} files/sec"

                    # Update ETA estimate
                    if download_rate > 0:
                        remaining_items = total - current
                        eta_seconds = remaining_items / download_rate
                        if eta_seconds > 60:
                            eta_text = (
                                f" | ETA: {int(eta_seconds/60)}m {int(eta_seconds%60)}s"
                            )
                        else:
                            eta_text = f" | ETA: {int(eta_seconds)}s"
                        download_rate_text += eta_text

        # Store current values for next calculation
        self._last_progress_update_time = time.time()
        self._last_progress_count = current

        # Update progress bar format with rate information
        self.progress_bar.setFormat(
            f"Downloading: {progress_percent}% ({current}/{total}){download_rate_text}"
        )

        # Update status message with more detailed information
        status_text = (
            f"<span style='color: #66aaff; font-weight: bold;'>"
            f"Downloading files: {current} of {total} ({progress_percent}%)</span>"
        )

        # Add download rate and success/failure info if available
        if hasattr(self, "_downloaded_success_count") and hasattr(
            self, "_downloaded_failed_count"
        ):
            success_count = getattr(self, "_downloaded_success_count", 0)
            failed_count = getattr(self, "_downloaded_failed_count", 0)
            if success_count > 0 or failed_count > 0:
                status_text += f"<br><span style='color: #aaccff;'>" f"Status: "
                if success_count > 0:
                    status_text += f"<span style='color: #66ff66;'>{success_count} successful</span>"
                    if failed_count > 0:
                        status_text += ", "
                if failed_count > 0:
                    status_text += (
                        f"<span style='color: #ff6666;'>{failed_count} failed</span>"
                    )
                status_text += f"{download_rate_text}</span>"

        # Display detail about current downloads
        if (
            hasattr(self.view_model, "currently_downloading_items")
            and self.view_model.currently_downloading_items
        ):
            status_text += (
                f"<br><span style='color: #aaccff; font-size: 90%;'>" f"Current files: "
            )

            # Add up to 3 filenames being downloaded
            displayed_items = 0
            for ts in self.view_model.currently_downloading_items:
                if displayed_items >= 3:  # Show max 3 downloads
                    status_text += f"... +{len(self.view_model.currently_downloading_items) - 3} more"
                    break

                # Format date for display
                formatted_date = ts.strftime("%Y-%m-%d %H:%M")
                status_text += f"{formatted_date}"

                displayed_items += 1
                if displayed_items < min(
                    3, len(self.view_model.currently_downloading_items)
                ):
                    status_text += ", "

            status_text += "</span>"

        self.status_label.setText(status_text)

        # Process events to ensure UI updates
        QApplication.processEvents()

    def _handle_scan_error(self, error_message: str) -> None:
        """Handle errors during scanning with enhanced error display.

        Args:
            error_message: The error message to display
        """
        LOGGER.error(f"Scan error: {error_message}")

        # Update status with error formatting
        self.status_label.setText(
            f"<span style='color: #ff6666; font-weight: bold;'>Error:</span> {error_message}"
        )

        # Set progress bar to red
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid #444;
                border-radius: 2px;
                text-align: center;
                background-color: #333;
            }
            QProgressBar::chunk {
                background-color: #a33;
                border-radius: 1px;
            }
        """
        )

        # Show enhanced error dialog
        self._show_detailed_error_dialog("Scan Error", error_message)

        # Update button states
        self._update_button_states()

    def _handle_download_error(self, error_message: str) -> None:
        """Handle errors during downloads with enhanced error display.

        Args:
            error_message: The error message to display
        """
        LOGGER.error(f"Download error: {error_message}")

        # Update status with error formatting
        self.status_label.setText(
            f"<span style='color: #ff6666; font-weight: bold;'>Download Error:</span> {error_message}"
        )

        # Set progress bar to red
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid #444;
                border-radius: 2px;
                text-align: center;
                background-color: #333;
            }
            QProgressBar::chunk {
                background-color: #a33;
                border-radius: 1px;
            }
        """
        )

        # Show enhanced error dialog
        self._show_detailed_error_dialog("Download Error", error_message)

        # Update button states
        self._update_button_states()

    def _handle_scan_completed(self, success: bool, message: str) -> None:
        """Handle scan completion with enhanced display."""
        # Reset progress bar to show 100%
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("100%")

        # Enhanced completion handling
        if success:
            # Scan succeeded
            self.status_label.setText(
                f"<span style='color: #66ff66; font-weight: bold;'>Scan completed successfully!</span> "
                f"Found {self.view_model.missing_count} missing files out of {self.view_model.total_expected} expected."
            )

            # Set the progress bar to green for successful completion
            self.progress_bar.setStyleSheet(
                """
                QProgressBar {
                    border: 1px solid #444;
                    border-radius: 2px;
                    text-align: center;
                    background-color: #333;
                }
                QProgressBar::chunk {
                    background-color: #3a3;
                    border-radius: 1px;
                }
            """
            )

            # Show success message with enhanced details
            if self.view_model.missing_count > 0:
                QMessageBox.information(
                    self,
                    "Scan Complete",
                    f"Found {self.view_model.missing_count} missing timestamps "
                    f"out of {self.view_model.total_expected} expected.\n\n"
                    f"You can now download the missing files or export a report.",
                )
            else:
                QMessageBox.information(
                    self,
                    "Scan Complete",
                    "No missing timestamps found. All files are present!",
                )
        else:
            # Scan failed - parse the error message for enhanced display
            self.status_label.setText(
                f"<span style='color: #ff6666; font-weight: bold;'>Scan failed:</span> {message}"
            )

            # Set the progress bar to red for failure
            self.progress_bar.setStyleSheet(
                """
                QProgressBar {
                    border: 1px solid #444;
                    border-radius: 2px;
                    text-align: center;
                    background-color: #333;
                }
                QProgressBar::chunk {
                    background-color: #a33;
                    border-radius: 1px;
                }
            """
            )

            # Show enhanced error dialog with detailed troubleshooting
            self._show_detailed_error_dialog("Scan Error", message)

        # Update button states to reflect post-scan operations
        self._update_button_states()

        # Ensure UI updates immediately
        QApplication.processEvents()

    def _show_detailed_error_dialog(self, title: str, message: str) -> None:
        """Show an enhanced error dialog with troubleshooting tips.

        This dialog extracts error codes and provides detailed, context-specific
        troubleshooting information based on the error type.

        Args:
            title: Dialog title
            message: Error message
        """
        # Extract error code if present
        error_code = "Unknown"
        if "[Error " in message and "]" in message:
            try:
                error_code = message.split("[Error ")[1].split("]")[0]
            except:
                pass

        # Create a custom dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(400)

        # Set up the dialog layout
        layout = QVBoxLayout(dialog)

        # Add error icon and title
        header_layout = QHBoxLayout()
        error_icon = QLabel()
        app_style = QApplication.style()
        if app_style is not None:
            icon = app_style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical)
            error_icon.setPixmap(icon.pixmap(32, 32))
        header_layout.addWidget(error_icon)

        error_title = QLabel(f"<h3>Error {error_code}</h3>")
        header_layout.addWidget(error_title)
        header_layout.addStretch(1)
        layout.addLayout(header_layout)

        # Add horizontal line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # Main error message
        error_label = QLabel(f"<b>Problem:</b> {message}")
        error_label.setWordWrap(True)
        error_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(error_label)

        # Add troubleshooting section based on error code
        tips_label = QLabel(self.tr("<b>Troubleshooting Tips:</b>"))
        layout.addWidget(tips_label)

        # Create a text browser for scrollable tips
        tips_browser = QTextBrowser()
        tips_browser.setOpenExternalLinks(True)
        tips_browser.setMinimumHeight(200)

        # Determine troubleshooting tips based on error type
        troubleshooting_html = ""

        # Authentication errors
        if (
            "AUTH-" in error_code
            or "access denied" in message.lower()
            or "permission" in message.lower()
        ):
            troubleshooting_html = """
            <ol>
                <li>NOAA GOES data should be accessible without AWS credentials</li>
                <li>If you have AWS credentials set in your environment, they might be interfering:
                    <ul>
                        <li>Try temporarily clearing AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables</li>
                    </ul>
                </li>
                <li>Your system time might be out of sync, which can cause S3 signature issues:
                    <ul>
                        <li>Verify your system date and time are accurate</li>
                        <li>Enable automatic time synchronization</li>
                    </ul>
                </li>
                <li>Network restrictions might be blocking AWS S3 access:
                    <ul>
                        <li>Check if you're behind a corporate firewall or VPN</li>
                        <li>Try using the CDN source instead of direct S3 access</li>
                    </ul>
                </li>
                <li>Check if you can access other AWS S3 resources or websites</li>
            </ol>
            """

        # Not found errors
        elif (
            "NF-" in error_code
            or "not found" in message.lower()
            or "no such" in message.lower()
        ):
            troubleshooting_html = """
            <ol>
                <li>The requested timestamp may not be available in the NOAA archive:
                    <ul>
                        <li>Try a different time period (data gaps are common)</li>
                        <li>Check if the date is within the operational period for the satellite</li>
                        <li>GOES-16 (East) has data from December 2017 onward</li>
                        <li>GOES-18 (West) has data from May 2022 onward</li>
                    </ul>
                </li>
                <li>Verify that you selected the correct satellite:
                    <ul>
                        <li>GOES-16 covers the eastern United States and Atlantic</li>
                        <li>GOES-18 covers the western United States and Pacific</li>
                    </ul>
                </li>
                <li>AWS S3 organization may have changed:
                    <ul>
                        <li>Try using the CDN source instead of direct S3 access</li>
                    </ul>
                </li>
                <li>Confirm data availability on the <a href="https://www.star.nesdis.noaa.gov/GOES/index.php">NOAA GOES website</a></li>
            </ol>
            """

        # Connection errors
        elif (
            "CONN-" in error_code
            or "NET-" in error_code
            or "connection" in message.lower()
            or "timeout" in message.lower()
        ):
            troubleshooting_html = """
            <ol>
                <li>Check your internet connection:
                    <ul>
                        <li>Verify that you can access other websites</li>
                        <li>Run a speed test to ensure adequate bandwidth</li>
                    </ul>
                </li>
                <li>Network configuration issues:
                    <ul>
                        <li>Temporarily disable any VPN or proxy services</li>
                        <li>Check if your firewall is blocking AWS S3 access</li>
                    </ul>
                </li>
                <li>AWS S3 service status:
                    <ul>
                        <li>Check the <a href="https://health.aws.amazon.com/health/status">AWS Service Health Dashboard</a></li>
                        <li>Try using the CDN source instead of direct S3 access</li>
                    </ul>
                </li>
                <li>Try again later if this is a temporary connectivity issue</li>
                <li>If downloading multiple files, try reducing the batch size</li>
            </ol>
            """

        # Rate limiting errors
        elif (
            "RATE-" in error_code
            or "throttl" in message.lower()
            or "limit" in message.lower()
        ):
            troubleshooting_html = """
            <ol>
                <li>AWS is limiting your request rate:
                    <ul>
                        <li>Reduce the number of concurrent requests</li>
                        <li>Try downloading fewer files at once</li>
                    </ul>
                </li>
                <li>Wait a few minutes before trying again</li>
                <li>Try using the CDN source instead of direct S3 access</li>
                <li>Consider downloading files in smaller batches</li>
            </ol>
            """

        # Server-side errors
        elif (
            "AWS-" in error_code or "S3-" in error_code or "service" in message.lower()
        ):
            troubleshooting_html = """
            <ol>
                <li>AWS S3 service issues:
                    <ul>
                        <li>Check the <a href="https://health.aws.amazon.com/health/status">AWS Service Health Dashboard</a></li>
                        <li>Try again later as this is a server-side issue</li>
                    </ul>
                </li>
                <li>Try using the CDN source instead of direct S3 access</li>
                <li>Try smaller requests (fewer files) which may be less likely to trigger service issues</li>
            </ol>
            """

        # File system errors
        elif "FILE-" in error_code or "DISK-" in error_code or "PERM-" in error_code:
            troubleshooting_html = """
            <ol>
                <li>Check your local file system:
                    <ul>
                        <li>Verify that the selected directory exists and is accessible</li>
                        <li>Ensure you have write permissions to the directory</li>
                    </ul>
                </li>
                <li>Disk space issues:
                    <ul>
                        <li>Check available disk space (GOES imagery can be large)</li>
                        <li>Free up space or choose a different location if needed</li>
                    </ul>
                </li>
                <li>External drives and network shares:
                    <ul>
                        <li>If using an external drive, verify it's properly connected</li>
                        <li>Network shares may have special permission requirements</li>
                    </ul>
                </li>
                <li>Antivirus software may be blocking write operations</li>
            </ol>
            """

        # DNS errors
        elif "DNS-" in error_code or "dns" in message.lower():
            troubleshooting_html = """
            <ol>
                <li>DNS resolution problems:
                    <ul>
                        <li>Check if your DNS settings are working correctly</li>
                        <li>Try using a different DNS server (e.g., 8.8.8.8 or 1.1.1.1)</li>
                    </ul>
                </li>
                <li>Verify that you can access other websites</li>
                <li>Your ISP might be having DNS issues</li>
                <li>Try using the CDN source instead of direct S3 access</li>
            </ol>
            """

        # SSL/TLS errors
        elif (
            "SSL-" in error_code
            or "ssl" in message.lower()
            or "certificate" in message.lower()
        ):
            troubleshooting_html = """
            <ol>
                <li>SSL/TLS certificate validation issues:
                    <ul>
                        <li>Check if your system date and time are correct</li>
                        <li>Update your operating system's SSL/TLS certificates</li>
                    </ul>
                </li>
                <li>Network interception:
                    <ul>
                        <li>Corporate networks might be inspecting secure connections</li>
                        <li>Security software might be interfering with HTTPS connections</li>
                    </ul>
                </li>
                <li>Try using the CDN source instead of direct S3 access</li>
            </ol>
            """

        # Memory errors
        elif "MEM-" in error_code or "memory" in message.lower():
            troubleshooting_html = """
            <ol>
                <li>Your system is running low on memory:
                    <ul>
                        <li>Close other applications to free up memory</li>
                        <li>Restart the application and try downloading fewer files at once</li>
                    </ul>
                </li>
                <li>For large downloads, try breaking them into smaller batches</li>
                <li>Consider upgrading your system memory if this happens frequently</li>
            </ol>
            """

        # Generic catch-all
        else:
            troubleshooting_html = """
            <ol>
                <li>Check your internet connection and general system health</li>
                <li>Verify that you've selected the correct satellite and time period</li>
                <li>Try using a different fetch source (CDN vs S3)</li>
                <li>Restart the application and try again</li>
                <li>Check the application log for more detailed error information</li>
                <li>Try a smaller date range or different interval setting</li>
                <li>If the problem persists, report this error with the timestamp details</li>
            </ol>
            """

        tips_browser.setHtml(troubleshooting_html)
        layout.addWidget(tips_browser)

        # Technical details section (collapsible)
        if "Error code:" in message or "Technical details:" in message:
            tech_details_label = QLabel(self.tr("<b>Technical Information:</b>"))
            layout.addWidget(tech_details_label)

            tech_details_edit = QTextEdit()
            tech_details_edit.setReadOnly(True)
            tech_details_edit.setMinimumHeight(100)

            # Extract technical details from the message
            tech_text = ""
            if "Technical details:" in message:
                try:
                    tech_text = message.split("Technical details:")[1].strip()
                except:
                    tech_text = "Unable to extract technical details."
            else:
                tech_text = "Error code: " + error_code

            tech_details_edit.setText(tech_text)
            layout.addWidget(tech_details_edit)

        # Add buttons at the bottom
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)

        # Show the dialog
        dialog.exec()
