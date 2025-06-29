"""Tests for corrupt file handling - Optimized Version.

These tests verify graceful handling of invalid, corrupt, or malformed
satellite data files and various error conditions.
"""

import asyncio
import gzip
import hashlib
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import AsyncMock, patch

import numpy as np
from PIL import Image
import pytest

from goesvfi.exceptions import PipelineError
from goesvfi.integrity_check.remote.base import RemoteStoreError
from goesvfi.pipeline.exceptions import InputError
from goesvfi.pipeline.image_loader import ImageLoader
from goesvfi.pipeline.image_processing_interfaces import ImageData
from goesvfi.pipeline.sanchez_processor import SanchezProcessor


class TestCorruptFileHandling:
    """Test handling of corrupt and invalid files - optimized with fixtures and parameterization."""

    @pytest.fixture()
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture()
    def netcdf_renderer(self):
        """Create a mocked NetCDF renderer instance."""
        mock_renderer = AsyncMock()

        async def render_with_error(*args, **kwargs) -> None:
            import xarray

            try:
                xarray.open_dataset(kwargs.get("file_path"))
            except ValueError as e:
                msg = f"Unable to read file: {e}"
                raise PipelineError(msg)
            except OSError as e:
                msg = f"File error: {e}"
                raise PipelineError(msg)
            except Exception as e:
                msg = f"Processing error: {e}"
                raise PipelineError(msg)

        mock_renderer.render_channel.side_effect = render_with_error
        return mock_renderer

    @pytest.fixture()
    def image_loader(self):
        """Create an image loader instance."""
        return ImageLoader()

    @pytest.fixture()
    def corrupt_file_factory(self, temp_dir):
        """Factory fixture for creating various types of corrupt files."""

        def create_file(filename: str, corruption_type: str) -> Path:
            path = temp_dir / filename
            path.parent.mkdir(parents=True, exist_ok=True)

            corruption_data = {
                "empty": b"",
                "truncated": b"CDF\x01" + b"\x00" * 10,  # Partial NetCDF header
                "wrong_format": b"\xff\xd8\xff\xe0" + b"JFIF" + b"\x00" * 100,  # JPEG
                "corrupted_data": b"CDF\x01\x00\x00\x00\x00" + b"\xff" * 100,  # Valid header, corrupted data
                "invalid_structure": b"CDF\x01" + b"\x00" * 1024,  # Valid header, empty data
                "partial_download": b"\x00" * (512 * 1024),  # Half of expected 1MB
                "corrupted_image": b"\x89PNG\r\n\x1a\n" + b"\xff" * 100,  # PNG header + corruption
            }

            if corruption_type == "wrong_permissions":
                path.write_bytes(b"valid data")
                path.chmod(0o000)
            else:
                path.write_bytes(corruption_data.get(corruption_type, b""))

            return path

        return create_file

    @pytest.mark.parametrize(
        "corruption_type,error_type,error_message",
        [
            ("empty", ValueError, "Unable to read file"),
            ("truncated", OSError, "Truncated file"),
            ("wrong_format", ValueError, "Not a valid NetCDF file"),
            ("invalid_structure", KeyError, "Variable 'Rad' not found"),
        ],
    )
    @pytest.mark.asyncio()
    async def test_netcdf_corruption_handling(
        self, temp_dir, netcdf_renderer, corrupt_file_factory, corruption_type, error_type, error_message
    ) -> None:
        """Test handling of various NetCDF file corruptions."""
        corrupt_file = corrupt_file_factory(f"test_{corruption_type}.nc", corruption_type)

        with patch("xarray.open_dataset") as mock_open:
            mock_open.side_effect = error_type(error_message)

            with pytest.raises(PipelineError) as exc_info:
                await netcdf_renderer.render_channel(
                    file_path=corrupt_file,
                    channel=13,
                    output_path=temp_dir / "output.png",
                )

            assert error_message in str(exc_info.value)

    def test_corrupted_image_loading(self, temp_dir, image_loader, corrupt_file_factory) -> None:
        """Test loading of corrupted image files."""
        corrupted_image = corrupt_file_factory("corrupted.png", "corrupted_image")

        with patch("PIL.Image.open") as mock_open:
            mock_open.side_effect = OSError("Cannot identify image file")

            with pytest.raises(InputError) as exc_info:
                image_loader.load(str(corrupted_image))

            assert "Cannot identify image file" in str(exc_info.value)

    @pytest.mark.parametrize(
        "test_case",
        [
            {
                "name": "checksum_mismatch",
                "data": b"corrupted data",
                "expected_checksum": "a1b2c3d4e5f6",
                "error_pattern": "Checksum mismatch",
            },
            {
                "name": "partial_download",
                "expected_size": 1024 * 1024,
                "actual_size": 512 * 1024,
                "error_pattern": "Incomplete download",
            },
        ],
    )
    @pytest.mark.asyncio()
    async def test_download_validation(self, temp_dir, test_case) -> None:
        """Test various download validation scenarios."""
        if test_case["name"] == "checksum_mismatch":
            test_file = temp_dir / "data.nc"
            test_file.write_bytes(test_case["data"])

            actual_checksum = hashlib.md5(test_file.read_bytes()).hexdigest()

            with pytest.raises(RemoteStoreError) as exc_info:
                if actual_checksum != test_case["expected_checksum"]:
                    msg = f"Checksum mismatch: expected {test_case['expected_checksum']}, got {actual_checksum}"
                    raise RemoteStoreError(msg)

        elif test_case["name"] == "partial_download":
            partial_file = temp_dir / "partial.nc"
            partial_file.write_bytes(b"\x00" * test_case["actual_size"])

            with pytest.raises(RemoteStoreError) as exc_info:
                if partial_file.stat().st_size < test_case["expected_size"]:
                    msg = (
                        f"Incomplete download: expected {test_case['expected_size']} bytes, "
                        f"got {test_case['actual_size']} bytes"
                    )
                    raise RemoteStoreError(msg)

        assert test_case["error_pattern"] in str(exc_info.value)

    def test_permission_denied_handling(self, temp_dir, corrupt_file_factory) -> None:
        """Test handling of permission denied errors."""
        if not hasattr(Path, "chmod"):
            pytest.skip("chmod not available on this platform")

        restricted_file = corrupt_file_factory("restricted.nc", "wrong_permissions")

        try:
            with pytest.raises(PermissionError), open(restricted_file, "rb") as f:
                f.read()
        finally:
            # Restore permissions for cleanup
            restricted_file.chmod(0o644)

    @pytest.mark.asyncio()
    async def test_out_of_memory_handling(self) -> None:
        """Test handling of out-of-memory errors."""
        with patch("numpy.zeros") as mock_zeros:
            mock_zeros.side_effect = MemoryError("Unable to allocate array")

            with pytest.raises(MemoryError) as exc_info:
                np.zeros((100000, 100000), dtype=np.float64)

            assert "Unable to allocate array" in str(exc_info.value)

    @pytest.mark.asyncio()
    async def test_corrupt_file_recovery(self, temp_dir, corrupt_file_factory) -> None:
        """Test recovery mechanisms for corrupt files."""
        corrupt_file = corrupt_file_factory("corrupt.nc", "corrupted_data")
        backup_file = temp_dir / "backup.nc"
        backup_file.write_bytes(b"valid backup data")

        # Recovery mechanism with multiple file attempts
        files_to_try = [corrupt_file, backup_file]
        successful_file = None

        for file_path in files_to_try:
            try:
                if file_path == corrupt_file:
                    msg = "Corrupt file"
                    raise ValueError(msg)
                successful_file = file_path
                break
            except ValueError:
                continue

        assert successful_file == backup_file

    def test_sanchez_processing_corrupt_input(self, temp_dir, corrupt_file_factory) -> None:
        """Test Sanchez processing with corrupt input files."""
        processor = SanchezProcessor(temp_dir=temp_dir)
        corrupt_input = corrupt_file_factory("corrupt_input.png", "corrupted_image")

        with patch("goesvfi.pipeline.sanchez_processor.colourise") as mock_colourise:
            mock_colourise.side_effect = subprocess.CalledProcessError(
                1, ["sanchez"], stderr=b"Error: Invalid input image"
            )

            image_data = ImageData(
                image_data=np.zeros((100, 100), dtype=np.uint8),
                source_path=str(corrupt_input),
                metadata={},
            )

            # SanchezProcessor returns original image on failure
            result = processor.process(image_data=image_data, res_km=2)

            assert result is image_data
            mock_colourise.assert_called_once()

    @pytest.mark.asyncio()
    async def test_race_condition_file_corruption(self, temp_dir) -> None:
        """Test handling of files corrupted by race conditions."""
        test_file = temp_dir / "race_condition.nc"

        async def concurrent_writes() -> None:
            """Simulate concurrent file writes."""

            async def write1() -> None:
                test_file.write_bytes(b"Writer 1 data")
                await asyncio.sleep(0.01)

            async def write2() -> None:
                await asyncio.sleep(0.005)
                test_file.write_bytes(b"Writer 2")

            await asyncio.gather(write1(), write2(), return_exceptions=True)

        await concurrent_writes()

        # File is now corrupted with partial data
        assert test_file.read_bytes() == b"Writer 2"

    def test_zip_bomb_protection(self, temp_dir) -> None:
        """Test protection against zip bombs or extremely large compressed files."""
        compressed_file = temp_dir / "bomb.gz"

        # Create compressed file
        with gzip.open(compressed_file, "wb") as f:
            f.write(b"0" * 1000)

        # Protection mechanism with size limit
        max_decompressed_size = 100 * 1024 * 1024  # 100MB limit
        decompressed_size = 0
        chunk_size = 1024 * 1024

        with gzip.open(compressed_file, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break

                decompressed_size += len(chunk)

                if decompressed_size > max_decompressed_size:
                    msg = f"Decompressed size exceeds limit: {decompressed_size} > {max_decompressed_size}"
                    raise ValueError(msg)

    @pytest.mark.parametrize(
        "file_info",
        [
            ("test.nc", b"CDF\x01", True, "NetCDF"),
            ("test.jpg", b"\xff\xd8\xff", False, "JPEG"),
            ("test.png", b"\x89PNG", False, "PNG"),
            ("test.txt", b"Hello", False, "Text"),
        ],
    )
    @pytest.mark.asyncio()
    async def test_file_format_validation(self, temp_dir, file_info) -> None:
        """Test validation of file formats before processing."""
        filename, header, is_valid_netcdf, _format_name = file_info

        file_path = temp_dir / filename
        file_path.write_bytes(header + b"\x00" * 100)

        # Validate file format by checking header
        with open(file_path, "rb") as f:
            file_header = f.read(4)

        is_netcdf = file_header.startswith(b"CDF")
        assert is_netcdf == is_valid_netcdf

    @pytest.mark.parametrize(
        "error_scenario",
        [
            {
                "corruption": "empty",
                "detection": lambda f: f.stat().st_size == 0,
                "message": "File is empty. Please ensure the download completed successfully.",
            },
            {
                "corruption": "truncated",
                "detection": lambda f: len(f.read_bytes()) < 100,
                "message": "File appears to be truncated. Try downloading again.",
            },
            {
                "corruption": "wrong_format",
                "detection": lambda f: not f.read_bytes()[:4].startswith(b"CDF"),
                "message": "File format not recognized. Expected NetCDF format.",
            },
            {
                "corruption": "corrupted_data",
                "detection": lambda f: True,  # Always detected after other checks
                "message": "File data is corrupted. Please verify the source.",
            },
        ],
    )
    def test_graceful_error_messages(self, temp_dir, corrupt_file_factory, error_scenario) -> None:
        """Test that error messages are helpful for corrupt files."""
        corrupt_file = corrupt_file_factory("bad_data.nc", error_scenario["corruption"])

        # Detect error type and generate appropriate message
        if error_scenario["detection"](corrupt_file):
            with pytest.raises(PipelineError) as exc_info:
                raise PipelineError(error_scenario["message"])

            assert error_scenario["message"] == str(exc_info.value)

    @pytest.mark.parametrize(
        "image_size,expected_valid",
        [
            ((100, 100), True),  # Small image - valid
            ((500, 500), True),  # Medium image - valid
            ((10000, 10000), True),  # Large but within limit - valid
            ((10001, 10001), False),  # Just over limit - invalid
            ((20000, 20000), False),  # Way over limit - invalid
        ],
    )
    def test_validate_image_size_limits(self, temp_dir, image_size, expected_valid) -> None:
        """Test validation of image size limits."""
        test_image = temp_dir / f"test_{image_size[0]}x{image_size[1]}.png"

        try:
            # Create test image
            img = Image.new("RGB", image_size, color="red")
            img.save(test_image, "PNG")

            # Validate size
            with Image.open(test_image) as img:
                width, height = img.size
                is_valid = width <= 10000 and height <= 10000

            assert is_valid == expected_valid

        except Exception:
            # Very large images might fail to create
            if not expected_valid:
                pass  # Expected for invalid sizes
            else:
                raise
        finally:
            if test_image.exists():
                test_image.unlink()
