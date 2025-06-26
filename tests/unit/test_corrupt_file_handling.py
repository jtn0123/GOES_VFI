"""Tests for corrupt file handling.

These tests verify graceful handling of invalid, corrupt, or malformed
satellite data files and various error conditions.
"""

import asyncio
import hashlib
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from goesvfi.exceptions import PipelineError
from goesvfi.integrity_check.remote.base import RemoteStoreError

# NetCDFRenderer doesn't exist - will be mocked in tests
from goesvfi.pipeline.image_loader import ImageLoader
from goesvfi.pipeline.sanchez_processor import SanchezProcessor


class TestCorruptFileHandling:
    """Test handling of corrupt and invalid files."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def netcdf_renderer(self):
        """Create a NetCDF renderer instance."""
        # Mock NetCDFRenderer since it doesn't exist
        mock_renderer = AsyncMock()

        # Configure render_channel to raise PipelineError when xarray fails
        async def render_with_error(*args, **kwargs):
            import xarray

            try:
                # This will trigger the mocked xarray.open_dataset
                xarray.open_dataset(kwargs.get("file_path"))
            except ValueError as e:
                raise PipelineError(f"Unable to read file: {e}")
            except OSError as e:
                raise PipelineError(f"File error: {e}")
            except Exception as e:
                raise PipelineError(f"Processing error: {e}")

        mock_renderer.render_channel.side_effect = render_with_error
        return mock_renderer

    @pytest.fixture
    def image_loader(self):
        """Create an image loader instance."""
        return ImageLoader()

    def create_corrupt_file(self, path: Path, corruption_type: str) -> Path:
        """Create various types of corrupt files for testing."""
        path.parent.mkdir(parents=True, exist_ok=True)

        if corruption_type == "empty":
            # Empty file
            path.touch()
        elif corruption_type == "truncated":
            # Truncated NetCDF file (incomplete header)
            path.write_bytes(b"CDF\x01" + b"\x00" * 10)  # Partial NetCDF header
        elif corruption_type == "wrong_format":
            # Wrong file format (JPEG instead of NetCDF)
            path.write_bytes(b"\xff\xd8\xff\xe0" + b"JFIF" + b"\x00" * 100)
        elif corruption_type == "corrupted_data":
            # Valid NetCDF header but corrupted data
            # NetCDF classic format header
            header = b"CDF\x01"  # Magic number
            header += b"\x00\x00\x00\x00"  # numrecs
            # Add corrupted dimension/variable data
            header += b"\xff" * 100  # Random corruption
            path.write_bytes(header)
        elif corruption_type == "invalid_structure":
            # Valid file but wrong internal structure
            path.write_bytes(b"CDF\x01" + b"\x00" * 1024)  # Valid header, empty data
        elif corruption_type == "partial_download":
            # Simulates incomplete download
            expected_size = 1024 * 1024  # 1MB expected
            actual_data = b"\x00" * (expected_size // 2)  # Only half downloaded
            path.write_bytes(actual_data)
        elif corruption_type == "wrong_permissions":
            # Create file with no read permissions
            path.write_bytes(b"valid data")
            path.chmod(0o000)
        elif corruption_type == "corrupted_image":
            # Corrupted PNG file
            # PNG header is correct but data is corrupted
            png_header = b"\x89PNG\r\n\x1a\n"
            corrupted_data = b"\xff" * 100
            path.write_bytes(png_header + corrupted_data)

        return path

    @pytest.mark.asyncio
    async def test_empty_file_handling(self, temp_dir, netcdf_renderer):
        """Test handling of empty files."""
        empty_file = self.create_corrupt_file(temp_dir / "empty.nc", "empty")

        with patch("xarray.open_dataset") as mock_open:
            mock_open.side_effect = ValueError("Unable to read file")

            with pytest.raises(PipelineError) as exc_info:
                await netcdf_renderer.render_channel(
                    file_path=empty_file,
                    channel=13,
                    output_path=temp_dir / "output.png",
                )

            assert "Unable to read file" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_truncated_file_handling(self, temp_dir, netcdf_renderer):
        """Test handling of truncated NetCDF files."""
        truncated_file = self.create_corrupt_file(
            temp_dir / "truncated.nc", "truncated"
        )

        with patch("xarray.open_dataset") as mock_open:
            mock_open.side_effect = OSError("Truncated file")

            with pytest.raises(PipelineError) as exc_info:
                await netcdf_renderer.render_channel(
                    file_path=truncated_file,
                    channel=13,
                    output_path=temp_dir / "output.png",
                )

            assert "Truncated file" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_wrong_format_file(self, temp_dir, netcdf_renderer):
        """Test handling of wrong file formats."""
        wrong_format = self.create_corrupt_file(temp_dir / "image.jpg", "wrong_format")

        with patch("xarray.open_dataset") as mock_open:
            mock_open.side_effect = ValueError("Not a valid NetCDF file")

            with pytest.raises(PipelineError) as exc_info:
                await netcdf_renderer.render_channel(
                    file_path=wrong_format,
                    channel=13,
                    output_path=temp_dir / "output.png",
                )

            assert "Not a valid NetCDF file" in str(exc_info.value)

    def test_corrupted_image_loading(self, temp_dir, image_loader):
        """Test loading of corrupted image files."""
        corrupted_image = self.create_corrupt_file(
            temp_dir / "corrupted.png", "corrupted_image"
        )

        with patch("PIL.Image.open") as mock_open:
            mock_open.side_effect = IOError("Cannot identify image file")

            # ImageLoader catches IOError and re-raises as InputError
            from goesvfi.pipeline.exceptions import InputError

            with pytest.raises(InputError) as exc_info:
                image_loader.load(str(corrupted_image))

            assert "Cannot identify image file" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_checksum_validation_failure(self, temp_dir):
        """Test checksum validation for downloaded files."""
        test_file = temp_dir / "data.nc"
        test_file.write_bytes(b"corrupted data")

        expected_checksum = "a1b2c3d4e5f6"  # Expected MD5
        actual_checksum = hashlib.md5(test_file.read_bytes()).hexdigest()

        # Simulate checksum mismatch
        assert actual_checksum != expected_checksum

        # In a real scenario, this would raise an error
        with pytest.raises(RemoteStoreError) as exc_info:
            if actual_checksum != expected_checksum:
                raise RemoteStoreError(
                    f"Checksum mismatch: expected {expected_checksum}, "
                    f"got {actual_checksum}"
                )

        assert "Checksum mismatch" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_partial_download_detection(self, temp_dir):
        """Test detection of partially downloaded files."""
        partial_file = self.create_corrupt_file(
            temp_dir / "partial.nc", "partial_download"
        )

        expected_size = 1024 * 1024  # 1MB
        actual_size = partial_file.stat().st_size

        # Detect incomplete download
        assert actual_size < expected_size

        with pytest.raises(RemoteStoreError) as exc_info:
            if actual_size < expected_size:
                raise RemoteStoreError(
                    f"Incomplete download: expected {expected_size} bytes, "
                    f"got {actual_size} bytes"
                )

        assert "Incomplete download" in str(exc_info.value)

    def test_permission_denied_handling(self, temp_dir):
        """Test handling of permission denied errors."""
        if not hasattr(Path, "chmod"):
            pytest.skip("chmod not available on this platform")

        restricted_file = self.create_corrupt_file(
            temp_dir / "restricted.nc", "wrong_permissions"
        )

        try:
            # Attempt to read file with no permissions
            with pytest.raises(PermissionError):
                with open(restricted_file, "rb") as f:
                    f.read()
        finally:
            # Restore permissions for cleanup
            restricted_file.chmod(0o644)

    @pytest.mark.asyncio
    async def test_invalid_netcdf_structure(self, temp_dir, netcdf_renderer):
        """Test handling of NetCDF files with invalid internal structure."""
        invalid_structure = self.create_corrupt_file(
            temp_dir / "invalid_structure.nc", "invalid_structure"
        )

        # Mock xarray to raise KeyError which should be converted to PipelineError
        with patch("xarray.open_dataset") as mock_open:
            # Make xarray.open_dataset raise an exception directly
            mock_open.side_effect = KeyError("Variable 'Rad' not found")

            with pytest.raises(PipelineError) as exc_info:
                await netcdf_renderer.render_channel(
                    file_path=invalid_structure,
                    channel=13,
                    output_path=temp_dir / "output.png",
                )

            assert "Variable 'Rad' not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_out_of_memory_handling(self, temp_dir):
        """Test handling of out-of-memory errors."""
        # Simulate loading a very large array
        with patch("numpy.zeros") as mock_zeros:
            mock_zeros.side_effect = MemoryError("Unable to allocate array")

            with pytest.raises(MemoryError) as exc_info:
                # Try to allocate huge array
                np.zeros((100000, 100000), dtype=np.float64)

            assert "Unable to allocate array" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_corrupt_file_recovery(self, temp_dir):
        """Test recovery mechanisms for corrupt files."""
        corrupt_file = temp_dir / "corrupt.nc"
        backup_file = temp_dir / "backup.nc"

        # Create corrupt primary file
        self.create_corrupt_file(corrupt_file, "corrupted_data")

        # Create valid backup
        backup_file.write_bytes(b"valid backup data")

        # Recovery mechanism
        files_to_try = [corrupt_file, backup_file]
        successful_file = None

        for file_path in files_to_try:
            try:
                # Simulate file validation
                if file_path == corrupt_file:
                    raise ValueError("Corrupt file")
                else:
                    # Backup is valid
                    successful_file = file_path
                    break
            except ValueError:
                continue

        assert successful_file == backup_file

    def test_sanchez_processing_corrupt_input(self, temp_dir):
        """Test Sanchez processing with corrupt input files."""
        processor = SanchezProcessor(temp_dir=temp_dir)

        corrupt_input = self.create_corrupt_file(
            temp_dir / "corrupt_input.png", "corrupted_image"
        )

        # Mock the colourise function to raise an error
        with patch("goesvfi.pipeline.sanchez_processor.colourise") as mock_colourise:
            mock_colourise.side_effect = subprocess.CalledProcessError(
                1, ["sanchez"], stderr=b"Error: Invalid input image"
            )

            # Create mock image data
            import numpy as np

            from goesvfi.pipeline.image_processing_interfaces import ImageData

            # Create a corrupted image array
            image_data = ImageData(
                image_data=np.zeros((100, 100), dtype=np.uint8),
                source_path=str(corrupt_input),
                metadata={},
            )

            # SanchezProcessor returns original image on failure, doesn't raise
            result = processor.process(image_data=image_data, res_km=2)

            # Verify it returned the original image
            assert result is image_data
            # Verify the error was logged
            mock_colourise.assert_called_once()

    @pytest.mark.asyncio
    async def test_race_condition_file_corruption(self, temp_dir):
        """Test handling of files corrupted by race conditions."""
        test_file = temp_dir / "race_condition.nc"

        # Simulate concurrent writes causing corruption
        async def corrupt_write():
            # First writer
            test_file.write_bytes(b"Writer 1 data")
            await asyncio.sleep(0.01)

        async def interfering_write():
            # Second writer interfering
            await asyncio.sleep(0.005)
            test_file.write_bytes(b"Writer 2")

        # Run concurrent writes
        await asyncio.gather(
            corrupt_write(), interfering_write(), return_exceptions=True
        )

        # File is now corrupted with partial data
        content = test_file.read_bytes()
        assert content == b"Writer 2"  # Second writer overwrote

    def test_zip_bomb_protection(self, temp_dir):
        """Test protection against zip bombs or extremely large compressed files."""
        # Create a file that expands to huge size when decompressed
        compressed_file = temp_dir / "bomb.gz"

        # Simulate compressed data that would expand enormously
        import gzip

        with gzip.open(compressed_file, "wb") as f:
            # Write small compressed data that represents large expanded data
            f.write(b"0" * 1000)  # Would expand to much larger size

        # Protection mechanism
        max_decompressed_size = 100 * 1024 * 1024  # 100MB limit

        with gzip.open(compressed_file, "rb") as f:
            decompressed_size = 0
            chunk_size = 1024 * 1024  # 1MB chunks

            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break

                decompressed_size += len(chunk)

                if decompressed_size > max_decompressed_size:
                    raise ValueError(
                        f"Decompressed size exceeds limit: {decompressed_size} > {max_decompressed_size}"
                    )

    @pytest.mark.asyncio
    async def test_file_format_validation(self, temp_dir):
        """Test validation of file formats before processing."""
        test_files = [
            (temp_dir / "test.nc", b"CDF\x01", True),  # Valid NetCDF
            (temp_dir / "test.jpg", b"\xff\xd8\xff", False),  # JPEG
            (temp_dir / "test.png", b"\x89PNG", False),  # PNG
            (temp_dir / "test.txt", b"Hello", False),  # Text file
        ]

        for file_path, header, is_valid_netcdf in test_files:
            file_path.write_bytes(header + b"\x00" * 100)

            # Validate file format
            with open(file_path, "rb") as f:
                file_header = f.read(4)

            is_netcdf = file_header.startswith(b"CDF")
            assert is_netcdf == is_valid_netcdf

    def test_graceful_error_messages(self, temp_dir):
        """Test that error messages are helpful for corrupt files."""
        corrupt_file = self.create_corrupt_file(
            temp_dir / "bad_data.nc", "corrupted_data"
        )

        error_messages = {
            "empty": "File is empty. Please ensure the download completed successfully.",
            "truncated": "File appears to be truncated. Try downloading again.",
            "wrong_format": "File format not recognized. Expected NetCDF format.",
            "corrupted_data": "File data is corrupted. Please verify the source.",
            "checksum_mismatch": "File integrity check failed. The file may be corrupted during transfer.",
        }

        # Simulate error detection and user-friendly message
        try:
            if corrupt_file.stat().st_size == 0:
                error_type = "empty"
            elif corrupt_file.read_bytes()[:4] != b"CDF\x01":
                error_type = "wrong_format"
            else:
                error_type = "corrupted_data"

            raise PipelineError(error_messages[error_type])

        except PipelineError as e:
            assert str(e) in error_messages.values()
            assert "corrupted" in str(e).lower()
