from unittest.mock import patch

import pytest

from goesvfi.integrity_check.remote.download_statistics import reset_global_stats
from goesvfi.integrity_check.remote.s3_store import (
    get_download_stats,
    log_download_statistics,
    update_download_stats,
)


@pytest.fixture(autouse=True)
def reset_stats() -> None:
    """Reset global statistics before each test."""
    reset_global_stats()


@pytest.mark.parametrize("success,error_type", [(True, None), (False, "timeout")])
def test_update_download_stats_basic(success, error_type) -> None:
    """Test basic download statistics tracking."""
    update_download_stats(
        success=success,
        download_time=1.0,
        file_size=100,
        error_type=error_type,
        error_message="err" if error_type else None,
    )
    stats = get_download_stats()
    assert stats.total_attempts == 1
    if success:
        assert stats.successful == 1
    else:
        assert stats.failed == 1


def test_error_history_limit() -> None:
    """Test that error history is bounded to prevent memory leaks."""
    for i in range(25):
        update_download_stats(success=False, error_type="network", error_message=f"e{i}")
    stats = get_download_stats()
    # Errors are limited to 20 (default maxlen)
    assert len(stats.errors) == 20
    # Should contain the most recent errors
    assert "e24" in stats.errors[-1]  # Most recent error


def test_download_times_bounded() -> None:
    """Test that download times are bounded to prevent memory leaks."""
    # Add more download times than the limit (100)
    for i in range(150):
        update_download_stats(success=True, download_time=float(i), file_size=100)

    stats = get_download_stats()
    # Download times should be bounded to max_download_times (100)
    assert len(stats.download_times) == 100
    # Should contain the most recent download times
    assert 149.0 in stats.download_times  # Most recent


def test_recent_attempts_bounded() -> None:
    """Test that recent attempts are bounded to prevent memory leaks."""
    # Add more attempts than the limit (50)
    for i in range(75):
        update_download_stats(success=True, download_time=1.0, file_size=100, satellite=f"sat{i}")

    stats = get_download_stats()
    # Recent attempts should be bounded to max_recent_attempts (50)
    assert len(stats.recent_attempts) == 50
    # Should contain the most recent attempts
    recent_satellites = [attempt.get("satellite") for attempt in stats.recent_attempts]
    assert "sat74" in recent_satellites  # Most recent


def test_log_download_statistics(caplog) -> None:
    """Test statistics logging functionality."""
    update_download_stats(success=True, download_time=1.0, file_size=50)
    with patch("goesvfi.integrity_check.remote.s3_store.LOGGER.info") as mock_log:
        log_download_statistics()
        mock_log.assert_called()  # Should be called (new class has its own logging)
