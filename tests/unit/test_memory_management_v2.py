"""Unit tests for memory management functionality - Optimized v2."""

import gc
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import psutil
import pytest

from goesvfi.pipeline.exceptions import ProcessingError
from goesvfi.pipeline.image_loader import ImageLoader
from goesvfi.utils.memory_manager import (
    MemoryMonitor,
    MemoryOptimizer,
    MemoryStats,
    ObjectPool,
    StreamingProcessor,
    estimate_memory_requirement,
    get_memory_monitor,
)


# Shared fixtures and test data
@pytest.fixture(scope="session")
def memory_stats_scenarios():
    """Pre-defined memory statistics scenarios for consistent testing."""
    return {
        "normal": MemoryStats(
            total_mb=8000,
            available_mb=2000,
            used_mb=6000,
            percent_used=75.0,
        ),
        "low_memory": MemoryStats(
            total_mb=8000,
            available_mb=400,
            used_mb=7600,
            percent_used=95.0,
        ),
        "critical_memory": MemoryStats(
            total_mb=8000,
            available_mb=150,
            used_mb=7850,
            percent_used=98.0,
        ),
    }


@pytest.fixture(scope="session")
def mock_psutil_data():
    """Mock psutil data for consistent testing."""
    return {
        "virtual_memory": Mock(total=8 * 1024**3, available=6 * 1024**3, used=2 * 1024**3, percent=25.0),
        "process": Mock(),
    }


@pytest.fixture()
def memory_monitor():
    """Create MemoryMonitor instance for testing."""
    return MemoryMonitor()


@pytest.fixture()
def memory_optimizer():
    """Create MemoryOptimizer instance for testing."""
    return MemoryOptimizer()


class TestMemoryStats:
    """Test MemoryStats dataclass with parameterized scenarios."""

    @pytest.mark.parametrize(
        "scenario,expected_low,expected_critical",
        [
            ("normal", False, False),
            ("low_memory", True, False),
            ("critical_memory", True, True),
        ],
    )
    def test_memory_detection_properties(
        self, memory_stats_scenarios, scenario: str, expected_low: bool, expected_critical: bool
    ) -> None:
        """Test low and critical memory detection properties."""
        stats = memory_stats_scenarios[scenario]

        assert stats.is_low_memory == expected_low
        assert stats.is_critical_memory == expected_critical


class TestMemoryMonitor:
    """Test MemoryMonitor class with optimized patterns."""

    def test_get_memory_stats_basic(self, memory_monitor) -> None:
        """Test basic memory statistics retrieval."""
        stats = memory_monitor.get_memory_stats()

        assert isinstance(stats, MemoryStats)
        assert stats.total_mb >= 0
        assert stats.available_mb >= 0
        assert stats.used_mb >= 0
        assert 0 <= stats.percent_used <= 100

    def test_callback_mechanism(self, memory_monitor, memory_stats_scenarios) -> None:
        """Test callback registration and execution."""
        callback_results = []
        callback_mock = Mock(side_effect=callback_results.append)

        memory_monitor.add_callback(callback_mock)
        test_stats = memory_stats_scenarios["normal"]

        # Manually trigger callbacks
        for callback in memory_monitor._callbacks:
            callback(test_stats)

        callback_mock.assert_called_once_with(test_stats)
        assert test_stats in callback_results

    @pytest.mark.parametrize("psutil_available", [True, False])
    def test_memory_stats_with_psutil_availability(
        self, memory_monitor, mock_psutil_data, psutil_available: bool
    ) -> None:
        """Test memory stats retrieval with and without psutil."""
        if psutil_available:
            fake_proc = Mock()
            fake_proc.memory_info.return_value = Mock(rss=256 * 1024**2)
            fake_proc.memory_percent.return_value = 1.2

            with (
                patch("goesvfi.utils.memory_manager.psutil") as mock_psutil,
                patch("goesvfi.utils.memory_manager.PSUTIL_AVAILABLE", True),
            ):
                mock_psutil.virtual_memory.return_value = mock_psutil_data["virtual_memory"]
                mock_psutil.Process.return_value = fake_proc

                stats = memory_monitor.get_memory_stats()

            assert stats.total_mb == 8192
            assert stats.available_mb == 6144
            assert stats.used_mb == 2048
            assert stats.percent_used == 25.0
            assert stats.process_mb == 256
            assert stats.process_percent == 1.2
        else:
            fake_rusage = Mock(ru_maxrss=500000)

            with (
                patch("goesvfi.utils.memory_manager.PSUTIL_AVAILABLE", False),
                patch("resource.getrusage", return_value=fake_rusage),
            ):
                stats = memory_monitor.get_memory_stats()

            assert stats.process_mb == 488  # Converted from rusage


class TestMemoryOptimizer:
    """Test MemoryOptimizer class with parameterized scenarios."""

    @pytest.mark.parametrize(
        "input_dtype,expected_dtype",
        [
            (np.float64, np.float32),
            (np.int64, np.uint8),
            (np.float32, np.float32),  # Should remain unchanged
        ],
    )
    def test_optimize_array_dtype(self, memory_optimizer, input_dtype, expected_dtype) -> None:
        """Test array dtype optimization for different input types."""
        if input_dtype == np.float64:
            arr = np.array([1.0, 2.0, 3.0], dtype=input_dtype)
        else:
            arr = np.array([10, 20, 30], dtype=input_dtype)

        optimized = memory_optimizer.optimize_array_dtype(arr)
        assert optimized.dtype == expected_dtype
        assert np.array_equal(optimized, arr.astype(expected_dtype))

    @pytest.mark.parametrize(
        "array_size,max_chunk_mb,expected_chunks",
        [
            ((1000, 1000), 1, "> 1"),  # Should create multiple chunks
            ((100, 100), 10, "== 1"),  # Should fit in one chunk
        ],
    )
    def test_chunk_large_array(
        self, memory_optimizer, array_size: tuple[int, int], max_chunk_mb: int, expected_chunks: str
    ) -> None:
        """Test array chunking with different sizes and limits."""
        large_array = np.zeros(array_size, dtype=np.float32)
        chunks = memory_optimizer.chunk_large_array(large_array, max_chunk_mb=max_chunk_mb)

        if expected_chunks == "> 1":
            assert len(chunks) > 1
        elif expected_chunks == "== 1":
            assert len(chunks) == 1

        # Verify chunks can be reconstructed
        assert sum(len(chunk) for chunk in chunks) == len(large_array)
        reconstructed = np.vstack(chunks) if len(chunks) > 1 else chunks[0]
        assert np.array_equal(reconstructed, large_array)

    @patch("goesvfi.utils.memory_manager.gc.collect")
    def test_free_memory_with_force(self, mock_gc_collect, memory_optimizer) -> None:
        """Test memory freeing with force option."""
        memory_optimizer.free_memory(force=True)
        mock_gc_collect.assert_called_once()

    @pytest.mark.parametrize(
        "required_mb,expected_result",
        [
            (10, True),  # Small requirement should pass
            (1000000, False),  # Huge requirement should fail
        ],
    )
    def test_check_available_memory(self, memory_optimizer, required_mb: int, expected_result: bool) -> None:
        """Test memory availability checking with different requirements."""
        has_memory, msg = memory_optimizer.check_available_memory(required_mb)

        assert has_memory == expected_result
        if expected_result:
            assert msg == "OK"
        else:
            assert "Insufficient memory" in msg or "critically low memory" in msg

    def test_optimize_array_chunks_independence(self, memory_optimizer) -> None:
        """Test that optimized array chunks don't share memory."""
        arr = np.arange(1000, dtype=np.float32)
        chunks = list(memory_optimizer.optimize_array_chunks(arr, max_chunk_mb=1))

        assert sum(len(c) for c in chunks) == len(arr)
        assert all(not np.shares_memory(arr, c) for c in chunks)


class TestObjectPool:
    """Test ObjectPool class with optimized patterns."""

    @pytest.mark.parametrize(
        "max_size,operations",
        [
            (2, ["acquire", "release", "acquire"]),  # Test reuse
            (2, ["acquire", "acquire", "acquire"]),  # Test creation
            (1, ["acquire", "release", "release"]),  # Test max size limit
        ],
    )
    def test_object_pool_operations(self, max_size: int, operations: list[str]) -> None:
        """Test object pool operations with different scenarios."""
        factory_mock = Mock(side_effect=object)
        pool = ObjectPool(factory_mock, max_size=max_size)
        objects = []

        for operation in operations:
            if operation == "acquire":
                obj = pool.acquire()
                objects.append(obj)
                assert obj is not None
            elif operation == "release" and objects:
                obj = objects.pop()
                pool.release(obj)

        # Verify factory was called appropriately
        assert factory_mock.call_count <= len([op for op in operations if op == "acquire"])

    def test_pool_max_size_enforcement(self) -> None:
        """Test that pool enforces maximum size limits."""
        pool = ObjectPool(object, max_size=2)

        # Create objects
        objs = [pool.acquire() for _ in range(3)]

        # Release all
        for obj in objs:
            pool.release(obj)

        # Pool should only keep max_size objects
        assert len(pool.pool) == 2


class TestImageLoaderMemoryIntegration:
    """Test ImageLoader memory integration with mocked dependencies."""

    @patch("goesvfi.utils.memory_manager.MemoryOptimizer")
    @patch("PIL.Image.open")
    def test_memory_optimized_loading_workflow(self, mock_open, mock_optimizer_class) -> None:
        """Test complete memory-optimized image loading workflow."""
        # Setup image mock
        mock_img = MagicMock()
        mock_img.size = (100, 100)
        mock_img.mode = "RGB"
        mock_img.format = "PNG"
        mock_img.__enter__ = Mock(return_value=mock_img)
        mock_img.__exit__ = Mock(return_value=None)
        mock_open.return_value = mock_img

        # Mock numpy array
        mock_array = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_img.__array__ = Mock(return_value=mock_array)

        # Create loader with memory optimization
        loader = ImageLoader(optimize_memory=True, max_image_size_mb=10)

        # Load image
        with (
            patch("numpy.array", return_value=mock_array),
            patch("os.path.exists", return_value=True),
        ):
            result = loader.load("test.png")

        assert result is not None
        assert result.metadata["memory_optimized"]
        assert "size_mb" in result.metadata

    @pytest.mark.parametrize(
        "image_size,size_limit,should_raise",
        [
            ((1000, 1000), 10, False),  # Within limit
            ((10000, 10000), 10, True),  # Exceeds limit
        ],
    )
    @patch("PIL.Image.open")
    def test_image_size_limit_enforcement(
        self, mock_open, image_size: tuple[int, int], size_limit: int, should_raise: bool
    ) -> None:
        """Test image size limit enforcement."""
        # Mock image with specified size
        mock_img = MagicMock()
        mock_img.size = image_size
        mock_img.mode = "RGB"
        mock_img.__enter__ = Mock(return_value=mock_img)
        mock_img.__exit__ = Mock(return_value=None)
        mock_open.return_value = mock_img

        # Create loader with size limit
        loader = ImageLoader(optimize_memory=True, max_image_size_mb=size_limit)

        if should_raise:
            with pytest.raises(ProcessingError, match="Image too large"):
                with patch("os.path.exists", return_value=True):
                    loader.load("test.png")
        else:
            # Should not raise for reasonable sizes
            mock_array = np.zeros((*image_size, 3), dtype=np.uint8)
            with (
                patch("os.path.exists", return_value=True),
                patch("numpy.array", return_value=mock_array),
            ):
                result = loader.load("test.png")
                assert result is not None


class TestMemoryEstimationAndUtilities:
    """Test memory estimation and utility functions."""

    @pytest.mark.parametrize(
        "shape,dtype,expected_mb",
        [
            ((1000, 1000, 3), np.uint8, 3),  # Basic RGB image
            ((3840, 2160, 3), np.float32, 95),  # 4K float32 image
            ((1000, 1000, 4), np.uint8, 4),  # RGBA image
        ],
    )
    def test_estimate_memory_requirement(self, shape: tuple[int, ...], dtype, expected_mb: int) -> None:
        """Test memory requirement estimation for various scenarios."""
        mb = estimate_memory_requirement(shape, dtype)
        assert mb == expected_mb

    def test_global_memory_monitor_singleton(self) -> None:
        """Test global memory monitor singleton pattern."""
        monitor1 = get_memory_monitor()
        monitor2 = get_memory_monitor()

        assert monitor1 is monitor2  # Should be same instance

    def test_streaming_processor_memory_efficiency(self) -> None:
        """Test that streaming processor maintains low memory usage."""
        processor = StreamingProcessor(chunk_size_mb=1)
        arr = np.ones(2_000_000, dtype=np.float32)  # ~8MB

        proc = psutil.Process()
        gc.collect()
        before = proc.memory_info().rss

        result = processor.process_array(arr, lambda x: x + 1)

        gc.collect()
        after = proc.memory_info().rss

        assert np.array_equal(result, arr + 1)
        # Should not drastically increase memory usage
        assert (after - before) < 20 * 1024 * 1024  # less than ~20MB increase
