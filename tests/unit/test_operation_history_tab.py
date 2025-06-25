import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import types

# Provide stub modules if missing
if "goesvfi.utils.enhanced_log" not in sys.modules:
    sys.modules["goesvfi.utils.enhanced_log"] = types.SimpleNamespace(get_enhanced_logger=lambda name: None)
if "goesvfi.utils.operation_history" not in sys.modules:
    sys.modules["goesvfi.utils.operation_history"] = types.SimpleNamespace(get_operation_store=lambda: None)

from unittest.mock import patch

import pytest
from PyQt6.QtWidgets import QApplication

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

    def cleanup_old_operations(self, days: int = 30):
        return 0

    def export_to_json(self, path, filters):
        pass


@pytest.fixture
def dummy_store():
    return DummyStore()


@pytest.fixture
def history_tab(dummy_store):
    app = QApplication.instance() or QApplication([])

    def immediate_start(self):
        oh_tab.RefreshWorker.run(self)

    with (
        patch(
            "goesvfi.gui_tabs.operation_history_tab.get_operation_store",
            return_value=dummy_store,
        ),
        patch("goesvfi.gui_tabs.operation_history_tab.QMessageBox"),
        patch(
            "goesvfi.gui_tabs.operation_history_tab.RefreshWorker.start",
            new=immediate_start,
        ),
    ):
        tab = oh_tab.OperationHistoryTab()
        QApplication.processEvents()
        yield tab
        tab.cleanup()


def test_table_models_populate(history_tab, dummy_store):
    assert history_tab.operations_model.rowCount() == len(dummy_store.operations)
    first_op_index = history_tab.operations_model.index(0, 1)
    assert history_tab.operations_model.data(first_op_index) == dummy_store.operations[0]["name"]

    assert history_tab.metrics_model.rowCount() == len(dummy_store.metrics)
    first_metric_index = history_tab.metrics_model.index(0, 0)
    assert history_tab.metrics_model.data(first_metric_index) == dummy_store.metrics[0]["operation_name"]


def test_auto_refresh_toggle(history_tab):
    assert not history_tab.auto_refresh_timer.isActive()

    history_tab.refresh_interval.setValue(1)
    history_tab.auto_refresh_check.setChecked(True)
    assert history_tab.auto_refresh_timer.isActive()
    assert history_tab.auto_refresh_timer.interval() == 1000

    history_tab.refresh_interval.setValue(2)
    history_tab._update_refresh_interval(2)
    assert history_tab.auto_refresh_timer.interval() == 2000

    history_tab.auto_refresh_check.setChecked(False)
    assert not history_tab.auto_refresh_timer.isActive()
