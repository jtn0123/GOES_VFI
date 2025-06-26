"""Configuration for integration tests to prevent GUI pop-ups."""

import os
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QMessageBox


@pytest.fixture(scope="session", autouse=True)
def _setup_headless_env():
    """Set up headless environment for all integration tests."""
    # Store original environment
    original_env = os.environ.copy()

    # Set headless environment
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["QT_LOGGING_RULES"] = "*.debug=false"  # Reduce Qt debug output

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture(autouse=True)
def _mock_resource_monitoring(monkeypatch):
    """Mock resource monitoring to prevent memory monitoring threads."""

    # Create a mock memory stats object
    from unittest.mock import MagicMock

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

    # Apply comprehensive mocking
    patches_to_apply = [
        (
            "goesvfi.pipeline.resource_manager.get_resource_manager",
            mock_get_resource_manager,
        ),
        ("goesvfi.utils.memory_manager.MemoryManager", MockMemoryManager),
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

        # Apply all patches
        for attr_path, mock_obj in patches_to_apply:
            monkeypatch.setattr(attr_path, mock_obj, raising=False)

    except (AttributeError, ImportError):
        # Module might not be importable, that's fine
        pass


@pytest.fixture(autouse=True)
def _no_gui_dialogs(monkeypatch):
    """Automatically prevent all GUI dialogs in integration tests."""
    # Mock all file dialogs to return empty/cancel
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QFileDialog.getOpenFileName", lambda *args, **kwargs: ("", "")
    )
    # Note: getOpenFileNames doesn't exist in PyQt6, only getOpenFileNames is valid
    # But we'll mock it just in case some code expects it
    try:
        monkeypatch.setattr(
            "PyQt6.QtWidgets.QFileDialog.getOpenFileNames",
            lambda *args, **kwargs: ([], ""),
        )
    except AttributeError:
        # Method doesn't exist, that's fine
        pass
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QFileDialog.getSaveFileName", lambda *args, **kwargs: ("", "")
    )
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QFileDialog.getExistingDirectory", lambda *args, **kwargs: ""
    )

    # Mock all message boxes
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QMessageBox.critical",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QMessageBox.warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QMessageBox.information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    # QMessageBox exec method handling
    try:
        monkeypatch.setattr(
            "PyQt6.QtWidgets.QMessageBox.exec",
            lambda self: QMessageBox.StandardButton.Ok,
        )
    except AttributeError:
        # Method doesn't exist, that's fine
        pass

    # Mock color dialog
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QColorDialog.getColor",
        lambda *args, **kwargs: MagicMock(isValid=lambda: False),
    )

    # Mock font dialog
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QFontDialog.getFont",
        lambda *args, **kwargs: (False, MagicMock()),
    )

    # Mock input dialog
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QInputDialog.getText", lambda *args, **kwargs: ("", False)
    )
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QInputDialog.getInt", lambda *args, **kwargs: (0, False)
    )
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QInputDialog.getDouble", lambda *args, **kwargs: (0.0, False)
    )
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QInputDialog.getItem", lambda *args, **kwargs: ("", False)
    )


@pytest.fixture
def mock_vfi_processing():
    """Mock the actual VFI processing to prevent real computation."""
    with (
        patch("goesvfi.pipeline.run_vfi.run_vfi") as mock_run_vfi,
        patch("goesvfi.pipeline.run_vfi.find_rife_executable") as mock_find_rife,
        patch("subprocess.run") as mock_subprocess_run,
        patch("subprocess.Popen") as mock_subprocess_popen,
    ):

        # Mock RIFE executable exists
        mock_find_rife.return_value = "/mock/rife"

        # Mock subprocess calls succeed
        mock_subprocess_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.wait.return_value = 0
        mock_process.communicate.return_value = (b"", b"")
        mock_subprocess_popen.return_value = mock_process

        # Mock run_vfi to return success
        mock_run_vfi.return_value = "/mock/output.mp4"

        yield {
            "run_vfi": mock_run_vfi,
            "find_rife": mock_find_rife,
            "subprocess_run": mock_subprocess_run,
            "subprocess_popen": mock_subprocess_popen,
        }


@pytest.fixture
def _mock_long_operations(monkeypatch):
    """Mock long-running operations to speed up tests."""
    # Mock sleep to be instant
    monkeypatch.setattr("time.sleep", lambda x: None)

    # Mock process pool executor to run synchronously
    def mock_executor(*args, **kwargs):
        executor = MagicMock()
        executor.__enter__ = lambda self: self
        executor.__exit__ = lambda self, *args: None
        executor.map = lambda func, items: [func(item) for item in items]
        executor.submit = lambda func, *args: MagicMock(result=lambda: func(*args))
        return executor

    monkeypatch.setattr("concurrent.futures.ProcessPoolExecutor", mock_executor)
    monkeypatch.setattr("concurrent.futures.ThreadPoolExecutor", mock_executor)


@pytest.fixture(autouse=True)
def _cleanup_threads_and_memory():
    """Aggressively clean up threads and memory monitoring after each test."""
    import gc
    import threading

    # Before test - record initial thread count
    initial_threads = set(threading.enumerate())

    yield

    # After test - aggressive cleanup
    try:
        # Force garbage collection
        gc.collect()

        # Get all current threads
        current_threads = set(threading.enumerate())
        new_threads = current_threads - initial_threads

        # Try to stop any new daemon threads that might be monitoring threads
        for thread in new_threads:
            if thread.daemon and thread.is_alive():
                getattr(thread, "name", "Unknown")
                target_func = getattr(thread, "_target", None)
                if target_func:
                    target_name = getattr(target_func, "__name__", str(target_func))
                    if (
                        "_monitor_loop" in target_name
                        or "memory" in target_name.lower()
                    ):
                        # This looks like a memory monitoring thread
                        try:
                            # Try to stop the monitoring by setting a flag
                            if hasattr(thread, "_args") and thread._args:
                                # The thread might have a reference to the MemoryManager instance
                                pass
                        except Exception:
                            pass

        # Try to import and force stop any active memory managers
        try:
            from goesvfi.pipeline.resource_manager import get_resource_manager

            rm = get_resource_manager()
            if hasattr(rm, "memory_monitor") and rm.memory_monitor:
                if hasattr(rm.memory_monitor, "stop_monitoring"):
                    rm.memory_monitor.stop_monitoring()
        except Exception:
            pass

        try:
            # Also look for any MemoryManager instances in globals that might still be running
            import sys

            for module_name, module in sys.modules.items():
                if "memory_manager" in module_name.lower() and hasattr(
                    module, "MemoryManager"
                ):
                    # This module has MemoryManager, see if there are any instances
                    pass
        except Exception:
            pass

        # Final garbage collection
        gc.collect()

    except Exception:
        # Don't let cleanup errors break tests
        pass
