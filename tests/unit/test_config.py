import builtins
import os
import pathlib
import sys

# import toml # Removed unnecessary import for Python 3.11+
from unittest import mock

import pytest

from goesvfi.utils import config


@pytest.fixture
def sample_toml_content():
    return """
output_dir = "/tmp/goesvfi_output"
cache_dir = "/tmp/goesvfi_cache"
"""


@mock.patch("pathlib.Path.exists", return_value=False)
def test_load_config_defaults(mock_exists, monkeypatch, tmp_path):
    # Patching exists globally, no need for monkeypatch setattr
    # monkeypatch.setattr(config.CONFIG_FILE, "exists", lambda: False)

    # Ensure _load_config cache is cleared for test isolation
    config._load_config.cache_clear()

    # Act: Call a function that uses _load_config
    out_dir = config.get_output_dir()

    # Assert: Defaults are used and directory created (get_output_dir ensures creation)
    expected_default_out = pathlib.Path(config.DEFAULTS["output_dir"]).expanduser()
    assert out_dir == expected_default_out
    assert mock_exists.called  # Check that exists was called (on CONFIG_FILE path)
    assert out_dir.is_dir()  # Check dir creation


def test_load_config_from_file(monkeypatch, tmp_path, sample_toml_content):
    # Create a temp config file with sample TOML content
    config_path = tmp_path / "config.toml"
    config_path.write_text(sample_toml_content)

    # Patch CONFIG_FILE to point to temp config file
    monkeypatch.setattr(config, "CONFIG_FILE", config_path)
    # Clear cache to reload config
    config._load_config.cache_clear()
    cfg = config._load_config()
    assert cfg["output_dir"] == "/tmp/goesvfi_output"
    assert cfg["cache_dir"] == "/tmp/goesvfi_cache"
    # Directories should exist
    assert pathlib.Path(cfg["output_dir"]).exists()
    assert pathlib.Path(cfg["cache_dir"]).exists()


def test_load_config_invalid_toml(monkeypatch, tmp_path):
    # Create a temp config file with invalid TOML content
    config_path = tmp_path / "config.toml"
    config_path.write_text("invalid = [this is not valid toml")

    # Patch CONFIG_FILE to point to temp config file
    monkeypatch.setattr(config, "CONFIG_FILE", config_path)
    # Clear cache to reload config
    config._load_config.cache_clear()
    cfg = config._load_config()
    # Should fallback to defaults
    assert cfg["output_dir"] == str(pathlib.Path.home() / "Documents/goesvfi")
    assert cfg["cache_dir"] == str(pathlib.Path.home() / "Documents/goesvfi/cache")


def test_get_output_dir(monkeypatch, tmp_path, sample_toml_content):
    config_path = tmp_path / "config.toml"
    config_path.write_text(sample_toml_content)
    monkeypatch.setattr(config, "CONFIG_FILE", config_path)
    config._load_config.cache_clear()
    output_dir = config.get_output_dir()
    assert isinstance(output_dir, pathlib.Path)
    assert str(output_dir) == "/tmp/goesvfi_output"


def test_get_cache_dir(monkeypatch, tmp_path, sample_toml_content):
    config_path = tmp_path / "config.toml"
    config_path.write_text(sample_toml_content)
    monkeypatch.setattr(config, "CONFIG_FILE", config_path)
    config._load_config.cache_clear()
    cache_dir = config.get_cache_dir()
    assert isinstance(cache_dir, pathlib.Path)
    assert str(cache_dir) == "/tmp/goesvfi_cache"


@mock.patch("shutil.which")
@mock.patch("pathlib.Path.exists")
def test_find_rife_executable_in_path(mock_exists, mock_which):
    # Simulate executable found in PATH
    mock_which.return_value = "/usr/bin/rife-ncnn-vulkan"
    path = config.find_rife_executable("rife-v4.6")
    assert path == pathlib.Path("/usr/bin/rife-ncnn-vulkan")
    mock_which.assert_called_once()


@mock.patch("shutil.which")
@mock.patch("pathlib.Path.exists", autospec=True)
def test_find_rife_executable_in_bin_dir(mock_exists, mock_which):
    # Simulate not found in PATH
    mock_which.return_value = None

    # Simulate bin fallback exists
    def exists_side_effect(self_path):
        if "bin/rife-cli" in str(self_path):
            return True
        return False

    mock_exists.side_effect = exists_side_effect

    path = config.find_rife_executable("rife-v4.6")
    assert "bin/rife-cli" in str(path)
    mock_which.assert_called_once()
    assert mock_exists.call_count > 0


@mock.patch("shutil.which")
@mock.patch("pathlib.Path.exists", autospec=True)
def test_find_rife_executable_in_model_dir(mock_exists, mock_which):
    # Simulate not found in PATH or bin dir
    mock_which.return_value = None

    def exists_side_effect(self_path):
        if "bin/rife-cli" in str(self_path):
            return False
        if "models/rife-v4.6/rife-ncnn-vulkan" in str(self_path):
            return True
        return False

    mock_exists.side_effect = exists_side_effect

    path = config.find_rife_executable("rife-v4.6")
    assert "rife-ncnn-vulkan" in str(path)
    mock_which.assert_called_once()
    assert mock_exists.call_count > 0


@mock.patch("shutil.which")
@mock.patch("pathlib.Path.exists")
def test_find_rife_executable_not_found(mock_exists, mock_which):
    # Simulate not found anywhere
    mock_which.return_value = None
    mock_exists.return_value = False

    with pytest.raises(FileNotFoundError):
        config.find_rife_executable("rife-v4.6")
