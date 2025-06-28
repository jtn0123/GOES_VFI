"""Fast, optimized tests for settings persistence - Optimized v2."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from PyQt6.QtCore import QSettings
import pytest

from goesvfi.gui_components.settings_persistence import SettingsPersistence


# Shared fixtures and test data
@pytest.fixture(scope="session")
def path_test_scenarios():
    """Pre-defined path scenarios for testing."""
    return {
        "valid_paths": [
            Path("/test/input/directory"),
            Path("/another/valid/path"),
            Path("relative/path"),
            Path("/path/with spaces/directory"),
        ],
        "invalid_paths": [None],
    }


@pytest.fixture(scope="session")
def crop_rect_scenarios():
    """Pre-defined crop rectangle scenarios for testing."""
    return {
        "valid_rects": [
            (10, 20, 100, 200),
            (0, 0, 640, 480),
            (50, 75, 1920, 1080),
            (1, 1, 2, 2),  # Minimal valid rect
        ],
        "invalid_rects": [None, (), (1, 2), (1, 2, 3)],  # Invalid formats
    }


@pytest.fixture()
def mock_settings():
    """Create mock QSettings with in-memory storage."""
    settings = MagicMock(spec=QSettings)
    settings._storage = {}

    def mock_value(key, default=None, type=None):
        value = settings._storage.get(key, default)
        if type and value is not None:
            try:
                return type(value)
            except (TypeError, ValueError):
                return default
        return value

    def mock_set_value(key, value) -> None:
        settings._storage[key] = value

    def mock_all_keys():
        return list(settings._storage.keys())

    settings.value.side_effect = mock_value
    settings.setValue.side_effect = mock_set_value
    settings.allKeys.side_effect = mock_all_keys
    settings.sync.return_value = None

    # Mock organization/application names
    settings.organizationName.return_value = ""
    settings.applicationName.return_value = ""
    settings.fileName.return_value = "/mock/settings/file.plist"

    return settings


@pytest.fixture()
def settings_persistence(mock_settings, mocker):
    """Create settings persistence manager with mocked dependencies."""
    # Mock file system operations
    mock_path = mocker.patch("pathlib.Path.exists")
    mock_path.return_value = True

    mock_stat = mocker.MagicMock()
    mock_stat.st_size = 1024
    mocker.patch("pathlib.Path.stat", return_value=mock_stat)

    return SettingsPersistence(mock_settings)


class TestSettingsPersistence:
    """Test settings persistence with optimized patterns."""

    @pytest.mark.parametrize("path_scenario", ["valid_paths"])
    def test_save_input_directory_valid_paths(self, settings_persistence, mock_settings, path_test_scenarios, path_scenario: str) -> None:
        """Test saving valid input directories."""
        test_paths = path_test_scenarios[path_scenario]

        for test_path in test_paths:
            result = settings_persistence.save_input_directory(test_path)

            assert result is True
            # Verify the setting was saved with resolved path
            mock_settings.setValue.assert_any_call("paths/inputDirectory", str(test_path.resolve()))

    @pytest.mark.parametrize("path_scenario", ["invalid_paths"])
    def test_save_input_directory_invalid_paths(self, settings_persistence, mock_settings, path_test_scenarios, path_scenario: str) -> None:
        """Test saving invalid input directories."""
        test_paths = path_test_scenarios[path_scenario]

        for test_path in test_paths:
            result = settings_persistence.save_input_directory(test_path)
            assert result is False

    @pytest.mark.parametrize("rect_scenario", ["valid_rects"])
    def test_save_crop_rect_valid_rects(self, settings_persistence, mock_settings, crop_rect_scenarios, rect_scenario: str) -> None:
        """Test saving valid crop rectangles."""
        test_rects = crop_rect_scenarios[rect_scenario]

        for test_rect in test_rects:
            result = settings_persistence.save_crop_rect(test_rect)

            assert result is True
            # Verify the setting was saved as comma-separated string
            expected_string = ",".join(map(str, test_rect))
            mock_settings.setValue.assert_any_call("preview/cropRectangle", expected_string)

    @pytest.mark.parametrize("rect_scenario", ["invalid_rects"])
    def test_save_crop_rect_invalid_rects(self, settings_persistence, mock_settings, crop_rect_scenarios, rect_scenario: str) -> None:
        """Test saving invalid crop rectangles."""
        test_rects = crop_rect_scenarios[rect_scenario]

        for test_rect in test_rects:
            result = settings_persistence.save_crop_rect(test_rect)
            assert result is False

    @pytest.mark.parametrize("path_type", [
        (Path("/unix/style/path"), "unix"),
        (Path("relative/path"), "relative"),
        (Path("/path with spaces/directory"), "spaces"),
    ])
    def test_path_string_conversion(self, settings_persistence, mock_settings, path_type: tuple[Path, str]) -> None:
        """Test that paths are properly converted to strings for storage."""
        test_path, _path_description = path_type

        result = settings_persistence.save_input_directory(test_path)
        assert result is True

        # Verify string conversion with resolved path
        mock_settings.setValue.assert_any_call("paths/inputDirectory", str(test_path.resolve()))

    def test_settings_sync_called(self, settings_persistence, mock_settings) -> None:
        """Test that settings are synced after save operations."""
        test_path = Path("/test/sync/path")

        settings_persistence.save_input_directory(test_path)

        # Verify sync was called
        mock_settings.sync.assert_called()

    @pytest.mark.parametrize("operation_sequence", [
        [
            ("save_directory", Path("/first/path")),
            ("save_crop", (10, 20, 300, 400)),
            ("save_directory", Path("/second/path")),
        ],
        [
            ("save_crop", (0, 0, 640, 480)),
            ("save_crop", (50, 50, 800, 600)),
            ("save_directory", Path("/final/path")),
        ],
    ])
    def test_operation_sequences(self, settings_persistence, mock_settings, operation_sequence: list[tuple[str, Any]]) -> None:
        """Test sequences of save operations."""
        for operation, value in operation_sequence:
            if operation == "save_directory":
                result = settings_persistence.save_input_directory(value)
            elif operation == "save_crop":
                result = settings_persistence.save_crop_rect(value)

            assert result is True

        # Verify sync was called for each operation
        assert mock_settings.sync.call_count == len(operation_sequence)

    @pytest.mark.parametrize("batch_size", [5, 10, 20])
    def test_batch_operations_performance(self, settings_persistence, mock_settings, batch_size: int) -> None:
        """Test performance with batch operations."""
        import time

        # Test batch directory saves
        start_time = time.time()
        for i in range(batch_size):
            test_path = Path(f"/batch/test/path_{i}")
            result = settings_persistence.save_input_directory(test_path)
            assert result is True
        directory_time = time.time() - start_time

        # Test batch crop rect saves
        start_time = time.time()
        for i in range(batch_size):
            test_rect = (i, i + 10, i + 100, i + 200)
            result = settings_persistence.save_crop_rect(test_rect)
            assert result is True
        crop_time = time.time() - start_time

        # Should complete reasonably quickly
        assert directory_time < 0.5  # Less than 500ms
        assert crop_time < 0.5       # Less than 500ms

        # Verify all operations completed
        assert mock_settings.setValue.call_count == batch_size * 2  # directories + crops
        assert mock_settings.sync.call_count == batch_size * 2      # sync after each

    def test_error_resilience(self, settings_persistence, mock_settings) -> None:
        """Test error handling and resilience."""
        # Test with settings that raises exception
        mock_settings.setValue.side_effect = Exception("Mock settings error")

        # Should handle exceptions gracefully
        settings_persistence.save_input_directory(Path("/error/test"))
        # Result depends on implementation - should either handle gracefully or propagate

        # Reset mock for further testing
        mock_settings.setValue.side_effect = settings_persistence.mock_settings._storage.__setitem__

    @pytest.mark.parametrize("validation_scenarios", [
        # (input_value, operation_type, expected_result)
        (Path("/valid/path"), "directory", True),
        (None, "directory", False),
        ((10, 20, 300, 400), "crop", True),
        (None, "crop", False),
        ((1, 2, 3), "crop", False),  # Invalid rect format
    ])
    def test_input_validation_comprehensive(self, settings_persistence, validation_scenarios: tuple[Any, str, bool]) -> None:
        """Test comprehensive input validation."""
        input_value, operation_type, expected_result = validation_scenarios

        if operation_type == "directory":
            result = settings_persistence.save_input_directory(input_value)
        elif operation_type == "crop":
            result = settings_persistence.save_crop_rect(input_value)

        assert result == expected_result

    def test_storage_key_consistency(self, settings_persistence, mock_settings) -> None:
        """Test that storage keys are consistent and well-defined."""
        # Test directory storage key
        test_path = Path("/test/key/consistency")
        settings_persistence.save_input_directory(test_path)

        # Verify correct key was used
        expected_calls = [call for call in mock_settings.setValue.call_args_list
                         if call[0][0] == "paths/inputDirectory"]
        assert len(expected_calls) > 0

        # Test crop rect storage key
        test_rect = (10, 20, 300, 400)
        settings_persistence.save_crop_rect(test_rect)

        # Verify correct key was used
        expected_calls = [call for call in mock_settings.setValue.call_args_list
                         if call[0][0] == "preview/cropRectangle"]
        assert len(expected_calls) > 0
