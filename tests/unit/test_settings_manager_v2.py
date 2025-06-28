"""Unit tests for the SettingsManager component - Optimized v2."""

from pathlib import Path
import tempfile
from typing import Any

from PyQt6.QtCore import QCoreApplication, QSettings
from PyQt6.QtWidgets import QApplication
import pytest

from goesvfi.gui_components.settings_manager import SettingsManager


# Shared test data and fixtures
@pytest.fixture(scope="session")
def app():
    """Create QApplication for all tests."""
    return QApplication([]) if not QApplication.instance() else QCoreApplication.instance()


@pytest.fixture(scope="session")
def test_data_scenarios():
    """Pre-defined test data scenarios for consistent testing."""
    return {
        "strings": [("test_string", "hello"), ("empty_string", ""), ("unicode_string", "测试")],
        "integers": [("test_int", 42), ("zero_int", 0), ("negative_int", -5)],
        "booleans": [("test_bool_true", True), ("test_bool_false", False)],
        "lists": [
            ("test_list", ["item1", "item2", "item3"]),
            ("empty_list", []),
            ("mixed_list", ["string", 123, True]),
        ],
        "paths": [
            (Path("/path/to/file1.txt"), Path("/path/to/file2.txt"), Path("/path/to/file3.txt")),
            (Path("/single/path.txt"),),
            (),  # Empty paths
        ],
        "window_geometry": [
            {"x": 100, "y": 200, "width": 800, "height": 600},
            {"x": 0, "y": 0, "width": 1920, "height": 1080},
            {"x": -100, "y": -50, "width": 640, "height": 480},  # Negative positions
        ],
    }


@pytest.fixture()
def temp_settings_file():
    """Create temporary settings file for testing."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".ini")
    temp_file.close()
    yield temp_file.name
    Path(temp_file.name).unlink(missing_ok=True)


@pytest.fixture()
def settings_manager(app, temp_settings_file):
    """Create SettingsManager instance with temporary file."""
    settings = QSettings(temp_settings_file, QSettings.Format.IniFormat)
    return SettingsManager(settings)


class TestSettingsManager:
    """Test SettingsManager with optimized test patterns."""

    def test_initialization(self, settings_manager) -> None:
        """Test SettingsManager initialization."""
        assert settings_manager.settings is not None

    @pytest.mark.parametrize("data_type", ["strings", "integers", "booleans", "lists"])
    def test_save_and_load_values(self, settings_manager, test_data_scenarios, data_type: str) -> None:
        """Test saving and loading different data types."""
        test_cases = test_data_scenarios[data_type]

        for key, value in test_cases:
            # Save value
            result = settings_manager.save_value(key, value)
            assert result is True

            # Load value with appropriate type
            if data_type == "strings":
                loaded = settings_manager.load_value(key, "")
            elif data_type == "integers":
                loaded = settings_manager.load_value(key, 0, int)
            elif data_type == "booleans":
                loaded = settings_manager.load_value(key, False, bool)
            elif data_type == "lists":
                loaded = settings_manager.load_value(key, [], list)

            assert loaded == value

    @pytest.mark.parametrize("key,default,expected_type", [
        ("non_existent_string", "default", str),
        ("non_existent_int", 99, int),
        ("non_existent_bool", True, bool),
        ("non_existent_list", ["default"], list),
    ])
    def test_load_nonexistent_values(self, settings_manager, key: str, default: Any, expected_type: type) -> None:
        """Test loading values that don't exist returns defaults."""
        if expected_type != list:
            loaded = settings_manager.load_value(key, default, expected_type)
        else:
            loaded = settings_manager.load_value(key, default, list)

        assert loaded == default
        assert type(loaded) == type(default)

    @pytest.mark.parametrize("geometry_index", [0, 1, 2])
    def test_window_geometry_operations(self, settings_manager, test_data_scenarios, geometry_index: int) -> None:
        """Test saving and loading window geometry with different configurations."""
        geometry = test_data_scenarios["window_geometry"][geometry_index]
        window_name = f"test_window_{geometry_index}"

        # Save geometry
        result = settings_manager.save_window_geometry(window_name, geometry)
        assert result is True

        # Load geometry
        loaded = settings_manager.load_window_geometry(window_name)
        assert loaded == geometry

    def test_load_nonexistent_window_geometry(self, settings_manager) -> None:
        """Test loading window geometry that doesn't exist."""
        loaded = settings_manager.load_window_geometry("non_existent_window")
        assert loaded is None

    def test_load_incomplete_window_geometry(self, settings_manager) -> None:
        """Test loading incomplete window geometry."""
        # Manually save incomplete geometry (missing required keys)
        settings_manager.settings.beginGroup("Windows/incomplete_window")
        settings_manager.settings.setValue("x", 10)
        settings_manager.settings.setValue("y", 20)
        settings_manager.settings.setValue("width", 300)
        # Intentionally not setting height
        settings_manager.settings.endGroup()
        settings_manager.settings.sync()

        # Should return None for incomplete geometry
        loaded = settings_manager.load_window_geometry("incomplete_window")
        assert loaded is None

    @pytest.mark.parametrize("path_scenario", [0, 1, 2])
    def test_recent_paths_operations(self, settings_manager, test_data_scenarios, path_scenario: int) -> None:
        """Test saving and loading recent paths with different scenarios."""
        paths = test_data_scenarios["paths"][path_scenario]
        key = f"recent_files_{path_scenario}"

        # Save paths
        result = settings_manager.save_recent_paths(key, paths)
        assert result is True

        # Load paths
        loaded = settings_manager.load_recent_paths(key)
        assert len(loaded) == len(paths)

        for original, loaded_path in zip(paths, loaded, strict=False):
            assert loaded_path == original

    @pytest.mark.parametrize("total_paths,max_items,expected_count", [
        (15, 10, 10),  # Should limit to max_items
        (5, 10, 5),    # Should keep all if under limit
        (0, 10, 0),    # Should handle empty list
    ])
    def test_recent_paths_max_items_limit(self, settings_manager, total_paths: int, max_items: int, expected_count: int) -> None:
        """Test that recent paths are limited to max_items."""
        # Create paths
        paths = [Path(f"/path/to/file{i}.txt") for i in range(total_paths)]

        # Save with max_items limit
        result = settings_manager.save_recent_paths("recent_files", paths, max_items=max_items)
        assert result is True

        # Load and verify count
        loaded = settings_manager.load_recent_paths("recent_files")
        assert len(loaded) == expected_count

        # Should keep the first max_items
        for i in range(expected_count):
            assert loaded[i] == paths[i]

    def test_load_nonexistent_recent_paths(self, settings_manager) -> None:
        """Test loading recent paths that don't exist."""
        loaded = settings_manager.load_recent_paths("non_existent")
        assert loaded == []

    @pytest.mark.parametrize("group_operations", [
        [("TestGroup/key1", "value1"), ("TestGroup/key2", "value2")],
        [("AnotherGroup/setting", 42), ("AnotherGroup/flag", True)],
        [("EmptyGroup/test", "test")],  # Single item group
    ])
    def test_clear_group_operations(self, settings_manager, group_operations: list[tuple[str, Any]]) -> None:
        """Test clearing settings groups with different configurations."""
        # Save settings in the group
        for key, value in group_operations:
            settings_manager.save_value(key, value)

        # Verify they exist
        for key, expected_value in group_operations:
            loaded = settings_manager.load_value(key, None)
            assert loaded == expected_value

        # Extract group name from first key
        group_name = group_operations[0][0].split("/")[0]

        # Clear the group
        result = settings_manager.clear_group(group_name)
        assert result is True

        # Verify they're gone
        for key, _ in group_operations:
            loaded = settings_manager.load_value(key, "DEFAULT_NOT_FOUND")
            assert loaded == "DEFAULT_NOT_FOUND"

    def test_get_all_keys_operation(self, settings_manager) -> None:
        """Test getting all settings keys."""
        # Save test values in different groups
        test_data = [
            ("test1", "value1"),
            ("test2", "value2"),
            ("group/test3", "value3"),
            ("another_group/test4", "value4"),
        ]

        for key, value in test_data:
            settings_manager.save_value(key, value)

        # Get all keys
        keys = settings_manager.get_all_keys()

        # Verify all test keys exist
        for key, _ in test_data:
            assert key in keys

    def test_remove_key_operation(self, settings_manager) -> None:
        """Test removing specific keys."""
        # Save multiple values
        test_keys = ["test_key1", "test_key2", "group/test_key3"]
        for key in test_keys:
            settings_manager.save_value(key, f"value_for_{key}")

        # Verify they exist
        for key in test_keys:
            loaded = settings_manager.load_value(key, "NOT_FOUND")
            assert loaded == f"value_for_{key}"

        # Remove one key
        target_key = test_keys[0]
        result = settings_manager.remove_key(target_key)
        assert result is True

        # Verify only target key is gone
        loaded = settings_manager.load_value(target_key, "DEFAULT")
        assert loaded == "DEFAULT"

        # Others should still exist
        for key in test_keys[1:]:
            loaded = settings_manager.load_value(key, "NOT_FOUND")
            assert loaded == f"value_for_{key}"

    def test_sync_operation(self, settings_manager) -> None:
        """Test syncing settings to disk."""
        # Save a value
        settings_manager.save_value("sync_test", "test_value")

        # Sync should succeed
        result = settings_manager.sync()
        assert result is True

        # Value should persist
        loaded_value = settings_manager.load_value("sync_test", "NOT_FOUND")
        assert loaded_value == "test_value"

    @pytest.mark.parametrize("operation_count", [5, 15, 30])
    def test_bulk_operations_performance(self, settings_manager, operation_count: int) -> None:
        """Test performance with bulk operations."""
        import time

        # Test bulk save
        start_time = time.time()
        for i in range(operation_count):
            settings_manager.save_value(f"bulk_key_{i}", f"value_{i}")
        save_time = time.time() - start_time

        # Test bulk load
        start_time = time.time()
        for i in range(operation_count):
            loaded = settings_manager.load_value(f"bulk_key_{i}", "NOT_FOUND")
            assert loaded == f"value_{i}"
        load_time = time.time() - start_time

        # Should complete reasonably quickly
        assert save_time < 1.0  # Less than 1 second for bulk saves
        assert load_time < 1.0  # Less than 1 second for bulk loads

    def test_error_handling_robustness(self, settings_manager) -> None:
        """Test error handling in various edge cases."""
        # Test with None values
        result = settings_manager.save_value("none_test", None)
        assert result is True

        # Test loading with None default
        loaded = settings_manager.load_value("none_test", None)
        assert loaded is None

        # Test with empty strings
        result = settings_manager.save_value("empty_test", "")
        assert result is True

        loaded = settings_manager.load_value("empty_test", "default")
        assert loaded == ""

        # Test with complex nested data
        complex_data = {"nested": {"data": [1, 2, {"inner": "value"}]}}
        result = settings_manager.save_value("complex_test", complex_data)
        assert result is True
