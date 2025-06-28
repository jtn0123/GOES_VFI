"""Fast, optimized tests for configuration management - critical infrastructure."""

import os
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, mock_open, patch

import pytest

from goesvfi.utils.config import (
    DEFAULTS,
    EXPECTED_SCHEMA,
    FFMPEG_PROFILES,
    _load_config,
    _validate_config,
    get_cache_dir,
    get_config_path,
    get_output_dir,
)


class TestConfigManagement:
    """Test configuration loading and validation with fast, mocked operations."""

    @pytest.fixture()
    def mock_env_vars(self, monkeypatch) -> None:
        """Mock environment variables for testing."""
        monkeypatch.delenv("GOESVFI_CONFIG_DIR", raising=False)
        monkeypatch.delenv("GOESVFI_CONFIG_FILE", raising=False)

    @pytest.fixture()
    def temp_config_file(self):
        """Create temporary config file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False, encoding="utf-8") as f:
            yield f.name
        os.unlink(f.name)

    def test_get_config_path_default(self, mock_env_vars) -> None:
        """Test default config path when no environment variables are set."""
        path = get_config_path()

        assert path.name == "config.toml"
        assert ".config/goesvfi" in str(path)

    def test_get_config_path_custom_file(self, monkeypatch) -> None:
        """Test custom config file via environment variable."""
        custom_path = "/custom/path/config.toml"
        monkeypatch.setenv("GOESVFI_CONFIG_FILE", custom_path)

        path = get_config_path()

        assert str(path) == custom_path

    def test_get_config_path_custom_dir(self, monkeypatch) -> None:
        """Test custom config directory via environment variable."""
        custom_dir = "/custom/config/dir"
        monkeypatch.setenv("GOESVFI_CONFIG_DIR", custom_dir)

        path = get_config_path()

        assert str(path) == f"{custom_dir}/config.toml"

    def test_validate_config_valid_data(self) -> None:
        """Test validation with valid configuration data."""
        valid_data = DEFAULTS.copy()

        # Should not raise any exception
        _validate_config(valid_data)

        # Data should remain unchanged
        assert valid_data == DEFAULTS

    def test_validate_config_missing_sections(self) -> None:
        """Test validation with missing sections (should use defaults)."""
        incomplete_data = {
            "output_dir": "/some/path",
            # Missing other required sections
        }

        with pytest.raises(ValueError, match="Invalid configuration"):
            _validate_config(incomplete_data)

        # Should have been filled with defaults
        assert "cache_dir" in incomplete_data
        assert "pipeline" in incomplete_data

    def test_validate_config_wrong_types(self) -> None:
        """Test validation with wrong data types."""
        invalid_data = {
            "output_dir": 123,  # Should be string
            "cache_dir": "/valid/path",
            "pipeline": "not_a_dict",  # Should be dict
            "logging": {"level": 456},  # level should be string
        }

        with pytest.raises(ValueError, match="Invalid configuration"):
            _validate_config(invalid_data)

        # Should have been corrected with defaults
        assert isinstance(invalid_data["output_dir"], str)
        assert isinstance(invalid_data["pipeline"], dict)

    def test_validate_config_nested_validation(self) -> None:
        """Test validation of nested configuration sections."""
        data_with_bad_nested = DEFAULTS.copy()
        # Need to copy nested dicts too
        data_with_bad_nested["pipeline"] = data_with_bad_nested["pipeline"].copy()
        data_with_bad_nested["theme"] = data_with_bad_nested["theme"].copy()

        data_with_bad_nested["pipeline"]["default_tile_size"] = "not_an_int"
        data_with_bad_nested["theme"]["custom_overrides"] = "not_a_bool"

        with pytest.raises(ValueError, match="Invalid configuration"):
            _validate_config(data_with_bad_nested)

        # Should have been corrected after the exception was raised
        assert isinstance(data_with_bad_nested["pipeline"]["default_tile_size"], int)
        assert isinstance(data_with_bad_nested["theme"]["custom_overrides"], bool)

    def test_load_config_no_file(self, monkeypatch) -> None:
        """Test loading config when no file exists (should use defaults)."""
        # Mock a non-existent config file
        with patch("goesvfi.utils.config.get_config_path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = False
            mock_path.return_value = mock_file

            # Clear the cache
            _load_config.cache_clear()

            with patch("pathlib.Path.mkdir"):  # Mock directory creation
                config = _load_config()

        # Should return defaults
        assert config["output_dir"] == DEFAULTS["output_dir"]
        assert config["cache_dir"] == DEFAULTS["cache_dir"]

    def test_load_config_valid_toml(self, monkeypatch) -> None:
        """Test loading valid TOML configuration."""
        toml_content = """
        output_dir = "/custom/output"
        cache_dir = "/custom/cache"

        [pipeline]
        default_tile_size = 4096

        [logging]
        level = "DEBUG"
        """

        with patch("goesvfi.utils.config.get_config_path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.open.return_value.__enter__.return_value = mock_open(read_data=toml_content.encode()).return_value
            mock_path.return_value = mock_file

            # Clear the cache
            _load_config.cache_clear()

            with patch("pathlib.Path.mkdir"):  # Mock directory creation
                config = _load_config()

        assert config["output_dir"] == "/custom/output"
        assert config["cache_dir"] == "/custom/cache"
        assert config["pipeline"]["default_tile_size"] == 4096
        assert config["logging"]["level"] == "DEBUG"

    def test_load_config_invalid_toml(self, monkeypatch) -> None:
        """Test loading invalid TOML raises appropriate error."""
        invalid_toml = "invalid toml content ["

        with patch("goesvfi.utils.config.get_config_path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.open.return_value.__enter__.return_value = mock_open(read_data=invalid_toml.encode()).return_value
            mock_path.return_value = mock_file

            # Clear the cache
            _load_config.cache_clear()

            with pytest.raises(ValueError, match="Invalid TOML"):
                _load_config()

    def test_get_output_dir(self) -> None:
        """Test output directory retrieval."""
        with patch("goesvfi.utils.config._load_config") as mock_load:
            mock_load.return_value = {"output_dir": "/test/output"}

            result = get_output_dir()

            assert isinstance(result, Path)
            assert str(result) == "/test/output"

    def test_get_cache_dir(self) -> None:
        """Test cache directory retrieval."""
        with patch("goesvfi.utils.config._load_config") as mock_load:
            mock_load.return_value = {"cache_dir": "/test/cache"}

            result = get_cache_dir()

            assert isinstance(result, Path)
            assert str(result) == "/test/cache"

    def test_get_output_dir_fallback(self) -> None:
        """Test output directory fallback when config is malformed."""
        with patch("goesvfi.utils.config._load_config") as mock_load:
            mock_load.return_value = {"output_dir": 123}  # Wrong type

            result = get_output_dir()

            assert isinstance(result, Path)
            assert str(result) == DEFAULTS["output_dir"]

    def test_ffmpeg_profiles_structure(self) -> None:
        """Test FFmpeg profiles have correct structure."""
        assert "Default" in FFMPEG_PROFILES
        assert "Optimal" in FFMPEG_PROFILES
        assert "Optimal 2" in FFMPEG_PROFILES

        for profile_name, profile in FFMPEG_PROFILES.items():
            # Test required keys exist
            required_keys = [
                "use_ffmpeg_interp",
                "mi_mode",
                "mc_mode",
                "me_mode",
                "crf",
                "bitrate",
                "pix_fmt",
                "filter_preset",
            ]

            for key in required_keys:
                assert key in profile, f"Profile '{profile_name}' missing key '{key}'"

            # Test type constraints
            assert isinstance(profile["use_ffmpeg_interp"], bool)
            assert isinstance(profile["crf"], int)
            assert isinstance(profile["bitrate"], int)
            assert isinstance(profile["mi_mode"], str)

    def test_ffmpeg_profile_validation(self) -> None:
        """Test FFmpeg profile parameter validation."""
        profile = FFMPEG_PROFILES["Default"]

        # Test reasonable value ranges
        assert 0 <= profile["crf"] <= 51
        assert profile["bitrate"] > 0
        assert profile["pix_fmt"] in {"yuv420p", "yuv444p", "yuv422p"}
        assert profile["mi_mode"] in {"dup", "mci"}
        assert profile["mc_mode"] in {"obmc", "aobmc"}

    def test_config_schema_completeness(self) -> None:
        """Test that expected schema covers all defaults."""

        def check_schema_coverage(defaults_section, schema_section, path="") -> None:
            for key, value in defaults_section.items():
                full_path = f"{path}.{key}" if path else key
                assert key in schema_section, f"Schema missing key: {full_path}"

                if isinstance(value, dict):
                    assert isinstance(schema_section[key], dict), f"Schema type mismatch at {full_path}"
                    check_schema_coverage(value, schema_section[key], full_path)

        check_schema_coverage(DEFAULTS, EXPECTED_SCHEMA)

    def test_config_caching(self) -> None:
        """Test that config loading uses LRU cache correctly."""
        with patch("goesvfi.utils.config.get_config_path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = False
            mock_path.return_value = mock_file

            # Clear cache first
            _load_config.cache_clear()

            with patch("pathlib.Path.mkdir"):
                # First call
                config1 = _load_config()
                # Second call should use cache
                config2 = _load_config()

            # Should be the exact same object due to caching
            assert config1 is config2

            # get_config_path should only be called once due to caching
            assert mock_path.call_count == 1

    def test_path_expansion(self, monkeypatch) -> None:
        """Test that paths are properly expanded (~ and environment variables)."""
        monkeypatch.setenv("HOME", "/home/testuser")

        with patch("goesvfi.utils.config._load_config") as mock_load:
            mock_load.return_value = {"output_dir": "~/Documents/test"}

            result = get_output_dir()

            # Should expand ~ to home directory
            assert "testuser" in str(result)
            assert "~" not in str(result)

    def test_directory_creation_on_load(self) -> None:
        """Test that directories are created when config is loaded."""
        test_config = {
            "output_dir": "/test/output",
            "cache_dir": "/test/cache",
            "sanchez": {"bin_dir": "/test/sanchez"},
        }

        with patch("goesvfi.utils.config.get_config_path") as mock_path, patch("pathlib.Path.mkdir") as mock_mkdir:
            mock_file = MagicMock()
            mock_file.exists.return_value = False
            mock_path.return_value = mock_file

            _load_config.cache_clear()

            with (
                patch("goesvfi.utils.config._validate_config"),
                patch.dict("goesvfi.utils.config.DEFAULTS", test_config),
            ):
                _load_config()

            # Should have created directories
            assert mock_mkdir.call_count >= 3  # output, cache, sanchez dirs
