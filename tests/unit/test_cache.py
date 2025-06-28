import pathlib
from typing import Never
from unittest.mock import patch

import numpy as np
import pytest

from goesvfi.pipeline import cache
from goesvfi.utils import config
from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)


@pytest.fixture()
def sample_paths(tmp_path):
    # Create two dummy files with some content for hashing
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    file1.write_text("content1")
    file2.write_text("content2")
    return file1, file2


def test_hash_pair_consistency(sample_paths) -> None:
    file1, file2 = sample_paths
    model_id = "modelA"
    num_frames = 3
    hash1 = cache._hash_pair(file1, file2, model_id, num_frames)
    hash2 = cache._hash_pair(file1, file2, model_id, num_frames)
    assert hash1 == hash2
    # Changing any input changes the hash
    hash3 = cache._hash_pair(file2, file1, model_id, num_frames)
    assert hash1 != hash3


def test_get_cache_filepath(tmp_path) -> None:
    base_key = "abc123"
    index = 5
    total_frames = 100
    expected_digits = len(str(total_frames - 1))
    expected_path = cache.CACHE_DIR / f"{base_key}_k{total_frames}_frame{index:0{expected_digits}}.npy"
    path = cache._get_cache_filepath(base_key, index, total_frames)
    assert path.name == expected_path.name


@patch(
    "goesvfi.pipeline.cache.CACHE_DIR",
    new_callable=lambda: pathlib.Path("/tmp/fake_cache_dir"),
)
def test_load_cached_none_for_zero_frames(mock_cache_dir, sample_paths) -> None:
    file1, file2 = sample_paths
    result = cache.load_cached(file1, file2, "modelA", 0)
    assert result is None


def test_load_cached_cache_miss_when_files_missing(monkeypatch, sample_paths, tmp_path) -> None:
    # Patch cache directory to temporary path
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(config, "get_cache_dir", lambda: tmp_path)
    file1, file2 = sample_paths
    num_frames = 3

    # No cache files exist, should return None
    result = cache.load_cached(file1, file2, "modelA", num_frames)
    assert result is None


def test_save_and_load_cache_roundtrip(monkeypatch, sample_paths, tmp_path) -> None:
    # Use monkeypatch to set CACHE_DIR within the module
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    file1, file2 = sample_paths
    model_id = "modelA"
    num_frames = 3

    # Create dummy frames as numpy arrays
    frames = [np.ones((2, 2)) * i for i in range(num_frames)]

    # Save cache
    cache.save_cache(file1, file2, model_id, num_frames, frames)

    # Load cache should return the same frames
    loaded_frames = cache.load_cached(file1, file2, model_id, num_frames)
    assert loaded_frames is not None
    assert len(loaded_frames) == num_frames
    for original, loaded in zip(frames, loaded_frames, strict=False):
        np.testing.assert_array_equal(original, loaded)


@patch("goesvfi.pipeline.cache.CACHE_DIR")
def test_save_cache_mismatch_length_warns_and_does_nothing(mock_cache_dir, sample_paths, caplog) -> None:
    mock_cache_dir.return_value = pathlib.Path("/tmp/fake_cache_dir")
    file1, file2 = sample_paths
    model_id = "modelA"
    num_frames = 3
    frames = [np.ones((2, 2))]  # length 1, mismatch with num_frames=3

    LOGGER.debug(
        "test_save_cache_mismatch_length_warns_and_does_nothing - num_frames: %s, frames length: %s",
        num_frames,
        len(frames),
    )
    cache.save_cache(file1, file2, model_id, num_frames, frames)

    # Check log messages using caplog
    assert "Cache save called with mismatch" in caplog.text


@patch("goesvfi.pipeline.cache.pathlib.Path")
def test_load_cached_handles_load_error(_mock_Path, monkeypatch, sample_paths, tmp_path, caplog) -> None:
    # Use monkeypatch to set the module-level CACHE_DIR value for the test duration
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)

    file1, file2 = sample_paths
    model_id = "modelA"
    num_frames = 1

    # Save a valid frame first
    frame = np.ones((2, 2))
    cache.save_cache(file1, file2, model_id, num_frames, [frame])

    # Monkeypatch np.load to raise an exception to simulate corrupted file
    def raise_io_error(path) -> Never:
        msg = "Simulated load error"
        raise OSError(msg)

    monkeypatch.setattr(np, "load", raise_io_error)

    result = cache.load_cached(file1, file2, model_id, num_frames)
    assert result is None
    assert "Error loading cache files" in caplog.text
