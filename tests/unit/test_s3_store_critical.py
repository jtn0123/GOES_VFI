"""Critical tests for S3 store functionality."""

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from goesvfi.integrity_check.remote.base import ResourceNotFoundError
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.time_index import SatellitePattern


class TestS3StoreCritical:
    """Test S3 store critical functionality."""

    @pytest.mark.asyncio
    async def test_s3_store_initialization(self):
        """Test S3 store initialization."""
        store = S3Store()

        # Test context manager
        async with store:
            assert store._s3_client is not None

        # After context exit, should be cleaned up
        assert store._s3_client is None

    @pytest.mark.asyncio
    async def test_download_success(self):
        """Test successful file download from S3."""
        store = S3Store()

        # Mock S3 client
        mock_s3_client = AsyncMock()

        # Mock head_object to return success
        mock_s3_client.head_object = AsyncMock(return_value={"ContentLength": 9})

        # Mock download_file
        mock_s3_client.download_file = AsyncMock()

        with patch.object(store, "_get_s3_client", return_value=mock_s3_client):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.stat") as mock_stat:
                    mock_stat.return_value.st_size = 9
                    with patch("pathlib.Path.mkdir"):
                        with tempfile.TemporaryDirectory() as temp_dir:
                            local_path = Path(temp_dir) / "test_file.nc"
                            ts = datetime(2023, 1, 1, 12, 0, 0)

                            # Test download
                            result = await store.download_file(
                                ts,
                                SatellitePattern.GOES_16,
                                local_path,
                            )

                            # Verify result
                            assert result == local_path

                            # Verify S3 client was called correctly
                            mock_s3_client.download_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_not_found(self):
        """Test handling of file not found errors."""
        store = S3Store()

        # Mock S3 client to raise NoSuchKey error
        mock_s3_client = AsyncMock()

        # Create boto3 style error
        import botocore.exceptions

        error = botocore.exceptions.ClientError({"Error": {"Code": "404", "Message": "NoSuchKey"}}, "HeadObject")
        mock_s3_client.head_object = AsyncMock(side_effect=error)

        # Mock the paginator for wildcard search
        mock_paginator = MagicMock()

        async def empty_paginate(*args, **kwargs):
            # Yield empty page
            yield {"Contents": []}

        mock_paginator.paginate = MagicMock(return_value=empty_paginate())
        mock_s3_client.get_paginator = MagicMock(return_value=mock_paginator)

        with patch.object(store, "_get_s3_client", return_value=mock_s3_client):
            with tempfile.TemporaryDirectory() as temp_dir:
                local_path = Path(temp_dir) / "missing_file.nc"
                ts = datetime(2023, 1, 1, 12, 0, 0)

                # Should raise ResourceNotFoundError
                with pytest.raises(ResourceNotFoundError) as exc_info:
                    await store.download_file(ts, SatellitePattern.GOES_16, local_path)

                # Verify it's about not finding files
                assert "No files found for GOES_16" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_exists_success(self):
        """Test checking if file exists."""
        store = S3Store()

        # Mock S3 client
        mock_s3_client = AsyncMock()
        mock_s3_client.head_object = AsyncMock(return_value={"ContentLength": 9})

        with patch.object(store, "_get_s3_client", return_value=mock_s3_client):
            ts = datetime(2023, 1, 1, 12, 0, 0)

            # Test exists
            result = await store.check_file_exists(ts, SatellitePattern.GOES_16)

            assert result is True

            # Verify S3 client was called correctly
            mock_s3_client.head_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_exists_not_found(self):
        """Test exists returns False for missing files."""
        store = S3Store()

        # Mock S3 client to raise 404 error
        mock_s3_client = AsyncMock()

        # Create boto3 style error
        import botocore.exceptions

        error = botocore.exceptions.ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject")
        mock_s3_client.head_object = AsyncMock(side_effect=error)

        with patch.object(store, "_get_s3_client", return_value=mock_s3_client):
            ts = datetime(2023, 1, 1, 12, 0, 0)

            # Test exists
            result = await store.check_file_exists(ts, SatellitePattern.GOES_16)

            assert result is False

    @pytest.mark.asyncio
    async def test_concurrent_downloads(self):
        """Test concurrent download handling."""
        store = S3Store()

        # Mock S3 client
        mock_s3_client = AsyncMock()
        mock_s3_client.head_object = AsyncMock(return_value={"ContentLength": 9})
        mock_s3_client.download_file = AsyncMock()

        with patch.object(store, "_get_s3_client", return_value=mock_s3_client):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.stat") as mock_stat:
                    mock_stat.return_value.st_size = 9
                    with patch("pathlib.Path.mkdir"):
                        with tempfile.TemporaryDirectory() as temp_dir:
                            # Download multiple files concurrently
                            tasks = []
                            for i in range(5):
                                local_path = Path(temp_dir) / f"concurrent_{i}.nc"
                                ts = datetime(2023, 1, 1, 12, i, 0)
                                task = store.download_file(
                                    ts,
                                    SatellitePattern.GOES_16,
                                    local_path,
                                )
                                tasks.append(task)

                            # Wait for all downloads
                            await asyncio.gather(*tasks)

                            # Verify all files were requested
                            assert mock_s3_client.download_file.call_count == 5

    @pytest.mark.asyncio
    async def test_download_with_wildcard(self):
        """Test download with wildcard pattern matching."""
        store = S3Store()

        # Mock S3 client
        mock_s3_client = AsyncMock()

        # Mock head_object to return 404 (so it tries wildcard)
        import botocore.exceptions

        error = botocore.exceptions.ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject")
        mock_s3_client.head_object = AsyncMock(side_effect=error)

        # Mock paginator for wildcard search
        mock_paginator = MagicMock()
        mock_page = {
            "Contents": [
                {
                    "Key": (
                        "ABI-L1b-RadC/2023/001/12/"
                        "OR_ABI-L1b-RadC-M6C13_G16_s20230011200000_e20230011200000_c20230011200000.nc"
                    )
                },
            ]
        }

        async def async_pages():
            yield mock_page

        mock_paginator.paginate = MagicMock(return_value=async_pages())
        mock_s3_client.get_paginator = MagicMock(return_value=mock_paginator)

        # Mock download_file
        mock_s3_client.download_file = AsyncMock()

        with patch.object(store, "_get_s3_client", return_value=mock_s3_client):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.stat") as mock_stat:
                    mock_stat.return_value.st_size = 1000
                    with patch("pathlib.Path.mkdir"):
                        with tempfile.TemporaryDirectory() as temp_dir:
                            local_path = Path(temp_dir) / "wildcard_test.nc"
                            ts = datetime(2023, 1, 1, 12, 0, 0)

                            # Test download
                            result = await store.download_file(
                                ts,
                                SatellitePattern.GOES_16,
                                local_path,
                            )

                            # Verify result
                            assert result == local_path

                            # Verify wildcard search was performed
                            mock_s3_client.get_paginator.assert_called_once()
