import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import types

# Provide stub modules if missing
if "goesvfi.utils.enhanced_log" not in sys.modules:
    stub_module = types.ModuleType("goesvfi.utils.enhanced_log")
    stub_module.get_enhanced_logger = lambda name: None  # type: ignore[attr-defined]
    sys.modules["goesvfi.utils.enhanced_log"] = stub_module
if "goesvfi.utils.operation_history" not in sys.modules:
    stub_module = types.ModuleType("goesvfi.utils.operation_history")
    stub_module.get_operation_store = lambda: None  # type: ignore[attr-defined]
    sys.modules["goesvfi.utils.operation_history"] = stub_module

from unittest.mock import patch

from PyQt6.QtWidgets import QApplication
import pytest

import goesvfi.gui_tabs.operation_history_tab as oh_tab


class DummyStore:
    def __init__(self) -> None:
        self.operations = [
            {
                "name": "process_frame",
                "status": "success",
                "start_time": 1000,
                "end_time": 1001,
                "duration": 1.0,
                "correlation_id": "abc12345",
                "metadata": {},
            },
            {
                "name": "download_data",
                "status": "failure",
                "start_time": 2000,
                "end_time": None,
                "duration": None,
                "correlation_id": "def67890",
                "metadata": {"error": "Timeout"},
            },
        ]
        self.metrics = [
            {
                "operation_name": "process_frame",
                "total_count": 1,
                "success_count": 1,
                "failure_count": 0,
                "avg_duration": 1.0,
                "min_duration": 1.0,
                "max_duration": 1.0,
            },
            {
                "operation_name": "download_data",
                "total_count": 1,
                "success_count": 0,
                "failure_count": 1,
                "avg_duration": 0.0,
                "min_duration": 0.0,
                "max_duration": 0.0,
            },
        ]

    def get_recent_operations(self, limit: int = 500):
        return self.operations[:limit]

    def search_operations(self, **filters):
        return self.operations

    def get_operation_metrics(self):
        return self.metrics

    def cleanup_old_operations(self, days: int = 30) -> int:
        return 0

    def export_to_json(self, path, filters) -> None:
        pass


@pytest.fixture()
def dummy_store():
    return DummyStore()


@pytest.fixture()
def history_tab_models(dummy_store):
    """Create just the table models without the full widget to avoid segfaults."""
    QApplication.instance() or QApplication([])

    # Create models directly without the parent widget
    operations_model = oh_tab.OperationTableModel()
    metrics_model = oh_tab.MetricsModel()

    # Populate with dummy data
    operations_model.update_operations(dummy_store.operations)
    metrics_model.update_metrics(dummy_store.metrics)

    # Create a mock tab object with just the models
    class MockHistoryTab:
        def __init__(self) -> None:
            self.operations_model = operations_model
            self.metrics_model = metrics_model

    return MockHistoryTab()


def test_table_models_populate(history_tab_models, dummy_store) -> None:
    """Test that table models can be populated with data."""
    assert history_tab_models.operations_model.rowCount() == len(dummy_store.operations)
    first_op_index = history_tab_models.operations_model.index(0, 1)
    assert history_tab_models.operations_model.data(first_op_index) == dummy_store.operations[0]["name"]

    assert history_tab_models.metrics_model.rowCount() == len(dummy_store.metrics)
    first_metric_index = history_tab_models.metrics_model.index(0, 0)
    assert history_tab_models.metrics_model.data(first_metric_index) == dummy_store.metrics[0]["operation_name"]


def test_refresh_worker_functionality(dummy_store) -> None:
    """Test that RefreshWorker can function without crashing."""
    QApplication.instance() or QApplication([])

    with patch(
        "goesvfi.gui_tabs.operation_history_tab.get_operation_store",
        return_value=dummy_store,
    ):
        worker = oh_tab.RefreshWorker()
        worker.filters = {}
        worker.load_metrics = True

        # Test that run method executes without error
        operations_received = []
        metrics_received = []

        def collect_operations(ops) -> None:
            operations_received.extend(ops)

        def collect_metrics(metrics) -> None:
            metrics_received.extend(metrics)

        worker.operations_loaded.connect(collect_operations)
        worker.metrics_loaded.connect(collect_metrics)

        # Run synchronously to avoid threading issues in tests
        worker.run()

        # Verify data was emitted
        assert len(operations_received) == len(dummy_store.operations)
        assert len(metrics_received) == len(dummy_store.metrics)
