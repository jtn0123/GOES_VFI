"""Crop management functionality for the main GUI window."""

from pathlib import Path

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)


class CropManager:
    """Manages crop rectangle functionality for the main window."""

    def __init__(self, settings: QSettings) -> None:
        """Initialize the crop manager.

        Args:
            settings: The QSettings instance to use for persistence
        """
        self.settings = settings
        self.current_crop_rect: tuple[int, int, int, int] | None = None

    def save_crop_rect(self, rect: tuple[int, int, int, int]) -> bool:
        """Save crop rectangle to settings persistently.

        Args:
            rect: The crop rectangle as (x, y, width, height)

        Returns:
            True if save was successful, False otherwise
        """
        if not rect:
            LOGGER.error("Cannot save crop rectangle: rect is None or empty")
            return False

        # Validate input format
        try:
            if not isinstance(rect, tuple) or len(rect) != 4 or not all(isinstance(x, (int, float)) for x in rect):
                LOGGER.error("Invalid rect format: %s", rect)
                return False
        except Exception:
            LOGGER.error("Error validating rect format: %s", rect)
            return False

        try:
            # Check if settings is None
            if self.settings is None:
                LOGGER.error("Cannot save crop rectangle: settings is None")
                return False

            rect_str = ",".join(map(str, rect))
            LOGGER.debug("Saving crop rectangle directly: %r", rect_str)

            # Log QSettings details to ensure settings are being saved to the right place
            org_name = self.settings.organizationName()
            app_name = self.settings.applicationName()
            filename = self.settings.fileName()
            LOGGER.debug(
                "QSettings details during crop save: org=%s, app=%s, file=%s",
                org_name,
                app_name,
                filename,
            )

            # Verify QSettings consistency - but only for real (non-temp) settings files
            app_instance = QApplication.instance()
            app_org = app_instance.organizationName() if app_instance is not None else ""
            app_name_global = app_instance.applicationName() if app_instance is not None else ""

            # Only correct settings if this isn't a temporary file (for testing)
            is_temp_file = filename and (
                "/tmp" in filename or "/TemporaryItems" in filename or filename.endswith(".ini")
            )

            if not is_temp_file and (org_name != app_org or app_name != app_name_global):
                LOGGER.warning(
                    "QSettings mismatch during crop save! Settings: org=%s, app=%s, but Application: org=%s, app=%s",
                    org_name,
                    app_name,
                    app_org,
                    app_name_global,
                )
                # Force consistency by updating our settings instance to match the application
                self.settings = QSettings(app_org, app_name_global)
                LOGGER.info(
                    "Corrected QSettings to: org=%s, app=%s, file=%s",
                    app_org,
                    app_name_global,
                    self.settings.fileName(),
                )

            # Save to multiple keys to ensure redundancy
            self.settings.setValue("preview/cropRectangle", rect_str)
            self.settings.setValue("cropRect", rect_str)  # Alternate key

            # Force immediate sync to disk
            self.settings.sync()

            # Verify the saved value
            saved_rect = self.settings.value("preview/cropRectangle", "", type=str)
            LOGGER.debug("Verification - Crop rectangle after direct save: %r", saved_rect)

            # Check if settings file exists and has appropriate size
            try:
                settings_file = Path(self.settings.fileName())
                if settings_file.exists():
                    LOGGER.debug(
                        "Settings file exists after crop save: %s (size: %d bytes)",
                        settings_file,
                        settings_file.stat().st_size,
                    )
                else:
                    LOGGER.warning(
                        "Settings file does not exist after crop save attempt: %s",
                        settings_file,
                    )
                    return False
            except Exception:
                LOGGER.exception("Error checking settings file after crop save")

            # Explicitly cast bool to avoid Any return type
            return bool(saved_rect == rect_str)
        except Exception:
            LOGGER.exception("Error directly saving crop rectangle")
            return False

    def set_crop_rect(self, rect: tuple[int, int, int, int] | None) -> bool:
        """Set the current crop rectangle state.

        Args:
            rect: The crop rectangle as (x, y, width, height), or None to clear

        Returns:
            True if the crop rect was successfully set and saved
        """
        LOGGER.debug("CropManager set_crop_rect called with rect: %s", rect)

        if self.current_crop_rect != rect:
            LOGGER.debug("CropManager setting crop_rect to: %s", rect)
            old_rect = self.current_crop_rect  # Store old rect for fallback
            self.current_crop_rect = rect

            # Save crop rectangle directly to settings
            if rect:
                success = self.save_crop_rect(rect)
                if not success:
                    LOGGER.error("Failed to save crop rectangle to settings!")
                    # If saving failed, try to revert to previous state
                    if old_rect:
                        LOGGER.warning("Crop rectangle not saved, attempting to revert to previous value")
                        self.save_crop_rect(old_rect)
                        self.current_crop_rect = old_rect
                    return False

            return True
        return True

    def get_crop_rect(self) -> tuple[int, int, int, int] | None:
        """Get the current crop rectangle.

        Returns:
            The crop rectangle as (x, y, width, height), or None if not set
        """
        return self.current_crop_rect

    def load_crop_rect(self) -> tuple[int, int, int, int] | None:
        """Load crop rectangle from settings.

        Returns:
            The loaded crop rectangle, or None if not found
        """
        if self.settings is None:
            return None

        try:
            # Try to load from primary key first
            rect_str = self.settings.value("preview/cropRectangle", "", type=str)
            if not rect_str:
                # Try alternate key
                rect_str = self.settings.value("cropRect", "", type=str)

            if rect_str and rect_str.strip():
                parts = rect_str.split(",")
                if len(parts) == 4:
                    try:
                        rect = (int(float(parts[0])), int(float(parts[1])), int(float(parts[2])), int(float(parts[3])))
                        self.current_crop_rect = rect
                        LOGGER.debug("Loaded crop rectangle from settings: %s", rect)
                        return self.current_crop_rect
                    except (ValueError, TypeError):
                        LOGGER.warning("Invalid crop rectangle format in settings: %s", rect_str)
                        return None
                else:
                    LOGGER.warning("Invalid crop rectangle format in settings: expected 4 values, got %d", len(parts))
                    return None
        except Exception:
            LOGGER.exception("Error loading crop rectangle from settings")

        return None

    def clear_crop_rect(self) -> None:
        """Clear the current crop rectangle."""
        LOGGER.debug("Clearing crop rectangle")
        self.current_crop_rect = None

        # Clear from settings if settings exists
        if self.settings is not None:
            self.settings.remove("preview/cropRectangle")
            self.settings.remove("cropRect")
            self.settings.sync()
