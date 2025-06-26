"""Advanced settings persistence tests for GOES VFI GUI."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from goesvfi.gui import MainWindow


class TestSettingsAdvanced:
    """Test advanced settings persistence functionality."""

    @pytest.fixture
    def window(self, qtbot, mocker):
        """Create a MainWindow instance for testing."""
        # Mock heavy components
        mocker.patch("goesvfi.gui.CombinedIntegrityAndImageryTab")
        mocker.patch("goesvfi.integrity_check.enhanced_gui_tab.EnhancedImageryTab")

        window = MainWindow(debug_mode=True)
        qtbot.addWidget(window)
        window._post_init_setup()

        return window

    @pytest.fixture
    def temp_settings_file(self, tmp_path):
        """Create temporary settings file."""
        settings_file = tmp_path / "test_settings.ini"
        return settings_file

    def test_profile_save_load_delete(self, qtbot, window, temp_settings_file):
        """Test profile save, load, and delete operations."""

        # Profile manager
        class ProfileManager:
            def __init__(self, base_path):
                self.base_path = Path(base_path)
                self.profiles_dir = self.base_path / "profiles"
                self.profiles_dir.mkdir(exist_ok=True)

            def save_profile(self, name, settings_dict):
                profile_path = self.profiles_dir / f"{name}.json"

                # Validate profile name
                if not name or "/" in name or "\\" in name:
                    raise ValueError("Invalid profile name")

                # Save profile
                with open(profile_path, "w") as f:
                    json.dump(settings_dict, f, indent=2)

                return profile_path

            def load_profile(self, name):
                profile_path = self.profiles_dir / f"{name}.json"

                if not profile_path.exists():
                    raise FileNotFoundError(f"Profile '{name}' not found")

                with open(profile_path, "r") as f:
                    return json.load(f)

            def delete_profile(self, name):
                profile_path = self.profiles_dir / f"{name}.json"

                if profile_path.exists():
                    profile_path.unlink()
                    return True
                return False

            def list_profiles(self):
                return [p.stem for p in self.profiles_dir.glob("*.json")]

        # Create profile manager
        profile_mgr = ProfileManager(temp_settings_file.parent)

        # Test save profile
        test_settings = {
            "fps": 60,
            "encoder": "RIFE",
            "quality": "high",
            "crop_rect": [100, 100, 400, 300],
            "advanced": {"threads": 8, "tile_size": 256},
        }

        profile_path = profile_mgr.save_profile("high_quality", test_settings)
        assert profile_path.exists()

        # Test list profiles
        profiles = profile_mgr.list_profiles()
        assert "high_quality" in profiles

        # Test load profile
        loaded_settings = profile_mgr.load_profile("high_quality")
        assert loaded_settings["fps"] == 60
        assert loaded_settings["encoder"] == "RIFE"
        assert loaded_settings["advanced"]["threads"] == 8

        # Test invalid profile name
        with pytest.raises(ValueError):
            profile_mgr.save_profile("invalid/name", test_settings)

        # Test delete profile
        assert profile_mgr.delete_profile("high_quality")
        assert "high_quality" not in profile_mgr.list_profiles()

        # Test load non-existent profile
        with pytest.raises(FileNotFoundError):
            profile_mgr.load_profile("non_existent")

    def test_window_geometry_persistence(self, qtbot, window, mocker):
        """Test window geometry persistence."""
        # Mock QSettings
        mock_settings = MagicMock(spec=QSettings)
        mocker.patch("PyQt6.QtCore.QSettings", return_value=mock_settings)

        # Window state manager
        class WindowStateManager:
            def __init__(self, window):
                self.window = window
                self.settings = QSettings()

            def save_window_state(self):
                # Save geometry
                self.settings.setValue("window/geometry", self.window.saveGeometry())

                # Save position and size separately for validation
                self.settings.setValue("window/pos_x", self.window.x())
                self.settings.setValue("window/pos_y", self.window.y())
                self.settings.setValue("window/width", self.window.width())
                self.settings.setValue("window/height", self.window.height())

                # Save window state (maximized, fullscreen, etc.)
                self.settings.setValue("window/is_maximized", self.window.isMaximized())
                self.settings.setValue(
                    "window/is_fullscreen", self.window.isFullScreen()
                )

            def restore_window_state(self):
                # Restore geometry
                geometry = self.settings.value("window/geometry")
                if geometry:
                    self.window.restoreGeometry(geometry)
                else:
                    # Fallback to individual values
                    x = self.settings.value("window/pos_x", 100, type=int)
                    y = self.settings.value("window/pos_y", 100, type=int)
                    width = self.settings.value("window/width", 1200, type=int)
                    height = self.settings.value("window/height", 800, type=int)

                    self.window.setGeometry(x, y, width, height)

                # Restore window state
                if self.settings.value("window/is_maximized", False, type=bool):
                    self.window.showMaximized()
                elif self.settings.value("window/is_fullscreen", False, type=bool):
                    self.window.showFullScreen()

        # Create manager
        state_mgr = WindowStateManager(window)

        # Set specific geometry
        window.setGeometry(200, 150, 1400, 900)

        # Save state
        state_mgr.save_window_state()

        # Verify save was called
        mock_settings.setValue.assert_any_call("window/pos_x", 200)
        mock_settings.setValue.assert_any_call("window/pos_y", 150)
        mock_settings.setValue.assert_any_call("window/width", 1400)
        mock_settings.setValue.assert_any_call("window/height", 900)

        # Change geometry
        window.setGeometry(300, 200, 1000, 700)

        # Mock restore values
        mock_settings.value.side_effect = lambda key, default=None, type=None: {
            "window/pos_x": 200,
            "window/pos_y": 150,
            "window/width": 1400,
            "window/height": 900,
            "window/is_maximized": False,
            "window/is_fullscreen": False,
        }.get(key, default)

        # Restore state
        state_mgr.restore_window_state()

        # Verify geometry was restored
        assert window.x() == 200
        assert window.y() == 150
        assert window.width() == 1400
        assert window.height() == 900

    def test_splitter_position_persistence(self, qtbot, window):
        """Test splitter position persistence."""

        # Splitter state manager
        class SplitterStateManager:
            def __init__(self):
                self.splitter_states = {}

            def save_splitter_state(self, name, sizes):
                """Save splitter sizes."""
                self.splitter_states[name] = sizes

            def restore_splitter_state(self, name, default_sizes):
                """Restore splitter sizes."""
                return self.splitter_states.get(name, default_sizes)

            def save_all_to_settings(self, settings):
                """Save all splitter states to settings."""
                for name, sizes in self.splitter_states.items():
                    settings.setValue(f"splitters/{name}", sizes)

            def load_all_from_settings(self, settings):
                """Load all splitter states from settings."""
                settings.beginGroup("splitters")
                for name in settings.childKeys():
                    sizes = settings.value(name, type=list)
                    if sizes:
                        self.splitter_states[name] = sizes
                settings.endGroup()

        # Create manager
        splitter_mgr = SplitterStateManager()

        # Save splitter states
        splitter_mgr.save_splitter_state("main_horizontal", [300, 900])
        splitter_mgr.save_splitter_state("preview_vertical", [400, 400])
        splitter_mgr.save_splitter_state("sidebar", [200, 1000])

        # Verify states saved
        assert splitter_mgr.splitter_states["main_horizontal"] == [300, 900]
        assert splitter_mgr.splitter_states["preview_vertical"] == [400, 400]

        # Test restore with defaults
        restored = splitter_mgr.restore_splitter_state("main_horizontal", [500, 700])
        assert restored == [300, 900]

        # Test restore non-existent
        restored = splitter_mgr.restore_splitter_state("non_existent", [100, 100])
        assert restored == [100, 100]

    def test_recent_items_management(self, qtbot, window):
        """Test recent files and directories management."""

        # Recent items manager
        class RecentItemsManager:
            def __init__(self, max_items=10):
                self.max_items = max_items
                self.recent_files = []
                self.recent_directories = []
                self.recent_searches = []

            def add_recent_file(self, filepath):
                filepath = str(filepath)

                # Remove if already exists
                if filepath in self.recent_files:
                    self.recent_files.remove(filepath)

                # Add to front
                self.recent_files.insert(0, filepath)

                # Trim to max
                self.recent_files = self.recent_files[: self.max_items]

            def add_recent_directory(self, dirpath):
                dirpath = str(dirpath)

                if dirpath in self.recent_directories:
                    self.recent_directories.remove(dirpath)

                self.recent_directories.insert(0, dirpath)
                self.recent_directories = self.recent_directories[: self.max_items]

            def add_recent_search(self, search_term):
                if search_term in self.recent_searches:
                    self.recent_searches.remove(search_term)

                self.recent_searches.insert(0, search_term)
                self.recent_searches = self.recent_searches[: self.max_items]

            def clear_recent_files(self):
                self.recent_files.clear()

            def clear_all(self):
                self.recent_files.clear()
                self.recent_directories.clear()
                self.recent_searches.clear()

            def get_recent_menu_actions(self, item_type="files"):
                if item_type == "files":
                    return self.recent_files
                elif item_type == "directories":
                    return self.recent_directories
                elif item_type == "searches":
                    return self.recent_searches
                return []

        # Create manager
        recent_mgr = RecentItemsManager(max_items=5)

        # Add items
        test_files = [
            "/path/to/file1.mp4",
            "/path/to/file2.mp4",
            "/path/to/file3.mp4",
            "/path/to/file1.mp4",  # Duplicate
            "/path/to/file4.mp4",
            "/path/to/file5.mp4",
            "/path/to/file6.mp4",  # Exceeds max
        ]

        for f in test_files:
            recent_mgr.add_recent_file(f)

        # Verify behavior
        assert len(recent_mgr.recent_files) == 5  # Max items
        assert recent_mgr.recent_files[0] == "/path/to/file6.mp4"  # Most recent
        assert recent_mgr.recent_files.count("/path/to/file1.mp4") == 1  # No duplicates

        # Test directories
        recent_mgr.add_recent_directory("/dir/one")
        recent_mgr.add_recent_directory("/dir/two")
        recent_mgr.add_recent_directory("/dir/one")  # Move to front

        assert recent_mgr.recent_directories[0] == "/dir/one"
        assert len(recent_mgr.recent_directories) == 2

        # Test clear
        recent_mgr.clear_recent_files()
        assert len(recent_mgr.recent_files) == 0
        assert len(recent_mgr.recent_directories) == 2  # Not cleared

        recent_mgr.clear_all()
        assert len(recent_mgr.recent_directories) == 0

    def test_settings_migration_v1_to_v2(self, qtbot, window, temp_settings_file):
        """Test settings migration from v1 to v2 format."""

        # Settings migrator
        class SettingsMigrator:
            def __init__(self):
                self.migrations = {
                    "1.0": self.migrate_1_0_to_1_1,
                    "1.1": self.migrate_1_1_to_2_0,
                }

            def get_version(self, settings):
                return settings.get("version", "1.0")

            def migrate(self, settings):
                current_version = self.get_version(settings)

                while current_version in self.migrations:
                    migration_func = self.migrations[current_version]
                    settings = migration_func(settings)
                    current_version = self.get_version(settings)

                return settings

            def migrate_1_0_to_1_1(self, settings):
                """Migrate from 1.0 to 1.1 format."""
                # Convert old format to new
                if "output_directory" in settings:
                    # Split into directory and filename
                    output_path = Path(settings["output_directory"])
                    settings["output_dir"] = str(output_path.parent)
                    settings["output_filename"] = output_path.name
                    del settings["output_directory"]

                # Add new fields
                settings.setdefault("auto_save", True)
                settings.setdefault("confirm_exit", True)

                settings["version"] = "1.1"
                return settings

            def migrate_1_1_to_2_0(self, settings):
                """Migrate from 1.1 to 2.0 format."""
                # Restructure settings
                old_settings = settings.copy()

                new_settings = {
                    "version": "2.0",
                    "general": {
                        "auto_save": old_settings.get("auto_save", True),
                        "confirm_exit": old_settings.get("confirm_exit", True),
                        "theme": old_settings.get("theme", "default"),
                    },
                    "processing": {
                        "fps": old_settings.get("fps", 30),
                        "encoder": old_settings.get("encoder", "RIFE"),
                        "quality": old_settings.get("quality", "high"),
                    },
                    "paths": {
                        "input_dir": old_settings.get("input_dir", ""),
                        "output_dir": old_settings.get("output_dir", ""),
                        "output_filename": old_settings.get("output_filename", ""),
                    },
                }

                return new_settings

        # Test migration
        migrator = SettingsMigrator()

        # Old v1.0 settings
        old_settings = {
            "output_directory": "/old/path/output.mp4",
            "fps": 24,
            "encoder": "FFmpeg",
            "quality": "medium",
        }

        # Migrate
        new_settings = migrator.migrate(old_settings)

        # Verify migration
        assert new_settings["version"] == "2.0"
        assert new_settings["general"]["auto_save"]
        assert new_settings["processing"]["fps"] == 24
        assert new_settings["processing"]["encoder"] == "FFmpeg"
        assert new_settings["paths"]["output_dir"] == "/old/path"
        assert new_settings["paths"]["output_filename"] == "output.mp4"

    def test_settings_export_import(self, qtbot, window, temp_settings_file, mocker):
        """Test settings export and import functionality."""
        # Mock file dialog
        mock_get_save_file = mocker.patch.object(QFileDialog, "getSaveFileName")
        mock_get_open_file = mocker.patch.object(QFileDialog, "getOpenFileName")

        export_path = temp_settings_file.parent / "exported_settings.json"
        mock_get_save_file.return_value = (str(export_path), "JSON Files (*.json)")
        mock_get_open_file.return_value = (str(export_path), "JSON Files (*.json)")

        # Settings import/export manager
        class SettingsPortability:
            def __init__(self, window):
                self.window = window

            def export_settings(self):
                # Get save location
                filepath, _ = QFileDialog.getSaveFileName(
                    self.window,
                    "Export Settings",
                    "goes_vfi_settings.json",
                    "JSON Files (*.json);;All Files (*)",
                )

                if not filepath:
                    return False

                # Gather all settings
                settings = {
                    "version": "2.0",
                    "exported_date": QTimer().toString(),
                    "main_settings": {
                        "fps": self.window.main_tab.fps_spinbox.value(),
                        "encoder": self.window.main_tab.encoder_combo.currentText(),
                        "enhance": self.window.main_tab.sanchez_checkbox.isChecked(),
                    },
                    "window_state": {
                        "geometry": str(self.window.geometry()),
                        "tab_index": self.window.tab_widget.currentIndex(),
                    },
                    "advanced": {"threads": 8, "memory_limit": 0.8},
                }

                # Write to file
                try:
                    with open(filepath, "w") as f:
                        json.dump(settings, f, indent=2)
                    return True
                except Exception:
                    return False

            def import_settings(self):
                # Get file to import
                filepath, _ = QFileDialog.getOpenFileName(
                    self.window,
                    "Import Settings",
                    "",
                    "JSON Files (*.json);;All Files (*)",
                )

                if not filepath:
                    return False

                try:
                    with open(filepath, "r") as f:
                        settings = json.load(f)

                    # Validate version
                    if settings.get("version") != "2.0":
                        raise ValueError("Incompatible settings version")

                    # Apply settings
                    main_settings = settings.get("main_settings", {})
                    self.window.main_tab.fps_spinbox.setValue(
                        main_settings.get("fps", 30)
                    )
                    self.window.main_tab.encoder_combo.setCurrentText(
                        main_settings.get("encoder", "RIFE")
                    )
                    self.window.main_tab.sanchez_checkbox.setChecked(
                        main_settings.get("enhance", False)
                    )

                    return True

                except Exception as e:
                    QMessageBox.critical(
                        self.window,
                        "Import Failed",
                        f"Failed to import settings: {str(e)}",
                    )
                    return False

        # Create manager
        portability = SettingsPortability(window)

        # Set some values
        window.main_tab.fps_spinbox.setValue(60)
        window.main_tab.encoder_combo.setCurrentText("RIFE")
        window.main_tab.sanchez_checkbox.setChecked(True)

        # Export settings
        success = portability.export_settings()
        assert success
        assert export_path.exists()

        # Change values
        window.main_tab.fps_spinbox.setValue(24)
        window.main_tab.encoder_combo.setCurrentText("FFmpeg")
        window.main_tab.sanchez_checkbox.setChecked(False)

        # Import settings
        success = portability.import_settings()
        assert success

        # Verify restored values
        assert window.main_tab.fps_spinbox.value() == 60
        assert window.main_tab.encoder_combo.currentText() == "RIFE"
        assert window.main_tab.sanchez_checkbox.isChecked()

    def test_preferences_reset_functionality(self, qtbot, window, mocker):
        """Test preferences reset functionality."""
        # Mock confirmation dialog
        mock_question = mocker.patch.object(QMessageBox, "question")
        mock_question.return_value = QMessageBox.StandardButton.Yes

        # Preferences reset manager
        class PreferencesReset:
            def __init__(self, window):
                self.window = window
                self.default_values = {
                    "fps": 30,
                    "encoder": "RIFE",
                    "quality": "high",
                    "threads": 4,
                    "enhance": False,
                    "crop": None,
                }

            def reset_to_defaults(self, category=None):
                # Confirm with user
                result = QMessageBox.question(
                    self.window,
                    "Reset Preferences",
                    f"Are you sure you want to reset {'all' if not category else category} preferences to defaults?\n"
                    "This action cannot be undone.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )

                if result != QMessageBox.StandardButton.Yes:
                    return False

                if not category or category == "main":
                    self.window.main_tab.fps_spinbox.setValue(
                        self.default_values["fps"]
                    )
                    self.window.main_tab.encoder_combo.setCurrentText(
                        self.default_values["encoder"]
                    )
                    self.window.main_tab.sanchez_checkbox.setChecked(
                        self.default_values["enhance"]
                    )

                if not category or category == "processing":
                    # Reset processing settings
                    if hasattr(self.window, "current_crop_rect"):
                        self.window.current_crop_rect = None
                        self.window.crop_handler.update_crop_ui()

                # Clear stored settings
                settings = QSettings()
                if not category:
                    settings.clear()
                else:
                    settings.beginGroup(category)
                    settings.remove("")  # Remove all in group
                    settings.endGroup()

                return True

        # Create reset manager
        reset_mgr = PreferencesReset(window)

        # Set non-default values
        window.main_tab.fps_spinbox.setValue(60)
        window.main_tab.encoder_combo.setCurrentText("FFmpeg")
        window.main_tab.sanchez_checkbox.setChecked(True)

        # Reset all
        success = reset_mgr.reset_to_defaults()
        assert success

        # Verify reset
        assert window.main_tab.fps_spinbox.value() == 30
        assert window.main_tab.encoder_combo.currentText() == "RIFE"
        assert not window.main_tab.sanchez_checkbox.isChecked()

        # Verify confirmation was shown
        mock_question.assert_called_once()
        args = mock_question.call_args[0]
        assert "Reset Preferences" in args[1]
        assert "all preferences" in args[2]

    def test_auto_save_settings(self, qtbot, window, mocker):
        """Test auto-save settings functionality."""
        # Mock QTimer for auto-save
        mock_timer = MagicMock()
        mocker.patch("PyQt6.QtCore.QTimer", return_value=mock_timer)

        # Auto-save manager
        class AutoSaveManager:
            def __init__(self, window, interval_ms=30000):
                self.window = window
                self.interval_ms = interval_ms
                self.timer = QTimer()
                self.timer.timeout.connect(self.auto_save)
                self.unsaved_changes = False
                self.last_save_time = None

            def start(self):
                self.timer.start(self.interval_ms)

            def stop(self):
                self.timer.stop()

            def mark_changed(self):
                self.unsaved_changes = True

            def auto_save(self):
                if self.unsaved_changes:
                    self.save_settings()
                    self.unsaved_changes = False
                    self.last_save_time = QTimer().toString()

            def save_settings(self):
                # Save current settings
                {
                    "fps": self.window.main_tab.fps_spinbox.value(),
                    "encoder": self.window.main_tab.encoder_combo.currentText(),
                    # Add more settings...
                }

                # Mock save operation
                return True

        # Create auto-save manager
        auto_save = AutoSaveManager(window, interval_ms=1000)  # 1 second for testing

        # Connect change signals
        window.main_tab.fps_spinbox.valueChanged.connect(auto_save.mark_changed)
        window.main_tab.encoder_combo.currentTextChanged.connect(auto_save.mark_changed)

        # Start auto-save
        auto_save.start()
        mock_timer.start.assert_called_with(1000)

        # Make changes
        window.main_tab.fps_spinbox.setValue(45)
        assert auto_save.unsaved_changes

        # Simulate auto-save trigger
        auto_save.auto_save()
        assert not auto_save.unsaved_changes
        assert auto_save.last_save_time is not None

        # Stop auto-save
        auto_save.stop()
        mock_timer.stop.assert_called()
