"""Settings management functionality for the main GUI window."""

from pathlib import Path
from typing import Any

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)


class SettingsManager:
    """Manages application settings persistence."""

    def __init__(self, settings: QSettings) -> None:
        """Initialize the settings manager.

        Args:
            settings: The QSettings instance to use
        """
        self.settings = settings
        self._verify_settings_consistency()

    def _verify_settings_consistency(self) -> None:
        """Verify QSettings consistency and fix if needed."""
        org_name = self.settings.organizationName()
        app_name = self.settings.applicationName()
        filename = self.settings.fileName()

        LOGGER.debug(
            "SettingsManager - QSettings details: org=%s, app=%s, file=%s",
            org_name,
            app_name,
            filename,
        )

        # Verify consistency with QApplication
        app_instance = QApplication.instance()
        if app_instance is not None:
            app_org = app_instance.organizationName()
            app_name_global = app_instance.applicationName()

            if org_name != app_org or app_name != app_name_global:
                LOGGER.error(
                    "QSettings mismatch detected! Settings: org=%s, app=%s, but Application: org=%s, app=%s",
                    org_name,
                    app_name,
                    app_org,
                    app_name_global,
                )
                LOGGER.error("This will cause settings to be saved in different locations!")

                # Force consistency
                self.settings = QSettings(app_org, app_name_global)
                LOGGER.info(
                    "Corrected QSettings to: org=%s, app=%s, file=%s",
                    app_org,
                    app_name_global,
                    self.settings.fileName(),
                )

    def save_value(self, key: str, value: Any) -> bool:
        """Save a single value to settings.

        Args:
            key: The settings key
            value: The value to save

        Returns:
            True if save was successful
        """
        try:
            self.settings.setValue(key, value)
            self.settings.sync()
            LOGGER.debug("Saved setting: %s = %s", key, value)
            return True
        except Exception:
            LOGGER.exception("Error saving setting %s", key)
            return False

    def load_value(self, key: str, default: Any = None, value_type: type | None = None) -> Any:
        """Load a single value from settings.

        Args:
            key: The settings key
            default: Default value if key not found
            value_type: Expected type of the value

        Returns:
            The loaded value or default
        """
        try:
            if value_type is not None:
                return self.settings.value(key, default, type=value_type)
            return self.settings.value(key, default)
        except Exception:
            LOGGER.exception("Error loading setting %s", key)
            return default

    def save_window_geometry(self, window_key: str, geometry: dict[str, int]) -> bool:
        """Save window geometry settings.

        Args:
            window_key: Unique key for the window
            geometry: Dictionary with x, y, width, height

        Returns:
            True if save was successful
        """
        try:
            self.settings.beginGroup(f"Windows/{window_key}")
            for key, value in geometry.items():
                self.settings.setValue(key, value)
            self.settings.endGroup()
            self.settings.sync()
            return True
        except Exception:
            LOGGER.exception("Error saving window geometry for %s", window_key)
            return False

    def load_window_geometry(self, window_key: str) -> dict[str, int] | None:
        """Load window geometry settings.

        Args:
            window_key: Unique key for the window

        Returns:
            Dictionary with geometry values or None
        """
        try:
            self.settings.beginGroup(f"Windows/{window_key}")
            geometry = {}

            for key in ["x", "y", "width", "height"]:
                value = self.settings.value(key, -1, type=int)
                if value >= 0:
                    geometry[key] = value

            self.settings.endGroup()

            # Return None if any required value is missing
            if len(geometry) != 4:
                return None

            return geometry
        except Exception:
            LOGGER.exception("Error loading window geometry for %s", window_key)
            return None

    def save_recent_paths(self, key: str, paths: list[Path], max_items: int = 10) -> bool:
        """Save a list of recent paths.

        Args:
            key: The settings key for the list
            paths: List of paths to save
            max_items: Maximum number of items to save

        Returns:
            True if save was successful
        """
        try:
            # Limit the number of items
            paths_to_save = paths[:max_items]

            # Convert to strings
            path_strings = [str(p) for p in paths_to_save]

            self.settings.setValue(f"RecentPaths/{key}", path_strings)
            self.settings.sync()
            return True
        except Exception:
            LOGGER.exception("Error saving recent paths for %s", key)
            return False

    def load_recent_paths(self, key: str) -> list[Path]:
        """Load a list of recent paths.

        Args:
            key: The settings key for the list

        Returns:
            List of Path objects
        """
        try:
            path_strings = self.settings.value(f"RecentPaths/{key}", [], type=list)
            return [Path(p) for p in path_strings if p]
        except Exception:
            LOGGER.exception("Error loading recent paths for %s", key)
            return []

    def clear_group(self, group_name: str) -> bool:
        """Clear all settings in a group.

        Args:
            group_name: Name of the settings group

        Returns:
            True if successful
        """
        try:
            self.settings.beginGroup(group_name)
            self.settings.remove("")  # Remove all keys in the group
            self.settings.endGroup()
            self.settings.sync()
            LOGGER.debug("Cleared settings group: %s", group_name)
            return True
        except Exception:
            LOGGER.exception("Error clearing settings group %s", group_name)
            return False

    def get_all_keys(self) -> list[str]:
        """Get all settings keys.

        Returns:
            List of all keys in settings
        """
        try:
            keys = self.settings.allKeys()
            return [str(key) for key in keys]  # Convert to List[str]
        except Exception:
            LOGGER.exception("Error getting all keys")
            return []

    def remove_key(self, key: str) -> bool:
        """Remove a specific key from settings.

        Args:
            key: The key to remove

        Returns:
            True if successful
        """
        try:
            self.settings.remove(key)
            self.settings.sync()
            LOGGER.debug("Removed setting key: %s", key)
            return True
        except Exception:
            LOGGER.exception("Error removing key %s", key)
            return False

    def sync(self) -> bool:
        """Force sync settings to disk.

        Returns:
            True if successful
        """
        try:
            self.settings.sync()
            return True
        except Exception:
            LOGGER.exception("Error syncing settings")
            return False
