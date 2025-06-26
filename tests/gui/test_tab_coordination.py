"""Tab-specific functionality and coordination tests for GOES VFI GUI."""

import pytest
from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
)

from goesvfi.gui import MainWindow


class MockModelDownloader(QThread):
    """Mock model downloader for testing."""

    progress = pyqtSignal(str, int)  # model_name, percent
    finished = pyqtSignal(str, bool, str)  # model_name, success, message

    def __init__(self, model_name, model_size_mb=100):
        super().__init__()
        self.model_name = model_name
        self.model_size_mb = model_size_mb
        self.cancelled = False

    def run(self):
        """Simulate model download."""
        for i in range(0, 101, 10):
            if self.cancelled:
                self.finished.emit(self.model_name, False, "Cancelled")
                return
            self.progress.emit(self.model_name, i)
            self.msleep(50)

        self.finished.emit(self.model_name, True, "Download complete")


class TestTabCoordination:
    """Test tab-specific functionality and inter-tab coordination."""

    @pytest.fixture
    def window(self, qtbot, mocker):
        """Create a MainWindow instance for testing."""
        # Mock heavy components
        mocker.patch("goesvfi.integrity_check.combined_tab.CombinedIntegrityAndImageryTab")
        mocker.patch("goesvfi.integrity_check.enhanced_imagery_tab.EnhancedGOESImageryTab")

        window = MainWindow(debug_mode=True)
        qtbot.addWidget(window)
        window._post_init_setup()

        return window

    def test_model_library_download_operations(self, qtbot, window, mocker):
        """Test model library download operations."""

        # Create mock model library tab
        class ModelLibraryTab:
            def __init__(self):
                self.model_list = QListWidget()
                self.download_button = QPushButton("Download")
                self.delete_button = QPushButton("Delete")
                self.progress_bars = {}
                self.available_models = {
                    "rife-v4.6": {"size": 150, "installed": False},
                    "rife-v4.13": {"size": 180, "installed": False},
                    "rife-v4.14": {"size": 200, "installed": True},
                }
                self.active_downloads = {}

            def populate_model_list(self):
                self.model_list.clear()
                for model_name, info in self.available_models.items():
                    item = QListWidgetItem(f"{model_name} ({info['size']}MB)")
                    item.setData(Qt.ItemDataRole.UserRole, model_name)
                    if info["installed"]:
                        item.setText(f"{item.text()} ✓")
                    self.model_list.addItem(item)

            def download_selected_model(self):
                current_item = self.model_list.currentItem()
                if not current_item:
                    return

                model_name = current_item.data(Qt.ItemDataRole.UserRole)
                if model_name in self.active_downloads:
                    return  # Already downloading

                # Create progress bar
                progress_bar = QProgressBar()
                self.progress_bars[model_name] = progress_bar

                # Start download
                downloader = MockModelDownloader(model_name)
                self.active_downloads[model_name] = downloader

                # Connect signals
                downloader.progress.connect(self.update_download_progress)
                downloader.finished.connect(self.handle_download_finished)

                downloader.start()

            def update_download_progress(self, model_name, percent):
                if model_name in self.progress_bars:
                    self.progress_bars[model_name].setValue(percent)

            def handle_download_finished(self, model_name, success, message):
                if success:
                    self.available_models[model_name]["installed"] = True
                    self.populate_model_list()

                # Clean up
                if model_name in self.active_downloads:
                    del self.active_downloads[model_name]
                if model_name in self.progress_bars:
                    del self.progress_bars[model_name]

        # Create and test model library
        model_tab = ModelLibraryTab()
        model_tab.populate_model_list()

        # Select model to download
        assert model_tab.model_list.count() == 3
        model_tab.model_list.setCurrentRow(0)  # Select rife-v4.6

        # Start download
        model_tab.download_selected_model()
        assert "rife-v4.6" in model_tab.active_downloads

        # Wait for download to complete
        qtbot.wait(600)

        # Verify model was marked as installed
        assert model_tab.available_models["rife-v4.6"]["installed"]
        assert "rife-v4.6" not in model_tab.active_downloads

    def test_model_library_delete_operations(self, qtbot, window, mocker):
        """Test model library delete operations."""
        # Mock confirmation dialog
        mock_question = mocker.patch("PyQt6.QtWidgets.QMessageBox.question")
        mock_question.return_value = QMessageBox.StandardButton.Yes

        # Model manager
        class ModelManager:
            def __init__(self):
                self.installed_models = {
                    "rife-v4.6": "/models/rife-v4.6",
                    "rife-v4.13": "/models/rife-v4.13",
                }

            def delete_model(self, model_name):
                if model_name in self.installed_models:
                    # Confirm deletion
                    result = QMessageBox.question(
                        None,
                        "Confirm Deletion",
                        f"Are you sure you want to delete {model_name}?\n" f"This action cannot be undone.",
                    )

                    if result == QMessageBox.StandardButton.Yes:
                        # Mock file deletion
                        del self.installed_models[model_name]
                        return True
                return False

            def get_model_size(self, model_name):
                # Mock model sizes
                sizes = {
                    "rife-v4.6": 150 * 1024 * 1024,
                    "rife-v4.13": 180 * 1024 * 1024,
                }
                return sizes.get(model_name, 0)

        # Test deletion
        manager = ModelManager()
        initial_count = len(manager.installed_models)

        # Delete a model
        success = manager.delete_model("rife-v4.6")
        assert success
        assert len(manager.installed_models) == initial_count - 1
        assert "rife-v4.6" not in manager.installed_models

        # Verify confirmation was shown
        mock_question.assert_called_once()
        args = mock_question.call_args[0]
        assert "Confirm Deletion" in args[1]
        assert "rife-v4.6" in args[2]

    def test_integrity_check_scan_workflow(self, qtbot, window, mocker):
        """Test integrity check scan workflow."""

        # Create integrity check scanner
        class IntegrityScanner(QObject):
            scan_progress = pyqtSignal(int, str)
            scan_complete = pyqtSignal(dict)

            def __init__(self):
                super().__init__()
                self.is_scanning = False
                self.scan_results = {}

            def start_scan(self, directory):
                self.is_scanning = True
                self.scan_results = {
                    "total_files": 0,
                    "corrupted_files": [],
                    "missing_files": [],
                    "valid_files": [],
                }

                # Simulate scan
                QTimer.singleShot(100, lambda: self._perform_scan(directory))

            def _perform_scan(self, directory):
                # Mock scanning files
                test_files = [
                    ("file1.nc", "valid"),
                    ("file2.nc", "corrupted"),
                    ("file3.nc", "valid"),
                    ("file4.nc", "missing"),
                ]

                total = len(test_files)
                for i, (filename, status) in enumerate(test_files):
                    if not self.is_scanning:
                        break

                    progress = int((i + 1) / total * 100)
                    self.scan_progress.emit(progress, f"Scanning {filename}")

                    self.scan_results["total_files"] += 1
                    if status == "valid":
                        self.scan_results["valid_files"].append(filename)
                    elif status == "corrupted":
                        self.scan_results["corrupted_files"].append(filename)
                    elif status == "missing":
                        self.scan_results["missing_files"].append(filename)

                    QTimer.singleShot(50, lambda: None)  # Small delay

                self.is_scanning = False
                self.scan_complete.emit(self.scan_results)

        # Create scanner and UI
        scanner = IntegrityScanner()
        progress_label = QLabel("Ready to scan")
        QPushButton("Start Scan")
        results_tree = QTreeWidget()
        results_tree.setHeaderLabels(["Status", "Count", "Files"])

        # Track progress
        progress_updates = []

        def on_progress(percent, message):
            progress_updates.append((percent, message))
            progress_label.setText(message)

        def on_complete(results):
            # Populate results tree
            results_tree.clear()

            valid_item = QTreeWidgetItem(["Valid", str(len(results["valid_files"]))])
            for filename in results["valid_files"]:
                valid_item.addChild(QTreeWidgetItem([filename]))

            corrupted_item = QTreeWidgetItem(["Corrupted", str(len(results["corrupted_files"]))])
            for filename in results["corrupted_files"]:
                corrupted_item.addChild(QTreeWidgetItem([filename]))

            missing_item = QTreeWidgetItem(["Missing", str(len(results["missing_files"]))])
            for filename in results["missing_files"]:
                missing_item.addChild(QTreeWidgetItem([filename]))

            results_tree.addTopLevelItems([valid_item, corrupted_item, missing_item])

        # Connect signals
        scanner.scan_progress.connect(on_progress)
        scanner.scan_complete.connect(on_complete)

        # Start scan
        scanner.start_scan("/test/data")

        # Wait for completion
        qtbot.wait(500)

        # Verify scan completed
        assert not scanner.is_scanning
        assert len(progress_updates) > 0
        assert results_tree.topLevelItemCount() == 3

        # Check results
        corrupted_item = results_tree.topLevelItem(1)
        assert corrupted_item.text(0) == "Corrupted"
        assert corrupted_item.text(1) == "1"
        assert corrupted_item.childCount() == 1

    def test_integrity_check_repair_actions(self, qtbot, window, mocker):
        """Test integrity check repair actions."""

        # Mock repair operations
        class RepairManager:
            def __init__(self):
                self.repair_queue = []
                self.repair_results = {}

            def queue_repair(self, file_info):
                self.repair_queue.append(file_info)

            def repair_corrupted_file(self, filepath):
                # Simulate repair attempt
                success = filepath != "unrepairable.nc"

                if success:
                    self.repair_results[filepath] = "Repaired successfully"
                    return True
                else:
                    self.repair_results[filepath] = "Repair failed - file too damaged"
                    return False

            def download_missing_file(self, filename, source_url):
                # Simulate download
                self.repair_results[filename] = f"Downloaded from {source_url}"
                return True

            def process_repair_queue(self, progress_callback):
                total = len(self.repair_queue)
                for i, file_info in enumerate(self.repair_queue):
                    progress = int((i + 1) / total * 100)
                    progress_callback(progress, f"Repairing {file_info['name']}")

                    if file_info["type"] == "corrupted":
                        self.repair_corrupted_file(file_info["path"])
                    elif file_info["type"] == "missing":
                        self.download_missing_file(file_info["name"], file_info["url"])

                self.repair_queue.clear()

        # Test repair workflow
        repair_mgr = RepairManager()

        # Add files to repair
        repair_mgr.queue_repair({"name": "corrupted.nc", "path": "/data/corrupted.nc", "type": "corrupted"})
        repair_mgr.queue_repair(
            {
                "name": "missing.nc",
                "path": "/data/missing.nc",
                "type": "missing",
                "url": "http://example.com/missing.nc",
            }
        )
        repair_mgr.queue_repair({"name": "unrepairable.nc", "path": "unrepairable.nc", "type": "corrupted"})

        # Process repairs
        repair_progress = []
        repair_mgr.process_repair_queue(lambda p, m: repair_progress.append((p, m)))

        # Verify results
        assert len(repair_mgr.repair_results) == 3
        assert "Repaired successfully" in repair_mgr.repair_results["/data/corrupted.nc"]
        assert "Downloaded from" in repair_mgr.repair_results["missing.nc"]
        assert "Repair failed" in repair_mgr.repair_results["unrepairable.nc"]

    def test_advanced_settings_validation(self, qtbot, window):
        """Test advanced settings validation."""

        # Create advanced settings validator
        class SettingsValidator:
            def __init__(self):
                self.validation_rules = {
                    "thread_count": (1, 32, int),
                    "tile_size": (128, 1024, int),
                    "memory_limit": (0.1, 0.9, float),  # Percentage
                    "cache_size": (100, 10000, int),  # MB
                    "network_timeout": (5, 300, int),  # seconds
                }

            def validate_setting(self, name, value):
                if name not in self.validation_rules:
                    return True, value

                min_val, max_val, type_func = self.validation_rules[name]

                try:
                    typed_value = type_func(value)
                    if min_val <= typed_value <= max_val:
                        return True, typed_value
                    else:
                        return False, f"Value must be between {min_val} and {max_val}"
                except (ValueError, TypeError):
                    return False, f"Invalid {type_func.__name__} value"

            def validate_all_settings(self, settings_dict):
                errors = []
                validated = {}

                for name, value in settings_dict.items():
                    valid, result = self.validate_setting(name, value)
                    if valid:
                        validated[name] = result
                    else:
                        errors.append(f"{name}: {result}")

                return validated, errors

        # Test validation
        validator = SettingsValidator()

        test_settings = {
            "thread_count": "8",
            "tile_size": "256",
            "memory_limit": "0.5",
            "cache_size": "50",  # Too small
            "network_timeout": "1000",  # Too large
        }

        validated, errors = validator.validate_all_settings(test_settings)

        # Check valid settings
        assert validated["thread_count"] == 8
        assert validated["tile_size"] == 256
        assert validated["memory_limit"] == 0.5

        # Check errors
        assert len(errors) == 2
        assert any("cache_size" in err for err in errors)
        assert any("network_timeout" in err for err in errors)

    def test_inter_tab_state_synchronization(self, qtbot, window):
        """Test state synchronization between tabs."""

        # Create state synchronizer
        class TabStateSynchronizer(QObject):
            state_changed = pyqtSignal(str, object)  # key, value

            def __init__(self):
                super().__init__()
                self.shared_state = {}
                self.tab_subscriptions = {}

            def register_tab(self, tab_name, keys_of_interest):
                self.tab_subscriptions[tab_name] = keys_of_interest

            def update_state(self, key, value):
                old_value = self.shared_state.get(key)
                if old_value != value:
                    self.shared_state[key] = value
                    self.state_changed.emit(key, value)

            def get_state(self, key, default=None):
                return self.shared_state.get(key, default)

            def sync_to_tab(self, tab_name, update_func):
                if tab_name in self.tab_subscriptions:
                    for key in self.tab_subscriptions[tab_name]:
                        if key in self.shared_state:
                            update_func(key, self.shared_state[key])

        # Create synchronizer
        sync = TabStateSynchronizer()

        # Register tabs
        sync.register_tab("main", ["input_dir", "output_file", "processing"])
        sync.register_tab("settings", ["encoder", "fps", "quality"])
        sync.register_tab("models", ["current_model", "available_models"])

        # Track state changes
        state_changes = []
        sync.state_changed.connect(lambda k, v: state_changes.append((k, v)))

        # Update states
        sync.update_state("input_dir", "/test/input")
        sync.update_state("encoder", "RIFE")
        sync.update_state("current_model", "rife-v4.6")

        # Verify state changes were emitted
        assert len(state_changes) == 3
        assert ("input_dir", "/test/input") in state_changes
        assert ("encoder", "RIFE") in state_changes

        # Test tab synchronization
        main_tab_state = {}
        sync.sync_to_tab("main", lambda k, v: main_tab_state.update({k: v}))

        assert main_tab_state["input_dir"] == "/test/input"
        assert "encoder" not in main_tab_state  # Not subscribed

    def test_dynamic_tab_management(self, qtbot, window):
        """Test dynamic tab creation and removal."""

        # Tab manager
        class DynamicTabManager:
            def __init__(self, tab_widget):
                self.tab_widget = tab_widget
                self.dynamic_tabs = {}

            def add_custom_tab(self, widget, title, closable=True):
                index = self.tab_widget.addTab(widget, title)

                if closable:
                    # Add close button
                    close_button = QPushButton("×")
                    close_button.setMaximumSize(20, 20)
                    close_button.clicked.connect(lambda: self.remove_tab(index))
                    self.tab_widget.tabBar().setTabButton(
                        index,
                        self.tab_widget.tabBar().ButtonPosition.RightSide,
                        close_button,
                    )

                self.dynamic_tabs[title] = {
                    "widget": widget,
                    "index": index,
                    "closable": closable,
                }

                return index

            def remove_tab(self, index):
                # Find tab by index
                for title, info in list(self.dynamic_tabs.items()):
                    if info["index"] == index:
                        self.tab_widget.removeTab(index)
                        del self.dynamic_tabs[title]

                        # Update indices
                        for other_title, other_info in self.dynamic_tabs.items():
                            if other_info["index"] > index:
                                other_info["index"] -= 1
                        break

            def get_tab(self, title):
                return self.dynamic_tabs.get(title)

        # Test dynamic tabs
        tab_mgr = DynamicTabManager(window.tab_widget)

        # Add dynamic tab
        custom_widget = QListWidget()
        custom_widget.addItem("Custom content")

        index = tab_mgr.add_custom_tab(custom_widget, "Analysis Results")
        assert "Analysis Results" in tab_mgr.dynamic_tabs
        assert window.tab_widget.count() > index

        # Add another tab
        log_widget = QListWidget()
        log_widget.addItem("Log entry 1")

        log_index = tab_mgr.add_custom_tab(log_widget, "Process Log", closable=False)
        assert "Process Log" in tab_mgr.dynamic_tabs

        # Remove first tab
        tab_mgr.remove_tab(index)
        assert "Analysis Results" not in tab_mgr.dynamic_tabs
        assert "Process Log" in tab_mgr.dynamic_tabs

        # Verify index was updated
        assert tab_mgr.dynamic_tabs["Process Log"]["index"] < log_index

    def test_tab_specific_shortcuts(self, qtbot, window):
        """Test tab-specific keyboard shortcuts."""

        # Shortcut manager
        class TabShortcutManager:
            def __init__(self):
                self.shortcuts = {}
                self.active_tab = None

            def register_shortcut(self, tab_name, key_sequence, action):
                if tab_name not in self.shortcuts:
                    self.shortcuts[tab_name] = {}
                self.shortcuts[tab_name][key_sequence] = action

            def set_active_tab(self, tab_name):
                self.active_tab = tab_name

            def handle_shortcut(self, key_sequence):
                if self.active_tab and self.active_tab in self.shortcuts:
                    if key_sequence in self.shortcuts[self.active_tab]:
                        action = self.shortcuts[self.active_tab][key_sequence]
                        action()
                        return True

                # Check global shortcuts
                if "global" in self.shortcuts and key_sequence in self.shortcuts["global"]:
                    self.shortcuts["global"][key_sequence]()
                    return True

                return False

        # Create manager
        shortcut_mgr = TabShortcutManager()

        # Track actions
        actions_triggered = []

        # Register shortcuts
        shortcut_mgr.register_shortcut("main", "Ctrl+R", lambda: actions_triggered.append("refresh_main"))
        shortcut_mgr.register_shortcut("models", "Ctrl+D", lambda: actions_triggered.append("download_model"))
        shortcut_mgr.register_shortcut("global", "F1", lambda: actions_triggered.append("show_help"))

        # Test tab-specific shortcut
        shortcut_mgr.set_active_tab("main")
        assert shortcut_mgr.handle_shortcut("Ctrl+R")
        assert "refresh_main" in actions_triggered

        # Test shortcut from different tab (should not work)
        assert not shortcut_mgr.handle_shortcut("Ctrl+D")
        assert "download_model" not in actions_triggered

        # Switch tab and test
        shortcut_mgr.set_active_tab("models")
        assert shortcut_mgr.handle_shortcut("Ctrl+D")
        assert "download_model" in actions_triggered

        # Test global shortcut (works from any tab)
        assert shortcut_mgr.handle_shortcut("F1")
        assert "show_help" in actions_triggered
