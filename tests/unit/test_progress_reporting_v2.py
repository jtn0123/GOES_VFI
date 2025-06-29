"""
Unit tests for the enhanced progress reporting functionality (Optimized v2).

This module tests the enhanced progress reporting capabilities of the
ReconcileManager, ensuring proper step-based and phase-based progress
messages are generated.

Optimizations:
- Mock asyncio.sleep to eliminate wait times
- Shared fixtures for common test objects
- Parameterized tests for similar scenarios
- Consolidated progress verification methods
- Reduced test data sizes for faster execution
"""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from goesvfi.integrity_check.cache_db import CacheDB
from goesvfi.integrity_check.reconcile_manager import ReconcileManager
from goesvfi.integrity_check.time_index import SatellitePattern


@pytest.fixture()
def mock_async_operations():
    """Mock async operations to eliminate wait times."""
    with patch("asyncio.sleep", return_value=None):
        yield


@pytest.fixture()
def mock_cache_db():
    """Create a comprehensive mock CacheDB for testing."""
    mock_db = AsyncMock(spec=CacheDB)
    # Configure mock behavior
    mock_db.get_timestamps.return_value = set()
    mock_db.add_timestamp.return_value = None
    mock_db.close.return_value = None
    return mock_db


@pytest.fixture()
def mock_stores():
    """Create mock CDN and S3 stores for testing."""
    # Mock CDN store
    mock_cdn_store = AsyncMock()
    mock_cdn_store.__aenter__.return_value = mock_cdn_store
    mock_cdn_store.__aexit__.return_value = None
    mock_cdn_store.exists.return_value = False
    mock_cdn_store.download.return_value = Path("/fake/path/image.png")

    # Mock S3 store
    mock_s3_store = AsyncMock()
    mock_s3_store.__aenter__.return_value = mock_s3_store
    mock_s3_store.__aexit__.return_value = None
    mock_s3_store.exists.return_value = False
    mock_s3_store.download.return_value = Path("/fake/path/image.nc")

    return mock_cdn_store, mock_s3_store


@pytest.fixture()
def reconcile_manager(mock_cache_db, mock_stores):
    """Create a ReconcileManager instance for testing."""
    mock_cdn_store, mock_s3_store = mock_stores
    return ReconcileManager(
        cache_db=mock_cache_db,
        base_dir="/fake/path",
        cdn_store=mock_cdn_store,
        s3_store=mock_s3_store,
        max_concurrency=1,  # Use 1 for predictable testing
    )


@pytest.fixture()
def test_date_ranges():
    """Create test date ranges for different scenarios."""
    now = datetime.now()
    return {
        "short_range": (now - timedelta(hours=2), now),
        "day_range": (now - timedelta(days=1), now),
        "week_range": (now - timedelta(days=7), now),
    }


@pytest.fixture()
def progress_collector():
    """Create a progress collector for testing."""

    class ProgressCollector:
        def __init__(self) -> None:
            self.messages = []
            self.steps = []

        def callback(self, current, total, message) -> None:
            self.messages.append(message)
            self.steps.append((current, total))

        def has_step_pattern(self, pattern):
            """Check if any message contains the step pattern."""
            return any(pattern in msg for msg in self.messages)

        def get_step_values(self):
            """Get all step current values."""
            return [step[0] for step in self.steps]

        def has_message_containing(self, text):
            """Check if any message contains the text."""
            return any(text in msg for msg in self.messages)

    return ProgressCollector()


class TestProgressReporting:
    """Test suite for the enhanced progress reporting functionality."""

    @pytest.mark.asyncio()
    async def test_scan_directory_progress_structure(
        self, mock_async_operations, reconcile_manager, test_date_ranges, progress_collector, tmp_path
    ) -> None:
        """Test the overall structure of scan_directory progress reporting."""
        start_date, end_date = test_date_ranges["short_range"]
        satellite = SatellitePattern.GOES_16
        interval_minutes = 30

        # Execute the method
        await reconcile_manager.scan_directory(
            directory=tmp_path,
            satellite=satellite,
            start_time=start_date,
            end_time=end_date,
            interval_minutes=interval_minutes,
            progress_callback=progress_collector.callback,
        )

        # Verify step-based progress structure
        expected_steps = ["Step 1/5", "Step 2/5", "Step 3/5", "Step 4/5", "Step 5/5"]
        for step in expected_steps:
            assert progress_collector.has_step_pattern(step), f"{step} message not found"

    @pytest.mark.parametrize(
        "step_info",
        [
            ("Step 1/5", "Generating expected timestamps"),
            ("Step 2/5", "Checking cache"),
            ("Step 3/5", "Checking filesystem"),
            ("Step 4/5", "Finalizing"),
            ("Step 5/5", "Scan complete"),
        ],
    )
    @pytest.mark.asyncio()
    async def test_scan_directory_step_content(
        self, mock_async_operations, reconcile_manager, test_date_ranges, progress_collector, tmp_path, step_info
    ) -> None:
        """Test specific step content in scan_directory progress reporting."""
        step_pattern, content_text = step_info
        start_date, end_date = test_date_ranges["short_range"]

        await reconcile_manager.scan_directory(
            directory=tmp_path,
            satellite=SatellitePattern.GOES_16,
            start_time=start_date,
            end_time=end_date,
            interval_minutes=30,
            progress_callback=progress_collector.callback,
        )

        # Verify both step pattern and content
        assert progress_collector.has_step_pattern(step_pattern)
        assert progress_collector.has_message_containing(content_text)

    @pytest.mark.asyncio()
    async def test_scan_directory_progress_sequence(
        self, mock_async_operations, reconcile_manager, test_date_ranges, progress_collector, tmp_path
    ) -> None:
        """Test that progress sequence is logical and complete."""
        start_date, end_date = test_date_ranges["short_range"]

        await reconcile_manager.scan_directory(
            directory=tmp_path,
            satellite=SatellitePattern.GOES_16,
            start_time=start_date,
            end_time=end_date,
            interval_minutes=30,
            progress_callback=progress_collector.callback,
        )

        # Check progressive step numbers
        step_values = progress_collector.get_step_values()

        # Should start from 0 and progress to 5
        assert 0 in step_values, "Progress reporting should start from step 0"
        assert 5 in step_values, "Progress reporting should end with step 5"

        # Should have a reasonable progression
        unique_steps = sorted(set(step_values))
        assert len(unique_steps) >= 3, "Should have multiple distinct progress steps"

    @pytest.mark.asyncio()
    async def test_fetch_missing_files_progress_structure(
        self, mock_async_operations, reconcile_manager, mock_stores, progress_collector
    ) -> None:
        """Test fetch_missing_files progress reporting structure."""
        _mock_cdn_store, _mock_s3_store = mock_stores

        # Create test timestamps (mix of recent and old)
        now = datetime.now()

        # Add recent timestamps (for CDN)
        mock_timestamps = [now - timedelta(hours=i) for i in range(2)]

        # Add older timestamps (for S3)
        mock_timestamps.extend(now - timedelta(days=30) - timedelta(hours=i) for i in range(2))

        # Mock the _is_recent method
        async def mock_is_recent(ts):
            return (now - ts) < timedelta(days=7)

        reconcile_manager._is_recent = mock_is_recent

        # Configure store mocks
        reconcile_manager.cdn_store.exists.return_value = True
        reconcile_manager.s3_store.exists.return_value = True

        # Execute the method
        await reconcile_manager.fetch_missing_files(
            missing_timestamps=mock_timestamps,
            satellite=SatellitePattern.GOES_16,
            destination_dir="/fake/destination",
            progress_callback=progress_collector.callback,
        )

        # Verify step-based progress structure
        expected_steps = ["Step 1/4", "Step 2/4", "Step 3/4", "Step 4/4"]
        for step in expected_steps:
            assert progress_collector.has_step_pattern(step), f"{step} message not found"

    @pytest.mark.parametrize(
        "content_check",
        [
            "Analyzing missing files",
            "Preparing download strategy",
            "from CDN",
            "from S3",
            "Download complete",
        ],
    )
    @pytest.mark.asyncio()
    async def test_fetch_missing_files_content(
        self, mock_async_operations, reconcile_manager, progress_collector, content_check
    ) -> None:
        """Test specific content in fetch_missing_files progress messages."""
        # Setup minimal test data
        now = datetime.now()
        mock_timestamps = [now - timedelta(hours=1), now - timedelta(days=30)]

        async def mock_is_recent(ts):
            return (now - ts) < timedelta(days=7)

        reconcile_manager._is_recent = mock_is_recent
        reconcile_manager.cdn_store.exists.return_value = True
        reconcile_manager.s3_store.exists.return_value = True

        await reconcile_manager.fetch_missing_files(
            missing_timestamps=mock_timestamps,
            satellite=SatellitePattern.GOES_16,
            destination_dir="/fake/destination",
            progress_callback=progress_collector.callback,
        )

        # Check for specific content
        assert progress_collector.has_message_containing(content_check)

    @pytest.mark.asyncio()
    async def test_reconcile_phase_based_progress_structure(
        self, mock_async_operations, reconcile_manager, test_date_ranges, progress_collector, tmp_path
    ) -> None:
        """Test phase-based progress reporting in the reconcile method."""
        start_date, end_date = test_date_ranges["short_range"]
        satellite = SatellitePattern.GOES_16

        # Configure mocks for reconcile method
        reconcile_manager.cdn_store.exists.return_value = True
        reconcile_manager._is_recent = AsyncMock(return_value=True)

        # Mock scan_directory to return controlled results

        async def mock_scan_directory(*args, **kwargs):
            # Call progress callback if provided
            progress_callback = kwargs.get("progress_callback")
            if progress_callback:
                progress_callback(1, 5, "Step 1/5: Mock scanning")
                progress_callback(5, 5, "Step 5/5: Mock scan complete")

            # Return mock results
            mock_existing = {datetime.now() - timedelta(hours=1)}
            mock_missing = {datetime.now() - timedelta(hours=2)}
            return mock_existing, mock_missing

        reconcile_manager.scan_directory = mock_scan_directory

        # Execute the method
        await reconcile_manager.reconcile(
            directory=tmp_path,
            satellite=satellite,
            start_time=start_date,
            end_time=end_date,
            interval_minutes=30,
            progress_callback=progress_collector.callback,
        )

        # Verify phase-based progress structure
        assert progress_collector.has_step_pattern("Phase 1/2"), "Phase 1 message not found"
        assert progress_collector.has_step_pattern("Phase 2/2"), "Phase 2 message not found"

    @pytest.mark.parametrize(
        "phase_content",
        [
            ("Phase 1", "scan"),
            ("Phase 2", "download"),
        ],
    )
    @pytest.mark.asyncio()
    async def test_reconcile_phase_content(
        self, mock_async_operations, reconcile_manager, test_date_ranges, progress_collector, tmp_path, phase_content
    ) -> None:
        """Test phase content in reconcile progress messages."""
        phase_pattern, content_text = phase_content
        start_date, end_date = test_date_ranges["short_range"]

        # Setup mocks
        reconcile_manager.cdn_store.exists.return_value = True
        reconcile_manager._is_recent = AsyncMock(return_value=True)

        async def mock_scan_directory(*args, **kwargs):
            progress_callback = kwargs.get("progress_callback")
            if progress_callback:
                progress_callback(5, 5, "Mock scan complete")
            return set(), {datetime.now()}

        reconcile_manager.scan_directory = mock_scan_directory

        await reconcile_manager.reconcile(
            directory=tmp_path,
            satellite=SatellitePattern.GOES_16,
            start_time=start_date,
            end_time=end_date,
            interval_minutes=30,
            progress_callback=progress_collector.callback,
        )

        # Check for phase pattern and content
        phase_messages = [msg for msg in progress_collector.messages if phase_pattern in msg]
        assert any(content_text.lower() in msg.lower() for msg in phase_messages), (
            f"Phase {phase_pattern} should contain '{content_text}'"
        )

    @pytest.mark.asyncio()
    async def test_reconcile_completion_message(
        self, mock_async_operations, reconcile_manager, test_date_ranges, progress_collector, tmp_path
    ) -> None:
        """Test final completion message in reconcile method."""
        start_date, end_date = test_date_ranges["short_range"]

        # Setup mocks for completion scenario
        reconcile_manager.cdn_store.exists.return_value = True
        reconcile_manager._is_recent = AsyncMock(return_value=True)

        async def mock_scan_directory(*args, **kwargs):
            return {datetime.now()}, {datetime.now() - timedelta(hours=1)}

        reconcile_manager.scan_directory = mock_scan_directory

        await reconcile_manager.reconcile(
            directory=tmp_path,
            satellite=SatellitePattern.GOES_16,
            start_time=start_date,
            end_time=end_date,
            interval_minutes=30,
            progress_callback=progress_collector.callback,
        )

        # Check final completion message
        assert progress_collector.has_message_containing("Reconciliation complete")

        # Should mention both existing and downloaded files
        completion_messages = [msg for msg in progress_collector.messages if "complete" in msg.lower()]
        assert any("existing" in msg and "downloaded" in msg for msg in completion_messages)

    @pytest.mark.asyncio()
    async def test_progress_sequence_integrity(
        self, mock_async_operations, reconcile_manager, test_date_ranges, progress_collector, tmp_path
    ) -> None:
        """Test that progress sequences maintain proper ordering and completion."""
        start_date, end_date = test_date_ranges["short_range"]

        # Setup for full reconcile test
        reconcile_manager.cdn_store.exists.return_value = True
        reconcile_manager._is_recent = AsyncMock(return_value=True)

        async def mock_scan_directory(*args, **kwargs):
            progress_callback = kwargs.get("progress_callback")
            if progress_callback:
                for i in range(1, 6):
                    progress_callback(i, 5, f"Step {i}/5: Mock step {i}")
            return {datetime.now()}, {datetime.now() - timedelta(hours=1)}

        reconcile_manager.scan_directory = mock_scan_directory

        await reconcile_manager.reconcile(
            directory=tmp_path,
            satellite=SatellitePattern.GOES_16,
            start_time=start_date,
            end_time=end_date,
            interval_minutes=30,
            progress_callback=progress_collector.callback,
        )

        # Check progressive phase values (should go from 0 to 2)
        phase_values = progress_collector.get_step_values()
        assert 0 in phase_values, "Phase progression should start from 0"
        assert 1 in phase_values, "Phase progression should include 1"
        assert 2 in phase_values, "Phase progression should end with 2"

        # Verify we have both step and phase progress messages
        step_messages = [msg for msg in progress_collector.messages if "Step" in msg]
        phase_messages = [msg for msg in progress_collector.messages if "Phase" in msg]

        assert len(step_messages) > 0, "Should have step-based progress messages"
        assert len(phase_messages) > 0, "Should have phase-based progress messages"

    @pytest.mark.parametrize(
        "satellite",
        [
            SatellitePattern.GOES_16,
            SatellitePattern.GOES_18,
        ],
    )
    @pytest.mark.asyncio()
    async def test_progress_reporting_with_different_satellites(
        self, mock_async_operations, reconcile_manager, test_date_ranges, satellite, tmp_path
    ) -> None:
        """Test progress reporting works with different satellite patterns."""
        start_date, end_date = test_date_ranges["short_range"]
        collector = progress_collector()

        await reconcile_manager.scan_directory(
            directory=tmp_path,
            satellite=satellite,
            start_time=start_date,
            end_time=end_date,
            interval_minutes=30,
            progress_callback=collector.callback,
        )

        # Should have standard progress structure regardless of satellite
        assert collector.has_step_pattern("Step 1/5")
        assert collector.has_step_pattern("Step 5/5")
        assert len(collector.messages) > 0

    @pytest.mark.asyncio()
    async def test_error_handling_in_progress_reporting(
        self, mock_async_operations, reconcile_manager, test_date_ranges, progress_collector, tmp_path
    ) -> None:
        """Test that progress reporting handles errors gracefully."""
        start_date, end_date = test_date_ranges["short_range"]

        # Mock an operation that will raise an exception
        original_method = reconcile_manager.cache_db.get_timestamps
        reconcile_manager.cache_db.get_timestamps.side_effect = Exception("Mock database error")

        try:
            await reconcile_manager.scan_directory(
                directory=tmp_path,
                satellite=SatellitePattern.GOES_16,
                start_time=start_date,
                end_time=end_date,
                interval_minutes=30,
                progress_callback=progress_collector.callback,
            )
        except Exception:
            # Exception is expected, but progress should still have been reported
            pass

        # Should have at least started progress reporting before the error
        assert len(progress_collector.messages) > 0, "Should have some progress messages even with errors"

        # Restore original method
        reconcile_manager.cache_db.get_timestamps = original_method
