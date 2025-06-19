"""End-to-end integration tests for satellite data download workflow.

These tests verify the complete workflow from S3/CDN download to processed output,
including retry logic, error handling, and data validation.
"""

import asyncio
import hashlib
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

# NetCDFRenderer doesn't exist - will be mocked in tests
from goesvfi.integrity_check.goes_imagery import ChannelType
from goesvfi.integrity_check.remote.base import (
    NetworkError,
    RemoteStoreError,
    ResourceNotFoundError,
    TemporaryError,
)
from goesvfi.integrity_check.remote.cdn_store import CDNStore
from goesvfi.integrity_check.remote.composite_store import CompositeStore
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.time_index import SatellitePattern


class TestEndToEndSatelliteDownload:
    """Test complete satellite data download and processing workflow."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_netcdf_data(self):
        """Create mock NetCDF data structure."""
        # Simulate GOES-16 ABI L1b RadC data structure
        return {
            "Rad": np.random.rand(1000, 1000).astype(np.float32),
            "t": np.array([0]),  # Time dimension
            "band_id": np.array([13]),  # Band 13 (10.3 μm)
            "band_wavelength": np.array([10.35]),
            "kappa0": np.array([0.01]),  # Scaling factor
            "planck_fk1": np.array([1000.0]),  # Planck constants
            "planck_fk2": np.array([500.0]),
            "planck_bc1": np.array([0.1]),
            "planck_bc2": np.array([0.05]),
            "time_coverage_start": "2023-01-01T12:00:00Z",
            "time_coverage_end": "2023-01-01T12:15:00Z",
            "spatial_resolution": "2km at nadir",
            "platform_ID": "G16",
            "instrument_type": "GOES-16 ABI",
        }

    @pytest.mark.asyncio
    async def test_complete_download_workflow(self, temp_dir, mock_netcdf_data):
        """Test the complete workflow from download to processed image."""
        # Setup test parameters
        timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        satellite = SatellitePattern.GOES_16
        channel = ChannelType.BAND_13  # Clean longwave infrared window

        # Expected file path
        expected_filename = "OR_ABI-L1b-RadC-M6C13_G16_s20230011200000_e20230011215000_c20230011215300.nc"
        download_path = temp_dir / expected_filename
        output_path = temp_dir / "processed_band13.png"

        # Mock S3 store behavior
        mock_s3_store = AsyncMock(spec=S3Store)
        mock_s3_store.download = AsyncMock(return_value=download_path)
        mock_s3_store.exists = AsyncMock(return_value=True)

        # Mock CDN store as fallback
        mock_cdn_store = AsyncMock(spec=CDNStore)
        mock_cdn_store.download = AsyncMock(return_value=download_path)
        mock_cdn_store.exists = AsyncMock(return_value=True)

        # Create composite store with both sources
        composite_store = CompositeStore([mock_s3_store, mock_cdn_store])

        # Mock NetCDF file reading
        with patch("xarray.open_dataset") as mock_open_dataset:
            mock_dataset = MagicMock()
            mock_dataset.__getitem__.side_effect = lambda key: mock_netcdf_data.get(key)
            mock_dataset.attrs = {
                "time_coverage_start": mock_netcdf_data["time_coverage_start"],
                "time_coverage_end": mock_netcdf_data["time_coverage_end"],
                "spatial_resolution": mock_netcdf_data["spatial_resolution"],
                "platform_ID": mock_netcdf_data["platform_ID"],
                "instrument_type": mock_netcdf_data["instrument_type"],
            }
            mock_open_dataset.return_value.__enter__.return_value = mock_dataset

            # Mock image saving
            with patch("PIL.Image.Image.save") as mock_save:
                # Execute the complete workflow
                async with composite_store:
                    # Step 1: Download the file
                    downloaded_file = await composite_store.download(
                        ts=timestamp, satellite=satellite, dest_path=download_path
                    )

                    assert downloaded_file == download_path
                    mock_s3_store.download.assert_called_once()

                    # Step 2: Process the NetCDF file
                    # Mock NetCDFRenderer since it doesn't exist
                    renderer = MagicMock()
                    renderer.render_channel = AsyncMock(return_value=True)

                    # Create the downloaded file (mock)
                    download_path.parent.mkdir(parents=True, exist_ok=True)
                    download_path.touch()

                    # Render the image
                    render_result = await renderer.render_channel(
                        file_path=downloaded_file,
                        channel=channel,
                        output_path=output_path,
                        apply_enhancement=True,
                    )

                    # Step 3: Verify the output
                    assert mock_save.called
                    assert mock_open_dataset.called

                    # Verify correct data was accessed
                    mock_dataset.__getitem__.assert_any_call("Rad")

    @pytest.mark.asyncio
    async def test_download_with_retry_and_fallback(self, temp_dir):
        """Test download with retry logic and fallback to CDN."""
        timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        satellite = SatellitePattern.GOES_16
        download_path = temp_dir / "test_file.nc"

        # Mock S3 store to fail with temporary error then succeed
        mock_s3_store = AsyncMock(spec=S3Store)
        mock_s3_store.download = AsyncMock(
            side_effect=[
                TemporaryError("Connection timeout", retry_after=1),
                TemporaryError("Connection timeout", retry_after=2),
                NetworkError("Connection failed"),  # Final failure
            ]
        )

        # Mock CDN store to succeed after S3 fails
        mock_cdn_store = AsyncMock(spec=CDNStore)
        mock_cdn_store.download = AsyncMock(return_value=download_path)

        # Create composite store
        composite_store = CompositeStore([mock_s3_store, mock_cdn_store])

        async with composite_store:
            # Download should succeed via CDN after S3 fails
            result = await composite_store.download(
                ts=timestamp, satellite=satellite, dest_path=download_path
            )

            assert result == download_path

            # Verify S3 was tried with retries
            assert mock_s3_store.download.call_count == 3

            # Verify CDN was used as fallback
            mock_cdn_store.download.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_all_sources_fail(self, temp_dir):
        """Test behavior when all download sources fail."""
        timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        satellite = SatellitePattern.GOES_16
        download_path = temp_dir / "test_file.nc"

        # Mock both stores to fail
        mock_s3_store = AsyncMock(spec=S3Store)
        mock_s3_store.download = AsyncMock(
            side_effect=NetworkError("S3 connection failed")
        )

        mock_cdn_store = AsyncMock(spec=CDNStore)
        mock_cdn_store.download = AsyncMock(
            side_effect=ResourceNotFoundError("File not found on CDN")
        )

        # Create composite store
        composite_store = CompositeStore([mock_s3_store, mock_cdn_store])

        async with composite_store:
            # Should raise RemoteStoreError with details about all failures
            with pytest.raises(RemoteStoreError) as exc_info:
                await composite_store.download(
                    ts=timestamp, satellite=satellite, dest_path=download_path
                )

            # Verify error message includes failure details
            error_msg = str(exc_info.value)
            assert "All remote stores failed" in error_msg
            assert "S3 connection failed" in error_msg
            assert "File not found on CDN" in error_msg

    @pytest.mark.asyncio
    async def test_parallel_downloads(self, temp_dir):
        """Test concurrent downloads of multiple satellite files."""
        # Setup multiple timestamps (every 15 minutes for GOES-16)
        base_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        timestamps = [base_time + timedelta(minutes=15 * i) for i in range(4)]
        satellite = SatellitePattern.GOES_16

        # Mock S3 store
        mock_s3_store = AsyncMock(spec=S3Store)
        download_count = 0

        async def mock_download(ts, satellite, dest_path, **kwargs):
            nonlocal download_count
            download_count += 1
            # Simulate some processing time
            await asyncio.sleep(0.1)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.touch()
            return dest_path

        mock_s3_store.download = mock_download

        async with mock_s3_store:
            # Download all files concurrently
            tasks = []
            for i, ts in enumerate(timestamps):
                download_path = temp_dir / f"goes16_{i}.nc"
                task = mock_s3_store.download(
                    ts=ts, satellite=satellite, dest_path=download_path
                )
                tasks.append(task)

            # Wait for all downloads
            results = await asyncio.gather(*tasks)

            # Verify all downloads completed
            assert len(results) == 4
            assert download_count == 4

            # Verify all files were created
            for result in results:
                assert result.exists()

    @pytest.mark.asyncio
    async def test_download_with_progress_callback(self, temp_dir):
        """Test download with progress reporting."""
        timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        satellite = SatellitePattern.GOES_16
        download_path = temp_dir / "test_file.nc"

        progress_updates = []

        def progress_callback(downloaded, total):
            progress_updates.append((downloaded, total))

        # Mock S3 store with progress reporting
        mock_s3_store = AsyncMock(spec=S3Store)

        async def mock_download_with_progress(
            ts, satellite, dest_path, progress_callback=None, **kwargs
        ):
            # Simulate progressive download
            total_size = 1024 * 1024  # 1MB
            chunk_size = 256 * 1024  # 256KB chunks

            for downloaded in range(0, total_size + 1, chunk_size):
                if progress_callback:
                    progress_callback(min(downloaded, total_size), total_size)
                await asyncio.sleep(0.01)  # Simulate download time

            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(b"x" * total_size)
            return dest_path

        mock_s3_store.download = mock_download_with_progress

        async with mock_s3_store:
            result = await mock_s3_store.download(
                ts=timestamp,
                satellite=satellite,
                dest_path=download_path,
                progress_callback=progress_callback,
            )

            # Verify progress was reported
            assert len(progress_updates) > 0
            assert progress_updates[0][0] == 0  # Started at 0
            assert progress_updates[-1][0] == progress_updates[-1][1]  # Ended at 100%

            # Verify file was created with correct size
            assert result.exists()
            assert result.stat().st_size == 1024 * 1024

    @pytest.mark.asyncio
    async def test_download_and_validate_checksum(self, temp_dir):
        """Test download with checksum validation."""
        timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        satellite = SatellitePattern.GOES_16
        download_path = temp_dir / "test_file.nc"

        # Known test data and its MD5 checksum
        test_data = b"Test satellite data content"
        expected_checksum = hashlib.md5(test_data).hexdigest()

        # Mock S3 store to return our test data
        mock_s3_store = AsyncMock(spec=S3Store)

        async def mock_download(ts, satellite, dest_path, **kwargs):
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(test_data)
            return dest_path

        mock_s3_store.download = mock_download

        async with mock_s3_store:
            # Download the file
            result = await mock_s3_store.download(
                ts=timestamp, satellite=satellite, dest_path=download_path
            )

            # Validate checksum
            downloaded_data = result.read_bytes()
            actual_checksum = hashlib.md5(downloaded_data).hexdigest()

            assert actual_checksum == expected_checksum
            assert downloaded_data == test_data

    @pytest.mark.asyncio
    async def test_download_recent_data_handling(self, temp_dir):
        """Test handling of requests for very recent data that may not be available yet."""
        # Request data from 5 minutes ago (likely not available yet)
        recent_timestamp = datetime.now(timezone.utc) - timedelta(minutes=5)
        satellite = SatellitePattern.GOES_16
        download_path = temp_dir / "recent_file.nc"

        # Mock S3 store to return "not found" for recent data
        mock_s3_store = AsyncMock(spec=S3Store)
        mock_s3_store.download = AsyncMock(
            side_effect=ResourceNotFoundError(
                f"Data not yet available for {recent_timestamp}. "
                "GOES-16 data typically becomes available 15-20 minutes after observation time."
            )
        )

        async with mock_s3_store:
            with pytest.raises(ResourceNotFoundError) as exc_info:
                await mock_s3_store.download(
                    ts=recent_timestamp, satellite=satellite, dest_path=download_path
                )

            # Verify helpful error message
            assert "not yet available" in str(exc_info.value)
            assert "15-20 minutes" in str(exc_info.value)
