"""
Optimized tests for advanced settings persistence with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for expensive operations
- Combined settings management scenarios
- Batch testing of import/export operations
- Enhanced error handling coverage
"""

import json
import operator
from pathlib import Path
from unittest.mock import MagicMock

from PyQt6.QtCore import QSettings, QTimer
from PyQt6.QtWidgets import QFileDialog, QMessageBox
import pytest

from goesvfi.gui import MainWindow


class TestSettingsAdvancedOptimizedV2:
    """Optimized advanced settings persistence tests with full coverage."""

    @pytest.fixture(scope="class")
    def shared_app(self):
        """Shared QApplication instance."""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app
        app.processEvents()

    @pytest.fixture()
    def main_window(self, qtbot, shared_app, mocker):
        """Create MainWindow instance with mocks."""
        # Mock heavy components
        mocker.patch("goesvfi.integrity_check.combined_tab.CombinedIntegrityAndImageryTab")
        mocker.patch("goesvfi.integrity_check.enhanced_imagery_tab.EnhancedGOESImageryTab")

        window = MainWindow(debug_mode=True)
        qtbot.addWidget(window)
        window._post_init_setup()

        return window

    @pytest.fixture(scope="class")
    def temp_settings_workspace(self, tmp_path_factory):
        """Create temporary workspace for settings tests."""
        workspace = tmp_path_factory.mktemp("settings_workspace")

        # Create directory structure
        profiles_dir = workspace / "profiles"
        profiles_dir.mkdir()

        exports_dir = workspace / "exports"
        exports_dir.mkdir()

        backups_dir = workspace / "backups"
        backups_dir.mkdir()

        return {
            "workspace": workspace,
            "profiles": profiles_dir,
            "exports": exports_dir,
            "backups": backups_dir,
            "settings_file": workspace / "test_settings.ini",
        }

    @pytest.fixture()
    def mock_settings_components(self, mocker):
        """Create comprehensive mocks for settings components."""
        mocks = {
            "settings": MagicMock(spec=QSettings),
            "file_dialog_save": mocker.patch.object(QFileDialog, "getSaveFileName"),
            "file_dialog_open": mocker.patch.object(QFileDialog, "getOpenFileName"),
            "message_box_question": mocker.patch.object(QMessageBox, "question"),
            "message_box_critical": mocker.patch.object(QMessageBox, "critical"),
            "timer": MagicMock(spec=QTimer),
        }

        # Configure default returns
        mocks["file_dialog_save"].return_value = ("", "")
        mocks["file_dialog_open"].return_value = ("", "")
        mocks["message_box_question"].return_value = QMessageBox.StandardButton.Yes

        mocker.patch("PyQt6.QtCore.QSettings", return_value=mocks["settings"])
        mocker.patch("PyQt6.QtCore.QTimer", return_value=mocks["timer"])

        return mocks

    def test_profile_management_comprehensive(self, qtbot, main_window, temp_settings_workspace) -> None:
        """Test comprehensive profile management operations."""

        # Enhanced profile manager with validation and metadata
        class ProfileManager:
            def __init__(self, base_path) -> None:
                self.base_path = Path(base_path)
                self.profiles_dir = self.base_path / "profiles"
                self.profiles_dir.mkdir(exist_ok=True)
                self.metadata_file = self.profiles_dir / "_metadata.json"
                self.load_metadata()

            def load_metadata(self) -> None:
                """Load profile metadata."""
                if self.metadata_file.exists():
                    with open(self.metadata_file, encoding="utf-8") as f:
                        self.metadata = json.load(f)
                else:
                    self.metadata = {"profiles": {}, "last_updated": None}

            def save_metadata(self) -> None:
                """Save profile metadata."""
                self.metadata["last_updated"] = QTimer().toString()
                with open(self.metadata_file, "w", encoding="utf-8") as f:
                    json.dump(self.metadata, f, indent=2)

            def validate_profile_name(self, name):
                """Validate profile name."""
                if not name or len(name.strip()) == 0:
                    msg = "Profile name cannot be empty"
                    raise ValueError(msg)
                if any(char in name for char in '/\\:*?"<>|'):
                    msg = "Profile name contains invalid characters"
                    raise ValueError(msg)
                if len(name) > 50:
                    msg = "Profile name too long (max 50 characters)"
                    raise ValueError(msg)
                return name.strip()

            def save_profile(self, name, settings_dict, description="", tags=None):
                """Save profile with metadata."""
                name = self.validate_profile_name(name)
                profile_path = self.profiles_dir / f"{name}.json"

                # Create profile data with metadata
                profile_data = {
                    "metadata": {
                        "name": name,
                        "description": description,
                        "tags": tags or [],
                        "created": QTimer().toString(),
                        "version": "2.0",
                    },
                    "settings": settings_dict,
                }

                # Save profile
                with open(profile_path, "w", encoding="utf-8") as f:
                    json.dump(profile_data, f, indent=2)

                # Update metadata
                self.metadata["profiles"][name] = {
                    "description": description,
                    "tags": tags or [],
                    "file_size": profile_path.stat().st_size,
                }
                self.save_metadata()

                return profile_path

            def load_profile(self, name):
                """Load profile with validation."""
                profile_path = self.profiles_dir / f"{name}.json"

                if not profile_path.exists():
                    msg = f"Profile '{name}' not found"
                    raise FileNotFoundError(msg)

                with open(profile_path, encoding="utf-8") as f:
                    profile_data = json.load(f)

                # Validate format
                if "settings" not in profile_data:
                    # Legacy format
                    return profile_data

                return profile_data["settings"]

            def delete_profile(self, name) -> bool:
                """Delete profile and cleanup metadata."""
                profile_path = self.profiles_dir / f"{name}.json"

                if profile_path.exists():
                    profile_path.unlink()

                    # Remove from metadata
                    if name in self.metadata["profiles"]:
                        del self.metadata["profiles"][name]
                        self.save_metadata()

                    return True
                return False

            def list_profiles(self, filter_tags=None):
                """List profiles with optional tag filtering."""
                profiles = []
                for profile_file in self.profiles_dir.glob("*.json"):
                    if profile_file.name == "_metadata.json":
                        continue

                    profile_name = profile_file.stem
                    metadata = self.metadata["profiles"].get(profile_name, {})

                    if filter_tags:
                        profile_tags = metadata.get("tags", [])
                        if not any(tag in profile_tags for tag in filter_tags):
                            continue

                    profiles.append({
                        "name": profile_name,
                        "description": metadata.get("description", ""),
                        "tags": metadata.get("tags", []),
                        "size": metadata.get("file_size", 0),
                    })

                return profiles

            def duplicate_profile(self, source_name, new_name):
                """Duplicate an existing profile."""
                source_settings = self.load_profile(source_name)
                return self.save_profile(
                    new_name, source_settings, description=f"Copy of {source_name}", tags=["duplicate"]
                )

            def export_profile(self, name, export_path) -> bool:
                """Export profile to external file."""
                profile_data = self.load_profile(name)
                export_data = {
                    "export_info": {
                        "source_profile": name,
                        "export_date": QTimer().toString(),
                        "version": "2.0",
                    },
                    "profile": profile_data,
                }

                with open(export_path, "w", encoding="utf-8") as f:
                    json.dump(export_data, f, indent=2)

                return True

        workspace = temp_settings_workspace
        profile_mgr = ProfileManager(workspace["workspace"])

        # Test comprehensive profile operations
        profile_test_scenarios = [
            {
                "name": "high_quality_60fps",
                "settings": {
                    "fps": 60,
                    "encoder": "RIFE",
                    "quality": "high",
                    "crop_rect": [100, 100, 400, 300],
                    "advanced": {"threads": 8, "tile_size": 256},
                },
                "description": "High quality 60fps processing",
                "tags": ["quality", "performance"],
            },
            {
                "name": "fast_processing",
                "settings": {
                    "fps": 30,
                    "encoder": "FFmpeg",
                    "quality": "medium",
                    "threads": 16,
                },
                "description": "Fast processing with FFmpeg",
                "tags": ["speed", "ffmpeg"],
            },
            {
                "name": "balanced",
                "settings": {
                    "fps": 45,
                    "encoder": "RIFE",
                    "quality": "high",
                    "enhance": True,
                },
                "description": "Balanced quality and speed",
                "tags": ["balanced", "enhance"],
            },
        ]

        # Save all test profiles
        saved_profiles = []
        for scenario in profile_test_scenarios:
            profile_path = profile_mgr.save_profile(
                scenario["name"], scenario["settings"], scenario["description"], scenario["tags"]
            )
            saved_profiles.append(profile_path)
            assert profile_path.exists(), f"Profile save failed for {scenario['name']}"

        # Test profile listing and filtering
        all_profiles = profile_mgr.list_profiles()
        assert len(all_profiles) == 3, "Profile count incorrect"

        # Test tag filtering
        quality_profiles = profile_mgr.list_profiles(filter_tags=["quality"])
        assert len(quality_profiles) == 1, "Quality tag filtering failed"
        assert quality_profiles[0]["name"] == "high_quality_60fps"

        speed_profiles = profile_mgr.list_profiles(filter_tags=["speed"])
        assert len(speed_profiles) == 1, "Speed tag filtering failed"

        # Test profile loading
        for scenario in profile_test_scenarios:
            loaded_settings = profile_mgr.load_profile(scenario["name"])
            assert loaded_settings["fps"] == scenario["settings"]["fps"], f"FPS mismatch for {scenario['name']}"
            assert loaded_settings["encoder"] == scenario["settings"]["encoder"], (
                f"Encoder mismatch for {scenario['name']}"
            )

        # Test profile duplication
        duplicate_path = profile_mgr.duplicate_profile("high_quality_60fps", "high_quality_60fps_copy")
        assert duplicate_path.exists(), "Profile duplication failed"

        duplicate_settings = profile_mgr.load_profile("high_quality_60fps_copy")
        original_settings = profile_mgr.load_profile("high_quality_60fps")
        assert duplicate_settings["fps"] == original_settings["fps"], "Duplicate settings mismatch"

        # Test profile export
        export_path = workspace["exports"] / "exported_profile.json"
        export_success = profile_mgr.export_profile("balanced", export_path)
        assert export_success, "Profile export failed"
        assert export_path.exists(), "Export file not created"

        # Verify export content
        with open(export_path, encoding="utf-8") as f:
            export_data = json.load(f)
        assert export_data["export_info"]["source_profile"] == "balanced"
        assert export_data["profile"]["fps"] == 45

        # Test validation errors
        invalid_names = ["", "   ", "profile/with/slashes", "a" * 60]
        for invalid_name in invalid_names:
            with pytest.raises(ValueError):
                profile_mgr.save_profile(invalid_name, {"fps": 30})

        # Test deletion
        for scenario in profile_test_scenarios:
            delete_success = profile_mgr.delete_profile(scenario["name"])
            assert delete_success, f"Profile deletion failed for {scenario['name']}"

        # Test loading non-existent profile
        with pytest.raises(FileNotFoundError):
            profile_mgr.load_profile("non_existent_profile")

    def test_window_state_comprehensive_persistence(self, qtbot, main_window, mock_settings_components) -> None:
        """Test comprehensive window state persistence."""
        window = main_window
        mock_settings = mock_settings_components["settings"]

        # Enhanced window state manager
        class WindowStateManager:
            def __init__(self, window) -> None:
                self.window = window
                self.settings = QSettings()
                self.state_history = []

            def capture_current_state(self):
                """Capture complete window state."""
                return {
                    "geometry": {
                        "x": self.window.x(),
                        "y": self.window.y(),
                        "width": self.window.width(),
                        "height": self.window.height(),
                    },
                    "window_state": {
                        "is_maximized": self.window.isMaximized(),
                        "is_fullscreen": self.window.isFullScreen(),
                        "is_minimized": self.window.isMinimized(),
                    },
                    "ui_state": {
                        "current_tab": getattr(self.window.tab_widget, "currentIndex", lambda: 0)(),
                        "splitter_sizes": self.get_splitter_sizes(),
                    },
                    "timestamp": QTimer().toString(),
                }

            def get_splitter_sizes(self):
                """Get all splitter sizes."""
                splitter_sizes = {}
                # Mock splitter data since we don't have real splitters in test
                splitter_sizes["main_splitter"] = [300, 900]
                splitter_sizes["preview_splitter"] = [400, 400]
                return splitter_sizes

            def save_window_state(self, backup=True):
                """Save complete window state."""
                state = self.capture_current_state()

                if backup and hasattr(self, "_last_state"):
                    self.state_history.append(self._last_state)
                    # Keep only last 10 states
                    self.state_history = self.state_history[-10:]

                self._last_state = state

                # Save to settings
                self.settings.setValue("window/geometry", self.window.saveGeometry())
                self.settings.setValue("window/pos_x", state["geometry"]["x"])
                self.settings.setValue("window/pos_y", state["geometry"]["y"])
                self.settings.setValue("window/width", state["geometry"]["width"])
                self.settings.setValue("window/height", state["geometry"]["height"])
                self.settings.setValue("window/is_maximized", state["window_state"]["is_maximized"])
                self.settings.setValue("window/is_fullscreen", state["window_state"]["is_fullscreen"])
                self.settings.setValue("window/current_tab", state["ui_state"]["current_tab"])

                # Save splitter sizes
                for splitter_name, sizes in state["ui_state"]["splitter_sizes"].items():
                    self.settings.setValue(f"splitters/{splitter_name}", sizes)

                return state

            def restore_window_state(self, fallback_geometry=None):
                """Restore complete window state."""
                # Restore geometry
                geometry = self.settings.value("window/geometry")
                if geometry:
                    self.window.restoreGeometry(geometry)
                else:
                    # Fallback to individual values
                    fallback = fallback_geometry or (100, 100, 1200, 800)
                    x = self.settings.value("window/pos_x", fallback[0], type=int)
                    y = self.settings.value("window/pos_y", fallback[1], type=int)
                    width = self.settings.value("window/width", fallback[2], type=int)
                    height = self.settings.value("window/height", fallback[3], type=int)

                    self.window.setGeometry(x, y, width, height)

                # Restore window state
                if self.settings.value("window/is_maximized", False, type=bool):
                    self.window.showMaximized()
                elif self.settings.value("window/is_fullscreen", False, type=bool):
                    self.window.showFullScreen()

                # Restore UI state
                tab_index = self.settings.value("window/current_tab", 0, type=int)
                if hasattr(self.window, "tab_widget"):
                    max_index = getattr(self.window.tab_widget, "count", lambda: 1)() - 1
                    if 0 <= tab_index <= max_index:
                        self.window.tab_widget.setCurrentIndex(tab_index)

                return self.capture_current_state()

            def restore_previous_state(self) -> bool:
                """Restore previous state from history."""
                if not self.state_history:
                    return False

                previous_state = self.state_history.pop()
                geo = previous_state["geometry"]
                self.window.setGeometry(geo["x"], geo["y"], geo["width"], geo["height"])

                return True

            def validate_state(self, state):
                """Validate window state is reasonable."""
                geo = state["geometry"]

                # Check geometry bounds
                if geo["width"] < 300 or geo["height"] < 200:
                    return False, "Window too small"
                if geo["width"] > 5000 or geo["height"] > 5000:
                    return False, "Window too large"
                if geo["x"] < -1000 or geo["y"] < -1000:
                    return False, "Window position too far off-screen"

                return True, "Valid"

        state_mgr = WindowStateManager(window)

        # Test multiple window state scenarios
        window_states = [
            (200, 150, 1400, 900, False, False, "Normal window"),
            (0, 0, 800, 600, False, False, "Top-left position"),
            (100, 100, 1920, 1080, True, False, "Maximized window"),
            (50, 50, 1600, 1200, False, False, "Large window"),
        ]

        for x, y, width, height, maximized, fullscreen, description in window_states:
            # Set window state
            window.setGeometry(x, y, width, height)
            if maximized:
                window.showMaximized()
            elif fullscreen:
                window.showFullScreen()
            else:
                window.showNormal()

            # Save state
            saved_state = state_mgr.save_window_state()

            # Validate state
            is_valid, validation_msg = state_mgr.validate_state(saved_state)
            assert is_valid, f"Invalid state for {description}: {validation_msg}"

            # Verify save calls
            mock_settings.setValue.assert_any_call("window/pos_x", x)
            mock_settings.setValue.assert_any_call("window/pos_y", y)
            mock_settings.setValue.assert_any_call("window/width", width)
            mock_settings.setValue.assert_any_call("window/height", height)

            # Change to different geometry
            window.setGeometry(x + 100, y + 100, width - 200, height - 200)

            # Configure mock restore values
            mock_settings.value.side_effect = lambda key, default=None, type=None: {
                "window/pos_x": x,
                "window/pos_y": y,
                "window/width": width,
                "window/height": height,
                "window/is_maximized": maximized,
                "window/is_fullscreen": fullscreen,
                "window/current_tab": 0,
            }.get(key, default)

            # Restore state
            state_mgr.restore_window_state()

            # Verify restoration
            assert window.x() == x, f"X position not restored for {description}"
            assert window.y() == y, f"Y position not restored for {description}"
            assert window.width() == width, f"Width not restored for {description}"
            assert window.height() == height, f"Height not restored for {description}"

        # Test state history
        assert len(state_mgr.state_history) > 0, "State history empty"

        # Test restore previous state
        restore_success = state_mgr.restore_previous_state()
        assert restore_success, "Restore previous state failed"

        # Test fallback geometry
        mock_settings.value.side_effect = lambda key, default=None, type=None: default
        state_mgr.restore_window_state(fallback_geometry=(300, 200, 1000, 700))
        assert window.x() == 300, "Fallback X not applied"
        assert window.y() == 200, "Fallback Y not applied"

    def test_recent_items_comprehensive_management(self, qtbot, main_window) -> None:
        """Test comprehensive recent items management."""

        # Enhanced recent items manager with categories and persistence
        class RecentItemsManager:
            def __init__(self, max_items=10) -> None:
                self.max_items = max_items
                self.categories = {
                    "files": [],
                    "directories": [],
                    "searches": [],
                    "urls": [],
                    "commands": [],
                }
                self.access_counts = {}
                self.last_access = {}

            def add_item(self, category, item, metadata=None) -> None:
                """Add item to category with metadata."""
                if category not in self.categories:
                    msg = f"Unknown category: {category}"
                    raise ValueError(msg)

                item_str = str(item)
                category_list = self.categories[category]

                # Remove if already exists
                if item_str in category_list:
                    category_list.remove(item_str)

                # Add to front
                category_list.insert(0, item_str)

                # Update access tracking
                self.access_counts[item_str] = self.access_counts.get(item_str, 0) + 1
                self.last_access[item_str] = QTimer().toString()

                # Store metadata if provided
                if metadata:
                    if not hasattr(self, "_metadata"):
                        self._metadata = {}
                    self._metadata[item_str] = metadata

                # Trim to max
                self.categories[category] = category_list[: self.max_items]

                # Clean up tracking for removed items
                self._cleanup_tracking(category_list)

            def _cleanup_tracking(self, current_items) -> None:
                """Clean up tracking data for removed items."""
                set(current_items)

                # Remove tracking for items no longer in any category
                all_items = set()
                for cat_items in self.categories.values():
                    all_items.update(cat_items)

                for item in list(self.access_counts.keys()):
                    if item not in all_items:
                        del self.access_counts[item]
                        if item in self.last_access:
                            del self.last_access[item]
                        if hasattr(self, "_metadata") and item in self._metadata:
                            del self._metadata[item]

            def get_items(self, category, sort_by="recent"):
                """Get items from category with optional sorting."""
                if category not in self.categories:
                    return []

                items = self.categories[category].copy()

                if sort_by == "frequency":
                    items.sort(key=lambda x: self.access_counts.get(x, 0), reverse=True)
                elif sort_by == "alphabetical":
                    items.sort()
                # "recent" is already in correct order

                return items

            def remove_item(self, category, item) -> bool:
                """Remove specific item from category."""
                if category in self.categories:
                    item_str = str(item)
                    if item_str in self.categories[category]:
                        self.categories[category].remove(item_str)
                        return True
                return False

            def clear_category(self, category) -> bool:
                """Clear all items from category."""
                if category in self.categories:
                    self.categories[category].clear()
                    return True
                return False

            def clear_all(self) -> None:
                """Clear all categories."""
                for category in self.categories:
                    self.categories[category].clear()
                self.access_counts.clear()
                self.last_access.clear()
                if hasattr(self, "_metadata"):
                    self._metadata.clear()

            def get_statistics(self):
                """Get usage statistics."""
                total_items = sum(len(items) for items in self.categories.values())
                most_accessed = (
                    max(self.access_counts.items(), key=operator.itemgetter(1)) if self.access_counts else None
                )

                return {
                    "total_items": total_items,
                    "categories": {k: len(v) for k, v in self.categories.items()},
                    "most_accessed": most_accessed,
                    "total_accesses": sum(self.access_counts.values()),
                }

            def export_to_dict(self):
                """Export all data to dictionary."""
                return {
                    "categories": self.categories,
                    "access_counts": self.access_counts,
                    "last_access": self.last_access,
                    "metadata": getattr(self, "_metadata", {}),
                    "max_items": self.max_items,
                }

            def import_from_dict(self, data) -> None:
                """Import data from dictionary."""
                self.categories = data.get("categories", {})
                self.access_counts = data.get("access_counts", {})
                self.last_access = data.get("last_access", {})
                if "metadata" in data:
                    self._metadata = data["metadata"]
                self.max_items = data.get("max_items", 10)

        recent_mgr = RecentItemsManager(max_items=5)

        # Test comprehensive item management scenarios
        test_scenarios = [
            {
                "category": "files",
                "items": [
                    "/path/to/video1.mp4",
                    "/path/to/video2.mp4",
                    "/path/to/video3.mp4",
                    "/path/to/video1.mp4",  # Duplicate - should move to front
                    "/path/to/video4.mp4",
                    "/path/to/video5.mp4",
                    "/path/to/video6.mp4",  # Exceeds max
                ],
                "metadata": {"type": "video", "format": "mp4"},
            },
            {
                "category": "directories",
                "items": [
                    "/home/user/videos",
                    "/home/user/downloads",
                    "/tmp/processing",
                    "/home/user/videos",  # Move to front
                ],
                "metadata": {"type": "directory"},
            },
            {
                "category": "searches",
                "items": [
                    "satellite imagery",
                    "weather data",
                    "GOES 16",
                    "RIFE interpolation",
                ],
                "metadata": {"type": "search_term"},
            },
            {
                "category": "urls",
                "items": [
                    "https://example.com/data1",
                    "https://example.com/data2",
                    "ftp://data.server.com/files",
                ],
                "metadata": {"type": "data_source"},
            },
        ]

        # Add items for each scenario
        for scenario in test_scenarios:
            category = scenario["category"]
            for item in scenario["items"]:
                recent_mgr.add_item(category, item, scenario["metadata"])

        # Verify item management
        for scenario in test_scenarios:
            category = scenario["category"]
            items = recent_mgr.get_items(category)

            assert len(items) <= 5, f"Max items exceeded for {category}"

            # Check specific behaviors
            if category == "files":
                assert items[0] == "/path/to/video6.mp4", "Most recent file not first"
                assert items.count("/path/to/video1.mp4") == 1, "Duplicate not handled correctly"
                assert len(items) == 5, "Max items not enforced"

            elif category == "directories":
                assert items[0] == "/home/user/videos", "Moved duplicate not first"
                assert len(items) == 3, f"Directory count incorrect: {len(items)}"

        # Test different sorting methods
        sort_test_category = "files"

        # Add more accesses to create frequency differences
        for _ in range(3):
            recent_mgr.add_item(sort_test_category, "/path/to/video2.mp4")

        # Test sorting
        recent_items = recent_mgr.get_items(sort_test_category, "recent")
        frequent_items = recent_mgr.get_items(sort_test_category, "frequency")
        alpha_items = recent_mgr.get_items(sort_test_category, "alphabetical")

        assert recent_items[0] == "/path/to/video2.mp4", "Recent sort incorrect"
        assert frequent_items[0] == "/path/to/video2.mp4", "Frequency sort incorrect"
        assert alpha_items == sorted(alpha_items), "Alphabetical sort incorrect"

        # Test item removal
        remove_success = recent_mgr.remove_item("files", "/path/to/video2.mp4")
        assert remove_success, "Item removal failed"
        assert "/path/to/video2.mp4" not in recent_mgr.get_items("files"), "Item not removed"

        # Test category clearing
        initial_count = len(recent_mgr.get_items("searches"))
        assert initial_count > 0, "No searches to clear"

        clear_success = recent_mgr.clear_category("searches")
        assert clear_success, "Category clear failed"
        assert len(recent_mgr.get_items("searches")) == 0, "Category not cleared"

        # Test statistics
        stats = recent_mgr.get_statistics()
        assert isinstance(stats["total_items"], int), "Invalid total items"
        assert "categories" in stats, "Categories missing from stats"
        assert stats["total_accesses"] > 0, "No accesses recorded"

        # Test export/import
        exported_data = recent_mgr.export_to_dict()
        assert "categories" in exported_data, "Export missing categories"
        assert "access_counts" in exported_data, "Export missing access counts"

        # Create new manager and import
        new_mgr = RecentItemsManager()
        new_mgr.import_from_dict(exported_data)

        # Verify import
        for category in recent_mgr.categories:
            assert new_mgr.categories[category] == recent_mgr.categories[category], f"Import failed for {category}"

        # Test clear all
        recent_mgr.clear_all()
        stats_after_clear = recent_mgr.get_statistics()
        assert stats_after_clear["total_items"] == 0, "Clear all failed"

    def test_settings_migration_comprehensive(self, qtbot, main_window, temp_settings_workspace) -> None:
        """Test comprehensive settings migration from multiple versions."""

        # Enhanced settings migrator with multiple version support
        class SettingsMigrator:
            def __init__(self) -> None:
                self.migrations = {
                    "1.0": self.migrate_1_0_to_1_1,
                    "1.1": self.migrate_1_1_to_1_2,
                    "1.2": self.migrate_1_2_to_2_0,
                    "2.0": self.migrate_2_0_to_2_1,
                }
                self.backup_dir = None

            def set_backup_dir(self, backup_dir) -> None:
                """Set directory for migration backups."""
                self.backup_dir = Path(backup_dir)
                self.backup_dir.mkdir(exist_ok=True)

            def create_backup(self, settings, version):
                """Create backup before migration."""
                if self.backup_dir:
                    backup_file = self.backup_dir / f"settings_backup_v{version}.json"
                    with open(backup_file, "w", encoding="utf-8") as f:
                        json.dump(settings, f, indent=2)
                    return backup_file
                return None

            def get_version(self, settings):
                """Get version from settings."""
                return settings.get("version", "1.0")

            def validate_migration(self, old_settings, new_settings) -> bool:
                """Validate migration didn't lose important data."""
                # Check that critical settings are preserved or migrated
                critical_keys = ["fps", "encoder", "quality"]
                for key in critical_keys:
                    if key in old_settings:
                        # Should exist somewhere in new settings structure
                        found = self._find_key_in_nested(new_settings, key)
                        if not found:
                            msg = f"Critical setting '{key}' lost in migration"
                            raise ValueError(msg)
                return True

            def _find_key_in_nested(self, data, key) -> bool:
                """Find key in nested dictionary."""
                if isinstance(data, dict):
                    if key in data:
                        return True
                    for value in data.values():
                        if self._find_key_in_nested(value, key):
                            return True
                return False

            def migrate(self, settings):
                """Migrate settings through all versions."""
                original_version = self.get_version(settings)
                current_version = original_version
                migration_log = []

                # Create initial backup
                self.create_backup(settings, original_version)

                while current_version in self.migrations:
                    old_settings = settings.copy()
                    migration_func = self.migrations[current_version]

                    try:
                        settings = migration_func(settings)
                        new_version = self.get_version(settings)

                        # Validate migration
                        self.validate_migration(old_settings, settings)

                        migration_log.append({
                            "from": current_version,
                            "to": new_version,
                            "status": "success",
                        })

                        current_version = new_version

                    except Exception as e:
                        migration_log.append({
                            "from": current_version,
                            "to": "failed",
                            "status": "error",
                            "error": str(e),
                        })
                        break

                settings["migration_log"] = migration_log
                return settings

            def migrate_1_0_to_1_1(self, settings):
                """Migrate from 1.0 to 1.1 format."""
                if "output_directory" in settings:
                    output_path = Path(settings["output_directory"])
                    settings["output_dir"] = str(output_path.parent)
                    settings["output_filename"] = output_path.name
                    del settings["output_directory"]

                # Add new v1.1 features
                settings.setdefault("auto_save", True)
                settings.setdefault("confirm_exit", True)
                settings.setdefault("max_memory_usage", 0.8)

                settings["version"] = "1.1"
                return settings

            def migrate_1_1_to_1_2(self, settings):
                """Migrate from 1.1 to 1.2 format."""
                # Add preview settings
                settings.setdefault("preview_quality", "medium")
                settings.setdefault("preview_fps", 15)

                # Convert boolean enhance to enhancement level
                if "enhance" in settings:
                    settings["enhancement_level"] = "high" if settings["enhance"] else "none"
                    del settings["enhance"]

                settings["version"] = "1.2"
                return settings

            def migrate_1_2_to_2_0(self, settings):
                """Migrate from 1.2 to 2.0 format (major restructure)."""
                old_settings = settings.copy()

                return {
                    "version": "2.0",
                    "general": {
                        "auto_save": old_settings.get("auto_save", True),
                        "confirm_exit": old_settings.get("confirm_exit", True),
                        "theme": old_settings.get("theme", "default"),
                        "language": old_settings.get("language", "en"),
                    },
                    "processing": {
                        "fps": old_settings.get("fps", 30),
                        "encoder": old_settings.get("encoder", "RIFE"),
                        "quality": old_settings.get("quality", "high"),
                        "enhancement_level": old_settings.get("enhancement_level", "none"),
                        "max_memory_usage": old_settings.get("max_memory_usage", 0.8),
                    },
                    "preview": {
                        "quality": old_settings.get("preview_quality", "medium"),
                        "fps": old_settings.get("preview_fps", 15),
                        "auto_update": old_settings.get("auto_preview", True),
                    },
                    "paths": {
                        "input_dir": old_settings.get("input_dir", ""),
                        "output_dir": old_settings.get("output_dir", ""),
                        "output_filename": old_settings.get("output_filename", ""),
                        "temp_dir": old_settings.get("temp_dir", ""),
                    },
                    "advanced": {
                        "threads": old_settings.get("threads", 4),
                        "tile_size": old_settings.get("tile_size", 256),
                        "debug_mode": old_settings.get("debug_mode", False),
                    },
                }

            def migrate_2_0_to_2_1(self, settings):
                """Migrate from 2.0 to 2.1 format."""
                # Add new v2.1 features
                if "ui" not in settings:
                    settings["ui"] = {}

                settings["ui"].update({
                    "show_tooltips": True,
                    "compact_mode": False,
                    "status_bar": True,
                    "toolbar": True,
                })

                # Add performance monitoring
                if "monitoring" not in settings:
                    settings["monitoring"] = {
                        "enable_metrics": False,
                        "log_performance": False,
                        "alert_on_errors": True,
                    }

                settings["version"] = "2.1"
                return settings

        workspace = temp_settings_workspace
        migrator = SettingsMigrator()
        migrator.set_backup_dir(workspace["backups"])

        # Test migration scenarios for different starting versions
        migration_test_cases = [
            {
                "name": "v1.0_basic",
                "input": {
                    "output_directory": "/old/path/output.mp4",
                    "fps": 24,
                    "encoder": "FFmpeg",
                    "quality": "medium",
                    "enhance": True,
                },
                "expected_final_version": "2.1",
            },
            {
                "name": "v1.1_intermediate",
                "input": {
                    "version": "1.1",
                    "output_dir": "/path/to/output",
                    "output_filename": "result.mp4",
                    "fps": 60,
                    "encoder": "RIFE",
                    "quality": "high",
                    "auto_save": False,
                    "enhance": True,
                },
                "expected_final_version": "2.1",
            },
            {
                "name": "v1.2_near_current",
                "input": {
                    "version": "1.2",
                    "fps": 45,
                    "encoder": "RIFE",
                    "quality": "high",
                    "enhancement_level": "medium",
                    "preview_quality": "high",
                    "preview_fps": 30,
                },
                "expected_final_version": "2.1",
            },
            {
                "name": "v2.0_current_major",
                "input": {
                    "version": "2.0",
                    "general": {"theme": "dark"},
                    "processing": {"fps": 30, "encoder": "RIFE"},
                    "paths": {"input_dir": "/input"},
                },
                "expected_final_version": "2.1",
            },
        ]

        for test_case in migration_test_cases:
            original_settings = test_case["input"].copy()

            # Perform migration
            migrated_settings = migrator.migrate(original_settings)

            # Verify final version
            final_version = migrator.get_version(migrated_settings)
            assert final_version == test_case["expected_final_version"], (
                f"Final version incorrect for {test_case['name']}: got {final_version}"
            )

            # Verify migration log exists
            assert "migration_log" in migrated_settings, f"Migration log missing for {test_case['name']}"

            # Verify all migrations were successful
            migration_log = migrated_settings["migration_log"]
            for migration_step in migration_log:
                assert migration_step["status"] == "success", (
                    f"Migration failed for {test_case['name']}: {migration_step}"
                )

            # Verify structure for v2.1 format
            if final_version == "2.1":
                expected_sections = ["general", "processing", "preview", "paths", "advanced", "ui", "monitoring"]
                for section in expected_sections:
                    assert section in migrated_settings, f"Missing section {section} in {test_case['name']}"

            # Verify critical data preservation
            if "fps" in original_settings:
                assert migrator._find_key_in_nested(migrated_settings, "fps"), (
                    f"FPS setting lost in {test_case['name']}"
                )

            if "encoder" in original_settings:
                assert migrator._find_key_in_nested(migrated_settings, "encoder"), (
                    f"Encoder setting lost in {test_case['name']}"
                )

        # Test migration failure handling
        invalid_settings = {
            "version": "1.0",
            "fps": "invalid_value",  # This should cause validation to fail
        }

        # Mock the validation to fail
        original_validate = migrator.validate_migration

        def failing_validate(old, new):
            if "fps" in old and old["fps"] == "invalid_value":
                msg = "Invalid FPS value"
                raise ValueError(msg)
            return original_validate(old, new)

        migrator.validate_migration = failing_validate

        failed_migration = migrator.migrate(invalid_settings)
        migration_log = failed_migration.get("migration_log", [])

        # Should have at least one failed migration
        failed_steps = [step for step in migration_log if step["status"] == "error"]
        assert len(failed_steps) > 0, "Failed migration not recorded"

    def test_settings_import_export_comprehensive(
        self, qtbot, main_window, temp_settings_workspace, mock_settings_components
    ) -> None:
        """Test comprehensive settings import and export functionality."""
        window = main_window
        workspace = temp_settings_workspace
        mocks = mock_settings_components

        # Enhanced settings import/export with validation and format support
        class SettingsPortability:
            def __init__(self, window) -> None:
                self.window = window
                self.supported_formats = ["json", "ini", "yaml"]
                self.export_templates = {
                    "minimal": ["processing", "paths"],
                    "standard": ["general", "processing", "paths", "preview"],
                    "complete": None,  # All sections
                }

            def gather_current_settings(self):
                """Gather all current settings from UI."""
                return {
                    "version": "2.1",
                    "exported_date": QTimer().toString(),
                    "export_source": "GUI",
                    "general": {
                        "theme": "default",
                        "language": "en",
                        "auto_save": True,
                    },
                    "processing": {
                        "fps": self.window.main_tab.fps_spinbox.value(),
                        "encoder": self.window.main_tab.encoder_combo.currentText(),
                        "enhance": self.window.main_tab.sanchez_checkbox.isChecked(),
                        "quality": "high",
                    },
                    "preview": {
                        "quality": "medium",
                        "auto_update": True,
                        "fps": 15,
                    },
                    "paths": {
                        "input_dir": getattr(self.window.main_tab.in_dir_edit, "text", lambda: "")(),
                        "output_file": getattr(self.window.main_tab.out_file_edit, "text", lambda: "")(),
                    },
                    "window_state": {
                        "geometry": str(self.window.geometry()),
                        "tab_index": getattr(self.window.tab_widget, "currentIndex", lambda: 0)(),
                    },
                    "advanced": {
                        "threads": getattr(self.window.main_tab.max_workers_spinbox, "value", lambda: 4)(),
                        "debug_mode": False,
                    },
                    "ui": {
                        "show_tooltips": True,
                        "compact_mode": False,
                    },
                }

            def filter_settings_by_template(self, settings, template_name):
                """Filter settings by export template."""
                if template_name not in self.export_templates:
                    return settings

                template_sections = self.export_templates[template_name]
                if template_sections is None:  # Complete export
                    return settings

                filtered = {
                    "version": settings.get("version"),
                    "exported_date": settings.get("exported_date"),
                    "export_template": template_name,
                }

                for section in template_sections:
                    if section in settings:
                        filtered[section] = settings[section]

                return filtered

            def export_settings(self, template="standard", format="json"):
                """Export settings with template and format options."""
                if format not in self.supported_formats:
                    msg = f"Unsupported format: {format}"
                    raise ValueError(msg)

                # Get save location
                file_extension = f"*.{format}"
                filter_text = f"{format.upper()} Files ({file_extension});;All Files (*)"
                default_filename = f"goes_vfi_settings_{template}.{format}"

                filepath, _selected_filter = QFileDialog.getSaveFileName(
                    self.window,
                    f"Export Settings ({template})",
                    default_filename,
                    filter_text,
                )

                if not filepath:
                    return {"success": False, "reason": "cancelled"}

                try:
                    # Gather and filter settings
                    all_settings = self.gather_current_settings()
                    export_settings = self.filter_settings_by_template(all_settings, template)

                    # Export in requested format
                    if format == "json":
                        with open(filepath, "w", encoding="utf-8") as f:
                            json.dump(export_settings, f, indent=2)
                    elif format == "ini":
                        # Convert to INI format (simplified)
                        ini_content = self._dict_to_ini(export_settings)
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(ini_content)
                    elif format == "yaml":
                        # Mock YAML export (would need PyYAML)
                        yaml_content = self._dict_to_yaml_mock(export_settings)
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(yaml_content)

                    return {
                        "success": True,
                        "filepath": filepath,
                        "format": format,
                        "template": template,
                        "sections_exported": len(export_settings) - 3,  # Minus metadata
                    }

                except Exception as e:
                    return {
                        "success": False,
                        "reason": "error",
                        "error": str(e),
                    }

            def _dict_to_ini(self, data):
                """Convert dictionary to INI format."""
                lines = []
                for section, values in data.items():
                    if isinstance(values, dict):
                        lines.append(f"[{section}]")
                        for key, value in values.items():
                            lines.append(f"{key} = {value}")
                        lines.append("")
                return "\n".join(lines)

            def _dict_to_yaml_mock(self, data):
                """Mock YAML conversion."""
                lines = []
                for section, values in data.items():
                    lines.append(f"{section}:")
                    if isinstance(values, dict):
                        for key, value in values.items():
                            lines.append(f"  {key}: {value}")
                    else:
                        lines.append(f"  {values}")
                return "\n".join(lines)

            def validate_import_file(self, filepath):
                """Validate import file format and content."""
                try:
                    if filepath.endswith(".json"):
                        with open(filepath, encoding="utf-8") as f:
                            data = json.load(f)
                    elif filepath.endswith(".ini"):
                        # Mock INI parsing
                        data = {"version": "2.0", "general": {}}
                    else:
                        return {"valid": False, "error": "Unsupported file format"}

                    # Check for required fields
                    if "version" not in data:
                        return {"valid": False, "error": "Missing version information"}

                    # Check version compatibility
                    version = data["version"]
                    if version not in {"1.0", "1.1", "1.2", "2.0", "2.1"}:
                        return {"valid": False, "error": f"Unsupported version: {version}"}

                    return {"valid": True, "data": data, "version": version}

                except Exception as e:
                    return {"valid": False, "error": f"File parsing error: {e!s}"}

            def import_settings(self, merge_mode="replace"):
                """Import settings with validation and merge options."""
                # Get file to import
                filter_text = "All Supported (*.json *.ini);;JSON Files (*.json);;INI Files (*.ini);;All Files (*)"
                filepath, _selected_filter = QFileDialog.getOpenFileName(
                    self.window,
                    "Import Settings",
                    "",
                    filter_text,
                )

                if not filepath:
                    return {"success": False, "reason": "cancelled"}

                # Validate file
                validation_result = self.validate_import_file(filepath)
                if not validation_result["valid"]:
                    QMessageBox.critical(
                        self.window,
                        "Import Failed",
                        f"Invalid settings file: {validation_result['error']}",
                    )
                    return {"success": False, "reason": "invalid_file", "error": validation_result["error"]}

                try:
                    import_data = validation_result["data"]

                    # Store current settings for rollback
                    current_settings = self.gather_current_settings()

                    # Apply imported settings based on merge mode
                    if merge_mode == "replace":
                        self._apply_all_settings(import_data)
                    elif merge_mode == "merge":
                        merged_settings = self._merge_settings(current_settings, import_data)
                        self._apply_all_settings(merged_settings)

                    return {
                        "success": True,
                        "filepath": filepath,
                        "merge_mode": merge_mode,
                        "version": validation_result["version"],
                        "sections_imported": len([k for k, v in import_data.items() if isinstance(v, dict)]),
                        "rollback_data": current_settings,
                    }

                except Exception as e:
                    QMessageBox.critical(
                        self.window,
                        "Import Failed",
                        f"Failed to apply settings: {e!s}",
                    )
                    return {"success": False, "reason": "apply_error", "error": str(e)}

            def _apply_all_settings(self, settings) -> None:
                """Apply settings to UI components."""
                # Apply processing settings
                if "processing" in settings:
                    proc = settings["processing"]
                    if "fps" in proc:
                        self.window.main_tab.fps_spinbox.setValue(proc["fps"])
                    if "encoder" in proc:
                        self.window.main_tab.encoder_combo.setCurrentText(proc["encoder"])
                    if "enhance" in proc:
                        self.window.main_tab.sanchez_checkbox.setChecked(proc["enhance"])

                # Apply path settings
                if "paths" in settings:
                    paths = settings["paths"]
                    if "input_dir" in paths:
                        self.window.main_tab.in_dir_edit.setText(paths["input_dir"])
                    if "output_file" in paths:
                        self.window.main_tab.out_file_edit.setText(paths["output_file"])

                # Apply advanced settings
                if "advanced" in settings:
                    adv = settings["advanced"]
                    if "threads" in adv:
                        self.window.main_tab.max_workers_spinbox.setValue(adv["threads"])

            def _merge_settings(self, current, imported):
                """Merge imported settings with current settings."""
                merged = current.copy()

                for section, values in imported.items():
                    if isinstance(values, dict) and section in merged:
                        merged[section].update(values)
                    else:
                        merged[section] = values

                return merged

            def rollback_import(self, rollback_data):
                """Rollback to previous settings."""
                try:
                    self._apply_all_settings(rollback_data)
                    return {"success": True}
                except Exception as e:
                    return {"success": False, "error": str(e)}

        portability = SettingsPortability(window)

        # Set up mock file dialog responses
        export_path = workspace["exports"] / "exported_settings.json"
        import_path = workspace["exports"] / "import_settings.json"

        mocks["file_dialog_save"].return_value = (str(export_path), "JSON Files (*.json)")
        mocks["file_dialog_open"].return_value = (str(import_path), "JSON Files (*.json)")

        # Test comprehensive export scenarios
        export_scenarios = [
            ("minimal", "json", ["processing", "paths"]),
            ("standard", "json", ["general", "processing", "paths", "preview"]),
            ("complete", "json", None),  # All sections
            ("standard", "ini", ["general", "processing", "paths", "preview"]),
        ]

        for template, format_type, expected_sections in export_scenarios:
            # Set some test values
            window.main_tab.fps_spinbox.setValue(60)
            window.main_tab.encoder_combo.setCurrentText("RIFE")
            window.main_tab.sanchez_checkbox.setChecked(True)

            # Test export
            export_result = portability.export_settings(template, format_type)

            assert export_result["success"], (
                f"Export failed for {template}/{format_type}: {export_result.get('reason', 'unknown')}"
            )
            assert export_result["template"] == template, "Template mismatch in result"
            assert export_result["format"] == format_type, "Format mismatch in result"

            # Verify file was created
            assert export_path.exists(), f"Export file not created for {template}/{format_type}"

            # Verify content for JSON exports
            if format_type == "json":
                with open(export_path, encoding="utf-8") as f:
                    exported_data = json.load(f)

                assert "version" in exported_data, "Version missing from export"
                assert "exported_date" in exported_data, "Export date missing"

                if expected_sections:
                    for section in expected_sections:
                        assert section in exported_data, f"Expected section {section} missing from {template} export"

            # Clean up for next test
            if export_path.exists():
                export_path.unlink()

        # Test import scenarios
        # Create test import files
        import_test_cases = [
            {
                "filename": "valid_settings.json",
                "content": {
                    "version": "2.1",
                    "processing": {"fps": 45, "encoder": "FFmpeg", "enhance": False},
                    "paths": {"input_dir": "/imported/input", "output_file": "/imported/output.mp4"},
                    "advanced": {"threads": 8},
                },
                "should_succeed": True,
            },
            {
                "filename": "old_version.json",
                "content": {
                    "version": "1.0",
                    "fps": 30,
                    "encoder": "RIFE",
                    "output_directory": "/old/output.mp4",
                },
                "should_succeed": True,
            },
            {
                "filename": "invalid_version.json",
                "content": {
                    "version": "999.0",
                    "processing": {"fps": 30},
                },
                "should_succeed": False,
            },
            {
                "filename": "no_version.json",
                "content": {
                    "processing": {"fps": 30},
                },
                "should_succeed": False,
            },
        ]

        for test_case in import_test_cases:
            import_file = workspace["exports"] / test_case["filename"]
            with open(import_file, "w", encoding="utf-8") as f:
                json.dump(test_case["content"], f, indent=2)

            # Mock file dialog to return this file
            mocks["file_dialog_open"].return_value = (str(import_file), "JSON Files (*.json)")

            # Test import
            import_result = portability.import_settings("replace")

            if test_case["should_succeed"]:
                assert import_result["success"], (
                    f"Import should have succeeded for {test_case['filename']}: {import_result.get('error', 'unknown')}"
                )
                assert "rollback_data" in import_result, "Rollback data not provided"

                # Verify settings were applied (for valid imports)
                if "processing" in test_case["content"]:
                    expected_fps = test_case["content"]["processing"]["fps"]
                    assert window.main_tab.fps_spinbox.value() == expected_fps, "FPS not imported correctly"

                # Test rollback
                rollback_result = portability.rollback_import(import_result["rollback_data"])
                assert rollback_result["success"], "Rollback failed"

            else:
                assert not import_result["success"], f"Import should have failed for {test_case['filename']}"
                assert "error" in import_result, "Error details not provided for failed import"

        # Test merge mode import
        # Set initial values
        window.main_tab.fps_spinbox.setValue(30)
        window.main_tab.encoder_combo.setCurrentText("RIFE")

        # Create partial import
        partial_import = workspace["exports"] / "partial_import.json"
        with open(partial_import, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "version": "2.1",
                    "processing": {"fps": 60},  # Only change FPS
                    # Encoder should remain unchanged
                },
                f,
            )

        mocks["file_dialog_open"].return_value = (str(partial_import), "JSON Files (*.json)")

        merge_result = portability.import_settings("merge")
        assert merge_result["success"], "Merge import failed"

        # Verify merge behavior
        assert window.main_tab.fps_spinbox.value() == 60, "FPS not updated in merge"
        assert window.main_tab.encoder_combo.currentText() == "RIFE", "Encoder changed unexpectedly in merge"

    def test_auto_save_and_preferences_comprehensive(self, qtbot, main_window, mock_settings_components) -> None:
        """Test comprehensive auto-save and preferences reset functionality."""
        window = main_window
        mocks = mock_settings_components

        # Enhanced auto-save with intelligent change detection
        class AutoSaveManager:
            def __init__(self, window, interval_ms=30000) -> None:
                self.window = window
                self.interval_ms = interval_ms
                self.timer = QTimer()
                self.timer.timeout.connect(self.auto_save)
                self.unsaved_changes = False
                self.change_tracking = {}
                self.last_save_time = None
                self.save_queue = []
                self.save_stats = {
                    "total_saves": 0,
                    "failed_saves": 0,
                    "last_save_duration": 0,
                }

            def start(self) -> None:
                """Start auto-save timer."""
                self.timer.start(self.interval_ms)
                self.last_save_time = QTimer().toString()

            def stop(self) -> None:
                """Stop auto-save timer."""
                self.timer.stop()

            def set_interval(self, interval_ms) -> None:
                """Change auto-save interval."""
                self.interval_ms = interval_ms
                if self.timer.isActive():
                    self.timer.stop()
                    self.timer.start(interval_ms)

            def mark_changed(self, setting_name, old_value, new_value) -> None:
                """Mark specific setting as changed with detailed tracking."""
                if old_value != new_value:
                    self.unsaved_changes = True
                    self.change_tracking[setting_name] = {
                        "old_value": old_value,
                        "new_value": new_value,
                        "timestamp": QTimer().toString(),
                    }

                    # Add to save queue if not already there
                    if setting_name not in self.save_queue:
                        self.save_queue.append(setting_name)

            def get_pending_changes(self):
                """Get list of pending changes."""
                return list(self.change_tracking.keys())

            def auto_save(self) -> None:
                """Perform auto-save if there are unsaved changes."""
                if self.unsaved_changes:
                    QTimer().toString()

                    try:
                        success = self.save_settings()
                        if success:
                            self.unsaved_changes = False
                            self.change_tracking.clear()
                            self.save_queue.clear()
                            self.last_save_time = QTimer().toString()
                            self.save_stats["total_saves"] += 1
                        else:
                            self.save_stats["failed_saves"] += 1

                    except Exception:
                        self.save_stats["failed_saves"] += 1
                        # Log error but don't crash

            def force_save(self):
                """Force immediate save regardless of changes."""
                return self.save_settings()

            def save_settings(self) -> bool | None:
                """Save current settings to persistent storage."""
                try:
                    settings_data = {
                        "fps": self.window.main_tab.fps_spinbox.value(),
                        "encoder": self.window.main_tab.encoder_combo.currentText(),
                        "enhance": self.window.main_tab.sanchez_checkbox.isChecked(),
                        "max_workers": getattr(self.window.main_tab.max_workers_spinbox, "value", lambda: 4)(),
                        "auto_save_enabled": True,
                        "last_save": self.last_save_time,
                    }

                    # Mock save operation to QSettings
                    settings = QSettings()
                    for key, value in settings_data.items():
                        settings.setValue(f"auto_save/{key}", value)

                    return True

                except Exception:
                    return False

            def get_save_statistics(self):
                """Get auto-save statistics."""
                return self.save_stats.copy()

        # Enhanced preferences reset with granular control
        class PreferencesReset:
            def __init__(self, window) -> None:
                self.window = window
                self.default_values = {
                    "general": {
                        "theme": "default",
                        "language": "en",
                        "auto_save": True,
                    },
                    "processing": {
                        "fps": 30,
                        "encoder": "RIFE",
                        "quality": "high",
                        "enhance": False,
                    },
                    "advanced": {
                        "threads": 4,
                        "tile_size": 256,
                        "debug_mode": False,
                    },
                    "paths": {
                        "input_dir": "",
                        "output_file": "",
                        "temp_dir": "",
                    },
                    "ui": {
                        "show_tooltips": True,
                        "compact_mode": False,
                    },
                }
                self.reset_history = []

            def get_resetable_categories(self):
                """Get list of categories that can be reset."""
                return list(self.default_values.keys())

            def preview_reset(self, categories=None):
                """Preview what would be reset without actually doing it."""
                if categories is None:
                    categories = self.get_resetable_categories()

                preview = {}
                for category in categories:
                    if category in self.default_values:
                        preview[category] = {
                            "current": self._get_current_values(category),
                            "defaults": self.default_values[category],
                        }

                return preview

            def _get_current_values(self, category):
                """Get current values for a category."""
                if category == "processing":
                    return {
                        "fps": self.window.main_tab.fps_spinbox.value(),
                        "encoder": self.window.main_tab.encoder_combo.currentText(),
                        "enhance": self.window.main_tab.sanchez_checkbox.isChecked(),
                    }
                if category == "advanced":
                    return {
                        "threads": getattr(self.window.main_tab.max_workers_spinbox, "value", lambda: 4)(),
                    }
                # Add more categories as needed
                return {}

            def reset_to_defaults(self, categories=None, confirm=True):
                """Reset specified categories to defaults."""
                if categories is None:
                    categories = self.get_resetable_categories()

                if confirm:
                    category_text = (
                        "all preferences" if len(categories) == len(self.default_values) else ", ".join(categories)
                    )
                    result = QMessageBox.question(
                        self.window,
                        "Reset Preferences",
                        f"Are you sure you want to reset {category_text} to defaults?\nThis action cannot be undone.",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    )

                    if result != QMessageBox.StandardButton.Yes:
                        return {"success": False, "reason": "cancelled"}

                # Store current values for history
                reset_entry = {
                    "timestamp": QTimer().toString(),
                    "categories": categories,
                    "previous_values": {},
                }

                try:
                    for category in categories:
                        if category in self.default_values:
                            reset_entry["previous_values"][category] = self._get_current_values(category)
                            self._apply_category_defaults(category)

                    # Clear stored settings for reset categories
                    settings = QSettings()
                    for category in categories:
                        settings.beginGroup(category)
                        settings.remove("")  # Remove all in group
                        settings.endGroup()

                    # Add to reset history
                    self.reset_history.append(reset_entry)
                    # Keep only last 10 resets
                    self.reset_history = self.reset_history[-10:]

                    return {
                        "success": True,
                        "categories_reset": categories,
                        "reset_count": len(categories),
                    }

                except Exception as e:
                    return {
                        "success": False,
                        "reason": "error",
                        "error": str(e),
                    }

            def _apply_category_defaults(self, category) -> None:
                """Apply default values for a specific category."""
                defaults = self.default_values.get(category, {})

                if category == "processing":
                    if "fps" in defaults:
                        self.window.main_tab.fps_spinbox.setValue(defaults["fps"])
                    if "encoder" in defaults:
                        self.window.main_tab.encoder_combo.setCurrentText(defaults["encoder"])
                    if "enhance" in defaults:
                        self.window.main_tab.sanchez_checkbox.setChecked(defaults["enhance"])

                elif category == "advanced":
                    if "threads" in defaults:
                        self.window.main_tab.max_workers_spinbox.setValue(defaults["threads"])

                # Add more category implementations as needed

            def get_reset_history(self):
                """Get history of recent resets."""
                return self.reset_history.copy()

            def can_undo_last_reset(self):
                """Check if last reset can be undone."""
                return len(self.reset_history) > 0

            def undo_last_reset(self):
                """Undo the most recent reset."""
                if not self.reset_history:
                    return {"success": False, "reason": "no_history"}

                try:
                    last_reset = self.reset_history.pop()

                    # Restore previous values
                    for category, values in last_reset["previous_values"].items():
                        if category == "processing":
                            if "fps" in values:
                                self.window.main_tab.fps_spinbox.setValue(values["fps"])
                            if "encoder" in values:
                                self.window.main_tab.encoder_combo.setCurrentText(values["encoder"])
                            if "enhance" in values:
                                self.window.main_tab.sanchez_checkbox.setChecked(values["enhance"])

                    return {
                        "success": True,
                        "restored_categories": list(last_reset["previous_values"].keys()),
                    }

                except Exception as e:
                    return {
                        "success": False,
                        "reason": "error",
                        "error": str(e),
                    }

        # Test auto-save functionality
        auto_save = AutoSaveManager(window, interval_ms=1000)  # 1 second for testing

        # Connect change signals
        def fps_changed(value) -> None:
            auto_save.mark_changed("fps", 30, value)

        def encoder_changed(text) -> None:
            auto_save.mark_changed("encoder", "RIFE", text)

        window.main_tab.fps_spinbox.valueChanged.connect(fps_changed)
        window.main_tab.encoder_combo.currentTextChanged.connect(encoder_changed)

        # Test auto-save start/stop
        auto_save.start()
        mocks["timer"].start.assert_called_with(1000)

        # Test change tracking
        window.main_tab.fps_spinbox.value()
        window.main_tab.fps_spinbox.setValue(45)

        assert auto_save.unsaved_changes, "Change not detected"
        pending_changes = auto_save.get_pending_changes()
        assert "fps" in pending_changes, "FPS change not tracked"

        # Test auto-save trigger
        auto_save.auto_save()
        assert not auto_save.unsaved_changes, "Changes not cleared after save"

        # Test save statistics
        stats = auto_save.get_save_statistics()
        assert stats["total_saves"] > 0, "Save not recorded in statistics"

        # Test interval change
        auto_save.set_interval(2000)
        assert auto_save.interval_ms == 2000, "Interval not updated"

        # Test force save
        window.main_tab.fps_spinbox.setValue(60)
        auto_save.mark_changed("fps", 45, 60)
        force_result = auto_save.force_save()
        assert force_result, "Force save failed"

        auto_save.stop()
        mocks["timer"].stop.assert_called()

        # Test preferences reset functionality
        reset_mgr = PreferencesReset(window)

        # Set non-default values
        window.main_tab.fps_spinbox.setValue(60)
        window.main_tab.encoder_combo.setCurrentText("FFmpeg")
        window.main_tab.sanchez_checkbox.setChecked(True)

        # Test reset preview
        preview = reset_mgr.preview_reset(["processing"])
        assert "processing" in preview, "Preview missing processing category"
        assert "current" in preview["processing"], "Current values missing from preview"
        assert "defaults" in preview["processing"], "Default values missing from preview"

        # Test partial reset
        mocks["message_box_question"].return_value = QMessageBox.StandardButton.Yes
        reset_result = reset_mgr.reset_to_defaults(["processing"])

        assert reset_result["success"], "Reset failed"
        assert "processing" in reset_result["categories_reset"], "Processing not in reset categories"

        # Verify reset worked
        assert window.main_tab.fps_spinbox.value() == 30, "FPS not reset to default"
        assert window.main_tab.encoder_combo.currentText() == "RIFE", "Encoder not reset to default"
        assert not window.main_tab.sanchez_checkbox.isChecked(), "Enhance not reset to default"

        # Test undo reset
        assert reset_mgr.can_undo_last_reset(), "Cannot undo last reset"

        undo_result = reset_mgr.undo_last_reset()
        assert undo_result["success"], "Undo reset failed"

        # Verify undo worked (values should be back to non-defaults)
        assert window.main_tab.fps_spinbox.value() == 60, "FPS not restored after undo"
        assert window.main_tab.encoder_combo.currentText() == "FFmpeg", "Encoder not restored after undo"

        # Test reset history
        history = reset_mgr.get_reset_history()
        assert len(history) == 0, "History not empty after undo"  # Should be empty after undo

        # Test full reset (all categories)
        reset_result = reset_mgr.reset_to_defaults(confirm=False)  # Skip confirmation
        assert reset_result["success"], "Full reset failed"

        # Test reset with cancellation
        mocks["message_box_question"].return_value = QMessageBox.StandardButton.No
        cancel_result = reset_mgr.reset_to_defaults(["processing"])
        assert not cancel_result["success"], "Reset should have been cancelled"
        assert cancel_result["reason"] == "cancelled", "Wrong cancellation reason"
