"""Unit tests for the ResourceLimitsTab GUI component - Optimized v2."""

from __future__ import annotations

from dataclasses import dataclass
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

from PyQt6.QtWidgets import QApplication
import pytest


# Optimized stub implementation with session-scoped fixture
@pytest.fixture(scope="session", autouse=True)
def stub_resource_manager(monkeypatch) -> Any:  # noqa: ANN001
    """Provide a minimal goesvfi.utils.resource_manager module for testing.

    Yields:
        None: This fixture provides a module stub for the test session.
    """
    module = ModuleType("goesvfi.utils.resource_manager")

    @dataclass
    class ResourceLimits:
        max_memory_mb: int | None = None
        max_cpu_percent: int | None = None
        max_processing_time_sec: int | None = None
        max_open_files: int | None = None
        enable_swap_limit: bool = True

    class ResourceMonitor:
        def __init__(self, limits: ResourceLimits, check_interval: float = 1.0) -> None:  # noqa: ARG002
            self.limits = limits
            self.started = False

        def start_monitoring(self) -> None:
            self.started = True

        def stop_monitoring(self) -> None:
            self.started = False

        def get_current_usage(self) -> SimpleNamespace:  # noqa: PLR6301
            return SimpleNamespace(
                memory_percent=0.0,
                cpu_percent=0.0,
                memory_mb=0.0,
                processing_time_sec=0.0,
                open_files=0,
            )

    def get_system_resource_info() -> dict[str, Any]:
        return {
            "memory": {"total_mb": 8192, "available_mb": 4096, "percent_used": 10.0},
            "cpu": {"count": 4},
            "disk": {"total_gb": 256, "free_gb": 128, "percent_used": 50.0},
        }

    module.ResourceLimits = ResourceLimits  # type: ignore[attr-defined]
    module.ResourceMonitor = ResourceMonitor  # type: ignore[attr-defined]
    module.get_system_resource_info = get_system_resource_info  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "goesvfi.utils.resource_manager", module)

    yield

    monkeypatch.delitem(sys.modules, "goesvfi.utils.resource_manager", raising=False)


@pytest.fixture()
def resource_tab(qtbot) -> Any:  # noqa: ANN001
    """Create a ResourceLimitsTab instance with the stub resource manager.

    Returns:
        ResourceLimitsTab: The created tab instance.
    """
    from goesvfi.gui_tabs.resource_limits_tab import ResourceLimitsTab  # noqa: PLC0415

    tab = ResourceLimitsTab()
    qtbot.addWidget(tab)
    QApplication.processEvents()
    return tab


class TestResourceLimitsTab:
    """Test ResourceLimitsTab GUI component with optimized patterns."""

    @pytest.mark.parametrize(
        "checkbox_spinbox_pairs",
        [
            [
                ("memory_limit_checkbox", "memory_limit_spinbox"),
                ("time_limit_checkbox", "time_limit_spinbox"),
                ("cpu_limit_checkbox", "cpu_limit_spinbox"),
                ("files_limit_checkbox", "files_limit_spinbox"),
            ]
        ],
    )
    def test_checkbox_spinbox_interactions(  # noqa: PLR6301
        self, resource_tab: Any, checkbox_spinbox_pairs: list[tuple[str, str]]
    ) -> None:
        """Test that checkboxes properly enable/disable their corresponding spinboxes."""
        for checkbox_name, spinbox_name in checkbox_spinbox_pairs:
            checkbox = getattr(resource_tab, checkbox_name)
            spinbox = getattr(resource_tab, spinbox_name)

            # Initial state should be disabled
            assert not spinbox.isEnabled()

            # Enable checkbox
            checkbox.setChecked(True)
            assert spinbox.isEnabled()

            # Disable checkbox
            checkbox.setChecked(False)
            assert not spinbox.isEnabled()

    @pytest.mark.parametrize(
        "limit_config",
        [
            {
                "memory": {"enabled": True, "value": 1024, "expected_attr": "max_memory_mb"},
                "time": {"enabled": False, "value": 600, "expected_attr": "max_processing_time_sec"},
            },
            {
                "memory": {"enabled": True, "value": 2048, "expected_attr": "max_memory_mb"},
                "time": {"enabled": True, "value": 300, "expected_attr": "max_processing_time_sec"},
            },
            {
                "memory": {"enabled": False, "value": 512, "expected_attr": "max_memory_mb"},
                "time": {"enabled": True, "value": 900, "expected_attr": "max_processing_time_sec"},
            },
        ],
    )
    def test_limits_changed_signal_emission(self, resource_tab: Any, limit_config: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test that limits_changed signal emits correct ResourceLimits values."""
        emitted_limits: list[Any] = []
        resource_tab.limits_changed.connect(emitted_limits.append)

        # Configure memory limit
        memory_config = limit_config["memory"]
        resource_tab.memory_limit_checkbox.setChecked(memory_config["enabled"])
        if memory_config["enabled"]:
            resource_tab.memory_limit_spinbox.setValue(memory_config["value"])
        QApplication.processEvents()

        # Configure time limit
        time_config = limit_config["time"]
        resource_tab.time_limit_checkbox.setChecked(time_config["enabled"])
        if time_config["enabled"]:
            resource_tab.time_limit_spinbox.setValue(time_config["value"])
        QApplication.processEvents()

        # Verify last emitted signal has correct values
        assert len(emitted_limits) > 0
        last_limits = emitted_limits[-1]

        # Check memory limit
        expected_memory = memory_config["value"] if memory_config["enabled"] else None
        assert getattr(last_limits, memory_config["expected_attr"]) == expected_memory

        # Check time limit
        expected_time = time_config["value"] if time_config["enabled"] else None
        assert getattr(last_limits, time_config["expected_attr"]) == expected_time

    def test_limit_workflow_sequence(self, resource_tab: Any) -> None:  # noqa: PLR6301
        """Test complete workflow of enabling, configuring, and disabling limits."""
        emitted_limits: list[Any] = []
        resource_tab.limits_changed.connect(emitted_limits.append)

        # Step 1: Enable memory limit and set value
        resource_tab.memory_limit_checkbox.setChecked(True)
        resource_tab.memory_limit_spinbox.setValue(1024)
        QApplication.processEvents()

        current_limits = emitted_limits[-1]
        assert current_limits.max_memory_mb == 1024
        assert current_limits.max_processing_time_sec is None

        # Step 2: Enable processing time limit
        resource_tab.time_limit_checkbox.setChecked(True)
        resource_tab.time_limit_spinbox.setValue(600)
        QApplication.processEvents()

        current_limits = emitted_limits[-1]
        assert current_limits.max_memory_mb == 1024
        assert current_limits.max_processing_time_sec == 600

        # Step 3: Disable memory limit (time remains enabled)
        resource_tab.memory_limit_checkbox.setChecked(False)
        QApplication.processEvents()

        current_limits = emitted_limits[-1]
        assert current_limits.max_memory_mb is None
        assert current_limits.max_processing_time_sec == 600

        # Step 4: Disable time limit (all limits disabled)
        resource_tab.time_limit_checkbox.setChecked(False)
        QApplication.processEvents()

        current_limits = emitted_limits[-1]
        assert current_limits.max_memory_mb is None
        assert current_limits.max_processing_time_sec is None
