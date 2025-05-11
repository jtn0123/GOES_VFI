"""
Unit tests for the enhanced progress reporting functionality.

This module tests the enhanced progress reporting capabilities of the
ReconcileManager, ensuring proper step-based and phase-based progress
messages are generated.
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from goesvfi.integrity_check.cache_db import CacheDB
from goesvfi.integrity_check.reconcile_manager import ReconcileManager
from goesvfi.integrity_check.time_index import SatellitePattern


class TestProgressReporting:
    """Test suite for the enhanced progress reporting functionality."""

    @pytest.fixture
    def mock_cache_db(self):
        """Create a mock CacheDB for testing."""
        mock_db = AsyncMock(spec=CacheDB)
        # Configure mock behavior
        mock_db.get_timestamps.return_value = set()
        mock_db.add_timestamp.return_value = None
        return mock_db

    @pytest.fixture
    def mock_cdn_store(self):
        """Create a mock CDN store for testing."""
        mock_store = AsyncMock()
        # Configure basic mock behavior
        mock_store.__aenter__.return_value = mock_store
        mock_store.__aexit__.return_value = None
        mock_store.exists.return_value = False
        mock_store.download.return_value = Path("/fake/path/image.png")
        return mock_store

    @pytest.fixture
    def mock_s3_store(self):
        """Create a mock S3 store for testing."""
        mock_store = AsyncMock()
        # Configure basic mock behavior
        mock_store.__aenter__.return_value = mock_store
        mock_store.__aexit__.return_value = None
        mock_store.exists.return_value = False
        mock_store.download.return_value = Path("/fake/path/image.nc")
        return mock_store

    @pytest.fixture
    def reconcile_manager(self, mock_cache_db, mock_cdn_store, mock_s3_store):
        """Create a ReconcileManager instance for testing."""
        return ReconcileManager(
            cache_db=mock_cache_db,
            base_dir="/fake/path",
            cdn_store=mock_cdn_store,
            s3_store=mock_s3_store,
            max_concurrency=1,  # Use 1 for predictable testing
        )

    @pytest.fixture
    def test_dates(self):
        """Create test date range for testing."""
        now = datetime.now()
        start_date = now - timedelta(days=1)
        end_date = now
        return start_date, end_date

    @pytest.mark.asyncio
    async def test_scan_directory_progress_reporting(
        self, reconcile_manager, test_dates, tmp_path
    ):
        """Test progress reporting during scan_directory method."""
        # Setup test parameters
        start_date, end_date = test_dates
        satellite = SatellitePattern.GOES_16
        interval_minutes = 30
        directory = tmp_path

        # Capture progress callbacks with a collector
        progress_messages = []
        progress_steps = []

        def progress_callback(current, total, message):
            progress_messages.append(message)
            progress_steps.append((current, total))

        # Execute the method
        await reconcile_manager.scan_directory(
            directory=directory,
            satellite=satellite,
            start_time=start_date,
            end_time=end_date,
            interval_minutes=interval_minutes,
            progress_callback=progress_callback,
        )

        # Assertions for step-based progress reporting
        assert any(
            "Step 1/5" in msg for msg in progress_messages
        ), "Step 1 message not found"
        assert any(
            "Step 2/5" in msg for msg in progress_messages
        ), "Step 2 message not found"
        assert any(
            "Step 3/5" in msg for msg in progress_messages
        ), "Step 3 message not found"
        assert any(
            "Step 4/5" in msg for msg in progress_messages
        ), "Step 4 message not found"
        assert any(
            "Step 5/5" in msg for msg in progress_messages
        ), "Step 5 message not found"

        # Ensure step messages contain useful information
        assert any("Generating expected timestamps" in msg for msg in progress_messages)
        assert any("Checking cache" in msg for msg in progress_messages)
        assert any("Checking filesystem" in msg for msg in progress_messages)
        assert any("Finalizing" in msg for msg in progress_messages)
        assert any("Scan complete" in msg for msg in progress_messages)

        # Check progressive step numbers
        step_values = [step[0] for step in progress_steps]
        # We should start from 0 and increase
        assert 0 in step_values, "Progress reporting should start from step 0"
        # Should end with step 5 (complete)
        assert 5 in step_values, "Progress reporting should end with step 5"

    @pytest.mark.asyncio
    async def test_fetch_missing_files_progress_reporting(
        self, reconcile_manager, test_dates
    ):
        """Test progress reporting during fetch_missing_files method."""
        # Setup test parameters
        start_date, end_date = test_dates
        satellite = SatellitePattern.GOES_16

        # Create a set of test timestamps (3 recent, 2 old)
        mock_timestamps = set()
        now = datetime.now()

        # Add recent timestamps (for CDN)
        for i in range(3):
            mock_timestamps.add(now - timedelta(hours=i))

        # Add older timestamps (for S3)
        for i in range(2):
            mock_timestamps.add(now - timedelta(days=30) - timedelta(hours=i))

        # Mock the _is_recent method to classify our test timestamps
        async def mock_is_recent(ts):
            return (now - ts) < timedelta(days=7)

        reconcile_manager._is_recent = mock_is_recent

        # Configure store mocks to return True for exists
        reconcile_manager.cdn_store.exists.return_value = True
        reconcile_manager.s3_store.exists.return_value = True

        # Capture progress callbacks with a collector
        progress_messages = []
        progress_steps = []

        def progress_callback(current, total, message):
            progress_messages.append(message)
            progress_steps.append((current, total))

        # Execute the method
        await reconcile_manager.fetch_missing_files(
            missing_timestamps=mock_timestamps,
            satellite=satellite,
            progress_callback=progress_callback,
        )

        # Assertions for step-based progress reporting
        assert any(
            "Step 1/4" in msg for msg in progress_messages
        ), "Step 1 message not found"
        assert any(
            "Step 2/4" in msg for msg in progress_messages
        ), "Step 2 message not found"
        assert any(
            "Step 3/4" in msg for msg in progress_messages
        ), "Step 3 message not found"
        assert any(
            "Step 4/4" in msg for msg in progress_messages
        ), "Step 4 message not found"

        # Ensure step messages contain useful information
        assert any("Analyzing missing files" in msg for msg in progress_messages)
        assert any("Preparing download strategy" in msg for msg in progress_messages)
        assert any("from CDN" in msg for msg in progress_messages)
        assert any("from S3" in msg for msg in progress_messages)
        assert any("Download complete" in msg for msg in progress_messages)

        # Check source-specific messages
        assert any("CDN" in msg for msg in progress_messages)
        assert any("S3" in msg for msg in progress_messages)

        # Check for item counts in progress messages
        assert any(
            "(1/" in msg for msg in progress_messages
        ), "Item count indicators not found"

    @pytest.mark.asyncio
    async def test_reconcile_phase_based_progress(
        self, reconcile_manager, test_dates, tmp_path
    ):
        """Test phase-based progress reporting in the reconcile method."""
        # Setup test parameters
        start_date, end_date = test_dates
        satellite = SatellitePattern.GOES_16
        interval_minutes = 30
        directory = tmp_path

        # Capture progress callbacks with a collector
        progress_messages = []
        progress_phases = []

        def progress_callback(current, total, message):
            progress_messages.append(message)
            progress_phases.append((current, total))

        # Configure store mocks to return True for exists (for one file)
        reconcile_manager.cdn_store.exists.return_value = True
        reconcile_manager._is_recent = AsyncMock(
            return_value=True
        )  # All files are "recent" for CDN

        # Mock scan_directory to return a fixed result
        orig_scan_directory = reconcile_manager.scan_directory

        async def mock_scan_directory(*args, **kwargs):
            # Call the original with the progress callback to get progress messages
            progress_cb = kwargs.get("progress_callback")

            # Simulate some timestamps
            mock_existing = set([datetime.now() - timedelta(hours=1)])
            mock_missing = set([datetime.now() - timedelta(hours=2)])

            # Call original to get progress messages
            await orig_scan_directory(*args, **kwargs)

            # Return our fixed result
            return mock_existing, mock_missing

        reconcile_manager.scan_directory = mock_scan_directory

        # Execute the method
        await reconcile_manager.reconcile(
            directory=directory,
            satellite=satellite,
            start_time=start_date,
            end_time=end_date,
            interval_minutes=interval_minutes,
            progress_callback=progress_callback,
        )

        # Assertions for phase-based progress reporting
        assert any(
            "Phase 1/2" in msg for msg in progress_messages
        ), "Phase 1 message not found"
        assert any(
            "Phase 2/2" in msg for msg in progress_messages
        ), "Phase 2 message not found"

        # Ensure we have both scan and download phase messages
        assert any(
            "scan" in msg.lower() for msg in progress_messages if "Phase 1" in msg
        )
        assert any(
            "download" in msg.lower() for msg in progress_messages if "Phase 2" in msg
        )

        # Check final completion message
        assert any("Reconciliation complete" in msg for msg in progress_messages)
        assert any(
            "existing" in msg and "downloaded" in msg
            for msg in progress_messages
            if "complete" in msg.lower()
        )

        # Check progressive phase values (should go from 0 to 2)
        phase_values = [phase[0] for phase in progress_phases]
        assert 0 in phase_values, "Phase progression should start from 0"
        assert 1 in phase_values, "Phase progression should include 1"
        assert 2 in phase_values, "Phase progression should end with 2"
