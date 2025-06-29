"""Operation history viewer tab for the GUI."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import IntEnum
from pathlib import Path
from typing import Any

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from goesvfi.gui_components.icon_manager import get_icon
from goesvfi.gui_components.update_manager import register_update, request_update
from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


# Column indices for operation table
class OperationTableColumn(IntEnum):
    """Column indices for the operation history table."""

    TIME = 0
    OPERATION = 1
    STATUS = 2
    DURATION = 3
    CORRELATION_ID = 4


# Column indices for metrics table
class MetricsTableColumn(IntEnum):
    """Column indices for the metrics table."""

    OPERATION = 0
    TOTAL = 1
    SUCCESS = 2
    FAILURE = 3
    AVG_DURATION = 4
    MIN = 5
    MAX = 6


# Default values
DEFAULT_OPERATIONS_LIMIT = 500


def get_operation_store() -> Any | None:
    """Get the operation store instance.

    Returns:
        Optional: The operation store instance, or None if not implemented.
    """
    # TODO: Implement operation store
    return None


class OperationTableModel(QAbstractTableModel):
    """Table model for displaying operations."""

    def __init__(self) -> None:  # noqa: D107
        super().__init__()
        self.operations: list[dict[str, Any]] = []
        self.columns = ["Time", "Operation", "Status", "Duration", "Correlation ID"]

    def update_operations(self, operations: list[dict[str, Any]]) -> None:
        """Update the operations list."""
        self.beginResetModel()
        self.operations = operations
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802, DOC201
        """Get number of rows."""
        if parent is None:
            parent = QModelIndex()
        return len(self.operations)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802, DOC201
        """Get number of columns."""
        if parent is None:
            parent = QModelIndex()
        return len(self.columns)

    def data(self, index: QModelIndex, role: int | None = None) -> Any:  # noqa: C901, PLR0911, PLR0912, DOC201
        """Get data for a cell."""
        if role is None:
            role = Qt.ItemDataRole.DisplayRole
        if not index.isValid() or index.row() >= len(self.operations):
            return None

        operation = self.operations[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == OperationTableColumn.TIME:  # Time
                timestamp = operation.get("start_time", 0)
                return datetime.fromtimestamp(timestamp, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
            if col == OperationTableColumn.OPERATION:  # Operation
                return operation.get("name", "")
            if col == OperationTableColumn.STATUS:  # Status
                return operation.get("status", "")
            if col == OperationTableColumn.DURATION:  # Duration
                duration = operation.get("duration")
                if duration is not None:
                    return f"{duration:.3f}s"
                return "N/A"
            if col == OperationTableColumn.CORRELATION_ID:  # Correlation ID
                return operation.get("correlation_id", "")[:8] + "..."

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in {OperationTableColumn.STATUS, OperationTableColumn.DURATION}:  # Center align status and duration
                return Qt.AlignmentFlag.AlignCenter

        elif role == Qt.ItemDataRole.ForegroundRole and col == OperationTableColumn.STATUS:  # Color code status
            status = operation.get("status", "")
            if status == "success":
                return Qt.GlobalColor.darkGreen
            if status == "failure":
                return Qt.GlobalColor.darkRed
            return Qt.GlobalColor.darkYellow

        return None

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """Get header data."""
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.columns[section]
        return None

    def get_operation(self, row: int) -> dict[str, Any] | None:
        """Get operation at given row."""
        if 0 <= row < len(self.operations):
            return self.operations[row]
        return None


class MetricsModel(QAbstractTableModel):
    """Table model for displaying operation metrics."""

    def __init__(self) -> None:
        super().__init__()
        self.metrics: list[dict[str, Any]] = []
        self.columns = [
            "Operation",
            "Total",
            "Success",
            "Failure",
            "Avg Duration",
            "Min",
            "Max",
        ]

    def update_metrics(self, metrics: list[dict[str, Any]]) -> None:
        """Update the metrics list."""
        self.beginResetModel()
        self.metrics = metrics
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        """Get number of rows."""
        if parent is None:
            parent = QModelIndex()
        return len(self.metrics)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        """Get number of columns."""
        if parent is None:
            parent = QModelIndex()
        return len(self.columns)

    def data(self, index: QModelIndex, role: int | None = None) -> Any:  # noqa: C901, PLR0911
        """Get data for a cell."""
        if role is None:
            role = Qt.ItemDataRole.DisplayRole
        if not index.isValid() or index.row() >= len(self.metrics):
            return None

        metric = self.metrics[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == MetricsTableColumn.OPERATION:  # Operation
                return metric.get("operation_name", "")
            if col == MetricsTableColumn.TOTAL:  # Total
                return str(metric.get("total_count", 0))
            if col == MetricsTableColumn.SUCCESS:  # Success
                return str(metric.get("success_count", 0))
            if col == MetricsTableColumn.FAILURE:  # Failure
                return str(metric.get("failure_count", 0))
            if col == MetricsTableColumn.AVG_DURATION:  # Avg Duration
                avg = metric.get("avg_duration", 0)
                return f"{avg:.3f}s" if avg else "N/A"
            if col == MetricsTableColumn.MIN:  # Min
                min_dur = metric.get("min_duration", 0)
                return f"{min_dur:.3f}s" if min_dur else "N/A"
            if col == MetricsTableColumn.MAX:  # Max
                max_dur = metric.get("max_duration", 0)
                return f"{max_dur:.3f}s" if max_dur else "N/A"

        elif (
            role == Qt.ItemDataRole.TextAlignmentRole and col > MetricsTableColumn.OPERATION
        ):  # Right align numeric columns
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

        return None

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """Get header data."""
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.columns[section]
        return None


class RefreshWorker(QThread):
    """Worker thread for refreshing operation data."""

    operations_loaded = pyqtSignal(list)
    metrics_loaded = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.filters: dict[str, Any] = {}
        self.load_metrics = True

    def run(self) -> None:
        """Run the refresh task."""
        try:
            store = get_operation_store()

            # Load operations
            if store is not None:
                if self.filters:
                    operations = store.search_operations(**self.filters)
                else:
                    operations = store.get_recent_operations(limit=DEFAULT_OPERATIONS_LIMIT)
                self.operations_loaded.emit(operations)

                # Load metrics if requested
                if self.load_metrics:
                    metrics = store.get_operation_metrics()
                    self.metrics_loaded.emit(metrics)
            else:
                # Emit empty data when store is not available
                self.operations_loaded.emit([])
                if self.load_metrics:
                    self.metrics_loaded.emit([])

        except Exception as e:
            LOGGER.exception("Error refreshing operation data")
            self.error_occurred.emit(str(e))


class OperationHistoryTab(QWidget):
    """Tab widget for viewing operation history."""

    def __init__(self) -> None:
        super().__init__()
        self.refresh_worker: RefreshWorker | None = None
        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(lambda: request_update("operation_history_refresh"))

        self._init_ui()
        self._setup_update_manager()
        self.refresh_data()

    def _init_ui(self) -> None:  # noqa: PLR0915, PLR0914
        """Initialize the user interface."""
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Add header with icon
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)

        icon_label = QLabel()
        icon_label.setPixmap(get_icon("📃").pixmap(24, 24))
        header_layout.addWidget(icon_label)

        header_text = QLabel("Operation History")
        header_text.setProperty("class", "AppHeader")
        header_layout.addWidget(header_text)
        header_layout.addStretch()

        layout.addWidget(header_widget)

        # Controls in a frame
        control_frame = QFrame()
        control_frame.setProperty("class", "ControlFrame")
        controls_layout = QHBoxLayout(control_frame)
        controls_layout.setContentsMargins(10, 10, 10, 10)
        controls_layout.setSpacing(10)

        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search operations...")
        self.search_input.setToolTip("Search operations by name")
        self.search_input.returnPressed.connect(self.refresh_data)
        search_label = QLabel("Search:")
        search_label.setProperty("class", "StandardLabel")
        controls_layout.addWidget(search_label)
        controls_layout.addWidget(self.search_input)

        # Status filter
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Success", "Failure", "In Progress"])
        self.status_filter.setToolTip("Filter operations by status")
        self.status_filter.currentTextChanged.connect(self.refresh_data)
        status_label = QLabel("Status:")
        status_label.setProperty("class", "StandardLabel")
        controls_layout.addWidget(status_label)
        controls_layout.addWidget(self.status_filter)

        # Auto-refresh
        self.auto_refresh_check = QCheckBox("Auto-refresh")
        self.auto_refresh_check.setToolTip("Automatically refresh operation history")
        self.auto_refresh_check.toggled.connect(self._toggle_auto_refresh)
        controls_layout.addWidget(self.auto_refresh_check)

        self.refresh_interval = QSpinBox()
        self.refresh_interval.setRange(1, 60)
        self.refresh_interval.setValue(5)
        self.refresh_interval.setSuffix(" sec")
        self.refresh_interval.setToolTip("Auto-refresh interval in seconds")
        self.refresh_interval.valueChanged.connect(self._update_refresh_interval)
        controls_layout.addWidget(self.refresh_interval)

        # Buttons
        self.refresh_button = QPushButton("🔄 Refresh")
        self.refresh_button.setProperty("class", "DialogButton")
        self.refresh_button.setToolTip("Manually refresh operation history")
        self.refresh_button.clicked.connect(self.refresh_data)
        controls_layout.addWidget(self.refresh_button)

        self.clear_button = QPushButton("🧹 Clear Old")
        self.clear_button.setProperty("class", "DialogButton")
        self.clear_button.setToolTip("Clear operations older than 30 days")
        self.clear_button.clicked.connect(self._clear_old_operations)
        controls_layout.addWidget(self.clear_button)

        self.export_button = QPushButton("💾 Export")
        self.export_button.setProperty("class", "DialogButton")
        self.export_button.setToolTip("Export operations to JSON file")
        self.export_button.clicked.connect(self._export_operations)
        controls_layout.addWidget(self.export_button)

        controls_layout.addStretch()
        layout.addWidget(control_frame)

        # Main content splitter
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Operations table
        operations_group = QGroupBox("📋 Operations")
        operations_layout = QVBoxLayout()

        self.operations_table = QTableView()
        self.operations_model = OperationTableModel()
        self.operations_table.setModel(self.operations_model)
        self.operations_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        selection_model = self.operations_table.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self._on_operation_selected)

        # Configure table
        table_header = self.operations_table.horizontalHeader()
        if table_header:
            table_header.setStretchLastSection(True)
            table_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Stretch operation name

        operations_layout.addWidget(self.operations_table)
        operations_group.setLayout(operations_layout)
        splitter.addWidget(operations_group)

        # Details panel
        details_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Operation details
        details_group = QGroupBox("Operation Details")
        details_layout = QVBoxLayout()

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        details_layout.addWidget(self.details_text)
        details_group.setLayout(details_layout)
        details_splitter.addWidget(details_group)

        # Metrics table
        metrics_group = QGroupBox("Operation Metrics")
        metrics_layout = QVBoxLayout()

        self.metrics_table = QTableView()
        self.metrics_model = MetricsModel()
        self.metrics_table.setModel(self.metrics_model)

        # Configure metrics table
        metrics_header = self.metrics_table.horizontalHeader()
        if metrics_header:
            metrics_header.setStretchLastSection(False)
            metrics_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Stretch operation name

        metrics_layout.addWidget(self.metrics_table)
        metrics_group.setLayout(metrics_layout)
        details_splitter.addWidget(metrics_group)

        splitter.addWidget(details_splitter)

        # Set splitter sizes
        splitter.setSizes([400, 200])
        details_splitter.setSizes([400, 400])

        layout.addWidget(splitter)
        self.setLayout(layout)

    def _setup_update_manager(self) -> None:
        """Set up UpdateManager integration for batched UI updates."""
        # Register update operations
        register_update("operation_history_table", self._update_table_display, priority=2)
        register_update("operation_history_details", self._update_details_display, priority=3)
        register_update("operation_history_refresh", self._do_refresh_data, priority=1)

        LOGGER.info("OperationHistoryTab integrated with UpdateManager")

    def _update_table_display(self) -> None:
        """Update table display (called by UpdateManager)."""
        if hasattr(self, "operations_table") and self.operations_table:
            # Force table view update
            viewport = self.operations_table.viewport()
            if viewport:
                viewport.update()

    def _update_details_display(self) -> None:
        """Update details display (called by UpdateManager)."""
        # Details are updated directly when selection changes

    def _do_refresh_data(self) -> None:
        """Perform data refresh (called by UpdateManager)."""
        # This allows batching of refresh requests
        self.refresh_data()

    def request_ui_update(self, update_type: str = "table") -> None:
        """Request UI updates through UpdateManager.

        Args:
            update_type: Type of update ('table', 'details', 'refresh')
        """
        if update_type == "table":
            request_update("operation_history_table")
        elif update_type == "details":
            request_update("operation_history_details")
        elif update_type == "refresh":
            request_update("operation_history_refresh")

    def refresh_data(self) -> None:
        """Refresh the operation data."""
        if self.refresh_worker and self.refresh_worker.isRunning():
            return

        # Build filters
        filters = {}

        search_text = self.search_input.text().strip()
        if search_text:
            filters["name"] = search_text

        status_text = self.status_filter.currentText()
        if status_text != "All":
            filters["status"] = status_text.lower().replace(" ", "_")

        # Create and start worker
        self.refresh_worker = RefreshWorker()
        self.refresh_worker.filters = filters
        self.refresh_worker.operations_loaded.connect(self._on_operations_loaded)
        self.refresh_worker.metrics_loaded.connect(self._on_metrics_loaded)
        self.refresh_worker.error_occurred.connect(self._on_error)
        self.refresh_worker.start()

        self.refresh_button.setEnabled(False)

    def _on_operations_loaded(self, operations: list[dict[str, Any]]) -> None:
        """Handle loaded operations."""
        self.operations_model.update_operations(operations)
        self.refresh_button.setEnabled(True)

    def _on_metrics_loaded(self, metrics: list[dict[str, Any]]) -> None:
        """Handle loaded metrics."""
        self.metrics_model.update_metrics(metrics)

    def _on_error(self, error_msg: str) -> None:
        """Handle refresh error."""
        self.refresh_button.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Failed to refresh data: {error_msg}")

    def _on_operation_selected(self) -> None:
        """Handle operation selection."""
        indexes = self.operations_table.selectedIndexes()
        if indexes:
            row = indexes[0].row()
            operation = self.operations_model.get_operation(row)
            if operation:
                self._show_operation_details(operation)

    def _show_operation_details(self, operation: dict[str, Any]) -> None:
        """Show details for selected operation."""
        details: list[str] = []
        details.extend((
            f"<b>Operation:</b> {operation.get('name', 'N/A')}",
            f"<b>Correlation ID:</b> {operation.get('correlation_id', 'N/A')}",
            f"<b>Status:</b> {operation.get('status', 'N/A')}",
        ))

        # Times
        start_time = operation.get("start_time", 0)
        end_time = operation.get("end_time")
        details.append(
            f"<b>Start Time:</b> {datetime.fromtimestamp(start_time, tz=UTC).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}"
        )

        if end_time:
            details.append(
                f"<b>End Time:</b> {datetime.fromtimestamp(end_time, tz=UTC).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}"
            )

        duration = operation.get("duration")
        if duration is not None:
            details.append(f"<b>Duration:</b> {duration:.3f} seconds")

        # Error
        error = operation.get("error")
        if error:
            details.append(f"<b>Error:</b> <span style='color: red;'>{error}</span>")

        # Metadata
        metadata = operation.get("metadata", {})
        if metadata:
            details.append("<b>Metadata:</b>")
            for key, value in metadata.items():
                details.append(f"  • {key}: {value}")

        self.details_text.setHtml("<br>".join(details))

    def _toggle_auto_refresh(self, checked: bool) -> None:  # noqa: FBT001
        """Toggle auto-refresh."""
        if checked:
            interval = self.refresh_interval.value() * 1000  # Convert to milliseconds
            self.auto_refresh_timer.start(interval)
        else:
            self.auto_refresh_timer.stop()

    def _update_refresh_interval(self, value: int) -> None:
        """Update refresh interval."""
        if self.auto_refresh_check.isChecked():
            self.auto_refresh_timer.setInterval(value * 1000)

    def _clear_old_operations(self) -> None:
        """Clear old operations."""
        reply = QMessageBox.question(
            self,
            "Clear Old Operations",
            "Clear operations older than 30 days?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                store = get_operation_store()
                if store is not None:
                    count = store.cleanup_old_operations(days=30)
                    QMessageBox.information(self, "Success", f"Cleared {count} old operations")
                    self.refresh_data()
                else:
                    QMessageBox.information(self, "Info", "Operation store not implemented yet")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear operations: {e!s}")

    def _export_operations(self) -> None:
        """Export operations to file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Operations",
            str(Path.home() / "operations_export.json"),
            "JSON Files (*.json)",
        )

        if file_path:
            try:
                store = get_operation_store()

                if store is not None:
                    # Get current filters
                    filters = {}
                    search_text = self.search_input.text().strip()
                    if search_text:
                        filters["name"] = search_text

                    status_text = self.status_filter.currentText()
                    if status_text != "All":
                        filters["status"] = status_text.lower().replace(" ", "_")

                    store.export_to_json(Path(file_path), filters)
                    QMessageBox.information(self, "Success", f"Operations exported to {file_path}")
                else:
                    QMessageBox.information(self, "Info", "Operation store not implemented yet")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export operations: {e!s}")

    def cleanup(self) -> None:
        """Clean up resources."""
        self.auto_refresh_timer.stop()
        if self.refresh_worker and self.refresh_worker.isRunning():
            self.refresh_worker.quit()
            self.refresh_worker.wait()
