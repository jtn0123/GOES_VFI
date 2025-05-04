# goesvfi/gui_tabs/model_library_tab.py
from __future__ import annotations

import logging
import pathlib # Import pathlib
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

from goesvfi.utils import config  # Assuming config is accessible this way

if TYPE_CHECKING:
    # Import types for type hinting only if needed, avoids circular imports
    pass

LOGGER = logging.getLogger(__name__)


class ModelLibraryTab(QWidget):
    """QWidget tab displaying available RIFE models."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Initialize the ModelLibraryTab.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._setup_ui()
        self._populate_model_table()

    def _setup_ui(self) -> None:
        """Set up the user interface elements for the tab."""
        layout = QVBoxLayout(self)

        info_label = QLabel("Available RIFE Models:")
        layout.addWidget(info_label)

        self.model_table = QTableWidget()
        self.model_table.setColumnCount(2)
        self.model_table.setHorizontalHeaderLabels(["Model Key", "Path"])
        header = self.model_table.horizontalHeader()
        if header is not None:  # Check if header is not None
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) # Stretch last section
        self.model_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )  # Make table read-only
        layout.addWidget(self.model_table)

        layout.addStretch(1)  # Push table to the top

    def _populate_model_table(self) -> None:
        """Populate the model table with available RIFE models."""
        LOGGER.debug("Populating model table...")
        try:
            available_models = config.get_available_rife_models() # Use config module
            self.model_table.setRowCount(len(available_models))

            # Get the project root directory relative to the config module
            project_root = pathlib.Path(config.__file__).parent.parent

            for row, model_key in enumerate(available_models): # Iterate over list of keys
                # Construct the model directory path
                model_dir_path = project_root / "models" / model_key
                self.model_table.setItem(row, 0, QTableWidgetItem(model_key))
                self.model_table.setItem(row, 1, QTableWidgetItem(str(model_dir_path))) # Use constructed path

            LOGGER.debug(f"Populated model table with {len(available_models)} models.")
        except Exception as e:
            LOGGER.error(f"Failed to populate model table: {e}", exc_info=True)
            # Optionally, display an error message in the UI
            error_item = QTableWidgetItem(f"Error loading models: {e}")
            self.model_table.setRowCount(1)
            self.model_table.setSpan(0, 0, 1, 2) # Span across columns
            self.model_table.setItem(0, 0, error_item)