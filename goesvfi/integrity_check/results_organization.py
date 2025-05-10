"""
Improved organization components for the integrity check results.

This module provides specialized widgets for better organizing and presenting
the integrity check results, including grouping, filtering, and categorization.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Union, Tuple, cast
from enum import Enum, auto

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QPushButton, QProgressBar, QTableView, QHeaderView,
    QGroupBox, QCheckBox, QComboBox, QDateTimeEdit, QSpinBox,
    QFileDialog, QLineEdit, QTextEdit, QMessageBox, QSplitter,
    QScrollArea, QFrame, QSizePolicy, QTabWidget, QDialog,
    QDialogButtonBox, QStackedWidget, QApplication, QRadioButton,
    QToolButton, QStyle, QToolTip, QMenu, QProgressDialog,
    QTextBrowser, QTreeView
)
from PyQt6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, QDateTime, QDate, QTime,
    pyqtSignal, QObject, QSize, QThreadPool, QThread, QRunnable,
    QSortFilterProxyModel, QTimer, QPoint, QAbstractItemModel,
    QItemSelectionModel
)
from PyQt6.QtGui import (
    QColor, QPalette, QIcon, QFont, QPixmap, QBrush, QAction,
    QStandardItemModel, QStandardItem
)

from goesvfi.integrity_check.view_model import MissingTimestamp


class GroupingModel(QAbstractItemModel):
    """Model for grouped missing timestamps."""
    
    def __init__(self, parent: Optional[QObject] = None) -> None:
        """Initialize the model."""
        super().__init__(parent)
        self._root_item = GroupItem("Root", None)
        self._headers = ["Group", "Count", "Status"]
    
    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        """Create an index for the given row, column, and parent."""
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        
        if not parent.isValid():
            parent_item = self._root_item
        else:
            parent_item = parent.internalPointer()
        
        child_item = parent_item.child(row)
        if child_item:
            return self.createIndex(row, column, child_item)
        else:
            return QModelIndex()
    
    def parent(self, index: QModelIndex) -> QModelIndex:
        """Return the parent index for the given index."""
        if not index.isValid():
            return QModelIndex()

        child_item: Any = index.internalPointer()
        if child_item is None:
            return QModelIndex()

        parent_item = child_item.parent()

        if parent_item is None or parent_item == self._root_item:
            return QModelIndex()

        return self.createIndex(parent_item.row(), 0, parent_item)
    
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the number of rows under the given parent."""
        if parent.column() > 0:
            return 0
        
        if not parent.isValid():
            parent_item = self._root_item
        else:
            parent_item = parent.internalPointer()
        
        return parent_item.childCount()
    
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the number of columns for the given parent."""
        return len(self._headers)
    
    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Return data for the given index and role."""
        if not index.isValid():
            return None
        
        item = index.internalPointer()
        col = index.column()
        
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:  # Group
                return item.data()
            elif col == 1:  # Count
                return item.itemCount()
            elif col == 2:  # Status
                return item.status()
        
        elif role == Qt.ItemDataRole.BackgroundRole:
            if col == 2:  # Status
                status = item.status()
                if status == "Complete":
                    return QColor(200, 255, 200)  # Light green
                elif status == "Partial":
                    return QColor(255, 240, 180)  # Light yellow
                elif status == "Missing":
                    return QColor(255, 200, 200)  # Light red
        
        return None
    
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Return header data for the given section, orientation, and role."""
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self._headers[section]
        return None
    
    def setItems(self, items: List[MissingTimestamp], grouping: str) -> None:
        """
        Set the items to be displayed in the model.
        
        Args:
            items: List of missing timestamps
            grouping: Grouping method ("day", "hour", "status")
        """
        self.beginResetModel()
        
        # Clear existing items
        self._root_item = GroupItem("Root", None)
        
        # Group by selected method
        if grouping == "day":
            self._group_by_day(items)
        elif grouping == "hour":
            self._group_by_hour(items)
        elif grouping == "status":
            self._group_by_status(items)
        else:
            # No grouping, just add all items
            for item in items:
                self._root_item.addChild(GroupItem(
                    str(item.timestamp), self._root_item, item
                ))
        
        self.endResetModel()
    
    def _group_by_day(self, items: List[MissingTimestamp]) -> None:
        """
        Group items by day.
        
        Args:
            items: List of missing timestamps
        """
        # Group by day
        day_groups: Dict[str, List[MissingTimestamp]] = {}
        
        for item in items:
            day_key = item.timestamp.strftime("%Y-%m-%d")
            if day_key not in day_groups:
                day_groups[day_key] = []
            day_groups[day_key].append(item)
        
        # Create group items
        for day, day_items in sorted(day_groups.items()):
            try:
                date = datetime.strptime(day, "%Y-%m-%d")
                day_text = date.strftime("%a, %b %d, %Y")
            except ValueError:
                day_text = day
                
            day_group = GroupItem(day_text, self._root_item)
            self._root_item.addChild(day_group)
            
            # Add items to day group
            for item in day_items:
                # Use time as item text
                time_text = item.timestamp.strftime("%H:%M:%S")
                day_group.addChild(GroupItem(time_text, day_group, item))
    
    def _group_by_hour(self, items: List[MissingTimestamp]) -> None:
        """
        Group items by hour.
        
        Args:
            items: List of missing timestamps
        """
        # Group by hour
        hour_groups: Dict[int, List[MissingTimestamp]] = {}
        
        for item in items:
            hour = item.timestamp.hour
            if hour not in hour_groups:
                hour_groups[hour] = []
            hour_groups[hour].append(item)
        
        # Create group items
        for hour in sorted(hour_groups.keys()):
            hour_text = f"{hour:02d}:00 - {hour:02d}:59"
            hour_group = GroupItem(hour_text, self._root_item)
            self._root_item.addChild(hour_group)
            
            # Sort items by date
            hour_items = sorted(hour_groups[hour], key=lambda x: x.timestamp)
            
            # Add items to hour group
            for item in hour_items:
                # Use date as item text
                date_text = item.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                hour_group.addChild(GroupItem(date_text, hour_group, item))
    
    def _group_by_status(self, items: List[MissingTimestamp]) -> None:
        """
        Group items by status.
        
        Args:
            items: List of missing timestamps
        """
        # Define status groups
        status_groups: Dict[str, List[MissingTimestamp]] = {
            "Downloaded": [],
            "Downloading": [],
            "Error": [],
            "Missing": []
        }
        
        # Assign items to groups
        for item in items:
            if getattr(item, 'is_downloaded', False):
                status_groups["Downloaded"].append(item)
            elif getattr(item, 'is_downloading', False):
                status_groups["Downloading"].append(item)
            elif getattr(item, 'download_error', ''):
                status_groups["Error"].append(item)
            else:
                status_groups["Missing"].append(item)
        
        # Create group items
        for status, status_items in status_groups.items():
            if status_items:  # Only create groups with items
                status_group = GroupItem(status, self._root_item)
                self._root_item.addChild(status_group)
                
                # Sort items by timestamp
                status_items.sort(key=lambda x: x.timestamp)
                
                # Add items to status group
                for item in status_items:
                    # Use timestamp as item text
                    timestamp_text = item.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    status_group.addChild(GroupItem(timestamp_text, status_group, item))
    
    def getItem(self, index: QModelIndex) -> Optional['GroupItem']:
        """
        Get the item at the given index.

        Args:
            index: Model index

        Returns:
            The item at the index, or None if invalid
        """
        if not index.isValid():
            return None

        # Cast the internal pointer to the correct type
        item = index.internalPointer()
        if isinstance(item, GroupItem):
            return item
        return None


class GroupItem:
    """Item in the group model."""
    
    def __init__(self, 
                data: str, 
                parent: Optional['GroupItem'], 
                item: Optional[MissingTimestamp] = None) -> None:
        """
        Initialize the group item.
        
        Args:
            data: Display text for the item
            parent: Parent item
            item: Associated MissingTimestamp or None for group items
        """
        self._data = data
        self._parent = parent
        self._item = item
        self._children: List[GroupItem] = []
    
    def data(self) -> str:
        """Return the item's data."""
        return self._data
    
    def parent(self) -> Optional['GroupItem']:
        """Return the item's parent."""
        return self._parent
    
    def child(self, row: int) -> Optional['GroupItem']:
        """Return the child at the given row."""
        if 0 <= row < len(self._children):
            return self._children[row]
        return None
    
    def childCount(self) -> int:
        """Return the number of children."""
        return len(self._children)
    
    def row(self) -> int:
        """Return the item's row number within its parent."""
        if self._parent:
            return self._parent._children.index(self)
        return 0
    
    def addChild(self, child: 'GroupItem') -> None:
        """Add a child to this item."""
        self._children.append(child)
    
    def itemCount(self) -> int:
        """Return the number of actual items in this group (including children)."""
        if self._item:
            return 1
        
        count = 0
        for child in self._children:
            count += child.itemCount()
        return count
    
    def status(self) -> str:
        """Return the status of this group."""
        if self._item:
            if getattr(self._item, 'is_downloaded', False):
                return "Complete"
            elif getattr(self._item, 'is_downloading', False):
                return "Downloading"
            elif getattr(self._item, 'download_error', ''):
                return "Error"
            else:
                return "Missing"
        
        # For groups, calculate based on children
        total = self.itemCount()
        if total == 0:
            return "Unknown"
        
        downloaded = 0
        errors = 0
        
        for child in self._children:
            if child._item:
                if getattr(child._item, 'is_downloaded', False):
                    downloaded += 1
                elif getattr(child._item, 'download_error', ''):
                    errors += 1
            else:
                # Recursive check for group
                child_status = child.status()
                child_count = child.itemCount()
                
                if child_status == "Complete":
                    downloaded += child_count
                elif child_status == "Error":
                    errors += child_count
                elif child_status == "Partial":
                    # Calculate approximately
                    downloaded += child_count // 2
                    errors += child_count // 4
        
        # Determine status based on counts
        if downloaded == total:
            return "Complete"
        elif downloaded == 0 and errors == 0:
            return "Missing"
        elif errors == total:
            return "Error"
        else:
            return "Partial"
    
    def timestamp(self) -> Optional[datetime]:
        """Return the timestamp if this is a leaf item."""
        if self._item:
            return self._item.timestamp
        return None


class MissingItemsTreeView(QWidget):
    """Tree view for grouped missing timestamps."""
    
    itemSelected = pyqtSignal(MissingTimestamp)
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the tree view."""
        super().__init__(parent)
        self._items: List[MissingTimestamp] = []
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create controls for grouping
        controls_layout = QHBoxLayout()
        
        # Group by label
        controls_layout.addWidget(QLabel("Group by:"))
        
        # Group by combo
        self.group_combo = QComboBox()
        self.group_combo.addItem("Day", "day")
        self.group_combo.addItem("Hour", "hour")
        self.group_combo.addItem("Status", "status")
        self.group_combo.setCurrentIndex(0)
        self.group_combo.currentIndexChanged.connect(self._update_grouping)
        controls_layout.addWidget(self.group_combo)
        
        # Add stretch to push controls to left
        controls_layout.addStretch()
        
        # Expand/collapse all buttons
        self.expand_all_btn = QPushButton("Expand All")
        self.expand_all_btn.clicked.connect(self._expand_all)
        controls_layout.addWidget(self.expand_all_btn)
        
        self.collapse_all_btn = QPushButton("Collapse All")
        self.collapse_all_btn.clicked.connect(self._collapse_all)
        controls_layout.addWidget(self.collapse_all_btn)
        
        layout.addLayout(controls_layout)
        
        # Tree view
        self.tree_view = QTreeView()
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
        self.tree_view.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        self.tree_view.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.tree_view.setSortingEnabled(False)
        self.tree_view.setUniformRowHeights(True)
        
        # Create model and set it before accessing header
        self.model = GroupingModel()
        self.tree_view.setModel(self.model)

        # Set header properties (using walrus operator to handle optional value)
        if header := self.tree_view.header():
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        # Connect selection signal (using walrus operator to handle optional value)
        if selection_model := self.tree_view.selectionModel():
            selection_model.selectionChanged.connect(self._handle_selection)
        
        layout.addWidget(self.tree_view)
    
    def set_items(self, items: List[MissingTimestamp]) -> None:
        """
        Set the items to be displayed.
        
        Args:
            items: List of missing timestamps
        """
        self._items = items
        self._update_grouping()
    
    def _update_grouping(self) -> None:
        """Update the tree view with the current grouping."""
        grouping = self.group_combo.currentData()
        self.model.setItems(self._items, grouping)
        
        # Expand top-level items
        for i in range(self.model.rowCount()):
            index = self.model.index(i, 0)
            self.tree_view.expand(index)
    
    def _expand_all(self) -> None:
        """Expand all items in the tree."""
        self.tree_view.expandAll()
    
    def _collapse_all(self) -> None:
        """Collapse all items in the tree."""
        self.tree_view.collapseAll()
        
        # Expand top-level items
        for i in range(self.model.rowCount()):
            index = self.model.index(i, 0)
            self.tree_view.expand(index)
    
    def _handle_selection(self, selected, deselected) -> None:
        """
        Handle selection changes in the tree view.
        
        Args:
            selected: Selected indexes
            deselected: Deselected indexes
        """
        indexes = selected.indexes()
        if not indexes:
            return
        
        # Get the selected item
        index = indexes[0]
        item = self.model.getItem(index)
        
        if item and item._item:
            # Only emit for leaf items with an associated MissingTimestamp
            self.itemSelected.emit(item._item)


class ResultsSummaryWidget(QWidget):
    """Summary widget for integrity check results."""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the summary widget."""
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Title
        title = QLabel("Results Summary")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
        # Create grid for statistics
        stats_grid = QGridLayout()
        stats_grid.setColumnStretch(1, 1)  # Give stretch priority to the count column
        
        # Row 1: Total expected
        stats_grid.addWidget(QLabel("Total Expected:"), 0, 0)
        self.total_expected_label = QLabel("0")
        self.total_expected_label.setStyleSheet("font-weight: bold;")
        stats_grid.addWidget(self.total_expected_label, 0, 1)
        
        # Row 2: Found
        stats_grid.addWidget(QLabel("Available:"), 1, 0)
        self.found_label = QLabel("0")
        self.found_label.setStyleSheet("color: #28a745;")  # Green
        stats_grid.addWidget(self.found_label, 1, 1)
        
        # Row 3: Missing
        stats_grid.addWidget(QLabel("Missing:"), 2, 0)
        self.missing_label = QLabel("0")
        self.missing_label.setStyleSheet("color: #dc3545;")  # Red
        stats_grid.addWidget(self.missing_label, 2, 1)
        
        # Row 4: Downloaded
        stats_grid.addWidget(QLabel("Downloaded:"), 3, 0)
        self.downloaded_label = QLabel("0")
        self.downloaded_label.setStyleSheet("color: #007bff;")  # Blue
        stats_grid.addWidget(self.downloaded_label, 3, 1)
        
        # Row 5: Errors
        stats_grid.addWidget(QLabel("Errors:"), 4, 0)
        self.errors_label = QLabel("0")
        self.errors_label.setStyleSheet("color: #ffc107;")  # Yellow
        stats_grid.addWidget(self.errors_label, 4, 1)
        
        # Add stats grid to layout
        layout.addLayout(stats_grid)
        
        # Add progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #bbb;
                border-radius: 4px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #007bff;
                width: 20px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Add stretch to push everything to the top
        layout.addStretch()
    
    def update_summary(self, 
                      items: List[MissingTimestamp], 
                      total_expected: int) -> None:
        """
        Update the summary with current data.
        
        Args:
            items: List of missing timestamps
            total_expected: Total expected timestamps
        """
        # Calculate statistics
        downloaded = sum(1 for item in items if getattr(item, 'is_downloaded', False))
        errors = sum(1 for item in items if getattr(item, 'download_error', ''))
        missing = len(items) - downloaded - errors
        
        # Calculate found (not in the missing list)
        found = total_expected - len(items)
        if found < 0:
            found = 0
        
        # Update labels
        self.total_expected_label.setText(str(total_expected))
        self.found_label.setText(str(found))
        self.missing_label.setText(str(missing))
        self.downloaded_label.setText(str(downloaded))
        self.errors_label.setText(str(errors))
        
        # Update progress bar
        if total_expected > 0:
            complete_percent = int((found + downloaded) / total_expected * 100)
            self.progress_bar.setValue(complete_percent)
            self.progress_bar.setFormat(f"{complete_percent}% Complete")
        else:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("0% Complete")


class ItemPreviewWidget(QWidget):
    """Preview widget for showing details of a selected item."""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the preview widget."""
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Title
        title = QLabel("Item Details")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
        # Create form layout for details
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        
        # Timestamp
        self.timestamp_label = QLabel("")
        form_layout.addRow("Timestamp:", self.timestamp_label)
        
        # Filename
        self.filename_label = QLabel("")
        self.filename_label.setWordWrap(True)
        form_layout.addRow("Filename:", self.filename_label)
        
        # Status
        self.status_label = QLabel("")
        form_layout.addRow("Status:", self.status_label)
        
        # Path
        self.path_label = QLabel("")
        self.path_label.setWordWrap(True)
        form_layout.addRow("Path:", self.path_label)
        
        # Error details (only shown for error status)
        self.error_group = QGroupBox("Error Details")
        self.error_group.setVisible(False)
        error_layout = QVBoxLayout(self.error_group)
        
        self.error_text = QTextEdit()
        self.error_text.setReadOnly(True)
        self.error_text.setMaximumHeight(100)
        error_layout.addWidget(self.error_text)
        
        # Add form layout to main layout
        layout.addLayout(form_layout)
        layout.addWidget(self.error_group)
        
        # Add actions
        actions_layout = QHBoxLayout()
        
        self.download_btn = QPushButton("Download")
        self.download_btn.setEnabled(False)
        actions_layout.addWidget(self.download_btn)
        
        self.view_btn = QPushButton("View File")
        self.view_btn.setEnabled(False)
        actions_layout.addWidget(self.view_btn)
        
        layout.addLayout(actions_layout)
        
        # Add stretch to push everything to the top
        layout.addStretch()
    
    def set_item(self, item: Optional[MissingTimestamp]) -> None:
        """
        Set the item to preview.
        
        Args:
            item: MissingTimestamp to preview, or None to clear
        """
        if item is None:
            # Clear all fields
            self.timestamp_label.setText("")
            self.filename_label.setText("")
            self.status_label.setText("")
            self.path_label.setText("")
            self.error_text.setText("")
            self.error_group.setVisible(False)
            self.download_btn.setEnabled(False)
            self.view_btn.setEnabled(False)
            return
        
        # Update fields
        self.timestamp_label.setText(item.timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        self.filename_label.setText(item.expected_filename)
        
        # Set status with color
        if getattr(item, 'is_downloaded', False):
            self.status_label.setText("Downloaded")
            self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")  # Green
            self.download_btn.setEnabled(False)
            self.view_btn.setEnabled(True)
        elif getattr(item, 'is_downloading', False):
            progress = getattr(item, 'progress', 0)
            self.status_label.setText(f"Downloading ({progress}%)")
            self.status_label.setStyleSheet("color: #007bff; font-weight: bold;")  # Blue
            self.download_btn.setEnabled(False)
            self.view_btn.setEnabled(False)
        elif getattr(item, 'download_error', ''):
            self.status_label.setText("Error")
            self.status_label.setStyleSheet("color: #dc3545; font-weight: bold;")  # Red
            self.download_btn.setEnabled(True)
            self.view_btn.setEnabled(False)
        else:
            self.status_label.setText("Missing")
            self.status_label.setStyleSheet("color: #6c757d; font-weight: bold;")  # Gray
            self.download_btn.setEnabled(True)
            self.view_btn.setEnabled(False)
        
        # Set path
        if getattr(item, 'local_path', ''):
            self.path_label.setText(item.local_path)
        else:
            self.path_label.setText("Not available")
        
        # Set error details if available
        if getattr(item, 'download_error', ''):
            self.error_text.setText(item.download_error)
            self.error_group.setVisible(True)
        else:
            self.error_text.setText("")
            self.error_group.setVisible(False)