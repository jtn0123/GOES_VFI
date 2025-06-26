
import pytest

from goesvfi.utils.validation import validate_path_exists, validate_positive_int


def test_validate_path_exists_ok(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    result = validate_path_exists(d, must_be_dir=True)
    assert result == d


def test_validate_path_exists_missing(tmp_path):
    p = tmp_path / "missing"
    with pytest.raises(FileNotFoundError):
        validate_path_exists(p, must_be_dir=True)


def test_validate_positive_int_ok():
    assert validate_positive_int(5, "value") == 5


def test_validate_positive_int_invalid():
    with pytest.raises(ValueError):
        validate_positive_int(0, "value")
    with pytest.raises(TypeError):
        validate_positive_int("1", "value")
