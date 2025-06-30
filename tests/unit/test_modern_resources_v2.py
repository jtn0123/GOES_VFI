"""Tests for modern resource management utilities."""

import asyncio
import os
from pathlib import Path
import tempfile
from typing import Any
import unittest
from unittest.mock import MagicMock, patch

from goesvfi.core.modern_resources import (
    MemoryMonitor,
    ResourceManager,
    ResourceTracker,
    atomic_write,
    get_memory_monitor,
    get_resource_manager,
    managed_async_resource,
    managed_resource,
    temporary_directory,
    temporary_env,
    temporary_file,
)


class MockResource:
    """Mock resource for testing."""

    def __init__(self, name: str):
        self.name = name
        self.cleaned_up = False

    def cleanup(self) -> None:
        self.cleaned_up = True


class MockAsyncResource:
    """Mock async resource for testing."""

    def __init__(self, name: str):
        self.name = name
        self.cleaned_up = False

    async def cleanup(self) -> None:
        self.cleaned_up = True


class TestResourceTracker(unittest.TestCase):
    """Test ResourceTracker functionality."""

    def test_track_and_cleanup(self) -> None:  # noqa: PLR6301
        """Test tracking and cleaning up resources."""
        tracker = ResourceTracker("test")
        resource = MockResource("test_resource")

        # Track resource
        tracker.track(resource)
        assert len(tracker._resources) == 1  # noqa: SLF001

        # Cleanup all
        tracker.cleanup_all()
        assert resource.cleaned_up
        assert len(tracker._resources) == 0  # noqa: SLF001

    def test_untrack(self) -> None:  # noqa: PLR6301
        """Test untracking resources."""
        tracker = ResourceTracker("test")
        resource = MockResource("test_resource")

        # Track and untrack
        tracker.track(resource)
        tracker.untrack(resource)
        assert len(tracker._resources) == 0  # noqa: SLF001

        # Cleanup should not affect untracked resource
        tracker.cleanup_all()
        assert not resource.cleaned_up

    def test_cleanup_with_different_methods(self) -> None:  # noqa: PLR6301
        """Test cleanup with different resource types."""
        tracker = ResourceTracker("test")

        # Resource with cleanup method
        resource1 = MockResource("cleanup_method")

        # Resource with close method
        resource2 = MagicMock()
        resource2.close = MagicMock()

        # Resource with __exit__ method
        resource3 = MagicMock()
        resource3.__exit__ = MagicMock()

        tracker.track(resource1)
        tracker.track(resource2)
        tracker.track(resource3)

        tracker.cleanup_all()

        assert resource1.cleaned_up
        resource2.close.assert_called_once()
        resource3.__exit__.assert_called_once_with(None, None, None)


class TestManagedResource(unittest.TestCase):
    """Test managed resource context managers."""

    def test_managed_resource_cleanup(self) -> None:  # noqa: PLR6301
        """Test managed resource context manager."""
        resource = MockResource("managed")

        with managed_resource(resource):
            assert not resource.cleaned_up

        assert resource.cleaned_up

    def test_managed_resource_custom_cleanup(self) -> None:  # noqa: PLR6301
        """Test managed resource with custom cleanup."""
        resource = MagicMock()
        cleanup_called = False

        def custom_cleanup(res: Any) -> None:
            nonlocal cleanup_called
            cleanup_called = True
            assert res is resource

        with managed_resource(resource, cleanup_fn=custom_cleanup):
            pass

        assert cleanup_called

    def test_managed_async_resource(self) -> None:  # noqa: PLR6301
        """Test async managed resource context manager."""

        async def run_test() -> None:
            resource = MockAsyncResource("async_managed")

            async with managed_async_resource(resource):
                assert not resource.cleaned_up

            assert resource.cleaned_up

        asyncio.run(run_test())

    def test_managed_async_resource_custom_cleanup(self) -> None:  # noqa: PLR6301
        """Test async managed resource with custom cleanup."""

        async def run_test() -> None:
            resource = MagicMock()
            cleanup_called = False

            async def custom_cleanup(res: Any) -> None:
                nonlocal cleanup_called
                cleanup_called = True
                assert res is resource

            async with managed_async_resource(resource, cleanup_fn=custom_cleanup):
                pass

            assert cleanup_called

        asyncio.run(run_test())


class TestTemporaryResources(unittest.TestCase):
    """Test temporary resource utilities."""

    def test_temporary_directory(self) -> None:  # noqa: PLR6301
        """Test temporary directory context manager."""
        temp_dir_path = None

        with temporary_directory(prefix="test_", suffix="_dir") as temp_dir:
            temp_dir_path = temp_dir
            assert temp_dir.exists()
            assert temp_dir.is_dir()
            assert "test_" in temp_dir.name
            assert "_dir" in temp_dir.name

        # Directory should be cleaned up
        assert not temp_dir_path.exists()

    def test_temporary_directory_no_cleanup(self) -> None:  # noqa: PLR6301
        """Test temporary directory without cleanup."""
        temp_dir_path = None

        with temporary_directory(cleanup=False) as temp_dir:
            temp_dir_path = temp_dir
            assert temp_dir.exists()

        # Directory should still exist
        assert temp_dir_path.exists()

        # Manual cleanup
        import shutil  # noqa: PLC0415

        shutil.rmtree(temp_dir_path)

    def test_temporary_file(self) -> None:  # noqa: PLR6301
        """Test temporary file context manager."""
        temp_file_path = None

        with temporary_file(prefix="test_", suffix=".tmp") as temp_file:
            temp_file_path = temp_file
            assert temp_file.exists()
            assert temp_file.is_file()
            assert "test_" in temp_file.name
            assert temp_file.name.endswith(".tmp")

        # File should be cleaned up
        assert not temp_file_path.exists()

    def test_temporary_file_no_cleanup(self) -> None:  # noqa: PLR6301
        """Test temporary file without cleanup."""
        temp_file_path = None

        with temporary_file(cleanup=False) as temp_file:
            temp_file_path = temp_file
            assert temp_file.exists()

        # File should still exist
        assert temp_file_path.exists()

        # Manual cleanup
        temp_file_path.unlink()


class TestResourceManager(unittest.TestCase):
    """Test ResourceManager functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Reset singleton
        import goesvfi.core.modern_resources

        goesvfi.core.modern_resources._resource_manager = None  # noqa: SLF001

    def test_singleton_pattern(self) -> None:  # noqa: PLR6301
        """Test ResourceManager singleton."""
        manager1 = get_resource_manager()
        manager2 = get_resource_manager()

        assert manager1 is manager2

    def test_track_and_cleanup(self) -> None:  # noqa: PLR6301
        """Test tracking and cleanup through ResourceManager."""
        manager = ResourceManager()
        resource = MockResource("managed")

        # Track resource
        manager.track(resource)
        assert not resource.cleaned_up

        # Cleanup - call the internal cleanup method directly
        manager._do_cleanup()  # noqa: SLF001
        assert resource.cleaned_up

    def test_managed_method(self) -> None:  # noqa: PLR6301
        """Test managed method."""
        manager = ResourceManager()
        resource = MockResource("managed")

        # Manage resource
        result = manager.managed(resource)
        assert result is resource

        # Cleanup
        manager._do_cleanup()  # noqa: SLF001
        assert resource.cleaned_up

    def test_batch_context(self) -> None:  # noqa: PLR6301
        """Test batch context manager."""
        manager = ResourceManager()

        # Add some initial resources
        initial_resource = MockResource("initial")
        manager.track(initial_resource)

        # Use batch context
        batch_resource = MockResource("batch")
        with manager.batch_context():
            manager.track(batch_resource)

        # Batch resource should be cleaned up
        assert batch_resource.cleaned_up
        # Initial resource should not be affected
        assert not initial_resource.cleaned_up


class TestAtomicWrite(unittest.TestCase):
    """Test atomic write utility."""

    def test_atomic_write_success(self) -> None:  # noqa: PLR6301
        """Test successful atomic write."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.txt"

            with atomic_write(test_file) as f:
                f.write("test content")

            # File should exist with correct content
            assert test_file.exists()
            assert test_file.read_text() == "test content"

    def test_atomic_write_with_backup(self) -> None:  # noqa: PLR6301
        """Test atomic write with backup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.txt"
            backup_file = test_file.with_suffix(".txt.bak")

            # Create initial file
            test_file.write_text("original content")

            # Atomic write with backup
            with atomic_write(test_file, backup=True) as f:
                f.write("new content")

            # File should have new content
            assert test_file.read_text() == "new content"
            # Backup should be cleaned up after success
            assert not backup_file.exists()

    def test_atomic_write_failure(self) -> None:  # noqa: PLR6301
        """Test atomic write failure.
        
        Raises:
            ValueError: Test error for atomic write failure.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.txt"
            temp_file = test_file.with_suffix(".txt.tmp")

            try:
                with atomic_write(test_file) as f:
                    f.write("partial content")
                    # Simulate error
                    raise ValueError("Test error")
            except ValueError:
                pass

            # Original file should not exist
            assert not test_file.exists()
            # Temp file should be cleaned up
            assert not temp_file.exists()


class TestMemoryMonitor(unittest.TestCase):
    """Test MemoryMonitor functionality."""

    def test_memory_monitor_singleton(self) -> None:  # noqa: PLR6301
        """Test memory monitor singleton."""
        monitor1 = get_memory_monitor()
        monitor2 = get_memory_monitor()

        assert monitor1 is monitor2

    @patch("goesvfi.core.modern_resources.psutil")
    def test_memory_usage_with_psutil(self, mock_psutil: Any) -> None:
        """Test memory usage with psutil available."""
        # Mock psutil
        mock_memory = MagicMock()
        mock_memory.total = 8000000000  # 8GB
        mock_memory.available = 4000000000  # 4GB
        mock_memory.percent = 50.0
        mock_memory.used = 4000000000
        mock_memory.free = 4000000000
        mock_psutil.virtual_memory.return_value = mock_memory

        monitor = MemoryMonitor()
        usage = monitor.get_memory_usage()

        assert usage["total"] == 8000000000
        assert usage["percent"] == 50.0

    def test_memory_usage_without_psutil(self) -> None:  # noqa: PLR6301
        """Test memory usage without psutil."""
        with patch.dict("sys.modules", {"psutil": None}):
            monitor = MemoryMonitor()
            usage = monitor.get_memory_usage()

            # Should return fallback data
            assert "percent" in usage

    def test_check_memory_thresholds(self) -> None:  # noqa: PLR6301
        """Test memory threshold checking."""
        monitor = MemoryMonitor(warning_threshold=0.7, critical_threshold=0.9)

        with patch.object(monitor, "get_memory_usage") as mock_usage:
            # Normal usage
            mock_usage.return_value = {"percent": 50.0}
            assert monitor.check_memory()

            # High usage (warning)
            mock_usage.return_value = {"percent": 80.0}
            assert monitor.check_memory()

            # Critical usage
            mock_usage.return_value = {"percent": 95.0}
            assert not monitor.check_memory()

    def test_monitor_context(self) -> None:  # noqa: PLR6301
        """Test memory monitoring context manager."""
        monitor = MemoryMonitor()

        with patch.object(monitor, "get_memory_usage") as mock_usage:
            mock_usage.side_effect = [
                {"percent": 50.0},  # Initial
                {"percent": 55.0},  # Final
            ]

            with monitor.monitor_context():
                pass

            assert mock_usage.call_count == 2


class TestTemporaryEnv(unittest.TestCase):
    """Test temporary environment variable utility."""

    def test_temporary_env_set_new(self) -> None:  # noqa: PLR6301
        """Test setting new environment variable."""
        test_var = "TEST_VAR_NEW"

        # Ensure variable doesn't exist
        original_value = os.environ.get(test_var)
        if original_value is not None:
            del os.environ[test_var]

        with temporary_env(**{test_var: "test_value"}):
            assert os.environ[test_var] == "test_value"

        # Should be removed after context
        assert test_var not in os.environ

    def test_temporary_env_modify_existing(self) -> None:  # noqa: PLR6301
        """Test modifying existing environment variable."""
        test_var = "PATH"  # PATH always exists
        original_value = os.environ[test_var]

        with temporary_env(**{test_var: "test_value"}):
            assert os.environ[test_var] == "test_value"

        # Should be restored
        assert os.environ[test_var] == original_value


if __name__ == "__main__":
    unittest.main()
