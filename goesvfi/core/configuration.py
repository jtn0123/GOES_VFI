"""Centralized configuration management for GOES VFI.

This module provides a unified configuration system that consolidates
multiple configuration sources (environment variables, config files, defaults)
into a single, type-safe interface with validation and hot-reloading.
"""

from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any, TypeVar

try:
    from pydantic import BaseModel, Field, validator

    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = object

    def Field(default: Any = None, description: str = "", **kwargs: Any) -> Any:
        """Fallback Field function when pydantic is not available.

        Args:
            default: Default value
            description: Field description (ignored)
            **kwargs: Additional arguments (ignored)

        Returns:
            The default value
        """
        return default


import contextlib

try:
    from goesvfi.core.base_manager import ConfigurableManager

    MANAGER_BASE_AVAILABLE = True
except ImportError:
    # Fallback for environments without PyQt6
    MANAGER_BASE_AVAILABLE = False

    class ConfigurableManager:
        """Fallback ConfigurableManager for environments without PyQt6."""

        def __init__(self, name: str, **kwargs):
            self.name = name

        def handle_error(self, error: Exception, context: str = "") -> None:
            """Handle an error with logging."""
            error_msg = str(error)
            if context:
                error_msg = f"{context}: {error_msg}"
            LOGGER.error("%s error: %s", self.name, error_msg)

        def log_debug(self, msg: str, *args: Any) -> None:
            """Log a debug message."""
            if args:
                formatted_msg = msg % args
                LOGGER.debug("[%s] %s", self.name, formatted_msg)
            else:
                LOGGER.debug("[%s] %s", self.name, msg)

        def log_info(self, msg: str, *args: Any) -> None:
            """Log an info message."""
            if args:
                formatted_msg = msg % args
                LOGGER.info("[%s] %s", self.name, formatted_msg)
            else:
                LOGGER.info("[%s] %s", self.name, msg)

        def log_warning(self, msg: str, *args: Any) -> None:
            """Log a warning message."""
            if args:
                formatted_msg = msg % args
                LOGGER.warning("[%s] %s", self.name, formatted_msg)
            else:
                LOGGER.warning("[%s] %s", self.name, msg)

        def log_error(self, msg: str, *args: Any) -> None:
            """Log an error message."""
            if args:
                formatted_msg = msg % args
                LOGGER.error("[%s] %s", self.name, formatted_msg)
            else:
                LOGGER.error("[%s] %s", self.name, msg)


from goesvfi.utils import log

LOGGER = log.get_logger(__name__)

T = TypeVar("T")


# Configuration schemas using Pydantic if available, dataclasses otherwise

if PYDANTIC_AVAILABLE:

    class ProcessingConfig(BaseModel):
        """Configuration for video processing operations."""

        max_workers: int = Field(default=4, description="Maximum number of worker processes")
        buffer_size: int = Field(default=64 * 1024, description="Buffer size for file operations")
        temp_directory: str | None = Field(default=None, description="Custom temporary directory")
        cache_size: int = Field(default=100, description="LRU cache size for processed images")
        batch_size: int = Field(default=10, description="Batch size for bulk operations")

        @validator("max_workers")
        @classmethod
        def validate_max_workers(cls, v):
            if v < 1 or v > 32:
                msg = "max_workers must be between 1 and 32"
                raise ValueError(msg)
            return v

        @validator("cache_size")
        @classmethod
        def validate_cache_size(cls, v):
            if v < 10 or v > 1000:
                msg = "cache_size must be between 10 and 1000"
                raise ValueError(msg)
            return v

    class NetworkConfig(BaseModel):
        """Configuration for network operations."""

        connection_timeout: float = Field(default=30.0, description="Connection timeout in seconds")
        read_timeout: float = Field(default=300.0, description="Read timeout in seconds")
        max_retries: int = Field(default=3, description="Maximum retry attempts")
        retry_delay: float = Field(default=1.0, description="Delay between retries")
        max_connections: int = Field(default=10, description="Maximum concurrent connections")

        @validator("connection_timeout", "read_timeout")
        @classmethod
        def validate_timeouts(cls, v):
            if v <= 0 or v > 3600:
                msg = "timeout must be between 0 and 3600 seconds"
                raise ValueError(msg)
            return v

    class StorageConfig(BaseModel):
        """Configuration for storage operations."""

        data_directory: str = Field(default="./data", description="Base data directory")
        output_directory: str = Field(default="./output", description="Output directory")
        log_directory: str = Field(default="./logs", description="Log file directory")
        cache_directory: str = Field(default="./cache", description="Cache directory")
        max_disk_usage: int = Field(default=10 * 1024 * 1024 * 1024, description="Max disk usage in bytes (10GB)")

        @validator("max_disk_usage")
        @classmethod
        def validate_disk_usage(cls, v):
            if v < 100 * 1024 * 1024:  # 100MB minimum
                msg = "max_disk_usage must be at least 100MB"
                raise ValueError(msg)
            return v

    class UIConfig(BaseModel):
        """Configuration for user interface."""

        theme: str = Field(default="light", description="UI theme (light/dark)")
        window_width: int = Field(default=1200, description="Default window width")
        window_height: int = Field(default=800, description="Default window height")
        update_interval: float = Field(default=0.1, description="UI update interval in seconds")
        preview_size: int = Field(default=512, description="Preview image size")

        @validator("theme")
        @classmethod
        def validate_theme(cls, v):
            if v not in {"light", "dark"}:
                msg = "theme must be 'light' or 'dark'"
                raise ValueError(msg)
            return v

    class ApplicationConfig(BaseModel):
        """Main application configuration."""

        processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
        network: NetworkConfig = Field(default_factory=NetworkConfig)
        storage: StorageConfig = Field(default_factory=StorageConfig)
        ui: UIConfig = Field(default_factory=UIConfig)

        # Global settings
        debug_mode: bool = Field(default=False, description="Enable debug mode")
        log_level: str = Field(default="INFO", description="Logging level")
        profile_performance: bool = Field(default=False, description="Enable performance profiling")

        @validator("log_level")
        @classmethod
        def validate_log_level(cls, v):
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if v.upper() not in valid_levels:
                msg = f"log_level must be one of: {valid_levels}"
                raise ValueError(msg)
            return v.upper()

else:
    # Fallback dataclass implementation when Pydantic is not available
    @dataclass
    class ProcessingConfig:
        """Configuration for video processing operations."""

        max_workers: int = 4
        buffer_size: int = 64 * 1024
        temp_directory: str | None = None
        cache_size: int = 100
        batch_size: int = 10

    @dataclass
    class NetworkConfig:
        """Configuration for network operations."""

        connection_timeout: float = 30.0
        read_timeout: float = 300.0
        max_retries: int = 3
        retry_delay: float = 1.0
        max_connections: int = 10

    @dataclass
    class StorageConfig:
        """Configuration for storage operations."""

        data_directory: str = "./data"
        output_directory: str = "./output"
        log_directory: str = "./logs"
        cache_directory: str = "./cache"
        max_disk_usage: int = 10 * 1024 * 1024 * 1024  # 10GB

    @dataclass
    class UIConfig:
        """Configuration for user interface."""

        theme: str = "light"
        window_width: int = 1200
        window_height: int = 800
        update_interval: float = 0.1
        preview_size: int = 512

    @dataclass
    class ApplicationConfig:
        """Main application configuration."""

        processing: ProcessingConfig = field(default_factory=ProcessingConfig)
        network: NetworkConfig = field(default_factory=NetworkConfig)
        storage: StorageConfig = field(default_factory=StorageConfig)
        ui: UIConfig = field(default_factory=UIConfig)
        debug_mode: bool = False
        log_level: str = "INFO"
        profile_performance: bool = False


class ConfigurationManager(ConfigurableManager):
    """Centralized configuration manager with hot-reloading and validation."""

    def __init__(self, config_file: Path | None = None):
        super().__init__("ConfigurationManager")

        self.config_file = config_file or Path("goesvfi_config.json")
        self._config = ApplicationConfig()
        self._watchers: list[callable] = []
        self._last_modified = 0.0
        self._lock = threading.RLock()
        self._watch_thread: threading.Thread | None = None
        self._watching = False

        # Environment variable prefix
        self.env_prefix = "GOESVFI_"

        # Load initial configuration
        self._load_configuration()

    def _load_configuration(self) -> None:
        """Load configuration from file and environment variables."""
        with self._lock:
            old_config = self._config  # Store old config for notification
            try:
                # Start with defaults
                config_dict = self._get_default_config_dict()

                # Override with file configuration
                if self.config_file.exists():
                    file_config = self._load_from_file()
                    config_dict = self._merge_configs(config_dict, file_config)
                    self._last_modified = self.config_file.stat().st_mtime

                # Override with environment variables
                env_config = self._load_from_environment()
                config_dict = self._merge_configs(config_dict, env_config)

                # Create and validate configuration
                if PYDANTIC_AVAILABLE:
                    new_config = ApplicationConfig(**config_dict)
                else:
                    new_config = self._create_dataclass_config(config_dict)

                # Update config and notify watchers if changed
                self._config = new_config
                if old_config is not None and old_config != new_config:
                    self._notify_watchers(old_config, new_config)

                self.log_info("Configuration loaded successfully")

            except Exception as e:
                self.handle_error(e, "load_configuration")
                # Keep existing config on error

    def _get_default_config_dict(self) -> dict[str, Any]:
        """Get default configuration as dictionary."""
        if PYDANTIC_AVAILABLE:
            return ApplicationConfig().dict()
        # Convert dataclass to dict
        import dataclasses

        config = ApplicationConfig()
        result = {}
        for section_name in ["processing", "network", "storage", "ui"]:
            section = getattr(config, section_name)
            result[section_name] = dataclasses.asdict(section)

        # Add global settings
        result.update({
            "debug_mode": config.debug_mode,
            "log_level": config.log_level,
            "profile_performance": config.profile_performance,
        })
        return result

    def _load_from_file(self) -> dict[str, Any]:
        """Load configuration from file."""
        try:
            with open(self.config_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.log_warning("Failed to load config file %s: %s", self.config_file, e)
            return {}

    def _load_from_environment(self) -> dict[str, Any]:
        """Load configuration from environment variables."""
        config = {}

        # Map environment variables to config structure
        env_mappings = {
            f"{self.env_prefix}PROCESSING_MAX_WORKERS": ("processing", "max_workers", int),
            f"{self.env_prefix}PROCESSING_CACHE_SIZE": ("processing", "cache_size", int),
            f"{self.env_prefix}NETWORK_TIMEOUT": ("network", "connection_timeout", float),
            f"{self.env_prefix}NETWORK_MAX_RETRIES": ("network", "max_retries", int),
            f"{self.env_prefix}STORAGE_DATA_DIR": ("storage", "data_directory", str),
            f"{self.env_prefix}STORAGE_OUTPUT_DIR": ("storage", "output_directory", str),
            f"{self.env_prefix}UI_THEME": ("ui", "theme", str),
            f"{self.env_prefix}DEBUG": ("debug_mode", None, lambda x: x.lower() in {"true", "1", "yes"}),
            f"{self.env_prefix}LOG_LEVEL": ("log_level", None, str),
        }

        for env_var, (section, key, converter) in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                try:
                    converted_value = converter(value)

                    if key is None:  # Global setting
                        config[section] = converted_value
                    else:  # Section setting
                        if section not in config:
                            config[section] = {}
                        config[section][key] = converted_value

                except (ValueError, TypeError) as e:
                    self.log_warning("Invalid environment variable %s=%s: %s", env_var, value, e)

        return config

    def _merge_configs(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Merge configuration dictionaries recursively."""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value

        return result

    def _create_dataclass_config(self, config_dict: dict[str, Any]) -> ApplicationConfig:
        """Create configuration from dictionary when Pydantic is not available."""
        # Create section configs
        processing = ProcessingConfig(**config_dict.get("processing", {}))
        network = NetworkConfig(**config_dict.get("network", {}))
        storage = StorageConfig(**config_dict.get("storage", {}))
        ui = UIConfig(**config_dict.get("ui", {}))

        return ApplicationConfig(
            processing=processing,
            network=network,
            storage=storage,
            ui=ui,
            debug_mode=config_dict.get("debug_mode", False),
            log_level=config_dict.get("log_level", "INFO"),
            profile_performance=config_dict.get("profile_performance", False),
        )

    def get_config(self) -> ApplicationConfig:
        """Get current configuration."""
        with self._lock:
            return self._config

    def get_section(self, section: str) -> Any:
        """Get a configuration section."""
        with self._lock:
            return getattr(self._config, section, None)

    def update_config(self, updates: dict[str, Any], save: bool = True) -> None:
        """Update configuration with new values."""
        with self._lock:
            try:
                # Merge updates with current config
                current_dict = self._config.dict() if PYDANTIC_AVAILABLE else self._get_default_config_dict()

                updated_dict = self._merge_configs(current_dict, updates)

                # Validate and create new config
                if PYDANTIC_AVAILABLE:
                    new_config = ApplicationConfig(**updated_dict)
                else:
                    new_config = self._create_dataclass_config(updated_dict)

                # Update current config
                old_config = self._config
                self._config = new_config

                if save:
                    self.save_to_file()

                # Notify watchers
                self._notify_watchers(old_config, new_config)

                self.log_info("Configuration updated successfully")

            except Exception as e:
                self.handle_error(e, "update_config")
                raise

    def save_to_file(self, file_path: Path | None = None) -> None:
        """Save current configuration to file."""
        target_file = file_path or self.config_file

        try:
            # Ensure directory exists
            target_file.parent.mkdir(parents=True, exist_ok=True)

            # Convert config to dict
            config_dict = self._config.dict() if PYDANTIC_AVAILABLE else self._get_default_config_dict()

            # Write to temporary file first (atomic write)
            temp_file = target_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)

            # Atomic move
            temp_file.replace(target_file)

            self.log_info("Configuration saved to %s", target_file)

        except Exception as e:
            self.handle_error(e, f"save_to_file({target_file})")
            raise

    def add_watcher(self, callback: callable) -> None:
        """Add a configuration change watcher."""
        with self._lock:
            self._watchers.append(callback)

    def remove_watcher(self, callback: callable) -> None:
        """Remove a configuration change watcher."""
        with self._lock, contextlib.suppress(ValueError):
            self._watchers.remove(callback)

    def _notify_watchers(self, old_config: ApplicationConfig, new_config: ApplicationConfig) -> None:
        """Notify watchers of configuration changes."""
        for watcher in self._watchers:
            try:
                watcher(old_config, new_config)
            except Exception as e:
                self.log_warning("Configuration watcher failed: %s", e)

    def start_file_watching(self) -> None:
        """Start watching configuration file for changes."""
        if self._watching:
            return

        self._watching = True
        self._watch_thread = threading.Thread(target=self._file_watcher, daemon=True)
        self._watch_thread.start()
        self.log_info("Started configuration file watching")

    def stop_file_watching(self) -> None:
        """Stop watching configuration file for changes."""
        self._watching = False
        if self._watch_thread:
            self._watch_thread.join(timeout=1.0)
        self.log_info("Stopped configuration file watching")

    def _file_watcher(self) -> None:
        """File watcher thread function."""
        while self._watching:
            try:
                if self.config_file.exists():
                    current_mtime = self.config_file.stat().st_mtime
                    if current_mtime > self._last_modified:
                        self.log_info("Configuration file changed, reloading...")
                        self._load_configuration()

                time.sleep(1.0)  # Check every second

            except Exception as e:
                self.log_warning("File watcher error: %s", e)
                time.sleep(5.0)  # Wait longer on error

    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""
        with self._lock:
            old_config = self._config
            self._config = ApplicationConfig()
            self._notify_watchers(old_config, self._config)
            self.log_info("Configuration reset to defaults")

    def validate_configuration(self) -> list[str]:
        """Validate current configuration and return any issues."""
        issues = []

        try:
            config = self.get_config()

            # Basic validation for dataclass version
            if not PYDANTIC_AVAILABLE:
                if config.processing.max_workers < 1 or config.processing.max_workers > 32:
                    issues.append("processing.max_workers must be between 1 and 32")

                if config.network.connection_timeout <= 0:
                    issues.append("network.connection_timeout must be positive")

                if config.ui.theme not in {"light", "dark"}:
                    issues.append("ui.theme must be 'light' or 'dark'")

            # Check directory permissions
            for dir_path in [config.storage.data_directory, config.storage.output_directory]:
                path = Path(dir_path)
                if path.exists() and not os.access(path, os.W_OK):
                    issues.append(f"Directory {dir_path} is not writable")

        except Exception as e:
            issues.append(f"Configuration validation error: {e}")

        return issues

    def get_effective_config_sources(self) -> dict[str, Any]:
        """Get information about which sources contributed to current config."""
        return {
            "defaults": True,
            "config_file": self.config_file.exists(),
            "environment": bool([k for k in os.environ if k.startswith(self.env_prefix)]),
            "config_file_path": str(self.config_file),
            "last_modified": datetime.fromtimestamp(self._last_modified) if self._last_modified else None,
            "pydantic_available": PYDANTIC_AVAILABLE,
        }


# Global configuration manager instance
_config_manager: ConfigurationManager | None = None
_config_lock = threading.Lock()


def get_config_manager(config_file: Path | None = None) -> ConfigurationManager:
    """Get the global configuration manager instance."""
    global _config_manager

    with _config_lock:
        if _config_manager is None:
            _config_manager = ConfigurationManager(config_file)
        return _config_manager


def get_config() -> ApplicationConfig:
    """Get current application configuration."""
    return get_config_manager().get_config()


def get_processing_config() -> ProcessingConfig:
    """Get processing configuration section."""
    return get_config().processing


def get_network_config() -> NetworkConfig:
    """Get network configuration section."""
    return get_config().network


def get_storage_config() -> StorageConfig:
    """Get storage configuration section."""
    return get_config().storage


def get_ui_config() -> UIConfig:
    """Get UI configuration section."""
    return get_config().ui


def update_config(updates: dict[str, Any], *, save: bool = True) -> None:
    """Update global configuration.

    Args:
        updates: Configuration updates to apply
        save: Whether to save the configuration after updating
    """
    get_config_manager().update_config(updates, save)


def save_config(file_path: Path | None = None) -> None:
    """Save current configuration to file."""
    get_config_manager().save_to_file(file_path)


def reset_config() -> None:
    """Reset configuration to defaults."""
    get_config_manager().reset_to_defaults()


def add_config_watcher(callback: callable) -> None:
    """Add a configuration change watcher."""
    get_config_manager().add_watcher(callback)


def remove_config_watcher(callback: callable) -> None:
    """Remove a configuration change watcher."""
    get_config_manager().remove_watcher(callback)


# Convenience functions for common configuration patterns


def is_debug_mode() -> bool:
    """Check if debug mode is enabled."""
    return get_config().debug_mode


def get_log_level() -> str:
    """Get current log level."""
    return get_config().log_level


def get_temp_directory() -> Path:
    """Get temporary directory for processing."""
    temp_dir = get_processing_config().temp_directory
    if temp_dir:
        return Path(temp_dir)
    return Path(tempfile.gettempdir()) / "goesvfi"


def get_data_directory() -> Path:
    """Get data directory."""
    return Path(get_storage_config().data_directory)


def get_output_directory() -> Path:
    """Get output directory."""
    return Path(get_storage_config().output_directory)


def get_cache_directory() -> Path:
    """Get cache directory."""
    return Path(get_storage_config().cache_directory)


def get_max_workers() -> int:
    """Get maximum number of worker processes."""
    return get_processing_config().max_workers


def get_connection_timeout() -> float:
    """Get network connection timeout."""
    return get_network_config().connection_timeout
