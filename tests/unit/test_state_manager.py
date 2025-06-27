"""Tests for StateManager functionality."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from goesvfi.gui_components.state_manager import StateManager


class TestStateManager:
    """Test StateManager functionality."""

    @pytest.fixture()
    def mock_main_window(self):
        """Create a mock main window for testing."""
        main_window = Mock()
        main_window.in_dir = None
        main_window.current_crop_rect = None
        main_window.sanchez_preview_cache = Mock()
        main_window.request_previews_update = Mock()
        main_window._save_input_directory = Mock(return_value=True)
        main_window._save_crop_rect = Mock(return_value=True)
        main_window.settings = Mock()

        # Mock main tab
        main_tab = Mock()
        main_tab.in_dir_edit = Mock()
        main_tab._update_crop_buttons_state = Mock()
        main_tab._update_start_button_state = Mock()
        main_tab.save_settings = Mock()
        main_window.main_tab = main_tab

        # Mock FFmpeg settings tab
        ffmpeg_tab = Mock()
        ffmpeg_tab.set_crop_rect = Mock()
        main_window.ffmpeg_settings_tab = ffmpeg_tab

        return main_window

    @pytest.fixture()
    def state_manager(self, mock_main_window):
        """Create StateManager instance for testing."""
        return StateManager(mock_main_window)

    def test_initialization(self, mock_main_window) -> None:
        """Test StateManager initialization."""
        manager = StateManager(mock_main_window)
        assert manager.main_window is mock_main_window

    def test_set_input_directory_new_path(self, state_manager, mock_main_window) -> None:
        """Test setting a new input directory."""
        new_path = Path("/test/input")

        state_manager.set_input_directory(new_path)

        # Check state was updated
        assert mock_main_window.in_dir == new_path

        # Check cache was cleared
        mock_main_window.sanchez_preview_cache.clear.assert_called_once()

        # Check UI updates
        mock_main_window.request_previews_update.emit.assert_called_once()
        mock_main_window.main_tab._update_start_button_state.assert_called_once()
        mock_main_window.main_tab._update_crop_buttons_state.assert_called_once()

        # Check directory saving
        mock_main_window._save_input_directory.assert_called_once_with(new_path)
        mock_main_window.main_tab.in_dir_edit.setText.assert_called_once_with(str(new_path))
        mock_main_window.main_tab.save_settings.assert_called_once()

    def test_set_input_directory_same_path(self, state_manager, mock_main_window) -> None:
        """Test setting the same input directory (should still update crop buttons)."""
        existing_path = Path("/existing/path")
        mock_main_window.in_dir = existing_path

        state_manager.set_input_directory(existing_path)

        # Should not update in_dir or clear cache
        assert mock_main_window.in_dir == existing_path
        mock_main_window.sanchez_preview_cache.clear.assert_not_called()
        mock_main_window.request_previews_update.emit.assert_not_called()

        # But should still update crop buttons
        mock_main_window.main_tab._update_crop_buttons_state.assert_called_once()

    def test_set_input_directory_none(self, state_manager, mock_main_window) -> None:
        """Test clearing input directory."""
        mock_main_window.in_dir = Path("/existing/path")

        state_manager.set_input_directory(None)

        # Check state was cleared
        assert mock_main_window.in_dir is None

        # Check cache was cleared
        mock_main_window.sanchez_preview_cache.clear.assert_called_once()

        # Should not call save_input_directory or set text field
        mock_main_window._save_input_directory.assert_not_called()
        mock_main_window.main_tab.in_dir_edit.setText.assert_not_called()

    def test_set_input_directory_save_failure(self, state_manager, mock_main_window) -> None:
        """Test handling of input directory save failure."""
        new_path = Path("/test/input")
        mock_main_window._save_input_directory.return_value = False

        with patch("goesvfi.gui_components.state_manager.LOGGER") as mock_logger:
            state_manager.set_input_directory(new_path)

            # Should log error
            mock_logger.error.assert_called_once()

    def test_set_input_directory_missing_ui_elements(self, state_manager, mock_main_window) -> None:
        """Test handling when UI elements are missing."""
        # Remove some UI elements
        delattr(mock_main_window.main_tab, "in_dir_edit")
        delattr(mock_main_window.main_tab, "_update_start_button_state")

        new_path = Path("/test/input")

        with patch("goesvfi.gui_components.state_manager.LOGGER") as mock_logger:
            # Should not raise exception
            state_manager.set_input_directory(new_path)

            # Should log warning for missing start button update
            mock_logger.warning.assert_called()

    def test_set_crop_rect_new_rect(self, state_manager, mock_main_window) -> None:
        """Test setting a new crop rectangle."""
        new_rect = (10, 20, 300, 400)

        state_manager.set_crop_rect(new_rect)

        # Check state was updated
        assert mock_main_window.current_crop_rect == new_rect

        # Check UI updates
        mock_main_window.request_previews_update.emit.assert_called_once()
        mock_main_window.main_tab._update_crop_buttons_state.assert_called_once()

        # Check saving
        mock_main_window._save_crop_rect.assert_called_once_with(new_rect)
        mock_main_window.ffmpeg_settings_tab.set_crop_rect.assert_called_once_with(new_rect)
        mock_main_window.main_tab.save_settings.assert_called_once()

    def test_set_crop_rect_same_rect(self, state_manager, mock_main_window) -> None:
        """Test setting the same crop rectangle."""
        existing_rect = (10, 20, 300, 400)
        mock_main_window.current_crop_rect = existing_rect

        state_manager.set_crop_rect(existing_rect)

        # Should not update state or trigger updates
        assert mock_main_window.current_crop_rect == existing_rect
        mock_main_window.request_previews_update.emit.assert_not_called()
        mock_main_window._save_crop_rect.assert_not_called()

    def test_set_crop_rect_none(self, state_manager, mock_main_window) -> None:
        """Test clearing crop rectangle."""
        mock_main_window.current_crop_rect = (10, 20, 300, 400)

        state_manager.set_crop_rect(None)

        # Check state was cleared
        assert mock_main_window.current_crop_rect is None

        # Check UI updates
        mock_main_window.request_previews_update.emit.assert_called_once()
        mock_main_window.main_tab._update_crop_buttons_state.assert_called_once()

        # Should not call save methods for None
        mock_main_window._save_crop_rect.assert_not_called()

    def test_set_crop_rect_save_failure(self, state_manager, mock_main_window) -> None:
        """Test handling of crop rect save failure."""
        new_rect = (10, 20, 300, 400)
        mock_main_window._save_crop_rect.return_value = False

        with patch("goesvfi.gui_components.state_manager.LOGGER") as mock_logger:
            state_manager.set_crop_rect(new_rect)

            # Should log error
            mock_logger.error.assert_called_once()

    def test_set_crop_rect_missing_ffmpeg_tab(self, state_manager, mock_main_window) -> None:
        """Test handling when FFmpeg tab is missing."""
        delattr(mock_main_window, "ffmpeg_settings_tab")

        new_rect = (10, 20, 300, 400)

        # Should not raise exception
        state_manager.set_crop_rect(new_rect)

        # State should still be updated
        assert mock_main_window.current_crop_rect == new_rect

    def test_update_crop_buttons_missing_method(self, state_manager, mock_main_window) -> None:
        """Test _update_crop_buttons when method is missing."""
        delattr(mock_main_window.main_tab, "_update_crop_buttons_state")

        with patch("goesvfi.gui_components.state_manager.LOGGER") as mock_logger:
            state_manager._update_crop_buttons()

            # Should log warning
            mock_logger.warning.assert_called_once()

    def test_save_all_settings_with_fallback_success(self, state_manager, mock_main_window) -> None:
        """Test successful settings save with fallback."""
        old_path = Path("/old/path")
        mock_main_window.in_dir = Path("/new/path")
        mock_main_window.settings.value.return_value = "/new/path"

        state_manager._save_all_settings_with_fallback(old_path)

        # Should save settings
        mock_main_window.main_tab.save_settings.assert_called_once()

        # Should verify the save
        mock_main_window.settings.value.assert_called_once_with("paths/inputDirectory", "", type=str)

    def test_save_all_settings_with_fallback_failure(self, state_manager, mock_main_window) -> None:
        """Test settings save failure with fallback."""
        old_path = Path("/old/path")
        mock_main_window.in_dir = Path("/new/path")
        mock_main_window.settings.value.return_value = ""  # Save failed

        with patch("goesvfi.gui_components.state_manager.LOGGER") as mock_logger:
            state_manager._save_all_settings_with_fallback(old_path)

            # Should attempt to revert
            mock_main_window._save_input_directory.assert_called_with(old_path)
            mock_logger.warning.assert_called_once()

    def test_save_all_settings_with_fallback_exception(self, state_manager, mock_main_window) -> None:
        """Test exception handling in settings save with fallback."""
        old_path = Path("/old/path")
        mock_main_window.main_tab.save_settings.side_effect = Exception("Save failed")

        with patch("goesvfi.gui_components.state_manager.LOGGER") as mock_logger:
            # Should not raise exception
            state_manager._save_all_settings_with_fallback(old_path)

            # Should log error
            mock_logger.error.assert_called_once()

    def test_save_all_settings_with_crop_fallback_success(self, state_manager, mock_main_window) -> None:
        """Test successful crop settings save with fallback."""
        old_rect = (5, 10, 200, 300)
        mock_main_window.current_crop_rect = (10, 20, 300, 400)
        mock_main_window.settings.value.return_value = "10,20,300,400"

        state_manager._save_all_settings_with_crop_fallback(old_rect)

        # Should save settings
        mock_main_window.main_tab.save_settings.assert_called_once()

        # Should verify the save
        mock_main_window.settings.value.assert_called_once_with("preview/cropRectangle", "", type=str)

    def test_save_all_settings_with_crop_fallback_failure(self, state_manager, mock_main_window) -> None:
        """Test crop settings save failure with fallback."""
        old_rect = (5, 10, 200, 300)
        mock_main_window.current_crop_rect = (10, 20, 300, 400)
        mock_main_window.settings.value.return_value = ""  # Save failed

        with patch("goesvfi.gui_components.state_manager.LOGGER") as mock_logger:
            state_manager._save_all_settings_with_crop_fallback(old_rect)

            # Should attempt to revert
            mock_main_window._save_crop_rect.assert_called_with(old_rect)
            mock_logger.warning.assert_called_once()

    def test_save_all_settings_with_crop_fallback_exception(self, state_manager, mock_main_window) -> None:
        """Test exception handling in crop settings save with fallback."""
        old_rect = (5, 10, 200, 300)
        mock_main_window.main_tab.save_settings.side_effect = Exception("Save failed")

        with patch("goesvfi.gui_components.state_manager.LOGGER") as mock_logger:
            # Should not raise exception
            state_manager._save_all_settings_with_crop_fallback(old_rect)

            # Should log error
            mock_logger.error.assert_called_once()

    def test_missing_main_tab_save_settings(self, state_manager, mock_main_window) -> None:
        """Test handling when main_tab doesn't have save_settings method."""
        delattr(mock_main_window.main_tab, "save_settings")

        # Should not raise exception
        state_manager._save_all_settings_with_fallback(None)
        state_manager._save_all_settings_with_crop_fallback(None)

    def test_integration_set_input_dir_then_crop(self, state_manager, mock_main_window) -> None:
        """Test setting input directory followed by crop rectangle."""
        input_path = Path("/test/input")
        crop_rect = (10, 20, 300, 400)

        # Set input directory first
        state_manager.set_input_directory(input_path)
        assert mock_main_window.in_dir == input_path

        # Reset mocks
        mock_main_window.request_previews_update.reset_mock()
        mock_main_window.main_tab.save_settings.reset_mock()

        # Set crop rectangle
        state_manager.set_crop_rect(crop_rect)
        assert mock_main_window.current_crop_rect == crop_rect

        # Both should be saved
        assert mock_main_window.main_tab.save_settings.call_count == 1

    def test_state_manager_with_minimal_main_window(self, mock_main_window) -> None:
        """Test StateManager with minimal main window setup."""
        # Remove optional attributes
        delattr(mock_main_window, "main_tab")
        delattr(mock_main_window, "ffmpeg_settings_tab")

        manager = StateManager(mock_main_window)

        # Should not raise exceptions
        manager.set_input_directory(Path("/test"))
        manager.set_crop_rect((10, 20, 300, 400))

        # Basic state should still be updated
        assert mock_main_window.in_dir == Path("/test")
        assert mock_main_window.current_crop_rect == (10, 20, 300, 400)
