"""
Optimized tests for cache utilities with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures at class level
- Batch cache operations testing
- Combined related test scenarios
- Parameterized tests for error conditions
"""

from pathlib import Path
from typing import List

import numpy as np
import pytest

from goesvfi.pipeline import cache
from goesvfi.utils import config


class TestCacheUtilsOptimizedV2:
    """Optimized cache utilities tests with full coverage."""

    @pytest.fixture(scope="class")
    def shared_cache_dir(self, tmp_path_factory):
        """Shared cache directory for all tests."""
        return tmp_path_factory.mktemp("cache_test")

    @pytest.fixture()
    def sample_files(self, tmp_path: Path) -> tuple[Path, Path]:
        """Create sample test files."""
        file1 = tmp_path / "a.txt"
        file2 = tmp_path / "b.txt"
        file1.write_text("a")
        file2.write_text("b")
        return file1, file2

    @pytest.fixture()
    def cache_setup(self, shared_cache_dir, monkeypatch):
        """Setup cache configuration for tests."""
        monkeypatch.setattr(cache, "CACHE_DIR", shared_cache_dir)
        monkeypatch.setattr(config, "get_cache_dir", lambda: shared_cache_dir)
        return shared_cache_dir

    def _expected_paths(self, file1: Path, file2: Path, model_id: str, frame_count: int) -> List[Path]:
        """Helper to get expected cache file paths."""
        base_key = cache._hash_pair(file1, file2, model_id, frame_count)
        return [cache._get_cache_filepath(base_key, i, frame_count) for i in range(frame_count)]

    def test_save_and_load_cache_complete_workflow(self, cache_setup, sample_files) -> None:
        """Test complete cache save and load workflow with multiple scenarios."""
        file1, file2 = sample_files
        cache_dir = cache_setup
        
        # Test scenario 1: Basic cache operation
        model = "model"
        frame_count = 3
        arrays = [np.full((2, 2), i, dtype=np.float32) for i in range(frame_count)]
        
        cache.save_cache(file1, file2, model, frame_count, arrays)
        
        expected_paths = self._expected_paths(file1, file2, model, frame_count)
        for p in expected_paths:
            assert p.exists(), f"Expected cache file {p} to exist"
        
        loaded = cache.load_cached(file1, file2, model, frame_count)
        assert loaded is not None
        assert len(loaded) == frame_count
        for orig, result in zip(arrays, loaded):
            np.testing.assert_array_equal(orig, result)
        
        # Test scenario 2: Different model and frame count
        model2 = "different_model"
        frame_count2 = 5
        arrays2 = [np.random.rand(3, 3).astype(np.float32) for _ in range(frame_count2)]
        
        cache.save_cache(file1, file2, model2, frame_count2, arrays2)
        
        expected_paths2 = self._expected_paths(file1, file2, model2, frame_count2)
        for p in expected_paths2:
            assert p.exists()
        
        loaded2 = cache.load_cached(file1, file2, model2, frame_count2)
        assert loaded2 is not None
        assert len(loaded2) == frame_count2
        for orig, result in zip(arrays2, loaded2):
            np.testing.assert_array_equal(orig, result)
        
        # Test scenario 3: Verify original cache still exists
        loaded_original = cache.load_cached(file1, file2, model, frame_count)
        assert loaded_original is not None
        assert len(loaded_original) == frame_count

    def test_cache_different_array_types_and_shapes(self, cache_setup, sample_files) -> None:
        """Test caching with different array types and shapes."""
        file1, file2 = sample_files
        
        test_cases = [
            # (model_name, arrays_description, arrays)
            ("int32_model", "int32 arrays", [np.full((4, 4), i, dtype=np.int32) for i in range(2)]),
            ("float64_model", "float64 arrays", [np.full((3, 5), i * 0.5, dtype=np.float64) for i in range(3)]),
            ("uint8_model", "uint8 arrays", [np.full((2, 6), i * 10, dtype=np.uint8) for i in range(4)]),
            ("mixed_shape_model", "mixed shape arrays", [
                np.zeros((2, 2), dtype=np.float32),
                np.ones((3, 3), dtype=np.float32),
                np.full((4, 4), 2, dtype=np.float32)
            ]),
        ]
        
        for model, description, arrays in test_cases:
            frame_count = len(arrays)
            
            # Save cache
            cache.save_cache(file1, file2, model, frame_count, arrays)
            
            # Verify files exist
            expected_paths = self._expected_paths(file1, file2, model, frame_count)
            for p in expected_paths:
                assert p.exists(), f"Cache file {p} for {description} should exist"
            
            # Load and verify
            loaded = cache.load_cached(file1, file2, model, frame_count)
            assert loaded is not None, f"Failed to load {description}"
            assert len(loaded) == frame_count
            
            for orig, result in zip(arrays, loaded):
                np.testing.assert_array_equal(orig, result)

    def test_cache_error_scenarios(self, cache_setup, sample_files, caplog) -> None:
        """Test cache error handling scenarios."""
        file1, file2 = sample_files
        
        # Test 1: Array count mismatch
        arrays_mismatch = [np.zeros((2, 2))]
        cache.save_cache(file1, file2, "mismatch_model", 3, arrays_mismatch)
        
        # Should not create cache files
        expected_paths = self._expected_paths(file1, file2, "mismatch_model", 3)
        for p in expected_paths:
            assert not p.exists(), f"Cache file {p} should not exist due to mismatch"
        
        assert "Cache save called with mismatch" in caplog.text
        
        # Test 2: Empty arrays list
        caplog.clear()
        cache.save_cache(file1, file2, "empty_model", 0, [])
        # Should handle gracefully without error
        
        # Test 3: Load non-existent cache
        loaded_nonexistent = cache.load_cached(file1, file2, "nonexistent_model", 5)
        assert loaded_nonexistent is None

    def test_cache_corruption_and_recovery(self, cache_setup, sample_files) -> None:
        """Test cache corruption handling and recovery."""
        file1, file2 = sample_files
        model = "corruption_test"
        frame_count = 2
        arrays = [np.zeros((2, 2)), np.ones((2, 2))]
        
        # Save valid cache
        cache.save_cache(file1, file2, model, frame_count, arrays)
        
        # Verify it loads correctly first
        loaded = cache.load_cached(file1, file2, model, frame_count)
        assert loaded is not None
        assert len(loaded) == frame_count
        
        # Corrupt the first file
        first_path = cache._get_cache_filepath(cache._hash_pair(file1, file2, model, frame_count), 0, frame_count)
        assert first_path.exists()
        first_path.write_text("corrupt data")
        
        # Should return None due to corruption
        loaded_corrupted = cache.load_cached(file1, file2, model, frame_count)
        assert loaded_corrupted is None
        
        # Test recovery by re-saving
        cache.save_cache(file1, file2, model, frame_count, arrays)
        loaded_recovered = cache.load_cached(file1, file2, model, frame_count)
        assert loaded_recovered is not None
        assert len(loaded_recovered) == frame_count

    def test_cache_hash_uniqueness(self, cache_setup, sample_files) -> None:
        """Test that cache hashing creates unique keys for different inputs."""
        file1, file2 = sample_files
        
        # Create additional test files
        file3 = file1.parent / "c.txt"
        file3.write_text("c")
        
        # Test different file combinations
        hash1 = cache._hash_pair(file1, file2, "model", 3)
        hash2 = cache._hash_pair(file1, file3, "model", 3)  # Different file2
        hash3 = cache._hash_pair(file2, file1, "model", 3)  # Swapped files
        hash4 = cache._hash_pair(file1, file2, "different_model", 3)  # Different model
        hash5 = cache._hash_pair(file1, file2, "model", 5)  # Different frame count
        
        # All hashes should be unique
        hashes = [hash1, hash2, hash3, hash4, hash5]
        assert len(set(hashes)) == len(hashes), "All cache hashes should be unique"
        
        # Test that same inputs produce same hash
        hash1_repeat = cache._hash_pair(file1, file2, "model", 3)
        assert hash1 == hash1_repeat

    def test_cache_file_path_generation(self, cache_setup, sample_files) -> None:
        """Test cache file path generation for different scenarios."""
        file1, file2 = sample_files
        model = "path_test"
        
        # Test different frame counts
        for frame_count in [1, 5, 10, 100]:
            base_key = cache._hash_pair(file1, file2, model, frame_count)
            
            # Generate all expected paths
            paths = []
            for i in range(frame_count):
                path = cache._get_cache_filepath(base_key, i, frame_count)
                paths.append(path)
                
                # Verify path format
                assert path.suffix == ".npy"
                assert str(path).startswith(str(cache_setup))
                
            # All paths should be unique
            assert len(set(paths)) == frame_count

    def test_cache_large_array_handling(self, cache_setup, sample_files) -> None:
        """Test cache handling of larger arrays."""
        file1, file2 = sample_files
        model = "large_array_test"
        
        # Create larger arrays
        large_arrays = [
            np.random.rand(100, 100).astype(np.float32),
            np.random.rand(150, 80).astype(np.float32),
            np.random.rand(200, 50).astype(np.float32),
        ]
        frame_count = len(large_arrays)
        
        # Save large arrays
        cache.save_cache(file1, file2, model, frame_count, large_arrays)
        
        # Verify cache files exist
        expected_paths = self._expected_paths(file1, file2, model, frame_count)
        for p in expected_paths:
            assert p.exists()
            # Check file size is reasonable for the array
            assert p.stat().st_size > 1000  # Should be substantial size
        
        # Load and verify
        loaded = cache.load_cached(file1, file2, model, frame_count)
        assert loaded is not None
        assert len(loaded) == frame_count
        
        for orig, result in zip(large_arrays, loaded):
            np.testing.assert_array_equal(orig, result)
            assert orig.shape == result.shape
            assert orig.dtype == result.dtype

    def test_cache_edge_cases(self, cache_setup, sample_files) -> None:
        """Test cache edge cases and boundary conditions."""
        file1, file2 = sample_files
        
        # Test with single frame
        single_array = [np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)]
        cache.save_cache(file1, file2, "single_frame", 1, single_array)
        loaded_single = cache.load_cached(file1, file2, "single_frame", 1)
        assert loaded_single is not None
        assert len(loaded_single) == 1
        np.testing.assert_array_equal(single_array[0], loaded_single[0])
        
        # Test with very small arrays
        tiny_arrays = [np.array([[0.5]], dtype=np.float32) for _ in range(3)]
        cache.save_cache(file1, file2, "tiny_arrays", 3, tiny_arrays)
        loaded_tiny = cache.load_cached(file1, file2, "tiny_arrays", 3)
        assert loaded_tiny is not None
        assert len(loaded_tiny) == 3
        
        # Test with arrays containing special values
        special_arrays = [
            np.array([[np.inf, -np.inf], [0.0, -0.0]], dtype=np.float32),
            np.array([[np.nan, 1.0], [2.0, 3.0]], dtype=np.float32),
        ]
        cache.save_cache(file1, file2, "special_values", 2, special_arrays)
        loaded_special = cache.load_cached(file1, file2, "special_values", 2)
        assert loaded_special is not None
        assert len(loaded_special) == 2
        
        # Verify special values are preserved (excluding NaN comparison)
        assert np.isinf(loaded_special[0][0, 0])
        assert np.isnan(loaded_special[1][0, 0])

    def test_cache_concurrent_access_simulation(self, cache_setup, sample_files) -> None:
        """Test cache behavior under simulated concurrent access scenarios."""
        file1, file2 = sample_files
        
        # Simulate multiple "processes" trying to cache different data
        scenarios = [
            ("process1", "model_a", 2, [np.ones((2, 2)) * 1, np.ones((2, 2)) * 2]),
            ("process2", "model_b", 3, [np.ones((3, 3)) * i for i in range(3)]),
            ("process3", "model_c", 4, [np.random.rand(4, 4) for _ in range(4)]),
        ]
        
        # Save all caches
        for process_name, model, frame_count, arrays in scenarios:
            cache.save_cache(file1, file2, model, frame_count, arrays)
        
        # Verify all caches can be loaded independently
        for process_name, model, frame_count, original_arrays in scenarios:
            loaded = cache.load_cached(file1, file2, model, frame_count)
            assert loaded is not None, f"Failed to load cache for {process_name}"
            assert len(loaded) == frame_count
            
            for orig, result in zip(original_arrays, loaded):
                np.testing.assert_array_equal(orig, result)