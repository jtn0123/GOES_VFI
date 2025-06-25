import time
from unittest.mock import patch

import pytest

from goesvfi.integrity_check.remote import s3_store
from goesvfi.integrity_check.remote.s3_store import (
    log_download_statistics,
    update_download_stats,
)


@pytest.fixture(autouse=True)
def reset_stats():
    s3_store.DOWNLOAD_STATS.clear()
    s3_store.DOWNLOAD_STATS.update(
        {
            "total_attempts": 0,
            "successful": 0,
            "failed": 0,
            "retry_count": 0,
            "not_found": 0,
            "auth_errors": 0,
            "timeouts": 0,
            "network_errors": 0,
            "download_times": [],
            "download_rates": [],
            "start_time": time.time(),
            "last_success_time": 0,
            "largest_file_size": 0,
            "smallest_file_size": float("inf"),
            "total_bytes": 0,
            "errors": [],
        }
    )
    yield


@pytest.mark.parametrize("success,error_type", [(True, None), (False, "timeout")])
def test_update_download_stats_basic(success, error_type):
    update_download_stats(
        success=success,
        download_time=1.0,
        file_size=100,
        error_type=error_type,
        error_message="err" if error_type else None,
    )
    assert s3_store.DOWNLOAD_STATS["total_attempts"] == 1
    if success:
        assert s3_store.DOWNLOAD_STATS["successful"] == 1
    else:
        assert s3_store.DOWNLOAD_STATS["failed"] == 1


def test_error_history_limit():
    for i in range(25):
        update_download_stats(success=False, error_type="network", error_message=f"e{i}")
    assert len(s3_store.DOWNLOAD_STATS["errors"]) == 20


def test_log_download_statistics(caplog):
    update_download_stats(success=True, download_time=1.0, file_size=50)
    with patch("goesvfi.integrity_check.remote.s3_store.LOGGER.info") as mock_log:
        log_download_statistics()
        mock_log.assert_called_once()
