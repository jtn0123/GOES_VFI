"""Tests for optimized RIFE interpolation with caching and reduced I/O."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from goesvfi.pipeline.optimized_interpolator import (
    BatchTempManager,
    ImageCache,
    OptimizedRifeBackend,
    interpolate_three,
)


@pytest.fixture()
def dummy_img():
    """Create a dummy 4x4 RGB float32 image."""
    return np.random.rand(4, 4, 3).astype(np.float32)


@pytest.fixture()
def different_img():
    """Create a different dummy 4x4 RGB float32 image."""
    return np.random.rand(4, 4, 3).astype(np.float32) * 0.5


class TestImageCache:
    """Test the ImageCache class."""

    def test_cache_initialization(self) -> None:
        """Test cache initializes correctly."""
        cache = ImageCache(max_size=10)
        assert cache.max_size == 10
        assert len(cache._cache) == 0
        assert len(cache._access_order) == 0

    def test_cache_miss(self, dummy_img) -> None:
        """Test cache miss returns None."""
        cache = ImageCache(max_size=10)
        result = cache.get(dummy_img)
        assert result is None

    def test_cache_hit(self, dummy_img) -> None:
        """Test cache hit returns correct result."""
        cache = ImageCache(max_size=10)
        expected_result = np.ones((4, 4, 3), dtype=np.float32) * 0.5

        # Cache the result
        cache.put(dummy_img, expected_result)

        # Retrieve from cache
        cached_result = cache.get(dummy_img)
        assert cached_result is not None
        np.testing.assert_array_equal(cached_result, expected_result)

    def test_cache_eviction(self) -> None:
        """Test LRU eviction works correctly."""
        cache = ImageCache(max_size=2)

        # Create three different images
        img1 = np.ones((2, 2, 3), dtype=np.float32)
        img2 = np.ones((2, 2, 3), dtype=np.float32) * 0.5
        img3 = np.ones((2, 2, 3), dtype=np.float32) * 0.25

        result1 = np.ones((2, 2, 3), dtype=np.float32) * 0.1
        result2 = np.ones((2, 2, 3), dtype=np.float32) * 0.2
        result3 = np.ones((2, 2, 3), dtype=np.float32) * 0.3

        # Fill cache
        cache.put(img1, result1)
        cache.put(img2, result2)
        assert len(cache._cache) == 2

        # Add third item (should evict first)
        cache.put(img3, result3)
        assert len(cache._cache) == 2

        # First item should be evicted
        assert cache.get(img1) is None
        # Second and third should still be there
        assert cache.get(img2) is not None
        assert cache.get(img3) is not None

    def test_cache_stats(self, dummy_img) -> None:
        """Test cache statistics."""
        cache = ImageCache(max_size=10)

        # Empty cache stats
        stats = cache.get_stats()
        assert stats["size"] == 0
        assert stats["max_size"] == 10
        assert stats["memory_usage_mb"] == 0

        # Add item and check stats
        result = np.ones((4, 4, 3), dtype=np.float32)
        cache.put(dummy_img, result)

        stats = cache.get_stats()
        assert stats["size"] == 1
        assert stats["memory_usage_mb"] > 0


class TestBatchTempManager:
    """Test the BatchTempManager class."""

    def test_temp_manager_initialization(self) -> None:
        """Test temp manager initializes correctly."""
        manager = BatchTempManager(max_files_per_dir=5)
        assert manager.max_files_per_dir == 5
        assert manager._current_dir is None
        assert manager._file_count == 0
        assert len(manager._dirs_created) == 0

    def test_get_temp_files_creates_directory(self) -> None:
        """Test that getting temp files creates directory."""
        manager = BatchTempManager(max_files_per_dir=5)

        input1, input2, output = manager.get_temp_files()

        # Check that directory was created
        assert manager._current_dir is not None
        assert manager._current_dir.exists()
        assert len(manager._dirs_created) == 1

        # Check that files have correct paths
        assert input1.parent == manager._current_dir
        assert input2.parent == manager._current_dir
        assert output.parent == manager._current_dir
        assert input1.name.endswith("_input1.png")
        assert input2.name.endswith("_input2.png")
        assert output.name.endswith("_output.png")

        # Cleanup
        manager.cleanup()

    def test_file_count_increments(self) -> None:
        """Test that file count increments correctly."""
        manager = BatchTempManager(max_files_per_dir=5)

        # Get files multiple times
        manager.get_temp_files()
        assert manager._file_count == 1

        manager.get_temp_files()
        assert manager._file_count == 2

        # Cleanup
        manager.cleanup()

    def test_new_directory_created_when_limit_reached(self) -> None:
        """Test new directory creation when file limit reached."""
        manager = BatchTempManager(max_files_per_dir=2)

        # Get files up to limit
        manager.get_temp_files()  # count = 1
        first_dir = manager._current_dir

        manager.get_temp_files()  # count = 2
        assert manager._current_dir == first_dir

        # Next call should create new directory
        manager.get_temp_files()  # count = 1 in new dir
        assert manager._current_dir != first_dir
        assert len(manager._dirs_created) == 2
        assert manager._file_count == 1

        # Cleanup
        manager.cleanup()

    def test_cleanup_removes_directories(self) -> None:
        """Test cleanup removes all created directories."""
        manager = BatchTempManager(max_files_per_dir=5)

        # Create some temp files
        manager.get_temp_files()
        manager.get_temp_files()

        temp_dir = manager._current_dir
        assert temp_dir.exists()

        # Cleanup
        manager.cleanup()

        # Check directory was removed
        assert not temp_dir.exists()
        assert len(manager._dirs_created) == 0
        assert manager._current_dir is None
        assert manager._file_count == 0


class TestOptimizedRifeBackend:
    """Test the OptimizedRifeBackend class."""

    @pytest.fixture()
    def mock_exe_path(self, tmp_path):
        """Create a mock executable path."""
        exe_path = tmp_path / "rife-cli"
        exe_path.touch()
        exe_path.chmod(0o755)  # Make executable
        return exe_path

    @pytest.fixture()
    def optimized_backend(self, mock_exe_path):
        """Create an optimized backend with mocked dependencies."""
        with patch("goesvfi.pipeline.optimized_interpolator.RifeCommandBuilder") as mock_builder:
            mock_builder.return_value = MagicMock()
            return OptimizedRifeBackend(mock_exe_path, cache_size=10)

    def test_backend_initialization(self, mock_exe_path) -> None:
        """Test backend initializes correctly."""
        with patch("goesvfi.pipeline.optimized_interpolator.RifeCommandBuilder"):
            backend = OptimizedRifeBackend(mock_exe_path, cache_size=5)

            assert backend.exe == mock_exe_path
            assert backend.cache.max_size == 5
            assert backend.stats["total_interpolations"] == 0

    def test_interpolate_pair_with_mocks(self, optimized_backend, dummy_img, different_img) -> None:
        """Test interpolate_pair with complete mocking."""
        with (
            patch.object(optimized_backend, "_run_rife_command") as mock_rife,
            patch.object(optimized_backend, "_save_image_optimized") as mock_save,
            patch.object(optimized_backend, "_load_image_optimized") as mock_load,
        ):
            # Setup mocks
            expected_result = np.ones((4, 4, 3), dtype=np.float32) * 0.75
            mock_load.return_value = expected_result

            # Call interpolate_pair
            result = optimized_backend.interpolate_pair(dummy_img, different_img)

            # Verify calls
            assert mock_save.call_count == 2  # Two input images
            mock_rife.assert_called_once()
            mock_load.assert_called_once()

            # Verify result
            np.testing.assert_array_equal(result, expected_result)

            # Verify stats
            assert optimized_backend.stats["total_interpolations"] == 1
            assert optimized_backend.stats["cache_misses"] == 1

    def test_caching_works(self, optimized_backend, dummy_img, different_img) -> None:
        """Test that caching reduces RIFE calls."""
        with (
            patch.object(optimized_backend, "_run_rife_command") as mock_rife,
            patch.object(optimized_backend, "_save_image_optimized"),
            patch.object(optimized_backend, "_load_image_optimized") as mock_load,
        ):
            expected_result = np.ones((4, 4, 3), dtype=np.float32) * 0.75
            mock_load.return_value = expected_result

            # First call
            result1 = optimized_backend.interpolate_pair(dummy_img, different_img)

            # Second call with same inputs (should hit cache)
            result2 = optimized_backend.interpolate_pair(dummy_img, different_img)

            # Verify RIFE only called once
            assert mock_rife.call_count == 1

            # Verify results are the same
            np.testing.assert_array_equal(result1, result2)

            # Verify stats
            assert optimized_backend.stats["total_interpolations"] == 2
            assert optimized_backend.stats["cache_hits"] == 1
            assert optimized_backend.stats["cache_misses"] == 1

    def test_performance_stats(self, optimized_backend) -> None:
        """Test performance statistics calculation."""
        # Set some dummy stats
        optimized_backend.stats.update({
            "total_interpolations": 10,
            "cache_hits": 3,
            "cache_misses": 7,
            "total_io_time": 2.0,
            "total_rife_time": 8.0
        })

        stats = optimized_backend.get_performance_stats()

        assert stats["cache_hit_rate"] == 0.3  # 3/10
        assert stats["total_time"] == 10.0  # 2.0 + 8.0
        assert stats["avg_io_time"] == 2.0 / 7  # total_io_time / cache_misses
        assert stats["avg_rife_time"] == 8.0 / 7  # total_rife_time / cache_misses

    def test_cleanup(self, optimized_backend) -> None:
        """Test cleanup clears resources."""
        # Add some dummy cache data
        optimized_backend._pair_cache = {"test": np.ones((2, 2, 3))}

        # Call cleanup
        optimized_backend.cleanup()

        # Verify cleanup
        assert len(optimized_backend.cache._cache) == 0
        assert len(optimized_backend._pair_cache) == 0


def test_interpolate_three_with_optimized_backend(dummy_img, different_img) -> None:
    """Test interpolate_three function with optimized backend."""
    # Create mock optimized backend
    mock_backend = MagicMock(spec=OptimizedRifeBackend)
    mock_backend.interpolate_pair.side_effect = [
        np.full((4, 4, 3), 0.5, dtype=np.float32),  # mid
        np.full((4, 4, 3), 0.25, dtype=np.float32),  # left
        np.full((4, 4, 3), 0.75, dtype=np.float32),  # right
    ]

    # Call interpolate_three
    result = interpolate_three(dummy_img, different_img, mock_backend)

    # Verify three calls were made
    assert mock_backend.interpolate_pair.call_count == 3

    # Verify result structure
    assert isinstance(result, list)
    assert len(result) == 3
    assert all(isinstance(arr, np.ndarray) for arr in result)

    # Verify values match expected order: [left, mid, right]
    np.testing.assert_array_equal(result[0], 0.25)  # left
    np.testing.assert_array_equal(result[1], 0.5)   # mid
    np.testing.assert_array_equal(result[2], 0.75)  # right


def test_interpolate_three_with_legacy_backend(dummy_img, different_img) -> None:
    """Test interpolate_three function with legacy backend."""
    # Create mock legacy backend
    mock_backend = MagicMock()
    mock_backend.interpolate_pair.side_effect = [
        np.full((4, 4, 3), 0.5, dtype=np.float32),  # mid
        np.full((4, 4, 3), 0.25, dtype=np.float32),  # left
        np.full((4, 4, 3), 0.75, dtype=np.float32),  # right
    ]

    # Call interpolate_three
    result = interpolate_three(dummy_img, different_img, mock_backend)

    # Verify three calls were made
    assert mock_backend.interpolate_pair.call_count == 3

    # Verify result structure
    assert isinstance(result, list)
    assert len(result) == 3
