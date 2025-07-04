"""Fast, optimized tests for resource management - Optimized v2."""

from dataclasses import dataclass
import threading
from unittest.mock import MagicMock, patch

import pytest

from goesvfi.pipeline.exceptions import ResourceError
from goesvfi.pipeline.resource_manager import ResourceLimits, ResourceManager


@dataclass
class MockMemoryStats:
    """Mock memory statistics for testing."""

    percent_used: float
    available_mb: int = 2048
    total_mb: int = 4096
    used_mb: int = 2048


# Shared test data and fixtures
@pytest.fixture(scope="session")
def memory_stats_scenarios():
    """Pre-defined memory statistics scenarios."""
    return {
        "normal": MockMemoryStats(percent_used=50.0, available_mb=2048),
        "warning": MockMemoryStats(percent_used=78.0, available_mb=1000),
        "critical": MockMemoryStats(percent_used=95.0, available_mb=200),
        "insufficient": MockMemoryStats(percent_used=50.0, available_mb=500),
    }


@pytest.fixture(scope="session")
def resource_limits_scenarios():
    """Pre-defined resource limits scenarios."""
    return {
        "default": ResourceLimits(),
        "custom": ResourceLimits(
            max_workers=4,
            max_memory_mb=2048,
            max_cpu_percent=75.0,
            chunk_size_mb=50,
            warn_memory_percent=70.0,
            critical_memory_percent=85.0,
        ),
        "strict": ResourceLimits(max_workers=1),
        "generous": ResourceLimits(max_workers=8, max_memory_mb=8192),
    }


@pytest.fixture()
def mock_memory_monitor(memory_stats_scenarios):
    """Mock memory monitor with configurable scenarios."""
    monitor = MagicMock()
    monitor.get_memory_stats.return_value = memory_stats_scenarios["normal"]
    monitor.start_monitoring = MagicMock()
    monitor.add_callback = MagicMock()
    return monitor


class TestResourceManager:
    """Test resource management with fast, mocked operations."""

    @pytest.mark.parametrize("limits_key", ["default", "custom"])
    def test_initialization(self, mock_memory_monitor, resource_limits_scenarios, limits_key: str) -> None:
        """Test initialization with different resource limits."""
        limits = resource_limits_scenarios[limits_key]

        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor:
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager(limits)
            manager.initialize()  # Trigger initialization

            assert manager.limits == limits
            if limits_key == "custom":
                assert manager.limits.max_workers == 4
                assert manager.limits.max_memory_mb == 2048
            else:
                assert manager.limits.max_workers == 2
                assert manager.limits.max_memory_mb == 4096

            mock_memory_monitor.start_monitoring.assert_called_once()
            mock_memory_monitor.add_callback.assert_called_once()

            manager.cleanup()

    @pytest.mark.parametrize(
        "memory_scenario,should_warn,should_critical",
        [
            ("normal", False, False),
            ("warning", True, False),
            ("critical", False, True),
        ],
    )
    def test_memory_callback_levels(
        self,
        mock_memory_monitor,
        memory_stats_scenarios,
        memory_scenario: str,
        should_warn: bool,
        should_critical: bool,
    ) -> None:
        """Test memory callback at different warning levels."""
        stats = memory_stats_scenarios[memory_scenario]

        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor:
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager()
            manager.initialize()  # Trigger initialization

            # Use the manager's internal logger instead of the module logger
            with (
                patch.object(manager, "log_warning") as mock_log_warning,
                patch.object(manager, "log_error") as mock_log_error,
            ):
                manager._memory_callback(stats)

                if should_warn:
                    mock_log_warning.assert_called_once()
                else:
                    mock_log_warning.assert_not_called()

                if should_critical:
                    mock_log_error.assert_called_once()
                else:
                    mock_log_error.assert_not_called()

            manager.cleanup()

    @pytest.mark.parametrize(
        "memory_scenario,required_memory,should_raise",
        [
            ("normal", 1000, False),  # Sufficient memory
            ("insufficient", 1000, True),  # Insufficient memory
            ("critical", None, True),  # Critical memory usage
        ],
    )
    def test_check_resources(
        self,
        mock_memory_monitor,
        memory_stats_scenarios,
        memory_scenario: str,
        required_memory: int,
        should_raise: bool,
    ) -> None:
        """Test resource checking with different memory conditions."""
        mock_memory_monitor.get_memory_stats.return_value = memory_stats_scenarios[memory_scenario]

        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor:
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager()
            manager.initialize()  # Trigger initialization

            if should_raise:
                with pytest.raises(ResourceError):
                    manager.check_resources(required_memory_mb=required_memory)
            else:
                # Should not raise exception
                manager.check_resources(required_memory_mb=required_memory)

            manager.cleanup()

    @pytest.mark.parametrize(
        "cpu_count,memory_available,expected_constraint",
        [
            (8, 8000, "max_workers"),  # Limited by configuration
            (8, 1000, "memory"),  # Limited by memory
            (2, 8000, "cpu"),  # Limited by CPU
            (None, 8000, "fallback"),  # CPU count unavailable
        ],
    )
    @patch("os.cpu_count")
    def test_get_optimal_workers_constraints(
        self,
        mock_cpu_count,
        mock_memory_monitor,
        memory_stats_scenarios,
        cpu_count: int,
        memory_available: int,
        expected_constraint: str,
    ) -> None:
        """Test optimal worker calculation under different constraints."""
        mock_cpu_count.return_value = cpu_count

        # Mock memory with specified available memory
        stats = memory_stats_scenarios["normal"]
        stats.available_mb = memory_available
        mock_memory_monitor.get_memory_stats.return_value = stats

        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor:
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager()
            manager.initialize()  # Trigger initialization
            optimal = manager.get_optimal_workers()

            # Verify constraint is applied
            if expected_constraint == "max_workers":
                assert optimal == manager.limits.max_workers  # Should be 2 (default)
            elif expected_constraint == "memory":
                # Memory-based calculation: available_mb / 500 (estimated per worker)
                expected = min(memory_available // 500, manager.limits.max_workers)
                assert optimal == max(1, expected)
            elif expected_constraint == "cpu":
                # CPU-based calculation: cpu_count * 0.75
                expected = min(int(cpu_count * 0.75), manager.limits.max_workers)
                assert optimal == max(1, expected)
            elif expected_constraint == "fallback":
                assert optimal >= 1  # Should have sensible fallback

            manager.cleanup()

    @pytest.mark.parametrize("limits_scenario", ["default", "strict", "generous"])
    def test_get_optimal_workers_with_limits(
        self, mock_memory_monitor, resource_limits_scenarios, limits_scenario: str
    ) -> None:
        """Test optimal worker calculation with different resource limits."""
        limits = resource_limits_scenarios[limits_scenario]
        mock_memory_monitor.get_memory_stats.return_value = MockMemoryStats(percent_used=30.0, available_mb=8000)

        with (
            patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor,
            patch("os.cpu_count", return_value=8),
        ):
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager(limits)
            manager.initialize()  # Trigger initialization
            optimal = manager.get_optimal_workers()

            # Should never exceed configured max_workers
            assert optimal <= limits.max_workers
            assert optimal >= 1

            manager.cleanup()

    @pytest.mark.parametrize(
        "max_workers,uses_optimal",
        [
            (None, True),  # Should use optimal calculation
            (3, False),  # Should use specified value
        ],
    )
    def test_process_executor_worker_configuration(
        self, mock_memory_monitor, max_workers: int, uses_optimal: bool
    ) -> None:
        """Test process executor worker configuration logic."""
        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor:
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager()
            manager.initialize()  # Trigger initialization

            with (
                patch("goesvfi.pipeline.resource_manager.ProcessPoolExecutor") as mock_executor_class,
                patch.object(manager, "get_optimal_workers", return_value=2) as mock_optimal,
            ):
                mock_executor = MagicMock()
                mock_executor_class.return_value = mock_executor

                with manager.process_executor(max_workers=max_workers):
                    pass

                if uses_optimal:
                    mock_optimal.assert_called_once()
                    mock_executor_class.assert_called_once_with(max_workers=2)
                else:
                    # Should use min of specified and max_workers limit
                    expected = min(max_workers, manager.limits.max_workers)
                    mock_executor_class.assert_called_once_with(max_workers=expected)

            manager.cleanup()

    def test_process_executor_resource_checking(self, mock_memory_monitor, memory_stats_scenarios) -> None:
        """Test process executor performs resource checking before creation."""
        # Mock critical memory situation
        mock_memory_monitor.get_memory_stats.return_value = memory_stats_scenarios["critical"]

        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor:
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager()
            manager.initialize()  # Trigger initialization

            with pytest.raises(ResourceError, match="Memory usage too high"), manager.process_executor():
                pass

            manager.cleanup()

    def test_thread_safety_verification(self, mock_memory_monitor) -> None:
        """Test thread safety of executor management."""
        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor:
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager()
            manager.initialize()  # Trigger initialization

            # Verify internal thread-safety components
            assert isinstance(manager._lock, type(threading.Lock()))
            assert isinstance(manager._executors, dict)
            assert len(manager._executors) == 0

            manager.cleanup()

    @pytest.mark.parametrize("scenario", ["default", "custom"])
    def test_resource_limits_dataclass(self, resource_limits_scenarios, scenario: str) -> None:
        """Test ResourceLimits dataclass with different configurations."""
        limits = resource_limits_scenarios[scenario]

        if scenario == "default":
            assert limits.max_workers == 2
            assert limits.max_memory_mb == 4096
            assert limits.max_cpu_percent == 80.0
            assert limits.chunk_size_mb == 100
            assert limits.warn_memory_percent == 75.0
            assert limits.critical_memory_percent == 90.0
        elif scenario == "custom":
            assert limits.max_workers == 4
            assert limits.max_memory_mb == 2048
            assert limits.max_cpu_percent == 75.0
            assert limits.chunk_size_mb == 50
            assert limits.warn_memory_percent == 70.0
            assert limits.critical_memory_percent == 85.0

        # Verify critical > warning for all scenarios
        assert limits.critical_memory_percent > limits.warn_memory_percent

    def test_cleanup_on_destruction(self, mock_memory_monitor) -> None:
        """Test that resources are cleaned up properly."""
        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor:
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager()
            manager.initialize()  # Trigger initialization

            # Add some mock executors
            mock_executor1 = MagicMock()
            mock_executor2 = MagicMock()
            manager._executors["test1"] = mock_executor1
            manager._executors["test2"] = mock_executor2

            # Verify cleanup functionality exists
            assert hasattr(manager, "_executors")
            assert len(manager._executors) == 2

            # Test shutdown_all method
            manager.shutdown_all()

            # Verify monitoring is stopped
            mock_memory_monitor.stop_monitoring.assert_called_once()

    @pytest.mark.parametrize("operation_count", [1, 3, 5])
    def test_multiple_operations_workflow(self, mock_memory_monitor, operation_count: int) -> None:
        """Test workflow with multiple operations to verify stability."""
        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor:
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager()
            manager.initialize()  # Trigger initialization

            # Perform multiple check_resources operations
            for _i in range(operation_count):
                manager.check_resources(required_memory_mb=100)

            # Should complete without issues
            assert mock_memory_monitor.get_memory_stats.call_count == operation_count

            manager.cleanup()
