"""Enhanced GUI tab for integrity checking with streamlined UI.

This module provides an improved version of the EnhancedIntegrityCheckTab with a
more streamlined and user-friendly interface.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, List, Optional, cast

from PyQt6.QtCore import (
    QDate,
    QModelIndex,
    QObject,
    QPoint,
    QSortFilterProxyModel,
    Qt,
    QTime,
    pyqtSignal,
)
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
    QApplication,
    QCalendarWidget,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from goesvfi.utils import log

from .time_index import SatellitePattern
from .view_model import MissingTimestamp, ScanStatus

LOGGER = log.get_logger(__name__)


class MissingTimestampsModel(QObject):
    """Base model for displaying missing timestamps."""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._items: List[MissingTimestamp] = []
        self._headers = ["Timestamp", "Status", "Path"]


class EnhancedMissingTimestamp(MissingTimestamp):
    """Enhanced missing timestamp with additional properties."""

    def __init__(self, timestamp: datetime, expected_filename: str):
        super().__init__(timestamp, expected_filename)
        self.progress: int = 0
        self.source: str = "auto"


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
                    return f"Error: {item.download_error[:30]}..."
                else:
                    return "Pending"
            elif col == 4:  # Progress
                if item.is_downloading:
                    return f"{item.progress}%"
                elif item.is_downloaded:
                    return "100%"
                else:
                    return "0%"
            elif col == 5:  # Path
                return item.local_path if item.local_path else ""

        return None


class ImprovedEnhancedIntegrityCheckTab(QWidget):
    """Improved enhanced integrity check tab with streamlined interface."""

    def __init__(self, view_model=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # Use provided view model or create a simple stub view model
        if view_model is not None:
            self.view_model = view_model
        else:
            from .view_model import IntegrityCheckViewModel

            self.view_model = IntegrityCheckViewModel()
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout(self)

        # Create a simple placeholder layout
        label = QLabel("Enhanced Integrity Check Tab (Improved)")
        layout.addWidget(label)

        # Directory selection
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Directory:"))
        self.directory_edit = QLineEdit()
        if hasattr(self.view_model, "base_directory"):
            self.directory_edit.setText(str(self.view_model.base_directory))
        dir_layout.addWidget(self.directory_edit)
        layout.addLayout(dir_layout)

        # Add basic controls
        button_layout = QHBoxLayout()
        self.scan_button = QPushButton("Start Scan")
        self.download_button = QPushButton("Download")
        self.download_button.setEnabled(False)
        self.export_button = QPushButton("Export")
        self.export_button.setEnabled(False)

        button_layout.addWidget(self.scan_button)
        button_layout.addWidget(self.download_button)
        button_layout.addWidget(self.export_button)
        layout.addLayout(button_layout)

        # Advanced options (collapsed by default)
        self.advanced_options = QCheckBox("Advanced Options")
        self.advanced_options.setChecked(False)
        layout.addWidget(self.advanced_options)

        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

    def _connect_signals(self) -> None:
        """Connect view model signals to UI updates."""
        self.view_model.status_updated.connect(self.status_label.setText)
        self.scan_button.clicked.connect(self._start_scan)

    def _start_scan(self) -> None:
        """Start the scan process."""
        self.view_model.start_scan()

    def cleanup(self) -> None:
        """Clean up resources."""
        if hasattr(self, "view_model"):
            self.view_model.cleanup()
