"""
Shared UI Components for GOES Imagery and Integrity Check Tabs

This module provides shared components that can be used by both the GOES Imagery
and Integrity Check tabs for improved integration and user experience.
"""

import logging

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QWidget

# Configure logging
logger = logging.getLogger(__name__)


class PreviewMetadata:
    """Metadata for preview components."""

    def __init__(
        self,
        channel=None,
        product_type=None,
        date_time=None,
        source=None,
        processing_options=None,
    ):
        self.channel = channel
        self.product_type = product_type
        self.date_time = date_time
        self.source = source
        self.processing_options = processing_options or {}


class ItemPreviewWidget(QWidget):
    """Widget for previewing items."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_item = None
        self.download_btn = QPushButton("Download")
        self.view_btn = QPushButton("View")

        layout = QVBoxLayout(self)
        layout.addWidget(self.download_btn)
        layout.addWidget(self.view_btn)

    def set_item(self, item):
        """Set the current item for preview."""
        self.current_item = item

    def clear(self):
        """Clear the preview."""
        self.current_item = None


class MissingItemsTreeView(QWidget):
    """Tree view for missing items."""

    itemSelected = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []

    def set_items(self, items):
        """Set items to display."""
        self._items = items

    def set_grouping(self, group_by):
        """Set grouping method."""
        pass

    def highlight_timestamp(self, timestamp):
        """Highlight item with given timestamp."""
        pass

    def expandAll(self):
        """Expand all groups."""
        pass

    def collapseAll(self):
        """Collapse all groups."""
        pass


class ResultsSummaryWidget(QWidget):
    """Widget for displaying results summary."""

    def __init__(self, parent=None):
        super().__init__(parent)

    def update_summary(self, items, total_expected):
        """Update the summary display."""
        pass


class CollapsibleSettingsGroup(QWidget):
    """Collapsible settings group widget."""

    def __init__(self, title="Settings", parent=None):
        super().__init__(parent)
        self.title = title
        self.collapsed = False

    def toggle_collapsed(self):
        """Toggle collapsed state."""
        self.collapsed = not self.collapsed
