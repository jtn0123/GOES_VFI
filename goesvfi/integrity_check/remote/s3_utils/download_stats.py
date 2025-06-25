"""Download statistics tracking for S3 operations.

This module provides thread-safe statistics tracking for S3 downloads,
replacing the global mutable state with a proper class-based approach.
"""

import random
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional, Union

from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)

# Type aliases
StatsValue = Union[int, float, str, List[Any]]
StatsDict = Dict[str, StatsValue]


@dataclass
class DownloadStats:
    """Container for download statistics."""

    # Basic counters
    total_attempts: int = 0
    successful: int = 0
    failed: int = 0
    retry_count: int = 0

    # Error type counters
    not_found: int = 0
    auth_errors: int = 0
    timeouts: int = 0
    network_errors: int = 0

    # Performance metrics
    download_times: List[float] = field(default_factory=list)
    download_rates: List[float] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    last_success_time: float = 0
    largest_file_size: int = 0
    smallest_file_size: float = float("inf")
    total_bytes: int = 0

    # Recent history
    errors: List[str] = field(default_factory=list)
    recent_attempts: List[Dict[str, Any]] = field(default_factory=list)

    # Session information
    session_id: str = field(default_factory=lambda: f"{int(time.time())}-{random.randint(1000, 9999)}")
    hostname: str = field(default_factory=socket.gethostname)
    start_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class DownloadStatsTracker:
    """Thread-safe tracker for S3 download statistics."""

    def __init__(self, max_errors: int = 20, max_attempts: int = 50) -> None:
        """Initialize the statistics tracker.

        Args:
            max_errors: Maximum number of error messages to keep
            max_attempts: Maximum number of recent attempts to track
        """
        self._stats = DownloadStats()
        self._lock = Lock()
        self._max_errors = max_errors
        self._max_attempts = max_attempts

    def reset(self) -> None:
        """Reset all statistics to initial values."""
        with self._lock:
            self._stats = DownloadStats()

    def update_attempt(
        self,
        success: bool,
        download_time: float = 0,
        file_size: int = 0,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        satellite: Optional[str] = None,
        bucket: Optional[str] = None,
        key: Optional[str] = None,
    ) -> None:
        """Update statistics for a download attempt.

        Args:
            success: Whether the download was successful
            download_time: Time taken for the download in seconds
            file_size: Size of the downloaded file in bytes
            error_type: Type of error if download failed
            error_message: Error message if download failed
            satellite: Satellite name for additional tracking
            bucket: S3 bucket name for additional tracking
            key: S3 key for additional tracking
        """
        with self._lock:
            # Update total attempts
            self._stats.total_attempts += 1

            # Create attempt record
            attempt_record = {
                "timestamp": datetime.now().isoformat(),
                "success": success,
                "download_time": download_time,
                "file_size": file_size,
                "error_type": error_type,
                "satellite": satellite,
                "bucket": bucket,
                "key": key,
            }

            # Update recent attempts list
            if len(self._stats.recent_attempts) >= self._max_attempts:
                self._stats.recent_attempts.pop(0)
            self._stats.recent_attempts.append(attempt_record)

            if success:
                self._update_success_stats(download_time, file_size)
            else:
                self._update_failure_stats(error_type, error_message)

    def _update_success_stats(self, download_time: float, file_size: int) -> None:
        """Update statistics for successful downloads."""
        self._stats.successful += 1
        self._stats.last_success_time = time.time()

        # Update download times
        self._stats.download_times.append(download_time)
        if len(self._stats.download_times) > 100:
            self._stats.download_times = self._stats.download_times[-100:]

        # Update total bytes
        self._stats.total_bytes += file_size

        # Update file size stats
        if file_size > self._stats.largest_file_size:
            self._stats.largest_file_size = file_size
        if file_size < self._stats.smallest_file_size:
            self._stats.smallest_file_size = file_size

        # Calculate and store download rate
        if download_time > 0:
            download_rate = file_size / download_time
            self._stats.download_rates.append(download_rate)
            if len(self._stats.download_rates) > 100:
                self._stats.download_rates = self._stats.download_rates[-100:]

    def _update_failure_stats(self, error_type: Optional[str], error_message: Optional[str]) -> None:
        """Update statistics for failed downloads."""
        self._stats.failed += 1

        # Update error type counters
        if error_type:
            error_counter_map = {
                "not_found": "not_found",
                "auth": "auth_errors",
                "timeout": "timeouts",
                "network": "network_errors",
            }
            if error_type in error_counter_map:
                setattr(
                    self._stats,
                    error_counter_map[error_type],
                    getattr(self._stats, error_counter_map[error_type]) + 1,
                )

        # Update error messages list
        if error_message:
            formatted_error = f"[{datetime.now().isoformat()}] {error_type or 'unknown'}: {error_message}"
            if len(self._stats.errors) >= self._max_errors:
                self._stats.errors.pop(0)
            self._stats.errors.append(formatted_error)

    def increment_retry(self) -> None:
        """Increment the retry counter."""
        with self._lock:
            self._stats.retry_count += 1

    def get_stats(self) -> DownloadStats:
        """Get a copy of the current statistics.

        Returns:
            Copy of current download statistics
        """
        with self._lock:
            # Create a shallow copy to avoid modifying the original
            return DownloadStats(
                total_attempts=self._stats.total_attempts,
                successful=self._stats.successful,
                failed=self._stats.failed,
                retry_count=self._stats.retry_count,
                not_found=self._stats.not_found,
                auth_errors=self._stats.auth_errors,
                timeouts=self._stats.timeouts,
                network_errors=self._stats.network_errors,
                download_times=list(self._stats.download_times),
                download_rates=list(self._stats.download_rates),
                start_time=self._stats.start_time,
                last_success_time=self._stats.last_success_time,
                largest_file_size=self._stats.largest_file_size,
                smallest_file_size=self._stats.smallest_file_size,
                total_bytes=self._stats.total_bytes,
                errors=list(self._stats.errors),
                recent_attempts=list(self._stats.recent_attempts),
                session_id=self._stats.session_id,
                hostname=self._stats.hostname,
                start_timestamp=self._stats.start_timestamp,
            )

    def get_metrics(self) -> Dict[str, Any]:
        """Calculate and return download metrics.

        Returns:
            Dictionary containing calculated metrics
        """
        with self._lock:
            total_attempts = self._stats.total_attempts
            successful = self._stats.successful

            if total_attempts == 0:
                return {
                    "total_attempts": 0,
                    "successful": 0,
                    "success_rate": 0,
                    "avg_time": 0,
                    "total_bytes": 0,
                    "network_speed": "N/A",
                    "avg_download_rate": "N/A",
                }

            # Calculate average download time
            avg_time = (
                sum(self._stats.download_times) / len(self._stats.download_times) if self._stats.download_times else 0
            )

            # Calculate network speed
            total_time = sum(self._stats.download_times)
            network_speed = "N/A"
            if self._stats.total_bytes > 0 and total_time > 0:
                speed_bps = self._stats.total_bytes / total_time
                network_speed = self._format_bytes_per_second(speed_bps)

            # Calculate average download rate
            avg_download_rate = "N/A"
            if self._stats.download_rates:
                avg_rate_bps = sum(self._stats.download_rates) / len(self._stats.download_rates)
                avg_download_rate = self._format_bytes_per_second(avg_rate_bps)

            return {
                "total_attempts": total_attempts,
                "successful": successful,
                "success_rate": (successful / total_attempts * 100),
                "avg_time": avg_time,
                "total_bytes": self._stats.total_bytes,
                "network_speed": network_speed,
                "avg_download_rate": avg_download_rate,
            }

    def get_error_metrics(self) -> Dict[str, int]:
        """Get error-related metrics.

        Returns:
            Dictionary containing error counts
        """
        with self._lock:
            return {
                "failed": self._stats.failed,
                "retry_count": self._stats.retry_count,
                "not_found": self._stats.not_found,
                "auth_errors": self._stats.auth_errors,
                "timeouts": self._stats.timeouts,
                "network_errors": self._stats.network_errors,
            }

    def should_log_stats(self) -> bool:
        """Check if statistics should be logged based on attempt count.

        Returns:
            True if stats should be logged (every 10 attempts)
        """
        with self._lock:
            return self._stats.total_attempts > 0 and self._stats.total_attempts % 10 == 0

    def should_collect_diagnostics(self) -> bool:
        """Check if network diagnostics should be collected.

        Returns:
            True if diagnostics should be collected (every 5 failures)
        """
        with self._lock:
            return self._stats.failed > 0 and self._stats.failed % 5 == 0

    @staticmethod
    def _format_bytes_per_second(speed_bps: float) -> str:
        """Format bytes per second to human readable string."""
        if speed_bps > 1024 * 1024:
            return f"{speed_bps / 1024 / 1024:.2f} MB/s"
        else:
            return f"{speed_bps / 1024:.2f} KB/s"

    def log_statistics(self) -> None:
        """Log detailed download statistics."""
        stats = self.get_stats()
        metrics = self.get_metrics()
        error_metrics = self.get_error_metrics()

        if metrics["total_attempts"] == 0:
            LOGGER.info("No S3 download attempts recorded yet")
            return

        # Calculate runtime
        total_time = time.time() - stats.start_time

        # Format statistics message
        stats_msg = (
            f"\nS3 Download Statistics:\n"
            f"---------------------\n"
            f"Session ID: {stats.session_id}\n"
            f"Hostname: {stats.hostname}\n"
            f"Start time: {stats.start_timestamp}\n"
            f"\nPerformance Summary:\n"
            f"Total attempts: {metrics['total_attempts']}\n"
            f"Successful: {metrics['successful']} ({metrics['success_rate']:.1f}%)\n"
            f"Failed: {error_metrics['failed']}\n"
            f"Retries: {error_metrics['retry_count']}\n"
            f"Not found errors: {error_metrics['not_found']}\n"
            f"Auth errors: {error_metrics['auth_errors']}\n"
            f"Timeouts: {error_metrics['timeouts']}\n"
            f"Network errors: {error_metrics['network_errors']}\n"
            f"\nDownload Metrics:\n"
            f"Average download time: {metrics['avg_time']:.2f} seconds\n"
            f"Total bytes: {metrics['total_bytes']} bytes\n"
            f"Average network speed: {metrics['network_speed']}\n"
            f"Average download rate: {metrics['avg_download_rate']}\n"
            f"Largest file: {stats.largest_file_size} bytes\n"
            f"Smallest file: {stats.smallest_file_size if stats.smallest_file_size != float('inf') else 'N/A'} bytes\n"
            f"Total runtime: {total_time:.1f} seconds\n"
        )

        # Add recent errors if any
        if stats.errors:
            stats_msg += "\nRecent errors:\n"
            for i, error in enumerate(stats.errors[-5:], 1):
                stats_msg += f"{i}. {error}\n"

        # Add recent attempts if any
        if stats.recent_attempts:
            stats_msg += "\nRecent download attempts:\n"
            for i, attempt in enumerate(stats.recent_attempts[-3:], 1):
                status = "✓ Success" if attempt.get("success") else "✗ Failed"
                file_size = attempt.get("file_size", 0)
                size_str = f"{file_size / 1024:.1f} KB" if file_size > 0 else "N/A"
                download_time = attempt.get("download_time", 0)
                time_str = f"{download_time:.2f}s" if download_time > 0 else "N/A"

                # Format the key for display
                key = attempt.get("key", "N/A")
                if key and len(key) > 40:
                    key_parts = key.split("/")
                    key = f".../{key_parts[-1]}" if key_parts else key

                timestamp = attempt.get("timestamp", "N/A")
                stats_msg += f"{i}. [{timestamp}] {status} - Size: {size_str}, Time: {time_str}, Key: {key}\n"

        # Add time since last successful download
        if stats.last_success_time > 0:
            time_since_last = time.time() - stats.last_success_time
            stats_msg += f"\nTime since last successful download: {time_since_last:.1f} seconds\n"

        LOGGER.info(stats_msg)
