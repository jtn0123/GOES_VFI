"""Optimized tests for cache functionality - v2."""

import time
from typing import Any, Never

import numpy as np
import pytest

from goesvfi.pipeline import cache
from goesvfi.utils import config
from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)


# Shared fixtures and test data
@pytest.fixture(scope="session")
def cache_test_scenarios() -> dict[str, Any]:
    """Pre-defined test scenarios for cache operations.

    Returns:
        dict[str, Any]: Test scenarios data.
    """
    return {
        "basic": {
            "model_id": "modelA",
            "num_frames": 3,
            "content1": "content1",
            "content2": "content2",
        },
        "large": {
            "model_id": "modelB",
            "num_frames": 100,
            "content1": "large_content_1",
            "content2": "large_content_2",
        },
        "minimal": {
            "model_id": "modelC",
            "num_frames": 1,
            "content1": "min1",
            "content2": "min2",
        },
    }


@pytest.fixture()
def sample_paths(tmp_path: Any, cache_test_scenarios: Any) -> dict[str, Any]:
    """Create sample files with different content for testing.

    Returns:
        dict[str, Any]: Sample file paths and data.
    """
    scenarios = cache_test_scenarios

    # Create files for each scenario
    files = {}
    for scenario_name, scenario_data in scenarios.items():
        file1 = tmp_path / f"file1_{scenario_name}.txt"
        file2 = tmp_path / f"file2_{scenario_name}.txt"
        file1.write_text(scenario_data["content1"])
        file2.write_text(scenario_data["content2"])
        files[scenario_name] = (file1, file2)

    return files


@pytest.fixture()
def mock_cache_dir(tmp_path: Any, monkeypatch: Any) -> Any:
    """Mock cache directory for testing.

    Returns:
        Any: Mock cache directory path.
    """
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(exist_ok=True)

    monkeypatch.setattr(cache, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(config, "get_cache_dir", lambda: cache_dir)

    return cache_dir


class TestCacheOperations:
    """Test cache operations with optimized patterns."""

    @pytest.mark.parametrize("scenario", ["basic", "large", "minimal"])
    def test_hash_pair_consistency(self, sample_paths: Any, cache_test_scenarios: Any, scenario: str) -> None:  # noqa: PLR6301
        """Test hash pair consistency across different scenarios."""
        file1, file2 = sample_paths[scenario]
        scenario_data = cache_test_scenarios[scenario]
        model_id = scenario_data["model_id"]
        num_frames = scenario_data["num_frames"]

        # Multiple calls should produce same hash
        hash1 = cache._hash_pair(file1, file2, model_id, num_frames)  # noqa: SLF001
        hash2 = cache._hash_pair(file1, file2, model_id, num_frames)  # noqa: SLF001
        assert hash1 == hash2

        # Different order should produce different hash
        hash3 = cache._hash_pair(file2, file1, model_id, num_frames)  # noqa: SLF001
        assert hash1 != hash3

    @pytest.mark.parametrize(
        "total_frames,frame_index",
        [
            (5, 0),  # First frame
            (5, 2),  # Middle frame
            (5, 4),  # Last frame
            (100, 42),  # Large cache
            (1, 0),  # Single frame
        ],
    )
    def test_get_cache_filepath_formatting(self, tmp_path: Any, total_frames: int, frame_index: int) -> None:  # noqa: PLR6301, ARG002
        """Test cache filepath formatting with different parameters."""
        base_key = "abc123"
        expected_digits = len(str(total_frames - 1))
        expected_filename = f"{base_key}_k{total_frames}_frame{frame_index:0{expected_digits}}.npy"

        path = cache._get_cache_filepath(base_key, frame_index, total_frames)  # noqa: SLF001
        assert path.name == expected_filename

    @pytest.mark.parametrize(
        "num_frames,should_return_none",
        [
            (0, True),  # Zero frames should return None
            (1, False),  # One frame should work
            (5, False),  # Multiple frames should work
        ],
    )
    def test_load_cached_frame_count_validation(  # noqa: PLR6301
        self, sample_paths: Any, mock_cache_dir: Any, num_frames: int, should_return_none: bool  # noqa: FBT001, ARG002
    ) -> None:
        """Test load_cached behavior with different frame counts."""
        file1, file2 = sample_paths["basic"]
        result = cache.load_cached(file1, file2, "modelA", num_frames)

        if should_return_none:
            assert result is None
        # For non-zero frames with no cache files, should also return None (cache miss)

    def test_load_cached_cache_miss_scenarios(self, sample_paths: Any, mock_cache_dir: Any) -> None:  # noqa: PLR6301, ARG002
        """Test cache miss scenarios when files are missing."""
        file1, file2 = sample_paths["basic"]
        num_frames = 3

        # No cache files exist, should return None
        result = cache.load_cached(file1, file2, "modelA", num_frames)
        assert result is None

    @pytest.mark.parametrize("scenario", ["basic", "minimal"])
    def test_save_and_load_cache_roundtrip(  # noqa: PLR6301
        self, sample_paths: Any, mock_cache_dir: Any, cache_test_scenarios: Any, scenario: str  # noqa: ARG002
    ) -> None:
        """Test complete save and load roundtrip for different scenarios."""
        file1, file2 = sample_paths[scenario]
        scenario_data = cache_test_scenarios[scenario]
        model_id = scenario_data["model_id"]
        num_frames = scenario_data["num_frames"]

        # Create frames with different patterns for each scenario
        if scenario == "basic":
            frames = [np.ones((2, 2)) * i for i in range(num_frames)]
        elif scenario == "minimal":
            frames = [np.zeros((3, 3))]  # Single frame
        else:
            rng = np.random.default_rng()
            frames = [rng.random((4, 4)) for _ in range(num_frames)]

        # Save cache
        cache.save_cache(file1, file2, model_id, num_frames, frames)

        # Load cache should return the same frames
        loaded_frames = cache.load_cached(file1, file2, model_id, num_frames)
        assert loaded_frames is not None
        assert len(loaded_frames) == num_frames

        for original, loaded in zip(frames, loaded_frames, strict=False):
            np.testing.assert_array_equal(original, loaded)

    @pytest.mark.parametrize(
        "num_frames,frame_count,should_warn",
        [
            (3, 1, True),  # Mismatch - should warn
            (3, 3, False),  # Match - should not warn
            (1, 1, False),  # Single frame match
            (5, 2, True),  # Large mismatch
        ],
    )
    def test_save_cache_mismatch_validation(  # noqa: PLR6301
        self, sample_paths: Any, mock_cache_dir: Any, caplog: Any, num_frames: int, frame_count: int, should_warn: bool  # noqa: FBT001, ARG002
    ) -> None:
        """Test save cache validation with frame count mismatches."""
        file1, file2 = sample_paths["basic"]
        model_id = "modelA"
        frames = [np.ones((2, 2)) for _ in range(frame_count)]

        LOGGER.debug(
            "Testing save_cache with num_frames: %s, actual frames: %s",
            num_frames,
            len(frames),
        )

        cache.save_cache(file1, file2, model_id, num_frames, frames)

        if should_warn:
            assert "Cache save called with mismatch" in caplog.text
        else:
            assert "Cache save called with mismatch" not in caplog.text

    def test_load_cached_error_handling(self, sample_paths: Any, mock_cache_dir: Any, caplog: Any, monkeypatch: Any) -> None:  # noqa: PLR6301, ARG002
        """Test load_cached error handling with corrupted files."""
        file1, file2 = sample_paths["basic"]
        model_id = "modelA"
        num_frames = 1

        # Save a valid frame first
        frame = np.ones((2, 2))
        cache.save_cache(file1, file2, model_id, num_frames, [frame])

        # Mock np.load to raise an exception to simulate corrupted file
        def raise_io_error(path: Any) -> Never:  # noqa: ARG001
            msg = "Simulated load error"
            raise OSError(msg)

        monkeypatch.setattr(np, "load", raise_io_error)

        result = cache.load_cached(file1, file2, model_id, num_frames)
        assert result is None
        assert "Error loading cache files" in caplog.text

    @pytest.mark.parametrize(
        "operation_sequence",
        [
            [("save", "modelA", 3), ("load", "modelA", 3), ("save", "modelB", 2)],
            [("load", "missing", 1), ("save", "test", 1), ("load", "test", 1)],
            [("save", "bulk", 5), ("load", "bulk", 5), ("load", "bulk", 5)],  # Multiple loads
        ],
    )
    def test_cache_operation_sequences(self, sample_paths: Any, mock_cache_dir: Any, operation_sequence: list[tuple]) -> None:  # noqa: PLR6301, ARG002
        """Test sequences of cache operations for robustness."""
        file1, file2 = sample_paths["basic"]
        saved_frames = {}

        for operation, model_id, num_frames in operation_sequence:
            if operation == "save":
                frames = [np.ones((2, 2)) * i for i in range(num_frames)]
                cache.save_cache(file1, file2, model_id, num_frames, frames)
                saved_frames[model_id] = frames
            elif operation == "load":
                result = cache.load_cached(file1, file2, model_id, num_frames)

                if model_id in saved_frames:
                    assert result is not None
                    assert len(result) == num_frames
                    for orig, loaded in zip(saved_frames[model_id], result, strict=False):
                        np.testing.assert_array_equal(orig, loaded)
                else:
                    # Should be None for non-existent cache
                    assert result is None

    @pytest.mark.parametrize("stress_level", [5, 10, 20])
    def test_cache_performance_stress(self, sample_paths: Any, mock_cache_dir: Any, stress_level: int) -> None:  # noqa: PLR6301, ARG002
        """Test cache performance under stress conditions."""

        file1, file2 = sample_paths["basic"]

        # Test multiple rapid saves
        start_time = time.time()
        for i in range(stress_level):
            model_id = f"stress_model_{i}"
            frames = [np.ones((2, 2)) * j for j in range(3)]
            cache.save_cache(file1, file2, model_id, 3, frames)
        save_time = time.time() - start_time

        # Test multiple rapid loads
        start_time = time.time()
        for i in range(stress_level):
            model_id = f"stress_model_{i}"
            result = cache.load_cached(file1, file2, model_id, 3)
            assert result is not None
        load_time = time.time() - start_time

        # Should complete in reasonable time
        assert save_time < 2.0  # Less than 2 seconds for saves
        assert load_time < 1.0  # Less than 1 second for loads

    @pytest.mark.parametrize("cache_size", [1, 10, 50])
    def test_cache_storage_efficiency(self, sample_paths: Any, mock_cache_dir: Any, cache_size: int) -> None:  # noqa: PLR6301
        """Test cache storage efficiency with different sizes."""
        file1, file2 = sample_paths["basic"]

        # Create caches of different sizes
        for i in range(cache_size):
            model_id = f"efficiency_model_{i}"
            frames = [np.ones((3, 3)) * j for j in range(2)]  # 2 frames each
            cache.save_cache(file1, file2, model_id, 2, frames)

        # Verify all caches can be loaded
        for i in range(cache_size):
            model_id = f"efficiency_model_{i}"
            result = cache.load_cached(file1, file2, model_id, 2)
            assert result is not None
            assert len(result) == 2

        # Check cache directory contains expected number of files
        cache_files = list(mock_cache_dir.glob("*.npy"))
        assert len(cache_files) == cache_size * 2  # 2 frames per model
