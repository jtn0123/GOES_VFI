"""Async I/O utilities for high-performance file operations.

This module provides async file operations that don't block the event loop,
improving performance for I/O-heavy operations like NetCDF processing and
large image file handling.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from itertools import starmap
from pathlib import Path
from typing import Any

import aiofiles
import aiofiles.os
import aiofiles.tempfile

from goesvfi.core.base_manager import BaseManager
from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class AsyncFileManager(BaseManager):
    """Manager for async file operations with batching and queue management."""

    def __init__(self, max_concurrent: int = 10, buffer_size: int = 64 * 1024):
        """Initialize async file manager.

        Args:
            max_concurrent: Maximum concurrent file operations
            buffer_size: Buffer size for file operations in bytes
        """
        super().__init__("AsyncFileManager")
        self.max_concurrent = max_concurrent
        self.buffer_size = buffer_size
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_operations = set()

    async def read_file(self, path: Path, mode: str = "r", encoding: str = "utf-8") -> str | bytes:
        """Read a file asynchronously.

        Args:
            path: Path to file
            mode: File mode ('r' for text, 'rb' for binary)
            encoding: Text encoding (ignored for binary mode)

        Returns:
            File contents as string or bytes
        """
        async with self._semaphore:
            self.log_debug("Reading file: %s", path)

            try:
                async with aiofiles.open(path, mode=mode, encoding=encoding if "b" not in mode else None) as f:
                    content = await f.read()
                    self.log_debug(
                        "Read %d %s from %s",
                        len(content),
                        "bytes" if isinstance(content, bytes) else "characters",
                        path,
                    )
                    return content
            except Exception as e:
                self.handle_error(e, f"read_file({path})")
                raise

    async def write_file(
        self, path: Path, content: str | bytes, mode: str = "w", encoding: str = "utf-8", create_parents: bool = True
    ) -> None:
        """Write a file asynchronously.

        Args:
            path: Path to file
            content: Content to write
            mode: File mode ('w' for text, 'wb' for binary)
            encoding: Text encoding (ignored for binary mode)
            create_parents: Whether to create parent directories
        """
        async with self._semaphore:
            self.log_debug("Writing file: %s", path)

            try:
                if create_parents:
                    await self.ensure_directory(path.parent)

                async with aiofiles.open(path, mode=mode, encoding=encoding if "b" not in mode else None) as f:
                    await f.write(content)
                    self.log_debug(
                        "Wrote %d %s to %s", len(content), "bytes" if isinstance(content, bytes) else "characters", path
                    )
            except Exception as e:
                self.handle_error(e, f"write_file({path})")
                raise

    async def copy_file(self, src: Path, dest: Path, create_parents: bool = True) -> None:
        """Copy a file asynchronously.

        Args:
            src: Source file path
            dest: Destination file path
            create_parents: Whether to create parent directories
        """
        async with self._semaphore:
            self.log_debug("Copying file: %s -> %s", src, dest)

            try:
                if create_parents:
                    await self.ensure_directory(dest.parent)

                # Read source in chunks for memory efficiency
                async with aiofiles.open(src, "rb") as src_file, aiofiles.open(dest, "wb") as dest_file:
                    while True:
                        chunk = await src_file.read(self.buffer_size)
                        if not chunk:
                            break
                        await dest_file.write(chunk)

                self.log_debug("Copied %s -> %s", src, dest)
            except Exception as e:
                self.handle_error(e, f"copy_file({src} -> {dest})")
                raise

    async def move_file(self, src: Path, dest: Path, create_parents: bool = True) -> None:
        """Move a file asynchronously.

        Args:
            src: Source file path
            dest: Destination file path
            create_parents: Whether to create parent directories
        """
        async with self._semaphore:
            self.log_debug("Moving file: %s -> %s", src, dest)

            try:
                if create_parents:
                    await self.ensure_directory(dest.parent)

                # Try atomic rename first
                try:
                    await aiofiles.os.rename(src, dest)
                    self.log_debug("Moved %s -> %s (atomic)", src, dest)
                except OSError:
                    # Fall back to copy + delete if rename fails (cross-filesystem)
                    await self.copy_file(src, dest, create_parents=False)
                    await aiofiles.os.remove(src)
                    self.log_debug("Moved %s -> %s (copy+delete)", src, dest)
            except Exception as e:
                self.handle_error(e, f"move_file({src} -> {dest})")
                raise

    async def delete_file(self, path: Path, missing_ok: bool = True) -> None:
        """Delete a file asynchronously.

        Args:
            path: Path to file
            missing_ok: Whether to ignore missing files
        """
        async with self._semaphore:
            self.log_debug("Deleting file: %s", path)

            try:
                await aiofiles.os.remove(path)
                self.log_debug("Deleted file: %s", path)
            except FileNotFoundError:
                if not missing_ok:
                    raise
                self.log_debug("File not found (ignored): %s", path)
            except Exception as e:
                self.handle_error(e, f"delete_file({path})")
                raise

    async def ensure_directory(self, path: Path) -> None:
        """Ensure directory exists asynchronously.

        Args:
            path: Directory path to create
        """
        try:
            await aiofiles.os.makedirs(path, exist_ok=True)
            self.log_debug("Ensured directory: %s", path)
        except Exception as e:
            self.handle_error(e, f"ensure_directory({path})")
            raise

    async def list_directory(self, path: Path, pattern: str = "*") -> list[Path]:
        """List directory contents asynchronously.

        Args:
            path: Directory path
            pattern: Glob pattern for filtering

        Returns:
            List of matching paths
        """
        try:
            # Use asyncio to run glob in thread pool
            import fnmatch

            entries = await aiofiles.os.listdir(path)

            matching_paths = [path / entry for entry in entries if fnmatch.fnmatch(entry, pattern)]

            self.log_debug("Listed %d entries in %s (pattern: %s)", len(matching_paths), path, pattern)
            return matching_paths
        except Exception as e:
            self.handle_error(e, f"list_directory({path})")
            raise

    async def get_file_info(self, path: Path) -> dict[str, Any]:
        """Get file information asynchronously.

        Args:
            path: File path

        Returns:
            Dictionary with file information
        """
        try:
            stat_result = await aiofiles.os.stat(path)

            info = {
                "size": stat_result.st_size,
                "mtime": stat_result.st_mtime,
                "ctime": stat_result.st_ctime,
                "mode": stat_result.st_mode,
                "is_file": path.is_file(),
                "is_dir": path.is_dir(),
                "exists": True,
            }

            self.log_debug("Got file info for %s: %d bytes", path, info["size"])
            return info
        except FileNotFoundError:
            return {"exists": False}
        except Exception as e:
            self.handle_error(e, f"get_file_info({path})")
            raise

    async def batch_read(self, paths: list[Path], mode: str = "r", encoding: str = "utf-8") -> dict[Path, str | bytes]:
        """Read multiple files concurrently.

        Args:
            paths: List of file paths
            mode: File mode
            encoding: Text encoding

        Returns:
            Dictionary mapping paths to contents
        """
        self.log_info("Starting batch read of %d files", len(paths))

        async def read_single(path: Path) -> tuple[Path, str | bytes]:
            content = await self.read_file(path, mode, encoding)
            return path, content

        # Process files concurrently
        tasks = [read_single(path) for path in paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Separate successful results from exceptions
        success_results = {}
        errors = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                errors.append((paths[i], result))
            else:
                path, content = result
                success_results[path] = content

        if errors:
            self.log_warning("Batch read had %d errors out of %d files", len(errors), len(paths))
            for path, error in errors:
                self.log_warning("Failed to read %s: %s", path, error)

        self.log_info("Batch read completed: %d successful, %d failed", len(success_results), len(errors))
        return success_results

    async def batch_write(
        self, data: dict[Path, str | bytes], mode: str = "w", encoding: str = "utf-8", create_parents: bool = True
    ) -> list[Path]:
        """Write multiple files concurrently.

        Args:
            data: Dictionary mapping paths to content
            mode: File mode
            encoding: Text encoding
            create_parents: Whether to create parent directories

        Returns:
            List of successfully written paths
        """
        self.log_info("Starting batch write of %d files", len(data))

        async def write_single(path: Path, content: str | bytes) -> Path:
            await self.write_file(path, content, mode, encoding, create_parents)
            return path

        # Process files concurrently
        tasks = list(starmap(write_single, data.items()))
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Separate successful results from exceptions
        success_paths = []
        errors = []

        for i, result in enumerate(results):
            path = list(data.keys())[i]
            if isinstance(result, Exception):
                errors.append((path, result))
            else:
                success_paths.append(result)

        if errors:
            self.log_warning("Batch write had %d errors out of %d files", len(errors), len(data))
            for path, error in errors:
                self.log_warning("Failed to write %s: %s", path, error)

        self.log_info("Batch write completed: %d successful, %d failed", len(success_paths), len(errors))
        return success_paths


# Context managers for async file operations


@asynccontextmanager
async def async_open(path: Path, mode: str = "r", encoding: str = "utf-8", **kwargs: Any) -> AsyncGenerator[Any]:
    """Async context manager for file operations.

    Args:
        path: File path
        mode: File mode
        encoding: Text encoding
        **kwargs: Additional arguments for aiofiles.open

    Yields:
        Async file object
    """
    file_obj = await aiofiles.open(path, mode=mode, encoding=encoding if "b" not in mode else None, **kwargs)
    try:
        yield file_obj
    finally:
        await file_obj.close()


@asynccontextmanager
async def async_temporary_file(
    suffix: str = "", prefix: str = "goes_vfi_", dir: Path | None = None, mode: str = "w+b"
) -> AsyncGenerator[tuple[Any, Path]]:
    """Async temporary file context manager.

    Args:
        suffix: File suffix
        prefix: File prefix
        dir: Directory for temp file
        mode: File mode

    Yields:
        Tuple of (file_object, file_path)
    """
    async with aiofiles.tempfile.NamedTemporaryFile(
        suffix=suffix, prefix=prefix, dir=str(dir) if dir else None, mode=mode, delete=False
    ) as temp_file:
        temp_path = Path(temp_file.name)

        try:
            yield temp_file, temp_path
        finally:
            try:
                await aiofiles.os.remove(temp_path)
            except FileNotFoundError:
                pass  # File already deleted


# High-level async file operations for common patterns


async def async_read_json(path: Path) -> dict[str, Any]:
    """Read JSON file asynchronously.

    Args:
        path: Path to JSON file

    Returns:
        Parsed JSON data
    """
    import json

    content = await AsyncFileManager().read_file(path, mode="r")
    return json.loads(content)


async def async_write_json(path: Path, data: dict[str, Any], indent: int = 2) -> None:
    """Write JSON file asynchronously.

    Args:
        path: Path to JSON file
        data: Data to write
        indent: JSON indentation
    """
    import json

    content = json.dumps(data, indent=indent, ensure_ascii=False)
    await AsyncFileManager().write_file(path, content, mode="w")


async def async_read_lines(path: Path, encoding: str = "utf-8") -> list[str]:
    """Read file lines asynchronously.

    Args:
        path: Path to file
        encoding: Text encoding

    Returns:
        List of lines
    """
    content = await AsyncFileManager().read_file(path, mode="r", encoding=encoding)
    return content.splitlines()


async def async_write_lines(path: Path, lines: list[str], encoding: str = "utf-8") -> None:
    """Write file lines asynchronously.

    Args:
        path: Path to file
        lines: Lines to write
        encoding: Text encoding
    """
    content = "\n".join(lines)
    await AsyncFileManager().write_file(path, content, mode="w", encoding=encoding)


# Singleton async file manager
_async_file_manager: AsyncFileManager | None = None


def get_async_file_manager() -> AsyncFileManager:
    """Get global async file manager instance."""
    global _async_file_manager
    if _async_file_manager is None:
        _async_file_manager = AsyncFileManager()
    return _async_file_manager


# Convenience functions using the global manager


async def read_file_async(path: Path, mode: str = "r", encoding: str = "utf-8") -> str | bytes:
    """Read file using global async manager."""
    return await get_async_file_manager().read_file(path, mode, encoding)


async def write_file_async(path: Path, content: str | bytes, mode: str = "w", encoding: str = "utf-8") -> None:
    """Write file using global async manager."""
    await get_async_file_manager().write_file(path, content, mode, encoding)


async def copy_file_async(src: Path, dest: Path) -> None:
    """Copy file using global async manager."""
    await get_async_file_manager().copy_file(src, dest)


async def move_file_async(src: Path, dest: Path) -> None:
    """Move file using global async manager."""
    await get_async_file_manager().move_file(src, dest)
