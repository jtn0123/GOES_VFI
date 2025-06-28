"""Download statistics tracking with bounded memory usage."""

from collections import deque
from datetime import UTC, datetime
import time
from typing import Any

from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)


class DownloadStatistics:
    """Thread-safe download statistics with bounded memory usage."""

    def __init__(
        self,
        max_recent_attempts: int = 50,
        max_download_times: int = 100,
        max_download_rates: int = 100,
        max_errors: int = 20,
    ):
        """Initialize statistics with memory bounds.

        Args:
            max_recent_attempts: Maximum recent attempts to track
            max_download_times: Maximum download times to track
            max_download_rates: Maximum download rates to track
            max_errors: Maximum errors to track
        """
        # Basic counters
        self.total_attempts: int = 0
        self.successful: int = 0
        self.failed: int = 0
        self.retry_count: int = 0

        # Error type counters
        self.not_found: int = 0
        self.auth_errors: int = 0
        self.timeouts: int = 0
        self.network_errors: int = 0

        # Performance metrics with bounded collections
        self.download_times: deque[float] = deque(maxlen=max_download_times)
        self.download_rates: deque[float] = deque(maxlen=max_download_rates)

        # Timing
        self.start_time: float = time.time()
        self.last_success_time: float = 0

        # File size tracking
        self.largest_file_size: int = 0
        self.smallest_file_size: float = float("inf")
        self.total_bytes: int = 0

        # History with bounded collections
        self.errors: deque[str] = deque(maxlen=max_errors)
        self.recent_attempts: deque[dict[str, Any]] = deque(maxlen=max_recent_attempts)

        # Session information
        import random
        import socket
        self.session_id: str = f"{int(time.time())}-{random.randint(1000, 9999)}"
        self.hostname: str = socket.gethostname()
        self.start_timestamp: str = datetime.now(UTC).isoformat()

    def add_attempt(
        self,
        success: bool,
        download_time: float = 0,
        file_size: int = 0,
        error_type: str | None = None,
        error_message: str | None = None,
        satellite: str | None = None,
        bucket: str | None = None,
        key: str | None = None,
    ) -> None:
        """Add a download attempt to statistics.

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
        # Create attempt record with timestamp
        timestamp = datetime.now(UTC).isoformat()
        attempt_record: dict[str, Any] = {
            "timestamp": timestamp,
            "success": success,
            "download_time": download_time,
            "file_size": file_size,
            "error_type": error_type,
            "satellite": satellite,
            "bucket": bucket,
            "key": key,
        }

        # Add to recent attempts (automatically bounded by deque)
        self.recent_attempts.append(attempt_record)

        # Update counters
        self.total_attempts += 1

        if success:
            self.successful += 1

            # Add performance metrics (automatically bounded by deque)
            self.download_times.append(download_time)
            self.last_success_time = time.time()
            self.total_bytes += file_size

            # Calculate and store download rate
            if download_time > 0 and file_size > 0:
                download_rate = file_size / download_time  # bytes per second
                self.download_rates.append(download_rate)

            # Update file size statistics
            self.largest_file_size = max(self.largest_file_size, file_size)
            self.smallest_file_size = min(self.smallest_file_size, file_size)
        else:
            self.failed += 1

            # Update error type counters
            if error_type == "not_found":
                self.not_found += 1
            elif error_type == "auth":
                self.auth_errors += 1
            elif error_type == "timeout":
                self.timeouts += 1
            elif error_type == "network":
                self.network_errors += 1

            # Add error message with timestamp formatting
            if error_message:
                formatted_error = self._format_error_message(error_type or "unknown", error_message)
                self.errors.append(formatted_error)

    def _format_error_message(self, error_type: str, error_message: str) -> str:
        """Format error message with consistent structure."""
        timestamp = datetime.now(UTC).isoformat()

        # Ensure error_type is not duplicated
        if error_message.startswith(f"{error_type}:"):
            return f"[{timestamp}] {error_message}"
        return f"[{timestamp}] {error_type}: {error_message}"

    def get_statistics_dict(self) -> dict[str, Any]:
        """Get statistics as dictionary for backward compatibility."""
        return {
            # Basic counters
            "total_attempts": self.total_attempts,
            "successful": self.successful,
            "failed": self.failed,
            "retry_count": self.retry_count,
            # Error type counters
            "not_found": self.not_found,
            "auth_errors": self.auth_errors,
            "timeouts": self.timeouts,
            "network_errors": self.network_errors,
            # Performance metrics (convert deque to list)
            "download_times": list(self.download_times),
            "download_rates": list(self.download_rates),
            # Timing
            "start_time": self.start_time,
            "last_success_time": self.last_success_time,
            # File size tracking
            "largest_file_size": self.largest_file_size,
            "smallest_file_size": self.smallest_file_size,
            "total_bytes": self.total_bytes,
            # History (convert deque to list)
            "errors": list(self.errors),
            "recent_attempts": list(self.recent_attempts),
            # Session information
            "session_id": self.session_id,
            "hostname": self.hostname,
            "start_timestamp": self.start_timestamp,
        }

    def log_statistics(self) -> None:
        """Log current download statistics."""
        try:
            # Basic stats
            success_rate = (self.successful / self.total_attempts * 100) if self.total_attempts > 0 else 0

            # Average download time
            avg_download_time = sum(self.download_times) / len(self.download_times) if self.download_times else 0

            # Average download rate
            avg_download_rate = sum(self.download_rates) / len(self.download_rates) if self.download_rates else 0

            # Format download rate
            if avg_download_rate > 1024 * 1024:
                rate_str = f"{avg_download_rate / 1024 / 1024:.2f} MB/s"
            else:
                rate_str = f"{avg_download_rate / 1024:.2f} KB/s"

            # Format total bytes
            if self.total_bytes > 1024 * 1024 * 1024:
                bytes_str = f"{self.total_bytes / 1024 / 1024 / 1024:.2f} GB"
            elif self.total_bytes > 1024 * 1024:
                bytes_str = f"{self.total_bytes / 1024 / 1024:.2f} MB"
            else:
                bytes_str = f"{self.total_bytes / 1024:.2f} KB"

            # Session duration
            session_duration = time.time() - self.start_time
            duration_str = f"{session_duration / 60:.1f} minutes" if session_duration > 60 else f"{session_duration:.1f} seconds"

            log_lines = [
                "Download Statistics Summary:",
                f"  Session: {self.session_id} ({duration_str})",
                f"  Total attempts: {self.total_attempts}",
                f"  Success rate: {success_rate:.1f}% ({self.successful}/{self.total_attempts})",
                f"  Failed: {self.failed} (not_found: {self.not_found}, timeouts: {self.timeouts}, "
                f"auth: {self.auth_errors}, network: {self.network_errors})",
                f"  Average download time: {avg_download_time:.2f}s",
                f"  Average download rate: {rate_str}",
                f"  Total bytes downloaded: {bytes_str}",
                f"  Memory usage: {len(self.download_times)} download times, "
                f"{len(self.download_rates)} rates, {len(self.errors)} errors tracked",
            ]

            # Recent errors
            if self.errors:
                log_lines.append(f"  Recent errors: {len(self.errors)} (last: {list(self.errors)[-1]})")

            LOGGER.info("\n".join(log_lines))

        except Exception as e:
            LOGGER.exception("Error logging download statistics: %s", e)

    def reset(self) -> None:
        """Reset all statistics."""
        self.__init__(
            max_recent_attempts=self.recent_attempts.maxlen,
            max_download_times=self.download_times.maxlen,
            max_download_rates=self.download_rates.maxlen,
            max_errors=self.errors.maxlen,
        )


# Global instance for backward compatibility
_global_stats: DownloadStatistics | None = None


def get_global_stats() -> DownloadStatistics:
    """Get or create global statistics instance."""
    global _global_stats
    if _global_stats is None:
        _global_stats = DownloadStatistics()
    return _global_stats


def reset_global_stats() -> None:
    """Reset global statistics instance."""
    global _global_stats
    _global_stats = None
