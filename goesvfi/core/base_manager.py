"""Base manager class providing common functionality for all manager classes.

This module provides a base class that implements common patterns found across
the various manager classes in the application, reducing code duplication.
"""

from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QSettings, pyqtSignal

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class BaseManager(QObject):
    """Base class for all manager classes providing common functionality.

    This class provides:
    - Logging setup
    - Settings management
    - Error handling
    - Resource cleanup
    - Common signals
    """

    # Common signals
    error_occurred = pyqtSignal(str)  # Error message
    state_changed = pyqtSignal()  # Generic state change notification

    def __init__(self, name: str, settings: QSettings | None = None, parent: QObject | None = None) -> None:
        """Initialize the base manager.

        Args:
            name: Name of the manager for logging
            settings: Optional QSettings instance for persistence
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self.name = name
        self.settings = settings
        self._logger = log.get_logger(f"{__name__}.{name}")
        self._is_initialized = False
        self._resources: list[Any] = []

        self._logger.debug("Initializing %s", self.name)

    def initialize(self) -> None:
        """Initialize the manager.

        Subclasses should override this to perform initialization.
        This method ensures initialization only happens once.
        """
        if self._is_initialized:
            self._logger.debug("%s already initialized", self.name)
            return

        try:
            self._logger.info("Initializing %s", self.name)
            self._do_initialize()
            self._is_initialized = True
            self._logger.info("%s initialized successfully", self.name)
        except Exception as e:
            self._logger.exception("Failed to initialize %s", self.name)
            self.error_occurred.emit(f"Failed to initialize {self.name}: {e}")
            raise

    def _do_initialize(self) -> None:
        """Perform actual initialization.

        Subclasses should override this method to perform their
        specific initialization logic.
        """

    def cleanup(self) -> None:
        """Clean up resources.

        This method ensures proper cleanup of resources and
        can be called multiple times safely.
        """
        if not self._is_initialized:
            return

        try:
            self._logger.info("Cleaning up %s", self.name)
            self._do_cleanup()
            self._cleanup_resources()
            self._is_initialized = False
            self._logger.info("%s cleaned up successfully", self.name)
        except Exception:
            self._logger.exception("Error during %s cleanup", self.name)
            # Don't raise during cleanup

    def _do_cleanup(self) -> None:
        """Perform actual cleanup.

        Subclasses should override this method to perform their
        specific cleanup logic.
        """

    def _cleanup_resources(self) -> None:
        """Clean up tracked resources."""
        for resource in self._resources:
            try:
                if hasattr(resource, "cleanup"):
                    resource.cleanup()
                elif hasattr(resource, "close"):
                    resource.close()
                elif hasattr(resource, "deleteLater"):
                    resource.deleteLater()
            except Exception as e:
                self._logger.warning("Failed to cleanup resource %s: %s", resource, e)
        self._resources.clear()

    def _track_resource(self, resource: Any) -> None:
        """Track a resource for cleanup.

        Args:
            resource: Resource to track for cleanup
        """
        self._resources.append(resource)

    def save_setting(self, key: str, value: Any) -> None:
        """Save a setting value.

        Args:
            key: Setting key
            value: Setting value
        """
        if self.settings is None:
            self._logger.debug("No settings instance, skipping save of %s", key)
            return

        try:
            self.settings.setValue(f"{self.name}/{key}", value)
            self.settings.sync()
            self._logger.debug("Saved setting %s/%s", self.name, key)
        except Exception:
            self._logger.exception("Failed to save setting %s/%s", self.name, key)

    def load_setting(self, key: str, default: Any = None) -> Any:
        """Load a setting value.

        Args:
            key: Setting key
            default: Default value if setting not found

        Returns:
            Setting value or default
        """
        if self.settings is None:
            self._logger.debug("No settings instance, returning default for %s", key)
            return default

        try:
            value = self.settings.value(f"{self.name}/{key}", default)
            self._logger.debug("Loaded setting %s/%s: %s", self.name, key, value)
            return value
        except Exception:
            self._logger.exception("Failed to load setting %s/%s", self.name, key)
            return default

    def handle_error(self, error: Exception, context: str = "") -> None:
        """Handle an error with logging and signal emission.

        Args:
            error: The exception that occurred
            context: Additional context about where the error occurred
        """
        error_msg = str(error)
        if context:
            error_msg = f"{context}: {error_msg}"

        self._logger.error("%s error: %s", self.name, error_msg)
        self.error_occurred.emit(error_msg)

    def log_debug(self, msg: str, *args: Any) -> None:
        """Log a debug message with manager context."""
        self._logger.debug(f"[{self.name}] {msg}", *args)

    def log_info(self, msg: str, *args: Any) -> None:
        """Log an info message with manager context."""
        self._logger.info(f"[{self.name}] {msg}", *args)

    def log_warning(self, msg: str, *args: Any) -> None:
        """Log a warning message with manager context."""
        self._logger.warning(f"[{self.name}] {msg}", *args)

    def log_error(self, msg: str, *args: Any) -> None:
        """Log an error message with manager context."""
        self._logger.error(f"[{self.name}] {msg}", *args)


class FileBasedManager(BaseManager):
    """Base class for managers that work with files.

    Provides common file handling functionality.
    """

    def __init__(
        self,
        name: str,
        base_path: Path | str | None = None,
        settings: QSettings | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the file-based manager.

        Args:
            name: Name of the manager
            base_path: Base path for file operations
            settings: Optional QSettings instance
            parent: Optional parent QObject
        """
        super().__init__(name, settings, parent)
        self._base_path = Path(base_path) if base_path else None

    @property
    def base_path(self) -> Path | None:
        """Get the base path for file operations."""
        return self._base_path

    @base_path.setter
    def base_path(self, path: Path | str | None) -> None:
        """Set the base path for file operations."""
        self._base_path = Path(path) if path else None
        self.log_debug("Base path set to: %s", self._base_path)
        self.state_changed.emit()

    def ensure_base_path_exists(self) -> bool:
        """Ensure the base path exists, creating it if necessary.

        Returns:
            True if path exists or was created, False otherwise
        """
        if not self._base_path:
            self.log_warning("No base path set")
            return False

        try:
            self._base_path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            self.handle_error(e, "Failed to create base path")
            return False

    def resolve_path(self, relative_path: str | Path) -> Path:
        """Resolve a path relative to the base path.

        Args:
            relative_path: Path relative to base path

        Returns:
            Resolved absolute path
        """
        if self._base_path:
            return self._base_path / relative_path
        return Path(relative_path)

    def path_exists(self, relative_path: str | Path) -> bool:
        """Check if a path exists relative to base path.

        Args:
            relative_path: Path to check

        Returns:
            True if path exists
        """
        full_path = self.resolve_path(relative_path)
        return full_path.exists()


class ConfigurableManager(BaseManager):
    """Base class for managers with configuration.

    Provides configuration management functionality.
    """

    def __init__(
        self,
        name: str,
        default_config: dict[str, Any] | None = None,
        settings: QSettings | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the configurable manager.

        Args:
            name: Name of the manager
            default_config: Default configuration values
            settings: Optional QSettings instance
            parent: Optional parent QObject
        """
        super().__init__(name, settings, parent)
        self._config: dict[str, Any] = default_config.copy() if default_config else {}
        self._default_config = default_config or {}

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if not found

        Returns:
            Configuration value or default
        """
        return self._config.get(key, default)

    def set_config(self, key: str, value: Any) -> None:
        """Set a configuration value.

        Args:
            key: Configuration key
            value: Configuration value
        """
        old_value = self._config.get(key)
        self._config[key] = value

        if old_value != value:
            self.log_debug("Config %s changed: %s -> %s", key, old_value, value)
            self.state_changed.emit()

            # Optionally save to settings
            if self.settings:
                self.save_setting(f"config/{key}", value)

    def update_config(self, config: dict[str, Any]) -> None:
        """Update multiple configuration values.

        Args:
            config: Dictionary of configuration values
        """
        for key, value in config.items():
            self.set_config(key, value)

    def reset_config(self) -> None:
        """Reset configuration to defaults."""
        self._config = self._default_config.copy()
        self.log_info("Configuration reset to defaults")
        self.state_changed.emit()

    def load_config_from_settings(self) -> None:
        """Load configuration from settings."""
        if not self.settings:
            return

        for key, default_value in self._default_config.items():
            stored_value = self.load_setting(f"config/{key}", default_value)
            self._config[key] = stored_value

        self.log_info("Configuration loaded from settings")

    def save_config_to_settings(self) -> None:
        """Save current configuration to settings."""
        if not self.settings:
            return

        for key, value in self._config.items():
            self.save_setting(f"config/{key}", value)

        self.log_info("Configuration saved to settings")
