"""Tests for resource manager functionality."""

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import threading
import time
from unittest.mock import Mock, patch

import pytest

from goesvfi.pipeline.exceptions import ResourceError
from goesvfi.pipeline.resource_manager import (
    ResourceLimits,
    ResourceManager,
    estimate_processing_memory,
    get_resource_manager,
    managed_executor,
)
from goesvfi.utils.memory_manager import MemoryStats


class TestResourceLimits:
    """Test ResourceLimits dataclass."""

    def test_default_values(self) -> None:
        """Test default resource limit values."""
        limits = ResourceLimits()
        assert limits.max_workers == 2
        assert limits.max_memory_mb == 4096
        assert limits.max_cpu_percent == 80.0
        assert limits.chunk_size_mb == 100
        assert limits.warn_memory_percent == 75.0
        assert limits.critical_memory_percent == 90.0

    def test_custom_values(self) -> None:
        """Test custom resource limit values."""
        limits = ResourceLimits(
            max_workers=4,
            max_memory_mb=8192,
            max_cpu_percent=90.0,
            chunk_size_mb=200,
            warn_memory_percent=80.0,
            critical_memory_percent=95.0,
        )
        assert limits.max_workers == 4
        assert limits.max_memory_mb == 8192
        assert limits.max_cpu_percent == 90.0
        assert limits.chunk_size_mb == 200
        assert limits.warn_memory_percent == 80.0
        assert limits.critical_memory_percent == 95.0


class TestResourceManager:
    """Test ResourceManager functionality."""

    @pytest.fixture()
    def mock_memory_monitor(self):
        """Mock memory monitor for testing."""
        mock_monitor = Mock()
        mock_monitor.start_monitoring = Mock()
        mock_monitor.add_callback = Mock()
        mock_monitor.stop_monitoring = Mock()
        mock_monitor.get_memory_stats = Mock(
            return_value=MemoryStats(
                total_mb=8192,
                available_mb=4096,
                used_mb=4096,
                percent_used=50.0,
                process_mb=512,
                process_percent=6.25,
            )
        )
        return mock_monitor

    @pytest.fixture()
    def resource_manager(self, mock_memory_monitor):
        """Create ResourceManager with mocked memory monitor."""
        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor", return_value=mock_memory_monitor):
            manager = ResourceManager()
            yield manager
            manager.shutdown_all()

    def test_initialization(self, mock_memory_monitor) -> None:
        """Test ResourceManager initialization."""
        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor", return_value=mock_memory_monitor):
            manager = ResourceManager()

            # Check default limits
            assert isinstance(manager.limits, ResourceLimits)
            assert manager.limits.max_workers == 2

            # Check memory monitor setup
            mock_memory_monitor.start_monitoring.assert_called_once_with(interval=2.0)
            mock_memory_monitor.add_callback.assert_called_once()

            # Check internal state
            assert hasattr(manager, "_executors")
            assert hasattr(manager, "_lock")
            assert isinstance(manager._lock, type(threading.Lock()))

            manager.shutdown_all()

    def test_initialization_with_custom_limits(self, mock_memory_monitor) -> None:
        """Test ResourceManager initialization with custom limits."""
        custom_limits = ResourceLimits(max_workers=4, max_memory_mb=8192)

        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor", return_value=mock_memory_monitor):
            manager = ResourceManager(custom_limits)

            assert manager.limits == custom_limits
            assert manager.limits.max_workers == 4
            assert manager.limits.max_memory_mb == 8192

            manager.shutdown_all()

    def test_memory_callback_warning(self, resource_manager) -> None:
        """Test memory callback logging warnings."""
        stats = MemoryStats(percent_used=80.0)

        with patch("goesvfi.pipeline.resource_manager.LOGGER") as mock_logger:
            resource_manager._memory_callback(stats)
            mock_logger.warning.assert_called_once()

    def test_memory_callback_critical(self, resource_manager) -> None:
        """Test memory callback logging critical alerts."""
        stats = MemoryStats(percent_used=95.0)

        with patch("goesvfi.pipeline.resource_manager.LOGGER") as mock_logger:
            resource_manager._memory_callback(stats)
            mock_logger.critical.assert_called_once()

    def test_memory_callback_normal(self, resource_manager) -> None:
        """Test memory callback with normal usage."""
        stats = MemoryStats(percent_used=50.0)

        with patch("goesvfi.pipeline.resource_manager.LOGGER") as mock_logger:
            resource_manager._memory_callback(stats)
            mock_logger.warning.assert_not_called()
            mock_logger.critical.assert_not_called()

    def test_check_resources_sufficient(self, resource_manager) -> None:
        """Test resource check with sufficient resources."""
        # Should not raise with default mock stats (4096MB available)
        resource_manager.check_resources(required_memory_mb=1000)

    def test_check_resources_insufficient_memory(self, resource_manager) -> None:
        """Test resource check with insufficient memory."""
        # Mock low available memory
        low_memory_stats = MemoryStats(
            total_mb=8192,
            available_mb=500,
            used_mb=7692,
            percent_used=94.0,
        )
        resource_manager.memory_monitor.get_memory_stats.return_value = low_memory_stats

        with pytest.raises(ResourceError) as exc_info:
            resource_manager.check_resources(required_memory_mb=1000)

        assert "Insufficient memory" in str(exc_info.value)
        assert exc_info.value.resource_type == "memory"

    def test_check_resources_critical_usage(self, resource_manager) -> None:
        """Test resource check with critical memory usage."""
        critical_stats = MemoryStats(
            total_mb=8192,
            available_mb=2000,
            used_mb=6192,
            percent_used=95.0,
        )
        resource_manager.memory_monitor.get_memory_stats.return_value = critical_stats

        with pytest.raises(ResourceError) as exc_info:
            resource_manager.check_resources()

        assert "Memory usage too high" in str(exc_info.value)
        assert exc_info.value.resource_type == "memory"

    @patch("os.cpu_count")
    def test_get_optimal_workers(self, mock_cpu_count, resource_manager) -> None:
        """Test optimal worker calculation."""
        mock_cpu_count.return_value = 8

        # Mock good memory stats
        good_stats = MemoryStats(
            total_mb=8192,
            available_mb=4000,
            used_mb=4192,
            percent_used=51.0,
        )
        resource_manager.memory_monitor.get_memory_stats.return_value = good_stats

        optimal = resource_manager.get_optimal_workers()

        # Should be min of: max_workers(2), memory_based(8), cpu_based(6)
        assert optimal == 2

    @patch("os.cpu_count")
    def test_get_optimal_workers_memory_limited(self, mock_cpu_count, resource_manager) -> None:
        """Test optimal worker calculation when memory is limiting factor."""
        mock_cpu_count.return_value = 8

        # Mock low memory stats
        low_memory_stats = MemoryStats(
            total_mb=2048,
            available_mb=1000,
            used_mb=1048,
            percent_used=51.0,
        )
        resource_manager.memory_monitor.get_memory_stats.return_value = low_memory_stats

        optimal = resource_manager.get_optimal_workers()

        # Should be min of: max_workers(2), memory_based(2), cpu_based(6)
        assert optimal == 2

    @patch("os.cpu_count")
    def test_get_optimal_workers_cpu_none(self, mock_cpu_count, resource_manager) -> None:
        """Test optimal worker calculation when CPU count is None."""
        mock_cpu_count.return_value = None

        optimal = resource_manager.get_optimal_workers()

        # Should default to 1 when CPU count is None
        assert optimal >= 1

    def test_process_executor_context_manager(self, resource_manager) -> None:
        """Test ProcessPoolExecutor context manager."""
        with resource_manager.process_executor(max_workers=1, executor_id="test") as executor:
            assert isinstance(executor, ProcessPoolExecutor)
            assert "test" in resource_manager._executors

        # Should be cleaned up after context
        assert "test" not in resource_manager._executors

    def test_thread_executor_context_manager(self, resource_manager) -> None:
        """Test ThreadPoolExecutor context manager."""
        with resource_manager.thread_executor(max_workers=1, executor_id="test") as executor:
            assert isinstance(executor, ThreadPoolExecutor)
            assert "test" in resource_manager._executors

        # Should be cleaned up after context
        assert "test" not in resource_manager._executors

    def test_executor_resource_check_failure(self, resource_manager) -> None:
        """Test executor creation when resource check fails."""
        # Mock critical memory situation
        critical_stats = MemoryStats(percent_used=95.0)
        resource_manager.memory_monitor.get_memory_stats.return_value = critical_stats

        with pytest.raises(ResourceError), resource_manager.process_executor():
            pass

    def test_executor_max_workers_limit(self, resource_manager) -> None:
        """Test executor respects max_workers limit."""
        # Request more workers than limit allows
        with resource_manager.process_executor(max_workers=10, executor_id="test") as executor:
            # Should be limited to configured max_workers (2)
            assert executor._max_workers <= resource_manager.limits.max_workers

    def test_executor_optimal_workers_when_none(self, resource_manager) -> None:
        """Test executor uses optimal workers when max_workers is None."""
        with patch.object(resource_manager, "get_optimal_workers", return_value=1) as mock_optimal:
            with resource_manager.process_executor(max_workers=None, executor_id="test"):
                mock_optimal.assert_called_once()

    def test_shutdown_all(self, resource_manager) -> None:
        """Test shutting down all executors."""
        # Create some executors
        with resource_manager.process_executor(executor_id="proc1"):
            with resource_manager.thread_executor(executor_id="thread1"):
                assert len(resource_manager._executors) == 2

                # Shutdown all
                resource_manager.shutdown_all()

                # Should be empty
                assert len(resource_manager._executors) == 0

        # Memory monitor should be stopped
        resource_manager.memory_monitor.stop_monitoring.assert_called()

    def test_get_chunk_size_normal(self, resource_manager) -> None:
        """Test chunk size calculation with normal memory."""
        chunk_size = resource_manager.get_chunk_size(total_size_mb=1000, min_chunks=4)

        # Should be reasonable chunk size
        assert chunk_size >= 10  # Minimum
        assert chunk_size <= resource_manager.limits.chunk_size_mb  # Maximum

    def test_get_chunk_size_low_memory(self, resource_manager) -> None:
        """Test chunk size calculation with low memory."""
        # Mock low memory
        low_memory_stats = MemoryStats(
            total_mb=2048,
            available_mb=400,
            used_mb=1648,
            percent_used=80.0,
        )
        resource_manager.memory_monitor.get_memory_stats.return_value = low_memory_stats

        chunk_size = resource_manager.get_chunk_size(total_size_mb=1000, min_chunks=2)

        # Should be smaller due to low memory
        assert chunk_size >= 10  # Still minimum
        assert chunk_size <= 100  # Limited by available memory

    def test_get_chunk_size_minimum_enforced(self, resource_manager) -> None:
        """Test chunk size minimum is enforced."""
        chunk_size = resource_manager.get_chunk_size(total_size_mb=50, min_chunks=10)

        # Should enforce minimum of 10MB
        assert chunk_size >= 10

    def test_concurrent_executor_access(self, resource_manager) -> None:
        """Test thread safety of executor management."""
        results = []

        def create_executor(executor_id) -> None:
            try:
                with resource_manager.thread_executor(max_workers=1, executor_id=executor_id):
                    time.sleep(0.1)  # Simulate work
                    results.append(executor_id)
            except Exception as e:
                results.append(f"error_{executor_id}: {e}")

        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_executor, args=(f"thread_{i}",))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # All should have succeeded
        assert len(results) == 5
        assert all(not str(r).startswith("error_") for r in results)


class TestGlobalResourceManager:
    """Test global resource manager functions."""

    def test_get_resource_manager_singleton(self) -> None:
        """Test global resource manager is singleton."""
        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor"):
            manager1 = get_resource_manager()
            manager2 = get_resource_manager()

            assert manager1 is manager2

            # Clean up
            manager1.shutdown_all()

    def test_get_resource_manager_with_limits(self) -> None:
        """Test global resource manager with custom limits."""
        custom_limits = ResourceLimits(max_workers=4)

        with patch("goesvfi.pipeline.resource_manager.get_memory_monitor"):
            # Reset global state
            import goesvfi.pipeline.resource_manager

            goesvfi.pipeline.resource_manager._resource_manager = None

            manager = get_resource_manager(custom_limits)
            assert manager.limits.max_workers == 4

            # Subsequent calls ignore limits
            manager2 = get_resource_manager(ResourceLimits(max_workers=8))
            assert manager2.limits.max_workers == 4  # Still original

            manager.shutdown_all()


class TestManagedExecutor:
    """Test managed executor convenience function."""

    @patch("goesvfi.pipeline.resource_manager.get_resource_manager")
    def test_managed_executor_process(self, mock_get_manager) -> None:
        """Test managed executor with process type."""
        mock_manager = Mock()
        mock_executor = Mock(spec=ProcessPoolExecutor)
        mock_manager.process_executor.return_value.__enter__ = Mock(return_value=mock_executor)
        mock_manager.process_executor.return_value.__exit__ = Mock(return_value=None)
        mock_get_manager.return_value = mock_manager

        with managed_executor(executor_type="process", max_workers=2) as executor:
            assert executor is mock_executor

        mock_manager.check_resources.assert_called_once()
        mock_manager.process_executor.assert_called_once_with(2)

    @patch("goesvfi.pipeline.resource_manager.get_resource_manager")
    def test_managed_executor_thread(self, mock_get_manager) -> None:
        """Test managed executor with thread type."""
        mock_manager = Mock()
        mock_executor = Mock(spec=ThreadPoolExecutor)
        mock_manager.thread_executor.return_value.__enter__ = Mock(return_value=mock_executor)
        mock_manager.thread_executor.return_value.__exit__ = Mock(return_value=None)
        mock_get_manager.return_value = mock_manager

        with managed_executor(executor_type="thread", max_workers=2) as executor:
            assert executor is mock_executor

        mock_manager.check_resources.assert_called_once()
        mock_manager.thread_executor.assert_called_once_with(2)

    @patch("goesvfi.pipeline.resource_manager.get_resource_manager")
    def test_managed_executor_no_resource_check(self, mock_get_manager) -> None:
        """Test managed executor with resources check disabled."""
        mock_manager = Mock()
        mock_executor = Mock(spec=ProcessPoolExecutor)
        mock_manager.process_executor.return_value.__enter__ = Mock(return_value=mock_executor)
        mock_manager.process_executor.return_value.__exit__ = Mock(return_value=None)
        mock_get_manager.return_value = mock_manager

        with managed_executor(executor_type="process", check_resources=False) as executor:
            assert executor is mock_executor

        mock_manager.check_resources.assert_not_called()

    def test_managed_executor_invalid_type(self) -> None:
        """Test managed executor with invalid type."""
        with pytest.raises(ValueError, match="Unknown executor type"):
            with managed_executor(executor_type="invalid"):
                pass


class TestEstimateProcessingMemory:
    """Test memory estimation function."""

    def test_estimate_basic(self) -> None:
        """Test basic memory estimation."""
        # 10 frames, 1920x1080, 3 channels, 1 byte per pixel
        memory_mb = estimate_processing_memory(10, 1920, 1080, 3, 1)

        # Single frame: 1920 * 1080 * 3 * 1 = 6,220,800 bytes
        # Total: 10 * 6,220,800 * 3 (input/output/working) = 186,624,000 bytes
        # With 20% buffer: 186,624,000 * 1.2 = 223,948,800 bytes = ~214 MB
        expected = int((10 * 1920 * 1080 * 3 * 1 * 3 / (1024 * 1024)) * 1.2)
        assert memory_mb == expected

    def test_estimate_high_resolution(self) -> None:
        """Test memory estimation for high resolution."""
        # 100 frames, 4K resolution
        memory_mb = estimate_processing_memory(100, 3840, 2160, 3, 1)

        # Should be significantly higher
        assert memory_mb > 1000  # At least 1GB

    def test_estimate_with_different_dtypes(self) -> None:
        """Test memory estimation with different data types."""
        # Same parameters but different byte sizes
        memory_1byte = estimate_processing_memory(10, 1920, 1080, 3, 1)
        memory_4bytes = estimate_processing_memory(10, 1920, 1080, 3, 4)

        # 4-byte should be exactly 4x more
        assert memory_4bytes == memory_1byte * 4

    def test_estimate_different_channels(self) -> None:
        """Test memory estimation with different channel counts."""
        memory_rgb = estimate_processing_memory(10, 1920, 1080, 3, 1)
        memory_rgba = estimate_processing_memory(10, 1920, 1080, 4, 1)

        # RGBA should be 4/3 times RGB
        expected_ratio = 4.0 / 3.0
        actual_ratio = memory_rgba / memory_rgb
        assert abs(actual_ratio - expected_ratio) < 0.1  # Allow small rounding differences
