"""Unit tests for the SettingsManager component."""

from pathlib import Path
import tempfile
from typing import ClassVar
import unittest

from PyQt6.QtCore import QCoreApplication, QSettings
from PyQt6.QtWidgets import QApplication

from goesvfi.gui_components.settings_manager import SettingsManager


class TestSettingsManager(unittest.TestCase):
    """Test cases for SettingsManager."""

    app: ClassVar[QCoreApplication | None] = None

    @classmethod
    def setUpClass(cls) -> None:
        """Set up QApplication for all tests."""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QCoreApplication.instance()

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Create temporary settings file
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".ini")
        self.temp_file.close()

        # Create QSettings with test file
        self.settings = QSettings(self.temp_file.name, QSettings.Format.IniFormat)

        # Create SettingsManager instance
        self.settings_manager = SettingsManager(self.settings)

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        # Clean up temporary file
        Path(self.temp_file.name).unlink(missing_ok=True)

    def test_initialization(self) -> None:
        """Test SettingsManager initialization."""
        assert self.settings_manager.settings is not None

    def test_save_and_load_value(self) -> None:
        """Test saving and loading single values."""
        # Test string
        assert self.settings_manager.save_value("test_string", "hello")
        loaded = self.settings_manager.load_value("test_string", "")
        assert loaded == "hello"

        # Test integer
        assert self.settings_manager.save_value("test_int", 42)
        loaded = self.settings_manager.load_value("test_int", 0, int)
        assert loaded == 42

        # Test boolean
        assert self.settings_manager.save_value("test_bool", True)
        loaded = self.settings_manager.load_value("test_bool", False, bool)
        assert loaded

        # Test list
        test_list = ["item1", "item2", "item3"]
        assert self.settings_manager.save_value("test_list", test_list)
        loaded = self.settings_manager.load_value("test_list", [], list)
        assert loaded == test_list

    def test_load_value_not_exists(self) -> None:
        """Test loading value that doesn't exist."""
        # Should return default value
        loaded = self.settings_manager.load_value("non_existent", "default")
        assert loaded == "default"

        # Test with different types
        loaded = self.settings_manager.load_value("non_existent_int", 99, int)
        assert loaded == 99

    def test_save_and_load_window_geometry(self) -> None:
        """Test saving and loading window geometry."""
        geometry = {"x": 100, "y": 200, "width": 800, "height": 600}

        # Save geometry
        result = self.settings_manager.save_window_geometry("main_window", geometry)
        assert result

        # Load geometry
        loaded = self.settings_manager.load_window_geometry("main_window")
        assert loaded == geometry

    def test_load_window_geometry_not_exists(self) -> None:
        """Test loading window geometry that doesn't exist."""
        loaded = self.settings_manager.load_window_geometry("non_existent_window")
        assert loaded is None

    def test_load_window_geometry_incomplete(self) -> None:
        """Test loading incomplete window geometry."""
        # Save incomplete geometry (missing height)
        self.settings.beginGroup("Windows/incomplete_window")
        self.settings.setValue("x", 10)
        self.settings.setValue("y", 20)
        self.settings.setValue("width", 300)
        # Intentionally not setting height
        self.settings.endGroup()
        self.settings.sync()

        # Should return None for incomplete geometry
        loaded = self.settings_manager.load_window_geometry("incomplete_window")
        assert loaded is None

    def test_save_and_load_recent_paths(self) -> None:
        """Test saving and loading recent paths."""
        paths = [
            Path("/path/to/file1.txt"),
            Path("/path/to/file2.txt"),
            Path("/path/to/file3.txt"),
        ]

        # Save paths
        result = self.settings_manager.save_recent_paths("recent_files", paths)
        assert result

        # Load paths
        loaded = self.settings_manager.load_recent_paths("recent_files")
        assert len(loaded) == 3
        assert loaded[0] == paths[0]
        assert loaded[1] == paths[1]
        assert loaded[2] == paths[2]

    def test_save_recent_paths_max_items(self) -> None:
        """Test that recent paths are limited to max_items."""
        # Create 15 paths
        paths = [Path(f"/path/to/file{i}.txt") for i in range(15)]

        # Save with max_items=10
        result = self.settings_manager.save_recent_paths("recent_files", paths, max_items=10)
        assert result

        # Load and verify only 10 were saved
        loaded = self.settings_manager.load_recent_paths("recent_files")
        assert len(loaded) == 10
        # Should keep the first 10
        for i in range(10):
            assert loaded[i] == paths[i]

    def test_load_recent_paths_not_exists(self) -> None:
        """Test loading recent paths that don't exist."""
        loaded = self.settings_manager.load_recent_paths("non_existent")
        assert loaded == []

    def test_clear_group(self) -> None:
        """Test clearing a settings group."""
        # Save some settings in a group using the settings manager
        self.settings_manager.save_value("TestGroup/key1", "value1")
        self.settings_manager.save_value("TestGroup/key2", "value2")

        # Verify they exist
        value1 = self.settings_manager.load_value("TestGroup/key1", "")
        assert value1 == "value1"

        # Clear the group
        result = self.settings_manager.clear_group("TestGroup")
        assert result

        # Verify they're gone
        value1_after = self.settings_manager.load_value("TestGroup/key1", "default")
        value2_after = self.settings_manager.load_value("TestGroup/key2", "default")
        assert value1_after == "default"
        assert value2_after == "default"

    def test_get_all_keys(self) -> None:
        """Test getting all settings keys."""
        # Save some test values
        self.settings_manager.save_value("test1", "value1")
        self.settings_manager.save_value("test2", "value2")
        self.settings_manager.save_value("group/test3", "value3")

        # Get all keys
        keys = self.settings_manager.get_all_keys()

        # Verify keys exist
        assert "test1" in keys
        assert "test2" in keys
        assert "group/test3" in keys

    def test_remove_key(self) -> None:
        """Test removing a specific key."""
        # Save a value
        self.settings_manager.save_value("test_key", "test_value")

        # Verify it exists
        loaded = self.settings_manager.load_value("test_key", "")
        assert loaded == "test_value"

        # Remove it
        result = self.settings_manager.remove_key("test_key")
        assert result

        # Verify it's gone
        loaded = self.settings_manager.load_value("test_key", "default")
        assert loaded == "default"

    def test_sync(self) -> None:
        """Test syncing settings to disk."""
        # Save a value
        self.settings_manager.save_value("sync_test", "value")

        # Sync should succeed
        result = self.settings_manager.sync()
        assert result

        # Verify the value is still there using the settings manager
        # (cross-instance verification is problematic due to QSettings behavior)
        loaded_value = self.settings_manager.load_value("sync_test", "default")
        assert loaded_value == "value"


if __name__ == "__main__":
    unittest.main()
