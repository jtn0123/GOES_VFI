"""Base settings management classes.

Provides the foundation for safe, organized settings persistence that reduces
complexity in settings-heavy functions.
"""

from abc import ABC, abstractmethod
import logging
from typing import Any

from PyQt6.QtCore import QSettings

from goesvfi.utils.errors import ErrorClassifier, StructuredError

LOGGER = logging.getLogger(__name__)


class SettingsSection(ABC):
    """Base class for settings sections.

    Each section handles a specific group of related settings, reducing
    complexity by organizing settings into focused, manageable units.
    """

    def __init__(self, name: str, classifier: ErrorClassifier | None = None) -> None:
        self.name = name
        self.classifier = classifier or ErrorClassifier()
        self._values: dict[str, Any] = {}
        self._errors: list[StructuredError] = []

    @abstractmethod
    def extract_values(self, source_object: Any) -> dict[str, Any]:
        """Extract settings values from source object (e.g., GUI widgets).

        Args:
            source_object: Object containing the settings data

        Returns:
            Dictionary of setting key -> value pairs
        """

    @abstractmethod
    def apply_values(self, target_object: Any, values: dict[str, Any]) -> None:
        """Apply settings values to target object (e.g., GUI widgets).

        Args:
            target_object: Object to apply settings to
            values: Dictionary of setting key -> value pairs
        """

    def save_to_qsettings(self, qsettings: QSettings) -> bool:
        """Save this section's values to QSettings.

        Returns:
            True if successful, False if there were errors
        """
        try:
            for key, value in self._values.items():
                qsettings.setValue(key, value)
            return True
        except Exception as e:
            error = self.classifier.create_structured_error(e, f"save_{self.name}_settings", "settings_section")
            self._errors.append(error)
            LOGGER.warning("Failed to save %s settings: %s", self.name, error.user_message)
            return False

    def load_from_qsettings(self, qsettings: QSettings, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
        """Load this section's values from QSettings.

        Args:
            qsettings: QSettings instance to load from
            defaults: Default values to use if setting not found

        Returns:
            Dictionary of loaded values
        """
        defaults = defaults or {}
        loaded_values = {}

        try:
            for key in self.get_setting_keys():
                default_value = defaults.get(key, None)
                loaded_values[key] = qsettings.value(key, default_value)
            return loaded_values
        except Exception as e:
            error = self.classifier.create_structured_error(e, f"load_{self.name}_settings", "settings_section")
            self._errors.append(error)
            LOGGER.warning("Failed to load %s settings: %s", self.name, error.user_message)
            return defaults

    @abstractmethod
    def get_setting_keys(self) -> list[str]:
        """Get list of setting keys this section handles."""

    def get_errors(self) -> list[StructuredError]:
        """Get any errors that occurred during operations."""
        return self._errors.copy()

    def clear_errors(self) -> None:
        """Clear error list."""
        self._errors.clear()

    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self._errors) > 0


class SettingsManager:
    """Manages multiple settings sections with centralized error handling.

    Reduces complexity by orchestrating settings operations across
    multiple focused sections instead of one monolithic function.
    """

    def __init__(self, qsettings: QSettings, classifier: ErrorClassifier | None = None) -> None:
        self.qsettings = qsettings
        self.classifier = classifier or ErrorClassifier()
        self.sections: dict[str, SettingsSection] = {}
        self._global_errors: list[StructuredError] = []

    def add_section(self, section: SettingsSection) -> "SettingsManager":
        """Add a settings section."""
        self.sections[section.name] = section
        return self

    def save_all_settings(self, source_object: Any) -> bool:
        """Save all settings sections.

        Args:
            source_object: Object to extract settings from (e.g., main window)

        Returns:
            True if all sections saved successfully
        """
        all_successful = True

        for section_name, section in self.sections.items():
            try:
                # Extract values from source
                values = section.extract_values(source_object)
                section._values = values

                # Save to QSettings
                success = section.save_to_qsettings(self.qsettings)
                if not success:
                    all_successful = False

            except Exception as e:
                error = self.classifier.create_structured_error(e, f"save_{section_name}", "settings_manager")
                self._global_errors.append(error)
                LOGGER.exception("Failed to save section %s: %s", section_name, error.user_message)
                all_successful = False

        return all_successful

    def load_all_settings(self, target_object: Any, defaults: dict[str, dict[str, Any]] | None = None) -> bool:
        """Load all settings sections.

        Args:
            target_object: Object to apply settings to (e.g., main window)
            defaults: Default values organized by section name

        Returns:
            True if all sections loaded successfully
        """
        defaults = defaults or {}
        all_successful = True

        for section_name, section in self.sections.items():
            try:
                # Load values from QSettings
                section_defaults = defaults.get(section_name, {})
                values = section.load_from_qsettings(self.qsettings, section_defaults)

                # Apply to target object
                section.apply_values(target_object, values)

            except Exception as e:
                error = self.classifier.create_structured_error(e, f"load_{section_name}", "settings_manager")
                self._global_errors.append(error)
                LOGGER.exception("Failed to load section %s: %s", section_name, error.user_message)
                all_successful = False

        return all_successful

    def get_all_errors(self) -> list[StructuredError]:
        """Get all errors from manager and sections."""
        all_errors = self._global_errors.copy()

        for section in self.sections.values():
            all_errors.extend(section.get_errors())

        return all_errors

    def clear_all_errors(self) -> None:
        """Clear all errors from manager and sections."""
        self._global_errors.clear()
        for section in self.sections.values():
            section.clear_errors()

    def has_any_errors(self) -> bool:
        """Check if there are any errors in manager or sections."""
        if self._global_errors:
            return True

        return any(section.has_errors() for section in self.sections.values())
