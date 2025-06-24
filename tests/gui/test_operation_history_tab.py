import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest


def test_export_operations_dialog_and_filters(qtbot, monkeypatch):
    """Export uses selected path and passes current filters."""
    # Provide stub for missing enhanced_log module before import
    dummy_log = ModuleType("enhanced_log")
    dummy_log.get_enhanced_logger = lambda *_args, **_kwargs: MagicMock()
    monkeypatch.setitem(sys.modules, "goesvfi.utils.enhanced_log", dummy_log)

    dummy_history = ModuleType("operation_history")
    store = MagicMock()
    dummy_history.get_operation_store = lambda: store
    monkeypatch.setitem(sys.modules, "goesvfi.utils.operation_history", dummy_history)

    from goesvfi.gui_tabs.operation_history_tab import OperationHistoryTab

    tab = OperationHistoryTab()
    qtbot.addWidget(tab)

    tab.search_input.setText("Download")
    tab.status_filter.setCurrentText("Success")

    dialog_path = Path("/tmp/export.json")
    mock_get_save = MagicMock(return_value=(str(dialog_path), "JSON Files (*.json)"))
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QFileDialog.getSaveFileName",
        mock_get_save,
    )
    monkeypatch.setattr(
        "goesvfi.gui_tabs.operation_history_tab.QMessageBox.information", MagicMock()
    )

    tab._export_operations()

    mock_get_save.assert_called_once()
    store.export_to_json.assert_called_once_with(
        dialog_path, {"name": "Download", "status": "success"}
    )
