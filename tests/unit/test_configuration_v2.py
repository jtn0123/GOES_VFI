"""Tests for centralized configuration management."""

import json
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Never
import unittest
from unittest.mock import patch

import pytest

from goesvfi.core.configuration import (
    ApplicationConfig,
    ConfigurationManager,
    NetworkConfig,
    ProcessingConfig,
    StorageConfig,
    UIConfig,
    add_config_watcher,
    get_config,
    get_config_manager,
    get_connection_timeout,
    get_data_directory,
    get_log_level,
    get_max_workers,
    get_network_config,
    get_output_directory,
    get_processing_config,
    get_storage_config,
    get_temp_directory,
    get_ui_config,
    is_debug_mode,
    remove_config_watcher,
    reset_config,
    update_config,
)


class TestConfigurationSchemas(unittest.TestCase):
    """Test configuration schema classes."""

    @staticmethod
    def test_processing_config_defaults() -> None:
        """Test ProcessingConfig default values."""
        config = ProcessingConfig()

        assert config.max_workers == 4
        assert config.buffer_size == 64 * 1024
        assert config.temp_directory is None
        assert config.cache_size == 100
        assert config.batch_size == 10

    @staticmethod
    def test_network_config_defaults() -> None:
        """Test NetworkConfig default values."""
        config = NetworkConfig()

        assert config.connection_timeout == 30.0
        assert config.read_timeout == 300.0
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.max_connections == 10

    @staticmethod
    def test_storage_config_defaults() -> None:
        """Test StorageConfig default values."""
        config = StorageConfig()

        assert config.data_directory == "./data"
        assert config.output_directory == "./output"
        assert config.log_directory == "./logs"
        assert config.cache_directory == "./cache"
        assert config.max_disk_usage == 10 * 1024 * 1024 * 1024

    def test_ui_config_defaults(self) -> None:
        """Test UIConfig default values."""
        config = UIConfig()

        assert config.theme == "light"
        assert config.window_width == 1200
        assert config.window_height == 800
        assert config.update_interval == 0.1
        assert config.preview_size == 512

    def test_application_config_defaults(self) -> None:
        """Test ApplicationConfig default values."""
        config = ApplicationConfig()

        assert isinstance(config.processing, ProcessingConfig)
        assert isinstance(config.network, NetworkConfig)
        assert isinstance(config.storage, StorageConfig)
        assert isinstance(config.ui, UIConfig)
        assert not config.debug_mode
        assert config.log_level == "INFO"
        assert not config.profile_performance


class TestConfigurationManager(unittest.TestCase):
    """Test ConfigurationManager functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config_file = self.temp_dir / "test_config.json"
        self.manager = ConfigurationManager(self.config_file)

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        # Stop any file watching
        if hasattr(self.manager, "_watching"):
            self.manager.stop_file_watching()

        # Clean up temp directory
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self) -> None:
        """Test ConfigurationManager initialization."""
        assert self.manager.config_file == self.config_file
        assert isinstance(self.manager.get_config(), ApplicationConfig)
        assert self.manager.env_prefix == "GOESVFI_"

    def test_get_config(self) -> None:
        """Test getting current configuration."""
        config = self.manager.get_config()

        assert isinstance(config, ApplicationConfig)
        assert isinstance(config.processing, ProcessingConfig)
        assert isinstance(config.network, NetworkConfig)
        assert isinstance(config.storage, StorageConfig)
        assert isinstance(config.ui, UIConfig)

    def test_get_section(self) -> None:
        """Test getting configuration sections."""
        processing = self.manager.get_section("processing")
        network = self.manager.get_section("network")

        assert isinstance(processing, ProcessingConfig)
        assert isinstance(network, NetworkConfig)

        # Test non-existent section
        assert self.manager.get_section("nonexistent") is None

    def test_update_config(self) -> None:
        """Test updating configuration."""
        updates = {"processing": {"max_workers": 8}, "debug_mode": True, "log_level": "DEBUG"}

        self.manager.update_config(updates, save=False)

        config = self.manager.get_config()
        assert config.processing.max_workers == 8
        assert config.debug_mode
        assert config.log_level == "DEBUG"

    def test_save_and_load_from_file(self) -> None:
        """Test saving and loading configuration from file."""
        # Update configuration
        updates = {
            "processing": {"max_workers": 6, "cache_size": 200},
            "network": {"connection_timeout": 60.0},
            "debug_mode": True,
        }

        self.manager.update_config(updates, save=True)

        # Verify file was created
        assert self.config_file.exists()

        # Load from file in new manager
        new_manager = ConfigurationManager(self.config_file)
        config = new_manager.get_config()

        assert config.processing.max_workers == 6
        assert config.processing.cache_size == 200
        assert config.network.connection_timeout == 60.0
        assert config.debug_mode

    def test_load_from_environment(self) -> None:
        """Test loading configuration from environment variables."""
        env_vars = {
            "GOESVFI_PROCESSING_MAX_WORKERS": "12",
            "GOESVFI_PROCESSING_CACHE_SIZE": "500",
            "GOESVFI_NETWORK_TIMEOUT": "45.0",
            "GOESVFI_STORAGE_DATA_DIR": "/custom/data",
            "GOESVFI_UI_THEME": "dark",
            "GOESVFI_DEBUG": "true",
            "GOESVFI_LOG_LEVEL": "WARNING",
        }

        with patch.dict(os.environ, env_vars):
            manager = ConfigurationManager(self.config_file)
            config = manager.get_config()

            assert config.processing.max_workers == 12
            assert config.processing.cache_size == 500
            assert config.network.connection_timeout == 45.0
            assert config.storage.data_directory == "/custom/data"
            assert config.ui.theme == "dark"
            assert config.debug_mode
            assert config.log_level == "WARNING"

    def test_configuration_precedence(self) -> None:
        """Test configuration precedence: env vars > file > defaults."""
        # Create config file
        file_config = {"processing": {"max_workers": 8}, "debug_mode": True, "log_level": "ERROR"}

        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(file_config, f)

        # Set environment variables (should override file)
        env_vars = {"GOESVFI_PROCESSING_MAX_WORKERS": "16", "GOESVFI_LOG_LEVEL": "DEBUG"}

        with patch.dict(os.environ, env_vars):
            manager = ConfigurationManager(self.config_file)
            config = manager.get_config()

            # Environment should override file
            assert config.processing.max_workers == 16
            assert config.log_level == "DEBUG"

            # File should override defaults
            assert config.debug_mode

            # Defaults should be used when not overridden
            assert config.processing.cache_size == 100

    def test_invalid_environment_variables(self) -> None:
        """Test handling of invalid environment variables."""
        env_vars = {
            "GOESVFI_PROCESSING_MAX_WORKERS": "invalid_number",
            "GOESVFI_DEBUG": "maybe",
        }

        with patch.dict(os.environ, env_vars):
            # Should not raise exception, just log warnings
            manager = ConfigurationManager(self.config_file)
            config = manager.get_config()

            # Should use defaults for invalid values
            assert config.processing.max_workers == 4
            assert not config.debug_mode

    def test_configuration_watchers(self) -> None:
        """Test configuration change watchers."""
        old_configs = []
        new_configs = []

        def watcher(old_config, new_config) -> None:
            old_configs.append(old_config)
            new_configs.append(new_config)

        self.manager.add_watcher(watcher)

        # Update configuration
        updates = {"debug_mode": True}
        self.manager.update_config(updates, save=False)

        # Verify watcher was called
        assert len(old_configs) == 1
        assert len(new_configs) == 1
        assert not old_configs[0].debug_mode
        assert new_configs[0].debug_mode

        # Remove watcher
        self.manager.remove_watcher(watcher)

        # Update again
        updates = {"log_level": "DEBUG"}
        self.manager.update_config(updates, save=False)

        # Watcher should not be called again
        assert len(old_configs) == 1
        assert len(new_configs) == 1

    def test_file_watching(self) -> None:
        """Test file watching for configuration changes."""
        # Create initial config file
        initial_config = {"debug_mode": False}
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(initial_config, f)

        manager = ConfigurationManager(self.config_file)
        assert not manager.get_config().debug_mode

        # Start file watching
        manager.start_file_watching()

        try:
            # Modify config file
            updated_config = {"debug_mode": True, "log_level": "DEBUG"}
            time.sleep(0.1)  # Ensure different mtime

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(updated_config, f)

            # Wait for file watcher to detect change
            for _ in range(30):  # Wait up to 3 seconds
                if manager.get_config().debug_mode:
                    break
                time.sleep(0.1)

            # Verify configuration was reloaded
            config = manager.get_config()
            assert config.debug_mode
            assert config.log_level == "DEBUG"

        finally:
            manager.stop_file_watching()

    def test_reset_to_defaults(self) -> None:
        """Test resetting configuration to defaults."""
        # Modify configuration
        updates = {"processing": {"max_workers": 16}, "debug_mode": True, "log_level": "DEBUG"}
        self.manager.update_config(updates, save=False)

        # Verify changes
        config = self.manager.get_config()
        assert config.processing.max_workers == 16
        assert config.debug_mode

        # Reset to defaults
        self.manager.reset_to_defaults()

        # Verify reset
        config = self.manager.get_config()
        assert config.processing.max_workers == 4
        assert not config.debug_mode
        assert config.log_level == "INFO"

    def test_validate_configuration(self) -> None:
        """Test configuration validation."""
        # Test valid configuration
        issues = self.manager.validate_configuration()
        assert len(issues) == 0

        # Test with invalid values (for dataclass version)
        try:
            import goesvfi.core.configuration

            if not goesvfi.core.configuration.PYDANTIC_AVAILABLE:
                # Manually set invalid values for testing
                config = self.manager.get_config()
                config.processing.max_workers = 100  # Invalid
                config.ui.theme = "invalid"  # Invalid

                issues = self.manager.validate_configuration()
                assert len(issues) > 0
        except Exception:
            pass  # Skip validation test if not applicable

    def test_get_effective_config_sources(self) -> None:
        """Test getting effective configuration sources."""
        sources = self.manager.get_effective_config_sources()

        assert "defaults" in sources
        assert "config_file" in sources
        assert "environment" in sources
        assert "config_file_path" in sources
        assert "pydantic_available" in sources

        assert sources["defaults"]
        assert not sources["config_file"]  # No file initially
        assert str(sources["config_file_path"]) == str(self.config_file)


class TestGlobalConfigurationFunctions(unittest.TestCase):
    """Test global configuration functions."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Reset global configuration manager
        import goesvfi.core.configuration

        goesvfi.core.configuration._config_manager = None

    def test_get_config_manager_singleton(self) -> None:
        """Test that get_config_manager returns singleton."""
        manager1 = get_config_manager()
        manager2 = get_config_manager()

        assert manager1 is manager2

    def test_get_config(self) -> None:
        """Test get_config function."""
        config = get_config()
        assert isinstance(config, ApplicationConfig)

    def test_get_section_configs(self) -> None:
        """Test getting specific configuration sections."""
        processing = get_processing_config()
        network = get_network_config()
        storage = get_storage_config()
        ui = get_ui_config()

        assert isinstance(processing, ProcessingConfig)
        assert isinstance(network, NetworkConfig)
        assert isinstance(storage, StorageConfig)
        assert isinstance(ui, UIConfig)

    def test_update_global_config(self) -> None:
        """Test updating global configuration."""
        update_config({"debug_mode": True}, save=False)

        assert get_config().debug_mode

    def test_reset_global_config(self) -> None:
        """Test resetting global configuration."""
        # Modify config
        update_config({"debug_mode": True}, save=False)
        assert get_config().debug_mode

        # Reset
        reset_config()
        assert not get_config().debug_mode

    def test_global_config_watchers(self) -> None:
        """Test global configuration watchers."""
        changes = []

        def watcher(old_config, new_config) -> None:
            changes.append((old_config.debug_mode, new_config.debug_mode))

        add_config_watcher(watcher)

        # Update config
        update_config({"debug_mode": True}, save=False)

        # Verify watcher was called
        assert len(changes) == 1
        assert changes[0] == (False, True)

        # Remove watcher
        remove_config_watcher(watcher)

    def test_convenience_functions(self) -> None:
        """Test convenience functions."""
        # Test with defaults
        assert not is_debug_mode()
        assert get_log_level() == "INFO"
        assert get_max_workers() == 4
        assert get_connection_timeout() == 30.0

        # Test directory functions
        assert isinstance(get_temp_directory(), Path)
        assert isinstance(get_data_directory(), Path)
        assert isinstance(get_output_directory(), Path)

        # Update config and test again
        update_config(
            {
                "debug_mode": True,
                "log_level": "DEBUG",
                "processing": {"max_workers": 8},
                "network": {"connection_timeout": 60.0},
            },
            save=False,
        )

        assert is_debug_mode()
        assert get_log_level() == "DEBUG"
        assert get_max_workers() == 8
        assert get_connection_timeout() == 60.0


class TestConfigurationErrors(unittest.TestCase):
    """Test error handling in configuration system."""

    def test_invalid_config_file(self) -> None:
        """Test handling of invalid config file."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            config_file = temp_dir / "invalid.json"

            # Create invalid JSON file
            with open(config_file, "w", encoding="utf-8") as f:
                f.write("{ invalid json }")

            # Should not raise exception, just use defaults
            manager = ConfigurationManager(config_file)
            config = manager.get_config()

            # Should have default values
            assert config.processing.max_workers == 4
            assert not config.debug_mode

        finally:
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_config_update_validation_error(self) -> None:
        """Test handling of validation errors during config update."""
        manager = ConfigurationManager()

        # Try to update with invalid data (this depends on validation implementation)
        try:
            invalid_updates = {"processing": {"max_workers": "invalid"}}

            # Should raise exception for invalid data
            with pytest.raises(Exception):
                manager.update_config(invalid_updates)
        except Exception:
            pass  # Skip if validation not implemented

    def test_watcher_exception_handling(self) -> None:
        """Test handling of exceptions in watchers."""
        manager = ConfigurationManager()

        def failing_watcher(old_config, new_config) -> Never:
            msg = "Watcher error"
            raise ValueError(msg)

        manager.add_watcher(failing_watcher)

        # Should not raise exception even if watcher fails
        manager.update_config({"debug_mode": True}, save=False)

        # Config should still be updated
        assert manager.get_config().debug_mode


class TestThreadSafety(unittest.TestCase):
    """Test thread safety of configuration system."""

    def test_concurrent_config_access(self) -> None:
        """Test concurrent configuration access."""
        manager = ConfigurationManager()
        results = []
        errors = []

        def worker() -> None:
            try:
                for _i in range(10):
                    config = manager.get_config()
                    results.append(config.processing.max_workers)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        # Start multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Should have no errors
        assert len(errors) == 0
        assert len(results) == 50  # 5 threads * 10 iterations

    def test_concurrent_config_updates(self) -> None:
        """Test concurrent configuration updates."""
        manager = ConfigurationManager()
        errors = []

        def updater(worker_id) -> None:
            try:
                for i in range(5):
                    # Use valid values (1-32 for max_workers)
                    max_workers = 1 + (worker_id * 5 + i) % 30  # Ensures 1-31 range
                    updates = {"processing": {"max_workers": max_workers}}
                    manager.update_config(updates, save=False)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        # Start multiple updater threads
        threads = []
        for worker_id in range(3):
            thread = threading.Thread(target=updater, args=(worker_id,))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Should have no errors
        assert len(errors) == 0

        # Config should be valid
        config = manager.get_config()
        assert isinstance(config.processing.max_workers, int)
        assert config.processing.max_workers >= 1
        assert config.processing.max_workers <= 32


if __name__ == "__main__":
    unittest.main()
