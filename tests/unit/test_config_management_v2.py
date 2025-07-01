"""Fast, optimized tests for configuration management - Optimized v2."""

from pathlib import Path
import time
from typing import Any
from unittest.mock import MagicMock, mock_open, patch

import pytest

from goesvfi.utils.config import (
    DEFAULTS,
    EXPECTED_SCHEMA,
    FFMPEG_PROFILES,
    _load_config,  # noqa: PLC2701
    _validate_config,  # noqa: PLC2701
    get_cache_dir,
    get_config_path,
    get_output_dir,
)


# Shared fixtures and test data
@pytest.fixture(scope="session")
def config_scenarios() -> dict[str, Any]:
    """Pre-defined configuration scenarios for testing.

    Returns:
        dict[str, Any]: Configuration scenarios.
    """
    return {
        "valid_minimal": {
            "output_dir": "/test/output",
            "cache_dir": "/test/cache",
            "pipeline": {"default_tile_size": 2048},
            "logging": {"level": "INFO"},
            "theme": {"custom_overrides": False},
        },
        "valid_complete": DEFAULTS.copy(),
        "invalid_types": {
            "output_dir": 123,  # Should be string
            "cache_dir": "/valid/path",
            "pipeline": "not_a_dict",  # Should be dict
            "logging": {"level": 456},  # level should be string
        },
        "missing_sections": {
            "output_dir": "/some/path",
            # Missing other required sections
        },
    }


@pytest.fixture(scope="session")
def toml_content_scenarios() -> dict[str, str]:
    """Pre-defined TOML content scenarios for testing.

    Returns:
        dict[str, str]: TOML content scenarios.
    """
    return {
        "valid_basic": """
        output_dir = "/custom/output"
        cache_dir = "/custom/cache"

        [pipeline]
        default_tile_size = 4096

        [logging]
        level = "DEBUG"
        """,
        "valid_extended": """
        output_dir = "/extended/output"
        cache_dir = "/extended/cache"

        [pipeline]
        default_tile_size = 2048
        max_workers = 4

        [logging]
        level = "INFO"
        enable_file_logging = true

        [theme]
        custom_overrides = true
        """,
        "invalid_toml": "invalid toml content [",
    }


@pytest.fixture(scope="session")
def env_var_scenarios() -> dict[str, str]:
    """Pre-defined environment variable scenarios.

    Returns:
        dict[str, str]: Environment variable scenarios.
    """
    return {
        "custom_file": "/custom/path/config.toml",
        "custom_dir": "/custom/config/dir",
        "home_expansion": "~/Documents/test",
    }


@pytest.fixture(autouse=True)
def clear_config_cache() -> None:
    """Clear config cache before each test.

    Yields:
        None: Test execution context.
    """
    _load_config.cache_clear()
    yield
    _load_config.cache_clear()


@pytest.fixture()
def mock_env_vars(monkeypatch: Any) -> Any:
    """Mock environment variables for testing.

    Returns:
        Any: Monkeypatch fixture.
    """
    monkeypatch.delenv("GOESVFI_CONFIG_DIR", raising=False)
    monkeypatch.delenv("GOESVFI_CONFIG_FILE", raising=False)
    return monkeypatch


class TestConfigManagement:
    """Test configuration loading and validation with optimized patterns."""

    def test_get_config_path_default(self, mock_env_vars: Any) -> None:  # noqa: PLR6301, ARG002
        """Test default config path when no environment variables are set."""
        path = get_config_path()

        assert path.name == "config.toml"
        assert ".config/goesvfi" in str(path)

    @pytest.mark.parametrize("env_scenario", ["custom_file", "custom_dir"])
    def test_get_config_path_custom(self, mock_env_vars: Any, env_var_scenarios: Any, env_scenario: str) -> None:  # noqa: PLR6301
        """Test custom config paths via environment variables."""
        if env_scenario == "custom_file":
            custom_path = env_var_scenarios["custom_file"]
            mock_env_vars.setenv("GOESVFI_CONFIG_FILE", custom_path)
            expected_path = custom_path
        elif env_scenario == "custom_dir":
            custom_dir = env_var_scenarios["custom_dir"]
            mock_env_vars.setenv("GOESVFI_CONFIG_DIR", custom_dir)
            expected_path = f"{custom_dir}/config.toml"

        path = get_config_path()
        assert str(path) == expected_path

    @pytest.mark.parametrize("config_scenario", ["valid_minimal", "valid_complete"])
    def test_validate_config_valid_data(self, config_scenarios: Any, config_scenario: str) -> None:  # noqa: PLR6301
        """Test validation with valid configuration data."""
        config_data = config_scenarios[config_scenario].copy()
        original_data = config_data.copy()

        # Should not raise any exception
        _validate_config(config_data)

        # Valid data should remain largely unchanged (may have defaults filled)
        assert config_data["output_dir"] == original_data["output_dir"]
        assert config_data["cache_dir"] == original_data["cache_dir"]

    @pytest.mark.parametrize("config_scenario", ["invalid_types", "missing_sections"])
    def test_validate_config_invalid_data(self, config_scenarios: Any, config_scenario: str) -> None:  # noqa: PLR6301
        """Test validation with invalid configuration data."""
        config_data = config_scenarios[config_scenario].copy()

        with pytest.raises(ValueError, match="Invalid configuration"):
            _validate_config(config_data)

        # Should have been corrected with defaults after exception
        assert isinstance(config_data["output_dir"], str)
        assert "pipeline" in config_data
        assert isinstance(config_data["pipeline"], dict)

    def test_validate_config_nested_validation(self, config_scenarios: Any) -> None:  # noqa: PLR6301
        """Test validation of nested configuration sections."""
        config_data = config_scenarios["valid_complete"].copy()
        # Deep copy nested dicts
        config_data["pipeline"] = config_data["pipeline"].copy()
        config_data["theme"] = config_data["theme"].copy()

        # Introduce invalid nested values
        config_data["pipeline"]["default_tile_size"] = "not_an_int"
        config_data["theme"]["custom_overrides"] = "not_a_bool"

        with pytest.raises(ValueError, match="Invalid configuration"):
            _validate_config(config_data)

        # Should have been corrected after exception
        assert isinstance(config_data["pipeline"]["default_tile_size"], int)
        assert isinstance(config_data["theme"]["custom_overrides"], bool)

    @pytest.mark.parametrize("file_exists", [True, False])
    def test_load_config_file_existence(self, mock_env_vars: Any, file_exists: bool) -> None:  # noqa: PLR6301, ARG002, FBT001
        """Test loading config when file exists or doesn't exist."""
        with patch("goesvfi.utils.config.get_config_path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = file_exists
            mock_path.return_value = mock_file

            if file_exists:
                # Mock valid file content
                toml_content = """
                output_dir = "/test/output"
                cache_dir = "/test/cache"

                [pipeline]
                default_tile_size = 2048

                [logging]
                level = "INFO"
                """
                mock_file.open.return_value.__enter__.return_value = mock_open(
                    read_data=toml_content.encode()
                ).return_value

            with patch("pathlib.Path.mkdir"):  # Mock directory creation
                config = _load_config()

            if file_exists:
                assert config["output_dir"] == "/test/output"
                assert config["cache_dir"] == "/test/cache"
            else:
                # Should return defaults
                assert config["output_dir"] == DEFAULTS["output_dir"]
                assert config["cache_dir"] == DEFAULTS["cache_dir"]

    @pytest.mark.parametrize("toml_scenario", ["valid_basic", "valid_extended"])
    def test_load_config_valid_toml(self, mock_env_vars: Any, toml_content_scenarios: Any, toml_scenario: str) -> None:  # noqa: PLR6301, ARG002
        """Test loading valid TOML configuration content."""
        toml_content = toml_content_scenarios[toml_scenario]

        with patch("goesvfi.utils.config.get_config_path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.open.return_value.__enter__.return_value = mock_open(read_data=toml_content.encode()).return_value
            mock_path.return_value = mock_file

            with patch("pathlib.Path.mkdir"):  # Mock directory creation
                config = _load_config()

            if toml_scenario == "valid_basic":
                assert config["output_dir"] == "/custom/output"
                assert config["cache_dir"] == "/custom/cache"
                assert config["pipeline"]["default_tile_size"] == 4096
                assert config["logging"]["level"] == "DEBUG"
            elif toml_scenario == "valid_extended":
                assert config["output_dir"] == "/extended/output"
                assert config["theme"]["custom_overrides"] is True

    def test_load_config_invalid_toml(self, mock_env_vars: Any, toml_content_scenarios: Any) -> None:  # noqa: PLR6301, ARG002
        """Test loading invalid TOML raises appropriate error."""
        invalid_toml = toml_content_scenarios["invalid_toml"]

        with patch("goesvfi.utils.config.get_config_path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.open.return_value.__enter__.return_value = mock_open(read_data=invalid_toml.encode()).return_value
            mock_path.return_value = mock_file

            with pytest.raises(ValueError, match="Invalid TOML"):
                _load_config()

    @pytest.mark.parametrize(
        "config_key,getter_func",
        [
            ("output_dir", get_output_dir),
            ("cache_dir", get_cache_dir),
        ],
    )
    def test_directory_getters(self, config_key: str, getter_func: Any) -> None:  # noqa: PLR6301
        """Test output and cache directory getter functions."""
        test_path = f"/test/{config_key}"

        with patch("goesvfi.utils.config._load_config") as mock_load:
            mock_load.return_value = {config_key: test_path}

            result = getter_func()

            assert isinstance(result, Path)
            assert str(result) == test_path

    @pytest.mark.parametrize(
        "malformed_value,expected_fallback",
        [
            (123, DEFAULTS["output_dir"]),  # Wrong type
            (None, DEFAULTS["output_dir"]),  # None value
            ("", DEFAULTS["output_dir"]),  # Empty string
        ],
    )
    def test_directory_getters_fallback(self, malformed_value: Any, expected_fallback: str) -> None:  # noqa: PLR6301
        """Test directory getters fallback when config is malformed."""
        with patch("goesvfi.utils.config._load_config") as mock_load:
            mock_load.return_value = {"output_dir": malformed_value, "cache_dir": malformed_value}

            output_result = get_output_dir()
            cache_result = get_cache_dir()

            assert isinstance(output_result, Path)
            assert isinstance(cache_result, Path)
            assert str(output_result) == expected_fallback
            assert str(cache_result) == DEFAULTS["cache_dir"]

    def test_ffmpeg_profiles_structure_validation(self) -> None:  # noqa: PLR6301
        """Test FFmpeg profiles have correct structure and valid values."""
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

        # Test all profiles have required structure
        for profile_name, profile in FFMPEG_PROFILES.items():
            for key in required_keys:
                assert key in profile, f"Profile '{profile_name}' missing key '{key}'"

            # Test type constraints
            assert isinstance(profile["use_ffmpeg_interp"], bool)
            assert isinstance(profile["crf"], int)
            assert isinstance(profile["bitrate"], int)
            assert isinstance(profile["mi_mode"], str)

    @pytest.mark.parametrize("profile_name", ["Default", "Optimal", "Optimal 2"])
    def test_ffmpeg_profile_parameter_ranges(self, profile_name: str) -> None:  # noqa: PLR6301
        """Test FFmpeg profile parameter validation with reasonable ranges."""
        profile = FFMPEG_PROFILES[profile_name]

        # Test reasonable value ranges
        assert 0 <= profile["crf"] <= 51
        assert profile["bitrate"] > 0
        assert profile["pix_fmt"] in {"yuv420p", "yuv444p", "yuv422p"}
        assert profile["mi_mode"] in {"dup", "mci"}
        assert profile["mc_mode"] in {"obmc", "aobmc"}

    def test_config_schema_completeness(self) -> None:  # noqa: PLR6301
        """Test that expected schema covers all defaults."""

        def check_schema_coverage(
            defaults_section: dict[str, Any], schema_section: dict[str, Any], path: str = ""
        ) -> None:
            for key, value in defaults_section.items():
                full_path = f"{path}.{key}" if path else key
                assert key in schema_section, f"Schema missing key: {full_path}"

                if isinstance(value, dict):
                    assert isinstance(schema_section[key], dict), f"Schema type mismatch at {full_path}"
                    check_schema_coverage(value, schema_section[key], full_path)

        check_schema_coverage(DEFAULTS, EXPECTED_SCHEMA)

    def test_config_caching_behavior(self) -> None:  # noqa: PLR6301
        """Test that config loading uses LRU cache correctly."""
        with patch("goesvfi.utils.config.get_config_path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = False
            mock_path.return_value = mock_file

            with patch("pathlib.Path.mkdir"):
                # First call
                config1 = _load_config()
                # Second call should use cache
                config2 = _load_config()

            # Should be the exact same object due to caching
            assert config1 is config2

            # get_config_path should only be called once due to caching
            assert mock_path.call_count == 1

    def test_path_expansion_functionality(self, mock_env_vars: Any) -> None:  # noqa: PLR6301
        """Test that paths are properly expanded."""
        mock_env_vars.setenv("HOME", "/home/testuser")

        with patch("goesvfi.utils.config._load_config") as mock_load:
            mock_load.return_value = {"output_dir": "~/Documents/test"}

            result = get_output_dir()

            # Should expand ~ to home directory
            assert "testuser" in str(result)
            assert "~" not in str(result)

    @pytest.mark.parametrize("directory_count", [1, 3, 5])
    def test_directory_creation_on_load(self, directory_count: int) -> None:  # noqa: PLR6301
        """Test that directories are created when config is loaded."""
        test_dirs = [f"/test/dir{i}" for i in range(directory_count)]
        test_config = {
            "output_dir": test_dirs[0] if test_dirs else "/test/output",
            "cache_dir": test_dirs[1] if len(test_dirs) > 1 else "/test/cache",
        }

        # Add sanchez config if we have enough directories
        if len(test_dirs) > 2:
            test_config["sanchez"] = {"bin_dir": test_dirs[2]}

        with (
            patch("goesvfi.utils.config.get_config_path") as mock_path,
            patch("pathlib.Path.mkdir") as mock_mkdir,
        ):
            mock_file = MagicMock()
            mock_file.exists.return_value = False
            mock_path.return_value = mock_file

            with (
                patch("goesvfi.utils.config._validate_config"),
                patch.dict("goesvfi.utils.config.DEFAULTS", test_config),
            ):
                _load_config()

            # Should have created at least the basic directories
            assert mock_mkdir.call_count >= 2  # At minimum output and cache dirs

    @pytest.mark.parametrize("cache_operations", [5, 10, 15])
    def test_config_cache_performance(self, cache_operations: int) -> None:  # noqa: PLR6301
        """Test config cache performance with multiple operations."""

        with patch("goesvfi.utils.config.get_config_path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = False
            mock_path.return_value = mock_file

            with patch("pathlib.Path.mkdir"):
                start_time = time.time()

                # Multiple calls should use cache
                configs = [_load_config() for _ in range(cache_operations)]

                end_time = time.time()

            # All should be the same object due to caching
            assert all(config is configs[0] for config in configs)

            # Should complete quickly due to caching
            assert (end_time - start_time) < 0.1  # Less than 100ms

            # get_config_path should only be called once
            assert mock_path.call_count == 1
