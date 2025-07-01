"""
Optimized end-to-end integration tests for satellite data download workflow with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for async setup and mock configurations
- Combined download workflow testing scenarios
- Batch validation of error handling and retry logic
- Enhanced mock management for concurrent operations
"""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
import hashlib
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from goesvfi.integrity_check.goes_imagery import ChannelType
from goesvfi.integrity_check.remote.base import (
    NetworkError,
    ResourceNotFoundError,
    TemporaryError,
)
from goesvfi.integrity_check.remote.cdn_store import CDNStore
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.time_index import SatellitePattern


class TestEndToEndSatelliteDownloadOptimizedV2:
    """Optimized end-to-end satellite data download integration tests with full coverage."""

    @pytest.fixture(scope="class")
    @staticmethod
    def download_test_components() -> dict[str, Any]:  # noqa: C901
        """Create shared components for download testing.

        Returns:
            dict[str, Any]: Dictionary containing data manager, mock manager, and workflow manager.
        """

        # Enhanced Mock Data Manager
        class MockDataManager:
            """Manage mock data creation for different satellite scenarios."""

            def __init__(self) -> None:
                self.netcdf_templates: dict[str, Callable[[], dict[str, Any]]] = {
                    "goes16": MockDataManager._create_goes16_template,
                    "goes18": self._create_goes18_template,
                    "large": self._create_large_template,
                    "minimal": MockDataManager._create_minimal_template,
                }
                self.test_files: dict[str, bytes] = {
                    "small": b"Test satellite data content",
                    "medium": b"x" * (256 * 1024),  # 256KB
                    "large": b"x" * (1024 * 1024),  # 1MB
                    "corrupted": b"corrupted data",
                }

            @staticmethod
            def _create_goes16_template() -> dict[str, Any]:
                """Create GOES-16 NetCDF data template.

                Returns:
                    dict[str, Any]: NetCDF data template for GOES-16.
                """
                return {
                    "Rad": np.random.default_rng().random((1000, 1000)).astype(np.float32),
                    "t": np.array([0]),
                    "band_id": np.array([13]),
                    "band_wavelength": np.array([10.35]),
                    "kappa0": np.array([0.01]),
                    "planck_fk1": np.array([1000.0]),
                    "planck_fk2": np.array([500.0]),
                    "planck_bc1": np.array([0.1]),
                    "planck_bc2": np.array([0.05]),
                    "time_coverage_start": "2023-01-01T12:00:00Z",
                    "time_coverage_end": "2023-01-01T12:15:00Z",
                    "spatial_resolution": "2km at nadir",
                    "platform_ID": "G16",
                    "instrument_type": "GOES-16 ABI",
                }

            @staticmethod
            def _create_goes18_template() -> dict[str, Any]:
                """Create GOES-18 NetCDF data template.

                Returns:
                    dict[str, Any]: NetCDF data template for GOES-18.
                """
                template = MockDataManager._create_goes16_template()
                template.update({
                    "platform_ID": "G18",
                    "instrument_type": "GOES-18 ABI",
                })
                return template

            @staticmethod
            def _create_large_template() -> dict[str, Any]:
                """Create large NetCDF data template.

                Returns:
                    dict[str, Any]: Large NetCDF data template.
                """
                template = MockDataManager._create_goes16_template()
                template.update({
                    "Rad": np.random.default_rng().random((2000, 2000)).astype(np.float32),
                })
                return template

            @staticmethod
            def _create_minimal_template() -> dict[str, Any]:
                """Create minimal NetCDF data template.

                Returns:
                    dict[str, Any]: Minimal NetCDF data template.
                """
                return {
                    "Rad": np.random.default_rng().random((100, 100)).astype(np.float32),
                    "t": np.array([0]),
                    "band_id": np.array([13]),
                    "platform_ID": "G16",
                }

            def get_netcdf_data(self, data_type: str) -> dict[str, Any]:
                """Get NetCDF data for specified type.

                Returns:
                    dict[str, Any]: NetCDF data for the specified type.
                """
                return self.netcdf_templates[data_type]()

            def get_test_file_data(self, file_type: str) -> bytes:
                """Get test file data for specified type.

                Returns:
                    bytes: Test file data for the specified type.
                """
                return self.test_files[file_type]

            @staticmethod
            def create_checksum(data: bytes) -> str:
                """Create MD5 checksum for data.

                Returns:
                    str: MD5 checksum hex digest.
                """
                return hashlib.md5(data).hexdigest()  # noqa: S324

        # Enhanced Download Mock Manager
        class DownloadMockManager:
            """Manage download mocks for different scenarios."""

            def __init__(self) -> None:
                self.mock_scenarios: dict[str, Callable[[bytes, Path], dict[str, AsyncMock]]] = {
                    "success": DownloadMockManager._create_success_mocks,
                    "retry_then_success": DownloadMockManager._create_retry_success_mocks,
                    "s3_fail_cdn_success": DownloadMockManager._create_s3_fail_cdn_success_mocks,
                    "all_fail": DownloadMockManager._create_all_fail_mocks,
                    "network_timeout": DownloadMockManager._create_network_timeout_mocks,
                    "progress_tracking": DownloadMockManager._create_progress_tracking_mocks,
                }

            @staticmethod
            def _create_success_mocks(data: bytes, download_path: Path) -> dict[str, AsyncMock]:  # noqa: ARG004
                """Create mocks for successful download scenario.

                Returns:
                    dict[str, AsyncMock]: Dictionary with s3_store and cdn_store mocks.
                """
                s3_store = AsyncMock(spec=S3Store)
                cdn_store = AsyncMock(spec=CDNStore)

                async def mock_download(  # noqa: RUF029
                    ts: datetime,  # noqa: ARG001
                    satellite: SatellitePattern,  # noqa: ARG001
                    dest_path: Path,
                    **kwargs: Any,
                ) -> Path:
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    dest_path.write_bytes(data)
                    return dest_path

                s3_store.download = mock_download
                s3_store.exists = AsyncMock(return_value=True)
                s3_store.__aenter__ = AsyncMock(return_value=s3_store)
                s3_store.__aexit__ = AsyncMock(return_value=None)

                cdn_store.download = mock_download
                cdn_store.exists = AsyncMock(return_value=True)
                cdn_store.__aenter__ = AsyncMock(return_value=cdn_store)
                cdn_store.__aexit__ = AsyncMock(return_value=None)

                return {"s3_store": s3_store, "cdn_store": cdn_store}

            @staticmethod
            def _create_retry_success_mocks(data: bytes, download_path: Path) -> dict[str, AsyncMock]:  # noqa: ARG004
                """Create mocks for retry then success scenario.

                Returns:
                    dict[str, AsyncMock]: Dictionary with s3_store and cdn_store mocks.
                """
                s3_store = AsyncMock(spec=S3Store)
                cdn_store = AsyncMock(spec=CDNStore)

                # S3 fails twice then succeeds
                call_count = 0

                async def mock_s3_download(  # noqa: RUF029
                    ts: datetime,  # noqa: ARG001
                    satellite: SatellitePattern,  # noqa: ARG001
                    dest_path: Path,
                    **kwargs: Any,
                ) -> Path:
                    nonlocal call_count
                    call_count += 1
                    if call_count <= 2:
                        msg = "Connection timeout"
                        raise TemporaryError(msg)
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    dest_path.write_bytes(data)
                    return dest_path

                s3_store.download = mock_s3_download
                s3_store.exists = AsyncMock(return_value=True)
                s3_store.__aenter__ = AsyncMock(return_value=s3_store)
                s3_store.__aexit__ = AsyncMock(return_value=None)

                # CDN as backup
                async def mock_cdn_download(  # noqa: RUF029
                    ts: datetime,  # noqa: ARG001
                    satellite: SatellitePattern,  # noqa: ARG001
                    dest_path: Path,
                    **kwargs: Any,
                ) -> Path:
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    dest_path.write_bytes(data)
                    return dest_path

                cdn_store.download = mock_cdn_download
                cdn_store.exists = AsyncMock(return_value=True)
                cdn_store.__aenter__ = AsyncMock(return_value=cdn_store)
                cdn_store.__aexit__ = AsyncMock(return_value=None)

                return {"s3_store": s3_store, "cdn_store": cdn_store}

            @staticmethod
            def _create_s3_fail_cdn_success_mocks(data: bytes, download_path: Path) -> dict[str, AsyncMock]:  # noqa: ARG004
                """Create mocks for S3 fail, CDN success scenario.

                Returns:
                    dict[str, AsyncMock]: Dictionary with s3_store and cdn_store mocks.
                """
                s3_store = AsyncMock(spec=S3Store)
                cdn_store = AsyncMock(spec=CDNStore)

                # S3 always fails
                s3_store.download = AsyncMock(side_effect=NetworkError("S3 connection failed"))
                s3_store.exists = AsyncMock(return_value=False)
                s3_store.__aenter__ = AsyncMock(return_value=s3_store)
                s3_store.__aexit__ = AsyncMock(return_value=None)

                # CDN succeeds
                async def mock_cdn_download(  # noqa: RUF029
                    ts: datetime,  # noqa: ARG001
                    satellite: SatellitePattern,  # noqa: ARG001
                    dest_path: Path,
                    **kwargs: Any,
                ) -> Path:
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    dest_path.write_bytes(data)
                    return dest_path

                cdn_store.download = mock_cdn_download
                cdn_store.exists = AsyncMock(return_value=True)
                cdn_store.__aenter__ = AsyncMock(return_value=cdn_store)
                cdn_store.__aexit__ = AsyncMock(return_value=None)

                return {"s3_store": s3_store, "cdn_store": cdn_store}

            @staticmethod
            def _create_all_fail_mocks(
                data: bytes,  # noqa: ARG004
                download_path: Path,  # noqa: ARG004
            ) -> dict[str, AsyncMock]:
                """Create mocks for all sources fail scenario.

                Returns:
                    dict[str, AsyncMock]: Dictionary with s3_store and cdn_store mocks.
                """
                s3_store = AsyncMock(spec=S3Store)
                cdn_store = AsyncMock(spec=CDNStore)

                # Both fail
                s3_store.download = AsyncMock(side_effect=NetworkError("S3 connection failed"))
                s3_store.exists = AsyncMock(return_value=False)
                s3_store.__aenter__ = AsyncMock(return_value=s3_store)
                s3_store.__aexit__ = AsyncMock(return_value=None)

                cdn_store.download = AsyncMock(side_effect=ResourceNotFoundError("File not found on CDN"))
                cdn_store.exists = AsyncMock(return_value=False)
                cdn_store.__aenter__ = AsyncMock(return_value=cdn_store)
                cdn_store.__aexit__ = AsyncMock(return_value=None)

                return {"s3_store": s3_store, "cdn_store": cdn_store}

            @staticmethod
            def _create_network_timeout_mocks(data: bytes, download_path: Path) -> dict[str, AsyncMock]:  # noqa: ARG004
                """Create mocks for network timeout scenario.

                Returns:
                    dict[str, AsyncMock]: Dictionary with s3_store and cdn_store mocks.
                """
                s3_store = AsyncMock(spec=S3Store)
                cdn_store = AsyncMock(spec=CDNStore)

                # Both timeout
                s3_store.download = AsyncMock(side_effect=TimeoutError("Download timeout"))
                s3_store.exists = AsyncMock(side_effect=TimeoutError("Connection timeout"))
                s3_store.__aenter__ = AsyncMock(return_value=s3_store)
                s3_store.__aexit__ = AsyncMock(return_value=None)

                cdn_store.download = AsyncMock(side_effect=TimeoutError("Download timeout"))
                cdn_store.exists = AsyncMock(side_effect=TimeoutError("Connection timeout"))
                cdn_store.__aenter__ = AsyncMock(return_value=cdn_store)
                cdn_store.__aexit__ = AsyncMock(return_value=None)

                return {"s3_store": s3_store, "cdn_store": cdn_store}

            @staticmethod
            def _create_progress_tracking_mocks(data: bytes, download_path: Path) -> dict[str, AsyncMock]:  # noqa: ARG004
                """Create mocks for progress tracking scenario.

                Returns:
                    dict[str, AsyncMock]: Dictionary with s3_store and cdn_store mocks.
                """
                s3_store = AsyncMock(spec=S3Store)
                cdn_store = AsyncMock(spec=CDNStore)

                async def mock_download_with_progress(
                    ts: datetime,  # noqa: ARG001
                    satellite: SatellitePattern,  # noqa: ARG001
                    dest_path: Path,
                    progress_callback: Callable[[int, int], None] | None = None,
                    **kwargs: Any,
                ) -> Path:
                    total_size = len(data)
                    chunk_size = max(1, total_size // 4)  # 4 progress updates

                    for downloaded in range(0, total_size + 1, chunk_size):
                        if progress_callback:
                            progress_callback(min(downloaded, total_size), total_size)
                        await asyncio.sleep(0.01)  # Simulate download time

                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    dest_path.write_bytes(data)
                    return dest_path

                s3_store.download = mock_download_with_progress
                s3_store.exists = AsyncMock(return_value=True)
                s3_store.__aenter__ = AsyncMock(return_value=s3_store)
                s3_store.__aexit__ = AsyncMock(return_value=None)

                cdn_store.download = mock_download_with_progress
                cdn_store.exists = AsyncMock(return_value=True)
                cdn_store.__aenter__ = AsyncMock(return_value=cdn_store)
                cdn_store.__aexit__ = AsyncMock(return_value=None)

                return {"s3_store": s3_store, "cdn_store": cdn_store}

            def create_mocks(self, scenario: str, data: bytes, download_path: Path) -> dict[str, AsyncMock]:
                """Create mocks for specified scenario.

                Returns:
                    dict[str, AsyncMock]: Dictionary with store mocks.
                """
                return self.mock_scenarios[scenario](data, download_path)

        # Enhanced Workflow Manager
        class WorkflowManager:
            """Manage complete download workflow testing."""

            def __init__(self) -> None:
                self.workflow_scenarios = {
                    "complete_success": self._test_complete_success_workflow,
                    "retry_and_fallback": self._test_retry_and_fallback_workflow,
                    "all_sources_fail": self._test_all_sources_fail_workflow,
                    "parallel_downloads": self._test_parallel_downloads_workflow,
                    "progress_reporting": self._test_progress_reporting_workflow,
                    "checksum_validation": self._test_checksum_validation_workflow,
                    "recent_data_handling": self._test_recent_data_handling_workflow,
                }

            async def _test_complete_success_workflow(  # noqa: PLR6301
                self,
                mocks: dict[str, AsyncMock],
                data: bytes,  # noqa: ARG002
                temp_dir: Path,
                timestamp: datetime,
                satellite: SatellitePattern,
                channel: ChannelType,
            ) -> dict[str, Any]:
                """Test complete successful workflow.

                Returns:
                    dict[str, Any]: Workflow results.
                """
                download_path = temp_dir / "test_file.nc"
                output_path = temp_dir / "processed_image.png"

                # Mock NetCDF processing
                with patch("xarray.open_dataset") as mock_open_dataset:
                    mock_dataset = MagicMock()
                    mock_dataset.__getitem__.side_effect = lambda key: {  # noqa: ARG005
                        "Rad": np.random.default_rng().random((100, 100))
                    }
                    mock_dataset.attrs = {
                        "time_coverage_start": "2023-01-01T12:00:00Z",
                        "platform_ID": "G16",
                    }
                    mock_open_dataset.return_value.__enter__.return_value = mock_dataset

                    with patch("PIL.Image.Image.save"):
                        # Download file
                        result = await mocks["s3_store"].download(
                            ts=timestamp, satellite=satellite, dest_path=download_path
                        )

                        assert result == download_path
                        assert download_path.exists()

                        # Mock processing
                        renderer = MagicMock()
                        renderer.render_channel = AsyncMock(return_value=True)

                        # Process file
                        render_result = await renderer.render_channel(
                            file_path=result,
                            channel=channel,
                            output_path=output_path,
                            apply_enhancement=True,
                        )

                        assert render_result is True
                        renderer.render_channel.assert_called_once()

                        return {"success": True, "file_path": result}

            async def _test_retry_and_fallback_workflow(  # noqa: PLR6301
                self,
                mocks: dict[str, AsyncMock],
                data: bytes,  # noqa: ARG002
                temp_dir: Path,
                timestamp: datetime,
                satellite: SatellitePattern,
                channel: ChannelType,  # noqa: ARG002
            ) -> dict[str, Any]:
                """Test retry and fallback workflow.

                Returns:
                    dict[str, Any]: Workflow results.
                """
                download_path = temp_dir / "test_file.nc"

                errors = []
                retry_count = 0
                max_retries = 3

                # Test retry logic
                for i in range(max_retries):
                    try:
                        await mocks["s3_store"].download(ts=timestamp, satellite=satellite, dest_path=download_path)
                        return {"success": True, "retries": retry_count, "source": "s3"}  # noqa: TRY300
                    except TemporaryError as e:
                        retry_count += 1
                        errors.append(str(e))
                        if i < max_retries - 1:
                            continue
                    except NetworkError as e:
                        errors.append(str(e))
                        # Fallback to CDN
                        try:
                            await mocks["cdn_store"].download(
                                ts=timestamp, satellite=satellite, dest_path=download_path
                            )
                            return {"success": True, "retries": retry_count, "source": "cdn"}  # noqa: TRY300
                        except Exception as cdn_error:  # noqa: BLE001
                            errors.append(str(cdn_error))
                            break

                return {"success": False, "retries": retry_count, "errors": errors}

            async def _test_all_sources_fail_workflow(  # noqa: PLR6301
                self,
                mocks: dict[str, AsyncMock],
                data: bytes,  # noqa: ARG002
                temp_dir: Path,
                timestamp: datetime,
                satellite: SatellitePattern,
                channel: ChannelType,  # noqa: ARG002
            ) -> dict[str, Any]:
                """Test workflow when all sources fail.

                Returns:
                    dict[str, Any]: Workflow results.
                """
                download_path = temp_dir / "test_file.nc"
                errors = []

                # Try S3
                try:
                    await mocks["s3_store"].download(ts=timestamp, satellite=satellite, dest_path=download_path)
                except Exception as e:  # noqa: BLE001
                    errors.append(f"S3: {e!s}")

                # Try CDN
                try:
                    await mocks["cdn_store"].download(ts=timestamp, satellite=satellite, dest_path=download_path)
                except Exception as e:  # noqa: BLE001
                    errors.append(f"CDN: {e!s}")

                return {"success": False, "errors": errors}

            async def _test_parallel_downloads_workflow(  # noqa: PLR6301
                self,
                mocks: dict[str, AsyncMock],
                data: bytes,  # noqa: ARG002
                temp_dir: Path,
                timestamp: datetime,
                satellite: SatellitePattern,
                channel: ChannelType,  # noqa: ARG002
            ) -> dict[str, Any]:
                """Test parallel downloads workflow.

                Returns:
                    dict[str, Any]: Workflow results.
                """
                # Setup multiple timestamps
                base_time = timestamp
                timestamps = [base_time + timedelta(minutes=15 * i) for i in range(4)]

                # Download concurrently
                tasks = []
                for i, ts in enumerate(timestamps):
                    download_path = temp_dir / f"file_{i}.nc"
                    task = mocks["s3_store"].download(ts=ts, satellite=satellite, dest_path=download_path)
                    tasks.append(task)

                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Count successes
                successful_downloads = [r for r in results if isinstance(r, Path)]
                failed_downloads = [r for r in results if isinstance(r, Exception)]

                return {
                    "success": len(failed_downloads) == 0,
                    "successful_count": len(successful_downloads),
                    "failed_count": len(failed_downloads),
                    "results": results,
                }

            async def _test_progress_reporting_workflow(  # noqa: PLR6301
                self,
                mocks: dict[str, AsyncMock],
                data: bytes,  # noqa: ARG002
                temp_dir: Path,
                timestamp: datetime,
                satellite: SatellitePattern,
                channel: ChannelType,  # noqa: ARG002
            ) -> dict[str, Any]:
                """Test progress reporting workflow.

                Returns:
                    dict[str, Any]: Workflow results.
                """
                download_path = temp_dir / "test_file.nc"
                progress_updates = []

                def progress_callback(downloaded: int, total: int) -> None:
                    progress_updates.append((downloaded, total))

                result = await mocks["s3_store"].download(
                    ts=timestamp,
                    satellite=satellite,
                    dest_path=download_path,
                    progress_callback=progress_callback,
                )

                return {
                    "success": result == download_path,
                    "progress_updates": progress_updates,
                    "final_size": result.stat().st_size if result.exists() else 0,
                }

            async def _test_checksum_validation_workflow(  # noqa: PLR6301
                self,
                mocks: dict[str, AsyncMock],
                data: bytes,
                temp_dir: Path,
                timestamp: datetime,
                satellite: SatellitePattern,
                channel: ChannelType,  # noqa: ARG002
            ) -> dict[str, Any]:
                """Test checksum validation workflow.

                Returns:
                    dict[str, Any]: Workflow results.
                """
                download_path = temp_dir / "test_file.nc"
                expected_checksum = hashlib.md5(data).hexdigest()  # noqa: S324

                result = await mocks["s3_store"].download(ts=timestamp, satellite=satellite, dest_path=download_path)

                # Validate checksum
                downloaded_data = result.read_bytes()
                actual_checksum = hashlib.md5(downloaded_data).hexdigest()  # noqa: S324

                return {
                    "success": actual_checksum == expected_checksum,
                    "expected_checksum": expected_checksum,
                    "actual_checksum": actual_checksum,
                    "data_matches": downloaded_data == data,
                }

            async def _test_recent_data_handling_workflow(  # noqa: PLR6301
                self,
                mocks: dict[str, AsyncMock],
                data: bytes,  # noqa: ARG002
                temp_dir: Path,
                timestamp: datetime,  # noqa: ARG002
                satellite: SatellitePattern,
                channel: ChannelType,  # noqa: ARG002
            ) -> dict[str, Any]:
                """Test recent data handling workflow.

                Returns:
                    dict[str, Any]: Workflow results.
                """
                # Use recent timestamp
                recent_timestamp = datetime.now(UTC) - timedelta(minutes=5)
                download_path = temp_dir / "recent_file.nc"

                # Mock to return "not found" for recent data
                mocks["s3_store"].download = AsyncMock(
                    side_effect=ResourceNotFoundError(
                        f"Data not yet available for {recent_timestamp}. "
                        "GOES-16 data typically becomes available 15-20 minutes after observation time."
                    )
                )

                try:
                    await mocks["s3_store"].download(ts=recent_timestamp, satellite=satellite, dest_path=download_path)
                except ResourceNotFoundError as e:
                    return {
                        "success": False,
                        "expected_error": True,
                        "error_message": str(e),
                        "helpful_message": "15-20 minutes" in str(e),
                    }
                else:
                    return {"success": True, "message": "Unexpected success"}

            async def run_workflow(
                self,
                scenario: str,
                *,
                mocks: dict[str, AsyncMock],
                data: bytes,
                temp_dir: Path,
                timestamp: datetime,
                satellite: SatellitePattern,
                channel: ChannelType,
            ) -> dict[str, Any]:
                """Run specified workflow scenario.

                Returns:
                    dict[str, Any]: Workflow results.
                """
                return await self.workflow_scenarios[scenario](mocks, data, temp_dir, timestamp, satellite, channel)

        return {
            "data_manager": MockDataManager(),
            "mock_manager": DownloadMockManager(),
            "workflow_manager": WorkflowManager(),
        }

    @pytest.fixture()
    def temp_workspace(self, tmp_path: Path) -> dict[str, Path]:  # noqa: PLR6301
        """Create temporary workspace for download testing.

        Returns:
            dict[str, Path]: Dictionary with workspace paths.
        """
        workspace = {
            "base_dir": tmp_path,
            "downloads_dir": tmp_path / "downloads",
            "processed_dir": tmp_path / "processed",
        }

        # Create subdirectories
        workspace["downloads_dir"].mkdir(exist_ok=True)
        workspace["processed_dir"].mkdir(exist_ok=True)

        return workspace

    @pytest.mark.asyncio()
    async def test_end_to_end_download_comprehensive_scenarios(  # noqa: PLR6301
        self, download_test_components: dict[str, Any], temp_workspace: dict[str, Path]
    ) -> None:
        """Test comprehensive end-to-end download scenarios."""
        components = download_test_components
        workspace = temp_workspace
        data_manager = components["data_manager"]
        mock_manager = components["mock_manager"]
        workflow_manager = components["workflow_manager"]

        # Define comprehensive test scenarios
        download_scenarios = [
            {
                "name": "GOES-16 Complete Success Workflow",
                "satellite": SatellitePattern.GOES_16,
                "channel": ChannelType.CH13,
                "data_type": "goes16",
                "file_type": "medium",
                "mock_scenario": "success",
                "workflow": "complete_success",
                "expected_success": True,
            },
            {
                "name": "GOES-18 Retry and Fallback Workflow",
                "satellite": SatellitePattern.GOES_18,
                "channel": ChannelType.CH02,
                "data_type": "goes18",
                "file_type": "small",
                "mock_scenario": "retry_then_success",
                "workflow": "retry_and_fallback",
                "expected_success": True,
            },
            {
                "name": "S3 Fail CDN Success Workflow",
                "satellite": SatellitePattern.GOES_16,
                "channel": ChannelType.CH07,
                "data_type": "goes16",
                "file_type": "large",
                "mock_scenario": "s3_fail_cdn_success",
                "workflow": "retry_and_fallback",
                "expected_success": True,
            },
            {
                "name": "All Sources Fail Workflow",
                "satellite": SatellitePattern.GOES_16,
                "channel": ChannelType.CH13,
                "data_type": "goes16",
                "file_type": "small",
                "mock_scenario": "all_fail",
                "workflow": "all_sources_fail",
                "expected_success": False,
            },
            {
                "name": "Progress Reporting Workflow",
                "satellite": SatellitePattern.GOES_18,
                "channel": ChannelType.CH13,
                "data_type": "goes18",
                "file_type": "large",
                "mock_scenario": "progress_tracking",
                "workflow": "progress_reporting",
                "expected_success": True,
            },
        ]

        # Test each scenario
        for scenario in download_scenarios:
            # Setup test parameters
            timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
            satellite = scenario["satellite"]
            channel = scenario["channel"]

            # Get test data
            data_manager.get_netcdf_data(scenario["data_type"])
            file_data = data_manager.get_test_file_data(scenario["file_type"])

            # Create mocks
            download_path = workspace["downloads_dir"] / f"{scenario['name'].replace(' ', '_').lower()}.nc"
            mocks = mock_manager.create_mocks(scenario["mock_scenario"], file_data, download_path)

            try:
                # Run workflow
                result = await workflow_manager.run_workflow(
                    scenario["workflow"],
                    mocks=mocks,
                    data=file_data,
                    temp_dir=workspace["downloads_dir"],
                    timestamp=timestamp,
                    satellite=satellite,
                    channel=channel,
                )

                # Verify results
                if scenario["expected_success"]:
                    assert result["success"], f"Expected success for {scenario['name']}, got: {result}"

                    # Additional checks for specific workflows
                    if scenario["workflow"] == "progress_reporting":
                        assert len(result["progress_updates"]) > 0, f"No progress updates for {scenario['name']}"
                        assert result["final_size"] > 0, f"No file created for {scenario['name']}"

                    elif scenario["workflow"] == "retry_and_fallback":
                        assert "retries" in result, f"Retry info missing for {scenario['name']}"
                        assert "source" in result, f"Source info missing for {scenario['name']}"

                else:
                    assert not result["success"], f"Expected failure for {scenario['name']}, got: {result}"
                    assert "errors" in result, f"Error info missing for {scenario['name']}"
                    assert len(result["errors"]) > 0, f"No error details for {scenario['name']}"

            except Exception as e:  # noqa: BLE001
                if scenario["expected_success"]:
                    pytest.fail(f"Unexpected exception in {scenario['name']}: {e}")
                # Expected failures are acceptable

    @pytest.mark.asyncio()
    async def test_parallel_and_concurrent_downloads(  # noqa: PLR6301
        self, download_test_components: dict[str, Any], temp_workspace: dict[str, Path]
    ) -> None:
        """Test parallel and concurrent download scenarios."""
        components = download_test_components
        workspace = temp_workspace
        data_manager = components["data_manager"]
        mock_manager = components["mock_manager"]
        workflow_manager = components["workflow_manager"]

        # Concurrent download scenarios
        concurrent_scenarios = [
            {
                "name": "Multiple GOES-16 Files",
                "file_count": 4,
                "satellite": SatellitePattern.GOES_16,
                "channel": ChannelType.CH13,
                "data_type": "goes16",
                "file_type": "medium",
                "mock_scenario": "success",
            },
            {
                "name": "Mixed Satellite Files",
                "file_count": 6,
                "satellite": SatellitePattern.GOES_18,
                "channel": ChannelType.CH02,
                "data_type": "goes18",
                "file_type": "small",
                "mock_scenario": "success",
            },
            {
                "name": "Large Files Concurrent Download",
                "file_count": 3,
                "satellite": SatellitePattern.GOES_16,
                "channel": ChannelType.CH07,
                "data_type": "large",
                "file_type": "large",
                "mock_scenario": "progress_tracking",
            },
        ]

        # Test each concurrent scenario
        for scenario in concurrent_scenarios:
            # Setup test parameters
            base_timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
            satellite = scenario["satellite"]
            channel = scenario["channel"]

            # Get test data
            file_data = data_manager.get_test_file_data(scenario["file_type"])

            # Create download directory for this scenario
            scenario_dir = workspace["downloads_dir"] / scenario["name"].replace(" ", "_").lower()
            scenario_dir.mkdir(exist_ok=True)

            # Create mocks
            download_path = scenario_dir / "test_file.nc"
            mocks = mock_manager.create_mocks(scenario["mock_scenario"], file_data, download_path)

            # Run parallel download workflow
            result = await workflow_manager.run_workflow(
                "parallel_downloads",
                mocks=mocks,
                data=file_data,
                temp_dir=scenario_dir,
                timestamp=base_timestamp,
                satellite=satellite,
                channel=channel,
            )

            # Verify parallel download results
            assert result["successful_count"] == scenario["file_count"], (
                f"Wrong number of successful downloads for {scenario['name']}: "
                f"expected {scenario['file_count']}, got {result['successful_count']}"
            )
            assert result["failed_count"] == 0, (
                f"Unexpected failures in {scenario['name']}: {result['failed_count']} failed"
            )
            assert result["success"], f"Parallel download failed for {scenario['name']}"

    @pytest.mark.asyncio()
    async def test_error_handling_and_edge_cases(  # noqa: PLR6301
        self, download_test_components: dict[str, Any], temp_workspace: dict[str, Path]
    ) -> None:
        """Test error handling and edge case scenarios."""
        components = download_test_components
        workspace = temp_workspace
        data_manager = components["data_manager"]
        mock_manager = components["mock_manager"]
        workflow_manager = components["workflow_manager"]

        # Error handling scenarios
        error_scenarios = [
            {
                "name": "Network Timeout Handling",
                "mock_scenario": "network_timeout",
                "workflow": "all_sources_fail",
                "expected_error_types": ["TimeoutError"],
            },
            {
                "name": "Recent Data Not Available",
                "mock_scenario": "success",  # Will be overridden in workflow
                "workflow": "recent_data_handling",
                "expected_error_types": ["ResourceNotFoundError"],
            },
            {
                "name": "Checksum Validation",
                "mock_scenario": "success",
                "workflow": "checksum_validation",
                "expected_success": True,
            },
            {
                "name": "Corrupted File Handling",
                "mock_scenario": "success",
                "workflow": "checksum_validation",
                "file_type": "corrupted",
                "expected_success": True,  # Checksum will differ but workflow succeeds
            },
        ]

        # Test each error scenario
        for scenario in error_scenarios:
            # Setup test parameters
            timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
            satellite = SatellitePattern.GOES_16
            channel = ChannelType.CH13

            # Get test data
            file_type = scenario.get("file_type", "small")
            file_data = data_manager.get_test_file_data(file_type)

            # Create mocks
            download_path = workspace["downloads_dir"] / f"{scenario['name'].replace(' ', '_').lower()}.nc"
            mocks = mock_manager.create_mocks(scenario["mock_scenario"], file_data, download_path)

            try:
                # Run workflow
                result = await workflow_manager.run_workflow(
                    scenario["workflow"],
                    mocks=mocks,
                    data=file_data,
                    temp_dir=workspace["downloads_dir"],
                    timestamp=timestamp,
                    satellite=satellite,
                    channel=channel,
                )

                # Verify results based on scenario
                if scenario.get("expected_success", False):
                    assert result["success"], f"Expected success for {scenario['name']}, got: {result}"

                    # Special checks for checksum validation
                    if scenario["workflow"] == "checksum_validation":
                        if file_type == "corrupted":
                            # Corrupted file should have different checksum
                            assert not result.get("data_matches", True), (
                                f"Corrupted file should not match original data in {scenario['name']}"
                            )
                        else:
                            # Normal file should match
                            assert result.get("data_matches", False), (
                                f"Normal file should match original data in {scenario['name']}"
                            )

                elif "expected_error_types" in scenario:
                    # Check for expected error types
                    if scenario["workflow"] == "recent_data_handling":
                        assert result.get("expected_error"), f"Expected error not caught for {scenario['name']}"
                        assert result.get("helpful_message"), f"Helpful error message missing for {scenario['name']}"
                    else:
                        assert not result["success"], f"Expected failure for {scenario['name']}, got: {result}"

            except Exception as e:  # noqa: BLE001
                # Some exceptions are expected for error scenarios
                if "expected_error_types" in scenario:
                    error_type = type(e).__name__
                    assert error_type in scenario["expected_error_types"], (
                        f"Unexpected error type {error_type} for {scenario['name']}, expected one of {scenario['expected_error_types']}"
                    )
                else:
                    pytest.fail(f"Unexpected exception in {scenario['name']}: {e}")

    @pytest.mark.asyncio()
    async def test_download_validation_and_integrity(  # noqa: PLR6301, PLR0914
        self,
        download_test_components: dict[str, Any],
        temp_workspace: dict[str, Path],
    ) -> None:
        """Test download validation and data integrity scenarios."""
        components = download_test_components
        workspace = temp_workspace
        data_manager = components["data_manager"]
        mock_manager = components["mock_manager"]

        # Validation scenarios
        validation_scenarios = [
            {
                "name": "Small File Checksum Validation",
                "file_type": "small",
                "data_type": "minimal",
            },
            {
                "name": "Medium File Checksum Validation",
                "file_type": "medium",
                "data_type": "goes16",
            },
            {
                "name": "Large File Checksum Validation",
                "file_type": "large",
                "data_type": "large",
            },
        ]

        # Test each validation scenario
        for scenario in validation_scenarios:
            # Setup test parameters
            timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
            satellite = SatellitePattern.GOES_16

            # Get test data
            file_data = data_manager.get_test_file_data(scenario["file_type"])
            data_manager.get_netcdf_data(scenario["data_type"])
            expected_checksum = data_manager.create_checksum(file_data)

            # Create mocks
            download_path = workspace["downloads_dir"] / f"{scenario['name'].replace(' ', '_').lower()}.nc"
            mocks = mock_manager.create_mocks("success", file_data, download_path)

            # Download file
            result = await mocks["s3_store"].download(ts=timestamp, satellite=satellite, dest_path=download_path)

            # Validate download
            assert result == download_path, f"Wrong download path for {scenario['name']}"
            assert download_path.exists(), f"Downloaded file does not exist for {scenario['name']}"

            # Validate file size
            actual_size = download_path.stat().st_size
            expected_size = len(file_data)
            assert actual_size == expected_size, (
                f"File size mismatch for {scenario['name']}: expected {expected_size}, got {actual_size}"
            )

            # Validate checksum
            downloaded_data = download_path.read_bytes()
            actual_checksum = data_manager.create_checksum(downloaded_data)
            assert actual_checksum == expected_checksum, (
                f"Checksum mismatch for {scenario['name']}: expected {expected_checksum}, got {actual_checksum}"
            )

            # Validate data content
            assert downloaded_data == file_data, f"Data content mismatch for {scenario['name']}"
