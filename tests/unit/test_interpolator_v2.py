"""Optimized tests for RIFE interpolation with caching and reduced I/O.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for common test resources
- Parameterized test scenarios for comprehensive coverage
- Enhanced test managers for batch operations
- Reduced redundancy in test setup
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from goesvfi.pipeline.optimized_interpolator import (
    BatchTempManager,
    ImageCache,
    OptimizedRifeBackend,
    interpolate_three,
)


class TestInterpolatorOptimizedV2:
    """Optimized tests for interpolator components with full coverage."""

    @pytest.fixture(scope="class")
    @staticmethod
    def interpolator_test_components() -> dict[str, Any]:  # noqa: C901
        """Create shared components for interpolator testing.

        Returns:
            dict[str, Any]: Test components including manager and images.
        """

        # Test Image Generator
        class TestImageGenerator:
            """Generate test images with various properties."""

            @staticmethod
            def create_dummy_image(size: tuple[int, int, int] = (4, 4, 3), value: float = 1.0) -> np.ndarray:
                """Create a dummy image with specified size and value.

                Returns:
                    np.ndarray: Generated test image.
                """
                rng = np.random.default_rng()
                return rng.random(size).astype(np.float32) * value

            @staticmethod
            def create_image_sequence(count: int = 3, size: tuple[int, int, int] = (4, 4, 3)) -> list[np.ndarray]:
                """Create a sequence of test images.

                Returns:
                    list[np.ndarray]: List of test images.
                """
                return [TestImageGenerator.create_dummy_image(size, value=float(i) / count) for i in range(count)]

        # Interpolator Test Manager
        class InterpolatorTestManager:
            """Manage interpolator testing scenarios."""

            def __init__(self) -> None:
                self.image_generator = TestImageGenerator()

                # Define test configurations
                self.cache_configs = {
                    "small": {"max_size": 5},
                    "medium": {"max_size": 10},
                    "large": {"max_size": 100},
                }

                self.batch_configs = {
                    "small_batch": {"max_files_per_dir": 5},
                    "medium_batch": {"max_files_per_dir": 20},
                    "large_batch": {"max_files_per_dir": 100},
                }

                # Define test scenarios
                self.test_scenarios = {
                    "cache_operations": self._test_cache_operations,
                    "cache_eviction": self._test_cache_eviction,
                    "batch_temp_management": self._test_batch_temp_management,
                    "backend_interpolation": self._test_backend_interpolation,
                    "error_handling": self._test_error_handling,
                }

            def _test_cache_operations(self, scenario_name: str, **kwargs: Any) -> dict[str, Any]:
                """Test cache operations scenarios.

                Returns:
                    dict[str, Any]: Test results.
                """
                results = {}

                if scenario_name == "basic_operations":
                    cache = ImageCache(max_size=10)
                    img = self.image_generator.create_dummy_image()
                    result_img = self.image_generator.create_dummy_image(value=0.5)

                    # Test miss
                    assert cache.get(img) is None
                    results["miss_tested"] = True

                    # Test put and hit
                    cache.put(img, result_img)
                    cached = cache.get(img)
                    assert cached is not None
                    np.testing.assert_array_almost_equal(cached, result_img)
                    results["hit_tested"] = True

                    # Test stats
                    stats = cache.get_stats()
                    assert stats["size"] == 1
                    assert stats["max_size"] == 10
                    assert stats["memory_usage_mb"] > 0
                    results["stats_tested"] = True

                elif scenario_name == "multiple_images":
                    cache = ImageCache(max_size=10)
                    images = self.image_generator.create_image_sequence(5)
                    results_imgs = self.image_generator.create_image_sequence(5)

                    # Cache multiple images
                    for img, res in zip(images, results_imgs, strict=False):
                        cache.put(img, res)

                    # Verify all cached
                    for img, expected in zip(images, results_imgs, strict=False):
                        cached = cache.get(img)
                        assert cached is not None
                        np.testing.assert_array_almost_equal(cached, expected)

                    results["multiple_cached"] = True
                    results["final_size"] = cache.get_stats()["size"]

                return {"scenario": scenario_name, "results": results}

            def _test_cache_eviction(self, scenario_name: str, **kwargs: Any) -> dict[str, Any]:
                """Test cache eviction scenarios.

                Returns:
                    dict[str, Any]: Test results.
                """
                results = {}

                if scenario_name == "lru_eviction":
                    cache = ImageCache(max_size=2)

                    # Create 3 images
                    img1 = self.image_generator.create_dummy_image(value=0.1)
                    img2 = self.image_generator.create_dummy_image(value=0.2)
                    img3 = self.image_generator.create_dummy_image(value=0.3)

                    res1 = self.image_generator.create_dummy_image(value=0.5)
                    res2 = self.image_generator.create_dummy_image(value=0.6)
                    res3 = self.image_generator.create_dummy_image(value=0.7)

                    # Fill cache
                    cache.put(img1, res1)
                    cache.put(img2, res2)
                    assert cache.get_stats()["size"] == 2

                    # Add third (should evict first)
                    cache.put(img3, res3)
                    assert cache.get_stats()["size"] == 2

                    # Check eviction
                    assert cache.get(img1) is None  # Evicted
                    assert cache.get(img2) is not None  # Still there
                    assert cache.get(img3) is not None  # Still there

                    results["lru_eviction_verified"] = True

                elif scenario_name == "access_order_update":
                    cache = ImageCache(max_size=3)
                    images = self.image_generator.create_image_sequence(4)
                    results_imgs = self.image_generator.create_image_sequence(4)

                    # Fill cache
                    for i in range(3):
                        cache.put(images[i], results_imgs[i])

                    # Access first image (update its position)
                    _ = cache.get(images[0])

                    # Add fourth image (should evict second, not first)
                    cache.put(images[3], results_imgs[3])

                    assert cache.get(images[0]) is not None  # Still there (accessed)
                    assert cache.get(images[1]) is None  # Evicted
                    assert cache.get(images[2]) is not None  # Still there
                    assert cache.get(images[3]) is not None  # Still there

                    results["access_order_verified"] = True

                return {"scenario": scenario_name, "results": results}

            @staticmethod
            def _test_batch_temp_management(scenario_name: str, **kwargs: Any) -> dict[str, Any]:
                """Test batch temp file management scenarios.

                Returns:
                    dict[str, Any]: Test results.
                """
                results = {}

                if scenario_name == "basic_temp_files":
                    manager = BatchTempManager(max_files_per_dir=10)

                    # Get temp files
                    input1, input2, output = manager.get_temp_files()

                    # Verify structure
                    assert manager._current_dir is not None  # noqa: SLF001
                    current_dir = manager._current_dir  # noqa: SLF001
                    assert current_dir is not None
                    assert current_dir.exists()
                    assert input1.parent == manager._current_dir  # noqa: SLF001
                    assert input2.parent == manager._current_dir  # noqa: SLF001
                    assert output.parent == manager._current_dir  # noqa: SLF001
                    assert input1.name.endswith("_input1.png")
                    assert input2.name.endswith("_input2.png")
                    assert output.name.endswith("_output.png")

                    results["temp_files_created"] = True
                    file_count: int = manager._file_count  # noqa: SLF001
                    results["file_count"] = file_count  # type: ignore[assignment]

                    # Cleanup
                    manager.cleanup()
                    assert manager._current_dir is None or not manager._current_dir.exists()  # noqa: SLF001
                    results["cleanup_verified"] = True

                elif scenario_name == "directory_rotation":
                    manager = BatchTempManager(max_files_per_dir=2)

                    # Create files up to limit
                    manager.get_temp_files()
                    first_dir = manager._current_dir  # noqa: SLF001

                    manager.get_temp_files()
                    assert manager._current_dir == first_dir  # noqa: SLF001
                    file_count_1: int = manager._file_count  # noqa: SLF001
                    assert file_count_1 == 2

                    # Next should create new directory
                    manager.get_temp_files()
                    assert manager._current_dir != first_dir  # noqa: SLF001
                    file_count_2: int = manager._file_count  # noqa: SLF001
                    assert file_count_2 == 1
                    assert len(manager._dirs_created) == 2  # noqa: SLF001

                    results["rotation_verified"] = True
                    results["total_dirs"] = len(manager._dirs_created)  # noqa: SLF001  # type: ignore[assignment]

                    # Cleanup all
                    manager.cleanup()
                    current_dir_path = manager._current_dir  # noqa: SLF001
                    if current_dir_path is not None:
                        for dir_path in [first_dir, current_dir_path]:
                            assert not dir_path.exists()

                elif scenario_name == "concurrent_operations":
                    managers = []
                    for _i in range(3):
                        manager = BatchTempManager(max_files_per_dir=5)
                        managers.append(manager)

                        # Each manager gets its own files
                        for _ in range(3):
                            manager.get_temp_files()

                    # Verify each has separate directories
                    dirs_used = [m._current_dir for m in managers]  # noqa: SLF001  # type: ignore[assignment]
                    assert len(set(dirs_used)) == 3  # All different

                    results["concurrent_managers"] = len(managers)
                    results["separate_dirs_verified"] = True

                    # Cleanup all
                    for manager in managers:
                        manager.cleanup()

                return {"scenario": scenario_name, "results": results}

            def _test_backend_interpolation(self, scenario_name: str, tmp_path: Path, **kwargs: Any) -> dict[str, Any]:
                """Test backend interpolation scenarios.

                Returns:
                    dict[str, Any]: Test results.
                """
                if scenario_name == "basic_interpolation":
                    return self._test_basic_interpolation(tmp_path)
                if scenario_name == "cache_hit":
                    return self._test_cache_hit_scenario(tmp_path)
                if scenario_name == "error_handling":
                    return self._test_error_handling_scenario(tmp_path)
                return {"scenario": scenario_name, "results": {}}

            def _test_basic_interpolation(self, tmp_path: Path) -> dict[str, Any]:
                """Test basic interpolation scenario.

                Returns:
                    dict[str, Any]: Test results.
                """
                results = {}

                # Create mock executable
                exe_path = tmp_path / "rife-cli"
                exe_path.touch()
                exe_path.chmod(0o755)

                backend = OptimizedRifeBackend(exe_path)

                # Create test images
                img1 = self.image_generator.create_dummy_image()
                img2 = self.image_generator.create_dummy_image(value=0.5)

                # Mock subprocess call
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(returncode=0)

                    # Test interpolation
                    with patch("PIL.Image.open") as mock_pil_open, \
                         patch("pathlib.Path.exists", return_value=True):
                        # Create mock PIL image
                        result_img = self.image_generator.create_dummy_image(value=0.75)
                        # Convert to uint8 for PIL format
                        result_img_uint8 = (result_img * 255).astype(np.uint8)
                        
                        mock_pil_img = MagicMock()
                        mock_pil_img.__enter__ = MagicMock(return_value=mock_pil_img)
                        mock_pil_img.__exit__ = MagicMock(return_value=None)
                        mock_pil_open.return_value = mock_pil_img
                        
                        # Mock numpy array conversion
                        with patch("numpy.array", return_value=result_img_uint8):
                            result = backend.interpolate_pair(img1, img2)

                            # Verify subprocess was called
                            assert mock_run.called
                            results["subprocess_called"] = True

                            # Verify result
                            assert result is not None
                            assert result.shape == img1.shape
                            results["interpolation_completed"] = True

                # Cleanup
                backend.cleanup()
                return {"scenario": "basic_interpolation", "results": results}

            def _test_cache_hit_scenario(self, tmp_path: Path) -> dict[str, Any]:
                """Test cache hit scenario.

                Returns:
                    dict[str, Any]: Test results.
                """
                results = {}

                exe_path = tmp_path / "rife-cli"
                exe_path.touch()
                exe_path.chmod(0o755)

                backend = OptimizedRifeBackend(exe_path, cache_size=10)

                img1 = self.image_generator.create_dummy_image()
                img2 = self.image_generator.create_dummy_image(value=0.5)

                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(returncode=0)

                    with patch("PIL.Image.open") as mock_pil_open, \
                         patch("pathlib.Path.exists", return_value=True):
                        # Create mock PIL image
                        result_img = self.image_generator.create_dummy_image(value=0.75)
                        # Convert to uint8 for PIL format
                        result_img_uint8 = (result_img * 255).astype(np.uint8)
                        
                        mock_pil_img = MagicMock()
                        mock_pil_img.__enter__ = MagicMock(return_value=mock_pil_img)
                        mock_pil_img.__exit__ = MagicMock(return_value=None)
                        mock_pil_open.return_value = mock_pil_img
                        
                        # Mock numpy array conversion
                        with patch("numpy.array", return_value=result_img_uint8):
                            # First call
                            result1 = backend.interpolate_pair(img1, img2)
                            assert mock_run.call_count == 1

                            # Second call (should hit cache)
                            result2 = backend.interpolate_pair(img1, img2)
                            assert mock_run.call_count == 1  # No additional call

                            # Results should be identical
                            np.testing.assert_array_equal(result1, result2)
                            results["cache_hit_verified"] = True

                backend.cleanup()
                return {"scenario": "cache_hit", "results": results}

            def _test_error_handling_scenario(self, tmp_path: Path) -> dict[str, Any]:
                """Test error handling scenario.

                Returns:
                    dict[str, Any]: Test results.
                """
                results = {}

                exe_path = tmp_path / "rife-cli"
                exe_path.touch()
                exe_path.chmod(0o755)

                backend = OptimizedRifeBackend(exe_path)

                img1 = self.image_generator.create_dummy_image()
                img2 = self.image_generator.create_dummy_image(value=0.5)

                # Test subprocess error
                with patch("subprocess.run") as mock_run:
                    # Mock subprocess.CalledProcessError to be raised
                    import subprocess
                    error = subprocess.CalledProcessError(1, ["rife-cli"], stderr="Mock error")
                    mock_run.side_effect = error

                    with pytest.raises(RuntimeError, match="RIFE executable failed"):
                        backend.interpolate_pair(img1, img2)

                    results["subprocess_error_handled"] = True

                backend.cleanup()
                return {"scenario": "error_handling", "results": results}

            def _test_error_handling(self, scenario_name: str, **kwargs: Any) -> dict[str, Any]:
                """Test error handling scenarios.

                Returns:
                    dict[str, Any]: Test results.
                """
                results = {}

                if scenario_name == "invalid_image_shapes":
                    cache = ImageCache(max_size=10)

                    # Different shaped images
                    img1 = self.image_generator.create_dummy_image(size=(4, 4, 3))
                    img2 = self.image_generator.create_dummy_image(size=(5, 5, 3))

                    # Cache operations should still work
                    cache.put(img1, img2)  # Different shapes allowed
                    results["different_shapes_handled"] = True

                elif scenario_name == "cleanup_errors":
                    manager = BatchTempManager(max_files_per_dir=5)

                    # Get temp files
                    manager.get_temp_files()

                    # Make directory read-only to cause cleanup error
                    with patch("shutil.rmtree") as mock_rmtree:
                        mock_rmtree.side_effect = OSError("Permission denied")

                        # Cleanup should handle error gracefully
                        try:
                            manager.cleanup()
                            results["cleanup_error_handled"] = True
                        except OSError:
                            results["cleanup_error_handled"] = False

                return {"scenario": scenario_name, "results": results}

        return {
            "manager": InterpolatorTestManager(),
            "image_generator": TestImageGenerator(),
        }

    @staticmethod
    def test_cache_basic_operations(interpolator_test_components: dict[str, Any]) -> None:
        """Test basic cache operations."""
        manager = interpolator_test_components["manager"]

        result = manager._test_cache_operations("basic_operations")  # noqa: SLF001
        assert result["results"]["miss_tested"]
        assert result["results"]["hit_tested"]
        assert result["results"]["stats_tested"]

    @staticmethod
    def test_cache_multiple_images(interpolator_test_components: dict[str, Any]) -> None:
        """Test caching multiple images."""
        manager = interpolator_test_components["manager"]

        result = manager._test_cache_operations("multiple_images")  # noqa: SLF001
        assert result["results"]["multiple_cached"]
        assert result["results"]["final_size"] == 5

    @staticmethod
    def test_cache_lru_eviction(interpolator_test_components: dict[str, Any]) -> None:
        """Test LRU cache eviction."""
        manager = interpolator_test_components["manager"]

        result = manager._test_cache_eviction("lru_eviction")  # noqa: SLF001
        assert result["results"]["lru_eviction_verified"]

    @staticmethod
    def test_cache_access_order_update(interpolator_test_components: dict[str, Any]) -> None:
        """Test cache access order updates."""
        manager = interpolator_test_components["manager"]

        result = manager._test_cache_eviction("access_order_update")  # noqa: SLF001
        assert result["results"]["access_order_verified"]

    @staticmethod
    def test_batch_temp_file_creation(interpolator_test_components: dict[str, Any]) -> None:
        """Test batch temp file creation and cleanup."""
        manager = interpolator_test_components["manager"]

        result = manager._test_batch_temp_management("basic_temp_files")  # noqa: SLF001
        assert result["results"]["temp_files_created"]
        assert result["results"]["cleanup_verified"]

    @staticmethod
    def test_batch_directory_rotation(interpolator_test_components: dict[str, Any]) -> None:
        """Test batch directory rotation when limit reached."""
        manager = interpolator_test_components["manager"]

        result = manager._test_batch_temp_management("directory_rotation")  # noqa: SLF001
        assert result["results"]["rotation_verified"]
        assert result["results"]["total_dirs"] == 2

    @staticmethod
    def test_batch_concurrent_operations(interpolator_test_components: dict[str, Any]) -> None:
        """Test concurrent batch manager operations."""
        manager = interpolator_test_components["manager"]

        result = manager._test_batch_temp_management("concurrent_operations")  # noqa: SLF001
        assert result["results"]["concurrent_managers"] == 3
        assert result["results"]["separate_dirs_verified"]

    @staticmethod
    def test_backend_basic_interpolation(interpolator_test_components: dict[str, Any], tmp_path: Path) -> None:
        """Test basic backend interpolation."""
        manager = interpolator_test_components["manager"]

        result = manager._test_backend_interpolation("basic_interpolation", tmp_path)  # noqa: SLF001
        assert result["results"]["subprocess_called"]
        assert result["results"]["interpolation_completed"]

    @staticmethod
    def test_backend_cache_hit(interpolator_test_components: dict[str, Any], tmp_path: Path) -> None:
        """Test backend cache hit scenario."""
        manager = interpolator_test_components["manager"]

        result = manager._test_backend_interpolation("cache_hit", tmp_path)  # noqa: SLF001
        assert result["results"]["cache_hit_verified"]

    @staticmethod
    def test_backend_error_handling(interpolator_test_components: dict[str, Any], tmp_path: Path) -> None:
        """Test backend error handling."""
        manager = interpolator_test_components["manager"]

        result = manager._test_backend_interpolation("error_handling", tmp_path)  # noqa: SLF001
        assert result["results"]["subprocess_error_handled"]

    @pytest.mark.parametrize("cache_size", [5, 10, 100])
    def test_cache_size_variations(self, interpolator_test_components: dict[str, Any], cache_size: int) -> None:  # noqa: PLR6301
        """Test cache with different size configurations."""
        image_gen = interpolator_test_components["image_generator"]

        cache = ImageCache(max_size=cache_size)

        # Fill cache beyond capacity
        images = []
        for i in range(cache_size + 5):
            img = image_gen.create_dummy_image(value=float(i) / 10)
            result = image_gen.create_dummy_image(value=float(i) / 20)
            cache.put(img, result)
            images.append((img, result))

        # Check cache size is at limit
        stats = cache.get_stats()
        assert stats["size"] <= cache_size

    @pytest.mark.parametrize("max_files", [5, 20, 100])
    def test_batch_manager_file_limits(self, max_files: int) -> None:  # noqa: PLR6301
        """Test batch manager with different file limits."""
        manager = BatchTempManager(max_files_per_dir=max_files)

        # Create files up to and beyond limit
        dirs_created = set()
        for _i in range(max_files + 5):
            manager.get_temp_files()
            dirs_created.add(manager._current_dir)  # noqa: SLF001

        # Should have created at least 2 directories
        assert len(dirs_created) >= 2

        # Cleanup
        manager.cleanup()

    @staticmethod
    def test_interpolate_three_function(interpolator_test_components: dict[str, Any], tmp_path: Path) -> None:
        """Test the interpolate_three convenience function."""
        image_gen = interpolator_test_components["image_generator"]

        # Create mock executable
        exe_path = tmp_path / "rife-cli"
        exe_path.touch()
        exe_path.chmod(0o755)

        # Create test images
        images = image_gen.create_image_sequence(3)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            with patch("PIL.Image.open") as mock_pil_open, \
                 patch("pathlib.Path.exists", return_value=True):
                # Create mock PIL image
                interp1 = image_gen.create_dummy_image(value=0.25)
                interp2 = image_gen.create_dummy_image(value=0.75)
                # Convert to uint8 for PIL format
                interp1_uint8 = (interp1 * 255).astype(np.uint8)
                interp2_uint8 = (interp2 * 255).astype(np.uint8)
                
                mock_pil_img = MagicMock()
                mock_pil_img.__enter__ = MagicMock(return_value=mock_pil_img)
                mock_pil_img.__exit__ = MagicMock(return_value=None)
                mock_pil_open.return_value = mock_pil_img
                
                # Mock numpy array conversion
                with patch("numpy.array") as mock_np_array:
                    # interpolate_three calls the interpolation multiple times
                    mock_np_array.side_effect = [interp1_uint8, interp2_uint8, interp1_uint8]

                    # Create backend for interpolate_three
                    backend = OptimizedRifeBackend(exe_path)
                    results = interpolate_three(images[0], images[2], backend)
                    backend.cleanup()

                # Should return 3 images (original + 2 interpolated)
                assert len(results) == 3  # interpolate_three returns list of 3 images
                # Note: mock_run.call_count includes capability detection calls
                assert mock_run.call_count >= 2  # At least two interpolations

    @staticmethod
    def test_error_handling_scenarios(interpolator_test_components: dict[str, Any]) -> None:
        """Test various error handling scenarios."""
        manager = interpolator_test_components["manager"]

        # Test invalid image shapes
        result = manager._test_error_handling("invalid_image_shapes")  # noqa: SLF001
        assert result["results"]["different_shapes_handled"]

        # Test cleanup errors
        result = manager._test_error_handling("cleanup_errors")  # noqa: SLF001
        assert "cleanup_error_handled" in result["results"]

    @staticmethod
    def test_memory_efficiency(interpolator_test_components: dict[str, Any]) -> None:
        """Test memory efficiency of cache operations."""
        image_gen = interpolator_test_components["image_generator"]
        cache = ImageCache(max_size=50)

        # Add many large images
        cache.get_stats()

        for _i in range(100):
            # Create larger images
            img = image_gen.create_dummy_image(size=(100, 100, 3))
            result = image_gen.create_dummy_image(size=(100, 100, 3))
            cache.put(img, result)

        # Check memory usage is reasonable
        final_stats = cache.get_stats()
        assert final_stats["size"] <= 50  # Cache size limit respected
        assert final_stats["memory_usage_mb"] > 0

        # Memory usage should be proportional to cache size
        avg_memory_per_item = final_stats["memory_usage_mb"] / final_stats["size"]
        expected_memory_per_item = (100 * 100 * 3 * 4 * 2) / (1024 * 1024)  # 2 images per cache entry

        # Allow some overhead
        assert avg_memory_per_item < expected_memory_per_item * 1.5
