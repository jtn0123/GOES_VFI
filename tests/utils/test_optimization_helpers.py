"""Test optimization helpers to speed up slow tests while maintaining coverage."""

from contextlib import contextmanager
import time
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication


class FastQtTestHelper:
    """Helper for fast Qt testing without real window rendering."""

    @staticmethod
    def mock_main_window(mocker):
        """Create a lightweight mock of MainWindow."""
        mock_window = MagicMock()
        mock_window.isVisible.return_value = True
        mock_window.width.return_value = 800
        mock_window.height.return_value = 600

        # Mock all tabs
        for tab_name in ["main_tab", "enhanced_tab", "file_sorter_tab", "timeline_tab"]:
            setattr(mock_window, tab_name, MagicMock())

        # Mock heavy initialization
        mocker.patch("goesvfi.gui.MainWindow._post_init_setup")
        mocker.patch("goesvfi.gui.MainWindow._setup_ui")
        mocker.patch("goesvfi.gui.MainWindow._connect_signals")

        return mock_window

    @staticmethod
    def fast_qtbot_wait(qtbot, milliseconds) -> None:
        """Replace qtbot.wait with a faster alternative for tests."""
        # Instead of real waiting, just process events
        for _ in range(min(5, milliseconds // 10)):
            QApplication.processEvents()

    @staticmethod
    @contextmanager
    def mock_heavy_operations(mocker):
        """Mock all heavy operations in one go."""
        # Mock file operations
        mocker.patch("pathlib.Path.exists", return_value=True)
        mocker.patch("pathlib.Path.stat")
        mocker.patch("os.listdir", return_value=[])

        # Mock QSettings to use in-memory storage
        mock_settings = MagicMock()
        mock_settings._storage = {}
        mock_settings.value.side_effect = lambda k, d=None: mock_settings._storage.get(k, d)
        mock_settings.setValue.side_effect = lambda k, v: mock_settings._storage.update({k: v})
        mocker.patch("PyQt6.QtCore.QSettings", return_value=mock_settings)

        # Mock network operations
        mocker.patch("boto3.client")
        mocker.patch("aiohttp.ClientSession")
        mocker.patch("requests.get")

        yield mock_settings


class FastTestTimer:
    """Replace QTimer with instant execution for tests."""

    def __init__(self) -> None:
        self.callbacks = []

    def timeout(self):
        """Fake timeout signal."""

        class FakeSignal:
            def __init__(self, timer) -> None:
                self.timer = timer

            def connect(self, callback) -> None:
                self.timer.callbacks.append(callback)

        return FakeSignal(self)

    def start(self, interval=None) -> None:
        """Execute callbacks immediately instead of waiting."""
        for callback in self.callbacks:
            callback()

    def stop(self) -> None:
        """No-op for tests."""

    def isActive(self) -> bool:
        """Always return False."""
        return False


def optimize_test_performance(func):
    """Decorator to automatically optimize common slow patterns."""

    def wrapper(*args, **kwargs):
        # Patch common slow operations
        with patch("time.sleep", lambda x: None):  # No sleeping in tests
            with patch("PyQt6.QtCore.QTimer", FastTestTimer):  # Instant timers
                with patch("PyQt6.QtWidgets.QApplication.processEvents", lambda: None):  # No event processing
                    return func(*args, **kwargs)

    return wrapper


class MockedSettingsPersistence:
    """Fast mock for SettingsPersistence that avoids file I/O."""

    def __init__(self) -> None:
        self.storage = {}

    def save_input_directory(self, path) -> bool:
        """Mock save operation."""
        if path is None:
            return False
        self.storage["input_dir"] = str(path)
        return True

    def save_crop_rect(self, rect) -> bool:
        """Mock save operation."""
        if rect is None:
            return False
        self.storage["crop_rect"] = rect
        return True

    def load_input_directory(self):
        """Mock load operation."""
        return self.storage.get("input_dir")

    def load_crop_rect(self):
        """Mock load operation."""
        return self.storage.get("crop_rect")


def assert_mock_called_with_retry(mock_obj, *args, retries=3, delay=0.01) -> None:
    """Assert mock was called with args, with retries for async operations."""
    for i in range(retries):
        try:
            mock_obj.assert_called_with(*args)
            return
        except AssertionError:
            if i < retries - 1:
                time.sleep(delay)
                QApplication.processEvents()
            else:
                raise


def create_fast_mock_s3_client():
    """Create a properly configured mock S3 client."""
    mock_client = MagicMock()
    mock_client.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "test-file-1.nc", "Size": 1024},
            {"Key": "test-file-2.nc", "Size": 2048},
        ]
    }
    mock_client.head_object.return_value = {"ContentLength": 1024}
    mock_client.download_file.return_value = None
    return mock_client
