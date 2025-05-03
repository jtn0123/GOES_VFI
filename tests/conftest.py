"""
Configuration file for pytest.

This file defines shared fixtures, hooks, and plugins for the test suite.
Fixtures defined here are automatically available to all tests.
"""

import pytest
import tempfile
import pathlib
import shutil
import sys


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


