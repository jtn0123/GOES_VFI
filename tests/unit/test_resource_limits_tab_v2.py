"""Unit tests for the ResourceLimitsTab GUI component - Optimized v2."""

from __future__ import annotations

from dataclasses import dataclass
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

from PyQt6.QtWidgets import QApplication
import pytest


# Optimized stub implementation with function-scoped fixture
@pytest.fixture(autouse=True)
def stub_resource_manager(monkeypatch) -> Any:  # noqa: ANN001
    """Provide a minimal goesvfi.utils.resource_manager module for testing.

    Yields:
        None: This fixture provides a module stub for the test session.
    """
    module = ModuleType("goesvfi.pipeline.resource_manager")

    @dataclass
    class ResourceLimits:
        max_workers: int = 2
        max_memory_mb: int = 4096
        max_cpu_percent: float = 80.0
        chunk_size_mb: int = 100
        warn_memory_percent: float = 75.0
        critical_memory_percent: float = 90.0

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

    def get_resource_manager() -> ResourceMonitor:
        return ResourceMonitor(ResourceLimits())

    def managed_executor(*args: Any, **kwargs: Any) -> Any:
        return None

    module.ResourceLimits = ResourceLimits  # type: ignore[attr-defined]
    module.ResourceMonitor = ResourceMonitor  # type: ignore[attr-defined]
    module.get_system_resource_info = get_system_resource_info  # type: ignore[attr-defined]
    module.get_resource_manager = get_resource_manager  # type: ignore[attr-defined]
    module.managed_executor = managed_executor  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "goesvfi.pipeline.resource_manager", module)

    yield

    monkeypatch.delitem(sys.modules, "goesvfi.pipeline.resource_manager", raising=False)


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
                "memory": {"enabled": True, "value": 1024},
                "cpu": {"enabled": False, "value": 50},
            },
            {
                "memory": {"enabled": True, "value": 2048},
                "cpu": {"enabled": True, "value": 90},
            },
            {
                "memory": {"enabled": False, "value": 512},
                "cpu": {"enabled": True, "value": 60},
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

        # Configure CPU limit
        cpu_config = limit_config["cpu"]
        resource_tab.cpu_limit_checkbox.setChecked(cpu_config["enabled"])
        if cpu_config["enabled"]:
            resource_tab.cpu_limit_spinbox.setValue(cpu_config["value"])
        QApplication.processEvents()

        # Verify last emitted signal has correct values
        assert len(emitted_limits) > 0
        last_limits = emitted_limits[-1]

        # Check memory limit (defaults to 4096 when disabled)
        expected_memory = memory_config["value"] if memory_config["enabled"] else 4096
        assert last_limits.max_memory_mb == expected_memory

        # Check CPU limit (defaults to 80.0 when disabled)
        expected_cpu = float(cpu_config["value"]) if cpu_config["enabled"] else 80.0
        assert last_limits.max_cpu_percent == expected_cpu

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
        assert current_limits.max_cpu_percent == 80.0  # default

        # Step 2: Enable CPU limit
        resource_tab.cpu_limit_checkbox.setChecked(True)
        resource_tab.cpu_limit_spinbox.setValue(60)
        QApplication.processEvents()

        current_limits = emitted_limits[-1]
        assert current_limits.max_memory_mb == 1024
        assert current_limits.max_cpu_percent == 60.0

        # Step 3: Disable memory limit (CPU remains enabled)
        resource_tab.memory_limit_checkbox.setChecked(False)
        QApplication.processEvents()

        current_limits = emitted_limits[-1]
        assert current_limits.max_memory_mb == 4096  # default
        assert current_limits.max_cpu_percent == 60.0

        # Step 4: Disable CPU limit (all limits back to defaults)
        resource_tab.cpu_limit_checkbox.setChecked(False)
        QApplication.processEvents()

        current_limits = emitted_limits[-1]
        assert current_limits.max_memory_mb == 4096  # default
        assert current_limits.max_cpu_percent == 80.0  # default
