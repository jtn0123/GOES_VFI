from pathlib import Path
from typing import List

import numpy as np
import pytest

from goesvfi.pipeline import cache
from goesvfi.utils import config


@pytest.fixture()
def sample_files(tmp_path: Path) -> tuple[Path, Path]:
    file1 = tmp_path / "a.txt"
    file2 = tmp_path / "b.txt"
    file1.write_text("a")
    file2.write_text("b")
    return file1, file2


def _expected_paths(file1: Path, file2: Path, model_id: str, frame_count: int) -> List[Path]:
    base_key = cache._hash_pair(file1, file2, model_id, frame_count)
    return [cache._get_cache_filepath(base_key, i, frame_count) for i in range(frame_count)]


def test_save_and_load_arrays(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_files: tuple[Path, Path]) -> None:
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(config, "get_cache_dir", lambda: tmp_path)
    file1, file2 = sample_files
    model = "model"
    frame_count = 3
    arrays = [np.full((2, 2), i, dtype=np.float32) for i in range(frame_count)]

    cache.save_cache(file1, file2, model, frame_count, arrays)

    expected_paths = _expected_paths(file1, file2, model, frame_count)
    for p in expected_paths:
        assert p.exists(), f"Expected cache file {p} to exist"

    loaded = cache.load_cached(file1, file2, model, frame_count)
    assert loaded is not None
    assert len(loaded) == frame_count
    for orig, result in zip(arrays, loaded):
        np.testing.assert_array_equal(orig, result)


def test_save_cache_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sample_files: tuple[Path, Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(config, "get_cache_dir", lambda: tmp_path)
    file1, file2 = sample_files
    arrays = [np.zeros((2, 2))]

    cache.save_cache(file1, file2, "m", 3, arrays)

    assert not list(tmp_path.glob("*.npy"))
    assert "Cache save called with mismatch" in caplog.text


def test_load_cached_corrupted_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_files: tuple[Path, Path]
) -> None:
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(config, "get_cache_dir", lambda: tmp_path)
    file1, file2 = sample_files
    arrays = [np.zeros((2, 2)), np.ones((2, 2))]
    cache.save_cache(file1, file2, "m", 2, arrays)

    # Corrupt the first file
    first_path = cache._get_cache_filepath(cache._hash_pair(file1, file2, "m", 2), 0, 2)
    first_path.write_text("corrupt")

    assert cache.load_cached(file1, file2, "m", 2) is None
