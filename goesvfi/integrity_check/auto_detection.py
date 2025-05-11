"""
Enhanced auto-detection utilities for integrity check tabs.

This module provides improved auto-detection functionality with better feedback
and cross-tab integration for the integrity check system.
"""

import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QListWidget,
    QMessageBox,
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

    def __init__(
        self, title: str, label_text: str, parent: Optional[QWidget] = None
    ) -> None:
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
        if layout:
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
        self.log_widget.item(0).setForeground(Qt.GlobalColor.white)
        self.log_widget.item(0).setBackground(QColor(color))

        # Process events to ensure UI updates
        QApplication.processEvents()


class AutoDetectionWorker(QThread):
    """Worker thread for auto-detection operations."""

    # Define signals for communication
    progress = pyqtSignal(int, str, str)  # progress_value, message, level
    finished = pyqtSignal(dict)  # result dictionary
    error = pyqtSignal(str, str)  # error_message, traceback

    def __init__(self, operation: str, directory: Path, **kwargs) -> None:
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
                raise AutoDetectionError(f"Unknown operation: {self.operation}")

        except Exception as e:
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
                (
                    f"Found {len(png_files)} PNG files, {len(nc_files)} NetCDF files, "
                    f"{len(jpg_files)} JPG files"
                ),
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
        except Exception as dir_error:
            self.progress.emit(
                30, f"Error listing directory contents: {dir_error}", "error"
            )

        # Look for GOES-16 files
        self.progress.emit(50, "Scanning for GOES-16 files...", "info")
        goes16_files = []
        try:
            goes16_files = TimeIndex.scan_directory_for_timestamps(
                self.directory, SatellitePattern.GOES_16
            )
            self.progress.emit(60, f"Found {len(goes16_files)} GOES-16 files", "info")
        except Exception as scan_error:
            self.progress.emit(
                60, f"Error scanning for GOES-16 files: {scan_error}", "error"
            )

        # Look for GOES-18 files
        self.progress.emit(70, "Scanning for GOES-18 files...", "info")

        goes18_files = []
        try:
            goes18_files = TimeIndex.scan_directory_for_timestamps(
                self.directory, SatellitePattern.GOES_18
            )
            self.progress.emit(80, f"Found {len(goes18_files)} GOES-18 files", "info")
        except Exception as scan_error:
            self.progress.emit(
                80, f"Error scanning for GOES-18 files: {scan_error}", "error"
            )

        # Select satellite based on file count
        self.progress.emit(90, "Determining satellite type...", "info")
        goes16_count = len(goes16_files)
        goes18_count = len(goes18_files)
        if goes16_count == 0 and goes18_count == 0:
            self.progress.emit(95, "No valid GOES files found", "warning")
            result = {"status": "no_files", "goes16_count": 0, "goes18_count": 0}
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

        self.progress.emit(
            10, f"Checking directory for {satellite.name} files...", "info"
        )
        # Look for timestamps in directory based on the specified satellite pattern
        self.progress.emit(
            30, f"Scanning directory using {satellite.name} pattern...", "info"
        )
        timestamps = []
        try:
            timestamps = TimeIndex.scan_directory_for_timestamps(
                self.directory, satellite
            )
            self.progress.emit(50, f"Found {len(timestamps)} valid timestamps", "info")

            # Log sample timestamps
            if timestamps:
                sample_timestamps = ", ".join(
                    [ts.strftime("%Y-%m-%d %H:%M") for ts in timestamps[:3]]
                )
                self.progress.emit(
                    60, f"Sample timestamps: {sample_timestamps}", "info"
                )

        except Exception as scan_error:
            self.progress.emit(
                50, f"Error scanning for timestamps: {scan_error}", "error"
            )
            result = {
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
            result = {"status": "no_timestamps", "start": None, "end": None}
        else:
            # Sort timestamps
            timestamps.sort()

            # Get min and max dates
            start_date = timestamps[0]
            end_date = timestamps[-1]
            # Ensure end date has time set to end of day
            end_date = end_date.replace(hour=23, minute=59, second=59)
            self.progress.emit(
                90,
                (
                    f"Detected date range: {start_date.strftime('%Y-%m-%d')} "
                    f"to {end_date.strftime('%Y-%m-%d')}"
                ),
                "success",
            )

            result = {
                "status": "success",
                "start": start_date,
                "end": end_date,
                "timestamps": timestamps,
            }
        self.finished.emit(result)

    def _detect_interval(self) -> None:
        """Detect time interval between files in the directory."""
        timestamps = self.kwargs.get("timestamps", [])
        if not timestamps:
            # Try to get timestamps from the directory
            satellite = self.kwargs.get("satellite", SatellitePattern.GENERIC)
            self.progress.emit(
                10, "No timestamps provided, scanning directory...", "info"
            )
            try:
                timestamps = TimeIndex.scan_directory_for_timestamps(
                    self.directory, satellite
                )
                self.progress.emit(
                    30, f"Found {len(timestamps)} valid timestamps", "info"
                )
            except Exception as scan_error:
                self.progress.emit(
                    30, f"Error scanning for timestamps: {scan_error}", "error"
                )
                result = {
                    "status": "error",
                    "error": str(scan_error),
                    "interval_minutes": 0,
                }
                self.finished.emit(result)
                return

        # Process the timestamps to find the common interval
        self.progress.emit(40, "Analyzing timestamp intervals...", "info")

        if not timestamps or len(timestamps) < 2:
            self.progress.emit(
                50, "Not enough timestamps to determine interval", "warning"
            )
            result = {"status": "insufficient_data", "interval_minutes": 0}
            self.finished.emit(result)
            return

        # Sort timestamps
        timestamps.sort()

        # Calculate intervals between consecutive timestamps
        self.progress.emit(60, "Calculating intervals between timestamps...", "info")

        intervals = []
        for i in range(1, len(timestamps)):
            interval = (
                timestamps[i] - timestamps[i - 1]
            ).total_seconds() / 60  # Convert to minutes
            intervals.append(interval)

        # Find the most common interval
        from collections import Counter

        interval_counts = Counter(intervals)

        # Filter out any intervals that are clearly too large (e.g., gaps in data)
        # Typically, GOES data is available in various standard intervals:
        # 5-minute, 10-minute, 15-minute, or 30-minute
        valid_intervals = [
            i for i in intervals if i <= 60
        ]  # Consider intervals up to 1 hour

        if not valid_intervals:
            self.progress.emit(70, "No valid intervals found", "warning")
            result = {"status": "no_valid_intervals", "interval_minutes": 0}
        else:
            # Find the most common interval
            self.progress.emit(70, "Finding most common interval...", "info")

            interval_counts = Counter(valid_intervals)
            most_common_interval, count = interval_counts.most_common(1)[0]

            # Round to nearest standard interval (5, 10, 15, 30, 60 minutes)
            standard_intervals = [5, 10, 15, 30, 60]
            rounded_interval = min(
                standard_intervals, key=lambda x: abs(x - most_common_interval)
            )

            self.progress.emit(
                90,
                (
                    f"Detected interval: {rounded_interval} minutes "
                    f"(raw: {most_common_interval:.1f} minutes)"
                ),
                "success",
            )

            result = {
                "status": "success",
                "interval_minutes": rounded_interval,
                "raw_interval": most_common_interval,
                "interval_counts": dict(interval_counts),
            }

        self.finished.emit(result)

    def cancel(self) -> None:
        """Request cancellation of the operation."""
        self._cancel_requested = True


class EnhancedAutoDetector:
    """
    Enhanced auto-detection system with improved feedback and cross-tab integration.

    This class provides methods for auto-detecting various properties of satellite
    data, including satellite type, date range, and time interval, with improved
    feedback and integration with the rest of the integrity check system.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the enhanced auto-detector.

        Args:
            parent: Optional parent widget for dialogs
        """
        self.parent = parent
        self._workers: List[AutoDetectionWorker] = []

    def detect_satellite(self, directory: Path) -> Optional[Dict[str, Any]]:
        """
        Auto-detect satellite type from files in the directory.

        Args:
            directory: Directory to scan for satellite files

        Returns:
            Dictionary with detection results, or None if canceled
        """
        # Validate directory
        if not directory.exists() or not directory.is_dir():
            QMessageBox.critical(
                self.parent,
                "Invalid Directory",
                f"The directory {directory} does not exist or is not accessible.",
            )
            return None

        # Create progress dialog with enhanced feedback
        progress_dialog = DetectionProgressDialog(
            "Detecting Satellite Type", "Analyzing directory contents...", self.parent
        )
        progress_dialog.setMinimumDuration(0)  # Show immediately

        # Create worker thread
        worker = AutoDetectionWorker("satellite", directory)
        self._workers.append(worker)

        # Connect signals
        worker.progress.connect(
            lambda value, message, level: self._update_detection_progress(
                progress_dialog, value, message, level
            )
        )
        worker.finished.connect(
            lambda result: self._finish_detection(progress_dialog, result, "satellite")
        )
        worker.error.connect(
            lambda error, traceback: self._handle_detection_error(
                progress_dialog, error, traceback
            )
        )

        # Connect dialog's canceled signal to worker
        progress_dialog.canceled.connect(worker.cancel)

        # Start worker
        worker.start()

        # Show dialog (will block until closed)
        progress_dialog.exec()

        # Check if the operation was canceled
        if progress_dialog.wasCanceled():
            return None

        # Return the result
        return getattr(progress_dialog, "result", None)

    def detect_date_range(
        self, directory: Path, satellite: SatellitePattern = SatellitePattern.GENERIC
    ) -> Optional[Dict[str, Any]]:
        """
        Auto-detect date range from files in the directory.

        Args:
            directory: Directory to scan for files
            satellite: Satellite pattern to use for detection

        Returns:
            Dictionary with detection results, or None if canceled
        """
        # Validate directory
        if not directory.exists() or not directory.is_dir():
            QMessageBox.critical(
                self.parent,
                "Invalid Directory",
                f"The directory {directory} does not exist or is not accessible.",
            )
            return None

        # Create progress dialog with enhanced feedback
        progress_dialog = DetectionProgressDialog(
            "Detecting Date Range", f"Analyzing {satellite.name} files...", self.parent
        )
        progress_dialog.setMinimumDuration(0)  # Show immediately

        # Create worker thread
        worker = AutoDetectionWorker("date_range", directory, satellite=satellite)
        self._workers.append(worker)

        # Connect signals
        worker.progress.connect(
            lambda value, message, level: self._update_detection_progress(
                progress_dialog, value, message, level
            )
        )
        worker.finished.connect(
            lambda result: self._finish_detection(progress_dialog, result, "date_range")
        )
        worker.error.connect(
            lambda error, traceback: self._handle_detection_error(
                progress_dialog, error, traceback
            )
        )

        # Connect dialog's canceled signal to worker
        progress_dialog.canceled.connect(worker.cancel)

        # Start worker
        worker.start()

        # Show dialog (will block until closed)
        progress_dialog.exec()

        # Check if the operation was canceled
        if progress_dialog.wasCanceled():
            return None

        # Return the result
        return getattr(progress_dialog, "result", None)

    def detect_interval(
        self,
        directory: Path,
        timestamps: Optional[List[datetime]] = None,
        satellite: SatellitePattern = SatellitePattern.GENERIC,
    ) -> Optional[Dict[str, Any]]:
        """
        Auto-detect time interval between files in the directory.

        Args:
            directory: Directory to scan for files
            timestamps: Optional list of timestamps (if already available)
            satellite: Satellite pattern to use for detection if timestamps not provided

        Returns:
            Dictionary with detection results, or None if canceled
        """
        # Validate directory
        if not directory.exists() or not directory.is_dir():
            QMessageBox.critical(
                self.parent,
                "Invalid Directory",
                f"The directory {directory} does not exist or is not accessible.",
            )
            return None

        # Create progress dialog with enhanced feedback
        progress_dialog = DetectionProgressDialog(
            "Detecting Time Interval", "Analyzing file timestamps...", self.parent
        )
        progress_dialog.setMinimumDuration(0)  # Show immediately

        # Create worker thread
        worker = AutoDetectionWorker(
            "interval", directory, timestamps=timestamps, satellite=satellite
        )
        self._workers.append(worker)

        # Connect signals
        worker.progress.connect(
            lambda value, message, level: self._update_detection_progress(
                progress_dialog, value, message, level
            )
        )
        worker.finished.connect(
            lambda result: self._finish_detection(progress_dialog, result, "interval")
        )
        worker.error.connect(
            lambda error, traceback: self._handle_detection_error(
                progress_dialog, error, traceback
            )
        )

        # Connect dialog's canceled signal to worker
        progress_dialog.canceled.connect(worker.cancel)

        # Start worker
        worker.start()

        # Show dialog (will block until closed)
        progress_dialog.exec()

        # Check if the operation was canceled
        if progress_dialog.wasCanceled():
            return None

        # Return the result
        return getattr(progress_dialog, "result", None)

    def _update_detection_progress(
        self, dialog: DetectionProgressDialog, value: int, message: str, level: str
    ) -> None:
        """Update the detection progress dialog.

        Args:
            dialog: Progress dialog to update
            value: Progress value (0-100)
            message: Progress message
            level: Message level (info, warning, error, success)
        """
        dialog.setValue(value)
        dialog.add_log_message(message, level)

    def _finish_detection(
        self,
        dialog: DetectionProgressDialog,
        result: Dict[str, Any],
        detection_type: str,
    ) -> None:
        """Handle completion of detection operation.

        Args:
            dialog: Progress dialog to update
            result: Detection result dictionary
            detection_type: Type of detection operation
        """
        # Store the result in the dialog for retrieval
        dialog.result = result

        # Set the dialog's label based on the detection type and result
        if detection_type == "satellite":
            if result.get("status") == "success":
                satellite_name = result["satellite_name"]
                dialog.setLabelText(
                    f"Detected {satellite_name} as the primary satellite."
                )
            elif result.get("status") == "no_files":
                dialog.setLabelText("No valid GOES files found in the directory.")

        elif detection_type == "date_range":
            if result.get("status") == "success":
                start = result["start"].strftime("%Y-%m-%d")
                end = result["end"].strftime("%Y-%m-%d")
                dialog.setLabelText(f"Detected date range: {start} to {end}.")
            elif result.get("status") == "no_timestamps":
                dialog.setLabelText("No valid timestamps found in the directory.")

        elif detection_type == "interval":
            if result.get("status") == "success":
                interval = result["interval_minutes"]
                dialog.setLabelText(
                    f"Detected interval: {interval} minutes between files."
                )
            elif result.get("status") in ("insufficient_data", "no_valid_intervals"):
                dialog.setLabelText("Could not determine interval - not enough data.")

        # Set to 100% progress
        dialog.setValue(100)

        # Auto-close after a short delay if successful
        if result.get("status") == "success":
            QTimer.singleShot(2000, dialog.accept)

    def _handle_detection_error(
        self, dialog: DetectionProgressDialog, error: str, error_traceback: str
    ) -> None:
        """Handle detection error.

        Args:
            dialog: Progress dialog to update
            error: Error message
            error_traceback: Error traceback
        """
        dialog.setLabelText(f"Error: {error}")
        dialog.add_log_message(f"Error: {error}", "error")
        dialog.add_log_message(f"Traceback: {error_traceback}", "error")

        # Enable the cancel button for the user to dismiss the dialog
        dialog.setCancelButtonText("Close")

    def cleanup(self) -> None:
        """Clean up worker threads when done."""
        for worker in self._workers:
            if worker.isRunning():
                worker.cancel()
                worker.wait()

        self._workers.clear()


# Module-level auto-detector instance for singleton usage
auto_detector = EnhancedAutoDetector()


def detect_satellite(
    directory: Path, parent: Optional[QWidget] = None
) -> Optional[Dict[str, Any]]:
    """Auto-detect satellite type from files in the directory.

    Args:
        directory: Directory to scan for satellite files
        parent: Optional parent widget for dialogs

    Returns:
        Dictionary with detection results, or None if canceled
    """
    if parent is not None:
        auto_detector.parent = parent

    return auto_detector.detect_satellite(directory)


def detect_date_range(
    directory: Path,
    satellite: SatellitePattern = SatellitePattern.GENERIC,
    parent: Optional[QWidget] = None,
) -> Optional[Dict[str, Any]]:
    """Auto-detect date range from files in the directory.

    Args:
        directory: Directory to scan for files
        satellite: Satellite pattern to use for detection
        parent: Optional parent widget for dialogs

    Returns:
        Dictionary with detection results, or None if canceled
    """
    if parent is not None:
        auto_detector.parent = parent

    return auto_detector.detect_date_range(directory, satellite)


def detect_interval(
    directory: Path,
    timestamps: Optional[List[datetime]] = None,
    satellite: SatellitePattern = SatellitePattern.GENERIC,
    parent: Optional[QWidget] = None,
) -> Optional[Dict[str, Any]]:
    """Auto-detect time interval between files in the directory.

    Args:
        directory: Directory to scan for files
        timestamps: Optional list of timestamps (if already available)
        satellite: Satellite pattern to use for detection if timestamps not provided
        parent: Optional parent widget for dialogs

    Returns:
        Dictionary with detection results, or None if canceled
    """
    if parent is not None:
        auto_detector.parent = parent

    return auto_detector.detect_interval(directory, timestamps, satellite)
