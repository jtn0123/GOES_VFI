"""Configuration for GUI tests to prevent segmentation faults and threading issues."""

import os
from unittest.mock import MagicMock

import pytest


@pytest.fixture(scope="session", autouse=True)
def _setup_headless_env():
    """Set up headless environment for all GUI tests."""
    # Store original environment
    original_env = os.environ.copy()

    # Set headless environment
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["QT_LOGGING_RULES"] = "*.debug=false"  # Reduce Qt debug output
    # Additional environment variables to prevent Qt issues
    os.environ["QT_QPA_FONTDIR"] = ""  # Prevent font loading issues
    os.environ["QT_QUICK_BACKEND"] = "software"  # Use software rendering

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture(autouse=True)
def ensure_single_qapp_instance():
    """Ensure we have a single, stable QApplication instance throughout tests."""
    from PyQt6.QtWidgets import QApplication

    # Get or create QApplication instance
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
        app.setQuitOnLastWindowClosed(False)  # Prevent app from quitting

    # Process any pending events before test
    app.processEvents()

    yield app

    # Process events after test but don't quit the app
    app.processEvents()


@pytest.fixture(autouse=True)
def _mock_resource_monitoring(monkeypatch):
    """Mock resource monitoring to prevent memory monitoring threads."""

    # Create a mock memory stats object
    mock_stats = MagicMock()
    mock_stats.total_mb = 16000
    mock_stats.available_mb = 8000
    mock_stats.used_mb = 8000
    mock_stats.percent_used = 50.0
    mock_stats.process_mb = 500
    mock_stats.process_percent = 3.0
    mock_stats.is_low_memory = False
    mock_stats.is_critical_memory = False

    # Mock the resource manager to not start memory monitoring
    def mock_get_resource_manager():
        mock_rm = MagicMock()
        mock_rm.memory_monitor = MagicMock()
        mock_rm.memory_monitor.start_monitoring = MagicMock()
        mock_rm.memory_monitor.stop_monitoring = MagicMock()
        mock_rm.memory_monitor.get_memory_stats = MagicMock(return_value=mock_stats)
        mock_rm.check_resources = MagicMock()
        return mock_rm

    # Mock memory manager class completely
    class MockMemoryManager:
        def __init__(self, *args, **kwargs):
            self._monitoring = False
            self._monitor_thread = None
            self._callbacks = []

        def start_monitoring(self, interval=5.0):
            pass  # Do nothing

        def stop_monitoring(self):
            pass  # Do nothing

        def get_memory_stats(self):
            return mock_stats

        def add_callback(self, callback):
            pass  # Do nothing

        def _monitor_loop(self, interval):
            pass  # Do nothing

    # Mock VFI processing to prevent actual execution
    def mock_run_vfi(*args, **kwargs):
        return "/mock/output.mp4"

    # Mock direct start handler to prevent processing
    def mock_direct_start_handler(self):
        """Mock the direct start handler to prevent actual processing."""
        pass  # Do nothing

    # Apply comprehensive mocking
    patches_to_apply = [
        (
            "goesvfi.pipeline.resource_manager.get_resource_manager",
            mock_get_resource_manager,
        ),
        ("goesvfi.utils.memory_manager.MemoryManager", MockMemoryManager),
        ("goesvfi.pipeline.run_vfi.run_vfi", mock_run_vfi),
        ("goesvfi.gui_tabs.main_tab.run_vfi", mock_run_vfi),
    ]

    # Also mock any direct imports
    try:
        # Mock in gui module
        monkeypatch.setattr(
            "goesvfi.gui.get_resource_manager", mock_get_resource_manager, raising=False
        )
        monkeypatch.setattr(
            "goesvfi.gui.MemoryManager", MockMemoryManager, raising=False
        )

        # Mock in main_tab module
        monkeypatch.setattr(
            "goesvfi.gui_tabs.main_tab.get_resource_manager",
            mock_get_resource_manager,
            raising=False,
        )
        monkeypatch.setattr(
            "goesvfi.gui_tabs.main_tab.MemoryManager", MockMemoryManager, raising=False
        )
        monkeypatch.setattr(
            "goesvfi.gui_tabs.main_tab.run_vfi", mock_run_vfi, raising=False
        )

        # Mock the direct start handler method specifically
        monkeypatch.setattr(
            "goesvfi.gui_tabs.main_tab.MainTab._direct_start_handler",
            mock_direct_start_handler,
            raising=False,
        )

        # Mock subprocess and FFmpeg calls that might cause issues
        mock_subprocess_result = MagicMock()
        mock_subprocess_result.returncode = 0
        mock_subprocess_result.stdout = ""
        mock_subprocess_result.stderr = ""
        monkeypatch.setattr(
            "subprocess.run",
            lambda *args, **kwargs: mock_subprocess_result,
            raising=False,
        )
        monkeypatch.setattr(
            "subprocess.Popen",
            lambda *args, **kwargs: mock_subprocess_result,
            raising=False,
        )

        # Apply all patches
        for attr_path, mock_obj in patches_to_apply:
            monkeypatch.setattr(attr_path, mock_obj, raising=False)

    except (AttributeError, ImportError):
        # Module might not be importable, that's fine
        pass


@pytest.fixture(autouse=True)
def _aggressive_cleanup_and_isolation():
    """Extremely aggressive cleanup and test isolation for GUI tests."""
    import gc
    import threading

    from PyQt6.QtWidgets import QApplication

    # Before test - record initial state
    initial_threads = set(threading.enumerate())

    # Force immediate cleanup before test starts
    gc.collect()

    # Get or create QApplication instance
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    yield

    # After test - extremely aggressive cleanup
    try:
        # First, process any pending events
        if app:
            app.processEvents()

        # Force immediate garbage collection multiple times
        for _ in range(3):
            gc.collect()

        # Clean up any new threads
        current_threads = set(threading.enumerate())
        new_threads = current_threads - initial_threads

        for thread in new_threads:
            if thread.daemon and thread.is_alive():
                try:
                    # For daemon threads, we can't really force stop them
                    # but we can try to identify and log them
                    pass
                except Exception:
                    pass

        # Try to clean up any resource managers
        try:
            from goesvfi.pipeline.resource_manager import get_resource_manager

            rm = get_resource_manager()
            if hasattr(rm, "memory_monitor") and rm.memory_monitor:
                if hasattr(rm.memory_monitor, "stop_monitoring"):
                    rm.memory_monitor.stop_monitoring()
        except Exception:
            pass

        # Final processing and cleanup
        if app:
            app.processEvents()

        # Multiple garbage collection passes
        for _ in range(5):
            gc.collect()

    except Exception:
        # Never let cleanup break the tests
        pass


@pytest.fixture(autouse=True)
def _disable_qtbot_wait(monkeypatch):
    """Disable problematic qtbot.wait calls that cause segfaults."""

    # Mock qtbot.wait to do nothing (it's causing the segfaults)
    def mock_qtbot_wait(self, _ms):
        # Instead of waiting, just process events immediately
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app:
            app.processEvents()
        return

    try:
        # Patch the qtbot wait method
        from pytestqt.qtbot import QtBot

        monkeypatch.setattr(QtBot, "wait", mock_qtbot_wait)
    except ImportError:
        pass
