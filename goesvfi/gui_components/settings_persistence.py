"""Settings persistence functionality for MainWindow."""

from pathlib import Path
from typing import Tuple

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class SettingsPersistence:
    """Handles direct settings persistence for critical application state."""

    def __init__(self, settings: QSettings) -> None:
        """Initialize the settings persistence handler.

        Args:
            settings: QSettings instance to use
        """
        self.settings = settings

    def save_input_directory(self, path: Path) -> bool:
        """Save input directory to settings persistently.

        Args:
            path: The input directory path to save

        Returns:
            True if save was successful, False otherwise
        """
        if not path:
            return False

        try:
            # Always save as an absolute, resolved path for maximum compatibility
            in_dir_str = str(path.resolve())
            LOGGER.debug("Saving input directory directly (absolute): %r", in_dir_str)

            # Log QSettings details to ensure settings are being saved to the right place
            org_name = self.settings.organizationName()
            app_name = self.settings.applicationName()
            filename = self.settings.fileName()
            LOGGER.debug(
                "QSettings details during save: org=%s, app=%s, file=%s",
                org_name,
                app_name,
                filename,
            )

            # Verify QSettings consistency
            self._verify_settings_consistency()

            # Save to multiple keys to ensure redundancy
            self.settings.setValue("paths/inputDirectory", in_dir_str)
            self.settings.setValue("inputDir", in_dir_str)  # Alternate key

            # Force immediate sync to disk
            self.settings.sync()

            # Verify the saved value
            saved_dir = self.settings.value("paths/inputDirectory", "", type=str)
            LOGGER.debug("Verification - Input directory after direct save: %s", saved_dir)

            # Check if settings file exists
            if not self._verify_settings_file():
                return False

            # Explicitly cast bool to avoid Any return type
            return bool(saved_dir == in_dir_str)
        except Exception as e:
            LOGGER.error("Error directly saving input directory: %s", e)
            return False

    def save_crop_rect(self, rect: Tuple[int, int, int, int]) -> bool:
        """Save crop rectangle to settings persistently.

        Args:
            rect: The crop rectangle as (x, y, width, height)

        Returns:
            True if save was successful, False otherwise
        """
        if not rect:
            return False

        try:
            rect_str = ",".join(map(str, rect))
            LOGGER.debug("Saving crop rectangle directly: %r", rect_str)

            # Log QSettings details
            org_name = self.settings.organizationName()
            app_name = self.settings.applicationName()
            filename = self.settings.fileName()
            LOGGER.debug(
                "QSettings details during crop save: org=%s, app=%s, file=%s",
                org_name,
                app_name,
                filename,
            )

            # Verify QSettings consistency
            self._verify_settings_consistency()

            # Save to multiple keys to ensure redundancy
            self.settings.setValue("preview/cropRectangle", rect_str)
            self.settings.setValue("cropRect", rect_str)  # Alternate key

            # Force immediate sync to disk
            self.settings.sync()

            # Verify the saved value
            saved_rect = self.settings.value("preview/cropRectangle", "", type=str)
            LOGGER.debug("Verification - Crop rectangle after direct save: %s", saved_rect)

            # Check if settings file exists
            if not self._verify_settings_file():
                return False

            # Explicitly cast bool to avoid Any return type
            return bool(saved_rect == rect_str)
        except Exception as e:
            LOGGER.error("Error directly saving crop rectangle: %s", e)
            return False

    def _verify_settings_consistency(self) -> None:
        """Verify QSettings consistency with application settings."""
        # This will detect if we have mismatched organization/application names
        app_instance = QApplication.instance()
        app_org = app_instance.organizationName() if app_instance is not None else ""
        app_name_global = app_instance.applicationName() if app_instance is not None else ""

        org_name = self.settings.organizationName()
        app_name = self.settings.applicationName()

        if org_name != app_org or app_name != app_name_global:
            LOGGER.error(
                "QSettings mismatch! Settings: org=%s, app=%s, " "but Application: org=%s, app=%s",
                org_name,
                app_name,
                app_org,
                app_name_global,
            )
            LOGGER.error("This will cause settings to be saved in different locations!")
            # Force consistency by recreating settings instance
            self.settings = QSettings(app_org, app_name_global)
            LOGGER.info(
                "Corrected QSettings to: org=%s, app=%s, file=%s",
                app_org,
                app_name_global,
                self.settings.fileName(),
            )

    def _verify_settings_file(self) -> bool:
        """Verify that the settings file exists after save.

        Returns:
            True if file exists, False otherwise
        """
        try:
            settings_file = Path(self.settings.fileName())
            if settings_file.exists():
                LOGGER.debug(
                    "Settings file exists: %s (size: %s bytes)",
                    settings_file,
                    settings_file.stat().st_size,
                )
                return True
            else:
                LOGGER.warning("Settings file does not exist after save attempt: %s", settings_file)
                return False
        except Exception as file_error:
            LOGGER.error("Error checking settings file: %s", file_error)
            return False
