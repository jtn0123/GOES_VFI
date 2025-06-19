"""Tests for the CompositeStore with fallback mechanisms."""

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from goesvfi.integrity_check.remote.base import ConnectionError as RemoteConnectionError
from goesvfi.integrity_check.remote.base import RemoteStoreError, ResourceNotFoundError
from goesvfi.integrity_check.remote.composite_store import (
    CompositeStore,
    DataSourceResult,
)
from goesvfi.integrity_check.time_index import SatellitePattern


class TestCompositeStore:
    """Test the CompositeStore fallback functionality."""

    @pytest.mark.asyncio
    async def test_composite_store_initialization(self):
        """Test CompositeStore initialization."""
        # Test with all sources enabled
        store = CompositeStore(
            enable_s3=True,
            enable_cdn=True,
            enable_cache=False,  # Cache not implemented yet
            timeout=30,
        )

        assert len(store.sources) == 2
        assert store.sources[0][0] == "S3"
        assert store.sources[1][0] == "CDN"
        assert store.timeout == 30

        # Test with only S3
        store_s3_only = CompositeStore(
            enable_s3=True,
            enable_cdn=False,
            enable_cache=False,
        )
        assert len(store_s3_only.sources) == 1
        assert store_s3_only.sources[0][0] == "S3"

        # Test error when no sources enabled
        with pytest.raises(ValueError, match="At least one data source"):
            CompositeStore(
                enable_s3=False,
                enable_cdn=False,
                enable_cache=False,
            )

    @pytest.mark.asyncio
    async def test_successful_download_from_s3(self):
        """Test successful download from primary S3 source."""
        store = CompositeStore(enable_s3=True, enable_cdn=True)

        # Mock S3 store to succeed
        mock_s3 = AsyncMock()
        mock_s3.download = AsyncMock(return_value=Path("/tmp/test_file.nc"))

        # Replace the S3 store
        store.sources[0] = ("S3", mock_s3)

        # Attempt download
        ts = datetime(2023, 6, 15, 12, 0)
        result = await store.download(
            ts=ts,
            satellite=SatellitePattern.GOES_16,
            dest_path=Path("/tmp/test_download.nc"),
        )

        # Verify S3 was called and CDN was not
        assert result == Path("/tmp/test_file.nc")
        mock_s3.download.assert_called_once()

        # Check statistics
        stats = store.source_stats["S3"]
        assert stats["attempts"] == 1
        assert stats["successes"] == 1
        assert stats["failures"] == 0
        assert stats["consecutive_failures"] == 0

    @pytest.mark.asyncio
    async def test_fallback_to_cdn_when_s3_fails(self):
        """Test fallback to CDN when S3 fails."""
        store = CompositeStore(enable_s3=True, enable_cdn=True)

        # Mock S3 to fail
        mock_s3 = AsyncMock()
        mock_s3.download = AsyncMock(
            side_effect=ResourceNotFoundError(
                message="File not found in S3", technical_details="404 error"
            )
        )

        # Mock CDN to succeed
        mock_cdn = AsyncMock()
        mock_cdn.download = AsyncMock(return_value=Path("/tmp/cdn_file.nc"))

        # Replace stores
        store.sources[0] = ("S3", mock_s3)
        store.sources[1] = ("CDN", mock_cdn)

        # Attempt download
        ts = datetime(2023, 6, 15, 12, 0)
        result = await store.download(
            ts=ts,
            satellite=SatellitePattern.GOES_16,
            dest_path=Path("/tmp/test_download.nc"),
        )

        # Verify both were called in order
        assert result == Path("/tmp/cdn_file.nc")
        mock_s3.download.assert_called_once()
        mock_cdn.download.assert_called_once()

        # Check statistics
        s3_stats = store.source_stats["S3"]
        assert s3_stats["attempts"] == 1
        assert s3_stats["failures"] == 1
        assert s3_stats["consecutive_failures"] == 1

        cdn_stats = store.source_stats["CDN"]
        assert cdn_stats["attempts"] == 1
        assert cdn_stats["successes"] == 1
        assert cdn_stats["consecutive_failures"] == 0

    @pytest.mark.asyncio
    async def test_all_sources_fail(self):
        """Test comprehensive error when all sources fail."""
        store = CompositeStore(enable_s3=True, enable_cdn=True)

        # Mock both to fail
        mock_s3 = AsyncMock()
        mock_s3.download = AsyncMock(
            side_effect=RemoteConnectionError(
                message="S3 connection timeout", technical_details="Network error"
            )
        )

        mock_cdn = AsyncMock()
        mock_cdn.download = AsyncMock(
            side_effect=ResourceNotFoundError(
                message="CDN file not found", technical_details="404 from CDN"
            )
        )

        # Replace stores
        store.sources[0] = ("S3", mock_s3)
        store.sources[1] = ("CDN", mock_cdn)

        # Attempt download should raise error
        ts = datetime(2023, 6, 15, 12, 0)
        with pytest.raises(RemoteStoreError) as exc_info:
            await store.download(
                ts=ts,
                satellite=SatellitePattern.GOES_16,
                dest_path=Path("/tmp/test_download.nc"),
            )

        # Check error message includes all sources
        error = exc_info.value
        error_msg = str(error)
        assert "All data sources failed" in error_msg
        assert "S3" in error_msg
        assert "CDN" in error_msg

        # Check technical details and troubleshooting
        if hasattr(error, "technical_details"):
            assert "Troubleshooting tips" in error.technical_details
            assert "Alternative data sources" in error.technical_details
        if hasattr(error, "troubleshooting_tips"):
            assert "Check your internet connection" in error.troubleshooting_tips

    @pytest.mark.asyncio
    async def test_source_priority_reordering(self):
        """Test that sources are reordered based on performance."""
        store = CompositeStore(
            enable_s3=True, enable_cdn=True, prefer_recent_success=True
        )

        # Simulate S3 having multiple failures
        store.source_stats["S3"]["attempts"] = 10
        store.source_stats["S3"]["failures"] = 8
        store.source_stats["S3"]["successes"] = 2
        store.source_stats["S3"]["consecutive_failures"] = 3
        store.source_stats["S3"]["total_time"] = 50.0  # Slow

        # Simulate CDN having good performance
        store.source_stats["CDN"]["attempts"] = 10
        store.source_stats["CDN"]["successes"] = 9
        store.source_stats["CDN"]["failures"] = 1
        store.source_stats["CDN"]["total_time"] = 20.0  # Fast

        # Get ordered sources
        ordered = store._get_ordered_sources()

        # CDN should be first due to better performance
        assert ordered[0][0] == "CDN"
        assert ordered[1][0] == "S3"

    def test_statistics_tracking(self):
        """Test statistics are properly tracked."""
        store = CompositeStore(enable_s3=True, enable_cdn=False)

        # Update stats for a successful operation
        store._update_stats("S3", success=True, elapsed_time=2.5)

        stats = store.source_stats["S3"]
        assert stats["attempts"] == 1
        assert stats["successes"] == 1
        assert stats["failures"] == 0
        assert stats["total_time"] == 2.5
        assert stats["consecutive_failures"] == 0
        assert stats["last_success"] is not None

        # Update stats for a failed operation
        store._update_stats("S3", success=False, elapsed_time=10.0)

        stats = store.source_stats["S3"]
        assert stats["attempts"] == 2
        assert stats["successes"] == 1
        assert stats["failures"] == 1
        assert stats["total_time"] == 12.5
        assert stats["consecutive_failures"] == 1
        assert stats["last_failure"] is not None

    def test_get_statistics(self):
        """Test getting formatted statistics."""
        store = CompositeStore(enable_s3=True, enable_cdn=True)

        # Set some stats
        store.source_stats["S3"]["attempts"] = 100
        store.source_stats["S3"]["successes"] = 85
        store.source_stats["S3"]["total_time"] = 250.0

        stats = store.get_statistics()

        assert "S3" in stats
        assert stats["S3"]["attempts"] == 100
        assert stats["S3"]["success_rate"] == "85.0%"
        assert stats["S3"]["average_time"] == "2.50s"

    def test_reset_statistics(self):
        """Test resetting statistics."""
        store = CompositeStore(enable_s3=True, enable_cdn=True)

        # Set some stats
        store.source_stats["S3"]["attempts"] = 50
        store.source_stats["S3"]["successes"] = 40

        # Reset
        store.reset_statistics()

        # Verify all reset
        for source_stats in store.source_stats.values():
            assert source_stats["attempts"] == 0
            assert source_stats["successes"] == 0
            assert source_stats["failures"] == 0
            assert source_stats["consecutive_failures"] == 0

    @pytest.mark.asyncio
    async def test_exists_checks_all_sources(self):
        """Test exists() checks all sources until one returns True."""
        store = CompositeStore(enable_s3=True, enable_cdn=True)

        # Mock S3 to return False
        mock_s3 = AsyncMock()
        mock_s3.exists = AsyncMock(return_value=False)

        # Mock CDN to return True
        mock_cdn = AsyncMock()
        mock_cdn.exists = AsyncMock(return_value=True)

        # Replace stores
        store.sources[0] = ("S3", mock_s3)
        store.sources[1] = ("CDN", mock_cdn)

        # Check existence
        ts = datetime(2023, 6, 15, 12, 0)
        exists = await store.exists(
            ts=ts,
            satellite=SatellitePattern.GOES_16,
        )

        assert exists is True
        mock_s3.exists.assert_called_once()
        mock_cdn.exists.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
