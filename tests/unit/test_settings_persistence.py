"""Fast, optimized tests for settings persistence - high business value."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from PyQt6.QtCore import QSettings

from goesvfi.gui_components.settings_persistence import SettingsPersistence


class TestSettingsPersistence:
    """Test settings persistence with fast, mocked operations."""

    @pytest.fixture
    def mock_settings(self):
        """Mock QSettings to avoid file I/O."""
        settings = MagicMock(spec=QSettings)
        settings._storage = {}

        def mock_value(key, default=None, type=None):
            value = settings._storage.get(key, default)
            if type and value is not None:
                return type(value)
            return value

        def mock_set_value(key, value):
            settings._storage[key] = value

        def mock_all_keys():
            return list(settings._storage.keys())

        settings.value.side_effect = mock_value
        settings.setValue.side_effect = mock_set_value
        settings.allKeys.side_effect = mock_all_keys
        settings.sync.return_value = None

        # Mock organization/application names to match empty defaults
        settings.organizationName.return_value = ""
        settings.applicationName.return_value = ""
        settings.fileName.return_value = "/mock/settings/file.plist"

        return settings

    @pytest.fixture
    def settings_manager(self, mock_settings, mocker):
        """Create settings persistence manager with mocked QSettings."""
        # Mock the file existence check to always return True
        mock_path = mocker.patch("pathlib.Path.exists")
        mock_path.return_value = True

        # Mock the file stat
        mock_stat = mocker.MagicMock()
        mock_stat.st_size = 1024
        mocker.patch("pathlib.Path.stat", return_value=mock_stat)

        return SettingsPersistence(mock_settings)

    def test_save_input_directory(self, settings_manager, mock_settings):
        """Test saving input directory."""
        test_path = Path("/test/input/directory")

        result = settings_manager.save_input_directory(test_path)

        assert result is True
        # Verify the setting was saved (actual implementation uses multiple keys)
        mock_settings.setValue.assert_any_call("paths/inputDirectory", str(test_path.resolve()))

    def test_save_crop_rect(self, settings_manager, mock_settings):
        """Test saving crop rectangle."""
        test_rect = (10, 20, 100, 200)

        result = settings_manager.save_crop_rect(test_rect)

        assert result is True
        # Verify the setting was saved
        mock_settings.setValue.assert_any_call("preview/cropRectangle", "10,20,100,200")

    def test_save_crop_rect_validation(self, settings_manager, mock_settings):
        """Test crop rectangle validation."""
        # Test with None
        result = settings_manager.save_crop_rect(None)
        assert result is False

        # Test with valid rectangle
        valid_rect = (0, 0, 640, 480)
        result = settings_manager.save_crop_rect(valid_rect)
        assert result is True

    def test_save_input_directory_validation(self, settings_manager, mock_settings):
        """Test input directory validation."""
        # Test with None
        result = settings_manager.save_input_directory(None)
        assert result is False

        # Test with valid path
        valid_path = Path("/valid/test/path")
        result = settings_manager.save_input_directory(valid_path)
        assert result is True

    def test_path_string_conversion(self, settings_manager, mock_settings):
        """Test that paths are properly converted to strings for storage."""
        test_paths = [
            Path("/unix/style/path"),
            Path("relative/path")
        ]

        for path in test_paths:
            result = settings_manager.save_input_directory(path)
            assert result is True
            # Verify string conversion (actual implementation uses resolved paths)
            mock_settings.setValue.assert_any_call("paths/inputDirectory", str(path.resolve()))

    def test_settings_sync_called(self, settings_manager, mock_settings):
        """Test that settings are synced after save operations."""
        test_path = Path("/test/sync/path")

        settings_manager.save_input_directory(test_path)

        # Verify sync was called
        mock_settings.sync.assert_called()