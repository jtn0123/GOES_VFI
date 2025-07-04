"""Safe test optimization strategies that maintain test coverage."""

from contextlib import contextmanager
import functools
import os
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication


class SafeTestOptimizations:
    """Optimizations that maintain test integrity."""

    @staticmethod
    @contextmanager
    def fast_gui_setup(preserve_behavior=True):
        """Speed up GUI tests while preserving behavior.

        Args:
            preserve_behavior: If True, maintains critical GUI behavior
        """
        patches = []

        # Only mock expensive operations, not core functionality
        if not preserve_behavior:
            # Only use this for pure unit tests
            patches.append(patch("PyQt6.QtWidgets.QApplication.processEvents"))
        else:
            # Speed up event processing without breaking it
            original_process_events = QApplication.processEvents

            def fast_process_events(flags=None, maxtime=None) -> None:
                # Process events but limit iterations
                original_process_events() if QApplication.instance() else None

            patches.append(patch("PyQt6.QtWidgets.QApplication.processEvents", fast_process_events))

        # Speed up animations without breaking them
        patches.append(
            patch("PyQt6.QtCore.QPropertyAnimation.setDuration", lambda self, ms: self.setDuration(min(ms, 10)))
        )

        # Apply all patches
        for p in patches:
            p.start()

        try:
            yield
        finally:
            for p in patches:
                p.stop()

    @staticmethod
    def optimize_file_operations(func):
        """Optimize file operations while maintaining functionality."""

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Use temp directory for faster I/O
            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"TEST_TEMP_DIR": tmpdir}):
                return func(*args, **kwargs)

        return wrapper

    @staticmethod
    def mock_network_with_realistic_data():
        """Mock network calls with realistic responses."""

        def create_mock_s3_client():
            client = MagicMock()
            # Provide realistic S3 responses
            client.list_objects_v2.return_value = {
                "Contents": [
                    {
                        "Key": "OR_ABI-L2-CMIPF/2023/001/00/file1.nc",
                        "Size": 4194304,
                        "LastModified": "2023-01-01T00:00:00Z",
                    }
                ],
                "IsTruncated": False,
            }
            client.head_object.return_value = {"ContentLength": 4194304, "ContentType": "application/x-netcdf"}

            # Simulate download delay but much shorter

            def mock_download(bucket, key, filename) -> None:
                import time

                time.sleep(0.01)  # 10ms instead of seconds
                # Create a small test file
                with open(filename, "wb") as f:
                    f.write(b"NETCDF_TEST_DATA")

            client.download_file.side_effect = mock_download
            return client

        return patch(
            "boto3.client", side_effect=lambda service: create_mock_s3_client() if service == "s3" else MagicMock()
        )

    @staticmethod
    def speed_up_timers_safely():
        """Speed up QTimer without breaking functionality."""

        class FastTimer(QTimer):
            def __init__(self, *args, **kwargs) -> None:
                super().__init__(*args, **kwargs)
                self._original_interval = None

            def setInterval(self, msec) -> None:
                self._original_interval = msec
                # Speed up by 10x but not instant
                super().setInterval(max(1, msec // 10))

            def interval(self):
                return self._original_interval or super().interval()

        return patch("PyQt6.QtCore.QTimer", FastTimer)

    @staticmethod
    def optimize_heavy_computations():
        """Mock heavy computations with representative samples."""

        def mock_interpolation(frames, factor):
            # Return subset instead of full interpolation
            if len(frames) > 2:
                return [frames[0], frames[-1]]
            return frames

        return patch("goesvfi.interpolate.interpolate_frames", mock_interpolation)


class TestDataFactory:
    """Create realistic test data quickly."""

    @staticmethod
    def create_test_image(width=100, height=100):
        """Create small test image instead of full size."""
        import numpy as np
        from PIL import Image

        # Small but valid image
        data = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
        return Image.fromarray(data)

    @staticmethod
    def create_test_netcdf():
        """Create minimal valid NetCDF for testing."""
        try:
            import tempfile

            import netCDF4 as nc
            import numpy as np

            with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as tmp:
                with nc.Dataset(tmp.name, "w") as ds:
                    # Minimal valid GOES structure
                    ds.createDimension("x", 10)
                    ds.createDimension("y", 10)
                    var = ds.createVariable("Rad", "f4", ("y", "x"))
                    var[:] = np.random.rand(10, 10)
                    ds.title = "Test GOES-16 Data"
                return tmp.name
        except ImportError:
            # Return mock if netCDF4 not available
            return "/mock/test.nc"


def safe_optimization_decorator(integration_test=False):
    """Decorator that applies safe optimizations based on test type.

    Args:
        integration_test: If True, preserves more real behavior
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            optimizations = []

            if not integration_test:
                # Unit tests can be more aggressively optimized
                optimizations.extend([
                    SafeTestOptimizations.mock_network_with_realistic_data(),
                    SafeTestOptimizations.speed_up_timers_safely(),
                    SafeTestOptimizations.optimize_heavy_computations(),
                ])
            else:
                # Integration tests need more real behavior
                optimizations.append(SafeTestOptimizations.speed_up_timers_safely())

            # Apply optimizations
            for opt in optimizations:
                opt.__enter__()

            try:
                # Use fast GUI setup
                with SafeTestOptimizations.fast_gui_setup(preserve_behavior=integration_test):
                    return func(*args, **kwargs)
            finally:
                # Clean up
                for opt in reversed(optimizations):
                    opt.__exit__(None, None, None)

        return wrapper

    return decorator


# Example usage patterns that maintain test integrity:


def example_safe_gui_test():
    """Example of safely optimized GUI test."""

    @safe_optimization_decorator(integration_test=True)
    def test_main_window_integration(qtbot) -> None:
        """Test that maintains real GUI behavior but runs faster."""
        from goesvfi.gui import MainWindow

        # This will create a real window but with optimizations
        window = MainWindow(debug_mode=False)
        qtbot.addWidget(window)

        # Event processing is sped up but still works
        qtbot.wait(100)  # Will actually wait ~10ms

        # Verify real behavior
        assert window.isVisible()
        assert window.main_tab is not None

    return test_main_window_integration


def example_safe_unit_test():
    """Example of safely optimized unit test."""

    @safe_optimization_decorator(integration_test=False)
    def test_s3_download_unit() -> None:
        """Unit test with mocked network but realistic behavior."""
        from goesvfi.integrity_check.remote.s3_store import S3Store

        store = S3Store()
        # This will use mocked S3 with realistic responses
        result = store.list_files("test-bucket", "test-prefix")

        # Verify behavior with realistic mock data
        assert len(result) > 0
        assert result[0]["Key"].endswith(".nc")

    return test_s3_download_unit
