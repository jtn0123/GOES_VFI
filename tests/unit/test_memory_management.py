"""Unit tests for memory management functionality."""

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


class TestMemoryStats:
    """Test MemoryStats dataclass."""

    def test_low_memory_detection(self) -> None:
        """Test low memory detection."""
        # Normal memory
        stats = MemoryStats(
            total_mb=8000,
            available_mb=2000,
            used_mb=6000,
            percent_used=75.0,
        )
        assert not stats.is_low_memory
        assert not stats.is_critical_memory

        # Low memory by available MB
        stats = MemoryStats(
            total_mb=8000,
            available_mb=400,
            used_mb=7600,
            percent_used=95.0,
        )
        assert stats.is_low_memory
        assert not stats.is_critical_memory

        # Critical memory
        stats = MemoryStats(
            total_mb=8000,
            available_mb=150,
            used_mb=7850,
            percent_used=98.0,
        )
        assert stats.is_low_memory
        assert stats.is_critical_memory


class TestMemoryMonitor:
    """Test MemoryMonitor class."""

    def test_get_memory_stats(self) -> None:
        """Test getting memory statistics."""
        monitor = MemoryMonitor()
        stats = monitor.get_memory_stats()

        assert isinstance(stats, MemoryStats)
        assert stats.total_mb >= 0
        assert stats.available_mb >= 0
        assert stats.used_mb >= 0
        assert 0 <= stats.percent_used <= 100

    def test_callbacks(self) -> None:
        """Test callback mechanism."""
        monitor = MemoryMonitor()
        callback_mock = Mock()

        monitor.add_callback(callback_mock)

        # Manually trigger callback with test stats
        test_stats = MemoryStats(
            total_mb=8000,
            available_mb=2000,
            used_mb=6000,
            percent_used=75.0,
        )

        # Call all callbacks
        for callback in monitor._callbacks:
            callback(test_stats)

        callback_mock.assert_called_once_with(test_stats)

    def test_get_memory_stats_psutil_mock(self) -> None:
        """Memory stats should be retrieved using psutil when available."""
        fake_vm = Mock(total=8 * 1024**3, available=6 * 1024**3, used=2 * 1024**3, percent=25.0)
        fake_proc = Mock()
        fake_proc.memory_info.return_value = Mock(rss=256 * 1024**2)
        fake_proc.memory_percent.return_value = 1.2

        with (
            patch("goesvfi.utils.memory_manager.psutil") as mock_psutil,
            patch("goesvfi.utils.memory_manager.PSUTIL_AVAILABLE", True),
        ):
            mock_psutil.virtual_memory.return_value = fake_vm
            mock_psutil.Process.return_value = fake_proc

            monitor = MemoryMonitor()
            stats = monitor.get_memory_stats()

        assert stats.total_mb == 8192
        assert stats.available_mb == 6144
        assert stats.used_mb == 2048
        assert stats.percent_used == 25.0
        assert stats.process_mb == 256
        assert stats.process_percent == 1.2

    def test_get_memory_stats_without_psutil(self) -> None:
        """Fallback path should work when psutil is unavailable."""
        fake_rusage = Mock(ru_maxrss=500000)

        with (
            patch("goesvfi.utils.memory_manager.PSUTIL_AVAILABLE", False),
            patch("resource.getrusage", return_value=fake_rusage),
        ):
            monitor = MemoryMonitor()
            stats = monitor.get_memory_stats()

        assert stats.process_mb == 488


class TestMemoryOptimizer:
    """Test MemoryOptimizer class."""

    def test_optimize_array_dtype(self) -> None:
        """Test array dtype optimization."""
        optimizer = MemoryOptimizer()

        # Test float64 to float32 conversion
        arr_f64 = np.array([1.0, 2.0, 3.0], dtype=np.float64)
        optimized = optimizer.optimize_array_dtype(arr_f64)
        assert optimized.dtype == np.float32
        assert np.array_equal(optimized, arr_f64)

        # Test int64 to uint8 conversion
        arr_i64 = np.array([10, 20, 30], dtype=np.int64)
        optimized = optimizer.optimize_array_dtype(arr_i64)
        assert optimized.dtype == np.uint8
        assert np.array_equal(optimized, arr_i64)

    def test_chunk_large_array(self) -> None:
        """Test array chunking."""
        optimizer = MemoryOptimizer()

        # Create a large array
        large_array = np.zeros((1000, 1000), dtype=np.float32)  # ~4MB

        # Chunk it into smaller pieces
        chunks = optimizer.chunk_large_array(large_array, max_chunk_mb=1)

        assert len(chunks) > 1
        assert sum(len(chunk) for chunk in chunks) == len(large_array)

        # Verify chunks can be reconstructed
        reconstructed = np.vstack(chunks)
        assert np.array_equal(reconstructed, large_array)

    @patch("goesvfi.utils.memory_manager.gc.collect")
    def test_free_memory(self, mock_gc_collect) -> None:
        """Test memory freeing."""
        optimizer = MemoryOptimizer()

        optimizer.free_memory(force=True)
        mock_gc_collect.assert_called_once()

    def test_check_available_memory(self) -> None:
        """Test memory availability checking."""
        optimizer = MemoryOptimizer()

        # Test with small memory requirement (should pass)
        has_memory, msg = optimizer.check_available_memory(10)  # 10MB
        assert has_memory
        assert msg == "OK"

        # Test with huge memory requirement (should fail)
        has_memory, msg = optimizer.check_available_memory(1000000)  # 1TB
        assert not has_memory
        assert "Insufficient memory" in msg or "critically low memory" in msg


class TestObjectPool:
    """Test ObjectPool class."""

    def test_acquire_release(self) -> None:
        """Test object acquisition and release."""
        factory_mock = Mock(side_effect=object)
        pool = ObjectPool(factory_mock, max_size=2)

        # First acquire should create new object
        obj1 = pool.acquire()
        assert obj1 is not None
        factory_mock.assert_called_once()

        # Release and re-acquire should reuse
        pool.release(obj1)
        obj2 = pool.acquire()
        assert obj2 is obj1
        assert factory_mock.call_count == 1

        # Acquire another should create new
        obj3 = pool.acquire()
        assert obj3 is not obj1
        assert factory_mock.call_count == 2

    def test_pool_max_size(self) -> None:
        """Test pool maximum size enforcement."""
        pool = ObjectPool(object, max_size=2)

        objs = [pool.acquire() for _ in range(3)]

        # Release all
        for obj in objs:
            pool.release(obj)

        # Pool should only keep max_size objects
        assert len(pool.pool) == 2


class TestImageLoaderMemoryIntegration:
    """Test ImageLoader memory integration."""

    @patch("goesvfi.utils.memory_manager.MemoryOptimizer")
    @patch("PIL.Image.open")
    def test_memory_optimized_loading(self, mock_open, _mock_optimizer_class) -> None:
        """Test memory-optimized image loading."""
        # Setup mocks
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
        with patch("numpy.array", return_value=mock_array), patch("os.path.exists", return_value=True):
            result = loader.load("test.png")

        assert result is not None
        assert result.metadata["memory_optimized"]
        assert "size_mb" in result.metadata

    @patch("PIL.Image.open")
    def test_image_size_limit(self, mock_open) -> None:
        """Test image size limit enforcement."""
        # Mock large image
        mock_img = MagicMock()
        mock_img.size = (10000, 10000)  # Very large
        mock_img.mode = "RGB"
        mock_img.__enter__ = Mock(return_value=mock_img)
        mock_img.__exit__ = Mock(return_value=None)
        mock_open.return_value = mock_img

        # Create loader with small size limit
        loader = ImageLoader(optimize_memory=True, max_image_size_mb=10)

        # Should raise ProcessingError for oversized image (ValueError is wrapped)
        with pytest.raises(ProcessingError, match="Image too large"):
            with patch("os.path.exists", return_value=True):
                loader.load("huge.png")


def test_estimate_memory_requirement() -> None:
    """Test memory requirement estimation."""
    # Test 1000x1000 RGB image
    mb = estimate_memory_requirement((1000, 1000, 3), np.uint8)
    assert mb == 3  # ~2.86MB, rounded up to 3MB

    # Test 4K image
    mb = estimate_memory_requirement((3840, 2160, 3), np.float32)
    assert mb == 95  # ~99MB


def test_global_memory_monitor() -> None:
    """Test global memory monitor singleton."""
    monitor1 = get_memory_monitor()
    monitor2 = get_memory_monitor()

    assert monitor1 is monitor2  # Should be same instance


def test_optimize_array_chunks_no_shared_memory() -> None:
    """Chunks returned by optimize_array_chunks should not share memory."""
    optimizer = MemoryOptimizer()

    arr = np.arange(1000, dtype=np.float32)
    chunks = list(optimizer.optimize_array_chunks(arr, max_chunk_mb=1))

    assert sum(len(c) for c in chunks) == len(arr)
    assert all(not np.shares_memory(arr, c) for c in chunks)


def test_streaming_processor_low_memory_usage() -> None:
    """Processing in chunks should not drastically increase memory usage."""
    processor = StreamingProcessor(chunk_size_mb=1)
    arr = np.ones(2_000_000, dtype=np.float32)  # ~8MB

    proc = psutil.Process()
    gc.collect()
    before = proc.memory_info().rss

    result = processor.process_array(arr, lambda x: x + 1)

    gc.collect()
    after = proc.memory_info().rss

    assert np.array_equal(result, arr + 1)
    assert (after - before) < 20 * 1024 * 1024  # less than ~20MB increase
