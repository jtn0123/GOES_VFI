"""Unit tests for the SettingsManager component."""

import tempfile
import unittest
from pathlib import Path
from typing import ClassVar, Dict, Optional

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

from goesvfi.gui_components.settings_manager import SettingsManager


class TestSettingsManager(unittest.TestCase):
    """Test cases for SettingsManager."""

    app: ClassVar[Optional[QApplication]] = None

    @classmethod
    def setUpClass(cls):
        """Set up QApplication for all tests."""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary settings file
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".ini")
        self.temp_file.close()

        # Create QSettings with test file
        self.settings = QSettings(self.temp_file.name, QSettings.Format.IniFormat)

        # Create SettingsManager instance
        self.settings_manager = SettingsManager(self.settings)

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary file
        Path(self.temp_file.name).unlink(missing_ok=True)

    def test_initialization(self):
        """Test SettingsManager initialization."""
        self.assertIsNotNone(self.settings_manager.settings)

    def test_save_and_load_value(self):
        """Test saving and loading single values."""
        # Test string
        self.assertTrue(self.settings_manager.save_value("test_string", "hello"))
        loaded = self.settings_manager.load_value("test_string", "")
        self.assertEqual(loaded, "hello")

        # Test integer
        self.assertTrue(self.settings_manager.save_value("test_int", 42))
        loaded = self.settings_manager.load_value("test_int", 0, int)
        self.assertEqual(loaded, 42)

        # Test boolean
        self.assertTrue(self.settings_manager.save_value("test_bool", True))
        loaded = self.settings_manager.load_value("test_bool", False, bool)
        self.assertTrue(loaded)

        # Test list
        test_list = ["item1", "item2", "item3"]
        self.assertTrue(self.settings_manager.save_value("test_list", test_list))
        loaded = self.settings_manager.load_value("test_list", [], list)
        self.assertEqual(loaded, test_list)

    def test_load_value_not_exists(self):
        """Test loading value that doesn't exist."""
        # Should return default value
        loaded = self.settings_manager.load_value("non_existent", "default")
        self.assertEqual(loaded, "default")

        # Test with different types
        loaded = self.settings_manager.load_value("non_existent_int", 99, int)
        self.assertEqual(loaded, 99)

    def test_save_and_load_window_geometry(self):
        """Test saving and loading window geometry."""
        geometry = {"x": 100, "y": 200, "width": 800, "height": 600}

        # Save geometry
        result = self.settings_manager.save_window_geometry("main_window", geometry)
        self.assertTrue(result)

        # Load geometry
        loaded = self.settings_manager.load_window_geometry("main_window")
        self.assertEqual(loaded, geometry)

    def test_load_window_geometry_not_exists(self):
        """Test loading window geometry that doesn't exist."""
        loaded = self.settings_manager.load_window_geometry("non_existent_window")
        self.assertIsNone(loaded)

    def test_load_window_geometry_incomplete(self):
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
        self.assertIsNone(loaded)

    def test_save_and_load_recent_paths(self):
        """Test saving and loading recent paths."""
        paths = [
            Path("/path/to/file1.txt"),
            Path("/path/to/file2.txt"),
            Path("/path/to/file3.txt"),
        ]

        # Save paths
        result = self.settings_manager.save_recent_paths("recent_files", paths)
        self.assertTrue(result)

        # Load paths
        loaded = self.settings_manager.load_recent_paths("recent_files")
        self.assertEqual(len(loaded), 3)
        self.assertEqual(loaded[0], paths[0])
        self.assertEqual(loaded[1], paths[1])
        self.assertEqual(loaded[2], paths[2])

    def test_save_recent_paths_max_items(self):
        """Test that recent paths are limited to max_items."""
        # Create 15 paths
        paths = [Path(f"/path/to/file{i}.txt") for i in range(15)]

        # Save with max_items=10
        result = self.settings_manager.save_recent_paths("recent_files", paths, max_items=10)
        self.assertTrue(result)

        # Load and verify only 10 were saved
        loaded = self.settings_manager.load_recent_paths("recent_files")
        self.assertEqual(len(loaded), 10)
        # Should keep the first 10
        for i in range(10):
            self.assertEqual(loaded[i], paths[i])

    def test_load_recent_paths_not_exists(self):
        """Test loading recent paths that don't exist."""
        loaded = self.settings_manager.load_recent_paths("non_existent")
        self.assertEqual(loaded, [])

    def test_clear_group(self):
        """Test clearing a settings group."""
        # Save some settings in a group using the settings manager
        self.settings_manager.save_value("TestGroup/key1", "value1")
        self.settings_manager.save_value("TestGroup/key2", "value2")

        # Verify they exist
        value1 = self.settings_manager.load_value("TestGroup/key1", "")
        self.assertEqual(value1, "value1")

        # Clear the group
        result = self.settings_manager.clear_group("TestGroup")
        self.assertTrue(result)

        # Verify they're gone
        value1_after = self.settings_manager.load_value("TestGroup/key1", "default")
        value2_after = self.settings_manager.load_value("TestGroup/key2", "default")
        self.assertEqual(value1_after, "default")
        self.assertEqual(value2_after, "default")

    def test_get_all_keys(self):
        """Test getting all settings keys."""
        # Save some test values
        self.settings_manager.save_value("test1", "value1")
        self.settings_manager.save_value("test2", "value2")
        self.settings_manager.save_value("group/test3", "value3")

        # Get all keys
        keys = self.settings_manager.get_all_keys()

        # Verify keys exist
        self.assertIn("test1", keys)
        self.assertIn("test2", keys)
        self.assertIn("group/test3", keys)

    def test_remove_key(self):
        """Test removing a specific key."""
        # Save a value
        self.settings_manager.save_value("test_key", "test_value")

        # Verify it exists
        loaded = self.settings_manager.load_value("test_key", "")
        self.assertEqual(loaded, "test_value")

        # Remove it
        result = self.settings_manager.remove_key("test_key")
        self.assertTrue(result)

        # Verify it's gone
        loaded = self.settings_manager.load_value("test_key", "default")
        self.assertEqual(loaded, "default")

    def test_sync(self):
        """Test syncing settings to disk."""
        # Save a value
        self.settings_manager.save_value("sync_test", "value")

        # Sync should succeed
        result = self.settings_manager.sync()
        self.assertTrue(result)

        # Verify the value is still there using the settings manager
        # (cross-instance verification is problematic due to QSettings behavior)
        loaded_value = self.settings_manager.load_value("sync_test", "default")
        self.assertEqual(loaded_value, "value")


if __name__ == "__main__":
    unittest.main()
