"""Tests for StateManager functionality - Optimized v2."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from goesvfi.gui_components.state_manager import StateManager


# Shared fixtures and test data
@pytest.fixture(scope="session")
def path_scenarios():
    """Pre-defined path scenarios for testing."""
    return {
        "new_path": Path("/test/input"),
        "existing_path": Path("/existing/path"),
        "none_path": None,
    }


@pytest.fixture(scope="session")
def crop_rect_scenarios():
    """Pre-defined crop rectangle scenarios for testing."""
    return {
        "new_rect": (10, 20, 300, 400),
        "existing_rect": (5, 10, 200, 300),
        "none_rect": None,
    }


@pytest.fixture()
def mock_main_window():
    """Create a comprehensive mock main window for testing."""
    main_window = Mock()

    # Main window attributes
    main_window.in_dir = None
    main_window.current_crop_rect = None
    main_window.sanchez_preview_cache = Mock()
    main_window.request_previews_update = Mock()
    main_window._save_input_directory = Mock(return_value=True)
    main_window._save_crop_rect = Mock(return_value=True)
    main_window.settings = Mock()

    # Main tab
    main_tab = Mock()
    main_tab.in_dir_edit = Mock()
    main_tab._update_crop_buttons_state = Mock()
    main_tab._update_start_button_state = Mock()
    main_tab.save_settings = Mock()
    main_window.main_tab = main_tab

    # FFmpeg settings tab
    ffmpeg_tab = Mock()
    ffmpeg_tab.set_crop_rect = Mock()
    main_window.ffmpeg_settings_tab = ffmpeg_tab

    return main_window


@pytest.fixture()
def state_manager(mock_main_window):
    """Create StateManager instance for testing."""
    return StateManager(mock_main_window)


class TestStateManager:
    """Test StateManager functionality with optimized test patterns."""

    def test_initialization(self, mock_main_window) -> None:
        """Test StateManager initialization."""
        manager = StateManager(mock_main_window)
        assert manager.main_window is mock_main_window

    @pytest.mark.parametrize(
        "path_scenario,should_clear_cache,should_update_ui",
        [
            ("new_path", True, True),  # New path - full update
            ("existing_path", False, False),  # Same path - minimal update
            ("none_path", True, False),  # Clear path - cache clear only
        ],
    )
    def test_set_input_directory(
        self,
        state_manager,
        mock_main_window,
        path_scenarios,
        path_scenario: str,
        should_clear_cache: bool,
        should_update_ui: bool,
    ) -> None:
        """Test setting input directory with different scenarios."""
        path = path_scenarios[path_scenario]

        # Set existing path for comparison test
        if path_scenario == "existing_path":
            mock_main_window.in_dir = path

        state_manager.set_input_directory(path)

        # Check state update
        assert mock_main_window.in_dir == path

        # Check cache clearing
        if should_clear_cache:
            mock_main_window.sanchez_preview_cache.clear.assert_called_once()
        else:
            mock_main_window.sanchez_preview_cache.clear.assert_not_called()

        # Check UI updates
        if should_update_ui:
            mock_main_window.request_previews_update.emit.assert_called_once()
            mock_main_window.main_tab._update_start_button_state.assert_called_once()
        else:
            mock_main_window.request_previews_update.emit.assert_not_called()

        # Crop buttons should always be updated
        mock_main_window.main_tab._update_crop_buttons_state.assert_called_once()

        # Check saving behavior
        if path is not None:
            mock_main_window._save_input_directory.assert_called_once_with(path)
            mock_main_window.main_tab.in_dir_edit.setText.assert_called_once_with(str(path))
            mock_main_window.main_tab.save_settings.assert_called_once()
        else:
            mock_main_window._save_input_directory.assert_not_called()
            mock_main_window.main_tab.in_dir_edit.setText.assert_not_called()

    @pytest.mark.parametrize("save_success", [True, False])
    def test_set_input_directory_save_handling(
        self, state_manager, mock_main_window, path_scenarios, save_success: bool
    ) -> None:
        """Test input directory save success/failure handling."""
        path = path_scenarios["new_path"]
        mock_main_window._save_input_directory.return_value = save_success

        with patch("goesvfi.gui_components.state_manager.LOGGER") as mock_logger:
            state_manager.set_input_directory(path)

            if save_success:
                mock_logger.error.assert_not_called()
            else:
                mock_logger.error.assert_called_once()

    @pytest.mark.parametrize(
        "crop_scenario,should_update_ui,should_save",
        [
            ("new_rect", True, True),  # New rect - full update
            ("existing_rect", False, False),  # Same rect - no update
            ("none_rect", True, False),  # Clear rect - update but no save
        ],
    )
    def test_set_crop_rect(
        self,
        state_manager,
        mock_main_window,
        crop_rect_scenarios,
        crop_scenario: str,
        should_update_ui: bool,
        should_save: bool,
    ) -> None:
        """Test setting crop rectangle with different scenarios."""
        rect = crop_rect_scenarios[crop_scenario]

        # Set existing rect for comparison test
        if crop_scenario == "existing_rect":
            mock_main_window.current_crop_rect = rect

        state_manager.set_crop_rect(rect)

        # Check state update
        assert mock_main_window.current_crop_rect == rect

        # Check UI updates
        if should_update_ui:
            mock_main_window.request_previews_update.emit.assert_called_once()
            mock_main_window.main_tab._update_crop_buttons_state.assert_called_once()
        else:
            mock_main_window.request_previews_update.emit.assert_not_called()

        # Check saving behavior
        if should_save:
            mock_main_window._save_crop_rect.assert_called_once_with(rect)
            mock_main_window.ffmpeg_settings_tab.set_crop_rect.assert_called_once_with(rect)
            mock_main_window.main_tab.save_settings.assert_called_once()
        else:
            mock_main_window._save_crop_rect.assert_not_called()

    @pytest.mark.parametrize("save_success", [True, False])
    def test_set_crop_rect_save_handling(
        self, state_manager, mock_main_window, crop_rect_scenarios, save_success: bool
    ) -> None:
        """Test crop rect save success/failure handling."""
        rect = crop_rect_scenarios["new_rect"]
        mock_main_window._save_crop_rect.return_value = save_success

        with patch("goesvfi.gui_components.state_manager.LOGGER") as mock_logger:
            state_manager.set_crop_rect(rect)

            if save_success:
                mock_logger.error.assert_not_called()
            else:
                mock_logger.error.assert_called_once()

    @pytest.mark.parametrize(
        "missing_components",
        [
            ["in_dir_edit"],
            ["_update_start_button_state"],
            ["ffmpeg_settings_tab"],
            ["in_dir_edit", "_update_start_button_state"],
        ],
    )
    def test_missing_ui_components_handling(
        self, state_manager, mock_main_window, path_scenarios, missing_components: list[str]
    ) -> None:
        """Test handling when UI components are missing."""
        # Remove specified components
        for component in missing_components:
            if component == "ffmpeg_settings_tab":
                delattr(mock_main_window, component)
            else:
                delattr(mock_main_window.main_tab, component)

        path = path_scenarios["new_path"]

        with patch("goesvfi.gui_components.state_manager.LOGGER") as mock_logger:
            # Should not raise exception
            state_manager.set_input_directory(path)

            # Should log warnings for missing components
            if "_update_start_button_state" in missing_components:
                mock_logger.warning.assert_called()

        # Basic state should still be updated
        assert mock_main_window.in_dir == path

    def test_update_crop_buttons_missing_method(self, state_manager, mock_main_window) -> None:
        """Test _update_crop_buttons when method is missing."""
        delattr(mock_main_window.main_tab, "_update_crop_buttons_state")

        with patch("goesvfi.gui_components.state_manager.LOGGER") as mock_logger:
            state_manager._update_crop_buttons()

            # Should log warning
            mock_logger.warning.assert_called_once()

    @pytest.mark.parametrize(
        "settings_save_success,verification_success",
        [
            (True, True),  # Normal save and verify
            (True, False),  # Save appears to work but verify fails
            (False, False),  # Save fails immediately
        ],
    )
    def test_save_all_settings_with_fallback(
        self, state_manager, mock_main_window, path_scenarios, settings_save_success: bool, verification_success: bool
    ) -> None:
        """Test settings save with fallback handling."""
        old_path = path_scenarios["existing_path"]
        new_path = path_scenarios["new_path"]
        mock_main_window.in_dir = new_path

        # Configure save and verification behavior
        if not settings_save_success:
            mock_main_window.main_tab.save_settings.side_effect = Exception("Save failed")

        mock_main_window.settings.value.return_value = str(new_path) if verification_success else ""

        with patch("goesvfi.gui_components.state_manager.LOGGER") as mock_logger:
            state_manager._save_all_settings_with_fallback(old_path)

            if settings_save_success and verification_success:
                # Should save and verify successfully
                mock_main_window.main_tab.save_settings.assert_called_once()
                mock_main_window.settings.value.assert_called_once_with("paths/inputDirectory", "", type=str)
                mock_logger.warning.assert_not_called()
            elif settings_save_success and not verification_success:
                # Should attempt revert after failed verification
                mock_main_window._save_input_directory.assert_called_with(old_path)
                mock_logger.warning.assert_called_once()
            else:
                # Should log error for save failure
                mock_logger.error.assert_called_once()

    @pytest.mark.parametrize(
        "settings_save_success,verification_success",
        [
            (True, True),  # Normal save and verify
            (True, False),  # Save appears to work but verify fails
            (False, False),  # Save fails immediately
        ],
    )
    def test_save_all_settings_with_crop_fallback(
        self,
        state_manager,
        mock_main_window,
        crop_rect_scenarios,
        settings_save_success: bool,
        verification_success: bool,
    ) -> None:
        """Test crop settings save with fallback handling."""
        old_rect = crop_rect_scenarios["existing_rect"]
        new_rect = crop_rect_scenarios["new_rect"]
        mock_main_window.current_crop_rect = new_rect

        # Configure save and verification behavior
        if not settings_save_success:
            mock_main_window.main_tab.save_settings.side_effect = Exception("Save failed")

        expected_rect_str = "10,20,300,400" if verification_success else ""
        mock_main_window.settings.value.return_value = expected_rect_str

        with patch("goesvfi.gui_components.state_manager.LOGGER") as mock_logger:
            state_manager._save_all_settings_with_crop_fallback(old_rect)

            if settings_save_success and verification_success:
                # Should save and verify successfully
                mock_main_window.main_tab.save_settings.assert_called_once()
                mock_main_window.settings.value.assert_called_once_with("preview/cropRectangle", "", type=str)
                mock_logger.warning.assert_not_called()
            elif settings_save_success and not verification_success:
                # Should attempt revert after failed verification
                mock_main_window._save_crop_rect.assert_called_with(old_rect)
                mock_logger.warning.assert_called_once()
            else:
                # Should log error for save failure
                mock_logger.error.assert_called_once()

    def test_missing_main_tab_save_settings(self, state_manager, mock_main_window) -> None:
        """Test handling when main_tab doesn't have save_settings method."""
        delattr(mock_main_window.main_tab, "save_settings")

        # Should not raise exception
        state_manager._save_all_settings_with_fallback(None)
        state_manager._save_all_settings_with_crop_fallback(None)

    def test_integration_workflow(self, state_manager, mock_main_window, path_scenarios, crop_rect_scenarios) -> None:
        """Test complete workflow of setting input directory and crop rectangle."""
        input_path = path_scenarios["new_path"]
        crop_rect = crop_rect_scenarios["new_rect"]

        # Set input directory first
        state_manager.set_input_directory(input_path)
        assert mock_main_window.in_dir == input_path

        # Reset mocks to track only crop rect operations
        mock_main_window.request_previews_update.reset_mock()
        mock_main_window.main_tab.save_settings.reset_mock()

        # Set crop rectangle
        state_manager.set_crop_rect(crop_rect)
        assert mock_main_window.current_crop_rect == crop_rect

        # Both should be properly configured
        assert mock_main_window.main_tab.save_settings.call_count == 1

    def test_state_manager_with_minimal_main_window(self, mock_main_window) -> None:
        """Test StateManager with minimal main window setup."""
        # Remove optional components
        delattr(mock_main_window, "main_tab")
        delattr(mock_main_window, "ffmpeg_settings_tab")

        manager = StateManager(mock_main_window)

        # Should not raise exceptions
        manager.set_input_directory(Path("/test"))
        manager.set_crop_rect((10, 20, 300, 400))

        # Basic state should still be updated
        assert mock_main_window.in_dir == Path("/test")
        assert mock_main_window.current_crop_rect == (10, 20, 300, 400)

    @pytest.mark.parametrize(
        "operation_sequence",
        [
            ["set_input", "set_crop", "set_input_none", "set_crop_none"],
            ["set_crop", "set_input", "set_crop", "set_input"],
            ["set_input", "set_input", "set_crop", "set_crop"],
        ],
    )
    def test_operation_sequence_robustness(
        self, state_manager, mock_main_window, path_scenarios, crop_rect_scenarios, operation_sequence: list[str]
    ) -> None:
        """Test robustness with different operation sequences."""
        for operation in operation_sequence:
            if operation == "set_input":
                state_manager.set_input_directory(path_scenarios["new_path"])
            elif operation == "set_input_none":
                state_manager.set_input_directory(None)
            elif operation == "set_crop":
                state_manager.set_crop_rect(crop_rect_scenarios["new_rect"])
            elif operation == "set_crop_none":
                state_manager.set_crop_rect(None)

        # Should complete without errors
        # Final state depends on last operations but should be consistent
        assert hasattr(mock_main_window, "in_dir")
        assert hasattr(mock_main_window, "current_crop_rect")
