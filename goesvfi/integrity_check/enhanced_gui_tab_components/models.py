"""Model classes for the enhanced integrity check GUI tab."""

from typing import Any, cast

from PyQt6.QtCore import QModelIndex, QObject, Qt
from PyQt6.QtGui import QColor

from goesvfi.integrity_check.enhanced_view_model import EnhancedMissingTimestamp
from goesvfi.integrity_check.view_model import (
    MissingItemsTreeModel as MissingTimestampsModel,
)


class EnhancedMissingTimestampsModel(MissingTimestampsModel):
    """Enhanced model for displaying missing timestamps with source information."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__()
        self._items: list[Any] = []  # Initialize _items
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

        item = cast("EnhancedMissingTimestamp", self._items[index.row()])
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._get_display_data(item, col)
        if role == Qt.ItemDataRole.ToolTipRole:
            return self._get_tooltip_data(item, col)
        if role == Qt.ItemDataRole.BackgroundRole:
            return self._get_background_color(item, col)
        if role == Qt.ItemDataRole.ForegroundRole:
            return self._get_foreground_color(item, col)

        return None

    def _get_display_data(self, item: EnhancedMissingTimestamp, col: int) -> str | None:
        """Get display data for the given item and column."""
        if col == 0:  # Timestamp
            return item.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        if col == 1:  # Satellite
            return item.satellite if isinstance(item.satellite, str) else "Unknown"
        if col == 2:  # Source
            return item.source.upper() if item.source else "AUTO"
        if col == 3:  # Status
            return self._format_status(item)
        if col == 4:  # Progress
            return self._format_progress(item)
        if col == 5:  # Path
            return item.local_path or ""
        return None

    def _format_status(self, item: EnhancedMissingTimestamp) -> str:
        """Format the status column based on item state."""
        if item.is_downloaded:
            return "Downloaded"
        if item.is_downloading:
            return "Downloading..."
        if item.download_error:
            return self._format_error_message(item.download_error)
        return "Missing"

    def _format_error_message(self, error_msg: str) -> str:
        """Format error message to be user-friendly."""
        # Extract error code if present
        error_code = self._extract_error_code(error_msg)

        # Check for specific error types
        if "SQLite objects created in a thread" in error_msg:
            return "Error: Database thread conflict"

        # Map error patterns to user-friendly messages
        error_patterns = {
            ("unable to connect", "connection"): "Error: Connection failed",
            ("not found", "404"): "Error: File not found",
            ("permission", "access denied"): "Error: Access denied",
            ("timeout",): "Error: Connection timeout",
            ("service",): "Error: Service unavailable",
            ("unexpected",): f"Error: Download failed ({error_code})",
        }

        lower_msg = error_msg.lower()
        for patterns, message in error_patterns.items():
            if any(pattern in lower_msg for pattern in patterns):
                return message

        # Default: truncate long messages
        if len(error_msg) > 50:
            return f"Error: {error_msg[:47]}..."
        return f"Error: {error_msg}"

    def _extract_error_code(self, error_msg: str) -> str:
        """Extract error code from error message."""
        if "[Error " in error_msg and "]" in error_msg:
            try:
                return error_msg.split("[Error ")[1].split("]")[0]
            except (IndexError, ValueError):
                pass
        return "Unknown"

    def _format_progress(self, item: EnhancedMissingTimestamp) -> str:
        """Format the progress column."""
        if item.is_downloading:
            return f"{item.progress}%"
        if item.is_downloaded:
            return "100%"
        return ""

    def _get_tooltip_data(self, item: EnhancedMissingTimestamp, col: int) -> str | None:
        """Get tooltip data for the given item and column."""
        if col == 3 and item.download_error:  # Status column with error
            return self._format_error_tooltip(item.download_error)
        if col == 0:  # Timestamp column
            return item.timestamp.isoformat()
        if col == 5 and item.local_path and item.is_downloaded:  # Path column
            return f"Double-click to open folder containing:\n{item.local_path}"
        return None

    def _format_error_tooltip(self, error_msg: str) -> str:
        """Format error message for tooltip."""
        tooltip = "Double-click for details\n\n"

        # Add the error message, but limit length for very long ones
        if len(error_msg) > 500:
            tooltip += error_msg[:500] + "...\n\n"
        else:
            tooltip += error_msg + "\n\n"

        tooltip += "Right-click to show context menu with more options"
        return tooltip

    def _get_background_color(self, item: EnhancedMissingTimestamp, col: int) -> QColor | None:
        """Get background color for the given item and column."""
        if col == 3:  # Status column
            if item.is_downloaded:
                return QColor(0, 120, 0)  # Dark green for dark mode
            if item.download_error:
                return QColor(120, 0, 0)  # Dark red for dark mode
            if item.is_downloading:
                return QColor(0, 0, 120)  # Dark blue for dark mode
        return None

    def _get_foreground_color(self, item: EnhancedMissingTimestamp, col: int) -> QColor | None:
        """Get foreground color for the given item and column."""
        if col == 3:  # Status column
            if item.is_downloaded or item.download_error or item.is_downloading:
                return QColor(255, 255, 255)  # White text for colored backgrounds
        return None
