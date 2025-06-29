"""Optimized configuration tests to speed up slow tests while maintaining coverage.

Optimizations applied:
- Shared fixtures for common configuration setups and mock configurations
- Parameterized test scenarios for comprehensive configuration validation
- Enhanced error handling and edge case coverage
- Streamlined file system operations with proper cleanup
- Mock-based testing to avoid real file I/O where possible
"""

import pathlib
from unittest import mock
from unittest.mock import MagicMock
import pytest

from goesvfi.utils import config


class TestConfigurationV2:
    """Optimized test class for configuration functionality."""

    @pytest.fixture(scope="class")
    def sample_toml_configurations(self):
        """Sample TOML configurations for testing various scenarios."""
        return {
            "complete": """
output_dir = "/tmp/goesvfi_output"
cache_dir = "/tmp/goesvfi_cache"

[pipeline]
default_tile_size = 2048
supported_extensions = [".png", ".jpg"]

[sanchez]
bin_dir = "/tmp/sanchez"

[logging]
level = "INFO"
""",
            "minimal": """
output_dir = "/tmp/minimal_output"
""",
            "partial": """
output_dir = "/tmp/partial_output"
[pipeline]
default_tile_size = 512
""",
            "invalid_toml": "invalid = [this is not valid toml",
            "invalid_types": """
output_dir = 123
cache_dir = true
""",
            "missing_required": """
cache_dir = "/tmp/cache"
[logging]
level = "DEBUG"
"""
        }

    @pytest.fixture
    def config_cache_cleanup(self):
        """Ensure config cache is clean for each test."""
        config._load_config.cache_clear()
        yield
        config._load_config.cache_clear()

    @pytest.fixture
    def mock_file_operations(self):
        """Mock file system operations for testing."""
        with mock.patch("pathlib.Path.exists") as mock_exists, \
             mock.patch("pathlib.Path.mkdir") as mock_mkdir, \
             mock.patch("pathlib.Path.write_text") as mock_write:
            mock_exists.return_value = True
            mock_mkdir.return_value = None
            mock_write.return_value = None
            yield {
                "exists": mock_exists,
                "mkdir": mock_mkdir,
                "write_text": mock_write
            }

    @pytest.mark.parametrize("exists_return_value,expected_behavior", [
        (False, "uses_defaults"),
        (True, "loads_from_file")
    ])
    def test_load_config_scenarios(self, config_cache_cleanup, exists_return_value, expected_behavior):
        """Test configuration loading with various file existence scenarios."""
        with mock.patch("pathlib.Path.exists", return_value=exists_return_value):
            if exists_return_value:
                # Mock file content loading
                with mock.patch("pathlib.Path.read_text", return_value="output_dir = '/test/output'"):
                    with mock.patch("tomllib.loads", return_value={"output_dir": "/test/output"}):
                        result = config._load_config()
                        if expected_behavior == "loads_from_file":
                            assert result["output_dir"] == "/test/output"
            else:
                # Test defaults
                result = config._load_config()
                if expected_behavior == "uses_defaults":
                    assert result["output_dir"] == config.DEFAULTS["output_dir"]

    @pytest.mark.parametrize("config_name,expected_output_dir,should_succeed", [
        ("complete", "/tmp/goesvfi_output", True),
        ("minimal", "/tmp/minimal_output", True),
        ("partial", "/tmp/partial_output", True),
        ("invalid_toml", None, False),
        ("invalid_types", None, False)
    ])
    def test_config_loading_with_content(self, config_cache_cleanup, sample_toml_configurations, 
                                        tmp_path, monkeypatch, config_name, expected_output_dir, should_succeed):
        """Test configuration loading with various TOML content scenarios."""
        config_content = sample_toml_configurations[config_name]
        config_path = tmp_path / "config.toml"
        config_path.write_text(config_content)
        
        monkeypatch.setenv("GOESVFI_CONFIG_FILE", str(config_path))
        
        if should_succeed:
            cfg = config._load_config()
            assert cfg["output_dir"] == expected_output_dir
            # Verify defaults are merged for partial configs
            if config_name == "partial":
                assert "cache_dir" in cfg
                assert cfg["pipeline"]["default_tile_size"] == 512
        else:
            with pytest.raises(ValueError):
                config._load_config()

    def test_config_environment_overrides(self, config_cache_cleanup, sample_toml_configurations, tmp_path, monkeypatch):
        """Test configuration file path overrides via environment variables."""
        config_content = sample_toml_configurations["complete"]
        
        # Test GOESVFI_CONFIG_FILE override
        config_file = tmp_path / "custom_config.toml"
        config_file.write_text(config_content)
        monkeypatch.setenv("GOESVFI_CONFIG_FILE", str(config_file))
        
        cfg = config._load_config()
        assert cfg["output_dir"] == "/tmp/goesvfi_output"
        
        # Clean and test GOESVFI_CONFIG_DIR override
        config._load_config.cache_clear()
        config_dir = tmp_path / "config_dir"
        config_dir.mkdir()
        (config_dir / "config.toml").write_text(config_content)
        monkeypatch.setenv("GOESVFI_CONFIG_DIR", str(config_dir))
        monkeypatch.delenv("GOESVFI_CONFIG_FILE", raising=False)
        
        cfg = config._load_config()
        assert cfg["output_dir"] == "/tmp/goesvfi_output"

    def test_config_directory_creation(self, config_cache_cleanup, tmp_path, monkeypatch):
        """Test that configuration directories are created when accessed."""
        config_content = """
output_dir = "/tmp/test_output"
cache_dir = "/tmp/test_cache"
"""
        config_path = tmp_path / "config.toml"
        config_path.write_text(config_content)
        monkeypatch.setenv("GOESVFI_CONFIG_FILE", str(config_path))
        
        # Test get_output_dir creates directory
        output_dir = config.get_output_dir()
        assert isinstance(output_dir, pathlib.Path)
        assert output_dir.exists()
        
        # Test get_cache_dir creates directory
        cache_dir = config.get_cache_dir()
        assert isinstance(cache_dir, pathlib.Path)
        assert cache_dir.exists()

    @pytest.mark.parametrize("which_return,bin_exists,model_exists,should_find", [
        ("/usr/bin/rife-ncnn-vulkan", False, False, True),  # Found in PATH
        (None, True, False, True),   # Found in bin dir
        (None, False, True, True),   # Found in model dir
        (None, False, False, False)  # Not found anywhere
    ])
    def test_find_rife_executable_scenarios(self, which_return, bin_exists, model_exists, should_find):
        """Test RIFE executable finding with various location scenarios."""
        with mock.patch("shutil.which", return_value=which_return) as mock_which, \
             mock.patch("pathlib.Path.exists") as mock_exists:
            
            def exists_side_effect(self_path):
                path_str = str(self_path)
                if bin_exists and "bin/rife-cli" in path_str:
                    return True
                if model_exists and "models/rife-v4.6/rife-cli" in path_str:
                    return True
                return False
            
            mock_exists.side_effect = exists_side_effect
            
            if should_find:
                path = config.find_rife_executable("rife-v4.6")
                assert path is not None
                assert isinstance(path, pathlib.Path)
                mock_which.assert_called_once()
            else:
                with pytest.raises(FileNotFoundError):
                    config.find_rife_executable("rife-v4.6")

    def test_config_partial_merge_comprehensive(self, config_cache_cleanup, tmp_path, monkeypatch):
        """Test comprehensive configuration merging with defaults."""
        # Test various partial configurations
        partial_configs = [
            ("output_only", "output_dir = '/test/output'"),
            ("pipeline_only", "[pipeline]\ndefault_tile_size = 1024"),
            ("nested_partial", """
output_dir = "/custom/output"
[pipeline]
default_tile_size = 512
[sanchez]
bin_dir = "/custom/sanchez"
""")
        ]
        
        for config_name, config_content in partial_configs:
            config_path = tmp_path / f"{config_name}.toml"
            config_path.write_text(config_content)
            monkeypatch.setenv("GOESVFI_CONFIG_FILE", str(config_path))
            config._load_config.cache_clear()
            
            cfg = config._load_config()
            
            # Verify custom values are preserved
            if "output_dir" in config_content:
                assert "/custom/output" in cfg.get("output_dir", "") or "/test/output" in cfg.get("output_dir", "")
            
            # Verify defaults are merged for missing keys
            assert "cache_dir" in cfg
            assert "pipeline" in cfg
            assert "supported_extensions" in cfg["pipeline"]

    def test_config_validation_edge_cases(self, config_cache_cleanup, tmp_path, monkeypatch):
        """Test configuration validation with edge cases."""
        edge_cases = [
            # Empty file
            ("", True),
            # Only whitespace
            ("   \n  \t  \n", True),
            # Only comments
            ("# This is just a comment\n# Another comment", True),
            # Valid but minimal
            ("output_dir = '/valid'", False)
        ]
        
        for content, should_use_defaults in edge_cases:
            config_path = tmp_path / f"edge_case.toml"
            config_path.write_text(content)
            monkeypatch.setenv("GOESVFI_CONFIG_FILE", str(config_path))
            config._load_config.cache_clear()
            
            cfg = config._load_config()
            
            if should_use_defaults:
                # Should fall back to defaults
                assert cfg["output_dir"] == config.DEFAULTS["output_dir"]
            else:
                # Should use provided value
                assert cfg["output_dir"] == "/valid"

    def test_config_error_handling_comprehensive(self, config_cache_cleanup, tmp_path, monkeypatch):
        """Test comprehensive error handling scenarios."""
        # Test file permission errors
        config_path = tmp_path / "config.toml"
        config_path.write_text("output_dir = '/test'")
        config_path.chmod(0o000)  # Remove all permissions
        
        monkeypatch.setenv("GOESVFI_CONFIG_FILE", str(config_path))
        
        try:
            # Should handle permission errors gracefully
            cfg = config._load_config()
            # Should fall back to defaults on permission error
            assert cfg["output_dir"] == config.DEFAULTS["output_dir"]
        except (PermissionError, OSError):
            # Permission error is acceptable behavior
            pass
        finally:
            # Restore permissions for cleanup
            config_path.chmod(0o644)

    def test_config_caching_behavior(self, config_cache_cleanup, tmp_path, monkeypatch):
        """Test configuration caching behavior."""
        config_content = "output_dir = '/cached/output'"
        config_path = tmp_path / "config.toml"
        config_path.write_text(config_content)
        monkeypatch.setenv("GOESVFI_CONFIG_FILE", str(config_path))
        
        # First call should load from file
        cfg1 = config._load_config()
        
        # Second call should use cache (modify file to verify)
        config_path.write_text("output_dir = '/modified/output'")
        cfg2 = config._load_config()
        
        # Should be the same (cached)
        assert cfg1["output_dir"] == cfg2["output_dir"] == "/cached/output"
        
        # After cache clear, should reload
        config._load_config.cache_clear()
        cfg3 = config._load_config()
        assert cfg3["output_dir"] == "/modified/output"

    def test_config_type_validation_comprehensive(self, config_cache_cleanup, tmp_path, monkeypatch):
        """Test comprehensive type validation for configuration values."""
        invalid_type_configs = [
            ("output_dir = 123", "output_dir should be string"),
            ("cache_dir = []", "cache_dir should be string"),
            ("[pipeline]\ndefault_tile_size = 'not_a_number'", "tile_size should be int"),
            ("[pipeline]\nsupported_extensions = 'not_a_list'", "extensions should be list")
        ]
        
        for invalid_config, description in invalid_type_configs:
            config_path = tmp_path / "invalid.toml"
            config_path.write_text(invalid_config)
            monkeypatch.setenv("GOESVFI_CONFIG_FILE", str(config_path))
            config._load_config.cache_clear()
            
            with pytest.raises(ValueError, match=r".*"):
                config._load_config()

    def test_rife_executable_search_patterns(self):
        """Test various RIFE executable search patterns and naming conventions."""
        executable_patterns = [
            "rife-ncnn-vulkan",
            "rife-cli",
            "rife",
            "RIFE-ncnn-vulkan.exe"  # Windows variant
        ]
        
        for pattern in executable_patterns:
            with mock.patch("shutil.which", return_value=f"/usr/bin/{pattern}") as mock_which:
                path = config.find_rife_executable("rife-v4.6")
                assert str(path) == f"/usr/bin/{pattern}"
                mock_which.assert_called()

    def test_config_integration_workflow(self, config_cache_cleanup, tmp_path, monkeypatch):
        """Test complete configuration workflow integration."""
        # Create comprehensive config
        config_content = """
output_dir = "/integration/output"
cache_dir = "/integration/cache"

[pipeline]
default_tile_size = 4096
supported_extensions = [".png", ".jpg", ".tiff"]

[sanchez]
bin_dir = "/integration/sanchez"

[logging]
level = "DEBUG"
"""
        config_path = tmp_path / "integration_config.toml"
        config_path.write_text(config_content)
        monkeypatch.setenv("GOESVFI_CONFIG_FILE", str(config_path))
        
        # Test complete workflow
        output_dir = config.get_output_dir()
        cache_dir = config.get_cache_dir()
        
        assert str(output_dir) == "/integration/output"
        assert str(cache_dir) == "/integration/cache"
        assert output_dir.exists()
        assert cache_dir.exists()
        
        # Test configuration access
        cfg = config._load_config()
        assert cfg["pipeline"]["default_tile_size"] == 4096
        assert ".tiff" in cfg["pipeline"]["supported_extensions"]
        assert cfg["sanchez"]["bin_dir"] == "/integration/sanchez"
        assert cfg["logging"]["level"] == "DEBUG"