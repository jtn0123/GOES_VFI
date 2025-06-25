"""Unit tests for the ResourceLimitsTab GUI component."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from types import ModuleType, SimpleNamespace
from typing import Optional

import pytest
from PyQt6.QtWidgets import QApplication

# ---------------------------------------------------------------------------
# Fixtures to provide stub implementations for the resource manager module.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def stub_resource_manager(monkeypatch):
    """Provide a minimal goesvfi.utils.resource_manager module for testing."""
    module = ModuleType("goesvfi.utils.resource_manager")

    @dataclass
    class ResourceLimits:
        max_memory_mb: Optional[int] = None
        max_cpu_percent: Optional[int] = None
        max_processing_time_sec: Optional[int] = None
        max_open_files: Optional[int] = None
        enable_swap_limit: bool = True

    class ResourceMonitor:
        def __init__(self, limits: ResourceLimits, check_interval: float = 1.0) -> None:
            self.limits = limits
            self.started = False

        def start_monitoring(self) -> None:
            self.started = True

        def stop_monitoring(self) -> None:
            self.started = False

        def get_current_usage(self) -> SimpleNamespace:
            return SimpleNamespace(
                memory_percent=0.0,
                cpu_percent=0.0,
                memory_mb=0.0,
                processing_time_sec=0.0,
                open_files=0,
            )

    def get_system_resource_info() -> dict:
        return {
            "memory": {"total_mb": 8192, "available_mb": 4096, "percent_used": 10.0},
            "cpu": {"count": 4},
            "disk": {"total_gb": 256, "free_gb": 128, "percent_used": 50.0},
        }

    module.ResourceLimits = ResourceLimits
    module.ResourceMonitor = ResourceMonitor
    module.get_system_resource_info = get_system_resource_info

    monkeypatch.setitem(sys.modules, "goesvfi.utils.resource_manager", module)

    yield

    monkeypatch.delitem(sys.modules, "goesvfi.utils.resource_manager", raising=False)


@pytest.fixture
def resource_tab(qtbot):
    """Create a ResourceLimitsTab instance with the stub resource manager."""
    from goesvfi.gui_tabs.resource_limits_tab import ResourceLimitsTab

    tab = ResourceLimitsTab()
    qtbot.addWidget(tab)
    QApplication.processEvents()
    return tab


def test_checkboxes_toggle_spinboxes(resource_tab):
    """Each limit checkbox should enable or disable its spinbox."""
    pairs = [
        (resource_tab.memory_limit_checkbox, resource_tab.memory_limit_spinbox),
        (resource_tab.time_limit_checkbox, resource_tab.time_limit_spinbox),
        (resource_tab.cpu_limit_checkbox, resource_tab.cpu_limit_spinbox),
        (resource_tab.files_limit_checkbox, resource_tab.files_limit_spinbox),
    ]

    for checkbox, spinbox in pairs:
        # Initial state should be disabled
        assert not spinbox.isEnabled()
        # Enable
        checkbox.setChecked(True)
        assert spinbox.isEnabled()
        # Disable again
        checkbox.setChecked(False)
        assert not spinbox.isEnabled()


def test_limits_changed_emits_expected_values(resource_tab):
    """Toggling limits should emit ResourceLimits with expected values."""
    from goesvfi.utils.resource_manager import ResourceLimits

    emitted = []
    resource_tab.limits_changed.connect(lambda limits: emitted.append(limits))

    # Enable memory limit and set value
    resource_tab.memory_limit_checkbox.setChecked(True)
    resource_tab.memory_limit_spinbox.setValue(1024)
    QApplication.processEvents()
    assert getattr(emitted[-1], "max_memory_mb") == 1024
    assert getattr(emitted[-1], "max_processing_time_sec") is None

    # Enable processing time limit
    resource_tab.time_limit_checkbox.setChecked(True)
    resource_tab.time_limit_spinbox.setValue(600)
    QApplication.processEvents()
    last = emitted[-1]
    assert last.max_memory_mb == 1024
    assert last.max_processing_time_sec == 600

    # Disable memory limit
    resource_tab.memory_limit_checkbox.setChecked(False)
    QApplication.processEvents()
    last = emitted[-1]
    assert last.max_memory_mb is None
    assert last.max_processing_time_sec == 600

    # Disable time limit
    resource_tab.time_limit_checkbox.setChecked(False)
    QApplication.processEvents()
    last = emitted[-1]
    assert last.max_memory_mb is None
    assert last.max_processing_time_sec is None
