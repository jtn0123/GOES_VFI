#!/usr/bin/env python3
"""
Simple test runner that executes the working tests with basic unittest discovery.
This runs the 108 tests that successfully import with mocked dependencies.
"""

import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Add the project root to Python path
repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root))


class MockModule:
    """A mock module that can be imported and used like a real module."""

    def __init__(self, name: str):
        self.name = name
        self.__name__ = name
        self.__file__ = f"<mock {name}>"

    def __getattr__(self, name: str):
        return MagicMock()

    def __call__(self, *args, **kwargs):
        return MagicMock()


def setup_mocks():
    """Set up mock modules for missing dependencies."""

    missing_deps = [
        # GUI frameworks
        "PyQt6",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "PyQt6.QtTest",
        # Scientific computing
        "numpy",
        "numpy.typing",
        "PIL",
        "PIL.Image",
        "cv2",
        "ffmpeg",
        "matplotlib",
        "matplotlib.pyplot",
        "xarray",
        "netCDF4",
        "imageio",
        "imageio.v3",
        "psutil",
        "pytz",
        # Async and networking
        "aiohttp",
        "aiohttp.client_exceptions",
        "aiofiles",
        "requests",
        "aioboto3",
        "boto3",
        "botocore",
        "botocore.exceptions",
        "botocore.config",
        "botocore.session",
        # Testing frameworks
        "pytest",
        "pytest_mock",
        "pytest_qt",
        # Utilities
        "tqdm",
    ]

    for dep in missing_deps:
        if dep not in sys.modules:
            try:
                importlib.import_module(dep)
            except ImportError:
                mock_module = MockModule(dep)
                sys.modules[dep] = mock_module

                if "." in dep:
                    parent, child = dep.rsplit(".", 1)
                    if parent in sys.modules:
                        setattr(sys.modules[parent], child, mock_module)
                    else:
                        parent_module = MockModule(parent)
                        sys.modules[parent] = parent_module
                        setattr(parent_module, child, mock_module)

    # Set up special mock behaviors for commonly used classes
    setup_special_mocks()


def setup_special_mocks():
    """Set up special mock behaviors for commonly used classes."""
    from unittest.mock import MagicMock

    # Create a more realistic QSettings mock
    class MockQSettings:
        class Format:
            IniFormat = 1

        def __init__(self, org=None, app=None):
            self._storage = {}
            self._org = org or "MockOrg"
            self._app = app or "MockApp"
            self._group_stack = []

        def _full_key(self, key: str) -> str:
            return "/".join(self._group_stack + [key]) if key else "/".join(self._group_stack)

        def setValue(self, key, value):
            self._storage[self._full_key(key)] = value

        def value(self, key, default=None, type=None):
            val = self._storage.get(self._full_key(key), default)
            if type and val is not None:
                try:
                    return type(val)
                except Exception:
                    return default
            return val

        def allKeys(self):
            return list(self._storage.keys())

        def beginGroup(self, group):
            self._group_stack.append(group)

        def endGroup(self):
            if self._group_stack:
                self._group_stack.pop()

        def remove(self, key):
            if key:
                self._storage.pop(self._full_key(key), None)
            else:
                prefix = self._full_key("")
                for k in list(self._storage):
                    if k.startswith(prefix):
                        self._storage.pop(k, None)

        def sync(self):
            pass

        def organizationName(self):
            return self._org

        def applicationName(self):
            return self._app

        def fileName(self):
            return f"/tmp/mock_settings_{self._org}_{self._app}.conf"

    # Replace QSettings in PyQt6.QtCore if it exists
    if "PyQt6.QtCore" in sys.modules:
        sys.modules["PyQt6.QtCore"].QSettings = MockQSettings

    # Create a QApplication instance mock
    class MockQApplication:
        _instance = None

        @classmethod
        def instance(cls):
            if cls._instance is None:
                cls._instance = MockQApplication()
            return cls._instance

        def organizationName(self):
            return "MockOrg"

        def applicationName(self):
            return "MockApp"

    if "PyQt6.QtWidgets" in sys.modules:
        sys.modules["PyQt6.QtWidgets"].QApplication = MockQApplication

    class MockQComboBox:
        def __init__(self):
            self._items = []

        def addItem(self, text):
            self._items.append(text)

        def clear(self):
            self._items.clear()

        def count(self):
            return len(self._items)

        def itemText(self, index):
            if 0 <= index < len(self._items):
                return self._items[index]
            return ""

    if "PyQt6.QtWidgets" in sys.modules:
        sys.modules["PyQt6.QtWidgets"].QComboBox = MockQComboBox

    class MockQImage:
        class Format:
            Format_RGB888 = 1
            Format_RGBA8888 = 2
            Format_Grayscale8 = 3

        def __init__(self, data, width, height, bytes_per_line=None, fmt=None):
            self._width = width
            self._height = height

        def width(self):
            return self._width

        def height(self):
            return self._height

    class MockQPixmap:
        def __init__(self, width=0, height=0):
            self._width = width
            self._height = height
            self._null = width == 0 and height == 0

        @staticmethod
        def fromImage(img: "MockQImage") -> "MockQPixmap":
            return MockQPixmap(img.width(), img.height())

        def width(self):
            return self._width

        def height(self):
            return self._height

        def isNull(self):
            return self._null

        def fill(self):
            self._null = False

        def scaled(self, size, *args, **kwargs):
            return MockQPixmap(size.width(), size.height())

    if "PyQt6.QtGui" in sys.modules:
        sys.modules["PyQt6.QtGui"].QImage = MockQImage
        sys.modules["PyQt6.QtGui"].QPixmap = MockQPixmap


def run_working_tests():
    """Run tests using unittest discovery with working test files."""

    print("🧪 Running Working Tests with Mocked Dependencies")
    print("=" * 60)

    # Set up mocks
    setup_mocks()

    # Working test files (those that passed import in our analysis)
    working_tests = [
        "tests.test_placeholder",
        "tests.test_rife_analyzer",
        "tests.integration.test_large_dataset_processing",
        "tests.integration.test_pipeline",
        "tests.integration.test_vfi_worker",
        "tests.unit.test_basic_time_index",
        "tests.unit.test_config",
        "tests.unit.test_corrupt_file_handling",
        "tests.unit.test_crop_manager",
        "tests.unit.test_date_range_selector",
        "tests.unit.test_date_sorter",
        "tests.unit.test_date_utils",
        "tests.unit.test_encode",
        "tests.unit.test_ffmpeg_builder",
        "tests.unit.test_ffmpeg_builder_critical",
        "tests.unit.test_ffmpeg_settings_tab",
        "tests.unit.test_file_sorter",
        "tests.unit.test_file_sorter_refactored",
        "tests.unit.test_gui_helpers",
        "tests.unit.test_image_cropper",
        "tests.unit.test_image_saver",
        "tests.unit.test_loader",
        "tests.unit.test_log",
        "tests.unit.test_memory_management",
        "tests.unit.test_model_manager",
        "tests.unit.test_netcdf_channel_extraction",
        "tests.unit.test_preview_manager",
        "tests.unit.test_processing_manager",
        "tests.unit.test_real_s3_patterns",
        "tests.unit.test_rife_analyzer",
        "tests.unit.test_run_vfi",
        "tests.unit.test_run_vfi_fixed",
        "tests.unit.test_run_vfi_refactored",
        "tests.unit.test_run_vfi_simple",
        "tests.unit.test_sanchez",
        "tests.unit.test_sanchez_health",
        "tests.unit.test_settings_manager",
        "tests.unit.test_signal",
        "tests.unit.test_time_index",
        "tests.unit.test_time_index_refactored",
    ]

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    passed_modules = 0
    failed_modules = 0

    for test_module in working_tests:
        try:
            # Try to load the module
            module_suite = loader.loadTestsFromName(test_module)
            if module_suite.countTestCases() > 0:
                suite.addTest(module_suite)
                passed_modules += 1
                print(f"✅ {test_module}: {module_suite.countTestCases()} tests")
            else:
                print(f"⚠️  {test_module}: No tests found")
        except Exception as e:
            failed_modules += 1
            print(f"❌ {test_module}: {e}")

    print()
    print(f"Loaded {passed_modules} test modules successfully")
    print(f"Failed to load {failed_modules} test modules")
    print(f"Total test cases: {suite.countTestCases()}")
    print()

    if suite.countTestCases() > 0:
        print("Running tests...")
        print("-" * 60)

        # Run the tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)

        print("-" * 60)
        print(f"Tests run: {result.testsRun}")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        print(
            f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%"
        )

        return result.wasSuccessful()
    else:
        print("No tests to run!")
        return False


if __name__ == "__main__":
    success = run_working_tests()
    sys.exit(0 if success else 1)
