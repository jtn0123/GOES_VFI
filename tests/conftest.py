"""
Configuration file for pytest.

This file defines shared fixtures, hooks, and plugins for the test suite.
Fixtures defined here are automatically available to all tests.
"""

import pathlib
import sys
import tempfile

import pytest

# More robust solution to prevent pytest-qt segmentation faults


@pytest.fixture(scope="function")
def temp_dir():
    """
    Pytest fixture to create a temporary directory for a test function.

    Yields:
        pathlib.Path: The path to the created temporary directory.

    The directory and its contents are automatically removed after the test finishes.
    """
    with tempfile.TemporaryDirectory(prefix="goesvfi_test_") as tmpdir:
        yield pathlib.Path(tmpdir)
    # Cleanup is handled by TemporaryDirectory context manager


@pytest.fixture(scope="session")
def project_root():
    """
    Pytest fixture to get the root directory of the project.

    Returns:
        pathlib.Path: The project root directory.
    """
    # Assumes conftest.py is in the 'tests' directory, one level below the root
    return pathlib.Path(__file__).parent.parent


# Add more shared fixtures here as needed, e.g., for sample data,
# mocked objects, or application instances.


def pytest_configure(config):
    """Configure pytest with Qt-specific settings."""
    # Set Qt to use a specific font to avoid "Sans Serif" search delay
    import os

    # This environment variable tells Qt to use a specific font
    if sys.platform == "darwin":  # macOS
        os.environ.setdefault("QT_QPA_FONTDIR", "/System/Library/Fonts")
        os.environ.setdefault("QT_QPA_PLATFORMTHEME", "cocoa")


# Hook into pytest-qt's qapp fixture
@pytest.fixture(scope="session")
def qapp_args():
    """Arguments to pass to QApplication constructor."""
    return []


@pytest.fixture(scope="session")
def qapp(qapp_args, pytestconfig):  # noqa: ARG001  # vulture: ignore
    """Create the QApplication instance with custom font settings."""
    from PyQt6.QtWidgets import QApplication

    # Create or get existing app
    app = QApplication.instance()
    if app is None:
        app = QApplication(qapp_args)

    # Set default font to avoid "Sans Serif" search delay
    if isinstance(app, QApplication):
        default_font = app.font()
    if sys.platform == "darwin":
        default_font.setFamily("Helvetica")
    elif sys.platform == "win32":
        default_font.setFamily("Segoe UI")
    else:
        default_font.setFamily("DejaVu Sans")
        app.setFont(default_font)

    yield app

    # Cleanup handled by pytest-qt
