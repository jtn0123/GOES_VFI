# goesvfi/gui_tabs/model_library_tab.py
from __future__ import annotations

import logging
import pathlib  # Import pathlib

from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from goesvfi.gui_components.icon_manager import get_icon
from goesvfi.utils import config  # Assuming config is accessible this way

LOGGER = logging.getLogger(__name__)


class ModelLibraryTab(QWidget):
    """QWidget tab displaying available RIFE models."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the ModelLibraryTab.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._setup_ui()
        self._populate_model_table()

    def _setup_ui(self) -> None:
        """Set up the user interface elements for the tab."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Add enhanced header
        self._create_header(layout)

        # Enhanced info section
        info_container = self._create_info_section()
        layout.addWidget(info_container)

        # Enhanced model table
        self.model_table = QTableWidget()
        self.model_table.setColumnCount(3)
        self.model_table.setHorizontalHeaderLabels(["Model Key", "Path", "Status"])

        # Style the table
        # Use default qt-material styling for QTableWidget

        header = self.model_table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        self.model_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.model_table.setAlternatingRowColors(True)
        self.model_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        layout.addWidget(self.model_table)

        # Add enhanced status section
        self._create_status_section(layout)

        layout.addStretch(1)  # Push content to the top

    def _create_header(self, layout: QVBoxLayout) -> None:
        """Create the enhanced header section."""
        # Create header with icon
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)

        icon_label = QLabel()
        icon_label.setPixmap(get_icon("🤖").pixmap(24, 24))
        header_layout.addWidget(icon_label)

        header = QLabel("RIFE Model Library")
        header.setProperty("class", "AppHeader")
        header_layout.addWidget(header)
        header_layout.addStretch()
        # AppHeader class already set above, remove duplicate styling
        layout.addWidget(header_widget)

    def _create_info_section(self) -> QFrame:
        """Create the information section."""
        container = QFrame()
        # Use default qt-material styling for QFrame

        layout = QVBoxLayout(container)
        layout.setSpacing(8)

        # Create info label with icon
        info_widget = QWidget()
        info_layout = QHBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)

        info_icon_label = QLabel()
        info_icon_label.setPixmap(get_icon("📚").pixmap(16, 16))
        info_layout.addWidget(info_icon_label)

        info_label = QLabel("Available RIFE Models")
        info_label.setProperty("class", "FFmpegLabel")
        info_layout.addWidget(info_label)
        info_layout.addStretch()
        layout.addWidget(info_widget)

        description = QLabel(
            "RIFE (Real-time Intermediate Flow Estimation) models for video frame interpolation. "
            "Models with Available status are ready to use for processing."
        )
        description.setWordWrap(True)
        # Use default qt-material styling for QLabel
        layout.addWidget(description)

        return container

    def _create_status_section(self, layout: QVBoxLayout) -> None:
        """Create the status section."""
        status_container = QFrame()
        # Use default qt-material styling for QFrame

        status_layout = QHBoxLayout(status_container)

        # Status label
        self.status_label = QLabel("🔄 Loading model information...")
        self.status_label.setProperty("class", "StatusInfo")
        # StatusInfo class already provides styling
        status_layout.addWidget(self.status_label)

        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setProperty("class", "DialogButton")
        refresh_btn.setToolTip("Refresh the model list")
        refresh_btn.clicked.connect(self._populate_model_table)
        status_layout.addWidget(refresh_btn)

        status_layout.addStretch()
        layout.addWidget(status_container)

    def _populate_model_table(self) -> None:
        """Populate the model table with available RIFE models."""
        LOGGER.debug("Populating model table...")
        try:
            available_models = config.get_available_rife_models()  # Use config module
            self.model_table.setRowCount(len(available_models))

            # Get the project root directory relative to the config module
            project_root = pathlib.Path(config.__file__).parent.parent

            for row, model_key in enumerate(available_models):
                # Construct the model directory path
                model_dir_path = project_root / "models" / model_key

                # Check if model exists
                model_exists = model_dir_path.exists()

                # Create table items with enhanced styling
                key_item = QTableWidgetItem(model_key)
                path_item = QTableWidgetItem(str(model_dir_path))

                if model_exists:
                    status_item = QTableWidgetItem("Available")
                    status_item.setData(1, get_icon("✅"))
                    font = status_item.font()
                    font.setBold(True)
                    status_item.setFont(font)
                else:
                    status_item = QTableWidgetItem("Missing")
                    status_item.setData(1, get_icon("❌"))
                    font = status_item.font()
                    font.setBold(True)
                    status_item.setFont(font)

                self.model_table.setItem(row, 0, key_item)
                self.model_table.setItem(row, 1, path_item)
                self.model_table.setItem(row, 2, status_item)

            LOGGER.debug("Populated model table with %s models.", len(available_models))

            # Update status label
            if hasattr(self, "status_label"):
                available_count = sum(
                    1
                    for row in range(self.model_table.rowCount())
                    if (item := self.model_table.item(row, 2)) is not None and "Available" in item.text()
                )
                self.status_label.setText(f"{available_count} of {len(available_models)} models available")
        except Exception as e:
            LOGGER.error("Failed to populate model table: %s", e, exc_info=True)
            # Enhanced error display
            error_item = QTableWidgetItem(f"Error loading models: {e}")
            error_item.setData(1, get_icon("⚠️"))
            status_item = QTableWidgetItem("Failed")
            status_item.setData(1, get_icon("❌"))
            font = status_item.font()
            font.setBold(True)
            status_item.setFont(font)

            self.model_table.setRowCount(1)
            self.model_table.setSpan(0, 0, 1, 2)
            self.model_table.setItem(0, 0, error_item)
            self.model_table.setItem(0, 2, status_item)

            # Update status label for error
            if hasattr(self, "status_label"):
                self.status_label.setText("Error loading model information")
                self.status_label.setProperty("class", "StatusError")
                # StatusError class already provides styling
