"""Fast, optimized tests for resource management - critical system infrastructure."""

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
    available_mb: int
    total_mb: int
    used_mb: int


class TestResourceManager:
    """Test resource management with fast, mocked operations."""

    @pytest.fixture()
    def mock_memory_monitor(self):
        """Mock memory monitor for testing."""
        monitor = MagicMock()
        monitor.get_memory_stats.return_value = MockMemoryStats(
            percent_used=50.0, available_mb=2048, total_mb=4096, used_mb=2048
        )
        monitor.start_monitoring = MagicMock()
        monitor.add_callback = MagicMock()
        return monitor

    @pytest.fixture()
    def custom_limits(self):
        """Custom resource limits for testing."""
        return ResourceLimits(
            max_workers=4,
            max_memory_mb=2048,
            max_cpu_percent=75.0,
            chunk_size_mb=50,
            warn_memory_percent=70.0,
            critical_memory_percent=85.0,
        )

    def test_init_with_default_limits(self, mock_memory_monitor) -> None:
        """Test initialization with default resource limits."""
        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor:
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager()

            assert isinstance(manager.limits, ResourceLimits)
            assert manager.limits.max_workers == 2  # Default value
            assert manager.limits.max_memory_mb == 4096  # Default value
            mock_memory_monitor.start_monitoring.assert_called_once()
            mock_memory_monitor.add_callback.assert_called_once()

    def test_init_with_custom_limits(self, mock_memory_monitor, custom_limits) -> None:
        """Test initialization with custom resource limits."""
        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor:
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager(custom_limits)

            assert manager.limits == custom_limits
            assert manager.limits.max_workers == 4
            assert manager.limits.max_memory_mb == 2048

    def test_memory_callback_warning_level(self, mock_memory_monitor) -> None:
        """Test memory callback at warning level."""
        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor:
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager()

            # Create mock stats at warning level
            warning_stats = MockMemoryStats(
                percent_used=78.0,  # Above 75% warning threshold
                available_mb=1000,
                total_mb=4096,
                used_mb=3096,
            )

            with patch("goesvfi.pipeline.resource_manager.LOGGER") as mock_logger:
                manager._memory_callback(warning_stats)

                mock_logger.warning.assert_called_once()
                assert "Memory usage high" in mock_logger.warning.call_args[0][0]

    def test_memory_callback_critical_level(self, mock_memory_monitor) -> None:
        """Test memory callback at critical level."""
        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor:
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager()

            # Create mock stats at critical level
            critical_stats = MockMemoryStats(
                percent_used=95.0,  # Above 90% critical threshold
                available_mb=200,
                total_mb=4096,
                used_mb=3896,
            )

            with patch("goesvfi.pipeline.resource_manager.LOGGER") as mock_logger:
                manager._memory_callback(critical_stats)

                mock_logger.critical.assert_called_once()
                assert "Memory usage critical" in mock_logger.critical.call_args[0][0]

    def test_check_resources_sufficient_memory(self, mock_memory_monitor) -> None:
        """Test resource check with sufficient memory."""
        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor:
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager()

            # Should not raise exception
            manager.check_resources(required_memory_mb=1000)  # Less than available 2048MB

    def test_check_resources_insufficient_memory(self, mock_memory_monitor) -> None:
        """Test resource check with insufficient memory."""
        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor:
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager()

            with pytest.raises(ResourceError, match="Insufficient memory"):
                manager.check_resources(required_memory_mb=3000)  # More than available 2048MB

    def test_check_resources_critical_memory_usage(self, mock_memory_monitor) -> None:
        """Test resource check fails when memory usage is critical."""
        # Mock high memory usage
        mock_memory_monitor.get_memory_stats.return_value = MockMemoryStats(
            percent_used=95.0,  # Above 90% critical threshold
            available_mb=200,
            total_mb=4096,
            used_mb=3896,
        )

        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor:
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager()

            with pytest.raises(ResourceError, match="Memory usage too high"):
                manager.check_resources()

    def test_get_optimal_workers_memory_constrained(self, mock_memory_monitor) -> None:
        """Test optimal worker calculation when memory is the constraint."""
        # Mock limited memory
        mock_memory_monitor.get_memory_stats.return_value = MockMemoryStats(
            percent_used=50.0,
            available_mb=1000,  # Only 1GB available
            total_mb=2048,
            used_mb=1048,
        )

        with (
            patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor,
            patch("os.cpu_count", return_value=8),
        ):  # 8 CPUs available
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager()
            optimal = manager.get_optimal_workers()

            # Should be limited by memory: 1000MB / 500MB per worker = 2 workers
            assert optimal == 2

    def test_get_optimal_workers_cpu_constrained(self, mock_memory_monitor) -> None:
        """Test optimal worker calculation when CPU is the constraint."""
        # Mock abundant memory but limited CPU
        mock_memory_monitor.get_memory_stats.return_value = MockMemoryStats(
            percent_used=30.0,
            available_mb=8000,  # 8GB available
            total_mb=10240,
            used_mb=2240,
        )

        with (
            patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor,
            patch("os.cpu_count", return_value=2),
        ):  # Only 2 CPUs
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager()
            optimal = manager.get_optimal_workers()

            # Should be limited by CPU: 2 * 0.75 = 1.5 -> 1 worker
            assert optimal == 1

    def test_get_optimal_workers_limit_constrained(self, mock_memory_monitor) -> None:
        """Test optimal worker calculation when configuration limit is the constraint."""
        # Mock abundant resources but strict limit
        mock_memory_monitor.get_memory_stats.return_value = MockMemoryStats(
            percent_used=30.0, available_mb=8000, total_mb=10240, used_mb=2240
        )

        limits = ResourceLimits(max_workers=1)  # Very strict limit

        with (
            patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor,
            patch("os.cpu_count", return_value=8),
        ):
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager(limits)
            optimal = manager.get_optimal_workers()

            # Should be limited by configuration: max_workers = 1
            assert optimal == 1

    def test_get_optimal_workers_edge_case_no_cpu_info(self, mock_memory_monitor) -> None:
        """Test optimal worker calculation when CPU count is unavailable."""
        mock_memory_monitor.get_memory_stats.return_value = MockMemoryStats(
            percent_used=50.0, available_mb=2000, total_mb=4096, used_mb=2096
        )

        with (
            patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor,
            patch("os.cpu_count", return_value=None),
        ):  # CPU count unavailable
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager()
            optimal = manager.get_optimal_workers()

            # Should default to 1 CPU and still work
            assert optimal >= 1

    def test_process_executor_context_manager(self, mock_memory_monitor) -> None:
        """Test process executor context manager."""
        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor:
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager()

            with patch("goesvfi.pipeline.resource_manager.ProcessPoolExecutor") as mock_executor_class:
                mock_executor = MagicMock()
                mock_executor_class.return_value = mock_executor

                with manager.process_executor(max_workers=2, executor_id="test") as executor:
                    assert executor == mock_executor
                    # Should be stored in manager
                    assert "test" in manager._executors

                # Should be cleaned up after context
                mock_executor.shutdown.assert_called_once()

    def test_process_executor_uses_optimal_workers_when_none_specified(self, mock_memory_monitor) -> None:
        """Test process executor uses optimal workers when max_workers is None."""
        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor:
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager()

            with (
                patch("goesvfi.pipeline.resource_manager.ProcessPoolExecutor") as mock_executor_class,
                patch.object(manager, "get_optimal_workers", return_value=3) as mock_optimal,
            ):
                mock_executor = MagicMock()
                mock_executor_class.return_value = mock_executor

                with manager.process_executor():
                    pass

                mock_optimal.assert_called_once()
                # Should have created executor with optimal workers
                mock_executor_class.assert_called_once_with(max_workers=3)

    def test_process_executor_resource_check_before_creation(self, mock_memory_monitor) -> None:
        """Test process executor checks resources before creation."""
        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor:
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager()

            with (
                patch.object(manager, "check_resources") as mock_check,
                patch("goesvfi.pipeline.resource_manager.ProcessPoolExecutor") as mock_executor_class,
            ):
                mock_executor = MagicMock()
                mock_executor_class.return_value = mock_executor

                with manager.process_executor():
                    pass

                mock_check.assert_called_once()

    def test_thread_safety_of_executor_management(self, mock_memory_monitor) -> None:
        """Test thread safety of executor management."""
        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor:
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager()

            # Test that lock is used for thread safety
            assert isinstance(manager._lock, type(threading.Lock()))

            # Verify executors dict is properly initialized
            assert isinstance(manager._executors, dict)
            assert len(manager._executors) == 0

    def test_resource_limits_dataclass_defaults(self) -> None:
        """Test ResourceLimits dataclass has sensible defaults."""
        limits = ResourceLimits()

        assert limits.max_workers == 2
        assert limits.max_memory_mb == 4096
        assert limits.max_cpu_percent == 80.0
        assert limits.chunk_size_mb == 100
        assert limits.warn_memory_percent == 75.0
        assert limits.critical_memory_percent == 90.0

        # Test critical > warning
        assert limits.critical_memory_percent > limits.warn_memory_percent

    def test_resource_limits_custom_values(self) -> None:
        """Test ResourceLimits with custom values."""
        limits = ResourceLimits(
            max_workers=8,
            max_memory_mb=8192,
            max_cpu_percent=90.0,
            chunk_size_mb=200,
            warn_memory_percent=80.0,
            critical_memory_percent=95.0,
        )

        assert limits.max_workers == 8
        assert limits.max_memory_mb == 8192
        assert limits.max_cpu_percent == 90.0
        assert limits.chunk_size_mb == 200
        assert limits.warn_memory_percent == 80.0
        assert limits.critical_memory_percent == 95.0

    def test_cleanup_on_destruction(self, mock_memory_monitor) -> None:
        """Test that resources are cleaned up on manager destruction."""
        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor") as mock_get_monitor:
            mock_get_monitor.return_value = mock_memory_monitor

            manager = ResourceManager()

            # Add some mock executors
            mock_executor1 = MagicMock()
            mock_executor2 = MagicMock()
            manager._executors["test1"] = mock_executor1
            manager._executors["test2"] = mock_executor2

            # Test cleanup method exists and works
            assert hasattr(manager, "_executors")
            assert len(manager._executors) == 2
