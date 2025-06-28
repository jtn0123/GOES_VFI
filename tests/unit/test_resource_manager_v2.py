"""Tests for the refactored ResourceManager using BaseManager."""

import unittest
from unittest.mock import MagicMock, patch

import pytest

from goesvfi.pipeline.exceptions import ResourceError
from goesvfi.pipeline.resource_manager import ResourceLimits, ResourceManager, get_resource_manager


class TestResourceManagerV2(unittest.TestCase):
    """Test ResourceManager using BaseManager functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Reset global instance
        import goesvfi.pipeline.resource_manager
        goesvfi.pipeline.resource_manager._resource_manager = None

        # Create mock memory monitor
        self.mock_memory_monitor = MagicMock()
        self.mock_memory_monitor.get_memory_stats.return_value = MagicMock(
            percent_used=50.0,
            available_mb=2048,
            used_mb=2048,
            total_mb=4096
        )

    def tearDown(self) -> None:
        """Clean up after tests."""
        # Reset global instance
        import goesvfi.pipeline.resource_manager
        goesvfi.pipeline.resource_manager._resource_manager = None

    @patch("goesvfi.pipeline.resource_manager.get_memory_monitor")
    def test_inheritance_from_base_manager(self, mock_get_monitor) -> None:
        """Test that ResourceManager properly inherits from BaseManager."""
        mock_get_monitor.return_value = self.mock_memory_monitor

        manager = ResourceManager()

        # Check base class attributes
        assert manager.name == "ResourceManager"
        assert manager._logger is not None
        assert not manager._is_initialized
        assert len(manager._resources) == 1  # Memory monitor tracked

        # Check ConfigurableManager functionality
        assert manager._config is not None
        assert manager.get_config("max_workers") == 2
        assert manager.get_config("chunk_size_mb") == 100

    @patch("goesvfi.pipeline.resource_manager.get_memory_monitor")
    def test_configuration_management(self, mock_get_monitor) -> None:
        """Test configuration management through base class."""
        mock_get_monitor.return_value = self.mock_memory_monitor

        limits = ResourceLimits(
            max_workers=4,
            max_memory_mb=8192,
            chunk_size_mb=200,
            warn_memory_percent=80.0,
            critical_memory_percent=95.0
        )

        manager = ResourceManager(limits)

        # Check initial config from limits
        assert manager.get_config("max_workers") == 4
        assert manager.get_config("max_memory_mb") == 8192
        assert manager.get_config("chunk_size_mb") == 200

        # Update config dynamically
        manager.set_config("max_workers", 8)
        assert manager.get_config("max_workers") == 8

    @patch("goesvfi.pipeline.resource_manager.get_memory_monitor")
    def test_initialization_lifecycle(self, mock_get_monitor) -> None:
        """Test proper initialization through base class."""
        mock_get_monitor.return_value = self.mock_memory_monitor

        manager = ResourceManager()

        # Not initialized yet
        assert not manager._is_initialized

        # Initialize
        manager.initialize()
        assert manager._is_initialized
        self.mock_memory_monitor.start_monitoring.assert_called_once_with(interval=2.0)
        self.mock_memory_monitor.add_callback.assert_called_once()

        # Second initialization should be a no-op
        manager.initialize()
        assert self.mock_memory_monitor.start_monitoring.call_count == 1

    @patch("goesvfi.pipeline.resource_manager.get_memory_monitor")
    def test_cleanup_lifecycle(self, mock_get_monitor) -> None:
        """Test proper cleanup through base class."""
        mock_get_monitor.return_value = self.mock_memory_monitor

        manager = ResourceManager()
        manager.initialize()

        # Add some executors to track
        with patch("concurrent.futures.ProcessPoolExecutor") as mock_executor_class:
            mock_executor = MagicMock()
            mock_executor_class.return_value = mock_executor

            with manager.process_executor(max_workers=2, executor_id="test"):
                assert len(manager._executors) == 1

        # Cleanup
        manager.cleanup()
        assert not manager._is_initialized
        self.mock_memory_monitor.stop_monitoring.assert_called_once()

    @patch("goesvfi.pipeline.resource_manager.get_memory_monitor")
    def test_memory_callback_with_config(self, mock_get_monitor) -> None:
        """Test memory callback uses configuration values."""
        mock_get_monitor.return_value = self.mock_memory_monitor

        manager = ResourceManager()
        manager.initialize()

        # Update config
        manager.set_config("warn_memory_percent", 60.0)
        manager.set_config("critical_memory_percent", 80.0)

        # Test warning threshold
        with patch.object(manager, "log_warning") as mock_log_warning:
            stats = MagicMock(percent_used=65.0)
            manager._memory_callback(stats)
            mock_log_warning.assert_called_once()

        # Test critical threshold
        with patch.object(manager, "log_error") as mock_log_error:
            with patch.object(manager, "error_occurred") as mock_signal:
                stats = MagicMock(percent_used=85.0)
                manager._memory_callback(stats)
                mock_log_error.assert_called_once()
                mock_signal.emit.assert_called_once()

    @patch("goesvfi.pipeline.resource_manager.get_memory_monitor")
    def test_error_handling_integration(self, mock_get_monitor) -> None:
        """Test error handling through base class."""
        mock_get_monitor.return_value = self.mock_memory_monitor

        manager = ResourceManager()
        manager.initialize()

        # Test 1: Insufficient memory
        self.mock_memory_monitor.get_memory_stats.return_value = MagicMock(
            percent_used=50.0,
            available_mb=200,
            used_mb=2048,
            total_mb=4096
        )

        with pytest.raises(ResourceError) as cm:
            manager.check_resources(required_memory_mb=500)

        assert "Insufficient memory" in str(cm.value)

        # Test 2: High memory usage percentage
        self.mock_memory_monitor.get_memory_stats.return_value = MagicMock(
            percent_used=95.0,
            available_mb=2000,  # Enough available memory
            used_mb=3896,
            total_mb=4096
        )

        with pytest.raises(ResourceError) as cm:
            manager.check_resources(required_memory_mb=100)

        assert "Memory usage too high" in str(cm.value)
        assert "95.0%" in str(cm.value)

        # Test 3: Error handling through memory callback
        with patch.object(manager, "error_occurred") as mock_signal:
            stats = MagicMock(percent_used=95.0)
            manager._memory_callback(stats)
            mock_signal.emit.assert_called_once()

    @patch("goesvfi.pipeline.resource_manager.get_memory_monitor")
    def test_logging_methods(self, mock_get_monitor) -> None:
        """Test logging through base class methods."""
        mock_get_monitor.return_value = self.mock_memory_monitor

        manager = ResourceManager()

        with patch.object(manager._logger, "info") as mock_info:
            manager.log_info("Test message with %s", "args")
            mock_info.assert_called_once_with("[ResourceManager] Test message with %s", "args")

        with patch.object(manager._logger, "debug") as mock_debug:
            manager.log_debug("Debug message")
            mock_debug.assert_called_once_with("[ResourceManager] Debug message")

    @patch("goesvfi.pipeline.resource_manager.get_memory_monitor")
    @patch("os.cpu_count")
    def test_optimal_workers_calculation(self, mock_cpu_count, mock_get_monitor) -> None:
        """Test optimal workers calculation with config."""
        mock_get_monitor.return_value = self.mock_memory_monitor
        mock_cpu_count.return_value = 8

        manager = ResourceManager()
        manager.initialize()

        # Default config
        optimal = manager.get_optimal_workers()
        assert optimal == 2  # Limited by max_workers config

        # Update config
        manager.set_config("max_workers", 10)
        optimal = manager.get_optimal_workers()
        assert optimal == 4  # Limited by available memory (2048MB / 500MB per worker)

    @patch("goesvfi.pipeline.resource_manager.get_memory_monitor")
    def test_chunk_size_calculation(self, mock_get_monitor) -> None:
        """Test chunk size calculation with config."""
        mock_get_monitor.return_value = self.mock_memory_monitor

        manager = ResourceManager()
        manager.initialize()

        # Default config
        chunk_size = manager.get_chunk_size(1000, min_chunks=4)
        assert chunk_size == 100  # Limited by config

        # Update config
        manager.set_config("chunk_size_mb", 50)
        chunk_size = manager.get_chunk_size(1000, min_chunks=4)
        assert chunk_size == 50  # Limited by new config

    @patch("goesvfi.pipeline.resource_manager.get_memory_monitor")
    def test_global_instance_singleton(self, mock_get_monitor) -> None:
        """Test global instance management."""
        mock_get_monitor.return_value = self.mock_memory_monitor

        # First call creates instance
        manager1 = get_resource_manager()
        assert manager1 is not None

        # Second call returns same instance
        manager2 = get_resource_manager()
        assert manager1 is manager2

        # Custom limits only used on first call
        custom_limits = ResourceLimits(max_workers=10)
        manager3 = get_resource_manager(custom_limits)
        assert manager1 is manager3
        assert manager3.get_config("max_workers") == 2  # Original value


if __name__ == "__main__":
    unittest.main()
