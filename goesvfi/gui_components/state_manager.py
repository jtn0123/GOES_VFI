"""State management functionality for MainWindow."""

from pathlib import Path
from typing import Any, Callable

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
        """Save all settings with atomic transaction and fallback on failure.

        Args:
            old_path: Previous path to revert to if save fails
        """
        # Create atomic settings transaction
        success = self._atomic_settings_save(self._save_input_directory_settings)

        if not success and old_path:
            LOGGER.warning("Settings save failed, reverting to previous path: %s", old_path)
            # Try to revert atomically
            self._atomic_settings_save(lambda: self.main_window._save_input_directory(old_path))

    def _save_all_settings_with_crop_fallback(self, old_rect: tuple[int, int, int, int] | None) -> None:
        """Save all settings with atomic transaction and fallback for crop rect.

        Args:
            old_rect: Previous rect to revert to if save fails
        """
        # Create atomic settings transaction
        success = self._atomic_settings_save(self._save_crop_settings)

        if not success and old_rect:
            LOGGER.warning("Crop settings save failed, reverting to previous rect: %s", old_rect)
            # Try to revert atomically
            self._atomic_settings_save(lambda: self.main_window._save_crop_rect(old_rect))

    def _atomic_settings_save(self, save_operation: Callable[[], None]) -> bool:
        """Perform atomic settings save operation with verification.

        Args:
            save_operation: Function to perform the save operation

        Returns:
            True if save was successful and verified, False otherwise
        """
        try:
            # Force settings sync before operation
            self.main_window.settings.sync()

            # Store pre-operation state for verification
            pre_state = self._capture_settings_state()

            # Perform the save operation
            save_operation()

            # Force sync and verify
            self.main_window.settings.sync()

            # Verify the operation succeeded
            post_state = self._capture_settings_state()
            success = self._verify_settings_change(pre_state, post_state)

            if success:
                LOGGER.debug("Atomic settings save completed successfully")
            else:
                LOGGER.error("Settings save verification failed")

            return success

        except Exception as e:
            LOGGER.exception("Error during atomic settings save: %s", e)
            return False

    def _capture_settings_state(self) -> dict[str, Any]:
        """Capture current settings state for verification.

        Returns:
            Dictionary of current settings values
        """
        state = {}
        try:
            # Capture key settings that we care about
            state["input_directory"] = self.main_window.settings.value("paths/inputDirectory", "", type=str)
            state["crop_rectangle"] = self.main_window.settings.value("preview/cropRectangle", "", type=str)
            state["output_directory"] = self.main_window.settings.value("paths/outputDirectory", "", type=str)
        except Exception as e:
            LOGGER.exception("Error capturing settings state: %s", e)
        return state

    def _verify_settings_change(self, pre_state: dict[str, Any], post_state: dict[str, Any]) -> bool:
        """Verify that settings change was applied correctly.

        Args:
            pre_state: Settings state before operation
            post_state: Settings state after operation

        Returns:
            True if verification passed, False otherwise
        """
        try:
            # Check if any settings actually changed
            changes_detected = False
            for key in post_state:
                if post_state[key] != pre_state.get(key):
                    LOGGER.debug("Settings change verified for %s: %s -> %s", key, pre_state.get(key), post_state[key])
                    changes_detected = True

                    # Additional validation: ensure the new value is not empty when we expect a value
                    if key in ["input_directory", "crop_rectangle"] and not post_state[key]:
                        LOGGER.warning("Settings verification failed: %s is empty after save", key)
                        return False

            # If we expected changes but didn't detect any, verification fails
            # This can happen if the save operation silently failed
            if not changes_detected:
                LOGGER.warning("Settings verification failed: no changes detected after save operation")
                return False

            return True
        except Exception as e:
            LOGGER.exception("Settings verification failed: %s", e)
            return False

    def _save_input_directory_settings(self) -> None:
        """Save input directory settings."""
        if hasattr(self.main_window.main_tab, "save_settings"):
            LOGGER.info("Saving input directory settings")
            self.main_window.main_tab.save_settings()
        else:
            LOGGER.warning("Main tab save_settings method not available")

    def _save_crop_settings(self) -> None:
        """Save crop rectangle settings."""
        if hasattr(self.main_window.main_tab, "save_settings"):
            LOGGER.info("Saving crop rectangle settings")
            self.main_window.main_tab.save_settings()
        else:
            LOGGER.warning("Main tab save_settings method not available")
