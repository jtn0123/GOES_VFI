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
def _no_gui_dialogs(monkeypatch):
    """Automatically prevent all GUI dialogs in integration tests."""
    # Mock all file dialogs to return empty/cancel
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QFileDialog.getOpenFileName", lambda *args, **kwargs: ("", "")
    )
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QFileDialog.getOpenFileNames", lambda *args, **kwargs: ([], "")
    )
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
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QMessageBox.exec", lambda self: QMessageBox.StandardButton.Ok
    )

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
