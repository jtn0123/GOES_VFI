"""
Shared UI Components for GOES Imagery and Integrity Check Tabs

This module provides shared components that can be used by both the GOES Imagery
and Integrity Check tabs for improved integration and user experience.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QWidget

# Configure logging
logger = logging.getLogger(__name__)


class PreviewMetadata:
    """Metadata for preview components."""

    def __init__(
        self,
        channel: Optional[Any] = None,
        product_type: Optional[Any] = None,
        date_time: Optional[datetime] = None,
        source: Optional[str] = None,
        processing_options: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.channel = channel
        self.product_type = product_type
        self.date_time = date_time
        self.source = source
        self.processing_options = processing_options or {}


class ItemPreviewWidget(QWidget):
    """Widget for previewing items."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.current_item = None
        self.download_btn = QPushButton("Download")
        self.view_btn = QPushButton("View")

        layout = QVBoxLayout(self)
        layout.addWidget(self.download_btn)
        layout.addWidget(self.view_btn)

    def set_item(self, item: Any) -> None:
        """Set the current item for preview."""
        self.current_item = item
        # Update button states based on item
        if item:
            # Enable download button for missing items
            self.download_btn.setEnabled(not getattr(item, "is_downloaded", False))
            # Enable view button for downloaded items
            self.view_btn.setEnabled(getattr(item, "is_downloaded", False))

    def clear(self) -> None:
        """Clear the preview."""
        self.current_item = None
        self.download_btn.setEnabled(False)
        self.view_btn.setEnabled(False)


class MissingItemsTreeView(QWidget):
    """Tree view for missing items."""

    itemSelected = pyqtSignal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._items: list[object] = []
        self._grouping = "day"  # Default grouping
        # Create a minimal model for testing
        from PyQt6.QtCore import QStringListModel

        self.model = QStringListModel()

    def set_items(self, items: List[Any]) -> None:
        """Set items to display."""
        self._items = items
        # Update model based on grouping
        self._update_model()

    def set_grouping(self, group_by: str) -> None:
        """Set grouping method."""
        self._grouping = group_by
        # Update model with new grouping
        self._update_model()

    def _update_model(self) -> None:
        """Update the model based on current grouping."""
        if not self._items:
            self.model.setStringList([])
            return

        if self._grouping == "day":
            # Group by day
            days = set()
            for item in self._items:
                if hasattr(item, "timestamp"):
                    days.add(item.timestamp.date())
            self.model.setStringList([f"Day {i + 1}" for i in range(len(days))])
        elif self._grouping == "status":
            # Group by status (Downloaded, Downloading, Error, Missing)
            statuses = set()
            for item in self._items:
                if getattr(item, "is_downloaded", False):
                    statuses.add("Downloaded")
                elif getattr(item, "download_error", None):
                    statuses.add("Error")
                elif getattr(item, "is_downloading", False):
                    statuses.add("Downloading")
                else:
                    statuses.add("Missing")
            self.model.setStringList(sorted(statuses))
        elif self._grouping == "satellite":
            # Group by satellite
            satellites = set()
            for item in self._items:
                if hasattr(item, "expected_filename"):
                    # Extract satellite from filename (e.g., G16, G17, G18)
                    if "G16" in item.expected_filename:
                        satellites.add("GOES-16")
                    elif "G17" in item.expected_filename:
                        satellites.add("GOES-17")
                    elif "G18" in item.expected_filename:
                        satellites.add("GOES-18")
            self.model.setStringList(sorted(satellites))
        else:
            # Default: show all items
            self.model.setStringList([f"Item {i}" for i in range(len(self._items))])

    def rowCount(self) -> int:
        """Get the number of rows in the model."""
        return self.model.rowCount()

    def highlight_timestamp(self, timestamp: datetime) -> None:
        """Highlight item with given timestamp."""
        pass

    def expandAll(self) -> None:
        """Expand all groups."""
        pass

    def collapseAll(self) -> None:
        """Collapse all groups."""
        pass


class ResultsSummaryWidget(QWidget):
    """Widget for displaying results summary."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        from PyQt6.QtWidgets import QLabel

        # Create labels for summary display
        self.total_expected_label = QLabel("0")
        self.downloaded_label = QLabel("0")
        self.missing_label = QLabel("0")
        self.errors_label = QLabel("0")

    def update_summary(self, items: List[Any], total_expected: int) -> None:
        """Update the summary display."""
        # Update total expected
        self.total_expected_label.setText(str(total_expected))

        # Count items by status
        downloaded_count = sum(
            1 for item in items if getattr(item, "is_downloaded", False)
        )
        error_count = sum(1 for item in items if getattr(item, "download_error", None))
        downloading_count = sum(
            1 for item in items if getattr(item, "is_downloading", False)
        )
        missing_count = len(items) - downloaded_count - error_count - downloading_count

        # Update labels
        self.downloaded_label.setText(str(downloaded_count))
        self.missing_label.setText(str(missing_count))
        self.errors_label.setText(str(error_count))


class CollapsibleSettingsGroup(QWidget):
    """Collapsible settings group widget."""

    def __init__(
        self, title: str = "Settings", parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.title = title
        self.collapsed = False

    def toggle_collapsed(self) -> None:
        """Toggle collapsed state."""
        self.collapsed = not self.collapsed
