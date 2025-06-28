"""Enhanced auto-detection utilities for integrity check tabs.

This module provides improved auto-detection functionality with better feedback
and cross-tab integration for the integrity check system.
"""

import logging
from pathlib import Path
import traceback
from typing import Any

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QGridLayout,
    QListWidget,
    QProgressDialog,
    QWidget,
)

from .time_index import SatellitePattern, TimeIndex

# Configure logging
LOGGER = logging.getLogger(__name__)


class AutoDetectionError(Exception):
    """Exception raised for auto-detection errors."""


class DetectionProgressDialog(QProgressDialog):
    """Enhanced progress dialog for auto-detection operations with detailed feedback."""

    def __init__(self, title: str, label_text: str, parent: QWidget | None = None) -> None:
        """Initialize the detection progress dialog.

        Args:
            title: Dialog title
            label_text: Initial label text
            parent: Optional parent widget
        """
        super().__init__(parent)

        # Set up basic properties
        self.setWindowTitle(title)
        self.setLabelText(label_text)
        self.setMinimum(0)
        self.setMaximum(100)
        self.setValue(0)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumWidth(400)

        # Make the dialog look nicer with rounded corners and a border
        self.setStyleSheet(
            """
            QProgressDialog {
                background-color: #2d2d2d;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 10px;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 12px;
            }
            QProgressBar {
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #333;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """
        )

        # Create a status log widget that will display detailed progress
        self.log_widget = QListWidget()
        self.log_widget.setMaximumHeight(150)
        self.log_widget.setStyleSheet(
            """
            QListWidget {
                background-color: #1d1d1d;
                border: 1px solid #555;
                border-radius: 4px;
                color: #e0e0e0;
                font-family: monospace;
                font-size: 11px;
            }
        """
        )

        # Find the progress dialog's layout and add our log widget
        layout = self.layout()
        if layout and isinstance(layout, QGridLayout):
            layout.addWidget(self.log_widget, 2, 0, 1, layout.columnCount())

        # Adjust default size for better visibility
        self.resize(450, 350)

    def add_log_message(self, message: str, level: str = "info") -> None:
        """Add a log message to the progress dialog.

        Args:
            message: Log message text
            level: Log level (info, warning, error, success)
        """
        # Add styled message based on level
        color = "#e0e0e0"  # Default color
        if level == "warning":
            color = "#f39c12"
        elif level == "error":
            color = "#e74c3c"
        elif level == "success":
            color = "#2ecc71"

        # Insert at the top for most recent messages
        self.log_widget.insertItem(0, message)
        item = self.log_widget.item(0)
        if item:
            item.setForeground(QColor(color))

        # Process events to ensure UI updates
        QApplication.processEvents()


class AutoDetectionWorker(QThread):
    """Worker thread for auto-detection operations."""

    # Define signals for communication
    progress = pyqtSignal(int, str, str)  # progress_value, message, level
    finished = pyqtSignal(dict)  # result dictionary
    error = pyqtSignal(str, str)  # error_message, traceback

    def __init__(self, operation: str, directory: Path, **kwargs: Any) -> None:
        """Initialize the auto-detection worker.

        Args:
            operation: Type of detection operation ("satellite", "date_range", "interval")
            directory: Directory to scan
            **kwargs: Additional parameters for the detection operation
        """
        super().__init__()

        self.operation = operation
        self.directory = directory
        self.kwargs = kwargs
        self._cancel_requested = False

    def run(self) -> None:
        """Execute the auto-detection operation."""
        try:
            self.progress.emit(0, f"Starting {self.operation} detection...", "info")

            if self.operation == "satellite":
                self._detect_satellite()
            elif self.operation == "date_range":
                self._detect_date_range()
            elif self.operation == "interval":
                self._detect_interval()
            else:
                msg = f"Unknown operation: {self.operation}"
                raise AutoDetectionError(msg)

        except (OSError, ValueError, RuntimeError) as e:
            error_traceback = traceback.format_exc()
            self.error.emit(str(e), error_traceback)

    def _detect_satellite(self) -> None:
        """Detect satellite type from files in the directory."""
        self.progress.emit(10, "Checking directory contents...", "info")

        # Log number of files in the directory
        try:
            png_files = list(self.directory.glob("**/*.png"))
            nc_files = list(self.directory.glob("**/*.nc"))
            jpg_files = list(self.directory.glob("**/*.jpg"))

            self.progress.emit(
                20,
                f"Found {len(png_files)} PNG files, {len(nc_files)} NetCDF files, {len(jpg_files)} JPG files",
                "info",
            )

            # Log a few sample filenames for debugging
            if png_files:
                sample_files = ", ".join([f.name for f in png_files[:3]])
                self.progress.emit(30, f"Sample PNG files: {sample_files}", "info")

            if nc_files:
                sample_files = ", ".join([f.name for f in nc_files[:3]])
                self.progress.emit(35, f"Sample NetCDF files: {sample_files}", "info")

            if jpg_files:
                sample_files = ", ".join([f.name for f in jpg_files[:3]])
                self.progress.emit(40, f"Sample JPG files: {sample_files}", "info")

        except (OSError, PermissionError) as dir_error:
            self.progress.emit(30, f"Error listing directory contents: {dir_error}", "error")

        # Look for GOES-16 files
        self.progress.emit(50, "Scanning for GOES-16 files...", "info")
        goes16_files = []
        try:
            goes16_files = TimeIndex.scan_directory_for_timestamps(self.directory, SatellitePattern.GOES_16)
            self.progress.emit(60, f"Found {len(goes16_files)} GOES-16 files", "info")
        except (OSError, ValueError, RuntimeError) as scan_error:
            self.progress.emit(60, f"Error scanning for GOES-16 files: {scan_error}", "error")

        # Look for GOES-18 files
        self.progress.emit(70, "Scanning for GOES-18 files...", "info")
        goes18_files = []
        try:
            goes18_files = TimeIndex.scan_directory_for_timestamps(self.directory, SatellitePattern.GOES_18)
            self.progress.emit(80, f"Found {len(goes18_files)} GOES-18 files", "info")
        except (OSError, ValueError, RuntimeError) as scan_error:
            self.progress.emit(80, f"Error scanning for GOES-18 files: {scan_error}", "error")

        # Select satellite based on file count
        self.progress.emit(90, "Determining satellite type...", "info")
        goes16_count = len(goes16_files)
        goes18_count = len(goes18_files)

        result: dict[str, Any]
        if goes16_count == 0 and goes18_count == 0:
            self.progress.emit(95, "No valid GOES files found", "warning")
            result = {
                "status": "no_files",
                "goes16_count": 0,
                "goes18_count": 0,
            }
        elif goes16_count > goes18_count:
            self.progress.emit(
                100,
                f"Detected GOES-16 as primary satellite ({goes16_count} files vs {goes18_count})",
                "success",
            )
            result = {
                "status": "success",
                "satellite": SatellitePattern.GOES_16,
                "satellite_name": "GOES-16 (East)",
                "goes16_count": goes16_count,
                "goes18_count": goes18_count,
            }
        else:
            self.progress.emit(
                100,
                f"Detected GOES-18 as primary satellite ({goes18_count} files vs {goes16_count})",
                "success",
            )
            result = {
                "status": "success",
                "satellite": SatellitePattern.GOES_18,
                "satellite_name": "GOES-18 (West)",
                "goes16_count": goes16_count,
                "goes18_count": goes18_count,
            }

        self.finished.emit(result)

    def _detect_date_range(self) -> None:
        """Detect date range from files in the directory."""
        satellite = self.kwargs.get("satellite", SatellitePattern.GENERIC)

        self.progress.emit(10, f"Checking directory for {satellite.name} files...", "info")

        # Look for timestamps in directory based on the specified satellite pattern
        self.progress.emit(30, f"Scanning directory using {satellite.name} pattern...", "info")

        timestamps = []
        try:
            timestamps = TimeIndex.scan_directory_for_timestamps(self.directory, satellite)
            self.progress.emit(50, f"Found {len(timestamps)} valid timestamps", "info")

            # Log sample timestamps
            if timestamps:
                sample_timestamps = ", ".join([ts.strftime("%Y-%m-%d %H:%M") for ts in timestamps[:3]])
                self.progress.emit(60, f"Sample timestamps: {sample_timestamps}", "info")

        except (OSError, ValueError, RuntimeError) as scan_error:
            self.progress.emit(50, f"Error scanning for timestamps: {scan_error}", "error")
            result: dict[str, Any] = {
                "status": "error",
                "error": str(scan_error),
                "start": None,
                "end": None,
            }
            self.finished.emit(result)
            return

        # Process the timestamps to find the min and max dates
        self.progress.emit(70, "Analyzing timestamps...", "info")

        if not timestamps:
            self.progress.emit(90, "No valid timestamps found", "warning")
            result = {
                "status": "no_timestamps",
                "start": None,
                "end": None,
            }
        else:
            # Sort timestamps
            timestamps.sort()

            # Get min and max dates
            start_date = timestamps[0]
            end_date = timestamps[-1]

            self.progress.emit(
                100,
                f"Date range detected: {start_date.strftime('%Y-%m-%d %H:%M')} to "
                f"{end_date.strftime('%Y-%m-%d %H:%M')}",
                "success",
            )

            result = {
                "status": "success",
                "start": start_date,
                "end": end_date,
                "total_files": len(timestamps),
            }

        self.finished.emit(result)

    def _detect_interval(self) -> None:
        """Detect time interval between files."""
        satellite = self.kwargs.get("satellite", SatellitePattern.GENERIC)

        self.progress.emit(10, "Scanning for files...", "info")

        timestamps = []
        try:
            timestamps = TimeIndex.scan_directory_for_timestamps(self.directory, satellite)
        except (OSError, ValueError, RuntimeError) as e:
            self.error.emit(f"Error scanning directory: {e!s}", "")
            return

        if len(timestamps) < 2:
            self.progress.emit(100, "Not enough files to detect interval", "warning")
            result: dict[str, Any] = {"status": "insufficient_files", "interval": None}
            self.finished.emit(result)
            return

        # Sort timestamps
        timestamps.sort()

        # Calculate intervals
        self.progress.emit(50, "Calculating intervals...", "info")
        intervals = []
        for i in range(1, len(timestamps)):
            interval = (timestamps[i] - timestamps[i - 1]).total_seconds() / 60
            intervals.append(interval)

        # Find most common interval
        from collections import Counter

        interval_counts = Counter(int(interval) for interval in intervals)
        most_common_interval = interval_counts.most_common(1)[0][0]

        self.progress.emit(
            100,
            f"Detected interval: {most_common_interval} minutes",
            "success",
        )

        result = {
            "status": "success",
            "interval": most_common_interval,
            "total_files": len(timestamps),
        }
        self.finished.emit(result)

    def cancel(self) -> None:
        """Request cancellation of the operation."""
        self._cancel_requested = True
