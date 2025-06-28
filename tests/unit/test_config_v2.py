"""
Optimized tests for configuration utilities with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures at class level
- Batch configuration operations
- Parameterized tests for similar scenarios
- Combined related test cases without losing granularity
"""

import pathlib
from unittest import mock

import pytest

from goesvfi.utils import config


class TestConfigOptimizedV2:
    """Optimized configuration tests with full coverage."""

    @pytest.fixture(scope="class")
    def sample_toml_content(self) -> str:
        """Shared TOML content for tests."""
        return """
output_dir = "/tmp/goesvfi_output"
cache_dir = "/tmp/goesvfi_cache"

[pipeline]
default_tile_size = 2048
supported_extensions = [".png"]

[sanchez]
bin_dir = "/tmp/sanchez"

[logging]
level = "INFO"
"""

    @pytest.fixture(scope="class")
    def minimal_toml_content(self) -> str:
        """Minimal TOML content for partial config tests."""
        return """
output_dir = "/tmp/out"
[pipeline]
default_tile_size = 512
"""

    def test_config_defaults_and_directory_creation(self, tmp_path) -> None:
        """Test default configuration loading and directory creation."""
        with mock.patch("pathlib.Path.exists", return_value=False):
            # Clear cache for test isolation
            config._load_config.cache_clear()

            # Test default output directory
            out_dir = config.get_output_dir()
            expected_default_out = pathlib.Path(config.DEFAULTS["output_dir"]).expanduser()
            assert out_dir == expected_default_out
            assert out_dir.is_dir()

            # Test default cache directory
            cache_dir = config.get_cache_dir()
            expected_default_cache = pathlib.Path(config.DEFAULTS["cache_dir"]).expanduser()
            assert cache_dir == expected_default_cache
            assert cache_dir.is_dir()

    def test_config_loading_from_file(self, monkeypatch, tmp_path, sample_toml_content) -> None:
        """Test configuration loading from TOML file."""
        # Create temp config file
        config_path = tmp_path / "config.toml"
        config_path.write_text(sample_toml_content)

        # Test environment variable override
        monkeypatch.setenv("GOESVFI_CONFIG_FILE", str(config_path))
        config._load_config.cache_clear()

        cfg = config._load_config()
        assert cfg["output_dir"] == "/tmp/goesvfi_output"
        assert cfg["cache_dir"] == "/tmp/goesvfi_cache"
        assert cfg["pipeline"]["default_tile_size"] == 2048
        assert cfg["pipeline"]["supported_extensions"] == [".png"]
        assert cfg["sanchez"]["bin_dir"] == "/tmp/sanchez"
        assert cfg["logging"]["level"] == "INFO"

        # Verify directories are created
        assert pathlib.Path(cfg["output_dir"]).exists()
        assert pathlib.Path(cfg["cache_dir"]).exists()

    def test_config_environment_overrides(self, monkeypatch, tmp_path, sample_toml_content) -> None:
        """Test configuration environment variable overrides."""
        # Test CONFIG_FILE override
        cfg_path = tmp_path / "alt.toml"
        cfg_path.write_text(sample_toml_content)
        monkeypatch.setenv("GOESVFI_CONFIG_FILE", str(cfg_path))
        config._load_config.cache_clear()

        cfg = config._load_config()
        assert cfg["output_dir"] == "/tmp/goesvfi_output"

        # Test CONFIG_DIR override
        cfg_dir = tmp_path / "conf"
        cfg_dir.mkdir()
        cfg_file = cfg_dir / "config.toml"
        cfg_file.write_text(sample_toml_content)
        monkeypatch.setenv("GOESVFI_CONFIG_DIR", str(cfg_dir))
        config._load_config.cache_clear()

        cfg = config._load_config()
        assert cfg["output_dir"] == "/tmp/goesvfi_output"

    def test_config_partial_merge_and_defaults(self, monkeypatch, tmp_path, minimal_toml_content) -> None:
        """Test partial configuration merging with defaults."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(minimal_toml_content)
        monkeypatch.setenv("GOESVFI_CONFIG_FILE", str(cfg_file))
        config._load_config.cache_clear()

        cfg = config._load_config()

        # Test overridden values
        assert cfg["output_dir"] == "/tmp/out"
        assert cfg["pipeline"]["default_tile_size"] == 512

        # Test defaults filled in for missing keys
        assert cfg["cache_dir"] == config.DEFAULTS["cache_dir"]
        assert cfg["pipeline"]["supported_extensions"] == config.DEFAULTS["pipeline"]["supported_extensions"]

    def test_config_error_handling(self, monkeypatch, tmp_path) -> None:
        """Test configuration error handling scenarios."""
        # Test invalid TOML
        invalid_config_path = tmp_path / "invalid.toml"
        invalid_config_path.write_text("invalid = [this is not valid toml")
        monkeypatch.setenv("GOESVFI_CONFIG_FILE", str(invalid_config_path))
        config._load_config.cache_clear()

        with pytest.raises(ValueError):
            config._load_config()

        # Test invalid config type
        bad_type_config = tmp_path / "bad_type.toml"
        bad_type_config.write_text("output_dir = 123")
        monkeypatch.setenv("GOESVFI_CONFIG_FILE", str(bad_type_config))
        config._load_config.cache_clear()

        with pytest.raises(ValueError):
            config._load_config()

        # Test missing required key handling
        missing_key_config = tmp_path / "missing.toml"
        missing_key_config.write_text("cache_dir='/tmp/cache'")
        monkeypatch.setenv("GOESVFI_CONFIG_FILE", str(missing_key_config))
        config._load_config.cache_clear()

        cfg = config._load_config()
        # Should fall back to default
        assert cfg["output_dir"] == str(pathlib.Path.home() / "Documents/goesvfi")

    def test_directory_getter_functions(self, monkeypatch, tmp_path, sample_toml_content) -> None:
        """Test directory getter functions."""
        config_path = tmp_path / "config.toml"
        config_path.write_text(sample_toml_content)
        monkeypatch.setattr(config, "CONFIG_FILE", config_path)
        config._load_config.cache_clear()

        # Test get_output_dir
        output_dir = config.get_output_dir()
        assert isinstance(output_dir, pathlib.Path)
        assert str(output_dir) == "/tmp/goesvfi_output"

        # Test get_cache_dir
        cache_dir = config.get_cache_dir()
        assert isinstance(cache_dir, pathlib.Path)
        assert str(cache_dir) == "/tmp/goesvfi_cache"

    @pytest.mark.parametrize(
        "which_result,bin_exists,model_exists,expected_pattern",
        [
            # Found in PATH
            ("/usr/bin/rife-ncnn-vulkan", False, False, "/usr/bin/rife-ncnn-vulkan"),
            # Found in bin directory
            (None, True, False, "bin/rife-cli"),
            # Found in model directory
            (None, False, True, "models/rife-v4.6/rife-cli"),
            # Not found anywhere
            (None, False, False, None),
        ],
    )
    def test_find_rife_executable_all_scenarios(self, which_result, bin_exists, model_exists, expected_pattern) -> None:
        """Test RIFE executable finding in all scenarios."""
        with (
            mock.patch("shutil.which", return_value=which_result) as mock_which,
            mock.patch("pathlib.Path.exists", autospec=True) as mock_exists,
        ):

            def exists_side_effect(self_path):
                path_str = str(self_path)
                if "bin/rife-cli" in path_str:
                    return bin_exists
                if "models/rife-v4.6/rife-cli" in path_str:
                    return model_exists
                return False

            mock_exists.side_effect = exists_side_effect

            if expected_pattern is None:
                # Should raise FileNotFoundError
                with pytest.raises(FileNotFoundError):
                    config.find_rife_executable("rife-v4.6")
            else:
                path = config.find_rife_executable("rife-v4.6")
                assert expected_pattern in str(path)

            mock_which.assert_called_once()

    def test_rife_executable_search_order(self) -> None:
        """Test RIFE executable search order and fallback behavior."""
        with (
            mock.patch("shutil.which") as mock_which,
            mock.patch("pathlib.Path.exists", autospec=True) as mock_exists,
        ):
            # Test PATH first
            mock_which.return_value = "/usr/bin/rife-ncnn-vulkan"
            path = config.find_rife_executable("rife-v4.6")
            assert path == pathlib.Path("/usr/bin/rife-ncnn-vulkan")
            mock_which.assert_called_once()

            # Reset mocks
            mock_which.reset_mock()
            mock_exists.reset_mock()

            # Test bin directory fallback
            mock_which.return_value = None

            def exists_side_effect(self_path):
                return "bin/rife-cli" in str(self_path)

            mock_exists.side_effect = exists_side_effect

            path = config.find_rife_executable("rife-v4.6")
            assert "bin/rife-cli" in str(path)
            assert mock_exists.call_count > 0

    def test_config_module_integration(self, monkeypatch, tmp_path) -> None:
        """Test complete configuration module integration."""
        # Create comprehensive config
        config_content = """
output_dir = "/tmp/integration_test/output"
cache_dir = "/tmp/integration_test/cache"

[pipeline]
default_tile_size = 4096
supported_extensions = [".png", ".jpg", ".tiff"]

[sanchez]
bin_dir = "/usr/local/bin/sanchez"

[logging]
level = "DEBUG"

[rife]
models_dir = "/opt/rife/models"
default_model = "rife-v4.6"
"""

        config_path = tmp_path / "integration.toml"
        config_path.write_text(config_content)
        monkeypatch.setenv("GOESVFI_CONFIG_FILE", str(config_path))
        config._load_config.cache_clear()

        # Test all configuration aspects
        cfg = config._load_config()

        # Verify all sections loaded correctly
        assert cfg["output_dir"] == "/tmp/integration_test/output"
        assert cfg["cache_dir"] == "/tmp/integration_test/cache"
        assert cfg["pipeline"]["default_tile_size"] == 4096
        assert cfg["pipeline"]["supported_extensions"] == [".png", ".jpg", ".tiff"]
        assert cfg["sanchez"]["bin_dir"] == "/usr/local/bin/sanchez"
        assert cfg["logging"]["level"] == "DEBUG"
        assert cfg["rife"]["models_dir"] == "/opt/rife/models"
        assert cfg["rife"]["default_model"] == "rife-v4.6"

        # Test getter functions work with integration config
        output_dir = config.get_output_dir()
        cache_dir = config.get_cache_dir()

        assert str(output_dir) == "/tmp/integration_test/output"
        assert str(cache_dir) == "/tmp/integration_test/cache"
        assert output_dir.exists()
        assert cache_dir.exists()

    def test_config_cache_behavior(self, monkeypatch, tmp_path, sample_toml_content) -> None:
        """Test configuration caching behavior."""
        config_path = tmp_path / "cache_test.toml"
        config_path.write_text(sample_toml_content)
        monkeypatch.setenv("GOESVFI_CONFIG_FILE", str(config_path))

        # Clear cache and load config
        config._load_config.cache_clear()
        cfg1 = config._load_config()

        # Load again - should be cached
        cfg2 = config._load_config()

        # Should be the same object due to caching
        assert cfg1 is cfg2
        assert cfg1["output_dir"] == "/tmp/goesvfi_output"

        # Clear cache and verify new load
        config._load_config.cache_clear()
        cfg3 = config._load_config()

        # Different object but same content
        assert cfg1 is not cfg3
        assert cfg1["output_dir"] == cfg3["output_dir"]
