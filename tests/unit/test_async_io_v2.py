"""Tests for async I/O utilities."""

import asyncio
import json
from pathlib import Path
import tempfile
import unittest

import pytest

from goesvfi.core.async_io import (
    AsyncFileManager,
    async_open,
    async_read_json,
    async_read_lines,
    async_temporary_file,
    async_write_json,
    async_write_lines,
    copy_file_async,
    get_async_file_manager,
    move_file_async,
    read_file_async,
    write_file_async,
)


class TestAsyncFileManager(unittest.TestCase):
    """Test AsyncFileManager functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.manager = AsyncFileManager(max_concurrent=2, buffer_size=1024)

    def test_initialization(self) -> None:
        """Test AsyncFileManager initialization."""
        assert self.manager.max_concurrent == 2
        assert self.manager.buffer_size == 1024
        assert self.manager._semaphore._value == 2

    def test_read_file_text(self) -> None:
        """Test reading text files."""
        async def run_test() -> None:
            with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
                f.write("test content")
                temp_path = Path(f.name)

            try:
                content = await self.manager.read_file(temp_path, mode="r")
                assert content == "test content"
                assert isinstance(content, str)
            finally:
                temp_path.unlink()

        asyncio.run(run_test())

    def test_read_file_binary(self) -> None:
        """Test reading binary files."""
        async def run_test() -> None:
            test_data = b"binary test data"
            with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
                f.write(test_data)
                temp_path = Path(f.name)

            try:
                content = await self.manager.read_file(temp_path, mode="rb")
                assert content == test_data
                assert isinstance(content, bytes)
            finally:
                temp_path.unlink()

        asyncio.run(run_test())

    def test_write_file_text(self) -> None:
        """Test writing text files."""
        async def run_test() -> None:
            with tempfile.TemporaryDirectory() as temp_dir:
                test_path = Path(temp_dir) / "test.txt"
                test_content = "test write content"

                await self.manager.write_file(test_path, test_content, mode="w")

                # Verify content
                assert test_path.exists()
                assert test_path.read_text() == test_content

        asyncio.run(run_test())

    def test_write_file_binary(self) -> None:
        """Test writing binary files."""
        async def run_test() -> None:
            with tempfile.TemporaryDirectory() as temp_dir:
                test_path = Path(temp_dir) / "test.bin"
                test_content = b"binary write content"

                await self.manager.write_file(test_path, test_content, mode="wb")

                # Verify content
                assert test_path.exists()
                assert test_path.read_bytes() == test_content

        asyncio.run(run_test())

    def test_write_file_create_parents(self) -> None:
        """Test writing files with parent directory creation."""
        async def run_test() -> None:
            with tempfile.TemporaryDirectory() as temp_dir:
                test_path = Path(temp_dir) / "subdir" / "nested" / "test.txt"
                test_content = "nested content"

                await self.manager.write_file(test_path, test_content, create_parents=True)

                # Verify parent directories were created
                assert test_path.parent.exists()
                assert test_path.read_text() == test_content

        asyncio.run(run_test())

    def test_copy_file(self) -> None:
        """Test copying files."""
        async def run_test() -> None:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create source file
                src_path = Path(temp_dir) / "source.txt"
                dest_path = Path(temp_dir) / "dest.txt"
                test_content = "copy test content"
                src_path.write_text(test_content)

                await self.manager.copy_file(src_path, dest_path)

                # Verify copy
                assert dest_path.exists()
                assert dest_path.read_text() == test_content
                assert src_path.exists()  # Original should still exist

        asyncio.run(run_test())

    def test_copy_file_large(self) -> None:
        """Test copying large files in chunks."""
        async def run_test() -> None:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create large source file
                src_path = Path(temp_dir) / "large_source.bin"
                dest_path = Path(temp_dir) / "large_dest.bin"

                # Create content larger than buffer size
                large_content = b"x" * (self.manager.buffer_size * 3)
                src_path.write_bytes(large_content)

                await self.manager.copy_file(src_path, dest_path)

                # Verify copy
                assert dest_path.exists()
                assert dest_path.read_bytes() == large_content

        asyncio.run(run_test())

    def test_move_file(self) -> None:
        """Test moving files."""
        async def run_test() -> None:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create source file
                src_path = Path(temp_dir) / "source.txt"
                dest_path = Path(temp_dir) / "dest.txt"
                test_content = "move test content"
                src_path.write_text(test_content)

                await self.manager.move_file(src_path, dest_path)

                # Verify move
                assert dest_path.exists()
                assert dest_path.read_text() == test_content
                assert not src_path.exists()  # Original should be gone

        asyncio.run(run_test())

    def test_delete_file(self) -> None:
        """Test deleting files."""
        async def run_test() -> None:
            with tempfile.NamedTemporaryFile(delete=False) as f:
                temp_path = Path(f.name)

            # File should exist initially
            assert temp_path.exists()

            await self.manager.delete_file(temp_path)

            # File should be deleted
            assert not temp_path.exists()

        asyncio.run(run_test())

    def test_delete_file_missing_ok(self) -> None:
        """Test deleting non-existent files with missing_ok=True."""
        async def run_test() -> None:
            non_existent = Path("/tmp/non_existent_file_test.txt")

            # Should not raise exception
            await self.manager.delete_file(non_existent, missing_ok=True)

        asyncio.run(run_test())

    def test_delete_file_missing_not_ok(self) -> None:
        """Test deleting non-existent files with missing_ok=False."""
        async def run_test() -> None:
            non_existent = Path("/tmp/non_existent_file_test.txt")

            with pytest.raises(FileNotFoundError):
                await self.manager.delete_file(non_existent, missing_ok=False)

        asyncio.run(run_test())

    def test_ensure_directory(self) -> None:
        """Test ensuring directories exist."""
        async def run_test() -> None:
            with tempfile.TemporaryDirectory() as temp_dir:
                new_dir = Path(temp_dir) / "new" / "nested" / "directory"

                await self.manager.ensure_directory(new_dir)

                assert new_dir.exists()
                assert new_dir.is_dir()

        asyncio.run(run_test())

    def test_list_directory(self) -> None:
        """Test listing directory contents."""
        async def run_test() -> None:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Create test files
                (temp_path / "file1.txt").write_text("test")
                (temp_path / "file2.py").write_text("test")
                (temp_path / "file3.txt").write_text("test")

                # List all files
                all_files = await self.manager.list_directory(temp_path)
                assert len(all_files) == 3

                # List only .txt files
                txt_files = await self.manager.list_directory(temp_path, "*.txt")
                assert len(txt_files) == 2

                # Verify paths are Path objects
                for path in txt_files:
                    assert isinstance(path, Path)
                    assert path.name.endswith(".txt")

        asyncio.run(run_test())

    def test_get_file_info(self) -> None:
        """Test getting file information."""
        async def run_test() -> None:
            with tempfile.NamedTemporaryFile(delete=False) as f:
                f.write(b"test content")
                temp_path = Path(f.name)

            try:
                info = await self.manager.get_file_info(temp_path)

                assert info["exists"]
                assert info["size"] == 12  # "test content" is 12 bytes
                assert "mtime" in info
                assert "ctime" in info
                assert "mode" in info
            finally:
                temp_path.unlink()

        asyncio.run(run_test())

    def test_get_file_info_non_existent(self) -> None:
        """Test getting info for non-existent files."""
        async def run_test() -> None:
            non_existent = Path("/tmp/non_existent_file_test.txt")
            info = await self.manager.get_file_info(non_existent)

            assert not info["exists"]

        asyncio.run(run_test())

    def test_batch_read(self) -> None:
        """Test batch reading multiple files."""
        async def run_test() -> None:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Create test files
                files = []
                for i in range(3):
                    file_path = temp_path / f"file{i}.txt"
                    file_path.write_text(f"content {i}")
                    files.append(file_path)

                # Batch read
                results = await self.manager.batch_read(files)

                assert len(results) == 3
                for i, file_path in enumerate(files):
                    assert results[file_path] == f"content {i}"

        asyncio.run(run_test())

    def test_batch_write(self) -> None:
        """Test batch writing multiple files."""
        async def run_test() -> None:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Prepare data
                data = {}
                for i in range(3):
                    file_path = temp_path / f"file{i}.txt"
                    data[file_path] = f"batch content {i}"

                # Batch write
                written_paths = await self.manager.batch_write(data)

                assert len(written_paths) == 3

                # Verify all files were written
                for file_path, content in data.items():
                    assert file_path.exists()
                    assert file_path.read_text() == content

        asyncio.run(run_test())

    def test_concurrency_limit(self) -> None:
        """Test that semaphore limits concurrent operations."""
        async def run_test() -> None:
            # Create a manager with very low concurrency
            limited_manager = AsyncFileManager(max_concurrent=1)

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Create multiple files to read
                files = []
                for i in range(5):
                    file_path = temp_path / f"file{i}.txt"
                    file_path.write_text(f"content {i}")
                    files.append(file_path)

                # Start batch read (should limit concurrency)
                results = await limited_manager.batch_read(files)

                # All files should still be read successfully
                assert len(results) == 5

        asyncio.run(run_test())


class TestAsyncContextManagers(unittest.TestCase):
    """Test async context managers."""

    def test_async_open(self) -> None:
        """Test async_open context manager."""
        async def run_test() -> None:
            with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
                f.write("test content")
                temp_path = Path(f.name)

            try:
                async with async_open(temp_path, mode="r") as f:
                    content = await f.read()
                    assert content == "test content"
            finally:
                temp_path.unlink()

        asyncio.run(run_test())

    def test_async_temporary_file(self) -> None:
        """Test async_temporary_file context manager."""
        async def run_test() -> None:
            temp_file_path = None

            async with async_temporary_file(suffix=".test", prefix="async_") as (temp_file, temp_path):
                temp_file_path = temp_path

                # File should exist during context
                assert temp_path.exists()
                assert "async_" in temp_path.name
                assert temp_path.name.endswith(".test")

                # Write some content
                await temp_file.write(b"async temp content")

            # File should be cleaned up after context
            assert not temp_file_path.exists()

        asyncio.run(run_test())


class TestHighLevelAsyncOperations(unittest.TestCase):
    """Test high-level async file operations."""

    def test_async_read_json(self) -> None:
        """Test async JSON reading."""
        async def run_test() -> None:
            test_data = {"key": "value", "number": 42, "list": [1, 2, 3]}

            with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json", encoding="utf-8") as f:
                json.dump(test_data, f)
                temp_path = Path(f.name)

            try:
                data = await async_read_json(temp_path)
                assert data == test_data
            finally:
                temp_path.unlink()

        asyncio.run(run_test())

    def test_async_write_json(self) -> None:
        """Test async JSON writing."""
        async def run_test() -> None:
            test_data = {"async": True, "data": [1, 2, 3]}

            with tempfile.TemporaryDirectory() as temp_dir:
                json_path = Path(temp_dir) / "test.json"

                await async_write_json(json_path, test_data, indent=4)

                # Verify file was written correctly
                assert json_path.exists()

                with open(json_path, encoding="utf-8") as f:
                    loaded_data = json.load(f)

                assert loaded_data == test_data

        asyncio.run(run_test())

    def test_async_read_lines(self) -> None:
        """Test async line reading."""
        async def run_test() -> None:
            test_lines = ["line 1", "line 2", "line 3"]

            with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
                f.write("\n".join(test_lines))
                temp_path = Path(f.name)

            try:
                lines = await async_read_lines(temp_path)
                assert lines == test_lines
            finally:
                temp_path.unlink()

        asyncio.run(run_test())

    def test_async_write_lines(self) -> None:
        """Test async line writing."""
        async def run_test() -> None:
            test_lines = ["async line 1", "async line 2", "async line 3"]

            with tempfile.TemporaryDirectory() as temp_dir:
                lines_path = Path(temp_dir) / "lines.txt"

                await async_write_lines(lines_path, test_lines)

                # Verify file was written correctly
                assert lines_path.exists()
                content = lines_path.read_text()
                assert content == "\n".join(test_lines)

        asyncio.run(run_test())


class TestGlobalAsyncManager(unittest.TestCase):
    """Test global async file manager and convenience functions."""

    def test_singleton_manager(self) -> None:
        """Test that get_async_file_manager returns singleton."""
        manager1 = get_async_file_manager()
        manager2 = get_async_file_manager()

        assert manager1 is manager2

    def test_convenience_read_write(self) -> None:
        """Test convenience functions for read/write."""
        async def run_test() -> None:
            with tempfile.TemporaryDirectory() as temp_dir:
                test_path = Path(temp_dir) / "convenience.txt"
                test_content = "convenience test content"

                # Write using convenience function
                await write_file_async(test_path, test_content)

                # Read using convenience function
                read_content = await read_file_async(test_path)

                assert read_content == test_content

        asyncio.run(run_test())

    def test_convenience_copy_move(self) -> None:
        """Test convenience functions for copy/move."""
        async def run_test() -> None:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Create source file
                src_path = temp_path / "source.txt"
                copy_path = temp_path / "copy.txt"
                move_path = temp_path / "moved.txt"
                test_content = "copy move test"

                await write_file_async(src_path, test_content)

                # Test copy
                await copy_file_async(src_path, copy_path)
                assert copy_path.exists()
                assert src_path.exists()  # Original should remain

                # Test move
                await move_file_async(copy_path, move_path)
                assert move_path.exists()
                assert not copy_path.exists()  # Source should be gone

        asyncio.run(run_test())


class TestErrorHandling(unittest.TestCase):
    """Test error handling in async file operations."""

    def test_read_non_existent_file(self) -> None:
        """Test reading non-existent file raises appropriate error."""
        async def run_test() -> None:
            manager = AsyncFileManager()
            non_existent = Path("/tmp/definitely_does_not_exist.txt")

            with pytest.raises(FileNotFoundError):
                await manager.read_file(non_existent)

        asyncio.run(run_test())

    def test_write_to_read_only_directory(self) -> None:
        """Test writing to read-only directory handles error gracefully."""
        async def run_test() -> None:
            manager = AsyncFileManager()

            # Try to write to root (should fail with permission error or OSError)
            read_only_path = Path("/read_only_test.txt")

            with pytest.raises((PermissionError, OSError)):
                await manager.write_file(read_only_path, "test")

        asyncio.run(run_test())

    def test_batch_operations_with_errors(self) -> None:
        """Test batch operations handle partial failures gracefully."""
        async def run_test() -> None:
            manager = AsyncFileManager()

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Mix of valid and invalid paths
                paths = [
                    temp_path / "valid1.txt",
                    Path("/invalid/path/file.txt"),  # Should fail
                    temp_path / "valid2.txt",
                ]

                # Create valid files
                paths[0].write_text("content 1")
                paths[2].write_text("content 2")

                # Batch read should return partial results
                results = await manager.batch_read(paths)

                # Should get the valid files
                assert len(results) == 2
                assert paths[0] in results
                assert paths[2] in results

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
