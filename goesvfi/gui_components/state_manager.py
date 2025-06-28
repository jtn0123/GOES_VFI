"""State management functionality for MainWindow."""

from pathlib import Path
from typing import Any

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class StateManager:
    """Manages state updates and related UI coordination."""

    def __init__(self, main_window: Any) -> None:
        """Initialize the state manager.

        Args:
            main_window: Reference to the MainWindow instance
        """
        self.main_window = main_window

    def set_input_directory(self, path: Path | None) -> None:
        """Set the input directory state, save settings, and clear Sanchez cache.

        Args:
            path: The new input directory path, or None to clear
        """
        LOGGER.debug("StateManager set_input_directory called with path: %s", path)

        if self.main_window.in_dir != path:
            LOGGER.debug("Setting in_dir to: %s", path)
            old_path = self.main_window.in_dir
            self.main_window.in_dir = path
            self.main_window.sanchez_preview_cache.clear()  # Clear cache when dir changes

            # Update UI elements
            self._update_ui_for_input_dir_change()

            # Trigger preview update
            self.main_window.request_previews_update.emit()

            # Save input directory
            if path:
                success = self.main_window._save_input_directory(path)
                if not success:
                    LOGGER.error("Failed to save input directory to settings!")

                # Update UI text field
                if hasattr(self.main_window.main_tab, "in_dir_edit"):
                    self.main_window.main_tab.in_dir_edit.setText(str(path))

            # Save all settings
            self._save_all_settings_with_fallback(old_path)

        # Always update crop buttons state
        if hasattr(self.main_window.main_tab, "_update_crop_buttons_state"):
            self.main_window.main_tab._update_crop_buttons_state()

    def set_crop_rect(self, rect: tuple[int, int, int, int] | None) -> None:
        """Set the current crop rectangle state.

        Args:
            rect: The crop rectangle as (x, y, width, height), or None to clear
        """
        LOGGER.debug("StateManager set_crop_rect called with rect: %s", rect)

        if self.main_window.current_crop_rect != rect:
            LOGGER.debug("Setting crop_rect to: %s", rect)
            old_rect = self.main_window.current_crop_rect
            self.main_window.current_crop_rect = rect

            # Trigger preview and button updates
            self.main_window.request_previews_update.emit()
            self._update_crop_buttons()

            # Save crop rectangle
            if rect:
                success = self.main_window._save_crop_rect(rect)
                if not success:
                    LOGGER.error("Failed to save crop rectangle to settings!")

            # Update FFmpeg settings tab
            if hasattr(self.main_window, "ffmpeg_settings_tab") and hasattr(
                self.main_window.ffmpeg_settings_tab, "set_crop_rect"
            ):
                self.main_window.ffmpeg_settings_tab.set_crop_rect(rect)

            # Save all settings
            self._save_all_settings_with_crop_fallback(old_rect)

    def _update_ui_for_input_dir_change(self) -> None:
        """Update UI elements when input directory changes."""
        # Update start button state
        LOGGER.debug("Updating start button state due to input directory change")
        if hasattr(self.main_window.main_tab, "_update_start_button_state"):
            self.main_window.main_tab._update_start_button_state()
        else:
            LOGGER.warning("Cannot update start button - method not found")

    def _update_crop_buttons(self) -> None:
        """Update crop button states."""
        if hasattr(self.main_window, "main_tab") and hasattr(self.main_window.main_tab, "_update_crop_buttons_state"):
            self.main_window.main_tab._update_crop_buttons_state()
        else:
            LOGGER.warning("Could not call main_tab._update_crop_buttons_state()")

    def _save_all_settings_with_fallback(self, old_path: Path | None) -> None:
        """Save all settings with fallback on failure.

        Args:
            old_path: Previous path to revert to if save fails
        """
        try:
            if hasattr(self.main_window.main_tab, "save_settings"):
                LOGGER.info("Saving all settings due to input directory change")
                self.main_window.main_tab.save_settings()

                # Final verification
                if self.main_window.in_dir:
                    saved_dir = self.main_window.settings.value("paths/inputDirectory", "", type=str)
                    LOGGER.debug("Final verification - Input directory: %s", saved_dir)

                    # If saving failed, try to revert
                    if not saved_dir and old_path:
                        LOGGER.warning("Input directory not saved, attempting to revert to previous value")
                        self.main_window._save_input_directory(old_path)
        except Exception as e:
            LOGGER.exception("Error saving settings after input directory change: %s", e)

    def _save_all_settings_with_crop_fallback(self, old_rect: tuple[int, int, int, int] | None) -> None:
        """Save all settings with fallback for crop rect.

        Args:
            old_rect: Previous rect to revert to if save fails
        """
        try:
            if hasattr(self.main_window.main_tab, "save_settings"):
                LOGGER.info("Saving all settings due to crop rectangle change")
                self.main_window.main_tab.save_settings()

                # Final verification
                if self.main_window.current_crop_rect:
                    saved_rect = self.main_window.settings.value("preview/cropRectangle", "", type=str)
                    LOGGER.debug("Final verification - Crop rectangle: %s", saved_rect)

                    # If saving failed, try to revert
                    if not saved_rect and old_rect:
                        LOGGER.warning("Crop rectangle not saved, attempting to revert to previous value")
                        self.main_window._save_crop_rect(old_rect)
        except Exception as e:
            LOGGER.exception("Error saving settings after crop rectangle change: %s", e)
